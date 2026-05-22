import unittest
from pathlib import Path

from game.open_world_pack_balance import (
    get_open_world_pack_archetype_metadata,
    get_open_world_route_encounter_compositions,
    is_open_world_pack_enabled_mob,
    validate_open_world_spawn_profile_placement,
)
from game.open_world_reward_alignment import validate_open_world_reward_alignment_metadata
from game.open_world_reward_pools import OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY
from game.open_world_route_balance_report import (
    build_all_open_world_route_balance_reports,
    build_open_world_route_balance_report,
    validate_open_world_route_balance_reports,
)
from game.skills import SKILLS


class OpenWorldRouteBalanceReadinessPR3ETests(unittest.TestCase):
    def test_build_report_for_every_route_composition(self):
        required_keys = {
            'route_id', 'threat_band', 'content_tier_min', 'content_tier_max', 'location_ids', 'location_count',
            'solo_mob_ids', 'pack_mob_ids', 'elite_anchor_mob_ids', 'rare_anchor_mob_ids', 'solo_count',
            'pack_count', 'elite_anchor_count', 'rare_anchor_count', 'spawn_profiles_present', 'reward_category',
            'reward_profile_id', 'is_sparse_or_stub', 'readiness_warnings',
        }
        for composition in get_open_world_route_encounter_compositions():
            route_id = composition['route_id']
            report = build_open_world_route_balance_report(route_id)
            self.assertEqual(report.get('route_id'), route_id)
            self.assertGreaterEqual(report.get('location_count', 0), 1)
            self.assertTrue(required_keys.issubset(set(report.keys())))

    def test_all_reports_cover_all_route_compositions(self):
        reports = build_all_open_world_route_balance_reports()
        report_route_ids = {report['route_id'] for report in reports}
        composition_route_ids = {entry['route_id'] for entry in get_open_world_route_encounter_compositions()}
        self.assertEqual(report_route_ids, composition_route_ids)

    def test_report_counts_match_lists(self):
        for report in build_all_open_world_route_balance_reports():
            self.assertEqual(report['solo_count'], len(report['solo_mob_ids']))
            self.assertEqual(report['pack_count'], len(report['pack_mob_ids']))
            self.assertEqual(report['elite_anchor_count'], len(report['elite_anchor_mob_ids']))
            self.assertEqual(report['rare_anchor_count'], len(report['rare_anchor_mob_ids']))

    def test_reward_alignment_registry_backed(self):
        for report in build_all_open_world_route_balance_reports():
            category = report.get('reward_category')
            profile_id = report.get('reward_profile_id')
            self.assertTrue(category)
            self.assertTrue(profile_id)
            self.assertIn(category, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY)
            self.assertEqual(profile_id, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY[category])

    def test_pack_coverage_in_reports(self):
        for report in build_all_open_world_route_balance_reports():
            for mob_id in report.get('pack_mob_ids', ()):
                self.assertTrue(is_open_world_pack_enabled_mob(mob_id))
                self.assertTrue(get_open_world_pack_archetype_metadata(mob_id))

    def test_sparse_stub_routes_marked(self):
        south_coast = build_open_world_route_balance_report('route_south_coast_stub')
        self.assertTrue(south_coast.get('is_sparse_or_stub'))

        old_mine = build_open_world_route_balance_report('route_old_mine_stub')
        if old_mine:
            self.assertTrue(old_mine.get('is_sparse_or_stub'))

        self.assertFalse(build_open_world_route_balance_report('route_westwild').get('is_sparse_or_stub'))

    def test_readiness_warnings_are_diagnostic(self):
        for report in build_all_open_world_route_balance_reports():
            warnings = report.get('readiness_warnings')
            self.assertIsInstance(warnings, (tuple, list))
            self.assertTrue(all(isinstance(item, str) and item.strip() for item in warnings))
        self.assertEqual(validate_open_world_route_balance_reports(), [])

    def test_structural_validator_passes(self):
        self.assertEqual(validate_open_world_route_balance_reports(), [])

    def test_existing_reward_and_placement_validators_remain_green(self):
        self.assertEqual(validate_open_world_spawn_profile_placement(), [])
        self.assertEqual(validate_open_world_reward_alignment_metadata(), [])

    def test_targeting_rollout_stays_frozen_guard(self):
        expected_pattern_skills = {
            'flame_wave', 'heavy_swing', 'cleave_through', 'arcane_lance',
            'hunters_mark', 'aimed_shot', 'piercing_arrow', 'deadeye',
        }
        actual_pattern_skills = {skill_id for skill_id, skill in SKILLS.items() if skill.get('target_pattern_id') is not None}
        self.assertEqual(actual_pattern_skills, expected_pattern_skills)

    def test_documentation_guard(self):
        doc = Path(__file__).resolve().parent.parent.joinpath('docs', 'OPEN_WORLD_ROUTE_BALANCE_READINESS_V1.md')
        self.assertTrue(doc.exists())
        text = doc.read_text(encoding='utf-8').lower()
        self.assertIn('route balance', text)
        self.assertIn('readiness', text)
        self.assertIn('warnings', text)
        self.assertIn('no reward number changes', text)
        self.assertIn('no combat formula changes', text)
        self.assertIn('no new mobs', text)
        self.assertIn('mixed-mob packs remain future work', text)


if __name__ == '__main__':
    unittest.main()
