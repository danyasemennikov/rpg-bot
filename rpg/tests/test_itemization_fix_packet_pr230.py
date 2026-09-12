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
from game.combat import init_battle, process_skill_turn, process_turn
from game.equipment_stats import get_equipped_item_ids, get_player_effective_stats
from game.field_catalog import FIELD_WEAPON_IDS, GEAR_CHANCE_BY_SPAWN_PROFILE
from game.gear_instances import create_gear_instance, get_equipped_gear_instances
from game.gear_progression import (
    apply_gear_intent,
    apply_legacy_gear_intent,
    issue_gear_intent,
    issue_legacy_gear_intent,
)
from game.i18n import t
from game.mobs import get_mob
from game.pve_live import (
    _SOLO_PVE_RUNTIME_STORE,
    create_or_load_open_world_pve_encounter,
    create_pve_encounter,
    ensure_runtime_for_battle,
    join_open_world_pve_encounter,
    leave_open_world_pve_encounter,
    persist_solo_pve_encounter_state,
    reset_solo_pve_runtime_store,
)
from game.pve_reward_settlement import (
    _roll_unit_rewards,
    apply_prepared_settlement,
    get_settlement,
    list_recent_reward_receipts,
    prepare_victory_settlement,
    recover_player_settlements,
    review_ambiguous_legacy_victories,
)
from game.pvp_live import create_live_engagement
from game.skill_engine import get_battle_skills
from game.skills import get_available_skills
from game.weapon_mastery import get_mastery, upgrade_skill
from handlers.battle import get_equipped_combat_items
from handlers.inventory import (
    build_item_detail,
    build_recent_gear_receipts,
    build_reward_receipt_detail,
    handle_inventory_buttons,
)
from handlers.location import try_buy_curated_shop_item


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


def _create_anchored_encounter(owner_id: int, *, player_ids: list[int] | None = None):
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
    encounter_id, status = create_or_load_open_world_pve_encounter(
        owner_player_id=owner_id,
        location_id='westwild_n3',
        mob_id='forest_wolf',
        battle_state=battle,
        mob=mob,
        side_a_player_ids=player_ids or [owner_id],
    )
    assert status == 'created'
    battle['pve_encounter_id'] = encounter_id
    battle.setdefault('side_a_player_ids', list(player_ids or [owner_id]))
    return str(encounter_id), battle, mob


def _terminalize_anchored(encounter_id: str, battle: dict, mob: dict) -> None:
    ensure_runtime_for_battle(player_id=int(battle['side_a_player_ids'][0]), battle_state=battle, mob=mob)
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
            'unit_id': str(unit.get('unit_id') or f'enemy-{index}'),
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


@pytest.mark.parametrize(('mutation', 'reason'), [
    ('living', 'terminal_living_unit'),
    ('extra', 'terminal_spawn_roster_mismatch'),
    ('duplicate', 'terminal_unit_identity_mismatch'),
    ('mismatched', 'terminal_spawn_mob_mismatch'),
    ('substituted', 'terminal_spawn_roster_mismatch'),
])
def test_f2_authoritative_terminal_validation_rejects_tampered_units(mutation, reason):
    owner = BASE_PID + 20
    _make_player(owner)
    encounter_id, battle, mob = _create_anchored_encounter(owner)
    _terminalize_anchored(encounter_id, battle, mob)
    unit = battle['enemy_units'][0]
    if mutation == 'living':
        unit.update(dead=False, hp=1)
    elif mutation == 'extra':
        extra = copy.deepcopy(unit)
        extra.update(unit_id='enemy-extra', spawn_instance_id='spawn-unproven')
        battle['enemy_units'].append(extra)
    elif mutation == 'duplicate':
        duplicate = copy.deepcopy(unit)
        duplicate['spawn_instance_id'] = 'spawn-unproven'
        battle['enemy_units'].append(duplicate)
    elif mutation == 'mismatched':
        unit['mob_id'] = 'forest_boar'
    elif mutation == 'substituted':
        unit['spawn_instance_id'] = 'spawn-unproven'
    persist_solo_pve_encounter_state(encounter_id=encounter_id, battle_state=battle, mob=mob)
    result = prepare_victory_settlement(
        encounter_id=encounter_id, battle_state=battle, mob=mob)
    assert result == {'status': 'invalid_outcome', 'reason': reason}
    assert get_settlement(encounter_id) is None
    assert _rows('SELECT status FROM pve_encounters WHERE encounter_id=?', (encounter_id,))[0]['status'] == 'active'


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
    skill_result = process_skill_turn(
        skill['id'], player, mob, battle, user_id=player_id, lang='en',
        include_enemy_response=False, cooldown_override=0,
        commit_cooldown_to_db=False,
    )
    assert skill_result['success'], (item_id, skill['id'], skill_result)
    before_attack_hp = skill_result['battle_state']['mob_hp']
    attack_result = process_turn(
        player, mob, skill_result['battle_state'], lang='en',
        user_id=player_id, include_enemy_response=False)
    assert attack_result['log']
    assert attack_result['mob_hp'] <= before_attack_hp


def test_f8_real_runtime_guarantee_survives_restart_and_recovers(monkeypatch):
    player_id = BASE_PID + 200
    _make_player(player_id)
    encounter_id, battle, mob = _create_anchored_encounter(player_id)
    ensure_runtime_for_battle(player_id=player_id, battle_state=battle, mob=mob)
    conn = get_connection()
    conn.execute(
        "INSERT INTO player_gear_progress(player_id,route_id,dry_streak) VALUES (?,'route_westwild',11)",
        (player_id,),
    )
    conn.commit()
    conn.close()

    combat_player = dict(get_player(player_id))
    combat_player['strength'] = 10_000
    battle['effective_strength'] = 10_000
    battle['weapon_damage'] = 100
    with (
        patch('game.balance.random.randint', return_value=1),
        patch('game.combat.random.random', return_value=0.0),
    ):
        battle = process_turn(
            combat_player, mob, battle, lang='en', user_id=player_id)
    assert battle['mob_dead'] and battle['mob_hp'] == 0
    persist_solo_pve_encounter_state(
        encounter_id=encounter_id, battle_state=battle, mob=mob)
    monkeypatch.setitem(GEAR_CHANCE_BY_SPAWN_PROFILE, 'normal', 0.0)
    assert prepare_victory_settlement(
        encounter_id=encounter_id, battle_state=battle, mob=mob)['status'] == 'prepared'

    reset_solo_pve_runtime_store()
    recovered = recover_player_settlements(player_id)
    assert len(recovered['recovered']) == 1
    recipient = recovered['recovered'][0]['result']['recipients'][0]
    assert recipient['guaranteed'] is True
    assert len(recipient['gear']) == 1
    instance_id = recipient['gear'][0]['instance_id']
    assert _rows(
        'SELECT id,source_settlement_id FROM gear_instances WHERE id=?', (instance_id,)
    ) == [{'id': instance_id, 'source_settlement_id': encounter_id}]
    assert list_recent_reward_receipts(player_id)[0]['recipient']['gear'][0]['instance_id'] == instance_id
