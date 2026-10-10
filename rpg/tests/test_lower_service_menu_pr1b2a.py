import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from game.contextual_keyboard import build_contextual_main_keyboard
from game.i18n import t
from handlers.location import handle_lower_menu_service_text


def _keyboard_text_rows(keyboard):
    return [[button.text for button in row] for row in keyboard.keyboard]


class LowerServiceMenuTests(unittest.IsolatedAsyncioTestCase):
    def test_fixed_menu_and_contextual_service_visibility(self):
        from database import get_connection,get_player
        from handlers.world_views import location_card
        capital=build_contextual_main_keyboard({'location_id':'capital_city'},'en')
        wilderness=build_contextual_main_keyboard({'location_id':'dark_forest'},'en')
        self.assertEqual(_keyboard_text_rows(capital),_keyboard_text_rows(wilderness))
        self.assertEqual([len(row) for row in capital.keyboard],[2,2,2])
        for location,has_inn in (('capital_city',True),('dark_forest',False)):
            conn=get_connection()
            conn.execute('UPDATE players SET location_id=? WHERE telegram_id=1',(location,))
            conn.commit();conn.close()
            _,keyboard=location_card(dict(get_player(1)),category='services')
            callbacks=[b.callback_data for row in keyboard.inline_keyboard for b in row]
            self.assertEqual('inn' in callbacks,has_inn)
            if has_inn:
                self.assertIn('shop',callbacks)
                self.assertIn('quest_board',callbacks)

    async def test_stale_service_label_returns_localized_message_and_stops(self):
        update = SimpleNamespace(message=SimpleNamespace(text='🏪 Shop', reply_text=AsyncMock()), effective_user=SimpleNamespace(id=1))
        context = SimpleNamespace()
        with patch('handlers.location.get_player', return_value={'telegram_id': 1, 'lang': 'en', 'location_id': 'dark_forest'}), \
             patch('handlers.location.handle_location_buttons', new=AsyncMock()) as handle_mock:
            handled = await handle_lower_menu_service_text(update, context)
        self.assertTrue(handled)
        handle_mock.assert_not_awaited()
        update.message.reply_text.assert_awaited_once_with(t('location.lower_service_stale', 'en'))

    async def test_pvp_and_battle_blocks_are_reused_via_shared_callback_pipeline(self):
        update = SimpleNamespace(message=SimpleNamespace(text='🏪 Shop', reply_text=AsyncMock()), effective_user=SimpleNamespace(id=1))
        context = SimpleNamespace()
        query_answer = AsyncMock()
        with patch('handlers.location.get_player', side_effect=[{'telegram_id': 1, 'lang': 'en', 'location_id': 'capital_city'}, {'telegram_id': 1, 'lang': 'en', 'location_id': 'capital_city', 'in_battle': 0}]), \
             patch('handlers.location.has_active_live_pvp_engagement', return_value=True):
            # simulate handle_location_buttons path by intercepting adapter answer call
            with patch('handlers.location._MessageActionQueryAdapter.answer', query_answer):
                handled = await handle_lower_menu_service_text(update, context)
        self.assertTrue(handled)
