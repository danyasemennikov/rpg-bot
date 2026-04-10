import unittest
from unittest.mock import Mock, patch

from database import get_connection
from game.pve_live import (
    create_or_load_open_world_pve_encounter,
    finish_solo_pve_encounter,
    get_active_pve_encounter_id_for_player,
    get_open_world_pve_encounter_detail,
    list_location_active_pve_encounters,
    list_location_available_spawn_instances,
)
from handlers.location import build_location_message


class WorldPveEncounterFoundationTests(unittest.TestCase):
    def setUp(self):
        self.player_id = 709001
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
        conn.close()

    def tearDown(self):
        finish_solo_pve_encounter(player_id=self.player_id, status='test_cleanup')
        conn = get_connection()
        conn.execute('DELETE FROM pve_encounter_participants WHERE player_id=?', (self.player_id,))
        conn.execute('DELETE FROM pve_encounters WHERE owner_player_id=?', (self.player_id,))
        conn.execute('DELETE FROM pve_spawn_instances WHERE location_id=?', (self.location_id,))
        conn.execute('DELETE FROM players WHERE telegram_id=?', (self.player_id,))
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
