import unittest
from datetime import datetime, timedelta, timezone

from game.combat import apply_timeout_fallback_guard
from handlers import battle as battle_handler
from game.pve_live import (
    SIDE_PLAYER,
    _SOLO_PVE_RUNTIME_STORE,
    create_group_pve_encounter,
    ensure_runtime_for_battle,
    ensure_participant_combat_state,
    finish_solo_pve_encounter,
    get_active_pve_encounter_id_for_player,
    get_pve_encounter_player_ids,
    process_due_timeout_for_battle,
    resolve_current_side_if_ready,
    run_enemy_instant_side,
    run_with_participant_projection,
    submit_player_commit,
    sync_projection_for_participant,
    update_participant_combat_state_from_projection,
)


class GroupPveRuntimeEnablementTests(unittest.TestCase):
    def setUp(self):
        _SOLO_PVE_RUNTIME_STORE.reset()
        self.player_a = 702101
        self.player_b = 702102
        self.battle_a = {'mob_id': 'forest_wolf', 'log': []}
        self.battle_b = {'mob_id': 'forest_wolf', 'log': []}
        self.mob = {'id': 'forest_wolf', 'hp': 40}

        self.encounter_id = create_group_pve_encounter(
            player_ids=[self.player_a, self.player_b],
            battle_state=self.battle_a,
            mob=self.mob,
        )
        self.battle_a['pve_encounter_id'] = self.encounter_id
        self.battle_b['pve_encounter_id'] = self.encounter_id

    def tearDown(self):
        finish_solo_pve_encounter(
            player_id=self.player_a,
            encounter_id=self.encounter_id,
            status='test_cleanup',
        )
        _SOLO_PVE_RUNTIME_STORE.reset()

    def test_creating_group_encounter_persists_multiple_side_a_players(self):
        player_roster = get_pve_encounter_player_ids(encounter_id=self.encounter_id)
        self.assertEqual(player_roster, [self.player_a, self.player_b])
        self.assertEqual(get_active_pve_encounter_id_for_player(player_id=self.player_a), self.encounter_id)
        self.assertEqual(get_active_pve_encounter_id_for_player(player_id=self.player_b), self.encounter_id)

    def test_group_player_side_has_shared_deadline_and_status_projection(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        state_a = ensure_runtime_for_battle(
            player_id=self.player_a,
            battle_state=self.battle_a,
            mob=self.mob,
            now=now,
        )
        state_b = ensure_runtime_for_battle(
            player_id=self.player_b,
            battle_state=self.battle_b,
            mob=self.mob,
            now=now,
        )

        self.assertEqual(state_a.encounter_id, self.encounter_id)
        self.assertEqual(state_b.encounter_id, self.encounter_id)
        self.assertEqual(self.battle_a['active_side'], SIDE_PLAYER)
        self.assertEqual(self.battle_b['active_side'], SIDE_PLAYER)
        self.assertEqual(self.battle_a['side_deadline_at'], self.battle_b['side_deadline_at'])
        self.assertEqual(self.battle_a['side_a_player_ids'], [self.player_a, self.player_b])
        self.assertEqual(self.battle_b['side_a_player_ids'], [self.player_a, self.player_b])
        self.assertEqual(self.battle_a['ally_commit_status'][str(self.player_a)], 'eligible')
        self.assertEqual(self.battle_a['ally_commit_status'][str(self.player_b)], 'eligible')

    def test_multiple_players_commit_to_same_phase_and_close_early(self):
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob)
        ensure_runtime_for_battle(player_id=self.player_b, battle_state=self.battle_b, mob=self.mob)

        ok_a, _ = submit_player_commit(
            player_id=self.player_a,
            action_type='basic_attack',
            encounter_id=self.encounter_id,
            battle_state=self.battle_a,
        )
        self.assertTrue(ok_a)
        state = _SOLO_PVE_RUNTIME_STORE.get(self.encounter_id)
        self.assertEqual(state.side_turn_state, 'collecting_orders')

        ok_b, _ = submit_player_commit(
            player_id=self.player_b,
            action_type='skill',
            skill_id='fireball',
            encounter_id=self.encounter_id,
            battle_state=self.battle_b,
        )
        self.assertTrue(ok_b)
        state = _SOLO_PVE_RUNTIME_STORE.get(self.encounter_id)
        self.assertEqual(state.side_turn_state, 'ready_to_lock')

    def test_second_participant_projection_load_does_not_reset_runtime(self):
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob)
        ok_a, _ = submit_player_commit(
            player_id=self.player_a,
            action_type='basic_attack',
            encounter_id=self.encounter_id,
            battle_state=self.battle_a,
        )
        self.assertTrue(ok_a)
        before = _SOLO_PVE_RUNTIME_STORE.get(self.encounter_id)
        before_turn_revision = before.turn_revision
        before_side_state = before.side_turn_state
        before_actions = list(before.submitted_actions.keys())

        # Second participant opens projection for the same encounter.
        ensure_runtime_for_battle(player_id=self.player_b, battle_state=self.battle_b, mob=self.mob)
        after = _SOLO_PVE_RUNTIME_STORE.get(self.encounter_id)

        self.assertIs(before, after)
        self.assertEqual(after.turn_revision, before_turn_revision)
        self.assertEqual(after.side_turn_state, before_side_state)
        self.assertEqual(list(after.submitted_actions.keys()), before_actions)
        self.assertIn(self.player_a, after.submitted_actions)

    def test_timeout_assigns_fallback_only_for_missing_players(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob, now=now)
        ensure_runtime_for_battle(player_id=self.player_b, battle_state=self.battle_b, mob=self.mob, now=now)

        ok_a, _ = submit_player_commit(
            player_id=self.player_a,
            action_type='basic_attack',
            encounter_id=self.encounter_id,
            battle_state=self.battle_a,
        )
        self.assertTrue(ok_a)

        events = []
        timed_out = process_due_timeout_for_battle(
            player_id=self.player_a,
            battle_state=self.battle_a,
            now=now + timedelta(seconds=16),
            on_player_timeout_action=lambda action: events.append((action.participant_id, action.action_type)),
            on_enemy_action=lambda _action: None,
        )
        self.assertTrue(timed_out)

        self.assertIn((self.player_a, 'basic_attack'), events)
        self.assertIn((self.player_b, 'fallback_guard'), events)
        self.assertEqual(sum(1 for pid, _ in events if pid == self.player_b), 1)

    def test_timeout_uses_encounter_state_not_stale_projection_for_enemy_side_gate(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        self.battle_a.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50, 'player_dead': False})
        self.battle_b.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50, 'player_dead': False})
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob, now=now)
        ensure_runtime_for_battle(player_id=self.player_b, battle_state=self.battle_b, mob=self.mob, now=now)

        events = []

        def _on_player_timeout(action):
            events.append((action.participant_id, action.action_type))
            # Simulate stale projection bleed from last acted participant.
            if action.participant_id == self.player_b:
                self.battle_a['player_dead'] = True
                self.battle_a['participant_states'][str(self.player_b)] = {
                    'player_hp': 0, 'hp': 0, 'player_dead': True, 'defeated': True,
                }
                self.battle_a['participant_states'][str(self.player_a)] = {
                    'player_hp': 100, 'hp': 100, 'player_dead': False, 'defeated': False,
                }

        handled = process_due_timeout_for_battle(
            player_id=self.player_a,
            battle_state=self.battle_a,
            now=now + timedelta(seconds=16),
            on_player_timeout_action=_on_player_timeout,
            on_enemy_action=lambda _action: events.append(('enemy', 'enemy_basic_attack')),
        )
        self.assertTrue(handled)
        self.assertIn(('enemy', 'enemy_basic_attack'), events)

    def test_timeout_group_terminal_when_all_participants_defeated_skips_enemy_side(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        self.battle_a.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50, 'player_dead': False})
        self.battle_b.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50, 'player_dead': False})
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob, now=now)
        ensure_runtime_for_battle(player_id=self.player_b, battle_state=self.battle_b, mob=self.mob, now=now)

        events = []

        def _on_player_timeout(action):
            events.append((action.participant_id, action.action_type))
            self.battle_a['participant_states'][str(self.player_a)] = {
                'player_hp': 0, 'hp': 0, 'player_dead': True, 'defeated': True,
            }
            self.battle_a['participant_states'][str(self.player_b)] = {
                'player_hp': 0, 'hp': 0, 'player_dead': True, 'defeated': True,
            }

        handled = process_due_timeout_for_battle(
            player_id=self.player_a,
            battle_state=self.battle_a,
            now=now + timedelta(seconds=16),
            on_player_timeout_action=_on_player_timeout,
            on_enemy_action=lambda _action: events.append(('enemy', 'enemy_basic_attack')),
        )
        self.assertTrue(handled)
        self.assertNotIn(('enemy', 'enemy_basic_attack'), events)

    def test_timeout_group_resurrection_candidate_keeps_enemy_side_running(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        self.battle_a.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50, 'player_dead': False})
        self.battle_b.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50, 'player_dead': False})
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob, now=now)
        ensure_runtime_for_battle(player_id=self.player_b, battle_state=self.battle_b, mob=self.mob, now=now)

        events = []

        def _on_player_timeout(action):
            events.append((action.participant_id, action.action_type))
            if action.participant_id == self.player_b:
                self.battle_a['participant_states'][str(self.player_b)] = {
                    'player_hp': 0,
                    'hp': 0,
                    'player_dead': True,
                    'defeated': True,
                    'resurrection_active': True,
                    'resurrection_hp': 30,
                    'player_max_hp': 100,
                }

        handled = process_due_timeout_for_battle(
            player_id=self.player_a,
            battle_state=self.battle_a,
            now=now + timedelta(seconds=16),
            on_player_timeout_action=_on_player_timeout,
            on_enemy_action=lambda _action: events.append(('enemy', 'enemy_basic_attack')),
        )

        self.assertTrue(handled)
        self.assertIn(('enemy', 'enemy_basic_attack'), events)

    def test_group_players_have_distinct_participant_hp_mana_state(self):
        self.battle_a.update({'player_hp': 120, 'player_mana': 70, 'player_max_hp': 120, 'player_max_mana': 70})
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob)

        ensure_participant_combat_state(
            battle_state=self.battle_a,
            participant_ids=[self.player_a, self.player_b],
            preferred_player_id=self.player_a,
        )
        self.battle_a['participant_states'][str(self.player_a)] = {'hp': 120, 'mana': 70, 'defeated': False}
        self.battle_a['participant_states'][str(self.player_b)] = {'hp': 95, 'mana': 30, 'defeated': False}

        pstate = self.battle_a['participant_states']
        self.assertEqual(pstate[str(self.player_a)]['hp'], 120)
        self.assertEqual(pstate[str(self.player_a)]['mana'], 70)
        self.assertEqual(pstate[str(self.player_b)]['hp'], 95)
        self.assertEqual(pstate[str(self.player_b)]['mana'], 30)

    def test_damage_to_one_participant_does_not_overwrite_other_participant_hp(self):
        self.battle_a.update({'player_hp': 120, 'player_mana': 70, 'player_max_hp': 120, 'player_max_mana': 70})
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob)
        ensure_participant_combat_state(
            battle_state=self.battle_a,
            participant_ids=[self.player_a, self.player_b],
            preferred_player_id=self.player_a,
        )
        self.battle_a['participant_states'][str(self.player_b)] = {'hp': 95, 'mana': 30, 'defeated': False}

        # Damage player A only.
        self.battle_a['player_hp'] = 80
        update_participant_combat_state_from_projection(battle_state=self.battle_a, player_id=self.player_a)

        self.assertEqual(self.battle_a['participant_states'][str(self.player_a)]['hp'], 80)
        self.assertEqual(self.battle_a['participant_states'][str(self.player_b)]['hp'], 95)

    def test_group_player_resolution_uses_participant_scoped_state(self):
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob)
        ensure_participant_combat_state(
            battle_state=self.battle_a,
            participant_ids=[self.player_a, self.player_b],
            preferred_player_id=self.player_a,
        )
        self.battle_a['participant_states'][str(self.player_a)] = {'hp': 120, 'mana': 50, 'defeated': False}
        self.battle_a['participant_states'][str(self.player_b)] = {'hp': 90, 'mana': 40, 'defeated': False}
        self.battle_a['player_max_hp'] = 120
        self.battle_a['player_max_mana'] = 50
        self.battle_b = {'pve_encounter_id': self.encounter_id, 'participant_states': self.battle_a['participant_states']}

        submit_player_commit(
            player_id=self.player_a,
            action_type='basic_attack',
            encounter_id=self.encounter_id,
            battle_state=self.battle_a,
        )
        submit_player_commit(
            player_id=self.player_b,
            action_type='basic_attack',
            encounter_id=self.encounter_id,
            battle_state=self.battle_b,
        )

        def _apply_fake_damage(action):
            actor_id = action.participant_id
            sync_projection_for_participant(battle_state=self.battle_a, player_id=actor_id)
            self.battle_a['player_hp'] = max(0, self.battle_a.get('player_hp', 0) - 10)
            update_participant_combat_state_from_projection(battle_state=self.battle_a, player_id=actor_id)

        resolved = resolve_current_side_if_ready(
            encounter_id=self.encounter_id,
            battle_state=self.battle_a,
            projection_states=[self.battle_b],
            on_player_action=_apply_fake_damage,
            on_enemy_action=lambda _action: None,
        )
        self.assertTrue(resolved)
        self.assertEqual(self.battle_a['participant_states'][str(self.player_a)]['hp'], 110)
        self.assertEqual(self.battle_a['participant_states'][str(self.player_b)]['hp'], 80)

    def test_run_with_projection_restores_full_participant_combat_snapshot(self):
        self.battle_a.update({
            'player_hp': 120,
            'player_mana': 60,
            'player_max_hp': 120,
            'player_max_mana': 60,
            'weapon_type': 'melee',
            'weapon_profile': 'sword_1h',
            'weapon_damage': 15,
            'armor_class': 'heavy',
            'offhand_profile': 'shield',
            'encumbrance': 30,
            'effective_strength': 25,
            'effective_agility': 8,
            'effective_intuition': 5,
            'effective_vitality': 18,
            'effective_wisdom': 6,
            'effective_luck': 4,
            'equipment_physical_defense_bonus': 10,
            'equipment_magic_defense_bonus': 2,
            'equipment_accuracy_bonus': 1,
            'equipment_evasion_bonus': 0,
            'equipment_block_chance_bonus': 6,
            'equipment_magic_power_bonus': 0,
            'equipment_healing_power_bonus': 0,
        })
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob)
        ensure_participant_combat_state(
            battle_state=self.battle_a,
            participant_ids=[self.player_a, self.player_b],
            preferred_player_id=self.player_a,
        )
        self.battle_a['participant_states'][str(self.player_b)].update({
            'player_hp': 70,
            'player_mana': 45,
            'player_max_hp': 90,
            'player_max_mana': 55,
            'weapon_type': 'magic',
            'weapon_profile': 'staff',
            'weapon_damage': 22,
            'armor_class': 'light',
            'offhand_profile': 'focus',
            'encumbrance': 5,
            'effective_strength': 4,
            'effective_agility': 12,
            'effective_intuition': 28,
            'effective_vitality': 9,
            'effective_wisdom': 21,
            'effective_luck': 11,
            'equipment_physical_defense_bonus': 3,
            'equipment_magic_defense_bonus': 9,
            'equipment_accuracy_bonus': 7,
            'equipment_evasion_bonus': 5,
            'equipment_block_chance_bonus': 1,
            'equipment_magic_power_bonus': 13,
            'equipment_healing_power_bonus': 2,
            'player_dead': False,
            'hp': 70,
            'mana': 45,
            'defeated': False,
        })

        seen_projection = {}

        def _resolver():
            seen_projection['weapon_type'] = self.battle_a.get('weapon_type')
            seen_projection['armor_class'] = self.battle_a.get('armor_class')
            seen_projection['effective_intuition'] = self.battle_a.get('effective_intuition')
            seen_projection['equipment_magic_power_bonus'] = self.battle_a.get('equipment_magic_power_bonus')
            self.battle_a['player_hp'] = 55

        run_with_participant_projection(
            battle_state=self.battle_a,
            participant_id=self.player_b,
            resolver=_resolver,
        )

        self.assertEqual(seen_projection['weapon_type'], 'magic')
        self.assertEqual(seen_projection['armor_class'], 'light')
        self.assertEqual(seen_projection['effective_intuition'], 28)
        self.assertEqual(seen_projection['equipment_magic_power_bonus'], 13)
        self.assertEqual(self.battle_a['participant_states'][str(self.player_b)]['player_hp'], 55)

    def test_fallback_guard_for_participant_survives_snapshot_roundtrip(self):
        self.battle_a.update({
            'player_hp': 100,
            'player_mana': 50,
            'player_max_hp': 100,
            'player_max_mana': 50,
            'defense_buff_turns': 0,
            'defense_buff_value': 0,
        })
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob)
        ensure_participant_combat_state(
            battle_state=self.battle_a,
            participant_ids=[self.player_a, self.player_b],
            preferred_player_id=self.player_a,
        )
        self.battle_a['participant_states'][str(self.player_a)].update({
            'defense_buff_turns': 0,
            'defense_buff_value': 0,
        })
        self.battle_a['participant_states'][str(self.player_b)].update({
            'defense_buff_turns': 0,
            'defense_buff_value': 0,
            'player_hp': 80,
            'player_mana': 40,
            'hp': 80,
            'mana': 40,
            'defeated': False,
            'player_dead': False,
        })

        run_with_participant_projection(
            battle_state=self.battle_a,
            participant_id=self.player_b,
            resolver=lambda: apply_timeout_fallback_guard(self.battle_a, lang='en'),
        )

        self.assertGreaterEqual(self.battle_a['participant_states'][str(self.player_b)]['defense_buff_turns'], 1)
        self.assertGreaterEqual(self.battle_a['participant_states'][str(self.player_b)]['defense_buff_value'], 15)
        self.assertEqual(self.battle_a['participant_states'][str(self.player_a)]['defense_buff_turns'], 0)
        self.assertEqual(self.battle_a['participant_states'][str(self.player_a)]['defense_buff_value'], 0)

        # Rehydrate B and verify guard snapshot restoration.
        sync_projection_for_participant(battle_state=self.battle_a, player_id=self.player_b)
        self.assertGreaterEqual(self.battle_a['defense_buff_turns'], 1)
        self.assertGreaterEqual(self.battle_a['defense_buff_value'], 15)

    def test_dead_participant_removed_from_active_membership_while_ally_keeps_encounter(self):
        self.battle_a.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50})
        self.battle_b.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50})
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob)
        ensure_runtime_for_battle(player_id=self.player_b, battle_state=self.battle_b, mob=self.mob)
        self.battle_b['participant_states'][str(self.player_a)] = {
            'player_hp': 0,
            'player_mana': 0,
            'player_dead': True,
            'hp': 0,
            'mana': 0,
            'defeated': True,
        }
        battle_handler._reconcile_group_participant_outcomes(self.battle_b)

        self.assertIsNone(get_active_pve_encounter_id_for_player(player_id=self.player_a))
        self.assertEqual(get_active_pve_encounter_id_for_player(player_id=self.player_b), self.encounter_id)
        active_roster = get_pve_encounter_player_ids(encounter_id=self.encounter_id)
        self.assertEqual(active_roster, [self.player_b])

    def test_next_turn_after_death_does_not_wait_for_dead_participant(self):
        self.battle_a.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50})
        self.battle_b.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50})
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob)
        ensure_runtime_for_battle(player_id=self.player_b, battle_state=self.battle_b, mob=self.mob)
        self.battle_b['participant_states'][str(self.player_a)] = {
            'player_hp': 0,
            'player_mana': 0,
            'player_dead': True,
            'hp': 0,
            'mana': 0,
            'defeated': True,
        }
        battle_handler._reconcile_group_participant_outcomes(self.battle_b)

        submit_player_commit(
            player_id=self.player_b,
            action_type='basic_attack',
            encounter_id=self.encounter_id,
            battle_state=self.battle_b,
        )
        resolve_current_side_if_ready(
            encounter_id=self.encounter_id,
            battle_state=self.battle_b,
            on_player_action=lambda _action: None,
            on_enemy_action=lambda _action: None,
        )
        run_enemy_instant_side(
            player_id=self.player_b,
            battle_state=self.battle_b,
            on_enemy_action=lambda _action: None,
        )

        self.assertEqual(self.battle_b['side_a_player_ids'], [self.player_b])
        self.assertEqual(self.battle_b['ally_commit_status'][str(self.player_b)], 'eligible')
        self.assertNotIn(str(self.player_a), self.battle_b['ally_commit_status'])

    def test_timeout_after_death_does_not_assign_fallback_to_dead_participant(self):
        now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        self.battle_a.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50})
        self.battle_b.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50})
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob, now=now)
        ensure_runtime_for_battle(player_id=self.player_b, battle_state=self.battle_b, mob=self.mob, now=now)
        self.battle_b['participant_states'][str(self.player_a)] = {
            'player_hp': 0,
            'player_mana': 0,
            'player_dead': True,
            'hp': 0,
            'mana': 0,
            'defeated': True,
        }
        battle_handler._reconcile_group_participant_outcomes(self.battle_b)

        events = []
        handled = process_due_timeout_for_battle(
            player_id=self.player_b,
            battle_state=self.battle_b,
            now=now + timedelta(seconds=16),
            on_player_timeout_action=lambda action: events.append((action.participant_id, action.action_type)),
            on_enemy_action=lambda _action: None,
        )

        self.assertTrue(handled)
        self.assertIn((self.player_b, 'fallback_guard'), events)
        self.assertNotIn((self.player_a, 'fallback_guard'), events)

    def test_resurrection_participant_is_not_removed_from_active_roster(self):
        self.battle_a.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50})
        self.battle_b.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50})
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob)
        ensure_runtime_for_battle(player_id=self.player_b, battle_state=self.battle_b, mob=self.mob)
        self.battle_b['participant_states'][str(self.player_a)] = {
            'player_hp': 0,
            'player_mana': 0,
            'player_dead': True,
            'hp': 0,
            'mana': 0,
            'defeated': True,
            'resurrection_active': True,
            'resurrection_hp': 30,
            'player_max_hp': 100,
        }

        battle_handler._reconcile_group_participant_outcomes(self.battle_b)
        battle_handler._process_group_participant_death_consequences(
            battle_state=self.battle_b,
            owner_player_id=self.player_b,
            log=self.battle_b.setdefault('log', []),
            lang='en',
        )

        active_roster = get_pve_encounter_player_ids(encounter_id=self.encounter_id)
        self.assertIn(self.player_a, active_roster)
        self.assertIn(self.player_b, active_roster)
        revived = self.battle_b['participant_states'][str(self.player_a)]
        self.assertFalse(revived.get('player_dead'))
        self.assertGreater(revived.get('player_hp', 0), 0)

    def test_resurrected_participant_can_commit_in_future_turn(self):
        self.battle_a.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50})
        self.battle_b.update({'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50})
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob)
        ensure_runtime_for_battle(player_id=self.player_b, battle_state=self.battle_b, mob=self.mob)
        self.battle_b['participant_states'][str(self.player_a)] = {
            'player_hp': 0,
            'player_mana': 0,
            'player_dead': True,
            'hp': 0,
            'mana': 0,
            'defeated': True,
            'resurrection_active': True,
            'resurrection_hp': 30,
            'player_max_hp': 100,
        }

        battle_handler._reconcile_group_participant_outcomes(self.battle_b)
        battle_handler._process_group_participant_death_consequences(
            battle_state=self.battle_b,
            owner_player_id=self.player_b,
            log=self.battle_b.setdefault('log', []),
            lang='en',
        )

        accepted, reason = submit_player_commit(
            player_id=self.player_a,
            action_type='basic_attack',
            encounter_id=self.encounter_id,
            battle_state=self.battle_a,
        )
        self.assertTrue(accepted, reason)

    def test_player_side_resolution_order_is_deterministic_by_roster(self):
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob)
        ensure_runtime_for_battle(player_id=self.player_b, battle_state=self.battle_b, mob=self.mob)

        submit_player_commit(
            player_id=self.player_b,
            action_type='skill',
            skill_id='fireball',
            encounter_id=self.encounter_id,
            battle_state=self.battle_b,
        )
        submit_player_commit(
            player_id=self.player_a,
            action_type='basic_attack',
            encounter_id=self.encounter_id,
            battle_state=self.battle_a,
        )

        seen = []
        resolved = resolve_current_side_if_ready(
            encounter_id=self.encounter_id,
            battle_state=self.battle_a,
            projection_states=[self.battle_b],
            on_player_action=lambda action: seen.append(action.participant_id),
            on_enemy_action=lambda _action: None,
        )
        self.assertTrue(resolved)
        self.assertEqual(seen, [self.player_a, self.player_b])

    def test_enemy_side_runs_instantly_after_group_player_side(self):
        ensure_runtime_for_battle(player_id=self.player_a, battle_state=self.battle_a, mob=self.mob)
        ensure_runtime_for_battle(player_id=self.player_b, battle_state=self.battle_b, mob=self.mob)

        submit_player_commit(
            player_id=self.player_a,
            action_type='basic_attack',
            encounter_id=self.encounter_id,
            battle_state=self.battle_a,
        )
        submit_player_commit(
            player_id=self.player_b,
            action_type='basic_attack',
            encounter_id=self.encounter_id,
            battle_state=self.battle_b,
        )

        resolve_current_side_if_ready(
            encounter_id=self.encounter_id,
            battle_state=self.battle_a,
            projection_states=[self.battle_b],
            on_player_action=lambda _action: None,
            on_enemy_action=lambda _action: None,
        )

        enemy_events = []
        run_enemy_instant_side(
            player_id=self.player_a,
            battle_state=self.battle_a,
            on_enemy_action=lambda action: enemy_events.append(action.action_type),
        )
        self.assertEqual(enemy_events, ['enemy_basic_attack'])
        self.assertEqual(self.battle_a['active_side'], SIDE_PLAYER)
        self.assertEqual(self.battle_a['round_index'], 2)
        self.assertEqual(self.battle_a['ally_commit_status'][str(self.player_a)], 'eligible')
        self.assertEqual(self.battle_a['ally_commit_status'][str(self.player_b)], 'eligible')

    def test_solo_pve_still_works_with_shared_encounter_model(self):
        solo_battle = {'mob_id': 'forest_wolf', 'log': []}
        solo_player = 702103
        solo_mob = {'id': 'forest_wolf', 'hp': 20}

        state = ensure_runtime_for_battle(player_id=solo_player, battle_state=solo_battle, mob=solo_mob)
        self.assertEqual(state.active_side_id, SIDE_PLAYER)
        self.assertEqual(solo_battle['side_a_player_ids'], [solo_player])

        accepted, reason = submit_player_commit(
            player_id=solo_player,
            action_type='basic_attack',
            battle_state=solo_battle,
        )
        self.assertTrue(accepted)
        self.assertEqual(reason, 'committed')

        finished = resolve_current_side_if_ready(
            player_id=solo_player,
            battle_state=solo_battle,
            on_player_action=lambda _action: None,
            on_enemy_action=lambda _action: None,
        )
        self.assertTrue(finished)

        finish_solo_pve_encounter(
            player_id=solo_player,
            encounter_id=solo_battle.get('pve_encounter_id'),
            status='test_cleanup',
        )


if __name__ == '__main__':
    unittest.main()
