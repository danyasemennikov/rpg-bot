import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import database
from database import get_connection, init_db
from game.quest_board import (
    HUNTER_RANK_THRESHOLDS,
    _ensure_player_hunt_contract_table,
    accept_hunt_contract,
    abandon_hunt_contract,
    build_hunt_contract_progress_line,
    claim_completed_hunt_contract,
    get_player_hunt_contract_state,
    get_player_hunter_progress,
    list_hunt_contracts_for_location,
    list_hunt_contracts_for_player,
    register_hunt_kill_progress,
    resolve_hunter_rank,
)
from handlers.location import build_quest_board_message
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
        conn.execute(
            '''
            INSERT OR REPLACE INTO items (
                item_id, name, item_type, rarity, req_level,
                req_strength, req_agility, req_intuition, req_wisdom,
                buy_price, stat_bonus_json
            ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 0, '{}')
            ''',
            ('wolf_fang', 'Wolf Fang', 'material', 'common', 1),
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

    async def test_player_can_abandon_active_contract_from_board_callback(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        query = SimpleNamespace(
            data='quest_board_abandon',
            from_user=SimpleNamespace(id=8101),
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(user_data={})

        with patch('handlers.location.get_location', return_value={'id': 'village', 'services': ['shop', 'quest_board']}):
            await handle_location_buttons(update, context)

        self.assertIsNone(get_player_hunt_contract_state(8101))
        query.answer.assert_awaited()
        query.edit_message_text.assert_awaited()

    def test_board_renders_claim_and_abandon_buttons_truthfully(self):
        player = {'telegram_id': 8101, 'lang': 'en'}
        location = {'id': 'village'}

        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        _text_active, keyboard_active = build_quest_board_message(player, location)
        active_callbacks = {btn.callback_data for row in keyboard_active.inline_keyboard for btn in row}
        self.assertIn('quest_board_abandon', active_callbacks)
        self.assertNotIn('quest_board_claim', active_callbacks)

        for _ in range(5):
            register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf')
        _text_ready, keyboard_ready = build_quest_board_message(player, location)
        ready_callbacks = {btn.callback_data for row in keyboard_ready.inline_keyboard for btn in row}
        self.assertIn('quest_board_claim', ready_callbacks)
        self.assertNotIn('quest_board_abandon', ready_callbacks)

    def test_single_slot_policy_rejects_second_active_contract(self):
        ok, reason = accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        self.assertTrue(ok)
        self.assertEqual(reason, 'accepted')

        ok2, reason2 = accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_elite_boars')
        self.assertFalse(ok2)
        self.assertEqual(reason2, 'already_active')

    def test_accept_uses_connection_local_gate_without_global_state_read_call(self):
        with patch('game.quest_board.get_player_hunt_contract_state') as state_mock:
            ok, reason = accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        self.assertTrue(ok)
        self.assertEqual(reason, 'accepted')
        state_mock.assert_not_called()

    def test_curated_contract_set_is_broader_than_phase1_baseline(self):
        contracts = list_hunt_contracts_for_location('village')
        keys = {contract.contract_key for contract in contracts}
        self.assertGreaterEqual(len(contracts), 6)
        self.assertIn('hunt_forest_wolves', keys)
        self.assertIn('hunt_elite_boars', keys)
        self.assertIn('hunt_greyfang', keys)
        self.assertIn('hunt_forest_spiders', keys)
        self.assertIn('hunt_mine_goblins', keys)
        self.assertIn('hunt_amber_golem', keys)

    def test_new_player_has_baseline_hunter_rank(self):
        progress = get_player_hunter_progress(8101)
        self.assertEqual(progress['hunter_points'], 0)
        self.assertEqual(progress['current_rank'], 'novice')
        self.assertEqual(resolve_hunter_rank(0), 'novice')
        self.assertEqual(HUNTER_RANK_THRESHOLDS[0][0], 'novice')

    def test_hunter_progression_increases_on_successful_claim(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        for _ in range(5):
            register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf')

        before = get_player_hunter_progress(8101)
        ok, reason, reward = claim_completed_hunt_contract(player_id=8101, location_id='village')
        self.assertTrue(ok)
        self.assertEqual(reason, 'claimed')
        self.assertIsNotNone(reward)
        assert reward is not None
        hunter_result = reward['hunter_progress']
        self.assertEqual(hunter_result['points_gained'], 20)

        after = get_player_hunter_progress(8101)
        self.assertEqual(after['hunter_points'], before['hunter_points'] + 20)

    def test_rank_threshold_crossing_happens_after_points_gain(self):
        for _ in range(2):
            accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
            for _ in range(5):
                register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf')
            ok, reason, reward = claim_completed_hunt_contract(player_id=8101, location_id='village')
            self.assertTrue(ok)
            self.assertEqual(reason, 'claimed')
            self.assertIsNotNone(reward)

        progress = get_player_hunter_progress(8101)
        self.assertEqual(progress['hunter_points'], 40)
        self.assertEqual(progress['current_rank'], 'tracker')

    def test_locked_contracts_cannot_be_accepted_before_rank_unlock(self):
        ok, reason = accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_elite_boars')
        self.assertFalse(ok)
        self.assertEqual(reason, 'rank_locked')

    def test_locked_contract_becomes_available_after_progression(self):
        for _ in range(2):
            accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
            for _ in range(5):
                register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf')
            claim_completed_hunt_contract(player_id=8101, location_id='village')

        split = list_hunt_contracts_for_player(location_id='village', player_id=8101, lang='en')
        available_keys = {contract.contract_key for contract in split['available']}
        locked_keys = {row['contract'].contract_key for row in split['locked']}
        self.assertIn('hunt_elite_boars', available_keys)
        self.assertNotIn('hunt_elite_boars', locked_keys)

    def test_board_ui_shows_hunter_progress_and_locked_reason(self):
        player = {'telegram_id': 8101, 'lang': 'en'}
        location = {'id': 'village'}
        text, _keyboard = build_quest_board_message(player, location)
        self.assertIn('Hunter rank:', text)
        self.assertIn('Locked contracts:', text)
        self.assertIn('requires rank Tracker', text)

    def test_claim_atomicity_keeps_hunter_progress_unchanged_on_failure(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_greyfang')
        register_hunt_kill_progress(
            player_id=8101,
            mob_id='forest_wolf',
            spawn_profile='rare',
            special_spawn_key='greyfang',
        )
        with patch('game.quest_board.grant_item_to_player', side_effect=RuntimeError('boom')):
            ok, reason, reward = claim_completed_hunt_contract(player_id=8101, location_id='village')
        self.assertFalse(ok)
        self.assertEqual(reason, 'reward_delivery_failed')
        self.assertIsNone(reward)
        self.assertEqual(get_player_hunter_progress(8101)['hunter_points'], 0)
        state = get_player_hunt_contract_state(8101)
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state['status'], 'completed')

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

    def test_register_progress_hot_path_does_not_invoke_schema_ensure(self):
        _ensure_player_hunt_contract_table()
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        with patch('game.quest_board._ensure_player_hunt_contract_table') as ensure_mock:
            result = register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf')
        ensure_mock.assert_not_called()
        self.assertTrue(result['updated'])

    def test_state_read_and_location_line_are_safe_without_schema_init(self):
        with patch('game.quest_board._ensure_player_hunt_contract_table') as ensure_mock:
            state = get_player_hunt_contract_state(8101)
            line = build_hunt_contract_progress_line(player_id=8101, lang='en')
        ensure_mock.assert_not_called()
        self.assertIsNone(state)
        self.assertIsNone(line)

    def test_player_can_abandon_active_contract_and_accept_new_one(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf')

        ok, reason = abandon_hunt_contract(player_id=8101)
        self.assertTrue(ok)
        self.assertEqual(reason, 'abandoned')
        self.assertIsNone(get_player_hunt_contract_state(8101))

        ok2, reason2 = accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_spiders')
        self.assertTrue(ok2)
        self.assertEqual(reason2, 'accepted')
        state = get_player_hunt_contract_state(8101)
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state['contract_key'], 'hunt_forest_spiders')

    def test_completed_contract_cannot_be_abandoned_until_claimed(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        for _ in range(5):
            register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf')

        ok, reason = abandon_hunt_contract(player_id=8101)
        self.assertFalse(ok)
        self.assertEqual(reason, 'completed_must_claim')

    def test_abandon_uses_connection_local_gate_without_global_state_read_call(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        with patch('game.quest_board.get_player_hunt_contract_state') as state_mock:
            ok, reason = abandon_hunt_contract(player_id=8101)
        self.assertTrue(ok)
        self.assertEqual(reason, 'abandoned')
        state_mock.assert_not_called()

    def test_elite_and_special_filters_match_truthfully(self):
        for _ in range(2):
            accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
            for _ in range(5):
                register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf')
            claim_completed_hunt_contract(player_id=8101, location_id='village')

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
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_greyfang')
        register_hunt_kill_progress(
            player_id=8101,
            mob_id='forest_wolf',
            spawn_profile='rare',
            special_spawn_key='greyfang',
        )

        ok, reason, reward = claim_completed_hunt_contract(player_id=8101, location_id='village')
        self.assertTrue(ok)
        self.assertEqual(reason, 'claimed')
        self.assertIsNotNone(reward)
        assert reward is not None
        self.assertEqual(reward.get('bonus_item', {}).get('item_id'), 'wolf_fang')
        self.assertEqual(reward.get('bonus_item', {}).get('quantity'), 2)

        ok2, reason2, _ = claim_completed_hunt_contract(player_id=8101, location_id='village')
        self.assertFalse(ok2)
        self.assertEqual(reason2, 'already_claimed')

        state = get_player_hunt_contract_state(8101)
        self.assertEqual(state['status'], 'claimed')

        conn = get_connection()
        player = conn.execute('SELECT exp, gold FROM players WHERE telegram_id=?', (8101,)).fetchone()
        item_qty = conn.execute(
            'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (8101, 'wolf_fang'),
        ).fetchone()
        conn.close()
        self.assertGreaterEqual(int(player['exp']), 120)
        self.assertGreaterEqual(int(player['gold']), 170)
        self.assertIsNotNone(item_qty)
        assert item_qty is not None
        self.assertEqual(int(item_qty['quantity']), 2)

    def test_bonus_item_failure_rolls_back_claim_and_keeps_contract_completed(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_greyfang')
        register_hunt_kill_progress(
            player_id=8101,
            mob_id='forest_wolf',
            spawn_profile='rare',
            special_spawn_key='greyfang',
        )

        with (
            patch('game.quest_board.grant_item_to_player', side_effect=RuntimeError('grant failed')),
            patch('game.quest_board.logger.exception') as log_exception_mock,
        ):
            ok, reason, reward = claim_completed_hunt_contract(player_id=8101, location_id='village')

        self.assertFalse(ok)
        self.assertEqual(reason, 'reward_delivery_failed')
        self.assertIsNone(reward)
        log_exception_mock.assert_called_once()
        state = get_player_hunt_contract_state(8101)
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state['status'], 'completed')

    def test_claim_starts_transaction_before_completed_state_read(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        for _ in range(5):
            register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf')

        base_conn = get_connection()
        sql_log: list[str] = []

        class _LoggedConn:
            def execute(self, sql, params=()):
                sql_log.append(str(sql).strip().upper())
                return base_conn.execute(sql, params)

            def commit(self):
                return base_conn.commit()

            def rollback(self):
                return base_conn.rollback()

            def close(self):
                return base_conn.close()

        with (
            patch('game.quest_board._ensure_player_hunt_contract_table'),
            patch('game.quest_board.get_connection', return_value=_LoggedConn()),
        ):
            ok, reason, _reward = claim_completed_hunt_contract(player_id=8101, location_id='village')

        self.assertTrue(ok)
        self.assertEqual(reason, 'claimed')
        begin_index = next(i for i, sql in enumerate(sql_log) if sql.startswith('BEGIN IMMEDIATE'))
        state_read_index = next(i for i, sql in enumerate(sql_log) if 'FROM PLAYER_HUNT_CONTRACTS' in sql)
        self.assertLess(begin_index, state_read_index)
