import unittest
from datetime import datetime, timedelta, timezone

from game.pve_live import (
    SIDE_ENEMY,
    SIDE_PLAYER,
    _SOLO_PVE_RUNTIME_STORE,
    finish_solo_pve_encounter,
    get_active_solo_pve_encounter_id,
    load_active_solo_pve_encounter,
    ensure_runtime_for_battle,
    persist_solo_pve_encounter_state,
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
        self.mob = {'id': 'forest_wolf', 'hp': 20}

    def tearDown(self):
        finish_solo_pve_encounter(player_id=self.player_id, status='test_cleanup')
        _SOLO_PVE_RUNTIME_STORE.reset()

    def test_battle_start_creates_runtime_state_and_player_side_deadline(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        state = ensure_runtime_for_battle(
            player_id=self.player_id,
            battle_state=self.battle_state,
            mob=self.mob,
            now=now,
        )

        self.assertEqual(state.active_side_id, SIDE_PLAYER)
        self.assertEqual(state.turn_revision, 1)
        self.assertEqual(state.side_deadline_at, now + timedelta(seconds=15))
        self.assertEqual(self.battle_state['active_side'], SIDE_PLAYER)
        self.assertTrue(str(self.battle_state.get('pve_encounter_id', '')).startswith('pve-enc-'))
        self.assertEqual(self.battle_state['runtime_encounter_id'], self.battle_state['pve_encounter_id'])

    def test_player_commit_resolves_then_enemy_instant_side_runs(self):
        ensure_runtime_for_battle(player_id=self.player_id, battle_state=self.battle_state, mob=self.mob)

        accepted, reason = submit_player_commit(
            player_id=self.player_id,
            action_type='basic_attack',
            battle_state=self.battle_state,
        )
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
        ensure_runtime_for_battle(player_id=self.player_id, battle_state=self.battle_state, mob=self.mob, now=now)

        resolved = resolve_due_player_timeout_if_any(
            player_id=self.player_id,
            now=now + timedelta(seconds=16),
            on_player_action=lambda _action: None,
        )
        self.assertTrue(resolved)

        accepted, reason = submit_player_commit(
            player_id=self.player_id,
            action_type='basic_attack',
            battle_state=self.battle_state,
        )
        self.assertFalse(accepted)
        self.assertIn(reason, ('turn_not_collecting', 'stale_revision'))

    def test_next_round_advances_after_player_and_enemy_sides(self):
        ensure_runtime_for_battle(player_id=self.player_id, battle_state=self.battle_state, mob=self.mob)

        accepted, _ = submit_player_commit(
            player_id=self.player_id,
            action_type='basic_attack',
            battle_state=self.battle_state,
        )
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

        state = _SOLO_PVE_RUNTIME_STORE.get(self.battle_state['pve_encounter_id'])
        self.assertIsNotNone(state)
        self.assertEqual(state.active_side_id, SIDE_PLAYER)
        self.assertEqual(state.round_index, 2)

    def test_clear_runtime_removes_runtime_state(self):
        ensure_runtime_for_battle(player_id=self.player_id, battle_state=self.battle_state, mob=self.mob)
        encounter_id = self.battle_state['pve_encounter_id']
        self.assertIsNotNone(_SOLO_PVE_RUNTIME_STORE.get(encounter_id))
        finish_solo_pve_encounter(player_id=self.player_id, encounter_id=encounter_id, status='test_done')
        self.assertIsNone(_SOLO_PVE_RUNTIME_STORE.get(encounter_id))
        self.assertIsNone(get_active_solo_pve_encounter_id(player_id=self.player_id))

    def test_due_timeout_orchestration_runs_enemy_instant_side(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        self.battle_state.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50})
        ensure_runtime_for_battle(player_id=self.player_id, battle_state=self.battle_state, mob=self.mob, now=now)

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

    def test_due_timeout_terminal_player_batch_skips_enemy_side(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        self.battle_state.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50})
        ensure_runtime_for_battle(player_id=self.player_id, battle_state=self.battle_state, mob=self.mob, now=now)

        events = []

        def _on_timeout(action):
            events.append(('player', action.action_type))
            self.battle_state['mob_dead'] = True

        handled = process_due_timeout_for_battle(
            player_id=self.player_id,
            battle_state=self.battle_state,
            now=now + timedelta(seconds=16),
            on_player_timeout_action=_on_timeout,
            on_enemy_action=lambda action: events.append(('enemy', action.action_type)),
        )

        self.assertTrue(handled)
        self.assertEqual(events[0], ('player', 'fallback_guard'))
        self.assertNotIn(('enemy', 'enemy_basic_attack'), events)

    def test_due_timeout_death_with_resurrection_still_runs_enemy_side(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        self.battle_state.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50})
        ensure_runtime_for_battle(player_id=self.player_id, battle_state=self.battle_state, mob=self.mob, now=now)

        events = []

        def _on_timeout(action):
            events.append(('player', action.action_type))
            self.battle_state['player_dead'] = True
            self.battle_state['resurrection_active'] = True

        handled = process_due_timeout_for_battle(
            player_id=self.player_id,
            battle_state=self.battle_state,
            now=now + timedelta(seconds=16),
            on_player_timeout_action=_on_timeout,
            on_enemy_action=lambda action: events.append(('enemy', action.action_type)),
        )

        self.assertTrue(handled)
        self.assertIn(('enemy', 'enemy_basic_attack'), events)

    def test_payload_round_trip_restores_battle_state_by_encounter(self):
        ensure_runtime_for_battle(player_id=self.player_id, battle_state=self.battle_state, mob=self.mob)
        encounter_id = self.battle_state['pve_encounter_id']
        self.battle_state['player_hp'] = 77
        persist_solo_pve_encounter_state(
            encounter_id=encounter_id,
            battle_state=self.battle_state,
            mob=self.mob,
        )
        restored = load_active_solo_pve_encounter(player_id=self.player_id)
        self.assertIsNotNone(restored)
        restored_battle_state, restored_mob = restored
        self.assertEqual(restored_battle_state['pve_encounter_id'], encounter_id)
        self.assertEqual(restored_battle_state['player_hp'], 77)
        self.assertEqual(restored_mob['id'], 'forest_wolf')


if __name__ == '__main__':
    unittest.main()
