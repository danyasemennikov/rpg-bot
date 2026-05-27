"""Release-grade balance foundation helpers for level 1-100.

This module is reference/audit-only and must not alter live gameplay runtime behavior.
"""

from __future__ import annotations

MAX_RELEASE_LEVEL = 100

GEAR_TIER_LEVEL_BANDS = (
    ("T1", 1, 10),
    ("T2", 11, 20),
    ("T3", 21, 30),
    ("T4", 31, 40),
    ("T5", 41, 50),
    ("T6", 51, 60),
    ("T7", 61, 70),
    ("T8", 71, 80),
    ("T9", 81, 90),
    ("T10", 91, 100),
)

BALANCE_MACRO_BANDS = (
    ("bootstrap", 1, 10),
    ("frontier", 11, 20),
    ("specialization", 21, 35),
    ("structured midgame", 36, 55),
    ("late midgame", 56, 75),
    ("late game", 76, 90),
    ("apex", 91, 100),
)

TTK_TARGET_BANDS = {
    "old_trivial": (1, 2),
    "normal": (3, 6),
    "pressure": (5, 9),
    "elite_solo": (8, 15),
    "bad_matchup_elite": (12, 20),
    "pack": None,
    "boss_group": None,
}

SIMULATION_STAGE_PLAYER_LEVEL_ASSUMPTIONS = {
    "soft_entry": 10,
    "identity_visible": 35,
    "build_testing": 70,
    "route_exam": 95,
}


def validate_release_level(level: int) -> bool:
    if level < 1:
        raise ValueError(f"Level {level} is invalid. Minimum release level is 1.")
    if level > MAX_RELEASE_LEVEL:
        raise ValueError(
            f"Level {level} is outside current release cap ({MAX_RELEASE_LEVEL})."
        )
    return True


def resolve_level_band(level: int) -> dict[str, int | str]:
    validate_release_level(level)
    for tier_id, min_level, max_level in GEAR_TIER_LEVEL_BANDS:
        if min_level <= level <= max_level:
            return {
                "tier_id": tier_id,
                "min_level": min_level,
                "max_level": max_level,
            }
    raise ValueError(f"No level band found for level {level}.")


def resolve_gear_tier_for_level(level: int) -> str:
    return str(resolve_level_band(level)["tier_id"])


def resolve_macro_band_for_level(level: int) -> str:
    validate_release_level(level)
    for band_name, min_level, max_level in BALANCE_MACRO_BANDS:
        if min_level <= level <= max_level:
            return band_name
    raise ValueError(f"No macro band found for level {level}.")


def resolve_simulation_stage_player_level(stage: str) -> int | None:
    return SIMULATION_STAGE_PLAYER_LEVEL_ASSUMPTIONS.get(str(stage or "").strip())


def build_simulation_stage_progression_context(stage: str) -> dict[str, str | int | None]:
    normalized_stage = str(stage or "").strip()
    assumed_player_level = resolve_simulation_stage_player_level(normalized_stage)
    macro_band = None
    gear_tier = None
    if assumed_player_level is not None:
        macro_band = resolve_macro_band_for_level(assumed_player_level)
        gear_tier = resolve_gear_tier_for_level(assumed_player_level)
    return {
        "stage": normalized_stage,
        "assumed_player_level": assumed_player_level,
        "macro_band": macro_band,
        "gear_tier": gear_tier,
        "gear_rarity_assumption": None,
        "enhancement_assumption": None,
        "assumption_status": None,
        "simulation_gear_preset": None,
    }
