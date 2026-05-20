import unittest

from game.targeting import (
    TARGET_PATTERN_ALL_ENEMIES_IN_SMALL_PACK,
    TARGET_PATTERN_BACK_LINE_SINGLE,
    TARGET_PATTERN_FRONT_LINE_CLUSTER,
    TARGET_PATTERN_IDS,
    TARGET_PATTERN_ORDINARY_SINGLE_ENEMY,
    TARGET_PATTERN_RANGED_LINE_SINGLE,
    TARGET_PATTERN_TWO_FRONT_LINES_2X2,
    TARGET_PATTERNS,
    get_target_pattern,
    resolve_target_pattern_id,
    select_all_enemies_in_small_pack,
    select_back_line_single,
    select_front_line_cluster,
    select_targets_for_pattern,
)


class TargetPatternRegistryPR2C5Tests(unittest.TestCase):
    def test_required_pattern_ids_exist(self):
        self.assertEqual(
            TARGET_PATTERN_IDS,
            (
                'ordinary_single_enemy',
                'all_enemies_in_small_pack',
                'front_line_cluster',
                'back_line_single',
                'two_front_lines_2x2',
                'ranged_line_single',
            ),
        )

    def test_target_patterns_contains_all_required_entries(self):
        self.assertTrue(set(TARGET_PATTERN_IDS).issubset(set(TARGET_PATTERNS.keys())))

    def test_pattern_kinds_and_execution_modes_are_valid(self):
        valid_kinds = {'single', 'all_targets', 'line_window'}
        valid_modes = {'single', 'single_redirect', 'fanout'}
        for pattern in TARGET_PATTERNS.values():
            self.assertIn(pattern.get('kind'), valid_kinds)
            self.assertIn(pattern.get('execution_mode'), valid_modes)

    def test_unknown_pattern_lookup_fails_safe(self):
        self.assertIsNone(get_target_pattern('missing_pattern'))

    def test_resolver_priority_and_mappings(self):
        self.assertEqual(
            resolve_target_pattern_id({'target_pattern_id': TARGET_PATTERN_FRONT_LINE_CLUSTER, 'target_shape': 'back_line_single'}),
            TARGET_PATTERN_FRONT_LINE_CLUSTER,
        )
        self.assertEqual(
            resolve_target_pattern_id({'target_shape': 'all_enemies_in_small_pack'}),
            TARGET_PATTERN_ALL_ENEMIES_IN_SMALL_PACK,
        )
        self.assertEqual(
            resolve_target_pattern_id({'target_shape': 'front_line_cluster'}),
            TARGET_PATTERN_FRONT_LINE_CLUSTER,
        )
        self.assertEqual(
            resolve_target_pattern_id({'target_shape': 'back_line_single'}),
            TARGET_PATTERN_BACK_LINE_SINGLE,
        )
        self.assertEqual(resolve_target_pattern_id({}), TARGET_PATTERN_ORDINARY_SINGLE_ENEMY)

    def test_unknown_explicit_pattern_is_safe_and_visible(self):
        self.assertIsNone(resolve_target_pattern_id({'target_pattern_id': 'unknown_pattern'}))

    def test_ordinary_single_enemy_active_then_frontmost(self):
        targets = [
            {'unit_id': 'm1', 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'r1', 'dead': False, 'formation_line': 'ranged'},
        ]
        self.assertEqual(
            [x['unit_id'] for x in select_targets_for_pattern(targets, TARGET_PATTERN_ORDINARY_SINGLE_ENEMY, active_unit_id='r1')],
            ['r1'],
        )
        self.assertEqual(
            [x['unit_id'] for x in select_targets_for_pattern(targets, TARGET_PATTERN_ORDINARY_SINGLE_ENEMY, active_unit_id='x')],
            ['m1'],
        )

    def test_existing_selectors_remain_behavior_compatible(self):
        targets = [
            {'unit_id': 'f1', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f3', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f4', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f5', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'r1', 'dead': False, 'formation_line': 'ranged'},
        ]
        self.assertEqual(
            [x['unit_id'] for x in select_all_enemies_in_small_pack(targets, active_unit_id='r1')],
            [x['unit_id'] for x in select_targets_for_pattern(targets, TARGET_PATTERN_ALL_ENEMIES_IN_SMALL_PACK, active_unit_id='r1')],
        )
        self.assertEqual(
            [x['unit_id'] for x in select_front_line_cluster(targets, active_unit_id='f3')],
            [x['unit_id'] for x in select_targets_for_pattern(targets, TARGET_PATTERN_FRONT_LINE_CLUSTER, active_unit_id='f3')],
        )
        self.assertEqual(
            [x['unit_id'] for x in select_back_line_single(targets, active_unit_id='f3')],
            [x['unit_id'] for x in select_targets_for_pattern(targets, TARGET_PATTERN_BACK_LINE_SINGLE, active_unit_id='f3')],
        )

    def test_legacy_front_line_cluster_cap_compatibility(self):
        targets = [
            {'unit_id': 'f1', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f3', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f4', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f5', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f6', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'dead': False, 'formation_line': 'melee'},
        ]
        self.assertEqual(len(select_front_line_cluster(targets, cap=2)), 2)
        self.assertEqual(len(select_front_line_cluster(targets, cap=4)), 4)
        self.assertEqual(len(select_front_line_cluster(targets, cap=6)), 6)

    def test_registry_front_line_cluster_stays_canonical_cap_of_four(self):
        targets = [
            {'unit_id': 'f1', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f3', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f4', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f5', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f6', 'dead': False, 'formation_line': 'front'},
        ]
        selected = select_targets_for_pattern(targets, TARGET_PATTERN_FRONT_LINE_CLUSTER)
        self.assertEqual(len(selected), 4)

    def test_two_front_lines_2x2_selection(self):
        targets = [
            {'unit_id': 'f1', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f3', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'm2', 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'm3', 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'r1', 'dead': False, 'formation_line': 'ranged'},
        ]
        selected = select_targets_for_pattern(targets, TARGET_PATTERN_TWO_FRONT_LINES_2X2, active_unit_id='m2')
        self.assertEqual([x['unit_id'] for x in selected], ['f1', 'f2', 'm2', 'm1'])

    def test_ranged_line_single_selection_and_empty_case(self):
        targets = [
            {'unit_id': 'f1', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'r1', 'dead': False, 'formation_line': 'ranged'},
            {'unit_id': 'r2', 'dead': False, 'formation_line': 'ranged'},
        ]
        selected = select_targets_for_pattern(targets, TARGET_PATTERN_RANGED_LINE_SINGLE, active_unit_id='r2')
        self.assertEqual([x['unit_id'] for x in selected], ['r2'])
        self.assertEqual(
            select_targets_for_pattern([{'unit_id': 'f1', 'dead': False, 'formation_line': 'front'}], TARGET_PATTERN_RANGED_LINE_SINGLE),
            [],
        )


if __name__ == '__main__':
    unittest.main()
