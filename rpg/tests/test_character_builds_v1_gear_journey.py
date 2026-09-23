"""Earned gear provenance through production reward, UI and combat snapshots."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from database import get_connection, get_player
from game.build_progression import migrate_character_builds_v1
from game.equipment_stats import get_player_effective_stats
from game.gear_instances import (
    get_equipped_gear_instances,
    resolve_gear_instance_item_data,
)
from game.gear_ui import compare_instance_to_slot
from game.pve_live import reset_solo_pve_runtime_store
from game.pve_reward_settlement import get_settlement
from game.pvp_live import (
    advance_engagement_to_live_battle_if_ready,
    create_live_engagement,
)
from handlers.inventory import build_item_detail, handle_inventory_buttons
from tests.test_character_builds_v1_group_journeys import (
    _encounter_state,
    _finish_group,
    _frozen_combat_clock,
    _move,
    _start_group,
)
from tests.test_character_builds_v1_journeys import ProductionJourney, _callbacks
from tests.test_playable_alpha_v1 import PLAYER, Journey, run_chapter


GEAR_REWARD_SEED = "gear-v1-361030"
COMPANION_ID = 93051


def _rows(sql: str, args=()) -> list[dict]:
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def _resolved_instance(instance_id: int) -> dict:
    row = _rows("SELECT * FROM gear_instances WHERE id=?", (instance_id,))[0]
    return resolve_gear_instance_item_data(row)


def _assert_upgraded_snapshot(snapshot: dict, *, instance_id: int, resolved: dict) -> None:
    assert snapshot["weapon_instance_id"] == instance_id
    assert snapshot["weapon_item_id"] == "field_sword_1h"
    assert snapshot["weapon_min"] == resolved["damage_min"]
    assert snapshot["weapon_max"] == resolved["damage_max"]
    assert snapshot["equipment"]["weapon"]["enhance_level"] == 1
    assert snapshot["equipment"]["weapon"]["secondary_rolls"] == [
        {"stat": "vitality", "value": 2},
    ]


async def _run_earned_gear_journey() -> dict:
    reset_solo_pve_runtime_store()
    migrate_character_builds_v1()

    # The existing first-chapter journey earns its gold, materials, levels and
    # common T1 sword exclusively through production actions.
    await run_chapter("en", build_case=("sword_1h", "A"))
    guardian = ProductionJourney(PLAYER, lang="en")
    await _move(guardian, "westwild_n1")

    baseline = get_equipped_gear_instances(PLAYER)["weapon"]
    assert baseline["base_item_id"] == "field_sword_1h"
    assert baseline["rarity"] == "common" and baseline["item_tier"] == 1
    baseline_effective = get_player_effective_stats(PLAYER, dict(get_player(PLAYER)))

    # These three values are selected before combat: encounter identity,
    # combat RNG seed and reward seed. The last seed follows the unmodified
    # field-loot policy to an uncommon sword and an enhancement shard.
    seeded_ids = [
        SimpleNamespace(hex="gearjourney001000000000000000000000"),
        SimpleNamespace(hex="gearcombat001000000000000000000000"),
        SimpleNamespace(hex=GEAR_REWARD_SEED),
    ]
    reward_journey = Journey("en")
    with patch("game.pve_live.uuid.uuid4", side_effect=seeded_ids):
        reward_encounter_id = await reward_journey.fight("westwild_rabbit")

    settlement = get_settlement(reward_encounter_id)
    assert settlement and settlement["plan"]["reward_seed"] == GEAR_REWARD_SEED
    recipient = next(
        row for row in settlement["result"]["recipients"]
        if row["player_id"] == PLAYER
    )
    earned = next(
        row for row in recipient["gear"]
        if row["base_item_id"] == "field_sword_1h"
    )
    assert earned["rarity"] == "uncommon" and earned["item_tier"] == 1
    assert earned["secondary_rolls"] == [{"stat": "vitality", "value": 2}]
    assert "enhance_shard" in recipient["stackable_items"]
    instance_id = int(earned["instance_id"])
    instance = _rows("SELECT * FROM gear_instances WHERE id=?", (instance_id,))[0]
    assert instance["source_settlement_id"] == reward_encounter_id
    provenance = json.loads(instance["source_metadata_json"])
    assert provenance["encounter_id"] == reward_encounter_id
    assert provenance["mob_id"] == "westwild_rabbit"

    detail, markup = build_item_detail(PLAYER, f"g{instance_id}", "weapon", "en")
    assert "Uncommon" in detail and "Vitality +2" in detail
    comparison = compare_instance_to_slot(PLAYER, instance_id, "weapon")
    assert comparison["deltas"]["vitality"] == 2
    assert comparison["deltas"]["max_hp"] == 36
    equip_callback = next(
        value for value in _callbacks(markup) if value.startswith("inv_gequip_")
    )
    await guardian.callback(equip_callback, handle_inventory_buttons)
    equipped_effective = get_player_effective_stats(PLAYER, dict(get_player(PLAYER)))
    assert equipped_effective["vitality"] == baseline_effective["vitality"] + 2
    assert equipped_effective["max_hp"] == baseline_effective["max_hp"] + 36

    before_upgrade = _resolved_instance(instance_id)
    before_gold = int(get_player(PLAYER)["gold"])
    before_shards = _rows(
        "SELECT quantity FROM inventory WHERE telegram_id=? AND item_id='enhance_shard'",
        (PLAYER,),
    )[0]["quantity"]
    assert before_gold >= 100 and before_shards >= 1
    _, enhance_markup = build_item_detail(PLAYER, f"g{instance_id}", "weapon", "en")
    enhance_callback = next(
        value for value in _callbacks(enhance_markup) if value.startswith("inv_genh_")
    )
    with patch("game.gear_instances.random.random", return_value=0.0):
        response = await guardian.callback(enhance_callback, handle_inventory_buttons)
    assert not [
        call for call in response.answer.await_args_list
        if call.kwargs.get("show_alert") and "Enhanced" not in str(call)
    ]
    after_upgrade = _resolved_instance(instance_id)
    assert after_upgrade["enhance_level"] == 1
    assert after_upgrade["damage_max"] > before_upgrade["damage_max"]
    assert get_player(PLAYER)["gold"] == before_gold - 100
    after_shards = _rows(
        "SELECT COALESCE(SUM(quantity),0) AS quantity FROM inventory "
        "WHERE telegram_id=? AND item_id='enhance_shard'",
        (PLAYER,),
    )[0]["quantity"]
    assert after_shards == before_shards - 1

    companion = ProductionJourney(COMPANION_ID, lang="en")
    await companion.register(primary="strength", name="Gear Witness")
    await companion.buy_and_equip_field_weapon("sword_1h")
    await companion.travel("westwild_n1")

    with _frozen_combat_clock():
        owner_encounter, owner_roster, owner_mastery = await _start_group(
            guardian, [companion], mob_id="westwild_rabbit",
        )
        owner_snapshot = _encounter_state(owner_encounter)["participant_states_v1"][str(PLAYER)]
        _assert_upgraded_snapshot(
            owner_snapshot, instance_id=instance_id, resolved=after_upgrade,
        )
        await _finish_group(owner_encounter, owner_roster, owner_mastery)

    with _frozen_combat_clock():
        joiner_encounter, joiner_roster, joiner_mastery = await _start_group(
            companion, [guardian], mob_id="westwild_rabbit",
        )
        joiner_snapshot = _encounter_state(joiner_encounter)["participant_states_v1"][str(PLAYER)]
        _assert_upgraded_snapshot(
            joiner_snapshot, instance_id=instance_id, resolved=after_upgrade,
        )
        await _finish_group(joiner_encounter, joiner_roster, joiner_mastery)

    attacker = dict(get_player(PLAYER))
    defender = dict(get_player(COMPANION_ID))
    engagement_id = create_live_engagement(
        attacker=attacker,
        defender=defender,
        location_id="westwild_n1",
        illegal_aggression=False,
    )
    engagement = _rows(
        "SELECT * FROM pvp_engagements WHERE id=?", (engagement_id,),
    )[0]
    ready_at = datetime.fromisoformat(str(engagement["engagement_ready_at"]))
    state, payload = advance_engagement_to_live_battle_if_ready(
        engagement,
        now=ready_at + timedelta(seconds=1),
    )
    assert state == "converted_to_battle"
    pvp_snapshot = payload["battle"]["participants_v1"][str(PLAYER)]
    _assert_upgraded_snapshot(
        pvp_snapshot, instance_id=instance_id, resolved=after_upgrade,
    )
    return {
        "reward_encounter_id": reward_encounter_id,
        "owner_encounter_id": owner_encounter,
        "joiner_encounter_id": joiner_encounter,
        "pvp_engagement_id": engagement_id,
        "instance_id": instance_id,
        "resolved_damage": [after_upgrade["damage_min"], after_upgrade["damage_max"]],
    }


def test_earned_secondary_upgrade_reaches_owner_joiner_and_pvp_snapshots():
    result = asyncio.run(_run_earned_gear_journey())
    assert result["reward_encounter_id"]
    assert result["owner_encounter_id"] != result["joiner_encounter_id"]
    assert result["pvp_engagement_id"] > 0
    assert result["resolved_damage"][1] > result["resolved_damage"][0]
