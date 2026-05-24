import unittest
from pathlib import Path
from unittest.mock import patch

from game.open_world_pack_balance import validate_open_world_spawn_profile_placement
from game.open_world_pve_tuning import (
    build_all_open_world_pve_numeric_tuning_reports,
    build_open_world_pve_numeric_profile,
    build_route_pve_numeric_tuning_report,
    validate_open_world_pve_numeric_tuning_baseline,
)
from game.open_world_readiness_gap_report import build_open_world_readiness_gap_report, validate_open_world_readiness_gap_report
from game.open_world_reward_alignment import validate_open_world_reward_alignment_metadata
from game.open_world_route_balance_report import validate_open_world_route_balance_reports
from game.skills import SKILLS


class OpenWorldPveNumericTuningBaselinePR3JTests(unittest.TestCase):
    def test_numeric_ready_route_gate(self):
        readiness = build_open_world_readiness_gap_report()
        numeric_ready = set(readiness['numeric_tuning_ready_routes'])
        self.assertTrue({'route_westwild', 'route_frostspine', 'route_ashen_ruins', 'route_mireveil'}.issubset(numeric_ready))
        self.assertIn('route_sunscar', numeric_ready)

        sparse = set(readiness['sparse_stub_routes'])
        self.assertIn('route_south_coast_stub', sparse)
        self.assertIn('route_old_mine_stub', sparse)

    def test_numeric_report_builds_for_all_routes(self):
        required_keys = {
            'route_id', 'threat_band', 'content_tier_min', 'content_tier_max', 'is_sparse_or_stub',
            'numeric_tuning_ready', 'mob_ids', 'solo_mob_ids', 'pack_mob_ids', 'elite_anchor_mob_ids',
            'hp_min', 'hp_max', 'damage_min', 'damage_max', 'level_min', 'level_max', 'warnings',
        }
        for report in build_all_open_world_pve_numeric_tuning_reports():
            self.assertTrue(required_keys.issubset(set(report.keys())))

    def test_numeric_ready_routes_have_required_content_shape(self):
        for route_id in ('route_westwild', 'route_frostspine', 'route_ashen_ruins', 'route_mireveil'):
            report = build_route_pve_numeric_tuning_report(route_id)
            self.assertEqual(report.get('route_id'), route_id)
            self.assertFalse(report.get('is_sparse_or_stub'))
            self.assertTrue(report.get('numeric_tuning_ready'))
            self.assertEqual(report.get('actionable_warnings'), ())
            self.assertGreater(report.get('solo_count', 0), 0)
            self.assertGreater(report.get('pack_mob_count', 0), 0)
            self.assertGreater(report.get('elite_anchor_count', 0), 0)
            self.assertTrue(report.get('pack_eligibility_coverage_complete'))
            self.assertTrue(report.get('pack_archetype_coverage_complete'))
            self.assertTrue(str(report.get('reward_category') or '').strip())
            self.assertTrue(str(report.get('reward_profile_id') or '').strip())

    def test_sunscar_is_ready_via_route_specific_pressure(self):
        readiness = build_open_world_readiness_gap_report()
        self.assertFalse(any(gap['route_id'] == 'route_sunscar' for gap in readiness['actionable_gaps']))
        report = build_route_pve_numeric_tuning_report('route_sunscar')
        self.assertFalse(report.get('is_sparse_or_stub'))
        self.assertTrue(report.get('numeric_tuning_ready'))

    def test_numeric_profile_sanity(self):
        readiness = build_open_world_readiness_gap_report()
        for route_id in readiness['numeric_tuning_ready_routes']:
            report = build_route_pve_numeric_tuning_report(route_id)
            for mob_id in report.get('mob_ids', ()):
                profile = build_open_world_pve_numeric_profile(mob_id)
                self.assertTrue(profile)
                for key in ('hp', 'level', 'damage_min', 'damage_max'):
                    value = profile.get(key)
                    if value is not None:
                        self.assertGreater(value, 0)

            for min_key, max_key in (('hp_min', 'hp_max'), ('damage_min', 'damage_max'), ('level_min', 'level_max')):
                min_val = report.get(min_key)
                max_val = report.get(max_key)
                if min_val is not None and max_val is not None:
                    self.assertLessEqual(min_val, max_val)

    def test_per_mob_invalid_damage_range_is_reported(self):
        route_id = 'route_westwild'
        report = build_route_pve_numeric_tuning_report(route_id)
        target_mob_id = report['mob_ids'][0]

        original_builder = build_open_world_pve_numeric_profile

        def _fake_profile(mob_id):
            profile = original_builder(mob_id)
            if mob_id == target_mob_id:
                profile = dict(profile)
                profile['damage_min'] = 9
                profile['damage_max'] = 3
            return profile

        with patch('game.open_world_pve_tuning.build_open_world_pve_numeric_profile', side_effect=_fake_profile):
            errors = validate_open_world_pve_numeric_tuning_baseline()

        self.assertTrue(any('invalid damage range' in err and route_id in err and target_mob_id in err for err in errors))

    def test_numeric_profile_shape_for_known_mob(self):
        profile = build_open_world_pve_numeric_profile('forest_wolf')
        self.assertEqual(profile.get('mob_id'), 'forest_wolf')
        for key in ('level', 'hp', 'damage_min', 'damage_max'):
            self.assertIn(key, profile)

    def test_existing_validators_remain_green(self):
        self.assertEqual(validate_open_world_spawn_profile_placement(), [])
        self.assertEqual(validate_open_world_reward_alignment_metadata(), [])
        self.assertEqual(validate_open_world_route_balance_reports(), [])
        self.assertEqual(validate_open_world_readiness_gap_report(), [])
        self.assertEqual(validate_open_world_pve_numeric_tuning_baseline(), [])

    def test_targeting_rollout_remains_frozen(self):
        expected_pattern_skills = {
            'flame_wave', 'heavy_swing', 'cleave_through', 'arcane_lance',
            'hunters_mark', 'aimed_shot', 'piercing_arrow', 'deadeye',
        }
        actual_pattern_skills = {
            skill_id
            for skill_id, skill in SKILLS.items()
            if skill.get('target_pattern_id') is not None
        }
        self.assertEqual(actual_pattern_skills, expected_pattern_skills)

    def test_documentation_guard(self):
        doc = Path(__file__).resolve().parent.parent.joinpath('docs', 'OPEN_WORLD_PVE_NUMERIC_TUNING_BASELINE_V1.md')
        self.assertTrue(doc.exists())
        text = doc.read_text(encoding='utf-8').lower()
        self.assertIn('numeric pve', text)
        self.assertIn('route_westwild', text)
        self.assertIn('route_frostspine', text)
        self.assertIn('route_ashen_ruins', text)
        self.assertIn('route_mireveil', text)
        self.assertTrue('route_sunscar' in text and ('excluded' in text or 'not numeric-ready' in text))
        self.assertIn('no combat formula changes', text)
        self.assertIn('no reward number changes', text)
        self.assertIn('no new mobs', text)
        self.assertIn('no spawn probability changes', text)
        self.assertIn('no mixed-mob packs', text)


if __name__ == '__main__':
    unittest.main()
