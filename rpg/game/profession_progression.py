"""Frozen Epic I profession policy, independent of character progression."""
from dataclasses import dataclass

MAX_PROFESSION_LEVEL = 30
PROFESSION_TIER_RANGES = tuple((15*i+1, 15*(i+1)) for i in range(8))
POLICY_VERSION = 3


def profession_tier(level: int) -> int:
    if type(level) is not int or not 1 <= level <= 120:
        raise ValueError('invalid_profession_level')
    return (level-1)//15+1


def profession_exp_needed(level: int) -> int:
    if 1 <= level <= 14:
        return 100+20*(level-1)
    if 16 <= level <= 29:
        return 300+30*(level-16)
    raise ValueError('profession_xp_halted')


def xp_to_level(current_level: int, current_exp: int, target_level: int) -> int:
    return max(0, sum(profession_exp_needed(p) for p in range(current_level,target_level))-current_exp)


def work_xp(*, gathering: bool, work_tier: int, category: str, current_level: int) -> int:
    if work_tier not in (1,2) or category not in ('S','R','C'):
        raise ValueError('invalid_work_policy')
    base = ((3,4,5) if gathering else (6,12,18))[('S','R','C').index(category)]*work_tier
    return max(1,base//5) if current_level >= 16 and work_tier == 1 else base


def crafting_xp_for_success(*, current_level: int, current_exp: int, recipe_level: int,
                            material_value: int, category: str = 'S') -> int:
    return work_xp(gathering=False,work_tier=profession_tier(recipe_level),category=category,current_level=current_level)


@dataclass(frozen=True)
class ProfessionProgression:
    old_level: int
    old_exp: int
    new_level: int
    new_exp: int
    xp_awarded: int
    attempted: int = 0
    applied: int = 0
    discarded: int = 0


def apply_profession_xp(current_level: int, current_exp: int, xp_awarded: int) -> ProfessionProgression:
    if (type(current_level) is not int or not 1 <= current_level <= 30
            or type(current_exp) is not int or current_exp < 0
            or type(xp_awarded) is not int or xp_awarded < 0):
        raise ValueError('invalid_profession_xp')
    cap = 15 if current_level <= 15 else 30
    level, exp = current_level, current_exp
    if level == cap:
        if exp:
            raise ValueError('invalid_profession_cap_exp')
        applied = 0
    else:
        applied = min(xp_awarded,xp_to_level(level,exp,cap))
        exp += applied
        while level < cap and exp >= profession_exp_needed(level):
            exp -= profession_exp_needed(level)
            level += 1
        if level == cap:
            exp = 0
    return ProfessionProgression(current_level,current_exp,level,exp,applied,xp_awarded,applied,xp_awarded-applied)


def personal_batch_limit(level: int) -> int:
    return 4 if level >= 25 else 2 if level >= 10 else 1


def processing_duration_ms(level: int) -> int:
    return 108000 if level >= 25 else 114000 if level >= 10 else 120000
