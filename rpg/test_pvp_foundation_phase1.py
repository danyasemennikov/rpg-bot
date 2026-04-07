import unittest
from datetime import datetime, timedelta, timezone

from game.locations import get_location_security_tier, resolve_region_safe_hub
from game.pvp_engagement import (
    ENGAGEMENT_PREPARATION_WINDOW_SECONDS,
    ENGAGEMENT_STATE_CONVERTED_TO_BATTLE,
    ENGAGEMENT_STATE_ESCAPED,
    ENGAGEMENT_STATE_PENDING,
    activate_engagement_if_ready,
    create_open_world_pvp_engagement,
    resolve_escape_attempt,
)
from game.pvp_death_policy import (
    resolve_death_respawn_hub,
    resolve_pve_death_loss_percent,
    resolve_pvp_death_loss_percent,
)
from game.pvp_inventory_policy import (
    PROTECTED,
    VULNERABLE_ON_PVE_DEATH,
    VULNERABLE_ON_PVP_DEATH,
    resolve_item_death_vulnerability,
)
from game.pvp_rules import (
    does_novice_protection_block_interaction,
    is_aggression_illegal,
    is_target_attackable,
    should_apply_red_flag,
)
from game.pvp_state import build_player_pvp_state
from game.pvp_turn_timing import (
    ACTION_FAMILY_ATTACK,
    ACTION_FAMILY_CORE,
    ACTION_FAMILY_DEFENSIVE,
    ACTION_FAMILY_FINISHING,
    PvpActionOption,
    resolve_timed_turn_action,
)


class OpenWorldPvpFoundationTests(unittest.TestCase):
    def test_security_tier_resolution(self):
        self.assertEqual(get_location_security_tier('village'), 'safe')
        self.assertEqual(get_location_security_tier('dark_forest'), 'guarded')
        self.assertEqual(get_location_security_tier('old_mines'), 'frontier')

    def test_illegal_aggression_in_guarded_zone(self):
        attacker = {'telegram_id': 1, 'pvp_status': 'neutral', 'red_flag': 0}
        defender = {'telegram_id': 2, 'pvp_status': 'neutral', 'red_flag': 0}

        self.assertTrue(
            is_aggression_illegal(
                attacker=attacker,
                defender=defender,
                location_id='dark_forest',
            )
        )
        self.assertFalse(
            is_aggression_illegal(
                attacker=attacker,
                defender=defender,
                location_id='old_mines',
            )
        )

    def test_flagged_target_in_guarded_zone_is_legal_aggression(self):
        attacker = {'telegram_id': 1, 'pvp_status': 'neutral', 'red_flag': 0}
        defender = {'telegram_id': 2, 'pvp_status': 'flagged', 'red_flag': 0}

        self.assertFalse(
            is_aggression_illegal(
                attacker=attacker,
                defender=defender,
                location_id='dark_forest',
            )
        )

    def test_forced_flagged_target_is_attackable_outside_safe(self):
        attacker = {'telegram_id': 1, 'level': 20, 'novice_protection': 0, 'red_flag': 0}
        defender = {'telegram_id': 2, 'pvp_status': 'forced_flagged', 'level': 20, 'novice_protection': 0, 'red_flag': 0}

        self.assertTrue(
            is_target_attackable(
                attacker=attacker,
                defender=defender,
                location_id='old_mines',
            )
        )

    def test_war_flagged_target_is_attackable_outside_safe(self):
        attacker = {'telegram_id': 1, 'level': 20, 'novice_protection': 0, 'red_flag': 0}
        defender = {'telegram_id': 2, 'pvp_status': 'war_flagged', 'level': 20, 'novice_protection': 0, 'red_flag': 0}

        self.assertTrue(
            is_target_attackable(
                attacker=attacker,
                defender=defender,
                location_id='old_mines',
            )
        )

    def test_novice_protection_still_blocks_in_guarded(self):
        attacker = {'telegram_id': 1, 'level': 5, 'novice_protection': 1, 'red_flag': 0}
        defender = {'telegram_id': 2, 'level': 20, 'novice_protection': 0, 'red_flag': 0}

        self.assertTrue(
            does_novice_protection_block_interaction(
                attacker=attacker,
                defender=defender,
                location_id='dark_forest',
            )
        )
        self.assertFalse(
            does_novice_protection_block_interaction(
                attacker=attacker,
                defender=defender,
                location_id='old_mines',
            )
        )

    def test_safe_zone_still_blocks_attacks(self):
        attacker = {'telegram_id': 1, 'level': 20, 'novice_protection': 0, 'red_flag': 0}
        defender = {'telegram_id': 2, 'pvp_status': 'war_flagged', 'level': 20, 'novice_protection': 0, 'red_flag': 0}

        self.assertFalse(
            is_target_attackable(
                attacker=attacker,
                defender=defender,
                location_id='village',
            )
        )

    def test_should_apply_red_flag_for_illegal_guarded_aggression(self):
        attacker = {'telegram_id': 1, 'pvp_status': 'neutral', 'red_flag': 0}
        defender = {'telegram_id': 2, 'pvp_status': 'neutral', 'red_flag': 0}
        self.assertTrue(
            should_apply_red_flag(
                attacker=attacker,
                defender=defender,
                location_id='dark_forest',
            )
        )

    def test_should_not_apply_red_flag_when_attacker_already_red(self):
        attacker = {'telegram_id': 1, 'pvp_status': 'neutral', 'red_flag': 1}
        defender = {'telegram_id': 2, 'pvp_status': 'neutral', 'red_flag': 0}
        self.assertFalse(
            should_apply_red_flag(
                attacker=attacker,
                defender=defender,
                location_id='dark_forest',
            )
        )

    def test_engagement_window_creation_has_five_minute_ready_time(self):
        started_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        engagement = create_open_world_pvp_engagement(
            attacker_id=101,
            defender_id=202,
            location_id='dark_forest',
            now=started_at,
        )
        self.assertEqual(engagement.engagement_state, ENGAGEMENT_STATE_PENDING)
        self.assertEqual(
            engagement.engagement_ready_at,
            started_at + timedelta(seconds=ENGAGEMENT_PREPARATION_WINDOW_SECONDS),
        )

    def test_engagement_pending_until_ready_then_active(self):
        started_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        engagement = create_open_world_pvp_engagement(
            attacker_id=101,
            defender_id=202,
            location_id='dark_forest',
            now=started_at,
        )
        still_pending = activate_engagement_if_ready(
            engagement,
            now=started_at + timedelta(seconds=120),
        )
        self.assertEqual(still_pending.engagement_state, ENGAGEMENT_STATE_PENDING)

        active = activate_engagement_if_ready(
            engagement,
            now=engagement.engagement_ready_at + timedelta(seconds=1),
        )
        self.assertEqual(active.engagement_state, 'active')

    def test_failed_escape_triggers_early_battle_conversion(self):
        engagement = create_open_world_pvp_engagement(
            attacker_id=101,
            defender_id=202,
            location_id='dark_forest',
            now=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        updated, should_start_battle = resolve_escape_attempt(
            engagement,
            escape_succeeded=False,
        )
        self.assertTrue(should_start_battle)
        self.assertEqual(updated.engagement_state, ENGAGEMENT_STATE_CONVERTED_TO_BATTLE)

    def test_successful_escape_terminates_engagement_cleanly(self):
        engagement = create_open_world_pvp_engagement(
            attacker_id=101,
            defender_id=202,
            location_id='dark_forest',
            now=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        updated, should_start_battle = resolve_escape_attempt(
            engagement,
            escape_succeeded=True,
        )
        self.assertFalse(should_start_battle)
        self.assertEqual(updated.engagement_state, ENGAGEMENT_STATE_ESCAPED)

    def test_timed_turn_uses_auto_action_after_timeout(self):
        started_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        options = [
            PvpActionOption('finish_strike', ACTION_FAMILY_FINISHING, True),
            PvpActionOption('guard_stance', ACTION_FAMILY_DEFENSIVE, True),
            PvpActionOption('core_slash', ACTION_FAMILY_CORE, True),
            PvpActionOption('normal_attack', ACTION_FAMILY_ATTACK, True),
        ]
        resolved = resolve_timed_turn_action(
            turn_started_at=started_at,
            available_options=options,
            selected_action_id=None,
            now=started_at + timedelta(seconds=20),
        )
        self.assertEqual(resolved.action_source, 'auto')
        self.assertEqual(resolved.action_id, 'finish_strike')
        self.assertTrue(resolved.timed_out)

    def test_timed_turn_waits_before_timeout_when_no_action_selected(self):
        started_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        options = [
            PvpActionOption('finish_strike', ACTION_FAMILY_FINISHING, True),
            PvpActionOption('normal_attack', ACTION_FAMILY_ATTACK, True),
        ]
        resolved = resolve_timed_turn_action(
            turn_started_at=started_at,
            available_options=options,
            selected_action_id=None,
            now=started_at + timedelta(seconds=5),
        )
        self.assertIsNone(resolved)

    def test_timed_turn_preserves_player_action_before_timeout(self):
        started_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        options = [
            PvpActionOption('core_slash', ACTION_FAMILY_CORE, True),
            PvpActionOption('normal_attack', ACTION_FAMILY_ATTACK, True),
        ]
        resolved = resolve_timed_turn_action(
            turn_started_at=started_at,
            available_options=options,
            selected_action_id='core_slash',
            now=started_at + timedelta(seconds=5),
        )
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.action_source, 'player')
        self.assertEqual(resolved.action_id, 'core_slash')
        self.assertFalse(resolved.timed_out)

    def test_vulnerable_inventory_classification(self):
        wolf_pelt = resolve_item_death_vulnerability('wolf_pelt')
        health_potion = resolve_item_death_vulnerability('health_potion')
        iron_sword = resolve_item_death_vulnerability('iron_sword')

        self.assertEqual(wolf_pelt.classification, VULNERABLE_ON_PVP_DEATH)
        self.assertEqual(health_potion.classification, VULNERABLE_ON_PVE_DEATH)
        self.assertEqual(iron_sword.classification, PROTECTED)

    def test_regional_safe_hub_resolution(self):
        self.assertEqual(resolve_region_safe_hub(location_id='old_mines'), 'village')
        self.assertEqual(resolve_death_respawn_hub(location_id='dark_forest'), 'village')

    def test_death_loss_policy_resolution_by_zone_type(self):
        self.assertEqual(resolve_pvp_death_loss_percent(location_id='village'), 0.0)
        self.assertEqual(resolve_pvp_death_loss_percent(location_id='dark_forest'), 0.5)
        self.assertEqual(resolve_pvp_death_loss_percent(location_id='old_mines'), 0.6)
        self.assertEqual(resolve_pvp_death_loss_percent(security_tier='core_war'), 0.7)
        self.assertEqual(resolve_pve_death_loss_percent(), 0.25)

    def test_pvp_state_normalization_uses_approved_vocab(self):
        state = build_player_pvp_state({'pvp_status': 'contested'})
        self.assertEqual(state.pvp_status, 'neutral')
        flagged = build_player_pvp_state({'pvp_status': 'war_flagged'})
        self.assertEqual(flagged.pvp_status, 'war_flagged')

    def test_missing_novice_protection_defaults_to_enabled(self):
        attacker = {'telegram_id': 1, 'level': 20, 'novice_protection': 0, 'red_flag': 0}
        defender = {'telegram_id': 2, 'level': 5, 'red_flag': 0}

        self.assertTrue(
            does_novice_protection_block_interaction(
                attacker=attacker,
                defender=defender,
                location_id='dark_forest',
            )
        )
        self.assertFalse(
            is_target_attackable(
                attacker=attacker,
                defender=defender,
                location_id='dark_forest',
            )
        )


if __name__ == '__main__':
    unittest.main()
