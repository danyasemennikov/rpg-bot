import unittest
from unittest.mock import AsyncMock, patch

from handlers.location import build_location_message, handle_location_buttons, location_command, pvp_command
from handlers.profile import unstuck_command


class _FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id


class _FakeMessage:
    def __init__(self):
        self.reply_text = AsyncMock()


class _FakeUpdate:
    def __init__(self, user_id: int):
        self.effective_user = _FakeUser(user_id)
        self.message = _FakeMessage()


class _FakeCallbackQuery:
    def __init__(self, user_id: int, data: str):
        self.from_user = _FakeUser(user_id)
        self.data = data
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()
        self.message = type('Msg', (), {'message_id': 777})()


class _FakeCallbackUpdate:
    def __init__(self, user_id: int, data: str):
        self.callback_query = _FakeCallbackQuery(user_id, data)


class LivePvpLocationCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_location_command_allows_live_pvp_view_when_in_battle(self):
        update = _FakeUpdate(12345)
        player = {
            'telegram_id': 12345,
            'lang': 'en',
            'in_battle': 1,
            'location_id': 'dark_forest',
        }
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': []}
        with (
            patch('handlers.location.get_player', return_value=player),
            patch('handlers.location.is_player_busy_with_live_pvp', return_value=True),
            patch('handlers.location.is_in_battle', return_value=True),
            patch('handlers.location.get_location', return_value=location),
            patch('handlers.location.build_location_message', return_value=('live-pvp', None)),
        ):
            await location_command(update, context=None)

        update.message.reply_text.assert_awaited_once_with('live-pvp', reply_markup=None, parse_mode='HTML')

    async def test_location_command_keeps_non_pvp_battle_block(self):
        update = _FakeUpdate(12345)
        player = {
            'telegram_id': 12345,
            'lang': 'en',
            'in_battle': 1,
            'location_id': 'dark_forest',
        }
        with (
            patch('handlers.location.get_player', return_value=player),
            patch('handlers.location.is_player_busy_with_live_pvp', return_value=False),
            patch('handlers.location.t', side_effect=lambda key, _lang, **kwargs: key),
        ):
            await location_command(update, context=None)

        update.message.reply_text.assert_awaited_once_with('location.in_battle_block')

    async def test_pending_engagement_blocks_location_move(self):
        update = _FakeCallbackUpdate(1001, 'goto_village')
        player = {'telegram_id': 1001, 'lang': 'en', 'in_battle': 0, 'location_id': 'dark_forest', 'level': 10}
        with (
            patch('handlers.location.get_player', return_value=player),
            patch('handlers.location.has_active_live_pvp_engagement', return_value=True),
            patch('handlers.location.t', side_effect=lambda key, _lang, **kwargs: key),
        ):
            await handle_location_buttons(update, context=None)
        update.callback_query.answer.assert_awaited_once_with('location.pvp_context_block', show_alert=True)

    async def test_converted_battle_blocks_location_move(self):
        update = _FakeCallbackUpdate(1001, 'goto_village')
        player = {'telegram_id': 1001, 'lang': 'en', 'in_battle': 1, 'location_id': 'dark_forest', 'level': 10}
        with (
            patch('handlers.location.get_player', return_value=player),
            patch('handlers.location.has_active_live_pvp_engagement', return_value=True),
            patch('handlers.location.t', side_effect=lambda key, _lang, **kwargs: key),
        ):
            await handle_location_buttons(update, context=None)
        update.callback_query.answer.assert_awaited_once_with('location.pvp_context_block', show_alert=True)

    async def test_normal_player_can_still_move(self):
        update = _FakeCallbackUpdate(1001, 'goto_village')
        player = {'telegram_id': 1001, 'lang': 'en', 'in_battle': 0, 'location_id': 'dark_forest', 'level': 10}
        target_location = {'id': 'village', 'safe': True, 'level_min': 1, 'level_max': 10, 'mobs': [], 'services': []}
        context = type('Ctx', (), {'application': type('A', (), {'create_task': lambda *args, **kwargs: None})()})()
        with (
            patch('handlers.location.get_player', return_value=player),
            patch('handlers.location.has_active_live_pvp_engagement', return_value=False),
            patch('handlers.location.is_in_battle', return_value=False),
            patch('handlers.location.get_location', return_value=target_location),
            patch('handlers.location.get_location_name', return_value='Village'),
            patch('handlers.location.get_location_desc', return_value='road'),
            patch('handlers.location.asyncio.sleep', new=AsyncMock()),
            patch('handlers.location.get_connection') as connection_mock,
            patch('handlers.location.build_location_message', return_value=('ok', None)),
            patch('handlers.location.t', side_effect=lambda key, _lang, **kwargs: key),
        ):
            connection_mock.return_value.execute.return_value = None
            connection_mock.return_value.commit.return_value = None
            connection_mock.return_value.close.return_value = None
            await handle_location_buttons(update, context=context)
        self.assertGreaterEqual(update.callback_query.edit_message_text.await_count, 2)

    def test_pvp_only_view_hides_nearby_attack_buttons(self):
        player = {
            'telegram_id': 1001,
            'lang': 'en',
            'level': 10,
            'hp': 80,
            'max_hp': 100,
            'mana': 40,
            'max_mana': 60,
            'gold': 20,
        }
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': []}
        nearby = [{'telegram_id': 2002, 'name': 'Enemy', 'level': 11}]
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = nearby
            conn_mock.return_value.close.return_value = None
            text, keyboard = build_location_message(player, location, pvp_only_view=True)
        self.assertNotIn('Nearby players', text)
        self.assertEqual(list(keyboard.inline_keyboard), [])

    def test_live_pvp_view_uses_battle_runtime_hp_mana(self):
        player = {
            'telegram_id': 1001,
            'lang': 'en',
            'level': 10,
            'hp': 1,
            'max_hp': 1,
            'mana': 1,
            'max_mana': 1,
            'gold': 20,
        }
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': []}
        engagement = {'id': 9, 'attacker_id': 1001, 'defender_id': 2002}
        payload = {'battle': {'attacker_hp': 77, 'attacker_max_hp': 120, 'attacker_mana': 33, 'attacker_max_mana': 90, 'defender_hp': 22, 'turn_owner': 1001}}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=engagement),
            patch('handlers.location.advance_engagement_to_live_battle_if_ready', return_value=('converted_to_battle', payload)),
            patch('handlers.location.get_manual_pvp_action_labels', return_value=[]),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            text, _ = build_location_message(player, location, pvp_only_view=True)
        self.assertIn('❤️ 77/120', text)
        self.assertIn('🔵 33/90', text)

    def test_live_pvp_view_uses_battle_runtime_hp_mana_for_defender(self):
        player = {
            'telegram_id': 2002,
            'lang': 'en',
            'level': 10,
            'hp': 1,
            'max_hp': 1,
            'mana': 1,
            'max_mana': 1,
            'gold': 20,
        }
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': []}
        engagement = {'id': 9, 'attacker_id': 1001, 'defender_id': 2002}
        payload = {'battle': {'defender_hp': 66, 'defender_max_hp': 111, 'defender_mana': 25, 'defender_max_mana': 70, 'attacker_hp': 88, 'turn_owner': 1001}}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=engagement),
            patch('handlers.location.advance_engagement_to_live_battle_if_ready', return_value=('converted_to_battle', payload)),
            patch('handlers.location.get_manual_pvp_action_labels', return_value=[]),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            text, _ = build_location_message(player, location, pvp_only_view=True)
        self.assertIn('❤️ 66/111', text)
        self.assertIn('🔵 25/70', text)

    def test_converted_live_battle_shows_controls_only_for_active_core_player(self):
        player = {
            'telegram_id': 2002,
            'lang': 'en',
            'level': 10,
            'hp': 1,
            'max_hp': 1,
            'mana': 1,
            'max_mana': 1,
            'gold': 20,
        }
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': []}
        engagement = {'id': 9, 'attacker_id': 1001, 'defender_id': 2002}
        payload = {'battle': {'defender_hp': 66, 'defender_max_hp': 111, 'defender_mana': 25, 'defender_max_mana': 70, 'attacker_hp': 88, 'turn_owner': 1001}}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=engagement),
            patch('handlers.location.advance_engagement_to_live_battle_if_ready', return_value=('converted_to_battle', payload)),
            patch('handlers.location.get_manual_pvp_action_labels', return_value=[('normal_attack', '⚔️ Strike')]) as labels_mock,
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            text, keyboard = build_location_message(player, location, pvp_only_view=True)
        self.assertIn('turn: enemy', text)
        self.assertEqual(list(keyboard.inline_keyboard), [])
        labels_mock.assert_not_called()

    def test_converted_live_battle_hides_combat_ui_for_reinforcement_only_viewer(self):
        player = {
            'telegram_id': 3003,
            'lang': 'en',
            'level': 10,
            'hp': 80,
            'max_hp': 100,
            'mana': 40,
            'max_mana': 60,
            'gold': 20,
        }
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': []}
        engagement = {'id': 9, 'attacker_id': 1001, 'defender_id': 2002}
        payload = {'battle': {'attacker_hp': 77, 'attacker_max_hp': 120, 'attacker_mana': 33, 'attacker_max_mana': 90, 'defender_hp': 22, 'turn_owner': 1001}}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=engagement),
            patch('handlers.location.advance_engagement_to_live_battle_if_ready', return_value=('converted_to_battle', payload)),
            patch('handlers.location.get_manual_pvp_action_labels', return_value=[('normal_attack', '⚔️ Strike')]) as action_mock,
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            text, keyboard = build_location_message(player, location, pvp_only_view=True)
        self.assertIn('prep commitment is now released', text)
        self.assertNotIn('PvP battle', text)
        self.assertIn('❤️ 80/100', text)
        self.assertIn('🔵 40/60', text)
        callback_ids = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
        self.assertNotIn('pvp_act_9_normal_attack', callback_ids)
        action_mock.assert_not_called()

    def test_location_view_shows_pending_pvp_encounters_section(self):
        player = {
            'telegram_id': 1001,
            'lang': 'en',
            'level': 10,
            'hp': 80,
            'max_hp': 100,
            'mana': 40,
            'max_mana': 60,
            'gold': 20,
        }
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': []}
        encounters = [{
            'id': 12,
            'attacker_name': 'A',
            'defender_name': 'D',
            'seconds_until_start': 55,
            'initiator_side_count': 3,
            'defender_side_count': 2,
        }]
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=encounters),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            text, keyboard = build_location_message(player, location, pvp_only_view=False)
        self.assertIn('Active prep PvP encounters', text)
        callback_ids = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
        self.assertIn('pvp_view_12', callback_ids)

    def test_invited_ally_sees_reinforcement_accept_decline_controls_in_location(self):
        player = {
            'telegram_id': 3003,
            'lang': 'en',
            'level': 10,
            'hp': 80,
            'max_hp': 100,
            'mana': 40,
            'max_mana': 60,
            'gold': 20,
        }
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': []}
        engagement = {'id': 9, 'attacker_id': 1001, 'defender_id': 2002, 'engagement_state': 'pending'}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=engagement),
            patch('handlers.location.advance_engagement_to_live_battle_if_ready', return_value=('pending', {})),
            patch('handlers.location.get_engagement_reinforcement_state', return_value={'initiator': {}, 'defender': {}}),
            patch('handlers.location.get_pending_reinforcement_invite_for_player', return_value={'id': 11, 'ally_id': 3003, 'status': 'pending'}),
            patch('handlers.location.is_player_joined_pending_encounter', return_value=False),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            _text, keyboard = build_location_message(player, location, pvp_only_view=False)
        callback_ids = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
        self.assertIn('pvp_reinf_accept_9', callback_ids)
        self.assertIn('pvp_reinf_decline_9', callback_ids)

    def test_accepted_ally_sees_consistent_prep_commitment_notice(self):
        player = {
            'telegram_id': 3003,
            'lang': 'en',
            'level': 10,
            'hp': 80,
            'max_hp': 100,
            'mana': 40,
            'max_mana': 60,
            'gold': 20,
        }
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': []}
        engagement = {'id': 9, 'attacker_id': 1001, 'defender_id': 2002, 'engagement_state': 'pending'}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=engagement),
            patch('handlers.location.advance_engagement_to_live_battle_if_ready', return_value=('pending', {})),
            patch('handlers.location.get_engagement_reinforcement_state', return_value={
                'initiator': {'ally_id': 3003, 'ally_name': 'Ally', 'status': 'accepted'},
                'defender': {},
            }),
            patch('handlers.location.get_pending_reinforcement_invite_for_player', return_value=None),
            patch('handlers.location.is_player_joined_pending_encounter', return_value=True),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            text, keyboard = build_location_message(player, location, pvp_only_view=False)
        self.assertIn('committed as reinforcement', text)
        callback_ids = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
        self.assertNotIn('pvp_reinf_accept_9', callback_ids)
        self.assertNotIn('pvp_reinf_decline_9', callback_ids)

    async def test_invited_ally_accept_path_works_from_location_callback(self):
        update = _FakeCallbackUpdate(3003, 'pvp_reinf_accept_9')
        player = {'telegram_id': 3003, 'lang': 'en', 'in_battle': 0, 'location_id': 'dark_forest', 'level': 10}
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': []}
        with (
            patch('handlers.location.get_player', return_value=player),
            patch('handlers.location.has_active_live_pvp_engagement', return_value=False),
            patch('handlers.location.respond_to_reinforcement_invite', return_value=(True, None)) as respond_mock,
            patch('handlers.location.get_location', return_value=location),
            patch('handlers.location.build_location_message', return_value=('ok', None)),
            patch('handlers.location.t', side_effect=lambda key, _lang, **kwargs: key),
        ):
            await handle_location_buttons(update, context=None)
        respond_mock.assert_called_once_with(engagement_id=9, ally_id=3003, accepted=True)
        update.callback_query.answer.assert_awaited_once_with('location.pvp_reinforcement_accept_done', show_alert=True)

    async def test_invited_ally_decline_path_works_from_location_callback(self):
        update = _FakeCallbackUpdate(3003, 'pvp_reinf_decline_9')
        player = {'telegram_id': 3003, 'lang': 'en', 'in_battle': 0, 'location_id': 'dark_forest', 'level': 10}
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': []}
        with (
            patch('handlers.location.get_player', return_value=player),
            patch('handlers.location.has_active_live_pvp_engagement', return_value=False),
            patch('handlers.location.respond_to_reinforcement_invite', return_value=(True, None)) as respond_mock,
            patch('handlers.location.get_location', return_value=location),
            patch('handlers.location.build_location_message', return_value=('ok', None)),
            patch('handlers.location.t', side_effect=lambda key, _lang, **kwargs: key),
        ):
            await handle_location_buttons(update, context=None)
        respond_mock.assert_called_once_with(engagement_id=9, ally_id=3003, accepted=False)
        update.callback_query.answer.assert_awaited_once_with('location.pvp_reinforcement_decline_done', show_alert=True)

    async def test_pvp_command_lists_pending_location_encounters(self):
        update = _FakeUpdate(1001)
        player = {'telegram_id': 1001, 'lang': 'en', 'location_id': 'dark_forest'}
        location = {'id': 'dark_forest', 'safe': False}
        encounters = [{
            'id': 21,
            'attacker_name': 'A',
            'defender_name': 'D',
            'seconds_until_start': 30,
            'initiator_side_count': 2,
            'defender_side_count': 4,
        }]
        with (
            patch('handlers.location.get_player', return_value=player),
            patch('handlers.location.get_location', return_value=location),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_pending_location_encounters', return_value=encounters),
        ):
            await pvp_command(update, context=None)
        update.message.reply_text.assert_awaited()
        args, kwargs = update.message.reply_text.await_args
        self.assertIn('Pending PvP encounters', args[0])
        keyboard = kwargs['reply_markup']
        callback_ids = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
        self.assertIn('pvp_view_21', callback_ids)

    async def test_pvp_view_callback_shows_detail_with_join_buttons(self):
        update = _FakeCallbackUpdate(1001, 'pvp_view_21')
        player = {'telegram_id': 1001, 'lang': 'en', 'in_battle': 0, 'location_id': 'dark_forest'}
        detail = {
            'id': 21,
            'engagement_state': 'pending',
            'location_id': 'dark_forest',
            'seconds_until_start': 40,
            'attacker_name': 'A',
            'defender_name': 'D',
            'attacker_id': 10,
            'defender_id': 11,
            'initiator_names': ['A'],
            'defender_names': ['D'],
        }
        with (
            patch('handlers.location.get_player', return_value=player),
            patch('handlers.location.has_active_live_pvp_engagement', return_value=False),
            patch('handlers.location.get_pending_encounter_detail', return_value=detail),
            patch('handlers.location.can_join_pending_encounter_side', side_effect=[(True, None), (True, None)]),
            patch('handlers.location.get_location_name', return_value='Forest'),
        ):
            await handle_location_buttons(update, context=None)
        update.callback_query.edit_message_text.assert_awaited()
        _args, kwargs = update.callback_query.edit_message_text.await_args
        keyboard = kwargs['reply_markup']
        callback_ids = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
        self.assertIn('pvp_join_21_initiator', callback_ids)
        self.assertIn('pvp_join_21_defender', callback_ids)

    async def test_unstuck_is_blocked_during_active_pvp(self):
        update = _FakeUpdate(12345)
        with (
            patch('handlers.profile.get_player_lang', return_value='en'),
            patch('handlers.profile.is_pvp_mobility_blocked', return_value=True),
            patch('handlers.profile.t', side_effect=lambda key, _lang, **kwargs: key),
        ):
            await unstuck_command(update, context=type('Ctx', (), {'user_data': {}})())
        update.message.reply_text.assert_awaited_once_with('location.pvp_mobility_block')
