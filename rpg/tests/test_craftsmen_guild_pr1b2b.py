import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from game.contextual_keyboard import build_contextual_main_keyboard, resolve_lower_service_button
from game.locations import get_location
from game.i18n import t
from database import get_connection,get_player
from handlers.world_views import location_card
from game.resource_handbook import build_resource_handbook_index
from handlers.location import (
    build_craftsmen_handbook_home,
    build_craftsmen_handbook_profession_page,
    handle_location_buttons,
)


def _flat_rows(keyboard):
    return [button.text for row in keyboard.keyboard for button in row]


def _services(location_id):
    conn=get_connection()
    conn.execute('UPDATE players SET location_id=?,lang=? WHERE telegram_id=1',(location_id,'en'))
    conn.commit();conn.close()
    _,keyboard=location_card(dict(get_player(1)),category='services')
    return [b.callback_data for row in keyboard.inline_keyboard for b in row]


class CraftsmenGuildPR1B2BTests(unittest.IsolatedAsyncioTestCase):
    def test_lower_button_visibility_and_order(self):
        cap = _flat_rows(build_contextual_main_keyboard({'location_id': 'capital_city'}, 'en'))
        self.assertEqual(cap,[t('pxe1.menu.'+key,'en') for key in ('location','map','journal','inventory','character','activities')])
        for location in ('hub_sunscar','westwild_n7'):
            self.assertEqual(cap,_flat_rows(build_contextual_main_keyboard({'location_id':location},'en')))
        services=_services('capital_city')
        self.assertIn('craftsmen_guild',services)
        self.assertLess(services.index('quest_board'),services.index('craftsmen_guild'))
        self.assertIn('craftsmen_guild',_services('hub_sunscar'))
        self.assertNotIn('craftsmen_guild',_services('westwild_n7'))

    def test_lower_service_dispatch(self):
        service_id = resolve_lower_service_button('🛠️ Craftsmen Guild', {'location_id': 'capital_city'}, 'en')
        self.assertEqual(service_id, 'craftsmen_guild')
        stale = resolve_lower_service_button('🛠️ Craftsmen Guild', {'location_id': 'westwild_n7'}, 'en')
        self.assertEqual(stale, '')

    def test_late_hubs_keep_guild_without_shop_and_add_rav1_inns(self):
        for hub_id in ('hub_ashen_ruins', 'hub_sunscar', 'hub_mireveil'):
            services = list((get_location(hub_id) or {}).get('services', []))
            self.assertIn('craftsmen_guild', services)
            self.assertNotIn('shop', services)
            self.assertIn('inn', services)
            if hub_id == 'hub_sunscar':
                self.assertIn('quest_board', services)
            else:
                self.assertNotIn('quest_board', services)

    def test_late_hub_lower_menu_shows_guild_and_rav1_inn_but_not_shop(self):
        for hub_id in ('hub_ashen_ruins', 'hub_sunscar', 'hub_mireveil'):
            flat = _services(hub_id)
            self.assertIn('craftsmen_guild', flat)
            self.assertNotIn('shop', flat)
            self.assertIn('inn', flat)
            if hub_id == 'hub_sunscar':
                self.assertIn('quest_board', flat)
            else:
                self.assertNotIn('quest_board', flat)

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
