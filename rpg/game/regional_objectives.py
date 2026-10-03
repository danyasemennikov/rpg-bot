"""Narrow same-transaction RAV1 craft and combat observers."""

from __future__ import annotations

import hashlib
import json

from game.regional_adventures import _active_step, _mark_objective, get_project_state, list_project_states
from game.regional_catalog import MIXED_ENCOUNTERS, PROJECTS_BY_ID


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _rav1_installed(conn) -> bool:
    tables = {
        str(row["name"]) for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('economy_schema_migrations','rav1_projects','rav1_combat_bindings')"
        )
    }
    return tables == {'economy_schema_migrations', 'rav1_projects', 'rav1_combat_bindings'} and bool(
        conn.execute(
            "SELECT 1 FROM economy_schema_migrations WHERE version='regional_adventures_v1'"
        ).fetchone()
    )


def observe_successful_craft(conn, *, player_id: int, recipe_id: str, output_item_id: str) -> list[str]:
    """Advance only objectives active when this successful execution entered."""
    if not _rav1_installed(conn):
        return []
    matches: list[tuple[str, str]] = []
    for state in list_project_states(player_id, conn=conn):
        if state["state"] != "active":
            continue
        step = _active_step(state["definition"], state)
        for objective in step.objectives if step else ():
            if (objective.kind == "craft" and objective.target.get("recipe_id") == recipe_id
                    and objective.target.get("output_item_id") == output_item_id):
                matches.append((state["project_id"], objective.objective_id))
    advanced: list[str] = []
    for project_id, objective_id in matches:
        state = get_project_state(player_id, project_id, conn=conn)
        step = _active_step(state["definition"], state) if state else None
        if state and step and any(o.objective_id == objective_id and o.kind == "craft" for o in step.objectives):
            _mark_objective(conn, player_id, project_id, objective_id)
            advanced.append(project_id)
    return advanced


def _source_snapshot(encounter) -> tuple[dict, dict]:
    try:
        battle = json.loads(str(encounter["battle_state_json"] or "{}"))
        source = json.loads(str(encounter["source_units_json"] or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("rav1_combat_source_invalid") from exc
    if not isinstance(battle, dict) or not isinstance(source, dict) or not isinstance(source.get("units"), list):
        raise RuntimeError("rav1_combat_source_invalid")
    return battle, source


def mark_new_anchored_encounter(conn, battle_state: dict, *, anchor_spawn_instance_id: str | None) -> None:
    """Stamp creation-time eligibility only after the migration is installed."""
    if not anchor_spawn_instance_id:
        return
    installed = conn.execute(
        "SELECT 1 FROM economy_schema_migrations WHERE version='regional_adventures_v1'"
    ).fetchone()
    if installed:
        battle_state["rav1_credit_version"] = 1


def preserve_combat_credit_marker(persisted_state: dict, next_state: dict) -> dict:
    """Carry the immutable creation marker across every combat payload save.

    A missing marker in an update payload is repaired from the authoritative
    persisted snapshot.  An attempted change is corruption and must never be
    written.  Encounters created before RAV1 remain genuinely marker-free.
    """
    if "rav1_credit_version" not in persisted_state:
        if "rav1_credit_version" in next_state:
            raise RuntimeError("rav1_combat_marker_immutable")
        return next_state
    marker = persisted_state["rav1_credit_version"]
    if "rav1_credit_version" in next_state and next_state["rav1_credit_version"] != marker:
        raise RuntimeError("rav1_combat_marker_immutable")
    next_state["rav1_credit_version"] = marker
    return next_state


def _credit_marker_state(battle: dict, binding_count: int) -> str:
    if "rav1_credit_version" not in battle:
        if binding_count:
            raise RuntimeError("rav1_combat_marker_missing")
        return "legacy"
    marker = battle["rav1_credit_version"]
    if isinstance(marker, bool) or not isinstance(marker, int) or marker != 1:
        raise RuntimeError("rav1_combat_marker_unsupported")
    return "rav1"


def _kill_source_ids(objective, units: list[dict], location_id: str) -> list[str]:
    if location_id not in objective.locations:
        return []
    target = objective.target
    matches = []
    for unit in units:
        special = str(unit.get("special_spawn_key") or "")
        special_rule = str(target.get("special") or "any")
        if (str(unit.get("mob_id") or "") == str(target.get("mob_id") or "")
                and str(unit.get("spawn_profile") or "normal") in tuple(target.get("profiles") or ())
                and (special_rule == "any" or (special_rule == "ordinary" and not special))):
            matches.append(str(unit.get("unit_id") or ""))
    return sorted(item for item in matches if item)


def _encounter_source_ids(objective, units: list[dict], location_id: str, mixed_id: str) -> list[str]:
    if location_id not in objective.locations or mixed_id != objective.target.get("mixed_encounter_id"):
        return []
    recipe = next((row for row in MIXED_ENCOUNTERS if row["content_id"] == mixed_id), None)
    if not recipe or len(units) != len(recipe["units"]):
        return []
    actual = sorted((str(unit.get("mob_id") or ""), str(unit.get("spawn_profile") or "normal"),
                     str(unit.get("special_spawn_key") or "")) for unit in units)
    expected = sorted((mob_id, "normal", "") for mob_id, _formation in recipe["units"])
    if actual != expected:
        return []
    return sorted(str(unit.get("unit_id") or "") for unit in units)


def capture_combat_bindings(conn, *, encounter_id: str, player_ids: list[int]) -> None:
    if not _rav1_installed(conn):
        return
    encounter = conn.execute("SELECT * FROM pve_encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
    if not encounter:
        raise RuntimeError("rav1_encounter_missing")
    battle, source = _source_snapshot(encounter)
    binding_count = int(conn.execute(
        "SELECT COUNT(*) AS total FROM rav1_combat_bindings WHERE encounter_id=?", (encounter_id,)
    ).fetchone()["total"])
    if _credit_marker_state(battle, binding_count) == "legacy":
        return
    location_id = str(encounter["location_id"] or "")
    units = list(source["units"])
    mixed_id = str(battle.get("mixed_encounter_id") or "")
    for player_id in player_ids:
        bindings: list[dict] = []
        for state in list_project_states(int(player_id), conn=conn):
            if state["state"] != "active":
                continue
            project = state["definition"]
            step = _active_step(project, state)
            for objective in step.objectives if step else ():
                if objective.kind == "kill":
                    source_ids = _kill_source_ids(objective, units, location_id)
                elif objective.kind == "encounter":
                    source_ids = _encounter_source_ids(objective, units, location_id, mixed_id)
                else:
                    continue
                if not source_ids:
                    continue
                binding = {
                    "project_id": project.project_id, "catalog_version": project.catalog_version,
                    "step_id": step.step_id, "objective_id": objective.objective_id,
                    "kind": objective.kind, "source_unit_ids": source_ids,
                }
                if objective.kind == "encounter":
                    binding["mixed_encounter_id"] = mixed_id
                bindings.append(binding)
        bindings.sort(key=lambda item: (item["project_id"], item["step_id"], item["objective_id"]))
        envelope = {"encounter_id": encounter_id, "player_id": int(player_id),
                    "schema_version": 1, "bindings": bindings}
        snapshot_hash = hashlib.sha256(_canonical(envelope).encode()).hexdigest()
        existing = conn.execute(
            "SELECT bindings_json, snapshot_hash FROM rav1_combat_bindings WHERE encounter_id=? AND player_id=?",
            (encounter_id, int(player_id)),
        ).fetchone()
        if existing:
            if str(existing["bindings_json"]) != _canonical(bindings) or str(existing["snapshot_hash"]) != snapshot_hash:
                raise RuntimeError("rav1_combat_binding_immutable")
            continue
        conn.execute(
            """INSERT INTO rav1_combat_bindings
               (encounter_id, player_id, schema_version, bindings_json, snapshot_hash)
               VALUES (?, ?, 1, ?, ?)""",
            (encounter_id, int(player_id), _canonical(bindings), snapshot_hash),
        )


def apply_combat_bindings(conn, *, encounter_id: str, plan: dict) -> dict[int, list[str]]:
    encounter = conn.execute(
        "SELECT battle_state_json, locked_roster_json FROM pve_encounters WHERE encounter_id=?", (encounter_id,)
    ).fetchone()
    if not encounter:
        raise RuntimeError("rav1_encounter_missing")
    try:
        battle = json.loads(str(encounter["battle_state_json"] or "{}"))
        roster_payload = json.loads(str(encounter["locked_roster_json"] or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("rav1_combat_binding_invalid") from exc
    bindings_table_exists = bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='rav1_combat_bindings'"
    ).fetchone())
    rows = conn.execute(
        "SELECT * FROM rav1_combat_bindings WHERE encounter_id=? ORDER BY player_id", (encounter_id,)
    ).fetchall() if bindings_table_exists else []
    if _credit_marker_state(battle, len(rows)) == "legacy":
        return {}
    if not bindings_table_exists:
        raise RuntimeError("rav1_combat_binding_missing")
    roster = sorted(int(value) for value in roster_payload.get("player_ids", []))
    if [int(row["player_id"]) for row in rows] != roster:
        raise RuntimeError("rav1_combat_binding_missing")
    eligible = {int(value) for value in plan.get("eligible_recipient_ids") or []}
    recipient_units = {
        int(recipient["player_id"]): {
            str(unit.get("unit_id") or "") for unit in recipient.get("units") or []
        }
        for recipient in plan.get("recipients") or []
    }
    advanced: dict[int, list[str]] = {}
    for row in rows:
        if int(row["schema_version"]) != 1 or row["applied_at"] is not None:
            raise RuntimeError("rav1_combat_binding_replay_or_version")
        bindings = json.loads(str(row["bindings_json"]))
        envelope = {"encounter_id": encounter_id, "player_id": int(row["player_id"]),
                    "schema_version": 1, "bindings": bindings}
        if hashlib.sha256(_canonical(envelope).encode()).hexdigest() != str(row["snapshot_hash"]):
            raise RuntimeError("rav1_combat_binding_hash_mismatch")
        player_id = int(row["player_id"])
        if player_id in eligible:
            won_units = recipient_units.get(player_id, set())
            for binding in bindings:
                source_ids = set(binding.get("source_unit_ids") or [])
                qualifies = (bool(source_ids & won_units) if binding.get("kind") == "kill"
                             else bool(source_ids) and source_ids.issubset(won_units))
                if not qualifies:
                    continue
                state = get_project_state(player_id, binding["project_id"], conn=conn)
                step = _active_step(state["definition"], state) if state else None
                if (not state or state["state"] != "active" or int(state["catalog_version"]) != 1
                        or not step or step.step_id != binding["step_id"]):
                    continue
                objective = next((o for o in step.objectives if o.objective_id == binding["objective_id"]), None)
                if not objective or objective.kind != binding["kind"]:
                    continue
                amount = len(source_ids & won_units) if objective.kind == "kill" else 1
                _mark_objective(conn, player_id, binding["project_id"], binding["objective_id"], amount=amount)
                advanced.setdefault(player_id, []).append(binding["project_id"])
        conn.execute(
            "UPDATE rav1_combat_bindings SET applied_at=CURRENT_TIMESTAMP WHERE encounter_id=? AND player_id=? AND applied_at IS NULL",
            (encounter_id, player_id),
        )
    return advanced
