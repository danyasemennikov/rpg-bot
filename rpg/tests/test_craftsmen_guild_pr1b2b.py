import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from game.contextual_keyboard import build_contextual_main_keyboard, resolve_lower_service_button
from game.locations import get_location
from game.resource_handbook import build_resource_handbook_index
from handlers.location import (
    build_craftsmen_handbook_home,
    build_craftsmen_handbook_profession_page,
    handle_location_buttons,
)


def _flat_rows(keyboard):
    return [button.text for row in keyboard.keyboard for button in row]


class CraftsmenGuildPR1B2BTests(unittest.IsolatedAsyncioTestCase):
    def test_lower_button_visibility_and_order(self):
        cap = _flat_rows(build_contextual_main_keyboard({'location_id': 'capital_city'}, 'en'))
        self.assertIn('🛠️ Craftsmen Guild', cap)
        self.assertIn('🛠️ Craftsmen Guild', _flat_rows(build_contextual_main_keyboard({'location_id': 'hub_sunscar'}, 'en')))
        self.assertNotIn('🛠️ Craftsmen Guild', _flat_rows(build_contextual_main_keyboard({'location_id': 'westwild_n7'}, 'en')))
        self.assertLess(cap.index('📋 Quest Board'), cap.index('🛠️ Craftsmen Guild'))

    def test_lower_service_dispatch(self):
        service_id = resolve_lower_service_button('🛠️ Craftsmen Guild', {'location_id': 'capital_city'}, 'en')
        self.assertEqual(service_id, 'craftsmen_guild')
        stale = resolve_lower_service_button('🛠️ Craftsmen Guild', {'location_id': 'westwild_n7'}, 'en')
        self.assertEqual(stale, '')

    def test_late_hubs_are_guild_only_services(self):
        for hub_id in ('hub_ashen_ruins', 'hub_sunscar', 'hub_mireveil'):
            services = list((get_location(hub_id) or {}).get('services', []))
            self.assertIn('craftsmen_guild', services)
            self.assertNotIn('shop', services)
            self.assertNotIn('inn', services)
            self.assertNotIn('quest_board', services)

    def test_late_hub_lower_menu_shows_guild_but_not_other_services(self):
        for hub_id in ('hub_ashen_ruins', 'hub_sunscar', 'hub_mireveil'):
            flat = _flat_rows(build_contextual_main_keyboard({'location_id': hub_id}, 'en'))
            self.assertIn('🛠️ Craftsmen Guild', flat)
            self.assertNotIn('🏪 Shop', flat)
            self.assertNotIn('🏨 Inn', flat)
            self.assertNotIn('📋 Quest Board', flat)

    def test_handbook_home_buttons(self):
        _text, kb = build_craftsmen_handbook_home({'lang': 'en'})
        callbacks = [b.callback_data for row in kb.inline_keyboard for b in row]
        self.assertIn('craftsmen_handbook_herbalism', callbacks)
        self.assertIn('craftsmen_handbook_woodcutting', callbacks)
        self.assertIn('craftsmen_handbook_mining', callbacks)
        self.assertIn('craftsmen_handbook_fishing', callbacks)
        self.assertIn('craftsmen_back_to_guild', callbacks)

    def test_profession_page_data_and_no_ids_or_chance(self):
        text, kb = build_craftsmen_handbook_profession_page({'lang': 'en'}, 'mining')
        self.assertIn('Resource Handbook', text)
        self.assertNotIn('old_mine_entrance', text)
        self.assertNotIn('iron_ore', text)
        self.assertNotIn('0.', text)
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, 'craftsmen_handbook')

    def test_handbook_aggregation_deterministic(self):
        first = build_resource_handbook_index()
        second = build_resource_handbook_index()
        self.assertEqual(first, second)
        self.assertTrue(first['herbalism'])

    async def test_guild_callback_unavailable_stale(self):
        query = SimpleNamespace(
            data='craftsmen_handbook_mining',
            from_user=SimpleNamespace(id=1),
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        with patch('handlers.location.get_player', return_value={'telegram_id': 1, 'lang': 'en', 'location_id': 'westwild_n7', 'in_battle': 0}), \
             patch('handlers.location.has_active_live_pvp_engagement', return_value=False):
            await handle_location_buttons(SimpleNamespace(callback_query=query), SimpleNamespace())
        query.answer.assert_awaited()
        query.edit_message_text.assert_not_awaited()
