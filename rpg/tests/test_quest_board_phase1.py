import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import database
from database import get_connection, init_db
from game.locations import get_location
from game.pve_live import list_location_available_spawn_instances
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
            register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='dark_forest')
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
        self.assertGreaterEqual(len(contracts), 4)
        self.assertIn('hunt_forest_wolves', keys)
        self.assertIn('hunt_elite_boars', keys)
        self.assertIn('hunt_greyfang', keys)
        self.assertIn('hunt_forest_spiders', keys)

    def test_frontier_outpost_board_has_distinct_curated_contracts(self):
        village_keys = {contract.contract_key for contract in list_hunt_contracts_for_location('village')}
        outpost_contracts = list_hunt_contracts_for_location('frontier_outpost')
        outpost_keys = {contract.contract_key for contract in outpost_contracts}
        self.assertGreaterEqual(len(outpost_contracts), 4)
        self.assertIn('hunt_mine_rats', outpost_keys)
        self.assertIn('hunt_cave_bats', outpost_keys)
        self.assertIn('hunt_mine_goblins', outpost_keys)
        self.assertIn('hunt_amber_golem', outpost_keys)
        self.assertTrue(outpost_keys.isdisjoint(village_keys))

    def test_frontier_contract_targets_match_old_mines_spawn_pool(self):
        outpost_contracts = list_hunt_contracts_for_location('frontier_outpost')
        old_mines_spawns = list_location_available_spawn_instances(location_id='old_mines')
        spawn_pairs = {
            (
                str(spawn.get('mob_id') or ''),
                str(spawn.get('special_spawn_key') or '').strip().lower(),
            )
            for spawn in old_mines_spawns
        }
        for contract in outpost_contracts:
            self.assertEqual(contract.target_location_ids, ('old_mines',))
            required_special = str(contract.special_spawn_key or '').strip().lower()
            self.assertIn((contract.target_mob_id, required_special), spawn_pairs)

    def test_old_mines_has_special_spawn_for_amber_golem_contract(self):
        old_mines = get_location('old_mines')
        self.assertIsNotNone(old_mines)
        assert old_mines is not None
        special_spawns = old_mines.get('world_special_spawns', [])
        amber_special = [
            row for row in special_spawns
            if row.get('mob_id') == 'stone_golem' and row.get('key') == 'amber_colossus'
        ]
        self.assertEqual(len(amber_special), 1)
        self.assertNotIn('name', amber_special[0])

    def test_accept_from_wrong_board_is_rejected_truthfully(self):
        ok, reason = accept_hunt_contract(
            player_id=8101,
            location_id='village',
            contract_key='hunt_mine_rats',
        )
        self.assertFalse(ok)
        self.assertEqual(reason, 'wrong_board')

    def test_new_player_has_baseline_hunter_rank(self):
        progress = get_player_hunter_progress(8101)
        self.assertEqual(progress['hunter_points'], 0)
        self.assertEqual(progress['current_rank'], 'novice')
        self.assertEqual(resolve_hunter_rank(0), 'novice')
        self.assertEqual(HUNTER_RANK_THRESHOLDS[0][0], 'novice')

    def test_hunter_progression_increases_on_successful_claim(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        for _ in range(5):
            register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='dark_forest')

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
                register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='dark_forest')
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
                register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='dark_forest')
            claim_completed_hunt_contract(player_id=8101, location_id='village')

        split = list_hunt_contracts_for_player(location_id='village', player_id=8101, lang='en')
        available_keys = {contract.contract_key for contract in split['available']}
        locked_keys = {row['contract'].contract_key for row in split['locked']}
        self.assertIn('hunt_elite_boars', available_keys)
        self.assertNotIn('hunt_elite_boars', locked_keys)

    def test_hunter_rank_unlocks_frontier_board_contracts(self):
        split_before = list_hunt_contracts_for_player(location_id='frontier_outpost', player_id=8101, lang='en')
        self.assertIn('hunt_mine_rats', {row['contract'].contract_key for row in split_before['locked']})

        for _ in range(2):
            accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
            for _ in range(5):
                register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='dark_forest')
            claim_completed_hunt_contract(player_id=8101, location_id='village')

        split_after = list_hunt_contracts_for_player(location_id='frontier_outpost', player_id=8101, lang='en')
        self.assertIn('hunt_mine_rats', {contract.contract_key for contract in split_after['available']})
        self.assertNotIn('hunt_mine_rats', {row['contract'].contract_key for row in split_after['locked']})

    def test_board_ui_shows_hunter_progress_and_locked_reason(self):
        player = {'telegram_id': 8101, 'lang': 'en'}
        location = {'id': 'village'}
        text, _keyboard = build_quest_board_message(player, location)
        self.assertIn('Hunter rank:', text)
        self.assertIn('Board: 🏘️ Ashen Village', text)
        self.assertIn('Locked contracts:', text)
        self.assertIn('requires rank Tracker', text)
        self.assertIn('board: 🏘️ Ashen Village', text)
        self.assertIn('place: 🌲 Dark Forest', text)

    def test_board_ui_shows_other_board_claim_hint_for_completed_contract(self):
        player = {'telegram_id': 8101, 'lang': 'en'}
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        for _ in range(5):
            register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='dark_forest')

        text, keyboard = build_quest_board_message(player, {'id': 'frontier_outpost'})
        callbacks = {btn.callback_data for row in keyboard.inline_keyboard for btn in row}
        self.assertIn('Claim board(s): 🏘️ Ashen Village', text)
        self.assertIn('Claim it at: 🏘️ Ashen Village', text)
        self.assertNotIn('quest_board_claim', callbacks)

    def test_completed_contract_claim_fails_on_wrong_board(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        for _ in range(5):
            register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='dark_forest')
        ok, reason, reward = claim_completed_hunt_contract(player_id=8101, location_id='frontier_outpost')
        self.assertFalse(ok)
        self.assertEqual(reason, 'wrong_board')
        self.assertIsNone(reward)

    def test_claim_atomicity_keeps_hunter_progress_unchanged_on_failure(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_greyfang')
        register_hunt_kill_progress(
            player_id=8101,
            mob_id='forest_wolf',
            location_id='dark_forest',
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

        non_match = register_hunt_kill_progress(player_id=8101, mob_id='forest_boar', location_id='dark_forest')
        self.assertFalse(non_match['updated'])

        for _ in range(4):
            result = register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='dark_forest', spawn_profile='normal')
            self.assertTrue(result['updated'])
            self.assertFalse(result['completed_now'])

        final = register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='dark_forest', spawn_profile='normal')
        self.assertTrue(final['updated'])
        self.assertTrue(final['completed_now'])

        state = get_player_hunt_contract_state(8101)
        self.assertEqual(state['progress_kills'], 5)
        self.assertEqual(state['status'], 'completed')


    def test_wrong_location_kill_does_not_increment_progress(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')

        wrong_location = register_hunt_kill_progress(
            player_id=8101,
            mob_id='forest_wolf',
            location_id='old_mines',
        )
        self.assertFalse(wrong_location['updated'])

        state = get_player_hunt_contract_state(8101)
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state['progress_kills'], 0)

    def test_contract_without_geography_metadata_remains_backward_compatible(self):
        _ensure_player_hunt_contract_table()
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT INTO player_hunt_contracts (player_id, contract_key, progress_kills, status, completed_at, claimed_at, updated_at)
                VALUES (?, ?, 0, 'active', NULL, NULL, CURRENT_TIMESTAMP)
                ON CONFLICT(player_id) DO UPDATE SET
                    contract_key=excluded.contract_key,
                    progress_kills=0,
                    status='active',
                    completed_at=NULL,
                    claimed_at=NULL,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (8101, 'legacy_no_geo_contract'),
            )
            conn.commit()
        finally:
            conn.close()

        with patch('game.quest_board.get_hunt_contract') as contract_mock:
            from game.quest_board import HuntContract
            contract_mock.return_value = HuntContract(
                contract_key='legacy_no_geo_contract',
                title_i18n_key='location.quest_contract_wolves_title',
                target_mob_id='forest_wolf',
                required_kills=2,
                reward_exp=1,
                reward_gold=1,
                board_locations=('village',),
            )
            result = register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='old_mines')

        self.assertTrue(result['updated'])
        conn = get_connection()
        try:
            row = conn.execute(
                'SELECT progress_kills FROM player_hunt_contracts WHERE player_id=?',
                (8101,),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(int(row['progress_kills']), 1)

    def test_register_progress_hot_path_does_not_invoke_schema_ensure(self):
        _ensure_player_hunt_contract_table()
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        with patch('game.quest_board._ensure_player_hunt_contract_table') as ensure_mock:
            result = register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='dark_forest')
        ensure_mock.assert_not_called()
        self.assertTrue(result['updated'])

    def test_location_progress_hint_shows_here_or_target_location(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')

        here_line = build_hunt_contract_progress_line(
            player_id=8101,
            lang='en',
            current_location_id='dark_forest',
        )
        elsewhere_line = build_hunt_contract_progress_line(
            player_id=8101,
            lang='en',
            current_location_id='old_mines',
        )

        self.assertIsNotNone(here_line)
        self.assertIsNotNone(elsewhere_line)
        assert here_line is not None
        assert elsewhere_line is not None
        self.assertIn('target here', here_line)
        self.assertIn('target: 🌲 Dark Forest', elsewhere_line)

    def test_state_read_and_location_line_are_safe_without_schema_init(self):
        with patch('game.quest_board._ensure_player_hunt_contract_table') as ensure_mock:
            state = get_player_hunt_contract_state(8101)
            line = build_hunt_contract_progress_line(player_id=8101, lang='en')
        ensure_mock.assert_not_called()
        self.assertIsNone(state)
        self.assertIsNone(line)

    def test_player_can_abandon_active_contract_and_accept_new_one(self):
        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_forest_wolves')
        register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='dark_forest')

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
            register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='dark_forest')

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
                register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='dark_forest')
            claim_completed_hunt_contract(player_id=8101, location_id='village')

        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_elite_boars')

        normal_kill = register_hunt_kill_progress(player_id=8101, mob_id='forest_boar', location_id='dark_forest', spawn_profile='normal')
        self.assertFalse(normal_kill['updated'])
        elite_kill = register_hunt_kill_progress(player_id=8101, mob_id='forest_boar', location_id='dark_forest', spawn_profile='elite')
        self.assertTrue(elite_kill['updated'])
        register_hunt_kill_progress(player_id=8101, mob_id='forest_boar', location_id='dark_forest', spawn_profile='elite')
        claim_completed_hunt_contract(player_id=8101, location_id='village')

        accept_hunt_contract(player_id=8101, location_id='village', contract_key='hunt_greyfang')
        wrong_named = register_hunt_kill_progress(
            player_id=8101,
            mob_id='forest_wolf',
            location_id='dark_forest',
            spawn_profile='rare',
            special_spawn_key='other_wolf',
        )
        self.assertFalse(wrong_named['updated'])
        correct_named = register_hunt_kill_progress(
            player_id=8101,
            mob_id='forest_wolf',
            location_id='dark_forest',
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
            location_id='dark_forest',
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
            location_id='dark_forest',
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
            register_hunt_kill_progress(player_id=8101, mob_id='forest_wolf', location_id='dark_forest')

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
