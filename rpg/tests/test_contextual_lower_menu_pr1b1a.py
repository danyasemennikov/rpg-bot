import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from game.contextual_keyboard import (
    LOWER_TRAVEL_PREFIX,
    build_contextual_main_keyboard,
    build_lower_travel_label,
)
from handlers.location import (
    build_location_message,
    handle_location_buttons,
    handle_lower_menu_travel_text,
    location_command,
)


def _keyboard_text_rows(keyboard):
    return [[button.text for button in row] for row in keyboard.keyboard]


class ContextualLowerMenuTests(unittest.TestCase):
    def test_contextual_lower_menu_renders_neighbor_travel_above_baseline(self):
        keyboard = build_contextual_main_keyboard({'location_id': 'capital_city'}, 'en')
        rows = _keyboard_text_rows(keyboard)

        self.assertTrue(rows[0][0].startswith(LOWER_TRAVEL_PREFIX))
        self.assertIn(build_lower_travel_label('westwild_n1', 'en'), [row[0] for row in rows if len(row) == 1])
        self.assertGreater(rows.index(['📍 Location', '🗺️ Map']), 0)

    def test_contextual_lower_menu_filters_invalid_neighbors(self):
        with patch('game.contextual_keyboard.get_location_neighbors', return_value=['westwild_n1', 'missing_place']):
            keyboard = build_contextual_main_keyboard({'location_id': 'capital_city'}, 'en')

        flat = [text for row in _keyboard_text_rows(keyboard) for text in row]
        self.assertIn(build_lower_travel_label('westwild_n1', 'en'), flat)
        self.assertFalse(any('missing_place' in text for text in flat))

    def test_baseline_system_buttons_and_dedicated_map_label_remain_present(self):
        keyboard = build_contextual_main_keyboard({'location_id': 'capital_city'}, 'en')
        flat = [text for row in _keyboard_text_rows(keyboard) for text in row]

        for label in ['📍 Location', '🗺️ Map', '🎒 Inventory', '👤 Profile', '🔮 Skills', '📊 Stats', '⚙️ Settings', '❓ Help']:
            self.assertIn(label, flat)


class LocationInlineRenderingTests(unittest.TestCase):
    def _build_location(self, *, gather_profiles=None, services=None):
        player = {
            'telegram_id': 5001,
            'lang': 'en',
            'level': 10,
            'hp': 120,
            'max_hp': 120,
            'mana': 50,
            'max_mana': 50,
            'gold': 0,
        }
        location = {
            'id': 'capital_city',
            'safe': True,
            'level_min': 1,
            'level_max': 30,
            'mobs': [],
            'services': services or [],
        }
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_location_name', side_effect=lambda location_id, _lang: location_id),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[]),
            patch('handlers.location.list_location_available_spawn_instances', return_value=[]),
            patch('handlers.location.list_location_active_pve_encounters', return_value=[]),
            patch('handlers.location.build_location_gather_source_profiles', return_value=gather_profiles or []),
            patch('handlers.location.get_item_name', return_value='Herb'),
            patch('handlers.location.build_hunt_contract_progress_line', return_value=None),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            return build_location_message(player, location, include_action_map=True)

    def test_location_removes_inline_ordinary_travel_without_dangling_heading(self):
        text, keyboard, _snapshot = self._build_location()
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

        self.assertFalse([callback for callback in callbacks if callback.startswith('goto_')])
        self.assertNotIn('Travel to:', text)

    def test_location_keeps_inline_gather_when_profiles_exist(self):
        _text, keyboard, _snapshot = self._build_location(gather_profiles=[SimpleNamespace(item_id='herb_common')])
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

        self.assertIn('gather', callbacks)

    def test_location_keeps_unrelated_inline_location_actions(self):
        text, keyboard, snapshot = self._build_location(services=['shop'])
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

        self.assertIn('shop', snapshot['actions'].values())
        self.assertIn('sv1 shop', text)
        self.assertFalse([callback for callback in callbacks if callback.startswith('goto_')])


class LowerMenuTextDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_lower_travel_button_routes_to_shared_goto_flow(self):
        update = SimpleNamespace(
            message=SimpleNamespace(text=build_lower_travel_label('westwild_n1', 'en'), reply_text=AsyncMock()),
            effective_user=SimpleNamespace(id=1),
        )
        context = SimpleNamespace()

        with patch('handlers.location.get_player', return_value={'telegram_id': 1, 'lang': 'en', 'location_id': 'capital_city'}), \
             patch('handlers.location.handle_location_buttons', new=AsyncMock()) as handle_mock:
            handled = await handle_lower_menu_travel_text(update, context)

        self.assertTrue(handled)
        adapted_update = handle_mock.await_args.args[0]
        self.assertEqual(adapted_update.callback_query.data, 'goto_westwild_n1')

    async def test_stale_lower_travel_button_replies_and_does_not_fall_through(self):
        update = SimpleNamespace(
            message=SimpleNamespace(text=build_lower_travel_label('westwild_n1', 'en'), reply_text=AsyncMock()),
            effective_user=SimpleNamespace(id=1),
        )
        context = SimpleNamespace()

        with patch('handlers.location.get_player', return_value={'telegram_id': 1, 'lang': 'en', 'location_id': 'westwild_n7'}), \
             patch('handlers.location.handle_location_buttons', new=AsyncMock()) as handle_mock:
            handled = await handle_lower_menu_travel_text(update, context)

        self.assertTrue(handled)
        handle_mock.assert_not_awaited()
        update.message.reply_text.assert_awaited_once_with(
            '⏳ This travel option is no longer available from your current location. Refresh with /location.'
        )

    async def test_stale_lower_travel_text_does_not_reach_name_handler(self):
        from bot import handle_text

        update = SimpleNamespace(
            message=SimpleNamespace(text=build_lower_travel_label('westwild_n1', 'en'), reply_text=AsyncMock()),
            effective_user=SimpleNamespace(id=1),
        )
        context = SimpleNamespace()

        with patch('handlers.location.get_player', return_value={'telegram_id': 1, 'lang': 'en', 'location_id': 'westwild_n7'}), \
             patch('bot.handle_name_input', new=AsyncMock()) as name_mock:
            await handle_text(update, context)

        name_mock.assert_not_awaited()
        update.message.reply_text.assert_awaited_once()

    async def test_map_lower_menu_text_opens_map_command(self):
        from bot import handle_text

        update = SimpleNamespace(message=SimpleNamespace(text='🗺️ Map'), effective_user=SimpleNamespace(id=1))
        context = SimpleNamespace()

        with patch('bot.map_command', new=AsyncMock()) as map_mock:
            await handle_text(update, context)

        map_mock.assert_awaited_once_with(update, context)


class LowerMenuRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_location_command_sends_inline_location_then_lower_menu_sync(self):
        reply_text = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(text='/location', reply_text=reply_text),
            effective_user=SimpleNamespace(id=1),
        )
        context = SimpleNamespace(user_data={})
        player = {
            'telegram_id': 1,
            'lang': 'en',
            'location_id': 'capital_city',
            'in_battle': 0,
            'level': 10,
            'hp': 100,
            'max_hp': 100,
            'mana': 50,
            'max_mana': 50,
            'gold': 0,
        }

        with patch('handlers.location.get_player', return_value=player), \
             patch('handlers.location.is_player_busy_with_live_pvp', return_value=False), \
             patch('handlers.location.is_in_battle', return_value=False), \
             patch('handlers.location.get_location', return_value={'id': 'capital_city', 'safe': True}), \
             patch('handlers.location._build_location_message_with_snapshot', return_value=('location text', Mock())):
            await location_command(update, context)

        self.assertEqual(reply_text.await_count, 2)
        first_call, second_call = reply_text.await_args_list
        self.assertEqual(first_call.args[0], 'location text')
        self.assertEqual(second_call.args[0], '⌨️ Lower menu updated.')
        self.assertIn('reply_markup', first_call.kwargs)
        self.assertIn('reply_markup', second_call.kwargs)

    async def test_successful_travel_arrival_refreshes_lower_menu(self):
        query_message = SimpleNamespace(message_id=10, reply_text=AsyncMock())
        query = SimpleNamespace(
            data='goto_westwild_n1',
            from_user=SimpleNamespace(id=1),
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            message=query_message,
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(application=SimpleNamespace(create_task=lambda coro: coro), user_data={})
        player_before = {'telegram_id': 1, 'lang': 'en', 'in_battle': 0, 'location_id': 'capital_city', 'level': 10}
        player_after = {
            'telegram_id': 1,
            'lang': 'en',
            'in_battle': 0,
            'location_id': 'westwild_n1',
            'level': 10,
            'hp': 100,
            'max_hp': 100,
            'mana': 50,
            'max_mana': 50,
            'gold': 0,
        }
        conn = Mock()

        with patch('handlers.location.get_player', side_effect=[player_before, player_after]), \
             patch('handlers.location.has_active_live_pvp_engagement', return_value=False), \
             patch('handlers.location.is_in_battle', return_value=False), \
             patch('handlers.location.is_pvp_mobility_blocked', return_value=False), \
             patch('handlers.location.asyncio.sleep', new=AsyncMock()), \
             patch('handlers.location.get_location', return_value={'id': 'westwild_n1', 'safe': True}), \
             patch('handlers.location.get_connection', return_value=conn), \
             patch('handlers.location.ensure_player_location_discovered'), \
             patch('handlers.location.clear_respawn_protection_on_dangerous_reentry'), \
             patch('handlers.location._build_location_message_with_snapshot', return_value=('arrived text', Mock())):
            await handle_location_buttons(update, context)

        query.edit_message_text.assert_any_await('arrived text', reply_markup=unittest.mock.ANY, parse_mode='HTML')
        query_message.reply_text.assert_awaited_once()
        self.assertEqual(query_message.reply_text.await_args.args[0], '⌨️ Lower menu updated.')
