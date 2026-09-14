"""One shared, caller-connection actor snapshot for every combat surface."""

from __future__ import annotations

from typing import Any

from game.balance import normalize_damage_school
from game.actor_state import finalize_actor_snapshot, healing_power, raw_power_range
from game.build_contract import RULES_VERSION, normalize_family
from game.build_progression import create_family_if_needed, family_skill_ranks
from game.equipment_stats import get_player_effective_stats
from game.gear_instances import (
    get_equipped_gear_instances,
    resolve_equipped_item_ids_with_fallback,
    resolve_gear_instance_item_data,
)
from game.items_data import get_item
from game.targeting import resolve_default_player_formation_line


def _resolved_equipment(player_id: int, conn) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    instances = get_equipped_gear_instances(player_id, conn=conn)
    resolved = {slot: resolve_gear_instance_item_data(row) for slot, row in instances.items()}
    ids = resolve_equipped_item_ids_with_fallback(player_id, conn=conn)
    for slot, item_id in ids.items():
        if slot not in resolved:
            item = get_item(item_id)
            if item:
                resolved[slot] = dict(item)
    return resolved, ids


def _offhand_profile(item: dict[str, Any] | None) -> str:
    item = item or {}
    explicit = str(item.get("offhand_profile") or "")
    if explicit:
        return explicit
    item_id = str(item.get("item_id") or "")
    if "shield" in item_id:
        return "shield"
    return str(item.get("slot_identity") or "none") if item else "none"


def build_actor_snapshot(
    player_id: int,
    *,
    conn,
    effects: list[dict[str, Any]] | None = None,
    cooldowns: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Resolve the exact equipped instances, ranks and effective attributes.

    ``conn`` is required so encounter creation, PvP and UI preview can share one
    transaction and cannot observe mismatched gear/build revisions.
    """
    row = conn.execute("SELECT * FROM players WHERE telegram_id=?", (player_id,)).fetchone()
    if not row:
        raise ValueError("player_not_found")
    player = dict(row)
    resolved, item_ids = _resolved_equipment(player_id, conn)
    weapon = dict(resolved.get("weapon") or {})
    family = normalize_family(weapon.get("weapon_profile") or weapon.get("item_id") or "unarmed")
    if family == "unarmed":
        mastery = {"level": 1, "exp": 0, "skill_points": 0}
        ranks: dict[str, int] = {}
    else:
        mastery = create_family_if_needed(player_id, family, conn=conn)
        ranks = family_skill_ranks(player_id, family, conn=conn)
    effective = get_player_effective_stats(player_id, player, conn=conn)
    offhand = dict(resolved.get("offhand") or {})
    offhand_profile = _offhand_profile(offhand)
    weapon_type = str(weapon.get("weapon_type") or "melee")
    school = normalize_damage_school(
        weapon.get("damage_school"), weapon_profile=family, weapon_type=weapon_type,
    )
    weapon_min = int(weapon.get("damage_min", 5) or 5) if weapon else 5
    weapon_max = max(weapon_min, int(weapon.get("damage_max", 5) or 5)) if weapon else 5
    stats = {key: int(effective[key]) for key in (
        "strength", "agility", "intuition", "vitality", "wisdom", "luck",
    )}
    physical_defense = int(effective.get("effective_physical_defense", 0))
    magic_defense = int(effective.get("effective_magic_defense", 0))
    accuracy = 100 + 2 * stats["agility"] + stats["intuition"] + int(effective.get("accuracy_bonus", 0))
    evasion = 100 + 2 * stats["agility"] + stats["luck"] + int(effective.get("evasion_bonus", 0))
    block = max(0.0, min(40.0, float(effective.get("block_chance_bonus", 0))))
    max_hp = int(effective["max_hp"])
    max_mana = int(effective["max_mana"])
    if cooldowns is None:
        cooldowns = {
            str(cd["skill_id"]): int(cd["turns_left"])
            for cd in conn.execute('''SELECT skill_id, turns_left FROM skill_cooldowns
                WHERE telegram_id=? AND turns_left>0''', (player_id,))
        }
    return finalize_actor_snapshot({
        "rules_version": RULES_VERSION,
        "actor_id": int(player_id),
        "name": str(player.get("name") or player_id),
        "level": int(player.get("level", 1)),
        "build_revision": int(player.get("build_revision", 0)),
        "gear_revision": int(player.get("gear_revision", 0)),
        "family": family,
        "mastery_level": int(mastery["level"]),
        "mastery_exp": int(mastery["exp"]),
        "skill_points": int(mastery["skill_points"]),
        "skill_ranks": ranks,
        "cooldowns": dict(cooldowns),
        "base_attributes": {key: int(player[key]) for key in stats},
        "attributes": stats,
        **stats,
        "hp": min(int(player.get("hp", max_hp)), max_hp),
        "max_hp": max_hp,
        "mana": min(int(player.get("mana", max_mana)), max_mana),
        "max_mana": max_mana,
        "weapon_instance_id": weapon.get("instance_id"),
        "weapon_item_id": weapon.get("item_id") or item_ids.get("weapon"),
        "weapon_name": str(weapon.get("name") or "Unarmed"),
        "weapon_min": weapon_min,
        "weapon_max": weapon_max,
        "weapon_type": weapon_type,
        "damage_school": school,
        "offhand_profile": offhand_profile,
        "formation": resolve_default_player_formation_line(
            weapon_profile=family, offhand_profile=offhand_profile,
        ),
        "physical_defense": physical_defense,
        "magic_defense": magic_defense,
        "accuracy": accuracy,
        "evasion": evasion,
        "block_chance": block,
        "magic_power": max(0, int(effective.get("magic_power_bonus", 0))),
        "healing_power": max(0, int(effective.get("healing_power_bonus", 0))),
        "equipment": resolved,
        "effects": list(effects or []),
        "setups": [],
        "opportunity_index": 0,
        "manual_contribution": False,
        "death_prevention_used": False,
    })


def snapshot_cache_key(snapshot: dict[str, Any]) -> tuple[int, int, int]:
    return (
        int(snapshot["actor_id"]),
        int(snapshot.get("build_revision", 0)),
        int(snapshot.get("gear_revision", 0)),
    )
