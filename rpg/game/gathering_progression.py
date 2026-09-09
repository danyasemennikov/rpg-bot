"""Pure gathering profession XP and level progression helpers."""

from __future__ import annotations

from dataclasses import dataclass


MAX_GATHERING_PROFESSION_LEVEL = 20


@dataclass(frozen=True)
class GatheringProfessionProgressionResult:
    profession_key: str
    old_level: int
    new_level: int
    old_exp: int
    new_exp: int
    xp_awarded: int
    leveled_up: bool
    levels_gained: int
    exp_needed: int | None
    at_cap: bool


def gathering_profession_exp_needed(level: int) -> int:
    """Return XP needed to advance from the current profession level."""
    return max(1, int(level)) * 50


def gathering_profession_xp_for_success(
    *,
    current_profession_level: int,
    required_profession_level: int,
) -> int:
    """Return deterministic XP for one successfully granted resource."""
    current_level = max(1, int(current_profession_level))
    if current_level >= MAX_GATHERING_PROFESSION_LEVEL:
        return 0

    required_level = max(1, int(required_profession_level))
    base_xp = 8 + (2 * required_level)
    level_gap = current_level - required_level
    if level_gap <= 4:
        scaled_xp = base_xp
    elif level_gap <= 8:
        scaled_xp = base_xp // 2
    else:
        scaled_xp = base_xp // 4
    return max(1, scaled_xp)


def apply_gathering_profession_progression(
    *,
    profession_key: str,
    current_level: int,
    current_exp: int,
    xp_awarded: int,
) -> GatheringProfessionProgressionResult:
    """Apply current-level XP, including multiple level-ups and cap handling."""
    old_level = max(1, min(MAX_GATHERING_PROFESSION_LEVEL, int(current_level)))
    old_exp = max(0, int(current_exp))
    if old_level >= MAX_GATHERING_PROFESSION_LEVEL:
        old_exp = 0
        awarded = 0
    else:
        awarded = max(0, int(xp_awarded))

    new_level = old_level
    new_exp = old_exp + awarded
    while (
        new_level < MAX_GATHERING_PROFESSION_LEVEL
        and new_exp >= gathering_profession_exp_needed(new_level)
    ):
        new_exp -= gathering_profession_exp_needed(new_level)
        new_level += 1

    at_cap = new_level >= MAX_GATHERING_PROFESSION_LEVEL
    if at_cap:
        new_exp = 0

    levels_gained = new_level - old_level
    return GatheringProfessionProgressionResult(
        profession_key=profession_key,
        old_level=old_level,
        new_level=new_level,
        old_exp=old_exp,
        new_exp=new_exp,
        xp_awarded=awarded,
        leveled_up=levels_gained > 0,
        levels_gained=levels_gained,
        exp_needed=None if at_cap else gathering_profession_exp_needed(new_level),
        at_cap=at_cap,
    )
