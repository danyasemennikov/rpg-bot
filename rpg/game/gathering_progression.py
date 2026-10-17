"""Pure gathering profession XP and level progression helpers."""

from __future__ import annotations

from dataclasses import dataclass


MAX_GATHERING_PROFESSION_LEVEL = 30


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
    from game.profession_progression import profession_exp_needed
    return profession_exp_needed(level)


def gathering_profession_xp_for_success(
    *,
    current_profession_level: int,
    required_profession_level: int,
) -> int:
    from game.profession_progression import work_xp, profession_tier
    return work_xp(gathering=True,work_tier=profession_tier(required_profession_level),
                   category='S',current_level=current_profession_level)


def apply_gathering_profession_progression(
    *,
    profession_key: str,
    current_level: int,
    current_exp: int,
    xp_awarded: int,
) -> GatheringProfessionProgressionResult:
    from game.profession_progression import apply_profession_xp
    result = apply_profession_xp(current_level,current_exp,xp_awarded)
    halted = result.new_level in (15,30)
    return GatheringProfessionProgressionResult(
        profession_key=profession_key,old_level=result.old_level,new_level=result.new_level,
        old_exp=result.old_exp,new_exp=result.new_exp,xp_awarded=result.applied,
        leveled_up=result.new_level>result.old_level,levels_gained=result.new_level-result.old_level,
        exp_needed=None if halted else gathering_profession_exp_needed(result.new_level),at_cap=halted)
