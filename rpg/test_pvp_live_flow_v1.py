import json
import unittest
from datetime import datetime, timedelta, timezone

from database import get_connection
from game.pvp_live import (
    advance_engagement_to_live_battle_if_ready,
    apply_illegal_aggression_penalties,
    can_create_live_engagement,
    create_live_engagement,
    get_pending_player_engagement,
    get_manual_pvp_action_labels,
    is_player_busy_with_live_pvp,
    process_live_pvp_due_events,
    resolve_engagement_escape,
    resolve_live_battle_turn,
    _resolve_repeat_kill_dampening,
)
from game.pvp_rules import (
    clear_respawn_protection,
    get_attack_block_reason,
    is_target_attackable,
    resolve_illegal_aggression_infamy,
    resolve_kill_infamy_delta,
)
from game.weapon_mastery import get_skill_cooldown


class OpenWorldPvpLiveFlowV1Tests(unittest.TestCase):
    ATTACKER_ID = 910001
    DEFENDER_ID = 910002

    def setUp(self):
        conn = get_connection()
        conn.execute('DELETE FROM pvp_log WHERE attacker_id IN (?, ?) OR defender_id IN (?, ?)', (
            self.ATTACKER_ID, self.DEFENDER_ID, self.ATTACKER_ID, self.DEFENDER_ID,
        ))
        conn.execute('DELETE FROM pvp_engagements WHERE attacker_id IN (?, ?) OR defender_id IN (?, ?)', (
            self.ATTACKER_ID, self.DEFENDER_ID, self.ATTACKER_ID, self.DEFENDER_ID,
        ))
        conn.execute('DELETE FROM inventory WHERE telegram_id IN (?, ?)', (self.ATTACKER_ID, self.DEFENDER_ID))
        conn.execute('DELETE FROM skill_cooldowns WHERE telegram_id IN (?, ?)', (self.ATTACKER_ID, self.DEFENDER_ID))
        conn.execute('DELETE FROM player_skills WHERE telegram_id IN (?, ?)', (self.ATTACKER_ID, self.DEFENDER_ID))
        conn.execute('DELETE FROM weapon_mastery WHERE telegram_id IN (?, ?)', (self.ATTACKER_ID, self.DEFENDER_ID))
        conn.execute('DELETE FROM equipment WHERE telegram_id IN (?, ?)', (self.ATTACKER_ID, self.DEFENDER_ID))
        conn.execute('DELETE FROM players WHERE telegram_id IN (?, ?)', (self.ATTACKER_ID, self.DEFENDER_ID))
        conn.execute(
            '''
            INSERT INTO players (telegram_id, username, name, level, location_id, hp, max_hp, mana, max_mana, pvp_status, novice_protection, red_flag, infamy)
            VALUES (?, 'attacker', 'Attacker', 20, 'dark_forest', 100, 100, 50, 50, 'neutral', 0, 0, 0)
            ''',
            (self.ATTACKER_ID,),
        )
        conn.execute(
            '''
            INSERT INTO players (telegram_id, username, name, level, location_id, hp, max_hp, mana, max_mana, pvp_status, novice_protection, red_flag, infamy)
            VALUES (?, 'defender', 'Defender', 20, 'dark_forest', 100, 100, 50, 50, 'neutral', 0, 0, 0)
            ''',
            (self.DEFENDER_ID,),
        )
        conn.execute('INSERT INTO equipment (telegram_id) VALUES (?)', (self.ATTACKER_ID,))
        conn.execute('INSERT INTO equipment (telegram_id) VALUES (?)', (self.DEFENDER_ID,))
        conn.commit()
        conn.close()

    def tearDown(self):
        conn = get_connection()
        conn.execute('DELETE FROM pvp_log WHERE attacker_id IN (?, ?) OR defender_id IN (?, ?)', (
            self.ATTACKER_ID, self.DEFENDER_ID, self.ATTACKER_ID, self.DEFENDER_ID,
        ))
        conn.execute('DELETE FROM pvp_engagements WHERE attacker_id IN (?, ?) OR defender_id IN (?, ?)', (
            self.ATTACKER_ID, self.DEFENDER_ID, self.ATTACKER_ID, self.DEFENDER_ID,
        ))
        conn.execute('DELETE FROM inventory WHERE telegram_id IN (?, ?)', (self.ATTACKER_ID, self.DEFENDER_ID))
        conn.execute('DELETE FROM skill_cooldowns WHERE telegram_id IN (?, ?)', (self.ATTACKER_ID, self.DEFENDER_ID))
        conn.execute('DELETE FROM player_skills WHERE telegram_id IN (?, ?)', (self.ATTACKER_ID, self.DEFENDER_ID))
        conn.execute('DELETE FROM weapon_mastery WHERE telegram_id IN (?, ?)', (self.ATTACKER_ID, self.DEFENDER_ID))
        conn.execute('DELETE FROM equipment WHERE telegram_id IN (?, ?)', (self.ATTACKER_ID, self.DEFENDER_ID))
        conn.execute('DELETE FROM players WHERE telegram_id IN (?, ?)', (self.ATTACKER_ID, self.DEFENDER_ID))
        conn.commit()
        conn.close()

    def _players(self):
        conn = get_connection()
        a = dict(conn.execute('SELECT * FROM players WHERE telegram_id=?', (self.ATTACKER_ID,)).fetchone())
        d = dict(conn.execute('SELECT * FROM players WHERE telegram_id=?', (self.DEFENDER_ID,)).fetchone())
        conn.close()
        return a, d

    def test_player_world_pvp_initiation_legality_and_safe_zone_block(self):
        attacker, defender = self._players()
        self.assertTrue(is_target_attackable(attacker=attacker, defender=defender, location_id='dark_forest'))
        self.assertFalse(is_target_attackable(attacker=attacker, defender=defender, location_id='village'))

    def test_guarded_illegal_attack_creates_engagement_and_red_flag(self):
        attacker, defender = self._players()
        engagement_id = create_live_engagement(
            attacker=attacker,
            defender=defender,
            location_id='dark_forest',
            illegal_aggression=True,
        )
        apply_illegal_aggression_penalties(attacker_id=self.ATTACKER_ID)
        conn = get_connection()
        row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
        attacker_after = conn.execute('SELECT red_flag, infamy FROM players WHERE telegram_id=?', (self.ATTACKER_ID,)).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(attacker_after['red_flag'], 1)
        self.assertGreaterEqual(attacker_after['infamy'], 1)

    def test_repeat_kill_dampens_vulnerable_transfer_value(self):
        conn = get_connection()
        conn.execute(
            "INSERT INTO pvp_log (attacker_id, defender_id, winner_id, exp_gained, gold_gained) VALUES (?, ?, ?, 0, 0)",
            (self.ATTACKER_ID, self.DEFENDER_ID, self.ATTACKER_ID),
        )
        conn.commit()
        conn.close()
        repeat_count, transfer_scale = _resolve_repeat_kill_dampening(
            winner_id=self.ATTACKER_ID,
            loser_id=self.DEFENDER_ID,
        )
        self.assertEqual(repeat_count, 1)
        self.assertLess(transfer_scale, 1.0)

    def test_respawn_protection_blocks_immediate_reengage_in_guarded_zone(self):
        conn = get_connection()
        conn.execute(
            "UPDATE players SET pvp_respawn_protection_until=strftime('%s','now') + 120 WHERE telegram_id=?",
            (self.DEFENDER_ID,),
        )
        conn.commit()
        attacker, defender = self._players()
        conn.close()
        self.assertFalse(is_target_attackable(attacker=attacker, defender=defender, location_id='dark_forest'))
        self.assertEqual(
            get_attack_block_reason(attacker=attacker, defender=defender, location_id='dark_forest'),
            'respawn_protection',
        )

    def test_respawn_protection_breaks_on_hostile_action(self):
        conn = get_connection()
        conn.execute(
            "UPDATE players SET pvp_respawn_protection_until=strftime('%s','now') + 120 WHERE telegram_id=?",
            (self.ATTACKER_ID,),
        )
        conn.commit()
        conn.close()
        clear_respawn_protection(player_id=self.ATTACKER_ID)
        attacker, _ = self._players()
        self.assertEqual(int(attacker['pvp_respawn_protection_until']), 0)

    def test_illegal_infamy_is_stronger_than_retaliation(self):
        attacker, defender = self._players()
        fresh = resolve_illegal_aggression_infamy(
            attacker=attacker,
            defender=defender,
            location_id='dark_forest',
        )
        conn = get_connection()
        conn.execute(
            "INSERT INTO pvp_log (attacker_id, defender_id, winner_id, exp_gained, gold_gained) VALUES (?, ?, ?, 0, 0)",
            (self.DEFENDER_ID, self.ATTACKER_ID, self.DEFENDER_ID),
        )
        conn.commit()
        conn.close()
        retaliation = resolve_illegal_aggression_infamy(
            attacker=attacker,
            defender=defender,
            location_id='dark_forest',
        )
        self.assertGreater(fresh, retaliation)

    def test_repeat_harassment_increases_kill_infamy(self):
        attacker, defender = self._players()
        base = resolve_kill_infamy_delta(
            winner=attacker,
            loser=defender,
            location_id='dark_forest',
            repeat_kill_count=0,
        )
        repeated = resolve_kill_infamy_delta(
            winner=attacker,
            loser=defender,
            location_id='dark_forest',
            repeat_kill_count=2,
        )
        self.assertGreater(repeated, base)

    def test_duplicate_parallel_engagements_are_blocked_for_1v1_scope(self):
        attacker, defender = self._players()
        ok, reason = can_create_live_engagement(attacker_id=self.ATTACKER_ID, defender_id=self.DEFENDER_ID)
        self.assertTrue(ok)
        self.assertIsNone(reason)

        create_live_engagement(
            attacker=attacker,
            defender=defender,
            location_id='dark_forest',
            illegal_aggression=False,
        )
        self.assertTrue(is_player_busy_with_live_pvp(self.ATTACKER_ID))
        self.assertTrue(is_player_busy_with_live_pvp(self.DEFENDER_ID))

        ok2, reason2 = can_create_live_engagement(attacker_id=self.ATTACKER_ID, defender_id=self.DEFENDER_ID)
        self.assertFalse(ok2)
        self.assertIn(reason2, {'attacker_busy', 'defender_busy', 'duplicate_pair'})

    def test_engagement_conversion_and_escape_paths(self):
        attacker, defender = self._players()
        engagement_id = create_live_engagement(
            attacker=attacker,
            defender=defender,
            location_id='dark_forest',
            illegal_aggression=False,
        )
        conn = get_connection()
        conn.execute(
            "UPDATE pvp_engagements SET engagement_ready_at=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), engagement_id),
        )
        conn.commit()
        row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
        conn.close()
        state, payload = advance_engagement_to_live_battle_if_ready(row)
        self.assertEqual(state, 'converted_to_battle')
        self.assertEqual(payload['battle']['state'], 'live')
        self.assertEqual(payload['battle']['attacker_hp'], 100)
        self.assertEqual(payload['battle']['attacker_max_hp'], 100)

        # Successful escape in separate engagement
        engagement_id_2 = create_live_engagement(
            attacker=attacker, defender=defender, location_id='dark_forest', illegal_aggression=False
        )
        row2 = get_pending_player_engagement(self.ATTACKER_ID)
        state2, should_start_2 = resolve_engagement_escape(row2, escape_succeeded=True)
        self.assertEqual(state2, 'escaped')
        self.assertFalse(should_start_2)

        # Failed escape converts early
        engagement_id_3 = create_live_engagement(
            attacker=attacker, defender=defender, location_id='dark_forest', illegal_aggression=False
        )
        conn = get_connection()
        row3 = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id_3,)).fetchone()
        conn.close()
        state3, should_start_3 = resolve_engagement_escape(row3, escape_succeeded=False)
        self.assertEqual(state3, 'converted_to_battle')
        self.assertTrue(should_start_3)

    def test_scheduler_progresses_engagement_and_turn_without_callback(self):
        attacker, defender = self._players()
        engagement_id = create_live_engagement(
            attacker=attacker,
            defender=defender,
            location_id='dark_forest',
            illegal_aggression=False,
        )
        conn = get_connection()
        conn.execute(
            "UPDATE pvp_engagements SET engagement_ready_at=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), engagement_id),
        )
        conn.commit()
        conn.close()
        events = process_live_pvp_due_events(now=datetime.now(timezone.utc))
        self.assertTrue(any(event['type'] == 'engagement_live' for event in events))

        conn = get_connection()
        payload = json.loads(conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()['reason_context'])
        payload['battle']['turn_started_at'] = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()
        conn.execute('UPDATE pvp_engagements SET reason_context=? WHERE id=?', (json.dumps(payload), engagement_id))
        conn.commit()
        conn.close()
        events2 = process_live_pvp_due_events(now=datetime.now(timezone.utc))
        self.assertTrue(any(event['type'] == 'turn_auto_resolved' for event in events2))

    def test_timed_turn_waits_then_auto_acts_after_timeout(self):
        attacker, defender = self._players()
        engagement_id = create_live_engagement(
            attacker=attacker,
            defender=defender,
            location_id='dark_forest',
            illegal_aggression=False,
        )
        conn = get_connection()
        conn.execute(
            "UPDATE pvp_engagements SET engagement_state='converted_to_battle', reason_context=? WHERE id=?",
            (json.dumps({
                'battle': {
                    'state': 'live',
                    'attacker_hp': 100,
                    'defender_hp': 100,
                    'attacker_max_hp': 100,
                    'defender_max_hp': 100,
                    'turn_owner': self.ATTACKER_ID,
                    'turn_started_at': datetime.now(timezone.utc).isoformat(),
                    'guarded_player_id': None,
                    'last_log': '',
                }
            }), engagement_id),
        )
        conn.commit()
        row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
        conn.close()
        waiting, _ = resolve_live_battle_turn(row, actor_id=self.ATTACKER_ID, selected_action_id=None)
        self.assertEqual(waiting, 'waiting')

        conn = get_connection()
        payload = json.loads(conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()['reason_context'])
        payload['battle']['turn_started_at'] = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()
        conn.execute('UPDATE pvp_engagements SET reason_context=? WHERE id=?', (json.dumps(payload), engagement_id))
        conn.commit()
        row2 = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
        conn.close()
        resolved, _ = resolve_live_battle_turn(row2, actor_id=self.ATTACKER_ID, selected_action_id=None)
        self.assertEqual(resolved, 'resolved')

    def test_auto_action_not_structurally_forced_to_normal_attack(self):
        attacker, defender = self._players()
        engagement_id = create_live_engagement(
            attacker=attacker,
            defender=defender,
            location_id='dark_forest',
            illegal_aggression=False,
        )
        conn = get_connection()
        conn.execute(
            "UPDATE pvp_engagements SET engagement_state='converted_to_battle', reason_context=? WHERE id=?",
            (json.dumps({
                'battle': {
                    'state': 'live',
                    'attacker_hp': 30,
                    'defender_hp': 100,
                    'attacker_mana': 0,
                    'defender_mana': 0,
                    'attacker_max_hp': 100,
                    'defender_max_hp': 100,
                    'turn_owner': self.ATTACKER_ID,
                    'turn_started_at': (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat(),
                    'guarded_player_id': None,
                    'last_log': '',
                }
            }), engagement_id),
        )
        conn.commit()
        row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
        conn.close()
        status, payload = resolve_live_battle_turn(row, actor_id=self.ATTACKER_ID, selected_action_id=None)
        self.assertEqual(status, 'resolved')
        self.assertIn('guard', payload['battle']['last_log'])

    def test_auto_action_can_use_ready_skill(self):
        attacker, defender = self._players()
        conn = get_connection()
        conn.execute("INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, 'iron_sword', 1)", (self.ATTACKER_ID,))
        inv_id = conn.execute(
            "SELECT id FROM inventory WHERE telegram_id=? AND item_id='iron_sword' ORDER BY id DESC LIMIT 1",
            (self.ATTACKER_ID,),
        ).fetchone()['id']
        conn.execute("UPDATE equipment SET weapon=? WHERE telegram_id=?", (inv_id, self.ATTACKER_ID))
        conn.execute(
            "INSERT OR REPLACE INTO weapon_mastery (telegram_id, weapon_id, level, exp, skill_points) VALUES (?, 'iron_sword', 1, 0, 1)",
            (self.ATTACKER_ID,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO player_skills (telegram_id, skill_id, level) VALUES (?, 'power_strike', 1)",
            (self.ATTACKER_ID,),
        )
        conn.commit()
        conn.close()

        engagement_id = create_live_engagement(
            attacker=attacker,
            defender=defender,
            location_id='dark_forest',
            illegal_aggression=False,
        )
        conn = get_connection()
        conn.execute(
            "UPDATE pvp_engagements SET engagement_state='converted_to_battle', reason_context=? WHERE id=?",
            (json.dumps({
                'battle': {
                    'state': 'live',
                    'attacker_hp': 100,
                    'defender_hp': 100,
                    'attacker_mana': 100,
                    'defender_mana': 100,
                    'attacker_max_hp': 100,
                    'defender_max_hp': 100,
                    'turn_owner': self.ATTACKER_ID,
                    'turn_started_at': (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat(),
                    'guarded_player_id': None,
                    'last_log': '',
                }
            }), engagement_id),
        )
        conn.commit()
        row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
        conn.close()
        status, payload = resolve_live_battle_turn(row, actor_id=self.ATTACKER_ID, selected_action_id=None)
        self.assertEqual(status, 'resolved')
        self.assertIn('skill_ok', payload['battle']['last_log'])

    def test_skill_actions_are_exposed_and_usable(self):
        attacker, defender = self._players()
        conn = get_connection()
        conn.execute(
            "INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, 'iron_sword', 1)",
            (self.ATTACKER_ID,),
        )
        inv_id = conn.execute(
            "SELECT id FROM inventory WHERE telegram_id=? AND item_id='iron_sword' ORDER BY id DESC LIMIT 1",
            (self.ATTACKER_ID,),
        ).fetchone()['id']
        conn.execute(
            "UPDATE equipment SET weapon=? WHERE telegram_id=?",
            (inv_id, self.ATTACKER_ID),
        )
        conn.execute(
            "INSERT OR REPLACE INTO weapon_mastery (telegram_id, weapon_id, level, exp, skill_points) VALUES (?, 'iron_sword', 1, 0, 1)",
            (self.ATTACKER_ID,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO player_skills (telegram_id, skill_id, level) VALUES (?, 'power_strike', 1)",
            (self.ATTACKER_ID,),
        )
        conn.commit()
        conn.close()
        labels = get_manual_pvp_action_labels(player_id=self.ATTACKER_ID, lang='en')
        action_ids = {row[0] for row in labels}
        self.assertIn('normal_attack', action_ids)
        self.assertIn('guard', action_ids)
        self.assertIn('skill:power_strike', action_ids)

        engagement_id = create_live_engagement(
            attacker=attacker,
            defender=defender,
            location_id='dark_forest',
            illegal_aggression=False,
        )
        conn = get_connection()
        conn.execute(
            "UPDATE pvp_engagements SET engagement_state='converted_to_battle', reason_context=? WHERE id=?",
            (json.dumps({
                'battle': {
                    'state': 'live',
                    'attacker_hp': 100,
                    'defender_hp': 100,
                    'attacker_mana': 100,
                    'defender_mana': 100,
                    'attacker_max_hp': 100,
                    'defender_max_hp': 100,
                    'turn_owner': self.ATTACKER_ID,
                    'turn_started_at': datetime.now(timezone.utc).isoformat(),
                    'guarded_player_id': None,
                    'last_log': '',
                }
            }), engagement_id),
        )
        conn.commit()
        row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
        conn.close()
        result, payload = resolve_live_battle_turn(row, actor_id=self.ATTACKER_ID, selected_action_id='skill:power_strike')
        self.assertEqual(result, 'resolved')
        self.assertIn('skill_ok', payload['battle']['last_log'])

    def test_live_turn_progression_ticks_skill_cooldowns(self):
        attacker, defender = self._players()
        conn = get_connection()
        conn.execute(
            "INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, 'iron_sword', 1)",
            (self.ATTACKER_ID,),
        )
        inv_id = conn.execute(
            "SELECT id FROM inventory WHERE telegram_id=? AND item_id='iron_sword' ORDER BY id DESC LIMIT 1",
            (self.ATTACKER_ID,),
        ).fetchone()['id']
        conn.execute("UPDATE equipment SET weapon=? WHERE telegram_id=?", (inv_id, self.ATTACKER_ID))
        conn.execute(
            "INSERT OR REPLACE INTO weapon_mastery (telegram_id, weapon_id, level, exp, skill_points) VALUES (?, 'iron_sword', 1, 0, 1)",
            (self.ATTACKER_ID,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO player_skills (telegram_id, skill_id, level) VALUES (?, 'power_strike', 1)",
            (self.ATTACKER_ID,),
        )
        conn.commit()
        conn.close()

        engagement_id = create_live_engagement(
            attacker=attacker,
            defender=defender,
            location_id='dark_forest',
            illegal_aggression=False,
        )
        conn = get_connection()
        conn.execute(
            "UPDATE pvp_engagements SET engagement_state='converted_to_battle', reason_context=? WHERE id=?",
            (json.dumps({
                'battle': {
                    'state': 'live',
                    'attacker_hp': 100,
                    'defender_hp': 100,
                    'attacker_mana': 100,
                    'defender_mana': 100,
                    'attacker_max_hp': 100,
                    'defender_max_hp': 100,
                    'turn_owner': self.ATTACKER_ID,
                    'turn_started_at': datetime.now(timezone.utc).isoformat(),
                    'guarded_player_id': None,
                    'last_log': '',
                }
            }), engagement_id),
        )
        conn.commit()
        row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
        conn.close()

        first_result, _ = resolve_live_battle_turn(row, actor_id=self.ATTACKER_ID, selected_action_id='skill:power_strike')
        self.assertEqual(first_result, 'resolved')
        self.assertEqual(get_skill_cooldown(self.ATTACKER_ID, 'power_strike'), 1)

        conn = get_connection()
        row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
        conn.close()
        second_result, _ = resolve_live_battle_turn(row, actor_id=self.DEFENDER_ID, selected_action_id='normal_attack')
        self.assertEqual(second_result, 'resolved')
        self.assertEqual(get_skill_cooldown(self.ATTACKER_ID, 'power_strike'), 1)

        conn = get_connection()
        row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
        conn.close()
        third_result, _ = resolve_live_battle_turn(row, actor_id=self.ATTACKER_ID, selected_action_id='normal_attack')
        self.assertEqual(third_result, 'resolved')
        self.assertEqual(get_skill_cooldown(self.ATTACKER_ID, 'power_strike'), 0)

    def test_unready_skill_not_surfaced_and_invalid_submission_does_not_consume_turn(self):
        attacker, defender = self._players()
        conn = get_connection()
        conn.execute("INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, 'iron_sword', 1)", (self.ATTACKER_ID,))
        inv_id = conn.execute(
            "SELECT id FROM inventory WHERE telegram_id=? AND item_id='iron_sword' ORDER BY id DESC LIMIT 1",
            (self.ATTACKER_ID,),
        ).fetchone()['id']
        conn.execute("UPDATE equipment SET weapon=? WHERE telegram_id=?", (inv_id, self.ATTACKER_ID))
        conn.execute(
            "INSERT OR REPLACE INTO weapon_mastery (telegram_id, weapon_id, level, exp, skill_points) VALUES (?, 'iron_sword', 1, 0, 1)",
            (self.ATTACKER_ID,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO player_skills (telegram_id, skill_id, level) VALUES (?, 'power_strike', 1)",
            (self.ATTACKER_ID,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO skill_cooldowns (telegram_id, skill_id, turns_left) VALUES (?, 'power_strike', 2)",
            (self.ATTACKER_ID,),
        )
        conn.execute("UPDATE players SET mana=0 WHERE telegram_id=?", (self.ATTACKER_ID,))
        conn.commit()
        conn.close()

        labels = get_manual_pvp_action_labels(player_id=self.ATTACKER_ID, lang='en')
        action_ids = {row[0] for row in labels}
        self.assertNotIn('skill:power_strike', action_ids)

        engagement_id = create_live_engagement(
            attacker=attacker,
            defender=defender,
            location_id='dark_forest',
            illegal_aggression=False,
        )
        original_started = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        conn.execute(
            "UPDATE pvp_engagements SET engagement_state='converted_to_battle', reason_context=? WHERE id=?",
            (json.dumps({
                'battle': {
                    'state': 'live',
                    'attacker_hp': 100,
                    'defender_hp': 100,
                    'attacker_mana': 0,
                    'defender_mana': 100,
                    'attacker_max_hp': 100,
                    'defender_max_hp': 100,
                    'turn_owner': self.ATTACKER_ID,
                    'turn_started_at': original_started,
                    'guarded_player_id': None,
                    'last_log': '',
                }
            }), engagement_id),
        )
        conn.commit()
        row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
        conn.close()

        status, payload = resolve_live_battle_turn(row, actor_id=self.ATTACKER_ID, selected_action_id='skill:power_strike')
        self.assertEqual(status, 'invalid_action')
        self.assertEqual(payload['battle']['turn_owner'], self.ATTACKER_ID)
        self.assertEqual(payload['battle']['turn_started_at'], original_started)

    def test_manual_skill_labels_use_live_battle_mana(self):
        conn = get_connection()
        conn.execute(
            "INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, 'iron_sword', 1)",
            (self.ATTACKER_ID,),
        )
        inv_id = conn.execute(
            "SELECT id FROM inventory WHERE telegram_id=? AND item_id='iron_sword' ORDER BY id DESC LIMIT 1",
            (self.ATTACKER_ID,),
        ).fetchone()['id']
        conn.execute("UPDATE equipment SET weapon=? WHERE telegram_id=?", (inv_id, self.ATTACKER_ID))
        conn.execute(
            "INSERT OR REPLACE INTO weapon_mastery (telegram_id, weapon_id, level, exp, skill_points) VALUES (?, 'iron_sword', 1, 0, 1)",
            (self.ATTACKER_ID,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO player_skills (telegram_id, skill_id, level) VALUES (?, 'power_strike', 1)",
            (self.ATTACKER_ID,),
        )
        conn.execute("UPDATE players SET mana=100 WHERE telegram_id=?", (self.ATTACKER_ID,))
        conn.commit()
        conn.close()

        low_live_mana = {'attacker_mana': 0, 'defender_mana': 100}
        labels_low = get_manual_pvp_action_labels(
            player_id=self.ATTACKER_ID,
            lang='en',
            battle=low_live_mana,
            attacker_id=self.ATTACKER_ID,
            defender_id=self.DEFENDER_ID,
        )
        self.assertNotIn('skill:power_strike', {row[0] for row in labels_low})

        conn = get_connection()
        conn.execute("UPDATE players SET mana=0 WHERE telegram_id=?", (self.ATTACKER_ID,))
        conn.commit()
        conn.close()
        high_live_mana = {'attacker_mana': 100, 'defender_mana': 100}
        labels_high = get_manual_pvp_action_labels(
            player_id=self.ATTACKER_ID,
            lang='en',
            battle=high_live_mana,
            attacker_id=self.ATTACKER_ID,
            defender_id=self.DEFENDER_ID,
        )
        self.assertIn('skill:power_strike', {row[0] for row in labels_high})

    def test_pvp_resolution_logs_respawn_and_vulnerable_transfer(self):
        attacker, defender = self._players()
        conn = get_connection()
        conn.execute("INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, 'wolf_pelt', 10)", (self.DEFENDER_ID,))
        conn.commit()
        conn.close()

        engagement_id = create_live_engagement(
            attacker=attacker,
            defender=defender,
            location_id='dark_forest',
            illegal_aggression=False,
        )
        battle_payload = {
            'battle': {
                'state': 'live',
                'attacker_hp': 100,
                'defender_hp': 1,
                'attacker_max_hp': 100,
                'defender_max_hp': 100,
                'turn_owner': self.ATTACKER_ID,
                'turn_started_at': (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat(),
                'guarded_player_id': None,
                'last_log': '',
            }
        }
        conn = get_connection()
        conn.execute(
            "UPDATE pvp_engagements SET engagement_state='converted_to_battle', reason_context=? WHERE id=?",
            (json.dumps(battle_payload), engagement_id),
        )
        conn.commit()
        row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
        conn.close()
        result = 'resolved'
        for _ in range(10):
            status, _ = resolve_live_battle_turn(row, actor_id=self.ATTACKER_ID, selected_action_id=None)
            result = status
            if result == 'finished':
                break
            conn = get_connection()
            payload = json.loads(conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()['reason_context'])
            payload['battle']['turn_owner'] = self.ATTACKER_ID
            payload['battle']['turn_started_at'] = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()
            conn.execute('UPDATE pvp_engagements SET reason_context=? WHERE id=?', (json.dumps(payload), engagement_id))
            conn.commit()
            row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
            conn.close()
        self.assertEqual(result, 'finished')

        conn = get_connection()
        pvp_log_row = conn.execute(
            'SELECT winner_id, exp_gained, gold_gained FROM pvp_log WHERE attacker_id=? AND defender_id=? ORDER BY id DESC LIMIT 1',
            (self.ATTACKER_ID, self.DEFENDER_ID),
        ).fetchone()
        defender_after = conn.execute(
            'SELECT location_id, in_battle FROM players WHERE telegram_id=?',
            (self.DEFENDER_ID,),
        ).fetchone()
        loser_inv = conn.execute(
            "SELECT quantity FROM inventory WHERE telegram_id=? AND item_id='wolf_pelt'",
            (self.DEFENDER_ID,),
        ).fetchone()
        winner_inv = conn.execute(
            "SELECT quantity FROM inventory WHERE telegram_id=? AND item_id='wolf_pelt'",
            (self.ATTACKER_ID,),
        ).fetchone()
        winner_after = conn.execute(
            'SELECT hp, in_battle FROM players WHERE telegram_id=?',
            (self.ATTACKER_ID,),
        ).fetchone()
        conn.close()

        self.assertEqual(pvp_log_row['winner_id'], self.ATTACKER_ID)
        self.assertEqual(pvp_log_row['exp_gained'], 0)
        self.assertEqual(pvp_log_row['gold_gained'], 0)
        self.assertEqual(defender_after['location_id'], 'village')
        self.assertEqual(defender_after['in_battle'], 0)
        self.assertEqual(loser_inv['quantity'], 5)  # guarded zone: 50%
        self.assertEqual(winner_inv['quantity'], 5)
        self.assertGreaterEqual(winner_after['hp'], 1)
        self.assertEqual(winner_after['in_battle'], 0)


if __name__ == '__main__':
    unittest.main()
