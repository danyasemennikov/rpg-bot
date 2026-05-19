import unittest
from unittest.mock import patch

from game.combat import process_skill_turn
from game.skills import get_skill
from game.skill_engine import use_skill
from game.i18n import t, get_skill_name


class PackAoeFanoutPR2B2Tests(unittest.TestCase):
    def _base_battle_state(self):
        return {
            'enemy_units': [
                {'unit_id': 'u1', 'hp': 40, 'max_hp': 40, 'mob_effects': [], 'dead': False},
                {'unit_id': 'u2', 'hp': 35, 'max_hp': 35, 'mob_effects': [], 'dead': False},
                {'unit_id': 'u3', 'hp': 30, 'max_hp': 30, 'mob_effects': [], 'dead': False},
            ],
            'active_enemy_unit_id': 'u1',
            'mob_hp': 40,
            'mob_max_hp': 40,
            'mob_effects': [],
            'mob_dead': False,
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'player_max_mana': 100,
            'log': [],
        }

    def _base_player(self):
        return {'strength': 10, 'agility': 10, 'intuition': 20, 'vitality': 10, 'wisdom': 10, 'luck': 10}

    def _base_mob(self):
        return {'id': 'forest_wolf', 'mob_id': 'forest_wolf', 'defense': 0}

    def test_flame_wave_is_explicit_pack_fanout_and_twin_cut_is_not(self):
        self.assertEqual(get_skill('flame_wave').get('enemy_target_mode'), 'pack_fanout')
        self.assertNotEqual(get_skill('twin_cut').get('enemy_target_mode'), 'pack_fanout')

    def test_real_use_skill_result_carries_skill_id(self):
        state = {'player_mana': 100, 'weapon_profile': 'magic_staff', 'weapon_type': 'magic'}
        player = {'mana': 100, 'strength': 10, 'agility': 10, 'intuition': 20, 'vitality': 10, 'wisdom': 10, 'luck': 10}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = use_skill('flame_wave', player, mob_state, state, telegram_id=777, lang='en')
        self.assertTrue(result.get('success'))
        self.assertEqual(result.get('skill_id'), 'flame_wave')

    def test_pack_fanout_activates_with_real_use_skill_result_shape(self):
        battle_state = self._base_battle_state()
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            result = process_skill_turn('flame_wave', self._base_player(), self._base_mob(), battle_state, user_id=1, lang='en', include_enemy_response=False)
        self.assertEqual(result['skill_result']['skill_id'], 'flame_wave')
        self.assertEqual(result['skill_result']['direct_damage_result']['targets_total'], 3)
        self.assertEqual(len(result['skill_result']['direct_damage_result']['per_target']), 3)
        self.assertTrue(all(unit['hp'] < unit['max_hp'] for unit in battle_state['enemy_units']))

    def test_pack_flame_wave_fanout_writes_damage_per_living_unit(self):
        battle_state = self._base_battle_state()
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value={'success': True, 'skill_id': 'flame_wave', 'log': 'cast', 'damage': 10, 'heal': 0, 'effects': [], 'target_kind': 'enemy', 'direct_damage_skill': True}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            process_skill_turn('flame_wave', self._base_player(), self._base_mob(), battle_state, user_id=1, include_enemy_response=False)
        self.assertEqual([u['hp'] for u in battle_state['enemy_units']], [30, 25, 20])
        self.assertIn(get_skill_name('flame_wave', 'ru'), battle_state['log'][-1])
        self.assertIn('3', battle_state['log'][-1])

    def test_pack_flame_wave_hit_checks_are_target_local(self):
        battle_state = self._base_battle_state()
        outcomes = [{'is_hit': True}, {'is_hit': False}, {'is_hit': True}]
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value={'success': True, 'skill_id': 'flame_wave', 'log': 'cast', 'damage': 10, 'heal': 0, 'effects': [], 'target_kind': 'enemy', 'direct_damage_skill': True}), \
             patch('game.combat.resolve_hit_check', side_effect=outcomes):
            result = process_skill_turn('flame_wave', self._base_player(), self._base_mob(), battle_state, user_id=1, include_enemy_response=False)
        self.assertEqual([u['hp'] for u in battle_state['enemy_units']], [30, 35, 20])
        per_target = result['skill_result']['direct_damage_result']['per_target']
        self.assertEqual([p['is_hit'] for p in per_target], [True, False, True])
        self.assertEqual(result['skill_result']['log'], t('battle.pack_fanout_skill_targets_hit', 'ru', skill_name=get_skill_name('flame_wave', 'ru'), count=2))

    def test_all_miss_fanout_log_does_not_keep_stale_prehit_damage_text(self):
        battle_state = self._base_battle_state()
        stale_log = '🔥 Flame Wave deals 99 damage (stale pre-hit text)'
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value={'success': True, 'skill_id': 'flame_wave', 'log': stale_log, 'damage': 10, 'heal': 0, 'effects': [], 'target_kind': 'enemy', 'direct_damage_skill': True}), \
             patch('game.combat.resolve_hit_check', side_effect=[{'is_hit': False}, {'is_hit': False}, {'is_hit': False}]):
            result = process_skill_turn('flame_wave', self._base_player(), self._base_mob(), battle_state, user_id=1, lang='en', include_enemy_response=False)
        self.assertEqual(result['skill_result']['damage'], 0)
        self.assertEqual(result['skill_result']['direct_damage_result']['targets_hit'], 0)
        self.assertNotIn('99 damage', result['skill_result']['log'])
        self.assertEqual(
            result['skill_result']['log'],
            t('battle.pack_fanout_skill_targets_hit', 'en', skill_name=get_skill_name('flame_wave', 'en'), count=0),
        )

    def test_partial_hit_fanout_log_uses_resolved_summary_only(self):
        battle_state = self._base_battle_state()
        stale_log = '🔥 Flame Wave deals 777 damage (stale pre-hit text)'
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value={'success': True, 'skill_id': 'flame_wave', 'log': stale_log, 'damage': 10, 'heal': 0, 'effects': [], 'target_kind': 'enemy', 'direct_damage_skill': True}), \
             patch('game.combat.resolve_hit_check', side_effect=[{'is_hit': True}, {'is_hit': False}, {'is_hit': True}]):
            result = process_skill_turn('flame_wave', self._base_player(), self._base_mob(), battle_state, user_id=1, lang='en', include_enemy_response=False)
        self.assertEqual(result['skill_result']['direct_damage_result']['targets_hit'], 2)
        self.assertNotIn('777 damage', result['skill_result']['log'])
        self.assertEqual(
            result['skill_result']['log'],
            t('battle.pack_fanout_skill_targets_hit', 'en', skill_name=get_skill_name('flame_wave', 'en'), count=2),
        )

    def test_kill_non_active_enemy_marks_dead(self):
        battle_state = self._base_battle_state()
        battle_state['active_enemy_unit_id'] = 'u1'
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value={'success': True, 'skill_id': 'flame_wave', 'log': 'cast', 'damage': 34, 'heal': 0, 'effects': [], 'target_kind': 'enemy', 'direct_damage_skill': True}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            process_skill_turn('flame_wave', self._base_player(), self._base_mob(), battle_state, user_id=1, include_enemy_response=False)
        self.assertTrue(battle_state['enemy_units'][2]['dead'])
        self.assertFalse(battle_state['mob_dead'])

    def test_kill_active_target_switches_to_next_living(self):
        battle_state = self._base_battle_state()
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value={'success': True, 'skill_id': 'flame_wave', 'log': 'cast', 'damage': 40, 'heal': 0, 'effects': [], 'target_kind': 'enemy', 'direct_damage_skill': True}), \
             patch('game.combat.resolve_hit_check', side_effect=[{'is_hit': True}, {'is_hit': False}, {'is_hit': False}]):
            process_skill_turn('flame_wave', self._base_player(), self._base_mob(), battle_state, user_id=1, include_enemy_response=False)
        self.assertEqual(battle_state['active_enemy_unit_id'], 'u2')
        self.assertEqual(battle_state['mob_hp'], 35)

    def test_kill_all_enemies_sets_mob_dead(self):
        battle_state = self._base_battle_state()
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value={'success': True, 'skill_id': 'flame_wave', 'log': 'cast', 'damage': 100, 'heal': 0, 'effects': [], 'target_kind': 'enemy', 'direct_damage_skill': True}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            process_skill_turn('flame_wave', self._base_player(), self._base_mob(), battle_state, user_id=1, include_enemy_response=False)
        self.assertTrue(battle_state['mob_dead'])

    def test_non_aoe_skill_in_pack_remains_single_target(self):
        battle_state = self._base_battle_state()
        with patch('game.combat.precheck_skill_use', return_value={'success': True}), \
             patch('game.combat.use_skill', return_value={'success': True, 'skill_id': 'fireball', 'log': 'cast', 'damage': 10, 'heal': 0, 'effects': [], 'target_kind': 'enemy', 'direct_damage_skill': True}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            process_skill_turn('fireball', self._base_player(), self._base_mob(), battle_state, user_id=1, include_enemy_response=False)
        self.assertEqual([u['hp'] for u in battle_state['enemy_units']], [40, 35, 30])
        self.assertEqual(battle_state['mob_hp'], 30)

    def test_generic_fanout_summary_locale_key_uses_skill_name(self):
        line = t(
            'battle.pack_fanout_skill_targets_hit',
            'en',
            skill_name=get_skill_name('flame_wave', 'en'),
            count=3,
        )
        self.assertIn('Flame Wave', line)
        self.assertIn('3', line)
