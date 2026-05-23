import unittest
from pathlib import Path

from game.open_world_pack_balance import (
    get_open_world_pack_archetype_metadata,
    is_open_world_pack_enabled_mob,
    validate_open_world_spawn_profile_placement,
)
from game.open_world_pve_tuning import (
    build_open_world_pve_numeric_profile,
    build_route_pve_numeric_tuning_report,
    validate_open_world_pve_numeric_tuning_baseline,
)
from game.open_world_readiness_gap_report import build_open_world_readiness_gap_report, validate_open_world_readiness_gap_report
from game.open_world_reward_alignment import validate_open_world_reward_alignment_metadata
from game.open_world_route_balance_report import validate_open_world_route_balance_reports
from game.mobs import MOBS
from game.skills import SKILLS


TUNED_ROUTES = ('route_westwild', 'route_frostspine', 'route_ashen_ruins', 'route_mireveil')
STUB_ROUTES = ('route_south_coast_stub', 'route_old_mine_stub')


class OpenWorldPveNumericTuningPass1PR3KTests(unittest.TestCase):
    def test_numeric_ready_gate_stays_correct(self):
        readiness = build_open_world_readiness_gap_report()
        numeric_ready = set(readiness['numeric_tuning_ready_routes'])
        self.assertTrue(set(TUNED_ROUTES).issubset(numeric_ready))
        self.assertNotIn('route_sunscar', numeric_ready)

    def test_tuned_routes_have_coherent_numeric_reports(self):
        for route_id in TUNED_ROUTES:
            report = build_route_pve_numeric_tuning_report(route_id)
            self.assertTrue(report)
            self.assertTrue(report['numeric_tuning_ready'])
            self.assertLessEqual(report['hp_min'], report['hp_max'])
            self.assertLessEqual(report['damage_min'], report['damage_max'])
            self.assertLessEqual(report['level_min'], report['level_max'])
            self.assertGreater(report['solo_count'], 0)
            self.assertGreater(report['pack_mob_count'], 0)
            self.assertGreater(report['elite_anchor_count'], 0)
            self.assertEqual(report['actionable_warnings'], ())

    def test_per_mob_numeric_sanity(self):
        for route_id in TUNED_ROUTES:
            report = build_route_pve_numeric_tuning_report(route_id)
            for mob_id in report['mob_ids']:
                profile = build_open_world_pve_numeric_profile(mob_id)
                self.assertTrue(profile)
                self.assertGreater(profile['level'], 0)
                self.assertGreater(profile['hp'], 0)
                self.assertGreater(profile['damage_min'], 0)
                self.assertGreater(profile['damage_max'], 0)
                self.assertLessEqual(profile['damage_min'], profile['damage_max'])

    def test_elite_anchor_sanity(self):
        for route_id in TUNED_ROUTES:
            report = build_route_pve_numeric_tuning_report(route_id)
            elite_hp_max = max(build_open_world_pve_numeric_profile(m)['hp'] for m in report['elite_anchor_mob_ids'])
            elite_level_max = max(build_open_world_pve_numeric_profile(m)['level'] for m in report['elite_anchor_mob_ids'])
            solo_hp_max = max(build_open_world_pve_numeric_profile(m)['hp'] for m in report['solo_mob_ids'])
            solo_level_max = max(build_open_world_pve_numeric_profile(m)['level'] for m in report['solo_mob_ids'])
            self.assertTrue(elite_hp_max >= solo_hp_max or elite_level_max >= solo_level_max)

    def test_pack_mob_sanity(self):
        for route_id in TUNED_ROUTES:
            report = build_route_pve_numeric_tuning_report(route_id)
            for mob_id in report['pack_mob_ids']:
                profile = build_open_world_pve_numeric_profile(mob_id)
                self.assertGreater(profile['hp'], 0)
                self.assertGreater(profile['damage_min'], 0)
                self.assertGreater(profile['damage_max'], 0)
                self.assertTrue(is_open_world_pack_enabled_mob(mob_id))
                self.assertTrue(get_open_world_pack_archetype_metadata(mob_id))

    def test_westwild_remains_starter_safe(self):
        reports = {route_id: build_route_pve_numeric_tuning_report(route_id) for route_id in TUNED_ROUTES}
        westwild = reports['route_westwild']
        self.assertEqual(westwild['level_min'], min(r['level_min'] for r in reports.values()))
        self.assertTrue(any(westwild['hp_max'] <= report['hp_max'] for rid, report in reports.items() if rid != 'route_westwild'))

    def test_route_progression_sanity(self):
        westwild = build_route_pve_numeric_tuning_report('route_westwild')
        for route_id in ('route_frostspine', 'route_ashen_ruins', 'route_mireveil'):
            report = build_route_pve_numeric_tuning_report(route_id)
            self.assertTrue(report['level_max'] >= westwild['level_max'] or report['hp_max'] >= westwild['hp_max'])

    def test_sunscar_exclusion_remains_truthful(self):
        report = build_route_pve_numeric_tuning_report('route_sunscar')
        self.assertFalse(report['numeric_tuning_ready'])
        self.assertIn('no_pack_mobs_on_non_stub_route', report['actionable_warnings'])

    def test_stubs_remain_smoke_sanity_only(self):
        for route_id in STUB_ROUTES:
            report = build_route_pve_numeric_tuning_report(route_id)
            self.assertTrue(report)
            self.assertTrue(report['is_sparse_or_stub'])

    def test_validators_stay_green(self):
        self.assertEqual(validate_open_world_spawn_profile_placement(), [])
        self.assertEqual(validate_open_world_reward_alignment_metadata(), [])
        self.assertEqual(validate_open_world_route_balance_reports(), [])
        self.assertEqual(validate_open_world_readiness_gap_report(), [])
        self.assertEqual(validate_open_world_pve_numeric_tuning_baseline(), [])

    def test_targeting_rollout_remains_frozen(self):
        expected = {
            'flame_wave', 'heavy_swing', 'cleave_through', 'arcane_lance',
            'hunters_mark', 'aimed_shot', 'piercing_arrow', 'deadeye',
        }
        actual = {skill_id for skill_id, skill in SKILLS.items() if skill.get('target_pattern_id') is not None}
        self.assertEqual(actual, expected)


    def test_changed_mobs_keep_combat_tuning_and_preserve_old_rewards(self):
        expected = {
            'white_wolf': {'level': 4, 'hp': 58, 'damage_min': 8, 'damage_max': 13, 'exp_reward': 30, 'gold_min': 1, 'gold_max': 6},
            'mountain_stone_golem': {'level': 10, 'hp': 210, 'damage_min': 15, 'damage_max': 24, 'exp_reward': 60, 'gold_min': 3, 'gold_max': 9},
            'zombie': {'level': 4, 'hp': 62, 'damage_min': 7, 'damage_max': 12, 'exp_reward': 30, 'gold_min': 1, 'gold_max': 6},
            'leech': {'level': 3, 'hp': 38, 'damage_min': 5, 'damage_max': 9, 'exp_reward': 20, 'gold_min': 1, 'gold_max': 5},
            'drowned': {'level': 10, 'hp': 138, 'damage_min': 20, 'damage_max': 30, 'exp_reward': 70, 'gold_min': 3, 'gold_max': 10},
        }
        for mob_id, expected_values in expected.items():
            mob = MOBS[mob_id]
            for key, value in expected_values.items():
                self.assertEqual(mob[key], value, f"{mob_id} {key}")

    def test_documentation_guard(self):
        doc = Path(__file__).resolve().parent.parent / 'docs' / 'OPEN_WORLD_PVE_NUMERIC_TUNING_PASS1.md'
        self.assertTrue(doc.exists())
        text = doc.read_text(encoding='utf-8').lower()
        for token in ('route_westwild', 'route_frostspine', 'route_ashen_ruins', 'route_mireveil'):
            self.assertIn(token, text)
        self.assertTrue('route_sunscar' in text and 'excluded' in text)
        self.assertIn('no combat formula changes', text)
        self.assertIn('no reward number changes', text)
        self.assertIn('no spawn probability changes', text)
        self.assertIn('no new mobs', text)
        self.assertIn('no mixed-mob packs', text)


if __name__ == '__main__':
    unittest.main()
