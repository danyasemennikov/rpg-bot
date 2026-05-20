import unittest
from unittest.mock import patch

from game.combat import (
    process_skill_turn,
    resolve_back_line_single_direct_damage_skill_action,
    resolve_pack_fanout_direct_damage_skill_action,
)
from game.targeting import resolve_target_pattern_id


class PatternRuntimeMigrationPR2C6Tests(unittest.TestCase):
    def _player(self):
        return {'strength': 10, 'agility': 10, 'intuition': 20, 'vitality': 10, 'wisdom': 10, 'luck': 10}

    def _mob(self):
        return {'id': 'forest_wolf', 'mob_id': 'forest_wolf', 'defense': 0}

    def _skill_result(self, skill_id='future_skill'):
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

    def _state(self, enemy_units, active_enemy_unit_id='u1'):
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

    def test_fanout_flame_wave_shape_compat_still_works_and_has_pattern_id(self):
        battle_state = self._state([
            {'unit_id': 'u1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False},
            {'unit_id': 'u2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False},
        ])
        skill_result = self._skill_result('flame_wave')
        with patch('game.combat.get_skill', return_value={'target_shape': 'all_enemies_in_small_pack'}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            result = resolve_pack_fanout_direct_damage_skill_action(self._player(), self._mob(), battle_state, skill_result, lang='en')
        self.assertTrue(result['handled'])
        self.assertEqual(skill_result['direct_damage_result']['target_pattern_id'], 'all_enemies_in_small_pack')

    def test_fanout_supports_two_front_lines_2x2_and_cap(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f3', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'm2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'r1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'ranged'},
        ], active_enemy_unit_id='m2')
        skill_result = self._skill_result('future_two_line_skill')
        with patch('game.combat.get_skill', return_value={'target_pattern_id': 'two_front_lines_2x2'}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            result = resolve_pack_fanout_direct_damage_skill_action(self._player(), self._mob(), battle_state, skill_result, lang='en')
        self.assertTrue(result['handled'])
        self.assertEqual([x['unit_id'] for x in skill_result['direct_damage_result']['per_target']], ['f1', 'f2', 'm2', 'm1'])

    def test_fanout_empty_selection_is_handled_no_valid_target(self):
        battle_state = self._state([
            {'unit_id': 'u1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False},
            {'unit_id': 'u2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False},
        ], active_enemy_unit_id='u1')
        skill_result = self._skill_result('future_two_line_skill')
        skill_result['heal'] = 8
        skill_result['effects'] = [{'type': 'bleed', 'value': 3, 'turns': 2}]
        with patch('game.combat.get_skill', return_value={'target_pattern_id': 'two_front_lines_2x2'}):
            result = resolve_pack_fanout_direct_damage_skill_action(self._player(), self._mob(), battle_state, skill_result, lang='en')
        self.assertTrue(result['handled'])
        self.assertTrue(result['no_valid_target'])
        self.assertEqual(result['targets_total'], 0)
        self.assertEqual(result['targets_hit'], 0)
        self.assertEqual([u['hp'] for u in battle_state['enemy_units']], [20, 20])
        self.assertEqual(skill_result['damage'], 0)
        self.assertEqual(skill_result['heal'], 0)
        self.assertEqual(skill_result['effects'], [])
        self.assertTrue(skill_result['direct_damage_result']['no_valid_target'])
        self.assertEqual(skill_result['direct_damage_result']['target_pattern_id'], 'two_front_lines_2x2')

    def test_process_fanout_empty_selection_does_not_fall_through(self):
        battle_state = self._state([
            {'unit_id': 'u1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False},
            {'unit_id': 'u2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False},
        ], active_enemy_unit_id='u1')
        battle_state['player_hp'] = 50
        skill_result = self._skill_result('future_two_line_skill')
        skill_result['heal'] = 8
        skill_result['effects'] = [{'type': 'bleed', 'value': 3, 'turns': 2}]
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.get_skill', return_value={'target_pattern_id': 'two_front_lines_2x2'}):
            result = process_skill_turn('future_two_line_skill', self._player(), self._mob(), battle_state, user_id=1, lang='en', include_enemy_response=False)
        self.assertTrue(result['success'])
        self.assertEqual(battle_state['player_hp'], 50)
        self.assertEqual([u['hp'] for u in battle_state['enemy_units']], [20, 20])
        self.assertEqual(skill_result['damage'], 0)
        self.assertEqual(skill_result['heal'], 0)
        self.assertEqual(skill_result['effects'], [])
        self.assertTrue(skill_result['direct_damage_result']['no_valid_target'])

    def test_fanout_rejects_unknown_or_non_fanout_patterns(self):
        state = self._state([{'unit_id': 'u1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False}])
        with patch('game.combat.get_skill', return_value={'target_pattern_id': 'unknown_pattern'}):
            self.assertFalse(resolve_pack_fanout_direct_damage_skill_action(self._player(), self._mob(), state, self._skill_result(), lang='en')['handled'])
        with patch('game.combat.get_skill', return_value={'target_pattern_id': 'back_line_single'}):
            self.assertFalse(resolve_pack_fanout_direct_damage_skill_action(self._player(), self._mob(), state, self._skill_result(), lang='en')['handled'])

    def test_redirect_supports_backline_and_ranged_line_patterns(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'r1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'ranged'},
            {'unit_id': 's1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
        ], active_enemy_unit_id='f1')

        with patch('game.combat.get_skill', return_value={'target_pattern_id': 'back_line_single'}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            skill_result = self._skill_result('backline')
            backline_result = resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), battle_state, skill_result, lang='en')
        self.assertTrue(backline_result['handled'])
        self.assertEqual(backline_result['selected_unit_id'], 's1')
        self.assertEqual(skill_result['direct_damage_result']['target_pattern_id'], 'back_line_single')

        with patch('game.combat.get_skill', return_value={'target_pattern_id': 'ranged_line_single'}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            skill_result = self._skill_result('rangedline')
            ranged_result = resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), battle_state, skill_result, lang='en')
        self.assertTrue(ranged_result['handled'])
        self.assertEqual(ranged_result['selected_unit_id'], 'r1')
        self.assertEqual(skill_result['direct_damage_result']['target_pattern_id'], 'ranged_line_single')

    def test_redirect_empty_ranged_line_is_handled_no_valid_target(self):
        no_ranged_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
        ])
        skill_result = self._skill_result()
        skill_result['heal'] = 7
        skill_result['effects'] = [{'type': 'bleed', 'value': 3, 'turns': 2}]
        with patch('game.combat.get_skill', return_value={'target_pattern_id': 'ranged_line_single'}):
            result = resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), no_ranged_state, skill_result, lang='en')
        self.assertTrue(result['handled'])
        self.assertIsNone(result['selected_unit_id'])
        self.assertTrue(result['no_valid_target'])
        self.assertEqual([u['hp'] for u in no_ranged_state['enemy_units']], [20, 20])
        self.assertEqual(skill_result['damage'], 0)
        self.assertEqual(skill_result['heal'], 0)
        self.assertEqual(skill_result['effects'], [])
        self.assertEqual(skill_result['log'], 'No valid target.')
        self.assertEqual(skill_result['direct_damage_result']['target_pattern_id'], 'ranged_line_single')
        self.assertTrue(skill_result['direct_damage_result']['no_valid_target'])

    def test_redirect_unknown_pattern_is_not_handled(self):
        no_ranged_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
        ])
        with patch('game.combat.get_skill', return_value={'target_pattern_id': 'unknown_pattern'}):
            self.assertFalse(resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), no_ranged_state, self._skill_result(), lang='en')['handled'])

    def test_process_does_not_fall_through_on_empty_ranged_line(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
        ], active_enemy_unit_id='f1')
        battle_state['player_hp'] = 50
        skill_result = self._skill_result('rangedline')
        skill_result['heal'] = 9
        skill_result['effects'] = [{'type': 'bleed', 'value': 3, 'turns': 2}]
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.get_skill', return_value={'target_pattern_id': 'ranged_line_single'}):
            result = process_skill_turn('rangedline', self._player(), self._mob(), battle_state, user_id=1, lang='en', include_enemy_response=False)
        self.assertTrue(result['success'])
        self.assertEqual(battle_state['player_hp'], 50)
        self.assertEqual([u['hp'] for u in battle_state['enemy_units']], [20, 20])
        self.assertEqual(battle_state['enemy_units'][0]['mob_effects'], [])
        self.assertEqual(battle_state['enemy_units'][1]['mob_effects'], [])
        self.assertEqual(skill_result['heal'], 0)
        self.assertTrue(skill_result['direct_damage_result']['no_valid_target'])
        self.assertEqual(skill_result['direct_damage_result']['selected_unit_id'], None)

    def test_solo_no_enemy_units_keeps_ordinary_direct_path(self):
        battle_state = {
            'mob_hp': 20,
            'mob_max_hp': 20,
            'mob_effects': [],
            'mob_dead': False,
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'player_max_mana': 100,
            'log': [],
        }
        skill_result = self._skill_result('ordinary_solo')
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.get_skill', return_value={'target_pattern_id': 'ranged_line_single'}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            result = process_skill_turn('ordinary_solo', self._player(), self._mob(), battle_state, user_id=1, lang='en', include_enemy_response=False)
        self.assertTrue(result['success'])
        self.assertEqual(battle_state['mob_hp'], 10)

    def test_process_unknown_explicit_pattern_is_blocked_no_fallback(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
        ], active_enemy_unit_id='f1')
        battle_state['player_hp'] = 50
        skill_result = self._skill_result('bad_pattern_skill')
        skill_result['heal'] = 11
        skill_result['effects'] = [{'type': 'bleed', 'value': 3, 'turns': 2}]
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.get_skill', return_value={'target_pattern_id': 'unknown_pattern'}):
            result = process_skill_turn('bad_pattern_skill', self._player(), self._mob(), battle_state, user_id=1, lang='en', include_enemy_response=False)
        self.assertTrue(result['success'])
        self.assertEqual(battle_state['player_hp'], 50)
        self.assertEqual(battle_state['enemy_units'][0]['hp'], 20)
        self.assertEqual(skill_result['damage'], 0)
        self.assertEqual(skill_result['heal'], 0)
        self.assertEqual(skill_result['effects'], [])
        self.assertTrue(skill_result['direct_damage_result']['invalid_target_pattern'])
        self.assertTrue(skill_result['direct_damage_result']['no_valid_target'])

    def test_ordinary_pattern_resolution_and_process_behavior_stays_stable(self):
        self.assertEqual(resolve_target_pattern_id({}), 'ordinary_single_enemy')
        self.assertEqual(resolve_target_pattern_id({'target_shape': 'single_active_enemy'}), 'ordinary_single_enemy')

        battle_state = self._state([
            {'unit_id': 'u1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
        ], active_enemy_unit_id='u1')
        skill_result = self._skill_result('ordinary_direct')
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.get_skill', return_value={}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            result = process_skill_turn('ordinary_direct', self._player(), self._mob(), battle_state, user_id=1, lang='en', include_enemy_response=False)
        self.assertTrue(result['success'])
        self.assertEqual(battle_state['mob_hp'], 10)
        self.assertEqual(skill_result['direct_damage_result'].get('target_pattern_id'), 'ordinary_single_enemy')


if __name__ == '__main__':
    unittest.main()
