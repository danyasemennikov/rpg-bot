"""Explicit V1 enemy defense, formation and deterministic behavior authority."""

from __future__ import annotations

from typing import Any

from game.build_contract import RULES_VERSION


ARMORED_IDS = frozenset({
    "forest_boar", "rock_lizard", "stone_beetle", "mountain_stone_golem",
    "stone_golem", "skeleton_guard", "temple_guardian", "earth_elemental",
    "shore_turtle",
})
BRUTE_IDS = frozenset({
    "bear", "troll", "ice_troll", "troll_chief", "desert_elephant",
    "mountain_stone_golem", "temple_guardian",
})
EVASIVE_IDS = frozenset({
    "crow", "cave_bat", "goblin_scout", "ghost", "scavenger", "snake",
    "scorpion", "air_elemental",
})
CASTER_IDS = frozenset({
    "goblin_shaman", "skeleton_mage", "skeleton_priest", "swamp_witch",
    "old_witch", "fire_elemental",
})
VENOM_IDS = frozenset({
    "forest_spider", "swamp_spider", "water_snake", "scorpion", "snake",
    "toxic_slime",
})
LEECH_IDS = frozenset({"leech", "giant_leech"})

MIXED_ENCOUNTERS = {
    "westwild_n8_mixed": {
        "location_id": "westwild_n8",
        "label": {"en": "Bear Hunting Party", "ru": "Охотничий отряд медведя", "es": "Partida de caza del oso"},
        "units": (("bear", "front"), ("goblin_hunter", "melee"), ("goblin_shaman", "support")),
    },
    "ashen_n3c1_mixed": {
        "location_id": "ashen_n3c1",
        "label": {"en": "Ruins Patrol", "ru": "Патруль руин", "es": "Patrulla de las ruinas"},
        "units": (("zombie", "melee"), ("zombie", "melee"), ("skeleton_mage", "ranged")),
    },
}


def enemy_profile(mob_id: str, level: int) -> dict[str, Any]:
    mob_id = str(mob_id)
    level = max(1, int(level))
    physical_defense = 0
    magic_defense = 0
    if mob_id in ARMORED_IDS:
        physical_defense = 12 + 6 * level
        magic_defense = 2 * level
    if mob_id in CASTER_IDS:
        physical_defense = level
        magic_defense = 8 + 4 * level
    accuracy_bonus = 8 if mob_id in EVASIVE_IDS else 0
    evasion_bonus = 24 if mob_id in EVASIVE_IDS else 0
    school = "magic" if mob_id in CASTER_IDS or mob_id in {"ghost", "air_elemental"} else "physical"
    behavior = "heavy" if mob_id in BRUTE_IDS else (
        "shaman" if mob_id == "goblin_shaman" else
        "priest" if mob_id == "skeleton_priest" else
        "witch" if mob_id in {"swamp_witch", "old_witch"} else
        "fire_elemental" if mob_id == "fire_elemental" else
        "caster" if mob_id in CASTER_IDS else "basic"
    )
    on_hit = []
    if mob_id in VENOM_IDS:
        on_hit.append("venom_third_hit")
    if mob_id in LEECH_IDS:
        on_hit.append("leech_third_hit")
    return {
        "rules_version": RULES_VERSION,
        "physical_defense": physical_defense,
        "magic_defense": magic_defense,
        "accuracy_bonus": accuracy_bonus,
        "evasion_bonus": evasion_bonus,
        "damage_school": school,
        "behavior": behavior,
        "on_hit_behaviors": on_hit,
    }


def resolve_enemy_snapshot(
    mob: dict[str, Any],
    *,
    unit_id: str | int | None = None,
    formation: str | None = None,
    spawn_profile: str = "normal",
) -> dict[str, Any]:
    mob_id = str(mob.get("id") or mob.get("mob_id") or "unknown")
    level = max(1, int(mob.get("level", 1) or 1))
    profile = enemy_profile(mob_id, level)
    hp = max(1, int(mob.get("hp", mob.get("max_hp", 1)) or 1))
    min_damage = max(1, int(mob.get("damage_min", mob.get("damage", 1)) or 1))
    max_damage = max(min_damage, int(mob.get("damage_max", mob.get("damage", min_damage)) or min_damage))
    resolved_formation = formation or (
        "support" if mob_id in {"goblin_shaman", "skeleton_priest", "swamp_witch", "old_witch"}
        else "ranged" if mob_id in {"skeleton_mage", "fire_elemental", "ghost", "air_elemental"}
        else "melee"
    )
    return {
        "rules_version": RULES_VERSION,
        "unit_id": str(unit_id if unit_id is not None else mob_id),
        "mob_id": mob_id,
        "name": str(mob.get("name") or mob_id),
        "level": level,
        "hp": hp,
        "max_hp": hp,
        "weapon_min": min_damage,
        "weapon_max": max_damage,
        "family": "enemy",
        "damage_school": profile["damage_school"],
        "physical_defense": profile["physical_defense"],
        "magic_defense": profile["magic_defense"],
        "accuracy": 100 + 2 * level + int(profile["accuracy_bonus"]),
        "evasion": 100 + level + int(profile["evasion_bonus"]),
        "block_chance": max(0, min(40, int(mob.get("block_chance", 0) or 0))),
        "formation": resolved_formation,
        "behavior": profile["behavior"],
        "on_hit_behaviors": profile["on_hit_behaviors"],
        "spawn_profile": str(spawn_profile or "normal"),
        "effects": [],
        "cooldowns": {},
        "skill_ranks": {},
        "opportunity_index": 0,
        "ai_action_index": 0,
        "successful_attacks": 0,
        "heavy_intent": False,
        "dead": False,
    }


def choose_enemy_action(enemy: dict[str, Any], allies: list[dict[str, Any]]) -> dict[str, Any]:
    """Choose a deterministic profile action for this enemy opportunity."""
    opportunity = int(enemy.get("ai_action_index", 0)) + 1
    behavior = str(enemy.get("behavior") or "basic")
    if behavior == "heavy" and opportunity % 3 == 0:
        return {"kind": "enemy_attack", "coefficient": 1.6, "behavior": "heavy"}
    if behavior == "shaman" and (opportunity == 1 or (opportunity - 1) % 4 == 0):
        return {"kind": "enemy_ward", "value": .20, "duration": 2, "behavior": "shaman"}
    if behavior == "priest" and opportunity % 3 == 0:
        living = [ally for ally in allies if int(ally.get("hp", 0)) > 0]
        injured = [ally for ally in living if int(ally.get("hp", 0)) * 10 < int(ally.get("max_hp", 1)) * 7]
        if injured:
            target = max(enumerate(injured), key=lambda pair: ((int(pair[1]["max_hp"]) - int(pair[1]["hp"])) / max(1, int(pair[1]["max_hp"])), -pair[0]))[1]
            return {"kind": "enemy_heal", "target_id": str(target.get("unit_id")), "fraction": .20, "behavior": "priest"}
    if behavior == "witch" and opportunity % 3 == 0:
        return {"kind": "enemy_weakness", "value": .20, "duration": 2, "behavior": "witch"}
    return {"kind": "enemy_attack", "coefficient": 1.0, "behavior": behavior}


def next_enemy_intent(enemy: dict[str, Any]) -> dict[str, Any] | None:
    next_opportunity = int(enemy.get("ai_action_index", 0)) + 1
    if str(enemy.get("behavior")) == "heavy" and next_opportunity % 3 == 0:
        return {"kind": "heavy", "coefficient": 1.6}
    return None

