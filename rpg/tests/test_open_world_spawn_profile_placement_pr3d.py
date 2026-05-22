import unittest
from pathlib import Path

from game.locations import WORLD_LOCATIONS, WORLD_ROUTES
from game.open_world_pack_balance import (
    collect_open_world_route_mob_ids,
    get_expected_spawn_profile_for_route_mob,
    get_open_world_pack_archetype_metadata,
    get_open_world_route_composition_by_route_id,
    get_open_world_route_encounter_compositions,
    get_world_location_ids_by_route_id,
    is_open_world_pack_enabled_mob,
    validate_open_world_spawn_profile_placement,
)
from game.open_world_reward_alignment import (
    get_open_world_reward_category_for_spawn_profile,
    get_open_world_reward_profile_for_threat_band,
)
from game.open_world_reward_pools import OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY
from game.pve_live import WORLD_SPAWN_PROFILES
from game.skills import SKILLS


class OpenWorldSpawnProfilePlacementPR3DTests(unittest.TestCase):
    def test_route_composition_resolves_by_route_id(self):
        for entry in get_open_world_route_encounter_compositions():
            route_id = entry.get('route_id')
            self.assertTrue(route_id)
            resolved = get_open_world_route_composition_by_route_id(route_id)
            self.assertEqual(resolved, entry)

    def test_route_location_mapping_exists_for_covered_routes(self):
        covered_route_ids = {entry['route_id'] for entry in get_open_world_route_encounter_compositions()}
        self.assertTrue(covered_route_ids)
        for route_id in covered_route_ids:
            self.assertIn(route_id, WORLD_ROUTES)
            location_ids = get_world_location_ids_by_route_id(route_id)
            self.assertTrue(location_ids, msg=f'No WORLD_LOCATIONS mapping for {route_id}')

    def test_world_spawn_profile_keys_are_valid_and_reward_aligned(self):
        known_profiles = set(WORLD_SPAWN_PROFILES)
        discovered_profiles = set()
        for location in WORLD_LOCATIONS.values():
            for profile_map in (location.get('world_spawn_profiles') or {}).values():
                for profile in profile_map:
                    normalized = str(profile).strip().lower()
                    discovered_profiles.add(normalized)
                    self.assertIn(normalized, known_profiles)
                    category = get_open_world_reward_category_for_spawn_profile(normalized)
                    self.assertTrue(category)
        self.assertTrue(discovered_profiles)

    def test_route_composition_mob_ids_are_present_in_route_live_content(self):
        for entry in get_open_world_route_encounter_compositions():
            route_id = entry['route_id']
            location_ids = get_world_location_ids_by_route_id(route_id)
            route_mobs = set()
            for location_id in location_ids:
                route_mobs.update(str(mob_id) for mob_id in WORLD_LOCATIONS[location_id].get('mobs', []))
            for mob_id in collect_open_world_route_mob_ids(route_id):
                self.assertIn(mob_id, route_mobs, msg=f'{mob_id} missing from {route_id}')

    def test_route_live_content_is_represented_in_route_composition(self):
        for entry in get_open_world_route_encounter_compositions():
            route_id = entry['route_id']
            composition_mobs = collect_open_world_route_mob_ids(route_id)
            location_ids = get_world_location_ids_by_route_id(route_id)
            route_live_all = set()
            for location_id in location_ids:
                location = WORLD_LOCATIONS[location_id]
                route_live_all.update(str(mob_id) for mob_id in location.get('mobs', []) if str(mob_id).strip())
                route_live_all.update(
                    str(mob_id) for mob_id in (location.get('world_spawn_profiles') or {}).keys() if str(mob_id).strip()
                )
            missing = sorted(route_live_all - composition_mobs)
            self.assertFalse(missing, msg=f'{route_id} missing composition coverage for: {missing}')

    def test_pack_mobs_are_normal_profile_compatible(self):
        for entry in get_open_world_route_encounter_compositions():
            route_id = entry['route_id']
            location_ids = get_world_location_ids_by_route_id(route_id)
            for mob_id in entry.get('pack_mob_ids', ()):
                self.assertTrue(is_open_world_pack_enabled_mob(mob_id))
                self.assertTrue(get_open_world_pack_archetype_metadata(mob_id))
                self.assertEqual(get_expected_spawn_profile_for_route_mob(route_id, mob_id), 'normal')

                profile_keys = set()
                for location_id in location_ids:
                    profile_keys.update((WORLD_LOCATIONS[location_id].get('world_spawn_profiles') or {}).get(mob_id, {}).keys())
                self.assertIn('normal', profile_keys)

    def test_elite_anchor_alignment(self):
        for entry in get_open_world_route_encounter_compositions():
            route_id = entry['route_id']
            location_ids = get_world_location_ids_by_route_id(route_id)
            for mob_id in entry.get('elite_anchor_mob_ids', ()):
                self.assertEqual(get_expected_spawn_profile_for_route_mob(route_id, mob_id), 'elite')
                route_profile_keys = set()
                for location_id in location_ids:
                    route_profile_keys.update((WORLD_LOCATIONS[location_id].get('world_spawn_profiles') or {}).get(mob_id, {}).keys())
                if route_profile_keys:
                    self.assertFalse('rare' in route_profile_keys and 'elite' not in route_profile_keys)

    def test_rare_anchor_alignment_if_present(self):
        has_rare = any(entry.get('rare_anchor_mob_ids') for entry in get_open_world_route_encounter_compositions())
        if not has_rare:
            self.assertFalse(has_rare)
            return
        for entry in get_open_world_route_encounter_compositions():
            route_id = entry['route_id']
            location_ids = get_world_location_ids_by_route_id(route_id)
            for mob_id in entry.get('rare_anchor_mob_ids', ()):
                self.assertEqual(get_expected_spawn_profile_for_route_mob(route_id, mob_id), 'rare')
                route_profile_keys = set()
                for location_id in location_ids:
                    route_profile_keys.update((WORLD_LOCATIONS[location_id].get('world_spawn_profiles') or {}).get(mob_id, {}).keys())
                if route_profile_keys:
                    self.assertIn('rare', route_profile_keys)

    def test_reward_alignment_bridge_remains_valid(self):
        discovered_profiles = set()
        for location in WORLD_LOCATIONS.values():
            for profile_map in (location.get('world_spawn_profiles') or {}).values():
                discovered_profiles.update(str(profile).strip().lower() for profile in profile_map)
        for profile in discovered_profiles:
            category = get_open_world_reward_category_for_spawn_profile(profile)
            self.assertIn(category, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY)

        for entry in get_open_world_route_encounter_compositions():
            band_profile = get_open_world_reward_profile_for_threat_band(entry.get('threat_band'))
            self.assertIn(band_profile.get('reward_category'), OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY)
            self.assertEqual(
                band_profile.get('reward_profile_id'),
                OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY[band_profile.get('reward_category')],
            )

    def test_targeting_rollout_stays_frozen_guard(self):
        expected_pattern_skills = {
            'flame_wave', 'heavy_swing', 'cleave_through', 'arcane_lance',
            'hunters_mark', 'aimed_shot', 'piercing_arrow', 'deadeye',
        }
        actual_pattern_skills = {skill_id for skill_id, skill in SKILLS.items() if skill.get('target_pattern_id') is not None}
        self.assertEqual(actual_pattern_skills, expected_pattern_skills)

    def test_documentation_guard(self):
        doc_text = Path(__file__).resolve().parent.parent.joinpath('docs', 'OPEN_WORLD_SPAWN_PROFILE_PLACEMENT_V1.md').read_text(encoding='utf-8').lower()
        self.assertIn('spawn profile placement', doc_text)
        self.assertIn('route composition', doc_text)
        self.assertIn('normal / elite / rare', doc_text)
        self.assertIn('no reward number changes', doc_text)
        self.assertIn('no combat formula changes', doc_text)
        self.assertIn('no blanket skill rollout', doc_text)
        self.assertIn('mixed-mob packs remain future work', doc_text)

    def test_policy_validator_reports_no_errors(self):
        self.assertEqual(validate_open_world_spawn_profile_placement(), [])


if __name__ == '__main__':
    unittest.main()
