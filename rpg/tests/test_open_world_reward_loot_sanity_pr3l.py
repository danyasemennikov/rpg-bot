import unittest
from pathlib import Path
from unittest.mock import patch

from game.mobs import MOBS
from game.open_world_pack_balance import get_open_world_pack_archetype_metadata, is_open_world_pack_enabled_mob, validate_open_world_spawn_profile_placement
from game.open_world_pve_tuning import validate_open_world_pve_numeric_tuning_baseline
from game.open_world_readiness_gap_report import build_open_world_readiness_gap_report, validate_open_world_readiness_gap_report
from game.open_world_reward_alignment import validate_open_world_reward_alignment_metadata
from game.open_world_reward_sanity import (
    build_open_world_mob_reward_profile,
    build_route_open_world_reward_sanity_report,
    validate_open_world_reward_loot_sanity,
)
from game.open_world_route_balance_report import validate_open_world_route_balance_reports
from game.skills import SKILLS

NUMERIC_READY = ('route_westwild', 'route_frostspine', 'route_ashen_ruins', 'route_mireveil')
STUBS = ('route_south_coast_stub', 'route_old_mine_stub')


class OpenWorldRewardLootSanityPR3LTests(unittest.TestCase):
    def test_reward_reports_build(self):
        required = {'route_id', 'numeric_tuning_ready', 'is_sparse_or_stub', 'reward_category', 'reward_profile_id', 'solo_mob_ids', 'pack_mob_ids', 'elite_anchor_mob_ids', 'rare_anchor_mob_ids', 'exp_min', 'exp_max', 'gold_min', 'gold_max', 'has_loot_tables', 'route_reward_warnings', 'missing_mob_ids'}
        for route_id in (*NUMERIC_READY, 'route_sunscar', *STUBS):
            report = build_route_open_world_reward_sanity_report(route_id)
            self.assertTrue(report)
            self.assertTrue(required.issubset(report.keys()))


    def test_missing_mob_profiles_are_preserved_and_validated(self):
        fake_report = {
            'route_id': 'route_fake_ready',
            'numeric_tuning_ready': True,
            'is_sparse_or_stub': False,
            'reward_category': 'open_world_normal',
            'reward_profile_id': 'open_world_normal_surface',
            'mob_ids': ('forest_wolf', 'typo_missing_mob'),
            'solo_mob_ids': ('forest_wolf',),
            'pack_mob_ids': (),
            'elite_anchor_mob_ids': (),
            'rare_anchor_mob_ids': (),
            'actionable_warnings': (),
        }
        with patch('game.open_world_reward_sanity.build_route_pve_numeric_tuning_report', return_value=fake_report):
            route_report = build_route_open_world_reward_sanity_report('route_fake_ready')

        self.assertIn('typo_missing_mob', route_report['missing_mob_ids'])
        self.assertIn('missing_mob_reward_profile:typo_missing_mob', route_report['route_reward_warnings'])

        with patch('game.open_world_reward_sanity.build_all_open_world_reward_sanity_reports', return_value=(route_report,)):
            errors = validate_open_world_reward_loot_sanity()

        joined = '\n'.join(errors)
        self.assertIn('missing reward profile', joined)
        self.assertIn('typo_missing_mob', joined)
        self.assertIn('route_fake_ready', joined)

    def test_numeric_ready_reward_shape(self):
        for route_id in NUMERIC_READY:
            report = build_route_open_world_reward_sanity_report(route_id)
            self.assertTrue(report['numeric_tuning_ready'])
            self.assertGreater(len(report['mob_profiles']), 0)
            self.assertGreater(report['exp_min'], 0)
            self.assertGreaterEqual(report['exp_max'], report['exp_min'])
            self.assertGreaterEqual(report['gold_min'], 0)
            self.assertGreaterEqual(report['gold_max'], report['gold_min'])
            self.assertTrue(report['has_loot_tables'])

    def test_per_mob_reward_sanity(self):
        for route_id in NUMERIC_READY:
            report = build_route_open_world_reward_sanity_report(route_id)
            for mob_id in report['solo_mob_ids'] + report['pack_mob_ids'] + report['elite_anchor_mob_ids']:
                profile = build_open_world_mob_reward_profile(mob_id)
                self.assertGreater(profile['exp_reward'], 0)
                self.assertGreaterEqual(profile['gold_min'], 0)
                self.assertGreaterEqual(profile['gold_max'], profile['gold_min'])
                self.assertIsInstance(profile['loot_table'], (list, tuple))
                for entry in profile['loot_table']:
                    self.assertIsInstance(entry, (list, tuple))
                    self.assertEqual(len(entry), 2)
                    item_id, chance = entry
                    self.assertTrue(isinstance(item_id, str) and item_id.strip())
                    self.assertTrue(0 < chance <= 1)

    def test_elite_reward_sanity(self):
        for route_id in NUMERIC_READY:
            report = build_route_open_world_reward_sanity_report(route_id)
            elite = [build_open_world_mob_reward_profile(m) for m in report['elite_anchor_mob_ids']]
            solo = [build_open_world_mob_reward_profile(m) for m in report['solo_mob_ids']]
            self.assertGreaterEqual(min(p['exp_reward'] for p in elite), min(p['exp_reward'] for p in solo))
            self.assertTrue(max(p['exp_reward'] for p in elite) >= max(p['exp_reward'] for p in solo) or max(p['gold_max'] for p in elite) >= max(p['gold_max'] for p in solo))

    def test_pack_reward_sanity(self):
        for route_id in NUMERIC_READY:
            report = build_route_open_world_reward_sanity_report(route_id)
            for mob_id in report['pack_mob_ids']:
                profile = build_open_world_mob_reward_profile(mob_id)
                self.assertGreater(profile['exp_reward'], 0)
                self.assertGreaterEqual(profile['gold_max'], profile['gold_min'])
                self.assertEqual(profile['invalid_loot_entries'], ())
                self.assertTrue(is_open_world_pack_enabled_mob(mob_id))
                self.assertTrue(get_open_world_pack_archetype_metadata(mob_id))

    def test_explicit_reward_changes(self):
        self.assertEqual(MOBS['mountain_stone_golem']['exp_reward'], 110)
        self.assertEqual(MOBS['mountain_stone_golem']['gold_min'], 5)
        self.assertEqual(MOBS['mountain_stone_golem']['gold_max'], 14)
        self.assertEqual(MOBS['drowned']['exp_reward'], 105)
        self.assertEqual(MOBS['drowned']['gold_min'], 5)
        self.assertEqual(MOBS['drowned']['gold_max'], 14)

    def test_sunscar_excluded(self):
        report = build_route_open_world_reward_sanity_report('route_sunscar')
        readiness = build_open_world_readiness_gap_report()
        self.assertTrue(report)
        self.assertFalse(report['numeric_tuning_ready'])
        self.assertIn({'route_id': 'route_sunscar', 'warning_id': 'no_pack_mobs_on_non_stub_route'}, list(readiness['actionable_gaps']))

    def test_stubs(self):
        for route_id in STUBS:
            report = build_route_open_world_reward_sanity_report(route_id)
            self.assertTrue(report)
            self.assertTrue(report['is_sparse_or_stub'])

    def test_validators_green(self):
        self.assertEqual(validate_open_world_spawn_profile_placement(), [])
        self.assertEqual(validate_open_world_reward_alignment_metadata(), [])
        self.assertEqual(validate_open_world_route_balance_reports(), [])
        self.assertEqual(validate_open_world_readiness_gap_report(), [])
        self.assertEqual(validate_open_world_pve_numeric_tuning_baseline(), [])
        self.assertEqual(validate_open_world_reward_loot_sanity(), [])

    def test_combat_numeric_frozen(self):
        expected = {
            'white_wolf': {'level': 4, 'hp': 58, 'damage_min': 8, 'damage_max': 13},
            'mountain_stone_golem': {'level': 10, 'hp': 210, 'damage_min': 15, 'damage_max': 24},
            'zombie': {'level': 4, 'hp': 62, 'damage_min': 7, 'damage_max': 12},
            'leech': {'level': 3, 'hp': 38, 'damage_min': 5, 'damage_max': 9},
            'drowned': {'level': 10, 'hp': 138, 'damage_min': 20, 'damage_max': 30},
        }
        for mob_id, values in expected.items():
            for key, value in values.items():
                self.assertEqual(MOBS[mob_id][key], value)

    def test_targeting_rollout_frozen(self):
        expected = {'flame_wave', 'heavy_swing', 'cleave_through', 'arcane_lance', 'hunters_mark', 'aimed_shot', 'piercing_arrow', 'deadeye'}
        actual = {skill_id for skill_id, skill in SKILLS.items() if skill.get('target_pattern_id') is not None}
        self.assertEqual(actual, expected)

    def test_documentation_guard(self):
        doc = Path(__file__).resolve().parent.parent / 'docs' / 'OPEN_WORLD_REWARD_LOOT_SANITY_PASS1.md'
        self.assertTrue(doc.exists())
        text = doc.read_text(encoding='utf-8').lower()
        for token in ('reward', 'loot', 'route_westwild', 'route_frostspine', 'route_ashen_ruins', 'route_mireveil'):
            self.assertIn(token, text)
        self.assertIn('route_sunscar excluded', text)
        self.assertIn('no combat formula changes', text)
        self.assertIn('no mob combat stat changes', text)
        self.assertIn('no reward formula changes', text)
        self.assertIn('no new mobs', text)
        self.assertIn('no spawn probability changes', text)
        self.assertIn('no mixed-mob packs', text)


if __name__ == '__main__':
    unittest.main()
