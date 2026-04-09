import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers import battle as battle_handler


class _DummyQuery:
    def __init__(self, data: str, user_id: int = 88001):
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()


class _DummyUpdate:
    def __init__(self, data: str, user_id: int = 88001):
        self.callback_query = _DummyQuery(data, user_id=user_id)


class _DummyContext:
    def __init__(self, battle_state: dict, mob: dict):
        self.user_data = {'battle': battle_state, 'battle_mob': mob}


class SoloPveRuntimeHandlerFlowTests(unittest.IsolatedAsyncioTestCase):
    def _player_row(self):
        return {
            'telegram_id': 88001,
            'lang': 'en',
            'hp': 100,
            'mana': 50,
            'agility': 10,
            'vitality': 10,
            'wisdom': 10,
            'luck': 10,
            'exp': 0,
            'gold': 0,
            'level': 1,
            'stat_points': 0,
        }

    async def test_attack_flow_uses_player_only_then_enemy_side(self):
        update = _DummyUpdate('battle_attack_forest_wolf')
        battle_state = {
            'mob_hp': 20,
            'player_hp': 100,
            'player_mana': 50,
            'player_max_mana': 50,
            'player_max_hp': 100,
            'log': [],
            'turn': 1,
            'weapon_id': 'unarmed',
        }
        mob = {'id': 'forest_wolf', 'hp': 20}
        context = _DummyContext(battle_state, mob)

        with patch('handlers.battle.get_player', return_value=self._player_row()), \
             patch('handlers.battle.ensure_runtime_for_battle'), \
             patch('handlers.battle.process_due_timeout_for_battle', return_value=False), \
             patch('handlers.battle.submit_player_commit', return_value=(True, 'committed')), \
             patch('handlers.battle.resolve_current_side_if_ready', side_effect=lambda **kwargs: kwargs['on_player_action'](None) or True), \
             patch('handlers.battle.process_turn', return_value={**battle_state, 'mob_dead': False, 'player_dead': False}) as player_side_mock, \
             patch('handlers.battle.run_enemy_instant_side', side_effect=lambda **kwargs: kwargs['on_enemy_action'](None)), \
             patch('handlers.battle.process_enemy_side_turn', side_effect=lambda *args, **kwargs: {**battle_state, 'mob_dead': False, 'player_dead': False}) as enemy_side_mock, \
             patch('handlers.battle.tick_cooldowns'), \
             patch('handlers.battle._resolve_post_attack_combat_resolution', new=AsyncMock(return_value=False)):
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(player_side_mock.call_count, 1)
        self.assertEqual(enemy_side_mock.call_count, 1)

    async def test_skill_flow_disables_enemy_response_inside_player_side(self):
        update = _DummyUpdate('battle_skill_fireball|forest_wolf')
        battle_state = {
            'mob_hp': 20,
            'player_hp': 100,
            'player_mana': 50,
            'player_max_mana': 50,
            'player_max_hp': 100,
            'log': [],
            'turn': 1,
            'weapon_id': 'unarmed',
            'mastery_level': 1,
        }
        mob = {'id': 'forest_wolf', 'hp': 20}
        context = _DummyContext(battle_state, mob)

        with patch('handlers.battle.get_player', return_value=self._player_row()), \
             patch('handlers.battle.ensure_runtime_for_battle'), \
             patch('handlers.battle.process_due_timeout_for_battle', return_value=False), \
             patch('handlers.battle.preview_skill_turn_precheck', return_value={'success': True, 'log': ''}) as precheck_mock, \
             patch('handlers.battle.submit_player_commit', return_value=(True, 'committed')), \
             patch('handlers.battle.resolve_current_side_if_ready', side_effect=lambda **kwargs: kwargs['on_player_action'](None) or True), \
             patch('handlers.battle.process_skill_turn', return_value={'success': True, 'battle_state': battle_state, 'skill_result': {'log': 'ok'}}, autospec=True) as skill_turn_mock, \
             patch('handlers.battle.add_mastery_exp'), \
             patch('handlers.battle.tick_cooldowns'), \
             patch('handlers.battle.run_enemy_instant_side', side_effect=lambda **kwargs: kwargs['on_enemy_action'](None)), \
             patch('handlers.battle.process_enemy_side_turn') as enemy_side_mock, \
             patch('handlers.battle._handle_battle_continues_update', new=AsyncMock()) as continues_mock:
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(precheck_mock.call_count, 1)
        self.assertEqual(skill_turn_mock.call_count, 1)
        _, kwargs = skill_turn_mock.call_args
        self.assertFalse(kwargs['include_enemy_response'])
        self.assertFalse(kwargs['tick_timed_trigger_buffs_now'])
        self.assertEqual(enemy_side_mock.call_count, 1)
        self.assertEqual(continues_mock.call_count, 1)

    async def test_failed_skill_precheck_does_not_commit_turn(self):
        update = _DummyUpdate('battle_skill_fireball|forest_wolf')
        battle_state = {
            'mob_hp': 20,
            'player_hp': 100,
            'player_mana': 0,
            'player_max_mana': 50,
            'player_max_hp': 100,
            'log': [],
            'turn': 1,
            'weapon_id': 'unarmed',
        }
        mob = {'id': 'forest_wolf', 'hp': 20}
        context = _DummyContext(battle_state, mob)

        with patch('handlers.battle.get_player', return_value=self._player_row()), \
             patch('handlers.battle.ensure_runtime_for_battle'), \
             patch('handlers.battle.process_due_timeout_for_battle', return_value=False), \
             patch('handlers.battle.preview_skill_turn_precheck', return_value={'success': False, 'log': 'not enough mana'}), \
             patch('handlers.battle.submit_player_commit') as commit_mock:
            await battle_handler.handle_battle_buttons(update, context)

        commit_mock.assert_not_called()
        update.callback_query.answer.assert_awaited()

    async def test_rejected_skill_commit_does_not_execute_skill_turn(self):
        update = _DummyUpdate('battle_skill_fireball|forest_wolf')
        battle_state = {
            'mob_hp': 20,
            'player_hp': 100,
            'player_mana': 50,
            'player_max_mana': 50,
            'player_max_hp': 100,
            'log': [],
            'turn': 1,
            'weapon_id': 'unarmed',
            'mastery_level': 1,
        }
        mob = {'id': 'forest_wolf', 'hp': 20}
        context = _DummyContext(battle_state, mob)

        with patch('handlers.battle.get_player', return_value=self._player_row()), \
             patch('handlers.battle.ensure_runtime_for_battle'), \
             patch('handlers.battle.process_due_timeout_for_battle', return_value=False), \
             patch('handlers.battle.preview_skill_turn_precheck', return_value={'success': True, 'log': ''}), \
             patch('handlers.battle.submit_player_commit', return_value=(False, 'stale_revision')), \
             patch('handlers.battle.process_skill_turn') as skill_turn_mock, \
             patch('handlers.battle.tick_cooldowns') as tick_mock:
            await battle_handler.handle_battle_buttons(update, context)

        skill_turn_mock.assert_not_called()
        tick_mock.assert_not_called()

    async def test_accepted_skill_commit_executes_skill_turn_and_ticks_cooldowns(self):
        update = _DummyUpdate('battle_skill_fireball|forest_wolf')
        battle_state = {
            'mob_hp': 20,
            'player_hp': 100,
            'player_mana': 50,
            'player_max_mana': 50,
            'player_max_hp': 100,
            'log': [],
            'turn': 1,
            'weapon_id': 'unarmed',
            'mastery_level': 1,
        }
        mob = {'id': 'forest_wolf', 'hp': 20}
        context = _DummyContext(battle_state, mob)

        with patch('handlers.battle.get_player', return_value=self._player_row()), \
             patch('handlers.battle.ensure_runtime_for_battle'), \
             patch('handlers.battle.process_due_timeout_for_battle', return_value=False), \
             patch('handlers.battle.preview_skill_turn_precheck', return_value={'success': True, 'log': ''}), \
             patch('handlers.battle.submit_player_commit', return_value=(True, 'committed')), \
             patch('handlers.battle.resolve_current_side_if_ready', side_effect=lambda **kwargs: kwargs['on_player_action'](None) or True), \
             patch('handlers.battle.process_skill_turn', return_value={'success': True, 'battle_state': battle_state, 'skill_result': {'log': 'ok'}}, autospec=True) as skill_turn_mock, \
             patch('handlers.battle.run_enemy_instant_side', side_effect=lambda **kwargs: kwargs['on_enemy_action'](None)), \
             patch('handlers.battle.process_enemy_side_turn'), \
             patch('handlers.battle.add_mastery_exp'), \
             patch('handlers.battle._handle_battle_continues_update', new=AsyncMock()), \
             patch('handlers.battle.tick_cooldowns') as tick_mock:
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(skill_turn_mock.call_count, 1)
        self.assertEqual(tick_mock.call_count, 1)

    async def test_timeout_wiring_executes_before_manual_action(self):
        update = _DummyUpdate('battle_attack_forest_wolf')
        battle_state = {
            'mob_hp': 20,
            'player_hp': 100,
            'player_mana': 50,
            'player_max_mana': 50,
            'player_max_hp': 100,
            'log': [],
            'turn': 1,
            'weapon_id': 'unarmed',
            'mob_dead': False,
            'player_dead': False,
        }
        mob = {'id': 'forest_wolf', 'hp': 20}
        context = _DummyContext(battle_state, mob)

        with patch('handlers.battle.get_player', return_value=self._player_row()), \
             patch('handlers.battle.ensure_runtime_for_battle'), \
             patch('handlers.battle.process_due_timeout_for_battle', return_value=True) as timeout_mock, \
             patch('handlers.battle._resolve_post_attack_combat_resolution', new=AsyncMock(return_value=False)) as resolution_mock, \
             patch('handlers.battle.submit_player_commit') as commit_mock:
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(timeout_mock.call_count, 1)
        self.assertEqual(resolution_mock.call_count, 1)
        commit_mock.assert_not_called()

    async def test_timeout_fallback_changes_battle_state_with_guard_effect(self):
        update = _DummyUpdate('battle_attack_forest_wolf')
        battle_state = {
            'mob_hp': 20,
            'player_hp': 100,
            'player_mana': 50,
            'player_max_mana': 50,
            'player_max_hp': 100,
            'log': [],
            'turn': 1,
            'weapon_id': 'unarmed',
            'mob_dead': False,
            'player_dead': False,
            'defense_buff_turns': 0,
            'defense_buff_value': 0,
        }
        mob = {'id': 'forest_wolf', 'hp': 20}
        context = _DummyContext(battle_state, mob)

        def timeout_side_effect(**kwargs):
            kwargs['on_player_timeout_action'](SimpleNamespace(action_type='fallback_guard'))
            return True

        with patch('handlers.battle.get_player', return_value=self._player_row()), \
             patch('handlers.battle.ensure_runtime_for_battle'), \
             patch('handlers.battle.process_due_timeout_for_battle', side_effect=timeout_side_effect), \
             patch('handlers.battle._resolve_post_attack_combat_resolution', new=AsyncMock(return_value=False)):
            await battle_handler.handle_battle_buttons(update, context)

        self.assertGreaterEqual(battle_state['defense_buff_turns'], 1)
        self.assertGreaterEqual(battle_state['defense_buff_value'], 15)

    async def test_timeout_continue_path_calls_normal_battle_update_render(self):
        update = _DummyUpdate('battle_attack_forest_wolf')
        battle_state = {
            'mob_hp': 20,
            'player_hp': 100,
            'player_mana': 50,
            'player_max_mana': 50,
            'player_max_hp': 100,
            'log': [],
            'turn': 1,
            'weapon_id': 'unarmed',
            'mob_dead': False,
            'player_dead': False,
        }
        mob = {'id': 'forest_wolf', 'hp': 20}
        context = _DummyContext(battle_state, mob)

        with patch('handlers.battle.get_player', return_value=self._player_row()), \
             patch('handlers.battle.ensure_runtime_for_battle'), \
             patch('handlers.battle.process_due_timeout_for_battle', return_value=True), \
             patch('handlers.battle._handle_battle_continues_update', new=AsyncMock()) as continue_mock:
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(continue_mock.call_count, 1)

    async def test_timeout_victory_and_death_paths_keep_terminal_routing(self):
        for mob_dead, player_dead, expected in ((True, False, 'victory'), (False, True, 'death')):
            update = _DummyUpdate('battle_attack_forest_wolf')
            battle_state = {
                'mob_hp': 0 if mob_dead else 20,
                'player_hp': 0 if player_dead else 100,
                'player_mana': 50,
                'player_max_mana': 50,
                'player_max_hp': 100,
                'log': [],
                'turn': 1,
                'weapon_id': 'unarmed',
                'mob_dead': mob_dead,
                'player_dead': player_dead,
            }
            mob = {'id': 'forest_wolf', 'hp': 20}
            context = _DummyContext(battle_state, mob)

            with patch('handlers.battle.get_player', return_value=self._player_row()), \
                 patch('handlers.battle.ensure_runtime_for_battle'), \
                 patch('handlers.battle.process_due_timeout_for_battle', return_value=True), \
                 patch('handlers.battle._handle_victory_cleanup', new=AsyncMock()) as victory_mock, \
                 patch('handlers.battle._handle_death_or_resurrection', new=AsyncMock(return_value=True)) as death_mock:
                await battle_handler.handle_battle_buttons(update, context)

            if expected == 'victory':
                self.assertEqual(victory_mock.call_count, 1)
                self.assertEqual(death_mock.call_count, 0)
            else:
                self.assertEqual(victory_mock.call_count, 0)
                self.assertEqual(death_mock.call_count, 1)

    async def test_state_lost_without_active_encounter_finishes_with_state_lost_cleanup(self):
        update = _DummyUpdate('battle_attack_forest_wolf')
        context = _DummyContext(battle_state={}, mob={})
        context.user_data = {}

        with patch('handlers.battle.get_player', return_value=self._player_row()), \
             patch('handlers.battle.load_active_solo_pve_encounter', return_value=None), \
             patch('handlers.battle.finish_solo_pve_encounter') as finish_mock, \
             patch('handlers.battle.end_battle') as end_battle_mock:
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(end_battle_mock.call_count, 1)
        finish_mock.assert_called_once_with(player_id=88001, status='state_lost')

    async def test_state_lost_recovers_from_shared_encounter_payload(self):
        update = _DummyUpdate('battle_attack_forest_wolf')
        context = _DummyContext(battle_state={}, mob={})
        context.user_data = {}
        restored_state = {
            'pve_encounter_id': 'pve-enc-test123',
            'mob_hp': 20,
            'player_hp': 100,
            'player_mana': 50,
            'player_max_mana': 50,
            'player_max_hp': 100,
            'log': [],
            'turn': 1,
            'weapon_id': 'unarmed',
            'mob_dead': False,
            'player_dead': False,
        }
        restored_mob = {'id': 'forest_wolf', 'hp': 20}

        with patch('handlers.battle.get_player', return_value=self._player_row()), \
             patch('handlers.battle.load_active_solo_pve_encounter', return_value=(restored_state, restored_mob)), \
             patch('handlers.battle.ensure_runtime_for_battle'), \
             patch('handlers.battle.process_due_timeout_for_battle', return_value=False), \
             patch('handlers.battle.submit_player_commit', return_value=(False, 'stale_revision')), \
             patch('handlers.battle.finish_solo_pve_encounter') as finish_mock:
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(context.user_data['battle']['pve_encounter_id'], 'pve-enc-test123')
        self.assertEqual(context.user_data['battle_mob']['id'], 'forest_wolf')
        self.assertEqual(finish_mock.call_count, 0)


if __name__ == '__main__':
    unittest.main()
