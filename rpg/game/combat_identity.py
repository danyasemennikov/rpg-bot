"""Pure Character Builds & Combat Identity V1 action evaluator.

The evaluator has no database, Telegram or wall-clock dependency.  Callers pass
fully resolved actor/unit snapshots and a deterministic seed; the returned
state and event log are safe to persist atomically as one side result.
"""

from __future__ import annotations

import copy
import hashlib
import math
import random
from typing import Any, Iterable

from game.actor_state import healing_power, raw_power_range
from game.build_contract import (
    POWER_STRIKE,
    RULES_VERSION,
    SKILL_SPECS,
    normalize_family,
    rank_mana_cost,
    rank_multiplier,
    rank_percent,
)


ORDINARY_REDUCTION_CAP = .75
RATING_REDUCTION_CAP = .55
RATING_IGNORE_CAP = .60
WARD_CAP = .45
EXPOSURE_CAP = .30
WEAKNESS_CAP = .30
ATTACK_UP_CAP = .30
BLOCK_CAP = .40
BLOCK_REDUCTION = .35
BARRIER_CAP = .35
SETUP_BONUS_CAP = .50
CRIT_CAP_PERCENT = 35.0
CRIT_MULTIPLIER = 1.5


def combat_seed(*parts: Any) -> int:
    raw = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def _id(entity: dict[str, Any]) -> str:
    return str(entity.get("actor_id", entity.get("unit_id", entity.get("id", ""))))


def _alive(entity: dict[str, Any]) -> bool:
    return int(entity.get("hp", 0)) > 0 and not bool(entity.get("dead"))


def _effects(entity: dict[str, Any]) -> list[dict[str, Any]]:
    value = entity.setdefault("effects", [])
    if not isinstance(value, list):
        value = []
        entity["effects"] = value
    return value


def _find_effect(
    entity: dict[str, Any],
    kind: str,
    *,
    source_id: Any | None = None,
    school: str | None = None,
) -> list[dict[str, Any]]:
    return [
        effect for effect in _effects(entity)
        if effect.get("kind") == kind
        and (source_id is None or str(effect.get("source_id")) == str(source_id))
        and (school is None or effect.get("school") == school)
    ]


def _strongest(entity: dict[str, Any], kinds: str | Iterable[str]) -> float:
    allowed = {kinds} if isinstance(kinds, str) else set(kinds)
    return max((float(effect.get("value", 0)) for effect in _effects(entity) if effect.get("kind") in allowed), default=0.0)


def _remove_effects(
    entity: dict[str, Any], kinds: Iterable[str], *, source_id: Any | None = None,
) -> list[dict[str, Any]]:
    kinds = set(kinds)
    removed = []
    kept = []
    for effect in _effects(entity):
        match = effect.get("kind") in kinds and (
            source_id is None or str(effect.get("source_id")) == str(source_id)
        )
        (removed if match else kept).append(effect)
    entity["effects"] = kept
    return removed


def _effect(
    kind: str,
    source: dict[str, Any],
    duration: int,
    *,
    value: float = 0.0,
    skill_id: str,
    side_index: int,
    school: str | None = None,
    raw_tick: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "source_id": _id(source),
        "skill_id": skill_id,
        "duration": max(1, int(duration)),
        "value": float(value),
        "school": school,
        "raw_tick": None if raw_tick is None else max(0, int(raw_tick)),
        "created_side_index": int(side_index),
        "metadata": dict(metadata or {}),
    }


def _add_effect(target: dict[str, Any], effect: dict[str, Any]) -> None:
    kind = str(effect["kind"])
    source_id = effect.get("source_id")
    school = effect.get("school")
    effects = _effects(target)
    if kind == "barrier":
        effect["value"] = min(float(effect["value"]), int(target.get("max_hp", 1)) * BARRIER_CAP)
    if kind in {"ward", "guard", "barrier", "exposure", "dawn_mark", "weakness", "attack_up"}:
        category = "exposure" if kind in {"exposure", "dawn_mark"} else kind
        same_category = [
            old for old in effects
            if ("exposure" if old.get("kind") in {"exposure", "dawn_mark"} else old.get("kind")) == category
        ]
        strongest = max(same_category, key=lambda old: float(old.get("value", 0)), default=None)
        if strongest and float(strongest.get("value", 0)) > float(effect.get("value", 0)):
            return
        target["effects"] = [old for old in effects if old not in same_category]
        effects = _effects(target)
    elif kind in {"bleed", "burn", "regeneration", "chilled", "judgment", "hunters_mark"}:
        target["effects"] = [
            old for old in effects
            if not (
                old.get("kind") == kind
                and str(old.get("source_id")) == str(source_id)
                and (kind != "burn" or old.get("school") == school)
            )
        ]
        effects = _effects(target)
    elif kind == "slow":
        target["effects"] = [old for old in effects if old.get("kind") != "slow"]
        effects = _effects(target)
    elif kind == "poison":
        own = [old for old in effects if old.get("kind") == "poison" and str(old.get("source_id")) == str(source_id)]
        if len(own) >= 3:
            oldest = min(own, key=lambda old: (int(old.get("created_side_index", 0)), effects.index(old)))
            effects.remove(oldest)
    effects.append(effect)


def _has(entity: dict[str, Any], kind: str, *, source_id: Any | None = None) -> bool:
    return bool(_find_effect(entity, kind, source_id=source_id))


def _effect_value(entity: dict[str, Any], kind: str, *, source_id: Any | None = None) -> float:
    return max((float(item.get("value", 0)) for item in _find_effect(entity, kind, source_id=source_id)), default=0.0)


def _ranked(base: float, rank: int) -> float:
    return float(base) * rank_multiplier(rank)


def hit_chance(actor: dict[str, Any], target: dict[str, Any], *, accuracy_bonus: int = 0) -> int:
    accuracy = int(actor.get("accuracy", 100)) + int(accuracy_bonus)
    accuracy += int(_strongest(actor, "accuracy_up"))
    if _has(actor, "slow"):
        accuracy -= 40
    evasion = int(target.get("evasion", 100)) + int(_strongest(target, "evasion_up"))
    return max(50, min(95, 85 + math.floor((accuracy - evasion) / 4)))


def crit_chance(actor: dict[str, Any]) -> float:
    return min(CRIT_CAP_PERCENT, .35 * int(actor.get("luck", 0)) + .05 * int(actor.get("agility", 0)))


def mitigation_fraction(
    target: dict[str, Any],
    *,
    source_level: int,
    school: str,
    penetration: float = 0.0,
) -> float:
    defense_key = "physical_defense" if school in {"physical", "poison", "bleed"} else "magic_defense"
    rating = max(0.0, float(target.get(defense_key, 0)))
    break_value = min(RATING_IGNORE_CAP, _strongest(target, "physical_break") if defense_key == "physical_defense" else _strongest(target, "magic_break"))
    total_ignore = min(RATING_IGNORE_CAP, 1 - (1 - max(0.0, min(RATING_IGNORE_CAP, penetration))) * (1 - break_value))
    effective = rating * (1 - total_ignore)
    k = 120 + 6 * max(0, int(source_level) - 1)
    return min(RATING_REDUCTION_CAP, effective / (effective + k)) if effective > 0 else 0.0


def preview_damage_range(
    actor: dict[str, Any], target: dict[str, Any], *, coefficient: float = 1.0,
    school: str | None = None, penetration: float = 0.0,
) -> tuple[int, int]:
    low, high = raw_power_range(actor)
    school = school or str(actor.get("damage_school") or "physical")
    exposure = min(EXPOSURE_CAP, _strongest(target, {"exposure", "dawn_mark"}))
    weakness = min(WEAKNESS_CAP, _strongest(actor, "weakness"))
    ward = min(WARD_CAP, _strongest(target, {"ward", "guard"}))
    rating = mitigation_fraction(target, source_level=int(actor.get("level", 1)), school=school, penetration=penetration)
    combined = min(ORDINARY_REDUCTION_CAP, 1 - (1 - rating) * (1 - ward) * (1 - weakness))
    return (
        max(1, int(low * coefficient * (1 + exposure) * (1 - combined))),
        max(1, int(high * coefficient * (1 + exposure) * (1 - combined))),
    )


def _formation_rank(value: str) -> int:
    return {"front": 0, "melee": 1, "ranged": 2, "support": 3}.get(str(value), 1)


def select_targets(
    target_code: str,
    actor: dict[str, Any],
    allies: list[dict[str, Any]],
    opponents: list[dict[str, Any]],
    target_id: Any | None,
) -> list[dict[str, Any]]:
    living_opponents = [target for target in opponents if _alive(target)]
    living_allies = [target for target in allies if _alive(target)]
    wanted = str(target_id) if target_id is not None else None
    exact_enemy = next((target for target in living_opponents if _id(target) == wanted), None)
    exact_ally = next((target for target in living_allies if _id(target) == wanted), None)
    if target_code == "Self":
        return [actor]
    if target_code == "Ally":
        return [exact_ally] if exact_ally else []
    if target_code == "Party":
        return living_allies
    if target_code == "AllyOrEnemy":
        return [exact_ally or exact_enemy] if (exact_ally or exact_enemy) else []
    if not living_opponents:
        return []
    stable = sorted(enumerate(living_opponents), key=lambda pair: (_formation_rank(pair[1].get("formation", "melee")), pair[0]))
    ordered = [target for _, target in stable]
    if target_code == "S":
        return [exact_enemy or ordered[0]]
    if target_code == "B":
        back_rank = max(_formation_rank(target.get("formation", "melee")) for target in living_opponents)
        if exact_enemy:
            return [exact_enemy] if _formation_rank(exact_enemy.get("formation", "melee")) == back_rank else []
        return [next(target for target in ordered if _formation_rank(target.get("formation", "melee")) == back_rank)]
    if target_code == "F":
        front_rank = min(_formation_rank(target.get("formation", "melee")) for target in living_opponents)
        return [target for target in ordered if _formation_rank(target.get("formation", "melee")) == front_rank][:4]
    if target_code == "A":
        return living_opponents
    if target_code == "2x2":
        selected = []
        for line in sorted({_formation_rank(target.get("formation", "melee")) for target in living_opponents})[:2]:
            selected.extend([target for target in living_opponents if _formation_rank(target.get("formation", "melee")) == line][:2])
        return selected
    return []


def _heal(target: dict[str, Any], amount: float) -> int:
    if not _alive(target):
        return 0
    missing = max(0, int(target.get("max_hp", 1)) - int(target.get("hp", 0)))
    actual = min(missing, max(0, int(amount)))
    target["hp"] = int(target.get("hp", 0)) + actual
    return actual


def _prevent_death_with_covenant(target: dict[str, Any]) -> bool:
    if int(target.get("hp", 0)) > 0 or bool(target.get("death_prevention_used")):
        return False
    covenants = _find_effect(target, "life_covenant")
    if not covenants:
        return False
    covenant = max(covenants, key=lambda item: float(item.get("value", 0)))
    target["death_prevention_used"] = True
    target["hp"] = min(int(target.get("max_hp", 1)), max(1, int(covenant.get("value", 1))))
    target["dead"] = False
    _remove_effects(target, {"life_covenant"})
    return True


def _restore_mana(target: dict[str, Any], amount: float) -> int:
    missing = max(0, int(target.get("max_mana", 0)) - int(target.get("mana", 0)))
    actual = min(missing, max(0, int(amount)))
    target["mana"] = int(target.get("mana", 0)) + actual
    return actual


def _apply_barrier(target: dict[str, Any], source: dict[str, Any], amount: int, duration: int, skill_id: str, side_index: int) -> None:
    amount = min(max(0, int(amount)), int(target.get("max_hp", 1) * BARRIER_CAP))
    current = _find_effect(target, "barrier")
    if current and max(float(item.get("value", 0)) for item in current) > amount:
        return
    _add_effect(target, _effect("barrier", source, duration, value=amount, skill_id=skill_id, side_index=side_index))


def _apply_direct_damage(
    actor: dict[str, Any],
    target: dict[str, Any],
    *,
    raw: int,
    school: str,
    penetration: float,
    rng: random.Random,
    can_crit: bool = True,
    retaliation: bool = False,
) -> dict[str, Any]:
    crit = can_crit and rng.random() * 100 < crit_chance(actor)
    offense = float(raw) * (CRIT_MULTIPLIER if crit else 1.0)
    offense *= 1 + min(EXPOSURE_CAP, _strongest(target, {"exposure", "dawn_mark"}))
    offense *= 1 + max(0.0, _strongest(target, "received_damage_up"))
    rating = mitigation_fraction(
        target, source_level=int(actor.get("level", 1)), school=school, penetration=penetration,
    )
    ward = min(WARD_CAP, _strongest(target, {"ward", "guard"}))
    weakness = min(WEAKNESS_CAP, _strongest(actor, "weakness"))
    combined = min(ORDINARY_REDUCTION_CAP, 1 - (1 - rating) * (1 - ward) * (1 - weakness))
    mitigated = max(1, int(offense * (1 - combined)))
    finished = _finish_direct_packet(target, mitigated=mitigated, rng=rng, retaliation=retaliation)
    return {
        "raw": int(raw), "crit": crit,
        "ordinary_reduction": combined,
        **finished,
    }


def _finish_direct_packet(
    target: dict[str, Any], *, mitigated: int, rng: random.Random, retaliation: bool,
) -> dict[str, Any]:
    blocked = False
    block_chance = min(BLOCK_CAP, max(0.0, float(target.get("block_chance", 0)) / 100))
    if not retaliation and block_chance and rng.random() < block_chance:
        mitigated = max(1, int(mitigated * (1 - BLOCK_REDUCTION)))
        blocked = True
    parried = 0
    parry_retaliation = 0.0
    parries = _find_effect(target, "parry")
    if parries and not retaliation:
        parry = parries[0]
        parry_retaliation = float(parry.get("value", 0))
        reduced = int(mitigated * .60)
        mitigated -= reduced
        parried = reduced
        _remove_effects(target, {"parry"}, source_id=parry.get("source_id"))
    barrier_absorbed = 0
    barriers = _find_effect(target, "barrier")
    if barriers:
        barrier = max(barriers, key=lambda item: float(item.get("value", 0)))
        barrier_absorbed = min(mitigated, int(barrier.get("value", 0)))
        barrier["value"] = int(barrier.get("value", 0)) - barrier_absorbed
        mitigated -= barrier_absorbed
        if int(barrier["value"]) <= 0:
            _effects(target).remove(barrier)
    before = int(target.get("hp", 0))
    actual = min(before, max(0, mitigated))
    target["hp"] = before - actual
    death_prevented = _prevent_death_with_covenant(target)
    target["dead"] = int(target.get("hp", 0)) <= 0
    return {
        "blocked": blocked, "parried": parried,
        "barrier_absorbed": barrier_absorbed, "hp_removed": actual,
        "death_prevented": death_prevented,
        "parry_retaliation": parry_retaliation,
    }


def _apply_periodic_damage(
    target: dict[str, Any], *, raw: int, school: str, source_level: int,
    weakness: float = 0.0,
) -> dict[str, Any]:
    """Resolve a DoT/consumed-DoT packet without direct-hit-only layers."""
    rating = mitigation_fraction(
        target, source_level=source_level, school=school, penetration=0,
    )
    ward = min(WARD_CAP, _strongest(target, {"ward", "guard"}))
    combined = min(
        ORDINARY_REDUCTION_CAP,
        1 - (1 - rating) * (1 - ward) * (1 - min(WEAKNESS_CAP, max(0.0, weakness))),
    )
    damage = max(1, int(max(0, raw) * (1 - combined))) if raw else 0
    before = int(target.get("hp", 0))
    actual = min(before, damage)
    target["hp"] = before - actual
    death_prevented = _prevent_death_with_covenant(target)
    target["dead"] = int(target.get("hp", 0)) <= 0
    return {
        "raw": int(raw), "ordinary_reduction": combined,
        "hp_removed": actual, "death_prevented": death_prevented,
    }


def _apply_mixed_direct_damage(
    actor: dict[str, Any], target: dict[str, Any], *, magic_raw: int,
    holy_raw: int, rng: random.Random,
) -> dict[str, Any]:
    """Resolve two schools with one hit/crit/block/barrier action packet."""
    crit = rng.random() * 100 < crit_chance(actor)
    exposure = min(EXPOSURE_CAP, _strongest(target, {"exposure", "dawn_mark"}))
    received = 1 + max(0.0, _strongest(target, "received_damage_up"))
    ward = min(WARD_CAP, _strongest(target, {"ward", "guard"}))
    weakness = min(WEAKNESS_CAP, _strongest(actor, "weakness"))
    packets = []
    for school, raw in (("magic", magic_raw), ("holy", holy_raw)):
        offense = float(raw) * (CRIT_MULTIPLIER if crit else 1.0) * (1 + exposure) * received
        rating = mitigation_fraction(target, source_level=int(actor.get("level", 1)), school=school)
        combined = min(ORDINARY_REDUCTION_CAP, 1 - (1 - rating) * (1 - ward) * (1 - weakness))
        packets.append({
            "school": school, "raw": int(raw), "ordinary_reduction": combined,
            "mitigated": max(1, int(offense * (1 - combined))),
        })
    finished = _finish_direct_packet(
        target, mitigated=sum(packet["mitigated"] for packet in packets),
        rng=rng, retaliation=False,
    )
    return {
        "raw": int(magic_raw) + int(holy_raw), "crit": crit,
        "mixed_packets": packets, "ordinary_reduction": None, **finished,
    }


def _resolve_defensive_triggers(
    defender: dict[str, Any],
    attacker: dict[str, Any],
    damage_result: dict[str, Any],
    *,
    defensive_active_before: bool,
    duel_window_before: bool,
    side_index: int,
    rng: random.Random,
    events: list[dict[str, Any]],
    deferred: list[tuple[dict[str, Any], dict[str, Any], list[tuple[str, float]]]] | None = None,
) -> None:
    """Resolve explicit landed-hit tokens/retaliation without recursion."""
    if duel_window_before and not _has(defender, "reprisal", source_id=_id(defender)):
        _add_effect(defender, _effect("reprisal", defender, 2, value=.25, skill_id="dueling_ward", side_index=side_index))
        events.append({"kind": "reprisal_granted", "target_id": _id(defender)})
    retaliation_coefficients = []
    parry_coefficient = float(damage_result.get("parry_retaliation", 0))
    if parry_coefficient > 0:
        retaliation_coefficients.append(("parry", parry_coefficient))
    counter_rank = int(defender.get("skill_ranks", {}).get("counter", 0))
    if (
        counter_rank > 0 and defensive_active_before
        and bool(defender.get("pve_passives_enabled", True))
        and int(defender.get("counter_used_side_index", -1)) != int(side_index)
    ):
        retaliation_coefficients.append(("counter", _ranked(.40, counter_rank)))
        defender["counter_used_side_index"] = int(side_index)
    if deferred is not None:
        deferred.append((defender, attacker, retaliation_coefficients))
        return
    _apply_retaliations(defender, attacker, retaliation_coefficients, rng=rng, events=events)


def _apply_retaliations(
    defender: dict[str, Any], attacker: dict[str, Any],
    retaliation_coefficients: list[tuple[str, float]], *,
    rng: random.Random, events: list[dict[str, Any]],
) -> None:
    if not _alive(attacker) or not _alive(defender):
        return
    for trigger, coefficient in retaliation_coefficients:
        low, high = raw_power_range(defender)
        raw = int(((low + high) / 2) * coefficient)
        packet = _apply_direct_damage(
            defender, attacker, raw=raw, school="physical", penetration=0,
            rng=rng, can_crit=False, retaliation=True,
        )
        events.append({
            "kind": "retaliation", "trigger": trigger,
            "actor_id": _id(defender), "target_id": _id(attacker), **packet,
        })


def _setup_bonus(actor: dict[str, Any], skill_id: str, action_kind: str) -> tuple[float, list[str]]:
    source = _id(actor)
    bonus = 0.0
    consumed = []
    mappings = {
        "driving": .20,
        "focus": .25,
        "flow": 0.0,
        "opening": .25,
        "aim": .25,
        "surge": .25,
        "echo": .25,
        "reprisal": .25,
        "grace": .20,
        "envenom": 0.0,
    }
    eligible = {
        "driving": action_kind == "normal",
        "focus": action_kind in {"normal", "skill"},
        "flow": False,
        "opening": action_kind == "normal",
        "aim": action_kind in {"normal", "skill"} and normalize_family(actor.get("family")) == "bow",
        "surge": action_kind in {"normal", "skill"} and normalize_family(actor.get("family")) == "magic_staff",
        "echo": action_kind in {"normal", "skill"} and normalize_family(actor.get("family")) == "wand",
        "reprisal": action_kind == "normal",
        "grace": action_kind == "normal" and normalize_family(actor.get("family")) == "tome",
        "envenom": action_kind in {"normal", "skill"} and normalize_family(actor.get("family")) == "daggers",
    }
    for kind, value in mappings.items():
        if eligible[kind] and _has(actor, kind, source_id=source):
            stored = _effect_value(actor, kind, source_id=source)
            # Some setup tokens carry effect-specific payload rather than a
            # direct-damage multiplier. Envenom's stored value scales only the
            # poison attached by _on_hit.
            if value > 0:
                bonus += stored if stored > 0 else value
            consumed.append(kind)
    return min(SETUP_BONUS_CAP, bonus), consumed


def _ranked_percent(base: float, rank: int) -> float:
    return min(1.0, rank_percent(base, rank))


def _apply_skill_support(
    actor: dict[str, Any],
    allies: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    *,
    skill_id: str,
    rank: int,
    side_index: int,
    events: list[dict[str, Any]],
) -> None:
    h = healing_power(actor) * rank_multiplier(rank)
    if skill_id in {"defensive_stance", "radiant_ward", "aura_of_resolve", "dueling_ward"}:
        values = {"defensive_stance": .30, "radiant_ward": .20, "aura_of_resolve": .20, "dueling_ward": .25}
        duration = 2 if skill_id != "dueling_ward" else 1
        value = min(WARD_CAP, _ranked_percent(values[skill_id], rank))
        for target in targets:
            metadata = {"duel": skill_id == "dueling_ward"}
            _add_effect(target, _effect("ward", actor, duration, value=value, skill_id=skill_id, side_index=side_index, metadata=metadata))
            if skill_id == "aura_of_resolve" and _id(target) != _id(actor):
                _add_effect(target, _effect("intercept", actor, 1, skill_id=skill_id, side_index=side_index, metadata={"protector_id": _id(actor)}))
    elif skill_id == "parry":
        _add_effect(actor, _effect("parry", actor, 1, value=_ranked(.45, rank), skill_id=skill_id, side_index=side_index))
    elif skill_id == "executioners_focus":
        _add_effect(actor, _effect("focus", actor, 2, value=_ranked_percent(.25, rank), skill_id=skill_id, side_index=side_index))
    elif skill_id == "battle_stance":
        _add_effect(actor, _effect("attack_up", actor, 2, value=_ranked_percent(.15, rank), skill_id=skill_id, side_index=side_index))
        _add_effect(actor, _effect("ward", actor, 2, value=_ranked_percent(.15, rank), skill_id=skill_id, side_index=side_index))
        _add_effect(actor, _effect("battle_stance", actor, 2, skill_id=skill_id, side_index=side_index))
        _add_effect(actor, _effect("flow", actor, 2, skill_id=skill_id, side_index=side_index))
    elif skill_id in {"riposte_step", "smoke_bomb", "reposition"}:
        base = {"riposte_step": 40, "smoke_bomb": 40, "reposition": 45}[skill_id]
        value = int(base * rank_multiplier(rank))
        _add_effect(actor, _effect("evasion_up", actor, 2, value=value, skill_id=skill_id, side_index=side_index))
        if skill_id in {"riposte_step", "smoke_bomb"}:
            token = "flow" if skill_id == "riposte_step" else "opening"
            _add_effect(actor, _effect(token, actor, 2, skill_id=skill_id, side_index=side_index))
    elif skill_id == "rage_call":
        payment = max(1, int(int(actor.get("hp", 1)) * .08))
        actor["hp"] = max(1, int(actor.get("hp", 1)) - payment)
        _add_effect(actor, _effect("attack_up", actor, 2, value=_ranked_percent(.25, rank), skill_id=skill_id, side_index=side_index, metadata={"rage": True}))
        _add_effect(actor, _effect("received_damage_up", actor, 2, value=.15, skill_id=skill_id, side_index=side_index, metadata={"rage": True}))
        _add_effect(actor, _effect("rage", actor, 2, skill_id=skill_id, side_index=side_index))
        events.append({"kind": "hp_cost", "target_id": _id(actor), "amount": payment})
    elif skill_id == "blooded_resolve":
        raw = (25 + 2.5 * int(actor.get("vitality", 0))) * rank_multiplier(rank)
        raw *= 1 + min(40, max(0, int(actor.get("healing_power", 0)))) / 100
        amount = min(int(raw), int(actor.get("max_hp", 1) * .25))
        events.append({"kind": "heal", "target_id": _id(actor), "amount": _heal(actor, amount)})
    elif skill_id in {"envenom_blades", "steady_aim", "arcane_surge", "spell_echo"}:
        token = {"envenom_blades": "envenom", "steady_aim": "aim", "arcane_surge": "surge", "spell_echo": "echo"}[skill_id]
        value = _ranked_percent(.25, rank) if token in {"aim", "surge", "echo"} else rank_multiplier(rank)
        _add_effect(actor, _effect(token, actor, 2, value=value, skill_id=skill_id, side_index=side_index))
    elif skill_id == "quick_channel":
        events.append({"kind": "mana", "target_id": _id(actor), "amount": _restore_mana(actor, _ranked(20, rank))})
    elif skill_id in {"heal", "mend_self"}:
        coefficient = 1.0 if skill_id == "heal" else .65
        for target in targets:
            events.append({"kind": "heal", "target_id": _id(target), "amount": _heal(target, h * coefficient)})
    elif skill_id == "regeneration":
        for target in targets:
            _add_effect(target, _effect("regeneration", actor, 3, value=int(h * .35), skill_id=skill_id, side_index=side_index))
    elif skill_id == "cleanse":
        for target in targets:
            removed = _remove_effects(target, {"poison", "bleed", "burn", "weakness"})
            events.append({"kind": "cleanse", "target_id": _id(target), "removed": [item["kind"] for item in removed]})
    elif skill_id == "blessing":
        for target in targets:
            _add_effect(target, _effect("attack_up", actor, 2, value=_ranked_percent(.12, rank), skill_id=skill_id, side_index=side_index))
    elif skill_id == "resurrection":
        for target in targets:
            if not _alive(target) or bool(target.get("death_prevention_used")):
                raise ValueError("covenant_target_invalid")
            _add_effect(target, _effect("life_covenant", actor, 3, value=int(h * .80), skill_id=skill_id, side_index=side_index))
    elif skill_id in {"sacred_shield", "mana_shield", "arcane_shield"}:
        coefficient = {"sacred_shield": .75, "mana_shield": .80, "arcane_shield": .60}[skill_id]
        for target in targets:
            _apply_barrier(target, actor, int(h * coefficient), 2, skill_id, side_index)
    elif skill_id == "guardian_light":
        for target in targets:
            _apply_barrier(target, actor, int(h * .55), 2, skill_id, side_index)
        _add_effect(actor, _effect("ward", actor, 2, value=_ranked_percent(.25, rank), skill_id=skill_id, side_index=side_index))
    elif skill_id == "insight":
        for target in targets:
            events.append({"kind": "mana", "target_id": _id(target), "amount": _restore_mana(target, _ranked(22, rank))})
    elif skill_id == "grand_enchantment":
        for target in targets:
            _add_effect(target, _effect("ward", actor, 2, value=_ranked_percent(.20, rank), skill_id=skill_id, side_index=side_index))
            events.append({
                "kind": "mana",
                "target_id": _id(target),
                "amount": _restore_mana(target, _ranked(14, rank)),
                "skill_id": skill_id,
            })
    else:
        raise ValueError("unsupported_support_skill")


def _skill_context(
    actor: dict[str, Any], target: dict[str, Any], skill_id: str, rank: int,
) -> tuple[float, float, str, dict[str, Any]]:
    """Return base coefficient, penetration, school and named conditions."""
    spec = POWER_STRIKE if skill_id == "power_strike" else SKILL_SPECS[skill_id]
    coefficient = spec.power * rank_multiplier(rank)
    penetration = 0.0
    school = spec.school or str(actor.get("damage_school") or "physical")
    if school == "weapon":
        school = str(actor.get("damage_school") or "physical")
    source = _id(actor)
    flags: dict[str, Any] = {}
    if _has(target, "hunters_mark", source_id=source):
        coefficient *= 1 + _effect_value(target, "hunters_mark", source_id=source)
    if skill_id == "punishing_cut" and _has(target, "exposure"):
        coefficient += _ranked(.55, rank)
    elif skill_id == "vanguard_surge" and _has(target, "exposure"):
        coefficient += _ranked(.40, rank); flags["surge_ward"] = True
    elif skill_id == "cleave_through" and int(target.get("hp", 0)) * 2 <= int(target.get("max_hp", 1)):
        coefficient += _ranked(.30, rank)
    elif skill_id == "executioners_stroke" and int(target.get("hp", 0)) * 100 <= int(target.get("max_hp", 1)) * 35:
        coefficient += _ranked(1.0, rank)
    elif skill_id in {"flowing_combo", "masters_sequence"} and _has(actor, "flow", source_id=source):
        coefficient += _ranked(.65 if skill_id == "flowing_combo" else .55, rank); flags["consume_flow"] = True
        if skill_id == "masters_sequence": flags["masters_ward"] = True
    elif skill_id == "savage_chop" and _has(actor, "rage", source_id=source):
        coefficient += _ranked(.35, rank)
    elif skill_id == "frenzy_chain" and _has(actor, "rage", source_id=source):
        coefficient += _ranked(.70, rank); flags["consume_rage"] = True
    elif skill_id == "last_roar" and int(actor.get("hp", 0)) * 100 <= int(actor.get("max_hp", 1)) * 40:
        coefficient += _ranked(.85, rank)
    elif skill_id == "brutal_overhead":
        penetration = .25
    elif skill_id == "reopen_wounds" and _has(target, "bleed", source_id=source):
        coefficient += _ranked(.45, rank); flags["refresh_bleed"] = True
    elif skill_id == "ravage":
        if _has(target, "bleed", source_id=source): coefficient += _ranked(.40, rank)
        if _has(target, "physical_break"): coefficient += _ranked(.40, rank)
    elif skill_id == "widows_kiss":
        coefficient += _ranked(.23, rank) * min(3, len(_find_effect(target, "poison", source_id=source)))
    elif skill_id == "rupture_toxins":
        flags["rupture_poison"] = True
    elif skill_id in {"quick_slice", "backstab", "shadow_chain"} and _has(actor, "opening", source_id=source):
        coefficient += _ranked({"quick_slice": .35, "backstab": .80, "shadow_chain": .80}[skill_id], rank); flags["consume_opening"] = True
        if skill_id == "shadow_chain": flags["shadow_evasion"] = True
    elif skill_id in {"hunters_mark"}:
        pass
    elif skill_id == "piercing_arrow":
        penetration = .35
    elif skill_id == "deadeye":
        flags["guaranteed_hit"] = True
        if _has(target, "hunters_mark", source_id=source): coefficient += _ranked(.55, rank)
    elif skill_id == "volley_step" and _has(target, "slow"):
        coefficient += _ranked(.50, rank)
    elif skill_id == "rain_of_barbs" and _has(target, "slow"):
        coefficient += _ranked(.20, rank)
    elif skill_id == "arcane_lance":
        penetration = .25
    elif skill_id == "cataclysm" and _find_effect(target, "burn", source_id=source, school="magic"):
        coefficient += _ranked(.40, rank)
    elif skill_id == "shatter" and _has(target, "chilled", source_id=source):
        coefficient += _ranked(.70, rank); flags["consume_chilled"] = True
    elif skill_id == "overload" and _has(actor, "echo", source_id=source):
        coefficient += _ranked(.25, rank); flags["consume_echo"] = True
    elif skill_id == "arcane_barrage" and _has(actor, "echo", source_id=source):
        flags["consume_echo"] = True; flags["barrage_refund"] = True
    elif skill_id in {"counterpulse", "duel_arc"} and _has(actor, "reprisal", source_id=source):
        coefficient += _ranked(.75 if skill_id == "counterpulse" else .70, rank); flags["consume_reprisal"] = True
    elif skill_id in {"sanctified_burst", "halo_of_dawn"} and _has(target, "dawn_mark"):
        coefficient += _ranked(.45 if skill_id == "sanctified_burst" else .25, rank)
    elif skill_id == "aegis_strike" and _has(actor, "barrier"):
        coefficient += _ranked(.45, rank)
    elif skill_id == "radiant_strike" and _has(target, "judgment", source_id=source):
        flags["radiant_heal"] = True
    elif skill_id == "punish_the_wicked" and _has(target, "judgment", source_id=source):
        coefficient += _ranked(.55, rank)
    elif skill_id == "final_verdict" and _has(target, "judgment", source_id=source):
        coefficient += _ranked(.60, rank); flags["verdict"] = True
    elif skill_id == "synthesis":
        if _find_effect(target, "burn", source_id=source, school="magic"): flags["burn_bonus"] = _ranked(.35, rank)
        if _has(actor, "grace", source_id=source): flags["grace_bonus"] = _ranked(.35, rank); flags["consume_grace"] = True
    elif skill_id == "forbidden_thesis":
        if _has(actor, "grace", source_id=source): flags["grace_bonus"] = _ranked(.55, rank); flags["consume_grace"] = True; flags["thesis_heal"] = True
        if _find_effect(target, "burn", source_id=source, school="magic"): flags["consume_burn"] = True
    return coefficient, penetration, school, flags


def _on_hit(
    actor: dict[str, Any],
    allies: list[dict[str, Any]],
    target: dict[str, Any],
    *,
    skill_id: str,
    rank: int,
    base_power: int,
    actual_damage: int,
    flags: dict[str, Any],
    side_index: int,
    events: list[dict[str, Any]],
) -> None:
    source = _id(actor)
    def add(kind: str, duration: int, value: float = 0, school: str | None = None, raw_tick: int | None = None, metadata=None):
        if kind in {"poison", "bleed", "burn"} and not _alive(target):
            return
        effect_metadata = dict(metadata or {})
        if kind in {"poison", "bleed", "burn"}:
            attack_up = min(ATTACK_UP_CAP, _strongest(actor, "attack_up"))
            raw_tick = int(int(raw_tick or 0) * (1 + attack_up))
            effect_metadata.update({
                "source_level": int(actor.get("level", 1)),
                "weakness_snapshot": min(WEAKNESS_CAP, _strongest(actor, "weakness")),
            })
        _add_effect(target, _effect(
            kind, actor, duration, value=value, skill_id=skill_id,
            side_index=side_index, school=school, raw_tick=raw_tick,
            metadata=effect_metadata,
        ))

    if skill_id == "sword_rush": add("challenge", 2, metadata={"challenger_id": source})
    elif skill_id == "shield_bash": add("weakness", 2, _ranked_percent(.20, rank))
    elif skill_id in {"expose_guard", "armor_split"}: add("exposure", 2, _ranked_percent(.15, rank))
    elif skill_id == "driving_slash": _add_effect(actor, _effect("driving", actor, 2, value=.20, skill_id=skill_id, side_index=side_index))
    elif skill_id == "press_the_line": _add_effect(actor, _effect("attack_up", actor, 2, value=_ranked_percent(.15, rank), skill_id=skill_id, side_index=side_index))
    elif flags.get("surge_ward"): _add_effect(actor, _effect("ward", actor, 2, value=_ranked_percent(.20, rank), skill_id=skill_id, side_index=side_index))
    elif skill_id == "twin_cut": _add_effect(actor, _effect("flow", actor, 2, skill_id=skill_id, side_index=side_index))
    elif skill_id == "bleeding_cut": add("bleed", 3, school="physical", raw_tick=int(base_power * _ranked(.20, rank)))
    elif skill_id == "sunder_armor": add("physical_break", 3, .30)
    elif skill_id == "reopen_wounds" and flags.get("refresh_bleed"):
        for bleed in _find_effect(target, "bleed", source_id=source): bleed["duration"] = 3
    elif skill_id == "toxic_cut": add("poison", 3, school="physical", raw_tick=int(base_power * _ranked(.23, rank)))
    elif skill_id == "crippling_venom":
        add("slow", 2); add("weakness", 2, _ranked_percent(.15, rank))
    elif skill_id == "feint_step":
        _add_effect(actor, _effect("accuracy_up", actor, 2, value=int(20 * rank_multiplier(rank)), skill_id=skill_id, side_index=side_index))
        _add_effect(actor, _effect("opening", actor, 2, skill_id=skill_id, side_index=side_index))
    elif skill_id == "hunters_mark": add("hunters_mark", 3, _ranked_percent(.15, rank))
    elif skill_id == "hamstring_arrow": add("slow", 2)
    elif skill_id == "rain_of_barbs": add("slow", 2)
    elif skill_id in {"fireball", "flame_wave"}:
        ratio, duration = ((.15, 2) if skill_id == "fireball" else (.10, 2))
        add("burn", duration, school="magic", raw_tick=int(base_power * _ranked(ratio, rank)))
    elif skill_id == "frost_bolt":
        add("slow", 2); add("chilled", 3)
    elif skill_id == "ice_shackles":
        add("chilled", 3); _apply_hard_control(target, actor, skill_id, side_index, events)
    elif skill_id == "absolute_zero":
        add("slow", 2); add("chilled", 3)
    elif skill_id == "hex_bolt": add("weakness", 2, _ranked_percent(.15, rank))
    elif skill_id == "mana_feint":
        add("slow", 2)
        events.append({"kind": "mana", "target_id": source, "amount": _restore_mana(actor, _ranked(4, rank)), "skill_id": skill_id})
    elif skill_id == "judgment_mark": add("dawn_mark", 3, _ranked_percent(.12, rank))
    elif skill_id == "judgment": add("judgment", 3)
    elif skill_id == "rod_consecration": add("burn", 3, school="holy", raw_tick=int(base_power * _ranked(.20, rank)))
    elif skill_id == "borrowed_flame": add("burn", 3, school="magic", raw_tick=int(base_power * _ranked(.15, rank)))
    elif skill_id == "borrowed_grace":
        events.append({
            "kind": "heal", "actor_id": source, "target_id": source,
            "amount": _heal(actor, healing_power(actor) * _ranked(.35, rank)), "skill_id": skill_id,
        })
        _add_effect(actor, _effect("grace", actor, 2, value=.20, skill_id=skill_id, side_index=side_index))
    if _has(actor, "envenom", source_id=source) and normalize_family(actor.get("family")) == "daggers":
        add("poison", 3, school="physical", raw_tick=int(base_power * .2875 * _effect_value(actor, "envenom", source_id=source)))
        _remove_effects(actor, {"envenom"}, source_id=source)

    if flags.get("masters_ward"):
        _add_effect(actor, _effect("ward", actor, 1, value=_ranked_percent(.25, rank), skill_id=skill_id, side_index=side_index))
    if flags.get("shadow_evasion"):
        _add_effect(actor, _effect("evasion_up", actor, 1, value=int(40 * rank_multiplier(rank)), skill_id=skill_id, side_index=side_index))

    for kind in ("flow", "rage", "opening", "echo", "reprisal", "grace"):
        if flags.get(f"consume_{kind}"):
            _remove_effects(actor, {kind}, source_id=source)
    if flags.get("consume_chilled"):
        _remove_effects(target, {"chilled"}, source_id=source)
    if flags.get("consume_rage"):
        _remove_effects(actor, {"rage", "received_damage_up"}, source_id=source)
        actor["effects"] = [effect for effect in _effects(actor) if not (effect.get("kind") == "attack_up" and effect.get("metadata", {}).get("rage"))]
    if flags.get("consume_opening"):
        _remove_effects(actor, {"opening"}, source_id=source)
    if flags.get("rupture_poison"):
        poisons = _find_effect(target, "poison", source_id=source)
        packets = [
            (
                int(item.get("raw_tick", 0)) * int(item.get("duration", 0)),
                int(item.get("metadata", {}).get("source_level", actor.get("level", 1))),
                float(item.get("metadata", {}).get("weakness_snapshot", 0)),
            )
            for item in poisons
        ]
        _remove_effects(target, {"poison"}, source_id=source)
        budget = sum(item[0] for item in packets)
        if budget and _alive(target):
            weighted_weakness = sum(raw * weakness for raw, _, weakness in packets) / budget
            source_level = max((level for _, level, _ in packets), default=int(actor.get("level", 1)))
            result = _apply_periodic_damage(
                target, raw=int(budget * .92), school="poison",
                source_level=source_level, weakness=weighted_weakness,
            )
            events.append({"kind": "poison_rupture", "actor_id": source, "source_id": source, "target_id": _id(target), **result})
    if flags.get("consume_burn"):
        burns = _find_effect(target, "burn", source_id=source, school="magic")
        packets = [
            (
                int(item.get("raw_tick", 0)) * int(item.get("duration", 0)),
                int(item.get("metadata", {}).get("source_level", actor.get("level", 1))),
                float(item.get("metadata", {}).get("weakness_snapshot", 0)),
            )
            for item in burns
        ]
        for burn in burns: _effects(target).remove(burn)
        budget = sum(item[0] for item in packets)
        if budget and _alive(target):
            weighted_weakness = sum(raw * weakness for raw, _, weakness in packets) / budget
            source_level = max((level for _, level, _ in packets), default=int(actor.get("level", 1)))
            result = _apply_periodic_damage(
                target, raw=int(budget * .60), school="magic",
                source_level=source_level, weakness=weighted_weakness,
            )
            events.append({"kind": "burn_consumed", "actor_id": source, "source_id": source, "target_id": _id(target), **result})
    if flags.get("barrage_refund"):
        events.append({"kind": "mana", "target_id": source, "amount": _restore_mana(actor, _ranked(8, rank))})
    heal_factor = 1 + min(40, max(0, int(actor.get("healing_power", 0)))) / 100
    if skill_id == "last_roar":
        events.append({"kind": "heal", "actor_id": source, "target_id": source, "amount": _heal(actor, min(int(actual_damage * .15 * heal_factor), int(actor.get("max_hp", 1) * .12))), "skill_id": skill_id})
    if skill_id == "smite":
        events.append({"kind": "heal", "actor_id": source, "target_id": source, "amount": _heal(actor, min(int(actual_damage * .15 * heal_factor), int(actor.get("max_hp", 1) * .08))), "skill_id": skill_id})
    if flags.get("radiant_heal"):
        events.append({"kind": "heal", "actor_id": source, "target_id": source, "amount": _heal(actor, min(int(actual_damage * .20 * heal_factor), int(actor.get("max_hp", 1) * .10))), "skill_id": skill_id})
    if flags.get("verdict"):
        events.append({"kind": "heal", "actor_id": source, "target_id": source, "amount": _heal(actor, min(int(actual_damage * .25 * heal_factor), int(actor.get("max_hp", 1) * .18))), "skill_id": skill_id})
        _remove_effects(target, {"judgment"}, source_id=source)
    if flags.get("thesis_heal"):
        events.append({"kind": "heal", "actor_id": source, "target_id": source, "amount": _heal(actor, healing_power(actor) * _ranked(.35, rank)), "skill_id": skill_id})
    if skill_id == "duel_arc" and flags.get("consume_reprisal"):
        _apply_barrier(actor, actor, int(healing_power(actor) * _ranked(.45, rank)), 2, skill_id, side_index)


def _apply_hard_control(target, actor, skill_id, side_index, events):
    if _has(target, "resolve"):
        events.append({"kind": "control_rejected", "target_id": _id(target), "reason": "resolve"})
        return
    _add_effect(target, _effect("freeze", actor, 1, skill_id=skill_id, side_index=side_index))


def _resolve_guard(actor: dict[str, Any], *, side_index: int, timeout: bool, events: list[dict[str, Any]]) -> None:
    _add_effect(actor, _effect("guard", actor, 1, value=.20, skill_id="timeout_guard" if timeout else "guard", side_index=side_index))
    events.append({"kind": "guard", "actor_id": _id(actor), "timeout": timeout, "ward": .20})


def evaluate_action(
    actor_snapshot: dict[str, Any],
    ally_snapshots: list[dict[str, Any]],
    opponent_snapshots: list[dict[str, Any]],
    action: dict[str, Any],
    *,
    rng_seed: int | str,
    side_index: int = 0,
) -> dict[str, Any]:
    """Resolve one committed main opportunity without performing any I/O."""
    actor = copy.deepcopy(actor_snapshot)
    allies = copy.deepcopy(ally_snapshots)
    opponents = copy.deepcopy(opponent_snapshots)
    actor_id = _id(actor)
    # Replace the ally copy of the actor with the canonical mutable object.
    replaced = False
    for index, ally in enumerate(allies):
        if _id(ally) == actor_id:
            allies[index] = actor
            replaced = True
            break
    if not replaced:
        allies.insert(0, actor)
    actor.setdefault("effects", [])
    actor.setdefault("cooldowns", {})
    actor.setdefault("opportunity_index", 0)
    events: list[dict[str, Any]] = []
    rng = random.Random(rng_seed)
    action_kind = str(action.get("kind") or "normal")
    manual = bool(action.get("manual", True))
    timeout = action_kind == "timeout_guard"
    cast_index = int(actor.get("opportunity_index", 0))

    if not _alive(actor):
        return {"accepted": False, "reason": "actor_dead", "actor": actor, "allies": allies, "opponents": opponents, "events": events}

    freezes = _find_effect(actor, "freeze")
    if freezes:
        _effects(actor).remove(freezes[0])
        _add_effect(actor, _effect("resolve", actor, 2, skill_id="resolve", side_index=side_index))
        actor["opportunity_index"] = cast_index + 1
        events.append({"kind": "controlled_skip", "actor_id": actor_id})
        return {"accepted": True, "skipped": True, "actor": actor, "allies": allies, "opponents": opponents, "events": events}

    if action_kind in {"guard", "timeout_guard"}:
        _resolve_guard(actor, side_index=side_index, timeout=timeout, events=events)
        actor["opportunity_index"] = cast_index + 1
        if manual and not timeout:
            actor["manual_contribution"] = True
        return {"accepted": True, "actor": actor, "allies": allies, "opponents": opponents, "events": events}

    if action_kind == "flee_failed":
        actor["opportunity_index"] = cast_index + 1
        actor["manual_contribution"] = True
        events.append({"kind": "flee_failed", "actor_id": actor_id})
        return {"accepted": True, "actor": actor, "allies": allies, "opponents": opponents, "events": events}

    skill_id = str(action.get("skill_id") or "") if action_kind == "skill" else ""
    rank = 1
    target_code = "S"
    mana_cost = 0
    cooldown = 0
    school = str(actor.get("damage_school") or "physical")
    coefficient = 1.0
    spec = None
    if action_kind == "skill":
        if skill_id == "power_strike":
            spec = POWER_STRIKE
            rank = 1
        else:
            spec = SKILL_SPECS.get(skill_id)
            rank = int(actor.get("skill_ranks", {}).get(skill_id, 0))
            if not spec or spec.family != normalize_family(actor.get("family")) or rank < 1:
                return {"accepted": False, "reason": "skill_not_learned", "actor": actor, "allies": allies, "opponents": opponents, "events": events}
        if spec.passive:
            return {"accepted": False, "reason": "passive_skill", "actor": actor, "allies": allies, "opponents": opponents, "events": events}
        target_code = spec.target
        mana_cost = rank_mana_cost(spec, rank)
        cooldown = int(spec.cooldown or 0)
        ready_at = int(actor["cooldowns"].get(skill_id, 0))
        if ready_at > cast_index:
            return {"accepted": False, "reason": "cooldown", "remaining": ready_at - cast_index, "actor": actor, "allies": allies, "opponents": opponents, "events": events}
        if int(actor.get("mana", 0)) < mana_cost:
            return {"accepted": False, "reason": "mana", "required": mana_cost, "actor": actor, "allies": allies, "opponents": opponents, "events": events}
    elif action_kind != "normal":
        return {"accepted": False, "reason": "unknown_action", "actor": actor, "allies": allies, "opponents": opponents, "events": events}

    targets = select_targets(target_code, actor, allies, opponents, action.get("target_id"))
    if not targets:
        # A target that was legal at commit but died resolves as cost-free Guard.
        _resolve_guard(actor, side_index=side_index, timeout=False, events=events)
        actor["opportunity_index"] = cast_index + 1
        if manual:
            actor["manual_contribution"] = True
        events.append({"kind": "target_lost_fallback", "skill_id": skill_id or None})
        return {"accepted": True, "fallback": "guard", "actor": actor, "allies": allies, "opponents": opponents, "events": events}

    if action_kind == "skill":
        actor["mana"] = int(actor.get("mana", 0)) - mana_cost
        actor["cooldowns"][skill_id] = cast_index + cooldown
    support_kind = spec.kind if spec else "damage"
    if action_kind == "skill" and support_kind not in {"damage", "poison", "hostile_effect", "dispel"}:
        try:
            _apply_skill_support(actor, allies, targets, skill_id=skill_id, rank=rank, side_index=side_index, events=events)
        except ValueError as exc:
            # Legality should normally be caught before commit.  Keep this pure
            # failure explicit for callers that bypass prevalidation.
            return {"accepted": False, "reason": str(exc), "actor": actor_snapshot, "allies": ally_snapshots, "opponents": opponent_snapshots, "events": []}
    else:
        weapon_roll = rng.randint(int(actor.get("weapon_min", 5)), int(actor.get("weapon_max", 5)))
        base_low, _ = raw_power_range({**actor, "weapon_min": weapon_roll, "weapon_max": weapon_roll})
        setup_bonus, setup_consumptions = _setup_bonus(actor, skill_id, action_kind)
        context_actor = copy.deepcopy(actor)
        hit_any = False
        landed_target_ids: set[str] = set()
        deferred_retaliations: list[tuple[dict[str, Any], dict[str, Any], list[tuple[str, float]]]] = []
        damaged_targets = []
        opponent_ids = {_id(item) for item in opponents}
        for target in targets:
            target_coefficient = coefficient
            penetration = 0.0
            flags: dict[str, Any] = {}
            target_school = school
            if spec:
                target_coefficient, penetration, target_school, flags = _skill_context(context_actor, target, skill_id, rank)
            if action_kind == "normal":
                target_coefficient = 1.0
                if _has(target, "hunters_mark", source_id=actor_id):
                    target_coefficient *= 1 + _effect_value(target, "hunters_mark", source_id=actor_id)
                if _has(target, "judgment", source_id=actor_id) and normalize_family(actor.get("family")) == "holy_rod":
                    target_coefficient += _ranked(.15, max(1, int(actor.get("skill_ranks", {}).get("judgment", 1))))
                    flags["judgment_normal"] = True
            target_coefficient *= 1 + min(ATTACK_UP_CAP, _strongest(actor, "attack_up"))
            target_coefficient *= 1 + setup_bonus
            accuracy_bonus = 20 if skill_id in {"aimed_shot", "steady_aim"} or _has(actor, "aim") else 0
            ally_dispel = skill_id == "dispel_script" and _id(target) not in opponent_ids
            chance = None if ally_dispel else (100 if flags.get("guaranteed_hit") else hit_chance(actor, target, accuracy_bonus=accuracy_bonus))
            roll = None if ally_dispel else rng.randint(1, 100)
            landed = True if ally_dispel else bool(roll <= chance)
            event = {"kind": "direct", "actor_id": actor_id, "target_id": _id(target), "skill_id": skill_id or "normal", "hit_chance": chance, "hit_roll": roll, "hit": landed}
            if landed:
                hit_any = True
                landed_target_ids.add(_id(target))
                defensive_active_before = bool(_find_effect(target, "parry") or _find_effect(target, "ward") or _find_effect(target, "guard"))
                duel_window_before = any(bool(item.get("metadata", {}).get("duel")) for item in _find_effect(target, "ward"))
                if support_kind == "hostile_effect":
                    if skill_id == "hunters_mark":
                        _add_effect(target, _effect("hunters_mark", actor, 3, value=_ranked_percent(.15, rank), skill_id=skill_id, side_index=side_index))
                    elif skill_id == "weaken":
                        _add_effect(target, _effect("weakness", actor, 2, value=_ranked_percent(.20, rank), skill_id=skill_id, side_index=side_index))
                    event["hp_removed"] = 0
                elif skill_id == "dispel_script":
                    if _id(target) in opponent_ids:
                        removed = _remove_effects(target, {"ward", "guard", "barrier", "attack_up"})
                    else:
                        removed = _remove_effects(target, {"weakness", "slow", "exposure", "dawn_mark"})
                    event["removed"] = [item["kind"] for item in removed]
                    event["hp_removed"] = 0
                elif target_school == "mixed":
                    extra_magic = float(flags.get("burn_bonus", 0))
                    extra_holy = float(flags.get("grace_bonus", 0))
                    result = _apply_mixed_direct_damage(
                        actor, target,
                        magic_raw=max(1, int(base_low * (target_coefficient / 2 + extra_magic))),
                        holy_raw=max(1, int(base_low * (target_coefficient / 2 + extra_holy))),
                        rng=rng,
                    )
                    event.update(result)
                    damaged_targets.append(target)
                    _resolve_defensive_triggers(
                        target, actor, result,
                        defensive_active_before=defensive_active_before,
                        duel_window_before=duel_window_before,
                        side_index=side_index, rng=rng, events=events, deferred=deferred_retaliations,
                    )
                    _on_hit(actor, allies, target, skill_id=skill_id, rank=rank, base_power=base_low, actual_damage=result["hp_removed"], flags=flags, side_index=side_index, events=events)
                else:
                    raw = max(1, int(base_low * target_coefficient))
                    result = _apply_direct_damage(actor, target, raw=raw, school=target_school, penetration=penetration, rng=rng)
                    event.update(result)
                    damaged_targets.append(target)
                    _resolve_defensive_triggers(
                        target, actor, result,
                        defensive_active_before=defensive_active_before,
                        duel_window_before=duel_window_before,
                        side_index=side_index, rng=rng, events=events, deferred=deferred_retaliations,
                    )
                    if action_kind in {"skill", "normal"}:
                        _on_hit(actor, allies, target, skill_id=skill_id or "normal", rank=rank, base_power=base_low, actual_damage=result["hp_removed"], flags=flags, side_index=side_index, events=events)
                    if flags.get("judgment_normal"):
                        events.append({
                            "kind": "heal", "actor_id": actor_id,
                            "target_id": actor_id,
                            "amount": _heal(
                                actor,
                                min(
                                    int(result["hp_removed"] * .10),
                                    int(actor.get("max_hp", 1) * .05),
                                ),
                            ),
                            "skill_id": "judgment",
                        })
            events.append(event)
        if hit_any:
            for token in setup_consumptions:
                _remove_effects(actor, {token}, source_id=actor_id)
        if skill_id == "absolute_zero" and hit_any:
            selected_id = str(action.get("target_id")) if action.get("target_id") is not None else _id(targets[0])
            active_target = next((target for target in targets if _id(target) == selected_id), None)
            if active_target is not None and selected_id in landed_target_ids:
                _apply_hard_control(active_target, actor, skill_id, side_index, events)
        if skill_id == "sanctified_burst" and hit_any:
            living = [ally for ally in allies if _alive(ally)]
            if living:
                lowest = min(enumerate(living), key=lambda pair: (int(pair[1]["hp"]) / max(1, int(pair[1]["max_hp"])), pair[0]))[1]
                events.append({"kind": "heal", "target_id": _id(lowest), "amount": _heal(lowest, healing_power(actor) * _ranked(.25, rank))})
        if skill_id == "halo_of_dawn" and hit_any:
            for ally in allies:
                if _alive(ally):
                    events.append({"kind": "heal", "target_id": _id(ally), "amount": _heal(ally, healing_power(actor) * _ranked(.25, rank))})
        for defender, retaliation_target, coefficients in deferred_retaliations:
            _apply_retaliations(defender, retaliation_target, coefficients, rng=rng, events=events)
    if action_kind == "normal":
        restored = _restore_mana(actor, 6)
        events.append({"kind": "mana", "target_id": actor_id, "amount": restored, "source": "normal"})
        if hit_any and _has(actor, "battle_stance", source_id=actor_id):
            _add_effect(actor, _effect("flow", actor, 2, skill_id="battle_stance", side_index=side_index))
    actor["opportunity_index"] = cast_index + 1
    if manual:
        actor["manual_contribution"] = True
    return {
        "accepted": True,
        "rules_version": RULES_VERSION,
        "actor": actor,
        "allies": allies,
        "opponents": opponents,
        "events": events,
    }


def _frontmost_player_target(enemy: dict[str, Any], players: list[dict[str, Any]]) -> dict[str, Any] | None:
    living = [player for player in players if _alive(player)]
    if not living:
        return None
    challenges = _find_effect(enemy, "challenge")
    if challenges:
        challenger = str(challenges[-1].get("metadata", {}).get("challenger_id", ""))
        chosen = next((player for player in living if _id(player) == challenger), None)
        if chosen:
            return chosen
    return min(enumerate(living), key=lambda pair: (_formation_rank(pair[1].get("formation", "melee")), pair[0]))[1]


def evaluate_enemy_action(
    enemy_snapshot: dict[str, Any],
    enemy_allies: list[dict[str, Any]],
    player_snapshots: list[dict[str, Any]],
    action: dict[str, Any],
    *,
    rng_seed: int | str,
    side_index: int = 0,
) -> dict[str, Any]:
    """Resolve explicit deterministic enemy-profile actions through G2."""
    enemy = copy.deepcopy(enemy_snapshot)
    allies = copy.deepcopy(enemy_allies)
    players = copy.deepcopy(player_snapshots)
    for index, ally in enumerate(allies):
        if _id(ally) == _id(enemy):
            allies[index] = enemy
            break
    rng = random.Random(rng_seed)
    events: list[dict[str, Any]] = []
    opportunity = int(enemy.get("opportunity_index", 0))
    ai_action_index = int(enemy.get("ai_action_index", 0))
    freezes = _find_effect(enemy, "freeze")
    if freezes:
        _effects(enemy).remove(freezes[0])
        _add_effect(enemy, _effect("resolve", enemy, 2, skill_id="resolve", side_index=side_index))
        enemy["opportunity_index"] = opportunity + 1
        return {"accepted": True, "skipped": True, "enemy": enemy, "allies": allies, "players": players, "events": [{"kind": "controlled_skip", "actor_id": _id(enemy)}]}
    kind = str(action.get("kind") or "enemy_attack")
    if kind == "enemy_ward":
        _add_effect(enemy, _effect("ward", enemy, int(action.get("duration", 2)), value=min(WARD_CAP, float(action.get("value", .20))), skill_id="enemy_ward", side_index=side_index))
        events.append({"kind": "enemy_ward", "actor_id": _id(enemy), "value": float(action.get("value", .20))})
    elif kind == "enemy_heal":
        target_id = str(action.get("target_id") or "")
        target = next((ally for ally in allies if _id(ally) == target_id and _alive(ally)), enemy)
        amount = int(target.get("max_hp", 1) * float(action.get("fraction", .20)))
        events.append({"kind": "enemy_heal", "actor_id": _id(enemy), "target_id": _id(target), "amount": _heal(target, amount)})
    else:
        target = _frontmost_player_target(enemy, players)
        if not target:
            return {"accepted": False, "reason": "no_target", "enemy": enemy, "allies": allies, "players": players, "events": events}
        if kind == "enemy_weakness":
            chance = hit_chance(enemy, target)
            roll = rng.randint(1, 100)
            landed = roll <= chance
            if landed:
                _add_effect(target, _effect("weakness", enemy, int(action.get("duration", 2)), value=float(action.get("value", .20)), skill_id="enemy_weakness", side_index=side_index))
            events.append({"kind": "enemy_weakness", "actor_id": _id(enemy), "target_id": _id(target), "hit": landed, "hit_chance": chance, "hit_roll": roll})
        else:
            intercepts = _find_effect(target, "intercept")
            if intercepts:
                protector_id = str(intercepts[0].get("metadata", {}).get("protector_id", ""))
                protector = next((player for player in players if _id(player) == protector_id and _alive(player)), None)
                if protector:
                    _effects(target).remove(intercepts[0])
                    events.append({"kind": "intercept", "from_id": _id(target), "target_id": _id(protector)})
                    target = protector
            chance = hit_chance(enemy, target)
            roll = rng.randint(1, 100)
            landed = roll <= chance
            direct_event = {"kind": "enemy_direct", "actor_id": _id(enemy), "target_id": _id(target), "hit": landed, "hit_chance": chance, "hit_roll": roll, "behavior": action.get("behavior")}
            if landed:
                raw_roll = rng.randint(int(enemy.get("weapon_min", 1)), int(enemy.get("weapon_max", 1)))
                raw = max(1, int(raw_roll * float(action.get("coefficient", 1.0))))
                defensive = bool(_find_effect(target, "parry") or _find_effect(target, "ward") or _find_effect(target, "guard"))
                duel = any(bool(item.get("metadata", {}).get("duel")) for item in _find_effect(target, "ward"))
                packet = _apply_direct_damage(enemy, target, raw=raw, school=str(enemy.get("damage_school") or "physical"), penetration=0, rng=rng)
                direct_event.update(packet)
                _resolve_defensive_triggers(target, enemy, packet, defensive_active_before=defensive, duel_window_before=duel, side_index=side_index, rng=rng, events=events)
                enemy["successful_attacks"] = int(enemy.get("successful_attacks", 0)) + 1
                successful = int(enemy["successful_attacks"])
                if successful % 3 == 0:
                    if "venom_third_hit" in enemy.get("on_hit_behaviors", []) and _alive(target):
                        _add_effect(target, _effect("poison", enemy, 3, skill_id="enemy_venom", side_index=side_index, school="physical", raw_tick=max(1, int(raw * .15)), metadata={"source_level": int(enemy.get("level", 1))}))
                        events.append({"kind": "enemy_poison", "target_id": _id(target), "raw_tick": max(1, int(raw * .15))})
                    if "leech_third_hit" in enemy.get("on_hit_behaviors", []):
                        events.append({"kind": "enemy_leech", "actor_id": _id(enemy), "amount": _heal(enemy, int(packet["hp_removed"] * .20))})
                    if str(enemy.get("behavior")) == "fire_elemental" and _alive(target):
                        _add_effect(target, _effect("burn", enemy, 2, skill_id="enemy_fire", side_index=side_index, school="magic", raw_tick=max(1, int(raw * .15)), metadata={"source_level": int(enemy.get("level", 1))}))
                        events.append({"kind": "enemy_burn", "target_id": _id(target), "raw_tick": max(1, int(raw * .15))})
            events.append(direct_event)
    enemy["opportunity_index"] = opportunity + 1
    enemy["ai_action_index"] = ai_action_index + 1
    from game.enemy_profiles import next_enemy_intent
    intent = next_enemy_intent(enemy)
    enemy["heavy_intent"] = bool(intent)
    if intent:
        target = _frontmost_player_target(enemy, players)
        events.append({"kind": "enemy_intent", "actor_id": _id(enemy), "target_id": _id(target) if target else None, **intent})
    return {"accepted": True, "rules_version": RULES_VERSION, "enemy": enemy, "allies": allies, "players": players, "events": events}


def advance_affected_side(
    entities: list[dict[str, Any]],
    *,
    side_index: int,
) -> dict[str, Any]:
    """Apply one end-of-affected-side tick and duration decrement."""
    state = copy.deepcopy(entities)
    events: list[dict[str, Any]] = []
    for target in state:
        if not _alive(target):
            continue
        for effect in list(_effects(target)):
            if int(effect.get("created_side_index", -1)) == int(side_index):
                continue
            kind = str(effect.get("kind"))
            if kind in {"poison", "bleed", "burn"}:
                raw = int(effect.get("raw_tick", 0))
                source_level = int(effect.get("metadata", {}).get("source_level", 1))
                weakness = float(effect.get("metadata", {}).get("weakness_snapshot", 0))
                school = str(effect.get("school") or ("physical" if kind in {"poison", "bleed"} else "magic"))
                packet = _apply_periodic_damage(
                    target, raw=raw, school=school,
                    source_level=source_level, weakness=weakness,
                )
                events.append({
                    "kind": "dot", "effect": kind, "target_id": _id(target),
                    "amount": packet["hp_removed"], "source_id": effect.get("source_id"),
                    **packet,
                })
            elif kind == "regeneration":
                amount = _heal(target, effect.get("value", 0))
                events.append({"kind": "hot", "effect": kind, "target_id": _id(target), "amount": amount, "source_id": effect.get("source_id")})
            effect["duration"] = int(effect.get("duration", 1)) - 1
            if effect["duration"] <= 0 and effect in _effects(target):
                _effects(target).remove(effect)
            if not _alive(target):
                break
    return {"entities": state, "events": events}


def cooldown_remaining(actor: dict[str, Any], skill_id: str) -> int:
    return max(0, int(actor.get("cooldowns", {}).get(skill_id, 0)) - int(actor.get("opportunity_index", 0)))


def legal_actions(actor: dict[str, Any], *, pvp: bool = False) -> list[str]:
    from game.build_contract import PVP_SKILL_ALLOWLIST

    result = ["normal", "guard", "power_strike"]
    for skill_id, rank in actor.get("skill_ranks", {}).items():
        spec = SKILL_SPECS.get(skill_id)
        if not spec or spec.passive or int(rank) < 1 or spec.family != normalize_family(actor.get("family")):
            continue
        if pvp and skill_id not in PVP_SKILL_ALLOWLIST:
            continue
        result.append(skill_id)
    return result
