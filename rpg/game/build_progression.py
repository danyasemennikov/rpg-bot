"""Persistence, migration and atomic mutations for build V1.

All public mutators validate a server-side intent under ``BEGIN IMMEDIATE``.
They intentionally accept a caller-owned SQLite connection only through the
small helpers used by settlement/migration; Telegram handlers never update the
build tables directly.
"""

from __future__ import annotations

import json
import math
import sqlite3
from typing import Any

from database import get_connection
from game.action_receipts import ActionRejected, consume_action, issue_actions, peaceful_player
from game.build_contract import (
    FAMILIES,
    MAX_MASTERY,
    MAX_SKILL_RANK,
    MIGRATION_KEY,
    MASTERY_MODEL_VERSION,
    RETIRED_SKILL_IDS,
    RULES_VERSION,
    SAFE_BUILD_HUBS,
    SKILL_SPECS,
    SKILL_TREES,
    legal_family_budget,
    mastery_exp_needed,
    normalize_family,
)


ATTRIBUTE_KEYS = ("strength", "agility", "intuition", "vitality", "wisdom", "luck")
BUILD_ACTION_KIND = "build_v1"
MIGRATION_NOTICE_KEY = "build_v1_migrated"


class BuildRejected(ValueError):
    """A stable public rejection reason for forged, stale or illegal changes."""


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column(conn: sqlite3.Connection, table: str, name: str, definition: str) -> None:
    if name not in _column_names(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def ensure_build_schema(conn: sqlite3.Connection) -> None:
    """Install only additive build/rules tables and columns."""
    _add_column(conn, "players", "build_revision", "INTEGER NOT NULL DEFAULT 0")
    _add_column(conn, "players", "attribute_budget", "INTEGER")
    _add_column(conn, "players", "build_migration_version", "INTEGER NOT NULL DEFAULT 0")
    _add_column(conn, "players", "build_notice_pending", "INTEGER NOT NULL DEFAULT 0")
    _add_column(conn, "weapon_mastery", "model_version", "INTEGER NOT NULL DEFAULT 0")

    if _table_exists(conn, "pve_encounters"):
        _add_column(conn, "pve_encounters", "rules_version", "TEXT NOT NULL DEFAULT 'legacy_v0'")
        _add_column(conn, "pve_encounters", "combat_seed", "TEXT")
        _add_column(conn, "pve_encounters", "turn_revision", "INTEGER NOT NULL DEFAULT 0")
    if _table_exists(conn, "pvp_engagements"):
        _add_column(conn, "pvp_engagements", "rules_version", "TEXT NOT NULL DEFAULT 'legacy_v0'")
        _add_column(conn, "pvp_engagements", "combat_seed", "TEXT")
        _add_column(conn, "pvp_engagements", "turn_revision", "INTEGER NOT NULL DEFAULT 0")

    conn.execute('''CREATE TABLE IF NOT EXISTS build_rules_state (
        migration_key TEXT PRIMARY KEY,
        rules_version TEXT NOT NULL,
        state TEXT NOT NULL,
        details_json TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS build_migration_archive (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        migration_version INTEGER NOT NULL,
        snapshot_json TEXT NOT NULL,
        audit_flags_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, migration_version)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS build_mutation_receipts (
        token TEXT PRIMARY KEY,
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        kind TEXT NOT NULL,
        result_json TEXT NOT NULL,
        build_revision INTEGER NOT NULL,
        gear_revision INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS combat_orders_v1 (
        encounter_kind TEXT NOT NULL,
        encounter_id TEXT NOT NULL,
        turn_revision INTEGER NOT NULL,
        actor_id INTEGER NOT NULL,
        action_json TEXT NOT NULL,
        target_id TEXT,
        rules_version TEXT NOT NULL,
        deadline_at TEXT NOT NULL,
        order_kind TEXT NOT NULL DEFAULT 'manual',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (encounter_kind, encounter_id, turn_revision, actor_id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS combat_turn_results_v1 (
        encounter_kind TEXT NOT NULL,
        encounter_id TEXT NOT NULL,
        turn_revision INTEGER NOT NULL,
        result_json TEXT NOT NULL,
        state_json TEXT NOT NULL,
        rules_version TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (encounter_kind, encounter_id, turn_revision)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS player_build_notices (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        notice_key TEXT NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        consumed_at TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, notice_key)
    )''')


def install_build_schema() -> None:
    conn = get_connection()
    try:
        ensure_build_schema(conn)
        conn.commit()
    finally:
        conn.close()


def normal_attribute_budget(level: int) -> int:
    return 6 + (3 * (max(1, int(level)) - 1))


def observed_attribute_budget(player: dict[str, Any]) -> int:
    points = int(player.get("stat_points", 0))
    if points < 0:
        raise BuildRejected("invalid_attribute_ledger")
    values = []
    for key in ATTRIBUTE_KEYS:
        value = int(player.get(key, 1))
        if value < 1:
            raise BuildRejected("invalid_attribute_ledger")
        values.append(value)
    return points + sum(value - 1 for value in values)


def _old_total_exp(level: int, within_level_exp: int) -> int:
    level = max(1, min(MAX_MASTERY, int(level)))
    return max(0, int(within_level_exp)) + 25 * (level - 1) * level


def _convert_old_mastery(level: int, old_exp: int) -> tuple[int, int]:
    level = max(1, min(MAX_MASTERY, int(level)))
    if level >= MAX_MASTERY:
        return MAX_MASTERY, 0
    old_threshold = 50 * level
    fraction = max(0.0, min(1.0, max(0, int(old_exp)) / old_threshold))
    converted = math.floor(fraction * mastery_exp_needed(level))
    if converted >= mastery_exp_needed(level):
        return min(MAX_MASTERY, level + 1), 0
    return level, converted


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _archive_player(conn: sqlite3.Connection, player: dict[str, Any]) -> tuple[dict, list[str]]:
    player_id = int(player["telegram_id"])
    snapshot = {
        "player": {key: player.get(key) for key in player},
        "masteries": _rows(conn, "SELECT * FROM weapon_mastery WHERE telegram_id=? ORDER BY weapon_id", (player_id,)),
        "skills": _rows(conn, "SELECT * FROM player_skills WHERE telegram_id=? ORDER BY skill_id", (player_id,)),
        "cooldowns": _rows(conn, "SELECT * FROM skill_cooldowns WHERE telegram_id=? ORDER BY skill_id", (player_id,)),
    }
    flags: list[str] = []
    observed = observed_attribute_budget(player)
    expected = normal_attribute_budget(int(player.get("level", 1)))
    if observed > expected:
        flags.append(f"historic_attribute_excess:{observed - expected}")
    unknown = sorted(
        row["skill_id"] for row in snapshot["skills"]
        if row["skill_id"] not in SKILL_SPECS
        and row["skill_id"] != "power_strike"
        and row["skill_id"] not in RETIRED_SKILL_IDS
    )
    if unknown:
        flags.append("unknown_skills:" + ",".join(unknown))
    conn.execute('''INSERT OR IGNORE INTO build_migration_archive
        (player_id, migration_version, snapshot_json, audit_flags_json)
        VALUES (?, ?, ?, ?)''', (player_id, MASTERY_MODEL_VERSION, _json(snapshot), _json(flags)))
    return snapshot, flags


def _normalize_masteries(snapshot: dict[str, Any]) -> list[dict[str, int | str]]:
    grouped: dict[str, list[dict]] = {}
    for row in snapshot["masteries"]:
        family = normalize_family(row.get("weapon_id"))
        if family not in FAMILIES:
            continue
        grouped.setdefault(family, []).append(row)
    normalized = []
    for family, rows in grouped.items():
        # Alias/canonical duplicates are alternative evidence, never additive.
        best = max(rows, key=lambda row: _old_total_exp(row.get("level", 1), row.get("exp", 0)))
        level, exp = _convert_old_mastery(best.get("level", 1), best.get("exp", 0))
        normalized.append({
            "family": family,
            "level": level,
            "exp": exp,
            "skill_points": legal_family_budget(level),
        })
    return sorted(normalized, key=lambda item: FAMILIES.index(str(item["family"])))


def _player_has_staff(conn: sqlite3.Connection, player_id: int) -> bool:
    params = (player_id,)
    instance = conn.execute('''SELECT 1 FROM gear_instances gi
        WHERE gi.telegram_id=? AND gi.base_item_id='magic_staff' LIMIT 1''', params).fetchone()
    if instance:
        return True
    legacy = conn.execute('''SELECT 1 FROM inventory inv JOIN items i ON i.item_id=inv.item_id
        WHERE inv.telegram_id=? AND i.item_id='magic_staff' LIMIT 1''', params).fetchone()
    return legacy is not None


def _cancel_old_pve(conn: sqlite3.Connection) -> list[str]:
    if not _table_exists(conn, "pve_encounters"):
        return []
    ensure_build_schema(conn)
    rows = _rows(conn, '''SELECT encounter_id, battle_state_json FROM pve_encounters
        WHERE status IN ('forming','active') AND rules_version<>?''', (RULES_VERSION,))
    encounter_ids = [str(row["encounter_id"]) for row in rows]
    if not encounter_ids:
        return []
    for row in rows:
        try:
            battle = json.loads(str(row.get("battle_state_json") or "{}"))
        except (TypeError, ValueError):
            battle = {}
        state_map = battle.get("participant_states_v1") or battle.get("participant_states") or {}
        if not isinstance(state_map, dict):
            continue
        for raw_player_id, state in state_map.items():
            if not isinstance(state, dict):
                continue
            try:
                participant_id = int(raw_player_id)
                hp = int(state.get("hp", state.get("player_hp")))
                mana = int(state.get("mana", state.get("player_mana")))
            except (TypeError, ValueError):
                continue
            conn.execute(
                "UPDATE players SET hp=MAX(0, ?), mana=MAX(0, ?) WHERE telegram_id=?",
                (hp, mana, participant_id),
            )
    placeholders = ",".join("?" for _ in encounter_ids)
    conn.execute(f'''UPDATE pve_encounters SET status='rules_updated', finished_at=CURRENT_TIMESTAMP,
        updated_at=CURRENT_TIMESTAMP WHERE encounter_id IN ({placeholders})''', encounter_ids)
    conn.execute(f'''UPDATE pve_encounter_participants SET status='rules_updated', updated_at=CURRENT_TIMESTAMP
        WHERE encounter_id IN ({placeholders}) AND status='active' ''', encounter_ids)
    if _table_exists(conn, "pve_spawn_instances"):
        # This is the existing non-victory path: the exact sources enter their
        # ordinary respawn, never immediate idle availability.
        conn.execute(f'''UPDATE pve_spawn_instances SET state='respawning', linked_encounter_id=NULL,
            respawn_available_at=datetime('now', '+30 seconds'), updated_at=CURRENT_TIMESTAMP
            WHERE linked_encounter_id IN ({placeholders})''', encounter_ids)
    conn.execute(f'''UPDATE players SET in_battle=0 WHERE telegram_id IN (
        SELECT player_id FROM pve_encounter_participants WHERE encounter_id IN ({placeholders})
    )''', encounter_ids)
    for encounter_id in encounter_ids:
        conn.execute('''INSERT OR IGNORE INTO combat_turn_results_v1
            (encounter_kind, encounter_id, turn_revision, result_json, state_json, rules_version)
            VALUES ('pve', ?, -1, ?, '{}', ?)''', (
                encounter_id,
                _json({"status": "rules_updated", "rewards": False, "penalty": False}),
                RULES_VERSION,
            ))
    return encounter_ids


def _cancel_old_pvp(conn: sqlite3.Connection) -> list[int]:
    if not _table_exists(conn, "pvp_engagements"):
        return []
    ensure_build_schema(conn)
    rows = _rows(conn, '''SELECT id, attacker_id, defender_id, reason_context FROM pvp_engagements
        WHERE engagement_state IN ('pending','active','converted_to_battle') AND rules_version<>?''', (RULES_VERSION,))
    ids = [int(row["id"]) for row in rows]
    for row in rows:
        try:
            old_payload = json.loads(str(row.get("reason_context") or "{}"))
        except (TypeError, ValueError):
            old_payload = {}
        battle = old_payload.get("battle") if isinstance(old_payload, dict) else None
        if isinstance(battle, dict):
            for role in ("attacker", "defender"):
                player_id = int(row[f"{role}_id"])
                hp = battle.get(f"{role}_hp")
                mana = battle.get(f"{role}_mana")
                assignments = []
                values: list[int] = []
                if hp is not None:
                    assignments.append("hp=MAX(0, ?)")
                    values.append(int(hp))
                if mana is not None:
                    assignments.append("mana=MAX(0, ?)")
                    values.append(int(mana))
                if assignments:
                    conn.execute(
                        f"UPDATE players SET {', '.join(assignments)} WHERE telegram_id=?",
                        (*values, player_id),
                    )
        payload = {"flow": "rules_updated", "winner_id": None, "transfer": False, "defeat_loss": False}
        conn.execute('''UPDATE pvp_engagements SET engagement_state='cancelled', reason_context=?
            WHERE id=?''', (_json(payload), int(row["id"])))
        conn.execute("UPDATE players SET in_battle=0 WHERE telegram_id IN (?, ?)", (
            int(row["attacker_id"]), int(row["defender_id"]),
        ))
        conn.execute('''INSERT OR IGNORE INTO combat_turn_results_v1
            (encounter_kind, encounter_id, turn_revision, result_json, state_json, rules_version)
            VALUES ('pvp', ?, -1, ?, '{}', ?)''', (
                str(row["id"]), _json(payload), RULES_VERSION,
            ))
    return ids


def _has_reward_review(conn: sqlite3.Connection, player_id: int) -> bool:
    if not _table_exists(conn, "pve_reward_settlements") or not _table_exists(conn, "pve_encounter_participants"):
        return False
    return conn.execute('''SELECT 1 FROM pve_reward_settlements s
        JOIN pve_encounter_participants p ON p.encounter_id=s.encounter_id
        WHERE p.player_id=? AND s.status='legacy_review' LIMIT 1''', (player_id,)).fetchone() is not None


def _migrate_player(
    conn: sqlite3.Connection, player_id: int, *, old_fight_ended: bool = False,
) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM players WHERE telegram_id=?", (player_id,)).fetchone()
    if not row:
        raise BuildRejected("no_player")
    player = dict(row)
    if int(player.get("build_migration_version", 0)) >= MASTERY_MODEL_VERSION:
        return {"status": "already_migrated", "player_id": player_id}
    if _has_reward_review(conn, player_id):
        return {"status": "legacy_review", "player_id": player_id}
    snapshot, flags = _archive_player(conn, player)
    budget = observed_attribute_budget(player)
    masteries = _normalize_masteries(snapshot)
    conn.execute("DELETE FROM weapon_mastery WHERE telegram_id=?", (player_id,))
    conn.executemany('''INSERT INTO weapon_mastery
        (telegram_id, weapon_id, level, exp, skill_points, model_version)
        VALUES (?, ?, ?, ?, ?, ?)''', (
            (player_id, item["family"], item["level"], item["exp"], item["skill_points"], MASTERY_MODEL_VERSION)
            for item in masteries
        ))
    conn.execute("DELETE FROM player_skills WHERE telegram_id=?", (player_id,))
    conn.execute("INSERT INTO player_skills (telegram_id, skill_id, level) VALUES (?, 'power_strike', 1)", (player_id,))
    conn.execute("DELETE FROM skill_cooldowns WHERE telegram_id=?", (player_id,))
    staff_changed = _player_has_staff(conn, player_id)
    max_hp = 100 + (18 * int(player["vitality"]))
    max_mana = 50 + (12 * int(player["wisdom"]))
    conn.execute('''UPDATE players SET attribute_budget=?, max_hp=?, max_mana=?,
        hp=MIN(hp, ?), mana=MIN(mana, ?), build_revision=build_revision+1,
        build_migration_version=?, build_notice_pending=1 WHERE telegram_id=?''', (
            budget, max_hp, max_mana, max_hp, max_mana, MASTERY_MODEL_VERSION, player_id,
        ))
    notice = {
        "skills_refunded": True,
        "free_hub_resets": True,
        "staff_normalized": staff_changed,
        "old_fight_ended": bool(old_fight_ended),
        "rules_version": RULES_VERSION,
    }
    conn.execute('''INSERT OR REPLACE INTO player_build_notices
        (player_id, notice_key, payload_json, consumed_at) VALUES (?, ?, ?, NULL)''', (
            player_id, MIGRATION_NOTICE_KEY, _json(notice),
        ))
    return {
        "status": "migrated",
        "player_id": player_id,
        "attribute_budget": budget,
        "masteries": masteries,
        "audit_flags": flags,
        "staff_normalized": staff_changed,
    }


def migrate_character_builds_v1(*, dry_run: bool = False) -> dict[str, Any]:
    """Idempotently activate the frozen rules after old settlements recover."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_build_schema(conn)
        current = conn.execute(
            "SELECT state FROM build_rules_state WHERE migration_key=?", (MIGRATION_KEY,)
        ).fetchone()
        if current and str(current["state"]) == "active":
            conn.rollback()
            return {"status": "already_active", "migrated": 0, "blocked": []}
        conn.execute('''INSERT OR REPLACE INTO build_rules_state
            (migration_key, rules_version, state, details_json, updated_at)
            VALUES (?, ?, 'migrating', '{}', CURRENT_TIMESTAMP)''', (MIGRATION_KEY, RULES_VERSION))
        cancelled_pve = _cancel_old_pve(conn)
        cancelled_pvp = _cancel_old_pvp(conn)
        affected_players: set[int] = set()
        if cancelled_pve:
            placeholders = ",".join("?" for _ in cancelled_pve)
            affected_players.update(
                int(row["player_id"])
                for row in conn.execute(
                    f"SELECT player_id FROM pve_encounter_participants WHERE encounter_id IN ({placeholders})",
                    cancelled_pve,
                )
            )
        if cancelled_pvp:
            placeholders = ",".join("?" for _ in cancelled_pvp)
            for row in conn.execute(
                f"SELECT attacker_id, defender_id FROM pvp_engagements WHERE id IN ({placeholders})",
                cancelled_pvp,
            ):
                affected_players.update((int(row["attacker_id"]), int(row["defender_id"])))
        players = [int(row["telegram_id"]) for row in conn.execute("SELECT telegram_id FROM players ORDER BY telegram_id")]
        results = [
            _migrate_player(conn, player_id, old_fight_ended=player_id in affected_players)
            for player_id in players
        ]
        blocked = [item["player_id"] for item in results if item["status"] == "legacy_review"]
        details = {
            "migrated": sum(item["status"] == "migrated" for item in results),
            "blocked": blocked,
            "cancelled_pve": cancelled_pve,
            "cancelled_pvp": cancelled_pvp,
        }
        conn.execute('''UPDATE build_rules_state SET state='active', details_json=?,
            updated_at=CURRENT_TIMESTAMP WHERE migration_key=?''', (_json(details), MIGRATION_KEY))
        if dry_run:
            conn.rollback()
            return {"status": "dry_run", **details}
        conn.commit()
        return {"status": "active", **details}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_player_build_v1(player_id: int, *, conn: sqlite3.Connection) -> dict[str, Any]:
    ensure_build_schema(conn)
    row = conn.execute("SELECT build_migration_version FROM players WHERE telegram_id=?", (player_id,)).fetchone()
    if not row:
        raise BuildRejected("no_player")
    if int(row["build_migration_version"] or 0) < MASTERY_MODEL_VERSION:
        return _migrate_player(conn, player_id)
    return {"status": "ready", "player_id": player_id}


def get_pending_build_notice(player_id: int, *, consume: bool = False) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        ensure_build_schema(conn)
        row = conn.execute('''SELECT payload_json FROM player_build_notices
            WHERE player_id=? AND notice_key=? AND consumed_at IS NULL''', (player_id, MIGRATION_NOTICE_KEY)).fetchone()
        if not row:
            return None
        payload = json.loads(str(row["payload_json"]))
        if consume:
            conn.execute('''UPDATE player_build_notices SET consumed_at=CURRENT_TIMESTAMP
                WHERE player_id=? AND notice_key=? AND consumed_at IS NULL''', (player_id, MIGRATION_NOTICE_KEY))
            conn.execute("UPDATE players SET build_notice_pending=0 WHERE telegram_id=?", (player_id,))
            conn.commit()
        return payload
    finally:
        conn.close()


def create_family_if_needed(player_id: int, family: str, *, conn: sqlite3.Connection) -> dict[str, Any]:
    family = normalize_family(family)
    if family not in FAMILIES:
        raise BuildRejected("unknown_family")
    ensure_player_build_v1(player_id, conn=conn)
    conn.execute('''INSERT OR IGNORE INTO weapon_mastery
        (telegram_id, weapon_id, level, exp, skill_points, model_version)
        VALUES (?, ?, 1, 0, 2, ?)''', (player_id, family, MASTERY_MODEL_VERSION))
    return dict(conn.execute('''SELECT * FROM weapon_mastery
        WHERE telegram_id=? AND weapon_id=?''', (player_id, family)).fetchone())


def family_skill_ranks(player_id: int, family: str, *, conn: sqlite3.Connection) -> dict[str, int]:
    family = normalize_family(family)
    if family not in FAMILIES:
        return {}
    ids = [skill_id for branch in SKILL_TREES[family].values() for skill_id in branch]
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(f'''SELECT skill_id, level FROM player_skills
        WHERE telegram_id=? AND skill_id IN ({placeholders})''', (player_id, *ids)).fetchall()
    return {str(row["skill_id"]): max(0, min(MAX_SKILL_RANK, int(row["level"]))) for row in rows}


def validate_family_invariant(player_id: int, family: str, *, conn: sqlite3.Connection) -> bool:
    mastery = create_family_if_needed(player_id, family, conn=conn)
    ranks = family_skill_ranks(player_id, family, conn=conn)
    return sum(ranks.values()) + int(mastery["skill_points"]) == legal_family_budget(int(mastery["level"]))


def _parse_intent(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise BuildRejected("malformed_intent") from exc
    if not isinstance(payload, dict) or payload.get("rules_version") != RULES_VERSION:
        raise BuildRejected("stale_action")
    return payload


def _receipt(conn: sqlite3.Connection, token: str, player_id: int) -> dict[str, Any] | None:
    row = conn.execute('''SELECT result_json FROM build_mutation_receipts
        WHERE token=? AND player_id=?''', (token, player_id)).fetchone()
    return json.loads(str(row["result_json"])) if row else None


def _store_receipt(conn: sqlite3.Connection, token: str, player_id: int, kind: str, result: dict[str, Any]) -> None:
    revisions = conn.execute('''SELECT build_revision, gear_revision FROM players
        WHERE telegram_id=?''', (player_id,)).fetchone()
    conn.execute('''INSERT INTO build_mutation_receipts
        (token, player_id, kind, result_json, build_revision, gear_revision)
        VALUES (?, ?, ?, ?, ?, ?)''', (
            token, player_id, kind, _json(result), int(revisions["build_revision"]), int(revisions["gear_revision"]),
        ))


def _validate_intent_authority(conn: sqlite3.Connection, player_id: int, intent: dict[str, Any]) -> dict[str, Any]:
    player = peaceful_player(conn, player_id)
    if int(player.get("build_revision", 0)) != int(intent.get("build_revision", -1)):
        raise BuildRejected("stale_build")
    if int(player.get("gear_revision", 0)) != int(intent.get("gear_revision", -1)):
        raise BuildRejected("stale_gear")
    return player


def apply_skill_purchase(player_id: int, token: str) -> dict[str, Any]:
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_build_schema(conn)
        duplicate = _receipt(conn, token, player_id)
        if duplicate is not None:
            conn.rollback()
            return {**duplicate, "already_applied": True}
        raw = consume_action(conn, player_id, BUILD_ACTION_KIND, token)
        intent = _parse_intent(raw)
        if intent.get("op") != "learn":
            raise BuildRejected("wrong_intent")
        _validate_intent_authority(conn, player_id, intent)
        family = normalize_family(intent.get("family"))
        skill_id = str(intent.get("skill_id") or "")
        spec = SKILL_SPECS.get(skill_id)
        if not spec or family not in FAMILIES or spec.family != family:
            raise BuildRejected("wrong_family")
        mastery = create_family_if_needed(player_id, family, conn=conn)
        ranks = family_skill_ranks(player_id, family, conn=conn)
        current = int(ranks.get(skill_id, 0))
        wanted = current + 1
        if wanted > MAX_SKILL_RANK:
            raise BuildRejected("max_rank")
        rank_requirement = {1: spec.unlock_mastery, 2: 4, 3: 10}[wanted]
        if int(mastery["level"]) < rank_requirement:
            raise BuildRejected("mastery_required")
        if wanted == 1 and spec.position == 4:
            branch_other = [item for item in SKILL_TREES[family][spec.branch] if item != skill_id]
            if sum(ranks.get(item, 0) for item in branch_other) < 8:
                raise BuildRejected("capstone_branch_points_required")
        if int(mastery["skill_points"]) < 1:
            raise BuildRejected("no_points")
        conn.execute('''INSERT INTO player_skills (telegram_id, skill_id, level) VALUES (?, ?, 1)
            ON CONFLICT(telegram_id, skill_id) DO UPDATE SET level=level+1''', (player_id, skill_id))
        updated = conn.execute('''UPDATE weapon_mastery SET skill_points=skill_points-1
            WHERE telegram_id=? AND weapon_id=? AND skill_points>0''', (player_id, family))
        if updated.rowcount != 1:
            raise BuildRejected("conflict")
        conn.execute("UPDATE players SET build_revision=build_revision+1 WHERE telegram_id=?", (player_id,))
        result = {"success": True, "op": "learn", "family": family, "skill_id": skill_id, "rank": wanted}
        _store_receipt(conn, token, player_id, "learn", result)
        if not validate_family_invariant(player_id, family, conn=conn):
            raise RuntimeError("family_budget_invariant")
        conn.commit()
        return result
    except (ActionRejected, BuildRejected) as exc:
        conn.rollback()
        return {"success": False, "reason": str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _required_unequips(conn: sqlite3.Connection, player_id: int, attributes: dict[str, int], level: int) -> list[dict[str, Any]]:
    from game.gear_instances import get_equipped_gear_instances, resolve_gear_instance_item_data

    result = []
    for slot, instance in get_equipped_gear_instances(player_id, conn=conn).items():
        item = resolve_gear_instance_item_data(instance)
        requirements = {
            "level": int(item.get("req_level", 1) or 1),
            "strength": int(item.get("req_strength", 0) or 0),
            "agility": int(item.get("req_agility", 0) or 0),
            "intuition": int(item.get("req_intuition", 0) or 0),
            "wisdom": int(item.get("req_wisdom", 0) or 0),
        }
        valid = level >= requirements["level"] and all(
            attributes[key] >= requirements[key] for key in ("strength", "agility", "intuition", "wisdom")
        )
        if not valid:
            result.append({
                "slot": slot,
                "instance_id": int(instance["id"]),
                "item_id": str(instance["base_item_id"]),
                "name": str(item.get("name") or instance["base_item_id"]),
            })
    return sorted(result, key=lambda item: (item["slot"], item["instance_id"]))


def apply_attribute_redistribution(player_id: int, token: str) -> dict[str, Any]:
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_build_schema(conn)
        duplicate = _receipt(conn, token, player_id)
        if duplicate is not None:
            conn.rollback()
            return {**duplicate, "already_applied": True}
        raw = consume_action(conn, player_id, BUILD_ACTION_KIND, token)
        intent = _parse_intent(raw)
        if intent.get("op") != "attributes":
            raise BuildRejected("wrong_intent")
        player = _validate_intent_authority(conn, player_id, intent)
        location = str(player.get("location_id") or "")
        if location not in SAFE_BUILD_HUBS:
            raise BuildRejected("safe_hub_required")
        proposed = intent.get("attributes")
        if not isinstance(proposed, dict) or set(proposed) != set(ATTRIBUTE_KEYS):
            raise BuildRejected("malformed_attributes")
        attributes = {key: int(proposed[key]) for key in ATTRIBUTE_KEYS}
        if any(value < 1 or value > 100 for value in attributes.values()):
            raise BuildRejected("attribute_bounds")
        budget = int(player.get("attribute_budget") if player.get("attribute_budget") is not None else observed_attribute_budget(player))
        spent = sum(value - 1 for value in attributes.values())
        if spent > budget:
            raise BuildRejected("attribute_budget")
        if intent.get("unequips") != _required_unequips(conn, player_id, attributes, int(player["level"])):
            raise BuildRejected("stale_gear_preview")
        unequips = _required_unequips(conn, player_id, attributes, int(player["level"]))
        for item in unequips:
            conn.execute('''UPDATE gear_instances SET equipped_slot=NULL, revision=revision+1
                WHERE telegram_id=? AND id=? AND equipped_slot=?''', (
                    player_id, item["instance_id"], item["slot"],
                ))
        max_hp = 100 + (18 * attributes["vitality"])
        max_mana = 50 + (12 * attributes["wisdom"])
        values = [attributes[key] for key in ATTRIBUTE_KEYS]
        gear_changed = bool(unequips)
        conn.execute('''UPDATE players SET strength=?, agility=?, intuition=?, vitality=?, wisdom=?, luck=?,
            stat_points=?, max_hp=?, max_mana=?, hp=MIN(hp, ?), mana=MIN(mana, ?),
            carry_weight=?, build_revision=build_revision+1,
            gear_revision=gear_revision+? WHERE telegram_id=?''', (
                *values, budget - spent, max_hp, max_mana, max_hp, max_mana,
                20 + 5 * attributes["strength"], int(gear_changed), player_id,
            ))
        result = {"success": True, "op": "attributes", "attributes": attributes, "unspent": budget - spent, "unequipped": unequips}
        _store_receipt(conn, token, player_id, "attributes", result)
        conn.commit()
        return result
    except (ActionRejected, BuildRejected, TypeError, ValueError) as exc:
        conn.rollback()
        return {"success": False, "reason": str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def apply_family_reset(player_id: int, token: str) -> dict[str, Any]:
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_build_schema(conn)
        duplicate = _receipt(conn, token, player_id)
        if duplicate is not None:
            conn.rollback()
            return {**duplicate, "already_applied": True}
        raw = consume_action(conn, player_id, BUILD_ACTION_KIND, token)
        intent = _parse_intent(raw)
        if intent.get("op") != "reset_family":
            raise BuildRejected("wrong_intent")
        player = _validate_intent_authority(conn, player_id, intent)
        if str(player.get("location_id") or "") not in SAFE_BUILD_HUBS:
            raise BuildRejected("safe_hub_required")
        family = normalize_family(intent.get("family"))
        mastery = create_family_if_needed(player_id, family, conn=conn)
        ranks = family_skill_ranks(player_id, family, conn=conn)
        expected = {skill_id: ranks[skill_id] for skill_id in sorted(ranks)}
        if intent.get("ranks") != expected:
            raise BuildRejected("stale_build")
        ids = [skill_id for branch in SKILL_TREES[family].values() for skill_id in branch]
        placeholders = ",".join("?" for _ in ids)
        conn.execute(f"DELETE FROM player_skills WHERE telegram_id=? AND skill_id IN ({placeholders})", (player_id, *ids))
        conn.execute('''UPDATE weapon_mastery SET skill_points=? WHERE telegram_id=? AND weapon_id=?''', (
            legal_family_budget(int(mastery["level"])), player_id, family,
        ))
        conn.execute("UPDATE players SET build_revision=build_revision+1 WHERE telegram_id=?", (player_id,))
        result = {"success": True, "op": "reset_family", "family": family, "refunded": sum(ranks.values())}
        _store_receipt(conn, token, player_id, "reset_family", result)
        conn.commit()
        return result
    except (ActionRejected, BuildRejected) as exc:
        conn.rollback()
        return {"success": False, "reason": str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def build_intent_payload(player: dict[str, Any], op: str, **payload: Any) -> str:
    """Create the server-stored payload used by ``issue_actions``."""
    return _json({
        "rules_version": RULES_VERSION,
        "op": op,
        "build_revision": int(player.get("build_revision", 0)),
        "gear_revision": int(player.get("gear_revision", 0)),
        **payload,
    })


def issue_skill_purchase_intent(player_id: int, family: str, skill_id: str) -> dict[str, Any]:
    conn = get_connection()
    try:
        ensure_build_schema(conn)
        player_row = conn.execute("SELECT * FROM players WHERE telegram_id=?", (player_id,)).fetchone()
        if not player_row:
            return {"success": False, "reason": "no_player"}
        player = dict(player_row)
        peaceful_player(conn, player_id)
        family = normalize_family(family)
        spec = SKILL_SPECS.get(skill_id)
        if not spec or spec.family != family:
            return {"success": False, "reason": "wrong_family"}
        mastery = create_family_if_needed(player_id, family, conn=conn)
        ranks = family_skill_ranks(player_id, family, conn=conn)
        current = int(ranks.get(skill_id, 0))
        wanted = current + 1
        if wanted > MAX_SKILL_RANK:
            return {"success": False, "reason": "max_rank"}
        requirement = {1: spec.unlock_mastery, 2: 4, 3: 10}[wanted]
        capstone_spent = None
        if wanted == 1 and spec.position == 4:
            capstone_spent = sum(ranks.get(item, 0) for item in SKILL_TREES[family][spec.branch] if item != skill_id)
        payload = build_intent_payload(player, "learn", family=family, skill_id=skill_id)
        conn.commit()
    except ActionRejected as exc:
        return {"success": False, "reason": str(exc)}
    finally:
        conn.close()
    tokens = issue_actions(player_id, BUILD_ACTION_KIND, [payload])
    return {
        "success": True,
        "token": tokens[payload],
        "family": family,
        "skill_id": skill_id,
        "current_rank": current,
        "next_rank": wanted,
        "mastery_level": int(mastery["level"]),
        "mastery_required": requirement,
        "points": int(mastery["skill_points"]),
        "capstone_branch_spent": capstone_spent,
        "legal": (
            int(mastery["level"]) >= requirement
            and int(mastery["skill_points"]) > 0
            and (capstone_spent is None or capstone_spent >= 8)
        ),
    }


def attribute_redistribution_preview(player_id: int, attributes: dict[str, int]) -> dict[str, Any]:
    conn = get_connection()
    try:
        ensure_build_schema(conn)
        row = conn.execute("SELECT * FROM players WHERE telegram_id=?", (player_id,)).fetchone()
        if not row:
            return {"success": False, "reason": "no_player"}
        player = dict(row)
        peaceful_player(conn, player_id)
        if str(player.get("location_id") or "") not in SAFE_BUILD_HUBS:
            return {"success": False, "reason": "safe_hub_required"}
        if set(attributes) != set(ATTRIBUTE_KEYS):
            return {"success": False, "reason": "malformed_attributes"}
        normalized = {key: int(attributes[key]) for key in ATTRIBUTE_KEYS}
        if any(value < 1 or value > 100 for value in normalized.values()):
            return {"success": False, "reason": "attribute_bounds"}
        budget = int(player.get("attribute_budget") if player.get("attribute_budget") is not None else observed_attribute_budget(player))
        spent = sum(value - 1 for value in normalized.values())
        if spent > budget:
            return {"success": False, "reason": "attribute_budget"}
        unequips = _required_unequips(conn, player_id, normalized, int(player["level"]))
        payload = build_intent_payload(player, "attributes", attributes=normalized, unequips=unequips)
    except (ActionRejected, BuildRejected, ValueError, TypeError) as exc:
        return {"success": False, "reason": str(exc)}
    finally:
        conn.close()
    tokens = issue_actions(player_id, BUILD_ACTION_KIND, [payload])
    return {
        "success": True, "token": tokens[payload], "attributes": normalized,
        "unspent": budget - spent, "unequips": unequips,
        "max_hp": 100 + 18 * normalized["vitality"],
        "max_mana": 50 + 12 * normalized["wisdom"],
        "carry_weight": 20 + 5 * normalized["strength"],
    }


def issue_family_reset_intent(player_id: int, family: str) -> dict[str, Any]:
    conn = get_connection()
    try:
        ensure_build_schema(conn)
        row = conn.execute("SELECT * FROM players WHERE telegram_id=?", (player_id,)).fetchone()
        if not row:
            return {"success": False, "reason": "no_player"}
        player = dict(row)
        peaceful_player(conn, player_id)
        if str(player.get("location_id") or "") not in SAFE_BUILD_HUBS:
            return {"success": False, "reason": "safe_hub_required"}
        family = normalize_family(family)
        mastery = create_family_if_needed(player_id, family, conn=conn)
        ranks = family_skill_ranks(player_id, family, conn=conn)
        encoded_ranks = {skill_id: ranks[skill_id] for skill_id in sorted(ranks)}
        payload = build_intent_payload(player, "reset_family", family=family, ranks=encoded_ranks)
        conn.commit()
    except (ActionRejected, BuildRejected) as exc:
        return {"success": False, "reason": str(exc)}
    finally:
        conn.close()
    tokens = issue_actions(player_id, BUILD_ACTION_KIND, [payload])
    return {
        "success": True, "token": tokens[payload], "family": family,
        "mastery_level": int(mastery["level"]), "ranks": encoded_ranks,
        "refund": sum(encoded_ranks.values()),
    }


def build_migration_audit(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    owns = conn is None
    if owns:
        conn = get_connection()
    try:
        ensure_build_schema(conn)
        broken_families = []
        for row in conn.execute("SELECT telegram_id, weapon_id FROM weapon_mastery WHERE model_version=?", (MASTERY_MODEL_VERSION,)):
            if not validate_family_invariant(int(row["telegram_id"]), str(row["weapon_id"]), conn=conn):
                broken_families.append([int(row["telegram_id"]), str(row["weapon_id"])])
        broken_attributes = []
        for row in conn.execute("SELECT * FROM players WHERE build_migration_version=?", (MASTERY_MODEL_VERSION,)):
            player = dict(row)
            if observed_attribute_budget(player) != int(player["attribute_budget"]):
                broken_attributes.append(int(player["telegram_id"]))
        return {"family_invariant_failures": broken_families, "attribute_invariant_failures": broken_attributes}
    finally:
        if owns:
            conn.close()
