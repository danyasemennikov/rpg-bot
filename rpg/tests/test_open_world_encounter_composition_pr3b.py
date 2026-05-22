import unittest
from pathlib import Path

from database import get_connection
from game.locations import WORLD_LOCATIONS, WORLD_ROUTES
from game.open_world_pack_balance import (
    ALLOWED_OPEN_WORLD_THREAT_BANDS,
    get_open_world_pack_archetype_metadata,
    get_open_world_route_encounter_compositions,
    get_pack_enabled_mob_ids,
    is_open_world_pack_enabled_mob,
)
from game.pve_live import (
    PACK_ENABLED_MOB_IDS,
    create_or_load_open_world_pve_encounter,
    finish_solo_pve_encounter,
    list_location_available_spawn_instances,
)
from game.skills import SKILLS


class OpenWorldEncounterCompositionPR3BTests(unittest.TestCase):
    @staticmethod
    def _collect_known_live_open_world_mob_ids() -> set[str]:
        known_mob_ids: set[str] = set()
        for location_data in WORLD_LOCATIONS.values():
            for mob_id in location_data.get('mobs', ()) or ():
                if isinstance(mob_id, str) and mob_id.strip():
                    known_mob_ids.add(mob_id.strip())
            spawn_profiles = location_data.get('world_spawn_profiles') or {}
            if isinstance(spawn_profiles, dict):
                for mob_id in spawn_profiles.keys():
                    if isinstance(mob_id, str) and mob_id.strip():
                        known_mob_ids.add(mob_id.strip())
        return known_mob_ids

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
            (709301, 'pr3b_tester', 'PR3B Tester', 'westwild_n7'),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        finish_solo_pve_encounter(player_id=709301, status='test_cleanup')
        conn = get_connection()
        try:
            conn.execute('DELETE FROM pve_encounter_participants WHERE player_id=?', (709301,))
            conn.execute('DELETE FROM pve_encounters WHERE owner_player_id=?', (709301,))
            has_spawn_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pve_spawn_instances' LIMIT 1"
            ).fetchone()
            if has_spawn_table:
                conn.execute('DELETE FROM pve_spawn_instances WHERE location_id=?', ('westwild_n7',))
            conn.execute('DELETE FROM players WHERE telegram_id=?', (709301,))
            conn.commit()
        finally:
            conn.close()

    def test_pack_enabled_source_of_truth_contains_required_mobs(self):
        enabled = get_pack_enabled_mob_ids()
        self.assertTrue({'forest_wolf', 'white_wolf', 'leech', 'zombie'}.issubset(enabled))

    def test_pve_live_pack_enabled_set_matches_policy_helper(self):
        self.assertEqual(PACK_ENABLED_MOB_IDS, get_pack_enabled_mob_ids())
        for mob_id in PACK_ENABLED_MOB_IDS:
            self.assertTrue(is_open_world_pack_enabled_mob(mob_id))

    def test_every_pack_enabled_mob_has_archetype_metadata(self):
        for mob_id in get_pack_enabled_mob_ids():
            metadata = get_open_world_pack_archetype_metadata(mob_id)
            self.assertTrue(metadata, mob_id)
            self.assertTrue(metadata.get('pack_archetype_id'), mob_id)
            self.assertIn(metadata.get('threat_band'), ALLOWED_OPEN_WORLD_THREAT_BANDS, mob_id)
            self.assertLessEqual(int(metadata.get('expected_size_min', 0)), int(metadata.get('expected_size_max', 0)), mob_id)

    def test_route_composition_entries_are_valid(self):
        for entry in get_open_world_route_encounter_compositions():
            self.assertTrue(entry.get('route_id') or entry.get('region_id'))
            self.assertIn(entry.get('threat_band'), ALLOWED_OPEN_WORLD_THREAT_BANDS)

            for key in ('solo_mob_ids', 'pack_mob_ids', 'elite_anchor_mob_ids', 'rare_anchor_mob_ids'):
                value = entry.get(key)
                self.assertIsInstance(value, (list, tuple), key)
                self.assertTrue(all(isinstance(mob_id, str) for mob_id in value), key)

            for mob_id in entry.get('pack_mob_ids', ()):  # type: ignore[arg-type]
                self.assertIn(mob_id, get_pack_enabled_mob_ids())
                self.assertTrue(get_open_world_pack_archetype_metadata(mob_id))

    def test_route_composition_references_existing_live_mobs(self):
        known_live_mob_ids = self._collect_known_live_open_world_mob_ids()
        self.assertTrue(known_live_mob_ids)

        for entry in get_open_world_route_encounter_compositions():
            route_id = str(entry.get('route_id') or entry.get('region_id') or 'unknown_route')
            for field_name in ('solo_mob_ids', 'pack_mob_ids', 'elite_anchor_mob_ids', 'rare_anchor_mob_ids'):
                listed_mob_ids = entry.get(field_name, ()) or ()
                missing_ids = sorted(
                    mob_id for mob_id in listed_mob_ids
                    if mob_id not in known_live_mob_ids
                )
                self.assertEqual(
                    missing_ids,
                    [],
                    msg=f'route={route_id} field={field_name} has missing live mob ids: {missing_ids}',
                )

    def test_canonical_route_coverage_exists(self):
        composed_ids = {entry.get('route_id') for entry in get_open_world_route_encounter_compositions()}
        required = {
            'route_westwild',
            'route_frostspine',
            'route_ashen_ruins',
            'route_sunscar',
            'route_mireveil',
            'route_south_coast_stub',
        }
        self.assertTrue(required.issubset(set(WORLD_ROUTES.keys())))
        self.assertTrue(required.issubset(composed_ids))

    def test_same_group_pack_runtime_behavior_still_works(self):
        encounter_id, status = create_or_load_open_world_pve_encounter(
            owner_player_id=709301,
            location_id='westwild_n7',
            mob_id='forest_wolf',
            battle_state={'mob_id': 'forest_wolf', 'mob_hp': 30, 'mob_max_hp': 30, 'log': []},
            mob={'id': 'forest_wolf', 'hp': 30, 'level': 3},
            side_a_player_ids=[709301],
            spawn_instance_id=str(next(spawn['spawn_instance_id'] for spawn in list_location_available_spawn_instances(location_id='westwild_n7') if spawn.get('mob_id') == 'forest_wolf')),
            pack_claim_from_visible_group=True,
        )
        self.assertEqual(status, 'created')

        from game.pve_live import load_active_pve_encounter

        loaded = load_active_pve_encounter(encounter_id=encounter_id)
        self.assertIsNotNone(loaded)
        battle_state, _mob_state = loaded
        units = battle_state.get('enemy_units') or []
        self.assertEqual(len(units), 3)
        self.assertTrue(all(unit.get('formation_line') == 'melee' for unit in units))
        self.assertTrue((battle_state.get('pack_archetype') or {}).get('pack_archetype_id'))

    def test_targeting_rollout_stays_frozen_guard(self):
        expected_pattern_skills = {
            'flame_wave', 'heavy_swing', 'cleave_through', 'arcane_lance',
            'hunters_mark', 'aimed_shot', 'piercing_arrow', 'deadeye',
        }
        actual_pattern_skills = {skill_id for skill_id, skill in SKILLS.items() if skill.get('target_pattern_id') is not None}
        self.assertEqual(actual_pattern_skills, expected_pattern_skills)

    def test_documentation_mentions_scope_boundaries(self):
        doc_text = Path(__file__).resolve().parent.parent.joinpath('docs', 'OPEN_WORLD_ENCOUNTER_COMPOSITION_V1.md').read_text(encoding='utf-8').lower()
        self.assertIn('route-level encounter composition', doc_text)
        self.assertIn('pack eligibility', doc_text)
        self.assertIn('mixed-mob packs', doc_text)
        self.assertIn('no combat formula changes', doc_text)
        self.assertIn('no reward number changes', doc_text)
        self.assertIn('no blanket skill rollout', doc_text)


if __name__ == '__main__':
    unittest.main()
