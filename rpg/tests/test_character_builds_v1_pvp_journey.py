"""Earned V1 PvP actions through production handlers and durable recovery."""

from __future__ import annotations

import asyncio
import copy
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from database import get_connection, get_player
from game.build_contract import RULES_VERSION
from game.build_progression import migrate_character_builds_v1
from game.combat_identity import cooldown_remaining
from game.combat_orders import consume_combat_intent, load_combat_orders
from game.field_catalog import FIELD_ITEMS
from game.pvp_live import (
    _LIVE_PVP_RUNTIME_STORE,
    advance_engagement_to_live_battle_if_ready,
    issue_manual_pvp_action_labels,
    process_live_pvp_due_events,
    resolve_live_battle_turn,
)
from handlers.location import handle_location_buttons
from tests.test_character_builds_v1_journeys import ProductionJourney


SWORD_ID = 94101
HOLY_ID = 94102
BOW_ID = 94103
STAFF_ID = 94104


def _rows(sql: str, args=()) -> list[dict]:
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def _engagement(engagement_id: int) -> dict:
    return _rows("SELECT * FROM pvp_engagements WHERE id=?", (engagement_id,))[0]


def _payload(row: dict) -> dict:
    return json.loads(str(row["reason_context"]))


def _primary_for(family: str) -> str:
    item = FIELD_ITEMS[f"field_{family}"]
    return next(
        key.removeprefix("req_")
        for key, value in item.items()
        if key.startswith("req_") and key != "req_level" and int(value or 0) > 0
    )


async def _earned_actor(
    player_id: int,
    *,
    family: str,
    entry_skill: str,
    name: str,
) -> ProductionJourney:
    journey = ProductionJourney(player_id, lang="en")
    await journey.register(primary=_primary_for(family), name=name)
    await journey.buy_and_equip_field_weapon(family)
    await journey.learn(family, entry_skill)
    await journey.travel("westwild_n1")
    return journey


async def _begin_pvp(
    attacker: ProductionJourney,
    defender: ProductionJourney,
    *,
    combat_seed: str,
) -> tuple[int, dict]:
    before = _rows(
        "SELECT COUNT(*) AS total FROM pvp_engagements WHERE attacker_id=? AND defender_id=?",
        (attacker.player_id, defender.player_id),
    )[0]["total"]
    callback = await attacker.callback(
        f"pvp_attack_{defender.player_id}", handle_location_buttons,
    )
    assert callback.answer.await_args.kwargs.get("show_alert") is True
    rows = _rows(
        "SELECT * FROM pvp_engagements WHERE attacker_id=? AND defender_id=? ORDER BY id DESC",
        (attacker.player_id, defender.player_id),
    )
    assert len(rows) == before + 1
    row = rows[0]
    ready_at = datetime.fromisoformat(str(row["engagement_ready_at"]))
    with patch(
        "game.pvp_live.uuid.uuid4",
        return_value=SimpleNamespace(hex=combat_seed),
    ):
        state, payload = advance_engagement_to_live_battle_if_ready(
            row, now=ready_at + timedelta(seconds=1),
        )
    assert state == "converted_to_battle"
    assert payload["battle"]["rules_version"] == RULES_VERSION
    assert payload["battle"]["combat_seed"] == combat_seed
    return int(row["id"]), payload


def _issued_actions(
    *,
    engagement_id: int,
    player_id: int,
    battle: dict,
    attacker_id: int,
    defender_id: int,
) -> dict[str, str]:
    labels = issue_manual_pvp_action_labels(
        engagement_id=engagement_id,
        player_id=player_id,
        lang="en",
        battle=battle,
        attacker_id=attacker_id,
        defender_id=defender_id,
    )
    actions: dict[str, str] = {}
    for token, _label in labels:
        stored = _rows(
            "SELECT payload FROM player_ui_actions WHERE player_id=? AND kind='combat_v1' AND token=?",
            (player_id, token),
        )[0]
        action = json.loads(stored["payload"])["action"]
        kind = str(action["kind"])
        action_id = (
            "normal_attack" if kind == "normal"
            else "guard" if kind == "guard"
            else f"skill:{action['skill_id']}" if kind == "skill"
            else kind
        )
        actions[action_id] = token
    return actions


async def _act(
    journey: ProductionJourney,
    *,
    engagement_id: int,
    action_id: str,
    attacker_id: int,
    defender_id: int,
) -> tuple[dict, dict, list[dict], dict[str, str]]:
    before_row = _engagement(engagement_id)
    before = _payload(before_row)["battle"]
    assert int(before["turn_owner"]) == journey.player_id
    issued = _issued_actions(
        engagement_id=engagement_id,
        player_id=journey.player_id,
        battle=before,
        attacker_id=attacker_id,
        defender_id=defender_id,
    )
    assert action_id in issued, (action_id, issued)
    before_events = len(before.get("events_v1") or [])
    response = await journey.callback(
        f"pvp_v1_{issued[action_id]}", handle_location_buttons,
    )
    assert response.answer.await_args.kwargs.get("show_alert") is True
    after = _payload(_engagement(engagement_id))["battle"]
    return before, after, list(after.get("events_v1") or [])[before_events:], issued


def _direct(events: list[dict], skill_id: str) -> dict:
    return next(
        event for event in events
        if event.get("kind") == "direct" and event.get("skill_id") == skill_id
    )


async def _run_pvp_journey() -> dict:
    _LIVE_PVP_RUNTIME_STORE.reset()
    migrate_character_builds_v1()
    sword = await _earned_actor(
        SWORD_ID, family="sword_1h", entry_skill="sword_rush", name="V1 Sword",
    )
    holy = await _earned_actor(
        HOLY_ID, family="holy_staff", entry_skill="smite", name="V1 Dawn",
    )
    bow = await _earned_actor(
        BOW_ID, family="bow", entry_skill="quick_shot", name="V1 Ranger",
    )
    staff = await _earned_actor(
        STAFF_ID, family="magic_staff", entry_skill="fireball", name="V1 Destruction",
    )

    sword_engagement, sword_payload = await _begin_pvp(
        sword, holy, combat_seed="pvp-earned-sword-holy-2",
    )
    assert sword_payload["illegal_aggression"] is False
    opening_row = _engagement(sword_engagement)
    opening_battle = _payload(opening_row)["battle"]
    opening_revision = int(opening_battle["turn_revision"])

    # Learned but PvE-only actions never consume the PvP turn.
    status, _ = resolve_live_battle_turn(
        opening_row, actor_id=SWORD_ID, selected_action_id="skill:sword_rush",
    )
    assert status == "invalid_action"
    assert _payload(_engagement(sword_engagement))["battle"]["turn_revision"] == opening_revision

    # Even a forged learned-rank projection cannot cross the equipped family.
    forged_row = copy.deepcopy(opening_row)
    forged = _payload(forged_row)
    forged["battle"]["participants_v1"][str(SWORD_ID)]["skill_ranks"]["quick_shot"] = 1
    forged_row["reason_context"] = json.dumps(forged)
    status, _ = resolve_live_battle_turn(
        forged_row, actor_id=SWORD_ID, selected_action_id="skill:quick_shot",
    )
    assert status == "invalid_action"
    assert _payload(_engagement(sword_engagement))["battle"]["turn_revision"] == opening_revision

    before_power, after_power, power_events, opening_tokens = await _act(
        sword,
        engagement_id=sword_engagement,
        action_id="skill:power_strike",
        attacker_id=SWORD_ID,
        defender_id=HOLY_ID,
    )
    power = _direct(power_events, "power_strike")
    assert power["hit"] is True and power["hp_removed"] > 0
    sword_after_power = after_power["participants_v1"][str(SWORD_ID)]
    assert sword_after_power["mana"] == before_power["participants_v1"][str(SWORD_ID)]["mana"] - 12
    assert cooldown_remaining(sword_after_power, "power_strike") == 2

    # An unused callback from the completed revision is rejected and cannot
    # add another order or advance the turn.
    stale_token = opening_tokens["normal_attack"]
    stale_revision = int(after_power["turn_revision"])
    stale_order_count = len(_rows(
        "SELECT * FROM combat_orders_v1 WHERE encounter_kind='pvp' AND encounter_id=?",
        (str(sword_engagement),),
    ))
    stale_response = await sword.callback(
        f"pvp_v1_{stale_token}", handle_location_buttons,
    )
    assert stale_response.answer.await_args.kwargs.get("show_alert") is True
    assert _payload(_engagement(sword_engagement))["battle"]["turn_revision"] == stale_revision
    assert len(_rows(
        "SELECT * FROM combat_orders_v1 WHERE encounter_kind='pvp' AND encounter_id=?",
        (str(sword_engagement),),
    )) == stale_order_count

    _, after_guard, guard_events, _ = await _act(
        holy,
        engagement_id=sword_engagement,
        action_id="guard",
        attacker_id=SWORD_ID,
        defender_id=HOLY_ID,
    )
    assert any(
        event.get("kind") == "guard" and event.get("timeout") is False
        for event in guard_events
    )
    assert any(
        effect.get("kind") == "guard" and effect.get("value") == 0.20
        for effect in after_guard["participants_v1"][str(HOLY_ID)]["effects"]
    )

    _, _, normal_events, _ = await _act(
        sword,
        engagement_id=sword_engagement,
        action_id="normal_attack",
        attacker_id=SWORD_ID,
        defender_id=HOLY_ID,
    )
    normal = _direct(normal_events, "normal")
    assert normal["hit"] is True and normal["hp_removed"] > 0
    assert normal["ordinary_reduction"] >= 0.20

    before_smite, after_smite, smite_events, _ = await _act(
        holy,
        engagement_id=sword_engagement,
        action_id="skill:smite",
        attacker_id=SWORD_ID,
        defender_id=HOLY_ID,
    )
    smite = _direct(smite_events, "smite")
    smite_heal = next(
        event for event in smite_events
        if event.get("kind") == "heal" and event.get("skill_id") == "smite"
    )
    assert smite["hit"] is True and smite["hp_removed"] > 0
    assert smite_heal["amount"] > 0
    holy_before = before_smite["participants_v1"][str(HOLY_ID)]
    holy_after = after_smite["participants_v1"][str(HOLY_ID)]
    assert holy_after["hp"] == holy_before["hp"] + smite_heal["amount"]
    assert holy_after["mana"] == holy_before["mana"] - 8
    assert cooldown_remaining(holy_after, "smite") == 1

    # Finish this ordinary fight entirely through issued production actions.
    for _ in range(80):
        row = _engagement(sword_engagement)
        if row["engagement_state"] == "cancelled":
            break
        battle = _payload(row)["battle"]
        actor_id = int(battle["turn_owner"])
        actor = sword if actor_id == SWORD_ID else holy
        await _act(
            actor,
            engagement_id=sword_engagement,
            action_id="normal_attack",
            attacker_id=SWORD_ID,
            defender_id=HOLY_ID,
        )
    else:
        raise AssertionError("earned PvP finalization exceeded 80 turns")
    final_row = _engagement(sword_engagement)
    final_battle = _payload(final_row)["battle"]
    assert final_row["engagement_state"] == "cancelled"
    assert final_battle["state"] == "finished"
    assert len(_rows(
        "SELECT * FROM pvp_log WHERE attacker_id=? AND defender_id=?",
        (SWORD_ID, HOLY_ID),
    )) == 1
    assert process_live_pvp_due_events() == []
    assert len(_rows(
        "SELECT * FROM pvp_log WHERE attacker_id=? AND defender_id=?",
        (SWORD_ID, HOLY_ID),
    )) == 1
    for player_id in (SWORD_ID, HOLY_ID):
        player = dict(get_player(player_id))
        assert player["in_battle"] == 0
        assert player["infamy"] == 0 and player["red_flag"] == 0

    bow_engagement, _ = await _begin_pvp(
        bow, staff, combat_seed="pvp-earned-bow-staff-1",
    )
    before_quick, after_quick, quick_events, _ = await _act(
        bow,
        engagement_id=bow_engagement,
        action_id="skill:quick_shot",
        attacker_id=BOW_ID,
        defender_id=STAFF_ID,
    )
    quick = _direct(quick_events, "quick_shot")
    assert quick["hit"] is True and quick["hp_removed"] > 0
    bow_before = before_quick["participants_v1"][str(BOW_ID)]
    bow_after = after_quick["participants_v1"][str(BOW_ID)]
    assert bow_after["mana"] == bow_before["mana"] - 6
    assert bow_after["cooldowns"]["quick_shot"] == bow_before["opportunity_index"] + 1

    # Commit Fireball, lose all runtime state, then recover the durable order.
    fire_row = _engagement(bow_engagement)
    fire_before = _payload(fire_row)["battle"]
    fire_tokens = _issued_actions(
        engagement_id=bow_engagement,
        player_id=STAFF_ID,
        battle=fire_before,
        attacker_id=BOW_ID,
        defender_id=STAFF_ID,
    )
    consumed = consume_combat_intent(STAFF_ID, fire_tokens["skill:fireball"])
    assert consumed["accepted"] is True
    fire_revision = int(fire_before["turn_revision"])
    orders = load_combat_orders(
        encounter_kind="pvp",
        encounter_id=str(bow_engagement),
        turn_revision=fire_revision,
    )
    assert len(orders) == 1 and orders[0]["action"]["skill_id"] == "fireball"
    _LIVE_PVP_RUNTIME_STORE.reset()
    status, recovered = resolve_live_battle_turn(
        _engagement(bow_engagement), actor_id=STAFF_ID, selected_action_id=None,
    )
    assert status == "resolved"
    fire_after = recovered["battle"]
    recovered_events = list(fire_after["events_v1"])[len(fire_before["events_v1"]):]
    fire = _direct(recovered_events, "fireball")
    assert fire["hit"] is True and fire["hp_removed"] > 0
    staff_before = fire_before["participants_v1"][str(STAFF_ID)]
    staff_after = fire_after["participants_v1"][str(STAFF_ID)]
    assert staff_after["mana"] == staff_before["mana"] - 12
    assert cooldown_remaining(staff_after, "fireball") == 1
    bow_burns = [
        effect for effect in fire_after["participants_v1"][str(BOW_ID)]["effects"]
        if effect.get("kind") == "burn" and effect.get("skill_id") == "fireball"
    ]
    assert len(bow_burns) == 1 and bow_burns[0]["duration"] == 2

    before_burn, after_burn, burn_events, _ = await _act(
        bow,
        engagement_id=bow_engagement,
        action_id="guard",
        attacker_id=BOW_ID,
        defender_id=STAFF_ID,
    )
    burn = next(
        event for event in burn_events
        if event.get("kind") == "dot" and event.get("effect") == "burn"
    )
    assert burn["amount"] > 0
    assert after_burn["participants_v1"][str(BOW_ID)]["hp"] < before_burn["participants_v1"][str(BOW_ID)]["hp"]

    # Reject a target already dead before submission without creating an
    # order. The pure evaluator's post-commit target-loss Guard remains intact.
    dead_row = _engagement(bow_engagement)
    dead_payload = _payload(dead_row)
    dead_payload["battle"]["attacker_hp"] = 0
    dead_target = dead_payload["battle"]["participants_v1"][str(BOW_ID)]
    dead_target["hp"] = 0
    dead_target["dead"] = True
    dead_row["reason_context"] = json.dumps(dead_payload)
    dead_revision = int(dead_payload["battle"]["turn_revision"])
    dead_orders_before = len(_rows(
        "SELECT * FROM combat_orders_v1 WHERE encounter_kind='pvp' AND encounter_id=?",
        (str(bow_engagement),),
    ))
    status, _ = resolve_live_battle_turn(
        dead_row, actor_id=STAFF_ID, selected_action_id="normal_attack",
    )
    assert status == "invalid_action"
    assert _payload(_engagement(bow_engagement))["battle"]["turn_revision"] == dead_revision
    assert len(_rows(
        "SELECT * FROM combat_orders_v1 WHERE encounter_kind='pvp' AND encounter_id=?",
        (str(bow_engagement),),
    )) == dead_orders_before

    return {
        "sword_engagement": sword_engagement,
        "bow_engagement": bow_engagement,
        "normal_damage": normal["hp_removed"],
        "power_damage": power["hp_removed"],
        "quick_damage": quick["hp_removed"],
        "fire_damage": fire["hp_removed"],
        "burn_damage": burn["amount"],
        "smite_damage": smite["hp_removed"],
        "smite_heal": smite_heal["amount"],
    }


def test_earned_supported_pvp_actions_rejections_restart_and_finalization():
    result = asyncio.run(_run_pvp_journey())
    assert result["sword_engagement"] != result["bow_engagement"]
    for key in (
        "normal_damage", "power_damage", "quick_damage", "fire_damage",
        "burn_damage", "smite_damage", "smite_heal",
    ):
        assert result[key] > 0
