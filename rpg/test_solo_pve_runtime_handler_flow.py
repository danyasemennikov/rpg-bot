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


class _DummyStartBattleContext:
    def __init__(self):
        self.user_data = {}
        self.application = SimpleNamespace(user_data={88001: {'aggro_message_id': 999}})


class SoloPveRuntimeHandlerFlowTests(unittest.IsolatedAsyncioTestCase):
    def _player_row(self):
        return {
            'telegram_id': 88001,
            'lang': 'en',
            'in_battle': 1,
            'location_id': 'dark_forest',
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

    async def test_fight_first_spawn_unavailable_rolls_back_prelocated_battle_lock(self):
        update = _DummyUpdate('fight_first_forest_wolf')
        context = _DummyStartBattleContext()
        conn = SimpleNamespace(execute=lambda *args, **kwargs: None, commit=lambda: None, close=lambda: None)
        with patch('handlers.battle.get_player', return_value=self._player_row()), \
             patch('handlers.battle.ensure_location_pve_spawn_instances'), \
             patch('handlers.battle.list_location_available_spawn_instances', return_value=[]), \
             patch('handlers.battle.get_mob', return_value={'id': 'forest_wolf', 'hp': 20, 'level': 2}), \
             patch('handlers.battle.get_equipped_combat_items', return_value={}), \
             patch('handlers.battle.get_player_effective_stats', return_value={
                 'strength': 5, 'agility': 5, 'intuition': 5, 'vitality': 5, 'wisdom': 5, 'luck': 5,
                 'max_hp': 100, 'max_mana': 50, 'physical_defense_bonus': 0, 'magic_defense_bonus': 0,
                 'accuracy_bonus': 0, 'evasion_bonus': 0, 'block_chance_bonus': 0, 'magic_power_bonus': 0, 'healing_power_bonus': 0,
             }), \
             patch('handlers.battle.get_mastery', return_value={'level': 1, 'exp': 0}), \
             patch('handlers.battle.init_battle', return_value={'mob_id': 'forest_wolf', 'log': [], 'player_hp': 100, 'player_mana': 50, 'player_max_hp': 100, 'player_max_mana': 50}), \
             patch('handlers.battle.create_or_load_open_world_pve_encounter', return_value=(None, 'spawn_unavailable')), \
             patch('handlers.battle.get_connection', return_value=conn):
            await battle_handler.start_battle(update, context, 'forest_wolf', mob_first=True)

        update.callback_query.answer.assert_awaited_once()
        self.assertNotIn('aggro_message_id', context.application.user_data[88001])

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
             patch('handlers.battle.resolve_current_side_if_ready', side_effect=lambda **kwargs: kwargs['on_player_action'](SimpleNamespace(action_type='basic_attack', participant_id=88001)) or True), \
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
             patch('handlers.battle.resolve_current_side_if_ready', side_effect=lambda **kwargs: kwargs['on_player_action'](SimpleNamespace(action_type='skill', skill_id='fireball', participant_id=88001)) or True), \
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
             patch('handlers.battle.resolve_current_side_if_ready', side_effect=lambda **kwargs: kwargs['on_player_action'](SimpleNamespace(action_type='skill', skill_id='fireball', participant_id=88001)) or True), \
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

    async def test_first_group_commit_does_not_run_enemy_side_while_collecting(self):
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
             patch('handlers.battle.process_due_timeout_for_battle', return_value=False), \
             patch('handlers.battle.submit_player_commit', return_value=(True, 'committed')), \
             patch('handlers.battle.resolve_current_side_if_ready', return_value=False), \
             patch('handlers.battle.run_enemy_instant_side') as enemy_side_mock, \
             patch('handlers.battle._handle_battle_continues_update', new=AsyncMock()) as continue_mock:
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(enemy_side_mock.call_count, 0)
        self.assertEqual(continue_mock.call_count, 1)

    async def test_owner_projection_restored_before_post_resolve_branching(self):
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
            'mob_dead': False,
            'player_dead': False,
            'side_a_player_ids': [88001, 88002],
            'participant_states': {
                '88001': {'player_hp': 100, 'player_mana': 50, 'player_dead': False, 'hp': 100, 'mana': 50, 'defeated': False},
                '88002': {'player_hp': 0, 'player_mana': 0, 'player_dead': True, 'hp': 0, 'mana': 0, 'defeated': True},
            },
        }
        mob = {'id': 'forest_wolf', 'hp': 20}
        context = _DummyContext(battle_state, mob)

        def resolve_side_effect(**kwargs):
            # Simulate batch ended on dead ally projection.
            battle_state['player_hp'] = 0
            battle_state['player_dead'] = True
            return True

        with patch('handlers.battle.get_player', return_value=self._player_row()), \
             patch('handlers.battle.ensure_runtime_for_battle'), \
             patch('handlers.battle.process_due_timeout_for_battle', return_value=False), \
             patch('handlers.battle.preview_skill_turn_precheck', return_value={'success': True, 'log': ''}), \
             patch('handlers.battle.submit_player_commit', return_value=(True, 'committed')), \
             patch('handlers.battle.resolve_current_side_if_ready', side_effect=resolve_side_effect), \
             patch('handlers.battle.run_enemy_instant_side') as enemy_side_mock, \
             patch('handlers.battle._handle_death_or_resurrection', new=AsyncMock(return_value=True)) as death_mock, \
             patch('handlers.battle._handle_battle_continues_update', new=AsyncMock()) as continue_mock:
            await battle_handler.handle_battle_buttons(update, context)

        self.assertEqual(death_mock.call_count, 0)
        self.assertEqual(enemy_side_mock.call_count, 1)
        self.assertEqual(continue_mock.call_count, 1)

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

    def test_timeout_fallback_updates_timed_out_participant_only(self):
        battle_state = {
            'side_a_player_ids': [88001, 88002],
            'participant_states': {
                '88001': {'hp': 100, 'mana': 50, 'defeated': False},
                '88002': {'hp': 70, 'mana': 30, 'defeated': False},
            },
            'player_hp': 100,
            'player_mana': 50,
            'player_max_hp': 100,
            'player_max_mana': 50,
            'defense_buff_turns': 0,
            'defense_buff_value': 0,
        }
        action = SimpleNamespace(action_type='fallback_guard', participant_id=88002)

        battle_handler._apply_timeout_fallback_action(action, battle_state, lang='en')

        self.assertEqual(battle_state['participant_states']['88001']['hp'], 100)
        self.assertEqual(battle_state['participant_states']['88002']['hp'], 70)
        self.assertGreaterEqual(battle_state['participant_states']['88002']['mana'], 30)

    def test_enemy_side_targets_deterministic_non_defeated_participant_not_owner(self):
        battle_state = {
            'side_a_player_ids': [88001, 88002],
            'participant_states': {
                '88001': {'hp': 0, 'mana': 0, 'defeated': True, 'player_hp': 0, 'player_mana': 0, 'player_dead': True},
                '88002': {
                    'hp': 70,
                    'mana': 30,
                    'defeated': False,
                    'player_hp': 70,
                    'player_mana': 30,
                    'player_dead': False,
                    'armor_class': 'light',
                    'offhand_profile': 'focus',
                    'encumbrance': 5,
                    'equipment_physical_defense_bonus': 3,
                    'equipment_magic_defense_bonus': 9,
                    'equipment_block_chance_bonus': 1,
                    'effective_agility': 12,
                    'effective_vitality': 9,
                    'effective_wisdom': 21,
                    'effective_luck': 11,
                },
            },
            'player_hp': 0,
            'player_mana': 0,
            'player_max_hp': 100,
            'player_max_mana': 50,
            'armor_class': 'heavy',
            'offhand_profile': 'shield',
            'encumbrance': 30,
            'equipment_physical_defense_bonus': 10,
            'equipment_magic_defense_bonus': 2,
            'equipment_block_chance_bonus': 6,
            'effective_agility': 5,
            'effective_vitality': 14,
            'effective_wisdom': 4,
            'effective_luck': 2,
        }
        owner_player = self._player_row()
        owner_player['telegram_id'] = 88001
        mob = {'id': 'forest_wolf', 'hp': 20}

        with patch('handlers.battle.get_player', side_effect=lambda pid: {
            88002: {
                'telegram_id': 88002,
                'lang': 'en',
                'hp': 70,
                'mana': 30,
                'agility': 10,
                'vitality': 10,
                'wisdom': 10,
                'luck': 10,
            }
        }.get(pid)), \
        patch('handlers.battle.process_enemy_side_turn') as enemy_turn_mock:
            battle_handler._run_group_enemy_side_action(
                owner_player=owner_player,
                mob=mob,
                battle_state=battle_state,
                lang='en',
            )

        call_args, kwargs = enemy_turn_mock.call_args
        player_state = call_args[1]
        self.assertEqual(kwargs['user_id'], 88002)
        self.assertEqual(player_state['armor_class'], 'light')
        self.assertEqual(player_state['offhand_profile'], 'focus')

    def test_mixed_batch_dispatch_uses_each_action_envelope_basic_and_skill(self):
        battle_state = {
            'side_a_player_ids': [88001, 88002],
            'participant_states': {
                '88001': {'hp': 100, 'mana': 50, 'defeated': False},
                '88002': {'hp': 100, 'mana': 50, 'defeated': False},
            },
            'player_hp': 100,
            'player_mana': 50,
            'player_max_hp': 100,
            'player_max_mana': 50,
            'mob_hp': 20,
        }
        owner = self._player_row()
        owner['telegram_id'] = 88001
        mob = {'id': 'forest_wolf', 'hp': 20}

        with patch('handlers.battle.process_turn', return_value=battle_state) as turn_mock, \
             patch('handlers.battle.process_skill_turn', return_value={'battle_state': battle_state}) as skill_mock, \
             patch('handlers.battle.tick_cooldowns'), \
             patch('handlers.battle.add_mastery_exp'):
            battle_handler._dispatch_group_player_action(
                SimpleNamespace(action_type='basic_attack', participant_id=88001),
                owner_player=owner,
                mob=mob,
                battle_state=battle_state,
                lang='en',
            )
            battle_handler._dispatch_group_player_action(
                SimpleNamespace(action_type='skill', participant_id=88002, skill_id='fireball'),
                owner_player=owner,
                mob=mob,
                battle_state=battle_state,
                lang='en',
            )

        self.assertEqual(turn_mock.call_count, 1)
        self.assertEqual(skill_mock.call_count, 1)
        _, skill_kwargs = skill_mock.call_args
        self.assertEqual(skill_kwargs['skill_id'], 'fireball')

    def test_mixed_batch_two_skills_use_their_own_skill_ids(self):
        battle_state = {
            'side_a_player_ids': [88001, 88002],
            'participant_states': {
                '88001': {'hp': 100, 'mana': 50, 'defeated': False},
                '88002': {'hp': 100, 'mana': 50, 'defeated': False},
            },
            'player_hp': 100,
            'player_mana': 50,
            'player_max_hp': 100,
            'player_max_mana': 50,
            'mob_hp': 20,
        }
        owner = self._player_row()
        owner['telegram_id'] = 88001
        mob = {'id': 'forest_wolf', 'hp': 20}

        with patch('handlers.battle.process_skill_turn', return_value={'battle_state': battle_state}) as skill_mock, \
             patch('handlers.battle.tick_cooldowns'), \
             patch('handlers.battle.add_mastery_exp'):
            battle_handler._dispatch_group_player_action(
                SimpleNamespace(action_type='skill', participant_id=88001, skill_id='fireball'),
                owner_player=owner,
                mob=mob,
                battle_state=battle_state,
                lang='en',
            )
            battle_handler._dispatch_group_player_action(
                SimpleNamespace(action_type='skill', participant_id=88002, skill_id='ice_blast'),
                owner_player=owner,
                mob=mob,
                battle_state=battle_state,
                lang='en',
            )

        first_kwargs = skill_mock.call_args_list[0].kwargs
        second_kwargs = skill_mock.call_args_list[1].kwargs
        self.assertEqual(first_kwargs['skill_id'], 'fireball')
        self.assertEqual(second_kwargs['skill_id'], 'ice_blast')

    def test_timeout_dispatch_executes_committed_and_fallback_actions(self):
        battle_state = {
            'side_a_player_ids': [88001, 88002],
            'participant_states': {
                '88001': {'hp': 100, 'mana': 50, 'defeated': False},
                '88002': {'hp': 100, 'mana': 50, 'defeated': False},
            },
            'player_hp': 100,
            'player_mana': 50,
            'player_max_hp': 100,
            'player_max_mana': 50,
            'mob_hp': 20,
            'defense_buff_turns': 0,
            'defense_buff_value': 0,
        }
        owner = self._player_row()
        owner['telegram_id'] = 88001
        mob = {'id': 'forest_wolf', 'hp': 20}

        with patch('handlers.battle.process_turn', return_value=battle_state) as turn_mock, \
             patch('handlers.battle.tick_cooldowns'), \
             patch('handlers.battle.apply_timeout_fallback_guard') as guard_mock:
            battle_handler._dispatch_group_player_action(
                SimpleNamespace(action_type='basic_attack', participant_id=88001),
                owner_player=owner,
                mob=mob,
                battle_state=battle_state,
                lang='en',
            )
            battle_handler._dispatch_group_player_action(
                SimpleNamespace(action_type='fallback_guard', participant_id=88002),
                owner_player=owner,
                mob=mob,
                battle_state=battle_state,
                lang='en',
            )

        self.assertEqual(turn_mock.call_count, 1)
        self.assertEqual(guard_mock.call_count, 1)

    async def test_group_victory_applies_rewards_to_all_surviving_participants(self):
        query = _DummyQuery('battle_attack_forest_wolf')
        context = _DummyContext(
            battle_state={'pve_encounter_id': 'pve-enc-group', 'side_a_player_ids': [88001, 88002], 'participant_states': {
                '88001': {'player_dead': False},
                '88002': {'player_dead': False},
            }, 'weapon_id': 'unarmed'},
            mob={'id': 'forest_wolf', 'hp': 20},
        )
        player = self._player_row()
        mob = {'id': 'forest_wolf', 'hp': 20}
        rewards = {'exp': 10, 'gold': 5, 'loot': [], 'mob_level': 1}

        with patch('handlers.battle.calc_rewards', return_value=rewards), \
             patch('handlers.battle.get_player', side_effect=lambda pid: {
                88001: self._player_row(),
                88002: {**self._player_row(), 'telegram_id': 88002, 'level': 2},
             }.get(pid)), \
             patch('handlers.battle.apply_rewards', return_value={'leveled_up': False, 'new_level': 1, 'new_exp': 0, 'new_gold': 0}) as rewards_mock, \
             patch('handlers.battle.end_battle'), \
             patch('handlers.battle.finish_solo_pve_encounter'), \
             patch('handlers.battle.add_mastery_exp', return_value={'leveled_up': False, 'new_skills': []}):
            await battle_handler._handle_victory_cleanup(
                query=query,
                context=context,
                user_id=88001,
                player=player,
                mob=mob,
                battle_state=context.user_data['battle'],
                lang='en',
            )

        rewarded_ids = [call_args.args[0] for call_args in rewards_mock.call_args_list]
        self.assertIn(88001, rewarded_ids)
        self.assertIn(88002, rewarded_ids)

    async def test_group_owner_death_does_not_finish_encounter_while_ally_alive(self):
        query = _DummyQuery('battle_attack_forest_wolf')
        context = _DummyContext(
            battle_state={'pve_encounter_id': 'pve-enc-group', 'side_a_player_ids': [88001, 88002], 'participant_states': {
                '88001': {'player_dead': True, 'player_hp': 0, 'player_mana': 0},
                '88002': {'player_dead': False, 'player_hp': 40, 'player_mana': 20},
            }, 'player_dead': True, 'player_hp': 0},
            mob={'id': 'forest_wolf', 'hp': 20},
        )

        with patch('handlers.battle.apply_death', return_value={'exp_loss': 1, 'gold_loss': 1}), \
             patch('handlers.battle.end_battle') as end_mock, \
             patch('handlers.battle.mark_group_participant_defeated') as mark_mock, \
             patch('handlers.battle.finish_solo_pve_encounter') as finish_mock, \
             patch('handlers.battle.persist_solo_pve_encounter_state') as persist_mock:
            handled = await battle_handler._handle_death_or_resurrection(
                query=query,
                context=context,
                user_id=88001,
                player=self._player_row(),
                mob={'id': 'forest_wolf', 'hp': 20},
                battle_state=context.user_data['battle'],
                lang='en',
                log=[],
            )

        self.assertTrue(handled)
        self.assertEqual(end_mock.call_count, 1)
        self.assertEqual(mark_mock.call_count, 1)
        self.assertEqual(finish_mock.call_count, 0)
        self.assertEqual(persist_mock.call_count, 1)

    async def test_group_defeat_finishes_encounter_only_when_all_participants_dead(self):
        query = _DummyQuery('battle_attack_forest_wolf')
        context = _DummyContext(
            battle_state={'pve_encounter_id': 'pve-enc-group', 'side_a_player_ids': [88001, 88002], 'participant_states': {
                '88001': {'player_dead': True, 'player_hp': 0, 'player_mana': 0},
                '88002': {'player_dead': True, 'player_hp': 0, 'player_mana': 0},
            }, 'player_dead': True, 'player_hp': 0},
            mob={'id': 'forest_wolf', 'hp': 20},
        )

        with patch('handlers.battle.apply_death', return_value={'exp_loss': 1, 'gold_loss': 1}), \
             patch('handlers.battle.end_battle'), \
             patch('handlers.battle.finish_solo_pve_encounter') as finish_mock:
            handled = await battle_handler._handle_death_or_resurrection(
                query=query,
                context=context,
                user_id=88001,
                player=self._player_row(),
                mob={'id': 'forest_wolf', 'hp': 20},
                battle_state=context.user_data['battle'],
                lang='en',
                log=[],
            )

        self.assertTrue(handled)
        self.assertEqual(finish_mock.call_count, 1)

    async def test_group_owner_death_penalty_is_not_applied_twice_when_cached(self):
        query = _DummyQuery('battle_attack_forest_wolf')
        context = _DummyContext(
            battle_state={
                'pve_encounter_id': 'pve-enc-group',
                'side_a_player_ids': [88001, 88002],
                'participant_states': {
                    '88001': {'player_dead': True, 'player_hp': 0, 'player_mana': 0},
                    '88002': {'player_dead': False, 'player_hp': 40, 'player_mana': 20},
                },
                'group_death_penalties': {'88001': {'exp_loss': 2, 'gold_loss': 1}},
                'player_dead': True,
                'player_hp': 0,
            },
            mob={'id': 'forest_wolf', 'hp': 20},
        )

        with patch('handlers.battle.apply_death') as death_mock, \
             patch('handlers.battle.end_battle'), \
             patch('handlers.battle.mark_group_participant_defeated'), \
             patch('handlers.battle.persist_solo_pve_encounter_state'):
            handled = await battle_handler._handle_death_or_resurrection(
                query=query,
                context=context,
                user_id=88001,
                player=self._player_row(),
                mob={'id': 'forest_wolf', 'hp': 20},
                battle_state=context.user_data['battle'],
                lang='en',
                log=[],
            )

        self.assertTrue(handled)
        death_mock.assert_not_called()

    def test_group_continue_persists_hp_mana_for_all_participants(self):
        battle_state = {
            'side_a_player_ids': [88001, 88002],
            'participant_states': {
                '88001': {'player_hp': 75, 'player_mana': 30},
                '88002': {'player_hp': 44, 'player_mana': 12},
            },
        }

        class _Conn:
            def __init__(self):
                self.calls = []
            def execute(self, sql, params):
                self.calls.append((sql, params))
            def commit(self):
                pass
            def close(self):
                pass

        conn = _Conn()
        with patch('handlers.battle.get_connection', return_value=conn):
            battle_handler._persist_group_participant_hp_mana(battle_state)

        updated_ids = [params[2] for _sql, params in conn.calls]
        self.assertIn(88001, updated_ids)
        self.assertIn(88002, updated_ids)

    async def test_non_owner_ally_death_is_reconciled_after_enemy_side(self):
        update = _DummyUpdate('battle_attack_forest_wolf', user_id=88002)
        battle_state = {
            'pve_encounter_id': 'pve-enc-group',
            'side_a_player_ids': [88001, 88002],
            'participant_states': {
                '88001': {'player_hp': 100, 'player_mana': 50, 'player_dead': False, 'hp': 100, 'mana': 50, 'defeated': False},
                '88002': {'player_hp': 100, 'player_mana': 50, 'player_dead': False, 'hp': 100, 'mana': 50, 'defeated': False},
            },
            'mob_hp': 20,
            'player_hp': 100,
            'player_mana': 50,
            'player_max_hp': 100,
            'player_max_mana': 50,
            'mob_dead': False,
            'player_dead': False,
            'log': [],
            'turn': 1,
            'weapon_id': 'unarmed',
        }
        mob = {'id': 'forest_wolf', 'hp': 20}
        context = _DummyContext(battle_state, mob)

        def resolve_side_effect(**kwargs):
            kwargs['on_player_action'](SimpleNamespace(action_type='basic_attack', participant_id=88002))
            return True

        def enemy_side_effect(**kwargs):
            # Enemy targets first alive participant (88001) and kills them.
            battle_state['participant_states']['88001'].update({
                'player_hp': 0, 'hp': 0, 'player_dead': True, 'defeated': True,
            })
            kwargs['on_enemy_action'](SimpleNamespace(action_type='enemy_basic_attack'))

        with patch('handlers.battle.get_player', side_effect=lambda pid: {
            88001: {**self._player_row(), 'telegram_id': 88001},
            88002: {**self._player_row(), 'telegram_id': 88002},
        }.get(pid, self._player_row())), \
             patch('handlers.battle.ensure_runtime_for_battle'), \
             patch('handlers.battle.process_due_timeout_for_battle', return_value=False), \
             patch('handlers.battle.submit_player_commit', return_value=(True, 'committed')), \
             patch('handlers.battle.resolve_current_side_if_ready', side_effect=resolve_side_effect), \
             patch('handlers.battle.process_turn', return_value=battle_state), \
             patch('handlers.battle.tick_cooldowns'), \
             patch('handlers.battle.process_enemy_side_turn'), \
             patch('handlers.battle.get_pve_encounter_player_ids', return_value=[88001, 88002]), \
             patch('handlers.battle.run_enemy_instant_side', side_effect=enemy_side_effect), \
             patch('handlers.battle.mark_group_participant_defeated') as mark_mock, \
             patch('handlers.battle._resolve_post_attack_combat_resolution', new=AsyncMock(return_value=False)):
            await battle_handler.handle_battle_buttons(update, context)

        marked_ids = [call.kwargs.get('participant_id') for call in mark_mock.call_args_list]
        self.assertIn(88001, marked_ids)

    async def test_non_owner_ally_death_is_reconciled_after_player_side_when_mob_dies(self):
        update = _DummyUpdate('battle_attack_forest_wolf', user_id=88002)
        battle_state = {
            'pve_encounter_id': 'pve-enc-group',
            'side_a_player_ids': [88001, 88002],
            'participant_states': {
                '88001': {'player_hp': 100, 'player_mana': 50, 'player_dead': False, 'hp': 100, 'mana': 50, 'defeated': False},
                '88002': {'player_hp': 100, 'player_mana': 50, 'player_dead': False, 'hp': 100, 'mana': 50, 'defeated': False},
            },
            'mob_hp': 20,
            'player_hp': 100,
            'player_mana': 50,
            'player_max_hp': 100,
            'player_max_mana': 50,
            'mob_dead': False,
            'player_dead': False,
            'log': [],
            'turn': 1,
            'weapon_id': 'unarmed',
        }
        mob = {'id': 'forest_wolf', 'hp': 20}
        context = _DummyContext(battle_state, mob)

        def resolve_side_effect(**kwargs):
            battle_state['participant_states']['88001'].update({'player_hp': 0, 'hp': 0, 'player_dead': True, 'defeated': True})
            battle_state['mob_dead'] = True
            kwargs['on_player_action'](SimpleNamespace(action_type='basic_attack', participant_id=88002))
            return True

        with patch('handlers.battle.get_player', side_effect=lambda pid: {
            88001: {**self._player_row(), 'telegram_id': 88001},
            88002: {**self._player_row(), 'telegram_id': 88002},
        }.get(pid, self._player_row())), \
             patch('handlers.battle.ensure_runtime_for_battle'), \
             patch('handlers.battle.process_due_timeout_for_battle', return_value=False), \
             patch('handlers.battle.submit_player_commit', return_value=(True, 'committed')), \
             patch('handlers.battle.resolve_current_side_if_ready', side_effect=resolve_side_effect), \
             patch('handlers.battle.process_turn', return_value=battle_state), \
             patch('handlers.battle.get_pve_encounter_player_ids', return_value=[88001, 88002]), \
             patch('handlers.battle.mark_group_participant_defeated') as mark_mock, \
             patch('handlers.battle.run_enemy_instant_side') as enemy_side_mock, \
             patch('handlers.battle._handle_victory_cleanup', new=AsyncMock()), \
             patch('handlers.battle._resolve_post_attack_combat_resolution', new=AsyncMock(return_value=True)):
            await battle_handler.handle_battle_buttons(update, context)

        marked_ids = [call.kwargs.get('participant_id') for call in mark_mock.call_args_list]
        self.assertIn(88001, marked_ids)
        enemy_side_mock.assert_not_called()

    async def test_non_owner_ally_death_is_reconciled_after_player_side_when_battle_continues(self):
        update = _DummyUpdate('battle_attack_forest_wolf', user_id=88002)
        battle_state = {
            'pve_encounter_id': 'pve-enc-group',
            'side_a_player_ids': [88001, 88002],
            'participant_states': {
                '88001': {'player_hp': 100, 'player_mana': 50, 'player_dead': False, 'hp': 100, 'mana': 50, 'defeated': False},
                '88002': {'player_hp': 100, 'player_mana': 50, 'player_dead': False, 'hp': 100, 'mana': 50, 'defeated': False},
            },
            'mob_hp': 20,
            'player_hp': 100,
            'player_mana': 50,
            'player_max_hp': 100,
            'player_max_mana': 50,
            'mob_dead': False,
            'player_dead': False,
            'log': [],
            'turn': 1,
            'weapon_id': 'unarmed',
        }
        mob = {'id': 'forest_wolf', 'hp': 20}
        context = _DummyContext(battle_state, mob)

        def resolve_side_effect(**kwargs):
            battle_state['participant_states']['88001'].update({'player_hp': 0, 'hp': 0, 'player_dead': True, 'defeated': True})
            kwargs['on_player_action'](SimpleNamespace(action_type='basic_attack', participant_id=88002))
            return True

        with patch('handlers.battle.get_player', side_effect=lambda pid: {
            88001: {**self._player_row(), 'telegram_id': 88001},
            88002: {**self._player_row(), 'telegram_id': 88002},
        }.get(pid, self._player_row())), \
             patch('handlers.battle.ensure_runtime_for_battle'), \
             patch('handlers.battle.process_due_timeout_for_battle', return_value=False), \
             patch('handlers.battle.submit_player_commit', return_value=(True, 'committed')), \
             patch('handlers.battle.resolve_current_side_if_ready', side_effect=resolve_side_effect), \
             patch('handlers.battle.process_turn', return_value=battle_state), \
             patch('handlers.battle.get_pve_encounter_player_ids', return_value=[88001, 88002]), \
             patch('handlers.battle.mark_group_participant_defeated') as mark_mock, \
             patch('handlers.battle.run_enemy_instant_side') as enemy_side_mock, \
             patch('handlers.battle._resolve_post_attack_combat_resolution', new=AsyncMock(return_value=False)):
            await battle_handler.handle_battle_buttons(update, context)

        marked_ids = [call.kwargs.get('participant_id') for call in mark_mock.call_args_list]
        self.assertIn(88001, marked_ids)
        enemy_side_mock.assert_called_once()

    async def test_timeout_group_batch_reconciles_dead_ally_before_terminal_resolution(self):
        update = _DummyUpdate('battle_attack_forest_wolf', user_id=88002)
        battle_state = {
            'pve_encounter_id': 'pve-enc-group',
            'side_a_player_ids': [88001, 88002],
            'participant_states': {
                '88001': {'player_hp': 100, 'player_mana': 50, 'player_dead': False, 'hp': 100, 'mana': 50, 'defeated': False},
                '88002': {'player_hp': 100, 'player_mana': 50, 'player_dead': False, 'hp': 100, 'mana': 50, 'defeated': False},
            },
            'mob_hp': 20,
            'player_hp': 100,
            'player_mana': 50,
            'player_max_hp': 100,
            'player_max_mana': 50,
            'mob_dead': False,
            'player_dead': False,
            'log': [],
            'turn': 1,
            'weapon_id': 'unarmed',
        }
        mob = {'id': 'forest_wolf', 'hp': 20}
        context = _DummyContext(battle_state, mob)

        def _timeout_side_effect(**_kwargs):
            battle_state['participant_states']['88001'].update({'player_hp': 0, 'hp': 0, 'player_dead': True, 'defeated': True})
            battle_state['mob_dead'] = True
            return True

        async def _post_resolve_side_effect(**_kwargs):
            marked_ids = [call.kwargs.get('participant_id') for call in mark_mock.call_args_list]
            self.assertIn(88001, marked_ids)
            return True

        with patch('handlers.battle.get_player', side_effect=lambda pid: {
            88001: {**self._player_row(), 'telegram_id': 88001},
            88002: {**self._player_row(), 'telegram_id': 88002},
        }.get(pid, self._player_row())), \
             patch('handlers.battle.ensure_runtime_for_battle'), \
             patch('handlers.battle.process_due_timeout_for_battle', side_effect=_timeout_side_effect), \
             patch('handlers.battle.get_pve_encounter_player_ids', return_value=[88001, 88002]), \
             patch('handlers.battle.mark_group_participant_defeated') as mark_mock, \
             patch('handlers.battle._resolve_post_attack_combat_resolution', new=AsyncMock(side_effect=_post_resolve_side_effect)):
            await battle_handler.handle_battle_buttons(update, context)

    def test_group_death_consequences_process_non_owner_resurrection(self):
        battle_state = {
            'pve_encounter_id': 'pve-enc-group',
            'side_a_player_ids': [88001, 88002],
            'participant_states': {
                '88001': {'player_hp': 0, 'hp': 0, 'player_dead': True, 'defeated': True, 'resurrection_active': True, 'resurrection_hp': 30, 'player_max_hp': 100},
                '88002': {'player_hp': 100, 'hp': 100, 'player_dead': False, 'defeated': False},
            },
            'log': [],
            'mob_dead': False,
        }
        with patch('handlers.battle.apply_death') as death_mock:
            battle_handler._process_group_participant_death_consequences(
                battle_state=battle_state,
                owner_player_id=88002,
                log=battle_state['log'],
                lang='en',
            )
        death_mock.assert_not_called()
        revived = battle_state['participant_states']['88001']
        self.assertFalse(revived.get('player_dead'))
        self.assertGreater(revived.get('player_hp', 0), 0)

    def test_group_death_consequences_process_non_owner_death_penalty(self):
        battle_state = {
            'pve_encounter_id': 'pve-enc-group',
            'side_a_player_ids': [88001, 88002],
            'participant_states': {
                '88001': {'player_hp': 0, 'hp': 0, 'player_dead': True, 'defeated': True},
                '88002': {'player_hp': 100, 'hp': 100, 'player_dead': False, 'defeated': False},
            },
            'log': [],
            'mob_dead': False,
        }
        with patch('handlers.battle.get_player', return_value={**self._player_row(), 'telegram_id': 88001}), \
             patch('handlers.battle.apply_death', return_value={'exp_loss': 5, 'gold_loss': 2}) as death_mock, \
             patch('handlers.battle.mark_group_participant_defeated'):
            battle_handler._process_group_participant_death_consequences(
                battle_state=battle_state,
                owner_player_id=88002,
                log=battle_state['log'],
                lang='en',
            )
        self.assertTrue(death_mock.called)
        dead_map = battle_state.get('group_death_penalties', {})
        self.assertIn('88001', dead_map)

    async def test_group_victory_rewards_only_surviving_participants(self):
        battle_state = {
            'pve_encounter_id': 'pve-enc-group',
            'side_a_player_ids': [88001, 88002],
            'participant_states': {
                '88001': {'player_hp': 0, 'hp': 0, 'player_dead': True, 'defeated': True},
                '88002': {'player_hp': 70, 'hp': 70, 'player_dead': False, 'defeated': False},
            },
            'group_death_penalties': {'88001': {'exp_loss': 10, 'gold_loss': 3}},
            'weapon_id': 'unarmed',
        }
        player = {**self._player_row(), 'telegram_id': 88001}
        mob = {'id': 'forest_wolf', 'hp': 20}
        query = _DummyQuery('battle_attack_forest_wolf')
        context = _DummyContext(battle_state, mob)

        rewarded_ids = []
        safe_edit_mock = AsyncMock()
        with patch('handlers.battle.get_pve_encounter_player_ids', return_value=[88002]), \
             patch('handlers.battle.calc_rewards', return_value={'exp': 10, 'gold': 5, 'loot': []}), \
             patch('handlers.battle.get_player', side_effect=lambda pid: {**self._player_row(), 'telegram_id': pid}), \
             patch('handlers.battle.apply_rewards', side_effect=lambda pid, _p, _r: rewarded_ids.append(pid) or {'leveled_up': False, 'new_level': 1, 'new_exp': 0, 'new_gold': 0}), \
             patch('handlers.battle.finish_solo_pve_encounter'), \
             patch('handlers.battle.safe_edit', new=safe_edit_mock), \
             patch('handlers.battle.add_mastery_exp', return_value=None), \
             patch('handlers.battle._build_mastery_text', return_value=''):
            await battle_handler._handle_victory_cleanup(
                query=query,
                context=context,
                user_id=88001,
                player=player,
                mob=mob,
                battle_state=battle_state,
                lang='en',
            )

        self.assertEqual(rewarded_ids, [88002])
        args = safe_edit_mock.await_args.args
        rendered_text = safe_edit_mock.await_args.kwargs.get('text', args[1] if len(args) > 1 else '')
        self.assertIn('You died', rendered_text)


if __name__ == '__main__':
    unittest.main()
