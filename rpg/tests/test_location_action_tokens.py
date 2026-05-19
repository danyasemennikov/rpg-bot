import re
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from game.locations import get_location
from handlers.location import (
    LOCATION_ACTION_SNAPSHOT_KEY,
    enc_command,
    handle_underscore_navigation_command,
    _build_location_message_with_snapshot,
    build_location_message,
    build_shop_message,
    handle_location_action_text,
)
from bot import LOCATION_CALLBACK_PATTERN, UNDERSCORE_NAV_COMMAND_PATTERN


class _DummyMessage:
    def __init__(self, text: str):
        self.text = text
        self.reply_text = AsyncMock()


class _DummyUpdate:
    def __init__(self, text: str, user_id: int = 5001):
        self.message = _DummyMessage(text)
        self.effective_user = SimpleNamespace(id=user_id)


class LocationActionTokenTests(unittest.IsolatedAsyncioTestCase):
    def test_bot_location_callback_pattern_includes_pve_prefix(self):
        self.assertIsNotNone(re.match(LOCATION_CALLBACK_PATTERN, 'pve_join_enc-1'))
        self.assertIsNotNone(re.match(LOCATION_CALLBACK_PATTERN, 'pve_leave_enc-1'))
        self.assertIsNotNone(re.match(LOCATION_CALLBACK_PATTERN, 'pve_enter_enc-1'))

    def test_underscore_command_pattern_accepts_hyphenated_encounter_ids(self):
        self.assertIsNotNone(re.match(UNDERSCORE_NAV_COMMAND_PATTERN, '/enc_pve-enc-abc123'))
        self.assertIsNotNone(re.match(UNDERSCORE_NAV_COMMAND_PATTERN, '/enc_pve-enc-abc123@TestBot'))

    def test_shop_message_title_is_truthful_for_village(self):
        player = {'telegram_id': 5001, 'lang': 'en', 'level': 10}
        location = get_location('village')
        assert location is not None
        text, _keyboard = build_shop_message(player, location)
        self.assertIn('Shop — 🏘️ Ashen Village', text)
        self.assertNotIn('Frontier Outpost', text)

    def test_shop_message_title_is_truthful_for_frontier_outpost(self):
        player = {'telegram_id': 5001, 'lang': 'en', 'level': 10}
        location = get_location('frontier_outpost')
        assert location is not None
        text, _keyboard = build_shop_message(player, location)
        self.assertIn('Shop — 🏕️ Frontier Outpost', text)
        self.assertNotIn('Village vendor', text)

    def test_frontier_outpost_does_not_expose_service_snapshot_commands(self):
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
        location = get_location('frontier_outpost')
        assert location is not None
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Frontier Outpost'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[]),
            patch('handlers.location.list_location_available_spawn_instances', return_value=[]),
            patch('handlers.location.list_location_active_pve_encounters', return_value=[]),
            patch('handlers.location.build_location_gather_source_profiles', return_value=[]),
            patch('handlers.location.build_hunt_contract_progress_line', return_value=None),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            text, _keyboard, snapshot = build_location_message(player, location, include_action_map=True)

        self.assertNotIn('sv1 shop', text)
        self.assertFalse([k for k in snapshot['actions'] if ' sv' in k])

    def test_shop_service_action_is_not_exposed_via_snapshot_text_command(self):
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
        location = {'id': 'village', 'safe': True, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': ['shop']}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Village'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[]),
            patch('handlers.location.list_location_available_spawn_instances', return_value=[]),
            patch('handlers.location.list_location_active_pve_encounters', return_value=[]),
            patch('handlers.location.build_location_gather_source_profiles', return_value=[]),
            patch('handlers.location.build_hunt_contract_progress_line', return_value=None),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            text, _keyboard, snapshot = build_location_message(player, location, include_action_map=True)

        self.assertNotIn('sv1 shop', text)
        self.assertIsNone(snapshot['actions'].get('s1 sv1 shop'))
        self.assertNotIn('snapshot_id', snapshot)

    def test_supported_services_are_not_present_in_snapshot_commands(self):
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
            'id': 'village',
            'safe': True,
            'level_min': 1,
            'level_max': 30,
            'mobs': [],
            'services': ['shop', 'inn', 'quest_board'],
        }
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Village'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[]),
            patch('handlers.location.list_location_available_spawn_instances', return_value=[]),
            patch('handlers.location.list_location_active_pve_encounters', return_value=[]),
            patch('handlers.location.build_location_gather_source_profiles', return_value=[]),
            patch('handlers.location.build_hunt_contract_progress_line', return_value=None),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            _text, _keyboard, snapshot = build_location_message(player, location, include_action_map=True)

        service_commands = [cmd for cmd in snapshot['actions'] if re.search(r'\ssv\d+\s', cmd)]
        self.assertEqual(service_commands, [])

    def test_pve_and_mob_snapshot_actions_removed_from_location_quick_tokens(self):
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
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': []}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[]),
            patch('handlers.location.list_location_available_spawn_instances', return_value=[
                {'spawn_instance_id': 'spawn-1', 'mob_id': 'forest_wolf', 'spawn_profile': 'normal', 'special_spawn_key': '', 'special_spawn_name': ''},
                {'spawn_instance_id': 'spawn-2', 'mob_id': 'forest_wolf', 'spawn_profile': 'normal', 'special_spawn_key': '', 'special_spawn_name': ''},
            ]),
            patch('handlers.location.list_location_active_pve_encounters', return_value=[{'encounter_id': 'enc-1', 'mob_id': 'forest_wolf', 'spawn_profile': 'normal', 'participant_player_ids': [], 'participant_count': 0, 'joinable': True}]),
            patch('handlers.location.build_location_gather_source_profiles', return_value=[]),
            patch('handlers.location.build_hunt_contract_progress_line', return_value=None),
            patch('handlers.location.get_mob', return_value={'aggressive': False, 'level': 10}),
            patch('handlers.location.can_join_open_world_pve_encounter', return_value=(True, None)),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            _text, _keyboard, snapshot = build_location_message(player, location, include_action_map=True)

        self.assertIn('/enc enc-1', _text)
        self.assertNotIn('pe1 view', _text)
        self.assertNotIn('m1 fight', _text)
        self.assertFalse([k for k in snapshot['actions'] if ' pe' in k or ' m' in k])
        flat_callbacks = [button.callback_data for row in _keyboard.inline_keyboard for button in row]
        self.assertIn('fight_spawn_spawn-1', flat_callbacks)
        self.assertIn('×2', _text)
        self.assertNotIn('spawn-1', _text)

    async def test_enc_command_prefers_pve_then_pvp_then_not_found(self):
        update = _DummyUpdate('/enc enc-77')
        context = SimpleNamespace()
        with (
            patch('handlers.location.get_player', return_value={'telegram_id': 5001, 'lang': 'en'}),
            patch('handlers.location.build_pve_encounter_detail_message', return_value=('PVE_DETAIL', 'KB')),
        ):
            await enc_command(update, context)
        update.message.reply_text.assert_awaited_with('PVE_DETAIL', reply_markup='KB', parse_mode='HTML')

        update2 = _DummyUpdate('/enc 77')
        with (
            patch('handlers.location.get_player', return_value={'telegram_id': 5001, 'lang': 'en'}),
            patch('handlers.location.build_pve_encounter_detail_message', return_value=('📭 This PvE encounter is no longer active.', 'KB1')),
            patch('handlers.location.build_pvp_encounter_detail_message', return_value=('PVP_DETAIL', 'KB2')),
        ):
            await enc_command(update2, context)
        update2.message.reply_text.assert_awaited_with('PVP_DETAIL', reply_markup='KB2', parse_mode='HTML')

        update3 = _DummyUpdate('/enc_404')
        with (
            patch('handlers.location.get_player', return_value={'telegram_id': 5001, 'lang': 'en'}),
            patch('handlers.location.build_pve_encounter_detail_message', return_value=('📭 This PvE encounter is no longer active.', 'KB1')),
            patch('handlers.location.build_pvp_encounter_detail_message', return_value=('❌ PvP engagement not found.', 'KB2')),
        ):
            await enc_command(update3, context)
        update3.message.reply_text.assert_awaited_with('📭 Encounter not found or already stale.')

    async def test_underscore_enc_command_routes_hyphenated_pve_id_to_enc_command(self):
        update = _DummyUpdate('/enc_pve-enc-abc123')
        context = SimpleNamespace()
        with patch('handlers.location.enc_command', new=AsyncMock()) as enc_mock:
            await handle_underscore_navigation_command(update, context)
        enc_mock.assert_awaited_once_with(update, context)

    def test_location_inline_keyboard_removes_gather_and_ordinary_travel(self):
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
        location = {'id': 'village', 'safe': True, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': ['shop']}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[{'id': 'dark_forest', 'safe': False, 'level_min': 1}]),
            patch('handlers.location.get_location_name', side_effect=lambda location_id, _lang: location_id),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[]),
            patch('handlers.location.list_location_available_spawn_instances', return_value=[]),
            patch('handlers.location.list_location_active_pve_encounters', return_value=[]),
            patch('handlers.location.build_location_gather_source_profiles', return_value=[SimpleNamespace(item_id='herb_common')]),
            patch('handlers.location.get_item_name', return_value='Herb'),
            patch('handlers.location.build_hunt_contract_progress_line', return_value=None),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            _text, keyboard, _snapshot = build_location_message(player, location, include_action_map=True)

        callback_rows = [[button.callback_data for button in row] for row in keyboard.inline_keyboard]
        flat_callbacks = [callback for row in callback_rows for callback in row]
        self.assertNotIn('gather', flat_callbacks)
        self.assertFalse([callback for callback in flat_callbacks if callback.startswith('goto_')])
        self.assertNotIn('shop', flat_callbacks)
        self.assertNotIn('Travel to:', _text)

    def test_snapshot_builder_initializes_missing_context_user_data(self):
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
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': ['forest_wolf'], 'services': []}
        context = SimpleNamespace()
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[]),
            patch('handlers.location.list_location_available_spawn_instances', return_value=[]),
            patch('handlers.location.list_location_active_pve_encounters', return_value=[]),
            patch('handlers.location.build_location_gather_source_profiles', return_value=[]),
            patch('handlers.location.build_hunt_contract_progress_line', return_value=None),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            _build_location_message_with_snapshot(context, player, location, pvp_only_view=False)

        self.assertIsInstance(context.user_data, dict)
        self.assertIn(LOCATION_ACTION_SNAPSHOT_KEY, context.user_data)

    def test_snapshot_tags_are_monotonic_per_user_context(self):
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
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': ['forest_wolf'], 'services': []}
        context = SimpleNamespace(user_data={})
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[]),
            patch('handlers.location.list_location_available_spawn_instances', return_value=[]),
            patch('handlers.location.list_location_active_pve_encounters', return_value=[]),
            patch('handlers.location.build_location_gather_source_profiles', return_value=[]),
            patch('handlers.location.build_hunt_contract_progress_line', return_value=None),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            _build_location_message_with_snapshot(context, player, location, pvp_only_view=False)
            first_snapshot = context.user_data[LOCATION_ACTION_SNAPSHOT_KEY]
            _build_location_message_with_snapshot(context, player, location, pvp_only_view=False)
            second_snapshot = context.user_data[LOCATION_ACTION_SNAPSHOT_KEY]

        self.assertEqual(first_snapshot['snapshot_tag'], 's1')
        self.assertEqual(second_snapshot['snapshot_tag'], 's2')

    def test_location_message_shows_compact_active_contract_progress_line(self):
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
        location = {'id': 'village', 'safe': True, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': ['shop']}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Village'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[]),
            patch('handlers.location.list_location_available_spawn_instances', return_value=[]),
            patch('handlers.location.list_location_active_pve_encounters', return_value=[]),
            patch('handlers.location.build_location_gather_source_profiles', return_value=[]),
            patch('handlers.location.build_hunt_contract_progress_line', return_value='📌 Contract: Hunt Wolves (2/5, in progress)'),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            text, _keyboard, _snapshot = build_location_message(player, location, include_action_map=True)

        self.assertIn('📌 Contract: Hunt Wolves (2/5, in progress)', text)

    def test_pvp_only_view_hides_active_contract_progress_line(self):
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
        location = {'id': 'village', 'safe': True, 'level_min': 1, 'level_max': 30, 'mobs': [], 'services': ['shop']}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Village'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[]),
            patch('handlers.location.list_location_available_spawn_instances', return_value=[]),
            patch('handlers.location.list_location_active_pve_encounters', return_value=[]),
            patch('handlers.location.build_location_gather_source_profiles', return_value=[]),
            patch('handlers.location.build_hunt_contract_progress_line', return_value='📌 Contract: Hunt Wolves (2/5, in progress)') as progress_mock,
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            text, _keyboard, _snapshot = build_location_message(
                player,
                location,
                include_action_map=True,
                pvp_only_view=True,
            )

        progress_mock.assert_not_called()
        self.assertNotIn('📌 Contract: Hunt Wolves (2/5, in progress)', text)

    async def test_current_snapshot_command_routes_to_existing_handler(self):
        update = _DummyUpdate('s1234 m1 fight')
        context = SimpleNamespace(user_data={
            LOCATION_ACTION_SNAPSHOT_KEY: {
                'player_id': 5001,
                'location_id': 'dark_forest',
                'snapshot_tag': 's1234',
                'actions': {'s1234 m1 fight': 'fight_spawn_spawn-dark_forest-forest_wolf'},
            },
        })
        with patch('handlers.location.get_player', return_value={'telegram_id': 5001, 'lang': 'en', 'location_id': 'dark_forest'}), \
             patch('handlers.location.handle_combat_buttons', new=AsyncMock()) as combat_mock:
            handled = await handle_location_action_text(update, context)

        self.assertTrue(handled)
        combat_mock.assert_awaited_once()

    async def test_old_command_from_snapshot1_is_stale_after_snapshot2(self):
        update = _DummyUpdate('s1 m1 fight')
        context = SimpleNamespace(user_data={
            LOCATION_ACTION_SNAPSHOT_KEY: {
                'player_id': 5001,
                'location_id': 'dark_forest',
                'snapshot_tag': 's2',
                'actions': {'s2 m1 fight': 'fight_spawn_spawn-dark_forest-forest_wolf-2'},
            },
        })
        with patch('handlers.location.get_player', return_value={'telegram_id': 5001, 'lang': 'en', 'location_id': 'dark_forest'}), \
             patch('handlers.location.handle_combat_buttons', new=AsyncMock()) as combat_mock, \
             patch('handlers.location.handle_location_buttons', new=AsyncMock()) as location_mock:
            handled = await handle_location_action_text(update, context)

        self.assertTrue(handled)
        update.message.reply_text.assert_awaited_once()
        combat_mock.assert_not_awaited()
        location_mock.assert_not_awaited()

    async def test_disappeared_encounter_command_stays_safe(self):
        update = _DummyUpdate('s2222 pe1 join')
        context = SimpleNamespace(user_data={
            LOCATION_ACTION_SNAPSHOT_KEY: {
                'player_id': 5001,
                'location_id': 'dark_forest',
                'snapshot_tag': 's2222',
                'actions': {'s2222 pe1 join': 'pve_join_pve-enc-missing'},
            },
        })
        query_answer = AsyncMock()
        with patch('handlers.location.get_player', return_value={'telegram_id': 5001, 'lang': 'en', 'location_id': 'dark_forest', 'in_battle': 0}), \
             patch('handlers.location.has_active_live_pvp_engagement', return_value=False), \
             patch('handlers.location.join_open_world_pve_encounter', return_value=(False, 'wrong_location')), \
             patch('handlers.location.build_pve_encounter_detail_message', return_value=('detail', None)), \
             patch('handlers.location._MessageActionQueryAdapter.answer', query_answer):
            handled = await handle_location_action_text(update, context)

        self.assertTrue(handled)
        query_answer.assert_awaited()

    async def test_service_text_command_routes_to_location_callback_handler(self):
        update = _DummyUpdate('s44 sv1 shop')
        context = SimpleNamespace(user_data={
            LOCATION_ACTION_SNAPSHOT_KEY: {
                'player_id': 5001,
                'location_id': 'village',
                'snapshot_tag': 's44',
                'actions': {'s44 sv1 shop': 'shop'},
            },
        })
        with patch('handlers.location.get_player', return_value={'telegram_id': 5001, 'lang': 'en', 'location_id': 'village'}), \
             patch('handlers.location.handle_location_buttons', new=AsyncMock()) as location_mock:
            handled = await handle_location_action_text(update, context)

        self.assertTrue(handled)
        location_mock.assert_awaited_once()

    def test_namespace_tokens_are_unique_between_entity_types(self):
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
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': ['forest_wolf'], 'services': ['shop']}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[{
                'id': 77,
                'attacker_name': 'A',
                'defender_name': 'B',
                'seconds_until_start': 30,
                'initiator_side_count': 1,
                'defender_side_count': 1,
            }]),
            patch('handlers.location.list_location_available_spawn_instances', return_value=[
                {'spawn_instance_id': 'spawn-dark_forest-forest_wolf', 'mob_id': 'forest_wolf'},
            ]),
            patch('handlers.location.list_location_active_pve_encounters', return_value=[{
                'encounter_id': 'pve-1',
                'mob_id': 'forest_wolf',
                'participant_player_ids': [],
                'participant_count': 1,
                'joinable': True,
            }]),
            patch('handlers.location.get_mob', return_value={'id': 'forest_wolf', 'level': 2, 'aggressive': False}),
            patch('handlers.location.build_location_gather_source_profiles', return_value=[]),
            patch('handlers.location.can_join_open_world_pve_encounter', return_value=(True, None)),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = [
                {'telegram_id': 9001, 'name': 'Nearby', 'level': 8},
            ]
            conn_mock.return_value.close.return_value = None
            text, _keyboard, snapshot = build_location_message(player, location, include_action_map=True)

        commands = list(snapshot['actions'].keys())
        self.assertTrue(any(re.search(r'\sp1 attack$', cmd) for cmd in commands))
        self.assertFalse(any(re.search(r'\sm\d+\sfight$', cmd) for cmd in commands))
        self.assertFalse(any(re.search(r'\spv\d+\sview$', cmd) for cmd in commands))
        self.assertFalse(any(re.search(r'\spe\d+\sview$', cmd) for cmd in commands))
        self.assertIn('/enc 77', text)
        self.assertIn('/enc pve-1', text)

    def test_location_text_marks_elite_and_rare_spawn_profiles(self):
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
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': ['forest_wolf'], 'services': []}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Forest'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[]),
            patch('handlers.location.list_location_active_pve_encounters', return_value=[{
                'encounter_id': 'pve-elite',
                'mob_id': 'forest_wolf',
                'spawn_profile': 'elite',
                'participant_player_ids': [],
                'participant_count': 1,
                'joinable': True,
            }]),
            patch('handlers.location.list_location_available_spawn_instances', return_value=[
                {'spawn_instance_id': 'spawn-dark_forest-forest_wolf-elite', 'mob_id': 'forest_wolf', 'spawn_profile': 'elite'},
                {'spawn_instance_id': 'spawn-dark_forest-forest_wolf-rare', 'mob_id': 'forest_wolf', 'spawn_profile': 'rare'},
            ]),
            patch('handlers.location.get_mob', return_value={'id': 'forest_wolf', 'level': 2, 'aggressive': False}),
            patch('handlers.location.build_location_gather_source_profiles', return_value=[]),
            patch('handlers.location.can_join_open_world_pve_encounter', return_value=(True, None)),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            text, _keyboard, snapshot = build_location_message(player, location, include_action_map=True)

        self.assertIn('[Elite]', text)
        self.assertIn('[Rare]', text)
        self.assertNotIn('m1', text)
        self.assertFalse(any(' m' in cmd and cmd.endswith('fight') for cmd in snapshot['actions']))
        callbacks = [button.callback_data for row in _keyboard.inline_keyboard for button in row]
        self.assertIn('fight_spawn_spawn-dark_forest-forest_wolf-elite', callbacks)
        self.assertIn('fight_spawn_spawn-dark_forest-forest_wolf-rare', callbacks)

    def test_location_text_localizes_special_spawn_key_and_keeps_same_mob_targets_distinguishable(self):
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
        location = {'id': 'old_mines', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': ['stone_golem'], 'services': []}
        with (
            patch('handlers.location.get_connection') as conn_mock,
            patch('handlers.location.get_connected_locations', return_value=[]),
            patch('handlers.location.get_location_name', return_value='Old Mines'),
            patch('handlers.location.get_location_desc', return_value='desc'),
            patch('handlers.location.get_pending_player_engagement', return_value=None),
            patch('handlers.location.get_pending_reinforcement_engagement_for_player', return_value=None),
            patch('handlers.location.get_pending_location_encounters', return_value=[]),
            patch('handlers.location.list_location_active_pve_encounters', return_value=[{
                'encounter_id': 'pve-amber',
                'mob_id': 'stone_golem',
                'spawn_profile': 'elite',
                'special_spawn_key': 'amber_colossus',
                'special_spawn_name': '',
                'participant_player_ids': [],
                'participant_count': 1,
                'joinable': True,
            }]),
            patch('handlers.location.list_location_available_spawn_instances', return_value=[
                {'spawn_instance_id': 'spawn-old_mines-stone_golem', 'mob_id': 'stone_golem', 'spawn_profile': 'normal'},
                {'spawn_instance_id': 'spawn-old_mines-stone_golem-special-amber_colossus', 'mob_id': 'stone_golem', 'spawn_profile': 'elite', 'special_spawn_key': 'amber_colossus', 'special_spawn_name': None},
            ]),
            patch('handlers.location.get_mob', return_value={'id': 'stone_golem', 'level': 8, 'aggressive': False}),
            patch('handlers.location.build_location_gather_source_profiles', return_value=[]),
            patch('handlers.location.can_join_open_world_pve_encounter', return_value=(True, None)),
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            text, _keyboard, snapshot = build_location_message(player, location, include_action_map=True)

        self.assertIn('[Elite] 🟠 Amber Colossus', text)
        self.assertIn('Stone Golem', text)
        callbacks = [button.callback_data for row in _keyboard.inline_keyboard for button in row]
        self.assertIn('fight_spawn_spawn-old_mines-stone_golem', callbacks)
        self.assertIn('fight_spawn_spawn-old_mines-stone_golem-special-amber_colossus', callbacks)


if __name__ == '__main__':
    unittest.main()
