from game.gear_instances import grant_item_to_player
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from game.contextual_keyboard import (
    LOWER_TRAVEL_PREFIX,
    build_contextual_main_keyboard,
    build_lower_travel_label,
    get_contextual_travel_targets,
    looks_like_lower_gather_button,
    looks_like_lower_service_button,
    resolve_lower_gather_profession_button,
)
from handlers.location import (
    _legacy_location_message as build_location_message,
    handle_location_buttons,
    handle_lower_menu_gather_text,
    handle_lower_menu_service_text,
    handle_lower_menu_travel_text,
    location_command,
)
from game.i18n import t
from database import get_connection,get_player
from handlers.world_views import location_card,local_entries


def _keyboard_text_rows(keyboard):
    return [[button.text for button in row] for row in keyboard.keyboard]


def _player_at(location_id):
    conn=get_connection()
    conn.execute('UPDATE players SET location_id=?,lang=? WHERE telegram_id=1',(location_id,'en'))
    conn.commit();conn.close()
    return dict(get_player(1))


class ContextualLowerMenuTests(unittest.TestCase):
    def test_contextual_lower_menu_renders_neighbor_travel_above_baseline(self):
        keyboard = build_contextual_main_keyboard({'location_id': 'capital_city'}, 'en')
        rows = _keyboard_text_rows(keyboard)

        self.assertEqual(rows[0],['📍 Location','🗺️ Map'])
        self.assertEqual([len(row) for row in rows],[2,2,2])
        _,inline=location_card(_player_at('capital_city'),category='exits')
        self.assertIn('goto_westwild_n1',[b.callback_data for row in inline.inline_keyboard for b in row])

    def test_contextual_lower_menu_filters_invalid_neighbors(self):
        with patch('game.contextual_keyboard.get_location_neighbors', return_value=['westwild_n1', 'missing_place']):
            targets=get_contextual_travel_targets('capital_city')
            keyboard = build_contextual_main_keyboard({'location_id': 'capital_city'}, 'en')

        flat = [text for row in _keyboard_text_rows(keyboard) for text in row]
        self.assertEqual(targets,['westwild_n1'])
        self.assertNotIn(build_lower_travel_label('westwild_n1', 'en'), flat)
        self.assertFalse(any('missing_place' in text for text in flat))

    def test_baseline_system_buttons_and_dedicated_map_label_remain_present(self):
        keyboard = build_contextual_main_keyboard({'location_id': 'capital_city'}, 'en')
        flat = [text for row in _keyboard_text_rows(keyboard) for text in row]

        self.assertEqual(flat,[t('pxe1.menu.'+key,'en') for key in ('location','map','journal','inventory','character','activities')])

    def test_contextual_lower_menu_renders_profession_rows_between_travel_and_baseline(self):
        with patch('game.profession_resources.location_sources',return_value=[('herb_common',.4),('iron_ore',.2)]):
            keyboard = build_contextual_main_keyboard({'location_id': 'capital_city'}, 'en')
            _,categories=local_entries(_player_at('capital_city'))
        rows = _keyboard_text_rows(keyboard)
        self.assertEqual([len(row) for row in rows],[2,2,2])
        self.assertEqual([callback for _,callback in categories['gathering']],['px:gatherpreview:herbalism','px:gatherpreview:mining'])

    def test_looks_like_lower_gather_button_accepts_cross_locale_labels(self):
        self.assertTrue(looks_like_lower_gather_button('🌿 Собирать'))
        self.assertTrue(looks_like_lower_gather_button('🌿 Gather'))
        self.assertTrue(looks_like_lower_gather_button('🌿 Recolectar'))

    def test_contextual_lower_menu_renders_service_rows_after_gather_before_baseline(self):
        with patch('game.contextual_keyboard.build_location_gather_source_profiles', return_value=[SimpleNamespace(profession_key='herbalism')]):
            keyboard = build_contextual_main_keyboard({'location_id': 'capital_city'}, 'en')
        rows = _keyboard_text_rows(keyboard)
        self.assertEqual([len(row) for row in rows],[2,2,2])
        _,services=location_card(_player_at('capital_city'),category='services')
        callbacks=[b.callback_data for row in services.inline_keyboard for b in row]
        self.assertEqual(callbacks[:4],['shop','quest_board','craftsmen_guild','inn'])


class LegacyLocationInlineRenderingTests(unittest.TestCase):
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
            patch('game.gathering_runtime.build_location_gather_source_profiles', return_value=gather_profiles or []),
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

    def test_location_removes_inline_gather_when_profiles_exist(self):
        _text, keyboard, _snapshot = self._build_location(gather_profiles=[SimpleNamespace(item_id='herb_common')])
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

        self.assertNotIn('gather', callbacks)

    def test_location_keeps_unrelated_inline_location_actions(self):
        text, keyboard, snapshot = self._build_location(services=['shop'])
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

        self.assertNotIn('shop', snapshot['actions'].values())
        self.assertNotIn('sv1 shop', text)
        self.assertFalse([callback for callback in callbacks if callback.startswith('goto_')])


class LowerMenuTextDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_looks_like_lower_service_button_accepts_cross_locale_labels(self):
        self.assertTrue(looks_like_lower_service_button('🏪 Shop'))
        self.assertTrue(looks_like_lower_service_button('🏨 Таверна'))
        self.assertTrue(looks_like_lower_service_button('📋 Tablero de encargos'))

    async def test_valid_lower_service_button_routes_to_shared_callback_flow(self):
        update = SimpleNamespace(
            message=SimpleNamespace(text='🏪 Shop', reply_text=AsyncMock()),
            effective_user=SimpleNamespace(id=1),
        )
        context = SimpleNamespace()
        with patch('handlers.location.get_player', return_value={'telegram_id': 1, 'lang': 'en', 'location_id': 'capital_city'}), \
             patch('handlers.location.handle_location_buttons', new=AsyncMock()) as handle_mock:
            handled = await handle_lower_menu_service_text(update, context)
        self.assertTrue(handled)
        adapted_update = handle_mock.await_args.args[0]
        self.assertEqual(adapted_update.callback_query.data, 'shop')
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

    async def test_stale_lower_gather_text_replies_and_does_not_fall_through(self):
        update = SimpleNamespace(
            message=SimpleNamespace(text='🌿 Gather', message_id=17, reply_text=AsyncMock()),
            effective_user=SimpleNamespace(id=1),
        )
        context = SimpleNamespace()
        with patch('handlers.location.get_player', return_value={'telegram_id': 1, 'lang': 'en', 'location_id': 'capital_city'}), \
             patch('game.gathering_runtime.build_location_gather_source_profiles', return_value=[]), \
             patch('game.gathering_runtime.grant_item_to_player', wraps=grant_item_to_player) as grant_mock:
            handled = await handle_lower_menu_gather_text(update, context)
        self.assertTrue(handled)
        grant_mock.assert_not_called()
        update.message.reply_text.assert_awaited_once()

    async def test_valid_lower_gather_button_grants_profession_filtered_resource(self):
        from tests.pxe1_gather_fixture import one_tick
        from game.player_experience_schema import grant_player_pxe1_starters
        _player_at('westwild_n1')
        conn=get_connection();grant_player_pxe1_starters(conn,1,now_ms=0,acquired_via='starter');conn.commit();conn.close()
        with patch('game.gathering_runtime.grant_item_to_player',wraps=grant_item_to_player) as grant_mock:
            handled,_,result=await one_tick(1,'herbalism',.2,17)
        self.assertTrue(handled)
        grant_mock.assert_called_once()
        self.assertEqual([row['item_id'] for row in result['granted']],['herb_common'])

    async def test_valid_lower_gather_button_fail_roll_replies_and_does_not_grant(self):
        from tests.pxe1_gather_fixture import one_tick
        from game.player_experience_schema import grant_player_pxe1_starters
        _player_at('westwild_n1')
        conn=get_connection();grant_player_pxe1_starters(conn,1,now_ms=0,acquired_via='starter');conn.commit();conn.close()
        with patch('game.gathering_runtime.grant_item_to_player',wraps=grant_item_to_player) as grant_mock:
            handled,message,result=await one_tick(1,'herbalism',.99,17)
        self.assertTrue(handled)
        grant_mock.assert_not_called()
        self.assertEqual(result['granted'],[])
        self.assertEqual(result['xp'],0)
        message.reply_text.assert_awaited_once()

    async def test_lower_gather_recognized_without_character_stops_fallthrough(self):
        from bot import handle_text
        update = SimpleNamespace(
            message=SimpleNamespace(text='🌿 Gather', message_id=17, reply_text=AsyncMock()),
            effective_user=SimpleNamespace(id=1),
        )
        context = SimpleNamespace()
        with patch('handlers.location.get_player', return_value=None), \
             patch('bot.handle_name_input', new=AsyncMock()) as name_mock:
            await handle_text(update, context)
        name_mock.assert_not_awaited()
        update.message.reply_text.assert_awaited_once_with(t('common.no_character', 'ru'))

    async def test_gather_blocked_while_in_battle(self):
        update = SimpleNamespace(
            message=SimpleNamespace(text='🌿 Gather', message_id=17, reply_text=AsyncMock()),
            effective_user=SimpleNamespace(id=1),
        )
        context = SimpleNamespace()
        with patch('handlers.location.get_player', return_value={'telegram_id': 1, 'lang': 'en', 'location_id': 'capital_city', 'level': 10, 'in_battle': 1}), \
             patch('handlers.location.has_active_live_pvp_engagement', return_value=False), \
             patch('game.gathering_runtime.grant_item_to_player', wraps=grant_item_to_player) as grant_mock:
            handled = await handle_lower_menu_gather_text(update, context)
        self.assertTrue(handled)
        grant_mock.assert_not_called()
        update.message.reply_text.assert_awaited_once_with(t('location.in_battle_block', 'en'))

    async def test_gather_blocked_in_pending_prep_live_pvp_context(self):
        update = SimpleNamespace(
            message=SimpleNamespace(text='🌿 Gather', message_id=17, reply_text=AsyncMock()),
            effective_user=SimpleNamespace(id=1),
        )
        context = SimpleNamespace()
        with patch('handlers.location.get_player', return_value={'telegram_id': 1, 'lang': 'en', 'location_id': 'capital_city', 'level': 10, 'in_battle': 0}), \
             patch('handlers.location.has_active_live_pvp_engagement', return_value=True), \
             patch('game.gathering_runtime.grant_item_to_player', wraps=grant_item_to_player) as grant_mock:
            handled = await handle_lower_menu_gather_text(update, context)
        self.assertTrue(handled)
        grant_mock.assert_not_called()
        update.message.reply_text.assert_awaited_once_with(t('location.pvp_context_block', 'en'))


class LowerMenuRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_location_command_sends_inline_location_then_lower_menu_sync(self):
        reply_text = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(text='/location', reply_text=reply_text),
            effective_user=SimpleNamespace(id=1),
        )
        context = SimpleNamespace(user_data={},bot=SimpleNamespace(send_message=AsyncMock(),edit_message_text=AsyncMock(),delete_message=AsyncMock()))
        player = {
            'telegram_id': 1,
            'name': 'TestUser',
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
        self.assertEqual(second_call.args[0],t('pxe1.menu.welcome_status','en',name=get_player(1)['name'],location='🏛️ Aster'))
        self.assertIn('reply_markup', first_call.kwargs)
        self.assertIn('reply_markup', second_call.kwargs)

    async def test_travel_arrival_keeps_fixed_menu_and_location_installs_it_once(self):
        from handlers.activities import handle_activity_buttons
        from game.travel_runtime import advance_travel_edge
        from database import is_location_discovered
        _player_at('capital_city')
        message=SimpleNamespace(message_id=10,chat_id=1,reply_text=AsyncMock())
        query=SimpleNamespace(data='goto_westwild_n1',from_user=SimpleNamespace(id=1),
            answer=AsyncMock(),edit_message_text=AsyncMock(),message=message)
        context=SimpleNamespace(user_data={},bot=SimpleNamespace(send_message=AsyncMock(),edit_message_text=AsyncMock(),delete_message=AsyncMock()))
        await handle_location_buttons(SimpleNamespace(callback_query=query),context)
        self.assertEqual(get_player(1)['location_id'],'capital_city')
        self.assertFalse(is_location_discovered(1,'westwild_n1'))
        keyboard=query.edit_message_text.call_args.kwargs['reply_markup']
        query.data=next(b.callback_data for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith('px:travel:'))
        with patch('time.time',return_value=1000):
            await handle_activity_buttons(SimpleNamespace(callback_query=query),context)
        conn=get_connection()
        session=conn.execute("SELECT * FROM player_travel_sessions WHERE player_id=1 AND status='running'").fetchone()
        self.assertIsNotNone(session)
        conn.execute('BEGIN IMMEDIATE')
        advance_travel_edge(conn,session['session_id'],now_ms=session['next_due_ms'])
        conn.commit();conn.close()
        self.assertEqual(get_player(1)['location_id'],'westwild_n1')
        self.assertTrue(is_location_discovered(1,'westwild_n1'))
        message.reply_text.assert_not_awaited()
        update=SimpleNamespace(message=message,effective_user=SimpleNamespace(id=1))
        await location_command(update,context)
        menus=[call.kwargs['reply_markup'] for call in message.reply_text.await_args_list
               if hasattr(call.kwargs.get('reply_markup'),'keyboard')]
        self.assertEqual(len(menus),1)
        self.assertEqual([len(row) for row in menus[0].keyboard],[2,2,2])
        await location_command(update,context)
        self.assertEqual(len([call for call in message.reply_text.await_args_list
            if hasattr(call.kwargs.get('reply_markup'),'keyboard')]),1)
