import asyncio
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from game.locations import WORLD_LOCATIONS
from game.pve_live import (
    PACK_ENABLED_MOB_IDS,
    _SOLO_PVE_RUNTIME_STORE,
    enemy_participant_ids_for_battle,
    enemy_unit_participant_id,
    ensure_runtime_for_battle,
    is_pack_enabled_mob,
    reset_solo_pve_runtime_store,
    run_enemy_instant_side,
    create_or_load_open_world_pve_encounter,
    _claim_spawn_pack_for_encounter,
    lock_open_world_pve_roster_for_runtime_start,
    resolve_current_side_if_ready,
    submit_player_commit,
)
from database import get_connection
from handlers.location import build_pve_encounter_detail_message
from handlers.battle import _handle_victory_cleanup
import handlers.battle as battle_handler


class PackRuntimePR2B1Tests(unittest.TestCase):
    def setUp(self):
        reset_solo_pve_runtime_store()

    def test_pack_enabled_mobs_are_exactly_approved_set(self):
        self.assertEqual(PACK_ENABLED_MOB_IDS, frozenset({'forest_wolf', 'white_wolf', 'leech', 'zombie'}))
        self.assertTrue(is_pack_enabled_mob('forest_wolf'))
        self.assertFalse(is_pack_enabled_mob('forest_boar'))

    def test_pack_counts_cover_all_existing_approved_mob_locations_including_westwild_n7_and_ashen(self):
        expected = {
            'forest_wolf': {'westwild_n3', 'westwild_n4', 'westwild_n6', 'westwild_n7'},
            'white_wolf': {'frostspine_n2', 'frostspine_n3', 'frostspine_n5'},
            'leech': {'mireveil_n1', 'mireveil_n2', 'mireveil_n5'},
            'zombie': {'ashen_n1', 'ashen_n2', 'ashen_n3c1'},
        }
        for mob_id, locations in expected.items():
            seen = set()
            for location_id in locations:
                profiles = (WORLD_LOCATIONS[location_id].get('world_spawn_profiles') or {}).get(mob_id) or {}
                self.assertEqual(int(profiles.get('normal', 1)), 3)
                seen.add(location_id)
            self.assertEqual(seen, locations)

    def test_pack_runtime_uses_one_enemy_participant_per_living_unit(self):
        battle_state = {
            'pve_encounter_id': 'enc-pack-1',
            'enemy_units': [
                {'unit_id': 'u1', 'dead': False},
                {'unit_id': 'u2', 'dead': False},
                {'unit_id': 'u3', 'dead': False},
            ],
        }
        participants = enemy_participant_ids_for_battle(encounter_id='enc-pack-1', battle_state=battle_state)
        self.assertEqual(len(participants), 3)
        self.assertEqual(len(set(participants)), 3)

    def test_enemy_instant_side_resolves_per_living_pack_unit_and_skips_dead(self):
        battle_state = {
            'pve_encounter_id': 'enc-pack-2',
            'enemy_units': [
                {'unit_id': 'u1', 'dead': False},
                {'unit_id': 'u2', 'dead': True},
                {'unit_id': 'u3', 'dead': False},
            ],
            'side_a_player_ids': [1001],
            'participant_states': {'1001': {'player_hp': 100}},
            'mob_dead': False,
            'player_dead': False,
        }
        ensure_runtime_for_battle(player_id=1001, battle_state=battle_state, mob={'id': 'forest_wolf', 'hp': 10})
        events = []
        with patch('game.pve_live.resolve_current_side_if_ready', return_value=True), patch('game.pve_live.open_next_player_side_turn'):
            run_enemy_instant_side(player_id=1001, battle_state=battle_state, on_enemy_action=lambda action: events.append(action))
        runtime = _SOLO_PVE_RUNTIME_STORE.get('enc-pack-2')
        side_b = runtime.sides['side_b']
        self.assertEqual(len(side_b.participant_order), 2)

    def test_enemy_side_roster_rebuild_after_pack_death_does_not_stall_resolution(self):
        battle_state = {
            'pve_encounter_id': 'enc-pack-live-1',
            'enemy_units': [
                {'unit_id': 'u1', 'dead': False},
                {'unit_id': 'u2', 'dead': False},
                {'unit_id': 'u3', 'dead': False},
            ],
            'side_a_player_ids': [1001],
            'participant_states': {'1001': {'player_hp': 100}},
            'mob_dead': False,
            'player_dead': False,
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 50,
            'player_max_mana': 50,
            'mob_hp': 10,
            'log': [],
        }
        ensure_runtime_for_battle(player_id=1001, battle_state=battle_state, mob={'id': 'forest_wolf', 'hp': 10})
        submit_player_commit(player_id=1001, action_type='basic_attack', battle_state=battle_state)
        resolve_current_side_if_ready(player_id=1001, battle_state=battle_state, on_player_action=lambda _a: None, on_enemy_action=lambda _a: None)
        battle_state['enemy_units'][0]['dead'] = True
        events = []
        run_enemy_instant_side(player_id=1001, battle_state=battle_state, on_enemy_action=lambda action: events.append(action))
        self.assertEqual(sum(1 for a in events if str(a.action_type) == 'enemy_basic_attack'), 2)

    def test_pack_enemy_actions_use_per_unit_projection_and_writeback(self):
        battle_state = {
            'pve_encounter_id': 'enc-pack-proj-1',
            'enemy_units': [
                {'unit_id': 'u1', 'dead': False, 'hp': 5, 'max_hp': 10, 'mob_effects': ['stun']},
                {'unit_id': 'u2', 'dead': False, 'hp': 9, 'max_hp': 10, 'mob_effects': ['slow']},
                {'unit_id': 'u3', 'dead': False, 'hp': 7, 'max_hp': 10, 'mob_effects': []},
            ],
            'active_enemy_unit_id': 'u1',
            'side_a_player_ids': [1001],
            'participant_states': {'1001': {'player_hp': 100}},
            'mob_dead': False,
            'player_dead': False,
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 50,
            'player_max_mana': 50,
            'mob_hp': 5,
            'mob_max_hp': 10,
            'mob_effects': ['stun'],
            'log': [],
        }
        seen = []
        def _fake_enemy_turn(_mob, _player_state, state, **_kwargs):
            seen.append((state.get('mob_hp'), tuple(state.get('mob_effects') or [])))
            if state.get('mob_hp') == 5:
                state['mob_hp'] = 0
                state['mob_effects'] = ['dead_mark']
            else:
                state['mob_effects'] = ['acted']

        with patch.object(battle_handler, 'process_enemy_side_turn', side_effect=_fake_enemy_turn):
            participant_ids = enemy_participant_ids_for_battle(encounter_id='enc-pack-proj-1', battle_state=battle_state)
            for pid in participant_ids:
                action = SimpleNamespace(participant_id=pid, action_type='enemy_basic_attack')
                battle_handler._run_group_enemy_side_action(
                    action=action, owner_player={'telegram_id': 1001, 'lang': 'en'}, mob={'id': 'forest_wolf', 'hp': 10},
                    battle_state=battle_state, lang='en',
                )
        self.assertEqual(len(seen), 3)
        self.assertIn((5, ('stun',)), seen)
        self.assertIn((9, ('slow',)), seen)
        self.assertTrue(any(e[0] == 7 for e in seen))
        self.assertTrue(battle_state['enemy_units'][0]['dead'])
        self.assertEqual(battle_state['enemy_units'][1]['mob_effects'], ['acted'])
        self.assertEqual(battle_state['enemy_units'][2]['mob_effects'], ['acted'])

    def test_non_active_acting_unit_does_not_overwrite_active_target_projection(self):
        battle_state = {
            'pve_encounter_id': 'enc-pack-proj-2',
            'enemy_units': [
                {'unit_id': 'u1', 'dead': False, 'hp': 11, 'max_hp': 11, 'mob_effects': []},
                {'unit_id': 'u2', 'dead': False, 'hp': 9, 'max_hp': 10, 'mob_effects': ['active_mark']},
                {'unit_id': 'u3', 'dead': False, 'hp': 7, 'max_hp': 10, 'mob_effects': ['acting_mark']},
            ],
            'active_enemy_unit_id': 'u2',
            'mob_hp': 9,
            'mob_max_hp': 10,
            'mob_effects': ['active_mark'],
            'player_hp': 100, 'player_max_hp': 100, 'player_mana': 50, 'player_max_mana': 50,
            'side_a_player_ids': [1001], 'participant_states': {'1001': {'player_hp': 100}},
        }
        pid_u3 = enemy_unit_participant_id('enc-pack-proj-2', 2)
        with patch.object(battle_handler, 'process_enemy_side_turn', side_effect=lambda _m, _p, s, **_k: (s.update({'mob_hp': 3, 'mob_effects': ['u3_after']}), s)[1]):
            battle_handler._run_group_enemy_side_action(
                action=SimpleNamespace(participant_id=pid_u3, action_type='enemy_basic_attack'),
                owner_player={'telegram_id': 1001, 'lang': 'en'},
                mob={'id': 'forest_wolf', 'hp': 10},
                battle_state=battle_state,
                lang='en',
            )
        self.assertEqual(battle_state['enemy_units'][2]['hp'], 3)
        self.assertEqual(battle_state['enemy_units'][2]['mob_effects'], ['u3_after'])
        self.assertEqual(battle_state['enemy_units'][1]['hp'], 9)
        self.assertEqual(battle_state['enemy_units'][1]['mob_effects'], ['active_mark'])
        self.assertEqual(battle_state['active_enemy_unit_id'], 'u2')
        self.assertEqual(battle_state['mob_hp'], 9)
        self.assertEqual(battle_state['mob_effects'], ['active_mark'])

    def test_non_pack_enemy_side_preserves_legitimate_mutations(self):
        battle_state = {
            'pve_encounter_id': 'enc-solo-preserve-1',
            'mob_hp': 12, 'mob_max_hp': 12, 'mob_effects': [],
            'player_hp': 100, 'player_max_hp': 100, 'player_mana': 50, 'player_max_mana': 50,
            'side_a_player_ids': [1001], 'participant_states': {'1001': {'player_hp': 100}},
        }
        with patch.object(battle_handler, 'process_enemy_side_turn', side_effect=lambda _m, _p, s, **_k: s.update({'mob_hp': 8})):
            battle_handler._run_group_enemy_side_action(
                action=SimpleNamespace(participant_id=-999, action_type='enemy_basic_attack'),
                owner_player={'telegram_id': 1001, 'lang': 'en'},
                mob={'id': 'forest_wolf', 'hp': 20},
                battle_state=battle_state,
                lang='en',
            )
        self.assertEqual(battle_state['mob_hp'], 8)

    def test_pack_enemy_side_timing_ticks_once_for_full_side(self):
        battle_state = {
            'pve_encounter_id': 'enc-pack-timing-1',
            'enemy_units': [
                {'unit_id': 'u1', 'dead': False, 'hp': 10, 'max_hp': 10, 'mob_effects': []},
                {'unit_id': 'u2', 'dead': False, 'hp': 10, 'max_hp': 10, 'mob_effects': []},
                {'unit_id': 'u3', 'dead': False, 'hp': 10, 'max_hp': 10, 'mob_effects': []},
            ],
            'active_enemy_unit_id': 'u1',
            'player_hp': 100, 'player_max_hp': 100, 'player_mana': 50, 'player_max_mana': 50,
            'mob_hp': 10, 'mob_max_hp': 10, 'mob_effects': [],
            'defense_buff_turns': 3, 'turn': 5,
            'side_a_player_ids': [1001], 'participant_states': {'1001': {'player_hp': 100}},
        }
        participant_ids = enemy_participant_ids_for_battle(encounter_id='enc-pack-timing-1', battle_state=battle_state)
        battle_state['_pack_enemy_side_total'] = len(participant_ids)
        battle_state['_pack_enemy_side_processed'] = 0

        calls = []
        def _fake_enemy_turn(_mob, _player_state, state, **kwargs):
            calls.append(kwargs)
            if kwargs.get('increment_turn'):
                state['turn'] = int(state.get('turn', 0) or 0) + 1
            if kwargs.get('tick_player_post_action_buffs'):
                state['defense_buff_turns'] = max(0, int(state.get('defense_buff_turns', 0) or 0) - 1)

        with patch.object(battle_handler, 'process_enemy_side_turn', side_effect=_fake_enemy_turn):
            for pid in participant_ids:
                battle_handler._run_group_enemy_side_action(
                    action=SimpleNamespace(participant_id=pid, action_type='enemy_basic_attack'),
                    owner_player={'telegram_id': 1001, 'lang': 'en'}, mob={'id': 'forest_wolf', 'hp': 20},
                    battle_state=battle_state, lang='en',
                )
        self.assertEqual(len(calls), 3)
        self.assertEqual(sum(1 for c in calls if c.get('increment_turn')), 1)
        self.assertEqual(battle_state['turn'], 6)
        self.assertEqual(battle_state['defense_buff_turns'], 2)

    def test_single_enemy_timing_behavior_unchanged(self):
        battle_state = {
            'pve_encounter_id': 'enc-solo-timing-1',
            'player_hp': 100, 'player_max_hp': 100, 'player_mana': 50, 'player_max_mana': 50,
            'mob_hp': 10, 'mob_max_hp': 10, 'mob_effects': [],
            'defense_buff_turns': 3, 'turn': 7,
            'side_a_player_ids': [1001], 'participant_states': {'1001': {'player_hp': 100}},
        }
        ensure_runtime_for_battle(player_id=1001, battle_state=battle_state, mob={'id': 'forest_wolf', 'hp': 20})
        submit_player_commit(player_id=1001, action_type='basic_attack', battle_state=battle_state)
        resolve_current_side_if_ready(player_id=1001, battle_state=battle_state, on_player_action=lambda _a: None, on_enemy_action=lambda _a: None)
        flags = []
        with patch.object(battle_handler, 'process_enemy_side_turn', side_effect=lambda _m, _p, s, **k: flags.append(k)):
            run_enemy_instant_side(
                player_id=1001,
                battle_state=battle_state,
                on_enemy_action=lambda action: battle_handler._run_group_enemy_side_action(
                    action=action, owner_player={'telegram_id': 1001, 'lang': 'en'}, mob={'id': 'forest_wolf', 'hp': 20},
                    battle_state=battle_state, lang='en',
                ),
            )
        self.assertEqual(len(flags), 1)
        self.assertTrue(flags[0].get('increment_turn'))
        self.assertTrue(flags[0].get('tick_player_post_action_buffs'))

    def test_pack_claim_links_all_same_group_spawns_under_one_encounter(self):
        player_id = 9101
        conn = get_connection()
        conn.execute(
            "UPDATE pve_spawn_instances SET state='idle', linked_encounter_id=NULL, respawn_available_at=NULL WHERE location_id='westwild_n7' AND mob_id='forest_wolf'"
        )
        conn.execute(
            """INSERT OR REPLACE INTO players (telegram_id, name, level, hp, max_hp, mana, max_mana, gold, exp, strength, agility, intuition, vitality, wisdom, luck, stat_points, location_id, in_battle, lang)
               VALUES (?, 'PackTester', 1, 50, 50, 20, 20, 0, 0, 5, 5, 5, 5, 5, 5, 0, 'westwild_n7', 0, 'en')""",
            (player_id,),
        )
        conn.commit()
        conn.close()
        battle_state = {'mob_id': 'forest_wolf', 'log': []}
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=player_id, location_id='westwild_n7', mob_id='forest_wolf',
            battle_state=battle_state, mob={'id': 'forest_wolf', 'hp': 20}, side_a_player_ids=[player_id],
            spawn_instance_id='spawn-westwild_n7-forest_wolf', pack_claim_from_visible_group=True,
        )
        self.assertEqual(status, 'created')
        self.assertTrue(encounter_id)
        conn = get_connection()
        enc = conn.execute("SELECT anchor_spawn_instance_id FROM pve_encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
        rows = conn.execute("SELECT spawn_instance_id, linked_encounter_id FROM pve_spawn_instances WHERE location_id='westwild_n7' AND mob_id='forest_wolf' AND linked_encounter_id=?", (encounter_id,)).fetchall()
        conn.close()
        self.assertTrue(enc['anchor_spawn_instance_id'])
        self.assertGreaterEqual(len(rows), 3)
        self.assertTrue(all(str(r['linked_encounter_id']) == str(encounter_id) for r in rows))

    def test_pack_claim_requires_explicit_anchor_spawn_still_idle_and_unlinked(self):
        player_id = 9103
        conn = get_connection()
        conn.execute(
            "UPDATE pve_spawn_instances SET state='idle', linked_encounter_id=NULL, respawn_available_at=NULL WHERE location_id='westwild_n7' AND mob_id='forest_wolf'"
        )
        conn.execute(
            "UPDATE pve_spawn_instances SET state='forming', linked_encounter_id='pve-enc-existing-anchor' WHERE spawn_instance_id='spawn-westwild_n7-forest_wolf'"
        )
        conn.execute(
            """INSERT OR REPLACE INTO players (telegram_id, name, level, hp, max_hp, mana, max_mana, gold, exp, strength, agility, intuition, vitality, wisdom, luck, stat_points, location_id, in_battle, lang)
               VALUES (?, 'PackAnchorBusy', 1, 50, 50, 20, 20, 0, 0, 5, 5, 5, 5, 5, 5, 0, 'westwild_n7', 0, 'en')""",
            (player_id,),
        )
        conn.commit()
        conn.close()

        battle_state = {'mob_id': 'forest_wolf', 'log': []}
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=player_id, location_id='westwild_n7', mob_id='forest_wolf',
            battle_state=battle_state, mob={'id': 'forest_wolf', 'hp': 20}, side_a_player_ids=[player_id],
            spawn_instance_id='spawn-westwild_n7-forest_wolf', pack_claim_from_visible_group=True,
        )
        self.assertEqual(status, 'spawn_busy')
        self.assertEqual(encounter_id, 'pve-enc-existing-anchor')

        conn = get_connection()
        linked_rows = conn.execute(
            "SELECT spawn_instance_id FROM pve_spawn_instances WHERE linked_encounter_id='pve-enc-existing-anchor' AND location_id='westwild_n7' AND mob_id='forest_wolf'"
        ).fetchall()
        sibling_rows = conn.execute(
            "SELECT spawn_instance_id FROM pve_spawn_instances WHERE location_id='westwild_n7' AND mob_id='forest_wolf' AND spawn_instance_id != 'spawn-westwild_n7-forest_wolf' AND linked_encounter_id IS NOT NULL"
        ).fetchall()
        conn.close()
        self.assertEqual(len(linked_rows), 1)
        self.assertEqual(len(sibling_rows), 0)

    def test_pack_claim_helper_rejects_group_claim_when_required_anchor_is_no_longer_claimable(self):
        conn = get_connection()
        conn.execute(
            "UPDATE pve_spawn_instances SET state='idle', linked_encounter_id=NULL, respawn_available_at=NULL WHERE location_id='westwild_n7' AND mob_id='forest_wolf'"
        )
        anchor_row = conn.execute(
            "SELECT spawn_instance_id FROM pve_spawn_instances WHERE location_id='westwild_n7' AND mob_id='forest_wolf' ORDER BY spawn_instance_id ASC LIMIT 1"
        ).fetchone()
        anchor_spawn_id = str(anchor_row['spawn_instance_id'])
        conn.execute(
            "UPDATE pve_spawn_instances SET state='forming', linked_encounter_id='pve-enc-busy-anchor' WHERE spawn_instance_id=?",
            (anchor_spawn_id,),
        )
        conn.commit()
        conn.close()

        claimed = _claim_spawn_pack_for_encounter(
            encounter_id='pve-enc-should-not-claim',
            location_id='westwild_n7',
            mob_id='forest_wolf',
            spawn_profile='normal',
            special_spawn_key=None,
            special_spawn_name=None,
            required_anchor_spawn_instance_id=anchor_spawn_id,
        )
        self.assertEqual(claimed, [])

        conn = get_connection()
        sibling_rows = conn.execute(
            "SELECT spawn_instance_id, linked_encounter_id, state FROM pve_spawn_instances WHERE location_id='westwild_n7' AND mob_id='forest_wolf' AND spawn_instance_id != ? ORDER BY spawn_instance_id ASC",
            (anchor_spawn_id,),
        ).fetchall()
        conn.close()
        self.assertGreaterEqual(len(sibling_rows), 2)
        self.assertTrue(all(str(row['state']) == 'idle' for row in sibling_rows))
        self.assertTrue(all(row['linked_encounter_id'] is None for row in sibling_rows))

    def test_pack_lock_runtime_start_transitions_all_linked_forming_rows_to_active(self):
        player_id = 9102
        conn = get_connection()
        conn.execute(
            "UPDATE pve_spawn_instances SET state='idle', linked_encounter_id=NULL, respawn_available_at=NULL WHERE location_id='westwild_n7' AND mob_id='forest_wolf'"
        )
        conn.execute(
            """INSERT OR REPLACE INTO players (telegram_id, name, level, hp, max_hp, mana, max_mana, gold, exp, strength, agility, intuition, vitality, wisdom, luck, stat_points, location_id, in_battle, lang)
               VALUES (?, 'PackLocker', 1, 50, 50, 20, 20, 0, 0, 5, 5, 5, 5, 5, 5, 0, 'westwild_n7', 0, 'en')""",
            (player_id,),
        )
        conn.commit()
        conn.close()

        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=player_id, location_id='westwild_n7', mob_id='forest_wolf',
            battle_state={'mob_id': 'forest_wolf', 'log': []}, mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[player_id], spawn_instance_id='spawn-westwild_n7-forest_wolf',
            pack_claim_from_visible_group=True,
        )
        self.assertEqual(status, 'created')
        conn = get_connection()
        forming_rows = conn.execute(
            "SELECT spawn_instance_id, state FROM pve_spawn_instances WHERE linked_encounter_id=? ORDER BY spawn_instance_id ASC",
            (encounter_id,),
        ).fetchall()
        conn.close()
        self.assertGreaterEqual(len(forming_rows), 3)
        self.assertTrue(all(str(row['state']) == 'forming' for row in forming_rows))

        locked_roster = lock_open_world_pve_roster_for_runtime_start(encounter_id=encounter_id)
        self.assertIsNotNone(locked_roster)
        conn = get_connection()
        active_rows = conn.execute(
            "SELECT spawn_instance_id, state FROM pve_spawn_instances WHERE linked_encounter_id=? ORDER BY spawn_instance_id ASC",
            (encounter_id,),
        ).fetchall()
        conn.close()
        self.assertEqual(len(active_rows), len(forming_rows))
        self.assertTrue(all(str(row['state']) == 'active' for row in active_rows))

    def test_victory_cleanup_preserves_levelup_if_earlier_pack_reward_levels_owner(self):
        query = SimpleNamespace()
        context = SimpleNamespace(user_data={})
        battle_state = {'enemy_units': [{}, {}], 'pve_encounter_id': 'enc-reward-1', 'weapon_id': 'unarmed'}
        player = {'telegram_id': 501, 'lang': 'en', 'level': 1, 'exp': 0, 'gold': 0}
        captured = []
        with patch('handlers.battle.get_player', return_value=player), \
             patch('handlers.battle.calc_rewards', side_effect=[{'exp': 10, 'gold': 5, 'loot': []}, {'exp': 10, 'gold': 5, 'loot': []}]), \
             patch('handlers.battle.apply_rewards', side_effect=[{'leveled_up': True, 'new_level': 2, 'new_exp': 1, 'new_gold': 5}, {'leveled_up': False, 'new_level': 2, 'new_exp': 2, 'new_gold': 10}]), \
             patch('handlers.battle.finish_solo_pve_encounter'), \
             patch('handlers.battle.end_battle'), \
             patch('handlers.battle.add_mastery_exp', return_value={'leveled_up': False}), \
             patch('handlers.battle.register_hunt_kill_progress'), \
             patch('handlers.battle.get_mob_name', return_value='wolf'), \
             patch('handlers.battle.t', side_effect=lambda key, lang='en', **kwargs: f"{key}:{kwargs}"), \
             patch('handlers.battle.safe_edit', side_effect=lambda _q, text, **_k: captured.append(text)):
            asyncio.run(_handle_victory_cleanup(query, context, 501, player, {'id': 'forest_wolf', 'hp': 20}, battle_state, 'en'))
        self.assertTrue(any('battle.levelup' in text for text in captured))

    def test_single_enemy_runtime_still_uses_one_enemy_participant(self):
        battle_state = {'pve_encounter_id': 'enc-solo-1', 'mob_dead': False, 'player_dead': False}
        participants = enemy_participant_ids_for_battle(encounter_id='enc-solo-1', battle_state=battle_state)
        self.assertEqual(len(participants), 1)

    def test_pve_detail_shows_pack_count_when_pack(self):
        player = {'telegram_id': 1, 'lang': 'en'}
        detail = {
            'encounter_id': 'enc-1', 'status': 'active', 'mob_id': 'forest_wolf', 'spawn_profile': 'normal',
            'special_spawn_key': '', 'special_spawn_name': '', 'participant_count': 1,
            'participant_player_ids': [1], 'joinable': True, 'is_pack': True, 'enemy_count': 3,
        }
        with patch('handlers.location.get_open_world_pve_encounter_detail', return_value=detail), patch('handlers.location.can_join_open_world_pve_encounter', return_value=(True, 'ok')):
            text, _ = build_pve_encounter_detail_message(player, 'enc-1')
        self.assertIn('Enemies: 3', text)


if __name__ == '__main__':
    unittest.main()
