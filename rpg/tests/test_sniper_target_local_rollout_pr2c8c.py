import unittest
from unittest.mock import patch

from game.combat import process_skill_turn
from game.skills import get_skill


class SniperTargetLocalRolloutPR2C8CTests(unittest.TestCase):
    def _player(self):
        return {'strength': 12, 'agility': 10, 'intuition': 20, 'vitality': 10, 'wisdom': 10, 'luck': 12}

    def _mob(self, defense=0):
        return {'id': 'forest_wolf', 'mob_id': 'forest_wolf', 'defense': defense}

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

    def _run(self, skill_id, state, mob=None, set_cd_mock=None):
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            if set_cd_mock is not None:
                with patch('game.skill_engine.set_skill_cooldown', set_cd_mock):
                    return process_skill_turn(skill_id, self._player(), mob or self._mob(), state, user_id=1, lang='en', include_enemy_response=False)
            return process_skill_turn(skill_id, self._player(), mob or self._mob(), state, user_id=1, lang='en', include_enemy_response=False)

    def test_metadata_rollout_and_balance_unchanged(self):
        aimed = get_skill('aimed_shot')
        self.assertEqual(aimed.get('target_pattern_id'), 'back_line_single')
        self.assertIs(aimed.get('target_local_resolution'), True)
        self.assertIsNone(aimed.get('target_shape'))
        self.assertEqual(aimed.get('mana_cost'), 25)
        self.assertEqual(aimed.get('cooldown'), 3)
        self.assertEqual(aimed.get('scale_mult'), 2.0)
        self.assertEqual(aimed.get('base_value'), 200)
        self.assertEqual(aimed.get('level_bonus'), 0.12)
        self.assertEqual(aimed.get('accuracy_bonus'), 25)
        self.assertEqual(aimed.get('marked_mult'), 1.22)

        piercing = get_skill('piercing_arrow')
        self.assertEqual(piercing.get('target_pattern_id'), 'back_line_single')
        self.assertIs(piercing.get('target_local_resolution'), True)
        self.assertIsNone(piercing.get('target_shape'))
        self.assertEqual(piercing.get('mana_cost'), 30)
        self.assertEqual(piercing.get('cooldown'), 4)
        self.assertEqual(piercing.get('scale_mult'), 2.2)
        self.assertEqual(piercing.get('base_value'), 220)
        self.assertEqual(piercing.get('ignore_defense'), 0.45)
        self.assertEqual(piercing.get('armor_defense_threshold'), 15)
        self.assertEqual(piercing.get('marked_mult'), 1.22)
        self.assertEqual(piercing.get('armored_mult'), 1.16)

        deadeye = get_skill('deadeye')
        self.assertEqual(deadeye.get('target_pattern_id'), 'back_line_single')
        self.assertIs(deadeye.get('target_local_resolution'), True)

        hunters_mark = get_skill('hunters_mark')
        self.assertEqual(hunters_mark.get('target_pattern_id'), 'back_line_single')

    def test_aimed_shot_selection_mark_leak_and_steady(self):
        direct = self._run('aimed_shot', self._state())
        direct_damage = direct['skill_result']['direct_damage_result']
        self.assertEqual(direct_damage['selected_unit_id'], 's1')
        self.assertEqual(direct_damage['target_pattern_id'], 'back_line_single')
        self.assertIs(direct_damage['shape_redirect'], True)

        marked_state = self._state()
        marked_state['enemy_units'][2]['mob_effects'] = [{'type': 'hunters_mark', 'value': 10, 'turns': 2}]
        marked = self._run('aimed_shot', marked_state)
        baseline = self._run('aimed_shot', self._state())
        self.assertGreater(marked['skill_result']['damage'], baseline['skill_result']['damage'])
        self.assertEqual(marked_state['enemy_units'][0]['hp'], 100)

        leaked_state = self._state()
        leaked_state['enemy_units'][0]['mob_effects'] = [{'type': 'hunters_mark', 'value': 10, 'turns': 2}]
        leaked = self._run('aimed_shot', leaked_state)
        self.assertEqual(leaked['skill_result']['damage'], baseline['skill_result']['damage'])

        steady_state = self._state()
        steady_state['steady_aim_turns'] = 2
        before = steady_state['steady_aim_turns']
        steady = self._run('aimed_shot', steady_state)
        self.assertGreater(steady['skill_result']['damage'], baseline['skill_result']['damage'])
        self.assertLess(steady_state['steady_aim_turns'], before)

    def test_piercing_arrow_selection_mark_armor_steady_fallbacks(self):
        direct = self._run('piercing_arrow', self._state())
        self.assertEqual(direct['skill_result']['direct_damage_result']['selected_unit_id'], 's1')

        marked_state = self._state()
        marked_state['enemy_units'][2]['mob_effects'] = [{'type': 'hunters_mark', 'value': 10, 'turns': 2}]
        marked = self._run('piercing_arrow', marked_state)
        baseline = self._run('piercing_arrow', self._state())
        self.assertGreater(marked['skill_result']['damage'], baseline['skill_result']['damage'])

        leaked_state = self._state()
        leaked_state['enemy_units'][0]['mob_effects'] = [{'type': 'hunters_mark', 'value': 10, 'turns': 2}]
        leaked = self._run('piercing_arrow', leaked_state)
        self.assertEqual(leaked['skill_result']['damage'], baseline['skill_result']['damage'])

        # Armor payoff currently uses shared mob_state defense, not per-unit defense.
        armored = self._run('piercing_arrow', self._state(), mob=self._mob(defense=30))
        self.assertIn('armored', armored['skill_result'].get('log_key', ''))

        no_armor_bonus = dict(get_skill('piercing_arrow'))
        no_armor_bonus['armored_mult'] = 1.0
        no_armor_bonus['marked_armored_mult'] = no_armor_bonus.get('marked_mult', 1.0)
        with patch('game.combat.get_skill', side_effect=lambda sid: no_armor_bonus if sid == 'piercing_arrow' else get_skill(sid)), \
             patch('game.skill_engine.get_skill', side_effect=lambda sid: no_armor_bonus if sid == 'piercing_arrow' else get_skill(sid)):
            non_armored_baseline = self._run('piercing_arrow', self._state(), mob=self._mob(defense=30))
        self.assertGreater(armored['skill_result']['damage'], non_armored_baseline['skill_result']['damage'])

        steady_state = self._state()
        steady_state['steady_aim_turns'] = 2
        steady = self._run('piercing_arrow', steady_state)
        self.assertGreater(steady['skill_result']['damage'], baseline['skill_result']['damage'])

        no_support = self._state(units=[self._unit('f1', 'front'), self._unit('r1', 'ranged')])
        self.assertEqual(self._run('piercing_arrow', no_support)['skill_result']['direct_damage_result']['selected_unit_id'], 'r1')

        only_front = self._state(units=[self._unit('f1', 'front')])
        self.assertEqual(self._run('piercing_arrow', only_front)['skill_result']['direct_damage_result']['selected_unit_id'], 'f1')

    def test_piercing_arrow_no_double_spend_and_preview_safe(self):
        state = self._state()
        state['player_mana'] = int(get_skill('piercing_arrow').get('mana_cost', 0))

        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': False}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.skill_engine.set_skill_cooldown') as set_cd_mock:
            result = process_skill_turn('piercing_arrow', self._player(), self._mob(), state, user_id=1, lang='en', include_enemy_response=False)

        self.assertTrue(result['success'])
        self.assertEqual(state['player_mana'], 0)
        self.assertEqual(set_cd_mock.call_count, 1)


if __name__ == '__main__':
    unittest.main()
