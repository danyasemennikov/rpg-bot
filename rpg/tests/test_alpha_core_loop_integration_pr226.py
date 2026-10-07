from itertools import count
_message_ids = count(1)
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from database import create_player, get_connection, get_player, is_in_battle, is_location_discovered
from game.combat import init_battle, process_turn
from game.gathering_foundation import build_location_gather_source_profiles
from game.locations import get_location
from game.mobs import get_mob
from game.pve_live import (
    claim_pve_encounter_victory,
    create_or_load_open_world_pve_encounter,
    ensure_runtime_for_battle as _ensure_runtime,
    finish_solo_pve_encounter,
    load_active_pve_encounter,
    persist_solo_pve_encounter_state,
)
from game.pve_reward_settlement import get_settlement
from game.quest_board import accept_hunt_contract, get_player_hunt_contract_state
from handlers.battle import _handle_victory_cleanup, save_battle
from handlers.location import handle_location_buttons, handle_lower_menu_gather_text


PLAYER_ID = 22601


def _discard_task(coro):
    coro.close()


def ensure_runtime_for_battle(**kwargs):
    conn=get_connection()
    deadline=conn.execute('SELECT formation_deadline_ms FROM pve_encounters WHERE encounter_id=?',(kwargs['battle_state']['pve_encounter_id'],)).fetchone()[0]
    conn.close()
    with patch('time.time',return_value=deadline/1000):
        return _ensure_runtime(**kwargs)


async def _travel(target):
    from handlers.activities import handle_activity_buttons
    from game.travel_runtime import advance_travel_edge
    query=SimpleNamespace(data='goto_'+target,from_user=SimpleNamespace(id=PLAYER_ID),
        answer=AsyncMock(),edit_message_text=AsyncMock(),message=SimpleNamespace(message_id=226,chat_id=PLAYER_ID))
    context=SimpleNamespace(user_data={})
    origin=get_player(PLAYER_ID)['location_id']
    await handle_location_buttons(SimpleNamespace(callback_query=query),context)
    assert get_player(PLAYER_ID)['location_id']==origin
    if not query.edit_message_text.called:
        return query
    keyboard=query.edit_message_text.call_args.kwargs.get('reply_markup')
    starts=[b.callback_data for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith('px:travel:')] if keyboard else []
    if not starts:
        return query
    query.data=starts[0]
    with patch('time.time',return_value=1000):
        await handle_activity_buttons(SimpleNamespace(callback_query=query),context)
    conn=get_connection()
    session=conn.execute("SELECT * FROM player_travel_sessions WHERE player_id=? AND status='running'",(PLAYER_ID,)).fetchone()
    assert session
    conn.execute('BEGIN IMMEDIATE')
    advance_travel_edge(conn,session['session_id'],now_ms=session['next_due_ms'])
    conn.commit();conn.close()
    return query


def _create_player():
    create_player(
        PLAYER_ID, 'pr226', 'PR226',
        {'strength': 5, 'agility': 5, 'intuition': 5, 'vitality': 5, 'wisdom': 5, 'luck': 5},
    )


def _encounter_status(encounter_id):
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT status FROM pve_encounters WHERE encounter_id=?', (encounter_id,),
        ).fetchone()
        return row['status'] if row else None
    finally:
        conn.close()


def test_complete_alpha_core_loop_uses_real_persisted_runtime_rails():
    asyncio.run(_run_complete_alpha_core_loop())


async def _run_complete_alpha_core_loop():
    _create_player()
    assert get_player(PLAYER_ID)['location_id'] == 'capital_city'
    assert is_location_discovered(PLAYER_ID, 'capital_city')
    assert {'shop', 'inn', 'quest_board'} <= set(get_location('capital_city')['services'])

    assert accept_hunt_contract(
        player_id=PLAYER_ID, location_id='capital_city', contract_key='hunt_forest_wolves',
    ) == (True, 'accepted')
    assert get_player_hunt_contract_state(PLAYER_ID)['status'] == 'active'

    await _travel('westwild_n3')
    assert get_player(PLAYER_ID)['location_id'] == 'capital_city'
    assert not is_location_discovered(PLAYER_ID, 'westwild_n3')

    for location_id in ('westwild_n1', 'westwild_n2', 'westwild_n3'):
        await _travel(location_id)
        assert get_player(PLAYER_ID)['location_id'] == location_id
        assert is_location_discovered(PLAYER_ID, location_id)

    mob = get_mob('forest_wolf')
    combat_player = dict(get_player(PLAYER_ID))
    # A deliberately overpowered test participant makes the production normal
    # attack deterministic without changing any global combat/balance values.
    combat_player['strength'] = 10_000
    battle_state = init_battle(combat_player, mob)
    battle_state.update({
        'weapon_id': 'unarmed', 'weapon_type': 'melee',
        'weapon_profile': 'unarmed', 'weapon_damage': 10,
        'effective_strength': combat_player['strength'],
        'location_id': 'westwild_n3', 'spawn_profile': 'normal',
    })
    assert battle_state['mob_hp'] == mob['hp'] > 0
    assert not battle_state.get('mob_dead', False)
    encounter_id, status = create_or_load_open_world_pve_encounter(
        owner_player_id=PLAYER_ID, location_id='westwild_n3',
        mob_id='forest_wolf', battle_state=battle_state, mob=mob,
    )
    assert status == 'created'
    battle_state['pve_encounter_id'] = encounter_id
    ensure_runtime_for_battle(
        player_id=PLAYER_ID, battle_state=battle_state, mob=mob,
    )
    persist_solo_pve_encounter_state(
        encounter_id=encounter_id, battle_state=battle_state, mob=mob,
    )
    save_battle(PLAYER_ID)
    assert _encounter_status(encounter_id) == 'active'
    assert is_in_battle(PLAYER_ID)

    # This is the same production combat action used by the live normal-attack
    # rail, not a pre-killed state or a mocked combat result.
    with (
        patch('game.balance.random.randint', return_value=1),
        patch('game.combat.random.random', return_value=0.0),
    ):
        battle_state = process_turn(
            combat_player, mob, battle_state, lang='en', user_id=PLAYER_ID,
        )
    assert battle_state['mob_dead']
    assert battle_state['mob_hp'] == 0
    persist_solo_pve_encounter_state(
        encounter_id=encounter_id, battle_state=battle_state, mob=mob,
    )
    restored_state, _ = load_active_pve_encounter(encounter_id=encounter_id)
    assert restored_state['mob_dead']
    assert restored_state['mob_hp'] == 0
    assert _encounter_status(encounter_id) == 'active'

    query = SimpleNamespace(edit_message_text=AsyncMock())
    context = SimpleNamespace(user_data={'battle': battle_state, 'battle_mob': mob})
    with (
        patch('handlers.battle.safe_edit', new=AsyncMock()),
    ):
        before = dict(get_player(PLAYER_ID))
        await _handle_victory_cleanup(
            query=query, context=context, user_id=PLAYER_ID, player=before,
            mob=mob, battle_state=battle_state, lang='en',
        )
        after = dict(get_player(PLAYER_ID))
        progress = get_player_hunt_contract_state(PLAYER_ID)['progress_kills']
        await _handle_victory_cleanup(
            query=query, context=context, user_id=PLAYER_ID, player=after,
            mob=mob, battle_state=battle_state, lang='en',
        )

    duplicate = dict(get_player(PLAYER_ID))
    receipt = get_settlement(encounter_id)['result']['recipients'][0]
    assert (after['exp'], after['gold']) == (receipt['exp_after'], receipt['gold_after'])
    assert (duplicate['exp'], duplicate['gold']) == (after['exp'], after['gold'])
    assert progress == get_player_hunt_contract_state(PLAYER_ID)['progress_kills'] == 1
    assert _encounter_status(encounter_id) == 'victory'
    assert not is_in_battle(PLAYER_ID)
    conn = get_connection()
    for item_id in receipt['stackable_items']:
        assert conn.execute(
            'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?', (PLAYER_ID, item_id),
        ).fetchone()['quantity'] >= receipt['stackable_items'].count(item_id)
    conn.close()

    profile = build_location_gather_source_profiles('westwild_n3')[0]
    from tests.pxe1_gather_fixture import one_tick
    handled,_,tick=await one_tick(PLAYER_ID,profile.profession_key,0.0,next(_message_ids))
    assert handled and tick['granted'][0]['item_id']==profile.item_id
    conn = get_connection()
    assert conn.execute(
        'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?',
        (PLAYER_ID, profile.item_id),
    ).fetchone()['quantity'] == 1
    conn.close()

    for location_id in ('westwild_n2', 'westwild_n1', 'capital_city'):
        await _travel(location_id)
    assert get_player(PLAYER_ID)['location_id'] == 'capital_city'
    assert {'shop', 'inn', 'quest_board'} <= set(get_location('capital_city')['services'])


def test_claim_return_semantics_fail_closed_for_every_persisted_state():
    _create_player()
    assert claim_pve_encounter_victory(encounter_id=None) is None
    assert claim_pve_encounter_victory(encounter_id='') is None
    assert claim_pve_encounter_victory(encounter_id='unknown-non-empty') is False

    conn=get_connection();conn.execute("UPDATE players SET location_id='westwild_n3' WHERE telegram_id=?",(PLAYER_ID,));conn.commit();conn.close()
    mob = get_mob('forest_wolf')
    battle_state = init_battle(dict(get_player(PLAYER_ID)), mob)
    encounter_id, _ = create_or_load_open_world_pve_encounter(
        owner_player_id=PLAYER_ID, location_id='westwild_n3',
        mob_id='forest_wolf', battle_state=battle_state, mob=mob,
    )
    assert claim_pve_encounter_victory(encounter_id=encounter_id) is True
    assert _encounter_status(encounter_id) == 'resolving_victory'
    assert claim_pve_encounter_victory(encounter_id=encounter_id) is False

    for terminal_status in ('death', 'finished', 'victory'):
        conn = get_connection()
        conn.execute(
            'UPDATE pve_encounters SET status=? WHERE encounter_id=?',
            (terminal_status, encounter_id),
        )
        conn.commit()
        conn.close()
        assert claim_pve_encounter_victory(encounter_id=encounter_id) is False


def test_pre_reward_failure_releases_claim_and_safe_retry_rewards_once():
    asyncio.run(_run_pre_reward_failure_retry())


async def _run_pre_reward_failure_retry():
    _create_player()
    conn=get_connection();conn.execute("UPDATE players SET location_id='westwild_n3' WHERE telegram_id=?",(PLAYER_ID,));conn.commit();conn.close()
    mob = get_mob('forest_wolf')
    battle_state = init_battle(dict(get_player(PLAYER_ID)), mob)
    battle_state.update({'location_id': 'westwild_n3', 'spawn_profile': 'normal'})
    encounter_id, _ = create_or_load_open_world_pve_encounter(
        owner_player_id=PLAYER_ID, location_id='westwild_n3',
        mob_id='forest_wolf', battle_state=battle_state, mob=mob,
    )
    battle_state['pve_encounter_id'] = encounter_id
    ensure_runtime_for_battle(
        player_id=PLAYER_ID, battle_state=battle_state, mob=mob,
    )
    battle_state['mob_dead'] = True
    battle_state['mob_hp'] = 0
    for unit in battle_state.get('enemy_units', []):
        unit['dead'] = True
        unit['hp'] = 0
    query = SimpleNamespace(edit_message_text=AsyncMock())
    context = SimpleNamespace(user_data={'battle': battle_state, 'battle_mob': mob})
    before = dict(get_player(PLAYER_ID))

    with (
        patch('game.pve_reward_settlement.build_reward_plan', side_effect=RuntimeError('pre-reward failure')),
        patch('handlers.battle.safe_edit', new=AsyncMock()),
    ):
        await _handle_victory_cleanup(
            query=query, context=context, user_id=PLAYER_ID, player=before,
            mob=mob, battle_state=battle_state, lang='en',
        )
    assert _encounter_status(encounter_id) == 'active'
    assert dict(get_player(PLAYER_ID))['exp'] == before['exp']

    with (
        patch('handlers.battle.safe_edit', new=AsyncMock()),
    ):
        await _handle_victory_cleanup(
            query=query, context=context, user_id=PLAYER_ID, player=before,
            mob=mob, battle_state=battle_state, lang='en',
        )
        await _handle_victory_cleanup(
            query=query, context=context, user_id=PLAYER_ID,
            player=dict(get_player(PLAYER_ID)), mob=mob,
            battle_state=battle_state, lang='en',
        )

    after = dict(get_player(PLAYER_ID))
    receipt = get_settlement(encounter_id)['result']['recipients'][0]
    assert (after['exp'], after['gold']) == (receipt['exp_after'], receipt['gold_after'])
    assert _encounter_status(encounter_id) == 'victory'
    conn = get_connection()
    try:
        for item_id in receipt['stackable_items']:
            assert conn.execute(
                'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?',
                (PLAYER_ID, item_id),
            ).fetchone()['quantity'] >= receipt['stackable_items'].count(item_id)
    finally:
        conn.close()


def test_invalid_gathering_surface_and_unfinished_encounter_grant_nothing():
    asyncio.run(_run_negative_paths())


async def _run_negative_paths():
    _create_player()
    assert build_location_gather_source_profiles('capital_city') == ()
    before = dict(get_player(PLAYER_ID))
    conn = get_connection()
    inventory_before = conn.execute(
        'SELECT COUNT(*) AS count FROM inventory WHERE telegram_id=?', (PLAYER_ID,),
    ).fetchone()['count']
    conn.close()

    mob = get_mob('forest_wolf')
    battle_state = {
        'mob_id': 'forest_wolf', 'location_id': 'capital_city',
        'spawn_profile': 'normal', 'weapon_id': 'unarmed',
    }
    encounter_id, _ = create_or_load_open_world_pve_encounter(
        owner_player_id=PLAYER_ID, location_id='westwild_n3',
        mob_id='forest_wolf', battle_state=battle_state, mob=mob,
    )
    assert encounter_id is None
    battle_state['pve_encounter_id'] = encounter_id
    finish_solo_pve_encounter(
        player_id=PLAYER_ID, encounter_id=encounter_id, status='death',
    )
    with patch('handlers.battle.safe_edit', new=AsyncMock()):
        await _handle_victory_cleanup(
            query=SimpleNamespace(edit_message_text=AsyncMock()),
            context=SimpleNamespace(user_data={}),
            user_id=PLAYER_ID,
            player=before,
            mob=mob,
            battle_state=battle_state,
            lang='en',
        )

    message = SimpleNamespace(text='Gather', message_id=next(_message_ids), reply_text=AsyncMock())
    update = SimpleNamespace(message=message, effective_user=SimpleNamespace(id=PLAYER_ID))
    with (
        patch('handlers.location.looks_like_lower_gather_button', return_value=True),
        patch('handlers.location.resolve_lower_gather_profession_button', return_value='herbalism'),
        patch('handlers.location.has_active_live_pvp_engagement', return_value=False),
        patch('handlers.location.is_in_battle', return_value=False),
    ):
        await handle_lower_menu_gather_text(update, SimpleNamespace())

    after = dict(get_player(PLAYER_ID))
    assert (after['exp'], after['gold']) == (before['exp'], before['gold'])
    conn = get_connection()
    assert conn.execute(
        'SELECT COUNT(*) AS count FROM inventory WHERE telegram_id=?', (PLAYER_ID,),
    ).fetchone()['count'] == inventory_before
    conn.close()
