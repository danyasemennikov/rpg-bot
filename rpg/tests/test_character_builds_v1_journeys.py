"""Ordinary earned Character Builds V1 journeys through production handlers.

The only accelerated rule is the world respawn clock.  Registration, the
45-gold vendor purchase, instance equip, skill receipts, combat orders, combat
resolution, rewards, and mastery all use their production authorities.
"""

from __future__ import annotations

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from database import get_connection, get_player
from game.build_contract import (
    BRANCH_IDENTITIES,
    SKILL_SPECS,
    SKILL_TREES,
)
from game.build_progression import build_migration_audit, migrate_character_builds_v1
from game.field_catalog import FIELD_ITEMS
from game.gear_instances import get_equipped_gear_instances
from game.pve_live import ensure_location_pve_spawn_instances, reset_solo_pve_runtime_store
from game.pve_reward_settlement import get_settlement
from game.weapon_mastery import get_mastery
from handlers.battle import handle_battle_buttons
from handlers.build import build_skills_command, handle_build_buttons
from handlers.inventory import build_item_detail, handle_inventory_buttons
from handlers.location import handle_combat_buttons, handle_location_buttons
from handlers.start import handle_name_input, handle_stat_buttons, start_command


BRANCH_CASES = tuple(
    (family, branch, BRANCH_IDENTITIES[family][branch])
    for family in SKILL_TREES
    for branch in ("A", "B")
)
DEEP_IDENTITIES = {"guardian", "venom", "healer", "synthesis"}


def _rows(sql: str, args: tuple = ()) -> list[dict]:
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute(sql, args)]
    finally:
        conn.close()


def _callbacks(markup) -> list[str]:
    if not markup or not hasattr(markup, "inline_keyboard"):
        return []
    return [
        str(button.callback_data)
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]


def _demonstrates_defining_skill_effect(action: dict, skill_id: str) -> bool:
    spec = SKILL_SPECS[skill_id]
    events = list(action['events'])
    actor_effects = list(action['actor_after'].get('effects') or [])
    enemy_effects = [
        effect for enemy in action['enemies_after']
        for effect in (enemy.get('effects') or [])
    ]
    if spec.kind in {'damage', 'poison', 'hostile_effect', 'dispel'}:
        direct = next(
            event for event in events
            if event.get('kind') == 'direct' and event.get('skill_id') == skill_id
        )
        if direct.get('hit') is not True:
            return False
        if spec.kind in {'damage', 'poison'}:
            assert int(direct.get('hp_removed', 0)) > 0, (skill_id, direct)
        if spec.kind == 'hostile_effect':
            assert any(effect.get('skill_id') == skill_id for effect in enemy_effects)
        return True
    matching_effect = any(
        effect.get('skill_id') == skill_id
        for effect in [*actor_effects, *enemy_effects]
    )
    semantic_events = {
        'heal': {'heal'}, 'hot': {'heal', 'hot'}, 'mana': {'mana'},
        'rage': {'hp_cost'}, 'cleanse': {'cleanse'}, 'dispel': {'direct'},
    }.get(spec.kind, set())
    return matching_effect or any(event.get('kind') in semantic_events for event in events)


def _assert_defining_skill_effect(action: dict, skill_id: str, player_id: int) -> None:
    assert _demonstrates_defining_skill_effect(action, skill_id), (
        skill_id, player_id, action['actor_after'], action['enemies_after'], action['events'],
    )


class ProductionJourney:
    """Small fake Telegram transport around real command/callback handlers."""

    def __init__(self, player_id: int, *, lang: str = "en"):
        self.player_id = int(player_id)
        self.lang = lang
        self.user = SimpleNamespace(
            id=self.player_id,
            username=f"journey_{self.player_id}",
            language_code=lang,
        )
        self.message_id = 0
        self.messages: list[tuple[str, object | None]] = []
        self.recovery_stops: list[dict] = []
        self.user_data: dict = {}
        self.bot = SimpleNamespace(send_message=AsyncMock(side_effect=self._output))
        self.context = SimpleNamespace(user_data=self.user_data, bot=self.bot)
        self.context.application = SimpleNamespace(
            user_data={self.player_id: self.user_data},
            create_task=lambda coroutine: coroutine.close(),
            bot=self.bot,
        )

    async def _output(self, text: str | None = None, **kwargs):
        rendered = str(text or "")
        assert len(rendered) <= 4096
        markup = kwargs.get("reply_markup")
        assert all(len(value.encode("utf-8")) <= 64 for value in _callbacks(markup))
        self.messages.append((rendered, markup))
        return SimpleNamespace(message_id=self.message_id)

    async def callback(self, data: str, handler):
        self.message_id += 1
        message = SimpleNamespace(
            message_id=self.message_id,
            chat_id=self.player_id,
            reply_text=AsyncMock(side_effect=self._output),
        )
        query = SimpleNamespace(
            data=data,
            from_user=self.user,
            answer=AsyncMock(),
            message=message,
            edit_message_text=AsyncMock(side_effect=self._output),
        )
        update = SimpleNamespace(
            callback_query=query,
            effective_user=self.user,
            effective_message=message,
        )
        await handler(update, self.context)
        return query

    async def text(self, value: str, handler):
        self.message_id += 1
        message = SimpleNamespace(
            text=value,
            message_id=self.message_id,
            chat_id=self.player_id,
            reply_text=AsyncMock(side_effect=self._output),
        )
        update = SimpleNamespace(
            message=message,
            callback_query=None,
            effective_user=self.user,
            effective_message=message,
        )
        await handler(update, self.context)

    async def register(self, *, primary: str, name: str) -> None:
        await self.text("/start", start_command)
        await self.text(name, handle_name_input)
        for stat in [primary] * 2 + ["vitality"] * 4:
            await self.callback(f"stat_plus_{stat}", handle_stat_buttons)
        await self.callback("stat_confirm", handle_stat_buttons)
        player = dict(get_player(self.player_id))
        assert player[primary] == 3
        assert sum(player[key] for key in (
            "strength", "agility", "intuition", "vitality", "wisdom", "luck"
        )) == 12
        assert player["gold"] == 50

    async def buy_and_equip_field_weapon(self, family: str) -> dict:
        item_id = f"field_{family}"
        await self.callback("shop", handle_location_buttons)
        await self.callback(f"shop_preview_{item_id}|0", handle_location_buttons)
        buy = next(
            value for value in _callbacks(self.messages[-1][1])
            if value.startswith(f"shop_buy_{item_id}|")
        )
        await self.callback(buy, handle_location_buttons)
        instance = _rows(
            "SELECT * FROM gear_instances WHERE telegram_id=? AND base_item_id=?",
            (self.player_id, item_id),
        )[0]
        metadata = json.loads(instance["source_metadata_json"])
        assert metadata["source"] == "vendor"
        assert metadata["location_id"] == "capital_city"
        assert instance["rarity"] == "common" and instance["item_tier"] == 1

        text, markup = build_item_detail(
            self.player_id, f"g{instance['id']}", "weapon", self.lang,
        )
        await self._output(text, reply_markup=markup)
        equip = next(
            value for value in _callbacks(markup) if value.startswith("inv_gequip_")
        )
        await self.callback(equip, handle_inventory_buttons)
        equipped = get_equipped_gear_instances(self.player_id)
        assert equipped["weapon"]["id"] == instance["id"]
        assert dict(get_player(self.player_id))["gold"] == 5
        return instance

    async def learn(self, family: str, skill_id: str) -> dict:
        await self.text("/skills", build_skills_command)
        await self.callback(f"bv_family_{family}", handle_build_buttons)
        await self.callback(f"bv_skill_{skill_id}", handle_build_buttons)
        assert f"bv_buy_{skill_id}" in _callbacks(self.messages[-1][1])
        await self.callback(f"bv_buy_{skill_id}", handle_build_buttons)
        apply_callback = next(
            value for value in _callbacks(self.messages[-1][1])
            if value.startswith("bv_apply_")
        )
        await self.callback(apply_callback, handle_build_buttons)
        token = apply_callback.removeprefix("bv_apply_")
        receipt = _rows(
            """SELECT * FROM build_mutation_receipts
               WHERE player_id=? AND kind='learn' AND token=?""",
            (self.player_id, token),
        )[0]
        result = json.loads(receipt["result_json"])
        assert result["success"] is True and result["skill_id"] == skill_id
        return {"token": receipt["token"], **result}

    async def travel(self, *destinations: str) -> None:
        for destination in destinations:
            with patch("handlers.location.asyncio.sleep", new=AsyncMock()):
                await self.callback(f"goto_{destination}", handle_location_buttons)
            assert get_player(self.player_id)["location_id"] == destination

    async def recover_if_needed(self) -> None:
        player = dict(get_player(self.player_id))
        if int(player["hp"]) * 10 > int(player["max_hp"]) * 7:
            return
        origin = str(player["location_id"])
        if origin == "westwild_n2":
            await self.travel("westwild_n1", "capital_city")
        elif origin == "westwild_n1":
            await self.travel("capital_city")
        else:
            raise AssertionError(("unsupported recovery origin", origin))
        before = dict(get_player(self.player_id))
        assert before["gold"] >= 12
        await self.callback("inn", handle_location_buttons)
        await self.callback("inn_rest", handle_location_buttons)
        after = dict(get_player(self.player_id))
        assert after["hp"] == after["max_hp"]
        assert after["mana"] == after["max_mana"]
        assert after["gold"] == before["gold"] - 12
        self.recovery_stops.append({
            "before_hp": before["hp"],
            "after_hp": after["hp"],
            "gold_cost": 12,
        })
        if origin == "westwild_n2":
            await self.travel("westwild_n1", "westwild_n2")
        else:
            await self.travel("westwild_n1")

    def _accelerate_respawn(self, mob_id: str) -> str:
        location_id = str(get_player(self.player_id)["location_id"])
        ensure_location_pve_spawn_instances(location_id=location_id)
        conn = get_connection()
        try:
            conn.execute(
                """UPDATE pve_spawn_instances
                   SET respawn_available_at='2000-01-01 00:00:00'
                   WHERE location_id=? AND mob_id=? AND state='respawning'""",
                (location_id, mob_id),
            )
            conn.commit()
        finally:
            conn.close()
        ensure_location_pve_spawn_instances(location_id=location_id)
        rows = _rows(
            """SELECT spawn_instance_id FROM pve_spawn_instances
               WHERE location_id=? AND mob_id=? AND spawn_profile='normal'
                 AND state='idle' ORDER BY spawn_instance_id LIMIT 1""",
            (location_id, mob_id),
        )
        assert rows, (location_id, mob_id)
        return str(rows[0]["spawn_instance_id"])

    def _intent_for_callback(self, callback: str) -> dict:
        token = callback.removeprefix("battle_v1_")
        rows = _rows(
            """SELECT payload FROM player_ui_actions
               WHERE player_id=? AND kind='combat_v1' AND token=?""",
            (self.player_id, token),
        )
        assert rows, callback
        return json.loads(rows[0]["payload"])

    def _find_combat_action(
        self,
        *,
        kind: str,
        skill_id: str | None = None,
        target_id: str | int | None = None,
    ) -> str:
        for callback in _callbacks(self.messages[-1][1]):
            if not callback.startswith("battle_v1_"):
                continue
            action = self._intent_for_callback(callback).get("action") or {}
            selected_target = (action.get("target_info") or {}).get("id")
            target_matches = target_id is None or str(selected_target) == str(target_id)
            if (
                action.get("kind") == kind
                and action.get("skill_id") == skill_id
                and target_matches
            ):
                return callback
        raise AssertionError((kind, skill_id, target_id, _callbacks(self.messages[-1][1])))

    async def fight(self, mob_id: str, *, opening: tuple[tuple[str, str | None], ...] = ()) -> dict:
        spawn_id = self._accelerate_respawn(mob_id)
        await self.callback(f"fight_spawn_{spawn_id}", handle_combat_buttons)
        enter = next(
            value for value in _callbacks(self.messages[-1][1])
            if value.startswith("pve_enter_")
        )
        encounter_id = enter.removeprefix("pve_enter_")
        await self.callback(enter, handle_location_buttons)
        assert self.context.user_data["battle"]["rules_version"] == "character_builds_combat_identity_v1"
        battle_state = self.context.user_data["battle"]
        selected_actions: list[dict] = []

        for turn in range(40):
            if "battle" not in self.context.user_data:
                break
            if turn < len(opening):
                kind, skill_id = opening[turn]
            else:
                kind, skill_id = "basic_attack", None
            callback = self._find_combat_action(kind=kind, skill_id=skill_id)
            payload = self._intent_for_callback(callback)["action"]
            before_events = len(battle_state.get("combat_events_v1", []))
            await self.callback(callback, handle_battle_buttons)
            current_battle = self.context.user_data.get("battle", battle_state)
            selected_actions.append({
                "kind": payload["kind"],
                "skill_id": payload.get("skill_id"),
                "events": battle_state.get("combat_events_v1", [])[before_events:],
                "actor_after": copy.deepcopy(
                    (current_battle.get("participant_states_v1") or {}).get(str(self.player_id), {})
                ),
                "enemies_after": copy.deepcopy(current_battle.get("enemy_states_v1") or []),
            })
        else:
            raise AssertionError((mob_id, battle_state))

        assert not battle_state.get("player_dead"), (mob_id, battle_state)
        settlement = get_settlement(encounter_id)
        assert settlement and settlement["status"] == "applied"
        award = next(
            row for row in settlement["result"]["mastery_awards"]
            if row["player_id"] == self.player_id
        )
        assert award["exp"] == 20
        return {
            "encounter_id": encounter_id,
            "spawn_instance_id": spawn_id,
            "mob_id": mob_id,
            "actions": selected_actions,
            "settlement": settlement,
        }

    async def earn_mastery(self, family: str, target_level: int) -> list[dict]:
        encounters = []
        while get_mastery(self.player_id, family)["level"] < target_level:
            await self.recover_if_needed()
            encounters.append(await self.fight("westwild_rabbit"))
        mastery = get_mastery(self.player_id, family)
        assert mastery["level"] == target_level and mastery["exp"] == 0
        return encounters


async def _run_branch_journey(family: str, branch: str, identity: str) -> dict:
    index = BRANCH_CASES.index((family, branch, identity))
    player_id = 92000 + index
    item_id = f"field_{family}"
    primary = next(
        key.removeprefix("req_")
        for key, value in FIELD_ITEMS[item_id].items()
        if key.startswith("req_") and key != "req_level" and int(value or 0) > 0
    )
    journey = ProductionJourney(player_id)
    await journey.register(primary=primary, name=f"V1 {identity.title()}"[:20])
    instance = await journey.buy_and_equip_field_weapon(family)

    branch_skills = SKILL_TREES[family][branch]
    entry = branch_skills[0]
    entry_receipt = await journey.learn(family, entry)
    await journey.travel("westwild_n1", "westwild_n2")
    start = await journey.fight(
        "forest_boar",
        opening=(("skill", entry), ("basic_attack", None)),
    )
    assert start["actions"][0]["skill_id"] == entry
    assert start["actions"][1]["kind"] == "basic_attack"

    earned = [start]
    entry_action = start["actions"][0]
    entry_attempts = 1
    while not _demonstrates_defining_skill_effect(entry_action, entry):
        assert entry_attempts < 8, (entry, entry_action)
        proof_fight = await journey.fight("forest_boar", opening=(("skill", entry),))
        earned.append(proof_fight)
        entry_action = proof_fight["actions"][0]
        entry_attempts += 1
    _assert_defining_skill_effect(entry_action, entry, player_id)
    earned.extend(await journey.earn_mastery(family, 8))
    assert len(earned) == 28
    await journey.travel("westwild_n1", "capital_city")

    m8_receipts = []
    for skill_id in branch_skills[:4]:
        current = _rows(
            "SELECT level FROM player_skills WHERE telegram_id=? AND skill_id=?",
            (player_id, skill_id),
        )
        for _ in range(2 - (int(current[0]["level"]) if current else 0)):
            m8_receipts.append(await journey.learn(family, skill_id))
    m8_receipts.append(await journey.learn(family, branch_skills[4]))
    ranks = {
        row["skill_id"]: row["level"]
        for row in _rows(
            "SELECT skill_id,level FROM player_skills WHERE telegram_id=?",
            (player_id,),
        )
        if row["skill_id"] in branch_skills
    }
    assert [ranks[skill_id] for skill_id in branch_skills] == [2, 2, 2, 2, 1]

    await journey.travel("westwild_n1", "westwild_n2")
    capstone = branch_skills[4]
    if SKILL_SPECS[capstone].passive:
        capstone_fight = await journey.fight(
            "forest_boar",
            opening=(
                ("skill", "defensive_stance"),
                *(("guard", None),) * 6,
            ),
        )
        assert any(
            event.get("kind") == "retaliation" and event.get("trigger") == capstone
            for action in capstone_fight["actions"]
            for event in action["events"]
        )
    else:
        capstone_fight = await journey.fight("forest_boar", opening=(("skill", capstone),))
        earned.append(capstone_fight)
        capstone_action = capstone_fight["actions"][0]
        capstone_attempts = 1
        while not _demonstrates_defining_skill_effect(capstone_action, capstone):
            assert capstone_attempts < 8, (capstone, capstone_action)
            capstone_fight = await journey.fight("forest_boar", opening=(("skill", capstone),))
            earned.append(capstone_fight)
            capstone_action = capstone_fight["actions"][0]
            capstone_attempts += 1
        assert capstone_action["skill_id"] == capstone
        _assert_defining_skill_effect(capstone_action, capstone, player_id)
    if capstone_fight not in earned:
        earned.append(capstone_fight)

    deep_receipts = []
    if identity in DEEP_IDENTITIES:
        earned.extend(await journey.earn_mastery(family, 14))
        await journey.travel("westwild_n1", "capital_city")
        for skill_id in branch_skills:
            current = _rows(
                "SELECT level FROM player_skills WHERE telegram_id=? AND skill_id=?",
                (player_id, skill_id),
            )[0]["level"]
            for _ in range(3 - int(current)):
                deep_receipts.append(await journey.learn(family, skill_id))
        ranks = {
            row["skill_id"]: row["level"]
            for row in _rows(
                "SELECT skill_id,level FROM player_skills WHERE telegram_id=?",
                (player_id,),
            )
            if row["skill_id"] in branch_skills
        }
        assert [ranks[skill_id] for skill_id in branch_skills] == [3, 3, 3, 3, 3]
        assert get_mastery(player_id, family)["skill_points"] == 0

    mastery = get_mastery(player_id, family)
    final_player = dict(get_player(player_id))
    assert final_player["attribute_budget"] == 6 + 3 * (final_player["level"] - 1)
    assert build_migration_audit()["attribute_invariant_failures"] == []
    return {
        "player_id": player_id,
        "family": family,
        "branch": branch,
        "identity": identity,
        "starting_attributes": {
            key: int(get_player(player_id)[key])
            for key in ("strength", "agility", "intuition", "vitality", "wisdom", "luck")
        },
        "vendor": {
            "item_id": item_id,
            "price": 45,
            "instance_id": instance["id"],
            "source_metadata": json.loads(instance["source_metadata_json"]),
        },
        "entry": entry_receipt,
        "entry_encounter_id": start["encounter_id"],
        "earned_encounters": len(earned),
        "mastery": {
            "level": mastery["level"],
            "exp": mastery["exp"],
            "skill_points": mastery["skill_points"],
        },
        "character_progression": {
            "level": final_player["level"],
            "exp": final_player["exp"],
            "gold": final_player["gold"],
            "attribute_budget": final_player["attribute_budget"],
            "unspent_stat_points": final_player["stat_points"],
        },
        "m8_receipts": [row["token"] for row in m8_receipts],
        "deep_receipts": [row["token"] for row in deep_receipts],
        "capstone": capstone,
        "capstone_encounter_id": capstone_fight["encounter_id"],
        "recovery_stops": list(journey.recovery_stops),
    }


@pytest.mark.parametrize("family,branch,identity", BRANCH_CASES, ids=lambda value: str(value))
def test_twenty_ordinary_branch_loops_reach_m8_and_named_four_reach_m14(
    family: str, branch: str, identity: str,
):
    reset_solo_pve_runtime_store()
    migrate_character_builds_v1()
    result = asyncio.run(_run_branch_journey(family, branch, identity))
    assert result["mastery"]["level"] == (14 if identity in DEEP_IDENTITIES else 8)
    assert result["earned_encounters"] == (91 if identity in DEEP_IDENTITIES else 29)
