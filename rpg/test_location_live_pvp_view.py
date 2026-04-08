import unittest
from unittest.mock import AsyncMock, patch

from handlers.location import location_command


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
