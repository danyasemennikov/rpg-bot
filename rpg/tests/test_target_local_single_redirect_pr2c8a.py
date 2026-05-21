import unittest
from unittest.mock import patch

from game.combat import process_skill_turn
from game.skills import get_skill


class TargetLocalSingleRedirectPR2C8ATests(unittest.TestCase):
    def _player(self):
        return {'strength': 12, 'agility': 10, 'intuition': 20, 'vitality': 10, 'wisdom': 10, 'luck': 12}

    def _mob(self):
        return {'id': 'forest_wolf', 'mob_id': 'forest_wolf', 'defense': 0}

    def _state(self):
        return {
            'enemy_units': [
                {'unit_id': 'f1', 'hp': 100, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
                {'unit_id': 's1', 'hp': 100, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
            ],
            'active_enemy_unit_id': 'f1',
            'mob_hp': 100,
            'mob_max_hp': 100,
            'mob_effects': [],
            'mob_dead': False,
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'player_max_mana': 100,
            'log': [],
        }

    def _deadeye_meta(self):
        return {'id': 'deadeye', 'target_pattern_id': 'back_line_single', 'target_local_resolution': True}

    def test_selected_target_payoff_uses_selected_unit_state(self):
        marked_state = self._state()
        marked_state['enemy_units'][1]['mob_effects'] = [{'type': 'hunters_mark', 'value': 10, 'turns': 2}]

        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.get_skill', return_value=self._deadeye_meta()), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            marked_result = process_skill_turn('deadeye', self._player(), self._mob(), marked_state, user_id=1, lang='en', include_enemy_response=False)

        baseline_state = self._state()
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.get_skill', return_value=self._deadeye_meta()), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            baseline_result = process_skill_turn('deadeye', self._player(), self._mob(), baseline_state, user_id=1, lang='en', include_enemy_response=False)

        self.assertTrue(marked_result['success'])
        direct = marked_result['skill_result']['direct_damage_result']
        self.assertEqual(direct['selected_unit_id'], 's1')
        self.assertGreater(marked_result['skill_result']['damage'], baseline_result['skill_result']['damage'])
        self.assertEqual(marked_state['enemy_units'][0]['hp'], 100)
        self.assertLess(marked_state['enemy_units'][1]['hp'], 100)
        self.assertEqual(marked_state['active_enemy_unit_id'], 'f1')

    def test_active_target_payoff_does_not_leak_to_redirected_target(self):
        state = self._state()
        state['enemy_units'][0]['mob_effects'] = [{'type': 'hunters_mark', 'value': 10, 'turns': 2}]

        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.get_skill', return_value=self._deadeye_meta()), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = process_skill_turn('deadeye', self._player(), self._mob(), state, user_id=1, lang='en', include_enemy_response=False)

        redirected_damage = result['skill_result']['damage']

        baseline_state = self._state()
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.get_skill', return_value=self._deadeye_meta()), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            baseline = process_skill_turn('deadeye', self._player(), self._mob(), baseline_state, user_id=1, lang='en', include_enemy_response=False)

        self.assertEqual(redirected_damage, baseline['skill_result']['damage'])

    def test_preview_does_not_check_cooldown_and_set_cooldown_twice(self):
        state = self._state()

        def cooldown_side_effect(*_args, **_kwargs):
            cooldown_side_effect.calls += 1
            if cooldown_side_effect.calls == 1:
                return 0
            raise AssertionError('preview must not call get_skill_cooldown')

        cooldown_side_effect.calls = 0

        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.get_skill', return_value=self._deadeye_meta()), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': False}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', side_effect=cooldown_side_effect), \
             patch('game.skill_engine.set_skill_cooldown') as set_cd_mock, \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = process_skill_turn('deadeye', self._player(), self._mob(), state, user_id=1, lang='en', include_enemy_response=False)

        self.assertTrue(result['success'])
        self.assertEqual(cooldown_side_effect.calls, 1)
        self.assertEqual(set_cd_mock.call_count, 1)
        self.assertEqual(state['active_enemy_unit_id'], 'f1')

    def test_preview_does_not_fail_when_original_cast_spends_exact_mana(self):
        state = self._state()
        state['player_mana'] = int(get_skill('deadeye').get('mana_cost', 0))
        state['enemy_units'][1]['mob_effects'] = [{'type': 'hunters_mark', 'value': 10, 'turns': 2}]

        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.get_skill', return_value=self._deadeye_meta()), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = process_skill_turn('deadeye', self._player(), self._mob(), state, user_id=1, lang='en', include_enemy_response=False)

        self.assertTrue(result['success'])
        self.assertEqual(state['player_mana'], 0)
        self.assertLess(state['enemy_units'][1]['hp'], 100)
        self.assertEqual(state['enemy_units'][0]['hp'], 100)
        self.assertEqual(state['active_enemy_unit_id'], 'f1')

    def test_arcane_lance_behavior_unchanged_without_flag(self):
        state = self._state()

        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = process_skill_turn('arcane_lance', self._player(), self._mob(), state, user_id=1, lang='en', include_enemy_response=False)

        self.assertTrue(result['success'])
        direct = result['skill_result']['direct_damage_result']
        self.assertEqual(direct['target_pattern_id'], 'back_line_single')
        self.assertEqual(direct['selected_unit_id'], 's1')


if __name__ == '__main__':
    unittest.main()
