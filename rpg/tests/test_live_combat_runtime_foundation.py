import unittest
from datetime import datetime, timedelta, timezone

from game.live_combat_runtime import LiveCombatRuntime, LiveCombatRuntimeStore


class LiveCombatRuntimeFoundationTests(unittest.TestCase):
    def setUp(self):
        self.store = LiveCombatRuntimeStore()
        self.runtime = LiveCombatRuntime(self.store)
        self.runtime.create_encounter(
            encounter_id='encounter-1',
            side_a_participants=[101, 102],
            side_b_participants=[201],
        )

    def test_invalid_active_side_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "active_side_id must be 'side_a' or 'side_b'"):
            self.runtime.create_encounter(
                encounter_id='bad-side',
                side_a_participants=[1],
                side_b_participants=[2],
                active_side_id='side_c',
            )

    def test_duplicate_participant_id_same_side_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'side_a_participants contains duplicate participant ids'):
            self.runtime.create_encounter(
                encounter_id='dup-side',
                side_a_participants=[1, 1],
                side_b_participants=[2],
            )

    def test_overlapping_participants_across_sides_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Participants cannot belong to both side_a and side_b'):
            self.runtime.create_encounter(
                encounter_id='overlap',
                side_a_participants=[1, 2],
                side_b_participants=[2, 3],
            )

    def test_open_side_turn_creates_deadline_and_eligible_roster(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        state = self.runtime.open_side_turn(encounter_id='encounter-1', now=now)

        self.assertEqual(state.side_turn_state, 'collecting_orders')
        self.assertEqual(state.turn_revision, 1)
        self.assertEqual(state.side_deadline_at, now + timedelta(seconds=15))
        self.assertEqual(self.runtime.get_active_side_eligible_participants(encounter_id='encounter-1'), [101, 102])

    def test_commit_from_eligible_participant_is_stored(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        state = self.runtime.open_side_turn(encounter_id='encounter-1', now=now)

        result = self.runtime.commit_action(
            encounter_id='encounter-1',
            participant_id=101,
            action_type='basic_attack',
            target_info={'participant_id': 201},
            skill_id=None,
            item_id=None,
            committed_at=now,
            turn_revision=state.turn_revision,
        )

        self.assertTrue(result.accepted)
        saved_state = self.store.get('encounter-1')
        self.assertEqual(saved_state.submitted_actions[101].action_type, 'basic_attack')
        self.assertEqual(saved_state.participants[101].phase_state, 'committed')

    def test_stale_revision_commit_is_rejected(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        self.runtime.open_side_turn(encounter_id='encounter-1', now=now)

        stale_result = self.runtime.commit_action(
            encounter_id='encounter-1',
            participant_id=101,
            action_type='basic_attack',
            target_info={'participant_id': 201},
            skill_id=None,
            item_id=None,
            committed_at=now,
            turn_revision=0,
        )
        self.assertFalse(stale_result.accepted)
        self.assertEqual(stale_result.reason, 'stale_revision')

    def test_duplicate_resolve_is_prevented(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        state = self.runtime.open_side_turn(encounter_id='encounter-1', now=now)

        self.runtime.commit_action(
            encounter_id='encounter-1', participant_id=101,
            action_type='basic_attack', target_info={'participant_id': 201},
            skill_id=None, item_id=None, committed_at=now, turn_revision=state.turn_revision,
        )
        self.runtime.commit_action(
            encounter_id='encounter-1', participant_id=102,
            action_type='guard', target_info=None,
            skill_id=None, item_id=None, committed_at=now, turn_revision=state.turn_revision,
        )

        first_claim = self.runtime.claim_side_resolution(encounter_id='encounter-1', turn_revision=state.turn_revision)
        second_claim = self.runtime.claim_side_resolution(encounter_id='encounter-1', turn_revision=state.turn_revision)

        self.assertTrue(first_claim.claimed)
        self.assertFalse(second_claim.claimed)
        self.assertEqual(second_claim.reason, 'already_claimed')

    def test_timeout_marks_unresolved_as_auto_fallback(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        state = self.runtime.open_side_turn(encounter_id='encounter-1', now=now)

        self.runtime.commit_action(
            encounter_id='encounter-1', participant_id=101,
            action_type='basic_attack', target_info={'participant_id': 201},
            skill_id=None, item_id=None, committed_at=now, turn_revision=state.turn_revision,
        )
        assigned = self.runtime.apply_timeout_fallbacks(
            encounter_id='encounter-1',
            now=now + timedelta(seconds=16),
        )

        self.assertEqual(assigned, 1)
        saved_state = self.store.get('encounter-1')
        self.assertEqual(saved_state.participants[102].phase_state, 'auto_fallback')
        self.assertEqual(saved_state.submitted_actions[102].source, 'fallback')
        self.assertEqual(saved_state.side_turn_state, 'ready_to_lock')

    def test_side_closes_early_when_all_eligible_committed(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        state = self.runtime.open_side_turn(encounter_id='encounter-1', now=now)

        self.runtime.commit_action(
            encounter_id='encounter-1', participant_id=101,
            action_type='basic_attack', target_info={'participant_id': 201},
            skill_id=None, item_id=None, committed_at=now, turn_revision=state.turn_revision,
        )
        self.runtime.commit_action(
            encounter_id='encounter-1', participant_id=102,
            action_type='guard', target_info=None,
            skill_id=None, item_id=None, committed_at=now, turn_revision=state.turn_revision,
        )

        saved_state = self.store.get('encounter-1')
        self.assertEqual(saved_state.side_turn_state, 'ready_to_lock')
        self.assertTrue(self.runtime.is_active_side_fully_resolved(encounter_id='encounter-1'))

    def test_unable_to_act_skips_current_phase_but_not_future_phase(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        state = self.runtime.open_side_turn(encounter_id='encounter-1', now=now)

        mark_result = self.runtime.mark_participant_unable_to_act_for_current_phase(
            encounter_id='encounter-1',
            participant_id=101,
            turn_revision=state.turn_revision,
        )
        self.assertTrue(mark_result.changed)

        self.runtime.commit_action(
            encounter_id='encounter-1', participant_id=102,
            action_type='guard', target_info=None,
            skill_id=None, item_id=None, committed_at=now, turn_revision=state.turn_revision,
        )

        current_phase = self.store.get('encounter-1')
        self.assertEqual(current_phase.participants[101].phase_state, 'unable_to_act')
        self.assertEqual(current_phase.side_turn_state, 'ready_to_lock')

        self.runtime.claim_side_resolution(encounter_id='encounter-1', turn_revision=state.turn_revision)
        self.runtime.complete_side_and_advance(encounter_id='encounter-1', turn_revision=state.turn_revision)

        side_b_state = self.runtime.open_side_turn(encounter_id='encounter-1', now=now + timedelta(seconds=20))
        self.runtime.commit_action(
            encounter_id='encounter-1', participant_id=201,
            action_type='basic_attack', target_info={'participant_id': 101},
            skill_id=None, item_id=None, committed_at=now, turn_revision=side_b_state.turn_revision,
        )
        self.runtime.claim_side_resolution(encounter_id='encounter-1', turn_revision=side_b_state.turn_revision)
        self.runtime.complete_side_and_advance(encounter_id='encounter-1', turn_revision=side_b_state.turn_revision)

        next_side_a = self.runtime.open_side_turn(encounter_id='encounter-1', now=now + timedelta(seconds=40))
        self.assertEqual(next_side_a.active_side_id, 'side_a')
        self.assertEqual(self.runtime.get_active_side_eligible_participants(encounter_id='encounter-1'), [101, 102])

    def test_claim_tracking_cleanup_uses_single_revision_slot(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        first_state = self.runtime.open_side_turn(encounter_id='encounter-1', now=now)

        self.runtime.commit_action(
            encounter_id='encounter-1', participant_id=101,
            action_type='guard', target_info=None,
            skill_id=None, item_id=None, committed_at=now, turn_revision=first_state.turn_revision,
        )
        self.runtime.commit_action(
            encounter_id='encounter-1', participant_id=102,
            action_type='guard', target_info=None,
            skill_id=None, item_id=None, committed_at=now, turn_revision=first_state.turn_revision,
        )

        first_claim = self.runtime.claim_side_resolution(encounter_id='encounter-1', turn_revision=first_state.turn_revision)
        duplicate_claim = self.runtime.claim_side_resolution(encounter_id='encounter-1', turn_revision=first_state.turn_revision)
        self.assertTrue(first_claim.claimed)
        self.assertFalse(duplicate_claim.claimed)

        self.runtime.complete_side_and_advance(encounter_id='encounter-1', turn_revision=first_state.turn_revision)

        side_b_state = self.runtime.open_side_turn(encounter_id='encounter-1', now=now + timedelta(seconds=20))
        self.runtime.commit_action(
            encounter_id='encounter-1', participant_id=201,
            action_type='guard', target_info=None,
            skill_id=None, item_id=None, committed_at=now, turn_revision=side_b_state.turn_revision,
        )
        second_claim = self.runtime.claim_side_resolution(encounter_id='encounter-1', turn_revision=side_b_state.turn_revision)
        self.assertTrue(second_claim.claimed)

        runtime_state = self.store.get('encounter-1')
        self.assertEqual(runtime_state.last_claimed_revision, side_b_state.turn_revision)

    def test_next_side_and_next_round_advancement(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        state = self.runtime.open_side_turn(encounter_id='encounter-1', now=now)
        self.runtime.commit_action(
            encounter_id='encounter-1', participant_id=101,
            action_type='basic_attack', target_info={'participant_id': 201},
            skill_id=None, item_id=None, committed_at=now, turn_revision=state.turn_revision,
        )
        self.runtime.commit_action(
            encounter_id='encounter-1', participant_id=102,
            action_type='guard', target_info=None,
            skill_id=None, item_id=None, committed_at=now, turn_revision=state.turn_revision,
        )
        self.runtime.claim_side_resolution(encounter_id='encounter-1', turn_revision=state.turn_revision)
        first_advance = self.runtime.complete_side_and_advance(encounter_id='encounter-1', turn_revision=state.turn_revision)

        self.assertTrue(first_advance.advanced)
        self.assertEqual(first_advance.new_active_side_id, 'side_b')
        self.assertEqual(first_advance.new_round_index, 1)

        state = self.runtime.open_side_turn(encounter_id='encounter-1', now=now + timedelta(seconds=20))
        self.runtime.commit_action(
            encounter_id='encounter-1', participant_id=201,
            action_type='basic_attack', target_info={'participant_id': 101},
            skill_id=None, item_id=None, committed_at=now, turn_revision=state.turn_revision,
        )
        self.runtime.claim_side_resolution(encounter_id='encounter-1', turn_revision=state.turn_revision)
        second_advance = self.runtime.complete_side_and_advance(encounter_id='encounter-1', turn_revision=state.turn_revision)

        self.assertTrue(second_advance.advanced)
        self.assertEqual(second_advance.new_active_side_id, 'side_a')
        self.assertEqual(second_advance.new_round_index, 2)


if __name__ == '__main__':
    unittest.main()
