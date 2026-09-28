"""Focused regression contract for independent-review findings F1-F9.

These tests intentionally exercise persisted authorities and emitted callbacks;
they are not substitutes for the J01-J20 acceptance journeys.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import threading

import pytest

import database
from database import get_connection, get_player
from game.action_receipts import issue_actions
from game.build_progression import migrate_character_builds_v1
from game.combat_orders import issue_combat_intents, persist_turn_result
from game.mobs import get_mob
from game.pve_live import (
    _prune_expired_forming_encounters,
    create_mixed_open_world_pve_encounter,
    create_or_load_open_world_pve_encounter,
    create_solo_pve_encounter,
    ensure_location_pve_spawn_instances,
    finish_solo_pve_encounter,
    leave_open_world_pve_encounter,
    list_location_mixed_encounter_availability,
    lock_open_world_pve_roster_for_runtime_start,
    persist_solo_pve_encounter_state,
    resolve_pve_flee_intent,
)
from game.pve_reward_settlement import prepare_victory_settlement
from game.regional_adventures import (
    execute_regional_action,
    get_project_state,
    issue_regional_action,
    list_claims,
)
from game.regional_catalog import PROJECTS_BY_ID
from game.regional_objectives import apply_combat_bindings
from game.regional_schema import ensure_regional_schema
from handlers.regional import (
    _list_screen,
    build_action_result,
    build_choice_preview,
    build_detail,
    build_regional_home,
    handle_regional_buttons,
)
from handlers.inventory import use_battle_consumable


def _move(player_id: int, location_id: str, *, lang: str = "en") -> dict:
    conn = get_connection()
    conn.execute(
        "UPDATE players SET location_id=?,lang=?,travel_revision=travel_revision+1,in_battle=0 WHERE telegram_id=?",
        (location_id, lang, player_id),
    )
    conn.commit(); conn.close()
    return dict(get_player(player_id))


def _inventory(player_id: int, item_id: str, quantity: int) -> None:
    conn = get_connection()
    conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (?,?,?)", (player_id, item_id, quantity))
    conn.commit(); conn.close()


def _quantity(player_id: int, item_id: str) -> int:
    conn = get_connection()
    value = conn.execute(
        "SELECT COALESCE(SUM(quantity),0) AS total FROM inventory WHERE telegram_id=? AND item_id=?",
        (player_id, item_id),
    ).fetchone()["total"]
    conn.close()
    return int(value)


def _callbacks(markup) -> list[str]:
    return [str(button.callback_data) for row in markup.inline_keyboard for button in row]


def _battle_state(mob_id: str) -> dict:
    mob = get_mob(mob_id)
    return {
        "mob_id": mob_id, "mob_hp": mob["hp"], "mob_max_hp": mob["hp"],
        "player_hp": 100, "player_max_hp": 100, "player_mana": 100,
        "player_max_mana": 100, "log": [],
    }


def _forming_mixed(location_id: str = "mireveil_n6", player_ids: list[int] | None = None) -> str:
    player_ids = player_ids or [1]
    for player_id in player_ids:
        _move(player_id, location_id)
    ensure_location_pve_spawn_instances(location_id=location_id)
    encounter_id, status = create_mixed_open_world_pve_encounter(
        owner_player_id=1,
        recipe_id="rav1_mireveil_n6_crosscurrent",
        battle_state=_battle_state("giant_leech"),
        side_a_player_ids=player_ids,
    )
    assert status == "created"
    return encounter_id


def _backdate(encounter_id: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE pve_encounters SET created_at=datetime('now','-10 minutes') WHERE encounter_id=?",
        (encounter_id,),
    )
    conn.commit(); conn.close()


@pytest.mark.parametrize("marker", [None, 2, "1"])
def test_f1_existing_bindings_with_missing_changed_or_unsupported_marker_fail_closed(marker):
    encounter_id = _forming_mixed()
    assert lock_open_world_pve_roster_for_runtime_start(encounter_id=encounter_id) == [1]
    conn = get_connection()
    state = json.loads(conn.execute(
        "SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?", (encounter_id,)
    ).fetchone()["battle_state_json"])
    if marker is None:
        state.pop("rav1_credit_version")
    else:
        state["rav1_credit_version"] = marker
    conn.execute("UPDATE pve_encounters SET battle_state_json=? WHERE encounter_id=?", (json.dumps(state), encounter_id))
    before = tuple(conn.execute("SELECT level,exp,gold FROM players WHERE telegram_id=1").fetchone())
    conn.commit(); conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(RuntimeError, match="rav1_combat_marker"):
        apply_combat_bindings(conn, encounter_id=encounter_id, plan={"eligible_recipient_ids": [1], "recipients": []})
    conn.rollback()
    assert tuple(conn.execute("SELECT level,exp,gold FROM players WHERE telegram_id=1").fetchone()) == before
    assert conn.execute(
        "SELECT applied_at FROM rav1_combat_bindings WHERE encounter_id=?", (encounter_id,)
    ).fetchone()["applied_at"] is None
    conn.close()


def test_f1_genuine_legacy_has_no_marker_and_no_bindings_but_unsupported_never_downgrades():
    encounter_id = create_solo_pve_encounter(player_id=1, battle_state=_battle_state("forest_wolf"), mob=get_mob("forest_wolf"))
    conn = get_connection(); conn.execute("BEGIN IMMEDIATE")
    assert apply_combat_bindings(conn, encounter_id=encounter_id, plan={}) == {}
    conn.rollback()
    state = json.loads(conn.execute(
        "SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?", (encounter_id,)
    ).fetchone()["battle_state_json"])
    state["rav1_credit_version"] = 99
    conn.execute("UPDATE pve_encounters SET battle_state_json=? WHERE encounter_id=?", (json.dumps(state), encounter_id))
    conn.commit(); conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(RuntimeError, match="unsupported"):
        apply_combat_bindings(conn, encounter_id=encounter_id, plan={})
    conn.rollback(); conn.close()


def test_f1_marker_is_preserved_by_solo_and_combat_order_state_saves():
    encounter_id = _forming_mixed()
    assert lock_open_world_pve_roster_for_runtime_start(encounter_id=encounter_id) == [1]
    conn = get_connection()
    row = conn.execute("SELECT battle_state_json,mob_json FROM pve_encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
    state, mob = json.loads(row["battle_state_json"]), json.loads(row["mob_json"])
    state.pop("rav1_credit_version")
    conn.close()
    assert persist_solo_pve_encounter_state(encounter_id=encounter_id, battle_state=state, mob=mob)
    conn = get_connection()
    persisted = json.loads(conn.execute(
        "SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?", (encounter_id,)
    ).fetchone()["battle_state_json"])
    assert persisted["rav1_credit_version"] == 1
    persisted.pop("rav1_credit_version")
    revision = int(persisted.get("turn_revision", 0))
    result = persist_turn_result(
        encounter_kind="pve", encounter_id=encounter_id, turn_revision=revision,
        result={"ok": True}, complete_state=persisted, conn=conn,
    )
    conn.commit()
    assert result["state"]["rav1_credit_version"] == 1
    conn.close()


def test_f1_marker_is_preserved_by_group_state_save():
    encounter_id = _forming_mixed(player_ids=[1, 777])
    assert lock_open_world_pve_roster_for_runtime_start(encounter_id=encounter_id) == [1, 777]
    conn = get_connection()
    row = conn.execute(
        "SELECT battle_state_json,mob_json FROM pve_encounters WHERE encounter_id=?", (encounter_id,)
    ).fetchone()
    state, mob = json.loads(row["battle_state_json"]), json.loads(row["mob_json"])
    state.pop("rav1_credit_version")
    conn.close()
    assert persist_solo_pve_encounter_state(encounter_id=encounter_id, battle_state=state, mob=mob)
    conn = get_connection()
    persisted = json.loads(conn.execute(
        "SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?", (encounter_id,)
    ).fetchone()["battle_state_json"])
    conn.close()
    assert persisted["rav1_credit_version"] == 1


def test_f1_marker_is_preserved_by_battle_consumable_persistence():
    encounter_id = _forming_mixed()
    assert lock_open_world_pve_roster_for_runtime_start(encounter_id=encounter_id) == [1]
    conn = get_connection()
    row = conn.execute(
        "SELECT battle_state_json,turn_revision,state_revision FROM pve_encounters WHERE encounter_id=?",
        (encounter_id,),
    ).fetchone()
    state = json.loads(row["battle_state_json"])
    state["player_hp"] = max(1, int(state.get("player_max_hp", 100)) - 20)
    conn.execute(
        "UPDATE pve_encounters SET battle_state_json=? WHERE encounter_id=?",
        (json.dumps(state), encounter_id),
    )
    conn.execute(
        "INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,'health_potion_small',1)"
    )
    inventory_id = conn.execute(
        "SELECT id FROM inventory WHERE telegram_id=1 AND item_id='health_potion_small'"
    ).fetchone()["id"]
    conn.commit(); conn.close()
    payload = f"{encounter_id}:{inventory_id}:1:{row['turn_revision']}:{row['state_revision']}"
    token = issue_actions(1, "battle_use", [payload])[payload]
    result = use_battle_consumable(1, token, encounter_id)
    assert result["status"] == "used"
    assert result["battle"]["rav1_credit_version"] == 1


def test_f1_marker_is_preserved_by_group_flee_persistence():
    migrate_character_builds_v1()
    encounter_id = _forming_mixed()
    assert lock_open_world_pve_roster_for_runtime_start(encounter_id=encounter_id) == [1]
    conn = get_connection()
    state = json.loads(conn.execute(
        "SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?", (encounter_id,)
    ).fetchone()["battle_state_json"])
    conn.close()
    action = {"kind": "flee", "skill_id": None, "item_id": None, "target_info": None}
    deadline = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
    token = issue_combat_intents(
        1, encounter_id=encounter_id, turn_revision=int(state["turn_revision"]),
        deadline_at=deadline, actions=[action],
    )[json.dumps(action, ensure_ascii=False, sort_keys=True, separators=(",", ":"))]
    result = resolve_pve_flee_intent(
        player_id=1, encounter_id=encounter_id, action_token=token, success=True,
    )
    assert result["fled"] is True
    assert result["battle"]["rav1_credit_version"] == 1


def test_f1_marker_is_preserved_in_t1_terminal_snapshot():
    migrate_character_builds_v1()
    encounter_id = _forming_mixed()
    assert lock_open_world_pve_roster_for_runtime_start(encounter_id=encounter_id) == [1]
    conn = get_connection()
    row = conn.execute(
        "SELECT battle_state_json,mob_json FROM pve_encounters WHERE encounter_id=?", (encounter_id,)
    ).fetchone()
    state, mob = json.loads(row["battle_state_json"]), json.loads(row["mob_json"])
    for unit in state["enemy_units"]:
        unit.update(hp=0, dead=True)
    for enemy in state["enemy_states_v1"]:
        enemy.update(hp=0, dead=True)
    state.update(mob_hp=0, mob_dead=True)
    conn.close()
    assert persist_solo_pve_encounter_state(encounter_id=encounter_id, battle_state=state, mob=mob)
    prepared = prepare_victory_settlement(encounter_id=encounter_id, battle_state=state, mob=mob)
    assert prepared["status"] == "prepared"
    conn = get_connection()
    persisted = json.loads(conn.execute(
        "SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?", (encounter_id,)
    ).fetchone()["battle_state_json"])
    conn.close()
    assert persisted["rav1_credit_version"] == 1


def test_f1_corrupt_binding_rolls_back_all_regional_progress():
    encounter_id = _forming_mixed()
    assert lock_open_world_pve_roster_for_runtime_start(encounter_id=encounter_id) == [1]
    conn = get_connection()
    conn.execute(
        "UPDATE rav1_combat_bindings SET bindings_json='not-json' WHERE encounter_id=?", (encounter_id,)
    )
    conn.commit(); conn.execute("BEGIN IMMEDIATE")
    with pytest.raises((RuntimeError, ValueError, json.JSONDecodeError)):
        apply_combat_bindings(conn, encounter_id=encounter_id, plan={"eligible_recipient_ids": [1]})
    conn.rollback()
    assert conn.execute(
        "SELECT applied_at FROM rav1_combat_bindings WHERE encounter_id=?", (encounter_id,)
    ).fetchone()["applied_at"] is None
    conn.close()


def test_f2_expiry_wins_first_once_for_mixed_sources_across_two_connections():
    encounter_id = _forming_mixed(); _backdate(encounter_id)
    first, second = get_connection(), get_connection()
    assert _prune_expired_forming_encounters(first, encounter_id=encounter_id) == [encounter_id]
    assert _prune_expired_forming_encounters(second, encounter_id=encounter_id) == []
    assert lock_open_world_pve_roster_for_runtime_start(encounter_id=encounter_id) is None
    row = second.execute("SELECT status FROM pve_encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
    assert row["status"] == "expired"
    assert second.execute(
        "SELECT COUNT(*) AS total FROM pve_spawn_instances WHERE linked_encounter_id=?", (encounter_id,)
    ).fetchone()["total"] == 0
    first.close(); second.close()


def test_f2_roster_activation_wins_before_ttl_and_active_encounter_survives_pruning():
    encounter_id = _forming_mixed()
    assert lock_open_world_pve_roster_for_runtime_start(encounter_id=encounter_id) == [1]
    _backdate(encounter_id)
    first, second = get_connection(), get_connection()
    assert _prune_expired_forming_encounters(first, encounter_id=encounter_id) == []
    assert _prune_expired_forming_encounters(second, encounter_id=encounter_id) == []
    assert second.execute("SELECT status FROM pve_encounters WHERE encounter_id=?", (encounter_id,)).fetchone()["status"] == "active"
    assert second.execute(
        "SELECT COUNT(*) AS total FROM pve_spawn_instances WHERE linked_encounter_id=? AND state='active'",
        (encounter_id,),
    ).fetchone()["total"] == 2
    first.close(); second.close()


def test_f2_named_source_expiry_releases_exactly_once_without_stale_busy_projection():
    _move(1, "westwild_n3")
    ensure_location_pve_spawn_instances(location_id="westwild_n3")
    conn = get_connection()
    spawn = conn.execute(
        "SELECT spawn_instance_id FROM pve_spawn_instances WHERE special_spawn_key='greyfang' AND state='idle'"
    ).fetchone()
    conn.close(); assert spawn
    encounter_id, status = create_or_load_open_world_pve_encounter(
        owner_player_id=1, location_id="westwild_n3", mob_id="forest_wolf",
        battle_state=_battle_state("forest_wolf"), mob=get_mob("forest_wolf"),
        spawn_instance_id=spawn["spawn_instance_id"],
    )
    assert status == "created"; _backdate(encounter_id)
    first, second = get_connection(), get_connection()
    assert _prune_expired_forming_encounters(first, encounter_id=encounter_id) == [encounter_id]
    assert _prune_expired_forming_encounters(second, encounter_id=encounter_id) == []
    row = second.execute(
        "SELECT state,linked_encounter_id FROM pve_spawn_instances WHERE spawn_instance_id=?", (spawn["spawn_instance_id"],)
    ).fetchone()
    assert tuple(row) == ("idle", None)
    first.close(); second.close()


def test_f3_same_token_business_rejections_serialize_to_one_durable_receipt():
    _move(1, "hub_westwild"); _inventory(1, "field_ration", 4)
    first = issue_regional_action(1, "ww_woodcutter_provisions", "deliver")
    assert execute_regional_action(1, first)["status"] == "completed"
    token = issue_regional_action(1, "ww_woodcutter_provisions", "deliver")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: execute_regional_action(1, token), range(2)))
    assert [row["status"] for row in results] == ["already_resolved", "already_resolved"]
    assert sum(bool(row.get("recovered")) for row in results) == 1
    assert _quantity(1, "field_ration") == 2
    conn = get_connection()
    assert conn.execute(
        "SELECT COUNT(*) AS total FROM economy_action_receipts WHERE player_id=1 AND request_id=?",
        (f"ui:{token}",),
    ).fetchone()["total"] == 1
    conn.close()


def test_f3_rejection_retains_lock_until_receipt_before_replenishment_retry():
    _move(1, "hub_westwild")
    token = issue_regional_action(1, "ww_ration_order", "deliver")
    reached = threading.Event(); release = threading.Event()

    def reject():
        return execute_regional_action(
            1, token,
            failure_hook=lambda point: (reached.set(), release.wait(5)) if point == "before_rejection_receipt" else None,
        )

    def replenish():
        reached.wait(5)
        _inventory(1, "field_ration", 2)
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        rejection = pool.submit(reject)
        refill = pool.submit(replenish)
        assert reached.wait(5)
        release.set()
        assert rejection.result()["status"] == "insufficient_goods"
        assert refill.result() is True
    assert execute_regional_action(1, token)["status"] == "insufficient_goods"
    fresh = issue_regional_action(1, "ww_ration_order", "deliver")
    assert execute_regional_action(1, fresh)["status"] == "delivered"


def _valid_project_payload(project_id: str, step_index: int) -> tuple[dict, dict, dict]:
    project = PROJECTS_BY_ID[project_id]
    progress = {f"{step.step_id}.{objective.objective_id}": 0 for step in project.steps for objective in step.objectives}
    choices, results = {}, {}
    for step in project.steps[:step_index]:
        winners = list(step.objectives if step.mode == "all" else step.objectives[:1])
        results[step.step_id] = [objective.objective_id for objective in winners]
        for objective in winners:
            progress[f"{step.step_id}.{objective.objective_id}"] = objective.required
            if objective.kind == "choose":
                choices[objective.target["choice_id"]] = objective.target["values"][0]
    return progress, choices, results


def _insert_project(project_id: str, step_index: int) -> None:
    progress, choices, results = _valid_project_payload(project_id, step_index)
    conn = get_connection()
    conn.execute(
        """INSERT INTO rav1_projects
           (player_id,project_id,catalog_version,state,step_index,progress_json,choices_json,step_results_json,revision)
           VALUES (1,?,1,'active',?,?,?,?,1)""",
        (project_id, step_index, json.dumps(progress), json.dumps(choices), json.dumps(results)),
    )
    conn.commit(); conn.close()


@pytest.mark.parametrize("corruption", [
    "skipped_evidence", "future_progress", "missing_all", "invalid_any",
    "multiple_any", "invalid_result_id", "premature_choice", "missing_choice",
])
def test_f4_semantically_impossible_project_rows_fail_startup_without_repair(corruption):
    project_id, step_index = ("fs_jammed_sled", 2) if corruption in {"invalid_any", "multiple_any"} else ("ar_two_names", 1)
    progress, choices, results = _valid_project_payload(project_id, step_index)
    if corruption == "skipped_evidence": progress["evidence.temple"] = 0
    elif corruption == "future_progress": progress["record.attribution"] = 1
    elif corruption == "missing_all": results.pop("evidence")
    elif corruption == "invalid_any": results["repair"] = ["bogus"]
    elif corruption == "multiple_any":
        results["repair"] = ["materials", "clear_lizard"]
        progress["repair.clear_lizard"] = 1
    elif corruption == "invalid_result_id": results["evidence"] = ["temple", "bogus"]
    elif corruption == "premature_choice": choices["attribution"] = "shared_credit"
    elif corruption == "missing_choice":
        step_index = 2
        progress["record.attribution"] = 1
        results["record"] = ["attribution"]
    conn = get_connection()
    state = "completed" if step_index == len(PROJECTS_BY_ID[project_id].steps) else "active"
    completed_at = "CURRENT_TIMESTAMP" if state == "completed" else "NULL"
    conn.execute(
        f"""INSERT INTO rav1_projects
            (player_id,project_id,catalog_version,state,step_index,progress_json,choices_json,step_results_json,revision,completed_at)
            VALUES (1,?,1,?,?,?,?,?,?,1,{completed_at})""",
        (project_id, state, step_index, json.dumps(progress), json.dumps(choices), json.dumps(results)),
    )
    conn.commit()
    before = tuple(conn.execute("SELECT * FROM rav1_projects WHERE player_id=1 AND project_id=?", (project_id,)).fetchone())
    with pytest.raises(RuntimeError):
        ensure_regional_schema(conn)
    after = tuple(conn.execute("SELECT * FROM rav1_projects WHERE player_id=1 AND project_id=?", (project_id,)).fetchone())
    assert after == before
    conn.close()


@pytest.mark.parametrize("project_id,step_index", [
    ("ar_two_names", 0), ("ar_two_names", 1), ("fs_jammed_sled", 2),
])
def test_f4_valid_intermediate_project_states_survive_startup_validation(project_id, step_index):
    _insert_project(project_id, step_index)
    conn = get_connection(); ensure_regional_schema(conn)
    assert conn.execute(
        "SELECT step_index FROM rav1_projects WHERE player_id=1 AND project_id=?", (project_id,)
    ).fetchone()["step_index"] == step_index
    conn.close()


def test_f4_valid_completed_project_with_required_choice_survives_startup_validation():
    project = PROJECTS_BY_ID["ar_two_names"]
    progress, choices, results = _valid_project_payload(project.project_id, len(project.steps))
    reward = {
        "content_id": project.project_id, "xp": project.reward.xp, "gold": project.reward.gold,
        "items": [], "progression": {},
    }
    conn = get_connection()
    conn.execute(
        """INSERT INTO rav1_projects
           (player_id,project_id,catalog_version,state,step_index,progress_json,choices_json,step_results_json,revision,completed_at)
           VALUES (1,?,1,'completed',?,?,?,?,1,CURRENT_TIMESTAMP)""",
        (project.project_id, len(project.steps), json.dumps(progress), json.dumps(choices), json.dumps(results)),
    )
    conn.execute(
        """INSERT INTO rav1_claims(player_id,content_id,catalog_version,request_id,reward_json)
           VALUES (1,?,1,'valid-complete',?)""", (project.project_id, json.dumps(reward)),
    )
    conn.commit(); ensure_regional_schema(conn)
    assert conn.execute("SELECT state FROM rav1_projects WHERE project_id=?", (project.project_id,)).fetchone()["state"] == "completed"
    conn.close()


@pytest.mark.parametrize("tamper", ["owner", "operation", "content", "hash", "version", "result"])
def test_f5_receipt_recovery_rejects_tampered_immutable_identity(tamper):
    _move(1, "hub_westwild"); _inventory(1, "field_ration", 2)
    token = issue_regional_action(1, "ww_woodcutter_provisions", "deliver")
    assert execute_regional_action(1, token)["status"] == "completed"
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM economy_action_receipts WHERE player_id=1 AND request_id=?", (f"ui:{token}",)
    ).fetchone()
    result = json.loads(row["result_json"])
    if tamper == "owner": result["player_id"] = 777
    elif tamper == "operation": result["intent"]["operation"] = "claim"
    elif tamper == "content": result["source"]["content_id"] = "mv_medic_table"
    elif tamper == "hash": conn.execute(
        "UPDATE economy_action_receipts SET request_hash=? WHERE player_id=1 AND request_id=?", ("0" * 64, f"ui:{token}"))
    elif tamper == "version": conn.execute(
        "UPDATE economy_action_receipts SET catalog_version=2 WHERE player_id=1 AND request_id=?", (f"ui:{token}",))
    elif tamper == "result": result["consumed"] = "field_ration"
    if tamper not in {"hash", "version"}:
        conn.execute(
            "UPDATE economy_action_receipts SET result_json=? WHERE player_id=1 AND request_id=?",
            (json.dumps(result), f"ui:{token}"),
        )
    conn.commit(); conn.close()
    assert execute_regional_action(1, token)["status"] in {"stale_action", "incompatible_version"}


def test_f5_committed_receipt_recovers_after_token_loss_move_revisions_restart_and_locale_change():
    _move(1, "hub_westwild"); _inventory(1, "field_ration", 2)
    token = issue_regional_action(1, "ww_woodcutter_provisions", "deliver")
    committed = execute_regional_action(1, token)
    conn = get_connection()
    conn.execute("DELETE FROM player_ui_actions WHERE token=?", (token,))
    conn.execute("UPDATE players SET location_id='hub_mireveil',lang='es',travel_revision=travel_revision+7 WHERE telegram_id=1")
    conn.commit(); conn.close()
    database.init_db()
    replay = execute_regional_action(1, token)
    assert replay["recovered"] is True
    assert {key: replay[key] for key in committed} == committed
    text, _markup = build_action_result(dict(get_player(1)), replay)
    assert "raciones" in text.lower() and "field_ration" not in text


class _User:
    id = 1


class _Query:
    def __init__(self, data):
        self.data, self.from_user, self.answers, self.edits = data, _User(), [], []
    async def answer(self, text=None, **kwargs): self.answers.append((text, kwargs))
    async def edit_message_text(self, text, **kwargs): self.edits.append((text, kwargs))


class _Update:
    def __init__(self, data): self.callback_query = _Query(data)


@pytest.mark.parametrize("lang", ["ru", "en", "es"])
@pytest.mark.parametrize("choice_index", [0, 1])
@pytest.mark.parametrize("project_id,step_index,location_id", [
    ("ar_two_names", 1, "hub_ashen_ruins"),
    ("ar_unquiet_storehouse", 2, "hub_ashen_ruins"),
    ("mv_ferry_crew", 2, "mireveil_n8"),
])
def test_f6_emitted_choice_selection_and_cancel_are_nonmutating_confirm_is_only_commit(lang, choice_index, project_id, step_index, location_id):
    player = _move(1, location_id, lang=lang); _insert_project(project_id, step_index)
    before = json.dumps(get_project_state(1, project_id), default=str, sort_keys=True)
    _text, markup = build_detail(player, "p", project_id)
    selections = [value for value in _callbacks(markup) if value.startswith("rv:c:")]
    selection = selections[choice_index]
    stale_alternate = selections[1 - choice_index]
    selected = _Update(selection); asyncio.run(handle_regional_buttons(selected, None))
    preview_text, preview_markup = selected.callback_query.edits[-1]
    assert json.dumps(get_project_state(1, project_id), default=str, sort_keys=True) == before
    callbacks = _callbacks(preview_markup["reply_markup"])
    assert any(value.startswith("rv:a:") for value in callbacks)
    assert f"rv:d:p:{project_id}" in callbacks
    assert all(fragment in preview_text.lower() for fragment in {
        "permanent" if lang == "en" else "навсегда" if lang == "ru" else "permanente",
    })
    cancel = _Update(f"rv:d:p:{project_id}"); asyncio.run(handle_regional_buttons(cancel, None))
    assert json.dumps(get_project_state(1, project_id), default=str, sort_keys=True) == before
    confirm = _Update(next(value for value in callbacks if value.startswith("rv:a:")))
    asyncio.run(handle_regional_buttons(confirm, None))
    committed = get_project_state(1, project_id)
    assert committed["choices"]
    alternate = _Update(stale_alternate); asyncio.run(handle_regional_buttons(alternate, None))
    assert get_project_state(1, project_id)["choices"] == committed["choices"]
    database.init_db(); conn = get_connection(); ensure_regional_schema(conn); conn.close()
    assert get_project_state(1, project_id)["choices"] == committed["choices"]


def test_f7_every_visible_hunt_gear_and_project_pin_token_has_distinct_scope_and_works():
    _move(1, "hub_westwild"); _insert_project("ww_tool_roll", 0)
    conn = get_connection()
    conn.execute("""CREATE TABLE IF NOT EXISTS player_hunt_contracts (
        player_id INTEGER PRIMARY KEY, contract_key TEXT, status TEXT, progress_kills INTEGER DEFAULT 0)""")
    conn.execute("INSERT INTO player_hunt_contracts(player_id,contract_key,status) VALUES (1,'hunt_greyfang','active')")
    conn.execute("""CREATE TABLE IF NOT EXISTS player_gear_goals (
        player_id INTEGER PRIMARY KEY, base_item_id TEXT)""")
    conn.execute("INSERT INTO player_gear_goals(player_id,base_item_id) VALUES (1,'field_sword_1h')")
    conn.commit(); conn.close()
    _text, markup = _list_screen(dict(get_player(1)), "p", 0, "all")
    tokens = [value.removeprefix("rv:a:") for value in _callbacks(markup) if value.startswith("rv:a:")]
    conn = get_connection()
    kinds = [conn.execute("SELECT kind FROM player_ui_actions WHERE token=?", (token,)).fetchone()["kind"] for token in tokens]
    conn.close()
    assert len(tokens) == len(kinds) == 3 and len(set(kinds)) == 3
    assert all(execute_regional_action(1, token)["status"] == "pinned" for token in tokens)
    _text, refreshed = _list_screen(dict(get_player(1)), "p", 0, "all")
    assert len([value for value in _callbacks(refreshed) if value.startswith("rv:a:")]) >= 3
    project_unpin = issue_regional_action(
        1, "ww_tool_roll", "pin", pin={"owner_kind":"project", "owner_id":"ww_tool_roll", "remove":True},
    )
    assert execute_regional_action(1, project_unpin)["status"] == "unpinned"
    project_repin = issue_regional_action(
        1, "ww_tool_roll", "pin", pin={"owner_kind":"project", "owner_id":"ww_tool_roll", "remove":False},
    )
    assert execute_regional_action(1, project_repin)["status"] == "pinned"
    _insert_project("ar_two_names", 0)
    fourth = issue_regional_action(
        1, "ar_two_names", "pin", pin={"owner_kind":"project", "owner_id":"ar_two_names", "remove":False},
    )
    assert execute_regional_action(1, fourth)["status"] == "pins_full"
    database.init_db(); conn = get_connection(); ensure_regional_schema(conn); conn.close()
    assert len(__import__('game.regional_adventures', fromlist=['list_pins']).list_pins(1)) == 3


def test_f8_navigation_previews_risk_hidden_cache_and_resolved_leads_follow_emitted_buttons():
    player = _move(1, "hub_mireveil")
    home_text, home = build_regional_home(player)
    assert home_text and any(value.startswith("map_route_") for value in _callbacks(home))
    project_text, project = build_detail(player, "p", "mv_medic_practice")
    assert "field_tonic" not in project_text
    assert {"pe_r:field_tonic", "pe_p:alchemy"} & set(_callbacks(project)) == set()
    _insert_project("mv_medic_practice", 0)
    project_text, project = build_detail(player, "p", "mv_medic_practice")
    assert "field_tonic" not in project_text and "pe_r:field_tonic" in _callbacks(project)
    hidden_text, _hidden = build_detail(_move(1, "westwild_n7"), "i", "ww_root_cache")
    assert "potion" not in hidden_text.lower() and "shard" not in hidden_text.lower()
    risk_text, risk = build_detail(_move(1, "mireveil_n6"), "e", "rav1_mireveil_n6_crosscurrent")
    assert "2" in risk_text and any(value.startswith("map_route_") for value in _callbacks(risk))


def test_f9_success_rejection_standing_choice_and_locale_replays_render_saved_result_without_raw_ids():
    _move(1, "hub_westwild", lang="en"); _inventory(1, "field_ration", 2)
    token = issue_regional_action(1, "ww_ration_order", "deliver")
    committed = execute_regional_action(1, token)
    _move(1, "hub_mireveil", lang="es")
    replay = execute_regional_action(1, token)
    text, _markup = build_action_result(dict(get_player(1)), replay)
    assert committed["consumed"] == replay["consumed"]
    assert "ración" in text.lower() and "field_ration" not in text and "field_tonic" not in text
    rejected_token = issue_regional_action(1, "mv_stew_order", "deliver")
    rejected = execute_regional_action(1, rejected_token)
    rejected_text, _ = build_action_result(dict(get_player(1)), execute_regional_action(1, rejected_token))
    assert rejected["status"] == "insufficient_goods"
    assert "lote" in rejected_text.lower() or "completo" in rejected_text.lower()
