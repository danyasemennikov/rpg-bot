from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from database import get_connection
from game.balance import exp_to_next_level
from game.build_contract import MASTERY_MODEL_VERSION, RULES_VERSION
from game.build_progression import (
    apply_attribute_redistribution,
    apply_skill_purchase,
    attribute_redistribution_preview,
    build_migration_audit,
    get_pending_build_notice,
    issue_skill_purchase_intent,
    migrate_character_builds_v1,
    ensure_player_build_v1,
    BuildRejected,
)
from game.gear_progression import ensure_gear_progression_schema
from game.pve_reward_settlement import _apply_progression, recover_prepared_settlements
from handlers.battle import apply_rewards


def test_migration_archives_and_uses_greatest_alias_evidence_and_preserves_live_resources():
    conn = get_connection()
    conn.execute(
        "INSERT INTO weapon_mastery (telegram_id, weapon_id, level, exp, skill_points) VALUES (1, 'practice_staff', 2, 20, 9)"
    )
    conn.execute(
        "INSERT INTO weapon_mastery (telegram_id, weapon_id, level, exp, skill_points) VALUES (1, 'magic_staff', 3, 10, 1)"
    )
    conn.execute("INSERT INTO player_skills (telegram_id, skill_id, level) VALUES (1, 'meteor', 3)")
    battle = {
        "participant_states": {
            "1": {"player_hp": 37, "player_mana": 11},
        }
    }
    conn.execute(
        """INSERT INTO pve_encounters
        (encounter_id, owner_player_id, status, mob_id, battle_state_json, mob_json,
         source_units_json, rules_version)
        VALUES ('old-encounter', 1, 'active', 'rat', ?, '{}', '[]', 'legacy_v0')""",
        (json.dumps(battle),),
    )
    conn.execute(
        "INSERT INTO pve_encounter_participants (encounter_id, player_id) VALUES ('old-encounter', 1)"
    )
    conn.execute(
        """INSERT INTO pve_spawn_instances
        (spawn_instance_id, location_id, mob_id, state, linked_encounter_id)
        VALUES ('spawn-old', 'capital_city', 'rat', 'engaged', 'old-encounter')"""
    )
    conn.commit()
    conn.close()

    result = migrate_character_builds_v1()
    assert result["status"] == "active"
    assert result["cancelled_pve"] == ["old-encounter"]

    conn = get_connection()
    mastery = dict(conn.execute(
        "SELECT * FROM weapon_mastery WHERE telegram_id=1 AND weapon_id='magic_staff'"
    ).fetchone())
    assert mastery["level"] == 3
    assert mastery["exp"] == 4
    assert mastery["skill_points"] == 4
    assert mastery["model_version"] == MASTERY_MODEL_VERSION
    player = dict(conn.execute("SELECT * FROM players WHERE telegram_id=1").fetchone())
    assert (player["hp"], player["mana"]) == (37, 11)
    assert player["attribute_budget"] == 54
    assert player["build_migration_version"] == MASTERY_MODEL_VERSION
    assert [row["skill_id"] for row in conn.execute(
        "SELECT skill_id FROM player_skills WHERE telegram_id=1"
    )] == ["power_strike"]
    archive = conn.execute(
        "SELECT snapshot_json FROM build_migration_archive WHERE player_id=1"
    ).fetchone()
    assert "meteor" in json.loads(archive["snapshot_json"])["skills"][0]["skill_id"]
    spawn = conn.execute(
        "SELECT state, linked_encounter_id, respawn_available_at FROM pve_spawn_instances WHERE spawn_instance_id='spawn-old'"
    ).fetchone()
    assert spawn["state"] == "respawning"
    assert spawn["linked_encounter_id"] is None
    assert spawn["respawn_available_at"] is not None
    conn.close()

    notice = get_pending_build_notice(1)
    assert notice == {
        "free_hub_resets": True,
        "old_fight_ended": True,
        "rules_version": RULES_VERSION,
        "skills_refunded": True,
        "staff_normalized": False,
    }
    assert migrate_character_builds_v1()["status"] == "already_active"
    assert build_migration_audit() == {
        "family_invariant_failures": [],
        "attribute_invariant_failures": [],
    }


def test_migration_dry_run_is_fully_rollback_safe():
    result = migrate_character_builds_v1(dry_run=True)
    assert result["status"] == "dry_run"
    conn = get_connection()
    player = conn.execute(
        "SELECT build_migration_version FROM players WHERE telegram_id=1"
    ).fetchone()
    state = conn.execute(
        "SELECT state FROM build_rules_state WHERE migration_key=?", (RULES_VERSION,)
    ).fetchone()
    assert player["build_migration_version"] == 0
    assert state is None
    conn.close()


def test_cutover_drains_more_than_one_recovery_batch_before_conversion():
    full_batch = [{"status": "applied", "encounter_id": str(index)} for index in range(100)]
    with patch('game.pve_reward_settlement.review_ambiguous_legacy_victories', return_value=0), \
         patch('game.pve_reward_settlement.recover_prepared_settlements', side_effect=[full_batch, []]) as recover:
        result = migrate_character_builds_v1()
    assert result['status'] == 'active'
    assert recover.call_count == 2


def test_legacy_settlement_uses_old_threshold_before_alias_conversion():
    conn = get_connection()
    ensure_gear_progression_schema(conn)
    conn.execute(
        "INSERT INTO weapon_mastery (telegram_id, weapon_id, level, exp, skill_points) "
        "VALUES (1, 'field_sword_1h', 1, 40, 0)"
    )
    conn.execute(
        """INSERT INTO pve_encounters
        (encounter_id, owner_player_id, status, mob_id, battle_state_json, mob_json,
         source_units_json, rules_version)
        VALUES ('legacy-threshold', 1, 'resolving_victory', 'rat', '{}', '{}', '[]', 'legacy_v0')"""
    )
    conn.execute(
        "INSERT INTO pve_encounter_participants (encounter_id, player_id) "
        "VALUES ('legacy-threshold', 1)"
    )
    plan = {
        'schema_version': 1,
        'policy_version': 'legacy_v0',
        'encounter_id': 'legacy-threshold',
        'owner_player_id': 1,
        'location_id': 'capital_city',
        'route_id': None,
        'eligible_recipient_ids': [1],
        'defeated_participant_ids': [],
        'recipients': [],
        'owner_mastery': {
            'player_id': 1,
            'weapon_id': 'field_sword_1h',
            'exp': 10,
        },
    }
    conn.execute(
        """INSERT INTO pve_reward_settlements
        (encounter_id, schema_version, policy_version, status, plan_json)
        VALUES ('legacy-threshold', 1, 'legacy_v0', 'prepared', ?)""",
        (json.dumps(plan),),
    )
    conn.commit()
    conn.close()

    recovered = recover_prepared_settlements()
    assert [item['status'] for item in recovered] == ['applied']
    conn = get_connection()
    before_migration = dict(conn.execute(
        "SELECT weapon_id, level, exp FROM weapon_mastery WHERE telegram_id=1"
    ).fetchone())
    conn.close()
    assert before_migration == {'weapon_id': 'field_sword_1h', 'level': 2, 'exp': 0}
    assert recover_prepared_settlements() == []

    assert migrate_character_builds_v1()['status'] == 'active'
    conn = get_connection()
    after_migration = dict(conn.execute(
        "SELECT weapon_id, level, exp, model_version FROM weapon_mastery WHERE telegram_id=1"
    ).fetchone())
    conn.close()
    assert after_migration == {
        'weapon_id': 'sword_1h', 'level': 2, 'exp': 0,
        'model_version': MASTERY_MODEL_VERSION,
    }
    assert migrate_character_builds_v1()['status'] == 'already_active'


def test_field_item_mastery_normalizes_by_item_profile_and_keeps_best_evidence():
    conn = get_connection()
    conn.execute("INSERT INTO weapon_mastery (telegram_id, weapon_id, level, exp) VALUES (1, 'field_sword_1h', 4, 30)")
    conn.execute("INSERT INTO weapon_mastery (telegram_id, weapon_id, level, exp) VALUES (1, 'wooden_sword', 3, 10)")
    conn.commit()
    conn.close()
    migrate_character_builds_v1()
    conn = get_connection()
    rows = conn.execute("SELECT weapon_id, level FROM weapon_mastery WHERE telegram_id=1").fetchall()
    conn.close()
    assert [(row['weapon_id'], row['level']) for row in rows] == [('sword_1h', 4)]


def test_invalid_player_is_quarantined_without_aborting_other_players_or_lazy_migrating():
    conn = get_connection()
    conn.execute('''INSERT INTO players
        (telegram_id, username, name, level, hp, max_hp, mana, max_mana,
         strength, agility, intuition, vitality, wisdom, luck, stat_points, location_id)
        VALUES (2, 'bad', 'Bad', 1, 100, 100, 50, 50, 1, 1, 1, 1, 1, 1, -1, 'capital_city')''')
    conn.execute("INSERT INTO equipment (telegram_id) VALUES (2)")
    conn.commit()
    conn.close()
    result = migrate_character_builds_v1()
    assert result['migrated'] == 2  # fixture players 1 and 777 still migrate
    assert result['blocked'] == [2]
    conn = get_connection()
    assert conn.execute("SELECT reason FROM build_migration_quarantine WHERE player_id=2").fetchone()['reason'] == 'invalid_attribute_ledger'
    with pytest.raises(BuildRejected, match='migration_quarantined'):
        ensure_player_build_v1(2, conn=conn)
    conn.close()


def test_migration_clamps_current_resources_to_retained_effective_gear_cap():
    conn = get_connection()
    conn.execute("UPDATE players SET hp=300, max_hp=316 WHERE telegram_id=1")
    cursor = conn.execute("INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (1, 'oak_guard_shield', 1)")
    conn.execute("UPDATE equipment SET offhand=? WHERE telegram_id=1", (cursor.lastrowid,))
    conn.commit()
    conn.close()
    migrate_character_builds_v1()
    conn = get_connection()
    player = dict(conn.execute("SELECT hp, max_hp FROM players WHERE telegram_id=1").fetchone())
    conn.close()
    assert player == {'hp': 300, 'max_hp': 280}


def test_atomic_skill_purchase_is_idempotent_and_preserves_family_budget():
    migrate_character_builds_v1()
    issued = issue_skill_purchase_intent(1, "bow", "quick_shot")
    assert issued["legal"] is True
    first = apply_skill_purchase(1, issued["token"])
    second = apply_skill_purchase(1, issued["token"])
    assert first == {
        "success": True, "op": "learn", "family": "bow",
        "skill_id": "quick_shot", "rank": 1,
    }
    assert second["already_applied"] is True
    conn = get_connection()
    mastery = conn.execute(
        "SELECT skill_points FROM weapon_mastery WHERE telegram_id=1 AND weapon_id='bow'"
    ).fetchone()
    assert mastery["skill_points"] == 1
    conn.close()
    assert build_migration_audit()["family_invariant_failures"] == []


def test_attribute_redistribution_uses_frozen_budget_and_recomputes_caps():
    migrate_character_builds_v1()
    attributes = {
        "strength": 1, "agility": 1, "intuition": 1,
        "vitality": 1, "wisdom": 1, "luck": 1,
    }
    preview = attribute_redistribution_preview(1, attributes)
    assert preview["success"] is True
    assert preview["unspent"] == 54
    result = apply_attribute_redistribution(1, preview["token"])
    assert result["success"] is True
    conn = get_connection()
    player = dict(conn.execute("SELECT * FROM players WHERE telegram_id=1").fetchone())
    conn.close()
    assert player["stat_points"] == 54
    assert player["max_hp"] == 118
    assert player["max_mana"] == 62
    assert player["carry_weight"] == 25


def test_settlement_level_up_extends_budget_and_invalidates_prelevel_draft():
    migrate_character_builds_v1()
    attributes = {
        "strength": 10, "agility": 10, "intuition": 10,
        "vitality": 10, "wisdom": 10, "luck": 10,
    }
    preview = attribute_redistribution_preview(1, attributes)
    assert preview["success"] is True

    conn = get_connection()
    conn.execute("BEGIN IMMEDIATE")
    progression = _apply_progression(conn, 1, 100, 0)
    conn.commit()
    player = dict(conn.execute("SELECT * FROM players WHERE telegram_id=1").fetchone())
    conn.close()

    assert progression["level_after"] == 2
    assert player["stat_points"] == 3
    assert player["attribute_budget"] == 57
    assert apply_attribute_redistribution(1, preview["token"]) == {
        "success": False, "reason": "stale_build",
    }
    assert build_migration_audit()["attribute_invariant_failures"] == []


def test_legacy_reward_level_up_extends_budget_and_invalidates_prelevel_draft():
    migrate_character_builds_v1()
    preview = attribute_redistribution_preview(1, {
        "strength": 10, "agility": 10, "intuition": 10,
        "vitality": 10, "wisdom": 10, "luck": 10,
    })
    assert preview["success"] is True

    conn = get_connection()
    player = dict(conn.execute("SELECT * FROM players WHERE telegram_id=1").fetchone())
    old_budget = int(player["attribute_budget"])
    conn.execute(
        "UPDATE players SET exp=? WHERE telegram_id=1",
        (exp_to_next_level(int(player["level"])) - 10,),
    )
    conn.commit()
    player = dict(conn.execute("SELECT * FROM players WHERE telegram_id=1").fetchone())
    conn.close()

    result = apply_rewards(1, player, {
        "exp": 10,
        "gold": 0,
        "loot": [],
        "mob_id": "forest_boar",
        "mob_level": 1,
        "location_id": "westwild_n2",
    })
    assert result["new_level"] == int(player["level"]) + 1

    conn = get_connection()
    advanced = dict(conn.execute("SELECT * FROM players WHERE telegram_id=1").fetchone())
    conn.close()
    assert advanced["stat_points"] == int(player["stat_points"]) + 3
    assert advanced["attribute_budget"] == old_budget + 3
    assert advanced["build_revision"] == int(player["build_revision"]) + 1
    assert apply_attribute_redistribution(1, preview["token"]) == {
        "success": False, "reason": "stale_build",
    }
    assert build_migration_audit()["attribute_invariant_failures"] == []
