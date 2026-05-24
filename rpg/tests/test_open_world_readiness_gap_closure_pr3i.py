import unittest
from unittest.mock import patch
from pathlib import Path

from game.locations import WORLD_LOCATIONS
from game.open_world_pack_balance import (
    OPEN_WORLD_PACK_ENABLED_MOB_IDS,
    collect_open_world_route_mob_ids,
    get_open_world_pack_archetype_metadata,
    get_open_world_route_composition_by_route_id,
    get_world_location_ids_by_route_id,
    is_open_world_pack_enabled_mob,
    validate_open_world_spawn_profile_placement,
)
from game.open_world_readiness_gap_report import (
    build_open_world_readiness_gap_report,
    validate_open_world_readiness_gap_report,
)
from game.open_world_reward_alignment import validate_open_world_reward_alignment_metadata
from game.open_world_reward_pools import OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY
from game.open_world_route_balance_report import (
    build_all_open_world_route_balance_reports,
    build_open_world_route_balance_report,
    validate_open_world_route_balance_reports,
)
from game.skills import SKILLS


class OpenWorldReadinessGapClosurePR3ITests(unittest.TestCase):
    def test_sunscar_route_specific_pressure_is_tracked(self):
        report = build_open_world_route_balance_report('route_sunscar')
        self.assertEqual(report.get('route_id'), 'route_sunscar')
        self.assertFalse(report.get('is_sparse_or_stub'))
        self.assertEqual(report.get('pack_count', 0), 0)
        warnings = set(report.get('readiness_warnings', ()))
        self.assertNotIn('no_pack_mobs_on_non_stub_route', warnings)
        self.assertEqual(report.get('pressure_profile_id'), 'solo_elite_precision_skirmish')

    def test_sunscar_scorpion_runtime_pack_pressure_not_possible_with_normal_one(self):
        selected_mob_id = 'scorpion'
        composition = get_open_world_route_composition_by_route_id('route_sunscar')
        self.assertNotIn(selected_mob_id, composition.get('pack_mob_ids', ()))
        self.assertFalse(is_open_world_pack_enabled_mob(selected_mob_id))
        self.assertEqual(get_open_world_pack_archetype_metadata(selected_mob_id), {})

        location_ids = get_world_location_ids_by_route_id('route_sunscar')
        found = 0
        for location_id in location_ids:
            profiles = (WORLD_LOCATIONS[location_id].get('world_spawn_profiles') or {}).get(selected_mob_id) or {}
            if 'normal' in profiles:
                found += 1
                self.assertEqual(int(profiles['normal']), 1)
        self.assertGreater(found, 0)

    def test_pack_enabled_set_exact_lock(self):
        self.assertEqual(
            OPEN_WORLD_PACK_ENABLED_MOB_IDS,
            frozenset({'forest_wolf', 'white_wolf', 'zombie', 'leech'}),
        )

    def test_consolidated_readiness_gap_report_shape_and_policy(self):
        report = build_open_world_readiness_gap_report()
        required_keys = {
            'routes_total', 'major_routes', 'sparse_stub_routes', 'routes_with_warnings',
            'remaining_warnings_by_route', 'actionable_gaps', 'deferred_gaps', 'numeric_tuning_ready_routes',
        }
        self.assertTrue(required_keys.issubset(set(report.keys())))

        self.assertIn('route_south_coast_stub', report['sparse_stub_routes'])
        self.assertIn('route_old_mine_stub', report['sparse_stub_routes'])
        self.assertIn('route_sunscar', report['major_routes'])

        actionable_gaps = report['actionable_gaps']
        self.assertFalse(any(gap['route_id'] == 'route_sunscar' for gap in actionable_gaps))

        deferred_gaps = report['deferred_gaps']
        self.assertTrue(any(gap['warning_id'] == 'no_rare_anchors' for gap in deferred_gaps))
        self.assertFalse(any(gap['warning_id'] == 'no_rare_anchors' for gap in actionable_gaps))

        self.assertIn('route_sunscar', report['numeric_tuning_ready_routes'])

    def test_validators_and_alignment_remain_green(self):
        self.assertEqual(validate_open_world_spawn_profile_placement(), [])
        self.assertEqual(validate_open_world_reward_alignment_metadata(), [])
        self.assertEqual(validate_open_world_route_balance_reports(), [])
        self.assertEqual(validate_open_world_readiness_gap_report(), [])

        for route_report in build_all_open_world_route_balance_reports():
            route_id = route_report['route_id']
            composition_mob_ids = collect_open_world_route_mob_ids(route_id)
            location_ids = get_world_location_ids_by_route_id(route_id)
            route_live_mob_ids = set()
            for location_id in location_ids:
                location = WORLD_LOCATIONS[location_id]
                route_live_mob_ids.update(str(mob_id) for mob_id in location.get('mobs', []) if str(mob_id).strip())
                route_live_mob_ids.update(str(mob_id) for mob_id in (location.get('world_spawn_profiles') or {}).keys() if str(mob_id).strip())

            self.assertEqual(composition_mob_ids - route_live_mob_ids, set(), msg=route_id)
            self.assertEqual(route_live_mob_ids - composition_mob_ids, set(), msg=route_id)

            reward_category = route_report.get('reward_category')
            reward_profile_id = route_report.get('reward_profile_id')
            self.assertIn(reward_category, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY)
            self.assertEqual(reward_profile_id, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY[reward_category])

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


    def test_unknown_warning_ids_are_actionable_and_validation_errors(self):
        fake_reports = (
            {
                'route_id': 'route_fake_major',
                'is_sparse_or_stub': False,
                'readiness_warnings': ('brand_new_warning',),
            },
        )
        with patch('game.open_world_readiness_gap_report.build_all_open_world_route_balance_reports', return_value=fake_reports):
            report = build_open_world_readiness_gap_report()
            self.assertTrue(any(
                gap['route_id'] == 'route_fake_major' and gap['warning_id'] == 'brand_new_warning'
                for gap in report['actionable_gaps']
            ))
            self.assertFalse(any(
                gap['route_id'] == 'route_fake_major' and gap['warning_id'] == 'brand_new_warning'
                for gap in report['deferred_gaps']
            ))
            errors = validate_open_world_readiness_gap_report()
            self.assertTrue(any('unknown readiness warning id' in err for err in errors))
            self.assertTrue(any('brand_new_warning' in err for err in errors))
    def test_documentation_guard(self):
        doc = Path(__file__).resolve().parent.parent.joinpath('docs', 'OPEN_WORLD_READINESS_GAP_CLOSURE_PR3I.md')
        self.assertTrue(doc.exists())
        text = doc.read_text(encoding='utf-8').lower()
        self.assertIn('route_sunscar', text)
        self.assertIn('pack pressure', text)
        self.assertIn('readiness gaps', text)
        self.assertIn('no reward number changes', text)
        self.assertIn('no combat formula changes', text)
        self.assertIn('no route topology changes', text)
        self.assertIn('no spawn probability changes', text)
        self.assertIn('no mixed-mob packs', text)
        self.assertIn('no blanket skill rollout', text)


if __name__ == '__main__':
    unittest.main()
