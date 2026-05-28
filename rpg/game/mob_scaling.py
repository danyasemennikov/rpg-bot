from __future__ import annotations

from copy import deepcopy
from typing import Any

from game.balance_foundation import resolve_simulation_stage_player_level
from game.mobs import MOBS

SCALING_STATUS_FORMULA_V1 = "formula_mob_scaling_v1"
SCALED_MOB_STAT_KEYS = ("hp", "damage", "accuracy", "evasion", "defense", "magic_defense")
ROLE_NORMAL = "normal"
ROLE_PRESSURE = "pressure"
ROLE_ELITE = "elite"
ROLE_BOSS = "boss"
ROLE_PACK_MEMBER = "pack_member"
ROLE_PACK_LEADER = "pack_leader"

MOB_ROLE_MULTIPLIERS: dict[str, dict[str, float]] = {
    ROLE_NORMAL: {"hp": 1.00, "damage": 1.00, "accuracy": 1.00, "evasion": 1.00, "defense": 1.00, "magic_defense": 1.00},
    ROLE_PRESSURE: {"hp": 1.20, "damage": 1.12, "accuracy": 1.05, "evasion": 1.04, "defense": 1.08, "magic_defense": 1.08},
    ROLE_ELITE: {"hp": 1.85, "damage": 1.35, "accuracy": 1.10, "evasion": 1.08, "defense": 1.18, "magic_defense": 1.18},
    ROLE_BOSS: {"hp": 3.20, "damage": 1.65, "accuracy": 1.16, "evasion": 1.10, "defense": 1.28, "magic_defense": 1.28},
    ROLE_PACK_MEMBER: {"hp": 0.78, "damage": 0.82, "accuracy": 0.98, "evasion": 1.00, "defense": 0.94, "magic_defense": 0.94},
    ROLE_PACK_LEADER: {"hp": 1.25, "damage": 1.12, "accuracy": 1.04, "evasion": 1.02, "defense": 1.06, "magic_defense": 1.06},
}

ROUTE_PRESSURE_MODIFIERS: dict[str, dict[str, float]] = {
    "route_westwild": {"hp": 1.00, "damage": 1.00, "accuracy": 1.00, "evasion": 1.00, "defense": 1.00, "magic_defense": 1.00},
    "route_frostspine": {"hp": 1.08, "damage": 1.00, "accuracy": 1.00, "evasion": 0.98, "defense": 1.10, "magic_defense": 1.04},
    "route_ashen_ruins": {"hp": 1.00, "damage": 1.06, "accuracy": 1.03, "evasion": 1.00, "defense": 0.98, "magic_defense": 1.12},
    "route_mireveil": {"hp": 1.04, "damage": 1.02, "accuracy": 1.00, "evasion": 1.08, "defense": 1.00, "magic_defense": 1.06},
    "route_sunscar": {"hp": 1.00, "damage": 1.10, "accuracy": 1.06, "evasion": 1.02, "defense": 1.00, "magic_defense": 1.00},
}

SIMULATION_STAGE_PRESSURE_MODIFIERS: dict[str, dict[str, float]] = {
    "soft_entry": {"hp": 1.00, "damage": 1.00, "accuracy": 1.00, "evasion": 1.00, "defense": 1.00, "magic_defense": 1.00},
    "identity_visible": {"hp": 1.08, "damage": 1.06, "accuracy": 1.01, "evasion": 1.00, "defense": 1.02, "magic_defense": 1.02},
    "build_testing": {"hp": 1.22, "damage": 1.30, "accuracy": 1.03, "evasion": 1.01, "defense": 1.06, "magic_defense": 1.06},
    "route_exam": {"hp": 1.30, "damage": 1.50, "accuracy": 1.05, "evasion": 1.02, "defense": 1.10, "magic_defense": 1.10},
}


def calculate_encounter_level_from_stage(stage: str) -> int | None:
    return resolve_simulation_stage_player_level(stage)


def calculate_mob_level_scale(encounter_level: int) -> dict[str, float]:
    level = int(encounter_level)
    if not 1 <= level <= 100:
        raise ValueError("encounter_level must be within 1..100")
    level_factor = level / 10.0
    return {
        "hp": 1.0 + 0.34 * level_factor + 0.030 * level_factor**2,
        "damage": 1.0 + 0.25 * level_factor + 0.018 * level_factor**2,
        "accuracy": 1.0 + 0.045 * level_factor,
        "evasion": 1.0 + 0.035 * level_factor,
        "defense": 1.0 + 0.18 * level_factor + 0.010 * level_factor**2,
        "magic_defense": 1.0 + 0.18 * level_factor + 0.010 * level_factor**2,
    }


def _scaled_value(base_value: Any, level_scale: float, role_scale: float, route_scale: float, stage_scale: float) -> int | None:
    if not isinstance(base_value, (int, float)):
        return None
    return int(round(base_value * level_scale * role_scale * route_scale * stage_scale))


def build_scaled_mob_stats(base_mob: dict, *, encounter_level: int, mob_role: str, route_id: str | None = None, stage: str | None = None) -> dict:
    role = str(mob_role or ROLE_NORMAL).lower()
    if role not in MOB_ROLE_MULTIPLIERS:
        role = ROLE_NORMAL
    level_scale = calculate_mob_level_scale(encounter_level)
    role_multiplier = MOB_ROLE_MULTIPLIERS[role]
    route_modifier = ROUTE_PRESSURE_MODIFIERS.get(str(route_id or ""), ROUTE_PRESSURE_MODIFIERS["route_westwild"])
    stage_key = str(stage or "")
    stage_modifier = SIMULATION_STAGE_PRESSURE_MODIFIERS.get(stage_key, SIMULATION_STAGE_PRESSURE_MODIFIERS["soft_entry"])

    scaled = deepcopy(base_mob)
    base_stats = {k: base_mob.get(k) for k in SCALED_MOB_STAT_KEYS if k in base_mob}
    final_stats: dict[str, int] = {}
    for key in SCALED_MOB_STAT_KEYS:
        val = _scaled_value(base_mob.get(key), level_scale[key], role_multiplier[key], route_modifier[key], stage_modifier[key])
        if val is not None:
            final_stats[key] = val
            scaled[key] = val

    if "damage" not in base_mob:
        dmin = base_mob.get("damage_min")
        dmax = base_mob.get("damage_max")
        if isinstance(dmin, (int, float)):
            scaled["damage_min"] = _scaled_value(dmin, level_scale["damage"], role_multiplier["damage"], route_modifier["damage"], stage_modifier["damage"])
        if isinstance(dmax, (int, float)):
            scaled["damage_max"] = _scaled_value(dmax, level_scale["damage"], role_multiplier["damage"], route_modifier["damage"], stage_modifier["damage"])
        if isinstance(scaled.get("damage_min"), int) and isinstance(scaled.get("damage_max"), int):
            scaled["damage"] = int(round((scaled["damage_min"] + scaled["damage_max"]) / 2))
            final_stats["damage"] = scaled["damage"]

    scaled["encounter_level"] = encounter_level
    scaled["mob_role"] = role
    scaled["route_id"] = route_id
    scaled["stage"] = stage
    scaled["scaling_status"] = SCALING_STATUS_FORMULA_V1
    scaled["base_template_id"] = base_mob.get("id")
    scaled["base_mob_stats"] = base_stats
    scaled["final_mob_stats"] = final_stats
    scaled["scale_components"] = {
        "level_scale": level_scale,
        "role_multiplier": role_multiplier,
        "route_modifier": route_modifier,
        "stage_pressure_modifier": stage_modifier,
    }
    return scaled


def build_scaled_mob_for_simulation(mob_id: str, route_id: str, stage: str, mob_role: str = ROLE_NORMAL) -> dict:
    base = MOBS.get(mob_id)
    if not isinstance(base, dict):
        raise KeyError(f"Unknown mob_id: {mob_id}")
    encounter_level = calculate_encounter_level_from_stage(stage)
    if encounter_level is None:
        raise ValueError(f"Unknown stage for encounter level resolution: {stage}")
    return build_scaled_mob_stats(base, encounter_level=encounter_level, mob_role=mob_role, route_id=route_id, stage=stage)
