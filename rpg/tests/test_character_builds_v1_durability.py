from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from database import get_connection
from game.build_contract import RULES_VERSION
from game.build_progression import ensure_build_schema
from game.build_progression import migrate_character_builds_v1
from game.combat_orders import consume_combat_intent, issue_combat_intents, load_combat_orders
from game.pve_reward_settlement import _v1_mastery_awards
from game.pve_live import (
    ensure_runtime_for_battle,
    get_pve_encounter_player_ids,
    resolve_pve_flee_intent,
    reset_solo_pve_runtime_store,
    run_enemy_instant_side,
)
from game.pvp_live import (
    _LIVE_PVP_RUNTIME_STORE,
    _deserialize_reason_context,
    _ensure_live_runtime_for_battle,
    _init_live_battle_payload,
    _write_engagement_state,
    create_live_engagement,
    issue_manual_pvp_action_labels,
    resolve_live_battle_turn,
    _finalize_pvp_battle,
)
from handlers import battle as battle_handler


def test_mastery_awards_only_manual_survivors_with_frozen_family_and_caps_at_80():
    state = {
        "participant_states_v1": {
            "1": {"family": "bow", "level": 10, "manual_contribution": True},
            "2": {"family": "wand", "level": 10, "manual_contribution": False},
            "3": {"family": "unarmed", "level": 10, "manual_contribution": True},
        }
    }
    units = [
        {"unit_id": "a", "mob_level": 10, "spawn_profile": "normal"},
        {"unit_id": "b", "mob_level": 10, "spawn_profile": "elite"},
        {"unit_id": "c", "mob_level": 1, "spawn_profile": "rare"},
        {"unit_id": "d", "mob_level": 10, "spawn_profile": "normal"},
    ]
    assert _v1_mastery_awards(battle_state=state, eligible=[1, 2, 3], units=units) == [{
        "player_id": 1,
        "weapon_id": "bow",
        "exp": 80,
        "units": [
            {"unit_id": "a", "mob_level": 10, "spawn_profile": "normal", "exp": 20},
            {"unit_id": "b", "mob_level": 10, "spawn_profile": "elite", "exp": 40},
            {"unit_id": "c", "mob_level": 1, "spawn_profile": "rare", "exp": 10},
            {"unit_id": "d", "mob_level": 10, "spawn_profile": "normal", "exp": 20},
        ],
    }]


def test_pve_ui_intent_is_single_use_deadline_bound_and_durable():
    conn = get_connection()
    ensure_build_schema(conn)
    conn.execute(
        """INSERT INTO pve_encounters
        (encounter_id, owner_player_id, status, mob_id, battle_state_json, mob_json,
         source_units_json, rules_version, turn_revision)
        VALUES ('intent-v1', 1, 'active', 'rat', '{}', '{}', '[]', ?, 0)""",
        (RULES_VERSION,),
    )
    conn.execute(
        "INSERT INTO pve_encounter_participants (encounter_id, player_id, status) VALUES ('intent-v1', 1, 'active')"
    )
    conn.commit()
    conn.close()

    deadline = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
    action = {"kind": "normal", "target_info": {"id": "enemy-1"}}
    token = issue_combat_intents(
        1, encounter_id="intent-v1", turn_revision=1,
        deadline_at=deadline, actions=[action],
    )[__import__("json").dumps(action, ensure_ascii=False, sort_keys=True, separators=(",", ":"))]
    assert consume_combat_intent(1, token)["accepted"] is True
    assert consume_combat_intent(1, token) == {"accepted": False, "reason": "stale_action"}
    orders = load_combat_orders(encounter_kind="pve", encounter_id="intent-v1", turn_revision=1)
    assert len(orders) == 1
    assert orders[0]["action"] == action


def test_v1_pvp_uses_opaque_durable_order_and_recovers_it_after_runtime_loss():
    migrate_character_builds_v1()
    attacker = 1
    defender = 777
    conn = get_connection()
    attacker_row = dict(conn.execute("SELECT * FROM players WHERE telegram_id=?", (attacker,)).fetchone())
    defender_row = dict(conn.execute("SELECT * FROM players WHERE telegram_id=?", (defender,)).fetchone())
    conn.close()
    engagement_id = create_live_engagement(
        attacker=attacker_row, defender=defender_row,
        location_id="capital_city", illegal_aggression=False,
    )
    conn = get_connection()
    row = conn.execute("SELECT * FROM pvp_engagements WHERE id=?", (engagement_id,)).fetchone()
    conn.close()
    battle = _init_live_battle_payload(
        attacker_id=attacker, defender_id=defender, now=datetime.now(timezone.utc),
    )
    _ensure_live_runtime_for_battle(engagement_row=row, battle=battle)
    initial_attacker_mana = battle["participants_v1"][str(attacker)]["mana"]
    payload = {"flow": "open_world_1v1", "battle": battle}
    _write_engagement_state(engagement_id=engagement_id, state="converted_to_battle", payload=payload)

    actions = issue_manual_pvp_action_labels(
        engagement_id=engagement_id, player_id=attacker, lang="en", battle=battle,
        attacker_id=attacker, defender_id=defender,
    )
    assert len(actions) == 3  # normal, Guard, universal Power Strike
    normal_token = actions[0][0]
    consumed = consume_combat_intent(attacker, normal_token)
    assert consumed["accepted"] is True
    assert consumed["encounter_kind"] == "pvp"

    # Simulate a process crash after the atomic order insert but before the
    # in-memory runtime receives/resolves that order.
    _LIVE_PVP_RUNTIME_STORE.reset()
    conn = get_connection()
    row = conn.execute("SELECT * FROM pvp_engagements WHERE id=?", (engagement_id,)).fetchone()
    conn.close()
    status, result_payload = resolve_live_battle_turn(
        row, actor_id=attacker, selected_action_id=None,
    )
    assert status == "resolved"
    assert result_payload["battle"]["turn_owner"] == defender
    assert result_payload["battle"]["participants_v1"][str(attacker)]["mana"] > initial_attacker_mana
    conn = get_connection()
    result = conn.execute(
        "SELECT result_json FROM combat_turn_results_v1 WHERE encounter_kind='pvp' AND encounter_id=?",
        (str(engagement_id),),
    ).fetchone()
    persisted = conn.execute("SELECT reason_context FROM pvp_engagements WHERE id=?", (engagement_id,)).fetchone()
    conn.close()
    assert result is not None
    assert _deserialize_reason_context(persisted["reason_context"])["battle"]["turn_owner"] == defender


def test_v1_mob_first_uses_shared_enemy_side_not_legacy_strike():
    player = {
        'telegram_id': 1, 'name': 'Hero', 'lang': 'en', 'location_id': 'westwild_n1',
        'hp': 118, 'mana': 62, 'level': 1, 'strength': 1, 'agility': 1,
        'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1,
    }
    effective = {
        **{key: player[key] for key in ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck')},
        'max_hp': 118, 'max_mana': 62, 'physical_defense_bonus': 0,
        'magic_defense_bonus': 0, 'accuracy_bonus': 0, 'evasion_bonus': 0,
        'block_chance_bonus': 0, 'magic_power_bonus': 0, 'healing_power_bonus': 0,
    }
    battle = {
        'mob_id': 'westwild_rabbit', 'log': [], 'player_hp': 118, 'player_max_hp': 118,
        'player_mana': 62, 'player_max_mana': 62,
    }
    query = SimpleNamespace(
        from_user=SimpleNamespace(id=1), answer=AsyncMock(), edit_message_text=AsyncMock(),
    )
    context = SimpleNamespace(user_data={}, application=SimpleNamespace(user_data={1: {}}))

    def create_v1(**kwargs):
        kwargs['battle_state'].update({
            'rules_version': RULES_VERSION, 'participant_states_v1': {
                '1': {'actor_id': 1, 'hp': 118, 'max_hp': 118, 'mana': 62, 'max_mana': 62},
            },
            'enemy_states_v1': [{'unit_id': 'enemy-1', 'hp': 20, 'max_hp': 20}],
        })
        return 'v1-first', 'created'

    with patch('handlers.battle.get_player', return_value=player), \
         patch('handlers.battle.get_mob', return_value={'id': 'westwild_rabbit', 'hp': 20, 'level': 1}), \
         patch('handlers.battle.get_equipped_combat_items', return_value={}), \
         patch('handlers.battle.get_player_effective_stats', return_value=effective), \
         patch('handlers.battle.get_mastery', return_value={'level': 1, 'exp': 0}), \
         patch('handlers.battle.init_battle', return_value=battle), \
         patch('handlers.battle.create_or_load_open_world_pve_encounter', side_effect=create_v1), \
         patch('handlers.battle.ensure_runtime_for_battle'), \
         patch('handlers.battle.run_enemy_instant_side') as enemy_side, \
         patch('handlers.battle.sync_projection_for_participant'), \
         patch('handlers.battle.update_participant_combat_state_from_projection'), \
         patch('handlers.battle.persist_solo_pve_encounter_state'), \
         patch('handlers.battle.save_battle'), \
         patch('handlers.battle.build_battle_message', return_value=('battle', None)), \
         patch('game.combat.mob_attack', side_effect=AssertionError('legacy bypass')):
        asyncio.run(battle_handler.start_battle(
            SimpleNamespace(callback_query=query), context, 'westwild_rabbit', mob_first=True,
        ))

    enemy_side.assert_called_once()
    assert battle['active_side'] == 'side_b'


def test_enemy_side_dot_kill_refreshes_terminal_projection_for_settlement():
    reset_solo_pve_runtime_store()
    migrate_character_builds_v1()
    effect = {
        'kind': 'bleed', 'source_id': '1', 'skill_id': 'bleeding_cut',
        'duration': 1, 'value': 0, 'created_side_index': 0,
        'school': 'physical', 'raw_tick': 5,
        'metadata': {'source_level': 1, 'weakness_snapshot': 0},
    }
    battle = {
        'rules_version': RULES_VERSION,
        'mob_id': 'westwild_rabbit',
        'mob_hp': 1,
        'mob_dead': False,
        'active_side': 'side_b',
        'log': [],
        'participant_states_v1': {
            '1': {'actor_id': 1, 'hp': 100, 'max_hp': 100, 'mana': 50,
                  'max_mana': 50, 'effects': [], 'cooldowns': {}},
        },
        'enemy_states_v1': [
            {'unit_id': 'enemy-dot', 'mob_id': 'westwild_rabbit', 'hp': 1,
             'max_hp': 22, 'effects': [effect]},
        ],
        'enemy_units': [
            {'unit_id': 'enemy-dot', 'mob_id': 'westwild_rabbit', 'hp': 1,
             'max_hp': 22, 'dead': False},
        ],
    }
    ensure_runtime_for_battle(
        player_id=1, battle_state=battle,
        mob={'id': 'westwild_rabbit', 'hp': 22},
    )
    battle['enemy_states_v1'][0].update({'hp': 1, 'effects': [effect]})
    battle['enemy_units'][0].update({'hp': 1, 'dead': False})
    battle['mob_hp'] = 1
    battle['mob_dead'] = False
    run_enemy_instant_side(
        player_id=1, battle_state=battle,
        on_enemy_action=lambda _action: None,
    )

    assert battle['enemy_states_v1'][0]['hp'] == 0
    assert battle['enemy_units'][0]['dead'] is True
    assert battle['mob_hp'] == 0
    assert battle['mob_dead'] is True


def test_group_flee_is_participant_scoped_and_replays_durable_result():
    migrate_character_builds_v1()
    state = {
        'rules_version': RULES_VERSION, 'turn_revision': 0, 'state_revision': 0,
        'side_a_player_ids': [1, 777], 'participant_states_v1': {
            '1': {'actor_id': 1, 'hp': 73, 'mana': 21},
            '777': {'actor_id': 777, 'hp': 88, 'mana': 32},
        },
        'participant_states': {
            '1': {'hp': 73, 'mana': 21, 'player_hp': 73, 'player_mana': 21},
            '777': {'hp': 88, 'mana': 32, 'player_hp': 88, 'player_mana': 32},
        },
    }
    conn = get_connection()
    ensure_build_schema(conn)
    conn.execute('''INSERT INTO pve_encounters
        (encounter_id, owner_player_id, status, mob_id, battle_state_json, mob_json,
         source_units_json, rules_version, turn_revision, state_revision)
        VALUES ('group-flee', 1, 'active', 'westwild_rabbit', ?, '{}', '[]', ?, 0, 0)''',
        (json.dumps(state), RULES_VERSION))
    conn.executemany('''INSERT INTO pve_encounter_participants
        (encounter_id, player_id, side_id, status) VALUES ('group-flee', ?, 'side_a', 'active')''',
        [(1,), (777,)])
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id IN (1, 777)')
    conn.commit()
    conn.close()
    action = {'kind': 'flee', 'skill_id': None, 'item_id': None, 'target_info': None}
    deadline = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
    token = issue_combat_intents(
        1, encounter_id='group-flee', turn_revision=0, deadline_at=deadline, actions=[action],
    )[json.dumps(action, ensure_ascii=False, sort_keys=True, separators=(',', ':'))]
    first = resolve_pve_flee_intent(
        player_id=1, encounter_id='group-flee', action_token=token, success=True,
    )
    replay = resolve_pve_flee_intent(
        player_id=1, encounter_id='group-flee', action_token=token, success=False,
    )
    assert first['fled'] is True
    assert replay['fled'] is True and replay['already_applied'] is True
    assert get_pve_encounter_player_ids(encounter_id='group-flee') == [777]
    conn = get_connection()
    encounter = conn.execute("""SELECT status, state_revision, battle_state_json
        FROM pve_encounters WHERE encounter_id='group-flee'""").fetchone()
    players = {row['telegram_id']: row['in_battle'] for row in conn.execute(
        'SELECT telegram_id, in_battle FROM players WHERE telegram_id IN (1, 777)')}
    conn.close()
    assert encounter['status'] == 'active'
    assert int(encounter['state_revision']) == 1
    assert json.loads(str(encounter['battle_state_json']))['state_revision'] == 1
    assert players == {1: 0, 777: 1}


def test_terminal_pvp_settlement_rolls_back_failure_and_applies_exactly_once():
    migrate_character_builds_v1()
    conn = get_connection()
    attacker = dict(conn.execute('SELECT * FROM players WHERE telegram_id=1').fetchone())
    defender = dict(conn.execute('SELECT * FROM players WHERE telegram_id=777').fetchone())
    conn.execute("UPDATE players SET location_id='westwild_n1' WHERE telegram_id IN (1, 777)")
    conn.execute("INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (777, 'wolf_pelt', 10)")
    conn.commit()
    attacker['location_id'] = defender['location_id'] = 'westwild_n1'
    conn.close()
    engagement_id = create_live_engagement(
        attacker=attacker, defender=defender, location_id='westwild_n1', illegal_aggression=False,
    )
    conn = get_connection()
    conn.execute("UPDATE pvp_engagements SET engagement_state='converted_to_battle', rules_version=? WHERE id=?", (
        RULES_VERSION, engagement_id,
    ))
    row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
    conn.commit()
    conn.close()
    payload = {'flow': 'open_world_1v1', 'battle': {
        'state': 'live', 'attacker_hp': 70, 'attacker_mana': 25,
        'defender_hp': 0, 'defender_mana': 10,
    }}
    try:
        _finalize_pvp_battle(
            engagement_row=row, payload=payload, winner_id=1, loser_id=777,
            failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError(point)) if point == 'after_inventory' else None,
        )
    except RuntimeError as exc:
        assert str(exc) == 'after_inventory'
    conn = get_connection()
    assert conn.execute('SELECT 1 FROM pvp_terminal_settlements_v1 WHERE engagement_id=?', (engagement_id,)).fetchone() is None
    assert conn.execute('SELECT COUNT(*) AS total FROM pvp_log WHERE attacker_id=1 AND defender_id=777').fetchone()['total'] == 0
    assert conn.execute("SELECT quantity FROM inventory WHERE telegram_id=777 AND item_id='wolf_pelt'").fetchone()['quantity'] == 10
    conn.close()
    first = _finalize_pvp_battle(engagement_row=row, payload=payload, winner_id=1, loser_id=777)
    replay = _finalize_pvp_battle(engagement_row=row, payload=payload, winner_id=1, loser_id=777)
    assert first['status'] == 'applied'
    assert replay['already_applied'] is True
    conn = get_connection()
    assert conn.execute('SELECT COUNT(*) AS total FROM pvp_log WHERE attacker_id=1 AND defender_id=777').fetchone()['total'] == 1
    conn.close()
