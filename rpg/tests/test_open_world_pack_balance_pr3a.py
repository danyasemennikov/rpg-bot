import unittest
from pathlib import Path

from game.open_world_pack_balance import (
    get_open_world_pack_archetype_metadata,
    resolve_enemy_formation_line_for_mob,
)
from database import get_connection
from game.pve_live import create_or_load_open_world_pve_encounter, finish_solo_pve_encounter, list_location_available_spawn_instances
from game.skills import SKILLS


class OpenWorldPackBalancePR3ATests(unittest.TestCase):


    def setUp(self):
        conn = get_connection()
        conn.execute(
            '''
            INSERT OR REPLACE INTO players (
                telegram_id, username, name, level, exp, hp, max_hp, mana, max_mana,
                strength, agility, intuition, vitality, wisdom, luck, stat_points,
                location_id, in_battle, gold, lang
            ) VALUES (?, ?, ?, 10, 0, 120, 120, 50, 50, 5, 5, 5, 5, 5, 5, 0, ?, 0, 0, 'en')
            ''',
            (709001, 'pr3a_tester', 'PR3A Tester', 'westwild_n7'),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        finish_solo_pve_encounter(player_id=709001, status='test_cleanup')
        conn = get_connection()
        try:
            conn.execute('DELETE FROM pve_encounter_participants WHERE player_id=?', (709001,))
            conn.execute('DELETE FROM pve_encounters WHERE owner_player_id=?', (709001,))
            has_spawn_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pve_spawn_instances' LIMIT 1"
            ).fetchone()
            if has_spawn_table:
                conn.execute('DELETE FROM pve_spawn_instances WHERE location_id=?', ('westwild_n7',))
            conn.execute('DELETE FROM players WHERE telegram_id=?', (709001,))
            conn.commit()
        finally:
            conn.close()
    def test_enemy_role_resolver_known_and_unknown_mobs(self):
        self.assertEqual(resolve_enemy_formation_line_for_mob('forest_boar'), 'front')
        self.assertEqual(resolve_enemy_formation_line_for_mob('forest_wolf'), 'melee')
        self.assertEqual(resolve_enemy_formation_line_for_mob('goblin_shaman'), 'support')
        self.assertEqual(resolve_enemy_formation_line_for_mob('totally_unknown_mob_id'), 'melee')

    def test_explicit_formation_line_wins_over_metadata(self):
        self.assertEqual(
            resolve_enemy_formation_line_for_mob('forest_wolf', formation_line='support'),
            'support',
        )


    def test_invalid_explicit_formation_does_not_override_known_metadata(self):
        self.assertEqual(
            resolve_enemy_formation_line_for_mob('forest_boar', formation_line='not_a_line'),
            'front',
        )
        self.assertEqual(
            resolve_enemy_formation_line_for_mob('goblin_shaman', formation_line='bad'),
            'support',
        )

    def test_invalid_explicit_unknown_mob_still_falls_back_safely(self):
        self.assertEqual(
            resolve_enemy_formation_line_for_mob('totally_unknown_mob_id', formation_line='bad'),
            'melee',
        )

    def test_pack_enemy_units_receive_formation_from_metadata(self):
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=709001,
            location_id='westwild_n7',
            mob_id='forest_wolf',
            battle_state={'mob_id': 'forest_wolf', 'mob_hp': 30, 'mob_max_hp': 30, 'log': []},
            mob={'id': 'forest_wolf', 'hp': 30, 'level': 3},
            side_a_player_ids=[709001],
            spawn_instance_id=str(next(spawn['spawn_instance_id'] for spawn in list_location_available_spawn_instances(location_id='westwild_n7') if spawn.get('mob_id') == 'forest_wolf')),
            pack_claim_from_visible_group=True,
        )
        self.assertEqual(status, 'created')

        from game.pve_live import load_active_pve_encounter

        loaded = load_active_pve_encounter(encounter_id=encounter_id)
        self.assertIsNotNone(loaded)
        battle_state, _mob_state = loaded
        units = battle_state.get('enemy_units') or []
        self.assertGreaterEqual(len(units), 2)
        self.assertTrue(all(unit.get('formation_line') == 'melee' for unit in units))
        self.assertEqual(
            battle_state.get('pack_archetype', {}).get('pack_archetype_id'),
            'beast_pack',
        )

    def test_same_group_pack_behavior_still_same(self):
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=709001,
            location_id='westwild_n7',
            mob_id='forest_wolf',
            battle_state={'mob_id': 'forest_wolf', 'mob_hp': 30, 'mob_max_hp': 30, 'log': []},
            mob={'id': 'forest_wolf', 'hp': 30, 'level': 3},
            side_a_player_ids=[709001],
            spawn_instance_id=str(next(spawn['spawn_instance_id'] for spawn in list_location_available_spawn_instances(location_id='westwild_n7') if spawn.get('mob_id') == 'forest_wolf')),
            pack_claim_from_visible_group=True,
        )
        self.assertEqual(status, 'created')
        from game.pve_live import load_active_pve_encounter

        loaded = load_active_pve_encounter(encounter_id=encounter_id)
        battle_state, _mob_state = loaded
        units = battle_state.get('enemy_units') or []
        self.assertEqual(len(units), 3)

    def test_targeting_rollout_stays_frozen_guard(self):
        expected_pattern_skills = {
            'flame_wave',
            'heavy_swing',
            'cleave_through',
            'arcane_lance',
            'hunters_mark',
            'aimed_shot',
            'piercing_arrow',
            'deadeye',
        }
        actual_pattern_skills = {skill_id for skill_id, skill in SKILLS.items() if skill.get('target_pattern_id') is not None}
        self.assertEqual(actual_pattern_skills, expected_pattern_skills)

    def test_documentation_exists_and_mentions_scope_guards(self):
        doc_text = Path(__file__).resolve().parent.parent.joinpath('docs', 'OPEN_WORLD_PACK_BALANCE_BASELINE.md').read_text(encoding='utf-8').lower()
        self.assertIn('formation', doc_text)
        self.assertIn('pack', doc_text)
        self.assertIn('no combat formula changes', doc_text)
        self.assertIn('no blanket skill rollout', doc_text)

    def test_archetype_metadata_is_available_for_live_mobs(self):
        data = get_open_world_pack_archetype_metadata('zombie')
        self.assertEqual(data.get('pack_archetype_id'), 'undead_cluster')


if __name__ == '__main__':
    unittest.main()
