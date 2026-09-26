"""Shared PEV1 profession thresholds and separate crafting XP policy."""

from __future__ import annotations

from dataclasses import dataclass

MAX_PROFESSION_LEVEL = 20


def profession_exp_needed(level: int) -> int:
    return max(1, int(level)) * 50


def xp_to_level(current_level: int, current_exp: int, target_level: int) -> int:
    return max(0, sum(profession_exp_needed(level) for level in range(current_level, target_level)) - int(current_exp))


def crafting_training_ceiling(recipe_level: int) -> int:
    if recipe_level <= 2:
        return 6
    if recipe_level <= 6:
        return 12
    if recipe_level <= 12:
        return 18
    return 20


def crafting_xp_for_success(*, current_level: int, current_exp: int, recipe_level: int) -> int:
    ceiling = crafting_training_ceiling(recipe_level)
    if current_level >= ceiling or current_level >= MAX_PROFESSION_LEVEL:
        return 0
    return min(250 * int(recipe_level), xp_to_level(current_level, current_exp, ceiling))


@dataclass(frozen=True)
class ProfessionProgression:
    old_level: int
    old_exp: int
    new_level: int
    new_exp: int
    xp_awarded: int


def apply_profession_xp(current_level: int, current_exp: int, xp_awarded: int) -> ProfessionProgression:
    old_level, old_exp = int(current_level), int(current_exp)
    if old_level >= MAX_PROFESSION_LEVEL or xp_awarded <= 0:
        return ProfessionProgression(old_level, old_exp, old_level, old_exp, 0)
    level, exp = old_level, old_exp + int(xp_awarded)
    while level < MAX_PROFESSION_LEVEL and exp >= profession_exp_needed(level):
        exp -= profession_exp_needed(level)
        level += 1
    if level >= MAX_PROFESSION_LEVEL:
        exp = 0
    return ProfessionProgression(old_level, old_exp, level, exp, int(xp_awarded))
