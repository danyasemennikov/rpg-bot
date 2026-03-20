import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from game import combat
from game import skill_engine
from handlers import battle as battle_handler


class _DummyQuery:
    def __init__(self, data: str, user_id: int = 101):
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()


class _DummyUpdate:
    def __init__(self, data: str, user_id: int = 101):
        self.callback_query = _DummyQuery(data, user_id)


class _DummyContext:
    def __init__(self, battle_state: dict, mob: dict):
        self.user_data = {
            'battle': battle_state,
            'battle_mob': mob,
        }


class CombatRegressionTests(unittest.TestCase):
    def test_invincible_blocks_enemy_response_damage_through_combat_core(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 8, 'damage_max': 8}
        state = {'player_hp': 100, 'mob_hp': 100, 'mob_effects': [], 'invincible_turns': 1}

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 8, 'player_hp': 92}):
            log = combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        self.assertEqual(state['player_hp'], 100)
        self.assertEqual(state['invincible_turns'], 0)
        self.assertTrue(len(log) > 0)
    
    def test_invincible_is_consumed_before_natural_dodge_path(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 8, 'damage_max': 8}
        state = {'player_hp': 100, 'mob_hp': 100, 'mob_effects': [], 'invincible_turns': 1}

        with patch('game.combat.mob_attack') as mob_attack_mock:
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        mob_attack_mock.assert_not_called()
        self.assertEqual(state['invincible_turns'], 0)

    def test_dodge_buff_prevents_enemy_response_damage_through_combat_core(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 8, 'damage_max': 8}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'dodge_buff_turns': 1,
            'dodge_buff_value': 100,
        }

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 8, 'player_hp': 92}):
            log = combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        self.assertEqual(state['player_hp'], 100)
        self.assertEqual(state['dodge_buff_turns'], 0)
        self.assertTrue(len(log) > 0)

    def test_dodge_buff_is_consumed_before_natural_dodge_short_circuit(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 8, 'damage_max': 8}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'dodge_buff_turns': 1,
            'dodge_buff_value': 0,
        }

        with patch('game.combat.mob_attack', return_value={'type': 'dodge', 'damage': 0, 'player_hp': 100}):
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        self.assertEqual(state['dodge_buff_turns'], 0)

    def test_defense_buff_mitigation_is_applied_in_centralized_enemy_damage_path(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 10, 'damage_max': 10}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'defense_buff_turns': 2,
            'defense_buff_value': 50,
        }

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 10, 'player_hp': 90}):
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        self.assertEqual(state['player_hp'], 95)
        self.assertEqual(state['defense_buff_turns'], 2)

    def test_fire_shield_uses_centralized_post_hit_path_and_skips_on_prevented_hit(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 10, 'damage_max': 10}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'fire_shield_turns': 2,
            'fire_shield_value': 6,
            'invincible_turns': 1,
        }

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 10, 'player_hp': 90}):
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        # Первый вход: invincible блокирует, щит не тратится.
        self.assertEqual(state['mob_hp'], 100)
        self.assertEqual(state['fire_shield_turns'], 2)

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 10, 'player_hp': 90}):
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        # Второй вход: удар прошёл и щит сработал в post-hit секции.
        self.assertEqual(state['mob_hp'], 94)
        self.assertEqual(state['fire_shield_turns'], 1)

    def test_defensive_buffs_not_consumed_when_enemy_dies_before_enemy_response(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 3,
            'mob_effects': [],
            'invincible_turns': 1,
            'dodge_buff_turns': 2,
            'dodge_buff_value': 50,
            'defense_buff_turns': 2,
            'defense_buff_value': 25,
            'disarm_turns': 2,
            'disarm_value': 30,
            'fire_shield_turns': 2,
            'fire_shield_value': 4,
            'log': [],
            'turn': 1,
        }

        with patch('game.combat.use_skill', return_value={'success': True, 'log': 'cast', 'damage': 3, 'heal': 0, 'effects': []}), \
             patch('game.combat.resolve_enemy_response') as response_mock:
            result = combat.process_skill_turn('fireball', player, mob, battle_state, user_id=101, lang='ru')

        self.assertEqual(response_mock.call_count, 0)
        self.assertEqual(result['battle_state']['invincible_turns'], 1)
        self.assertEqual(result['battle_state']['dodge_buff_turns'], 2)
        self.assertEqual(result['battle_state']['defense_buff_turns'], 2)
        self.assertEqual(result['battle_state']['disarm_turns'], 2)
        self.assertEqual(result['battle_state']['fire_shield_turns'], 2)

    def test_disarm_is_applied_in_centralized_enemy_damage_path(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 10, 'damage_max': 10}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'disarm_turns': 1,
            'disarm_value': 50,
        }

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 10, 'player_hp': 90}):
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        self.assertEqual(state['player_hp'], 95)
        self.assertEqual(state['disarm_turns'], 0)

    def test_disarm_is_not_consumed_when_invincible_short_circuits_enemy_response(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 10, 'damage_max': 10}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'invincible_turns': 1,
            'disarm_turns': 1,
            'disarm_value': 50,
        }

        with patch('game.combat.mob_attack') as mob_attack_mock:
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        mob_attack_mock.assert_not_called()
        self.assertEqual(state['invincible_turns'], 0)
        self.assertEqual(state['disarm_turns'], 1)

    def test_disarm_is_not_consumed_when_dodge_buff_short_circuits_enemy_response(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 10, 'damage_max': 10}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'dodge_buff_turns': 1,
            'dodge_buff_value': 100,
            'disarm_turns': 1,
            'disarm_value': 50,
        }

        with patch('game.combat.mob_attack') as mob_attack_mock:
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        mob_attack_mock.assert_not_called()
        self.assertEqual(state['dodge_buff_turns'], 0)
        self.assertEqual(state['disarm_turns'], 1)

    def test_disarm_ordering_remains_compatible_with_defense_buff_and_fire_shield(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 10, 'damage_max': 10}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'defense_buff_turns': 2,
            'defense_buff_value': 20,
            'disarm_turns': 2,
            'disarm_value': 50,
            'fire_shield_turns': 2,
            'fire_shield_value': 6,
        }

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 10, 'player_hp': 90}):
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        # 10 -> defense 20% => 8 -> disarm 50% => 4
        self.assertEqual(state['player_hp'], 96)
        self.assertEqual(state['disarm_turns'], 1)
        self.assertEqual(state['fire_shield_turns'], 1)
        self.assertEqual(state['mob_hp'], 94)

    def test_parry_reflects_enemy_response_damage_and_player_takes_no_damage(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 12, 'damage_max': 12}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'parry_active': True,
            'parry_value': 1.0,
        }

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 12, 'player_hp': 88}):
            log = combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        self.assertEqual(state['player_hp'], 100)
        self.assertEqual(state['mob_hp'], 88)
        self.assertIn('12', ''.join(log))

    def test_parry_is_consumed_once_after_triggering_enemy_response(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 10, 'damage_max': 10}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'parry_active': True,
            'parry_value': 1.0,
        }

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 10, 'player_hp': 90}):
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        self.assertFalse(state['parry_active'])

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 10, 'player_hp': 90}):
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        self.assertEqual(state['player_hp'], 90)
        self.assertEqual(state['mob_hp'], 90)

    def test_parry_is_not_consumed_when_enemy_response_never_happens(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 10, 'damage_max': 10}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [{'type': 'stun', 'turns': 1, 'value': 1}],
            'parry_active': True,
            'parry_value': 1.0,
        }

        with patch('game.combat.mob_attack') as mob_attack_mock:
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        mob_attack_mock.assert_not_called()
        self.assertTrue(state['parry_active'])
        self.assertEqual(state['mob_hp'], 100)

    def test_parry_ordering_remains_compatible_with_enemy_response_flow(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 10, 'damage_max': 10}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'parry_active': True,
            'parry_value': 1.0,
            'invincible_turns': 1,
        }

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 10, 'player_hp': 90}) as mob_attack_mock:
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        mob_attack_mock.assert_called_once()
        self.assertEqual(state['player_hp'], 100)
        self.assertEqual(state['mob_hp'], 90)
        # invincible остаётся нетронутым: parry отрабатывает в trigger-слое enemy response.
        self.assertEqual(state['invincible_turns'], 1)

    def test_parry_change_does_not_affect_other_defensive_mechanics(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 10, 'damage_max': 10}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'invincible_turns': 1,
            'disarm_turns': 1,
            'disarm_value': 50,
            'fire_shield_turns': 1,
            'fire_shield_value': 4,
        }

        with patch('game.combat.mob_attack') as mob_attack_mock:
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        mob_attack_mock.assert_not_called()
        self.assertEqual(state['player_hp'], 100)
        self.assertEqual(state['mob_hp'], 100)
        self.assertEqual(state['invincible_turns'], 0)
        self.assertEqual(state['disarm_turns'], 1)
        self.assertEqual(state['fire_shield_turns'], 1)

    def test_post_action_resurrection_tick_decrements_in_normal_attack_flow(self):
        player = {
            'hp': 120,
            'strength': 10,
            'agility': 10,
            'intuition': 10,
            'vitality': 10,
            'wisdom': 10,
            'luck': 10,
        }
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'mob_hp': 100,
            'player_hp': 120,
            'player_goes_first': True,
            'weapon_type': 'melee',
            'weapon_damage': 10,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'blessing_turns': 0,
            'blessing_value': 0,
            'resurrection_active': True,
            'resurrection_turns': 3,
            'turn': 1,
        }

        with patch('game.combat.apply_mob_effect_ticks', return_value=[]), \
             patch('game.combat.player_attack', return_value={'damage': 7, 'is_crit': False, 'mob_dead': False}), \
             patch('game.combat.resolve_enemy_response', return_value=[]), \
             patch('game.combat.apply_player_buffs', return_value=''):
            result = combat.process_turn(player, mob, battle_state, lang='ru', user_id=101)

        self.assertTrue(result['resurrection_active'])
        self.assertEqual(result['resurrection_turns'], 2)

    def test_post_action_resurrection_tick_decrements_in_skill_flow(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 50,
            'mob_effects': [],
            'resurrection_active': True,
            'resurrection_turns': 4,
            'log': [],
            'turn': 1,
        }

        with patch('game.combat.use_skill', return_value={'success': True, 'log': 'cast', 'damage': 5, 'heal': 0, 'effects': []}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('fireball', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(result['success'])
        self.assertTrue(result['battle_state']['resurrection_active'])
        self.assertEqual(result['battle_state']['resurrection_turns'], 3)

    def test_post_action_resurrection_tick_expires_buff_on_zero(self):
        state = {'resurrection_active': True, 'resurrection_turns': 1, 'player_hp': 50}

        combat.tick_post_action_timed_trigger_buffs(state)

        self.assertFalse(state['resurrection_active'])
        self.assertEqual(state['resurrection_turns'], 0)

    def test_post_action_resurrection_tick_does_nothing_when_already_expired(self):
        state = {'resurrection_active': False, 'resurrection_turns': 0}

        combat.tick_post_action_timed_trigger_buffs(state)

        self.assertFalse(state['resurrection_active'])
        self.assertEqual(state['resurrection_turns'], 0)

    def test_post_action_resurrection_tick_keeps_buff_for_death_resolution_window(self):
        state = {'resurrection_active': True, 'resurrection_turns': 1, 'player_hp': 0}

        combat.tick_post_action_timed_trigger_buffs(state)

        self.assertTrue(state['resurrection_active'])
        self.assertEqual(state['resurrection_turns'], 0)

    def test_normal_attack_triggers_enemy_response_once_when_battle_continues(self):
        player = {
            'hp': 120,
            'strength': 10,
            'agility': 10,
            'intuition': 10,
            'vitality': 10,
            'wisdom': 10,
            'luck': 10,
        }
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'mob_hp': 100,
            'player_hp': 120,
            'player_goes_first': True,
            'weapon_type': 'melee',
            'weapon_damage': 10,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'blessing_turns': 0,
            'blessing_value': 0,
            'turn': 1,
        }

        with patch('game.combat.apply_mob_effect_ticks', return_value=[]), \
             patch('game.combat.player_attack', return_value={'damage': 7, 'is_crit': False, 'mob_dead': False}), \
             patch('game.combat.resolve_enemy_response', return_value=['enemy attack']) as response_mock, \
             patch('game.combat.apply_player_buffs', return_value=''):
            result = combat.process_turn(player, mob, battle_state, lang='ru', user_id=101)

        self.assertFalse(result['mob_dead'])
        self.assertEqual(response_mock.call_count, 1)

    def test_normal_attack_uses_mob_effect_ticks_before_enemy_response(self):
        player = {
            'hp': 120,
            'strength': 10,
            'agility': 10,
            'intuition': 10,
            'vitality': 10,
            'wisdom': 10,
            'luck': 10,
        }
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'mob_hp': 100,
            'player_hp': 120,
            'player_goes_first': True,
            'weapon_type': 'melee',
            'weapon_damage': 10,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'blessing_turns': 0,
            'blessing_value': 0,
            'turn': 1,
        }
        call_order = []

        with patch('game.combat.apply_mob_effect_ticks', side_effect=lambda *_args, **_kwargs: call_order.append('mob_ticks') or []), \
             patch('game.combat.player_attack', return_value={'damage': 7, 'is_crit': False, 'mob_dead': False}), \
             patch('game.combat.resolve_enemy_response', side_effect=lambda *_args, **_kwargs: call_order.append('enemy_response') or []), \
             patch('game.combat.apply_player_buffs', return_value=''):
            combat.process_turn(player, mob, battle_state, lang='ru', user_id=101)

        self.assertEqual(call_order, ['mob_ticks', 'enemy_response'])

    def test_normal_attack_applies_player_buffs_after_exchange(self):
        player = {
            'hp': 120,
            'strength': 10,
            'agility': 10,
            'intuition': 10,
            'vitality': 10,
            'wisdom': 10,
            'luck': 10,
        }
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'mob_hp': 100,
            'player_hp': 120,
            'player_goes_first': True,
            'weapon_type': 'melee',
            'weapon_damage': 10,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'blessing_turns': 0,
            'blessing_value': 0,
            'turn': 1,
        }
        call_order = []

        with patch('game.combat.apply_mob_effect_ticks', return_value=[]), \
             patch('game.combat.player_attack', return_value={'damage': 7, 'is_crit': False, 'mob_dead': False}), \
             patch('game.combat.resolve_enemy_response', side_effect=lambda *_args, **_kwargs: call_order.append('enemy_response') or []), \
             patch('game.combat.apply_player_buffs', side_effect=lambda *_args, **_kwargs: call_order.append('player_buffs') or ''):
            combat.process_turn(player, mob, battle_state, lang='ru', user_id=101)

        self.assertEqual(call_order, ['enemy_response', 'player_buffs'])

    def test_skill_turn_uses_pre_enemy_response_ticks_before_enemy_response(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 50,
            'mob_effects': [],
            'log': [],
            'turn': 1,
        }
        call_order = []

        with patch('game.combat.use_skill', return_value={'success': True, 'log': 'cast', 'damage': 5, 'heal': 0, 'effects': []}), \
             patch('game.combat.apply_pre_enemy_response_ticks', side_effect=lambda *_args, **_kwargs: call_order.append('pre_ticks') or []), \
             patch('game.combat.resolve_enemy_response', side_effect=lambda *_args, **_kwargs: call_order.append('enemy_response') or []):
            result = combat.process_skill_turn('fireball', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(result['success'])
        self.assertEqual(call_order, ['pre_ticks', 'enemy_response'])

    def test_skill_turn_skips_enemy_response_if_mob_dies_from_skill(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 3,
            'mob_effects': [],
            'log': [],
            'turn': 1,
        }

        with patch('game.combat.use_skill', return_value={'success': True, 'log': 'cast', 'damage': 3, 'heal': 0, 'effects': []}), \
             patch('game.combat.apply_pre_enemy_response_ticks') as pre_ticks_mock, \
             patch('game.combat.resolve_enemy_response') as response_mock:
            result = combat.process_skill_turn('fireball', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(result['battle_state']['mob_dead'])
        self.assertEqual(pre_ticks_mock.call_count, 0)
        self.assertEqual(response_mock.call_count, 0)

    def test_skill_turn_pre_enemy_ticks_can_kill_mob_and_skip_enemy_response(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 10,
            'mob_effects': [],
            'log': [],
            'turn': 7,
        }

        def pre_ticks_side_effect(_mob, state):
            state['mob_hp'] = 0
            return ['dot']

        with patch('game.combat.use_skill', return_value={'success': True, 'log': 'cast', 'damage': 0, 'heal': 0, 'effects': []}), \
             patch('game.combat.apply_pre_enemy_response_ticks', side_effect=pre_ticks_side_effect), \
             patch('game.combat.resolve_enemy_response') as response_mock:
            result = combat.process_skill_turn('fireball', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(result['success'])
        self.assertTrue(result['battle_state']['mob_dead'])
        self.assertEqual(result['battle_state']['turn'], 7)
        self.assertEqual(result['battle_state'].get('resurrection_turns', 0), 0)
        self.assertEqual(response_mock.call_count, 0)

    def test_resurrection_with_one_turn_left_expires_after_survived_action(self):
        player = {
            'hp': 120,
            'strength': 10,
            'agility': 10,
            'intuition': 10,
            'vitality': 10,
            'wisdom': 10,
            'luck': 10,
        }
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'mob_hp': 100,
            'player_hp': 120,
            'player_goes_first': True,
            'weapon_type': 'melee',
            'weapon_damage': 10,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'blessing_turns': 0,
            'blessing_value': 0,
            'resurrection_active': True,
            'resurrection_turns': 1,
            'turn': 1,
        }

        with patch('game.combat.apply_mob_effect_ticks', return_value=[]), \
             patch('game.combat.player_attack', return_value={'damage': 7, 'is_crit': False, 'mob_dead': False}), \
             patch('game.combat.resolve_enemy_response', return_value=[]), \
             patch('game.combat.apply_player_buffs', return_value=''):
            result = combat.process_turn(player, mob, battle_state, lang='ru', user_id=101)

        self.assertFalse(result['resurrection_active'])
        self.assertEqual(result['resurrection_turns'], 0)

    def test_casting_resurrection_does_not_consume_first_runtime_window(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 50,
            'mob_effects': [],
            'resurrection_active': False,
            'resurrection_turns': 0,
            'log': [],
            'turn': 1,
        }

        def cast_res_side_effect(skill_id, _player_state, _mob_state, state, _user_id, _lang):
            self.assertEqual(skill_id, 'resurrection')
            state['resurrection_active'] = True
            state['resurrection_turns'] = 5
            state['resurrection_hp'] = 50
            return {'success': True, 'log': 'cast', 'damage': 0, 'heal': 0, 'effects': []}

        with patch('game.combat.use_skill', side_effect=cast_res_side_effect), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('resurrection', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(result['success'])
        self.assertTrue(result['battle_state']['resurrection_active'])
        self.assertEqual(result['battle_state']['resurrection_turns'], 5)

    def test_guaranteed_crit_is_consumed_by_normal_attack_in_combat_core(self):
        player = {
            'hp': 120,
            'strength': 10,
            'agility': 10,
            'intuition': 10,
            'vitality': 10,
            'wisdom': 10,
            'luck': 10,
        }
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'mob_hp': 100,
            'player_hp': 120,
            'player_goes_first': True,
            'weapon_type': 'melee',
            'weapon_damage': 10,
            'guaranteed_crit_turns': 1,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'blessing_turns': 0,
            'blessing_value': 0,
            'turn': 1,
        }

        with patch('game.combat.apply_mob_effect_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]), \
             patch('game.combat.apply_player_buffs', return_value=''):
            result = combat.process_turn(player, mob, battle_state, lang='ru', user_id=101)

        self.assertEqual(result['guaranteed_crit_turns'], 0)
        self.assertLess(result['mob_hp'], 100)

    def test_guaranteed_crit_is_consumed_by_damage_skill_but_not_by_non_damage_skill(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 50,
            'mob_effects': [],
            'guaranteed_crit_turns': 1,
            'log': [],
            'turn': 1,
        }

        with patch('game.combat.use_skill', return_value={'success': True, 'log': 'cast', 'damage': 10, 'heal': 0, 'effects': []}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result_damage = combat.process_skill_turn('fireball', player, mob, dict(battle_state), user_id=101, lang='ru')

        with patch('game.combat.use_skill', return_value={'success': True, 'log': 'cast', 'damage': 0, 'heal': 15, 'effects': []}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result_heal = combat.process_skill_turn('heal', player, mob, dict(battle_state), user_id=101, lang='ru')

        self.assertEqual(result_damage['battle_state']['guaranteed_crit_turns'], 0)
        self.assertEqual(result_heal['battle_state']['guaranteed_crit_turns'], 1)

    def test_hunters_mark_bonus_applies_to_normal_attack_and_decrements_on_use(self):
        result = combat.apply_direct_damage_action_modifiers(
            {'hunters_mark_turns': 2, 'hunters_mark_value': 50, 'vulnerability_turns': 0, 'vulnerability_value': 0, 'guaranteed_crit_turns': 0},
            20,
            can_consume_guaranteed_crit=False,
        )
        self.assertEqual(result['damage'], 30)

    def test_hunters_mark_bonus_applies_to_damage_skill_and_decrements_only_on_damage(self):
        state = {
            'guaranteed_crit_turns': 0,
            'hunters_mark_turns': 2,
            'hunters_mark_value': 50,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
        }

        damage_result = combat.apply_direct_damage_action_modifiers(state, 20, can_consume_guaranteed_crit=True)
        turns_after_damage = state['hunters_mark_turns']
        heal_result = combat.apply_direct_damage_action_modifiers(state, 0, can_consume_guaranteed_crit=True)

        self.assertEqual(damage_result['damage'], 30)
        self.assertEqual(turns_after_damage, 1)
        self.assertEqual(heal_result['damage'], 0)
        self.assertEqual(state['hunters_mark_turns'], 1)

    def test_vulnerability_bonus_applies_to_normal_attack_and_decrements_on_use(self):
        state = {
            'guaranteed_crit_turns': 0,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 2,
            'vulnerability_value': 25,
        }
        result = combat.apply_direct_damage_action_modifiers(state, 20, can_consume_guaranteed_crit=False)
        self.assertEqual(result['damage'], 25)
        self.assertEqual(state['vulnerability_turns'], 1)

    def test_vulnerability_bonus_applies_to_damage_skill_and_decrements_only_on_damage(self):
        state = {
            'guaranteed_crit_turns': 0,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 2,
            'vulnerability_value': 25,
        }
        damage_result = combat.apply_direct_damage_action_modifiers(state, 20, can_consume_guaranteed_crit=True)
        turns_after_damage = state['vulnerability_turns']
        control_result = combat.apply_direct_damage_action_modifiers(state, 0, can_consume_guaranteed_crit=True)

        self.assertEqual(damage_result['damage'], 25)
        self.assertEqual(turns_after_damage, 1)
        self.assertEqual(control_result['damage'], 0)
        self.assertEqual(state['vulnerability_turns'], 1)

    def test_non_damage_skill_action_does_not_consume_direct_damage_modifiers(self):
        state = {
            'guaranteed_crit_turns': 1,
            'hunters_mark_turns': 2,
            'hunters_mark_value': 30,
            'vulnerability_turns': 2,
            'vulnerability_value': 30,
        }
        result = combat.apply_direct_damage_action_modifiers(state, 0, can_consume_guaranteed_crit=True)

        self.assertEqual(result['damage'], 0)
        self.assertEqual(state['guaranteed_crit_turns'], 1)
        self.assertEqual(state['hunters_mark_turns'], 2)
        self.assertEqual(state['vulnerability_turns'], 2)

    def test_damage_skill_log_matches_final_modified_damage(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 200,
            'mob_effects': [],
            'guaranteed_crit_turns': 1,
            'hunters_mark_turns': 1,
            'hunters_mark_value': 20,
            'vulnerability_turns': 1,
            'vulnerability_value': 20,
            'log': [],
            'turn': 1,
        }

        with patch('game.combat.use_skill', return_value={
                'success': True,
                'log': '',
                'damage': 10,
                'heal': 0,
                'effects': [],
                'direct_damage_skill': True,
                'log_key': 'skills.log_damage',
                'log_params': {'name': 'Fireball', 'dmg': 10, 'cost': 5},
                'log_suffixes': [],
                'lifesteal_ratio': 0.0,
            }), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('fireball', player, mob, battle_state, user_id=101, lang='ru')

        # 10 -> crit 25 -> hunter 30 -> vulnerability 36
        self.assertEqual(result['skill_result']['damage'], 36)
        self.assertIn('36', result['battle_state']['log'][-1])
        self.assertNotIn('10', result['battle_state']['log'][-1])

    def test_lifesteal_heal_stays_consistent_with_final_modified_damage(self):
        player = {'hp': 40, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 40,
            'player_max_hp': 200,
            'player_mana': 80,
            'mob_hp': 200,
            'mob_effects': [],
            'guaranteed_crit_turns': 1,
            'hunters_mark_turns': 1,
            'hunters_mark_value': 20,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'log': [],
            'turn': 1,
        }

        with patch('game.combat.use_skill', return_value={
                'success': True,
                'log': '',
                'damage': 10,
                'heal': 3,
                'effects': [],
                'direct_damage_skill': True,
                'log_key': 'skills.log_damage',
                'log_params': {'name': 'Drain', 'dmg': 10, 'cost': 5},
                'log_suffixes': [],
                'lifesteal_ratio': 0.30,
            }), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('drain', player, mob, battle_state, user_id=101, lang='ru')

        # 10 -> crit 25 -> hunter 30, heal scales from 3 to 9
        self.assertEqual(result['skill_result']['damage'], 30)
        self.assertEqual(result['skill_result']['heal'], 9)
        self.assertEqual(result['battle_state']['player_hp'], 49)
        self.assertIn('30', result['battle_state']['log'][-1])
        self.assertIn('❤️+9', result['battle_state']['log'][-1])

    def test_non_damage_skill_flow_keeps_existing_log_unchanged(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 200,
            'mob_effects': [],
            'guaranteed_crit_turns': 1,
            'hunters_mark_turns': 1,
            'hunters_mark_value': 20,
            'vulnerability_turns': 1,
            'vulnerability_value': 20,
            'log': [],
            'turn': 1,
        }

        with patch('game.combat.use_skill', return_value={'success': True, 'log': 'Heal +15', 'damage': 0, 'heal': 15, 'effects': []}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('heal', player, mob, battle_state, user_id=101, lang='ru')

        self.assertEqual(result['battle_state']['log'][-1], 'Heal +15')

    def test_disarm_log_matches_final_modified_damage(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 200,
            'mob_effects': [],
            'guaranteed_crit_turns': 1,
            'hunters_mark_turns': 1,
            'hunters_mark_value': 20,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'log': [],
            'turn': 1,
        }

        with patch('game.combat.use_skill', return_value={
                'success': True,
                'log': '',
                'damage': 10,
                'heal': 0,
                'effects': [],
                'direct_damage_skill': True,
                'log_key': 'skills.log_damage_effect',
                'log_params': {'name': 'Disarm', 'dmg': 10, 'cost': 5},
                'log_suffixes': [],
                'lifesteal_ratio': 0.0,
            }), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('disarm', player, mob, battle_state, user_id=101, lang='ru')

        # 10 -> crit 25 -> hunter 30
        self.assertEqual(result['skill_result']['damage'], 30)
        self.assertIn('30', result['battle_state']['log'][-1])
        self.assertNotIn('10', result['battle_state']['log'][-1])

    def test_multi_hit_skill_with_modifiers_uses_consistent_final_log(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 300,
            'mob_effects': [],
            'guaranteed_crit_turns': 1,
            'hunters_mark_turns': 1,
            'hunters_mark_value': 20,
            'vulnerability_turns': 1,
            'vulnerability_value': 20,
            'log': [],
            'turn': 1,
        }

        with patch('game.combat.use_skill', return_value={
                'success': True,
                'log': '',
                'damage': 30,
                'heal': 0,
                'effects': [],
                'direct_damage_skill': True,
                'log_key': 'skills.log_damage_multi',
                'log_params': {'name': 'Flurry', 'hits': 3, 'parts': '8, 11, 11', 'total': 30, 'cost': 7},
                'log_suffixes': [],
                'lifesteal_ratio': 0.0,
            }), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('flurry', player, mob, battle_state, user_id=101, lang='ru')

        # 30 -> crit 75 -> hunter 90 -> vulnerability 108
        self.assertEqual(result['skill_result']['damage'], 108)
        final_log = result['battle_state']['log'][-1]
        self.assertIn('108', final_log)
        self.assertNotIn('[8, 11, 11]', final_log)


class SkillEngineRegressionTests(unittest.TestCase):
    def test_resurrection_skill_sets_runtime_turns_from_duration(self):
        player = {'mana': 200, 'wisdom': 25}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        battle_state = {'player_hp': 100, 'player_max_hp': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill(
                skill_id='resurrection',
                player=player,
                mob_state=mob_state,
                battle_state=battle_state,
                telegram_id=101,
                lang='ru',
            )

        self.assertTrue(result['success'])
        self.assertTrue(battle_state['resurrection_active'])
        self.assertEqual(battle_state['resurrection_turns'], 5)


class BattleHandlerRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_handler_attack_path_does_not_manually_consume_guaranteed_crit_before_process_turn(self):
        update = _DummyUpdate('battle_attack_wolf')
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 50,
            'player_max_mana': 100,
            'mob_hp': 40,
            'log': [],
            'weapon_id': 'unarmed',
            'guaranteed_crit_turns': 2,
            'mob_dead': False,
            'player_dead': False,
        }
        mob = {'id': 'wolf', 'defense': 0, 'hp': 100}
        context = _DummyContext(battle_state, mob)
        captured_turns = {}

        def process_turn_side_effect(_p, _mob, state, _lang, user_id=None):
            captured_turns['value'] = state.get('guaranteed_crit_turns')
            return dict(state, mob_dead=False, player_dead=False, log=['hit'])

        with patch('handlers.battle.get_player', return_value={'telegram_id': 101, 'hp': 100, 'mana': 50, 'lang': 'ru'}), \
             patch('handlers.battle.process_turn', side_effect=process_turn_side_effect), \
             patch('handlers.battle.tick_cooldowns'), \
             patch('handlers.battle.build_battle_message', return_value=('msg', None)), \
             patch('handlers.battle.safe_edit', new=AsyncMock()), \
             patch('handlers.battle.t', side_effect=lambda key, lang='ru', **kwargs: key):
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(captured_turns['value'], 2)

    async def test_normal_attack_kill_uses_victory_path_and_handler_does_not_reenter_enemy_response(self):
        update = _DummyUpdate('battle_attack_wolf')
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 50,
            'player_max_mana': 100,
            'mob_hp': 10,
            'log': [],
            'weapon_id': 'unarmed',
            'mob_dead': False,
            'player_dead': False,
        }
        mob = {'id': 'wolf', 'defense': 0, 'hp': 100}
        context = _DummyContext(battle_state, mob)

        post_turn_state = dict(battle_state)
        post_turn_state['mob_dead'] = True
        post_turn_state['player_dead'] = False

        with patch('handlers.battle.get_player', return_value={'telegram_id': 101, 'hp': 100, 'mana': 50, 'lang': 'ru'}), \
             patch('handlers.battle.process_turn', return_value=post_turn_state), \
             patch('handlers.battle.resolve_enemy_response') as response_mock, \
             patch('handlers.battle.tick_cooldowns'), \
             patch('handlers.battle.calc_rewards', return_value={'exp': 5, 'gold': 3, 'loot': []}), \
             patch('handlers.battle.apply_rewards', return_value={'leveled_up': False, 'new_level': 1}) as rewards_mock, \
             patch('handlers.battle.end_battle') as end_battle_mock, \
             patch('handlers.battle.add_mastery_exp', return_value={'leveled_up': False}), \
             patch('handlers.battle.safe_edit', new=AsyncMock()), \
             patch('handlers.battle.t', side_effect=lambda key, lang='ru', **kwargs: key), \
             patch('handlers.battle.get_mob_name', return_value='wolf'):
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(response_mock.call_count, 0)
        self.assertEqual(rewards_mock.call_count, 1)
        self.assertEqual(end_battle_mock.call_count, 1)
        self.assertNotIn('battle', context.user_data)
        self.assertNotIn('battle_mob', context.user_data)

    async def test_skill_action_calls_combat_core_once_when_battle_continues(self):
        update = _DummyUpdate('battle_skill_fireball|wolf')
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'player_max_mana': 100,
            'mob_hp': 50,
            'mob_effects': [],
            'log': [],
            'weapon_id': 'unarmed',
        }
        mob = {'id': 'wolf', 'defense': 0, 'hp': 100}
        context = _DummyContext(battle_state, mob)

        with patch('handlers.battle.get_player', return_value={'telegram_id': 101, 'hp': 100, 'mana': 80, 'lang': 'ru'}), \
             patch('handlers.battle.process_skill_turn', return_value={'success': True, 'skill_result': {'success': True, 'log': 'cast', 'damage': 5, 'heal': 0, 'effects': []}, 'battle_state': dict(battle_state, mob_hp=45, player_hp=90, player_dead=False, mob_dead=False, log=['cast', 'enemy'])}) as skill_turn_mock, \
             patch('handlers.battle.add_mastery_exp', return_value={'leveled_up': False}), \
             patch('handlers.battle.tick_cooldowns'), \
             patch('handlers.battle.get_connection') as conn_mock, \
             patch('handlers.battle.build_battle_message', return_value=('msg', None)), \
             patch('handlers.battle.safe_edit', new=AsyncMock()), \
             patch('handlers.battle.t', side_effect=lambda key, lang='ru', **kwargs: key):
            conn = Mock()
            conn.execute.return_value = None
            conn.commit.return_value = None
            conn.close.return_value = None
            conn_mock.return_value = conn
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(skill_turn_mock.call_count, 1)

    async def test_skill_flow_skips_enemy_response_if_pre_response_ticks_kill_mob(self):
        update = _DummyUpdate('battle_skill_fireball|wolf')
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'player_max_mana': 100,
            'mob_hp': 10,
            'mob_effects': [],
            'log': [],
            'weapon_id': 'unarmed',
        }
        mob = {'id': 'wolf', 'defense': 0, 'hp': 100}
        context = _DummyContext(battle_state, mob)

        with patch('handlers.battle.get_player', return_value={'telegram_id': 101, 'hp': 100, 'mana': 80, 'lang': 'ru', 'exp': 0, 'gold': 0, 'level': 1, 'stat_points': 0}), \
             patch('handlers.battle.process_skill_turn', return_value={'success': True, 'skill_result': {'success': True, 'log': 'cast', 'damage': 0, 'heal': 0, 'effects': []}, 'battle_state': dict(battle_state, mob_hp=0, mob_dead=True, player_dead=False, log=['cast', 'dot'])}) as skill_turn_mock, \
             patch('handlers.battle.calc_rewards', return_value={'exp': 0, 'gold': 0, 'loot': []}), \
             patch('handlers.battle.apply_rewards', return_value={'leveled_up': False, 'new_level': 1}), \
             patch('handlers.battle.end_battle'), \
             patch('handlers.battle.add_mastery_exp', return_value={'leveled_up': False}), \
             patch('handlers.battle.safe_edit', new=AsyncMock()), \
             patch('handlers.battle.t', side_effect=lambda key, lang='ru', **kwargs: key), \
             patch('handlers.battle.get_mob_name', return_value='wolf'):
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(skill_turn_mock.call_count, 1)

    async def test_skill_pre_ticks_kill_routes_to_victory_cleanup(self):
        update = _DummyUpdate('battle_skill_fireball|wolf')
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'player_max_mana': 100,
            'mob_hp': 10,
            'mob_effects': [],
            'log': [],
            'weapon_id': 'unarmed',
            'turn': 4,
        }
        mob = {'id': 'wolf', 'defense': 0, 'hp': 100}
        context = _DummyContext(battle_state, mob)

        def pre_ticks_side_effect(_mob, state):
            state['mob_hp'] = 0
            return ['dot']

        with patch('handlers.battle.get_player', return_value={'telegram_id': 101, 'hp': 100, 'mana': 80, 'lang': 'ru', 'exp': 0, 'gold': 0, 'level': 1, 'stat_points': 0}), \
             patch('game.combat.use_skill', return_value={'success': True, 'log': 'cast', 'damage': 0, 'heal': 0, 'effects': []}), \
             patch('game.combat.apply_pre_enemy_response_ticks', side_effect=pre_ticks_side_effect), \
             patch('game.combat.resolve_enemy_response') as response_mock, \
             patch('handlers.battle.calc_rewards', return_value={'exp': 0, 'gold': 0, 'loot': []}), \
             patch('handlers.battle.apply_rewards', return_value={'leveled_up': False, 'new_level': 1}) as rewards_mock, \
             patch('handlers.battle.end_battle') as end_battle_mock, \
             patch('handlers.battle.add_mastery_exp', return_value={'leveled_up': False}), \
             patch('handlers.battle.safe_edit', new=AsyncMock()), \
             patch('handlers.battle.t', side_effect=lambda key, lang='ru', **kwargs: key), \
             patch('handlers.battle.get_mob_name', return_value='wolf'):
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(response_mock.call_count, 0)
        self.assertEqual(rewards_mock.call_count, 1)
        self.assertEqual(end_battle_mock.call_count, 1)
        self.assertEqual(battle_state['turn'], 4)

    async def test_failed_flee_triggers_enemy_response_once(self):
        update = _DummyUpdate('battle_flee_wolf')
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 40,
            'player_max_mana': 100,
            'mob_hp': 50,
            'mob_effects': [],
            'log': [],
        }
        mob = {'id': 'wolf', 'defense': 0, 'hp': 100}
        context = _DummyContext(battle_state, mob)

        def enemy_response_side_effect(*args, **kwargs):
            args[2]['player_hp'] = 90
            return ['enemy']

        with patch('handlers.battle.get_player', return_value={'telegram_id': 101, 'hp': 100, 'mana': 40, 'lang': 'ru'}), \
             patch('handlers.battle.random.randint', return_value=95), \
             patch('handlers.battle.resolve_enemy_response', side_effect=enemy_response_side_effect) as response_mock, \
             patch('handlers.battle.build_battle_message', return_value=('msg', None)), \
             patch('handlers.battle.safe_edit', new=AsyncMock()), \
             patch('handlers.battle.t', side_effect=lambda key, lang='ru', **kwargs: key), \
             patch('handlers.battle.get_mob_name', return_value='wolf'):
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(response_mock.call_count, 1)

    async def test_enemy_response_not_triggered_if_mob_dies_before_response(self):
        update = _DummyUpdate('battle_skill_fireball|wolf')
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'player_max_mana': 100,
            'mob_hp': 3,
            'mob_effects': [],
            'log': [],
            'weapon_id': 'unarmed',
        }
        mob = {'id': 'wolf', 'defense': 0, 'hp': 100}
        context = _DummyContext(battle_state, mob)

        with patch('handlers.battle.get_player', return_value={'telegram_id': 101, 'hp': 100, 'mana': 80, 'lang': 'ru', 'exp': 0, 'gold': 0, 'level': 1, 'stat_points': 0}), \
             patch('handlers.battle.process_skill_turn', return_value={'success': True, 'skill_result': {'success': True, 'log': 'cast', 'damage': 3, 'heal': 0, 'effects': []}, 'battle_state': dict(battle_state, mob_hp=0, mob_dead=True, player_dead=False, log=['cast'])}) as skill_turn_mock, \
             patch('handlers.battle.calc_rewards', return_value={'exp': 0, 'gold': 0, 'loot': []}), \
             patch('handlers.battle.apply_rewards', return_value={'leveled_up': False, 'new_level': 1}), \
             patch('handlers.battle.end_battle'), \
             patch('handlers.battle.add_mastery_exp', return_value={'leveled_up': False}), \
             patch('handlers.battle.safe_edit', new=AsyncMock()), \
             patch('handlers.battle.t', side_effect=lambda key, lang='ru', **kwargs: key), \
             patch('handlers.battle.get_mob_name', return_value='wolf'):
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(skill_turn_mock.call_count, 1)

    async def test_skill_kill_uses_victory_path_and_skips_enemy_response(self):
        update = _DummyUpdate('battle_skill_fireball|wolf')
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'player_max_mana': 100,
            'mob_hp': 3,
            'mob_effects': [],
            'log': [],
            'weapon_id': 'unarmed',
        }
        mob = {'id': 'wolf', 'defense': 0, 'hp': 100}
        context = _DummyContext(battle_state, mob)

        with patch('handlers.battle.get_player', return_value={'telegram_id': 101, 'hp': 100, 'mana': 80, 'lang': 'ru', 'exp': 0, 'gold': 0, 'level': 1, 'stat_points': 0}), \
             patch('handlers.battle.process_skill_turn', return_value={'success': True, 'skill_result': {'success': True, 'log': 'cast', 'damage': 3, 'heal': 0, 'effects': []}, 'battle_state': dict(battle_state, mob_hp=0, mob_dead=True, player_dead=False, log=['cast'])}) as skill_turn_mock, \
             patch('handlers.battle.calc_rewards', return_value={'exp': 0, 'gold': 0, 'loot': []}), \
             patch('handlers.battle.apply_rewards', return_value={'leveled_up': False, 'new_level': 1}) as rewards_mock, \
             patch('handlers.battle.end_battle') as end_battle_mock, \
             patch('handlers.battle.add_mastery_exp', return_value={'leveled_up': False}), \
             patch('handlers.battle.safe_edit', new=AsyncMock()), \
             patch('handlers.battle.t', side_effect=lambda key, lang='ru', **kwargs: key), \
             patch('handlers.battle.get_mob_name', return_value='wolf'):
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(skill_turn_mock.call_count, 1)
        self.assertEqual(rewards_mock.call_count, 1)
        self.assertEqual(end_battle_mock.call_count, 1)

    async def test_player_death_after_enemy_response_uses_death_path(self):
        update = _DummyUpdate('battle_skill_fireball|wolf')
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'player_max_mana': 100,
            'mob_hp': 40,
            'mob_effects': [],
            'log': [],
            'weapon_id': 'unarmed',
            'resurrection_active': False,
            'resurrection_turns': 0,
        }
        mob = {'id': 'wolf', 'defense': 0, 'hp': 100}
        context = _DummyContext(battle_state, mob)

        with patch('handlers.battle.get_player', return_value={'telegram_id': 101, 'hp': 100, 'mana': 80, 'lang': 'ru'}), \
             patch('handlers.battle.process_skill_turn', return_value={'success': True, 'skill_result': {'success': True, 'log': 'cast', 'damage': 1, 'heal': 0, 'effects': []}, 'battle_state': dict(battle_state, player_hp=0, player_dead=True, mob_dead=False, log=['cast', 'enemy'])}), \
             patch('handlers.battle.add_mastery_exp', return_value={'leveled_up': False}), \
             patch('handlers.battle.tick_cooldowns'), \
             patch('handlers.battle.apply_death', return_value={'exp_loss': 1, 'gold_loss': 1}) as death_mock, \
             patch('handlers.battle.end_battle') as end_battle_mock, \
             patch('handlers.battle.apply_rewards') as rewards_mock, \
             patch('handlers.battle.get_connection') as conn_mock, \
             patch('handlers.battle.safe_edit', new=AsyncMock()), \
             patch('handlers.battle.t', side_effect=lambda key, lang='ru', **kwargs: key), \
             patch('handlers.battle.get_mob_name', return_value='wolf'):
            conn = Mock()
            conn.execute.return_value = None
            conn.commit.return_value = None
            conn.close.return_value = None
            conn_mock.return_value = conn
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(death_mock.call_count, 1)
        self.assertEqual(end_battle_mock.call_count, 1)
        self.assertEqual(rewards_mock.call_count, 0)
        self.assertNotIn('battle', context.user_data)
        self.assertNotIn('battle_mob', context.user_data)

    async def test_resurrection_prevents_death_path_and_restores_player_hp(self):
        update = _DummyUpdate('battle_skill_fireball|wolf')
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 200,
            'player_mana': 80,
            'player_max_mana': 100,
            'mob_hp': 40,
            'mob_effects': [],
            'log': [],
            'weapon_id': 'unarmed',
            'resurrection_active': True,
            'resurrection_hp': 30,
            'resurrection_turns': 2,
        }
        mob = {'id': 'wolf', 'defense': 0, 'hp': 100}
        context = _DummyContext(battle_state, mob)

        with patch('handlers.battle.get_player', return_value={'telegram_id': 101, 'hp': 100, 'mana': 80, 'lang': 'ru'}), \
             patch('handlers.battle.process_skill_turn', return_value={'success': True, 'skill_result': {'success': True, 'log': 'cast', 'damage': 1, 'heal': 0, 'effects': []}, 'battle_state': dict(battle_state, player_hp=0, player_dead=True, mob_dead=False, log=['cast', 'enemy'])}), \
             patch('handlers.battle.add_mastery_exp', return_value={'leveled_up': False}), \
             patch('handlers.battle.tick_cooldowns'), \
             patch('handlers.battle.apply_death') as death_mock, \
             patch('handlers.battle.end_battle') as end_battle_mock, \
             patch('handlers.battle.get_connection') as conn_mock, \
             patch('handlers.battle.build_battle_message', return_value=('msg', None)), \
             patch('handlers.battle.safe_edit', new=AsyncMock()), \
             patch('handlers.battle.t', side_effect=lambda key, lang='ru', **kwargs: key):
            conn = Mock()
            conn.execute.return_value = None
            conn.commit.return_value = None
            conn.close.return_value = None
            conn_mock.return_value = conn
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(death_mock.call_count, 0)
        self.assertEqual(end_battle_mock.call_count, 0)
        self.assertIn('battle', context.user_data)
        self.assertEqual(context.user_data['battle']['player_hp'], 60)
        self.assertFalse(context.user_data['battle']['resurrection_active'])
        self.assertEqual(context.user_data['battle']['resurrection_turns'], 2)

    async def test_resurrection_procs_on_last_window_when_turns_reaches_zero_on_death_action(self):
        update = _DummyUpdate('battle_skill_fireball|wolf')
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 200,
            'player_mana': 80,
            'player_max_mana': 100,
            'mob_hp': 40,
            'mob_effects': [],
            'log': [],
            'weapon_id': 'unarmed',
            'resurrection_active': True,
            'resurrection_hp': 30,
            'resurrection_turns': 0,
        }
        mob = {'id': 'wolf', 'defense': 0, 'hp': 100}
        context = _DummyContext(battle_state, mob)

        with patch('handlers.battle.get_player', return_value={'telegram_id': 101, 'hp': 100, 'mana': 80, 'lang': 'ru'}), \
             patch('handlers.battle.process_skill_turn', return_value={'success': True, 'skill_result': {'success': True, 'log': 'cast', 'damage': 1, 'heal': 0, 'effects': []}, 'battle_state': dict(battle_state, player_hp=0, player_dead=True, mob_dead=False, log=['cast', 'enemy'])}), \
             patch('handlers.battle.add_mastery_exp', return_value={'leveled_up': False}), \
             patch('handlers.battle.tick_cooldowns'), \
             patch('handlers.battle.apply_death') as death_mock, \
             patch('handlers.battle.end_battle') as end_battle_mock, \
             patch('handlers.battle.get_connection') as conn_mock, \
             patch('handlers.battle.build_battle_message', return_value=('msg', None)), \
             patch('handlers.battle.safe_edit', new=AsyncMock()), \
             patch('handlers.battle.t', side_effect=lambda key, lang='ru', **kwargs: key):
            conn = Mock()
            conn.execute.return_value = None
            conn.commit.return_value = None
            conn.close.return_value = None
            conn_mock.return_value = conn
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(death_mock.call_count, 0)
        self.assertEqual(end_battle_mock.call_count, 0)
        self.assertIn('battle', context.user_data)
        self.assertEqual(context.user_data['battle']['player_hp'], 60)


if __name__ == '__main__':
    unittest.main()
