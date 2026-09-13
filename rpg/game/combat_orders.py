"""Durable order/result receipts shared by PvE and PvP V1."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from database import get_connection
from game.build_contract import RULES_VERSION
from game.build_progression import ensure_build_schema


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def submit_combat_order(
    *,
    encounter_kind: str,
    encounter_id: str,
    turn_revision: int,
    actor_id: int,
    action: dict[str, Any],
    target_id: str | int | None,
    deadline_at: str,
    order_kind: str = "manual",
    conn=None,
) -> dict[str, Any]:
    """Insert one authoritative order; identical retries are acknowledged."""
    if encounter_kind not in {"pve", "pvp"}:
        return {"accepted": False, "reason": "unknown_encounter_kind"}
    owns = conn is None
    if owns:
        conn = get_connection()
        conn.execute("BEGIN IMMEDIATE")
    try:
        ensure_build_schema(conn)
        encoded = _stable_json(action)
        existing = conn.execute('''SELECT action_json, target_id, order_kind, rules_version
            FROM combat_orders_v1 WHERE encounter_kind=? AND encounter_id=?
            AND turn_revision=? AND actor_id=?''', (
                encounter_kind, encounter_id, int(turn_revision), int(actor_id),
            )).fetchone()
        normalized_target = None if target_id is None else str(target_id)
        if existing:
            identical = (
                str(existing["action_json"]) == encoded
                and existing["target_id"] == normalized_target
                and str(existing["order_kind"]) == order_kind
                and str(existing["rules_version"]) == RULES_VERSION
            )
            if owns:
                conn.rollback()
            return {"accepted": identical, "duplicate": identical, "reason": "duplicate" if identical else "conflicting_order"}
        result = conn.execute('''INSERT OR IGNORE INTO combat_orders_v1
            (encounter_kind, encounter_id, turn_revision, actor_id, action_json,
             target_id, rules_version, deadline_at, order_kind)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                encounter_kind, encounter_id, int(turn_revision), int(actor_id), encoded,
                normalized_target, RULES_VERSION, deadline_at, order_kind,
            ))
        if result.rowcount != 1:
            raise RuntimeError("combat_order_conflict")
        if owns:
            conn.commit()
        return {"accepted": True, "duplicate": False, "reason": "committed"}
    except Exception:
        if owns:
            conn.rollback()
        raise
    finally:
        if owns:
            conn.close()


def load_combat_orders(
    *, encounter_kind: str, encounter_id: str, turn_revision: int, conn=None,
) -> list[dict[str, Any]]:
    owns = conn is None
    if owns:
        conn = get_connection()
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='combat_orders_v1'").fetchone():
            return []
        rows = conn.execute('''SELECT * FROM combat_orders_v1 WHERE encounter_kind=?
            AND encounter_id=? AND turn_revision=? ORDER BY created_at, actor_id''', (
                encounter_kind, encounter_id, int(turn_revision),
            )).fetchall()
        return [{**dict(row), "action": json.loads(str(row["action_json"]))} for row in rows]
    finally:
        if owns:
            conn.close()


def persist_turn_result(
    *,
    encounter_kind: str,
    encounter_id: str,
    turn_revision: int,
    result: dict[str, Any],
    complete_state: dict[str, Any],
    expected_previous_revision: int | None = None,
    conn=None,
) -> dict[str, Any]:
    """Persist an applied side exactly once and advance encounter authority."""
    owns = conn is None
    if owns:
        conn = get_connection()
        conn.execute("BEGIN IMMEDIATE")
    try:
        ensure_build_schema(conn)
        existing = conn.execute('''SELECT result_json, state_json FROM combat_turn_results_v1
            WHERE encounter_kind=? AND encounter_id=? AND turn_revision=?''', (
                encounter_kind, encounter_id, int(turn_revision),
            )).fetchone()
        if existing:
            if owns:
                conn.rollback()
            return {
                "applied": True,
                "duplicate": True,
                "result": json.loads(str(existing["result_json"])),
                "state": json.loads(str(existing["state_json"])),
            }
        table = "pve_encounters" if encounter_kind == "pve" else "pvp_engagements"
        id_column = "encounter_id" if encounter_kind == "pve" else "id"
        revision_row = conn.execute(
            f"SELECT turn_revision, rules_version FROM {table} WHERE {id_column}=?", (encounter_id,)
        ).fetchone()
        if not revision_row or str(revision_row["rules_version"]) != RULES_VERSION:
            if owns:
                conn.rollback()
            return {"applied": False, "reason": "encounter_rules_mismatch"}
        expected = int(turn_revision if expected_previous_revision is None else expected_previous_revision)
        if int(revision_row["turn_revision"]) not in {expected, int(turn_revision) - 1}:
            if owns:
                conn.rollback()
            return {"applied": False, "reason": "stale_revision"}
        conn.execute('''INSERT INTO combat_turn_results_v1
            (encounter_kind, encounter_id, turn_revision, result_json, state_json, rules_version)
            VALUES (?, ?, ?, ?, ?, ?)''', (
                encounter_kind, encounter_id, int(turn_revision), _stable_json(result),
                _stable_json(complete_state), RULES_VERSION,
            ))
        if encounter_kind == "pve":
            conn.execute('''UPDATE pve_encounters SET battle_state_json=?, turn_revision=?,
                updated_at=CURRENT_TIMESTAMP WHERE encounter_id=? AND rules_version=?''', (
                    _stable_json(complete_state), int(turn_revision), encounter_id, RULES_VERSION,
                ))
        else:
            # PvP keeps its battle payload inside the established reason_context.
            conn.execute('''UPDATE pvp_engagements SET reason_context=?, turn_revision=?
                WHERE id=? AND rules_version=?''', (
                    _stable_json(complete_state), int(turn_revision), int(encounter_id), RULES_VERSION,
                ))
        if owns:
            conn.commit()
        return {"applied": True, "duplicate": False, "result": result, "state": complete_state}
    except Exception:
        if owns:
            conn.rollback()
        raise
    finally:
        if owns:
            conn.close()


def replay_turn_result(*, encounter_kind: str, encounter_id: str, turn_revision: int, conn=None) -> dict[str, Any] | None:
    owns = conn is None
    if owns:
        conn = get_connection()
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='combat_turn_results_v1'").fetchone():
            return None
        row = conn.execute('''SELECT result_json, state_json FROM combat_turn_results_v1
            WHERE encounter_kind=? AND encounter_id=? AND turn_revision=?''', (
                encounter_kind, encounter_id, int(turn_revision),
            )).fetchone()
        return None if not row else {"result": json.loads(str(row["result_json"])), "state": json.loads(str(row["state_json"]))}
    finally:
        if owns:
            conn.close()

