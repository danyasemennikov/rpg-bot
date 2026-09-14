"""Earned group-identity journeys through real source and Telegram handlers."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

from database import get_connection, get_player
from game.build_contract import (
    BRANCH_IDENTITIES,
    POWER_STRIKE,
    SKILL_SPECS,
    rank_mana_cost,
)
from game.build_progression import migrate_character_builds_v1
from game.combat_identity import cooldown_remaining
from game.enemy_profiles import MIXED_ENCOUNTERS
from game.locations import WORLD_LOCATIONS
from game.pve_live import reset_solo_pve_runtime_store
from game.pve_reward_settlement import get_settlement
from game.weapon_mastery import get_mastery
from handlers.battle import handle_battle_buttons
from handlers.location import handle_combat_buttons, handle_location_buttons
from tests.test_character_builds_v1_journeys import (
    BRANCH_CASES,
    ProductionJourney,
    _callbacks,
    _run_branch_journey,
)


@contextmanager
def _frozen_combat_clock():
    """Keep production deadlines stable while the fake Telegram UI renders."""
    frozen_now = datetime.now(timezone.utc)
    with (
        patch("game.pve_live._utc_now", return_value=frozen_now),
        patch("game.combat_orders.datetime", wraps=datetime) as order_datetime,
    ):
        order_datetime.now.return_value = frozen_now
        order_datetime.fromisoformat.side_effect = datetime.fromisoformat
        yield


def _encounter_state(encounter_id: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?",
            (encounter_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    return json.loads(row["battle_state_json"])


def _shortest_route(origin: str, destination: str) -> list[str]:
    if origin == destination:
        return []
    pending = deque([(origin, [])])
    visited = {origin}
    while pending:
        current, path = pending.popleft()
        for neighbor in WORLD_LOCATIONS[current]["connections"]:
            if neighbor in visited:
                continue
            next_path = [*path, neighbor]
            if neighbor == destination:
                return next_path
            visited.add(neighbor)
            pending.append((neighbor, next_path))
    raise AssertionError((origin, destination))


async def _move(journey: ProductionJourney, destination: str) -> None:
    origin = str(get_player(journey.player_id)["location_id"])
    await journey.travel(*_shortest_route(origin, destination))


async def _rest_at_capital(journey: ProductionJourney) -> None:
    await _move(journey, "capital_city")
    before = dict(get_player(journey.player_id))
    if before["hp"] == before["max_hp"] and before["mana"] == before["max_mana"]:
        return
    assert before["gold"] >= 12
    await journey.callback("inn", handle_location_buttons)
    await journey.callback("inn_rest", handle_location_buttons)
    after = dict(get_player(journey.player_id))
    assert after["hp"] == after["max_hp"]
    assert after["mana"] == after["max_mana"]
    assert after["gold"] == before["gold"] - 12


def _set_current_hp(player_id: int, hp: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE players SET hp=MIN(max_hp, MAX(1, ?)) WHERE telegram_id=?",
            (hp, player_id),
        )
        conn.commit()
    finally:
        conn.close()


async def _enter(journey: ProductionJourney, encounter_id: str) -> dict:
    before_messages = len(journey.messages)
    query = await journey.callback(f"pve_enter_{encounter_id}", handle_location_buttons)
    assert len(journey.messages) > before_messages, {
        "player_id": journey.player_id,
        "encounter_id": encounter_id,
        "answers": [str(call) for call in query.answer.await_args_list],
    }
    battle = journey.context.user_data.get("battle")
    assert battle and battle["pve_encounter_id"] == encounter_id
    return battle


async def _start_group(
    owner: ProductionJourney,
    joiners: list[ProductionJourney],
    *,
    mob_id: str,
) -> tuple[str, list[ProductionJourney], dict[int, dict]]:
    spawn_id = owner._accelerate_respawn(mob_id)
    return await _open_group(
        owner,
        joiners,
        start_callback=f"fight_spawn_{spawn_id}",
    )


async def _start_mixed_group(
    owner: ProductionJourney,
    joiners: list[ProductionJourney],
    *,
    recipe_id: str,
) -> tuple[str, list[ProductionJourney], dict[int, dict]]:
    recipe = MIXED_ENCOUNTERS[recipe_id]
    for mob_id in {str(unit[0]) for unit in recipe["units"]}:
        owner._accelerate_respawn(mob_id)
    return await _open_group(
        owner,
        joiners,
        start_callback=f"fight_mixed_{recipe_id}",
    )


async def _open_group(
    owner: ProductionJourney,
    joiners: list[ProductionJourney],
    *,
    start_callback: str,
) -> tuple[str, list[ProductionJourney], dict[int, dict]]:
    location_id = str(get_player(owner.player_id)["location_id"])
    assert all(str(get_player(item.player_id)["location_id"]) == location_id for item in joiners)
    mastery_before = {
        item.player_id: get_mastery(
            item.player_id,
            _encounter_family(item.player_id),
        )
        for item in [owner, *joiners]
    }
    await owner.callback(start_callback, handle_combat_buttons)
    enter_callback = next(
        callback for callback in _callbacks(owner.messages[-1][1])
        if callback.startswith("pve_enter_")
    )
    encounter_id = enter_callback.removeprefix("pve_enter_")
    for joiner in joiners:
        await joiner.callback(f"pve_join_{encounter_id}", handle_location_buttons)
    members = [owner, *joiners]
    for member in members:
        await _enter(member, encounter_id)
    state = _encounter_state(encounter_id)
    assert state["side_a_player_ids"][0] == owner.player_id
    assert set(state["side_a_player_ids"]) == {item.player_id for item in members}
    assert state["rules_version"] == "character_builds_combat_identity_v1"
    return encounter_id, members, mastery_before


def _encounter_family(player_id: int) -> str:
    state = _encounter_state_for_player(player_id)
    return str(state["family"])


def _encounter_state_for_player(player_id: int) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT gi.base_item_id
               FROM gear_instances gi
               WHERE gi.telegram_id=? AND gi.equipped_slot='weapon'""",
            (player_id,),
        ).fetchone()
    finally:
        conn.close()
    return {
        "family": (
            str(row["base_item_id"]).removeprefix("field_")
            if row is not None
            else "unarmed"
        )
    }


async def _commit_round(
    encounter_id: str,
    members: list[ProductionJourney],
    actions: dict[int, tuple[str, str | None, str | int | None]],
) -> dict:
    callbacks: list[tuple[ProductionJourney, str]] = []
    for member in members:
        await _enter(member, encounter_id)
        kind, skill_id, target_id = actions.get(
            member.player_id, ("guard", None, None),
        )
        callbacks.append((
            member,
            member._find_combat_action(
                kind=kind,
                skill_id=skill_id,
                target_id=target_id,
            ),
        ))
    latest: dict | None = None
    for member, callback in callbacks:
        latest = member.context.user_data["battle"]
        issued = member._intent_for_callback(callback)
        assert int(issued["turn_revision"]) == int(latest["turn_revision"])
        query = await member.callback(callback, handle_battle_buttons)
        alerts = [
            call for call in query.answer.await_args_list
            if call.kwargs.get("show_alert")
        ]
        assert not alerts, {
            "player_id": member.player_id,
            "callback": callback,
            "alerts": [str(call) for call in alerts],
        }
    return latest or _encounter_state(encounter_id)


def _events(state: dict, *, since: int = 0) -> list[dict]:
    return list(state.get("combat_events_v1") or [])[since:]


def _assert_once_settlement(
    encounter_id: str,
    members: list[ProductionJourney],
    mastery_before: dict[int, dict],
    *,
    expected_unit_count: int = 1,
) -> dict:
    settlement = get_settlement(encounter_id)
    assert settlement and settlement["status"] == "applied"
    planned_recipients = settlement["plan"]["recipients"]
    assert {row["player_id"] for row in planned_recipients} == {
        item.player_id for item in members
    }
    assert all(len(row["units"]) == expected_unit_count for row in planned_recipients)
    assert all(
        len({unit["spawn_instance_id"] for unit in row["units"]}) == expected_unit_count
        for row in planned_recipients
    )
    awards = settlement["result"]["mastery_awards"]
    assert {row["player_id"] for row in awards} == {item.player_id for item in members}
    assert len({row["player_id"] for row in awards}) == len(members)
    planned_awards = {
        row["player_id"]: row["exp"]
        for row in settlement["plan"]["mastery_awards"]
    }
    assert all(row["exp"] == planned_awards[row["player_id"]] for row in awards)
    assert all(0 < row["exp"] <= 80 for row in awards)
    for member in members:
        family = _encounter_family(member.player_id)
        after = get_mastery(member.player_id, family)
        before = mastery_before[member.player_id]
        assert after["level"] >= before["level"]
        assert after["level"] > before["level"] or after["exp"] >= before["exp"]
    return settlement


async def _finish_group(
    encounter_id: str,
    members: list[ProductionJourney],
    mastery_before: dict[int, dict],
    *,
    max_rounds: int = 20,
    expected_unit_count: int = 1,
    sustain: bool = False,
) -> dict:
    for _ in range(max_rounds):
        state = _encounter_state(encounter_id)
        if state.get("mob_dead"):
            break
        living = {
            int(actor["actor_id"])
            for actor in (state.get("participant_states_v1") or {}).values()
            if int(actor.get("hp", 0)) > 0
        }
        actions = {
            member.player_id: ("basic_attack", None, None)
            for member in members
            if member.player_id in living
        }
        if sustain:
            actors = state.get("participant_states_v1") or {}
            living_actors = [
                actor for actor in actors.values()
                if int(actor.get("hp", 0)) > 0
            ]
            lowest = min(
                living_actors,
                key=lambda actor: (
                    int(actor["hp"]) / max(1, int(actor["max_hp"])),
                    int(actor["actor_id"]),
                ),
            )
            for member in members:
                actor = actors.get(str(member.player_id)) or {}
                ranks = actor.get("skill_ranks") or {}
                for skill_id in ("halo_of_dawn", "smite", "sword_rush"):
                    if (
                        skill_id in ranks
                        and cooldown_remaining(actor, skill_id) == 0
                        and int(actor.get("mana", 0)) >= rank_mana_cost(
                            SKILL_SPECS[skill_id], int(ranks[skill_id]),
                        )
                    ):
                        actions[member.player_id] = ("skill", skill_id, None)
                        break
                else:
                    if (
                        cooldown_remaining(actor, "power_strike") == 0
                        and int(actor.get("mana", 0)) >= rank_mana_cost(POWER_STRIKE, 1)
                    ):
                        actions[member.player_id] = (
                            "skill", "power_strike", None,
                        )
                if (
                    "sacred_shield" in ranks
                    and cooldown_remaining(actor, "sacred_shield") == 0
                    and int(actor.get("mana", 0)) >= rank_mana_cost(
                        SKILL_SPECS["sacred_shield"], int(ranks["sacred_shield"]),
                    )
                ):
                    actions[member.player_id] = (
                        "skill", "sacred_shield", lowest["actor_id"],
                    )
                if (
                    "heal" in ranks
                    and int(lowest["hp"]) * 5 <= int(lowest["max_hp"]) * 3
                    and cooldown_remaining(actor, "heal") == 0
                    and int(actor.get("mana", 0)) >= rank_mana_cost(
                        SKILL_SPECS["heal"], int(ranks["heal"]),
                    )
                ):
                    actions[member.player_id] = (
                        "skill", "heal", lowest["actor_id"],
                    )
        await _commit_round(encounter_id, [m for m in members if m.player_id in living], actions)
        if get_settlement(encounter_id):
            break
    else:
        raise AssertionError(_encounter_state(encounter_id))
    return _assert_once_settlement(
        encounter_id,
        members,
        mastery_before,
        expected_unit_count=expected_unit_count,
    )


async def _exercise_protector_healer_group(
    guardian: ProductionJourney,
    protector: ProductionJourney,
    healer: ProductionJourney,
    *,
    mob_id: str,
    joiners: list[ProductionJourney],
    require_full_identity: bool,
) -> dict:
    encounter_id, members, mastery_before = await _start_group(
        guardian, joiners, mob_id=mob_id,
    )
    state = _encounter_state(encounter_id)
    enemy_id = str(state["enemy_states_v1"][0]["unit_id"])
    start_event_count = len(_events(state))

    await _commit_round(encounter_id, members, {
        guardian.player_id: ("skill", "sword_rush", enemy_id),
        protector.player_id: ("skill", "aura_of_resolve", guardian.player_id),
        healer.player_id: ("guard", None, None),
    })
    state = _encounter_state(encounter_id)
    identity_events = _events(state, since=start_event_count)
    assert any(
        event.get("kind") == "intercept"
        and str(event.get("from_id")) == str(guardian.player_id)
        and str(event.get("target_id")) == str(protector.player_id)
        for event in identity_events
    )
    assert any(
        event.get("kind") == "enemy_direct"
        and str(event.get("target_id")) == str(protector.player_id)
        for event in identity_events
    )

    protector_state = state["participant_states_v1"][str(protector.player_id)]
    injured = protector_state if int(protector_state["hp"]) < int(protector_state["max_hp"]) else None
    initial_heal = (
        ("skill", "heal", injured["actor_id"])
        if injured is not None
        else ("guard", None, None)
    )
    await _commit_round(encounter_id, members, {
        guardian.player_id: ("guard", None, None),
        protector.player_id: ("skill", "sacred_shield", guardian.player_id),
        healer.player_id: initial_heal,
    })
    state = _encounter_state(encounter_id)
    identity_events = _events(state, since=start_event_count)
    healed = any(
        event.get("kind") == "heal"
        and int(event.get("amount", 0)) > 0
        for event in identity_events
    )
    barrier_absorbed = any(
        event.get("kind") == "enemy_direct"
        and int(event.get("barrier_absorbed", 0)) > 0
        for event in identity_events
    )

    if require_full_identity:
        cleansed = False
        prevented = False
        covenant_cast = False
        for _ in range(12):
            state = _encounter_state(encounter_id)
            if get_settlement(encounter_id) or state.get("mob_dead"):
                break
            actors = state["participant_states_v1"]
            guardian_state = actors[str(guardian.player_id)]
            protector_state = actors[str(protector.player_id)]
            healer_state = actors[str(healer.player_id)]
            shield_ready = cooldown_remaining(protector_state, "sacred_shield") == 0
            poisoned = next((
                actor for actor in actors.values()
                if any(effect.get("kind") == "poison" for effect in actor.get("effects", []))
            ), None)
            covenant_active = any(
                effect.get("kind") == "life_covenant"
                for effect in guardian_state.get("effects", [])
            )
            resurrection_ready = cooldown_remaining(healer_state, "resurrection") == 0
            cleanse_ready = cooldown_remaining(healer_state, "cleanse") == 0
            heal_ready = cooldown_remaining(healer_state, "heal") == 0
            healer_action: tuple[str, str | None, str | int | None] = ("guard", None, None)
            if int(guardian_state["hp"]) <= 12 and not covenant_active and resurrection_ready:
                healer_action = ("skill", "resurrection", guardian.player_id)
                covenant_cast = True
            elif poisoned is not None and cleanse_ready:
                healer_action = ("skill", "cleanse", poisoned["actor_id"])
            elif (
                int(guardian_state["hp"]) <= 12
                and not covenant_active
                and not resurrection_ready
                and heal_ready
            ):
                healer_action = ("skill", "heal", guardian.player_id)
            elif not healed and heal_ready:
                injured = next((
                    actor for actor in actors.values()
                    if int(actor["hp"]) < int(actor["max_hp"])
                ), None)
                if injured is not None:
                    healer_action = ("skill", "heal", injured["actor_id"])
            protector_action: tuple[str, str | None, str | int | None] = ("guard", None, None)
            guardian_action: tuple[str, str | None, str | int | None] = ("guard", None, None)
            if not barrier_absorbed and shield_ready:
                protector_action = ("skill", "sacred_shield", guardian.player_id)
            before = len(_events(state))
            before_revision = int(state["turn_revision"])
            await _commit_round(encounter_id, members, {
                guardian.player_id: guardian_action,
                protector.player_id: protector_action,
                healer.player_id: healer_action,
            })
            state = _encounter_state(encounter_id)
            assert int(state["turn_revision"]) > before_revision, {
                "before_revision": before_revision,
                "after_revision": state.get("turn_revision"),
                "side": state.get("active_side"),
                "side_state": state.get("side_turn_state"),
                "commits": state.get("ally_commit_status"),
            }
            new_events = _events(state, since=before)
            if healer_action[1] == "cleanse":
                assert any(
                    event.get("kind") == "cleanse" and "poison" in event.get("removed", [])
                    for event in new_events
                )
                cleansed = True
            healed = healed or any(
                event.get("kind") == "heal"
                and int(event.get("amount", 0)) > 0
                for event in new_events
            )
            barrier_absorbed = barrier_absorbed or any(
                event.get("kind") == "enemy_direct"
                and int(event.get("barrier_absorbed", 0)) > 0
                for event in new_events
            )
            if any(event.get("death_prevented") for event in new_events):
                prevented = True
            if healed and barrier_absorbed and cleansed and prevented:
                break
        assert (healed, barrier_absorbed, cleansed, covenant_cast, prevented) == (
            True, True, True, True, True,
        )
    settlement = await _finish_group(encounter_id, members, mastery_before)
    return {
        "encounter_id": encounter_id,
        "join_order": [item.player_id for item in members],
        "mob_id": mob_id,
        "mastery_awards": settlement["result"]["mastery_awards"],
    }


async def _exercise_dawn_enchanter_group(
    dawn: ProductionJourney,
    enchanter: ProductionJourney,
) -> dict:
    encounter_id, members, mastery_before = await _start_group(
        dawn, [enchanter], mob_id="goblin_shaman",
    )
    state = _encounter_state(encounter_id)
    enemy_id = str(state["enemy_states_v1"][0]["unit_id"])
    before = len(_events(state))
    await _commit_round(encounter_id, members, {
        dawn.player_id: ("skill", "judgment_mark", enemy_id),
        enchanter.player_id: ("skill", "insight", dawn.player_id),
    })
    state = _encounter_state(encounter_id)
    first = _events(state, since=before)
    assert any(event.get("skill_id") == "judgment_mark" for event in first)
    assert any(
        event.get("kind") == "mana"
        and str(event.get("target_id")) == str(dawn.player_id)
        and int(event.get("amount", 0)) > 0
        for event in first
    )
    assert any(event.get("kind") == "enemy_ward" for event in first)

    before = len(_events(state))
    await _commit_round(encounter_id, members, {
        dawn.player_id: ("skill", "halo_of_dawn", None),
        enchanter.player_id: ("skill", "dispel_script", enemy_id),
    })
    state = _encounter_state(encounter_id)
    second = _events(state, since=before)
    assert any(event.get("skill_id") == "halo_of_dawn" for event in second)
    assert any(
        event.get("skill_id") == "dispel_script" and "ward" in event.get("removed", [])
        for event in second
    )

    before = len(_events(state))
    await _commit_round(encounter_id, members, {
        dawn.player_id: ("guard", None, None),
        enchanter.player_id: ("skill", "grand_enchantment", None),
    })
    state = _encounter_state(encounter_id)
    third = _events(state, since=before)
    assert len([
        event for event in third
        if event.get("kind") == "mana" and event.get("skill_id") == "grand_enchantment"
    ]) == 2
    assert all(
        any(effect.get("skill_id") == "grand_enchantment" for effect in actor.get("effects", []))
        for actor in state["participant_states_v1"].values()
    )

    settlement = await _finish_group(encounter_id, members, mastery_before)
    return {
        "encounter_id": encounter_id,
        "join_order": [item.player_id for item in members],
        "mob_id": "goblin_shaman",
        "mastery_awards": settlement["result"]["mastery_awards"],
    }


async def _exercise_multi_source_content(
    members: list[ProductionJourney],
) -> dict:
    results: dict[str, dict] = {}
    for recipe_id, location_id in (
        ("westwild_n8_mixed", "westwild_n8"),
        ("ashen_n3c1_mixed", "ashen_n3c1"),
    ):
        for member in members:
            await _rest_at_capital(member)
            await _move(member, location_id)
        with _frozen_combat_clock():
            encounter_id, roster, mastery_before = await _start_mixed_group(
                members[0], members[1:], recipe_id=recipe_id,
            )
            state = _encounter_state(encounter_id)
            expected_units = list(MIXED_ENCOUNTERS[recipe_id]["units"])
            assert [
                (unit["mob_id"], unit["formation_line"])
                for unit in state["enemy_units"]
            ] == expected_units
            settlement = await _finish_group(
                encounter_id,
                roster,
                mastery_before,
                max_rounds=30,
                expected_unit_count=len(expected_units),
                sustain=True,
            )
        assert all(
            int(recipient["exp"]) > 0 and int(recipient["gold"]) >= 0
            for recipient in settlement["result"]["recipients"]
        )
        results[recipe_id] = {
            "encounter_id": encounter_id,
            "source_units": [unit["mob_id"] for unit in settlement["plan"]["enemy_units"]],
        }

    for member in members:
        await _rest_at_capital(member)
        await _move(member, "westwild_n7")
    with _frozen_combat_clock():
        encounter_id, roster, mastery_before = await _start_group(
            members[0], members[1:], mob_id="forest_wolf",
        )
        state = _encounter_state(encounter_id)
        pack_units = list(state.get("enemy_units") or [])
        assert len(pack_units) >= 2
        assert {unit["mob_id"] for unit in pack_units} == {"forest_wolf"}
        settlement = await _finish_group(
            encounter_id,
            roster,
            mastery_before,
            max_rounds=30,
            expected_unit_count=len(pack_units),
            sustain=True,
        )
    results["homogeneous_pack"] = {
        "encounter_id": encounter_id,
        "source_units": [unit["mob_id"] for unit in settlement["plan"]["enemy_units"]],
    }
    return results


async def _run_group_identity_journey() -> dict:
    reset_solo_pve_runtime_store()
    migrate_character_builds_v1()
    trained: dict[str, ProductionJourney] = {}
    for key, family, branch in (
        ("guardian", "sword_1h", "A"),
        ("protector", "holy_rod", "A"),
        ("healer", "holy_staff", "A"),
        ("dawn", "holy_staff", "B"),
        ("enchanter", "tome", "A"),
    ):
        identity = BRANCH_IDENTITIES[family][branch]
        await _run_branch_journey(family, branch, identity)
        index = BRANCH_CASES.index((family, branch, identity))
        trained[key] = ProductionJourney(92000 + index)

    first_party = [trained["guardian"], trained["protector"], trained["healer"]]
    for member in first_party:
        await _rest_at_capital(member)
        await _move(member, "sunscar_n3")
    _set_current_hp(trained["guardian"].player_id, 1)
    protector_row = get_player(trained["protector"].player_id)
    _set_current_hp(
        trained["protector"].player_id,
        int(protector_row["max_hp"]) - 20,
    )
    venom = await _exercise_protector_healer_group(
        trained["guardian"], trained["protector"], trained["healer"],
        mob_id="scorpion",
        joiners=[trained["protector"], trained["healer"]],
        require_full_identity=True,
    )

    for member in first_party:
        await _rest_at_capital(member)
        await _move(member, "westwild_n6")
    reverse = await _exercise_protector_healer_group(
        trained["guardian"], trained["protector"], trained["healer"],
        mob_id="bear",
        joiners=[trained["healer"], trained["protector"]],
        require_full_identity=False,
    )
    assert venom["join_order"][1:] == list(reversed(reverse["join_order"][1:]))

    second_party = [trained["dawn"], trained["enchanter"]]
    for member in second_party:
        await _rest_at_capital(member)
        await _move(member, "westwild_n8")
    caster = await _exercise_dawn_enchanter_group(*second_party)
    content_party = [trained["guardian"], trained["dawn"], trained["healer"]]
    content = await _exercise_multi_source_content(content_party)
    return {
        "venom": venom,
        "reverse": reverse,
        "caster": caster,
        "content": content,
    }


def test_earned_group_identities_survive_real_content_and_reverse_join_order():
    result = asyncio.run(_run_group_identity_journey())
    assert set(result) == {"venom", "reverse", "caster", "content"}
    assert set(result["content"]) == {
        "westwild_n8_mixed", "ashen_n3c1_mixed", "homogeneous_pack",
    }


def test_late_joiners_receive_v1_snapshots_and_can_commit_consecutive_rounds():
    async def journey() -> None:
        migrate_character_builds_v1()
        conn = get_connection()
        conn.execute(
            "UPDATE players SET location_id='westwild_n2' WHERE telegram_id IN (1,777)"
        )
        conn.commit()
        conn.close()
        owner = ProductionJourney(1)
        joiner = ProductionJourney(777)
        spawn_id = owner._accelerate_respawn("forest_boar")
        await owner.callback(f"fight_spawn_{spawn_id}", handle_combat_buttons)
        encounter_id = next(
            callback.removeprefix("pve_enter_")
            for callback in _callbacks(owner.messages[-1][1])
            if callback.startswith("pve_enter_")
        )
        await joiner.callback(f"pve_join_{encounter_id}", handle_location_buttons)
        await _enter(owner, encounter_id)
        await _enter(joiner, encounter_id)
        state = _encounter_state(encounter_id)
        assert set(state["participant_states_v1"]) == {"1", "777"}
        revisions = []
        for _ in range(2):
            await _commit_round(encounter_id, [owner, joiner], {
                1: ("guard", None, None),
                777: ("guard", None, None),
            })
            revisions.append(int(_encounter_state(encounter_id)["turn_revision"]))
        assert revisions[1] > revisions[0]

    asyncio.run(journey())


def test_mixed_v1_group_resolves_enemy_side_and_rotates_units():
    async def journey() -> None:
        reset_solo_pve_runtime_store()
        migrate_character_builds_v1()
        conn = get_connection()
        conn.execute(
            """UPDATE players
               SET location_id='westwild_n8', strength=50, vitality=50,
                   hp=1000, max_hp=1000
               WHERE telegram_id IN (1,777)"""
        )
        conn.commit()
        conn.close()
        owner = ProductionJourney(1)
        joiner = ProductionJourney(777)
        with _frozen_combat_clock():
            encounter_id, members, _ = await _start_mixed_group(
                owner, [joiner], recipe_id="westwild_n8_mixed",
            )
            for _ in range(4):
                await _commit_round(encounter_id, members, {
                    1: ("basic_attack", None, None),
                    777: ("basic_attack", None, None),
                })
                state = _encounter_state(encounter_id)
                if get_settlement(encounter_id):
                    break
        assert get_settlement(encounter_id)
        assert len([
            enemy for enemy in state["enemy_states_v1"]
            if int(enemy["hp"]) <= 0
        ]) == 3

    asyncio.run(journey())
