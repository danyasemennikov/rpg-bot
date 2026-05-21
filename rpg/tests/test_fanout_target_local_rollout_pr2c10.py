import unittest
from unittest.mock import patch

from game.combat import process_skill_turn
from game.skills import get_skill


class FanoutTargetLocalRolloutPR2C10Tests(unittest.TestCase):
    def _player(self):
        return {'strength': 24, 'agility': 10, 'intuition': 10, 'vitality': 10, 'wisdom': 10, 'luck': 10}

    def _mob(self):
        return {'id': 'forest_wolf', 'mob_id': 'forest_wolf', 'defense': 0}

    def _state(self, enemy_units, active_enemy_unit_id='m1'):
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

    def _run(self, state):
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}), \
             patch('game.skill_engine.set_skill_cooldown') as set_cd:
            result = process_skill_turn('cleave_through', self._player(), self._mob(), state, user_id=1, lang='en', include_enemy_response=False)
        return result, set_cd

    def test_metadata_scope_rollouts(self):
        cleave = get_skill('cleave_through')
        self.assertEqual(cleave.get('target_pattern_id'), 'front_line_cluster')
        self.assertIs(cleave.get('target_local_resolution'), True)
        self.assertIsNone(cleave.get('target_shape'))

        flame = get_skill('flame_wave')
        self.assertEqual(flame.get('target_pattern_id'), 'all_enemies_in_small_pack')
        self.assertIsNone(flame.get('target_shape'))

        driving = get_skill('driving_slash')
        self.assertIsNone(driving.get('target_pattern_id'))
        self.assertIsNone(driving.get('target_local_resolution'))

    def test_front_line_cluster_selection(self):
        state = self._state([
            {'unit_id': 'f1', 'hp': 150, 'max_hp': 150, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 150, 'max_hp': 150, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 150, 'max_hp': 150, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 's1', 'hp': 150, 'max_hp': 150, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
        ], active_enemy_unit_id='m1')

        result, _ = self._run(state)
        direct = result['skill_result']['direct_damage_result']
        self.assertEqual([p['unit_id'] for p in direct['per_target']], ['f1', 'f2'])
        self.assertEqual(state['enemy_units'][2]['hp'], 150)
        self.assertEqual(state['enemy_units'][3]['hp'], 150)

    def test_front_line_cluster_cap_hits_only_four(self):
        state = self._state([
            {'unit_id': 'f1', 'hp': 120, 'max_hp': 120, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 120, 'max_hp': 120, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f3', 'hp': 120, 'max_hp': 120, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f4', 'hp': 120, 'max_hp': 120, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f5', 'hp': 120, 'max_hp': 120, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
        ], active_enemy_unit_id='f5')

        result, _ = self._run(state)
        direct = result['skill_result']['direct_damage_result']
        self.assertEqual(direct['targets_total'], 4)
        self.assertEqual(len(direct['per_target']), 4)
        self.assertEqual(sum(1 for u in state['enemy_units'] if u['hp'] < 120), 4)

    def test_fallback_to_melee_when_front_empty(self):
        state = self._state([
            {'unit_id': 'm1', 'hp': 120, 'max_hp': 120, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'm2', 'hp': 120, 'max_hp': 120, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'r1', 'hp': 120, 'max_hp': 120, 'mob_effects': [], 'dead': False, 'formation_line': 'ranged'},
            {'unit_id': 's1', 'hp': 120, 'max_hp': 120, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
        ], active_enemy_unit_id='s1')

        result, _ = self._run(state)
        direct = result['skill_result']['direct_damage_result']
        self.assertEqual([p['unit_id'] for p in direct['per_target']], ['m1', 'm2'])
        self.assertEqual(state['enemy_units'][2]['hp'], 120)
        self.assertEqual(state['enemy_units'][3]['hp'], 120)

    def test_wounded_selected_target_gets_higher_target_local_damage(self):
        state = self._state([
            {'unit_id': 'f1', 'hp': 40, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 100, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 100, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
        ], active_enemy_unit_id='m1')
        state['vulnerability_turns'] = 2
        state['vulnerability_value'] = 20

        result, _ = self._run(state)
        per = result['skill_result']['direct_damage_result']['per_target']
        self.assertGreater(per[0]['damage'], per[1]['damage'])

    def test_active_offline_wounded_target_does_not_leak_payoff(self):
        state = self._state([
            {'unit_id': 'f1', 'hp': 100, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 100, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 40, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
        ], active_enemy_unit_id='m1')
        state['vulnerability_turns'] = 2
        state['vulnerability_value'] = 20

        result, _ = self._run(state)
        per = result['skill_result']['direct_damage_result']['per_target']
        self.assertEqual(per[0]['damage'], per[1]['damage'])
        self.assertEqual(state['enemy_units'][2]['hp'], 40)

    def test_executioner_focus_boosts_every_selected_target_and_consumes_once(self):
        baseline = self._state([
            {'unit_id': 'f1', 'hp': 100, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 100, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
        ], active_enemy_unit_id='f1')
        baseline_result, _ = self._run(baseline)
        base_per = baseline_result['skill_result']['direct_damage_result']['per_target']

        focused = self._state([
            {'unit_id': 'f1', 'hp': 100, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 100, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 100, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
        ], active_enemy_unit_id='m1')
        focused['executioner_focus_turns'] = 2
        focused['executioner_focus_value'] = 35

        focused_result, _ = self._run(focused)
        focused_per = focused_result['skill_result']['direct_damage_result']['per_target']

        self.assertGreater(focused_per[0]['damage'], base_per[0]['damage'])
        self.assertGreater(focused_per[1]['damage'], base_per[1]['damage'])
        self.assertEqual(focused['executioner_focus_turns'], 0)

    def test_resource_safety_mana_and_cooldown_once(self):
        mana = get_skill('cleave_through').get('mana_cost')
        state = self._state([
            {'unit_id': 'f1', 'hp': 120, 'max_hp': 120, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 120, 'max_hp': 120, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
        ], active_enemy_unit_id='f1')
        state['player_mana'] = mana

        _, set_cd = self._run(state)
        self.assertEqual(state['player_mana'], 0)
        self.assertEqual(set_cd.call_count, 1)

    def test_process_fanout_target_local_preview_uses_real_user_id(self):
        seen_telegram_ids = []

        def _skill_level_side_effect(telegram_id, skill_id):
            if skill_id != 'cleave_through':
                return 0
            seen_telegram_ids.append(int(telegram_id))
            if int(telegram_id) == 777:
                return 1
            if int(telegram_id) == 0:
                return 0
            raise AssertionError(f'unexpected telegram_id={telegram_id}')

        state = self._state([
            {'unit_id': 'f1', 'hp': 40, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 100, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 100, 'max_hp': 100, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
        ], active_enemy_unit_id='m1')
        state['vulnerability_turns'] = 2
        state['vulnerability_value'] = 20

        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.skill_engine.get_skill_level', side_effect=_skill_level_side_effect), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = process_skill_turn('cleave_through', self._player(), self._mob(), state, user_id=777, lang='en', include_enemy_response=False)

        self.assertTrue(result['success'])
        direct = result['skill_result']['direct_damage_result']
        self.assertIs(direct.get('target_local_resolution'), True)
        self.assertGreater(direct['per_target'][0]['damage'], direct['per_target'][1]['damage'])
        self.assertIn(777, seen_telegram_ids)
        self.assertNotIn(0, seen_telegram_ids)


if __name__ == '__main__':
    unittest.main()
