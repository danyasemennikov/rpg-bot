import unittest
from pathlib import Path

from game.open_world_pack_balance import (
    ALLOWED_OPEN_WORLD_THREAT_BANDS,
    get_open_world_route_encounter_compositions,
    get_pack_enabled_mob_ids,
)
from game.open_world_reward_alignment import (
    ALLOWED_OPEN_WORLD_REWARD_CATEGORIES,
    OPEN_WORLD_SPAWN_PROFILE_TO_REWARD_CATEGORY,
    OPEN_WORLD_THREAT_BAND_TO_REWARD_PROFILE,
    get_open_world_pack_reward_alignment,
    get_open_world_reward_category_for_spawn_profile,
    get_open_world_reward_profile_for_threat_band,
    validate_open_world_reward_alignment_metadata,
)
from game.pve_live import WORLD_SPAWN_PROFILES, WORLD_SPAWN_PROFILE_COMBAT_MODIFIERS
from game.reward_policies import REWARD_FAMILIES_BY_SOURCE
from game.skills import SKILLS


class OpenWorldRewardThreatAlignmentPR3CTests(unittest.TestCase):
    def test_threat_band_alignment_coverage(self):
        self.assertEqual(validate_open_world_reward_alignment_metadata(), [])
        for threat_band in ALLOWED_OPEN_WORLD_THREAT_BANDS:
            profile = get_open_world_reward_profile_for_threat_band(threat_band)
            self.assertTrue(profile)
            self.assertIn(profile.get('reward_category'), ALLOWED_OPEN_WORLD_REWARD_CATEGORIES)
            self.assertIn(profile.get('reward_category'), REWARD_FAMILIES_BY_SOURCE)

        self.assertEqual(set(OPEN_WORLD_THREAT_BAND_TO_REWARD_PROFILE.keys()), set(ALLOWED_OPEN_WORLD_THREAT_BANDS))

    def test_route_composition_threat_bands_align_to_reward_metadata(self):
        for entry in get_open_world_route_encounter_compositions():
            band = entry.get('threat_band')
            self.assertIn(band, ALLOWED_OPEN_WORLD_THREAT_BANDS)
            profile = get_open_world_reward_profile_for_threat_band(band)
            self.assertIn(profile.get('reward_category'), REWARD_FAMILIES_BY_SOURCE)
            self.assertTrue(profile.get('reward_profile_id'))

    def test_pack_archetype_reward_alignment(self):
        for mob_id in get_pack_enabled_mob_ids():
            alignment = get_open_world_pack_reward_alignment(mob_id)
            self.assertTrue(alignment)
            self.assertEqual(alignment.get('mob_id'), mob_id)
            self.assertTrue(alignment.get('pack_archetype_id'))
            self.assertIn(alignment.get('threat_band'), ALLOWED_OPEN_WORLD_THREAT_BANDS)
            self.assertIn(alignment.get('reward_category'), REWARD_FAMILIES_BY_SOURCE)
            self.assertLessEqual(alignment.get('expected_size_min', 0), alignment.get('expected_size_max', 0))

    def test_spawn_profile_alignment(self):
        self.assertEqual(set(WORLD_SPAWN_PROFILES), {'normal', 'elite', 'rare'})
        for profile in WORLD_SPAWN_PROFILES:
            category = get_open_world_reward_category_for_spawn_profile(profile)
            self.assertIn(category, REWARD_FAMILIES_BY_SOURCE)

        self.assertEqual(get_open_world_reward_category_for_spawn_profile('normal'), 'open_world_normal')
        self.assertEqual(get_open_world_reward_category_for_spawn_profile('elite'), 'open_world_elite')
        self.assertEqual(get_open_world_reward_category_for_spawn_profile('rare'), 'open_world_rare_spawn')

        self.assertEqual(set(WORLD_SPAWN_PROFILE_COMBAT_MODIFIERS.keys()), set(WORLD_SPAWN_PROFILES))
        self.assertTrue(set(WORLD_SPAWN_PROFILES).issubset(set(OPEN_WORLD_SPAWN_PROFILE_TO_REWARD_CATEGORY.keys())))


    def test_unknown_spawn_profile_falls_back_to_open_world_normal(self):
        self.assertEqual(
            get_open_world_reward_category_for_spawn_profile('unknown_profile'),
            'open_world_normal',
        )
        self.assertEqual(
            get_open_world_reward_category_for_spawn_profile(None),
            'open_world_normal',
        )
        self.assertEqual(
            get_open_world_reward_category_for_spawn_profile(''),
            'open_world_normal',
        )
        self.assertEqual(
            get_open_world_reward_category_for_spawn_profile('  ELITE  '),
            'open_world_elite',
        )

    def test_reward_metadata_structure_guard_exists(self):
        for category in ('open_world_normal', 'open_world_elite', 'open_world_rare_spawn'):
            self.assertIn(category, REWARD_FAMILIES_BY_SOURCE)
            self.assertTrue(REWARD_FAMILIES_BY_SOURCE[category])

    def test_targeting_rollout_stays_frozen_guard(self):
        expected_pattern_skills = {
            'flame_wave', 'heavy_swing', 'cleave_through', 'arcane_lance',
            'hunters_mark', 'aimed_shot', 'piercing_arrow', 'deadeye',
        }
        actual_pattern_skills = {skill_id for skill_id, skill in SKILLS.items() if skill.get('target_pattern_id') is not None}
        self.assertEqual(actual_pattern_skills, expected_pattern_skills)

    def test_documentation_exists_and_mentions_scope_boundaries(self):
        doc_text = Path(__file__).resolve().parent.parent.joinpath('docs', 'OPEN_WORLD_REWARD_THREAT_ALIGNMENT_V1.md').read_text(encoding='utf-8').lower()
        self.assertIn('reward/threat alignment', doc_text)
        self.assertIn('route threat bands', doc_text)
        self.assertIn('pack archetypes', doc_text)
        self.assertIn('no reward number changes', doc_text)
        self.assertIn('no combat formula changes', doc_text)
        self.assertIn('no blanket skill rollout', doc_text)


if __name__ == '__main__':
    unittest.main()
