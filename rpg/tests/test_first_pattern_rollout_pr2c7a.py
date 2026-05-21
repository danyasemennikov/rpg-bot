import unittest
from unittest.mock import patch

from game.combat import (
    process_skill_turn,
    resolve_back_line_single_direct_damage_skill_action,
    resolve_pack_fanout_direct_damage_skill_action,
)
from game.skills import get_skill


class FirstPatternRolloutPR2C7ATests(unittest.TestCase):
    def _player(self):
        return {'strength': 20, 'agility': 10, 'intuition': 20, 'vitality': 10, 'wisdom': 10, 'luck': 10}

    def _mob(self):
        return {'id': 'forest_wolf', 'mob_id': 'forest_wolf', 'defense': 0
        }

    def _skill_result(self, skill_id):
        return {
            'success': True,
            'skill_id': skill_id,
            'log': 'cast',
            'damage': 10,
            'heal': 0,
            'effects': [],
            'target_kind': 'enemy',
            'direct_damage_skill': True,
        }

    def _state(self, enemy_units, active_enemy_unit_id='f1'):
        return {
            'enemy_units': enemy_units,
            'active_enemy_unit_id': active_enemy_unit_id,
            'mob_hp': enemy_units[0]['hp'] if enemy_units else 0,
            'mob_max_hp': enemy_units[0]['max_hp'] if enemy_units else 1,
            'mob_effects': [],
            'mob_dead': False,
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'player_max_mana': 100,
            'log': [],
        }

    def test_metadata_rollout_and_balance_fields_unchanged(self):
        heavy_swing = get_skill('heavy_swing')
        bow_ult_a = get_skill('bow_ult_a')
        cleave = get_skill('cleave_through')
        deadeye = get_skill('deadeye')

        self.assertEqual(heavy_swing.get('target_pattern_id'), 'front_line_cluster')
        self.assertEqual(bow_ult_a.get('target_pattern_id'), 'back_line_single')
        self.assertIsNone(heavy_swing.get('target_shape'))
        self.assertIsNone(bow_ult_a.get('target_shape'))

        self.assertIsNone(cleave.get('target_pattern_id'))
        self.assertIsNone(deadeye.get('target_pattern_id'))

        self.assertEqual(heavy_swing.get('mana_cost'), 18)
        self.assertEqual(heavy_swing.get('cooldown'), 3)
        self.assertEqual(heavy_swing.get('scale_mult'), 1.8)
        self.assertEqual(heavy_swing.get('base_value'), 148)
        self.assertEqual(heavy_swing.get('level_bonus'), 0.10)

        self.assertEqual(bow_ult_a.get('mana_cost'), 60)
        self.assertEqual(bow_ult_a.get('cooldown'), 7)
        self.assertEqual(bow_ult_a.get('scale_mult'), 3.5)
        self.assertEqual(bow_ult_a.get('base_value'), 350)
        self.assertEqual(bow_ult_a.get('level_bonus'), 0.15)
        self.assertEqual(bow_ult_a.get('ignore_defense'), 1.0)

    def test_heavy_swing_front_line_cluster_runtime_and_cap(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'r1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'ranged'},
            {'unit_id': 's1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
        ], active_enemy_unit_id='m1')

        with patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            skill_result = self._skill_result('heavy_swing')
            result = resolve_pack_fanout_direct_damage_skill_action(self._player(), self._mob(), battle_state, skill_result, lang='en')

        self.assertTrue(result['handled'])
        self.assertEqual([x['unit_id'] for x in skill_result['direct_damage_result']['per_target']], ['f1', 'f2'])
        self.assertTrue(skill_result['direct_damage_result']['fanout'])
        self.assertEqual(skill_result['direct_damage_result']['target_pattern_id'], 'front_line_cluster')
        self.assertEqual(skill_result['direct_damage_result']['targets_total'], 2)

        cap_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f3', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f4', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f5', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
        ], active_enemy_unit_id='f5')
        with patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            cap_result = self._skill_result('heavy_swing')
            resolve_pack_fanout_direct_damage_skill_action(self._player(), self._mob(), cap_state, cap_result, lang='en')
        self.assertEqual(len(cap_result['direct_damage_result']['per_target']), 4)

    def test_heavy_swing_uses_next_frontmost_line_if_front_empty(self):
        battle_state = self._state([
            {'unit_id': 'm1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'm2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'r1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'ranged'},
        ], active_enemy_unit_id='r1')

        with patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            skill_result = self._skill_result('heavy_swing')
            resolve_pack_fanout_direct_damage_skill_action(self._player(), self._mob(), battle_state, skill_result, lang='en')

        self.assertEqual([x['unit_id'] for x in skill_result['direct_damage_result']['per_target']], ['m1', 'm2'])

    def test_bow_ult_a_back_line_single_selection_and_projection_restore(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'r1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'ranged'},
            {'unit_id': 's1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
        ], active_enemy_unit_id='f1')

        with patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            skill_result = self._skill_result('bow_ult_a')
            result = resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), battle_state, skill_result, lang='en')

        self.assertTrue(result['handled'])
        self.assertEqual(result['selected_unit_id'], 's1')
        self.assertEqual(skill_result['direct_damage_result']['target_pattern_id'], 'back_line_single')
        self.assertTrue(skill_result['direct_damage_result']['shape_redirect'])
        self.assertEqual(skill_result['direct_damage_result']['selected_unit_id'], 's1')
        self.assertEqual(sum(1 for unit in battle_state['enemy_units'] if unit['hp'] < unit['max_hp']), 1)
        self.assertEqual(battle_state.get('active_enemy_unit_id'), 'f1')

        no_support_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'r1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'ranged'},
        ], active_enemy_unit_id='f1')
        with patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            ranged_result = self._skill_result('bow_ult_a')
            result = resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), no_support_state, ranged_result, lang='en')
        self.assertEqual(result['selected_unit_id'], 'r1')

        only_front_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
        ], active_enemy_unit_id='f1')
        with patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            front_result = self._skill_result('bow_ult_a')
            result = resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), only_front_state, front_result, lang='en')
        self.assertEqual(result['selected_unit_id'], 'f1')
        self.assertEqual(sum(1 for unit in only_front_state['enemy_units'] if unit['hp'] < unit['max_hp']), 1)

    def test_process_skill_turn_heavy_swing_routes_through_front_line_cluster(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
        ], active_enemy_unit_id='m1')

        skill_result = self._skill_result('heavy_swing')
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            result = process_skill_turn('heavy_swing', self._player(), self._mob(), battle_state, user_id=1, lang='en', include_enemy_response=False)

        self.assertTrue(result['success'])
        self.assertEqual(skill_result['direct_damage_result']['target_pattern_id'], 'front_line_cluster')
        self.assertEqual([x['unit_id'] for x in skill_result['direct_damage_result']['per_target']], ['f1', 'f2'])

    def test_process_skill_turn_bow_ult_a_routes_through_back_line_single(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'r1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'ranged'},
            {'unit_id': 's1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
        ], active_enemy_unit_id='f1')

        skill_result = self._skill_result('bow_ult_a')
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            result = process_skill_turn('bow_ult_a', self._player(), self._mob(), battle_state, user_id=1, lang='en', include_enemy_response=False)

        self.assertTrue(result['success'])
        self.assertEqual(skill_result['direct_damage_result']['target_pattern_id'], 'back_line_single')
        self.assertTrue(skill_result['direct_damage_result']['shape_redirect'])
        self.assertEqual(skill_result['direct_damage_result']['selected_unit_id'], 's1')


if __name__ == '__main__':
    unittest.main()
