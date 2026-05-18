import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.location import (
    _build_route_map_text,
    _parse_go_location_arg,
    _parse_map_route_arg,
    handle_location_buttons,
    handle_underscore_navigation_command,
)


class MapAndCommandParsingTests(unittest.TestCase):
    def test_map_parsing_variants(self):
        self.assertEqual(_parse_map_route_arg('/map westwild'), 'westwild')
        self.assertEqual(_parse_map_route_arg('/map_westwild'), 'westwild')
        self.assertEqual(_parse_map_route_arg('/map_westwild@SomeBot'), 'westwild')

    def test_go_parsing_variants(self):
        self.assertEqual(_parse_go_location_arg('/go westwild_n7'), 'westwild_n7')
        self.assertEqual(_parse_go_location_arg('/go_westwild_n7'), 'westwild_n7')
        self.assertEqual(_parse_go_location_arg('/go_westwild_n7@SomeBot'), 'westwild_n7')

    def test_westwild_order_is_natural(self):
        text = _build_route_map_text('westwild', 'capital_city', 'ru')
        self.assertLess(text.index('/go westwild_n1'), text.index('/go westwild_n2'))
        self.assertLess(text.index('/go westwild_n2'), text.index('/go westwild_n10'))

    def test_ashen_keeps_branching(self):
        text = _build_route_map_text('ashen_ruins', 'capital_city', 'ru')
        self.assertIn('├─', text)
        self.assertIn('/go ashen_n3a1', text)
        self.assertIn('/go ashen_n3b1', text)
        self.assertIn('/go ashen_n3c1', text)
        self.assertIn('/go ashen_n3b2a1', text)
        self.assertIn('/go ashen_n3b2b1', text)


class CallbackAndRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_map_route_callback_renders_without_crash(self):
        query = SimpleNamespace(
            data='map_route_westwild',
            from_user=SimpleNamespace(id=1),
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(application=SimpleNamespace(create_task=lambda x: x))

        with patch('handlers.location.get_player', return_value={'telegram_id': 1, 'lang': 'ru', 'in_battle': 0, 'location_id': 'capital_city'}), \
             patch('handlers.location.has_active_live_pvp_engagement', return_value=False):
            await handle_location_buttons(update, context)

        query.edit_message_text.assert_awaited()

    async def test_underscore_commands_are_routed_end_to_end(self):
        update_map = SimpleNamespace(message=SimpleNamespace(text='/map_westwild'), effective_user=SimpleNamespace(id=1))
        update_go = SimpleNamespace(message=SimpleNamespace(text='/go_westwild_n7'), effective_user=SimpleNamespace(id=1))
        context = SimpleNamespace()
        with patch('handlers.location.map_command', new=AsyncMock()) as map_mock, \
             patch('handlers.location.go_command', new=AsyncMock()) as go_mock:
            await handle_underscore_navigation_command(update_map, context)
            await handle_underscore_navigation_command(update_go, context)
        map_mock.assert_awaited_once()
        go_mock.assert_awaited_once()


class LongRouteGuardTests(unittest.IsolatedAsyncioTestCase):

    async def test_go_current_location_returns_already_here(self):
        query = SimpleNamespace(
            data='goto_westwild_n7',
            from_user=SimpleNamespace(id=1),
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            message=SimpleNamespace(message_id=1),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(application=SimpleNamespace(create_task=lambda x: x))
        with patch('handlers.location.get_player', return_value={'telegram_id': 1, 'lang': 'ru', 'in_battle': 0, 'location_id': 'westwild_n7', 'level': 1}),              patch('handlers.location.has_active_live_pvp_engagement', return_value=False),              patch('handlers.location.is_in_battle', return_value=False),              patch('handlers.location.is_pvp_mobility_blocked', return_value=False):
            await handle_location_buttons(update, context)
        self.assertTrue(query.answer.await_count >= 1)
        first_call = query.answer.await_args_list[0]
        self.assertNotIn('Локация не найдена', str(first_call))
        self.assertIn('уже находитесь', str(first_call))

    async def test_undiscovered_distant_rejected(self):
        query = SimpleNamespace(
            data='goto_westwild_n7',
            from_user=SimpleNamespace(id=1),
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            message=SimpleNamespace(message_id=1),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(application=SimpleNamespace(create_task=lambda x: x))
        with patch('handlers.location.get_player', return_value={'telegram_id': 1, 'lang': 'ru', 'in_battle': 0, 'location_id': 'capital_city', 'level': 1}), \
             patch('handlers.location.has_active_live_pvp_engagement', return_value=False), \
             patch('handlers.location.is_in_battle', return_value=False), \
             patch('handlers.location.is_pvp_mobility_blocked', return_value=False), \
             patch('handlers.location.is_location_discovered', return_value=False):
            await handle_location_buttons(update, context)
        self.assertTrue(query.answer.await_count >= 1)


if __name__ == '__main__':
    unittest.main()
