from __future__ import annotations

import json

from database import get_connection
from game.build_contract import MASTERY_MODEL_VERSION, RULES_VERSION
from game.build_progression import (
    apply_attribute_redistribution,
    apply_skill_purchase,
    attribute_redistribution_preview,
    build_migration_audit,
    get_pending_build_notice,
    issue_skill_purchase_intent,
    migrate_character_builds_v1,
)


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

