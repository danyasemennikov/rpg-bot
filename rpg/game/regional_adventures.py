"""Finite RAV1 project, fact, claim, delivery and pin transactions."""

from __future__ import annotations

import json
import time
from dataclasses import asdict

from database import get_connection
from game.action_receipts import ActionRejected, consume_action, issue_actions, peaceful_player, require_item_delivery
from game.economy_actions import intent_hash, store_business_rejection, store_receipt
from game.gear_instances import grant_item_to_player
from game.locations import resolve_location_id
from game.progression_rewards import apply_progression_reward
from game.regional_catalog import (
    CACHES,
    CATALOG_VERSION,
    DIRECT_REQUESTS,
    FACTS_BY_ID,
    INTERACTIONS_BY_ID,
    PROJECTS_BY_ID,
    STANDING_DELIVERIES,
    ObjectiveDefinition,
    ProjectDefinition,
    Reward,
)


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _loads_object(raw: str) -> dict:
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("invalid_rav1_json")
    return parsed


def _project_state(row) -> dict:
    state = dict(row)
    state["progress"] = _loads_object(str(row["progress_json"]))
    state["choices"] = _loads_object(str(row["choices_json"]))
    state["step_results"] = _loads_object(str(row["step_results_json"]))
    state["definition"] = PROJECTS_BY_ID.get(str(row["project_id"]))
    return state


def get_project_state(player_id: int, project_id: str, *, conn=None) -> dict | None:
    owns = conn is None
    conn = conn or get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM rav1_projects WHERE player_id=? AND project_id=?",
            (int(player_id), str(project_id)),
        ).fetchone()
        return _project_state(row) if row else None
    finally:
        if owns:
            conn.close()


def list_project_states(player_id: int, *, conn=None) -> list[dict]:
    owns = conn is None
    conn = conn or get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM rav1_projects WHERE player_id=? ORDER BY started_at, project_id",
            (int(player_id),),
        ).fetchall()
        return [_project_state(row) for row in rows]
    finally:
        if owns:
            conn.close()


def list_facts(player_id: int, *, conn=None) -> set[str]:
    owns = conn is None
    conn = conn or get_connection()
    try:
        return {str(row["fact_id"]) for row in conn.execute(
            "SELECT fact_id FROM rav1_facts WHERE player_id=?", (int(player_id),)
        )}
    finally:
        if owns:
            conn.close()


def list_claims(player_id: int, *, conn=None) -> dict[str, dict]:
    owns = conn is None
    conn = conn or get_connection()
    try:
        return {
            str(row["content_id"]): {
                **json.loads(str(row["reward_json"])),
                "request_id": str(row["request_id"]), "claimed_at": row["claimed_at"],
            }
            for row in conn.execute("SELECT * FROM rav1_claims WHERE player_id=?", (int(player_id),))
        }
    finally:
        if owns:
            conn.close()


def _initial_progress(project: ProjectDefinition) -> dict[str, int]:
    return {
        f"{step.step_id}.{objective.objective_id}": 0
        for step in project.steps for objective in step.objectives
    }


def _objective_key(step_id: str, objective_id: str) -> str:
    return f"{step_id}.{objective_id}"


def _active_step(project: ProjectDefinition, state: dict):
    index = int(state["step_index"])
    return project.steps[index] if str(state["state"]) == "active" and index < len(project.steps) else None


def _reconcile_current_facts(conn, player_id: int, project: ProjectDefinition, state: dict) -> bool:
    changed = False
    known = list_facts(player_id, conn=conn)
    while True:
        step = _active_step(project, state)
        if step is None:
            return changed
        for objective in step.objectives:
            if objective.kind == "fact" and objective.target["fact_id"] in known:
                key = _objective_key(step.step_id, objective.objective_id)
                if int(state["progress"][key]) < objective.required:
                    state["progress"][key] = objective.required
                    changed = True
        if not _complete_step_if_ready(project, state):
            return changed
        changed = True


def _complete_step_if_ready(project: ProjectDefinition, state: dict) -> bool:
    step = _active_step(project, state)
    if step is None:
        return False
    complete_ids = [
        objective.objective_id for objective in step.objectives
        if int(state["progress"][_objective_key(step.step_id, objective.objective_id)]) >= objective.required
    ]
    if (step.mode == "all" and len(complete_ids) != len(step.objectives)) or (
        step.mode == "any" and not complete_ids
    ):
        return False
    winners = sorted(complete_ids) if step.mode == "all" else [complete_ids[0]]
    state["step_results"][step.step_id] = winners
    state["step_index"] = int(state["step_index"]) + 1
    if int(state["step_index"]) == len(project.steps):
        state["state"] = "completed"
    return True


def _save_project(conn, state: dict, *, terminal: bool = False) -> None:
    conn.execute(
        """UPDATE rav1_projects SET state=?, step_index=?, progress_json=?, choices_json=?,
           step_results_json=?, revision=revision+1, updated_at=CURRENT_TIMESTAMP,
           completed_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE completed_at END
           WHERE player_id=? AND project_id=? AND revision=?""",
        (state["state"], int(state["step_index"]), _canonical(state["progress"]),
         _canonical(state["choices"]), _canonical(state["step_results"]), int(terminal),
         int(state["player_id"]), str(state["project_id"]), int(state["revision"])),
    )
    if conn.execute("SELECT changes() AS changed").fetchone()["changed"] != 1:
        raise ActionRejected("stale_action")
    state["revision"] = int(state["revision"]) + 1


def start_project_in_transaction(conn, player_id: int, project_id: str) -> dict:
    project = PROJECTS_BY_ID.get(str(project_id))
    if not project:
        raise ActionRejected("unknown_content")
    if conn.execute(
        "SELECT 1 FROM rav1_projects WHERE player_id=? AND project_id=?", (int(player_id), project.project_id)
    ).fetchone():
        raise ActionRejected("already_resolved")
    state = {
        "player_id": int(player_id), "project_id": project.project_id,
        "catalog_version": 1, "state": "active", "step_index": 0,
        "progress": _initial_progress(project), "choices": {}, "step_results": {}, "revision": 1,
    }
    _reconcile_current_facts(conn, player_id, project, state)
    conn.execute(
        """INSERT INTO rav1_projects
           (player_id, project_id, catalog_version, state, step_index, progress_json,
            choices_json, step_results_json, revision)
           VALUES (?, ?, 1, ?, ?, ?, ?, ?, 1)""",
        (int(player_id), project.project_id, state["state"], state["step_index"],
         _canonical(state["progress"]), _canonical(state["choices"]), _canonical(state["step_results"])),
    )
    return state


def _mark_objective(conn, player_id: int, project_id: str, objective_id: str,
                    *, amount: int = 1, choice_value: str | None = None,
                    expected_revision: int | None = None, expected_step_id: str | None = None) -> dict:
    state = get_project_state(player_id, project_id, conn=conn)
    if not state or state["state"] != "active":
        raise ActionRejected("already_resolved" if state else "project_not_active")
    project = state["definition"]
    step = _active_step(project, state)
    if not step:
        raise ActionRejected("incompatible_step")
    if expected_revision is not None and int(state["revision"]) != int(expected_revision):
        raise ActionRejected("incompatible_step")
    if expected_step_id is not None and step.step_id != expected_step_id:
        raise ActionRejected("incompatible_step")
    objective = next((item for item in step.objectives if item.objective_id == objective_id), None)
    if objective is None:
        raise ActionRejected("incompatible_step")
    key = _objective_key(step.step_id, objective.objective_id)
    if choice_value is not None:
        choice_id = str(objective.target.get("choice_id") or "")
        if objective.kind != "choose" or choice_value not in tuple(objective.target.get("values", ())):
            raise ActionRejected("malformed_action")
        existing = state["choices"].get(choice_id)
        if existing and existing != choice_value:
            raise ActionRejected("already_resolved")
        state["choices"][choice_id] = choice_value
        state["progress"][key] = objective.required
    else:
        state["progress"][key] = min(objective.required, int(state["progress"][key]) + max(0, int(amount)))
    _complete_step_if_ready(project, state)
    if state["state"] == "active":
        _reconcile_current_facts(conn, player_id, project, state)
    terminal = state["state"] == "completed"
    _save_project(conn, state, terminal=terminal)
    return state


def reconcile_new_fact(conn, player_id: int, fact_id: str) -> list[str]:
    advanced: list[str] = []
    for state in list_project_states(player_id, conn=conn):
        if state["state"] != "active":
            continue
        project = state["definition"]
        before = (state["step_index"], _canonical(state["progress"]))
        if _reconcile_current_facts(conn, player_id, project, state):
            # No frozen project can terminate on a fact objective.
            _save_project(conn, state, terminal=False)
        after = (state["step_index"], _canonical(state["progress"]))
        if before != after:
            advanced.append(project.project_id)
    return advanced


def _inventory_counts(conn, player_id: int) -> dict[str, int]:
    return {str(row["item_id"]): int(row["quantity"]) for row in conn.execute(
        "SELECT item_id, SUM(quantity) AS quantity FROM inventory WHERE telegram_id=? GROUP BY item_id",
        (int(player_id),),
    )}


def _consume_items(conn, player_id: int, items: tuple[tuple[str, int], ...]) -> list[dict]:
    counts = _inventory_counts(conn, player_id)
    if any(counts.get(item_id, 0) < quantity for item_id, quantity in items):
        raise ActionRejected("insufficient_goods")
    consumed: list[dict] = []
    for item_id, quantity in items:
        remaining = int(quantity)
        rows = conn.execute(
            "SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id=? AND quantity>0 ORDER BY id",
            (int(player_id), item_id),
        ).fetchall()
        for row in rows:
            take = min(remaining, int(row["quantity"]))
            changed = conn.execute(
                "UPDATE inventory SET quantity=quantity-? WHERE id=? AND telegram_id=? AND quantity>=?",
                (take, int(row["id"]), int(player_id), take),
            )
            if changed.rowcount != 1:
                raise RuntimeError("rav1_inventory_debit_race")
            conn.execute("DELETE FROM inventory WHERE id=? AND quantity=0", (int(row["id"]),))
            remaining -= take
            if remaining == 0:
                break
        if remaining:
            raise RuntimeError("rav1_inventory_debit_incomplete")
        consumed.append({"item_id": item_id, "quantity": int(quantity)})
    return consumed


def _grant_reward(conn, player_id: int, content_id: str, reward: Reward, request_id: str) -> dict:
    if conn.execute(
        "SELECT 1 FROM rav1_claims WHERE player_id=? AND content_id=?", (int(player_id), content_id)
    ).fetchone():
        raise ActionRejected("already_resolved")
    progression = apply_progression_reward(conn, player_id, reward.xp, reward.gold)
    granted: list[dict] = []
    for item_id, quantity in reward.items:
        grant = grant_item_to_player(
            int(player_id), item_id, quantity, source="rav1",
            provenance={"source": "rav1", "catalog_version": 1, "content_id": content_id,
                        "player_id": int(player_id), "request_id": request_id},
            conn=conn,
        )
        require_item_delivery(grant, quantity)
        granted.append({"item_id": item_id, "quantity": quantity,
                        "instance_ids": list(grant.get("instance_ids") or [])})
    reward_result = {
        "content_id": content_id, "xp": reward.xp, "gold": reward.gold,
        "items": granted, "progression": progression,
    }
    conn.execute(
        """INSERT INTO rav1_claims
           (player_id, content_id, catalog_version, request_id, reward_json)
           VALUES (?, ?, 1, ?, ?)""",
        (int(player_id), content_id, request_id, _canonical(reward_result)),
    )
    conn.execute(
        "DELETE FROM rav1_pins WHERE player_id=? AND owner_kind='project' AND owner_id=?",
        (int(player_id), content_id),
    )
    return reward_result


def _project_objective_from_payload(state: dict, payload: dict, kind: str) -> ObjectiveDefinition:
    project = state["definition"]
    step = _active_step(project, state)
    if not step or step.step_id != payload.get("step_id") or int(state["revision"]) != int(payload.get("revision", -1)):
        raise ActionRejected("incompatible_step")
    objective = next((o for o in step.objectives if o.objective_id == payload.get("objective_id")), None)
    if not objective or objective.kind != kind:
        raise ActionRejected("incompatible_step")
    return objective


def _expected_locations(payload: dict, player_id: int, conn) -> tuple[str, ...]:
    content_id, operation = str(payload.get("content_id") or ""), str(payload.get("operation") or "")
    if content_id in PROJECTS_BY_ID:
        project = PROJECTS_BY_ID[content_id]
        if operation == "start":
            return project.start_locations
        state = get_project_state(player_id, content_id, conn=conn)
        if state and state["state"] == "active":
            step = _active_step(project, state)
            objective = next((o for o in step.objectives if o.objective_id == payload.get("objective_id")), None) if step else None
            return objective.locations if objective else ()
    interaction = INTERACTIONS_BY_ID.get(content_id)
    return (interaction.location_id,) if interaction else ()


def issue_regional_action(player_id: int, content_id: str, operation: str, *,
                          objective_id: str | None = None, choice: str | None = None,
                          pin: dict | None = None) -> str | None:
    payload = {"catalog_version": 1, "content_id": str(content_id), "operation": str(operation)}
    if objective_id is not None:
        payload["objective_id"] = str(objective_id)
    if choice is not None:
        payload["choice"] = str(choice)
    if pin is not None:
        payload["pin"] = pin
    conn = get_connection()
    try:
        state = get_project_state(player_id, content_id, conn=conn)
        if state and state["state"] == "active" and operation in {"deliver", "respond", "choose"}:
            step = _active_step(state["definition"], state)
            payload.update({"revision": int(state["revision"]), "step_id": step.step_id})
    finally:
        conn.close()
    if operation == "pin" and pin:
        kind = f"rav1:pin:{pin.get('owner_kind')}:{pin.get('owner_id')}"
    else:
        kind = f"rav1:{content_id}:{operation}"
    raw = _canonical(payload)
    return issue_actions(int(player_id), kind, [raw]).get(raw)


def issue_project_choice_actions(player_id: int, project_id: str, objective_id: str) -> dict[str, str]:
    conn = get_connection()
    try:
        state = get_project_state(player_id, project_id, conn=conn)
        if not state or state["state"] != "active":
            return {}
        step = _active_step(state["definition"], state)
        objective = next((o for o in step.objectives if o.objective_id == objective_id and o.kind == "choose"), None)
        if not objective:
            return {}
        payloads = []
        for choice in objective.target["values"]:
            payloads.append(_canonical({
                "catalog_version": 1, "content_id": project_id, "operation": "choose",
                "objective_id": objective_id, "choice": choice,
                "revision": int(state["revision"]), "step_id": step.step_id,
            }))
        tokens = issue_actions(int(player_id), f"rav1:{project_id}:choose", payloads)
        return {json.loads(raw)["choice"]: token for raw, token in tokens.items()}
    finally:
        conn.close()


def preview_regional_choice(player_id: int, token: str) -> dict | None:
    """Read a current choice intent without consuming or mutating it."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT kind, payload, expires_at FROM player_ui_actions WHERE token=? AND player_id=? AND used=0",
            (str(token), int(player_id)),
        ).fetchone()
        if (
            not row
            or not str(row["kind"]).endswith(":choose")
            or float(row["expires_at"]) < time.time()
        ):
            return None
        payload = json.loads(str(row["payload"]))
        if not isinstance(payload, dict) or int(payload.get("catalog_version", 0)) != CATALOG_VERSION:
            return None
        project_id = str(payload.get("content_id") or "")
        state = get_project_state(player_id, project_id, conn=conn)
        if not state or state["state"] != "active":
            return None
        objective = _project_objective_from_payload(state, payload, "choose")
        if str(payload.get("choice") or "") not in tuple(objective.target.get("values", ())):
            return None
        return payload
    except (ActionRejected, TypeError, ValueError, json.JSONDecodeError):
        return None
    finally:
        conn.close()


def _expected_rav1_action_kind(intent: dict) -> str:
    operation = str(intent.get("operation") or "")
    content_id = str(intent.get("content_id") or "")
    if operation == "pin":
        pin = intent.get("pin") if isinstance(intent.get("pin"), dict) else {}
        return f"rav1:pin:{pin.get('owner_kind')}:{pin.get('owner_id')}"
    return f"rav1:{content_id}:{operation}"


def _receipt_item_totals(value: list) -> tuple[tuple[str, int], ...]:
    totals: dict[str, int] = {}
    for entry in value:
        if not isinstance(entry, dict):
            raise ActionRejected("stale_action")
        item_id = entry.get("item_id")
        quantity = entry.get("quantity")
        if not isinstance(item_id, str) or not item_id or isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ActionRejected("stale_action")
        totals[item_id] = totals.get(item_id, 0) + quantity
    return tuple(sorted(totals.items()))


def _receipt_int(value) -> int:
    if isinstance(value, bool):
        raise ActionRejected("stale_action")
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ActionRejected("stale_action") from exc


def _expected_receipt_effect(intent: dict, status: str) -> tuple[tuple[tuple[str, int], ...], Reward]:
    """Derive the immutable economic effect from frozen catalogue identity."""
    content_id = str(intent.get("content_id") or "")
    operation = str(intent.get("operation") or "")
    consumed: tuple[tuple[str, int], ...] = ()
    reward = Reward()
    if content_id in PROJECTS_BY_ID:
        project = PROJECTS_BY_ID[content_id]
        if operation in {"deliver", "respond", "choose"}:
            matching = [
                objective
                for step in project.steps
                for objective in step.objectives
                if step.step_id == intent.get("step_id")
                and objective.objective_id == intent.get("objective_id")
                and objective.kind == operation
            ]
            if len(matching) != 1:
                raise ActionRejected("stale_action")
            if operation == "deliver":
                consumed = tuple(matching[0].target["items"])
        if status == "completed":
            reward = project.reward
    elif content_id in INTERACTIONS_BY_ID:
        definition = INTERACTIONS_BY_ID[content_id]
        if operation == "deliver":
            consumed = definition.cost_items
        if status in {"completed", "delivered"}:
            reward = definition.reward
    return tuple(sorted(consumed)), reward


def _validate_recovered_receipt(player_id: int, receipt, token_row) -> dict:
    """Fail closed unless stored immutable intent and result agree exactly."""
    if _receipt_int(receipt["schema_version"]) != 1 or _receipt_int(receipt["catalog_version"]) != CATALOG_VERSION:
        raise ActionRejected("incompatible_version")
    try:
        result = json.loads(str(receipt["result_json"]))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ActionRejected("stale_action") from exc
    if not isinstance(result, dict):
        raise ActionRejected("stale_action")
    intent = result.get("intent")
    source = result.get("source")
    details = result.get("details")
    if not isinstance(intent, dict) or not isinstance(source, dict) or not isinstance(details, dict):
        raise ActionRejected("stale_action")
    action_kind = str(receipt["action_kind"])
    if (
        _receipt_int(result.get("schema_version", 0)) != 1
        or _receipt_int(result.get("player_id", 0)) != int(player_id)
        or str(result.get("action_kind") or "") != action_kind
        or _receipt_int(intent.get("catalog_version", 0)) != CATALOG_VERSION
        or _receipt_int(source.get("catalog_version", 0)) != CATALOG_VERSION
        or str(source.get("content_id") or "") != str(intent.get("content_id") or "")
        or str(source.get("operation") or "") != str(intent.get("operation") or "")
        or action_kind != _expected_rav1_action_kind(intent)
        or str(receipt["request_hash"]) != intent_hash(action_kind, int(player_id), intent)
    ):
        raise ActionRejected("stale_action")
    content_id = str(intent.get("content_id") or "")
    operation = str(intent.get("operation") or "")
    if operation == "pin":
        pin = intent.get("pin") if isinstance(intent.get("pin"), dict) else {}
        if pin.get("owner_kind") not in {"project", "hunt", "gear"} or not str(pin.get("owner_id") or ""):
            raise ActionRejected("stale_action")
    elif content_id not in PROJECTS_BY_ID and content_id not in INTERACTIONS_BY_ID:
        raise ActionRejected("stale_action")
    elif content_id in PROJECTS_BY_ID and operation not in {"start", "deliver", "respond", "choose"}:
        raise ActionRejected("stale_action")
    elif content_id in INTERACTIONS_BY_ID:
        definition = INTERACTIONS_BY_ID[content_id]
        expected_operation = (
            "inspect" if definition.kind in {"discovery", "inspect"}
            else "claim" if definition.kind == "cache" else "deliver"
        )
        if operation != expected_operation:
            raise ActionRejected("stale_action")
    if token_row:
        try:
            pending = json.loads(str(token_row["payload"]))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ActionRejected("stale_action") from exc
        if _receipt_int(token_row["player_id"]) != int(player_id) or str(token_row["kind"]) != action_kind or pending != intent:
            raise ActionRejected("stale_action")
    for key in ("consumed", "granted", "progression"):
        if not isinstance(result.get(key), list):
            raise ActionRejected("stale_action")
    status = str(result.get("status") or "")
    allowed = {
        "start": {"started"}, "inspect": {"inspected"},
        "deliver": {"advanced", "completed", "delivered"},
        "respond": {"advanced", "completed"}, "choose": {"advanced", "completed"},
        "claim": {"completed"}, "pin": {"pinned", "unpinned"},
    }
    rejection = str(details.get("reason") or "")
    if rejection:
        if (
            rejection != status
            or result.get("consumed")
            or result.get("granted")
            or result.get("progression")
            or _receipt_int(result.get("xp_delta", 0)) != 0
            or _receipt_int(result.get("gold_delta", 0)) != 0
        ):
            raise ActionRejected("stale_action")
    elif status not in allowed.get(operation, set()):
        raise ActionRejected("stale_action")
    if not rejection:
        expected_consumed, expected_reward = _expected_receipt_effect(intent, status)
        if (
            _receipt_item_totals(result["consumed"]) != expected_consumed
            or _receipt_item_totals(result["granted"]) != tuple(sorted(expected_reward.items))
            or _receipt_int(result.get("xp_delta", 0)) != expected_reward.xp
            or _receipt_int(result.get("gold_delta", 0)) != expected_reward.gold
            or len(result["progression"]) != (1 if expected_reward.xp or expected_reward.gold else 0)
        ):
            raise ActionRejected("stale_action")
    if not rejection and operation == "choose":
        choice_id = ""
        selected = str(intent.get("choice") or "")
        project = PROJECTS_BY_ID[content_id]
        for step in project.steps:
            for objective in step.objectives:
                if objective.objective_id == intent.get("objective_id") and objective.kind == "choose":
                    choice_id = str(objective.target["choice_id"])
        if not choice_id or (details.get("choices") or {}).get(choice_id) != selected:
            raise ActionRejected("stale_action")
    if not rejection and operation == "pin":
        pin = intent["pin"]
        if details.get("owner_kind") != pin.get("owner_kind") or details.get("owner_id") != pin.get("owner_id"):
            raise ActionRejected("stale_action")
    return result


def _pin_owner_valid(conn, player_id: int, owner_kind: str, owner_id: str) -> bool:
    if owner_kind == "project":
        row = conn.execute(
            "SELECT state FROM rav1_projects WHERE player_id=? AND project_id=?", (int(player_id), owner_id)
        ).fetchone()
        return bool(row and str(row["state"]) == "active")
    elif owner_kind == "hunt":
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='player_hunt_contracts'"
        ).fetchone():
            return False
        row = conn.execute(
            "SELECT contract_key, status FROM player_hunt_contracts WHERE player_id=?", (int(player_id),)
        ).fetchone()
        return bool(row and str(row["contract_key"]) == owner_id
                    and str(row["status"]) in {"active", "completed"})
    elif owner_kind == "gear":
        has_goals = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='player_gear_goals'"
        ).fetchone()
        return bool(owner_id == "current" and has_goals and conn.execute(
            "SELECT 1 FROM player_gear_goals WHERE player_id=?", (int(player_id),)
        ).fetchone())
    return False


def _validate_pin_owner(conn, player_id: int, owner_kind: str, owner_id: str) -> None:
    if _pin_owner_valid(conn, player_id, owner_kind, owner_id):
        return
    if owner_kind == "project":
        raise ActionRejected("project_not_active")
    if owner_kind == "hunt":
        raise ActionRejected("hunt_not_active")
    if owner_kind == "gear":
        raise ActionRejected("gear_not_active")
    else:
        raise ActionRejected("malformed_action")


def _prune_invalid_pins(conn, player_id: int) -> None:
    for row in conn.execute(
        "SELECT owner_kind, owner_id FROM rav1_pins WHERE player_id=?", (int(player_id),)
    ).fetchall():
        if not _pin_owner_valid(conn, player_id, str(row["owner_kind"]), str(row["owner_id"])):
            conn.execute(
                "DELETE FROM rav1_pins WHERE player_id=? AND owner_kind=? AND owner_id=?",
                (int(player_id), str(row["owner_kind"]), str(row["owner_id"])),
            )


def _apply_pin(conn, player_id: int, pin: dict) -> dict:
    owner_kind, owner_id = str(pin.get("owner_kind") or ""), str(pin.get("owner_id") or "")
    remove = bool(pin.get("remove"))
    if remove:
        conn.execute(
            "DELETE FROM rav1_pins WHERE player_id=? AND owner_kind=? AND owner_id=?",
            (int(player_id), owner_kind, owner_id),
        )
        return {"status": "unpinned", "owner_kind": owner_kind, "owner_id": owner_id}
    _prune_invalid_pins(conn, player_id)
    _validate_pin_owner(conn, player_id, owner_kind, owner_id)
    existing = conn.execute(
        "SELECT slot FROM rav1_pins WHERE player_id=? AND owner_kind=? AND owner_id=?",
        (int(player_id), owner_kind, owner_id),
    ).fetchone()
    if existing:
        return {"status": "pinned", "slot": int(existing["slot"]), "owner_kind": owner_kind, "owner_id": owner_id}
    occupied = {int(row["slot"]) for row in conn.execute("SELECT slot FROM rav1_pins WHERE player_id=?", (int(player_id),))}
    slot = next((value for value in range(1, 4) if value not in occupied), None)
    if slot is None:
        raise ActionRejected("pins_full")
    conn.execute(
        "INSERT INTO rav1_pins(player_id, slot, owner_kind, owner_id) VALUES (?, ?, ?, ?)",
        (int(player_id), slot, owner_kind, owner_id),
    )
    return {"status": "pinned", "slot": slot, "owner_kind": owner_kind, "owner_id": owner_id}


def execute_regional_action(player_id: int, token: str, *, failure_hook=None) -> dict:
    """Execute one opaque RAV1 intent with receipt-first recovery."""
    request_id = f"ui:{token}"
    conn = get_connection()
    authorized = False
    action_kind = "rav1:unknown"
    request_hash = ""
    payload: dict = {}
    savepoint_open = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        receipt = conn.execute(
            """SELECT action_kind, request_hash, schema_version, catalog_version, result_json
               FROM economy_action_receipts WHERE player_id=? AND request_id=?""",
            (int(player_id), request_id),
        ).fetchone()
        if receipt:
            token_row = conn.execute(
                "SELECT player_id, kind, payload FROM player_ui_actions WHERE token=?", (token,)
            ).fetchone()
            result = _validate_recovered_receipt(player_id, receipt, token_row)
            conn.commit()
            return {**result, "recovered": True}

        token_row = conn.execute(
            "SELECT kind, payload FROM player_ui_actions WHERE token=? AND player_id=?",
            (token, int(player_id)),
        ).fetchone()
        if not token_row:
            raise ActionRejected("stale_action")
        action_kind = str(token_row["kind"])
        if not action_kind.startswith("rav1:"):
            raise ActionRejected("malformed_action")
        payload = json.loads(str(token_row["payload"]))
        if not isinstance(payload, dict) or int(payload.get("catalog_version", 0)) != CATALOG_VERSION:
            raise ActionRejected("incompatible_version")
        request_hash = intent_hash(action_kind, int(player_id), payload)
        conn.execute("SAVEPOINT rav1_business_mutation")
        savepoint_open = True
        raw = consume_action(conn, int(player_id), action_kind, token, payload=_canonical(payload))
        if json.loads(raw) != payload:
            raise ActionRejected("malformed_action")
        authorized = True
        player = peaceful_player(conn, int(player_id))
        expected_locations = tuple(resolve_location_id(location) for location in _expected_locations(payload, player_id, conn))
        if expected_locations and resolve_location_id(player["location_id"]) not in expected_locations:
            raise ActionRejected("wrong_location")
        operation, content_id = str(payload.get("operation") or ""), str(payload.get("content_id") or "")
        consumed: list[dict] = []
        reward_result: dict | None = None
        details: dict = {}

        if operation == "start":
            state = start_project_in_transaction(conn, player_id, content_id)
            status, details = "started", {"revision": state["revision"], "step_index": state["step_index"]}
        elif operation == "inspect":
            definition = FACTS_BY_ID.get(content_id)
            if not definition:
                raise ActionRejected("unknown_content")
            inserted = conn.execute(
                """INSERT OR IGNORE INTO rav1_facts
                   (player_id, fact_id, catalog_version, location_id) VALUES (?, ?, 1, ?)""",
                (int(player_id), content_id, definition.location_id),
            ).rowcount
            advanced = reconcile_new_fact(conn, player_id, content_id) if inserted else []
            status, details = "inspected", {"new": bool(inserted), "advanced_projects": advanced}
        elif operation in {"deliver", "respond", "choose"} and content_id in PROJECTS_BY_ID:
            state = get_project_state(player_id, content_id, conn=conn)
            if not state:
                raise ActionRejected("project_not_active")
            kind = "deliver" if operation == "deliver" else "respond" if operation == "respond" else "choose"
            objective = _project_objective_from_payload(state, payload, kind)
            if kind == "deliver":
                consumed = _consume_items(conn, player_id, tuple(objective.target["items"]))
            state = _mark_objective(
                conn, player_id, content_id, objective.objective_id,
                choice_value=payload.get("choice") if kind == "choose" else None,
                expected_revision=int(payload["revision"]), expected_step_id=str(payload["step_id"]),
            )
            if state["state"] == "completed":
                reward_result = _grant_reward(conn, player_id, content_id, PROJECTS_BY_ID[content_id].reward, request_id)
                status = "completed"
            else:
                status = "advanced"
            details = {"revision": state["revision"], "step_index": state["step_index"],
                       "choices": state["choices"], "step_results": state["step_results"]}
        elif operation == "deliver" and content_id in INTERACTIONS_BY_ID:
            definition = INTERACTIONS_BY_ID[content_id]
            if definition.kind not in {"request", "standing"}:
                raise ActionRejected("unknown_content")
            consumed = _consume_items(conn, player_id, definition.cost_items)
            if definition.kind == "request":
                reward_result = _grant_reward(conn, player_id, content_id, definition.reward, request_id)
                status = "completed"
            else:
                progression = apply_progression_reward(conn, player_id, 0, definition.reward.gold)
                reward_result = {"content_id": content_id, "xp": 0, "gold": definition.reward.gold,
                                 "items": [], "progression": progression}
                status = "delivered"
        elif operation == "claim" and content_id in {entry.content_id for entry in CACHES}:
            definition = INTERACTIONS_BY_ID[content_id]
            if definition.requires_fact_id and not conn.execute(
                "SELECT 1 FROM rav1_facts WHERE player_id=? AND fact_id=?",
                (int(player_id), definition.requires_fact_id),
            ).fetchone():
                raise ActionRejected("not_discovered")
            reward_result = _grant_reward(conn, player_id, content_id, definition.reward, request_id)
            status = "completed"
        elif operation == "pin":
            pin_result = _apply_pin(conn, player_id, payload.get("pin") or {})
            status, details = pin_result["status"], pin_result
        else:
            raise ActionRejected("malformed_action")

        if failure_hook:
            failure_hook("before_receipt")
        result = {
            "schema_version": 1, "action_kind": action_kind, "status": status,
            "player_id": int(player_id), "location_id": str(player["location_id"]),
            "recipe_id": None, "consumed": consumed,
            "granted": (reward_result or {}).get("items", []),
            "xp_delta": int((reward_result or {}).get("xp", 0)),
            "gold_delta": int((reward_result or {}).get("gold", 0)),
            "gold_after": int(((reward_result or {}).get("progression") or {}).get("gold_after", player["gold"])),
            "progression": [((reward_result or {}).get("progression") or {})] if reward_result else [],
            "source": {"catalog_version": 1, "content_id": content_id, "operation": operation},
            "details": details, "intent": payload,
        }
        conn.execute("RELEASE SAVEPOINT rav1_business_mutation")
        savepoint_open = False
        store_receipt(conn, int(player_id), request_id, action_kind, request_hash, result)
        conn.commit()
        if failure_hook:
            failure_hook("after_commit")
        return result
    except ActionRejected as exc:
        status = str(exc)
        if authorized and status not in {"stale_action", "wrong_location", "malformed_action", "incompatible_version"}:
            if savepoint_open:
                conn.execute("ROLLBACK TO SAVEPOINT rav1_business_mutation")
                conn.execute("RELEASE SAVEPOINT rav1_business_mutation")
                savepoint_open = False
            # Keep the outer IMMEDIATE transaction and its serialization lock.
            # The rejected authorized intent is terminal and its receipt is
            # committed atomically with token consumption.
            conn.execute(
                "UPDATE player_ui_actions SET used=1 WHERE token=? AND player_id=? AND kind=?",
                (token, int(player_id), action_kind),
            )
            if failure_hook:
                failure_hook("before_rejection_receipt")
            player = conn.execute("SELECT location_id, gold FROM players WHERE telegram_id=?", (int(player_id),)).fetchone()
            result = store_business_rejection(
                conn, player_id=int(player_id), request_id=request_id, action_kind=action_kind,
                request_hash=request_hash, status=status,
                location_id=player["location_id"] if player else None,
                gold_after=int(player["gold"]) if player else 0,
                source={"catalog_version": 1, "content_id": payload.get("content_id"),
                        "operation": payload.get("operation")},
                intent=payload,
            )
            conn.commit()
            return result
        conn.rollback()
        return {"status": status}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_pins(player_id: int, *, conn=None) -> list[dict]:
    owns = conn is None
    conn = conn or get_connection()
    try:
        return [dict(row) for row in conn.execute(
            "SELECT slot, owner_kind, owner_id FROM rav1_pins WHERE player_id=? ORDER BY slot",
            (int(player_id),),
        ) if _pin_owner_valid(conn, int(player_id), str(row["owner_kind"]), str(row["owner_id"]))]
    finally:
        if owns:
            conn.close()
