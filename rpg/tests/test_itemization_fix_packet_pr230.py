"""Defect-specific acceptance coverage for the PR230 Astra fix packet."""

from __future__ import annotations

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from database import create_player, get_connection, get_player
from game.action_receipts import issue_actions
from game.combat import init_battle, process_turn
from game.equipment_stats import get_equipped_item_ids, get_player_effective_stats
from game.field_catalog import FIELD_ITEM_IDS, FIELD_WEAPON_IDS, GEAR_CHANCE_BY_SPAWN_PROFILE
from game.gear_instances import (
    create_gear_instance,
    get_equipped_gear_instances,
    grant_item_to_player,
)
from game.gear_progression import (
    apply_gear_intent,
    apply_legacy_gear_intent,
    issue_gear_intent,
    issue_legacy_gear_intent,
    get_equipment_goal,
)
from game.gear_ui import get_field_source_manifest
from game.i18n import t
from game.locations import get_location
from game.mobs import get_mob
from game.pve_live import (
    _SOLO_PVE_RUNTIME_STORE,
    create_or_load_open_world_pve_encounter,
    create_pve_encounter,
    ensure_location_pve_spawn_instances,
    ensure_runtime_for_battle,
    join_open_world_pve_encounter,
    leave_open_world_pve_encounter,
    load_active_pve_encounter,
    persist_solo_pve_encounter_state,
    reset_solo_pve_runtime_store,
)
from game.pve_reward_settlement import (
    _roll_unit_rewards,
    apply_prepared_settlement,
    get_settlement,
    list_recent_reward_receipts,
    prepare_victory_settlement,
    recover_prepared_settlements,
    recover_player_settlements,
    recover_unprepared_terminal_victories,
    review_ambiguous_legacy_victories,
)
from game.pvp_live import create_live_engagement
from game.quest_board import get_contract_history, get_player_hunt_contract_state
from game.skill_engine import get_battle_skills
from game.skills import get_available_skills
from game.weapon_mastery import get_mastery, upgrade_skill
from handlers import battle as battle_handler
from handlers.battle import get_equipped_combat_items
from handlers.chapter import (
    build_sell_menu,
    build_workshop,
    handle_chapter_buttons,
    journal_command,
)
from handlers.inventory import (
    INVENTORY_PAGE_SIZE,
    build_gear_comparison,
    build_inventory_list,
    build_item_detail,
    build_recent_gear_receipts,
    build_reward_receipt_detail,
    handle_inventory_buttons,
    make_entry_token,
)
from handlers.location import (
    _find_canonical_path,
    build_craftsmen_advancement_list,
    build_quest_board_message,
    handle_location_buttons,
    try_buy_curated_shop_item,
)
from handlers.location import location_command
from handlers.start import start_command


BASE_PID = 932_000


def _make_player(player_id: int, *, location: str = 'westwild_n3', gold: int = 100_000) -> None:
    create_player(player_id, f'p{player_id}', f'Player {player_id}', {
        'strength': 10, 'agility': 10, 'intuition': 10,
        'vitality': 10, 'wisdom': 10, 'luck': 10,
    }, lang='en')
    conn = get_connection()
    conn.execute(
        'UPDATE players SET location_id=?, gold=?, hp=max_hp, mana=max_mana WHERE telegram_id=?',
        (location, gold, player_id),
    )
    conn.commit()
    conn.close()


def _rows(sql: str, params=()) -> list[dict]:
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _callbacks(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


async def _inventory_callback(player_id: int, data: str):
    query = SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=player_id),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    context = SimpleNamespace(user_data={}, application=SimpleNamespace(user_data={}))
    await handle_inventory_buttons(SimpleNamespace(callback_query=query), context)
    return query


async def _handler_callback(player_id: int, data: str, handler):
    query = SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=player_id),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        message=SimpleNamespace(reply_text=AsyncMock(), message_id=1, chat_id=player_id),
    )
    context = SimpleNamespace(
        user_data={},
        application=SimpleNamespace(
            user_data={player_id: {}},
            create_task=lambda coroutine: coroutine.close(),
        ),
    )
    await handler(
        SimpleNamespace(
            callback_query=query,
            effective_user=query.from_user,
            effective_message=query.message,
        ),
        context,
    )
    return query


def _create_anchored_encounter(
        owner_id: int, *, player_ids: list[int] | None = None, pack: bool = False):
    mob = get_mob('forest_wolf')
    player = dict(get_player(owner_id))
    battle = init_battle(player, mob)
    battle.update({
        'location_id': 'westwild_n3',
        'weapon_id': 'field_bow',
        'weapon_profile': 'bow',
        'weapon_type': 'ranged',
        'weapon_damage': 12,
    })
    spawn_instance_id = None
    if pack:
        ensure_location_pve_spawn_instances(location_id='westwild_n3')
        spawn_instance_id = _rows(
            """SELECT spawn_instance_id FROM pve_spawn_instances
               WHERE location_id='westwild_n3' AND mob_id='forest_wolf' AND state='idle'
               ORDER BY spawn_instance_id LIMIT 1"""
        )[0]['spawn_instance_id']
    encounter_id, status = create_or_load_open_world_pve_encounter(
        owner_player_id=owner_id,
        location_id='westwild_n3',
        mob_id='forest_wolf',
        battle_state=battle,
        mob=mob,
        side_a_player_ids=player_ids or [owner_id],
        spawn_instance_id=spawn_instance_id,
        pack_claim_from_visible_group=pack,
    )
    assert status == 'created'
    battle['pve_encounter_id'] = encounter_id
    battle.setdefault('side_a_player_ids', list(player_ids or [owner_id]))
    return str(encounter_id), battle, mob


def _terminalize_anchored(encounter_id: str, battle: dict, mob: dict) -> None:
    ensure_runtime_for_battle(player_id=int(battle['side_a_player_ids'][0]), battle_state=battle, mob=mob)
    source = json.loads(_rows(
        'SELECT source_units_json FROM pve_encounters WHERE encounter_id=?', (encounter_id,)
    )[0]['source_units_json'])
    if not source.get('uses_enemy_units'):
        battle.pop('enemy_units', None)
        battle['mob_hp'] = 0
        battle['mob_dead'] = True
        persist_solo_pve_encounter_state(
            encounter_id=encounter_id, battle_state=battle, mob=mob)
        return
    spawn_rows = _rows(
        '''SELECT spawn_instance_id, mob_id, spawn_profile, special_spawn_key
           FROM pve_spawn_instances WHERE linked_encounter_id=? ORDER BY spawn_instance_id''',
        (encounter_id,),
    )
    assert spawn_rows
    existing = {
        str(unit.get('spawn_instance_id')): dict(unit)
        for unit in battle.get('enemy_units', [])
        if unit.get('spawn_instance_id')
    }
    units = []
    for index, spawn in enumerate(spawn_rows, start=1):
        unit = existing.get(str(spawn['spawn_instance_id']), {})
        unit.update({
            'unit_id': str(unit.get('unit_id') or f'unit-{index}'),
            'spawn_instance_id': str(spawn['spawn_instance_id']),
            'mob_id': str(spawn['mob_id']),
            'spawn_profile': str(spawn['spawn_profile']),
            'special_spawn_key': spawn['special_spawn_key'],
            'hp': 0,
            'dead': True,
        })
        units.append(unit)
    battle['enemy_units'] = units
    battle['mob_hp'] = 0
    battle['mob_dead'] = True
    persist_solo_pve_encounter_state(
        encounter_id=encounter_id, battle_state=battle, mob=mob)


def _equip_test_weapon(player_id: int, item_id: str) -> int:
    instance_id = create_gear_instance(player_id, item_id)
    token = issue_gear_intent(player_id, 'equip', instance_id, target_slot='weapon')
    assert apply_gear_intent(player_id, 'equip', token)['status'] == 'equipped'
    return instance_id


def _run_group_battle_handlers_to_settlement(
        encounter_id: str, *, restart_after_round: int = 1) -> int:
    """Drive the shared encounter exclusively through participant callbacks."""
    final_actor = 0
    restarted = False
    for round_index in range(30):
        active_ids = [
            row['player_id'] for row in _rows(
                """SELECT player_id FROM pve_encounter_participants
                   WHERE encounter_id=? AND status='active'
                   ORDER BY joined_at, player_id""",
                (encounter_id,),
            )
        ]
        assert active_ids
        for actor_id in active_ids:
            loaded = load_active_pve_encounter(encounter_id=encounter_id)
            assert loaded is not None
            battle, mob = loaded
            context = SimpleNamespace(
                user_data={'battle': battle, 'battle_mob': mob},
                application=SimpleNamespace(user_data={actor_id: {}}),
            )
            query = SimpleNamespace(
                data=f"battle_attack_{mob['id']}",
                from_user=SimpleNamespace(id=actor_id),
                answer=AsyncMock(),
                edit_message_text=AsyncMock(),
            )
            asyncio.run(battle_handler.handle_battle_buttons(
                SimpleNamespace(callback_query=query), context))
            if get_settlement(encounter_id):
                final_actor = actor_id
                return final_actor
        if round_index + 1 == restart_after_round and not restarted:
            reset_solo_pve_runtime_store()
            restarted = True
            assert load_active_pve_encounter(encounter_id=encounter_id) is not None
    pytest.fail('real group-runtime journey did not settle')


def _create_terminal_nonanchored(owner_id: int, encounter_id: str, roster: list[int]):
    states = {
        str(player_id): {
            'player_hp': 100,
            'hp': 100,
            'player_dead': False,
            'defeated': False,
            'weapon_id': 'field_bow' if player_id == owner_id else 'field_sword_1h',
        }
        for player_id in roster
    }
    battle = {
        'pve_encounter_id': encounter_id,
        'mob_id': 'contract_test_mob',
        'location_id': 'westwild_n3',
        'mob_hp': 0,
        'mob_dead': True,
        'side_a_player_ids': list(roster),
        'participant_states': states,
        'enemy_units': [{
            'unit_id': 'enemy-1', 'mob_id': 'contract_test_mob',
            'spawn_profile': 'normal', 'hp': 0, 'dead': True,
        }],
    }
    mob = {
        'id': 'contract_test_mob', 'level': 7, 'exp_reward': 9,
        'gold_min': 3, 'gold_max': 3, 'loot_table': [],
    }
    create_pve_encounter(
        owner_player_id=owner_id,
        side_a_player_ids=roster,
        battle_state=battle,
        mob=mob,
        encounter_id=encounter_id,
        location_id='westwild_n3',
    )
    persist_solo_pve_encounter_state(
        encounter_id=encounter_id, battle_state=battle, mob=mob)
    return battle, mob


def test_f1_forming_join_leave_uses_locked_roster_and_owner_weapon(monkeypatch):
    owner, ally, departed = BASE_PID, BASE_PID + 1, BASE_PID + 2
    for player_id in (owner, ally, departed):
        _make_player(player_id)
    encounter_id, battle, mob = _create_anchored_encounter(owner)
    assert join_open_world_pve_encounter(encounter_id=encounter_id, player_id=ally) == (True, 'joined')
    assert join_open_world_pve_encounter(encounter_id=encounter_id, player_id=departed) == (True, 'joined')
    assert leave_open_world_pve_encounter(encounter_id=encounter_id, player_id=departed) == (True, 'left')

    ensure_runtime_for_battle(player_id=owner, battle_state=battle, mob=mob)
    locked = json.loads(_rows(
        'SELECT locked_roster_json FROM pve_encounters WHERE encounter_id=?', (encounter_id,)
    )[0]['locked_roster_json'])['player_ids']
    assert locked == [owner, ally]
    battle['participant_states'][str(owner)]['weapon_id'] = 'field_bow'
    battle['participant_states'][str(ally)]['weapon_id'] = 'field_sword_1h'
    _terminalize_anchored(encounter_id, battle, mob)
    battle['last_actor_player_id'] = ally
    battle['weapon_id'] = 'field_sword_1h'
    persist_solo_pve_encounter_state(encounter_id=encounter_id, battle_state=battle, mob=mob)

    monkeypatch.setitem(GEAR_CHANCE_BY_SPAWN_PROFILE, 'normal', 0.0)
    prepared = prepare_victory_settlement(
        encounter_id=encounter_id, battle_state=battle, mob=mob)
    assert prepared['status'] == 'prepared'
    assert prepared['plan']['eligible_recipient_ids'] == [owner, ally]
    assert departed not in prepared['plan']['eligible_recipient_ids']
    applied = apply_prepared_settlement(encounter_id)['result']
    assert [row['player_id'] for row in applied['recipients']] == [owner, ally]
    assert [row['exp'] for row in applied['recipients']] == [mob['exp_reward'], mob['exp_reward']]
    assert all(mob['gold_min'] <= row['gold'] <= mob['gold_max'] for row in applied['recipients'])
    assert _rows(
        "SELECT player_id,dry_streak FROM player_gear_progress WHERE route_id='route_westwild' ORDER BY player_id"
    ) == [{'player_id': owner, 'dry_streak': 1}, {'player_id': ally, 'dry_streak': 1}]
    assert _rows(
        'SELECT telegram_id,weapon_id,exp FROM weapon_mastery WHERE telegram_id IN (?,?,?) ORDER BY telegram_id',
        (owner, ally, departed),
    ) == [{'telegram_id': owner, 'weapon_id': 'bow', 'exp': 10}]


@pytest.mark.parametrize('defeated_role', ['owner', 'ally'])
def test_f1_defeated_participant_is_excluded_from_every_progression_channel(monkeypatch, defeated_role):
    owner, ally = BASE_PID + 10, BASE_PID + 11
    for player_id in (owner, ally):
        _make_player(player_id)
    encounter_id = f'f1-defeated-{defeated_role}'
    battle, mob = _create_terminal_nonanchored(owner, encounter_id, [owner, ally])
    defeated_id = owner if defeated_role == 'owner' else ally
    survivor_id = ally if defeated_role == 'owner' else owner
    battle['participant_states'][str(defeated_id)].update(
        player_hp=0, hp=0, player_dead=True, defeated=True)
    battle['side_a_player_ids'] = [survivor_id]
    conn = get_connection()
    conn.execute(
        "UPDATE pve_encounter_participants SET status='defeated' WHERE encounter_id=? AND player_id=?",
        (encounter_id, defeated_id),
    )
    conn.commit()
    conn.close()
    persist_solo_pve_encounter_state(encounter_id=encounter_id, battle_state=battle, mob=mob)

    monkeypatch.setitem(GEAR_CHANCE_BY_SPAWN_PROFILE, 'normal', 0.0)
    plan = prepare_victory_settlement(
        encounter_id=encounter_id, battle_state=battle, mob=mob)['plan']
    assert plan['eligible_recipient_ids'] == [survivor_id]
    assert plan['defeated_participant_ids'] == [defeated_id]
    assert plan['owner_mastery']['exp'] == (0 if defeated_role == 'owner' else 10)
    result = apply_prepared_settlement(encounter_id)['result']
    assert [row['player_id'] for row in result['recipients']] == [survivor_id]
    assert not _rows('SELECT * FROM player_gear_progress WHERE player_id=?', (defeated_id,))
    assert get_player(defeated_id)['exp'] == 0
    mastery_rows = _rows(
        'SELECT telegram_id,weapon_id,exp FROM weapon_mastery WHERE telegram_id=?', (owner,))
    assert mastery_rows == ([] if defeated_role == 'owner' else [
        {'telegram_id': owner, 'weapon_id': 'bow', 'exp': 10}])


@pytest.mark.parametrize('defeated_role', ['owner', 'ally'])
def test_r4_real_group_runtime_departure_defeat_restart_and_owner_mastery(
        monkeypatch, defeated_role):
    offset = 300 if defeated_role == 'owner' else 310
    owner, finisher, casualty, departed, unrelated = (
        BASE_PID + offset + index for index in range(5))
    active_allies = [finisher] if defeated_role == 'owner' else [finisher, casualty]
    defeated_id = owner if defeated_role == 'owner' else casualty
    for player_id in (owner, *active_allies, departed, unrelated):
        _make_player(player_id)

    _equip_test_weapon(owner, 'field_bow')
    _equip_test_weapon(finisher, 'field_sword_2h')
    if defeated_role == 'ally':
        _equip_test_weapon(casualty, 'field_daggers')

    encounter_id, battle, mob = _create_anchored_encounter(owner, pack=True)
    for player_id in (*active_allies, departed):
        assert join_open_world_pve_encounter(
            encounter_id=encounter_id, player_id=player_id) == (True, 'joined')
    assert leave_open_world_pve_encounter(
        encounter_id=encounter_id, player_id=departed) == (True, 'left')

    unrelated_id = f'r4-group-unrelated-{defeated_role}'
    unrelated_battle = {
        'pve_encounter_id': unrelated_id, 'mob_id': 'westwild_rabbit',
        'mob_hp': 22, 'mob_dead': False, 'location_id': 'westwild_n3',
        'side_a_player_ids': [unrelated],
    }
    unrelated_mob = get_mob('westwild_rabbit')
    create_pve_encounter(
        owner_player_id=unrelated, side_a_player_ids=[unrelated],
        battle_state=unrelated_battle, mob=unrelated_mob,
        encounter_id=unrelated_id, location_id='westwild_n3',
    )
    unrelated_before = _rows(
        'SELECT status,battle_state_json FROM pve_encounters WHERE encounter_id=?',
        (unrelated_id,),
    )[0]

    conn = get_connection()
    conn.execute('UPDATE players SET hp=1 WHERE telegram_id=?', (defeated_id,))
    conn.execute(
        f"UPDATE players SET in_battle=1 WHERE telegram_id IN ({','.join('?' for _ in [owner, *active_allies])})",
        [owner, *active_allies],
    )
    conn.commit()
    conn.close()
    ensure_runtime_for_battle(player_id=owner, battle_state=battle, mob=mob)
    persist_solo_pve_encounter_state(
        encounter_id=encounter_id, battle_state=battle, mob=mob)
    locked = json.loads(_rows(
        'SELECT locked_roster_json FROM pve_encounters WHERE encounter_id=?',
        (encounter_id,),
    )[0]['locked_roster_json'])['player_ids']
    assert locked == [owner, *active_allies]

    kill_actors = []

    def tracked_process_turn(player, target_mob, state, lang, actor_id, **kwargs):
        hp_before = int(state.get('mob_hp', 0))
        updated = process_turn(player, target_mob, state, lang, actor_id, **kwargs)
        if hp_before > 0 and int(updated.get('mob_hp', 0)) <= 0:
            kill_actors.append(actor_id)
        return updated

    def choose_wounded_then_first_living(*, battle_state):
        states = battle_state.get('participant_states') or {}
        wounded = states.get(str(defeated_id), {})
        if int(wounded.get('player_hp', wounded.get('hp', 0)) or 0) > 0:
            return defeated_id
        for raw_id in battle_state.get('side_a_player_ids', []):
            snapshot = states.get(str(raw_id), {})
            if int(snapshot.get('player_hp', snapshot.get('hp', 0)) or 0) > 0:
                return int(raw_id)
        return None

    monkeypatch.setitem(GEAR_CHANCE_BY_SPAWN_PROFILE, 'normal', 0.0)
    with (
        patch('handlers.battle.process_turn', side_effect=tracked_process_turn),
        patch('handlers.battle.choose_enemy_target_participant_id',
              side_effect=choose_wounded_then_first_living),
        patch('game.combat.random.random', return_value=0.5),
        patch('game.balance.random.randint', return_value=1),
    ):
        final_callback_actor = _run_group_battle_handlers_to_settlement(encounter_id)

    settlement = get_settlement(encounter_id)
    assert settlement['status'] == 'applied'
    assert kill_actors and kill_actors[-1] == finisher
    assert final_callback_actor == finisher
    assert settlement['plan']['eligible_recipient_ids'] == [
        player_id for player_id in [owner, *active_allies]
        if player_id != defeated_id
    ]
    assert settlement['plan']['defeated_participant_ids'] == [defeated_id]
    assert _rows(
        'SELECT status FROM pve_encounter_participants WHERE encounter_id=? AND player_id=?',
        (encounter_id, departed),
    ) == [{'status': 'left'}]
    assert not _rows(
        'SELECT * FROM player_gear_progress WHERE player_id=?', (defeated_id,))
    owner_mastery = _rows(
        'SELECT weapon_id,exp FROM weapon_mastery WHERE telegram_id=?', (owner,))
    assert owner_mastery == ([] if defeated_role == 'owner' else [
        {'weapon_id': 'bow', 'exp': 10}])
    assert not _rows(
        'SELECT * FROM weapon_mastery WHERE telegram_id=?', (finisher,))
    assert _rows(
        'SELECT status,battle_state_json FROM pve_encounters WHERE encounter_id=?',
        (unrelated_id,),
    )[0] == unrelated_before


def test_r4_gear_longevity_and_guild_bridge_use_production_handlers():
    from game.crafting_runtime import LIVE_RECIPE_IDS

    player_id = BASE_PID + 330
    item_id = 'field_sword_1h'
    _make_player(player_id, location='capital_city')
    conn = get_connection()
    conn.executemany(
        'INSERT INTO player_contract_history(player_id,contract_key) VALUES (?,?)',
        [
            (player_id, 'chapter_first_watch'),
            (player_id, 'chapter_caravan'),
            (player_id, 'chapter_outfitter'),
        ],
    )
    conn.commit()
    conn.close()

    buy_token = issue_actions(player_id, 'shop_buy', [item_id])[item_id]
    assert try_buy_curated_shop_item(
        player_id, 'capital_city', 1, item_id, action_token=buy_token)['ok']
    instance = _rows(
        'SELECT * FROM gear_instances WHERE telegram_id=? AND base_item_id=?',
        (player_id, item_id),
    )[0]
    instance_id = instance['id']
    original_rolls = instance['secondary_rolls_json']
    _, detail_markup = build_item_detail(player_id, f'g{instance_id}', 'weapon', 'en')
    equip_callback = next(
        value for value in _callbacks(detail_markup) if value.startswith('inv_gequip_'))
    asyncio.run(_inventory_callback(player_id, equip_callback))
    damage_before = get_equipped_combat_items(player_id)['weapon']['damage_max']

    grant_item_to_player(player_id, 'herb_common', quantity=3)
    grant_item_to_player(player_id, 'wolf_pelt', quantity=1)
    grant_item_to_player(player_id, 'enhance_shard', quantity=8)
    board = build_quest_board_message(
        dict(get_player(player_id)), get_location('capital_city'))[1]
    accept_callback = next(
        value for value in _callbacks(board)
        if value == 'quest_board_accept_chapter_homecoming')
    asyncio.run(_handler_callback(player_id, accept_callback, handle_location_buttons))
    assert get_player_hunt_contract_state(player_id)['contract_key'] == 'chapter_homecoming'

    workshop = build_workshop(dict(get_player(player_id)))[1]
    craft_callbacks = [
        value for value in _callbacks(workshop) if value.startswith('alpha_craft_')]
    craft_callback = craft_callbacks[LIVE_RECIPE_IDS.index('field_tonic')]
    asyncio.run(_handler_callback(player_id, craft_callback, handle_chapter_buttons))

    sellable_rows = _rows(
        """SELECT inv.item_id FROM inventory inv JOIN items i ON i.item_id=inv.item_id
           WHERE inv.telegram_id=? AND i.item_type='material'
             AND i.sell_price>0 AND inv.quantity>0 ORDER BY inv.item_id LIMIT 20""",
        (player_id,),
    )
    sell_markup = build_sell_menu(dict(get_player(player_id)))[1]
    sale_callbacks = [
        value for value in _callbacks(sell_markup) if value.startswith('alpha_sellone_')]
    wolf_index = [row['item_id'] for row in sellable_rows].index('wolf_pelt')
    asyncio.run(_handler_callback(
        player_id, sale_callbacks[wolf_index], handle_chapter_buttons))
    assert get_player_hunt_contract_state(player_id)['status'] == 'completed'

    claim_board = build_quest_board_message(
        dict(get_player(player_id)), get_location('capital_city'))[1]
    claim_callback = next(
        value for value in _callbacks(claim_board)
        if value.startswith('quest_board_claim_'))
    asyncio.run(_handler_callback(player_id, claim_callback, handle_location_buttons))
    assert 'chapter_homecoming' in get_contract_history(player_id)

    _, enhance_markup = build_item_detail(
        player_id, f'g{instance_id}', 'weapon', 'en')
    enhance_callback = next(
        value for value in _callbacks(enhance_markup) if value.startswith('inv_genh_'))
    with patch('game.gear_instances.random.random', return_value=0.0):
        asyncio.run(_inventory_callback(player_id, enhance_callback))
    enhanced = _rows('SELECT * FROM gear_instances WHERE id=?', (instance_id,))[0]
    assert enhanced['enhance_level'] == 1
    assert enhanced['secondary_rolls_json'] == original_rolls
    damage_enhanced = get_equipped_combat_items(player_id)['weapon']['damage_max']
    assert damage_enhanced > damage_before

    exchange_menu = asyncio.run(_handler_callback(
        player_id, 'craftsmen_exchange', handle_location_buttons))
    exchange_markup = exchange_menu.edit_message_text.await_args.kwargs['reply_markup']
    exchange_callback = next(
        value for value in _callbacks(exchange_markup)
        if value.startswith('craftsmen_exchange_apply_'))
    asyncio.run(_handler_callback(player_id, exchange_callback, handle_location_buttons))
    assert _rows(
        "SELECT quantity FROM inventory WHERE telegram_id=? AND item_id='enhancement_crystal'",
        (player_id,),
    ) == [{'quantity': 1}]

    advancement_list = build_craftsmen_advancement_list(
        dict(get_player(player_id)))[1]
    advancement_callback = next(
        value for value in _callbacks(advancement_list)
        if value == f'craftsmen_advance_item_{instance_id}_0')
    advancement_detail = asyncio.run(_handler_callback(
        player_id, advancement_callback, handle_location_buttons))
    advancement_markup = advancement_detail.edit_message_text.await_args.kwargs['reply_markup']
    apply_callback = next(
        value for value in _callbacks(advancement_markup)
        if value.startswith('craftsmen_advance_apply_'))
    asyncio.run(_handler_callback(player_id, apply_callback, handle_location_buttons))

    advanced = _rows('SELECT * FROM gear_instances WHERE id=?', (instance_id,))[0]
    assert advanced['id'] == instance_id
    assert advanced['base_item_id'] == item_id
    assert advanced['item_tier'] == 5
    assert advanced['enhance_level'] == 1
    assert advanced['secondary_rolls_json'] == original_rolls
    damage_advanced = get_equipped_combat_items(player_id)['weapon']['damage_max']
    assert damage_advanced > damage_enhanced


@pytest.mark.parametrize(('mutation', 'reason'), [
    ('living', 'terminal_living_unit'),
    ('renamed', 'terminal_source_units_mismatch'),
    ('extra', 'terminal_source_units_mismatch'),
    ('duplicate', 'terminal_unit_identity_mismatch'),
    ('removed', 'terminal_source_units_mismatch'),
    ('mismatched', 'terminal_source_units_mismatch'),
    ('profile', 'terminal_source_units_mismatch'),
    ('substituted', 'terminal_source_units_mismatch'),
    ('location', 'terminal_source_units_mismatch'),
    ('special_key', 'terminal_source_units_mismatch'),
    ('special_name', 'terminal_source_units_mismatch'),
])
def test_f2_authoritative_terminal_validation_rejects_tampered_units(mutation, reason):
    owner = BASE_PID + 20
    _make_player(owner)
    encounter_id, battle, mob = _create_anchored_encounter(owner, pack=True)
    _terminalize_anchored(encounter_id, battle, mob)
    player_before = dict(get_player(owner))
    progress_before = _rows('SELECT * FROM player_gear_progress WHERE player_id=?', (owner,))
    unit = battle['enemy_units'][0]
    if mutation == 'living':
        unit.update(dead=False, hp=1)
    elif mutation == 'renamed':
        unit['unit_id'] = 'invented-unit'
    elif mutation == 'extra':
        extra = copy.deepcopy(unit)
        extra.update(unit_id='enemy-extra', spawn_instance_id='spawn-unproven')
        battle['enemy_units'].append(extra)
    elif mutation == 'duplicate':
        duplicate = copy.deepcopy(unit)
        duplicate['spawn_instance_id'] = 'spawn-unproven'
        battle['enemy_units'].append(duplicate)
    elif mutation == 'removed':
        battle['enemy_units'].pop()
    elif mutation == 'mismatched':
        unit['mob_id'] = 'forest_boar'
    elif mutation == 'profile':
        unit['spawn_profile'] = 'elite'
    elif mutation == 'substituted':
        unit['spawn_instance_id'] = 'spawn-unproven'
    elif mutation == 'location':
        battle['location_id'] = 'westwild_n4'
    elif mutation == 'special_key':
        unit['special_spawn_key'] = 'invented-special'
    elif mutation == 'special_name':
        unit['special_spawn_name'] = 'Invented special'
    persist_solo_pve_encounter_state(encounter_id=encounter_id, battle_state=battle, mob=mob)
    result = prepare_victory_settlement(
        encounter_id=encounter_id, battle_state=battle, mob=mob)
    assert result == {'status': 'invalid_outcome', 'reason': reason}
    assert get_settlement(encounter_id) is None
    assert _rows('SELECT status FROM pve_encounters WHERE encounter_id=?', (encounter_id,))[0]['status'] == 'active'
    assert dict(get_player(owner)) == player_before
    assert _rows('SELECT * FROM player_gear_progress WHERE player_id=?', (owner,)) == progress_before
    assert not _rows('SELECT * FROM gear_instances WHERE telegram_id=?', (owner,))


def test_r2_nonanchored_source_roster_rejects_added_unit_without_mutation():
    owner = BASE_PID + 21
    _make_player(owner)
    encounter_id = 'r2-nonanchored-extra'
    battle, mob = _create_terminal_nonanchored(owner, encounter_id, [owner])
    before = dict(get_player(owner))
    battle['enemy_units'].append({
        'unit_id': 'invented-extra', 'mob_id': mob['id'], 'spawn_profile': 'elite',
        'hp': 0, 'dead': True,
    })
    persist_solo_pve_encounter_state(encounter_id=encounter_id, battle_state=battle, mob=mob)

    result = prepare_victory_settlement(
        encounter_id=encounter_id, battle_state=battle, mob=mob)

    assert result == {'status': 'invalid_outcome', 'reason': 'terminal_source_units_mismatch'}
    assert get_settlement(encounter_id) is None
    assert dict(get_player(owner)) == before
    assert not _rows('SELECT * FROM player_gear_progress WHERE player_id=?', (owner,))


def test_r2_provable_pr229_anchored_resume_uses_spawn_authority_and_is_deterministic(monkeypatch):
    owner = BASE_PID + 22
    _make_player(owner)
    encounter_id, battle, mob = _create_anchored_encounter(owner, pack=True)
    _terminalize_anchored(encounter_id, battle, mob)
    conn = get_connection()
    conn.execute(
        'UPDATE pve_encounters SET source_units_json=NULL WHERE encounter_id=?',
        (encounter_id,),
    )
    conn.commit()
    conn.close()
    monkeypatch.setitem(GEAR_CHANCE_BY_SPAWN_PROFILE, 'normal', 0.0)

    first = prepare_victory_settlement(
        encounter_id=encounter_id, battle_state=battle, mob=mob)
    second = prepare_victory_settlement(
        encounter_id=encounter_id, battle_state=battle, mob=mob)

    assert first['status'] == second['status'] == 'prepared'
    assert json.dumps(first['plan'], sort_keys=True) == json.dumps(second['plan'], sort_keys=True)
    assert len(_rows(
        'SELECT encounter_id FROM pve_reward_settlements WHERE encounter_id=?', (encounter_id,)
    )) == 1


def test_r1_real_handler_terminal_gap_is_discovered_by_startup_once(monkeypatch):
    owner, other_pve, pvp_a, pvp_b = (BASE_PID + 23, BASE_PID + 24, BASE_PID + 25, BASE_PID + 26)
    for player_id in (owner, other_pve, pvp_a, pvp_b):
        _make_player(player_id)
    encounter_id, battle, mob = _create_anchored_encounter(owner)
    ensure_runtime_for_battle(player_id=owner, battle_state=battle, mob=mob)
    conn = get_connection()
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=?', (owner,))
    conn.commit()
    conn.close()

    other_battle = {
        'pve_encounter_id': 'r1-unrelated-pve', 'mob_id': 'forest_wolf',
        'location_id': 'westwild_n3', 'mob_hp': 50, 'mob_dead': False,
        'side_a_player_ids': [other_pve],
        'participant_states': {str(other_pve): {
            'player_hp': 100, 'hp': 100, 'player_dead': False,
            'defeated': False, 'weapon_id': 'unarmed',
        }},
    }
    create_pve_encounter(
        owner_player_id=other_pve, side_a_player_ids=[other_pve],
        battle_state=other_battle, mob=mob, encounter_id='r1-unrelated-pve',
        location_id='westwild_n3',
    )
    create_live_engagement(
        attacker=dict(get_player(pvp_a)), defender=dict(get_player(pvp_b)),
        location_id='westwild_n3', illegal_aggression=False,
    )
    unrelated_before = {
        'pve': _rows(
            'SELECT status,battle_state_json FROM pve_encounters WHERE encounter_id=?',
            ('r1-unrelated-pve',),
        ),
        'pvp': _rows('SELECT id,engagement_state FROM pvp_engagements'),
    }

    context = SimpleNamespace(
        user_data={'battle': battle, 'battle_mob': mob},
        application=SimpleNamespace(user_data={owner: {}}),
    )
    real_prepare = prepare_victory_settlement

    def fail_before_t1(**kwargs):
        return real_prepare(
            **kwargs,
            failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError(point)),
        )

    with (
        patch('game.pve_reward_settlement.prepare_victory_settlement', side_effect=fail_before_t1),
        patch('game.combat.random.random', return_value=0.0),
        patch('game.balance.random.randint', return_value=1),
    ):
        for _turn in range(20):
            query = SimpleNamespace(
                data='battle_attack_forest_wolf',
                from_user=SimpleNamespace(id=owner),
                answer=AsyncMock(),
                edit_message_text=AsyncMock(),
            )
            asyncio.run(battle_handler.handle_battle_buttons(
                SimpleNamespace(callback_query=query), context))
            persisted = _rows(
                'SELECT status,battle_state_json FROM pve_encounters WHERE encounter_id=?',
                (encounter_id,),
            )[0]
            if json.loads(persisted['battle_state_json']).get('mob_dead'):
                break
        else:
            pytest.fail('real battle handler did not reach terminal victory')

    assert persisted['status'] == 'active'
    assert get_settlement(encounter_id) is None
    assert get_player(owner)['in_battle'] == 1
    context.user_data.clear()
    reset_solo_pve_runtime_store()

    from bot import initialize_runtime
    initialize_runtime()
    settlement = get_settlement(encounter_id)
    assert settlement['status'] == 'applied'
    receipt = list_recent_reward_receipts(owner)[0]
    assert receipt['encounter_id'] == encounter_id
    gold_after = get_player(owner)['gold']
    assert get_player(owner)['in_battle'] == 0
    assert unrelated_before == {
        'pve': _rows(
            'SELECT status,battle_state_json FROM pve_encounters WHERE encounter_id=?',
            ('r1-unrelated-pve',),
        ),
        'pvp': _rows('SELECT id,engagement_state FROM pvp_engagements'),
    }

    initialize_runtime()
    assert get_player(owner)['gold'] == gold_after
    assert len(_rows(
        'SELECT encounter_id FROM pve_reward_settlements WHERE encounter_id=?', (encounter_id,)
    )) == 1
    assert len(list_recent_reward_receipts(owner)) == 1


@pytest.mark.parametrize('entrypoint', ['start', 'location', 'journal'])
def test_r1_each_player_entrypoint_recovers_unprepared_terminal_victory(entrypoint):
    player_id = BASE_PID + 30 + ['start', 'location', 'journal'].index(entrypoint)
    _make_player(player_id)
    encounter_id = f'r1-entrypoint-{entrypoint}'
    _create_terminal_nonanchored(player_id, encounter_id, [player_id])
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=player_id, language_code='en'),
        message=message,
    )
    context = SimpleNamespace(
        user_data={}, application=SimpleNamespace(user_data={player_id: {}}),
    )

    if entrypoint == 'start':
        asyncio.run(start_command(update, context))
    elif entrypoint == 'location':
        asyncio.run(location_command(update, context))
    else:
        asyncio.run(journal_command(update, context))

    assert get_settlement(encounter_id)['status'] == 'applied'
    assert list_recent_reward_receipts(player_id)[0]['encounter_id'] == encounter_id
    rendered = '\n'.join(str(call.args[0]) for call in message.reply_text.await_args_list)
    assert t('gear.settlement_recovered', 'en', count=1) in rendered
    gold_after = get_player(player_id)['gold']
    assert recover_player_settlements(player_id)['recovered'] == []
    assert get_player(player_id)['gold'] == gold_after


def test_r1_recovery_rolls_back_t1_and_t2_failures_then_retries():
    t1_player, t2_player = BASE_PID + 34, BASE_PID + 35
    for player_id in (t1_player, t2_player):
        _make_player(player_id)
    t1_battle, _ = _create_terminal_nonanchored(t1_player, 'r1-t1-rollback', [t1_player])
    _create_terminal_nonanchored(t2_player, 'r1-t2-rollback', [t2_player])
    t1_before = dict(get_player(t1_player))
    t2_before = dict(get_player(t2_player))

    t1_attempt = recover_unprepared_terminal_victories(
        player_id=t1_player,
        prepare_failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError(point)),
    )
    assert t1_attempt == [{'status': 'retryable', 'encounter_id': 'r1-t1-rollback'}]
    assert get_settlement('r1-t1-rollback') is None
    assert dict(get_player(t1_player)) == t1_before
    assert json.loads(_rows(
        'SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?', ('r1-t1-rollback',)
    )[0]['battle_state_json']) == t1_battle

    t2_attempt = recover_unprepared_terminal_victories(
        player_id=t2_player,
        apply_failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError(point)),
    )
    assert t2_attempt == [{'status': 'retryable', 'encounter_id': 'r1-t2-rollback'}]
    assert get_settlement('r1-t2-rollback')['status'] == 'prepared'
    assert dict(get_player(t2_player)) == t2_before

    recovered = recover_prepared_settlements()
    assert {row['result']['encounter_id'] for row in recovered if row.get('status') == 'applied'} == {
        'r1-t1-rollback', 'r1-t2-rollback',
    }
    gold_after = {player_id: get_player(player_id)['gold'] for player_id in (t1_player, t2_player)}
    assert recover_prepared_settlements() == []
    assert {player_id: get_player(player_id)['gold'] for player_id in (t1_player, t2_player)} == gold_after


class _AllDropsRng:
    def random(self):
        return 0.0

    def randint(self, low, high):
        return low

    def choice(self, values):
        return list(values)[0]

    def sample(self, values, k):
        return list(values)[:k]


@pytest.mark.parametrize(('category', 'profile', 'expected_materials', 'rarity_floor'), [
    ('open_world_normal', 'normal', {'enhance_shard'}, 'common'),
    ('open_world_elite', 'elite', {'enhance_shard', 'enhancement_crystal', 'power_essence'}, 'uncommon'),
    ('open_world_regional_boss', 'normal', {'enhance_shard', 'enhancement_crystal', 'power_essence'}, 'epic'),
])
def test_f3_mature_source_restrictions_and_legacy_quality_floors(
        category, profile, expected_materials, rarity_floor):
    fallback = {
        'id': 'policy_mob', 'level': 10, 'exp_reward': 1, 'gold_min': 0, 'gold_max': 0,
        'reward_source_category': category,
        'loot_table': [
            ('enhance_shard', 1.0), ('enhancement_crystal', 1.0),
            ('power_essence', 1.0), ('iron_sword', 1.0),
        ],
    }
    unit, _ = _roll_unit_rewards(
        unit={'unit_id': 'u1', 'mob_id': 'policy_mob', 'spawn_profile': profile},
        fallback_mob=fallback,
        route_id=None,
        policy_version='legacy_v0',
        dry_streak=0,
        rng=_AllDropsRng(),
        location_id='westwild_n3',
    )
    assert set(unit['non_gear']) == expected_materials
    assert len(unit['gear_specs']) == 1
    rarity_order = ['common', 'uncommon', 'rare', 'epic', 'legendary']
    assert rarity_order.index(unit['gear_specs'][0]['rarity']) >= rarity_order.index(rarity_floor)


def test_f3_zero_delivery_rolls_back_and_receipt_matches_concrete_inventory(monkeypatch):
    owner = BASE_PID + 30
    _make_player(owner)
    encounter_id = 'f3-zero-delivery'
    battle, mob = _create_terminal_nonanchored(owner, encounter_id, [owner])
    mob['loot_table'] = [('wolf_pelt', 1.0)]
    persist_solo_pve_encounter_state(encounter_id=encounter_id, battle_state=battle, mob=mob)
    prepare_victory_settlement(encounter_id=encounter_id, battle_state=battle, mob=mob)
    before = dict(get_player(owner))
    with patch('game.pve_reward_settlement.grant_item_to_player', return_value={
        'gear_instances_created': 0, 'stackable_added': 0,
    }):
        with pytest.raises(RuntimeError, match='stackable_delivery_mismatch'):
            apply_prepared_settlement(encounter_id)
    assert dict(get_player(owner)) == before
    assert get_settlement(encounter_id)['status'] == 'prepared'
    assert not _rows("SELECT * FROM inventory WHERE telegram_id=? AND item_id='wolf_pelt'", (owner,))

    applied = apply_prepared_settlement(encounter_id)['result']['recipients'][0]
    inventory = _rows(
        "SELECT item_id,quantity FROM inventory WHERE telegram_id=? AND item_id='wolf_pelt'", (owner,))
    assert applied['stackable_items'] == ['wolf_pelt']
    assert inventory == [{'item_id': 'wolf_pelt', 'quantity': 1}]


def test_f4_recovery_and_quarantine_preserve_other_pve_pvp_and_cooldowns():
    player_id, opponent_id = BASE_PID + 40, BASE_PID + 41
    _make_player(player_id)
    _make_player(opponent_id)

    prepared_id = 'f4-prepared-old'
    prepared_battle, prepared_mob = _create_terminal_nonanchored(
        player_id, prepared_id, [player_id])
    prepare_victory_settlement(
        encounter_id=prepared_id, battle_state=prepared_battle, mob=prepared_mob)

    legacy_id = 'f4-legacy-old'
    _create_terminal_nonanchored(player_id, legacy_id, [player_id])
    conn = get_connection()
    conn.execute("UPDATE pve_encounters SET status='resolving_victory' WHERE encounter_id=?", (legacy_id,))
    conn.commit()
    conn.close()

    live_id = 'f4-live-current'
    live_battle = {
        'pve_encounter_id': live_id, 'mob_id': 'forest_wolf',
        'mob_hp': 50, 'mob_dead': False, 'side_a_player_ids': [player_id],
        'participant_states': {str(player_id): {
            'player_hp': 100, 'hp': 100, 'player_dead': False,
            'defeated': False, 'weapon_id': 'field_bow',
        }},
    }
    live_mob = get_mob('forest_wolf')
    create_pve_encounter(
        owner_player_id=player_id, side_a_player_ids=[player_id],
        battle_state=live_battle, mob=live_mob, encounter_id=live_id,
        location_id='westwild_n3')
    runtime_before = ensure_runtime_for_battle(
        player_id=player_id, battle_state=live_battle, mob=live_mob)
    create_live_engagement(
        attacker=dict(get_player(player_id)), defender=dict(get_player(opponent_id)),
        location_id='westwild_n3', illegal_aggression=False)
    conn = get_connection()
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=?', (player_id,))
    conn.execute(
        "INSERT INTO skill_cooldowns(telegram_id,skill_id,turns_left) VALUES (?, 'f4_skill', 3)",
        (player_id,),
    )
    conn.commit()
    conn.close()
    live_rows_before = _rows(
        'SELECT encounter_id,player_id,status FROM pve_encounter_participants WHERE encounter_id=?',
        (live_id,),
    )

    assert recover_player_settlements(player_id)['recovered'][0]['status'] == 'applied'
    assert review_ambiguous_legacy_victories() == 1
    assert review_ambiguous_legacy_victories() == 0
    assert recover_player_settlements(player_id)['legacy_review'] == [legacy_id]
    assert get_player(player_id)['in_battle'] == 1
    assert _rows(
        'SELECT skill_id,turns_left FROM skill_cooldowns WHERE telegram_id=?', (player_id,)
    ) == [{'skill_id': 'f4_skill', 'turns_left': 3}]
    assert _rows('SELECT status FROM pve_encounters WHERE encounter_id=?', (live_id,))[0]['status'] == 'active'
    assert _rows(
        'SELECT encounter_id,player_id,status FROM pve_encounter_participants WHERE encounter_id=?',
        (live_id,),
    ) == live_rows_before
    assert _SOLO_PVE_RUNTIME_STORE.get(live_id) is runtime_before
    assert _rows('SELECT engagement_state FROM pvp_engagements') == [{'engagement_state': 'pending'}]


def test_f5_legacy_intents_fail_closed_and_roll_back_atomically():
    player_id = BASE_PID + 50
    _make_player(player_id, location='capital_city')
    conn = get_connection()
    first = conn.execute(
        "INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (?, 'wooden_sword', 1)",
        (player_id,),
    ).lastrowid
    second = conn.execute(
        "INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (?, 'wooden_sword', 1)",
        (player_id,),
    ).lastrowid
    conn.commit()
    conn.close()

    old_callback = f'inv_equip_i{first}_weapon_weapon'
    instance_id = create_gear_instance(player_id, 'field_sword_1h')
    current = issue_gear_intent(player_id, 'equip', instance_id, target_slot='weapon')
    assert apply_gear_intent(player_id, 'equip', current)['status'] == 'equipped'
    asyncio.run(_inventory_callback(player_id, old_callback))
    assert get_equipped_item_ids(player_id)['weapon'] == 'field_sword_1h'

    first_token = issue_legacy_gear_intent(player_id, 'equip', first, target_slot='weapon')
    assert apply_legacy_gear_intent(player_id, 'equip', first_token)['status'] == 'equipped'
    assert apply_legacy_gear_intent(player_id, 'equip', first_token)['status'] == 'stale_action'

    travel_token = issue_legacy_gear_intent(player_id, 'equip', second, target_slot='weapon')
    conn = get_connection()
    conn.execute("UPDATE players SET location_id='westwild_n1', travel_revision=travel_revision+1 WHERE telegram_id=?", (player_id,))
    conn.execute("UPDATE players SET location_id='capital_city', travel_revision=travel_revision+1 WHERE telegram_id=?", (player_id,))
    conn.commit()
    conn.close()
    assert apply_legacy_gear_intent(player_id, 'equip', travel_token)['status'] == 'stale_action'

    stale_token = issue_legacy_gear_intent(player_id, 'equip', second, target_slot='weapon')
    competing = issue_legacy_gear_intent(player_id, 'unequip', first, target_slot='weapon')
    assert apply_legacy_gear_intent(player_id, 'unequip', competing)['status'] == 'unequipped'
    assert apply_legacy_gear_intent(player_id, 'equip', stale_token)['status'] == 'stale_action'

    retryable = issue_legacy_gear_intent(player_id, 'equip', second, target_slot='weapon')
    before_equipment = _rows('SELECT * FROM equipment WHERE telegram_id=?', (player_id,))[0]
    before_revision = get_player(player_id)['gear_revision']
    with pytest.raises(RuntimeError, match='after_target_slot_clear'):
        apply_legacy_gear_intent(
            player_id, 'equip', retryable,
            failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError(point)),
        )
    assert _rows('SELECT * FROM equipment WHERE telegram_id=?', (player_id,))[0] == before_equipment
    assert get_player(player_id)['gear_revision'] == before_revision
    assert apply_legacy_gear_intent(player_id, 'equip', retryable)['status'] == 'equipped'


def test_f6_ring_callbacks_preserve_explicit_ring_targets():
    player_id = BASE_PID + 60
    _make_player(player_id, location='capital_city')
    ring1 = create_gear_instance(player_id, 'field_guard_ring')
    ring2 = create_gear_instance(player_id, 'field_precision_ring')
    candidate1 = create_gear_instance(player_id, 'field_guard_ring')
    candidate2 = create_gear_instance(player_id, 'field_precision_ring')
    conn = get_connection()
    conn.execute("UPDATE gear_instances SET equipped_slot='ring1' WHERE id=?", (ring1,))
    conn.execute("UPDATE gear_instances SET equipped_slot='ring2' WHERE id=?", (ring2,))
    conn.commit()
    conn.close()

    _, markup = build_item_detail(player_id, f'g{candidate1}', 'accessory', 'en')
    ring_callbacks = [value for value in _callbacks(markup) if value.startswith('inv_gequip_')]
    assert len(ring_callbacks) == 2
    asyncio.run(_inventory_callback(player_id, ring_callbacks[0]))
    equipped = get_equipped_gear_instances(player_id)
    assert equipped['ring1']['id'] == candidate1
    assert equipped['ring2']['id'] == ring2

    _, markup = build_item_detail(player_id, f'g{candidate2}', 'accessory', 'en')
    ring_callbacks = [value for value in _callbacks(markup) if value.startswith('inv_gequip_')]
    asyncio.run(_inventory_callback(player_id, ring_callbacks[1]))
    equipped = get_equipped_gear_instances(player_id)
    assert equipped['ring1']['id'] == candidate1
    assert equipped['ring2']['id'] == candidate2


def test_r3_ordinary_inventory_pages_17_mixed_entries_in_all_locales():
    player_id = BASE_PID + 61
    _make_player(player_id, location='capital_city')
    instance_ids = [
        create_gear_instance(player_id, FIELD_WEAPON_IDS[index % len(FIELD_WEAPON_IDS)])
        for index in range(9)
    ]
    conn = get_connection()
    legacy_ids = [
        conn.execute(
            "INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (?, 'wooden_sword', 1)",
            (player_id,),
        ).lastrowid
        for _index in range(8)
    ]
    conn.commit()
    conn.close()
    expected_tokens = {
        *(make_entry_token('gear_instance', instance_id) for instance_id in instance_ids),
        *(make_entry_token('legacy_inventory', inventory_id) for inventory_id in legacy_ids),
    }

    for lang in ('ru', 'en', 'es'):
        reached = []
        for page, expected_rows in enumerate((8, 8, 1)):
            text, markup = build_inventory_list(player_id, 'weapon', lang, page=page)
            callbacks = _callbacks(markup)
            item_callbacks = [value for value in callbacks if value.startswith('inv_item_')]
            assert len(item_callbacks) == expected_rows <= INVENTORY_PAGE_SIZE
            assert len(text) <= 4096
            assert t('gear.page', lang, page=page + 1, pages=3) in text
            route = 'weapon' if page == 0 else f'weapon~{page}'
            assert f'inv_tab_{route}' in callbacks
            assert all(len(value.encode('utf-8')) <= 64 for value in callbacks)
            reached.extend(value.split('_')[2] for value in item_callbacks)
            for value in item_callbacks:
                entry_token, route = value.split('_')[2:]
                _, detail_markup = build_item_detail(player_id, entry_token, route, lang)
                assert f'inv_tab_{route}' in _callbacks(detail_markup)
        assert len(reached) == len(set(reached)) == 17
        assert set(reached) == expected_tokens


def test_r3_page_context_survives_equip_sale_and_stale_page_clamps_safely():
    player_id = BASE_PID + 62
    _make_player(player_id, location='capital_city')
    instance_ids = [create_gear_instance(player_id, 'field_sword_1h') for _index in range(17)]
    _, last_page_markup = build_inventory_list(player_id, 'weapon', 'en', page=2)
    last_item_callback = next(
        value for value in _callbacks(last_page_markup) if value.startswith('inv_item_'))
    entry_token, route = last_item_callback.split('_')[2:]
    assert route == 'weapon~2'

    _, detail_markup = build_item_detail(player_id, entry_token, route, 'en')
    equip_callback = next(
        value for value in _callbacks(detail_markup) if value.startswith('inv_gequip_'))
    equip_query = asyncio.run(_inventory_callback(player_id, equip_callback))
    equip_render = equip_query.edit_message_text.await_args.kwargs['reply_markup']
    assert f'inv_tab_{route}' in _callbacks(equip_render)

    sale_instance = next(instance_id for instance_id in instance_ids if f'g{instance_id}' != entry_token)
    _, sale_detail = build_item_detail(player_id, f'g{sale_instance}', route, 'en')
    sale_ask = next(value for value in _callbacks(sale_detail) if value.startswith('inv_sellask_'))
    ask_query = asyncio.run(_inventory_callback(player_id, sale_ask))
    confirm_markup = ask_query.edit_message_text.await_args.kwargs['reply_markup']
    sale_confirm = next(value for value in _callbacks(confirm_markup) if value.startswith('inv_gsell_'))
    gold_before = get_player(player_id)['gold']
    sale_query = asyncio.run(_inventory_callback(player_id, sale_confirm))
    sale_render = sale_query.edit_message_text.await_args.kwargs['reply_markup']
    assert any(value.startswith('inv_item_') and value.endswith('_weapon~1') for value in _callbacks(sale_render))
    gold_after = get_player(player_id)['gold']
    assert gold_after > gold_before

    stale_query = asyncio.run(_inventory_callback(player_id, sale_confirm))
    stale_query.answer.assert_awaited()
    assert get_player(player_id)['gold'] == gold_after
    stale_page_query = asyncio.run(_inventory_callback(player_id, 'inv_tab_weapon~99'))
    stale_page_render = stale_page_query.edit_message_text.await_args.kwargs['reply_markup']
    assert all(len(value.encode('utf-8')) <= 64 for value in _callbacks(stale_page_render))


def test_f7_personal_receipt_limit_precedes_global_noise_and_details_survive_restart():
    player_id, other_id = BASE_PID + 70, BASE_PID + 71
    _make_player(player_id)
    _make_player(other_id)
    conn = get_connection()
    for index in range(125):
        owner = player_id if index < 20 else other_id
        encounter_id = f'receipt-{index:03d}'
        gear = [{
            'base_item_id': 'field_bow', 'instance_id': 10_000 + index,
            'item_tier': 1, 'rarity': 'uncommon', 'enhance_level': 0,
            'guaranteed': index == 19,
        }]
        result = {
            'encounter_id': encounter_id,
            'location_id': 'westwild_n3',
            'recipients': [{
                'player_id': owner, 'exp': index, 'gold': index,
                'stackable_items': ['wolf_pelt'], 'gear': gear,
                'guaranteed': index == 19,
            }],
        }
        conn.execute(
            '''INSERT INTO pve_encounters
               (encounter_id,owner_player_id,status,mob_id,battle_state_json,mob_json,
                location_id,reward_policy_version,locked_roster_json)
               VALUES (?,?,'victory','forest_wolf','{}','{}','westwild_n3','field_loot_v1',?)''',
            (encounter_id, owner, json.dumps({'player_ids': [owner]})),
        )
        conn.execute(
            "INSERT INTO pve_encounter_participants(encounter_id,player_id,status) VALUES (?,?,'victory')",
            (encounter_id, owner),
        )
        conn.execute(
            '''INSERT INTO pve_reward_settlements
               (encounter_id,schema_version,policy_version,status,plan_json,result_json,applied_at)
               VALUES (?,1,'field_loot_v1','applied','{}',?,?)''',
            (encounter_id, json.dumps(result), f'2026-01-01 00:{index:02d}:00'),
        )
    conn.commit()
    conn.close()

    reset_solo_pve_runtime_store()
    receipts = list_recent_reward_receipts(player_id)
    assert len(receipts) == 20
    assert {receipt['encounter_id'] for receipt in receipts} == {
        f'receipt-{index:03d}' for index in range(20)}
    for lang in ('en', 'ru', 'es'):
        player = dict(get_player(player_id))
        player['lang'] = lang
        list_text, list_markup = build_recent_gear_receipts(player, 0)
        detail_text, detail_markup = build_reward_receipt_detail(player, 'receipt-019', 0)
        assert len(list_text) <= 4096 and len(detail_text) <= 4096
        assert '#10019' in detail_text
        assert '19' in detail_text
        assert t('gear.receipt_guaranteed_yes', lang) in detail_text
        assert any(value.startswith('inv_receipt_') for value in _callbacks(list_markup))
        assert _callbacks(detail_markup) == ['inv_rpage_0']


@pytest.mark.parametrize('item_id', FIELD_WEAPON_IDS)
def test_f8_real_vendor_inventory_handler_skill_and_combat_journey(item_id):
    player_id = BASE_PID + 100 + FIELD_WEAPON_IDS.index(item_id)
    _make_player(player_id, location='capital_city')
    token = issue_actions(player_id, 'shop_buy', [item_id])[item_id]
    assert try_buy_curated_shop_item(
        player_id, 'capital_city', 1, item_id, action_token=token)['ok']
    instance_id = _rows(
        'SELECT id FROM gear_instances WHERE telegram_id=? AND base_item_id=?',
        (player_id, item_id),
    )[0]['id']
    _, markup = build_item_detail(player_id, f'g{instance_id}', 'weapon', 'en')
    equip_callback = next(
        value for value in _callbacks(markup) if value.startswith('inv_gequip_'))
    asyncio.run(_inventory_callback(player_id, equip_callback))
    assert get_equipped_item_ids(player_id)['weapon'] == item_id

    weapon = get_equipped_combat_items(player_id)['weapon']
    profile = weapon['weapon_profile']
    mastery = get_mastery(player_id, item_id)
    skill = next(
        row for row in get_available_skills(item_id, mastery['level'], profile)
        if row['id'] != 'power_strike' and row['type'] != 'passive')
    assert upgrade_skill(player_id, item_id, skill['id'])['success']
    battle_skills = get_battle_skills(player_id, item_id, mastery['level'], profile)
    assert skill['id'] in {row['id'] for row in battle_skills}

    player = dict(get_player(player_id))
    effective = get_player_effective_stats(player_id, player)
    player.update(effective)
    player.update({
        'weapon_damage': round((weapon['damage_min'] + weapon['damage_max']) / 2),
        'weapon_type': weapon['weapon_type'],
        'weapon_profile': profile,
        'damage_school': weapon['damage_school'],
    })
    mob = get_mob('westwild_rabbit')
    battle = init_battle(player, mob)
    battle.update({
        'weapon_id': item_id,
        'weapon_damage': player['weapon_damage'],
        'weapon_type': player['weapon_type'],
        'weapon_profile': profile,
        'damage_school': player['damage_school'],
    })
    encounter_id = f'r4-family-{FIELD_WEAPON_IDS.index(item_id)}'
    battle['pve_encounter_id'] = encounter_id
    create_pve_encounter(
        owner_player_id=player_id, side_a_player_ids=[player_id],
        battle_state=battle, mob=mob, encounter_id=encounter_id,
        location_id='capital_city',
    )
    ensure_runtime_for_battle(player_id=player_id, battle_state=battle, mob=mob)
    conn = get_connection()
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=?', (player_id,))
    conn.commit()
    conn.close()
    context = SimpleNamespace(
        user_data={'battle': battle, 'battle_mob': mob},
        application=SimpleNamespace(user_data={player_id: {}}),
    )
    before_action = json.loads(json.dumps(battle))
    query = SimpleNamespace(
        data=f"battle_skill_{skill['id']}|{mob['id']}",
        from_user=SimpleNamespace(id=player_id),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    with (
        patch('game.combat.random.random', return_value=0.0),
        patch('game.skill_engine.random.random', return_value=0.0),
        patch('game.balance.random.randint', return_value=1),
    ):
        asyncio.run(battle_handler.handle_battle_buttons(
            SimpleNamespace(callback_query=query), context))
    query.edit_message_text.assert_awaited()
    persisted = _rows(
        'SELECT status,battle_state_json FROM pve_encounters WHERE encounter_id=?',
        (encounter_id,),
    )[0]
    persisted_battle = json.loads(persisted['battle_state_json'])
    assert persisted['status'] in {'active', 'victory'}
    assert persisted_battle != before_action
    assert (
        persisted_battle.get('turn', 0) > before_action.get('turn', 0)
        or persisted_battle.get('player_mana') != before_action.get('player_mana')
        or persisted_battle.get('mob_hp') != before_action.get('mob_hp')
    )
    assert get_mastery(player_id, item_id)['weapon_id'] == profile


def test_r4_regional_chase_uses_goal_travel_combat_receipt_comparison_and_equip(monkeypatch):
    player_id = BASE_PID + 220
    target_item = 'field_bow'
    _make_player(player_id, location='capital_city')

    goal_callback = f'inv_goal_{FIELD_ITEM_IDS.index(target_item)}_weapon_0'
    asyncio.run(_inventory_callback(player_id, goal_callback))
    assert get_equipment_goal(player_id) == target_item
    sources = get_field_source_manifest(target_item)
    assert 'route_westwild' in sources['curated_routes']

    context = SimpleNamespace(
        user_data={},
        application=SimpleNamespace(
            user_data={player_id: {}},
            create_task=lambda coroutine: coroutine.close(),
        ),
    )
    path = _find_canonical_path('capital_city', 'westwild_n3')
    assert path[0] == 'capital_city' and path[-1] == 'westwild_n3'
    for destination in path[1:]:
        query = SimpleNamespace(
            data=f'goto_{destination}', from_user=SimpleNamespace(id=player_id),
            answer=AsyncMock(), edit_message_text=AsyncMock(),
            message=SimpleNamespace(reply_text=AsyncMock(), message_id=1),
        )
        with patch('handlers.location.asyncio.sleep', new=AsyncMock()):
            asyncio.run(handle_location_buttons(SimpleNamespace(callback_query=query), context))
        assert get_player(player_id)['location_id'] == destination

    player = dict(get_player(player_id))
    mob = get_mob('forest_wolf')
    battle = init_battle(player, mob)
    battle.update({'location_id': 'westwild_n3', 'weapon_id': 'unarmed'})
    encounter_id, status = create_or_load_open_world_pve_encounter(
        owner_player_id=player_id, location_id='westwild_n3', mob_id=mob['id'],
        battle_state=battle, mob=mob, side_a_player_ids=[player_id],
    )
    assert status == 'created'
    battle['pve_encounter_id'] = encounter_id
    battle['side_a_player_ids'] = [player_id]
    ensure_runtime_for_battle(player_id=player_id, battle_state=battle, mob=mob)
    conn = get_connection()
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=?', (player_id,))
    conn.commit()
    conn.close()
    combat_context = SimpleNamespace(
        user_data={'battle': battle, 'battle_mob': mob},
        application=SimpleNamespace(user_data={player_id: {}}),
    )
    monkeypatch.setitem(GEAR_CHANCE_BY_SPAWN_PROFILE, 'normal', 1.0)
    monkeypatch.setattr('game.pve_reward_settlement.choose_field_item', lambda *_args, **_kwargs: target_item)
    with (
        patch('game.combat.random.random', return_value=0.0),
        patch('game.balance.random.randint', return_value=1),
    ):
        for _turn in range(20):
            query = SimpleNamespace(
                data=f"battle_attack_{mob['id']}", from_user=SimpleNamespace(id=player_id),
                answer=AsyncMock(), edit_message_text=AsyncMock(),
            )
            asyncio.run(battle_handler.handle_battle_buttons(
                SimpleNamespace(callback_query=query), combat_context))
            if get_settlement(str(encounter_id)):
                break
        else:
            pytest.fail('regional real-combat journey did not settle')

    receipt = list_recent_reward_receipts(player_id)[0]
    reward = receipt['recipient']['gear'][0]
    assert reward['base_item_id'] == target_item
    instance = _rows('SELECT * FROM gear_instances WHERE id=?', (reward['instance_id'],))[0]
    provenance = json.loads(instance['source_metadata_json'])
    assert instance['source_settlement_id'] == encounter_id
    assert provenance['encounter_id'] == encounter_id
    assert provenance['location_id'] == 'westwild_n3'
    assert provenance['route_id'] == 'route_westwild'
    comparison_text, _ = build_gear_comparison(
        player_id, f"g{instance['id']}", 'weapon', 'weapon', 'en')
    assert t('gear.comparison_empty', 'en') in comparison_text
    _, detail_markup = build_item_detail(player_id, f"g{instance['id']}", 'weapon', 'en')
    equip_callback = next(
        value for value in _callbacks(detail_markup) if value.startswith('inv_gequip_'))
    asyncio.run(_inventory_callback(player_id, equip_callback))
    assert get_equipped_item_ids(player_id)['weapon'] == target_item


def test_f8_real_runtime_guarantee_survives_restart_and_recovers(monkeypatch):
    player_id = BASE_PID + 200
    _make_player(player_id)
    monkeypatch.setitem(GEAR_CHANCE_BY_SPAWN_PROFILE, 'normal', 0.0)
    monkeypatch.setattr(
        'game.pve_reward_settlement.choose_field_item',
        lambda *_args, **_kwargs: 'field_bow',
    )
    encounter_ids = []
    with (
        patch('game.balance.random.randint', return_value=1),
        patch('game.combat.random.random', return_value=0.0),
    ):
        for sequence_index in range(12):
            encounter_id = f'r4-dry-streak-{sequence_index + 1}'
            encounter_ids.append(encounter_id)
            mob = get_mob('westwild_rabbit')
            battle = init_battle(dict(get_player(player_id)), mob)
            battle.update({
                'pve_encounter_id': encounter_id,
                'location_id': 'westwild_n3',
                'weapon_id': 'unarmed',
            })
            create_pve_encounter(
                owner_player_id=player_id, side_a_player_ids=[player_id],
                battle_state=battle, mob=mob, encounter_id=encounter_id,
                location_id='westwild_n3',
            )
            ensure_runtime_for_battle(player_id=player_id, battle_state=battle, mob=mob)
            conn = get_connection()
            conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=?', (player_id,))
            conn.commit()
            conn.close()
            context = SimpleNamespace(
                user_data={'battle': battle, 'battle_mob': mob},
                application=SimpleNamespace(user_data={player_id: {}}),
            )
            if sequence_index == 5:
                reset_solo_pve_runtime_store()
                context.user_data.clear()
                loaded = load_active_pve_encounter(player_id=player_id)
                assert loaded is not None
                battle, mob = loaded
                context.user_data.update(battle=battle, battle_mob=mob)

            for _turn in range(20):
                query = SimpleNamespace(
                    data=f"battle_attack_{mob['id']}", from_user=SimpleNamespace(id=player_id),
                    answer=AsyncMock(), edit_message_text=AsyncMock(),
                )
                asyncio.run(battle_handler.handle_battle_buttons(
                    SimpleNamespace(callback_query=query), context))
                if get_settlement(encounter_id):
                    break
            else:
                pytest.fail(f'dry-streak encounter {sequence_index + 1} did not settle')

            settlement = get_settlement(encounter_id)
            recipient = settlement['result']['recipients'][0]
            if sequence_index < 11:
                assert recipient['gear'] == []
                assert recipient['guaranteed'] is False
                assert _rows(
                    "SELECT dry_streak FROM player_gear_progress WHERE player_id=? AND route_id='route_westwild'",
                    (player_id,),
                )[0]['dry_streak'] == sequence_index + 1

    final_settlement = get_settlement(encounter_ids[-1])
    recipient = final_settlement['result']['recipients'][0]
    assert recipient['guaranteed'] is True
    assert len(recipient['gear']) == 1
    assert recipient['gear'][0]['rarity'] == 'uncommon'
    final_unit = final_settlement['plan']['recipients'][0]['units'][0]
    assert final_unit['counter_before'] == 11
    assert final_unit['counter_after'] == 0
    assert final_unit['guaranteed'] is True
    assert _rows(
        "SELECT dry_streak FROM player_gear_progress WHERE player_id=? AND route_id='route_westwild'",
        (player_id,),
    )[0]['dry_streak'] == 0
    instance_id = recipient['gear'][0]['instance_id']
    assert _rows(
        'SELECT id,source_settlement_id FROM gear_instances WHERE id=?', (instance_id,)
    ) == [{'id': instance_id, 'source_settlement_id': encounter_ids[-1]}]
    final_receipt = next(
        receipt for receipt in list_recent_reward_receipts(player_id)
        if receipt['encounter_id'] == encounter_ids[-1]
    )
    assert final_receipt['recipient']['gear'][0]['instance_id'] == instance_id
    gold_after = get_player(player_id)['gold']
    reset_solo_pve_runtime_store()
    assert recover_player_settlements(player_id)['recovered'] == []
    assert recover_prepared_settlements() == []
    assert get_player(player_id)['gold'] == gold_after
    assert len(_rows(
        'SELECT id FROM gear_instances WHERE source_settlement_id=?', (encounter_ids[-1],)
    )) == 1
