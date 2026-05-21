import unittest
from unittest.mock import patch

from game.combat import process_skill_turn
from game.skills import get_skill


class EnemyEffectRedirectHuntersMarkPR2C9Tests(unittest.TestCase):
    def _player(self):
        return {'strength': 12, 'agility': 10, 'intuition': 20, 'vitality': 10, 'wisdom': 10, 'luck': 12}

    def _mob(self, defense=0):
        return {'id': 'forest_wolf', 'mob_id': 'forest_wolf', 'defense': defense}

    def _unit(self, unit_id, line, dead=False):
        return {'unit_id': unit_id, 'hp': 100 if not dead else 0, 'max_hp': 100, 'mob_effects': [], 'dead': dead, 'formation_line': line}

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
            'player_mana': 200,
            'player_max_mana': 200,
            'steady_aim_turns': 0,
            'log': [],
        }

    def _run(self, skill_id, state, resolve_hit=True):
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': resolve_hit}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            return process_skill_turn(skill_id, self._player(), self._mob(), state, user_id=1, lang='en', include_enemy_response=False)

    def test_metadata_rollout_and_no_sniper_changes(self):
        mark = get_skill('hunters_mark')
        self.assertEqual(mark.get('target_pattern_id'), 'back_line_single')
        self.assertIsNone(mark.get('target_shape'))
        self.assertIsNone(mark.get('target_local_resolution'))
        self.assertEqual(mark.get('mana_cost'), 20)
        self.assertEqual(mark.get('cooldown'), 4)
        self.assertEqual(mark.get('scale_mult'), 0.8)
        self.assertEqual(mark.get('base_value'), 25)
        self.assertEqual(mark.get('duration'), 3)
        self.assertEqual(mark.get('level_bonus'), 0.08)

        for sid in ('aimed_shot', 'piercing_arrow', 'deadeye'):
            s = get_skill(sid)
            self.assertEqual(s.get('target_pattern_id'), 'back_line_single')
            self.assertIs(s.get('target_local_resolution'), True)

    def test_marks_support_and_restores_active(self):
        state = self._state()
        result = self._run('hunters_mark', state)
        self.assertTrue(result['success'])
        sr = result['skill_result']
        self.assertEqual(sr.get('selected_unit_id'), 's1')
        self.assertEqual(sr.get('target_pattern_id'), 'back_line_single')
        self.assertTrue(sr.get('enemy_effect_redirect'))
        self.assertEqual(state['active_enemy_unit_id'], 'f1')
        self.assertFalse(state['enemy_units'][0]['mob_effects'])
        self.assertFalse(state['enemy_units'][1]['mob_effects'])
        self.assertTrue(any(e.get('type') == 'hunters_mark' for e in state['enemy_units'][2]['mob_effects']))

    def test_fallbacks(self):
        no_support = self._state(units=[self._unit('f1', 'front'), self._unit('r1', 'ranged')])
        self.assertEqual(self._run('hunters_mark', no_support)['skill_result'].get('selected_unit_id'), 'r1')
        only_front = self._state(units=[self._unit('f1', 'front')])
        self.assertEqual(self._run('hunters_mark', only_front)['skill_result'].get('selected_unit_id'), 'f1')

    def test_refresh_merge_remains_target_local(self):
        state = self._state()
        self._run('hunters_mark', state)
        self._run('hunters_mark', state)
        support_effects = [e for e in state['enemy_units'][2]['mob_effects'] if e.get('type') == 'hunters_mark']
        self.assertEqual(len(support_effects), 1)
        self.assertFalse(state['enemy_units'][0]['mob_effects'])

    def test_no_valid_target(self):
        dead_units = [self._unit('f1', 'front', dead=True), self._unit('r1', 'ranged', dead=True), self._unit('s1', 'support', dead=True)]
        state = self._state(units=dead_units)
        result = self._run('hunters_mark', state)
        self.assertFalse(result['success'])
        self.assertTrue(result['skill_result'].get('no_valid_target'))
        self.assertTrue(result['skill_result'].get('enemy_effect_redirect'))

    def test_single_spend_mana_and_cooldown(self):
        state = self._state()
        state['player_mana'] = int(get_skill('hunters_mark').get('mana_cost', 0))
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.skill_engine.set_skill_cooldown') as set_cd_mock:
            result = process_skill_turn('hunters_mark', self._player(), self._mob(), state, user_id=1, lang='en', include_enemy_response=False)
        self.assertTrue(result['success'])
        self.assertEqual(state['player_mana'], 0)
        self.assertEqual(set_cd_mock.call_count, 1)

    def test_forced_use_skill_failure_restores_active_projection(self):
        state = self._state(units=[self._unit('f1', 'front'), self._unit('s1', 'support')])
        state['enemy_units'][0]['hp'] = 91
        state['enemy_units'][0]['mob_effects'] = [{'type': 'front_only', 'turns': 2, 'value': 1}]
        state['mob_hp'] = 91
        state['mob_max_hp'] = 100
        state['mob_effects'] = list(state['enemy_units'][0]['mob_effects'])
        state['active_enemy_unit_id'] = 'f1'

        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.combat.use_skill', return_value={'success': False, 'skill_id': 'hunters_mark', 'log': 'forced fail'}):
            result = process_skill_turn('hunters_mark', self._player(), self._mob(), state, user_id=1, lang='en', include_enemy_response=False)

        self.assertFalse(result['success'])
        self.assertEqual(state['active_enemy_unit_id'], 'f1')
        self.assertEqual(state['mob_hp'], 91)
        self.assertEqual(state['mob_effects'], [{'type': 'front_only', 'turns': 2, 'value': 1}])
        self.assertEqual(state['enemy_units'][1]['mob_effects'], [])
        self.assertEqual(state['enemy_units'][0]['hp'], 91)
        self.assertNotIn('_pending_enemy_effect_redirect_projection', state)

    def test_include_enemy_response_true_ticks_selected_target_mark_duration(self):
        state = self._state(units=[self._unit('f1', 'front'), self._unit('s1', 'support')])
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.has_active_mob_effect', side_effect=lambda bs, *effects: any(e in ('stun', 'freeze') for e in effects)):
            result = process_skill_turn('hunters_mark', self._player(), self._mob(), state, user_id=1, lang='en', include_enemy_response=True)

        self.assertTrue(result['success'])
        support_marks = [e for e in state['enemy_units'][1]['mob_effects'] if e.get('type') == 'hunters_mark']
        self.assertEqual(len(support_marks), 1)
        self.assertEqual(int(support_marks[0].get('turns', 0)), 2)
        self.assertEqual(state['enemy_units'][0]['mob_effects'], [])
        self.assertEqual(state['active_enemy_unit_id'], 'f1')
        self.assertNotIn('_pending_enemy_effect_redirect_projection', state)

    def test_include_enemy_response_false_does_not_tick_early(self):
        state = self._state(units=[self._unit('f1', 'front'), self._unit('s1', 'support')])
        result = self._run('hunters_mark', state)
        self.assertTrue(result['success'])
        support_marks = [e for e in state['enemy_units'][1]['mob_effects'] if e.get('type') == 'hunters_mark']
        self.assertEqual(len(support_marks), 1)
        self.assertEqual(int(support_marks[0].get('turns', 0)), 3)
        self.assertEqual(state['active_enemy_unit_id'], 'f1')
        self.assertNotIn('_pending_enemy_effect_redirect_projection', state)

    def test_no_enemy_units_falls_back_to_ordinary_flow(self):
        state = self._state(units=[])
        state.pop('enemy_units', None)
        result = self._run('hunters_mark', state)
        self.assertTrue(result['success'])
        self.assertTrue(any(e.get('type') == 'hunters_mark' for e in state.get('mob_effects', [])))

    def _chain_baseline_and_marked(self, shot_skill):
        marked_state = self._state()
        self._run('hunters_mark', marked_state)
        marked = self._run(shot_skill, marked_state)

        baseline_state = self._state()
        baseline = self._run(shot_skill, baseline_state)
        return marked_state, marked, baseline

    def test_chain_hunters_mark_then_aimed_shot(self):
        marked_state, marked, baseline = self._chain_baseline_and_marked('aimed_shot')
        self.assertEqual(marked['skill_result']['direct_damage_result']['selected_unit_id'], 's1')
        self.assertGreater(marked['skill_result']['damage'], baseline['skill_result']['damage'])
        self.assertEqual(marked_state['enemy_units'][0]['hp'], 100)

    def test_chain_hunters_mark_then_piercing_arrow(self):
        marked_state, marked, baseline = self._chain_baseline_and_marked('piercing_arrow')
        self.assertEqual(marked['skill_result']['direct_damage_result']['selected_unit_id'], 's1')
        self.assertGreater(marked['skill_result']['damage'], baseline['skill_result']['damage'])
        self.assertEqual(marked_state['enemy_units'][0]['hp'], 100)

    def test_chain_hunters_mark_then_deadeye(self):
        marked_state, marked, baseline = self._chain_baseline_and_marked('deadeye')
        self.assertEqual(marked['skill_result']['direct_damage_result']['selected_unit_id'], 's1')
        self.assertGreater(marked['skill_result']['damage'], baseline['skill_result']['damage'])
        self.assertEqual(marked_state['enemy_units'][0]['hp'], 100)


if __name__ == '__main__':
    unittest.main()
