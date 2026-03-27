import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from game import combat
from game import items_data
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
        hit_check_patcher = patch(
            'game.combat.resolve_hit_check',
            return_value={
                'outcome': 'hit',
                'is_hit': True,
                'hit_chance': 95,
                'roll': 1,
                'accuracy_rating': 100,
                'evasion_rating': 100,
            },
        )
        self._hit_check_mock = hit_check_patcher.start()
        self.addCleanup(hit_check_patcher.stop)

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

    def test_smoke_bomb_runtime_window_skips_one_enemy_basic_attack_then_expires(self):
        player = {'mana': 100, 'hp': 100, 'agility': 16, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 8, 'damage_max': 8}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'weapon_damage': 10,
            'weapon_type': 'melee',
            'weapon_profile': 'dagger',
            'player_mana': 100,
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('smoke_bomb', player, mob_state, state, telegram_id=101, lang='ru')

        self.assertTrue(result['success'])
        self.assertEqual(state['dodge_buff_turns'], 1)

        with patch('game.combat.random.random', return_value=0.0), \
             patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 8, 'player_hp': 92}) as mob_attack_mock:
            combat.resolve_enemy_response(mob, {'hp': state['player_hp'], 'agility': 0, 'vitality': 0, 'wisdom': 0}, state, lang='ru', user_id=None)
        mob_attack_mock.assert_not_called()
        self.assertEqual(state['player_hp'], 100)
        self.assertEqual(state['dodge_buff_turns'], 0)

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 8, 'player_hp': 92}) as second_attack_mock:
            combat.resolve_enemy_response(mob, {'hp': state['player_hp'], 'agility': 0, 'vitality': 0, 'wisdom': 0}, state, lang='ru', user_id=None)
        second_attack_mock.assert_called_once()

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

    def test_guardian_light_does_not_refresh_defense_buff_when_direct_hit_fails(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 100,
            'mob_effects': [],
            'log': [],
            'turn': 1,
        }
        skill_result = {
            'success': True,
            'log': 'cast',
            'damage': 20,
            'heal': 0,
            'effects': [],
            'direct_damage_skill': True,
            'log_key': 'skills.log_damage',
            'log_params': {'name': 'Guardian Light', 'dmg': 20, 'cost': 10},
            'log_suffixes': [],
            'lifesteal_ratio': 0.0,
            'heal_from_damage_ratio': 0.0,
            'heal_cap_missing_hp': 0,
            'post_hit_actions': [{'type': 'refresh_defense_buff', 'turns': 2, 'value': 14, 'log_key': 'skills.log_guardian_light'}],
        }

        with patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.finalize_player_direct_damage_action', return_value={'final_damage': 0, 'mob_hp_after': 100, 'mob_dead': False}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('guardian_light', player, mob, battle_state, user_id=101, lang='ru')

        self.assertEqual(result['battle_state'].get('defense_buff_turns', 0), 0)
        self.assertEqual(result['battle_state'].get('defense_buff_value', 0), 0)

    def test_final_verdict_does_not_consume_vulnerability_when_direct_hit_fails(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 100,
            'mob_effects': [],
            'vulnerability_turns': 2,
            'vulnerability_value': 20,
            'log': [],
            'turn': 1,
        }
        skill_result = {
            'success': True,
            'log': 'cast',
            'damage': 25,
            'heal': 0,
            'effects': [],
            'direct_damage_skill': True,
            'log_key': 'skills.log_damage',
            'log_params': {'name': 'Final Verdict', 'dmg': 25, 'cost': 12},
            'log_suffixes': [],
            'lifesteal_ratio': 0.0,
            'heal_from_damage_ratio': 0.0,
            'heal_cap_missing_hp': 0,
            'post_hit_actions': [{'type': 'consume_vulnerability'}],
        }

        with patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.finalize_player_direct_damage_action', return_value={'final_damage': 0, 'mob_hp_after': 100, 'mob_dead': False}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('final_verdict', player, mob, battle_state, user_id=101, lang='ru')

        self.assertEqual(result['battle_state']['vulnerability_turns'], 2)
        self.assertEqual(result['battle_state']['vulnerability_value'], 20)

    def test_guardian_light_successful_hit_refreshes_defense_buff_post_hit(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 100,
            'mob_effects': [],
            'log': [],
            'turn': 1,
        }
        skill_result = {
            'success': True,
            'log': 'cast',
            'damage': 20,
            'heal': 0,
            'effects': [],
            'direct_damage_skill': True,
            'log_key': 'skills.log_damage',
            'log_params': {'name': 'Guardian Light', 'dmg': 20, 'cost': 10},
            'log_suffixes': [],
            'lifesteal_ratio': 0.0,
            'heal_from_damage_ratio': 0.0,
            'heal_cap_missing_hp': 0,
            'post_hit_actions': [{'type': 'refresh_defense_buff', 'turns': 2, 'value': 14, 'log_key': 'skills.log_guardian_light'}],
        }

        with patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.finalize_player_direct_damage_action', return_value={'final_damage': 20, 'mob_hp_after': 80, 'mob_dead': False}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('guardian_light', player, mob, battle_state, user_id=101, lang='ru')

        self.assertEqual(result['battle_state']['defense_buff_turns'], 2)
        self.assertEqual(result['battle_state']['defense_buff_value'], 14)

    def test_final_verdict_successful_judged_hit_consumes_vulnerability_post_hit(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 100,
            'mob_effects': [],
            'vulnerability_turns': 2,
            'vulnerability_value': 20,
            'log': [],
            'turn': 1,
        }
        skill_result = {
            'success': True,
            'log': 'cast',
            'damage': 25,
            'heal': 0,
            'effects': [],
            'direct_damage_skill': True,
            'log_key': 'skills.log_damage',
            'log_params': {'name': 'Final Verdict', 'dmg': 25, 'cost': 12},
            'log_suffixes': [],
            'lifesteal_ratio': 0.0,
            'heal_from_damage_ratio': 0.0,
            'heal_cap_missing_hp': 0,
            'post_hit_actions': [{'type': 'consume_vulnerability'}],
        }

        with patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.finalize_player_direct_damage_action', return_value={'final_damage': 25, 'mob_hp_after': 75, 'mob_dead': False}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('final_verdict', player, mob, battle_state, user_id=101, lang='ru')

        self.assertEqual(result['battle_state']['vulnerability_turns'], 0)
        self.assertEqual(result['battle_state']['vulnerability_value'], 0)

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

    def test_slow_no_longer_forces_hard_skip_and_enemy_can_attack(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 7, 'damage_max': 7}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [{'type': 'slow', 'turns': 1, 'value': 0}],
        }

        with patch('game.combat.random.random', return_value=0.99), \
             patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 7, 'player_hp': 93}):
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        self.assertEqual(state['player_hp'], 93)
        self.assertEqual(state['mob_effects'], [])

    def test_slowed_mob_can_miss_due_to_slow(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 7, 'damage_max': 7}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [{'type': 'slow', 'turns': 1, 'value': 0}],
        }

        with patch('game.combat.random.random', return_value=0.0), \
             patch('game.combat.mob_attack') as mob_attack_mock:
            log = combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        mob_attack_mock.assert_not_called()
        self.assertEqual(state['player_hp'], 100)
        self.assertEqual(state['mob_effects'], [])
        self.assertTrue(any('замед' in line.lower() or 'промах' in line.lower() for line in log))

    def test_ice_shackles_freeze_one_skips_exactly_one_enemy_response(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 9, 'damage_max': 9}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [{'type': 'freeze', 'turns': 1, 'value': 0}],
        }

        with patch('game.combat.mob_attack') as first_attack_mock:
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)
        first_attack_mock.assert_not_called()
        self.assertEqual(state['mob_effects'], [])
        self.assertEqual(state['player_hp'], 100)

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 9, 'player_hp': 91}) as second_attack_mock:
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)
        second_attack_mock.assert_called_once()
        self.assertEqual(state['player_hp'], 91)

    def test_absolute_zero_freeze_rider_no_longer_fizzles_before_enemy_response(self):
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 8, 'damage_max': 8, 'defense': 0}
        player = {'hp': 100, 'mana': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'mob_hp': 100,
            'mob_effects': [{'type': 'freeze', 'turns': 1, 'value': 0}],
            'log': [],
            'turn': 1,
        }

        combat.apply_pre_enemy_response_ticks(mob, state)
        self.assertEqual(state['mob_effects'][0]['type'], 'freeze')
        self.assertEqual(state['mob_effects'][0]['turns'], 1)

        with patch('game.combat.mob_attack') as mob_attack_mock:
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)
        mob_attack_mock.assert_not_called()
        self.assertEqual(state['mob_effects'], [])

    def test_poison_and_burn_pretick_behavior_stays_unchanged(self):
        mob_state = {
            'hp': 100,
            'defense': 0,
            'effects': [
                {'type': 'poison', 'turns': 1, 'value': 4},
                {'type': 'burn', 'turns': 1, 'value': 6},
                {'type': 'freeze', 'turns': 1, 'value': 0},
            ],
        }

        dmg, _ = skill_engine.apply_mob_effects(mob_state)

        self.assertEqual(dmg, 10)
        self.assertEqual(
            mob_state['effects'],
            [{'type': 'freeze', 'turns': 1, 'value': 0}],
        )

    def test_parry_uses_shared_enemy_precheck_before_trigger_resolution(self):
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

        mob_attack_mock.assert_not_called()
        self.assertEqual(state['player_hp'], 100)
        self.assertEqual(state['mob_hp'], 100)
        self.assertEqual(state['invincible_turns'], 0)
        # Parry не должен тратиться, если общий precheck пропустил атаку.
        self.assertTrue(state['parry_active'])

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

    def test_parry_path_respects_dodge_window_from_shared_precheck(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 10, 'damage_max': 10}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'parry_active': True,
            'parry_value': 1.0,
            'dodge_buff_turns': 1,
            'dodge_buff_value': 100,
        }

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 10, 'player_hp': 90}) as mob_attack_mock:
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        mob_attack_mock.assert_not_called()
        self.assertTrue(state['parry_active'])
        self.assertEqual(state['dodge_buff_turns'], 0)

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

    def test_berserk_natural_expiry_clears_berserk_damage_value(self):
        state = {'berserk_turns': 1, 'berserk_damage': 17}
        combat.tick_post_action_player_buff_durations(state)
        self.assertEqual(state['berserk_turns'], 0)
        self.assertEqual(state['berserk_damage'], 0)

    def test_berserk_penalty_natural_expiry_clears_penalty_value(self):
        state = {'berserk_defense_penalty_turns': 1, 'berserk_defense_penalty': 25}
        combat.tick_post_action_player_buff_durations(state)
        self.assertEqual(state['berserk_defense_penalty_turns'], 0)
        self.assertEqual(state['berserk_defense_penalty'], 0)

    def test_berserk_desynced_state_is_normalized_to_clean_inactive_runtime(self):
        state = {
            'berserk_turns': 0,
            'berserk_damage': 18,
            'berserk_defense_penalty_turns': 2,
            'berserk_defense_penalty': 25,
        }
        combat.tick_post_action_player_buff_durations(state)
        self.assertEqual(state['berserk_turns'], 0)
        self.assertEqual(state['berserk_damage'], 0)
        self.assertEqual(state['berserk_defense_penalty_turns'], 0)
        self.assertEqual(state['berserk_defense_penalty'], 0)

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

        self.assertEqual(result['final_damage'], 30)
        self.assertTrue(result['guaranteed_crit_applied'])
        self.assertEqual(state['guaranteed_crit_turns'], 0)
        self.assertEqual(state['hunters_mark_turns'], 1)
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

    def test_hunters_mark_is_not_global_direct_damage_modifier_anymore(self):
        result = combat.apply_direct_damage_action_modifiers(
            {'hunters_mark_turns': 2, 'hunters_mark_value': 50, 'vulnerability_turns': 0, 'vulnerability_value': 0, 'guaranteed_crit_turns': 0},
            20,
            can_consume_guaranteed_crit=False,
        )
        self.assertEqual(result['damage'], 20)

    def test_hunters_mark_is_not_consumed_in_generic_damage_modifier_path(self):
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

        self.assertEqual(damage_result['damage'], 20)
        self.assertEqual(turns_after_damage, 2)
        self.assertEqual(heal_result['damage'], 0)
        self.assertEqual(state['hunters_mark_turns'], 2)

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

        # 10 -> crit 25 -> vulnerability 30 (hunter mark no longer global here)
        self.assertEqual(result['skill_result']['damage'], 30)
        self.assertIn('30', result['battle_state']['log'][-1])
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

        # 10 -> crit 25, heal scales from 3 to 7
        self.assertEqual(result['skill_result']['damage'], 25)
        self.assertEqual(result['skill_result']['heal'], 7)
        self.assertEqual(result['battle_state']['player_hp'], 47)
        self.assertIn('25', result['battle_state']['log'][-1])
        self.assertIn('❤️+7', result['battle_state']['log'][-1])

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
        self.assertEqual(result['skill_result']['damage'], 25)
        self.assertEqual(result['skill_result']['heal'], 3)
        self.assertEqual(result['battle_state']['player_hp'], 43)

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
        self.assertEqual(result['skill_result']['damage'], 25)
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
        judged_state = dict(plain_state, mob_effects=[{'type': 'judgment_mark', 'turns': 2, 'value': 20}])

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
        self.assertEqual(result['skill_result']['damage'], 25)
        self.assertIn('25', result['battle_state']['log'][-1])
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
        self.assertEqual(result['skill_result']['damage'], 90)
        final_log = result['battle_state']['log'][-1]
        self.assertIn('90', final_log)
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
    def test_smoke_bomb_sets_dodge_buff_to_35_for_one_turn(self):
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
        self.assertEqual(battle_state['dodge_buff_turns'], 1)

    def test_backstab_gets_bonus_on_slowed_opened_target(self):
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
        self.assertEqual(result['damage'], 195)
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
        hit_check_patcher = patch(
            'game.combat.resolve_hit_check',
            return_value={
                'outcome': 'hit',
                'is_hit': True,
                'hit_chance': 95,
                'roll': 1,
                'accuracy_rating': 100,
                'evasion_rating': 100,
            },
        )
        self._hit_check_mock = hit_check_patcher.start()
        self.addAsyncCleanup(lambda: hit_check_patcher.stop())

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
        self.assertEqual(battle_state.get('vulnerability_source'), 'sword_rush')

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
        weakened_effect = next((e for e in battle_state.get('mob_effects', []) if e.get('type') == 'weakened'), None)
        self.assertIsNotNone(weakened_effect)
        self.assertEqual(weakened_effect['turns'], 2)
        self.assertGreater(weakened_effect['value'], 0)
        self.assertTrue(any(e['type'] == 'off_balance' for e in result['effects']))

        enemy_player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 10, 'damage_max': 10}
        battle_state_enemy = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [
                {'type': 'off_balance', 'turns': 1, 'value': 0},
                weakened_effect,
            ],
        }
        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 10, 'player_hp': 90}):
            log = combat.resolve_enemy_response(mob, enemy_player, battle_state_enemy, lang='ru', user_id=None)

        self.assertTrue(any('атак' in line.lower() for line in log))
        self.assertEqual(battle_state_enemy['player_hp'], 100 - int(10 * (1 - weakened_effect['value'] / 100)))

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
        self.assertEqual(battle_state.get('vulnerability_source'), 'expose_guard')

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

    def test_punishing_cut_has_stable_base_result_without_setup(self):
        player = {'mana': 100, 'strength': 14, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'melee', 'weapon_profile': 'sword_1h', 'player_mana': 100}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        punishing_cut = game_skills.get_skill('punishing_cut')
        skill_level = 1

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('punishing_cut', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')

        stats = {k: player.get(k, 1) for k in ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck')}
        base_attack = skill_engine.calc_final_damage(
            base_state['weapon_damage'],
            stats,
            base_state['weapon_type'],
            False,
            weapon_profile=base_state['weapon_profile'],
            damage_school='physical',
            armor_class=base_state.get('armor_class'),
            offhand_profile=base_state.get('offhand_profile'),
            encumbrance=base_state.get('encumbrance'),
        )
        expected_plain_damage = int(base_attack * (punishing_cut['base_value'] / 100) * (1 + punishing_cut['level_bonus'] * (skill_level - 1)))

        self.assertTrue(plain['success'])
        self.assertEqual(plain['damage'], expected_plain_damage)
        self.assertEqual(plain['log_key'], 'skills.log_damage')

    def test_punishing_cut_gets_payoff_into_vulnerability_window(self):
        player = {'mana': 100, 'strength': 14, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'melee', 'weapon_profile': 'sword_1h', 'player_mana': 100}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        punishing_cut = game_skills.get_skill('punishing_cut')

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('punishing_cut', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            vulnerable_state = dict(base_state, vulnerability_turns=2, vulnerability_value=25)
            vulnerable = skill_engine.use_skill('punishing_cut', dict(player), dict(mob_state), vulnerable_state, telegram_id=101, lang='ru')

        expected_vulnerable_damage = int(plain['damage'] * punishing_cut['payoff_vulnerable_mult'])
        self.assertEqual(vulnerable['damage'], expected_vulnerable_damage)
        self.assertEqual(vulnerable['log_key'], 'skills.log_punishing_cut')

    def test_punishing_cut_gets_tempo_payoff_with_press_the_line(self):
        player = {'mana': 100, 'strength': 14, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'melee', 'weapon_profile': 'sword_1h', 'player_mana': 100}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        punishing_cut = game_skills.get_skill('punishing_cut')

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('punishing_cut', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            tempo_state = dict(base_state, press_the_line_turns=1, press_the_line_value=16)
            tempo = skill_engine.use_skill('punishing_cut', dict(player), dict(mob_state), tempo_state, telegram_id=101, lang='ru')

        expected_tempo_damage = int(plain['damage'] * punishing_cut['payoff_press_line_mult'])
        self.assertEqual(tempo['damage'], expected_tempo_damage)
        self.assertEqual(tempo['log_key'], 'skills.log_punishing_cut_tempo')

    def test_punishing_cut_combined_window_uses_single_predictable_payoff_path(self):
        player = {'mana': 100, 'strength': 14, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'melee', 'weapon_profile': 'sword_1h', 'player_mana': 100}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        punishing_cut = game_skills.get_skill('punishing_cut')

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill(
                'punishing_cut',
                dict(player),
                dict(mob_state),
                dict(base_state),
                telegram_id=101,
                lang='ru',
            )
            vulnerable = skill_engine.use_skill(
                'punishing_cut',
                dict(player),
                dict(mob_state),
                dict(base_state, vulnerability_turns=2, vulnerability_value=25),
                telegram_id=101,
                lang='ru',
            )
            tempo = skill_engine.use_skill(
                'punishing_cut',
                dict(player),
                dict(mob_state),
                dict(base_state, press_the_line_turns=1, press_the_line_value=16),
                telegram_id=101,
                lang='ru',
            )
            combined = skill_engine.use_skill(
                'punishing_cut',
                dict(player),
                dict(mob_state),
                dict(base_state, vulnerability_turns=2, vulnerability_value=25, press_the_line_turns=1, press_the_line_value=16),
                telegram_id=101,
                lang='ru',
            )

        expected_vulnerable_damage = int(plain['damage'] * punishing_cut['payoff_vulnerable_mult'])
        expected_tempo_damage = int(plain['damage'] * punishing_cut['payoff_press_line_mult'])
        expected_combined_damage = int(plain['damage'] * punishing_cut['payoff_combined_mult'])

        self.assertEqual(combined['log_key'], 'skills.log_punishing_cut_combined')
        self.assertEqual(vulnerable['damage'], expected_vulnerable_damage)
        self.assertEqual(tempo['damage'], expected_tempo_damage)
        self.assertEqual(combined['damage'], expected_combined_damage)

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

    def test_counter_base_behavior_is_stable_without_setup(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 20, 'damage_max': 20}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'weapon_profile': 'sword_1h',
            'offhand_profile': 'none',
            'defense_buff_turns': 0,
            'vulnerability_turns': 0,
            'weaken_turns': 0,
            'disarm_turns': 0,
        }

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 20, 'player_hp': 80}), \
             patch('game.weapon_mastery.get_skill_level', return_value=1), \
             patch('game.combat.random.random', return_value=0.0):
            log = combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=101)

        self.assertEqual(state['mob_hp'], 93)
        self.assertTrue(any('Контратака!' in line for line in log))

    def test_counter_gets_payoff_on_opened_target_from_runtime_effect(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 20, 'damage_max': 20}
        base_state = {
            'player_hp': 100,
            'mob_hp': 100,
            'weapon_profile': 'sword_1h',
            'offhand_profile': 'none',
            'defense_buff_turns': 0,
            'vulnerability_turns': 0,
            'weaken_turns': 0,
            'disarm_turns': 0,
        }
        plain_state = dict(base_state, mob_effects=[])
        opened_state = dict(base_state, mob_effects=[{'type': 'off_balance', 'turns': 1, 'value': 0}])

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 20, 'player_hp': 80}), \
             patch('game.weapon_mastery.get_skill_level', return_value=1), \
             patch('game.combat.random.random', return_value=0.0):
            plain_log = combat.resolve_enemy_response(mob, player, plain_state, lang='ru', user_id=101)

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 20, 'player_hp': 80}), \
             patch('game.weapon_mastery.get_skill_level', return_value=1), \
             patch('game.combat.random.random', return_value=0.0):
            opened_log = combat.resolve_enemy_response(mob, player, opened_state, lang='ru', user_id=101)

        plain_damage = 100 - plain_state['mob_hp']
        opened_damage = 100 - opened_state['mob_hp']
        self.assertGreater(opened_damage, plain_damage)
        self.assertTrue(any('открытой цели' in line for line in opened_log))
        self.assertTrue(any('Контратака!' in line for line in plain_log))

    def test_shield_bash_runtime_opened_state_is_read_by_counter_path(self):
        player = {'hp': 100, 'mana': 100, 'strength': 10, 'agility': 1, 'intuition': 1, 'vitality': 12, 'wisdom': 1, 'luck': 1}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 20, 'damage_max': 20, 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_mana': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'weapon_damage': 14,
            'weapon_type': 'melee',
            'weapon_profile': 'sword_1h',
            'offhand_profile': 'none',
            'defense_buff_turns': 0,
            'vulnerability_turns': 0,
            'weaken_turns': 0,
            'disarm_turns': 0,
        }
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            shield_bash_result = skill_engine.use_skill(
                'shield_bash',
                dict(player),
                dict(mob_state),
                battle_state,
                telegram_id=101,
                lang='ru',
            )

        self.assertTrue(any(e.get('type') == 'off_balance' for e in shield_bash_result.get('effects', [])))
        battle_state['mob_effects'].extend(shield_bash_result.get('effects', []))

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 20, 'player_hp': 80}), \
             patch('game.weapon_mastery.get_skill_level', return_value=1), \
             patch('game.combat.random.random', return_value=0.0):
            log = combat.resolve_enemy_response(mob, player, battle_state, lang='ru', user_id=101)

        self.assertTrue(any('открытой цели' in line for line in log))

    def test_counter_combined_path_uses_single_combined_multiplier_not_double_stack(self):
        from game.skills import get_skill

        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 20, 'damage_max': 20}
        base_state = {
            'player_hp': 100,
            'mob_hp': 100,
            'weapon_profile': 'sword_1h',
            'offhand_profile': 'none',
            'defense_buff_value': 20,
            'vulnerability_turns': 0,
            'weaken_turns': 0,
            'disarm_turns': 0,
        }
        opened_state = dict(base_state, defense_buff_turns=0, mob_effects=[{'type': 'off_balance', 'turns': 1, 'value': 0}])
        combined_state = dict(base_state, defense_buff_turns=2, mob_effects=[{'type': 'off_balance', 'turns': 1, 'value': 0}])

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 20, 'player_hp': 80}), \
             patch('game.weapon_mastery.get_skill_level', return_value=1), \
             patch('game.combat.random.random', return_value=0.0):
            combat.resolve_enemy_response(mob, player, opened_state, lang='ru', user_id=101)

        with patch('game.combat.mob_attack', return_value={'type': 'mob_attack', 'damage': 20, 'player_hp': 80}), \
             patch('game.weapon_mastery.get_skill_level', return_value=1), \
             patch('game.combat.random.random', return_value=0.0):
            combined_log = combat.resolve_enemy_response(mob, player, combined_state, lang='ru', user_id=101)

        counter_skill = get_skill('counter')
        mitigated_damage = int(20 * (1 - base_state['defense_buff_value'] / 100))
        base_counter_damage = int(mitigated_damage * (0.30 + 0.07 * 1))
        expected_combined = int(base_counter_damage * counter_skill['payoff_opened_defense_mult'])

        combined_damage = 100 - combined_state['mob_hp']
        opened_damage = 100 - opened_state['mob_hp']
        hypothetical_double_stack = int(
            int(20 * (0.30 + 0.07 * 1) * counter_skill['payoff_opened_mult'])
            * counter_skill['payoff_defense_setup_mult']
        )

        self.assertEqual(combined_damage, expected_combined)
        self.assertLess(combined_damage, hypothetical_double_stack)
        self.assertNotEqual(combined_damage, opened_damage)
        self.assertTrue(any('защитном размене' in line for line in combined_log))

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

    def test_backstab_opened_payoff_triggers_from_runtime_weakened_effect(self):
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
            opened_from_weakened = skill_engine.use_skill(
                'backstab',
                dict(player),
                dict(mob_state),
                dict(base_state, mob_effects=[{'type': 'weakened', 'turns': 2, 'value': 10}]),
                telegram_id=101,
                lang='ru',
            )

        self.assertGreater(opened_from_weakened['damage'], plain['damage'])
        self.assertEqual(opened_from_weakened['log_key'], 'skills.log_backstab_crit')

    def test_envenom_blades_buffs_only_next_poison_application(self):
        player = {'hp': 100, 'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'player_max_mana': 100,
            'mob_hp': 120,
            'mob_effects': [],
            'log': [],
            'turn': 1,
            'weapon_damage': 14,
            'weapon_type': 'melee',
            'weapon_profile': 'dagger',
        }
        hit_check = {
            'outcome': 'hit',
            'is_hit': True,
            'hit_chance': 100,
            'roll': 1,
            'accuracy_rating': 999,
            'evasion_rating': 0,
            'guaranteed_hit': False,
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_enemy_response', return_value=[]), \
             patch('game.combat.resolve_hit_check', side_effect=[hit_check, hit_check]):
            setup = combat.process_skill_turn('envenom_blades', player, mob, battle_state, user_id=101, lang='ru')
            first = combat.process_skill_turn('toxic_cut', player, mob, battle_state, user_id=101, lang='ru')
            second = combat.process_skill_turn('toxic_cut', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(setup['success'])
        self.assertGreater(first['skill_result']['effects'][0]['turns'], second['skill_result']['effects'][0]['turns'])
        self.assertFalse(second['battle_state'].get('envenom_blades_active', False))

    def test_envenom_blades_is_not_consumed_by_non_poison_skill(self):
        player = {'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {'weapon_damage': 14, 'weapon_type': 'melee', 'weapon_profile': 'dagger', 'player_mana': 100, 'mob_effects': []}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            skill_engine.use_skill('envenom_blades', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')
            skill_engine.use_skill('backstab', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')
            toxic_cut_result = skill_engine.use_skill('toxic_cut', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')

        self.assertGreater(toxic_cut_result['effects'][0]['turns'], 3)
        self.assertTrue(state.get('envenom_blades_active', False))

    def test_envenom_blades_not_consumed_when_toxic_cut_misses_hit_gate(self):
        player = {'hp': 100, 'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'player_max_mana': 100,
            'mob_hp': 120,
            'mob_effects': [],
            'log': [],
            'turn': 1,
            'weapon_damage': 14,
            'weapon_type': 'melee',
            'weapon_profile': 'dagger',
        }

        miss_check = {
            'outcome': 'dodge',
            'is_hit': False,
            'hit_chance': 0,
            'roll': 99,
            'accuracy_rating': 0,
            'evasion_rating': 999,
            'guaranteed_hit': False,
        }
        hit_check = {
            'outcome': 'hit',
            'is_hit': True,
            'hit_chance': 100,
            'roll': 1,
            'accuracy_rating': 999,
            'evasion_rating': 0,
            'guaranteed_hit': False,
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_enemy_response', return_value=[]), \
             patch('game.combat.resolve_hit_check', side_effect=[miss_check, hit_check]):
            setup_result = combat.process_skill_turn('envenom_blades', player, mob, battle_state, user_id=101, lang='ru')
            miss_result = combat.process_skill_turn('toxic_cut', player, mob, battle_state, user_id=101, lang='ru')

            self.assertTrue(setup_result['success'])
            self.assertTrue(miss_result['success'])
            self.assertTrue(miss_result['skill_result']['direct_damage_result']['hit_check']['is_hit'] is False)
            self.assertTrue(miss_result['battle_state'].get('envenom_blades_active', False))

            hit_result = combat.process_skill_turn('toxic_cut', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(hit_result['success'])
        self.assertTrue(hit_result['skill_result']['direct_damage_result']['hit_check']['is_hit'])
        self.assertGreater(hit_result['skill_result']['effects'][0]['turns'], 3)
        self.assertFalse(hit_result['battle_state'].get('envenom_blades_active', False))

    def test_generic_poison_effect_hit_gated_path_consumes_envenom_only_after_hit(self):
        from game.skills import get_skill as base_get_skill

        player = {'hp': 100, 'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'player_max_mana': 100,
            'mob_hp': 140,
            'mob_effects': [],
            'log': [],
            'turn': 1,
            'weapon_damage': 14,
            'weapon_type': 'melee',
            'weapon_profile': 'dagger',
        }

        miss_check = {
            'outcome': 'dodge',
            'is_hit': False,
            'hit_chance': 0,
            'roll': 99,
            'accuracy_rating': 0,
            'evasion_rating': 999,
            'guaranteed_hit': False,
        }
        hit_check = {
            'outcome': 'hit',
            'is_hit': True,
            'hit_chance': 100,
            'roll': 1,
            'accuracy_rating': 999,
            'evasion_rating': 0,
            'guaranteed_hit': False,
        }

        def patched_get_skill(skill_id):
            skill = base_get_skill(skill_id)
            if skill_id == 'poison_blade' and skill:
                modified = dict(skill)
                modified['type'] = 'damage'
                modified['base_value'] = 105
                modified['level_bonus'] = 0.10
                return modified
            return skill

        with patch('game.skill_engine.get_skill', side_effect=patched_get_skill), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.skill_engine.random.random', return_value=0.0), \
             patch('game.combat.resolve_enemy_response', return_value=[]), \
             patch('game.combat.resolve_hit_check', side_effect=[miss_check, hit_check, hit_check]):
            combat.process_skill_turn('envenom_blades', player, mob, battle_state, user_id=101, lang='ru')
            miss_result = combat.process_skill_turn('poison_blade', player, mob, battle_state, user_id=101, lang='ru')

            self.assertTrue(miss_result['success'])
            self.assertFalse(miss_result['skill_result']['direct_damage_result']['hit_check']['is_hit'])
            self.assertTrue(miss_result['battle_state'].get('envenom_blades_active', False))

            boosted_hit = combat.process_skill_turn('poison_blade', player, mob, battle_state, user_id=101, lang='ru')
            base_hit = combat.process_skill_turn('poison_blade', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(boosted_hit['success'])
        self.assertTrue(base_hit['success'])
        self.assertFalse(boosted_hit['battle_state'].get('envenom_blades_active', False))
        self.assertEqual(
            boosted_hit['skill_result']['effects'][0]['value'],
            base_hit['skill_result']['effects'][0]['value'] * 2,
        )

    def test_quick_slice_has_stable_base_result_without_setup(self):
        player = {'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {'weapon_damage': 14, 'weapon_type': 'melee', 'weapon_profile': 'dagger', 'player_mana': 100, 'mob_effects': []}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('quick_slice', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')

        self.assertGreater(result['damage'], 0)
        self.assertFalse(any(e.get('type') == 'slow' for e in result['effects']))

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

    def test_widows_kiss_gets_payoff_bonus_on_poisoned_or_weakened_target(self):
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
            weakened = skill_engine.use_skill(
                'widows_kiss',
                dict(player),
                dict(mob_state),
                dict(base_state, mob_effects=[{'type': 'weakened', 'turns': 2, 'value': 8}]),
                telegram_id=101,
                lang='ru',
            )

        self.assertGreater(poisoned['damage'], plain['damage'])
        self.assertGreater(weakened['damage'], plain['damage'])
        self.assertEqual(poisoned['log_key'], 'skills.log_widows_kiss_payoff')
        self.assertEqual(weakened['log_key'], 'skills.log_widows_kiss_payoff')

    def test_widows_kiss_gets_payoff_bonus_on_opened_target(self):
        player = {'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 14, 'weapon_type': 'melee', 'weapon_profile': 'dagger', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('widows_kiss', dict(player), dict(mob_state), dict(base_state, mob_effects=[]), telegram_id=101, lang='ru')
            opened = skill_engine.use_skill(
                'widows_kiss',
                dict(player),
                dict(mob_state),
                dict(base_state, mob_effects=[{'type': 'slow', 'turns': 1, 'value': 0}]),
                telegram_id=101,
                lang='ru',
            )

        self.assertGreater(opened['damage'], plain['damage'])
        self.assertEqual(opened['log_key'], 'skills.log_widows_kiss_payoff')

    def test_rupture_toxins_consumes_poison_effects_and_keeps_slow(self):
        player = {'hp': 100, 'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob = {'id': 'wolf', 'defense': 0}
        state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'player_max_mana': 100,
            'mob_hp': 120,
            'log': [],
            'turn': 1,
            'weapon_damage': 14,
            'weapon_type': 'melee',
            'weapon_profile': 'dagger',
            'mob_effects': [
                {'type': 'poison', 'turns': 2, 'value': 8},
                {'type': 'poison', 'turns': 1, 'value': 5},
                {'type': 'slow', 'turns': 1, 'value': 0},
            ],
        }
        hit_check = {
            'outcome': 'hit',
            'is_hit': True,
            'hit_chance': 100,
            'roll': 1,
            'accuracy_rating': 999,
            'evasion_rating': 0,
            'guaranteed_hit': False,
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_enemy_response', return_value=[]), \
             patch('game.combat.resolve_hit_check', return_value=hit_check):
            result = combat.process_skill_turn('rupture_toxins', player, mob, state, user_id=101, lang='ru')

        self.assertGreater(result['skill_result']['damage'], 0)
        self.assertTrue(all(e.get('type') != 'poison' for e in state['mob_effects']))
        self.assertTrue(any(e.get('type') == 'slow' for e in state['mob_effects']))

    def test_rupture_toxins_scales_with_total_poison_strength(self):
        player = {'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        weak_poison_state = {
            'weapon_damage': 14,
            'weapon_type': 'melee',
            'weapon_profile': 'dagger',
            'player_mana': 100,
            'mob_effects': [
                {'type': 'poison', 'turns': 2, 'value': 3},
                {'type': 'poison', 'turns': 2, 'value': 3},
            ],
        }
        strong_poison_state = {
            **weak_poison_state,
            'mob_effects': [
                {'type': 'poison', 'turns': 2, 'value': 10},
                {'type': 'poison', 'turns': 2, 'value': 10},
            ],
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            weak = skill_engine.use_skill('rupture_toxins', dict(player), dict(mob_state), weak_poison_state, telegram_id=101, lang='ru')
            strong = skill_engine.use_skill('rupture_toxins', dict(player), dict(mob_state), strong_poison_state, telegram_id=101, lang='ru')

        self.assertGreater(strong['damage'], weak['damage'])

    def test_rupture_toxins_not_consumed_on_miss_and_consumed_on_next_hit(self):
        player = {'hp': 100, 'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'player_max_mana': 100,
            'mob_hp': 140,
            'mob_effects': [
                {'type': 'poison', 'turns': 2, 'value': 7},
                {'type': 'poison', 'turns': 2, 'value': 6},
                {'type': 'slow', 'turns': 1, 'value': 0},
            ],
            'log': [],
            'turn': 1,
            'weapon_damage': 14,
            'weapon_type': 'melee',
            'weapon_profile': 'dagger',
        }
        miss_check = {
            'outcome': 'dodge',
            'is_hit': False,
            'hit_chance': 0,
            'roll': 99,
            'accuracy_rating': 0,
            'evasion_rating': 999,
            'guaranteed_hit': False,
        }
        hit_check = {
            'outcome': 'hit',
            'is_hit': True,
            'hit_chance': 100,
            'roll': 1,
            'accuracy_rating': 999,
            'evasion_rating': 0,
            'guaranteed_hit': False,
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_enemy_response', return_value=[]), \
             patch('game.combat.resolve_hit_check', side_effect=[miss_check, hit_check]):
            miss_result = combat.process_skill_turn('rupture_toxins', player, mob, battle_state, user_id=101, lang='ru')
            self.assertTrue(miss_result['success'])
            self.assertFalse(miss_result['skill_result']['direct_damage_result']['hit_check']['is_hit'])
            self.assertTrue(any(e.get('type') == 'poison' for e in miss_result['battle_state']['mob_effects']))

            hit_result = combat.process_skill_turn('rupture_toxins', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(hit_result['success'])
        self.assertTrue(hit_result['skill_result']['direct_damage_result']['hit_check']['is_hit'])
        self.assertEqual(hit_result['skill_result'].get('log_key'), 'skills.log_rupture_toxins')
        self.assertTrue(all(e.get('type') != 'poison' for e in hit_result['battle_state']['mob_effects']))
        self.assertTrue(any(e.get('type') == 'slow' for e in hit_result['battle_state']['mob_effects']))

    def test_shadow_chain_finisher_stronger_on_opened_target(self):
        player = {'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 14, 'weapon_type': 'melee', 'weapon_profile': 'dagger', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('shadow_chain', dict(player), dict(mob_state), dict(base_state, mob_effects=[]), telegram_id=101, lang='ru')
            opened = skill_engine.use_skill(
                'shadow_chain',
                dict(player),
                dict(mob_state),
                dict(base_state, mob_effects=[{'type': 'slow', 'turns': 1, 'value': 0}]),
                telegram_id=101,
                lang='ru',
            )

        self.assertGreater(opened['damage'], plain['damage'])
        self.assertEqual(opened['log_key'], 'skills.log_shadow_chain_opened')

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
        base_state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100, 'mob_effects': []}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('aimed_shot', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            marked = skill_engine.use_skill(
                'aimed_shot',
                dict(player),
                dict(mob_state),
                dict(base_state, mob_effects=[{'type': 'hunters_mark', 'turns': 2, 'value': 20}]),
                telegram_id=101,
                lang='ru',
            )

        self.assertGreater(marked['damage'], plain['damage'])

    def test_aimed_shot_applies_accuracy_bonus_override(self):
        player = {'mana': 100, 'strength': 1, 'agility': 10, 'intuition': 16, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('aimed_shot', dict(player), dict(mob_state), dict(state), telegram_id=101, lang='ru')

        self.assertEqual(result.get('accuracy_bonus'), 25)

    def test_deadeye_applies_guaranteed_hit_override(self):
        player = {'mana': 100, 'strength': 1, 'agility': 10, 'intuition': 16, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('deadeye', dict(player), dict(mob_state), dict(state), telegram_id=101, lang='ru')

        self.assertTrue(result.get('guaranteed_hit'))

    def test_aimed_shot_uses_phase3_accuracy_hook_in_combat_flow(self):
        player = {'agility': 5, 'luck': 5, 'mana': 100}
        mob = {'id': 'wolf', 'level': 2}
        state = {'mob_hp': 100}
        skill_result = {
            'direct_damage_skill': True,
            'target_kind': 'enemy',
            'damage': 20,
            'effects': [],
            'accuracy_bonus': 25,
        }

        with patch('game.combat.get_player_accuracy_rating', return_value=120), \
             patch('game.combat.get_enemy_evasion_rating', return_value=90), \
             patch('game.combat.resolve_hit_check', return_value={'outcome': 'miss', 'is_hit': False}) as hit_check_mock:
            combat.resolve_enemy_targeted_direct_damage_skill_action(
                player,
                mob,
                state,
                skill_result,
                lang='ru',
            )

        hit_check_mock.assert_called_once_with(145, 90)

    def test_deadeye_bypasses_hit_check_in_combat_flow(self):
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
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.get_player_accuracy_rating') as accuracy_mock, \
             patch('game.combat.get_enemy_evasion_rating') as evasion_mock, \
             patch('game.combat.resolve_hit_check') as hit_check_mock, \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('deadeye', player, mob, battle_state, user_id=101, lang='ru')

        accuracy_mock.assert_not_called()
        evasion_mock.assert_not_called()
        hit_check_mock.assert_not_called()
        self.assertTrue(result['success'])
        self.assertTrue(result['skill_result']['direct_damage_result']['hit_check']['guaranteed_hit'])
        self.assertGreater(result['skill_result']['damage'], 0)

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
            'steady_aim_turns': 0,
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_hit_check', return_value={'outcome': 'hit', 'is_hit': True, 'hit_chance': 90, 'roll': 10}), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            setup = combat.process_skill_turn('steady_aim', player, mob, battle_state, user_id=101, lang='ru')
            self.assertTrue(setup['success'])
            self.assertEqual(setup['battle_state'].get('steady_aim_turns', 0), 1)
            attack = combat.process_skill_turn('aimed_shot', player, mob, battle_state, user_id=101, lang='ru')

        self.assertGreaterEqual(attack['skill_result']['damage'], 0)
        self.assertEqual(battle_state.get('steady_aim_turns', 0), 0)

    def test_piercing_arrow_gets_payoff_bonus_vs_marked_target(self):
        player = {'mana': 100, 'strength': 1, 'agility': 10, 'intuition': 16, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 20, 'effects': []}
        base_state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100, 'mob_effects': []}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('piercing_arrow', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            marked = skill_engine.use_skill(
                'piercing_arrow',
                dict(player),
                dict(mob_state),
                dict(base_state, mob_effects=[{'type': 'hunters_mark', 'turns': 2, 'value': 20}]),
                telegram_id=101,
                lang='ru',
            )

        self.assertGreater(marked['damage'], plain['damage'])

    def test_piercing_arrow_armored_only_path_uses_non_marked_log_key(self):
        player = {'mana': 100, 'strength': 1, 'agility': 10, 'intuition': 16, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 20, 'effects': []}
        state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100, 'mob_effects': []}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('piercing_arrow', dict(player), dict(mob_state), dict(state), telegram_id=101, lang='ru')

        self.assertEqual(result.get('log_key'), 'skills.log_piercing_arrow_armored')
        self.assertNotIn('marked', result.get('log_key', ''))

    def test_hamstring_arrow_applies_slow(self):
        player = {'mana': 100, 'strength': 1, 'agility': 14, 'intuition': 10, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('hamstring_arrow', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')

        slow_effect = next((e for e in result['effects'] if e.get('type') == 'slow'), None)
        self.assertIsNotNone(slow_effect)
        self.assertEqual(slow_effect.get('turns'), game_skills.get_skill('hamstring_arrow').get('slow_duration'))

    def test_reposition_sets_dodge_buff_correctly(self):
        player = {'mana': 100, 'strength': 1, 'agility': 14, 'intuition': 10, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('reposition', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')

        self.assertEqual(state.get('dodge_buff_turns', 0), 1)
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
                dict(base_state, mob_effects=[{'type': 'hunters_mark', 'turns': 2, 'value': 20}]),
                telegram_id=101,
                lang='ru',
            )

        self.assertGreater(rain_slowed['damage'], rain_plain['damage'])
        self.assertLess(rain_slowed['damage'], deadeye_marked['damage'])

    def test_hunters_mark_sets_runtime_target_state_with_data_duration(self):
        player = {'mana': 100, 'strength': 1, 'agility': 10, 'intuition': 16, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100, 'mob_effects': []}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('hunters_mark', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')

        self.assertTrue(result['success'])
        mark_effect = next((e for e in state['mob_effects'] if e.get('type') == 'hunters_mark'), None)
        self.assertIsNotNone(mark_effect)
        self.assertEqual(mark_effect.get('turns'), game_skills.get_skill('hunters_mark').get('duration'))

    def test_hunters_mark_legacy_mirrors_follow_merged_runtime_state(self):
        player = {'mana': 100, 'strength': 1, 'agility': 10, 'intuition': 10, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        state = {
            'weapon_damage': 14,
            'weapon_type': 'ranged',
            'weapon_profile': 'short_bow',
            'player_mana': 100,
            'mob_effects': [{'type': 'hunters_mark', 'turns': 5, 'value': 99, 'skill_id': 'hunters_mark'}],
            'hunters_mark_turns': 0,
            'hunters_mark_value': 0,
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('hunters_mark', dict(player), dict(mob_state), state, telegram_id=101, lang='ru')

        self.assertTrue(result['success'])
        merged_mark = next((e for e in state['mob_effects'] if e.get('type') == 'hunters_mark'), None)
        self.assertIsNotNone(merged_mark)
        self.assertEqual(merged_mark.get('turns'), 5)
        self.assertEqual(merged_mark.get('value'), 99)
        self.assertEqual(state['hunters_mark_turns'], merged_mark.get('turns'))
        self.assertEqual(state['hunters_mark_value'], merged_mark.get('value'))

    def test_deadeye_marked_focus_is_strongest_sniper_payoff(self):
        player = {'mana': 100, 'strength': 1, 'agility': 14, 'intuition': 14, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 20, 'effects': []}
        base_state = {'weapon_damage': 14, 'weapon_type': 'ranged', 'weapon_profile': 'short_bow', 'player_mana': 100, 'mob_effects': []}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            rain_slowed = skill_engine.use_skill(
                'rain_of_barbs',
                dict(player),
                dict(mob_state),
                dict(base_state, mob_effects=[{'type': 'slow', 'turns': 2, 'value': 0}]),
                telegram_id=101,
                lang='ru',
            )
            deadeye_marked_focus = skill_engine.use_skill(
                'deadeye',
                dict(player),
                dict(mob_state),
                dict(base_state, steady_aim_turns=1, mob_effects=[{'type': 'hunters_mark', 'turns': 2, 'value': 20}]),
                telegram_id=101,
                lang='ru',
            )

        self.assertGreater(deadeye_marked_focus['damage'], rain_slowed['damage'])

    def test_piercing_arrow_marked_and_armored_uses_controlled_combined_multiplier(self):
        player = {'mana': 100, 'strength': 1, 'agility': 10, 'intuition': 16, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 20, 'effects': []}
        state = {
            'weapon_damage': 14,
            'weapon_type': 'ranged',
            'weapon_profile': 'short_bow',
            'player_mana': 100,
            'mob_effects': [{'type': 'hunters_mark', 'turns': 2, 'value': 20}],
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('piercing_arrow', dict(player), dict(mob_state), dict(state), telegram_id=101, lang='ru')

        base_skill = game_skills.get_skill('piercing_arrow')
        base_state = dict(state, mob_effects=[])
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('piercing_arrow', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')

        max_expected = int(plain['damage'] * (base_skill['marked_armored_mult'] / base_skill['armored_mult']))
        self.assertIn(result['damage'], (max_expected, max_expected + 1))

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

    def test_magic_staff_tree_is_full_5_plus_5(self):
        tree = game_skills.SKILL_TREES['magic_staff']
        self.assertEqual(len(tree['A']), 5)
        self.assertEqual(len(tree['B']), 5)

    def test_magic_staff_branch_a_order_matches_final_design(self):
        expected = ['fireball', 'arcane_surge', 'flame_wave', 'arcane_lance', 'cataclysm']
        self.assertEqual(game_skills.SKILL_TREES['magic_staff']['A'], expected)

    def test_magic_staff_branch_b_order_matches_final_design(self):
        expected = ['frost_bolt', 'ice_shackles', 'mana_shield', 'shatter', 'absolute_zero']
        self.assertEqual(game_skills.SKILL_TREES['magic_staff']['B'], expected)

    def test_legacy_magic_staff_ids_stay_in_skills_but_not_in_active_tree(self):
        tree_skills = set(game_skills.SKILL_TREES['magic_staff']['A'] + game_skills.SKILL_TREES['magic_staff']['B'])
        for legacy_id in ('burning_ground', 'fire_shield', 'meteor', 'ice_lance', 'ice_chains', 'blizzard'):
            self.assertIn(legacy_id, game_skills.SKILLS)
            self.assertNotIn(legacy_id, tree_skills)

    def test_arcane_surge_sets_runtime_state(self):
        player = {'mana': 100, 'intuition': 18}
        state = {'weapon_damage': 12, 'weapon_type': 'magic', 'weapon_profile': 'magic_staff'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('arcane_surge', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertEqual(state.get('arcane_surge_turns', 0), game_skills.SKILLS['arcane_surge']['setup_runtime_turns'])
        self.assertGreater(state.get('arcane_surge_value', 0), 0)

    def test_fireball_keeps_stable_base_and_predictable_burn_from_skill_data(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 20, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'magic_staff'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.skill_engine.random.random', return_value=0.0):
            result = skill_engine.use_skill('fireball', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertGreater(result['damage'], 0)
        burn_effects = [e for e in result['effects'] if e.get('type') == 'burn']
        self.assertTrue(len(burn_effects) > 0)
        self.assertTrue(all(e.get('turns', 0) == game_skills.SKILLS['fireball']['effect'][2] for e in burn_effects))

    def test_arcane_lance_gets_surge_payoff_without_early_consume_in_engine(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 20, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'magic_staff'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('arcane_lance', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, dict(base_state), telegram_id=101, lang='ru')
            surged_state = dict(base_state, arcane_surge_turns=1, arcane_surge_value=30)
            surged = skill_engine.use_skill('arcane_lance', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, surged_state, telegram_id=101, lang='ru')
        self.assertGreater(surged['damage'], plain['damage'])
        self.assertEqual(surged_state.get('arcane_surge_turns', 0), 1)
        self.assertTrue(any(a.get('type') == 'consume_arcane_surge_setup' for a in surged.get('post_hit_actions', [])))

    def test_arcane_surge_consumes_only_after_successful_payoff_hit(self):
        player = {'mana': 100, 'hp': 100, 'max_hp': 100, 'strength': 1, 'agility': 1, 'intuition': 20, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob = {'id': 'wolf', 'name': 'Wolf', 'hp': 300, 'damage': 1, 'defense': 0, 'effects': []}
        base_state = {
            'mob_id': 'wolf',
            'mob_hp': 300,
            'mob_max_hp': 300,
            'mob_effects': [],
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'player_max_mana': 100,
            'log': [],
            'weapon_damage': 14,
            'weapon_type': 'magic',
            'weapon_profile': 'magic_staff',
            'arcane_surge_turns': 2,
            'arcane_surge_value': 35,
        }

        with patch('game.combat.precheck_skill_use', return_value={'success': True, 'log': ''}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': False, 'outcome': 'miss'}), \
             patch('game.combat.mob_attack', return_value={'type': 'hit', 'damage': 0}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            missed_state = dict(base_state)
            combat.process_skill_turn('arcane_lance', dict(player), dict(mob), missed_state, user_id=101, lang='ru')
        self.assertEqual(missed_state.get('arcane_surge_turns', 0), 1)

        with patch('game.combat.precheck_skill_use', return_value={'success': True, 'log': ''}), \
             patch('game.combat.resolve_hit_check', return_value={'is_hit': True, 'outcome': 'hit'}), \
             patch('game.combat.mob_attack', return_value={'type': 'hit', 'damage': 0}), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            hit_state = dict(base_state)
            combat.process_skill_turn('arcane_lance', dict(player), dict(mob), hit_state, user_id=101, lang='ru')
        self.assertEqual(hit_state.get('arcane_surge_turns', 0), 0)

    def test_frost_bolt_applies_slow_setup(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 20, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'magic_staff'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.skill_engine.random.random', return_value=0.0):
            result = skill_engine.use_skill('frost_bolt', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        slow_effects = [e for e in result['effects'] if e.get('type') == 'slow']
        self.assertTrue(len(slow_effects) > 0)
        self.assertTrue(all(e.get('turns', 0) == game_skills.SKILLS['frost_bolt']['effect'][2] for e in slow_effects))

    def test_ice_shackles_applies_freeze_with_zero_control_value(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 20, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'magic_staff'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.random', return_value=0.0):
            result = skill_engine.use_skill('ice_shackles', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        freeze_effects = [e for e in result['effects'] if e.get('type') == 'freeze']
        self.assertTrue(len(freeze_effects) > 0)
        self.assertTrue(all(e.get('turns', 0) > 0 for e in freeze_effects))
        self.assertTrue(all(e.get('value', -1) == 0 for e in freeze_effects))

    def test_mana_shield_sets_defense_runtime_state(self):
        player = {'mana': 100, 'intuition': 18}
        state = {'weapon_damage': 12, 'weapon_type': 'magic', 'weapon_profile': 'magic_staff'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('mana_shield', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertGreater(state.get('defense_buff_turns', 0), 0)
        self.assertGreater(state.get('defense_buff_value', 0), 0)

    def test_shatter_uses_controlled_payoff_path_without_chaos_stacking(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 20, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'magic_staff'}
        mob_plain = {'hp': 100, 'defense': 0, 'effects': []}
        mob_slowed = {'hp': 100, 'defense': 0, 'effects': [{'type': 'slow', 'turns': 2, 'value': 0}]}
        mob_frozen = {'hp': 100, 'defense': 0, 'effects': [{'type': 'freeze', 'turns': 1, 'value': 0}]}
        mob_controlled = {'hp': 100, 'defense': 0, 'effects': [{'type': 'slow', 'turns': 2, 'value': 0}, {'type': 'freeze', 'turns': 1, 'value': 0}]}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('shatter', dict(player), mob_plain, dict(base_state), telegram_id=101, lang='ru')
            slow_payoff = skill_engine.use_skill('shatter', dict(player), mob_slowed, dict(base_state), telegram_id=101, lang='ru')
            freeze_payoff = skill_engine.use_skill('shatter', dict(player), mob_frozen, dict(base_state), telegram_id=101, lang='ru')
            controlled_payoff = skill_engine.use_skill('shatter', dict(player), mob_controlled, dict(base_state), telegram_id=101, lang='ru')
        self.assertGreater(slow_payoff['damage'], plain['damage'])
        self.assertGreater(freeze_payoff['damage'], slow_payoff['damage'])
        self.assertGreater(controlled_payoff['damage'], freeze_payoff['damage'])

    def test_absolute_zero_no_longer_applies_long_freeze_lock(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 20, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'magic_staff'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.skill_engine.random.random', return_value=0.0):
            result = skill_engine.use_skill('absolute_zero', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        freeze_turns = [e.get('turns', 0) for e in result['effects'] if e.get('type') == 'freeze']
        self.assertTrue(result['damage'] > 0)
        self.assertTrue(all(turns <= 1 for turns in freeze_turns))

    def test_cataclysm_gets_controlled_bonus_on_surge_and_burning_target(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 20, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'magic_staff'}
        mob_plain = {'hp': 100, 'defense': 0, 'effects': []}
        mob_burning = {'hp': 100, 'defense': 0, 'effects': [{'type': 'burn', 'turns': 2, 'value': 9}]}

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('cataclysm', dict(player), dict(mob_plain), dict(base_state), telegram_id=101, lang='ru')
            burning = skill_engine.use_skill('cataclysm', dict(player), dict(mob_burning), dict(base_state), telegram_id=101, lang='ru')
            surged_burning = skill_engine.use_skill(
                'cataclysm',
                dict(player),
                dict(mob_burning),
                dict(base_state, arcane_surge_turns=1, arcane_surge_value=30),
                telegram_id=101,
                lang='ru',
            )
        self.assertGreater(burning['damage'], plain['damage'])
        self.assertGreater(surged_burning['damage'], burning['damage'])
        self.assertTrue(any(a.get('type') == 'consume_arcane_surge_setup' for a in surged_burning.get('post_hit_actions', [])))

    def test_flame_wave_stays_stable_two_hit_pressure_spell(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 20, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'magic_staff'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('flame_wave', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertTrue(result['damage'] > 0)
        self.assertEqual(result.get('log_key'), 'skills.log_damage_multi')

    def test_destruction_commit_peak_stays_above_control_commit_peak(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 20, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'magic_staff'}
        mob_burn_control = {'hp': 100, 'defense': 0, 'effects': [{'type': 'burn', 'turns': 2, 'value': 9}, {'type': 'slow', 'turns': 2, 'value': 0}, {'type': 'freeze', 'turns': 1, 'value': 0}]}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            destruction_peak = skill_engine.use_skill(
                'cataclysm',
                dict(player),
                dict(mob_burn_control),
                dict(base_state, arcane_surge_turns=1, arcane_surge_value=30),
                telegram_id=101,
                lang='ru',
            )
            control_peak = skill_engine.use_skill('absolute_zero', dict(player), dict(mob_burn_control), dict(base_state), telegram_id=101, lang='ru')
        self.assertGreater(destruction_peak['damage'], control_peak['damage'])

    def test_control_branch_has_defensive_tempo_tool_while_destruction_does_not(self):
        player = {'mana': 100, 'intuition': 18}
        base_state = {'weapon_damage': 12, 'weapon_type': 'magic', 'weapon_profile': 'magic_staff'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            mana_shield_state = dict(base_state)
            arcane_surge_state = dict(base_state)
            skill_engine.use_skill('mana_shield', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, mana_shield_state, telegram_id=101, lang='ru')
            skill_engine.use_skill('arcane_surge', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, arcane_surge_state, telegram_id=101, lang='ru')
        self.assertGreater(mana_shield_state.get('defense_buff_turns', 0), 0)
        self.assertEqual(arcane_surge_state.get('defense_buff_turns', 0), 0)

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

    def test_judgment_mark_sets_runtime_mark_effect(self):
        player = {'mana': 100, 'wisdom': 18}
        state = {'weapon_damage': 10, 'weapon_type': 'magic', 'weapon_profile': 'holy_staff', 'mob_effects': []}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('judgment_mark', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        mark_effects = [e for e in state.get('mob_effects', []) if e.get('type') == 'judgment_mark']
        self.assertEqual(len(mark_effects), 1)
        self.assertEqual(mark_effects[0].get('turns'), game_skills.SKILLS['judgment_mark']['duration'])
        self.assertGreater(mark_effects[0].get('value', 0), 0)

    def test_sanctified_burst_gets_payoff_vs_judged_target(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 12, 'vitality': 1, 'wisdom': 18, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'holy_staff'}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
            patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('sanctified_burst', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            judged_state = dict(base_state, mob_effects=[{'type': 'judgment_mark', 'turns': 2, 'value': 20}])
            judged = skill_engine.use_skill('sanctified_burst', dict(player), dict(mob_state), judged_state, telegram_id=101, lang='ru')
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
            judged_state = dict(base_state, mob_effects=[{'type': 'judgment_mark', 'turns': 2, 'value': 20}])
            judged = skill_engine.use_skill('halo_of_dawn', dict(player), dict(mob_state), judged_state, telegram_id=101, lang='ru')
        self.assertGreater(judged['damage'], plain['damage'])
        self.assertGreaterEqual(judged['heal'], 0)

    def test_light_combo_path_is_controlled_to_single_predictable_multiplier(self):
        player = {'mana': 100, 'hp': 70, 'max_hp': 100, 'strength': 1, 'agility': 1, 'intuition': 12, 'vitality': 1, 'wisdom': 18, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        plain_state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'holy_staff', 'player_hp': 70, 'player_max_hp': 100}
        judged_state = dict(plain_state, mob_effects=[{'type': 'judgment_mark', 'turns': 2, 'value': 20}])
        combo_state = dict(judged_state, defense_buff_turns=2, defense_buff_value=16)

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('sanctified_burst', dict(player), dict(mob_state), dict(plain_state), telegram_id=101, lang='ru')
            judged = skill_engine.use_skill('sanctified_burst', dict(player), dict(mob_state), dict(judged_state), telegram_id=101, lang='ru')
            combo = skill_engine.use_skill('sanctified_burst', dict(player), dict(mob_state), dict(combo_state), telegram_id=101, lang='ru')

        self.assertGreater(judged['damage'], plain['damage'])
        self.assertGreater(combo['damage'], judged['damage'])
        self.assertEqual(combo.get('log_key'), 'skills.log_sanctified_burst_combo')

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

    def test_cleanse_max_effects_does_not_zero_value_of_non_removed_debuff(self):
        player = {'mana': 100, 'hp': 70, 'max_hp': 100, 'wisdom': 18}
        state = {
            'weapon_damage': 10,
            'weapon_type': 'magic',
            'weapon_profile': 'holy_staff',
            'player_hp': 70,
            'player_max_hp': 100,
            'slow_turns': 1,
            'weaken_turns': 2,
            'weaken_value': 15,
        }
        original_max = game_skills.SKILLS['cleanse'].get('cleanse_max_effects', 3)
        game_skills.SKILLS['cleanse']['cleanse_max_effects'] = 1
        try:
            with patch('game.skill_engine.get_skill_level', return_value=1), \
                 patch('game.skill_engine.get_skill_cooldown', return_value=0), \
                 patch('game.skill_engine.set_skill_cooldown'):
                result = skill_engine.use_skill('cleanse', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        finally:
            game_skills.SKILLS['cleanse']['cleanse_max_effects'] = original_max

        self.assertEqual(result.get('target_kind'), 'self')
        self.assertEqual(state.get('slow_turns', 0), 0)
        self.assertEqual(state.get('weaken_turns', 0), 2)
        self.assertEqual(state.get('weaken_value', 0), 15)
        self.assertIn('снято эффектов: 1', result['log'])
        self.assertNotIn('cleanse_max_effects_override', state)

    def test_cleanse_does_not_write_service_override_field_to_state(self):
        player = {'mana': 100, 'hp': 75, 'max_hp': 100, 'wisdom': 18}
        state = {
            'weapon_damage': 10,
            'weapon_type': 'magic',
            'weapon_profile': 'holy_staff',
            'player_hp': 75,
            'player_max_hp': 100,
            'poison_turns': 2,
            'poison_value': 8,
            'burn_turns': 2,
            'burn_value': 6,
        }
        original_max = game_skills.SKILLS['cleanse'].get('cleanse_max_effects', 3)
        game_skills.SKILLS['cleanse']['cleanse_max_effects'] = 1
        try:
            with patch('game.skill_engine.get_skill_level', return_value=1), \
                 patch('game.skill_engine.get_skill_cooldown', return_value=0), \
                 patch('game.skill_engine.set_skill_cooldown'):
                skill_engine.use_skill('cleanse', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        finally:
            game_skills.SKILLS['cleanse']['cleanse_max_effects'] = original_max

        active_turns = int(state.get('poison_turns', 0) > 0) + int(state.get('burn_turns', 0) > 0)
        self.assertEqual(active_turns, 1)
        self.assertNotIn('cleanse_max_effects_override', state)

    def test_support_heal_can_target_ally_without_party_combat_rollout(self):
        player = {'mana': 100, 'hp': 100, 'max_hp': 100, 'wisdom': 18}
        state = {
            'weapon_damage': 10,
            'weapon_type': 'magic',
            'weapon_profile': 'holy_staff',
            'player_hp': 100,
            'player_max_hp': 100,
            'allies': {
                'ally_1': {'player_hp': 40, 'player_max_hp': 100},
            },
            'pending_skill_target': {'kind': 'ally', 'id': 'ally_1'},
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('heal', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')

        self.assertEqual(result['target_kind'], 'ally')
        self.assertEqual(result['target_ids'], ['ally_1'])
        self.assertGreater(state['allies']['ally_1']['player_hp'], 40)
        self.assertEqual(state['player_hp'], 100)

    def test_ally_target_heal_is_consumed_then_next_heal_defaults_to_self(self):
        player = {'mana': 200, 'hp': 60, 'max_hp': 100, 'wisdom': 18}
        state = {
            'weapon_damage': 10,
            'weapon_type': 'magic',
            'weapon_profile': 'holy_staff',
            'player_hp': 60,
            'player_max_hp': 100,
            'allies': {
                'ally_1': {'player_hp': 40, 'player_max_hp': 100},
            },
            'pending_skill_target': {'kind': 'ally', 'id': 'ally_1'},
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            first = skill_engine.use_skill('heal', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
            second = skill_engine.use_skill('heal', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')

        self.assertEqual(first['target_kind'], 'ally')
        self.assertNotIn('pending_skill_target', state)
        self.assertEqual(second['target_kind'], 'self')
        self.assertEqual(second['target_ids'], ['self'])
        self.assertGreater(state['player_hp'], 60)

    def test_support_buff_can_target_party_as_runtime_bridge(self):
        player = {'mana': 100, 'hp': 100, 'max_hp': 100, 'wisdom': 18}
        state = {
            'weapon_damage': 10,
            'weapon_type': 'magic',
            'weapon_profile': 'holy_staff',
            'player_hp': 100,
            'player_max_hp': 100,
            'allies': {
                'ally_1': {'player_hp': 90, 'player_max_hp': 100},
            },
            'pending_skill_target': {'kind': 'party'},
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('blessing', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')

        self.assertEqual(result['target_kind'], 'party')
        self.assertEqual(result['target_ids'], ['self', 'ally_1'])
        self.assertEqual(state['support_effects'][0]['skill_id'], 'blessing')
        self.assertEqual(state['allies']['ally_1']['support_effects'][0]['skill_id'], 'blessing')

    def test_cleanse_only_removes_supported_dispel_subset_for_party_targets(self):
        player = {'mana': 100, 'hp': 70, 'max_hp': 100, 'wisdom': 18}
        state = {
            'weapon_damage': 10,
            'weapon_type': 'magic',
            'weapon_profile': 'holy_staff',
            'player_hp': 70,
            'player_max_hp': 100,
            'allies': {
                'ally_1': {
                    'player_hp': 60,
                    'player_max_hp': 100,
                    'support_effects': [
                        {'skill_id': 'toxin', 'dispel_tag': 'poison', 'can_dispel': True},
                        {'skill_id': 'boss_lock', 'dispel_tag': 'boss_lock', 'can_dispel': True},
                    ],
                },
            },
            'support_effects': [
                {'skill_id': 'burning', 'dispel_tag': 'burn', 'can_dispel': True},
                {'skill_id': 'protected', 'dispel_tag': 'blessing', 'can_dispel': True},
            ],
            'pending_skill_target': {'kind': 'party'},
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('cleanse', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')

        self.assertEqual(result['target_kind'], 'party')
        self.assertEqual(len(state['support_effects']), 1)
        self.assertEqual(state['support_effects'][0]['skill_id'], 'protected')
        self.assertEqual(len(state['allies']['ally_1']['support_effects']), 1)
        self.assertEqual(state['allies']['ally_1']['support_effects'][0]['skill_id'], 'boss_lock')

    def test_party_target_buff_intent_does_not_leak_into_next_cast(self):
        player = {'mana': 200, 'hp': 100, 'max_hp': 100, 'wisdom': 18}
        state = {
            'weapon_damage': 10,
            'weapon_type': 'magic',
            'weapon_profile': 'holy_staff',
            'player_hp': 100,
            'player_max_hp': 100,
            'allies': {
                'ally_1': {'player_hp': 90, 'player_max_hp': 100},
            },
            'pending_skill_target': {'kind': 'party'},
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            first = skill_engine.use_skill('blessing', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
            second = skill_engine.use_skill('blessing', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')

        self.assertEqual(first['target_kind'], 'party')
        self.assertNotIn('pending_skill_target', state)
        self.assertEqual(second['target_kind'], 'self')
        self.assertEqual(second['target_ids'], ['self'])

    def test_successful_skill_flow_cleans_up_all_runtime_target_intent_fields(self):
        player = {'mana': 100, 'hp': 90, 'max_hp': 100, 'wisdom': 18}
        state = {
            'weapon_damage': 10,
            'weapon_type': 'magic',
            'weapon_profile': 'holy_staff',
            'player_hp': 90,
            'player_max_hp': 100,
            'allies': {
                'ally_1': {'player_hp': 70, 'player_max_hp': 100},
            },
            'pending_skill_target': {'kind': 'ally', 'id': 'ally_1'},
            'skill_target_kind': 'party',
            'skill_target_id': 'stale_ally',
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('heal', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')

        self.assertNotIn('pending_skill_target', state)
        self.assertNotIn('skill_target_kind', state)
        self.assertNotIn('skill_target_id', state)

    def test_process_skill_turn_self_heal_flow_stays_compatible(self):
        player = {'hp': 50, 'max_hp': 100, 'mana': 80, 'wisdom': 18}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 50,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 50,
            'mob_effects': [],
            'log': [],
            'turn': 1,
        }

        with patch('game.combat.resolve_enemy_response', return_value=[]), \
             patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = combat.process_skill_turn('heal', player, mob, battle_state, user_id=101, lang='ru')

        self.assertTrue(result['success'])
        self.assertGreater(result['battle_state']['player_hp'], 50)

    def test_legacy_holy_staff_ids_stay_in_skills_but_not_in_active_tree(self):
        tree_skills = set(game_skills.SKILL_TREES['holy_staff']['A'] + game_skills.SKILL_TREES['holy_staff']['B'])
        for legacy_id in ('holy_bolt', 'consecration', 'divine_wrath'):
            self.assertIn(legacy_id, game_skills.SKILLS)
            self.assertNotIn(legacy_id, tree_skills)

    def test_holy_rod_tree_is_full_5_plus_5(self):
        tree = game_skills.SKILL_TREES['holy_rod']
        self.assertEqual(tree['A'], ['sacred_shield', 'mend_self', 'aura_of_resolve', 'aegis_strike', 'guardian_light'])
        self.assertEqual(tree['B'], ['judgment', 'radiant_strike', 'rod_consecration', 'punish_the_wicked', 'final_verdict'])

    def test_sacred_shield_sets_defense_buff(self):
        player = {'mana': 100, 'wisdom': 18}
        state = {'weapon_damage': 12, 'weapon_type': 'light', 'weapon_profile': 'holy_rod'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('sacred_shield', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertGreater(state.get('defense_buff_turns', 0), 0)
        self.assertGreater(state.get('defense_buff_value', 0), 0)

    def test_judgment_sets_vulnerability(self):
        player = {'mana': 100, 'wisdom': 18}
        state = {'weapon_damage': 12, 'weapon_type': 'light', 'weapon_profile': 'holy_rod', 'mob_effects': []}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('judgment', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertGreater(state.get('vulnerability_turns', 0), 0)
        self.assertGreater(state.get('vulnerability_value', 0), 0)
        self.assertEqual(state.get('vulnerability_source'), 'judgment')
        judged_effects = [e for e in state.get('mob_effects', []) if e.get('type') == 'judgment']
        self.assertEqual(len(judged_effects), 1)
        self.assertGreater(judged_effects[0].get('turns', 0), 0)
        self.assertGreater(judged_effects[0].get('value', 0), 0)

    def test_judgment_mark_and_judgment_use_different_log_keys(self):
        player = {'mana': 100, 'wisdom': 18}
        holy_state = {'weapon_damage': 12, 'weapon_type': 'magic', 'weapon_profile': 'holy_staff', 'mob_effects': []}
        rod_state = {'weapon_damage': 12, 'weapon_type': 'light', 'weapon_profile': 'holy_rod'}

        def t_key_only(key, _lang='ru', **_kwargs):
            return key

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.t', side_effect=t_key_only):
            holy_result = skill_engine.use_skill('judgment_mark', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, holy_state, telegram_id=101, lang='ru')
            rod_result = skill_engine.use_skill('judgment', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, rod_state, telegram_id=101, lang='ru')

        self.assertEqual(holy_result['log'], 'skills.log_judgment_mark_holy')
        self.assertEqual(rod_result['log'], 'skills.log_judgment_vulnerability')

    def test_judgment_log_remains_vulnerability_oriented(self):
        player = {'mana': 100, 'wisdom': 18}
        state = {'weapon_damage': 12, 'weapon_type': 'light', 'weapon_profile': 'holy_rod'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('judgment', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')

        self.assertIn('входящий урон', result['log'])
        self.assertIn('+', result['log'])

    def test_judgment_mark_log_does_not_claim_generic_incoming_damage_bonus(self):
        player = {'mana': 100, 'wisdom': 18}
        state = {'weapon_damage': 12, 'weapon_type': 'magic', 'weapon_profile': 'holy_staff', 'mob_effects': []}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('judgment_mark', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')

        self.assertIn('Печатью суда', result['log'])
        self.assertNotIn('входящий урон', result['log'])
        self.assertNotIn('+', result['log'])

    def test_aegis_strike_gets_bonus_with_active_protection(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 12, 'vitality': 1, 'wisdom': 18, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'light', 'weapon_profile': 'holy_rod'}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('aegis_strike', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            protected = skill_engine.use_skill(
                'aegis_strike',
                dict(player),
                dict(mob_state),
                dict(base_state, defense_buff_turns=2, defense_buff_value=20),
                telegram_id=101,
                lang='ru',
            )
        self.assertGreater(protected['damage'], plain['damage'])

    def test_guardian_light_runtime_prepares_post_hit_action_with_base_log_params(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 12, 'vitality': 1, 'wisdom': 18, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'light', 'weapon_profile': 'holy_rod', 'defense_buff_turns': 1, 'blessing_turns': 0}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('guardian_light', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
        self.assertEqual(result.get('log_key'), 'skills.log_damage')
        self.assertIn('name', result.get('log_params', {}))
        self.assertIn('dmg', result.get('log_params', {}))
        self.assertIn('cost', result.get('log_params', {}))
        self.assertTrue(any(a.get('type') == 'refresh_defense_buff' for a in result.get('post_hit_actions', [])))

    def test_guardian_light_successful_post_hit_builds_truthful_special_log(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 12, 'vitality': 1, 'wisdom': 18, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'light', 'weapon_profile': 'holy_rod', 'defense_buff_turns': 1, 'blessing_turns': 0, 'mob_hp': 100}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('guardian_light', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')

        battle_state = dict(base_state)
        result['direct_damage_result'] = {'final_damage': result.get('damage', 0)}
        combat.apply_post_hit_skill_actions(result, battle_state)
        combat.finalize_direct_damage_skill_result(result, 'ru')

        self.assertEqual(result.get('log_key'), 'skills.log_guardian_light')
        self.assertIn('name', result.get('log_params', {}))
        self.assertIn('dmg', result.get('log_params', {}))
        self.assertIn('cost', result.get('log_params', {}))
        self.assertIn('value', result.get('log_params', {}))
        self.assertIn('turns', result.get('log_params', {}))
        self.assertTrue(result.get('log'))
        self.assertGreater(battle_state.get('defense_buff_turns', 0), 0)
        self.assertGreater(battle_state.get('defense_buff_value', 0), 0)

    def test_judicator_payoffs_get_bonus_on_judged_target(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 12, 'vitality': 1, 'wisdom': 18, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'light', 'weapon_profile': 'holy_rod', 'mob_effects': []}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            punish_plain = skill_engine.use_skill('punish_the_wicked', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            punish_judged = skill_engine.use_skill(
                'punish_the_wicked',
                dict(player),
                dict(mob_state),
                dict(base_state, mob_effects=[{'type': 'judgment', 'turns': 2, 'value': 20}]),
                telegram_id=101,
                lang='ru',
            )
            verdict_plain = skill_engine.use_skill('final_verdict', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            verdict_state = dict(base_state, mob_effects=[{'type': 'judgment', 'turns': 2, 'value': 20}])
            verdict_judged = skill_engine.use_skill('final_verdict', dict(player), dict(mob_state), verdict_state, telegram_id=101, lang='ru')
        self.assertGreater(punish_judged['damage'], punish_plain['damage'])
        self.assertGreater(verdict_judged['damage'], verdict_plain['damage'])
        self.assertTrue(any(a.get('type') == 'consume_judgment_window' for a in verdict_judged.get('post_hit_actions', [])))

    def test_judicator_payoffs_do_not_trigger_from_plain_vulnerability(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 12, 'vitality': 1, 'wisdom': 18, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'light', 'weapon_profile': 'holy_rod', 'mob_effects': []}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        vuln_state = dict(base_state, vulnerability_turns=2, vulnerability_value=20, vulnerability_source='expose_guard')
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            punish_plain = skill_engine.use_skill('punish_the_wicked', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            punish_vuln = skill_engine.use_skill('punish_the_wicked', dict(player), dict(mob_state), dict(vuln_state), telegram_id=101, lang='ru')
            verdict_plain = skill_engine.use_skill('final_verdict', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            verdict_vuln = skill_engine.use_skill('final_verdict', dict(player), dict(mob_state), dict(vuln_state), telegram_id=101, lang='ru')
        self.assertEqual(punish_vuln['damage'], punish_plain['damage'])
        self.assertEqual(verdict_vuln['damage'], verdict_plain['damage'])

    def test_judicator_payoffs_do_not_trigger_from_holy_staff_judgment_mark(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 12, 'vitality': 1, 'wisdom': 18, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'light', 'weapon_profile': 'holy_rod', 'mob_effects': []}
        marked_state = dict(base_state, mob_effects=[{'type': 'judgment_mark', 'turns': 2, 'value': 20}])
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            punish_plain = skill_engine.use_skill('punish_the_wicked', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            punish_marked = skill_engine.use_skill('punish_the_wicked', dict(player), dict(mob_state), dict(marked_state), telegram_id=101, lang='ru')
            verdict_plain = skill_engine.use_skill('final_verdict', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            verdict_marked = skill_engine.use_skill('final_verdict', dict(player), dict(mob_state), dict(marked_state), telegram_id=101, lang='ru')
        self.assertEqual(punish_marked['damage'], punish_plain['damage'])
        self.assertEqual(verdict_marked['damage'], verdict_plain['damage'])

    def test_final_verdict_post_hit_consumes_judgment_effect_window(self):
        state = {
            'mob_effects': [{'type': 'judgment', 'turns': 2, 'value': 20}],
            'vulnerability_turns': 2,
            'vulnerability_value': 20,
            'vulnerability_source': 'judgment',
        }
        skill_result = {
            'direct_damage_skill': True,
            'direct_damage_result': {'final_damage': 30},
            'post_hit_actions': [{'type': 'consume_judgment_window'}],
        }
        combat.apply_post_hit_skill_actions(skill_result, state)
        self.assertEqual(state.get('vulnerability_turns', 0), 0)
        self.assertEqual(state.get('vulnerability_value', 0), 0)
        self.assertIsNone(state.get('vulnerability_source'))
        self.assertFalse(any(e.get('type') == 'judgment' for e in state.get('mob_effects', [])))

    def test_consume_judgment_window_keeps_non_judgment_vulnerability(self):
        state = {
            'mob_effects': [{'type': 'judgment', 'turns': 2, 'value': 20}],
            'vulnerability_turns': 2,
            'vulnerability_value': 15,
            'vulnerability_source': 'sunder_armor',
        }
        skill_result = {
            'direct_damage_skill': True,
            'direct_damage_result': {'final_damage': 30},
            'post_hit_actions': [{'type': 'consume_judgment_window'}],
        }
        combat.apply_post_hit_skill_actions(skill_result, state)
        self.assertEqual(state.get('vulnerability_turns', 0), 2)
        self.assertEqual(state.get('vulnerability_value', 0), 15)
        self.assertEqual(state.get('vulnerability_source'), 'sunder_armor')
        self.assertFalse(any(e.get('type') == 'judgment' for e in state.get('mob_effects', [])))

    def test_mob_judgment_effect_expires_via_enemy_response_cleanup(self):
        state = {
            'mob_effects': [
                {'type': 'judgment', 'turns': 1, 'value': 20},
                {'type': 'burn', 'turns': 2, 'value': 5},
            ],
            'vulnerability_turns': 2,
            'vulnerability_value': 20,
            'vulnerability_source': 'judgment',
        }
        combat.decrement_mob_non_dot_effects_after_response(state)
        self.assertEqual(state.get('vulnerability_turns', 0), 0)
        self.assertEqual(state.get('vulnerability_value', 0), 0)
        self.assertIsNone(state.get('vulnerability_source'))
        self.assertFalse(any(e.get('type') == 'judgment' for e in state.get('mob_effects', [])))
        self.assertTrue(any(e.get('type') == 'burn' for e in state.get('mob_effects', [])))

    def test_vulnerability_source_clears_when_vulnerability_expires_naturally(self):
        state = {
            'vulnerability_turns': 1,
            'vulnerability_value': 20,
            'vulnerability_source': 'sunder_armor',
        }
        result = combat.apply_direct_damage_action_modifiers(
            state,
            base_damage=100,
            can_consume_guaranteed_crit=False,
        )
        self.assertGreater(result['damage'], 100)
        self.assertEqual(state.get('vulnerability_turns', 0), 0)
        self.assertEqual(state.get('vulnerability_value', 0), 0)
        self.assertIsNone(state.get('vulnerability_source'))

    def test_axe_2h_tree_is_full_5_plus_5(self):
        tree = game_skills.SKILL_TREES['axe_2h']
        self.assertEqual(len(tree['A']), 5)
        self.assertEqual(len(tree['B']), 5)

    def test_axe_2h_branch_a_order_matches_final_design(self):
        expected = ['rage_call', 'savage_chop', 'blooded_resolve', 'frenzy_chain', 'last_roar']
        self.assertEqual(game_skills.SKILL_TREES['axe_2h']['A'], expected)

    def test_axe_2h_branch_b_order_matches_final_design(self):
        expected = ['bleeding_cut', 'sunder_armor', 'brutal_overhead', 'reopen_wounds', 'ravage']
        self.assertEqual(game_skills.SKILL_TREES['axe_2h']['B'], expected)

    def test_rage_call_sets_berserk_runtime_and_applies_safe_self_cost(self):
        player = {'mana': 100, 'hp': 10, 'max_hp': 100, 'strength': 16}
        state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'axe_2h', 'player_hp': 10, 'player_max_hp': 100}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('rage_call', player, {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertGreater(state.get('berserk_turns', 0), 0)
        self.assertGreater(state.get('berserk_damage', 0), 0)
        self.assertGreater(state.get('berserk_defense_penalty_turns', 0), 0)
        self.assertGreater(state.get('berserk_defense_penalty', 0), 0)
        self.assertEqual(state.get('player_hp'), 1)
        self.assertEqual(player.get('hp'), 1)

    def test_rage_call_defense_penalty_scales_with_skill_level(self):
        player = {'mana': 100, 'hp': 100, 'max_hp': 100, 'strength': 16}
        base_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'axe_2h', 'player_hp': 100, 'player_max_hp': 100}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            level1 = dict(base_state)
            skill_engine.use_skill('rage_call', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, level1, telegram_id=101, lang='ru')
        with patch('game.skill_engine.get_skill_level', return_value=3), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            level3 = dict(base_state)
            skill_engine.use_skill('rage_call', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, level3, telegram_id=101, lang='ru')
        self.assertGreater(level3.get('berserk_defense_penalty', 0), level1.get('berserk_defense_penalty', 0))

    def test_frenzy_chain_gets_berserk_payoff_and_schedules_hit_gated_consumption(self):
        player = {'mana': 100, 'strength': 18, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'axe_2h'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('frenzy_chain', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            berserk_state = dict(base_state, berserk_turns=1, berserk_damage=20, berserk_defense_penalty_turns=1, berserk_defense_penalty=25)
            payoff = skill_engine.use_skill('frenzy_chain', dict(player), dict(mob_state), berserk_state, telegram_id=101, lang='ru')
        self.assertGreater(payoff['damage'], plain['damage'])
        self.assertEqual(berserk_state.get('berserk_turns', 0), 1)
        self.assertEqual(berserk_state.get('berserk_damage', 0), 20)
        self.assertIn({'type': 'consume_berserk_setup'}, payoff.get('post_hit_actions', []))

    def test_frenzy_chain_consumes_berserk_only_after_successful_hit(self):
        player = {
            'mana': 100, 'strength': 18, 'agility': 8, 'intuition': 1,
            'vitality': 1, 'wisdom': 1, 'luck': 1,
        }
        mob = {'id': 'wolf', 'hp': 100, 'max_hp': 100, 'defense': 0, 'effects': [], 'agility': 10, 'luck': 10}
        state = {
            'weapon_damage': 16,
            'weapon_type': 'melee',
            'weapon_profile': 'axe_2h',
            'mob_hp': 100,
            'mob_effects': [],
            'berserk_turns': 1,
            'berserk_damage': 20,
            'berserk_defense_penalty_turns': 1,
            'berserk_defense_penalty': 25,
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            skill_result = skill_engine.use_skill('frenzy_chain', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')

        with patch('game.combat.resolve_hit_check', return_value={'is_hit': False, 'outcome': 'miss', 'hit_chance': 35, 'roll': 99, 'accuracy_rating': 20, 'evasion_rating': 30}):
            resolve_miss = combat.resolve_enemy_targeted_direct_damage_skill_action(dict(player), dict(mob), state, skill_result, lang='ru')
        self.assertTrue(resolve_miss['handled'])
        self.assertFalse(resolve_miss['is_hit'])
        self.assertEqual(state.get('berserk_turns'), 1)
        self.assertEqual(state.get('berserk_damage'), 20)

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            skill_result_hit = skill_engine.use_skill('frenzy_chain', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')

        with patch('game.combat.resolve_hit_check', return_value={'is_hit': True, 'outcome': 'hit', 'hit_chance': 65, 'roll': 10, 'accuracy_rating': 40, 'evasion_rating': 30}):
            resolve_hit = combat.resolve_enemy_targeted_direct_damage_skill_action(dict(player), dict(mob), state, skill_result_hit, lang='ru')
        self.assertTrue(resolve_hit['handled'])
        self.assertTrue(resolve_hit['is_hit'])
        self.assertEqual(state.get('berserk_turns'), 0)
        self.assertEqual(state.get('berserk_damage'), 0)
        self.assertEqual(state.get('berserk_defense_penalty_turns'), 0)
        self.assertEqual(state.get('berserk_defense_penalty'), 0)

    def test_blooded_resolve_scales_heal_up_at_low_hp(self):
        player = {'mana': 100, 'hp': 90, 'max_hp': 100, 'vitality': 16}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        hi_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'axe_2h', 'player_hp': 90, 'player_max_hp': 100}
        low_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'axe_2h', 'player_hp': 20, 'player_max_hp': 100}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            heal_high = skill_engine.use_skill('blooded_resolve', dict(player), dict(mob_state), hi_state, telegram_id=101, lang='ru')
            heal_low = skill_engine.use_skill('blooded_resolve', dict(player), dict(mob_state), low_state, telegram_id=101, lang='ru')
        self.assertGreater(heal_low['heal'], heal_high['heal'])

    def test_bleeding_cut_applies_bleed(self):
        player = {'mana': 100, 'strength': 18, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'axe_2h'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('bleeding_cut', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertTrue(any(e.get('type') == 'bleed' and e.get('turns', 0) > 0 and e.get('value', 0) > 0 for e in result['effects']))

    def test_apply_mob_effects_ticks_bleed_without_breaking_poison_and_burn(self):
        mob_state = {
            'hp': 100,
            'effects': [
                {'type': 'poison', 'turns': 2, 'value': 5},
                {'type': 'burn', 'turns': 1, 'value': 7},
                {'type': 'bleed', 'turns': 3, 'value': 4},
                {'type': 'slow', 'turns': 2, 'value': 0},
            ],
        }
        dmg, _ = skill_engine.apply_mob_effects(mob_state)
        self.assertEqual(dmg, 16)
        self.assertTrue(any(e.get('type') == 'poison' and e.get('turns') == 1 for e in mob_state['effects']))
        self.assertFalse(any(e.get('type') == 'burn' for e in mob_state['effects']))
        self.assertTrue(any(e.get('type') == 'bleed' and e.get('turns') == 2 for e in mob_state['effects']))
        self.assertTrue(any(e.get('type') == 'slow' and e.get('turns') == 2 for e in mob_state['effects']))

    def test_sunder_armor_creates_runtime_vulnerability_window(self):
        player = {'mana': 100, 'strength': 16}
        state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'axe_2h'}
        expected_duration = game_skills.get_skill('sunder_armor').get('duration', 2)
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('sunder_armor', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertEqual(state.get('vulnerability_turns', 0), expected_duration)
        self.assertGreater(state.get('vulnerability_value', 0), 0)
        self.assertEqual(state.get('vulnerability_source'), 'sunder_armor')

    def test_reopen_wounds_gets_bonus_against_bleeding_target(self):
        player = {'mana': 100, 'strength': 18, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'axe_2h'}
        mob_plain = {'hp': 100, 'defense': 0, 'effects': []}
        mob_bleed = {'hp': 100, 'defense': 0, 'effects': [{'type': 'bleed', 'turns': 2, 'value': 4}]}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('reopen_wounds', dict(player), mob_plain, dict(base_state), telegram_id=101, lang='ru')
            vs_bleed = skill_engine.use_skill('reopen_wounds', dict(player), mob_bleed, dict(base_state), telegram_id=101, lang='ru')
        self.assertGreater(vs_bleed['damage'], plain['damage'])
        self.assertEqual(vs_bleed.get('log_key'), 'skills.log_reopen_wounds_payoff')

    def test_reopen_wounds_gets_bonus_against_vulnerable_target(self):
        player = {'mana': 100, 'strength': 18, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'axe_2h'}
        mob_plain = {'hp': 100, 'defense': 0, 'effects': []}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('reopen_wounds', dict(player), mob_plain, dict(base_state), telegram_id=101, lang='ru')
            vs_vulnerable = skill_engine.use_skill('reopen_wounds', dict(player), mob_plain, dict(base_state, vulnerability_turns=2, vulnerability_value=20), telegram_id=101, lang='ru')
        self.assertGreater(vs_vulnerable['damage'], plain['damage'])
        self.assertEqual(vs_vulnerable.get('log_key'), 'skills.log_reopen_wounds_payoff')

    def test_ravage_gets_bonus_against_prepared_target_without_double_stacking(self):
        player = {'mana': 100, 'strength': 18, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'axe_2h'}
        mob_plain = {'hp': 100, 'defense': 0, 'effects': []}
        mob_bleed = {'hp': 100, 'defense': 0, 'effects': [{'type': 'bleed', 'turns': 2, 'value': 4}]}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('ravage', dict(player), mob_plain, dict(base_state), telegram_id=101, lang='ru')
            bleed_prepared = skill_engine.use_skill('ravage', dict(player), mob_bleed, dict(base_state), telegram_id=101, lang='ru')
            vulnerable_prepared = skill_engine.use_skill('ravage', dict(player), mob_plain, dict(base_state, vulnerability_turns=2, vulnerability_value=20), telegram_id=101, lang='ru')
            both_prepared = skill_engine.use_skill(
                'ravage',
                dict(player),
                mob_bleed,
                dict(base_state, vulnerability_turns=2, vulnerability_value=20),
                telegram_id=101,
                lang='ru',
            )
        self.assertGreater(bleed_prepared['damage'], plain['damage'])
        self.assertEqual(vulnerable_prepared['damage'], bleed_prepared['damage'])
        self.assertEqual(both_prepared['damage'], bleed_prepared['damage'])
        self.assertEqual(both_prepared.get('log_key'), 'skills.log_ravage_payoff')

    def test_pack_uses_existing_runtime_fields_without_new_state_model(self):
        player = {'mana': 100, 'strength': 16}
        state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'axe_2h'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('sunder_armor', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertIn('vulnerability_turns', state)
        self.assertIn('vulnerability_value', state)
        self.assertNotIn('prepared_target_turns', state)

    def test_reopen_wounds_keeps_base_behavior_without_setup(self):
        player = {'mana': 100, 'strength': 18, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'axe_2h'}
        mob_plain = {'hp': 100, 'defense': 0, 'effects': []}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('reopen_wounds', dict(player), mob_plain, dict(base_state), telegram_id=101, lang='ru')
        self.assertGreater(result['damage'], 0)
        self.assertEqual(result.get('log_key'), 'skills.log_damage')

    def test_direct_damage_modifiers_apply_berserk_damage_bonus(self):
        state = {'berserk_turns': 1, 'berserk_damage': 12}
        out = combat.apply_direct_damage_action_modifiers(state, 20, can_consume_guaranteed_crit=False)
        self.assertEqual(out['damage'], 32)

    def test_enemy_damage_is_penalized_up_during_berserk_commit_window(self):
        state = {'berserk_defense_penalty_turns': 1, 'berserk_defense_penalty': 25}
        out = combat.resolve_enemy_damage_against_player(
            state,
            lang='ru',
            mob_result={'damage': 40, 'type': 'mob_attack'},
        )
        self.assertEqual(out['player_damage'], 50)

    def test_sword_2h_tree_is_full_5_plus_5(self):
        tree = game_skills.SKILL_TREES['sword_2h']
        self.assertEqual(len(tree['A']), 5)
        self.assertEqual(len(tree['B']), 5)

    def test_sword_2h_branch_a_order_matches_final_design(self):
        expected = ['heavy_swing', 'armor_split', 'executioners_focus', 'cleave_through', 'executioners_stroke']
        self.assertEqual(game_skills.SKILL_TREES['sword_2h']['A'], expected)

    def test_sword_2h_branch_b_order_matches_final_design(self):
        expected = ['battle_stance', 'twin_cut', 'riposte_step', 'flowing_combo', 'masters_sequence']
        self.assertEqual(game_skills.SKILL_TREES['sword_2h']['B'], expected)

    def test_armor_split_sets_vulnerability_runtime(self):
        player = {'mana': 100, 'strength': 16}
        state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'sword_2h'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('armor_split', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertGreater(state.get('vulnerability_turns', 0), 0)
        self.assertGreater(state.get('vulnerability_value', 0), 0)
        self.assertEqual(state.get('vulnerability_source'), 'armor_split')

    def test_executioners_focus_sets_runtime_state(self):
        player = {'mana': 100, 'strength': 16}
        state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'sword_2h'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('executioners_focus', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertEqual(state.get('executioner_focus_turns', 0), 2)
        self.assertGreater(state.get('executioner_focus_value', 0), 0)

    def test_cleave_through_gets_payoff_from_focus_and_marks_post_hit_focus_consumption(self):
        player = {'mana': 100, 'strength': 18, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'sword_2h', 'mob_hp': 100, 'mob_max_hp': 100}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('cleave_through', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            focus_state = dict(base_state, executioner_focus_turns=1, executioner_focus_value=20)
            payoff = skill_engine.use_skill('cleave_through', dict(player), dict(mob_state), focus_state, telegram_id=101, lang='ru')
        self.assertGreater(payoff['damage'], plain['damage'])
        self.assertEqual(focus_state.get('executioner_focus_turns', 0), 1)
        self.assertEqual(focus_state.get('executioner_focus_value', 0), 20)
        self.assertIn({'type': 'consume_executioner_focus'}, payoff.get('post_hit_actions', []))

    def test_cleave_through_is_stronger_into_vulnerable_and_or_wounded_target(self):
        player = {'mana': 100, 'strength': 18, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'max_hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'sword_2h', 'mob_hp': 100}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('cleave_through', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            vulnerable = skill_engine.use_skill('cleave_through', dict(player), dict(mob_state), dict(base_state, vulnerability_turns=2, vulnerability_value=20), telegram_id=101, lang='ru')
            wounded = skill_engine.use_skill('cleave_through', dict(player), dict(mob_state), dict(base_state, mob_hp=30), telegram_id=101, lang='ru')
        self.assertGreater(vulnerable['damage'], plain['damage'])
        self.assertGreater(wounded['damage'], plain['damage'])

    def test_executioners_stroke_is_stronger_into_wounded_target(self):
        player = {'mana': 100, 'strength': 18, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'max_hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'sword_2h', 'mob_hp': 100}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('executioners_stroke', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            wounded = skill_engine.use_skill('executioners_stroke', dict(player), dict(mob_state), dict(base_state, mob_hp=30), telegram_id=101, lang='ru')
        self.assertGreater(wounded['damage'], plain['damage'])

    def test_executioners_stroke_gets_focus_payoff_and_marks_post_hit_focus_consumption(self):
        player = {'mana': 100, 'strength': 18, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'max_hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'sword_2h', 'mob_hp': 100}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('executioners_stroke', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            focus_state = dict(base_state, executioner_focus_turns=1, executioner_focus_value=20)
            focused = skill_engine.use_skill('executioners_stroke', dict(player), dict(mob_state), focus_state, telegram_id=101, lang='ru')
        self.assertGreater(focused['damage'], plain['damage'])
        self.assertEqual(focus_state.get('executioner_focus_turns', 0), 1)
        self.assertEqual(focus_state.get('executioner_focus_value', 0), 20)
        self.assertIn({'type': 'consume_executioner_focus'}, focused.get('post_hit_actions', []))

    def test_init_battle_sets_mob_max_hp_for_live_runtime_wounded_checks(self):
        player = {
            'hp': 80, 'max_hp': 100, 'mana': 40, 'max_mana': 40,
            'agility': 5, 'luck': 5, 'armor_class': None, 'offhand_profile': 'none', 'encumbrance': 0,
        }
        mob = {'id': 'wolf', 'name': 'Wolf', 'hp': 77, 'level': 3}
        state = combat.init_battle(player, mob, mob_first=False)
        self.assertEqual(state.get('mob_hp'), 77)
        self.assertEqual(state.get('mob_max_hp'), 77)

    def test_battle_stance_sets_runtime_state(self):
        player = {'mana': 100, 'agility': 16}
        state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'sword_2h'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('battle_stance', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertEqual(state.get('battle_stance_turns', 0), 2)
        self.assertGreater(state.get('battle_stance_value', 0), 0)

    def test_twin_cut_uses_multi_hit_path_correctly(self):
        player = {'mana': 100, 'strength': 1, 'agility': 18, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'sword_2h'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('twin_cut', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertIn('log_damage_multi', result.get('log_key', ''))
        self.assertGreater(result['damage'], 0)

    def test_riposte_step_sets_dodge_runtime_via_existing_dodge_buff_path(self):
        player = {'mana': 100, 'agility': 16}
        state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'sword_2h'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('riposte_step', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertGreater(state.get('dodge_buff_turns', 0), 0)
        self.assertGreater(state.get('dodge_buff_value', 0), 0)

    def test_flowing_combo_gets_stance_payoff_and_marks_post_hit_stance_consumption(self):
        player = {'mana': 100, 'strength': 1, 'agility': 18, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'sword_2h'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('flowing_combo', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            stance_state = dict(base_state, battle_stance_turns=1, battle_stance_value=16)
            payoff = skill_engine.use_skill('flowing_combo', dict(player), dict(mob_state), stance_state, telegram_id=101, lang='ru')
        self.assertGreater(payoff['damage'], plain['damage'])
        self.assertEqual(stance_state.get('battle_stance_turns', 0), 1)
        self.assertEqual(stance_state.get('battle_stance_value', 0), 16)
        self.assertIn({'type': 'consume_battle_stance'}, payoff.get('post_hit_actions', []))

    def test_process_skill_turn_consumes_executioner_focus_only_on_successful_hit(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 100,
            'mob_effects': [],
            'executioner_focus_turns': 1,
            'executioner_focus_value': 20,
            'log': [],
            'turn': 1,
        }
        def make_skill_result():
            return {
                'success': True,
                'damage': 20,
                'heal': 0,
                'effects': [],
                'log': 'cast',
                'direct_damage_skill': True,
                'target_kind': 'enemy',
                'log_key': 'skills.log_damage',
                'log_params': {'name': 'Cleave Through', 'dmg': 20, 'cost': 10},
                'log_suffixes': [],
                'post_hit_actions': [{'type': 'consume_executioner_focus'}],
                'lifesteal_ratio': 0.0,
                'heal_from_damage_ratio': 0.0,
                'heal_cap_missing_hp': 0,
            }

        miss_hit_check = {'outcome': 'dodge', 'is_hit': False, 'hit_chance': 50, 'roll': 100, 'accuracy_rating': 100, 'evasion_rating': 120}
        with patch('game.combat.use_skill', side_effect=lambda *_args, **_kwargs: make_skill_result()), \
             patch('game.combat.resolve_hit_check', return_value=miss_hit_check), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            miss_result = combat.process_skill_turn('cleave_through', player, mob, dict(battle_state), user_id=101, lang='ru')
        self.assertEqual(miss_result['battle_state']['executioner_focus_turns'], 1)
        self.assertEqual(miss_result['battle_state']['executioner_focus_value'], 20)

        hit_hit_check = {'outcome': 'hit', 'is_hit': True, 'hit_chance': 95, 'roll': 1, 'accuracy_rating': 100, 'evasion_rating': 100}
        with patch('game.combat.use_skill', side_effect=lambda *_args, **_kwargs: make_skill_result()), \
             patch('game.combat.resolve_hit_check', return_value=hit_hit_check), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            hit_result = combat.process_skill_turn('cleave_through', player, mob, dict(battle_state), user_id=101, lang='ru')
        self.assertEqual(hit_result['battle_state']['executioner_focus_turns'], 0)
        self.assertEqual(hit_result['battle_state']['executioner_focus_value'], 0)

    def test_process_skill_turn_consumes_battle_stance_only_on_successful_hit(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0}
        battle_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 100,
            'mob_effects': [],
            'battle_stance_turns': 1,
            'battle_stance_value': 18,
            'log': [],
            'turn': 1,
        }
        def make_skill_result():
            return {
                'success': True,
                'damage': 20,
                'heal': 0,
                'effects': [],
                'log': 'cast',
                'direct_damage_skill': True,
                'target_kind': 'enemy',
                'log_key': 'skills.log_damage',
                'log_params': {'name': 'Flowing Combo', 'dmg': 20, 'cost': 10},
                'log_suffixes': [],
                'post_hit_actions': [{'type': 'consume_battle_stance'}],
                'lifesteal_ratio': 0.0,
                'heal_from_damage_ratio': 0.0,
                'heal_cap_missing_hp': 0,
            }

        miss_hit_check = {'outcome': 'dodge', 'is_hit': False, 'hit_chance': 50, 'roll': 100, 'accuracy_rating': 100, 'evasion_rating': 120}
        with patch('game.combat.use_skill', side_effect=lambda *_args, **_kwargs: make_skill_result()), \
             patch('game.combat.resolve_hit_check', return_value=miss_hit_check), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            miss_result = combat.process_skill_turn('flowing_combo', player, mob, dict(battle_state), user_id=101, lang='ru')
        self.assertEqual(miss_result['battle_state']['battle_stance_turns'], 1)
        self.assertEqual(miss_result['battle_state']['battle_stance_value'], 18)

        hit_hit_check = {'outcome': 'hit', 'is_hit': True, 'hit_chance': 95, 'roll': 1, 'accuracy_rating': 100, 'evasion_rating': 100}
        with patch('game.combat.use_skill', side_effect=lambda *_args, **_kwargs: make_skill_result()), \
             patch('game.combat.resolve_hit_check', return_value=hit_hit_check), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            hit_result = combat.process_skill_turn('flowing_combo', player, mob, dict(battle_state), user_id=101, lang='ru')
        self.assertEqual(hit_result['battle_state']['battle_stance_turns'], 0)
        self.assertEqual(hit_result['battle_state']['battle_stance_value'], 0)

    def test_masters_sequence_behaves_as_capstone_combo_finisher(self):
        player = {'mana': 100, 'strength': 1, 'agility': 18, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 16, 'weapon_type': 'melee', 'weapon_profile': 'sword_2h'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('masters_sequence', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            stance = skill_engine.use_skill('masters_sequence', dict(player), dict(mob_state), dict(base_state, battle_stance_turns=1, battle_stance_value=16), telegram_id=101, lang='ru')
        self.assertIn('log_damage_multi', plain.get('log_key', ''))
        self.assertGreater(plain['damage'], 0)
        self.assertGreater(stance['damage'], plain['damage'])

    def test_wand_tree_is_full_5_plus_5(self):
        tree = game_skills.SKILL_TREES['wand']
        self.assertEqual(len(tree['A']), 5)
        self.assertEqual(len(tree['B']), 5)

    def test_wand_branch_a_order_matches_final_design(self):
        expected = ['arcane_bolt', 'spell_echo', 'quick_channel', 'overload', 'arcane_barrage']
        self.assertEqual(game_skills.SKILL_TREES['wand']['A'], expected)

    def test_wand_branch_b_order_matches_final_design(self):
        expected = ['dueling_ward', 'hex_bolt', 'mana_feint', 'counterpulse', 'duel_arc']
        self.assertEqual(game_skills.SKILL_TREES['wand']['B'], expected)

    def test_spell_echo_sets_runtime_state(self):
        player = {'mana': 100, 'intuition': 16}
        state = {'weapon_damage': 16, 'weapon_type': 'magic', 'weapon_profile': 'wand'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('spell_echo', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertEqual(state.get('spell_echo_turns', 0), 2)
        self.assertGreater(state.get('spell_echo_value', 0), 0)

    def test_quick_channel_restores_mana_and_sets_runtime_state(self):
        player = {'mana': 50, 'max_mana': 100, 'intuition': 16}
        state = {'weapon_damage': 16, 'weapon_type': 'magic', 'weapon_profile': 'wand', 'player_max_mana': 100}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('quick_channel', player, {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertGreater(player.get('mana', 0), 30)
        self.assertEqual(state.get('quick_channel_turns', 0), 2)
        self.assertGreater(state.get('quick_channel_value', 0), 0)

    def test_overload_gets_payoff_from_setup_windows(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 18, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 16, 'weapon_type': 'magic', 'weapon_profile': 'wand'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('overload', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            setup_state = dict(base_state, spell_echo_turns=1, spell_echo_value=20, quick_channel_turns=1, quick_channel_value=15)
            payoff = skill_engine.use_skill('overload', dict(player), dict(mob_state), setup_state, telegram_id=101, lang='ru')
        self.assertGreater(payoff['damage'], plain['damage'])
        self.assertEqual(setup_state.get('spell_echo_turns', 0), 1)
        self.assertEqual(setup_state.get('quick_channel_turns', 0), 1)

    def test_arcane_bolt_benefits_from_setup_windows(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 18, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 16, 'weapon_type': 'magic', 'weapon_profile': 'wand'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('arcane_bolt', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            setup_state = dict(base_state, spell_echo_turns=1, spell_echo_value=20, quick_channel_turns=1, quick_channel_value=15)
            boosted = skill_engine.use_skill('arcane_bolt', dict(player), dict(mob_state), setup_state, telegram_id=101, lang='ru')
        self.assertGreater(boosted['damage'], plain['damage'])
        self.assertEqual(setup_state.get('spell_echo_turns', 0), 1)
        self.assertEqual(setup_state.get('quick_channel_turns', 0), 1)

    def test_arcane_barrage_uses_multi_hit_path_correctly(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 18, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        state = {'weapon_damage': 16, 'weapon_type': 'magic', 'weapon_profile': 'wand'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('arcane_barrage', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertIn('log_damage_multi', result.get('log_key', ''))
        self.assertGreater(result['damage'], 0)

    def test_arcane_barrage_benefits_from_setup_windows(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 18, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 16, 'weapon_type': 'magic', 'weapon_profile': 'wand'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('arcane_barrage', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            setup_state = dict(base_state, spell_echo_turns=1, spell_echo_value=20, quick_channel_turns=1, quick_channel_value=15)
            payoff = skill_engine.use_skill('arcane_barrage', dict(player), dict(mob_state), setup_state, telegram_id=101, lang='ru')
        self.assertGreater(payoff['damage'], plain['damage'])
        self.assertEqual(setup_state.get('spell_echo_turns', 0), 1)
        self.assertEqual(setup_state.get('quick_channel_turns', 0), 1)

    def test_wand_setup_windows_are_consumed_only_on_hit(self):
        player = {
            'mana': 100,
            'hp': 100,
            'max_hp': 100,
            'strength': 1,
            'agility': 1,
            'intuition': 18,
            'vitality': 1,
            'wisdom': 1,
            'luck': 1,
        }
        mob = {'id': 'forest_wolf', 'name': 'wolf', 'defense': 0, 'damage': (5, 8)}
        base_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'player_max_mana': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'log': [],
            'turn': 1,
            'weapon_damage': 16,
            'weapon_type': 'magic',
            'weapon_profile': 'wand',
            'spell_echo_turns': 1,
            'spell_echo_value': 20,
            'quick_channel_turns': 1,
            'quick_channel_value': 15,
        }

        miss_hit_check = {'outcome': 'dodge', 'is_hit': False, 'hit_chance': 50, 'roll': 100, 'accuracy_rating': 100, 'evasion_rating': 120}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.combat.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_hit_check', return_value=miss_hit_check), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            miss_result = combat.process_skill_turn('arcane_bolt', player, mob, dict(base_state), user_id=101, lang='ru')
        self.assertEqual(miss_result['battle_state'].get('spell_echo_turns', 0), 1)
        self.assertEqual(miss_result['battle_state'].get('quick_channel_turns', 0), 1)

        hit_hit_check = {'outcome': 'hit', 'is_hit': True, 'hit_chance': 95, 'roll': 1, 'accuracy_rating': 100, 'evasion_rating': 100}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.combat.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_hit_check', return_value=hit_hit_check), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            hit_result = combat.process_skill_turn('arcane_bolt', player, mob, dict(base_state), user_id=101, lang='ru')
        self.assertEqual(hit_result['battle_state'].get('spell_echo_turns', 0), 0)
        self.assertEqual(hit_result['battle_state'].get('quick_channel_turns', 0), 0)

    def test_counterpulse_consumes_dueling_ward_only_on_hit(self):
        player = {
            'mana': 100,
            'hp': 100,
            'max_hp': 100,
            'strength': 1,
            'agility': 1,
            'intuition': 18,
            'vitality': 1,
            'wisdom': 1,
            'luck': 1,
        }
        mob = {'id': 'forest_wolf', 'name': 'wolf', 'defense': 0, 'damage': (5, 8)}
        base_state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'player_max_mana': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'log': [],
            'turn': 1,
            'weapon_damage': 16,
            'weapon_type': 'magic',
            'weapon_profile': 'wand',
            'defense_buff_turns': 2,
            'defense_buff_value': 20,
            'defense_buff_source': 'dueling_ward',
        }

        miss_hit_check = {'outcome': 'dodge', 'is_hit': False, 'hit_chance': 50, 'roll': 100, 'accuracy_rating': 100, 'evasion_rating': 120}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.combat.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_hit_check', return_value=miss_hit_check), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            miss_result = combat.process_skill_turn('counterpulse', player, mob, dict(base_state), user_id=101, lang='ru')
        self.assertEqual(miss_result['battle_state'].get('defense_buff_turns', 0), 2)
        self.assertEqual(miss_result['battle_state'].get('defense_buff_value', 0), 20)
        self.assertEqual(miss_result['battle_state'].get('defense_buff_source'), 'dueling_ward')

        hit_hit_check = {'outcome': 'hit', 'is_hit': True, 'hit_chance': 95, 'roll': 1, 'accuracy_rating': 100, 'evasion_rating': 100}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.combat.random.uniform', return_value=1.0), \
             patch('game.combat.resolve_hit_check', return_value=hit_hit_check), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            hit_result = combat.process_skill_turn('counterpulse', player, mob, dict(base_state), user_id=101, lang='ru')
        self.assertEqual(hit_result['battle_state'].get('defense_buff_turns', 0), 0)
        self.assertEqual(hit_result['battle_state'].get('defense_buff_value', 0), 0)
        self.assertIsNone(hit_result['battle_state'].get('defense_buff_source'))

    def test_dueling_ward_sets_defense_runtime(self):
        player = {'mana': 100, 'intuition': 16}
        state = {'weapon_damage': 16, 'weapon_type': 'magic', 'weapon_profile': 'wand'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('dueling_ward', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertGreater(state.get('defense_buff_turns', 0), 0)
        self.assertGreater(state.get('defense_buff_value', 0), 0)
        self.assertEqual(state.get('defense_buff_source'), 'dueling_ward')

    def test_dueling_ward_window_expires_in_post_action_ticks(self):
        state = {'defense_buff_turns': 2, 'defense_buff_value': 20, 'defense_buff_source': 'dueling_ward'}
        combat.tick_post_action_player_buff_durations(state)
        self.assertEqual(state.get('defense_buff_turns', 0), 1)
        self.assertEqual(state.get('defense_buff_value', 0), 20)
        self.assertEqual(state.get('defense_buff_source'), 'dueling_ward')
        combat.tick_post_action_player_buff_durations(state)
        self.assertEqual(state.get('defense_buff_turns', 0), 0)
        self.assertIsNone(state.get('defense_buff_source'))

    def test_mana_feint_applies_slow_correctly(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 18, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        state = {'weapon_damage': 16, 'weapon_type': 'magic', 'weapon_profile': 'wand'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('mana_feint', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertTrue(any(e.get('type') == 'slow' and e.get('turns', 0) > 0 for e in result['effects']))
        self.assertGreater(result.get('damage', 0), 0)

    def test_hex_bolt_benefits_from_setup_windows(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 18, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 16, 'weapon_type': 'magic', 'weapon_profile': 'wand'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('hex_bolt', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            setup_state = dict(base_state, spell_echo_turns=1, spell_echo_value=20, quick_channel_turns=1, quick_channel_value=15)
            boosted = skill_engine.use_skill('hex_bolt', dict(player), dict(mob_state), setup_state, telegram_id=101, lang='ru')
        self.assertGreater(boosted['damage'], plain['damage'])

    def test_counterpulse_benefits_from_setup_windows(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 18, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 16, 'weapon_type': 'magic', 'weapon_profile': 'wand'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('counterpulse', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            setup_state = dict(base_state, spell_echo_turns=1, spell_echo_value=20, quick_channel_turns=1, quick_channel_value=15)
            boosted = skill_engine.use_skill('counterpulse', dict(player), dict(mob_state), setup_state, telegram_id=101, lang='ru')
        self.assertGreater(boosted['damage'], plain['damage'])

    def test_duel_arc_benefits_from_setup_windows(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 18, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 16, 'weapon_type': 'magic', 'weapon_profile': 'wand'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('duel_arc', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            setup_state = dict(base_state, spell_echo_turns=1, spell_echo_value=20, quick_channel_turns=1, quick_channel_value=15)
            boosted = skill_engine.use_skill('duel_arc', dict(player), dict(mob_state), setup_state, telegram_id=101, lang='ru')
        self.assertGreater(boosted['damage'], plain['damage'])

    def test_counterpulse_ward_payoff_requires_dueling_ward_source(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 18, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 16, 'weapon_type': 'magic', 'weapon_profile': 'wand'}
        mob_plain = {'hp': 100, 'defense': 0, 'effects': []}
        mob_slowed = {'hp': 100, 'defense': 0, 'effects': [{'type': 'slow', 'turns': 2, 'value': 0}]}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('counterpulse', dict(player), dict(mob_plain), dict(base_state), telegram_id=101, lang='ru')
            generic_defense = skill_engine.use_skill(
                'counterpulse',
                dict(player),
                dict(mob_plain),
                dict(base_state, defense_buff_turns=2, defense_buff_value=20, defense_buff_source='mana_shield'),
                telegram_id=101,
                lang='ru',
            )
            dueling_ward = skill_engine.use_skill(
                'counterpulse',
                dict(player),
                dict(mob_plain),
                dict(base_state, defense_buff_turns=2, defense_buff_value=20, defense_buff_source='dueling_ward'),
                telegram_id=101,
                lang='ru',
            )
            slowed = skill_engine.use_skill('counterpulse', dict(player), dict(mob_slowed), dict(base_state), telegram_id=101, lang='ru')
        self.assertEqual(generic_defense['damage'], plain['damage'])
        self.assertGreater(dueling_ward['damage'], plain['damage'])
        self.assertGreater(slowed['damage'], plain['damage'])

    def test_duel_arc_behaves_as_capstone_punish_in_active_duel_window(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 18, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        base_state = {'weapon_damage': 16, 'weapon_type': 'magic', 'weapon_profile': 'wand'}
        mob_plain = {'hp': 100, 'defense': 0, 'effects': []}
        mob_slowed = {'hp': 100, 'defense': 0, 'effects': [{'type': 'slow', 'turns': 2, 'value': 0}]}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('duel_arc', dict(player), dict(mob_plain), dict(base_state), telegram_id=101, lang='ru')
            duel_window = skill_engine.use_skill('duel_arc', dict(player), dict(mob_slowed), dict(base_state, defense_buff_turns=2, defense_buff_value=20), telegram_id=101, lang='ru')
        self.assertGreater(duel_window['damage'], plain['damage'])

    def test_dueling_ward_does_not_consume_spell_echo_or_quick_channel(self):
        player = {'mana': 100, 'intuition': 16}
        state = {
            'weapon_damage': 16,
            'weapon_type': 'magic',
            'weapon_profile': 'wand',
            'spell_echo_turns': 1,
            'spell_echo_value': 20,
            'quick_channel_turns': 1,
            'quick_channel_value': 15,
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('dueling_ward', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertEqual(state.get('spell_echo_turns', 0), 1)
        self.assertEqual(state.get('quick_channel_turns', 0), 1)

    def test_mana_feint_does_not_consume_spell_echo_or_quick_channel(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 18, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        state = {
            'weapon_damage': 16,
            'weapon_type': 'magic',
            'weapon_profile': 'wand',
            'spell_echo_turns': 1,
            'spell_echo_value': 20,
            'quick_channel_turns': 1,
            'quick_channel_value': 15,
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            skill_engine.use_skill('mana_feint', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertEqual(state.get('spell_echo_turns', 0), 1)
        self.assertEqual(state.get('quick_channel_turns', 0), 1)

    def test_arcanist_gets_stronger_setup_payoff_than_duelist_skill(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 18, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}
        base_state = {'weapon_damage': 16, 'weapon_type': 'magic', 'weapon_profile': 'wand'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            arcanist_plain = skill_engine.use_skill('arcane_bolt', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            arcanist_boost = skill_engine.use_skill(
                'arcane_bolt',
                dict(player),
                dict(mob_state),
                dict(base_state, spell_echo_turns=1, spell_echo_value=20, quick_channel_turns=1, quick_channel_value=15),
                telegram_id=101,
                lang='ru',
            )
            duelist_plain = skill_engine.use_skill('hex_bolt', dict(player), dict(mob_state), dict(base_state), telegram_id=101, lang='ru')
            duelist_boost = skill_engine.use_skill(
                'hex_bolt',
                dict(player),
                dict(mob_state),
                dict(base_state, spell_echo_turns=1, spell_echo_value=20, quick_channel_turns=1, quick_channel_value=15),
                telegram_id=101,
                lang='ru',
            )
        self.assertGreater(arcanist_boost['damage'] - arcanist_plain['damage'], duelist_boost['damage'] - duelist_plain['damage'])

    def test_tome_tree_is_full_5_plus_5(self):
        tree = game_skills.SKILL_TREES['tome']
        self.assertEqual(tree['A'], ['arcane_shield', 'weaken', 'insight', 'dispel_script', 'grand_enchantment'])
        self.assertEqual(tree['B'], ['hybrid_missile', 'borrowed_flame', 'borrowed_grace', 'synthesis', 'forbidden_thesis'])

    def test_tome_item_exists_with_weapon_profile(self):
        tome = items_data.ITEMS['tome']
        self.assertEqual(tome['item_type'], 'weapon')
        self.assertEqual(tome['weapon_profile'], 'tome')

    def test_arcane_shield_applies_support_defense_for_ally(self):
        player = {'mana': 100, 'wisdom': 18}
        state = {
            'weapon_damage': 12,
            'weapon_type': 'magic',
            'weapon_profile': 'tome',
            'player_hp': 100,
            'player_max_hp': 100,
            'allies': {'ally_1': {'player_hp': 80, 'player_max_hp': 100}},
            'pending_skill_target': {'kind': 'ally', 'id': 'ally_1'},
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('arcane_shield', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertEqual(result['target_kind'], 'ally')
        self.assertGreater(state['allies']['ally_1'].get('defense_buff_turns', 0), 0)
        self.assertGreater(state['allies']['ally_1'].get('defense_buff_value', 0), 0)

    def test_weakened_reduces_enemy_damage_in_centralized_path(self):
        state = {'mob_effects': [{'type': 'weakened', 'turns': 2, 'value': 25}]}
        result = combat.resolve_enemy_damage_against_player(
            state,
            lang='ru',
            mob_result={'type': 'mob_attack', 'damage': 100, 'player_hp': 0},
        )
        self.assertEqual(result['player_damage'], 75)
        self.assertEqual(state['mob_effects'][0]['turns'], 2)

    def test_weakened_duration_ticks_even_when_enemy_attack_is_skipped(self):
        player = {'hp': 100, 'agility': 0, 'vitality': 0, 'wisdom': 0}
        mob = {'id': 'wolf', 'weapon_type': 'melee', 'damage_min': 8, 'damage_max': 8}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [{'type': 'weakened', 'turns': 2, 'value': 20}],
            'invincible_turns': 1,
        }
        combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)
        self.assertEqual(state['mob_effects'][0]['turns'], 1)

    def test_multiple_weakened_sources_do_not_stack_and_strongest_wins(self):
        state = {
            'mob_effects': [
                {'type': 'weakened', 'turns': 2, 'value': 10},
                {'type': 'weakened', 'turns': 1, 'value': 30},
            ],
        }
        result = combat.resolve_enemy_damage_against_player(
            state,
            lang='ru',
            mob_result={'type': 'mob_attack', 'damage': 100, 'player_hp': 0},
        )
        self.assertEqual(result['player_damage'], 70)

    def test_weakened_writer_merges_strongest_value_with_longest_duration(self):
        state = {'mob_effects': []}

        skill_engine._apply_or_refresh_enemy_weakened_effect(
            state,
            value=12,   # weaker value
            turns=4,    # longer duration
            skill_id='first_source',
        )
        skill_engine._apply_or_refresh_enemy_weakened_effect(
            state,
            value=30,   # stronger value
            turns=1,    # shorter duration
            skill_id='second_source',
        )

        weakened_effects = [
            e for e in state.get('mob_effects', [])
            if e.get('type') == 'weakened' and int(e.get('turns', 0)) > 0
        ]
        self.assertEqual(len(weakened_effects), 1)
        self.assertEqual(weakened_effects[0]['value'], 30)
        self.assertEqual(weakened_effects[0]['turns'], 4)

    def test_weaken_skill_uses_duration_from_skill_content_data(self):
        player = {'mana': 100, 'wisdom': 14, 'strength': 1, 'agility': 1, 'intuition': 1, 'vitality': 1, 'luck': 1}
        state = {
            'weapon_damage': 10,
            'weapon_type': 'magic',
            'weapon_profile': 'tome',
            'player_mana': 100,
            'mob_effects': [],
        }
        expected_duration = skill_engine.get_skill('weaken')['duration']

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('weaken', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')

        self.assertTrue(result['success'])
        weakened_effect = next((e for e in state['mob_effects'] if e.get('type') == 'weakened'), None)
        self.assertIsNotNone(weakened_effect)
        self.assertEqual(weakened_effect['turns'], expected_duration)

    def test_widows_kiss_payoff_works_with_runtime_weakened_from_crippling_venom(self):
        player = {'mana': 100, 'strength': 1, 'agility': 16, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1}
        mob = {'id': 'wolf', 'defense': 0}
        state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'weapon_damage': 14,
            'weapon_type': 'melee',
            'weapon_profile': 'dagger',
            'log': [],
            'turn': 1,
        }

        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            setup_result = combat.process_skill_turn('crippling_venom', dict(player), mob, state, user_id=101, lang='ru')
            payoff_result = combat.process_skill_turn('widows_kiss', dict(player), mob, state, user_id=101, lang='ru')

        self.assertTrue(setup_result['success'])
        self.assertTrue(any(e.get('type') == 'weakened' for e in state.get('mob_effects', [])))
        self.assertEqual(payoff_result['skill_result'].get('log_key'), 'skills.log_widows_kiss_payoff')

    def test_insight_restores_mana_for_selected_targets(self):
        player = {'mana': 70, 'wisdom': 18}
        state = {
            'weapon_damage': 12,
            'weapon_type': 'magic',
            'weapon_profile': 'tome',
            'player_mana': 70,
            'player_max_mana': 100,
            'allies': {'ally_1': {'player_mana': 20, 'player_max_mana': 80}},
            'pending_skill_target': {'kind': 'ally', 'id': 'ally_1'},
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('insight', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertEqual(result['target_kind'], 'ally')
        self.assertGreater(state['allies']['ally_1']['player_mana'], 20)

    def test_dispel_script_removes_only_supported_subset(self):
        player = {'mana': 100, 'wisdom': 18}
        state = {
            'weapon_damage': 12,
            'weapon_type': 'magic',
            'weapon_profile': 'tome',
            'player_hp': 90,
            'player_max_hp': 100,
            'support_effects': [
                {'skill_id': 'toxin', 'dispel_tag': 'poison', 'can_dispel': True},
                {'skill_id': 'boss_lock', 'dispel_tag': 'boss_lock', 'can_dispel': True},
            ],
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            skill_engine.use_skill('dispel_script', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertEqual(len(state['support_effects']), 1)
        self.assertEqual(state['support_effects'][0]['skill_id'], 'boss_lock')

    def test_grand_enchantment_gives_party_value_without_party_combat_rewrite(self):
        player = {'mana': 100, 'wisdom': 18}
        state = {
            'weapon_damage': 12,
            'weapon_type': 'magic',
            'weapon_profile': 'tome',
            'player_mana': 50,
            'player_max_mana': 100,
            'allies': {'ally_1': {'player_mana': 20, 'player_max_mana': 80}},
            'pending_skill_target': {'kind': 'party'},
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('grand_enchantment', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertEqual(result['target_kind'], 'party')
        self.assertGreater(state['player_mana'], 50)
        self.assertGreater(state['allies']['ally_1']['player_mana'], 20)
        self.assertGreater(state.get('defense_buff_turns', 0), 0)

    def test_borrowed_flame_applies_burn_setup(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 16, 'vitality': 1, 'wisdom': 14, 'luck': 1}
        state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'tome'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('borrowed_flame', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertGreater(result['damage'], 0)
        self.assertTrue(any(e['type'] == 'burn' for e in result['effects']))

    def test_borrowed_flame_applies_exactly_one_burn_effect_without_double_stack(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 16, 'vitality': 1, 'wisdom': 14, 'luck': 1}
        state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'tome'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('borrowed_flame', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')

        burn_effects = [e for e in result['effects'] if e.get('type') == 'burn']
        self.assertEqual(len(burn_effects), 1)
        self.assertEqual(burn_effects[0].get('turns'), 3)
        self.assertGreaterEqual(burn_effects[0].get('value', 0), 1)
        self.assertLessEqual(burn_effects[0].get('value', 0), 1000)

    def test_borrowed_grace_sets_modest_holy_setup(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 12, 'vitality': 1, 'wisdom': 16, 'luck': 1}
        state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'tome'}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('borrowed_grace', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')
        self.assertEqual(result['damage_school'], 'holy')
        self.assertGreater(state.get('blessing_turns', 0), 0)

    def test_synthesis_gets_payoff_from_mixed_setup(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 16, 'vitality': 1, 'wisdom': 16, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'tome'}
        mob_plain = {'hp': 100, 'defense': 0, 'effects': []}
        mob_burn = {'hp': 100, 'defense': 0, 'effects': [{'type': 'burn', 'turns': 2, 'value': 5}]}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('synthesis', dict(player), dict(mob_plain), dict(base_state), telegram_id=101, lang='ru')
            boosted = skill_engine.use_skill('synthesis', dict(player), dict(mob_burn), dict(base_state, blessing_turns=2, blessing_value=8), telegram_id=101, lang='ru')
        self.assertGreater(boosted['damage'], plain['damage'])
        self.assertEqual(boosted['damage'], int(plain['damage'] * 1.50))

    def test_synthesis_gets_partial_payoff_from_one_side_setup(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 16, 'vitality': 1, 'wisdom': 16, 'luck': 1}
        base_state = {'weapon_damage': 14, 'weapon_type': 'magic', 'weapon_profile': 'tome'}
        mob_plain = {'hp': 100, 'defense': 0, 'effects': []}
        mob_burn = {'hp': 100, 'defense': 0, 'effects': [{'type': 'burn', 'turns': 2, 'value': 5}]}
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            plain = skill_engine.use_skill('synthesis', dict(player), dict(mob_plain), dict(base_state), telegram_id=101, lang='ru')
            burn_only = skill_engine.use_skill('synthesis', dict(player), dict(mob_burn), dict(base_state), telegram_id=101, lang='ru')
            grace_only = skill_engine.use_skill(
                'synthesis',
                dict(player),
                dict(mob_plain),
                dict(base_state, blessing_turns=2, blessing_value=8),
                telegram_id=101,
                lang='ru',
            )

        self.assertGreater(burn_only['damage'], plain['damage'])
        self.assertGreater(grace_only['damage'], plain['damage'])
        self.assertEqual(burn_only['damage'], int(plain['damage'] * 1.18))
        self.assertEqual(grace_only['damage'], int(plain['damage'] * 1.18))

    def test_forbidden_thesis_consumes_mixed_windows_only_on_successful_hit(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 16, 'vitality': 1, 'wisdom': 16, 'luck': 1}
        state = {
            'weapon_damage': 14,
            'weapon_type': 'magic',
            'weapon_profile': 'tome',
            'mob_effects': [{'type': 'burn', 'turns': 2, 'value': 8}],
            'blessing_turns': 2,
            'blessing_value': 8,
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            skill_result = skill_engine.use_skill('forbidden_thesis', dict(player), {'hp': 100, 'defense': 0, 'effects': state['mob_effects']}, state, telegram_id=101, lang='ru')
        skill_result['direct_damage_result'] = {'final_damage': skill_result['damage']}
        combat.apply_post_hit_skill_actions(skill_result, state)
        self.assertEqual(state.get('blessing_turns', 0), 0)
        self.assertFalse(any(e.get('type') == 'burn' for e in state.get('mob_effects', [])))

    def test_forbidden_thesis_no_hit_path_does_not_consume_setup_windows(self):
        state = {
            'mob_effects': [{'type': 'burn', 'turns': 2, 'value': 8}],
            'blessing_turns': 2,
            'blessing_value': 8,
        }
        skill_result = {
            'direct_damage_skill': True,
            'direct_damage_result': {'final_damage': 0},
            'post_hit_actions': [{'type': 'consume_burn_and_blessing'}],
        }
        combat.apply_post_hit_skill_actions(skill_result, state)
        self.assertEqual(state.get('blessing_turns', 0), 2)
        self.assertTrue(any(e.get('type') == 'burn' for e in state.get('mob_effects', [])))

    def test_dispel_script_enemy_target_strips_only_supported_enemy_subset(self):
        player = {'mana': 100, 'wisdom': 18}
        state = {
            'weapon_damage': 12,
            'weapon_type': 'magic',
            'weapon_profile': 'tome',
            'mob_effects': [
                {'type': 'blessing', 'turns': 2, 'value': 10},
                {'type': 'ward', 'turns': 1, 'value': 5},
                {'type': 'poison', 'turns': 3, 'value': 7},
            ],
            'pending_skill_target': {'kind': 'enemy', 'id': 'enemy_1'},
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('dispel_script', dict(player), {'hp': 100, 'defense': 0, 'effects': state['mob_effects']}, state, telegram_id=101, lang='ru')

        self.assertEqual(result['target_kind'], 'enemy')
        self.assertEqual(result['target_ids'], ['enemy'])
        self.assertFalse(any(e.get('type') in ('blessing', 'ward') for e in state.get('mob_effects', [])))
        self.assertTrue(any(e.get('type') == 'poison' for e in state.get('mob_effects', [])))

    def test_guardian_light_no_hit_path_does_not_refresh_defense_buff(self):
        state = {
            'defense_buff_turns': 0,
            'defense_buff_value': 0,
        }
        skill_result = {
            'direct_damage_skill': True,
            'direct_damage_result': {'final_damage': 0},
            'post_hit_actions': [{'type': 'refresh_defense_buff', 'turns': 2, 'value': 12, 'log_key': 'skills.log_guardian_light'}],
            'log_key': 'skills.log_damage',
            'log_params': {'name': 'Guardian Light', 'dmg': 0, 'cost': 0},
        }
        combat.apply_post_hit_skill_actions(skill_result, state)
        self.assertEqual(state.get('defense_buff_turns', 0), 0)
        self.assertEqual(state.get('defense_buff_value', 0), 0)
        self.assertEqual(skill_result.get('log_key'), 'skills.log_damage')

    def test_failed_skill_precheck_keeps_runtime_target_intent(self):
        state = {
            'weapon_damage': 12,
            'weapon_type': 'magic',
            'weapon_profile': 'tome',
            'pending_skill_target': {'kind': 'ally', 'id': 'ally_1'},
            'skill_target_kind': 'party',
            'skill_target_id': 'stale_ally',
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=2), \
             patch('game.skill_engine.set_skill_cooldown'):
            result = skill_engine.use_skill('heal', {'mana': 100, 'wisdom': 18}, {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')

        self.assertFalse(result['success'])
        self.assertIn('pending_skill_target', state)
        self.assertIn('skill_target_kind', state)
        self.assertIn('skill_target_id', state)

    def test_mixed_school_hooks_are_structurally_present_for_tome_damage_skill(self):
        player = {'mana': 100, 'strength': 1, 'agility': 1, 'intuition': 16, 'vitality': 1, 'wisdom': 16, 'luck': 1}
        state = {
            'weapon_damage': 14,
            'weapon_type': 'magic',
            'weapon_profile': 'tome',
            'blessing_turns': 2,
            'blessing_value': 8,
            'vulnerability_turns': 1,
            'vulnerability_value': 10,
        }
        with patch('game.skill_engine.get_skill_level', return_value=1), \
             patch('game.skill_engine.get_skill_cooldown', return_value=0), \
             patch('game.skill_engine.set_skill_cooldown'), \
             patch('game.skill_engine.random.uniform', return_value=1.0):
            result = skill_engine.use_skill('hybrid_missile', dict(player), {'hp': 100, 'defense': 0, 'effects': []}, state, telegram_id=101, lang='ru')

        hooks = result.get('mixed_school_hooks', {})
        self.assertIn('primary_school', hooks)
        self.assertIn('active_windows', hooks)
        self.assertEqual(hooks['primary_school'], 'magic')
        self.assertIn('blessing_turns', hooks['active_windows'])
        self.assertIn('vulnerability_turns', hooks['active_windows'])

    def test_enemy_targeted_direct_damage_skill_can_miss(self):
        player = {'hp': 100, 'mana': 80, 'agility': 5, 'luck': 5}
        mob = {'id': 'wolf', 'defense': 0, 'level': 2}
        state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 60,
            'mob_effects': [],
            'log': [],
            'turn': 1,
        }
        skill_result = {
            'success': True,
            'log': 'cast',
            'damage': 22,
            'heal': 0,
            'effects': [],
            'direct_damage_skill': True,
            'target_kind': 'enemy',
            'damage_school': 'magic',
            'log_key': 'skills.log_damage',
            'log_params': {'name': 'Fireball', 'dmg': 22, 'cost': 10},
            'log_suffixes': [],
            'post_hit_actions': [],
        }

        with patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.resolve_hit_check', return_value={'outcome': 'miss', 'is_hit': False, 'hit_chance': 25, 'roll': 99, 'accuracy_rating': 100, 'evasion_rating': 200}), \
             patch('game.combat.finalize_player_direct_damage_action') as finalize_mock, \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('fireball', player, mob, state, user_id=101, lang='ru')

        finalize_mock.assert_not_called()
        self.assertEqual(result['battle_state']['mob_hp'], 60)
        self.assertEqual(result['skill_result']['damage'], 0)
        self.assertIn('direct_damage_result', result['skill_result'])

    def test_enemy_targeted_direct_damage_skill_hit_path_still_works(self):
        player = {'hp': 100, 'mana': 80, 'agility': 5, 'luck': 5}
        mob = {'id': 'wolf', 'defense': 0, 'level': 2}
        state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 60,
            'mob_effects': [],
            'log': [],
            'turn': 1,
        }
        skill_result = {
            'success': True,
            'log': 'cast',
            'damage': 22,
            'heal': 0,
            'effects': [],
            'direct_damage_skill': True,
            'target_kind': 'enemy',
            'damage_school': 'magic',
            'log_key': 'skills.log_damage',
            'log_params': {'name': 'Fireball', 'dmg': 22, 'cost': 10},
            'log_suffixes': [],
            'post_hit_actions': [],
        }

        with patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.resolve_hit_check', return_value={'outcome': 'hit', 'is_hit': True, 'hit_chance': 95, 'roll': 1, 'accuracy_rating': 200, 'evasion_rating': 100}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('fireball', player, mob, state, user_id=101, lang='ru')

        self.assertEqual(result['battle_state']['mob_hp'], 38)
        self.assertEqual(result['skill_result']['damage'], 22)

    def test_direct_damage_skill_with_guaranteed_hit_bypasses_hit_check(self):
        player = {'hp': 100, 'mana': 80, 'agility': 5, 'luck': 5}
        mob = {'id': 'wolf', 'defense': 0, 'level': 2}
        state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 60,
            'mob_effects': [],
            'log': [],
            'turn': 1,
        }
        skill_result = {
            'success': True,
            'log': 'cast',
            'damage': 22,
            'heal': 0,
            'effects': [],
            'direct_damage_skill': True,
            'target_kind': 'enemy',
            'guaranteed_hit': True,
            'damage_school': 'magic',
            'log_key': 'skills.log_damage',
            'log_params': {'name': 'Fireball', 'dmg': 22, 'cost': 10},
            'log_suffixes': [],
            'post_hit_actions': [],
        }

        with patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.resolve_hit_check') as hit_check_mock, \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('fireball', player, mob, state, user_id=101, lang='ru')

        hit_check_mock.assert_not_called()
        self.assertEqual(result['battle_state']['mob_hp'], 38)
        self.assertEqual(result['skill_result']['damage'], 22)
        self.assertTrue(result['skill_result']['direct_damage_result']['hit_check']['guaranteed_hit'])

    def test_direct_damage_skill_accuracy_bonus_is_added_to_accuracy_rating(self):
        player = {'agility': 5, 'luck': 5}
        mob = {'id': 'wolf', 'level': 2}
        state = {'mob_hp': 100}
        skill_result = {
            'direct_damage_skill': True,
            'target_kind': 'enemy',
            'damage': 20,
            'effects': [],
            'accuracy_bonus': 15,
        }

        with patch('game.combat.get_player_accuracy_rating', return_value=120), \
             patch('game.combat.get_enemy_evasion_rating', return_value=90), \
             patch('game.combat.resolve_hit_check', return_value={'outcome': 'miss', 'is_hit': False}) as hit_check_mock:
            combat.resolve_enemy_targeted_direct_damage_skill_action(
                player,
                mob,
                state,
                skill_result,
                lang='ru',
            )

        hit_check_mock.assert_called_once_with(135, 90)

    def test_direct_damage_skill_ignore_evasion_uses_zero_evasion_rating(self):
        player = {'agility': 5, 'luck': 5}
        mob = {'id': 'wolf', 'level': 2}
        state = {'mob_hp': 100}
        skill_result = {
            'direct_damage_skill': True,
            'target_kind': 'enemy',
            'damage': 20,
            'effects': [],
            'ignore_evasion': True,
        }

        with patch('game.combat.get_player_accuracy_rating', return_value=120), \
             patch('game.combat.get_enemy_evasion_rating') as evasion_mock, \
             patch('game.combat.resolve_hit_check', return_value={'outcome': 'miss', 'is_hit': False}) as hit_check_mock:
            combat.resolve_enemy_targeted_direct_damage_skill_action(
                player,
                mob,
                state,
                skill_result,
                lang='ru',
            )

        evasion_mock.assert_not_called()
        hit_check_mock.assert_called_once_with(120, 0)

    def test_skill_without_accuracy_overrides_keeps_current_behavior(self):
        player = {'agility': 5, 'luck': 5}
        mob = {'id': 'wolf', 'level': 2}
        state = {'mob_hp': 100}
        skill_result = {
            'direct_damage_skill': True,
            'target_kind': 'enemy',
            'damage': 20,
            'effects': [],
        }

        with patch('game.combat.get_player_accuracy_rating', return_value=110) as player_accuracy_mock, \
             patch('game.combat.get_enemy_evasion_rating', return_value=95) as enemy_evasion_mock, \
             patch('game.combat.resolve_hit_check', return_value={'outcome': 'miss', 'is_hit': False}) as hit_check_mock:
            combat.resolve_enemy_targeted_direct_damage_skill_action(
                player,
                mob,
                state,
                skill_result,
                lang='ru',
            )

        player_accuracy_mock.assert_called_once_with(player, state)
        enemy_evasion_mock.assert_called_once_with(mob, state)
        hit_check_mock.assert_called_once_with(110, 95)

    def test_skill_miss_does_not_apply_post_hit_actions(self):
        player = {'hp': 100, 'mana': 80, 'agility': 5, 'luck': 5}
        mob = {'id': 'wolf', 'defense': 0, 'level': 2}
        state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 100,
            'mob_effects': [],
            'defense_buff_turns': 0,
            'defense_buff_value': 0,
            'log': [],
            'turn': 1,
        }
        skill_result = {
            'success': True,
            'log': 'cast',
            'damage': 20,
            'heal': 0,
            'effects': [],
            'direct_damage_skill': True,
            'target_kind': 'enemy',
            'damage_school': 'holy',
            'log_key': 'skills.log_damage',
            'log_params': {'name': 'Guardian Light', 'dmg': 20, 'cost': 10},
            'log_suffixes': [],
            'post_hit_actions': [{'type': 'refresh_defense_buff', 'turns': 2, 'value': 14}],
        }

        with patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.resolve_hit_check', return_value={'outcome': 'miss', 'is_hit': False, 'hit_chance': 25, 'roll': 99, 'accuracy_rating': 100, 'evasion_rating': 200}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('guardian_light', player, mob, state, user_id=101, lang='ru')

        self.assertEqual(result['battle_state']['defense_buff_turns'], 0)
        self.assertEqual(result['battle_state']['defense_buff_value'], 0)

    def test_skill_miss_does_not_consume_hit_gated_payoff_window(self):
        player = {'hp': 100, 'mana': 80, 'agility': 5, 'luck': 5}
        mob = {'id': 'wolf', 'defense': 0, 'level': 2}
        state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 100,
            'mob_effects': [],
            'vulnerability_turns': 2,
            'vulnerability_value': 20,
            'log': [],
            'turn': 1,
        }
        skill_result = {
            'success': True,
            'log': 'cast',
            'damage': 25,
            'heal': 0,
            'effects': [],
            'direct_damage_skill': True,
            'target_kind': 'enemy',
            'damage_school': 'physical',
            'log_key': 'skills.log_damage',
            'log_params': {'name': 'Final Verdict', 'dmg': 25, 'cost': 12},
            'log_suffixes': [],
            'post_hit_actions': [{'type': 'consume_vulnerability'}],
        }

        with patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.resolve_hit_check', return_value={'outcome': 'miss', 'is_hit': False, 'hit_chance': 25, 'roll': 99, 'accuracy_rating': 100, 'evasion_rating': 200}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('final_verdict', player, mob, state, user_id=101, lang='ru')

        self.assertEqual(result['battle_state']['vulnerability_turns'], 2)
        self.assertEqual(result['battle_state']['vulnerability_value'], 20)

    def test_skill_miss_does_not_apply_enemy_effects(self):
        player = {'hp': 100, 'mana': 80, 'agility': 5, 'luck': 5}
        mob = {'id': 'wolf', 'defense': 0, 'level': 2}
        state = {
            'player_hp': 100,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 100,
            'mob_effects': [],
            'log': [],
            'turn': 1,
        }
        skill_result = {
            'success': True,
            'log': 'cast',
            'damage': 25,
            'heal': 0,
            'effects': [
                {'type': 'burn', 'turns': 2, 'value': 4},
                {'type': 'slow', 'turns': 1, 'value': 20},
                {'type': 'weaken', 'turns': 2, 'value': 15},
            ],
            'direct_damage_skill': True,
            'target_kind': 'enemy',
            'damage_school': 'magic',
            'log_key': 'skills.log_damage',
            'log_params': {'name': 'Borrowed Flame', 'dmg': 25, 'cost': 12},
            'log_suffixes': [],
            'post_hit_actions': [],
        }

        with patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.resolve_hit_check', return_value={'outcome': 'miss', 'is_hit': False, 'hit_chance': 25, 'roll': 99, 'accuracy_rating': 100, 'evasion_rating': 200}), \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('borrowed_flame', player, mob, state, user_id=101, lang='ru')

        self.assertEqual(result['battle_state']['mob_hp'], 100)
        self.assertEqual(result['skill_result']['damage'], 0)
        self.assertEqual(result['battle_state']['mob_effects'], [])

    def test_non_enemy_skill_bypasses_accuracy_gate(self):
        player = {'hp': 100, 'mana': 80}
        mob = {'id': 'wolf', 'defense': 0, 'level': 2}
        state = {
            'player_hp': 70,
            'player_max_hp': 100,
            'player_mana': 80,
            'mob_hp': 100,
            'mob_effects': [],
            'log': [],
            'turn': 1,
        }
        skill_result = {
            'success': True,
            'log': 'cast',
            'damage': 0,
            'heal': 20,
            'effects': [],
            'direct_damage_skill': False,
            'target_kind': 'self',
            'log_key': None,
            'log_params': {},
            'log_suffixes': [],
            'post_hit_actions': [],
        }

        with patch('game.combat.use_skill', return_value=skill_result), \
             patch('game.combat.resolve_hit_check') as hit_check_mock, \
             patch('game.combat.apply_pre_enemy_response_ticks', return_value=[]), \
             patch('game.combat.resolve_enemy_response', return_value=[]):
            result = combat.process_skill_turn('heal', player, mob, state, user_id=101, lang='ru')

        hit_check_mock.assert_not_called()
        self.assertEqual(result['battle_state']['player_hp'], 90)

    def test_magic_staff_holy_staff_holy_rod_regression_spot_check(self):
        self.assertEqual(game_skills.SKILL_TREES['magic_staff']['A'][0], 'fireball')
        self.assertEqual(game_skills.SKILL_TREES['holy_staff']['A'][0], 'heal')
        self.assertEqual(game_skills.SKILL_TREES['holy_rod']['A'][0], 'sacred_shield')

    def test_player_normal_attack_can_miss_when_enemy_evasion_is_high(self):
        player = {
            'hp': 100,
            'strength': 10,
            'agility': 5,
            'intuition': 5,
            'vitality': 5,
            'wisdom': 5,
            'luck': 5,
            'weapon_damage': 10,
            'weapon_type': 'melee',
            'damage_school': 'physical',
        }
        mob = {'id': 'forest_wolf', 'defense': 0, 'level': 2}
        battle_state = {'mob_hp': 50, 'mastery_level': 1}

        with patch('game.combat.resolve_hit_check', return_value={'outcome': 'miss', 'is_hit': False, 'hit_chance': 25, 'roll': 99, 'accuracy_rating': 100, 'evasion_rating': 200}), \
             patch('game.combat.player_attack') as player_attack_mock:
            result = combat.resolve_normal_attack_action(player, mob, battle_state, lang='ru')

        player_attack_mock.assert_not_called()
        self.assertEqual(result['damage'], 0)
        self.assertFalse(result['is_crit'])
        self.assertIn('log_line', result)

    def test_player_normal_attack_hit_path_still_works(self):
        player = {
            'hp': 100,
            'strength': 10,
            'agility': 5,
            'intuition': 5,
            'vitality': 5,
            'wisdom': 5,
            'luck': 5,
            'weapon_damage': 10,
            'weapon_type': 'melee',
            'damage_school': 'physical',
        }
        mob = {'id': 'forest_wolf', 'defense': 0, 'level': 2}
        battle_state = {'mob_hp': 50, 'mastery_level': 1}

        with patch('game.combat.resolve_hit_check', return_value={'outcome': 'hit', 'is_hit': True, 'hit_chance': 95, 'roll': 1, 'accuracy_rating': 200, 'evasion_rating': 100}), \
             patch('game.combat.player_attack', return_value={'damage': 12, 'is_crit': False, 'mob_dead': False}):
            result = combat.resolve_normal_attack_action(player, mob, battle_state, lang='ru')

        self.assertEqual(result['damage'], 12)
        self.assertEqual(battle_state['mob_hp'], 38)
        self.assertFalse(result['mob_dead'])

    def test_enemy_attack_can_miss_when_player_evasion_is_high(self):
        player = {'hp': 100, 'agility': 10, 'vitality': 0, 'wisdom': 0, 'luck': 10}
        mob = {'id': 'forest_wolf', 'level': 2, 'damage_min': 10, 'damage_max': 10, 'weapon_type': 'melee'}
        state = {'player_hp': 100, 'mob_hp': 100, 'mob_effects': []}

        with patch('game.combat.resolve_hit_check', return_value={'outcome': 'miss', 'is_hit': False, 'hit_chance': 25, 'roll': 99, 'accuracy_rating': 100, 'evasion_rating': 200}), \
             patch('game.combat.mob_attack') as mob_attack_mock:
            log = combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        mob_attack_mock.assert_not_called()
        self.assertEqual(state['player_hp'], 100)
        self.assertTrue(len(log) > 0)

    def test_enemy_miss_does_not_trigger_or_consume_parry(self):
        player = {'hp': 100, 'agility': 10, 'vitality': 0, 'wisdom': 0, 'luck': 10}
        mob = {'id': 'forest_wolf', 'level': 2, 'damage_min': 10, 'damage_max': 10, 'weapon_type': 'melee'}
        state = {
            'player_hp': 100,
            'mob_hp': 100,
            'mob_effects': [],
            'parry_active': True,
            'parry_value': 1.0,
        }

        with patch('game.combat.resolve_hit_check', return_value={'outcome': 'miss', 'is_hit': False, 'hit_chance': 25, 'roll': 99, 'accuracy_rating': 100, 'evasion_rating': 200}), \
             patch('game.combat.mob_attack') as mob_attack_mock:
            combat.resolve_enemy_response(mob, player, state, lang='ru', user_id=None)

        mob_attack_mock.assert_not_called()
        self.assertTrue(state['parry_active'])
        self.assertEqual(state['mob_hp'], 100)


if __name__ == '__main__':
    unittest.main()
