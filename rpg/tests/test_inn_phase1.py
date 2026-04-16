import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import database
from database import get_connection, init_db
from game.locations import get_location
from handlers.location import INN_REST_COST_GOLD, handle_location_buttons
from handlers.location import build_inn_message


class InnPhase1Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self._tmpdir.name, 'test_game.db')
        init_db()
        conn = get_connection()
        conn.execute(
            '''
            INSERT INTO players (
                telegram_id, username, name, level, exp, hp, max_hp, mana, max_mana, gold,
                strength, agility, intuition, vitality, wisdom, luck, stat_points, location_id, in_battle, lang
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (9101, 'innuser', 'Inn User', 10, 0, 80, 120, 30, 50, 100, 5, 5, 5, 5, 5, 5, 0, 'village', 0, 'en'),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    @staticmethod
    def _build_update(data: str) -> tuple[SimpleNamespace, SimpleNamespace]:
        query = SimpleNamespace(
            data=data,
            from_user=SimpleNamespace(id=9101),
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(user_data={})
        return update, context

    async def test_safe_location_with_inn_service_opens_inn_screen(self):
        update, context = self._build_update('inn')
        await handle_location_buttons(update, context)
        update.callback_query.answer.assert_awaited()
        update.callback_query.edit_message_text.assert_awaited_once()
        rendered = update.callback_query.edit_message_text.await_args.args[0]
        self.assertIn('Tavern', rendered)
        self.assertIn('Rest cost', rendered)

    async def test_inn_open_is_blocked_when_location_is_unsafe_even_if_service_listed(self):
        update, context = self._build_update('inn')
        with patch('handlers.location.get_location', return_value={'id': 'dark_forest', 'safe': False, 'services': ['inn']}):
            await handle_location_buttons(update, context)
        update.callback_query.answer.assert_awaited_once()
        update.callback_query.edit_message_text.assert_not_awaited()

    async def test_rest_restores_hp_mana_and_charges_gold_once(self):
        update, context = self._build_update('inn_rest')
        await handle_location_buttons(update, context)

        conn = get_connection()
        row = conn.execute('SELECT hp, mana, gold FROM players WHERE telegram_id=?', (9101,)).fetchone()
        conn.close()
        self.assertEqual(int(row['hp']), 120)
        self.assertEqual(int(row['mana']), 50)
        self.assertEqual(int(row['gold']), 100 - INN_REST_COST_GOLD)
        update.callback_query.edit_message_text.assert_awaited_once()

    async def test_rest_blocks_when_not_enough_gold(self):
        conn = get_connection()
        conn.execute('UPDATE players SET gold=? WHERE telegram_id=?', (INN_REST_COST_GOLD - 1, 9101))
        conn.commit()
        conn.close()

        update, context = self._build_update('inn_rest')
        await handle_location_buttons(update, context)

        conn = get_connection()
        row = conn.execute('SELECT hp, mana, gold FROM players WHERE telegram_id=?', (9101,)).fetchone()
        conn.close()
        self.assertEqual(int(row['hp']), 80)
        self.assertEqual(int(row['mana']), 30)
        self.assertEqual(int(row['gold']), INN_REST_COST_GOLD - 1)
        update.callback_query.edit_message_text.assert_not_awaited()

    async def test_rest_when_already_full_does_not_charge_gold(self):
        conn = get_connection()
        conn.execute('UPDATE players SET hp=max_hp, mana=max_mana WHERE telegram_id=?', (9101,))
        conn.commit()
        conn.close()

        update, context = self._build_update('inn_rest')
        await handle_location_buttons(update, context)

        conn = get_connection()
        row = conn.execute('SELECT hp, mana, gold FROM players WHERE telegram_id=?', (9101,)).fetchone()
        conn.close()
        self.assertEqual(int(row['hp']), 120)
        self.assertEqual(int(row['mana']), 50)
        self.assertEqual(int(row['gold']), 100)
        update.callback_query.edit_message_text.assert_not_awaited()

    async def test_in_battle_blocks_rest_via_existing_gate(self):
        conn = get_connection()
        conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=?', (9101,))
        conn.commit()
        conn.close()

        update, context = self._build_update('inn_rest')
        await handle_location_buttons(update, context)
        update.callback_query.answer.assert_awaited_once()
        update.callback_query.edit_message_text.assert_not_awaited()

    async def test_inn_back_returns_to_location_view(self):
        update, context = self._build_update('inn_back')
        await handle_location_buttons(update, context)
        update.callback_query.answer.assert_awaited_once()
        update.callback_query.edit_message_text.assert_awaited_once()
        rendered = update.callback_query.edit_message_text.await_args.args[0]
        self.assertIn('Quick actions', rendered)

    def test_inn_message_title_is_location_aware_for_outpost(self):
        location = get_location('frontier_outpost')
        self.assertIsNotNone(location)
        assert location is not None
        player = {
            'telegram_id': 9101,
            'lang': 'en',
            'hp': 100,
            'max_hp': 120,
            'mana': 40,
            'max_mana': 50,
        }
        text, _keyboard = build_inn_message(player, location)
        self.assertIn('Tavern — 🏕️ Frontier Outpost', text)
