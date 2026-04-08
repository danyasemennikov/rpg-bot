import unittest
from datetime import datetime, timedelta, timezone

from game.pve_live import (
    SIDE_ENEMY,
    SIDE_PLAYER,
    _SOLO_PVE_RUNTIME_STORE,
    clear_solo_pve_runtime,
    ensure_runtime_for_battle,
    process_due_timeout_for_battle,
    resolve_current_side_if_ready,
    resolve_due_player_timeout_if_any,
    run_enemy_instant_side,
    submit_player_commit,
)


class SoloPveRuntimeAdapterTests(unittest.TestCase):
    def setUp(self):
        _SOLO_PVE_RUNTIME_STORE.reset()
        self.player_id = 701001
        self.battle_state = {'mob_id': 'forest_wolf', 'log': []}

    def tearDown(self):
        clear_solo_pve_runtime(self.player_id)
        _SOLO_PVE_RUNTIME_STORE.reset()

    def test_battle_start_creates_runtime_state_and_player_side_deadline(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        state = ensure_runtime_for_battle(player_id=self.player_id, battle_state=self.battle_state, now=now)

        self.assertEqual(state.active_side_id, SIDE_PLAYER)
        self.assertEqual(state.turn_revision, 1)
        self.assertEqual(state.side_deadline_at, now + timedelta(seconds=15))
        self.assertEqual(self.battle_state['active_side'], SIDE_PLAYER)

    def test_player_commit_resolves_then_enemy_instant_side_runs(self):
        ensure_runtime_for_battle(player_id=self.player_id, battle_state=self.battle_state)

        accepted, reason = submit_player_commit(player_id=self.player_id, action_type='basic_attack')
        self.assertTrue(accepted)
        self.assertEqual(reason, 'committed')

        events = []
        resolved = resolve_current_side_if_ready(
            player_id=self.player_id,
            on_player_action=lambda action: events.append(('player', action.action_type)),
            on_enemy_action=lambda action: events.append(('enemy', action.action_type)),
        )
        self.assertTrue(resolved)
        self.assertEqual(events, [('player', 'basic_attack')])

        run_enemy_instant_side(
            player_id=self.player_id,
            battle_state=self.battle_state,
            on_enemy_action=lambda action: events.append(('enemy', action.action_type)),
        )
        self.assertIn(('enemy', 'enemy_basic_attack'), events)
        self.assertEqual(self.battle_state['active_side'], SIDE_PLAYER)

    def test_timeout_fallback_and_late_manual_commit_does_not_double_resolve(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        ensure_runtime_for_battle(player_id=self.player_id, battle_state=self.battle_state, now=now)

        resolved = resolve_due_player_timeout_if_any(
            player_id=self.player_id,
            now=now + timedelta(seconds=16),
            on_player_action=lambda _action: None,
        )
        self.assertTrue(resolved)

        accepted, reason = submit_player_commit(player_id=self.player_id, action_type='basic_attack')
        self.assertFalse(accepted)
        self.assertIn(reason, ('turn_not_collecting', 'stale_revision'))

    def test_next_round_advances_after_player_and_enemy_sides(self):
        ensure_runtime_for_battle(player_id=self.player_id, battle_state=self.battle_state)

        accepted, _ = submit_player_commit(player_id=self.player_id, action_type='basic_attack')
        self.assertTrue(accepted)

        resolve_current_side_if_ready(
            player_id=self.player_id,
            on_player_action=lambda _action: None,
            on_enemy_action=lambda _action: None,
        )
        run_enemy_instant_side(
            player_id=self.player_id,
            battle_state=self.battle_state,
            on_enemy_action=lambda _action: None,
        )

        state = _SOLO_PVE_RUNTIME_STORE.get(f'solo-pve-{self.player_id}')
        self.assertIsNotNone(state)
        self.assertEqual(state.active_side_id, SIDE_PLAYER)
        self.assertEqual(state.round_index, 2)

    def test_clear_runtime_removes_runtime_state(self):
        ensure_runtime_for_battle(player_id=self.player_id, battle_state=self.battle_state)
        self.assertIsNotNone(_SOLO_PVE_RUNTIME_STORE.get(f'solo-pve-{self.player_id}'))
        clear_solo_pve_runtime(self.player_id)
        self.assertIsNone(_SOLO_PVE_RUNTIME_STORE.get(f'solo-pve-{self.player_id}'))

    def test_due_timeout_orchestration_runs_enemy_instant_side(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        ensure_runtime_for_battle(player_id=self.player_id, battle_state=self.battle_state, now=now)

        events = []
        handled = process_due_timeout_for_battle(
            player_id=self.player_id,
            battle_state=self.battle_state,
            now=now + timedelta(seconds=16),
            on_player_timeout_action=lambda action: events.append(('player', action.action_type)),
            on_enemy_action=lambda action: events.append(('enemy', action.action_type)),
        )

        self.assertTrue(handled)
        self.assertEqual(events[0], ('player', 'fallback_guard'))
        self.assertIn(('enemy', 'enemy_basic_attack'), events)
        self.assertEqual(self.battle_state['active_side'], SIDE_PLAYER)


if __name__ == '__main__':
    unittest.main()
