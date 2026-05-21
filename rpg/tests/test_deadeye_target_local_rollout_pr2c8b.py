import unittest
from copy import deepcopy
from unittest.mock import patch

from game.combat import process_skill_turn
from game.skills import get_skill


class DeadeyeTargetLocalRolloutPR2C8BTests(unittest.TestCase):
    def _player(self):
        return {'strength': 12, 'agility': 10, 'intuition': 20, 'vitality': 10, 'wisdom': 10, 'luck': 12}

    def _mob(self):
        return {'id': 'forest_wolf', 'mob_id': 'forest_wolf', 'defense': 0}

    def _unit(self, unit_id, line):
        return {'unit_id': unit_id, 'hp': 100, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': line}

    def _state(self, units=None):
        return {
            'enemy_units': units or [self._unit('f1', 'front'), self._unit('r1', 'ranged'), self._unit('s1', 'support')],
            'active_enemy_unit_id': 'f1',
            'mob_hp': 100,
            'mob_max_hp': 100,
            'mob_effects': [],
            'mob_dead': False,
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'player_max_mana': 100,
            'steady_aim_turns': 0,
            'log': [],
        }

    def _run(self, state, set_cd_mock=None):
        patches = [
            patch('game.combat.precheck_skill_use', return_value={'success': True}),
            patch('game.combat.resolve_hit_check', return_value={'is_hit': True}),
            patch('game.skill_engine.get_skill_level', return_value=1),
            patch('game.skill_engine.get_skill_cooldown', return_value=0),
            patch('game.skill_engine.random.uniform', return_value=1.0),
        ]
        if set_cd_mock is not None:
            patches.append(patch('game.skill_engine.set_skill_cooldown', set_cd_mock))

        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            if set_cd_mock is not None:
                with patches[5]:
                    return process_skill_turn('deadeye', self._player(), self._mob(), state, user_id=1, lang='en', include_enemy_response=False)
            return process_skill_turn('deadeye', self._player(), self._mob(), state, user_id=1, lang='en', include_enemy_response=False)

    def test_deadeye_metadata_rollout_and_balance_unchanged(self):
        deadeye = get_skill('deadeye')
        self.assertEqual(deadeye.get('target_pattern_id'), 'back_line_single')
        self.assertIs(deadeye.get('target_local_resolution'), True)
        self.assertIsNone(deadeye.get('target_shape'))

        self.assertEqual(deadeye.get('mana_cost'), 44)
        self.assertEqual(deadeye.get('cooldown'), 6)
        self.assertEqual(deadeye.get('scale_mult'), 2.7)
        self.assertEqual(deadeye.get('base_value'), 290)
        self.assertEqual(deadeye.get('level_bonus'), 0.14)
        self.assertEqual(deadeye.get('ignore_defense'), 0.55)
        self.assertEqual(deadeye.get('marked_mult'), 1.38)
        self.assertEqual(deadeye.get('steady_mult'), 1.18)
        self.assertEqual(deadeye.get('marked_steady_mult'), 1.55)

    def test_selects_support_over_front_and_ranged(self):
        state = self._state()
        result = self._run(state)

        self.assertTrue(result['success'])
        direct = result['skill_result']['direct_damage_result']
        self.assertEqual(direct['target_pattern_id'], 'back_line_single')
        self.assertIs(direct['shape_redirect'], True)
        self.assertEqual(direct['selected_unit_id'], 's1')
        self.assertEqual(state['enemy_units'][0]['hp'], 100)
        self.assertEqual(state['enemy_units'][1]['hp'], 100)
        self.assertLess(state['enemy_units'][2]['hp'], 100)
        self.assertEqual(state['active_enemy_unit_id'], 'f1')

    def test_marked_selected_support_gets_marked_payoff(self):
        marked_state = self._state()
        marked_state['enemy_units'][2]['mob_effects'] = [{'type': 'hunters_mark', 'value': 10, 'turns': 2}]
        marked = self._run(marked_state)

        baseline_state = self._state()
        baseline = self._run(baseline_state)

        self.assertGreater(marked['skill_result']['damage'], baseline['skill_result']['damage'])
        self.assertEqual(marked_state['enemy_units'][0]['hp'], 100)
        self.assertLess(marked_state['enemy_units'][2]['hp'], 100)
        self.assertEqual(marked_state['active_enemy_unit_id'], 'f1')

    def test_active_front_mark_does_not_leak(self):
        leaked_state = self._state()
        leaked_state['enemy_units'][0]['mob_effects'] = [{'type': 'hunters_mark', 'value': 10, 'turns': 2}]
        leaked = self._run(leaked_state)

        baseline = self._run(self._state())
        self.assertEqual(leaked['skill_result']['damage'], baseline['skill_result']['damage'])

    def test_steady_aim_payoff_works_on_selected_target(self):
        steady_state = self._state()
        steady_state['steady_aim_turns'] = 2
        before = steady_state['steady_aim_turns']
        steady = self._run(steady_state)

        baseline = self._run(self._state())
        self.assertGreater(steady['skill_result']['damage'], baseline['skill_result']['damage'])
        self.assertEqual(steady['skill_result']['direct_damage_result']['selected_unit_id'], 's1')
        self.assertLess(steady_state['steady_aim_turns'], before)

    def test_back_line_fallbacks(self):
        no_support = self._state(units=[self._unit('f1', 'front'), self._unit('r1', 'ranged')])
        result_no_support = self._run(no_support)
        self.assertEqual(result_no_support['skill_result']['direct_damage_result']['selected_unit_id'], 'r1')

        only_front = self._state(units=[self._unit('f1', 'front')])
        result_only_front = self._run(only_front)
        self.assertEqual(result_only_front['skill_result']['direct_damage_result']['selected_unit_id'], 'f1')

    def test_no_double_mana_or_cooldown_spend(self):
        state = self._state()
        state['player_mana'] = int(get_skill('deadeye').get('mana_cost', 0))

        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.skill_engine.set_skill_cooldown') as set_cd_mock:
            result = process_skill_turn('deadeye', self._player(), self._mob(), state, user_id=1, lang='en', include_enemy_response=False)

        self.assertTrue(result['success'])
        self.assertEqual(state['player_mana'], 0)
        self.assertEqual(set_cd_mock.call_count, 1)


if __name__ == '__main__':
    unittest.main()
