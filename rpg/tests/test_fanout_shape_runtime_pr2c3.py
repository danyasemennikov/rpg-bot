import unittest
from unittest.mock import patch

from game.combat import resolve_pack_fanout_direct_damage_skill_action


class FanoutShapeRuntimePR2C3Tests(unittest.TestCase):
    def _base_player(self):
        return {'strength': 10, 'agility': 10, 'intuition': 20, 'vitality': 10, 'wisdom': 10, 'luck': 10}

    def _base_mob(self):
        return {'id': 'forest_wolf', 'mob_id': 'forest_wolf', 'defense': 0}

    def _base_skill_result(self):
        return {
            'success': True,
            'skill_id': 'future_cluster_skill',
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

    def _run_front_cluster(self, battle_state, resolve_side_effect=None):
        player = self._base_player()
        mob = self._base_mob()
        skill_result = self._base_skill_result()
        cluster_def = {'enemy_target_mode': 'pack_fanout', 'target_shape': 'front_line_cluster'}
        patches = [
            patch('game.combat.get_skill', return_value=cluster_def),
        ]
        if resolve_side_effect is None:
            patches.append(patch('game.combat.resolve_hit_check', return_value={'is_hit': True}))
        else:
            patches.append(patch('game.combat.resolve_hit_check', side_effect=resolve_side_effect))

        with patches[0], patches[1]:
            return resolve_pack_fanout_direct_damage_skill_action(player, mob, battle_state, skill_result, lang='en'), skill_result

    def test_dispatch_handles_all_enemies_shape(self):
        battle_state = self._state([
            {'unit_id': 'u1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False},
            {'unit_id': 'u2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False},
        ])
        skill_result = self._base_skill_result()
        with patch('game.combat.get_skill', return_value={'enemy_target_mode': 'pack_fanout', 'target_shape': 'all_enemies_in_small_pack'}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True}):
            result = resolve_pack_fanout_direct_damage_skill_action(self._base_player(), self._base_mob(), battle_state, skill_result, lang='en')
        self.assertTrue(result['handled'])
        self.assertEqual(skill_result['direct_damage_result']['target_shape'], 'all_enemies_in_small_pack')

    def test_dispatch_rejects_unsupported_shapes(self):
        battle_state = self._state([{'unit_id': 'u1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False}])
        for shape in ('back_line_single', 'single_active_enemy', 'unknown_shape'):
            with self.subTest(shape=shape):
                with patch('game.combat.get_skill', return_value={'enemy_target_mode': 'pack_fanout', 'target_shape': shape}):
                    result = resolve_pack_fanout_direct_damage_skill_action(
                        self._base_player(), self._base_mob(), dict(battle_state), dict(self._base_skill_result()), lang='en'
                    )
                self.assertFalse(result['handled'])

    def test_front_cluster_picks_frontmost_occupied_line_only(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'r1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'ranged'},
            {'unit_id': 's1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'support'},
        ], active_enemy_unit_id='r1')
        result, skill_result = self._run_front_cluster(battle_state)
        self.assertTrue(result['handled'])
        self.assertEqual([x['unit_id'] for x in skill_result['direct_damage_result']['per_target']], ['f1', 'f2'])
        self.assertEqual([u['hp'] for u in battle_state['enemy_units']], [10, 10, 20, 20, 20])

    def test_front_cluster_falls_to_melee_when_front_empty(self):
        battle_state = self._state([
            {'unit_id': 'm1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'm2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
            {'unit_id': 'r1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'ranged'},
        ], active_enemy_unit_id='r1')
        _, skill_result = self._run_front_cluster(battle_state)
        self.assertEqual([x['unit_id'] for x in skill_result['direct_damage_result']['per_target']], ['m1', 'm2'])
        self.assertEqual([u['hp'] for u in battle_state['enemy_units']], [10, 10, 20])

    def test_front_cluster_caps_at_4_targets(self):
        battle_state = self._state([
            {'unit_id': f'f{i}', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'}
            for i in range(1, 7)
        ], active_enemy_unit_id='f6')
        _, skill_result = self._run_front_cluster(battle_state)
        self.assertEqual(len(skill_result['direct_damage_result']['per_target']), 4)
        self.assertEqual(skill_result['direct_damage_result']['targets_total'], 4)

    def test_front_cluster_keeps_active_first_when_active_in_selected_line(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f3', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
        ], active_enemy_unit_id='f2')
        _, skill_result = self._run_front_cluster(battle_state)
        self.assertEqual([x['unit_id'] for x in skill_result['direct_damage_result']['per_target']], ['f2', 'f1', 'f3'])

    def test_front_cluster_does_not_retarget_selected_line_to_active_outside_line(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'm1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'melee'},
        ], active_enemy_unit_id='m1')
        _, skill_result = self._run_front_cluster(battle_state)
        self.assertEqual([x['unit_id'] for x in skill_result['direct_damage_result']['per_target']], ['f1', 'f2'])

    def test_front_cluster_result_metadata_contains_shape_and_counts(self):
        battle_state = self._state([
            {'unit_id': 'f1', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f2', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
            {'unit_id': 'f3', 'hp': 20, 'max_hp': 20, 'mob_effects': [], 'dead': False, 'formation_line': 'front'},
        ], active_enemy_unit_id='f1')
        _, skill_result = self._run_front_cluster(battle_state, resolve_side_effect=[{'is_hit': True}, {'is_hit': False}, {'is_hit': True}])
        meta = skill_result['direct_damage_result']
        self.assertTrue(meta['fanout'])
        self.assertEqual(meta['target_mode'], 'pack_fanout')
        self.assertEqual(meta['target_shape'], 'front_line_cluster')
        self.assertEqual(meta['targets_total'], 3)
        self.assertEqual(meta['targets_hit'], 2)
        self.assertEqual(len(meta['per_target']), 3)


if __name__ == '__main__':
    unittest.main()
