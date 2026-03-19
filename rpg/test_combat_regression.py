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
