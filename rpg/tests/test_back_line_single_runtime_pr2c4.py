import unittest
from unittest.mock import patch

from game.combat import (
    process_skill_turn,
    resolve_back_line_single_direct_damage_skill_action,
)


class BackLineSingleRuntimePR2C4Tests(unittest.TestCase):
    def _player(self):
        return {'strength': 10, 'agility': 10, 'intuition': 20, 'vitality': 10, 'wisdom': 10, 'luck': 10}

    def _mob(self):
        return {'id': 'forest_wolf', 'mob_id': 'forest_wolf', 'defense': 0}

    def _skill_result(self):
        return {
            'success': True,
            'skill_id': 'future_backline_skill',
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

    def test_dispatch_contract_returns_false_when_not_applicable(self):
        base_state = self._state([{'unit_id': 'u1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False}])
        base_skill = self._skill_result()

        result = resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), {'mob_hp': 20}, base_skill, lang='en')
        self.assertFalse(result['handled'])

        with patch('game.combat.get_skill', return_value={'target_shape': 'single_active_enemy'}):
            result = resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), dict(base_state), dict(base_skill), lang='en')
        self.assertFalse(result['handled'])

        with patch('game.combat.get_skill', return_value={'target_shape': 'back_line_single'}):
            not_direct = dict(base_skill)
            not_direct['direct_damage_skill'] = False
            result = resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), dict(base_state), not_direct, lang='en')
        self.assertFalse(result['handled'])

        with patch('game.combat.get_skill', return_value={'target_shape': 'back_line_single'}):
            not_enemy = dict(base_skill)
            not_enemy['target_kind'] = 'self'
            result = resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), dict(base_state), not_enemy, lang='en')
        self.assertFalse(result['handled'])

    def test_selector_priority_and_single_unit_damage(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'r1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'ranged'},
            {'unit_id': 's1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
        ], active_enemy_unit_id='f1')
        skill_result = self._skill_result()
        with patch('game.combat.get_skill', return_value={'target_shape': 'back_line_single'}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            result = resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), battle_state, skill_result, lang='en')
        self.assertTrue(result['handled'])
        self.assertEqual(result['selected_unit_id'], 's1')
        self.assertEqual([u['hp'] for u in battle_state['enemy_units']], [20, 20, 20, 10])

    def test_selector_falls_back_ranged_then_melee(self):
        ranged_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'r1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'ranged'},
        ], active_enemy_unit_id='f1')
        with patch('game.combat.get_skill', return_value={'target_shape': 'back_line_single'}), patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            result = resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), ranged_state, self._skill_result(), lang='en')
        self.assertEqual(result['selected_unit_id'], 'r1')

        melee_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
        ], active_enemy_unit_id='f1')
        with patch('game.combat.get_skill', return_value={'target_shape': 'back_line_single'}), patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            result = resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), melee_state, self._skill_result(), lang='en')
        self.assertEqual(result['selected_unit_id'], 'm1')

    def test_active_target_restoration_and_final_kill(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 's1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
        ], active_enemy_unit_id='f1')
        with patch('game.combat.get_skill', return_value={'target_shape': 'back_line_single'}), patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            skill_result = self._skill_result()
            resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), battle_state, skill_result, lang='en')
        self.assertEqual(battle_state['active_enemy_unit_id'], 'f1')

        battle_state['enemy_units'][0]['dead'] = True
        battle_state['enemy_units'][0]['hp'] = 0
        with patch('game.combat.get_skill', return_value={'target_shape': 'back_line_single'}), patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            skill_result = self._skill_result()
            resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), battle_state, skill_result, lang='en')
        self.assertEqual(battle_state['active_enemy_unit_id'], 's1')

        solo_state = self._state([
            {'unit_id': 's1', 'hp': 10, 'max_hp': 10, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
        ], active_enemy_unit_id='s1')
        kill_skill = self._skill_result()
        kill_skill['damage'] = 20
        with patch('game.combat.get_skill', return_value={'target_shape': 'back_line_single'}), patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), solo_state, kill_skill, lang='en')
        self.assertTrue(solo_state['mob_dead'])
        self.assertEqual(solo_state['mob_hp'], 0)

    def test_miss_and_metadata(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 's1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
        ], active_enemy_unit_id='f1')
        skill_result = self._skill_result()
        with patch('game.combat.get_skill', return_value={'target_shape': 'back_line_single'}), patch('game.combat.resolve_hit_check', return_value={'is_hit': False}):
            result = resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), battle_state, skill_result, lang='en')
        self.assertTrue(result['handled'])
        self.assertEqual([u['hp'] for u in battle_state['enemy_units']], [20, 20])
        meta = skill_result['direct_damage_result']
        self.assertEqual(meta['target_shape'], 'back_line_single')
        self.assertEqual(meta['selected_unit_id'], 's1')
        self.assertTrue(meta['shape_redirect'])

    def test_redirected_hit_applies_effects_to_selected_backline_unit_only(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 's1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
        ], active_enemy_unit_id='f1')
        skill_result = self._skill_result()
        skill_result['effects'] = [{'type': 'bleed', 'value': 3, 'turns': 2}]
        with patch('game.combat.get_skill', return_value={'target_shape': 'back_line_single'}), patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), battle_state, skill_result, lang='en')
        self.assertEqual(battle_state['enemy_units'][0]['mob_effects'], [])
        self.assertEqual(battle_state['enemy_units'][1]['mob_effects'], [{'type': 'bleed', 'value': 3, 'turns': 2}])
        self.assertEqual(skill_result['effects'], [])

    def test_process_skill_turn_does_not_reapply_effect_to_restored_active_target(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 's1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
        ], active_enemy_unit_id='f1')
        skill_result = self._skill_result()
        skill_result['effects'] = [{'type': 'bleed', 'value': 3, 'turns': 2}]
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.get_skill', return_value={'target_shape': 'back_line_single'}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            result = process_skill_turn('future_backline_skill', self._player(), self._mob(), battle_state, user_id=1, lang='en', include_enemy_response=False)
        self.assertTrue(result['success'])
        self.assertEqual(battle_state['active_enemy_unit_id'], 'f1')
        self.assertEqual(battle_state['enemy_units'][0]['mob_effects'], [])
        self.assertEqual(battle_state['enemy_units'][1]['mob_effects'], [{'type': 'bleed', 'value': 3, 'turns': 2}])

    def test_miss_path_keeps_effects_off_all_enemy_units(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 's1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
        ], active_enemy_unit_id='f1')
        skill_result = self._skill_result()
        skill_result['effects'] = [{'type': 'bleed', 'value': 3, 'turns': 2}]
        with patch('game.combat.get_skill', return_value={'target_shape': 'back_line_single'}), patch('game.combat.resolve_hit_check', return_value={'is_hit': False}):
            resolve_back_line_single_direct_damage_skill_action(self._player(), self._mob(), battle_state, skill_result, lang='en')
        self.assertEqual(battle_state['enemy_units'][0]['mob_effects'], [])
        self.assertEqual(battle_state['enemy_units'][1]['mob_effects'], [])

    def test_process_dispatches_backline_before_regular_direct_target(self):
        battle_state = self._state([
            {'unit_id': 'u1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
        ], active_enemy_unit_id='u1')
        skill_result = self._skill_result()
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.resolve_pack_fanout_direct_damage_skill_action', return_value={'handled': False}), \
             patch('game.combat.resolve_back_line_single_direct_damage_skill_action', return_value={'handled': True}), \
             patch('game.combat.resolve_enemy_targeted_direct_damage_skill_action', return_value={'handled': True}) as direct_mock:
            process_skill_turn('future_backline_skill', self._player(), self._mob(), battle_state, user_id=1, lang='en', include_enemy_response=False)
        direct_mock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
