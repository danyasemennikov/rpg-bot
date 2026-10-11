"""Differential regressions for the residual F2/F3 narrow-review blockers."""
import copy
import json
import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import database
from game import pve_live
from tests.conftest import isolated_sqlite_db
from tests.test_pxe1_pve_world_tick import started, started_group


@pytest.mark.parametrize('revision', [2, 4, 5])
@pytest.mark.parametrize('fault', ['before_result', 'after_vitals', 'after_commit'])
@pytest.mark.parametrize('restart', [False, True])
@pytest.mark.parametrize('group_effects', [False, True])
def test_later_round_full_recovery_equivalence(revision, fault, restart, group_effects):
    encounter, _ = (started_group if group_effects else started)()
    state, mob = pve_live.load_active_pve_encounter(encounter_id=encounter)
    state['combat_seed'] = '01' * 16
    with database.get_connection() as conn:
        conn.execute('UPDATE pve_encounters SET combat_seed=? WHERE encounter_id=?',
                     (state['combat_seed'], encounter))
        conn.commit()
    for enemy in state['enemy_states_v1']:
        enemy.update(hp=10000, max_hp=10000)
        if group_effects:
            enemy['on_hit_behaviors'] = ['venom_third_hit', 'leech_third_hit']
            enemy['effects'] = [{'kind': 'burn', 'source_id': 777, 'duration': 3,
                'raw_tick': 1, 'created_side_index': 0, 'school': 'magic', 'metadata': {}}]
    if group_effects:
        for actor in state['participant_states_v1'].values():
            actor['effects'] = [{'kind': 'regeneration', 'source_id': actor['actor_id'],
                'duration': 3, 'value': 1, 'created_side_index': 0, 'metadata': {}}]
    pve_live._sync_v1_to_legacy_projection(state)
    assert pve_live.persist_solo_pve_encounter_state(
        encounter_id=encounter, battle_state=state, mob=mob)
    writer = pve_live.persist_turn_result
    vitals = pve_live.persist_pxe1_participant_vitals
    dispatch = pve_live._dispatch_v1_enemy_action
    evaluate = pve_live.evaluate_enemy_action
    snapshot = sqlite3.connect(':memory:')
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.backup(snapshot)

    def orders(conn):
        # SQLite creation timestamps measure wall clock, not combat identity.
        return [tuple(row) for row in conn.execute('''SELECT encounter_kind,
            encounter_id,turn_revision,actor_id,action_json,target_id,rules_version,
            deadline_at,order_kind FROM combat_orders_v1 ORDER BY turn_revision,actor_id''')]

    def durable_state():
        with database.get_connection() as conn:
            receipts = [(row[0], json.loads(row[1]), json.loads(row[2])) for row in
                conn.execute('''SELECT turn_revision,result_json,state_json
                FROM combat_turn_results_v1 WHERE encounter_id=? ORDER BY turn_revision''',
                (encounter,))]
            players = [dict(row) for row in conn.execute('SELECT * FROM players ORDER BY telegram_id')]
            row = conn.execute('SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?',
                               (encounter,)).fetchone()
            return receipts, players, json.loads(row[0]), orders(conn)

    def run(inject):
        with sqlite3.connect(database.DB_PATH) as conn:
            snapshot.backup(conn)
        pve_live.reset_solo_pve_runtime_store()
        hit = []
        evaluations = {}
        attempts = []
        active_revision = None

        def observe(action, *, battle_state):
            nonlocal active_revision
            runtime = pve_live._SOLO_PVE_RUNTIME_STORE.get(encounter)
            assert battle_state['turn_revision'] == runtime.turn_revision
            assert battle_state['round_index'] == runtime.round_index
            assert battle_state['active_side'] == runtime.active_side_id
            active_revision = runtime.turn_revision
            return dispatch(action, battle_state=battle_state)

        def observe_evaluation(*args, **kwargs):
            result = evaluate(*args, **kwargs)
            value = copy.deepcopy((args, kwargs, result))
            attempts.append((active_revision, value))
            evaluations[active_revision] = value
            return result

        def fail_vitals(*args, **kwargs):
            vitals(*args, **kwargs)
            raise sqlite3.OperationalError('rollback after transactional vitals')

        def write(**kwargs):
            if inject and not hit and kwargs['turn_revision'] == revision:
                hit.append(revision)
                with database.get_connection() as conn:
                    accepted_orders = [tuple(row) for row in conn.execute(
                        'SELECT * FROM combat_orders_v1 ORDER BY turn_revision,actor_id')]
                if fault == 'before_result':
                    raise sqlite3.OperationalError('before result')
                if fault == 'after_vitals':
                    with patch('game.pve_live.persist_pxe1_participant_vitals', side_effect=fail_vitals):
                        return writer(**kwargs)
                result = writer(**kwargs)
                assert result['applied']
                with database.get_connection() as conn:
                    assert accepted_orders == [tuple(row) for row in conn.execute(
                        'SELECT * FROM combat_orders_v1 ORDER BY turn_revision,actor_id')]
                raise sqlite3.OperationalError('ambiguous successful commit')
            return writer(**kwargs)

        with patch('game.pve_live._dispatch_v1_enemy_action', side_effect=observe), \
                patch('game.pve_live.evaluate_enemy_action', side_effect=observe_evaluation):
            for now in (1027, 1043, 1059):
                with patch('game.pve_live._utc_now', return_value=datetime.fromtimestamp(now, timezone.utc)):
                    with patch('game.pve_live.persist_turn_result', side_effect=write):
                        pve_live.process_due_pve_world_sides(now_ms=now * 1000, encounter_id=encounter)
                    with database.get_connection() as conn:
                        accepted = [tuple(row) for row in conn.execute(
                            'SELECT * FROM combat_orders_v1 ORDER BY turn_revision,actor_id')]
                    if restart:
                        pve_live.reset_solo_pve_runtime_store()
                    pve_live.process_due_pve_world_sides(now_ms=now * 1000, encounter_id=encounter)
                    with database.get_connection() as conn:
                        after = [tuple(row) for row in conn.execute(
                            'SELECT * FROM combat_orders_v1 ORDER BY turn_revision,actor_id')]
                    assert all(row in after for row in accepted)  # Accepted orders never replaced.
                    stable = durable_state()
                    for _ in range(2):
                        assert pve_live.process_due_pve_world_sides(
                            now_ms=now * 1000, encounter_id=encounter) == []
                        assert durable_state() == stable
        if inject:
            assert hit == [revision]
        result = durable_state()
        assert [row[0] for row in result[0]] == [1, 2, 3, 4, 5, 6]
        assert result[2]['turn_revision'] == 7
        assert result[2]['round_index'] == 4
        assert result[2]['active_side'] == pve_live.SIDE_PLAYER
        return result, evaluations, attempts

    try:
        expected, control_evaluations, _ = run(False)
        actual, recovered_evaluations, attempts = run(True)
        def differences(left, right, path=''):
            if type(left) != type(right):
                return [(path, left, right)]
            if isinstance(left, dict):
                return [d for key in left.keys() | right.keys() for d in
                        differences(left.get(key), right.get(key), path + '/' + str(key))]
            if isinstance(left, (list, tuple)):
                if len(left) != len(right):
                    return [(path + '/length', len(left), len(right))]
                return [d for index in range(len(left)) for d in
                        differences(left[index], right[index], path + '/' + str(index))]
            return [] if left == right else [(path, left, right)]
        assert actual == expected, differences(expected, actual)
        assert recovered_evaluations == control_evaluations
        for evaluated_revision, value in attempts:
            assert value == control_evaluations[evaluated_revision]  # Includes rolled-back attempts.
    finally:
        snapshot.close()


@pytest.mark.parametrize('restart', [False, True])
def test_partial_enemy_orders_are_reused_and_only_missing_orders_submitted(restart):
    from game.build_progression import migrate_character_builds_v1
    migrate_character_builds_v1()
    with database.get_connection() as conn:
        conn.execute("UPDATE players SET location_id='westwild_n8'")
        conn.commit()
    with patch('time.time', return_value=1000):
        encounter, status = pve_live.create_mixed_open_world_pve_encounter(
            owner_player_id=1, recipe_id='westwild_n8_mixed',
            side_a_player_ids=[1, 777], battle_state={})
    assert status == 'created'
    assert pve_live.process_due_pve_formations(now_ms=1012000)[0]['phase'] == 'active'
    state, mob = pve_live.load_active_pve_encounter(encounter_id=encounter)
    for enemy in state['enemy_states_v1']:
        enemy.update(hp=10000, max_hp=10000)
    pve_live._sync_v1_to_legacy_projection(state)
    assert pve_live.persist_solo_pve_encounter_state(
        encounter_id=encounter, battle_state=state, mob=mob)
    submit = pve_live.submit_combat_order
    inserted = []

    def interrupted(**kwargs):
        if kwargs['order_kind'] == 'ai':
            inserted.append(kwargs['actor_id'])
            if len(inserted) == 2:
                raise sqlite3.OperationalError('exit with partially committed AI orders')
        return submit(**kwargs)

    now = datetime.fromtimestamp(1027, timezone.utc)
    with patch('game.pve_live._utc_now', return_value=now):
        with patch('game.pve_live.submit_combat_order', side_effect=interrupted):
            pve_live.process_due_pve_world_sides(now_ms=1027000, encounter_id=encounter)
        with database.get_connection() as conn:
            accepted = [tuple(row) for row in conn.execute(
                "SELECT * FROM combat_orders_v1 WHERE encounter_id=? AND order_kind='ai'",
                (encounter,))]
        assert len(accepted) == 1
        if restart:
            pve_live.reset_solo_pve_runtime_store()
        with patch('game.pve_live.submit_combat_order', wraps=submit) as retried:
            result = pve_live.process_due_pve_world_sides(now_ms=1027000, encounter_id=encounter)
        assert result[0]['phase'] == 'active'
        ai_calls = [call.kwargs['actor_id'] for call in retried.call_args_list
                    if call.kwargs['order_kind'] == 'ai']
        assert len(ai_calls) == 2
        assert accepted[0][3] not in ai_calls
        with database.get_connection() as conn:
            after = [tuple(row) for row in conn.execute(
                "SELECT * FROM combat_orders_v1 WHERE encounter_id=? AND order_kind='ai'",
                (encounter,))]
            assert len(after) == 3 and accepted[0] in after
            receipt = json.loads(conn.execute('''SELECT result_json FROM combat_turn_results_v1
                WHERE encounter_id=? AND turn_revision=2''', (encounter,)).fetchone()[0])
            assert len(receipt['actions']) == 3
            assert len({action['actor_id'] for action in receipt['actions']}) == 3
        assert pve_live.process_due_pve_world_sides(now_ms=1027000, encounter_id=encounter) == []
