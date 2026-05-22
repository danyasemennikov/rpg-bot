import unittest
from pathlib import Path

from game.locations import WORLD_LOCATIONS
from game.open_world_pack_balance import (
    collect_open_world_route_mob_ids,
    get_world_location_ids_by_route_id,
    validate_open_world_spawn_profile_placement,
)
from game.open_world_reward_alignment import validate_open_world_reward_alignment_metadata
from game.open_world_reward_pools import OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY
from game.open_world_route_balance_report import (
    build_open_world_route_balance_report,
    validate_open_world_route_balance_reports,
)
from game.skills import SKILLS


class OpenWorldRouteTuningPass2PR3GTests(unittest.TestCase):
    def test_frostspine_route_report_tuning_state(self):
        report = build_open_world_route_balance_report('route_frostspine')

        self.assertEqual(report.get('route_id'), 'route_frostspine')
        self.assertFalse(report.get('is_sparse_or_stub'))
        self.assertGreaterEqual(report.get('location_count', 0), 1)

        self.assertGreater(report.get('solo_count', 0), 0)
        self.assertGreater(report.get('pack_count', 0), 0)
        self.assertGreater(report.get('elite_anchor_count', 0), 0)

        self.assertTrue(report.get('pack_archetype_coverage_complete'))
        self.assertTrue(report.get('pack_eligibility_coverage_complete'))

        reward_category = report.get('reward_category')
        reward_profile_id = report.get('reward_profile_id')
        self.assertIn(reward_category, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY)
        self.assertEqual(reward_profile_id, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY[reward_category])

        warnings = set(report.get('readiness_warnings', ()))
        self.assertNotIn('no_pack_mobs_on_non_stub_route', warnings)
        self.assertNotIn('no_elite_anchors_on_non_stub_route', warnings)
        self.assertNotIn('pack_mobs_missing_archetype_metadata', warnings)

        if report.get('rare_anchor_count', 0) == 0:
            self.assertIn('no_rare_anchors', warnings)

    def test_old_mine_stub_report_tuning_state(self):
        report = build_open_world_route_balance_report('route_old_mine_stub')

        self.assertEqual(report.get('route_id'), 'route_old_mine_stub')
        self.assertTrue(report.get('is_sparse_or_stub'))
        self.assertGreaterEqual(report.get('location_count', 0), 1)

        reward_category = report.get('reward_category')
        reward_profile_id = report.get('reward_profile_id')
        self.assertIn(reward_category, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY)
        self.assertEqual(reward_profile_id, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY[reward_category])

        warnings = set(report.get('readiness_warnings', ()))
        self.assertNotIn('no_pack_mobs_on_non_stub_route', warnings)
        self.assertNotIn('no_elite_anchors_on_non_stub_route', warnings)
        self.assertNotIn('no_rare_anchors', warnings)

    def test_global_validators_remain_green(self):
        self.assertEqual(validate_open_world_spawn_profile_placement(), [])
        self.assertEqual(validate_open_world_reward_alignment_metadata(), [])
        self.assertEqual(validate_open_world_route_balance_reports(), [])

    def test_route_composition_and_live_content_remain_bidirectionally_aligned_for_tuned_routes(self):
        for route_id in ('route_frostspine', 'route_old_mine_stub'):
            composition_mob_ids = collect_open_world_route_mob_ids(route_id)
            location_ids = get_world_location_ids_by_route_id(route_id)
            route_live_mob_ids = set()

            for location_id in location_ids:
                location = WORLD_LOCATIONS[location_id]
                route_live_mob_ids.update(str(mob_id) for mob_id in location.get('mobs', []) if str(mob_id).strip())
                route_live_mob_ids.update(
                    str(mob_id) for mob_id in (location.get('world_spawn_profiles') or {}).keys() if str(mob_id).strip()
                )

            self.assertEqual(composition_mob_ids - route_live_mob_ids, set(), msg=route_id)
            self.assertEqual(route_live_mob_ids - composition_mob_ids, set(), msg=route_id)

    def test_reward_alignment_registry_backed_for_tuned_routes(self):
        for route_id in ('route_frostspine', 'route_old_mine_stub'):
            report = build_open_world_route_balance_report(route_id)
            reward_category = report.get('reward_category')
            reward_profile_id = report.get('reward_profile_id')
            self.assertIn(reward_category, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY)
            self.assertEqual(reward_profile_id, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY[reward_category])

    def test_targeting_rollout_remains_frozen_guard(self):
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
        actual_pattern_skills = {
            skill_id
            for skill_id, skill in SKILLS.items()
            if skill.get('target_pattern_id') is not None
        }
        self.assertEqual(actual_pattern_skills, expected_pattern_skills)

    def test_documentation_guard(self):
        doc = Path(__file__).resolve().parent.parent.joinpath('docs', 'OPEN_WORLD_ROUTE_TUNING_PASS2.md')
        self.assertTrue(doc.exists())

        text = doc.read_text(encoding='utf-8').lower()
        self.assertIn('route_frostspine', text)
        self.assertIn('route_old_mine_stub', text)
        self.assertIn('mountain combat route', text)
        self.assertIn('sparse', text)
        self.assertIn('no reward number changes', text)
        self.assertIn('no combat formula changes', text)
        self.assertIn('no new mobs', text)
        self.assertIn('no blanket skill rollout', text)
        self.assertIn('mixed-mob packs remain future work', text)


if __name__ == '__main__':
    unittest.main()
