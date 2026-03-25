import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from game import combat
from game import skill_engine
from game import skills as game_skills
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
    def setUp(self):
        precheck_patcher = patch('game.combat.precheck_skill_use', return_value={'success': True, 'log': ''})
        self._precheck_mock = precheck_patcher.start()
        self.addCleanup(precheck_patcher.stop)

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

    def test_skill_flow_defense_buff_turns_one_expires_before_enemy_response(self):
        player = {'hp': 100, 'mana': 80, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 50,
            'mob_effects': [],
            'defense_buff_turns': 1,
            'defense_buff_value': 50,
            'log': [],
            'turn': 1,
        }

        def enemy_response_side_effect(_mob, _player_state, state, **_kwargs):
            # Старый контракт: бафф уже истёк к enemy response в skill flow.
            self.assertEqual(state['defense_buff_turns'], 0)
            result = combat.resolve_enemy_damage_against_player(
                state,
                lang='ru',
                mob_result={'type': 'mob_attack', 'damage': 10, 'player_hp': 90},
            )
            state['player_hp'] = max(0, state['player_hp'] - result['player_damage'])
            return []

        with patch('game.combat.use_skill', return_value={'success': True, 'log': 'cast', 'damage': 1, 'heal': 0, 'effects': []}), \
             patch('game.combat.resolve_enemy_response', side_effect=enemy_response_side_effect):
            result = combat.process_skill_turn('fireball', player, mob, battle_state, user_id=101, lang='ru')

        # Если бы защита не истекла заранее, было бы 95.
        self.assertEqual(result['battle_state']['player_hp'], 90)

    def test_skill_flow_berserk_and_blessing_tick_before_enemy_response(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 50,
            'mob_effects': [],
            'berserk_turns': 1,
            'blessing_turns': 1,
            'log': [],
            'turn': 1,
        }

        def enemy_response_side_effect(_mob, _player_state, state, **_kwargs):
            self.assertEqual(state['berserk_turns'], 0)
            self.assertEqual(state['blessing_turns'], 0)
            return []

        with patch('game.combat.use_skill', return_value={'success': True, 'log': 'cast', 'damage': 1, 'heal': 0, 'effects': []}), \
             patch('game.combat.resolve_enemy_response', side_effect=enemy_response_side_effect):
            combat.process_skill_turn('fireball', player, mob, battle_state, user_id=101, lang='ru')

    def test_normal_attack_flow_defense_buff_turns_one_still_applies_to_enemy_response(self):
        player = {
            'hp': 100,
            'strength': 10,
            'agility': 0,
            'intuition': 10,
            'vitality': 0,
            'wisdom': 0,
            'luck': 10,
        }
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'mob_hp': 100,
            'player_hp': 100,
            'player_goes_first': True,
            'weapon_type': 'melee',
            'weapon_damage': 10,
            'defense_buff_turns': 1,
            'defense_buff_value': 50,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'blessing_turns': 0,
            'blessing_value': 0,
            'turn': 1,
        }

        def enemy_response_side_effect(_mob, player_state, state, **_kwargs):
            result = combat.resolve_enemy_damage_against_player(
                state,
                lang='ru',
                mob_result={'type': 'mob_attack', 'damage': 10, 'player_hp': 90},
            )
            player_state['hp'] = max(0, player_state['hp'] - result['player_damage'])
            state['player_hp'] = player_state['hp']
            return []

        with patch('game.combat.apply_mob_effect_ticks', return_value=[]), \
             patch('game.combat.player_attack', return_value={'damage': 5, 'is_crit': False, 'mob_dead': False}), \
             patch('game.combat.resolve_enemy_response', side_effect=enemy_response_side_effect):
            result = combat.process_turn(player, mob, battle_state, lang='ru', user_id=101)

        # В normal flow бафф ещё действует на enemy response, затем тикает до 0.
        self.assertEqual(result['player_hp'], 95)
        self.assertEqual(result['defense_buff_turns'], 0)

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
             patch('game.combat.tick_post_action_player_buff_durations', return_value=''):
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

    def test_defense_buff_turns_decrement_in_combat_core_post_action_timing(self):
        state = {'defense_buff_turns': 2, 'berserk_turns': 0, 'blessing_turns': 0}
        combat.tick_post_action_player_buff_durations(state)
        self.assertEqual(state['defense_buff_turns'], 1)

    def test_berserk_turns_decrement_in_combat_core_post_action_timing(self):
        state = {'defense_buff_turns': 0, 'berserk_turns': 2, 'blessing_turns': 0}
        combat.tick_post_action_player_buff_durations(state)
        self.assertEqual(state['berserk_turns'], 1)

    def test_blessing_turns_decrement_in_combat_core_post_action_timing(self):
        state = {'defense_buff_turns': 0, 'berserk_turns': 0, 'blessing_turns': 2}
        combat.tick_post_action_player_buff_durations(state)
        self.assertEqual(state['blessing_turns'], 1)

    def test_feint_step_expires_in_combat_core_post_action_ticking_path(self):
        state = {
            'defense_buff_turns': 0,
            'berserk_turns': 0,
            'blessing_turns': 0,
            'press_the_line_turns': 0,
            'feint_step_turns': 1,
        }
        combat.tick_post_action_player_buff_durations(state)
        self.assertEqual(state['feint_step_turns'], 0)

    def test_regen_behavior_remains_unchanged_after_post_action_buff_move(self):
        state = {
            'defense_buff_turns': 1,
            'berserk_turns': 1,
            'blessing_turns': 1,
            'regen_turns': 2,
            'regen_amount': 10,
            'player_hp': 50,
            'player_max_hp': 100,
        }

        combat.tick_post_action_player_buff_durations(state)

        self.assertEqual(state['regen_turns'], 2)
        self.assertEqual(state['player_hp'], 50)

    def test_resurrection_behavior_remains_unchanged_after_post_action_buff_move(self):
        state = {
            'defense_buff_turns': 1,
            'berserk_turns': 1,
            'blessing_turns': 1,
            'resurrection_active': True,
            'resurrection_turns': 1,
            'player_hp': 50,
        }

        combat.tick_post_action_player_buff_durations(state)

        self.assertTrue(state['resurrection_active'])
        self.assertEqual(state['resurrection_turns'], 1)

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
             patch('game.combat.tick_post_action_player_buff_durations', return_value=''):
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
             patch('game.combat.tick_post_action_player_buff_durations', return_value=''):
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
             patch('game.combat.tick_post_action_player_buff_durations', side_effect=lambda *_args, **_kwargs: call_order.append('player_buffs') or ''):
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

    def test_regen_is_applied_at_start_of_normal_attack_turn(self):
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
            'player_hp': 50,
            'player_max_hp': 100,
            'player_goes_first': True,
            'weapon_type': 'melee',
            'weapon_damage': 10,
            'regen_turns': 1,
            'regen_amount': 10,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'blessing_turns': 0,
            'blessing_value': 0,
            'turn': 1,
        }

        def player_attack_side_effect(player_state, _mob_state):
            self.assertEqual(player_state['hp'], 60)
            return {'damage': 5, 'is_crit': False, 'mob_dead': False}

        with patch('game.combat.apply_mob_effect_ticks', return_value=[]), \
             patch('game.combat.player_attack', side_effect=player_attack_side_effect), \
             patch('game.combat.resolve_enemy_response', return_value=[]), \
             patch('game.combat.tick_post_action_player_buff_durations', return_value=''):
            result = combat.process_turn(player, mob, battle_state, lang='ru', user_id=101)

        self.assertEqual(result['player_hp'], 60)
        self.assertEqual(result['regen_turns'], 0)

    def test_regen_duration_ticks_predictably_and_stops_after_expire(self):
        state = {
            'player_hp': 50,
            'player_max_hp': 100,
            'regen_turns': 2,
            'regen_amount': 10,
        }

        first_log = combat.apply_player_start_of_turn_regen(state, 'ru')
        second_log = combat.apply_player_start_of_turn_regen(state, 'ru')
        third_log = combat.apply_player_start_of_turn_regen(state, 'ru')

        self.assertTrue(first_log)
        self.assertTrue(second_log)
        self.assertEqual(third_log, [])
        self.assertEqual(state['player_hp'], 70)
        self.assertEqual(state['regen_turns'], 0)

    def test_failed_skill_attempt_does_not_apply_or_consume_regen(self):
        player = {'hp': 100, 'mana': 0}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 50,
            'player_max_hp': 100,
            'player_mana': 0,
            'mob_hp': 50,
            'mob_effects': [],
            'regen_turns': 2,
            'regen_amount': 10,
            'log': [],
            'turn': 1,
        }

        with patch('game.combat.precheck_skill_use', return_value={'success': False, 'log': 'no mana'}), \
             patch('game.combat.use_skill') as use_skill_mock:
            result = combat.process_skill_turn('fireball', player, mob, battle_state, user_id=101, lang='ru')

        self.assertFalse(result['success'])
        self.assertEqual(result['battle_state']['player_hp'], 50)
        self.assertEqual(result['battle_state']['regen_turns'], 2)
        use_skill_mock.assert_not_called()

    def test_failed_skill_attempt_does_not_add_regen_log(self):
        player = {'hp': 100, 'mana': 0}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 50,
            'player_max_hp': 100,
            'player_mana': 0,
            'mob_hp': 50,
            'mob_effects': [],
            'regen_turns': 2,
            'regen_amount': 10,
            'log': ['before'],
            'turn': 1,
        }

        with patch('game.combat.precheck_skill_use', return_value={'success': False, 'log': 'no mana'}), \
             patch('game.combat.use_skill') as use_skill_mock:
            result = combat.process_skill_turn('fireball', player, mob, battle_state, user_id=101, lang='ru')

        self.assertEqual(result['battle_state']['log'], ['before'])
        use_skill_mock.assert_not_called()

    def test_successful_skill_uses_post_regen_hp_in_skill_logic(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 50,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 50,
            'mob_effects': [],
            'regen_turns': 1,
            'regen_amount': 10,
            'log': [],
            'turn': 1,
        }

        def use_skill_side_effect(_skill_id, player_state, _mob_state, _state, _user_id, _lang):
            self.assertEqual(player_state['hp'], 60)
            return {'success': True, 'log': 'cast', 'damage': 0, 'heal': 0, 'effects': []}

        with patch('game.combat.use_skill', side_effect=use_skill_side_effect), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('heal', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(result['success'])
        self.assertEqual(result['battle_state']['player_hp'], 60)

    def test_casting_regeneration_does_not_tick_new_regen_on_same_turn(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 40,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 50,
            'mob_effects': [],
            'regen_turns': 0,
            'regen_amount': 0,
            'log': [],
            'turn': 1,
        }

        def cast_regen_side_effect(_skill_id, _player_state, _mob_state, state, _user_id, _lang):
            state['regen_turns'] = 3
            state['regen_amount'] = 12
            return {'success': True, 'log': 'cast regen', 'damage': 0, 'heal': 0, 'effects': []}

        with patch('game.combat.use_skill', side_effect=cast_regen_side_effect), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('regeneration', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(result['success'])
        self.assertEqual(result['battle_state']['player_hp'], 40)
        self.assertEqual(result['battle_state']['regen_turns'], 3)

    def test_regen_start_of_turn_is_consistent_in_attack_and_skill_flows(self):
        player_normal = {
            'hp': 120,
            'strength': 10,
            'agility': 10,
            'intuition': 10,
            'vitality': 10,
            'wisdom': 10,
            'luck': 10,
        }
        player_skill = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}

        normal_state = {
            'mob_hp': 100,
            'player_hp': 50,
            'player_max_hp': 100,
            'player_goes_first': True,
            'weapon_type': 'melee',
            'weapon_damage': 10,
            'regen_turns': 2,
            'regen_amount': 10,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'blessing_turns': 0,
            'blessing_value': 0,
            'turn': 1,
        }
        skill_state = {
            'player_hp': 50,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 50,
            'mob_effects': [],
            'regen_turns': 2,
            'regen_amount': 10,
            'log': [],
            'turn': 1,
        }

        with patch('game.combat.apply_mob_effect_ticks', return_value=[]), \
             patch('game.combat.player_attack', return_value={'damage': 5, 'is_crit': False, 'mob_dead': False}), \
             patch('game.combat.resolve_enemy_response', return_value=[]), \
             patch('game.combat.tick_post_action_player_buff_durations', return_value=''):
            normal_result = combat.process_turn(player_normal, mob, normal_state, lang='ru', user_id=101)

        with patch('game.combat.use_skill', return_value={'success': True, 'log': 'cast', 'damage': 0, 'heal': 0, 'effects': []}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            skill_result = combat.process_skill_turn('heal', player_skill, mob, skill_state, user_id=101, lang='ru')

        self.assertEqual(normal_result['player_hp'], 60)
        self.assertEqual(normal_result['regen_turns'], 1)
        self.assertEqual(skill_result['battle_state']['player_hp'], 60)
        self.assertEqual(skill_result['battle_state']['regen_turns'], 1)

    def test_regen_normalization_does_not_change_other_player_buff_duration_ticks(self):
        state = {
            'defense_buff_turns': 2,
            'berserk_turns': 2,
            'blessing_turns': 2,
            'regen_turns': 2,
            'regen_amount': 10,
            'player_hp': 50,
            'player_max_hp': 100,
        }

        combat.tick_post_action_player_buff_durations(state)

        self.assertEqual(state['defense_buff_turns'], 1)
        self.assertEqual(state['berserk_turns'], 1)
        self.assertEqual(state['blessing_turns'], 1)
        self.assertEqual(state['regen_turns'], 2)
        self.assertEqual(state['player_hp'], 50)

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
             patch('game.combat.tick_post_action_player_buff_durations', return_value=''):
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
             patch('game.combat.tick_post_action_player_buff_durations', return_value=''):
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

    def test_normal_attack_uses_shared_finalize_direct_damage_helper(self):
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
            'guaranteed_crit_turns': 0,
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
             patch('game.combat.tick_post_action_player_buff_durations', return_value=''), \
             patch('game.combat.player_attack', return_value={'damage': 7, 'is_crit': False, 'mob_dead': False}), \
             patch('game.combat.finalize_player_direct_damage_action', wraps=combat.finalize_player_direct_damage_action) as finalize_mock:
            result = combat.process_turn(player, mob, battle_state, lang='ru', user_id=101)

        self.assertEqual(finalize_mock.call_count, 1)
        self.assertEqual(result['mob_hp'], 93)


    def test_player_attack_is_pure_and_does_not_mutate_mob_state_hp(self):
        player = {
            'strength': 10,
            'agility': 10,
            'intuition': 10,
            'vitality': 10,
            'wisdom': 10,
            'luck': 10,
            'weapon_type': 'melee',
            'weapon_damage': 10,
        }
        mob_state = {'hp': 40, 'defense': 0}

        with patch('game.combat.roll_crit', return_value=False),              patch('game.combat.calc_final_damage', return_value=12):
            result = combat.player_attack(player, mob_state)

        self.assertEqual(result['damage'], 12)
        self.assertEqual(result['mob_hp'], 28)
        # Новый контракт: helper не мутирует mob_state.
        self.assertEqual(mob_state['hp'], 40)

    def test_resolve_normal_attack_action_applies_final_mob_hp_in_finalize_layer(self):
        player = {
            'strength': 10,
            'agility': 10,
            'intuition': 10,
            'vitality': 10,
            'wisdom': 10,
            'luck': 10,
            'weapon_type': 'melee',
            'weapon_damage': 10,
        }
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'mob_hp': 25,
            'guaranteed_crit_turns': 0,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
        }

        with patch('game.combat.roll_crit', return_value=False),              patch('game.combat.calc_final_damage', return_value=8):
            result = combat.resolve_normal_attack_action(player, mob, battle_state, lang='ru')

        self.assertEqual(result['damage'], 8)
        self.assertEqual(result['mob_hp_after'], 17)
        self.assertEqual(battle_state['mob_hp'], 17)

    def test_normal_attack_helper_is_used_in_both_initiative_branches(self):
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
        first_state = {
            'mob_hp': 100,
            'player_hp': 120,
            'player_goes_first': True,
            'weapon_type': 'melee',
            'weapon_damage': 10,
            'guaranteed_crit_turns': 0,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'blessing_turns': 0,
            'blessing_value': 0,
            'turn': 1,
        }
        second_state = dict(first_state)
        second_state['player_goes_first'] = False

        with patch('game.combat.apply_mob_effect_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]), \
             patch('game.combat.tick_post_action_player_buff_durations', return_value=''), \
             patch('game.combat.resolve_normal_attack_action', wraps=combat.resolve_normal_attack_action) as normal_attack_helper_mock:
            combat.process_turn(player, mob, first_state, lang='ru', user_id=101)
            combat.process_turn(player, mob, second_state, lang='ru', user_id=101)

        self.assertEqual(normal_attack_helper_mock.call_count, 2)

    def test_normal_attack_helper_keeps_crit_log_enemy_timing_and_mob_death_behavior(self):
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
        base_state = {
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
             patch('game.combat.player_attack', return_value={'damage': 10, 'is_crit': True, 'mob_dead': False}), \
             patch('game.combat.resolve_enemy_response', return_value=['enemy response']) as response_mock, \
             patch('game.combat.tick_post_action_player_buff_durations', return_value=''):
            crit_result = combat.process_turn(player, mob, dict(base_state), lang='ru', user_id=101)

        self.assertEqual(crit_result['guaranteed_crit_turns'], 0)
        self.assertEqual(crit_result['log'][0], combat.t('battle.attack_crit', 'ru', damage=10))
        self.assertIn('enemy response', crit_result['log'])
        self.assertEqual(response_mock.call_count, 1)

        lethal_state = dict(base_state)
        lethal_state['guaranteed_crit_turns'] = 0
        lethal_state['mob_hp'] = 7
        with patch('game.combat.apply_mob_effect_ticks', return_value=[]), \
             patch('game.combat.player_attack', return_value={'damage': 7, 'is_crit': False, 'mob_dead': True}), \
             patch('game.combat.resolve_enemy_response') as lethal_response_mock, \
             patch('game.combat.tick_post_action_player_buff_durations', return_value=''):
            lethal_result = combat.process_turn(player, mob, lethal_state, lang='ru', user_id=101)

        self.assertTrue(lethal_result['mob_dead'])
        self.assertEqual(lethal_result['mob_hp'], 0)
        self.assertEqual(lethal_result['log'][0], combat.t('battle.attack_hit', 'ru', damage=7))
        self.assertEqual(lethal_response_mock.call_count, 0)

    def test_damage_skill_uses_shared_finalize_direct_damage_helper(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 50,
            'mob_effects': [],
            'guaranteed_crit_turns': 0,
            'log': [],
            'turn': 1,
        }

        with patch('game.combat.use_skill', return_value={'success': True, 'log': 'cast', 'damage': 10, 'heal': 0, 'effects': []}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]), \
             patch('game.combat.finalize_player_direct_damage_action', wraps=combat.finalize_player_direct_damage_action) as finalize_mock:
            result = combat.process_skill_turn('fireball', player, mob, battle_state, user_id=101, lang='ru')

        self.assertEqual(finalize_mock.call_count, 1)
        self.assertEqual(result['battle_state']['mob_hp'], 40)

    def test_normal_attack_and_damage_skill_share_direct_damage_result_contract(self):
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
        normal_state = {
            'mob_hp': 50,
            'player_hp': 120,
            'player_goes_first': True,
            'weapon_type': 'melee',
            'weapon_damage': 10,
            'guaranteed_crit_turns': 0,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'blessing_turns': 0,
            'blessing_value': 0,
            'turn': 1,
        }
        skill_state = {
            'player_hp': 120,
            'player_max_hp': 120,
            'player_mana': 80,
            'mob_hp': 50,
            'mob_effects': [],
            'guaranteed_crit_turns': 0,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'log': [],
            'turn': 1,
        }

        with patch('game.combat.player_attack', return_value={'damage': 10, 'is_crit': False, 'mob_dead': False}):
            normal_result = combat.resolve_normal_attack_action(dict(player), mob, normal_state, lang='ru')

        with patch('game.combat.use_skill', return_value={'success': True, 'log': 'cast', 'damage': 10, 'heal': 0, 'effects': []}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            skill_result = combat.process_skill_turn('fireball', dict(player), mob, skill_state, user_id=101, lang='ru')

        normal_contract = normal_result['direct_damage_result']
        skill_contract = skill_result['skill_result']['direct_damage_result']
        for key in ('base_damage', 'damage', 'final_damage', 'mob_hp_before', 'mob_hp_after', 'mob_dead', 'modifiers_applied', 'guaranteed_crit_applied'):
            self.assertIn(key, normal_contract)
            self.assertIn(key, skill_contract)

    def test_direct_damage_contract_preserves_modifier_behavior(self):
        state = {
            'mob_hp': 200,
            'guaranteed_crit_turns': 1,
            'hunters_mark_turns': 1,
            'hunters_mark_value': 20,
            'vulnerability_turns': 1,
            'vulnerability_value': 20,
        }

        result = combat.finalize_player_direct_damage_action(
            state,
            base_damage=10,
            can_consume_guaranteed_crit=True,
        )

        self.assertEqual(result['final_damage'], 36)
        self.assertTrue(result['guaranteed_crit_applied'])
        self.assertEqual(state['guaranteed_crit_turns'], 0)
        self.assertEqual(state['hunters_mark_turns'], 0)
        self.assertEqual(state['vulnerability_turns'], 0)

    def test_non_damage_skill_does_not_use_shared_finalize_direct_damage_helper(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 50,
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
             patch('game.combat.resolve_enemy_response', return_value=[]), \
             patch('game.combat.finalize_player_direct_damage_action', wraps=combat.finalize_player_direct_damage_action) as finalize_mock:
            result = combat.process_skill_turn('heal', player, mob, battle_state, user_id=101, lang='ru')

        self.assertEqual(finalize_mock.call_count, 0)
        self.assertEqual(result['battle_state']['guaranteed_crit_turns'], 1)

    def test_non_damage_skill_has_no_direct_damage_contract(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 50,
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

        self.assertNotIn('direct_damage_result', result['skill_result'])

    def test_direct_damage_contract_matches_visible_skill_outcome(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 100,
            'mob_effects': [],
            'guaranteed_crit_turns': 0,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
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
                'log_key': 'skills.log_damage',
                'log_params': {'name': 'Fireball', 'dmg': 10, 'cost': 5},
                'log_suffixes': [],
                'lifesteal_ratio': 0.0,
            }), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('fireball', player, mob, battle_state, user_id=101, lang='ru')

        contract = result['skill_result']['direct_damage_result']
        self.assertEqual(contract['final_damage'], result['skill_result']['damage'])
        self.assertEqual(contract['mob_hp_after'], result['battle_state']['mob_hp'])

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

    def test_halo_of_dawn_heal_recalculates_from_final_damage_after_finalize(self):
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
                'heal': 1,
                'effects': [],
                'direct_damage_skill': True,
                'log_key': 'skills.log_halo_of_dawn',
                'log_params': {'name': 'Halo of Dawn', 'dmg': 10, 'heal': 1, 'cost': 5},
                'log_suffixes': [],
                'lifesteal_ratio': 0.0,
                'heal_from_damage_ratio': 0.15,
                'heal_cap_missing_hp': 160,
            }), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('halo_of_dawn', player, mob, battle_state, user_id=101, lang='ru')

        # 10 -> crit 25 -> hunter 30, heal must be recomputed from final damage.
        self.assertEqual(result['skill_result']['damage'], 30)
        self.assertEqual(result['skill_result']['heal'], 4)
        self.assertEqual(result['battle_state']['player_hp'], 44)

    def test_halo_of_dawn_log_params_heal_matches_applied_heal(self):
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
                'heal': 1,
                'effects': [],
                'direct_damage_skill': True,
                'log_key': 'skills.log_halo_of_dawn',
                'log_params': {'name': 'Halo of Dawn', 'dmg': 10, 'heal': 1, 'cost': 5},
                'log_suffixes': [],
                'lifesteal_ratio': 0.0,
                'heal_from_damage_ratio': 0.15,
                'heal_cap_missing_hp': 160,
            }), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('halo_of_dawn', player, mob, battle_state, user_id=101, lang='ru')

        final_heal = result['skill_result']['heal']
        self.assertEqual(result['skill_result']['log_params']['heal'], final_heal)
        self.assertIn(f'+{final_heal}', result['battle_state']['log'][-1])

    def test_halo_of_dawn_near_full_hp_heal_is_capped_after_finalize(self):
        player = {'hp': 98, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 98,
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
                'heal': 1,
                'effects': [],
                'direct_damage_skill': True,
                'log_key': 'skills.log_halo_of_dawn',
                'log_params': {'name': 'Halo of Dawn', 'dmg': 10, 'heal': 1, 'cost': 5},
                'log_suffixes': [],
                'lifesteal_ratio': 0.0,
                'heal_from_damage_ratio': 0.15,
                'heal_cap_missing_hp': 2,
            }), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('halo_of_dawn', player, mob, battle_state, user_id=101, lang='ru')

        # 10 -> crit 25 -> hunter 30, raw heal would be 4 but near-full cap is 2.
        self.assertEqual(result['skill_result']['damage'], 30)
        self.assertEqual(result['skill_result']['heal'], 2)
        self.assertEqual(result['battle_state']['player_hp'], 100)

    def test_halo_of_dawn_near_full_hp_log_heal_matches_capped_applied_heal(self):
        player = {'hp': 98, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 98,
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
                'heal': 1,
                'effects': [],
                'direct_damage_skill': True,
                'log_key': 'skills.log_halo_of_dawn',
                'log_params': {'name': 'Halo of Dawn', 'dmg': 10, 'heal': 1, 'cost': 5},
                'log_suffixes': [],
                'lifesteal_ratio': 0.0,
                'heal_from_damage_ratio': 0.15,
                'heal_cap_missing_hp': 2,
            }), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('halo_of_dawn', player, mob, battle_state, user_id=101, lang='ru')

        self.assertEqual(result['skill_result']['log_params']['heal'], 2)
        self.assertIn('+2', result['battle_state']['log'][-1])

    def test_halo_of_dawn_judged_target_bonus_still_works_in_skill_flow(self):
        player = {'hp': 100, 'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 12, 'vitality': 1, 'wisdom': 18, 'luck': 1}
        mob = {'id': 'wolf', 'defense': 0}
        plain_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'mob_hp': 300,
            'mob_effects': [],
            'weapon_damage': 14,
            'weapon_type': 'magic',
            'weapon_profile': 'holy_staff',
            'guaranteed_crit_turns': 0,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
            'log': [],
            'turn': 1,
        }
        judged_state = dict(plain_state, vulnerability_turns=2, vulnerability_value=20)

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            plain = combat.process_skill_turn('halo_of_dawn', dict(player), dict(mob), dict(plain_state), user_id=101, lang='ru')
            judged = combat.process_skill_turn('halo_of_dawn', dict(player), dict(mob), dict(judged_state), user_id=101, lang='ru')

        self.assertGreater(judged['skill_result']['damage'], plain['skill_result']['damage'])

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

    def test_daggers_do_not_get_universal_damage_bonus_from_dodge_buff_window(self):
        state = {
            'weapon_profile': 'daggers',
            'dodge_buff_turns': 2,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
        }

        result = combat.apply_direct_damage_action_modifiers(
            state,
            base_damage=100,
            can_consume_guaranteed_crit=False,
        )

        self.assertEqual(result['damage'], 100)
        self.assertFalse(result['modifiers_applied'])
        self.assertEqual(state['dodge_buff_turns'], 2)

    def test_non_daggers_also_have_no_universal_damage_bonus_from_dodge_buff_window(self):
        state = {
            'weapon_profile': 'sword_1h',
            'dodge_buff_turns': 2,
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
        }

        result = combat.apply_direct_damage_action_modifiers(
            state,
            base_damage=100,
            can_consume_guaranteed_crit=False,
        )

        self.assertEqual(result['damage'], 100)
        self.assertFalse(result['modifiers_applied'])


class SkillEngineRegressionTests(unittest.TestCase):
    def test_smoke_bomb_sets_dodge_buff_to_35_for_two_turns(self):
        player = {'mana': 200, 'agility': 20}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        battle_state = {'player_hp': 100, 'player_max_hp': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill(
                skill_id='smoke_bomb',
                player=player,
                mob_state=mob_state,
                battle_state=battle_state,
                telegram_id=101,
                lang='ru',
            )

        self.assertTrue(result['success'])
        self.assertEqual(battle_state['dodge_buff_value'], 35)
        self.assertEqual(battle_state['dodge_buff_turns'], 2)

    def test_backstab_gets_crit_payoff_on_slow(self):
        player = {
            'mana': 200,
            'strength': 1,
            'agility': 20,
            'intuition': 1,
            'vitality': 1,
            'wisdom': 1,
            'luck': 1,
        }
        mob_state = {'hp': 300, 'defense': 0, 'effects': [{'type': 'slow', 'turns': 1, 'value': 1}]}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'weapon_damage': 10,
            'weapon_type': 'melee',
            'weapon_profile': 'daggers',
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.calc_final_damage', return_value=100), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill(
                skill_id='backstab',
                player=player,
                mob_state=mob_state,
                battle_state=battle_state,
                telegram_id=101,
                lang='ru',
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['damage'], 260)
        self.assertEqual(result['log_key'], 'skills.log_backstab_crit')

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
    async def asyncSetUp(self):
        precheck_patcher = patch('game.combat.precheck_skill_use', return_value={'success': True, 'log': ''})
        self._precheck_mock = precheck_patcher.start()
        self.addAsyncCleanup(lambda: precheck_patcher.stop())

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

    def test_sword_rush_sets_scaled_vulnerability_window(self):
        player = {'mana': 100, 'strength': 10, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'defense': 0, 'effects': []}
        battle_state = {
            'player_mana': 100,
            'player_max_hp': 100,
            'player_hp': 100,
            'weapon_profile': 'sword_1h',
            'weapon_type': 'melee',
            'weapon_damage': 12,
            'armor_class': 'light',
            'offhand_profile': 'none',
            'encumbrance': 0,
        }

        with patch('game.skill_engine.get_skill_level', return_value=3), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('sword_rush', player, mob_state, battle_state, telegram_id=101, lang='ru')

        self.assertTrue(result['success'])
        self.assertEqual(battle_state['vulnerability_turns'], 2)
        self.assertEqual(battle_state['vulnerability_value'], 31)

    def test_shield_bash_applies_weaken_off_balance_and_does_not_stun_skip(self):
        player = {'mana': 100, 'strength': 10, 'agility': 10, 'intuition': 1, 'vitality': 12, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        battle_state = {
            'weapon_damage': 12,
            'weapon_type': 'melee',
            'weapon_profile': 'sword_1h',
            'armor_class': None,
            'offhand_profile': 'shield',
            'encumbrance': None,
            'player_mana': 100,
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('shield_bash', player, mob_state, battle_state, telegram_id=101, lang='ru')

        self.assertTrue(result['success'])
        self.assertGreater(result['damage'], 0)
        self.assertEqual(battle_state['disarm_turns'], 2)
        self.assertGreater(battle_state['disarm_value'], 0)
        self.assertTrue(any(e['type'] == 'off_balance' for e in result['effects']))

        enemy_player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 10, 'damage_max': 10}
        battle_state_enemy = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [{'type': 'off_balance', 'turns': 1, 'value': 0}],
            'disarm_turns': battle_state['disarm_turns'],
            'disarm_value': battle_state['disarm_value'],
        }
        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 10, 'player_hp': 90}):
            log = combat.resolve_enemy_response(mob, enemy_player, battle_state_enemy, lang='ru', user_id=None)

        self.assertTrue(any('атак' in line.lower() for line in log))
        self.assertEqual(battle_state_enemy['player_hp'], 100 - int(10 * (1 - battle_state['disarm_value'] / 100)))

    def test_expose_guard_sets_vulnerability_window(self):
        player = {'mana': 100, 'strength': 10, 'agility': 12, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        battle_state = {'weapon_damage': 12, 'weapon_type': 'melee', 'weapon_profile': 'sword_1h', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('expose_guard', player, mob_state, battle_state, telegram_id=101, lang='ru')

        self.assertEqual(battle_state['vulnerability_turns'], 2)
        self.assertGreater(battle_state['vulnerability_value'], 0)

    def test_press_the_line_sets_and_expires(self):
        player = {'mana': 100, 'strength': 12, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        battle_state = {'weapon_damage': 12, 'weapon_type': 'melee', 'weapon_profile': 'sword_1h', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('press_the_line', player, mob_state, battle_state, telegram_id=101, lang='ru')

        self.assertEqual(battle_state['press_the_line_turns'], 2)
        self.assertGreater(battle_state['press_the_line_value'], 0)
        combat.tick_post_action_player_buff_durations(battle_state)
        self.assertEqual(battle_state['press_the_line_turns'], 1)
        combat.tick_post_action_player_buff_durations(battle_state)
        self.assertEqual(battle_state['press_the_line_turns'], 0)

    def test_punishing_cut_gets_payoff_into_exposed_target(self):
        player = {'mana': 100, 'strength': 14, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'melee', 'weapon_profile': 'sword_1h', 'player_mana': 100}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('punishing_cut', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            exposed_state = dict(base_state, vulnerability_turns=2, vulnerability_value=25)
            exposed = skill_engine.use_skill('punishing_cut', dict(player), dict(mob_state), exposed_state, telegram_id=101, lang='ru')

        self.assertGreater(exposed['damage'], plain['damage'])

    def test_vanguard_surge_gets_stronger_in_setup_window(self):
        player = {'mana': 100, 'strength': 15, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'sword_1h', 'player_mana': 100}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('vanguard_surge', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            setup_state = dict(base_state, vulnerability_turns=2, vulnerability_value=25, press_the_line_turns=1, press_the_line_value=16)
            setup = skill_engine.use_skill('vanguard_surge', dict(player), dict(mob_state), setup_state, telegram_id=101, lang='ru')

        self.assertGreater(setup['damage'], plain['damage'])

    def test_counter_defense_buff_reliability_changes_same_roll_threshold(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 20, 'damage_max': 20}
        base_state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'weapon_profile': 'sword_1h',
            'offhand_profile': 'none',
            'vulnerability_value': 0,
            'defense_buff_value': 20,
        }
        state_without_defense = dict(base_state, defense_buff_turns=0)
        state_with_defense = dict(base_state, defense_buff_turns=2)

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 20, 'player_hp': 80}), \
             patch('game.weapon_mastery.get_skill_level', return_value=1), \
             patch('game.combat.random.random', return_value=0.18):
            combat.resolve_enemy_response(mob, player, state_without_defense, lang='ru', user_id=101)

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 20, 'player_hp': 80}), \
             patch('game.weapon_mastery.get_skill_level', return_value=1), \
             patch('game.combat.random.random', return_value=0.18):
            combat.resolve_enemy_response(mob, player, state_with_defense, lang='ru', user_id=101)

        self.assertEqual(state_without_defense['mob_hp'], 100)
        self.assertEqual(state_with_defense['mob_hp'], 95)

    def test_counter_shield_reliability_changes_same_roll_threshold(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 20, 'damage_max': 20}
        no_shield_state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'weapon_profile': 'sword_1h',
            'offhand_profile': 'none',
            'vulnerability_turns': 0,
            'vulnerability_value': 0,
        }
        shield_state = dict(no_shield_state, offhand_profile='shield')

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 20, 'player_hp': 80}), \
             patch('game.weapon_mastery.get_skill_level', return_value=1), \
             patch('game.combat.random.random', return_value=0.24):
            combat.resolve_enemy_response(mob, player, no_shield_state, lang='ru', user_id=101)

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 20, 'player_hp': 80}), \
             patch('game.weapon_mastery.get_skill_level', return_value=1), \
             patch('game.combat.random.random', return_value=0.24):
            combat.resolve_enemy_response(mob, player, shield_state, lang='ru', user_id=101)

        self.assertEqual(no_shield_state['mob_hp'], 100)
        self.assertEqual(shield_state['mob_hp'], 93)

    def test_counter_remains_gated_for_non_sword_profile_even_with_vulnerability(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 10, 'damage_max': 10}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'weapon_profile': 'dagger',
            'offhand_profile': 'none',
            'vulnerability_turns': 2,
            'vulnerability_value': 30,
        }

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 10, 'player_hp': 90}), \
             patch('game.weapon_mastery.get_skill_level', return_value=5), \
             patch('game.combat.random.random', return_value=0.0):
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=101)

        self.assertEqual(state['mob_hp'], 100)

    def test_sword_tree_ui_assumptions_support_5_skills_per_branch(self):
        from game.skills import get_weapon_tree
        tree = get_weapon_tree('iron_sword')
        self.assertEqual(len(tree['A']), 5)
        self.assertEqual(len(tree['B']), 5)

    def test_sword_1h_guardian_metadata_matches_tree_branch_a(self):
        from game.skills import get_skill, get_weapon_tree

        tree = get_weapon_tree('iron_sword')
        guardian_ids = tree['A']

        self.assertEqual(
            guardian_ids,
            ['sword_rush', 'defensive_stance', 'shield_bash', 'parry', 'counter'],
        )
        for skill_id in guardian_ids:
            self.assertEqual(get_skill(skill_id)['branch'], 'A')

    def test_driving_slash_reads_off_balance_from_runtime_mob_effects(self):
        player = {'mana': 100, 'strength': 14, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {
            'weapon_damage': 14,
            'weapon_type': 'melee',
            'weapon_profile': 'sword_1h',
            'player_mana': 100,
            'mob_effects': [],
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            without_runtime_effect = skill_engine.use_skill(
                'driving_slash',
                dict(player),
                dict(mob_state),
                dict(base_state),
                telegram_id=101,
                lang='ru',
            )
            with_runtime_effect = skill_engine.use_skill(
                'driving_slash',
                dict(player),
                dict(mob_state),
                dict(base_state, mob_effects=[{'type': 'off_balance', 'turns': 1, 'value': 0}]),
                telegram_id=101,
                lang='ru',
            )

        self.assertGreater(with_runtime_effect['damage'], without_runtime_effect['damage'])

    def test_dagger_tree_ui_assumptions_support_5_skills_per_branch(self):
        from game.skills import get_weapon_tree
        tree = get_weapon_tree('dagger')
        self.assertEqual(
            tree['A'],
            ['envenom_blades', 'toxic_cut', 'crippling_venom', 'widows_kiss', 'rupture_toxins'],
        )
        self.assertEqual(
            tree['B'],
            ['smoke_bomb', 'feint_step', 'quick_slice', 'backstab', 'shadow_chain'],
        )

    def test_dagger_branch_b_unlock_progression_matches_tree_order(self):
        from game.skills import get_skill, get_weapon_tree

        branch_b = get_weapon_tree('dagger')['B']
        unlocks = [get_skill(skill_id)['unlock_mastery'] for skill_id in branch_b]

        self.assertEqual(branch_b, ['smoke_bomb', 'feint_step', 'quick_slice', 'backstab', 'shadow_chain'])
        self.assertEqual(unlocks, [1, 3, 5, 7, 10])

    def test_backstab_uses_runtime_mob_effects_from_battle_state(self):
        player = {'mana': 100, 'strength': 1, 'agility': 14, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {
            'weapon_damage': 12,
            'weapon_type': 'melee',
            'weapon_profile': 'dagger',
            'player_mana': 100,
            'mob_effects': [],
            'vulnerability_turns': 0,
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('backstab', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            opened = skill_engine.use_skill(
                'backstab',
                dict(player),
                dict(mob_state),
                dict(base_state, mob_effects=[{'type': 'slow', 'turns': 1, 'value': 0}]),
                telegram_id=101,
                lang='ru',
            )

        self.assertGreater(opened['damage'], plain['damage'])
        self.assertEqual(opened['log_key'], 'skills.log_backstab_crit')

    def test_backstab_does_not_trigger_opening_from_poison_alone(self):
        player = {'mana': 100, 'strength': 1, 'agility': 14, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {
            'weapon_damage': 12,
            'weapon_type': 'melee',
            'weapon_profile': 'dagger',
            'player_mana': 100,
            'vulnerability_turns': 0,
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('backstab', dict(player), dict(mob_state), dict(base_state, mob_effects=[]), telegram_id=101, lang='ru')
            poison_only = skill_engine.use_skill(
                'backstab',
                dict(player),
                dict(mob_state),
                dict(base_state, mob_effects=[{'type': 'poison', 'turns': 2, 'value': 5}]),
                telegram_id=101,
                lang='ru',
            )

        self.assertEqual(poison_only['damage'], plain['damage'])
        self.assertNotEqual(poison_only.get('log_key'), 'skills.log_backstab_crit')

    def test_envenom_blades_buffs_only_next_poison_application(self):
        player = {'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {'weapon_damage': 14, 'weapon_type': 'melee', 'weapon_profile': 'dagger', 'player_mana': 100, 'mob_effects': []}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            skill_engine.use_skill('envenom_blades', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')
            first = skill_engine.use_skill('toxic_cut', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')
            second = skill_engine.use_skill('toxic_cut', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')

        self.assertGreater(first['effects'][0]['value'], second['effects'][0]['value'])
        self.assertFalse(state.get('envenom_blades_active', False))

    def test_quick_slice_consumes_feint_step_and_applies_slow(self):
        player = {'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {'weapon_damage': 14, 'weapon_type': 'melee', 'weapon_profile': 'dagger', 'player_mana': 100, 'mob_effects': []}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            skill_engine.use_skill('feint_step', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')
            result = skill_engine.use_skill('quick_slice', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')

        self.assertEqual(state.get('feint_step_turns', 0), 0)
        self.assertTrue(any(e.get('type') == 'slow' for e in result['effects']))

    def test_quick_slice_consumes_feint_step_before_combat_core_expiry_tick(self):
        player = {'hp': 100, 'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'mob_hp': 120,
            'mob_effects': [],
            'feint_step_turns': 1,
            'log': [],
            'turn': 1,
            'weapon_damage': 14,
            'weapon_type': 'melee',
            'weapon_profile': 'dagger',
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('quick_slice', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(result['success'])
        self.assertEqual(result['battle_state'].get('feint_step_turns', 0), 0)

    def test_feint_step_survives_its_turn_and_is_consumed_by_next_quick_slice_flow(self):
        player = {'hp': 100, 'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'mob_hp': 120,
            'mob_effects': [],
            'log': [],
            'turn': 1,
            'weapon_damage': 14,
            'weapon_type': 'melee',
            'weapon_profile': 'dagger',
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            setup_result = combat.process_skill_turn('feint_step', player, mob, battle_state, user_id=101, lang='ru')
            self.assertTrue(setup_result['success'])
            self.assertEqual(setup_result['battle_state'].get('feint_step_turns', 0), 1)

            quick_result = combat.process_skill_turn('quick_slice', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(quick_result['success'])
        self.assertEqual(quick_result['battle_state'].get('feint_step_turns', 0), 0)
        self.assertEqual(quick_result['skill_result'].get('log_key'), 'skills.log_quick_slice_feint')

    def test_feint_step_expires_if_next_action_does_not_consume_it(self):
        player = {'hp': 100, 'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'mob_hp': 120,
            'mob_effects': [],
            'log': [],
            'turn': 1,
            'weapon_damage': 14,
            'weapon_type': 'melee',
            'weapon_profile': 'dagger',
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            setup_result = combat.process_skill_turn('feint_step', player, mob, battle_state, user_id=101, lang='ru')
            self.assertTrue(setup_result['success'])
            self.assertEqual(setup_result['battle_state'].get('feint_step_turns', 0), 1)

            other_action_result = combat.process_skill_turn('toxic_cut', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(other_action_result['success'])
        self.assertEqual(other_action_result['battle_state'].get('feint_step_turns', 0), 0)

    def test_widows_kiss_gets_payoff_bonus_on_poisoned_or_opened_target(self):
        player = {'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 14, 'weapon_type': 'melee', 'weapon_profile': 'dagger', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('widows_kiss', dict(player), dict(mob_state), dict(base_state, mob_effects=[]), telegram_id=101, lang='ru')
            poisoned = skill_engine.use_skill(
                'widows_kiss',
                dict(player),
                dict(mob_state),
                dict(base_state, mob_effects=[{'type': 'poison', 'turns': 2, 'value': 8}]),
                telegram_id=101,
                lang='ru',
            )

        self.assertGreater(poisoned['damage'], plain['damage'])
        self.assertEqual(poisoned['log_key'], 'skills.log_widows_kiss_payoff')

    def test_rupture_toxins_consumes_poison_effects_and_keeps_slow(self):
        player = {'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {
            'weapon_damage': 14,
            'weapon_type': 'melee',
            'weapon_profile': 'dagger',
            'player_mana': 100,
            'mob_effects': [
                {'type': 'poison', 'turns': 2, 'value': 8},
                {'type': 'poison', 'turns': 1, 'value': 5},
                {'type': 'slow', 'turns': 1, 'value': 0},
            ],
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('rupture_toxins', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')

        self.assertGreater(result['damage'], 0)
        self.assertTrue(all(e.get('type') != 'poison' for e in state['mob_effects']))
        self.assertTrue(any(e.get('type') == 'slow' for e in state['mob_effects']))

    def test_short_bow_tree_ui_assumptions_support_5_skills_per_branch(self):
        from game.skills import get_weapon_tree

        tree = get_weapon_tree('short_bow')
        self.assertEqual(
            tree['A'],
            ['hunters_mark', 'aimed_shot', 'steady_aim', 'piercing_arrow', 'deadeye'],
        )
        self.assertEqual(
            tree['B'],
            ['quick_shot', 'hamstring_arrow', 'reposition', 'volley_step', 'rain_of_barbs'],
        )

    def test_short_bow_branch_a_unlock_progression_matches_tree_order(self):
        from game.skills import get_skill, get_weapon_tree

        branch_a = get_weapon_tree('short_bow')['A']
        unlocks = [get_skill(skill_id)['unlock_mastery'] for skill_id in branch_a]
        self.assertEqual(unlocks, [1, 3, 5, 7, 10])

    def test_short_bow_branch_b_unlock_progression_matches_tree_order(self):
        from game.skills import get_skill, get_weapon_tree

        branch_b = get_weapon_tree('short_bow')['B']
        unlocks = [get_skill(skill_id)['unlock_mastery'] for skill_id in branch_b]
        self.assertEqual(unlocks, [1, 3, 5, 7, 10])

    def test_legacy_bow_ids_stay_in_skills_but_not_in_active_tree(self):
        from game.skills import SKILLS, get_weapon_tree

        legacy_ids = ['eagle_eye', 'bow_ult_a', 'retreat', 'arrow_rain', 'kite', 'bow_ult_b']
        tree_ids = set(get_weapon_tree('short_bow')['A'] + get_weapon_tree('short_bow')['B'])

        for skill_id in legacy_ids:
            self.assertIn(skill_id, SKILLS)
            self.assertNotIn(skill_id, tree_ids)

    def test_aimed_shot_stronger_vs_marked_target(self):
        player = {'mana': 100, 'strength': 1, 'agility': 10, 'intuition': 16, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('aimed_shot', dict(player), dict(mob_state), dict(base_state, hunters_mark_turns=0), telegram_id=101, lang='ru')
            marked = skill_engine.use_skill('aimed_shot', dict(player), dict(mob_state), dict(base_state, hunters_mark_turns=2), telegram_id=101, lang='ru')

        self.assertGreater(marked['damage'], plain['damage'])

    def test_steady_aim_sets_one_guaranteed_crit_and_is_consumed(self):
        player = {'mana': 100, 'strength': 1, 'agility': 10, 'intuition': 16, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'mob_hp': 150,
            'mob_effects': [],
            'log': [],
            'turn': 1,
            'weapon_damage': 14,
            'weapon_type': 'ranged',
            'weapon_profile': 'short_bow',
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
            'guaranteed_crit_turns': 0,
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.player_attack', return_value={'type': 'player_attack', 'damage': 15, 'is_crit': True, 'mob_dead': False, 'mob_hp': 135}), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            setup = combat.process_skill_turn('steady_aim', player, mob, battle_state, user_id=101, lang='ru')
            self.assertTrue(setup['success'])
            self.assertEqual(setup['battle_state'].get('guaranteed_crit_turns', 0), 1)

            attack = combat.resolve_normal_attack_action(player, mob, battle_state, lang='ru')

        self.assertGreaterEqual(attack['damage'], 0)
        self.assertEqual(battle_state.get('guaranteed_crit_turns', 0), 0)

    def test_piercing_arrow_gets_payoff_bonus_vs_marked_target(self):
        player = {'mana': 100, 'strength': 1, 'agility': 10, 'intuition': 16, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 20, 'effects': []}
        base_state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('piercing_arrow', dict(player), dict(mob_state), dict(base_state, hunters_mark_turns=0), telegram_id=101, lang='ru')
            marked = skill_engine.use_skill('piercing_arrow', dict(player), dict(mob_state), dict(base_state, hunters_mark_turns=2), telegram_id=101, lang='ru')

        self.assertGreater(marked['damage'], plain['damage'])

    def test_hamstring_arrow_applies_slow(self):
        player = {'mana': 100, 'strength': 1, 'agility': 14, 'intuition': 10, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('hamstring_arrow', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')

        self.assertTrue(any(e.get('type') == 'slow' for e in result['effects']))

    def test_reposition_sets_dodge_buff_correctly(self):
        player = {'mana': 100, 'strength': 1, 'agility': 14, 'intuition': 10, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('reposition', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')

        self.assertEqual(state.get('dodge_buff_turns', 0), 2)
        self.assertEqual(state.get('dodge_buff_value', 0), 45)

    def test_volley_step_reads_runtime_slow_correctly(self):
        player = {'mana': 100, 'strength': 1, 'agility': 14, 'intuition': 10, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('volley_step', dict(player), dict(mob_state), dict(base_state, mob_effects=[]), telegram_id=101, lang='ru')
            slowed = skill_engine.use_skill(
                'volley_step',
                dict(player),
                dict(mob_state),
                dict(base_state, mob_effects=[{'type': 'slow', 'turns': 2, 'value': 0}]),
                telegram_id=101,
                lang='ru',
            )

        self.assertGreater(slowed['damage'], plain['damage'])

    def test_rain_of_barbs_has_slow_synergy_without_overtaking_sniper_payoff(self):
        player = {'mana': 100, 'strength': 1, 'agility': 14, 'intuition': 14, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            rain_plain = skill_engine.use_skill('rain_of_barbs', dict(player), dict(mob_state), dict(base_state, mob_effects=[]), telegram_id=101, lang='ru')
            rain_slowed = skill_engine.use_skill(
                'rain_of_barbs',
                dict(player),
                dict(mob_state),
                dict(base_state, mob_effects=[{'type': 'slow', 'turns': 2, 'value': 0}]),
                telegram_id=101,
                lang='ru',
            )
            deadeye_marked = skill_engine.use_skill(
                'deadeye',
                dict(player),
                dict(mob_state),
                dict(base_state, hunters_mark_turns=2),
                telegram_id=101,
                lang='ru',
            )

        self.assertGreater(rain_slowed['damage'], rain_plain['damage'])
        self.assertLess(rain_slowed['damage'], deadeye_marked['damage'])

    def test_smoke_bomb_basic_evasive_behavior_still_works(self):
        player = {'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {'weapon_damage': 14, 'weapon_type': 'melee', 'weapon_profile': 'dagger', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('smoke_bomb', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')

        self.assertGreater(state.get('dodge_buff_turns', 0), 0)
        self.assertGreater(state.get('dodge_buff_value', 0), 0)

    def test_holy_staff_tree_is_full_5_plus_5(self):
        tree = game_skills.SKILL_TREES['holy_staff']
        self.assertEqual(len(tree['A']), 5)
        self.assertEqual(len(tree['B']), 5)

    def test_holy_staff_branch_a_progression_matches_tree_order(self):
        expected = ['heal', 'regeneration', 'cleanse', 'blessing', 'resurrection']
        tree = game_skills.SKILL_TREES['holy_staff']['A']
        self.assertEqual(tree, expected)
        self.assertEqual([game_skills.SKILLS[s]['unlock_mastery'] for s in tree], [1, 3, 5, 7, 10])

    def test_holy_staff_branch_b_progression_matches_tree_order(self):
        expected = ['smite', 'radiant_ward', 'judgment_mark', 'sanctified_burst', 'halo_of_dawn']
        tree = game_skills.SKILL_TREES['holy_staff']['B']
        self.assertEqual(tree, expected)
        self.assertEqual([game_skills.SKILLS[s]['unlock_mastery'] for s in tree], [1, 3, 5, 7, 10])

    def test_holy_staff_heal_still_restores_hp(self):
        player = {'mana': 100, 'hp': 50, 'max_hp': 100, 'wisdom': 18}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {'weapon_damage': 10, 'weapon_type': 'magic', 'weapon_profile': 'holy_staff', 'player_hp': 50, 'player_max_hp': 100}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('heal', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')
        self.assertGreater(result['heal'], 0)

    def test_holy_staff_regeneration_sets_runtime_state(self):
        player = {'mana': 100, 'wisdom': 18}
        state = {'weapon_damage': 10, 'weapon_type': 'magic', 'weapon_profile': 'holy_staff'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('regeneration', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertGreater(state.get('regen_turns', 0), 0)
        self.assertGreater(state.get('regen_amount', 0), 0)

    def test_holy_staff_blessing_sets_runtime_state(self):
        player = {'mana': 100, 'wisdom': 18}
        state = {'weapon_damage': 10, 'weapon_type': 'magic', 'weapon_profile': 'holy_staff'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('blessing', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertGreater(state.get('blessing_turns', 0), 0)
        self.assertGreater(state.get('blessing_value', 0), 0)

    def test_holy_staff_resurrection_sets_runtime_state(self):
        player = {'mana': 100, 'wisdom': 18}
        state = {'weapon_damage': 10, 'weapon_type': 'magic', 'weapon_profile': 'holy_staff'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('resurrection', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertTrue(state.get('resurrection_active', False))
        self.assertGreater(state.get('resurrection_hp', 0), 0)
        self.assertGreater(state.get('resurrection_turns', 0), 0)

    def test_radiant_ward_sets_defense_buff_correctly(self):
        player = {'mana': 100, 'wisdom': 18}
        state = {'weapon_damage': 10, 'weapon_type': 'magic', 'weapon_profile': 'holy_staff'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('radiant_ward', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertGreater(state.get('defense_buff_turns', 0), 0)
        self.assertGreater(state.get('defense_buff_value', 0), 0)

    def test_judgment_mark_sets_vulnerability_correctly(self):
        player = {'mana': 100, 'wisdom': 18}
        state = {'weapon_damage': 10, 'weapon_type': 'magic', 'weapon_profile': 'holy_staff'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('judgment_mark', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertGreater(state.get('vulnerability_turns', 0), 0)
        self.assertGreater(state.get('vulnerability_value', 0), 0)

    def test_sanctified_burst_gets_payoff_vs_judged_target(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 12, 'vitality': 1, 'wisdom': 18, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'holy_staff'}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('sanctified_burst', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            judged = skill_engine.use_skill('sanctified_burst', dict(player), dict(mob_state), dict(base_state, vulnerability_turns=2, vulnerability_value=20), telegram_id=101, lang='ru')
        self.assertGreater(judged['damage'], plain['damage'])

    def test_halo_of_dawn_gets_judged_target_synergy(self):
        player = {'mana': 100, 'hp': 70, 'max_hp': 100, 'strength': 1, 'agility': 1, 'intuition': 12, 'vitality': 1, 'wisdom': 18, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'holy_staff', 'player_hp': 70, 'player_max_hp': 100}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('halo_of_dawn', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            judged = skill_engine.use_skill('halo_of_dawn', dict(player), dict(mob_state), dict(base_state, vulnerability_turns=2, vulnerability_value=20), telegram_id=101, lang='ru')
        self.assertGreater(judged['damage'], plain['damage'])
        self.assertGreaterEqual(judged['heal'], 0)

    def test_cleanse_has_supported_truthful_behavior_without_new_state_framework(self):
        player = {'mana': 100, 'hp': 60, 'max_hp': 100, 'wisdom': 18}
        state = {
            'weapon_damage': 10,
            'weapon_type': 'magic',
            'weapon_profile': 'holy_staff',
            'player_hp': 60,
            'player_max_hp': 100,
            'poison_turns': 2,
            'poison_value': 6,
            'stun_turns': 1,
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('cleanse', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertEqual(state.get('poison_turns', 0), 0)
        self.assertEqual(state.get('stun_turns', 0), 0)
        self.assertGreater(result['heal'], 0)

    def test_legacy_holy_staff_ids_stay_in_skills_but_not_in_active_tree(self):
        tree_skills = set(game_skills.SKILL_TREES['holy_staff']['A'] + game_skills.SKILL_TREES['holy_staff']['B'])
        for legacy_id in ('holy_bolt', 'consecration', 'divine_wrath'):
            self.assertIn(legacy_id, game_skills.SKILLS)
            self.assertNotIn(legacy_id, tree_skills)


if __name__ == '__main__':
    unittest.main()
