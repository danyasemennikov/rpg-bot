"""Exact additive RAV1-1 storage migration and compatibility validation."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3

from game.regional_catalog import (
    CATALOG_VERSION,
    FACTS_BY_ID,
    INTERACTIONS_BY_ID,
    PROJECTS_BY_ID,
    validate_catalogue,
)


MIGRATION_VERSION = "regional_adventures_v1"
TABLES = (
    "rav1_projects",
    "rav1_facts",
    "rav1_claims",
    "rav1_pins",
    "rav1_combat_bindings",
)

_DDL = {
    "rav1_projects": """CREATE TABLE rav1_projects (
      player_id INTEGER NOT NULL REFERENCES players(telegram_id),
      project_id TEXT NOT NULL,
      catalog_version INTEGER NOT NULL CHECK (catalog_version = 1),
      state TEXT NOT NULL CHECK (state IN ('active','completed')),
      step_index INTEGER NOT NULL CHECK (step_index BETWEEN 0 AND 4),
      progress_json TEXT NOT NULL,
      choices_json TEXT NOT NULL,
      step_results_json TEXT NOT NULL,
      revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
      started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      completed_at TEXT,
      PRIMARY KEY (player_id, project_id),
      CHECK ((state='active' AND completed_at IS NULL) OR
             (state='completed' AND completed_at IS NOT NULL))
    )""",
    "rav1_facts": """CREATE TABLE rav1_facts (
      player_id INTEGER NOT NULL REFERENCES players(telegram_id),
      fact_id TEXT NOT NULL,
      catalog_version INTEGER NOT NULL CHECK (catalog_version = 1),
      location_id TEXT NOT NULL,
      discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (player_id, fact_id)
    )""",
    "rav1_claims": """CREATE TABLE rav1_claims (
      player_id INTEGER NOT NULL REFERENCES players(telegram_id),
      content_id TEXT NOT NULL,
      catalog_version INTEGER NOT NULL CHECK (catalog_version = 1),
      request_id TEXT NOT NULL,
      reward_json TEXT NOT NULL,
      claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (player_id, content_id),
      UNIQUE (player_id, request_id)
    )""",
    "rav1_pins": """CREATE TABLE rav1_pins (
      player_id INTEGER NOT NULL REFERENCES players(telegram_id),
      slot INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 3),
      owner_kind TEXT NOT NULL CHECK (owner_kind IN ('project','hunt','gear')),
      owner_id TEXT NOT NULL,
      PRIMARY KEY (player_id, slot),
      UNIQUE (player_id, owner_kind, owner_id)
    )""",
    "rav1_combat_bindings": """CREATE TABLE rav1_combat_bindings (
      encounter_id TEXT NOT NULL REFERENCES pve_encounters(encounter_id),
      player_id INTEGER NOT NULL REFERENCES players(telegram_id),
      schema_version INTEGER NOT NULL CHECK (schema_version = 1),
      bindings_json TEXT NOT NULL,
      snapshot_hash TEXT NOT NULL,
      captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      applied_at TEXT,
      PRIMARY KEY (encounter_id, player_id)
    )""",
}

_COLUMNS = {
    "rav1_projects": (
        ("player_id", "INTEGER", 1, None, 1), ("project_id", "TEXT", 1, None, 2),
        ("catalog_version", "INTEGER", 1, None, 0), ("state", "TEXT", 1, None, 0),
        ("step_index", "INTEGER", 1, None, 0), ("progress_json", "TEXT", 1, None, 0),
        ("choices_json", "TEXT", 1, None, 0), ("step_results_json", "TEXT", 1, None, 0),
        ("revision", "INTEGER", 1, "1", 0), ("started_at", "TEXT", 1, "CURRENT_TIMESTAMP", 0),
        ("updated_at", "TEXT", 1, "CURRENT_TIMESTAMP", 0), ("completed_at", "TEXT", 0, None, 0),
    ),
    "rav1_facts": (
        ("player_id", "INTEGER", 1, None, 1), ("fact_id", "TEXT", 1, None, 2),
        ("catalog_version", "INTEGER", 1, None, 0), ("location_id", "TEXT", 1, None, 0),
        ("discovered_at", "TEXT", 1, "CURRENT_TIMESTAMP", 0),
    ),
    "rav1_claims": (
        ("player_id", "INTEGER", 1, None, 1), ("content_id", "TEXT", 1, None, 2),
        ("catalog_version", "INTEGER", 1, None, 0), ("request_id", "TEXT", 1, None, 0),
        ("reward_json", "TEXT", 1, None, 0), ("claimed_at", "TEXT", 1, "CURRENT_TIMESTAMP", 0),
    ),
    "rav1_pins": (
        ("player_id", "INTEGER", 1, None, 1), ("slot", "INTEGER", 1, None, 2),
        ("owner_kind", "TEXT", 1, None, 0), ("owner_id", "TEXT", 1, None, 0),
    ),
    "rav1_combat_bindings": (
        ("encounter_id", "TEXT", 1, None, 1), ("player_id", "INTEGER", 1, None, 2),
        ("schema_version", "INTEGER", 1, None, 0), ("bindings_json", "TEXT", 1, None, 0),
        ("snapshot_hash", "TEXT", 1, None, 0),
        ("captured_at", "TEXT", 1, "CURRENT_TIMESTAMP", 0), ("applied_at", "TEXT", 0, None, 0),
    ),
}

_FOREIGN_KEYS = {
    "rav1_projects": {("players", "player_id", "telegram_id")},
    "rav1_facts": {("players", "player_id", "telegram_id")},
    "rav1_claims": {("players", "player_id", "telegram_id")},
    "rav1_pins": {("players", "player_id", "telegram_id")},
    "rav1_combat_bindings": {
        ("pve_encounters", "encounter_id", "encounter_id"),
        ("players", "player_id", "telegram_id"),
    },
}

_UNIQUE_KEYS = {
    "rav1_projects": {("player_id", "project_id")},
    "rav1_facts": {("player_id", "fact_id")},
    "rav1_claims": {("player_id", "content_id"), ("player_id", "request_id")},
    "rav1_pins": {("player_id", "slot"), ("player_id", "owner_kind", "owner_id")},
    "rav1_combat_bindings": {("encounter_id", "player_id")},
}


def _table_sql(conn: sqlite3.Connection, table: str) -> str | None:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return str(row["sql"]) if row else None


def _normalized_sql(sql: str) -> str:
    return re.sub(r"\s+", "", sql.lower().replace('"', "").replace("`", ""))


def _unique_keys(conn: sqlite3.Connection, table: str) -> set[tuple[str, ...]]:
    keys: set[tuple[str, ...]] = set()
    pk = tuple(
        row["name"] for row in sorted(
            (row for row in conn.execute(f'PRAGMA table_info("{table}")') if int(row["pk"])),
            key=lambda row: int(row["pk"]),
        )
    )
    if pk:
        keys.add(pk)
    for index in conn.execute(f'PRAGMA index_list("{table}")'):
        if not int(index["unique"]):
            continue
        keys.add(tuple(row["name"] for row in conn.execute(f'PRAGMA index_info("{index["name"]}")')))
    return keys


def validate_table_schema(conn: sqlite3.Connection, table: str) -> None:
    sql = _table_sql(conn, table)
    if sql is None:
        raise RuntimeError(f"missing RAV1 table: {table}")
    columns = tuple(
        (str(row["name"]), str(row["type"]).upper(), int(row["notnull"]), row["dflt_value"], int(row["pk"]))
        for row in conn.execute(f'PRAGMA table_info("{table}")')
    )
    if columns != _COLUMNS[table]:
        raise RuntimeError(f"incompatible RAV1 table columns: {table}")
    foreign_keys = {
        (str(row["table"]), str(row["from"]), str(row["to"]))
        for row in conn.execute(f'PRAGMA foreign_key_list("{table}")')
        if str(row["on_update"]) == "NO ACTION" and str(row["on_delete"]) == "NO ACTION"
    }
    if foreign_keys != _FOREIGN_KEYS[table]:
        raise RuntimeError(f"incompatible RAV1 foreign keys: {table}")
    if _unique_keys(conn, table) != _UNIQUE_KEYS[table]:
        raise RuntimeError(f"incompatible RAV1 unique keys: {table}")
    triggers = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (table,)
    ).fetchone()
    if triggers:
        raise RuntimeError(f"unexpected RAV1 trigger: {table}")
    # The frozen DDL is compared after SQLite's harmless whitespace/quoting rewrite.
    if _normalized_sql(sql) != _normalized_sql(_DDL[table]):
        raise RuntimeError(f"incompatible RAV1 checks/defaults: {table}")


def _json_object(raw: object, *, name: str) -> dict:
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {name} JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"invalid {name} JSON shape")
    return parsed


def _validate_project_row(row: sqlite3.Row) -> None:
    project = PROJECTS_BY_ID.get(str(row["project_id"]))
    if not project or int(row["catalog_version"]) != CATALOG_VERSION:
        raise RuntimeError("unknown RAV1 project/version")
    progress = _json_object(row["progress_json"], name="project progress")
    expected = {
        f"{step.step_id}.{objective.objective_id}": objective.required
        for step in project.steps for objective in step.objectives
    }
    if set(progress) != set(expected) or any(
        not isinstance(progress[key], int) or not 0 <= progress[key] <= required
        for key, required in expected.items()
    ):
        raise RuntimeError("incompatible RAV1 project progress")
    choices = _json_object(row["choices_json"], name="project choices")
    valid_choices = {
        objective.target["choice_id"]: set(objective.target["values"])
        for step in project.steps for objective in step.objectives if objective.kind == "choose"
    }
    if set(choices) - set(valid_choices) or any(value not in valid_choices[key] for key, value in choices.items()):
        raise RuntimeError("incompatible RAV1 project choices")
    results = _json_object(row["step_results_json"], name="project step results")
    if set(results) - {step.step_id for step in project.steps}:
        raise RuntimeError("incompatible RAV1 project results")
    step_index = int(row["step_index"])
    completed = str(row["state"]) == "completed"
    if step_index < 0 or step_index > len(project.steps) or completed != (step_index == len(project.steps)):
        raise RuntimeError("incompatible RAV1 project state")

    expected_result_steps = {step.step_id for step in project.steps[:step_index]}
    if set(results) != expected_result_steps:
        raise RuntimeError("incompatible RAV1 project result sequence")

    choice_steps: dict[str, tuple[int, object]] = {}
    for index, step in enumerate(project.steps):
        objective_ids = [objective.objective_id for objective in step.objectives]
        values = results.get(step.step_id)
        if index < step_index:
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                raise RuntimeError("incompatible RAV1 project result shape")
            if len(values) != len(set(values)) or set(values) - set(objective_ids):
                raise RuntimeError("incompatible RAV1 project result IDs")
            if step.mode == "all" and set(values) != set(objective_ids):
                raise RuntimeError("incomplete RAV1 ALL step result")
            if step.mode == "any" and len(values) != 1:
                raise RuntimeError("incompatible RAV1 ANY step result")
            winners = set(values)
            for objective in step.objectives:
                amount = progress[f"{step.step_id}.{objective.objective_id}"]
                if objective.objective_id in winners and amount != objective.required:
                    raise RuntimeError("unsatisfied RAV1 completed objective")
                if step.mode == "any" and objective.objective_id not in winners and amount != 0:
                    raise RuntimeError("multiple RAV1 ANY winners")
        else:
            amounts = [progress[f"{step.step_id}.{objective.objective_id}"] for objective in step.objectives]
            if index > step_index and any(amount != 0 for amount in amounts):
                raise RuntimeError("premature RAV1 future progress")
            if index == step_index and not completed:
                ready = all(amount == objective.required for amount, objective in zip(amounts, step.objectives))
                if step.mode == "any":
                    ready = any(amount == objective.required for amount, objective in zip(amounts, step.objectives))
                if ready:
                    raise RuntimeError("unreconciled RAV1 current step")
        for objective in step.objectives:
            if objective.kind == "choose":
                choice_steps[str(objective.target["choice_id"])] = (index, objective)

    for choice_id, (index, objective) in choice_steps.items():
        committed = choice_id in choices
        if committed != (index < step_index):
            raise RuntimeError("incompatible RAV1 choice timing")
        if committed:
            key = f"{project.steps[index].step_id}.{objective.objective_id}"
            if progress[key] != objective.required:
                raise RuntimeError("inconsistent RAV1 committed choice")


def _validate_rows(conn: sqlite3.Connection) -> None:
    from game.quest_board import HUNT_CONTRACTS_BY_KEY

    for row in conn.execute("SELECT * FROM rav1_projects"):
        _validate_project_row(row)
        has_claim = conn.execute(
            "SELECT 1 FROM rav1_claims WHERE player_id=? AND content_id=?",
            (row["player_id"], row["project_id"]),
        ).fetchone() is not None
        if (str(row["state"]) == "completed") != has_claim:
            raise RuntimeError("RAV1 project/claim terminal mismatch")
    for row in conn.execute("SELECT * FROM rav1_facts"):
        definition = FACTS_BY_ID.get(str(row["fact_id"]))
        if (not definition or int(row["catalog_version"]) != 1
                or str(row["location_id"]) != definition.location_id):
            raise RuntimeError("unknown RAV1 fact/version/location")
    finite_ids = set(PROJECTS_BY_ID) | {
        key for key, definition in INTERACTIONS_BY_ID.items() if definition.kind in {"request", "cache"}
    }
    for row in conn.execute("SELECT * FROM rav1_claims"):
        content_id = str(row["content_id"])
        if content_id not in finite_ids or int(row["catalog_version"]) != 1:
            raise RuntimeError("unknown RAV1 claim/version")
        reward = _json_object(row["reward_json"], name="claim reward")
        definition = PROJECTS_BY_ID.get(content_id) or INTERACTIONS_BY_ID.get(content_id)
        expected_reward = definition.reward
        if (reward.get("content_id") != content_id
                or reward.get("xp") != expected_reward.xp
                or reward.get("gold") != expected_reward.gold
                or not isinstance(reward.get("items"), list)
                or not isinstance(reward.get("progression"), dict)):
            raise RuntimeError("incompatible RAV1 claim reward")
        if content_id in PROJECTS_BY_ID:
            project = conn.execute(
                "SELECT state FROM rav1_projects WHERE player_id=? AND project_id=?",
                (row["player_id"], content_id),
            ).fetchone()
            if not project or str(project["state"]) != "completed":
                raise RuntimeError("RAV1 claim/project terminal mismatch")
    for row in conn.execute("SELECT * FROM rav1_pins"):
        kind, owner_id = str(row["owner_kind"]), str(row["owner_id"])
        if kind == "project" and owner_id not in PROJECTS_BY_ID:
            raise RuntimeError("unknown RAV1 project pin")
        if kind == "hunt" and owner_id not in HUNT_CONTRACTS_BY_KEY:
            raise RuntimeError("unknown RAV1 hunt pin")
        if kind == "gear" and owner_id != "current":
            raise RuntimeError("unknown RAV1 gear pin")
    for row in conn.execute("SELECT * FROM rav1_combat_bindings"):
        if int(row["schema_version"]) != 1 or row["applied_at"] is not None and not str(row["applied_at"]):
            raise RuntimeError("unknown RAV1 combat binding version")
        try:
            bindings = json.loads(str(row["bindings_json"]))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("invalid RAV1 combat binding JSON") from exc
        if not isinstance(bindings, list):
            raise RuntimeError("invalid RAV1 combat binding shape")
        for binding in bindings:
            if not isinstance(binding, dict):
                raise RuntimeError("invalid RAV1 combat binding entry")
            kind = str(binding.get("kind") or "")
            required_keys = {
                "project_id", "catalog_version", "step_id", "objective_id", "kind", "source_unit_ids"
            } | ({"mixed_encounter_id"} if kind == "encounter" else set())
            if set(binding) != required_keys or kind not in {"kill", "encounter"}:
                raise RuntimeError("invalid RAV1 combat binding entry shape")
            project = PROJECTS_BY_ID.get(str(binding["project_id"]))
            step = next((value for value in project.steps if value.step_id == binding["step_id"]), None) if project else None
            objective = next((value for value in step.objectives
                              if value.objective_id == binding["objective_id"]), None) if step else None
            sources = binding.get("source_unit_ids")
            if (not project or int(binding["catalog_version"]) != project.catalog_version
                    or not objective or objective.kind != kind
                    or not isinstance(sources, list) or not sources
                    or any(not isinstance(value, str) or not value for value in sources)
                    or len(set(sources)) != len(sources)):
                raise RuntimeError("invalid RAV1 combat binding authority")
            if (kind == "encounter"
                    and binding.get("mixed_encounter_id") != objective.target.get("mixed_encounter_id")):
                raise RuntimeError("invalid RAV1 mixed binding identity")
        canonical = json.dumps({
            "encounter_id": str(row["encounter_id"]), "player_id": int(row["player_id"]),
            "schema_version": 1, "bindings": bindings,
        }, sort_keys=True, separators=(",", ":"))
        if hashlib.sha256(canonical.encode()).hexdigest() != str(row["snapshot_hash"]):
            raise RuntimeError("RAV1 combat binding hash mismatch")


def _validate_prerequisites(conn: sqlite3.Connection) -> None:
    required = {"players", "pve_encounters", "economy_schema_migrations", "economy_action_receipts"}
    present = {
        str(row["name"]) for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?,?,?,?)", tuple(required)
        )
    }
    if present != required:
        raise RuntimeError("RAV1 prerequisite schema is incomplete")
    migration_columns = tuple(str(row["name"]) for row in conn.execute("PRAGMA table_info('economy_schema_migrations')"))
    if migration_columns != ("version", "applied_at"):
        raise RuntimeError("incompatible economy migration authority")


def ensure_regional_schema(conn: sqlite3.Connection) -> None:
    """Install/validate RAV1 atomically; never commit a caller-owned transaction."""
    validate_catalogue()
    from game.i18n import validate_rav1_locales
    validate_rav1_locales()
    owns_transaction = not conn.in_transaction
    savepoint = "rav1_migration"
    try:
        if owns_transaction:
            conn.execute("BEGIN IMMEDIATE")
        else:
            conn.execute(f"SAVEPOINT {savepoint}")
        _validate_prerequisites(conn)
        marker = conn.execute(
            "SELECT 1 FROM economy_schema_migrations WHERE version=?", (MIGRATION_VERSION,)
        ).fetchone()
        existing = {table for table in TABLES if _table_sql(conn, table) is not None}
        if marker and existing != set(TABLES):
            raise RuntimeError("RAV1 marker exists with incomplete schema")
        if not marker:
            for table in existing:
                validate_table_schema(conn, table)
                if conn.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone():
                    raise RuntimeError("unexpected nonempty unmarked RAV1 state")
            for table in TABLES:
                if table not in existing:
                    conn.execute(_DDL[table])
        for table in TABLES:
            validate_table_schema(conn, table)
        _validate_rows(conn)
        violations = [tuple(row) for row in conn.execute("PRAGMA foreign_key_check") if str(row[0]) in TABLES]
        if violations:
            raise RuntimeError(f"RAV1 foreign key violations: {violations!r}")
        if not marker:
            conn.execute("INSERT INTO economy_schema_migrations(version) VALUES (?)", (MIGRATION_VERSION,))
        if owns_transaction:
            conn.commit()
        else:
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
    except Exception:
        if owns_transaction:
            conn.rollback()
        else:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise
