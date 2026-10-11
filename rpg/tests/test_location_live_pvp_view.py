import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.location import _legacy_location_message as build_location_message, handle_location_buttons, location_command, pvp_command
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


class _FakeContext:
    def __init__(self):
        self.user_data = {}
        self.bot = SimpleNamespace(send_message=AsyncMock(),edit_message_text=AsyncMock())
        self.application = type('A', (), {'create_task': lambda *args, **kwargs: None})()


class LivePvpLocationCommandTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _location_message_stub(_player, _location, **kwargs):
        if kwargs.get('include_action_map'):
            return 'ok', None, {'snapshot_tag': 's1', 'actions': {}}
        return 'ok', None

    async def test_location_command_allows_live_pvp_view_when_in_battle(self):
        update = _FakeUpdate(12345)
        context = _FakeContext()
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
            patch('handlers.location.build_location_message', side_effect=self._location_message_stub),
        ):
            await location_command(update, context=context)

        update.message.reply_text.assert_awaited_once_with('ok', reply_markup=None, parse_mode='HTML')

    async def test_location_command_resumes_current_non_pvp_battle(self):
        from database import get_connection
        from tests.test_pxe1_pve_world_tick import started
        encounter,_=started()
        conn=get_connection()
        before=conn.execute('SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0]
        update=_FakeUpdate(1)
        with patch('time.time',return_value=1013):
            await location_command(update,_FakeContext())
        callbacks=[button.callback_data for call in update.message.reply_text.call_args_list
            if getattr(call.kwargs.get('reply_markup'),'inline_keyboard',None)
            for row in call.kwargs['reply_markup'].inline_keyboard for button in row]
        self.assertIn('pve_enter_'+encounter,callbacks)
        self.assertEqual(conn.execute('SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0],before)
        self.assertEqual(conn.execute('SELECT in_battle FROM players WHERE telegram_id=1').fetchone()[0],1)
        conn.close()

    async def _assert_current_pvp_blocks_move(self,live):
        from database import get_player,get_connection
        from tests.test_pxe1_pvp_membership import prepare
        from game.pvp_world import lock_preparation
        conn,e=prepare()
        if live:
            conn.execute('BEGIN IMMEDIATE');lock_preparation(conn,engagement_id=e,now_ms=1300000);conn.commit()
        update=_FakeCallbackUpdate(1,'goto_westwild_n5')
        before=dict(get_player(1))
        await handle_location_buttons(update,_FakeContext())
        kb=update.callback_query.edit_message_text.call_args.kwargs['reply_markup']
        self.assertFalse(any(b.callback_data.startswith('px:travel:') for row in kb.inline_keyboard for b in row))
        self.assertEqual(dict(get_player(1)),before)
        self.assertFalse(conn.execute('SELECT 1 FROM player_travel_sessions WHERE player_id=1').fetchone())
        conn.close()

    async def test_pending_engagement_blocks_location_move(self):
        await self._assert_current_pvp_blocks_move(False)

    async def test_converted_battle_blocks_location_move(self):
        await self._assert_current_pvp_blocks_move(True)

    async def test_normal_player_can_still_move(self):
        from tests.test_location_discovery_travel_migration import LocationDiscoveryTravelMigrationTests
        from database import get_player,is_location_discovered
        fixture=LocationDiscoveryTravelMigrationTests()
        fixture.setUp()
        try:
            query=await fixture._travel_for_test(start_location_id='capital_city',target_location_id='westwild_n1')
            self.assertEqual(get_player(9101)['location_id'],'westwild_n1')
            self.assertEqual(get_player(9101)['travel_revision'],2)
            self.assertTrue(is_location_discovered(9101,'westwild_n1'))
            self.assertEqual(query.edit_message_text.await_count,2)
        finally: fixture.tearDown()

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
        engagement = {'id': 9, 'attacker_id': 1001, 'defender_id': 2002, 'world_model_version': 0}
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
        engagement = {'id': 9, 'attacker_id': 1001, 'defender_id': 2002, 'world_model_version': 0}
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
        engagement = {'id': 9, 'attacker_id': 1001, 'defender_id': 2002, 'world_model_version': 0}
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
        engagement = {'id': 9, 'attacker_id': 1001, 'defender_id': 2002, 'world_model_version': 0}
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
        self.assertIn('/enc 12', text)
        self.assertNotIn('pv1 view', text)
        callback_ids = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
        self.assertNotIn('pvp_view_12', callback_ids)

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
        engagement = {'id': 9, 'attacker_id': 1001, 'defender_id': 2002, 'engagement_state': 'pending','world_model_version':0}
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
        engagement = {'id': 9, 'attacker_id': 1001, 'defender_id': 2002, 'engagement_state': 'pending','world_model_version':0}
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
        context = _FakeContext()
        player = {'telegram_id': 3003, 'lang': 'en', 'in_battle': 0, 'location_id': 'dark_forest', 'level': 10}
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': []}
        with (
            patch('handlers.location.get_player', return_value=player),
            patch('handlers.location.has_active_live_pvp_engagement', return_value=False),
            patch('handlers.location.respond_to_reinforcement_invite', return_value=(True, None)) as respond_mock,
            patch('handlers.location.get_location', return_value=location),
            patch('handlers.location.build_location_message', side_effect=self._location_message_stub),
            patch('handlers.location.t', side_effect=lambda key, _lang, **kwargs: key),
        ):
            await handle_location_buttons(update, context=context)
        respond_mock.assert_called_once_with(engagement_id=9, ally_id=3003, accepted=True)
        update.callback_query.answer.assert_awaited_once_with('location.pvp_reinforcement_accept_done', show_alert=True)

    async def test_invited_ally_decline_path_works_from_location_callback(self):
        update = _FakeCallbackUpdate(3003, 'pvp_reinf_decline_9')
        context = _FakeContext()
        player = {'telegram_id': 3003, 'lang': 'en', 'in_battle': 0, 'location_id': 'dark_forest', 'level': 10}
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': []}
        with (
            patch('handlers.location.get_player', return_value=player),
            patch('handlers.location.has_active_live_pvp_engagement', return_value=False),
            patch('handlers.location.respond_to_reinforcement_invite', return_value=(True, None)) as respond_mock,
            patch('handlers.location.get_location', return_value=location),
            patch('handlers.location.build_location_message', side_effect=self._location_message_stub),
            patch('handlers.location.t', side_effect=lambda key, _lang, **kwargs: key),
        ):
            await handle_location_buttons(update, context=context)
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
