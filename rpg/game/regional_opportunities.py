"""Read-only RAV1 opportunity aggregation.

This module never writes progress, claims, facts, pins, inventory, or travel state.
"""

from __future__ import annotations

from database import get_connection
from game.regional_adventures import get_project_state, list_claims, list_facts, list_pins, list_project_states
from game.regional_catalog import (
    CACHES, DIRECT_REQUESTS, DISCOVERIES, FACTS_BY_ID, INTERACTIONS_BY_ID,
    PROJECTS, PROJECTS_BY_ID, REGIONAL_SUMMARIES, REGIONAL_SUMMARIES_BY_CODE,
    STANDING_DELIVERIES,
)


PAGE_SIZE = 6
VIEW_CODES = frozenset({"h", "n", "l", "p", "r", "s", "w"})
REGION_CODES = frozenset({"all", "ww", "fs", "ar", "ss", "mv"})


def chapter_one_complete(player_id: int, *, conn=None) -> bool:
    owns = conn is None
    conn = conn or get_connection()
    try:
        return conn.execute(
            "SELECT 1 FROM player_contract_history WHERE player_id=? AND contract_key='chapter_homecoming'",
            (int(player_id),),
        ).fetchone() is not None
    finally:
        if owns:
            conn.close()


def inventory_counts(player_id: int, *, conn=None) -> dict[str, int]:
    owns = conn is None
    conn = conn or get_connection()
    try:
        return {str(row["item_id"]): int(row["quantity"]) for row in conn.execute(
            "SELECT item_id, SUM(quantity) AS quantity FROM inventory WHERE telegram_id=? GROUP BY item_id",
            (int(player_id),),
        )}
    finally:
        if owns:
            conn.close()


def _record(kind: str, content_id: str, status: str, **extra) -> dict:
    return {"kind": kind, "content_id": content_id, "status": status, **extra}


def nearby(player: dict, *, conn=None) -> list[dict]:
    owns = conn is None
    conn = conn or get_connection()
    try:
        player_id, location_id = int(player["telegram_id"]), str(player["location_id"])
        claims, facts = list_claims(player_id, conn=conn), list_facts(player_id, conn=conn)
        states = {state["project_id"]: state for state in list_project_states(player_id, conn=conn)}
        rows: list[dict] = []
        for project in PROJECTS:
            state = states.get(project.project_id)
            if state is None and location_id in project.start_locations:
                rows.append(_record("project", project.project_id, "available", operation="start"))
            elif state and state["state"] == "active":
                step = project.steps[int(state["step_index"])]
                local = [objective for objective in step.objectives if location_id in objective.locations]
                if local:
                    rows.append(_record("project", project.project_id, "active", state=state,
                                        objectives=local))
        for fact_id, definition in FACTS_BY_ID.items():
            if definition.location_id == location_id:
                rows.append(_record("discovery" if definition.kind == "discovery" else "inspect",
                                    fact_id, "found" if fact_id in facts else "available",
                                    operation="inspect"))
        for definition in DIRECT_REQUESTS:
            if definition.location_id == location_id and definition.content_id not in claims:
                rows.append(_record("interaction", definition.content_id, "available", operation="deliver"))
        for definition in CACHES:
            if (definition.location_id == location_id and definition.content_id not in claims
                    and definition.requires_fact_id in facts):
                rows.append(_record("interaction", definition.content_id, "available", operation="claim"))
        if any(definition.location_id == location_id for definition in STANDING_DELIVERIES):
            rows.append(_record("work_link", "local_work", "available"))
        from game.pve_live import (
            list_location_mixed_encounter_availability,
            list_location_special_target_availability,
        )
        for mixed in list_location_mixed_encounter_availability(location_id=location_id):
            rows.append(_record("encounter", str(mixed["recipe_id"]),
                                str(mixed["availability"]), data=mixed))
        for target in list_location_special_target_availability(location_id=location_id):
            rows.append(_record("encounter", str(target["content_id"]),
                                str(target["availability"]), data=target))
        category = {"project":0,"interaction":1,"discovery":2,"inspect":2,"encounter":3,"work_link":4}
        return sorted(rows, key=lambda row: (category[row["kind"]], row["content_id"]))
    finally:
        if owns:
            conn.close()


def leads(player_id: int, region_code: str = "all", *, conn=None) -> list[dict]:
    owns = conn is None
    conn = conn or get_connection()
    try:
        rows: list[dict] = []
        states = {state["project_id"]: state for state in list_project_states(player_id, conn=conn)}
        claims = list_claims(player_id, conn=conn)
        summaries = REGIONAL_SUMMARIES if region_code == "all" else (
            (REGIONAL_SUMMARIES_BY_CODE[region_code],) if region_code in REGIONAL_SUMMARIES_BY_CODE else ()
        )
        for summary in summaries:
            rows.append(_record("region", summary["content_id"], "available", data=summary))
            region_id = summary["region_id"]
            for project in PROJECTS:
                if (project.public or project.project_id in states) and project.region_id == region_id:
                    state = states.get(project.project_id)
                    status = "resolved" if project.project_id in claims else "active" if state else "available"
                    rows.append(_record("project", project.project_id, status))
            for definition in DIRECT_REQUESTS:
                if definition.region_id == region_id:
                    status = "resolved" if definition.content_id in claims else "available"
                    rows.append(_record("interaction", definition.content_id, status))
        return rows
    finally:
        if owns:
            conn.close()


def pursuits(player_id: int, *, conn=None) -> list[dict]:
    owns = conn is None
    conn = conn or get_connection()
    try:
        pins = {(row["owner_kind"], row["owner_id"]): row["slot"] for row in list_pins(player_id, conn=conn)}
        rows = [
            _record("project", state["project_id"], "active", state=state,
                    pinned=pins.get(("project", state["project_id"])))
            for state in list_project_states(player_id, conn=conn) if state["state"] == "active"
        ]
        hunt = conn.execute(
            "SELECT contract_key, status FROM player_hunt_contracts WHERE player_id=?", (int(player_id),)
        ).fetchone() if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='player_hunt_contracts'"
        ).fetchone() else None
        if hunt:
            rows.append(_record("hunt", str(hunt["contract_key"]), str(hunt["status"]),
                                pinned=pins.get(("hunt", str(hunt["contract_key"])))))
        has_goals = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='player_gear_goals'"
        ).fetchone()
        goal = conn.execute(
            "SELECT base_item_id FROM player_gear_goals WHERE player_id=?", (int(player_id),)
        ).fetchone() if has_goals else None
        rows.append(_record("gear", "current", "active" if goal else "available",
                            goal=str(goal["base_item_id"]) if goal else None,
                            pinned=pins.get(("gear", "current"))))
        rows.append(_record("profession", "professions", "available"))
        return rows
    finally:
        if owns:
            conn.close()


def resolved(player_id: int, findings: bool = False, *, conn=None) -> list[dict]:
    owns = conn is None
    conn = conn or get_connection()
    try:
        if findings:
            rows = conn.execute(
                "SELECT fact_id, discovered_at FROM rav1_facts WHERE player_id=? ORDER BY discovered_at DESC, fact_id",
                (int(player_id),),
            ).fetchall()
            discovery_ids = {entry.content_id for entry in DISCOVERIES}
            return [_record("discovery", str(row["fact_id"]), "found", timestamp=row["discovered_at"])
                    for row in rows if str(row["fact_id"]) in discovery_ids]
        rows = conn.execute(
            "SELECT content_id, claimed_at, reward_json FROM rav1_claims WHERE player_id=? ORDER BY claimed_at DESC, content_id",
            (int(player_id),),
        ).fetchall()
        return [_record("project" if str(row["content_id"]) in PROJECTS_BY_ID else "interaction",
                        str(row["content_id"]), "resolved", timestamp=row["claimed_at"],
                        reward_json=str(row["reward_json"])) for row in rows]
    finally:
        if owns:
            conn.close()


def local_work(player_id: int, *, conn=None) -> list[dict]:
    owns = conn is None
    conn = conn or get_connection()
    try:
        player = conn.execute("SELECT location_id FROM players WHERE telegram_id=?", (int(player_id),)).fetchone()
        counts = inventory_counts(player_id, conn=conn)
        return [
            _record("work", definition.content_id,
                    "local" if player and str(player["location_id"]) == definition.location_id else "remote",
                    definition=definition,
                    owned={item_id: counts.get(item_id, 0) for item_id, _quantity in definition.cost_items})
            for definition in STANDING_DELIVERIES
        ]
    finally:
        if owns:
            conn.close()


def page(rows: list[dict], requested: int) -> tuple[list[dict], int, int]:
    pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
    current = min(max(0, int(requested)), pages - 1)
    return rows[current * PAGE_SIZE:(current + 1) * PAGE_SIZE], current, pages
