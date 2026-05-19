import unittest

from game.targeting import (
    FORMATION_LINE_ICONS,
    FORMATION_LINES,
    TARGET_SHAPE_ALL_ENEMIES_IN_SMALL_PACK,
    TARGET_SHAPE_BACK_LINE_SINGLE,
    TARGET_SHAPE_FRONT_LINE_CLUSTER,
    TARGET_SHAPE_SINGLE_ACTIVE_ENEMY,
    TARGET_SHAPES,
    is_valid_formation_line,
    normalize_formation_line,
    select_all_enemies_in_small_pack,
    select_back_line_single,
    select_front_line_cluster,
)


class TargetingFoundationPR2C1Tests(unittest.TestCase):
    def test_formation_constants_exist_and_order_is_stable(self):
        self.assertEqual(FORMATION_LINES, ('front', 'melee', 'ranged', 'support'))

    def test_formation_icons_exist_for_all_lines(self):
        self.assertEqual(set(FORMATION_LINE_ICONS.keys()), set(FORMATION_LINES))

    def test_invalid_formation_inputs_fail_safe(self):
        self.assertEqual(normalize_formation_line(' FRONT '), 'front')
        self.assertIsNone(normalize_formation_line('tank'))
        self.assertFalse(is_valid_formation_line('tank'))

    def test_target_shape_definitions_exist(self):
        self.assertEqual(
            TARGET_SHAPES,
            (
                TARGET_SHAPE_SINGLE_ACTIVE_ENEMY,
                TARGET_SHAPE_ALL_ENEMIES_IN_SMALL_PACK,
                TARGET_SHAPE_FRONT_LINE_CLUSTER,
                TARGET_SHAPE_BACK_LINE_SINGLE,
            ),
        )

    def test_all_enemies_in_small_pack_returns_all_living_and_active_first(self):
        targets = [
            {'unit_id': 'u1', 'dead': False},
            {'unit_id': 'u2', 'dead': True},
            {'unit_id': 'u3', 'dead': False},
        ]
        self.assertEqual(
            [x['unit_id'] for x in select_all_enemies_in_small_pack(targets, active_unit_id='u3')],
            ['u3', 'u1'],
        )

    def test_all_enemies_in_small_pack_dead_active_falls_back_to_stable_living_order(self):
        targets = [
            {'unit_id': 'u1', 'dead': False},
            {'unit_id': 'u2', 'dead': True},
            {'unit_id': 'u3', 'dead': False},
        ]
        self.assertEqual(
            [x['unit_id'] for x in select_all_enemies_in_small_pack(targets, active_unit_id='u2')],
            ['u1', 'u3'],
        )

    def test_front_line_cluster_uses_frontmost_occupied_line_only_and_cap(self):
        targets = [
            {'unit_id': 'u1', 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'u2', 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'u3', 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'u4', 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'u5', 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'u6', 'dead': False, 'formation_line': 'ranged'},
        ]
        self.assertEqual(
            [x['unit_id'] for x in select_front_line_cluster(targets, active_unit_id='u4', cap=4)],
            ['u4', 'u1', 'u2', 'u3'],
        )

    def test_back_line_single_prefers_support_then_backmost_fallback(self):
        support_targets = [
            {'unit_id': 'u1', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'u2', 'dead': False, 'formation_line': 'support'},
            {'unit_id': 'u3', 'dead': False, 'formation_line': 'ranged'},
        ]
        self.assertEqual(
            [x['unit_id'] for x in select_back_line_single(support_targets, active_unit_id='u2')],
            ['u2'],
        )

        fallback_targets = [
            {'unit_id': 'u1', 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'u2', 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'u3', 'dead': False, 'formation_line': 'ranged'},
        ]
        selected = select_back_line_single(fallback_targets, active_unit_id='u3')
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['unit_id'], 'u3')


if __name__ == '__main__':
    unittest.main()
