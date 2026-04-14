import re
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.location import (
    LOCATION_ACTION_SNAPSHOT_KEY,
    _build_location_message_with_snapshot,
    build_location_message,
    handle_location_action_text,
)


class _DummyMessage:
    def __init__(self, text: str):
        self.text = text
        self.reply_text = AsyncMock()


class _DummyUpdate:
    def __init__(self, text: str, user_id: int = 5001):
        self.message = _DummyMessage(text)
        self.effective_user = SimpleNamespace(id=user_id)


class LocationActionTokenTests(unittest.IsolatedAsyncioTestCase):
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
        ):
            conn_mock.return_value.execute.return_value.fetchall.return_value = []
            conn_mock.return_value.close.return_value = None
            _build_location_message_with_snapshot(context, player, location, pvp_only_view=False)
            first_snapshot = context.user_data[LOCATION_ACTION_SNAPSHOT_KEY]
            _build_location_message_with_snapshot(context, player, location, pvp_only_view=False)
            second_snapshot = context.user_data[LOCATION_ACTION_SNAPSHOT_KEY]

        self.assertEqual(first_snapshot['snapshot_tag'], 's1')
        self.assertEqual(second_snapshot['snapshot_tag'], 's2')

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
        location = {'id': 'dark_forest', 'safe': False, 'level_min': 1, 'level_max': 30, 'mobs': ['forest_wolf'], 'services': []}
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
        self.assertTrue(any(re.search(r'\sm1 fight$', cmd) for cmd in commands))
        self.assertTrue(any(re.search(r'\spv1 view$', cmd) for cmd in commands))
        self.assertTrue(any(re.search(r'\spe1 view$', cmd) for cmd in commands))
        self.assertIn('pv1', text)
        self.assertIn('pe1', text)


if __name__ == '__main__':
    unittest.main()
