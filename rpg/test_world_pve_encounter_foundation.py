import unittest
import sqlite3
from unittest.mock import Mock, patch

from database import get_connection
import game.pve_live as pve_live_module
from game.pve_live import (
    OpenWorldRuntimeStartBlocked,
    can_join_open_world_pve_encounter,
    create_or_load_open_world_pve_encounter,
    finish_solo_pve_encounter,
    get_active_pve_encounter_id_for_player,
    get_open_world_pve_encounter_detail,
    join_open_world_pve_encounter,
    lock_open_world_pve_roster_for_runtime_start,
    list_location_active_pve_encounters,
    list_location_available_spawn_instances,
    open_world_runtime_start_mode,
    ensure_runtime_for_battle,
    get_pve_encounter_player_ids,
)
from handlers.location import build_location_message, build_pve_encounter_detail_message


class WorldPveEncounterFoundationTests(unittest.TestCase):
    def setUp(self):
        self.player_id = 709001
        self.player2_id = 709002
        self.player3_id = 709003
        self.location_id = 'dark_forest'
        conn = get_connection()
        conn.execute(
            '''
            INSERT OR REPLACE INTO players (
                telegram_id, username, name, level, exp, hp, max_hp, mana, max_mana,
                strength, agility, intuition, vitality, wisdom, luck, stat_points,
                location_id, in_battle, gold, lang
            ) VALUES (?, ?, ?, 10, 0, 120, 120, 50, 50, 5, 5, 5, 5, 5, 5, 0, ?, 0, 0, 'en')
            ''',
            (self.player_id, 'spawn_tester', 'SpawnTester', self.location_id),
        )
        conn.commit()
        conn.execute(
            '''
            INSERT OR REPLACE INTO players (
                telegram_id, username, name, level, exp, hp, max_hp, mana, max_mana,
                strength, agility, intuition, vitality, wisdom, luck, stat_points,
                location_id, in_battle, gold, lang
            ) VALUES (?, ?, ?, 10, 0, 120, 120, 50, 50, 5, 5, 5, 5, 5, 5, 0, ?, 0, 0, 'en')
            ''',
            (self.player2_id, 'join_tester', 'JoinTester', self.location_id),
        )
        conn.execute(
            '''
            INSERT OR REPLACE INTO players (
                telegram_id, username, name, level, exp, hp, max_hp, mana, max_mana,
                strength, agility, intuition, vitality, wisdom, luck, stat_points,
                location_id, in_battle, gold, lang
            ) VALUES (?, ?, ?, 10, 0, 120, 120, 50, 50, 5, 5, 5, 5, 5, 5, 0, ?, 0, 0, 'en')
            ''',
            (self.player3_id, 'late_tester', 'LateTester', self.location_id),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        finish_solo_pve_encounter(player_id=self.player_id, status='test_cleanup')
        conn = get_connection()
        conn.execute('DELETE FROM pve_encounter_participants WHERE player_id=?', (self.player_id,))
        conn.execute('DELETE FROM pve_encounter_participants WHERE player_id=?', (self.player2_id,))
        conn.execute('DELETE FROM pve_encounter_participants WHERE player_id=?', (self.player3_id,))
        conn.execute('DELETE FROM pve_encounters WHERE owner_player_id=?', (self.player_id,))
        conn.execute('DELETE FROM pve_encounters WHERE owner_player_id=?', (self.player2_id,))
        conn.execute('DELETE FROM pve_encounters WHERE owner_player_id=?', (self.player3_id,))
        conn.execute('DELETE FROM pve_spawn_instances WHERE location_id=?', (self.location_id,))
        conn.execute('DELETE FROM players WHERE telegram_id=?', (self.player_id,))
        conn.execute('DELETE FROM players WHERE telegram_id=?', (self.player2_id,))
        conn.execute('DELETE FROM players WHERE telegram_id=?', (self.player3_id,))
        conn.commit()
        conn.close()

    def test_location_renders_idle_spawn_as_available_content(self):
        spawns = list_location_available_spawn_instances(location_id=self.location_id)
        self.assertTrue(any(spawn['mob_id'] == 'forest_wolf' for spawn in spawns))

    def test_spawn_moves_from_available_to_active_encounter_projection(self):
        battle_state = {'mob_id': 'forest_wolf', 'log': []}
        mob = {'id': 'forest_wolf', 'hp': 20}
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state=battle_state,
            mob=mob,
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')
        self.assertIsNotNone(encounter_id)

        available_after = list_location_available_spawn_instances(location_id=self.location_id)
        self.assertFalse(any(spawn['mob_id'] == 'forest_wolf' for spawn in available_after))

        active = list_location_active_pve_encounters(location_id=self.location_id)
        self.assertTrue(any(row['encounter_id'] == encounter_id for row in active))

    def test_duplicate_engagement_same_spawn_is_prevented(self):
        first_state = {'mob_id': 'forest_wolf', 'log': []}
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state=first_state,
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')

        second_state = {'mob_id': 'forest_wolf', 'log': []}
        second_id, second_status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state=second_state,
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(second_status, 'spawn_busy')
        self.assertEqual(second_id, encounter_id)

    def test_cleanup_releases_spawn_after_respawn_window(self):
        battle_state = {'mob_id': 'forest_wolf', 'log': []}
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state=battle_state,
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')
        finish_solo_pve_encounter(player_id=self.player_id, encounter_id=encounter_id, status='victory')

        conn = get_connection()
        conn.execute(
            '''
            UPDATE pve_spawn_instances
            SET respawn_available_at=datetime('now', '-1 second')
            WHERE linked_encounter_id IS NULL AND location_id=? AND mob_id='forest_wolf'
            ''',
            (self.location_id,),
        )
        conn.commit()
        conn.close()

        available = list_location_available_spawn_instances(location_id=self.location_id)
        self.assertTrue(any(spawn['mob_id'] == 'forest_wolf' for spawn in available))

    def test_location_render_split_shows_active_encounter_and_hides_same_mob_button(self):
        battle_state = {'mob_id': 'forest_wolf', 'log': []}
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state=battle_state,
            mob={'id': 'forest_wolf', 'hp': 20, 'level': 2, 'aggressive': False},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')
        player = {
            'telegram_id': self.player_id,
            'lang': 'en',
            'level': 10,
            'hp': 120,
            'max_hp': 120,
            'mana': 50,
            'max_mana': 50,
            'gold': 0,
        }
        location = {'id': self.location_id, 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': ['forest_wolf'], 'services': []}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[]),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            text, keyboard = build_location_message(player, location, pvp_only_view=False)

        self.assertIn('Active PvE encounters', text)
        self.assertIn(encounter_id, text)
        callbacks = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
        self.assertIn(f'pve_view_{encounter_id}', callbacks)
        self.assertNotIn(f'fight_spawn_spawn-{self.location_id}-forest_wolf', callbacks)

    def test_encounter_detail_round_trip_contains_anchor(self):
        battle_state = {'mob_id': 'forest_wolf', 'log': []}
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state=battle_state,
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')
        detail = get_open_world_pve_encounter_detail(encounter_id=encounter_id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail['location_id'], self.location_id)
        self.assertTrue(str(detail['anchor_spawn_instance_id']).startswith('spawn-'))

    def test_joinable_world_pve_rendered_in_location_and_detail(self):
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state={'mob_id': 'forest_wolf', 'log': []},
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')

        player = {
            'telegram_id': self.player2_id,
            'lang': 'en',
            'level': 10,
            'hp': 120,
            'max_hp': 120,
            'mana': 50,
            'max_mana': 50,
            'gold': 0,
        }
        location = {'id': self.location_id, 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': ['forest_wolf'], 'services': []}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[]),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            text, keyboard = build_location_message(player, location, pvp_only_view=False)

        callbacks = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
        self.assertIn(f'pve_join_{encounter_id}', callbacks)
        self.assertIn('joinable', text)

        detail_text, detail_keyboard = build_pve_encounter_detail_message(player, encounter_id)
        detail_callbacks = [btn.callback_data for row in detail_keyboard.inline_keyboard for btn in row]
        self.assertIn(f'pve_join_{encounter_id}', detail_callbacks)
        self.assertIn('State: joinable', detail_text)

    def test_second_player_can_join_before_lock_and_roster_reaches_runtime(self):
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state={'mob_id': 'forest_wolf', 'log': [], 'player_hp': 120, 'player_mana': 50, 'player_max_hp': 120, 'player_max_mana': 50},
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')
        joined, reason = join_open_world_pve_encounter(encounter_id=encounter_id, player_id=self.player2_id)
        self.assertTrue(joined)
        self.assertEqual(reason, 'joined')

        roster = get_pve_encounter_player_ids(encounter_id=encounter_id)
        self.assertEqual(roster, [self.player_id, self.player2_id])

        battle_state = {'pve_encounter_id': encounter_id, 'mob_id': 'forest_wolf', 'log': [], 'player_hp': 120, 'player_mana': 50, 'player_max_hp': 120, 'player_max_mana': 50}
        runtime = ensure_runtime_for_battle(player_id=self.player_id, battle_state=battle_state, mob={'id': 'forest_wolf', 'hp': 20})
        self.assertEqual(runtime.sides['side_a'].participant_order, [self.player_id, self.player2_id])

    def test_same_player_cannot_join_twice(self):
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state={'mob_id': 'forest_wolf', 'log': []},
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')
        self.assertEqual(join_open_world_pve_encounter(encounter_id=encounter_id, player_id=self.player2_id), (True, 'joined'))
        self.assertEqual(join_open_world_pve_encounter(encounter_id=encounter_id, player_id=self.player2_id), (False, 'already_joined'))

    def test_player_cannot_join_after_lock_start(self):
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state={'mob_id': 'forest_wolf', 'log': [], 'player_hp': 120, 'player_mana': 50, 'player_max_hp': 120, 'player_max_mana': 50},
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')
        ensure_runtime_for_battle(
            player_id=self.player_id,
            battle_state={'pve_encounter_id': encounter_id, 'mob_id': 'forest_wolf', 'log': [], 'player_hp': 120, 'player_mana': 50, 'player_max_hp': 120, 'player_max_mana': 50},
            mob={'id': 'forest_wolf', 'hp': 20},
        )
        can_join, reason = can_join_open_world_pve_encounter(encounter_id=encounter_id, player_id=self.player2_id)
        self.assertFalse(can_join)
        self.assertEqual(reason, 'locked')

    def test_runtime_start_locks_final_roster_before_runtime_creation_boundary(self):
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state={'mob_id': 'forest_wolf', 'log': [], 'player_hp': 120, 'player_mana': 50, 'player_max_hp': 120, 'player_max_mana': 50},
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')
        self.assertEqual(join_open_world_pve_encounter(encounter_id=encounter_id, player_id=self.player2_id), (True, 'joined'))

        real_create = pve_live_module._SOLO_PVE_RUNTIME.create_encounter

        def _create_with_late_join(*args, **kwargs):
            late_result = join_open_world_pve_encounter(encounter_id=encounter_id, player_id=self.player3_id)
            self.assertEqual(late_result, (False, 'locked'))
            return real_create(*args, **kwargs)

        battle_state = {
            'pve_encounter_id': encounter_id,
            'mob_id': 'forest_wolf',
            'log': [],
            'player_hp': 120,
            'player_mana': 50,
            'player_max_hp': 120,
            'player_max_mana': 50,
        }
        with patch('game.pve_live._SOLO_PVE_RUNTIME.create_encounter', side_effect=_create_with_late_join):
            runtime = ensure_runtime_for_battle(player_id=self.player_id, battle_state=battle_state, mob={'id': 'forest_wolf', 'hp': 20})

        runtime_roster = runtime.sides['side_a'].participant_order
        db_roster = get_pve_encounter_player_ids(encounter_id=encounter_id)
        self.assertEqual(runtime_roster, [self.player_id, self.player2_id])
        self.assertEqual(db_roster, [self.player_id, self.player2_id])

    def test_hot_helpers_do_not_invoke_schema_ensure_in_runtime_join_paths(self):
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state={'mob_id': 'forest_wolf', 'log': []},
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')
        with patch('game.pve_live._ensure_pve_encounter_table', side_effect=AssertionError('schema ensure called')), \
             patch('game.pve_live._ensure_world_spawn_table', side_effect=AssertionError('schema ensure called')):
            mode = open_world_runtime_start_mode(encounter_id=encounter_id)
            self.assertIn(mode, {'forming_lock_required', 'active_resume'})

            roster = lock_open_world_pve_roster_for_runtime_start(encounter_id=encounter_id)
            self.assertEqual(roster, [self.player_id])

            detail = get_open_world_pve_encounter_detail(encounter_id=encounter_id)
            self.assertIsNotNone(detail)

    def test_anchored_first_start_is_blocked_if_atomic_lock_fails(self):
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state={'mob_id': 'forest_wolf', 'log': [], 'player_hp': 120, 'player_mana': 50, 'player_max_hp': 120, 'player_max_mana': 50},
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')
        battle_state = {
            'pve_encounter_id': encounter_id,
            'anchor_spawn_instance_id': f'spawn-{self.location_id}-forest_wolf',
            'mob_id': 'forest_wolf',
            'log': [],
            'player_hp': 120,
            'player_mana': 50,
            'player_max_hp': 120,
            'player_max_mana': 50,
        }

        with patch('game.pve_live.lock_open_world_pve_roster_for_runtime_start', return_value=None):
            with self.assertRaises(OpenWorldRuntimeStartBlocked):
                ensure_runtime_for_battle(player_id=self.player_id, battle_state=battle_state, mob={'id': 'forest_wolf', 'hp': 20})

    def test_non_anchored_first_start_keeps_fallback_runtime_path(self):
        battle_state = {
            'mob_id': 'forest_wolf',
            'log': [],
            'player_hp': 120,
            'player_mana': 50,
            'player_max_hp': 120,
            'player_max_mana': 50,
        }
        with patch('game.pve_live.open_world_runtime_start_mode', return_value='non_anchored'), \
             patch('game.pve_live.lock_open_world_pve_roster_for_runtime_start', return_value=None):
            runtime = ensure_runtime_for_battle(player_id=self.player_id, battle_state=battle_state, mob={'id': 'forest_wolf', 'hp': 20})
        self.assertIsNotNone(runtime)

    def test_anchored_active_resume_allows_runtime_recreation_without_lock_step(self):
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state={'mob_id': 'forest_wolf', 'log': [], 'player_hp': 120, 'player_mana': 50, 'player_max_hp': 120, 'player_max_mana': 50},
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')
        conn = get_connection()
        conn.execute(
            '''
            UPDATE pve_spawn_instances
            SET state='active'
            WHERE spawn_instance_id=?
            ''',
            (f'spawn-{self.location_id}-forest_wolf',),
        )
        conn.commit()
        conn.close()

        battle_state = {
            'pve_encounter_id': encounter_id,
            'anchor_spawn_instance_id': f'spawn-{self.location_id}-forest_wolf',
            'mob_id': 'forest_wolf',
            'log': [],
            'player_hp': 120,
            'player_mana': 50,
            'player_max_hp': 120,
            'player_max_mana': 50,
        }
        with patch('game.pve_live.lock_open_world_pve_roster_for_runtime_start', return_value=None):
            runtime = ensure_runtime_for_battle(player_id=self.player_id, battle_state=battle_state, mob={'id': 'forest_wolf', 'hp': 20})
        self.assertIsNotNone(runtime)

    def test_stale_non_live_anchored_encounter_cannot_be_joined(self):
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state={'mob_id': 'forest_wolf', 'log': []},
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')
        conn = get_connection()
        conn.execute(
            '''
            UPDATE pve_spawn_instances
            SET linked_encounter_id=NULL, state='respawning'
            WHERE spawn_instance_id=?
            ''',
            (f'spawn-{self.location_id}-forest_wolf',),
        )
        conn.commit()
        conn.close()
        self.assertEqual(
            join_open_world_pve_encounter(encounter_id=encounter_id, player_id=self.player2_id),
            (False, 'not_found'),
        )

    def test_atomic_join_does_not_insert_when_encounter_locked_even_if_stale_precheck_says_ok(self):
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state={'mob_id': 'forest_wolf', 'log': []},
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')

        with patch('game.pve_live.can_join_open_world_pve_encounter', return_value=(True, 'ok')):
            conn = get_connection()
            conn.execute(
                '''
                UPDATE pve_spawn_instances
                SET state='active'
                WHERE spawn_instance_id=?
                ''',
                (f'spawn-{self.location_id}-forest_wolf',),
            )
            conn.commit()
            conn.close()
            joined, reason = join_open_world_pve_encounter(encounter_id=encounter_id, player_id=self.player2_id)

        self.assertFalse(joined)
        self.assertEqual(reason, 'locked')
        roster = get_pve_encounter_player_ids(encounter_id=encounter_id)
        self.assertEqual(roster, [self.player_id])

    def test_stale_active_detail_not_returned_when_anchor_is_no_longer_live(self):
        battle_state = {'mob_id': 'forest_wolf', 'log': []}
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state=battle_state,
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(status, 'created')

        conn = get_connection()
        conn.execute(
            '''
            UPDATE pve_spawn_instances
            SET linked_encounter_id=NULL, state='respawning'
            WHERE spawn_instance_id=?
            ''',
            (f'spawn-{self.location_id}-forest_wolf',),
        )
        conn.commit()
        conn.close()

        detail = get_open_world_pve_encounter_detail(encounter_id=encounter_id)
        self.assertIsNone(detail)

    def test_ensure_schema_false_does_not_swallow_generic_operational_error(self):
        fake_conn = Mock()
        fake_conn.execute.side_effect = RuntimeError('db locked during select')
        fake_conn.close.return_value = None
        with patch('game.pve_live.get_connection', return_value=fake_conn):
            with self.assertRaises(RuntimeError):
                get_active_pve_encounter_id_for_player(player_id=self.player_id, ensure_schema=False)

    def test_partial_migration_owner_fallback_works_without_participants_table(self):
        db_uri = 'file:pve_partial_migration?mode=memory&cache=shared'
        keeper = sqlite3.connect(db_uri, uri=True)
        keeper.row_factory = sqlite3.Row
        keeper.execute(
            '''
            CREATE TABLE pve_encounters (
                encounter_id      TEXT PRIMARY KEY,
                owner_player_id   INTEGER NOT NULL,
                status            TEXT NOT NULL,
                mob_id            TEXT,
                battle_state_json TEXT NOT NULL,
                mob_json          TEXT NOT NULL,
                created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at       TIMESTAMP
            )
            '''
        )
        keeper.execute(
            '''
            CREATE TABLE pve_spawn_instances (
                spawn_instance_id     TEXT PRIMARY KEY,
                location_id           TEXT NOT NULL,
                mob_id                TEXT NOT NULL,
                state                 TEXT NOT NULL,
                linked_encounter_id   TEXT,
                respawn_available_at  TIMESTAMP,
                created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        keeper.execute(
            '''
            INSERT INTO pve_encounters (
                encounter_id, owner_player_id, status, mob_id, battle_state_json, mob_json
            ) VALUES (?, ?, 'active', 'forest_wolf', '{}', '{}')
            ''',
            ('legacy-enc-1', self.player_id),
        )
        keeper.execute(
            '''
            INSERT INTO pve_spawn_instances (
                spawn_instance_id, location_id, mob_id, state, linked_encounter_id
            ) VALUES (?, ?, ?, 'active', ?)
            ''',
            ('spawn-dark_forest-forest_wolf', self.location_id, 'forest_wolf', 'legacy-enc-1'),
        )
        keeper.commit()

        def _partial_conn():
            conn = sqlite3.connect(db_uri, uri=True)
            conn.row_factory = sqlite3.Row
            return conn

        with patch('game.pve_live.get_connection', side_effect=_partial_conn):
            encounter_id = get_active_pve_encounter_id_for_player(
                player_id=self.player_id,
                ensure_schema=False,
            )
            self.assertEqual(encounter_id, 'legacy-enc-1')

            finish_solo_pve_encounter(
                player_id=self.player_id,
                encounter_id=None,
                status='finished',
            )

            verify = _partial_conn()
            row = verify.execute(
                'SELECT status, finished_at FROM pve_encounters WHERE encounter_id=?',
                ('legacy-enc-1',),
            ).fetchone()
            spawn_row = verify.execute(
                'SELECT state, linked_encounter_id FROM pve_spawn_instances WHERE spawn_instance_id=?',
                ('spawn-dark_forest-forest_wolf',),
            ).fetchone()
            verify.close()

        keeper.close()

        self.assertEqual(row['status'], 'finished')
        self.assertIsNotNone(row['finished_at'])
        self.assertEqual(spawn_row['state'], 'respawning')
        self.assertIsNone(spawn_row['linked_encounter_id'])

    def test_supersede_transitions_old_anchored_spawn_to_respawning_and_releases_link(self):
        first_battle = {'mob_id': 'forest_wolf', 'log': []}
        first_encounter_id, first_status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state=first_battle,
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(first_status, 'created')

        second_battle = {'mob_id': 'forest_boar', 'log': []}
        second_encounter_id, second_status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_boar',
            battle_state=second_battle,
            mob={'id': 'forest_boar', 'hp': 22},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(second_status, 'created')
        self.assertNotEqual(first_encounter_id, second_encounter_id)

        conn = get_connection()
        first_row = conn.execute(
            'SELECT status FROM pve_encounters WHERE encounter_id=?',
            (first_encounter_id,),
        ).fetchone()
        spawn_row = conn.execute(
            '''
            SELECT state, linked_encounter_id, respawn_available_at
            FROM pve_spawn_instances
            WHERE spawn_instance_id=?
            ''',
            (f'spawn-{self.location_id}-forest_wolf',),
        ).fetchone()
        conn.close()

        self.assertEqual(first_row['status'], 'superseded')
        self.assertEqual(spawn_row['state'], 'respawning')
        self.assertIsNone(spawn_row['linked_encounter_id'])
        self.assertIsNotNone(spawn_row['respawn_available_at'])

    def test_superseded_spawn_does_not_stay_invisible_blocked(self):
        first_battle = {'mob_id': 'forest_wolf', 'log': []}
        first_encounter_id, first_status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_wolf',
            battle_state=first_battle,
            mob={'id': 'forest_wolf', 'hp': 20},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(first_status, 'created')

        second_battle = {'mob_id': 'forest_boar', 'log': []}
        _second_encounter_id, second_status = create_or_load_open_world_pve_encounter(
            owner_player_id=self.player_id,
            location_id=self.location_id,
            mob_id='forest_boar',
            battle_state=second_battle,
            mob={'id': 'forest_boar', 'hp': 22},
            side_a_player_ids=[self.player_id],
        )
        self.assertEqual(second_status, 'created')

        conn = get_connection()
        conn.execute(
            '''
            UPDATE pve_spawn_instances
            SET respawn_available_at=datetime('now', '-1 second')
            WHERE spawn_instance_id=?
            ''',
            (f'spawn-{self.location_id}-forest_wolf',),
        )
        conn.commit()
        conn.close()

        available = list_location_available_spawn_instances(location_id=self.location_id)
        self.assertTrue(any(row['spawn_instance_id'] == f'spawn-{self.location_id}-forest_wolf' for row in available))

        active = list_location_active_pve_encounters(location_id=self.location_id)
        self.assertFalse(any(row['encounter_id'] == first_encounter_id for row in active))


if __name__ == '__main__':
    unittest.main()
