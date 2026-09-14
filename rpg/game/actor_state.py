"""Serializable actor-state normalization shared by live and lab snapshots."""

from __future__ import annotations

import copy
from typing import Any

from game.balance import calc_profile_primary_offense_bonus, calc_profile_secondary_offense_bonus
from game.build_contract import RULES_VERSION, normalize_family


def finalize_actor_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(snapshot)
    result['rules_version'] = RULES_VERSION
    result['level'] = max(1, int(result.get('level', 1) or 1))
    result['family'] = normalize_family(result.get('family') or 'unarmed')
    result['skill_ranks'] = {
        str(skill_id): int(rank)
        for skill_id, rank in dict(result.get('skill_ranks') or {}).items()
        if int(rank) > 0
    }
    result['cooldowns'] = {
        str(skill_id): int(ready_at)
        for skill_id, ready_at in dict(result.get('cooldowns') or {}).items()
        if int(ready_at) >= 0
    }
    result['effects'] = list(result.get('effects') or [])
    result['setups'] = list(result.get('setups') or [])
    result['opportunity_index'] = max(0, int(result.get('opportunity_index', 0) or 0))
    result['max_hp'] = max(1, int(result.get('max_hp', 1) or 1))
    result['hp'] = max(0, min(int(result.get('hp', result['max_hp']) or 0), result['max_hp']))
    result['max_mana'] = max(0, int(result.get('max_mana', 0) or 0))
    result['mana'] = max(0, min(int(result.get('mana', result['max_mana']) or 0), result['max_mana']))
    result['manual_contribution'] = bool(result.get('manual_contribution', False))
    result['death_prevention_used'] = bool(result.get('death_prevention_used', False))
    result['dead'] = bool(result.get('dead', result['hp'] <= 0))
    return result


def raw_power_range(snapshot: dict[str, Any]) -> tuple[int, int]:
    profile = str(snapshot.get('family') or 'unarmed')
    primary = calc_profile_primary_offense_bonus(snapshot, profile)
    secondary = calc_profile_secondary_offense_bonus(snapshot, profile)
    school_multiplier = 1.0
    if snapshot.get('damage_school') in {'magic', 'holy'}:
        school_multiplier += min(40, max(0, int(snapshot.get('magic_power', 0)))) / 100
    return (
        max(1, int((int(snapshot.get('weapon_min', 5)) + primary + secondary) * school_multiplier)),
        max(1, int((int(snapshot.get('weapon_max', 5)) + primary + secondary) * school_multiplier)),
    )


def healing_power(snapshot: dict[str, Any], *, weapon_roll: float | None = None) -> int:
    if weapon_roll is None:
        weapon_roll = (int(snapshot.get('weapon_min', 5)) + int(snapshot.get('weapon_max', 5))) / 2
    raw = 30 + 3 * int(snapshot.get('wisdom', 0)) + .5 * float(weapon_roll)
    raw *= 1 + min(40, max(0, int(snapshot.get('healing_power', 0)))) / 100
    return max(1, int(raw))
