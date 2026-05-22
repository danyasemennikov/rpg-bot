import unittest
from pathlib import Path

from game.skills import SKILLS, get_skill
from game.targeting import TARGET_PATTERNS


class TargetingChapterStabilizationPR2C11Tests(unittest.TestCase):
    def test_live_rollout_metadata_lock(self):
        expected = {
            'flame_wave': {'target_pattern_id': 'all_enemies_in_small_pack', 'target_local_resolution': None, 'target_shape': None},
            'heavy_swing': {'target_pattern_id': 'front_line_cluster', 'target_local_resolution': None, 'target_shape': None},
            'cleave_through': {'target_pattern_id': 'front_line_cluster', 'target_local_resolution': True, 'target_shape': None},
            'arcane_lance': {'target_pattern_id': 'back_line_single', 'target_local_resolution': None, 'target_shape': None},
            'hunters_mark': {'target_pattern_id': 'back_line_single', 'target_local_resolution': None, 'target_shape': None},
            'aimed_shot': {'target_pattern_id': 'back_line_single', 'target_local_resolution': True, 'target_shape': None},
            'piercing_arrow': {'target_pattern_id': 'back_line_single', 'target_local_resolution': True, 'target_shape': None},
            'deadeye': {'target_pattern_id': 'back_line_single', 'target_local_resolution': True, 'target_shape': None},
        }

        for skill_id, locked in expected.items():
            skill = get_skill(skill_id)
            self.assertIsNotNone(skill, f'missing expected live skill: {skill_id}')
            self.assertEqual(skill.get('target_pattern_id'), locked['target_pattern_id'], skill_id)
            self.assertIs(skill.get('target_local_resolution'), locked['target_local_resolution'], skill_id)
            self.assertIsNone(skill.get('target_shape'), skill_id)

    def test_target_pattern_rollout_set_is_globally_locked(self):
        actual_pattern_skills = {
            skill_id
            for skill_id, skill in SKILLS.items()
            if skill.get('target_pattern_id') is not None
        }
        self.assertEqual(
            actual_pattern_skills,
            {
                'flame_wave',
                'heavy_swing',
                'cleave_through',
                'arcane_lance',
                'hunters_mark',
                'aimed_shot',
                'piercing_arrow',
                'deadeye',
            },
        )

    def test_target_local_resolution_set_is_globally_locked(self):
        actual_target_local_skills = {
            skill_id
            for skill_id, skill in SKILLS.items()
            if skill.get('target_local_resolution') is not None
        }
        approved_target_local_skills = {
            'cleave_through',
            'aimed_shot',
            'piercing_arrow',
            'deadeye',
        }
        self.assertEqual(actual_target_local_skills, approved_target_local_skills)
        for skill_id in approved_target_local_skills:
            self.assertIs(get_skill(skill_id).get('target_local_resolution'), True, skill_id)

    def test_target_shape_is_not_used_by_current_skill_metadata(self):
        skills_with_shape = [skill_id for skill_id, skill in SKILLS.items() if skill.get('target_shape') is not None]
        self.assertEqual(skills_with_shape, [], f'target_shape should remain compatibility-only, found: {skills_with_shape}')

    def test_target_pattern_registry_canonical_invariants(self):
        expected_modes = {
            'ordinary_single_enemy': 'single',
            'all_enemies_in_small_pack': 'fanout',
            'front_line_cluster': 'fanout',
            'back_line_single': 'single_redirect',
            'two_front_lines_2x2': 'fanout',
            'ranged_line_single': 'single_redirect',
        }

        self.assertTrue(set(expected_modes.keys()).issubset(set(TARGET_PATTERNS.keys())))
        for pattern_id, execution_mode in expected_modes.items():
            self.assertEqual(TARGET_PATTERNS[pattern_id].get('execution_mode'), execution_mode, pattern_id)

    def test_target_pattern_doc_mentions_chapter_lock_policy_keywords(self):
        doc_text = Path(__file__).resolve().parent.parent.joinpath('docs', 'TARGET_PATTERN_SYSTEM_V1.md').read_text(encoding='utf-8')
        normalized = doc_text.lower()

        self.assertIn('target_pattern_id', doc_text)
        self.assertIn('target_local_resolution', doc_text)
        self.assertIn('Current rollout', doc_text)
        self.assertIn('Rollout policy', doc_text)
        self.assertIn('target_shape', doc_text)
        self.assertIn('compatibility', normalized)
        self.assertTrue(('no blanket rollout' in normalized) or ('no mass rollout' in normalized))


if __name__ == '__main__':
    unittest.main()
