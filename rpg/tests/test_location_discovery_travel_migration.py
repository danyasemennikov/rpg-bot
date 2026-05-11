import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import database
from database import (
    create_player,
    ensure_player_location_discovered,
    get_connection,
    get_player,
    init_db,
    is_location_discovered,
    list_discovered_locations,
)
from game.locations import get_connected_locations, get_location, get_location_neighbors
from handlers.location import _build_location_message_with_snapshot, handle_location_buttons


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


    async def _travel_for_test(self, *, start_location_id: str, target_location_id: str):
        def _discard_task(coro):
            coro.close()

        conn = get_connection()
        conn.execute(
            'UPDATE players SET location_id=? WHERE telegram_id=?',
            (start_location_id, 9101),
        )
        conn.commit()
        conn.close()

        query = SimpleNamespace(
            data=f'goto_{target_location_id}',
            from_user=SimpleNamespace(id=9101),
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            message=SimpleNamespace(message_id=201),
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

        return query

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

    def test_capital_city_has_wave_a_radial_travel_options(self):
        expected = [
            'westwild_n1',
            'frostspine_n1',
            'ashen_n1',
            'sunscar_n1',
            'mireveil_n1',
            'south_coast_shore',
        ]
        self.assertEqual(get_location_neighbors('capital_city'), expected)
        self.assertEqual(
            [location['id'] for location in get_connected_locations('capital_city')],
            expected,
        )

    def test_shell_nodes_return_to_capital_without_deep_route_rollout(self):
        self.assertEqual(get_location_neighbors('westwild_n1'), ['capital_city'])
        self.assertEqual(get_location_neighbors('ashen_n1'), ['capital_city'])
        self.assertEqual(get_location_neighbors('sunscar_n1'), ['capital_city'])
        self.assertEqual(get_location_neighbors('mireveil_n1'), ['capital_city'])
        self.assertEqual(get_location_neighbors('south_coast_shore'), ['capital_city'])

    def test_frostspine_n1_exposes_old_mine_stub(self):
        self.assertEqual(get_location_neighbors('frostspine_n1'), ['capital_city', 'old_mine_entrance'])
        self.assertEqual(get_location_neighbors('old_mine_entrance'), ['frostspine_n1'])

    def test_capital_city_location_buttons_use_shell_nodes(self):
        player = dict(get_player(9101))
        player['location_id'] = 'capital_city'
        location = get_location('capital_city')
        text, keyboard = _build_location_message_with_snapshot(
            SimpleNamespace(user_data={}, application=SimpleNamespace(create_task=lambda coro: coro.close())),
            player,
            location,
        )

        callbacks = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
            if button.callback_data.startswith('goto_')
        ]
        self.assertEqual(
            callbacks,
            [
                'goto_westwild_n1',
                'goto_frostspine_n1',
                'goto_ashen_n1',
                'goto_sunscar_n1',
                'goto_mireveil_n1',
                'goto_south_coast_shore',
            ],
        )
        self.assertIn('Travel to:', text)

    def test_migrated_canonical_nodes_have_compatibility_egress(self):
        self.assertEqual(get_location_neighbors('westwild_n4'), ['hub_westwild'])
        self.assertEqual(get_location_neighbors('westwild_n5'), ['hub_westwild'])
        self.assertEqual(get_location_neighbors('westwild_n6'), ['hub_westwild'])
        self.assertEqual(get_location_neighbors('frostspine_n2'), ['hub_frostspine'])
        self.assertEqual(get_location_neighbors('sunscar_n8'), ['hub_sunscar'])
        self.assertEqual(get_location_neighbors('mireveil_n8'), ['hub_mireveil'])
        self.assertEqual(get_location_neighbors('hub_westwild'), ['capital_city'])
        self.assertEqual(get_location_neighbors('hub_frostspine'), ['frostspine_n1'])
        self.assertEqual(get_location_neighbors('old_mine_entrance'), ['frostspine_n1'])

    def test_legacy_travel_overlay_survives_for_existing_old_slice_ids(self):
        self.assertEqual(get_location_neighbors('village'), ['dark_forest', 'old_mines', 'frontier_outpost'])
        self.assertEqual(
            [location['id'] for location in get_connected_locations('village')],
            ['dark_forest', 'old_mines', 'frontier_outpost'],
        )

    def test_new_player_spawns_at_capital_city_and_discovers_it(self):
        create_player(
            9102,
            'newbie',
            'Newbie',
            {'strength': 1, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1},
        )

        player = get_player(9102)
        self.assertEqual(player['location_id'], 'capital_city')
        self.assertTrue(is_location_discovered(9102, 'capital_city'))

    async def test_handle_location_buttons_accepts_compatibility_egress_moves(self):
        moves = [
            ('westwild_n5', 'hub_westwild'),
            ('westwild_n6', 'hub_westwild'),
            ('frostspine_n2', 'hub_frostspine'),
            ('sunscar_n8', 'hub_sunscar'),
            ('mireveil_n8', 'hub_mireveil'),
            ('hub_westwild', 'capital_city'),
            ('hub_frostspine', 'frostspine_n1'),
            ('old_mine_entrance', 'frostspine_n1'),
        ]
        for start_location_id, target_location_id in moves:
            with self.subTest(start=start_location_id, target=target_location_id):
                query = await self._travel_for_test(
                    start_location_id=start_location_id,
                    target_location_id=target_location_id,
                )
                query.answer.assert_awaited()

                player = get_player(9101)
                self.assertEqual(player['location_id'], target_location_id)
                self.assertTrue(is_location_discovered(9101, target_location_id))

    async def test_successful_arrival_marks_destination_discovered_in_canonical_form(self):
        def _discard_task(coro):
            coro.close()

        query = SimpleNamespace(
            data='goto_westwild_n1',
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

        conn = get_connection()
        conn.execute('UPDATE players SET location_id=? WHERE telegram_id=?', ('capital_city', 9101))
        conn.commit()
        conn.close()

        with (
            patch('handlers.location.asyncio.sleep', new=AsyncMock()),
            patch('handlers.location.is_in_battle', return_value=False),
            patch('handlers.location.is_pvp_mobility_blocked', return_value=False),
            patch('handlers.location._build_location_message_with_snapshot', return_value=('ok', None)),
            patch('handlers.location.clear_respawn_protection_on_dangerous_reentry', return_value=None),
        ):
            await handle_location_buttons(update, context)

        self.assertTrue(is_location_discovered(9101, 'westwild_n1'))

    async def test_failed_movement_does_not_mark_discovery(self):
        def _discard_task(coro):
            coro.close()

        query = SimpleNamespace(
            data='goto_westwild_n1',
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

        conn = get_connection()
        conn.execute('UPDATE players SET location_id=? WHERE telegram_id=?', ('capital_city', 9101))
        conn.commit()
        conn.close()

        with (
            patch('handlers.location.is_in_battle', return_value=False),
            patch('handlers.location.is_pvp_mobility_blocked', return_value=True),
        ):
            await handle_location_buttons(update, context)

        self.assertFalse(is_location_discovered(9101, 'westwild_n1'))


if __name__ == '__main__':
    unittest.main()
