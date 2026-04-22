import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import database
from database import (
    ensure_player_location_discovered,
    get_connection,
    init_db,
    is_location_discovered,
    list_discovered_locations,
)
from game.locations import get_connected_locations, get_location_neighbors
from handlers.location import handle_location_buttons


class LocationDiscoveryTravelMigrationTests(unittest.IsolatedAsyncioTestCase):
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'en')
            ''',
            (9101, 'traveler', 'Traveler', 15, 0, 120, 120, 50, 50, 100, 5, 5, 5, 5, 5, 5, 0, 'village'),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def test_capital_city_treated_as_discovered_by_default(self):
        self.assertTrue(is_location_discovered(9101, 'capital_city'))
        discovered = list_discovered_locations(9101)
        self.assertIn('capital_city', discovered)

    def test_discovery_always_stores_canonical_location_ids(self):
        ensure_player_location_discovered(9101, 'village')

        conn = get_connection()
        rows = conn.execute(
            'SELECT telegram_id, location_id FROM player_location_discovery WHERE telegram_id=?',
            (9101,),
        ).fetchall()
        conn.close()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['location_id'], 'hub_westwild')

    def test_repeated_discovery_write_does_not_duplicate_rows(self):
        ensure_player_location_discovered(9101, 'frontier_outpost')
        ensure_player_location_discovered(9101, 'hub_frostspine')

        conn = get_connection()
        count = conn.execute(
            '''
            SELECT COUNT(*) AS c
            FROM player_location_discovery
            WHERE telegram_id=? AND location_id=?
            ''',
            (9101, 'hub_frostspine'),
        ).fetchone()['c']
        conn.close()

        self.assertEqual(count, 1)

    def test_travel_neighbors_resolve_from_canonical_graph_for_legacy_ids(self):
        self.assertEqual(get_location_neighbors('village'), ['westwild_n5'])
        self.assertEqual(get_location_neighbors('hub_westwild'), ['westwild_n5'])
        self.assertEqual(
            [location['id'] for location in get_connected_locations('village')],
            ['westwild_n5'],
        )

    async def test_successful_arrival_marks_destination_discovered_in_canonical_form(self):
        def _discard_task(coro):
            coro.close()

        query = SimpleNamespace(
            data='goto_westwild_n5',
            from_user=SimpleNamespace(id=9101),
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            message=SimpleNamespace(message_id=101),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(
            user_data={},
            application=SimpleNamespace(create_task=_discard_task),
        )

        with (
            patch('handlers.location.asyncio.sleep', new=AsyncMock()),
            patch('handlers.location.is_in_battle', return_value=False),
            patch('handlers.location.is_pvp_mobility_blocked', return_value=False),
            patch('handlers.location._build_location_message_with_snapshot', return_value=('ok', None)),
            patch('handlers.location.clear_respawn_protection_on_dangerous_reentry', return_value=None),
        ):
            await handle_location_buttons(update, context)

        self.assertTrue(is_location_discovered(9101, 'westwild_n5'))

    async def test_failed_movement_does_not_mark_discovery(self):
        def _discard_task(coro):
            coro.close()

        query = SimpleNamespace(
            data='goto_westwild_n5',
            from_user=SimpleNamespace(id=9101),
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            message=SimpleNamespace(message_id=102),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(
            user_data={},
            application=SimpleNamespace(create_task=_discard_task),
        )

        with (
            patch('handlers.location.is_in_battle', return_value=False),
            patch('handlers.location.is_pvp_mobility_blocked', return_value=True),
        ):
            await handle_location_buttons(update, context)

        self.assertFalse(is_location_discovered(9101, 'westwild_n5'))


if __name__ == '__main__':
    unittest.main()
