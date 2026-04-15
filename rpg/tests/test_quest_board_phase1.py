import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import database
from database import get_connection, init_db
from game.quest_board import (
    accept_hunt_contract,
    claim_completed_hunt_contract,
    get_player_hunt_contract_state,
    register_hunt_kill_progress,
)
from handlers.location import handle_location_buttons


class QuestBoardPhase1Tests(unittest.IsolatedAsyncioTestCase):
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
            (8101, 'quester', 'Quester', 10, 0, 120, 120, 50, 50, 100, 5, 5, 5, 5, 5, 5, 0, 'village'),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    async def test_player_can_open_quest_board_and_accept_contract(self):
        query = SimpleNamespace(
            data='quest_board_accept_hunt_forest_wolves',
            from_user=SimpleNamespace(id=8101),
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(user_data={})

        with patch('handlers.location.get_location', return_value={'id': 'village', 'services': ['shop', 'quest_board']}):
            await handle_location_buttons(update, context)

        state = get_player_hunt_contract_state(8101)
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state['contract_key'], 'hunt_forest_wolves')
        self.assertEqual(state['status'], 'active')
        query.answer.assert_awaited()
        query.edit_message_text.assert_awaited()

    def test_single_slot_policy_rejects_second_active_contract(self):
        ok, reason = accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        self.assertTrue(ok)
        self.assertEqual(reason, 'accepted')

        ok2, reason2 = accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_elite_boars')
        self.assertFalse(ok2)
        self.assertEqual(reason2, 'already_active')

    def test_matching_and_non_matching_kills_update_progress_correctly(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')

        non_match = register_hunt_kill_progress(player_id=8101, mob_id='forest_boar')
        self.assertFalse(non_match['updated'])

        for _ in range(4):
            result = register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', spawn_profile='normal')
            self.assertTrue(result['updated'])
            self.assertFalse(result['completed_now'])

        final = register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', spawn_profile='normal')
        self.assertTrue(final['updated'])
        self.assertTrue(final['completed_now'])

        state = get_player_hunt_contract_state(8101)
        self.assertEqual(state['progress_kills'], 5)
        self.assertEqual(state['status'], 'completed')

    def test_elite_and_special_filters_match_truthfully(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_elite_boars')

        normal_kill = register_hunt_kill_progress(player_id=8101, mob_id='forest_boar', spawn_profile='normal')
        self.assertFalse(normal_kill['updated'])
        elite_kill = register_hunt_kill_progress(player_id=8101, mob_id='forest_boar', spawn_profile='elite')
        self.assertTrue(elite_kill['updated'])
        register_hunt_kill_progress(player_id=8101, mob_id='forest_boar', spawn_profile='elite')
        claim_completed_hunt_contract(player_id=8101, location_id='village')

        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_greyfang')
        wrong_named = register_hunt_kill_progress(
            player_id=8101,
            mob_id='forest_wolf',
            spawn_profile='rare',
            special_spawn_key='other_wolf',
        )
        self.assertFalse(wrong_named['updated'])
        correct_named = register_hunt_kill_progress(
            player_id=8101,
            mob_id='forest_wolf',
            spawn_profile='rare',
            special_spawn_key='greyfang',
        )
        self.assertTrue(correct_named['updated'])
        self.assertTrue(correct_named['completed_now'])

    def test_claim_is_one_time_and_keeps_state_claimed(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        for _ in range(5):
            register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf')

        ok, reason, reward = claim_completed_hunt_contract(player_id=8101, location_id='village')
        self.assertTrue(ok)
        self.assertEqual(reason, 'claimed')
        self.assertIsNotNone(reward)

        ok2, reason2, _ = claim_completed_hunt_contract(player_id=8101, location_id='village')
        self.assertFalse(ok2)
        self.assertEqual(reason2, 'already_claimed')

        state = get_player_hunt_contract_state(8101)
        self.assertEqual(state['status'], 'claimed')

        conn = get_connection()
        player = conn.execute('SELECT exp, gold FROM players WHERE telegram_id=?', (8101,)).fetchone()
        conn.close()
        self.assertGreaterEqual(int(player['exp']), 70)
        self.assertGreaterEqual(int(player['gold']), 130)
