"""Partial group timeout writes must retain the same identity on every retry."""
import json
import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import database
from game import pve_live
from tests.test_pxe1_pve_world_tick import started_group


@pytest.mark.parametrize('restart', [False, True])
@pytest.mark.parametrize('manual_first', [False, True])
def test_partial_timeout_orders_match_uninterrupted_completion(restart, manual_first):
    encounter, _ = started_group()
    snapshot = sqlite3.connect(':memory:')
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.backup(snapshot)
    submit = pve_live.submit_combat_order
    now = datetime.fromtimestamp(1027, timezone.utc)

    def orders():
        with database.get_connection() as conn:
            return [dict(row) for row in conn.execute(
                'SELECT * FROM combat_orders_v1 WHERE encounter_id=? ORDER BY actor_id',
                (encounter,))]

    def durable_state():
        with database.get_connection() as conn:
            receipts = [(row[0], json.loads(row[1]), json.loads(row[2])) for row in
                conn.execute('''SELECT turn_revision,result_json,state_json
                    FROM combat_turn_results_v1 WHERE encounter_id=? ORDER BY turn_revision''',
                    (encounter,))]
            state = json.loads(conn.execute(
                'SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?',
                (encounter,)).fetchone()[0])
            players = [dict(row) for row in conn.execute('SELECT * FROM players ORDER BY telegram_id')]
        return receipts, state, players, orders()

    def run(interrupted):
        with sqlite3.connect(database.DB_PATH) as conn:
            snapshot.backup(conn)
        pve_live.reset_solo_pve_runtime_store()
        state, mob = pve_live.load_active_pve_encounter(encounter_id=encounter)
        runtime = pve_live.ensure_runtime_for_battle(
            player_id=1, battle_state=state, mob=mob, now=now)
        revision = runtime.turn_revision
        assert runtime.active_side_id == pve_live.SIDE_PLAYER
        assert runtime.side_deadline_at <= now
        if manual_first:
            # Exercise restoration of a real manual order, rather than only its
            # already-committed in-memory projection.
            assert submit(encounter_kind='pve', encounter_id=encounter,
                turn_revision=revision, actor_id=1,
                action={'kind': 'basic_attack'}, target_id=None,
                deadline_at=state['side_deadline_at'], order_kind='manual')['accepted']

        actions = []

        def observe(action):
            actions.append((action.participant_id, action.action_type, action.source))
            pve_live._dispatch_v1_player_action(action, battle_state=state)

        def resolve():
            return pve_live.resolve_due_player_timeout_if_any(
                player_id=1, battle_state=state, now=now, on_player_action=observe)

        def fail_second(**kwargs):
            if kwargs['actor_id'] == 777:
                raise sqlite3.OperationalError('second timeout order write failed')
            return submit(**kwargs)

        with patch('game.pve_live._utc_now', return_value=now):
            if interrupted:
                with patch('game.pve_live.submit_combat_order', side_effect=fail_second):
                    with pytest.raises(sqlite3.OperationalError, match='second timeout order'):
                        resolve()
                accepted = orders()
                assert len(accepted) == 1 and accepted[0]['actor_id'] == 1
                assert accepted[0]['order_kind'] == ('manual' if manual_first else 'timeout')
                assert not actions and durable_state()[0] == []
                if restart:
                    pve_live.reset_solo_pve_runtime_store()
                    state, mob = pve_live.load_active_pve_encounter(encounter_id=encounter)
                    pve_live.ensure_runtime_for_battle(
                        player_id=1, battle_state=state, mob=mob, now=now)
            assert resolve()
            if interrupted:
                assert accepted[0] in orders()  # Including immutable creation time.
            expected_sources = ['commit' if manual_first else 'fallback', 'fallback']
            assert [action[0] for action in actions] == [1, 777]
            assert [action[2] for action in actions] == expected_sources
            phases = {'1': 'committed' if manual_first else 'auto_fallback',
                      '777': 'auto_fallback'}
            assert state['ally_commit_status'] == phases
            result = durable_state()
            assert len(result[0]) == 1 and result[0][0][0] == revision
            assert [action['source'] for action in result[0][0][1]['actions']] == expected_sources
            assert result[0][0][2]['ally_commit_status'] == phases
            assert result[1] == state
            assert state['turn_revision'] == revision
            assert state['side_turn_state'] == 'completed'
            assert state['active_side'] == pve_live.SIDE_ENEMY
            assert not pve_live.resolve_current_side_if_ready(
                player_id=1, battle_state=state, on_player_action=observe,
                on_enemy_action=lambda _action: None)
            assert durable_state() == result and len(actions) == 2
        # Creation times differ between independent control/recovery executions;
        # each accepted row is checked byte-for-byte within its own execution.
        semantic_orders = [{key: value for key, value in row.items() if key != 'created_at'}
                           for row in result[3]]
        return result[:3], semantic_orders, actions

    try:
        expected = run(False)
        assert run(True) == expected
    finally:
        snapshot.close()
