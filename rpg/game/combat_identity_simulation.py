"""Production-aligned Character Builds V1 simulation and balance evidence.

This module intentionally does not call the legacy ``game.combat`` simulator.
It creates legal laboratory snapshots from obtainable Field Equipment V1 and
drives the same pure actor/enemy evaluators used by live PvE and supported PvP.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from typing import Any, Iterable

from game.actor_state import finalize_actor_snapshot, raw_power_range
from game.balance import (
    PROFILE_PRIMARY_SCALING,
    PROFILE_SECONDARY_SCALING,
    calc_magic_defense,
    calc_max_hp,
    calc_max_mana,
    calc_physical_defense,
)
from game.build_contract import (
    BRANCH_IDENTITIES,
    FAMILIES,
    RULES_VERSION, MAX_SKILL_RANK,
    RANK_REQUIREMENTS,
    SKILL_SPECS,
    SKILL_TREES,
    legal_family_budget,
    rank_mana_cost,
)
from game.combat_identity import (
    advance_affected_side,
    combat_seed,
    cooldown_remaining,
    evaluate_action,
    evaluate_enemy_action,
    preview_damage_range,
)
from game.enemy_profiles import MIXED_ENCOUNTERS, choose_enemy_action, resolve_enemy_snapshot
from game.field_catalog import FIELD_ITEMS
from game.mobs import get_mob
from game.targeting import resolve_default_player_formation_line


LAB_LEVEL = 6
LAB_MASTERY = 8
LAB_GEAR_TIER = 1
LAB_RARITY = 'common'
MAX_OPPORTUNITIES = 100
PAIR_SEEDS = tuple(range(200))
PROGRESSION_SEEDS = tuple(range(20))

FAMILY_ARMOR = {
    'sword_1h': 'heavy', 'sword_2h': 'heavy', 'axe_2h': 'heavy',
    'daggers': 'medium', 'bow': 'medium', 'magic_staff': 'light',
    'wand': 'light', 'holy_staff': 'light', 'holy_rod': 'medium', 'tome': 'light',
}
FAMILY_OFFHAND = {
    'sword_1h': 'field_shield', 'magic_staff': 'field_focus', 'wand': 'field_focus',
    'holy_staff': 'field_censer', 'holy_rod': 'field_shield', 'tome': 'field_censer',
}
FAMILY_PRESET = {
    'sword_1h': 'survival', 'holy_staff': 'resource', 'holy_rod': 'resource',
    'tome': 'resource',
}
PRESET_WEIGHTS = {
    'offense': (60, 25, 15),
    'survival': (40, 45, 15),
    'resource': (45, 25, 30),
}

# These rotations contain only frozen canonical IDs. The policy still checks
# visible target state, costs and cooldowns before committing an action.
BRANCH_ROTATIONS = {
    'guardian': ('sword_rush', 'defensive_stance', 'shield_bash', 'parry'),
    'vanguard': ('expose_guard', 'driving_slash', 'press_the_line', 'punishing_cut', 'vanguard_surge'),
    'executioner': ('armor_split', 'cleave_through', 'executioners_focus', 'heavy_swing', 'executioners_stroke'),
    'blademaster': ('battle_stance', 'flowing_combo', 'riposte_step', 'masters_sequence', 'twin_cut'),
    'berserker': ('rage_call', 'frenzy_chain', 'last_roar', 'savage_chop', 'blooded_resolve'),
    'ravager': ('bleeding_cut', 'sunder_armor', 'reopen_wounds', 'brutal_overhead', 'ravage'),
    'venom': ('envenom_blades', 'toxic_cut', 'widows_kiss', 'rupture_toxins', 'crippling_venom'),
    'shadow': ('smoke_bomb', 'backstab', 'feint_step', 'shadow_chain', 'quick_slice'),
    'sniper': ('hunters_mark', 'steady_aim', 'aimed_shot', 'piercing_arrow', 'deadeye'),
    'ranger': ('hamstring_arrow', 'volley_step', 'rain_of_barbs', 'reposition', 'quick_shot'),
    'destruction': ('arcane_surge', 'fireball', 'flame_wave', 'arcane_lance', 'cataclysm'),
    'control': ('frost_bolt', 'ice_shackles', 'mana_shield', 'shatter', 'absolute_zero'),
    'arcanist': ('spell_echo', 'arcane_bolt', 'quick_channel', 'overload', 'arcane_barrage'),
    'duelist': ('dueling_ward', 'hex_bolt', 'mana_feint', 'counterpulse', 'duel_arc'),
    'healer': ('resurrection', 'regeneration', 'heal', 'cleanse', 'blessing'),
    'dawn': ('judgment_mark', 'radiant_ward', 'smite', 'sanctified_burst', 'halo_of_dawn'),
    'protector': ('aura_of_resolve', 'sacred_shield', 'guardian_light', 'mend_self', 'aegis_strike'),
    'judgment': ('judgment', 'rod_consecration', 'radiant_strike', 'punish_the_wicked', 'final_verdict'),
    'enchanter': ('arcane_shield', 'weaken', 'insight', 'dispel_script', 'grand_enchantment'),
    'synthesis': ('borrowed_flame', 'borrowed_grace', 'hybrid_missile', 'synthesis', 'forbidden_thesis'),
}


def _largest_remainder(total: int, weighted_stats: list[tuple[str, int]]) -> dict[str, int]:
    combined: dict[str, int] = {}
    for stat, weight in weighted_stats:
        combined[stat] = combined.get(stat, 0) + int(weight)
    weight_total = sum(combined.values())
    raw = {stat: total * weight / weight_total for stat, weight in combined.items()}
    result = {stat: int(value) for stat, value in raw.items()}
    remainder = total - sum(result.values())
    order = ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck')
    ranked = sorted(combined, key=lambda stat: (-(raw[stat] - result[stat]), order.index(stat)))
    for stat in ranked[:remainder]:
        result[stat] += 1
    return result


def legal_attribute_allocation(family: str, *, level: int, preset: str) -> dict[str, int]:
    """Apply the frozen initial requirement, then J3's named distribution."""
    primary = PROFILE_PRIMARY_SCALING[family][0]
    total_points = 6 + 3 * (max(1, int(level)) - 1)
    attributes = {key: 1 for key in ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck')}
    requirement_points = max(0, 3 - attributes[primary])
    attributes[primary] += requirement_points
    remaining = total_points - requirement_points
    primary_weight, vitality_weight, wisdom_weight = PRESET_WEIGHTS[preset]
    distributed = _largest_remainder(
        remaining,
        [(primary, primary_weight), ('vitality', vitality_weight), ('wisdom', wisdom_weight)],
    )
    for stat, points in distributed.items():
        attributes[stat] += points
    return attributes


def legal_branch_ranks(family: str, branch: str, mastery_level: int) -> dict[str, int]:
    skills = list(SKILL_TREES[family][branch])
    mastery_level = int(mastery_level)
    if mastery_level >= 14:
        ranks = {skill_id: 3 for skill_id in skills}
    elif mastery_level >= 8:
        ranks = {skill_id: (1 if index == 4 else 2) for index, skill_id in enumerate(skills)}
    else:
        ranks = {
            skill_id: 1
            for index, skill_id in enumerate(skills)
            if SKILL_SPECS[skill_id].unlock_mastery <= mastery_level
        }
    assert sum(ranks.values()) <= legal_family_budget(mastery_level)
    return ranks


def _gear_loadout(family: str, gear_set: str) -> tuple[dict[str, dict[str, Any]], dict[str, int], int]:
    item_ids = [f'field_{family}']
    if gear_set == 'common_t1_full':
        armor_class = FAMILY_ARMOR[family]
        item_ids.extend(f'field_{armor_class}_{slot}' for slot in ('helmet', 'chest', 'legs', 'boots', 'gloves'))
        if family in FAMILY_OFFHAND:
            item_ids.append(FAMILY_OFFHAND[family])
    elif gear_set != 'entry_weapon_only':
        raise ValueError('unknown_gear_set')
    equipment: dict[str, dict[str, Any]] = {}
    bonuses: dict[str, int] = Counter()
    total_cost = 0
    for item_id in item_ids:
        item = dict(FIELD_ITEMS[item_id])
        slot = str(item.get('slot_identity') or 'weapon')
        equipment[slot] = item
        total_cost += int(item.get('buy_price', 0) or 0)
        bonuses['physical_defense'] += int(item.get('defense', 0) or 0)
        for key, value in json.loads(item.get('stat_bonus_json') or '{}').items():
            bonuses[str(key)] += int(value)
    return equipment, dict(bonuses), total_cost


def build_legal_lab_actor(
    family: str, branch: str, *, actor_id: int = 1, level: int = LAB_LEVEL,
    mastery_level: int = LAB_MASTERY, preset: str | None = None,
    gear_set: str = 'common_t1_full', cross_branch_mix: bool = False,
    attribute_swap_to: str | None = None,
) -> dict[str, Any]:
    """Build a legal common-T1 snapshot with explicit provenance and budgets."""
    if family not in FAMILIES or branch not in {'A', 'B'}:
        raise ValueError('unknown_build')
    preset = preset or FAMILY_PRESET.get(family, 'offense')
    base_attributes = legal_attribute_allocation(family, level=level, preset=preset)
    attribute_swap_points = 0
    if attribute_swap_to:
        primary = PROFILE_PRIMARY_SCALING[family][0]
        attribute_swap_points = min(15, max(0, base_attributes[primary] - 3))
        base_attributes[primary] -= attribute_swap_points
        base_attributes[attribute_swap_to] += attribute_swap_points
    equipment, bonuses, total_cost = _gear_loadout(family, gear_set)
    attributes = {
        stat: int(value) + int(bonuses.get(stat, 0))
        for stat, value in base_attributes.items()
    }
    weapon = equipment['weapon']
    offhand = equipment.get('offhand') or {}
    max_hp = calc_max_hp(attributes['vitality']) + int(bonuses.get('max_hp', 0))
    max_mana = calc_max_mana(attributes['wisdom']) + int(bonuses.get('max_mana', 0))
    ranks = legal_branch_ranks(family, branch, mastery_level)
    if cross_branch_mix:
        if mastery_level < 20:
            raise ValueError('cross_branch_mix_requires_m20')
        sibling = 'B' if branch == 'A' else 'A'
        sibling_skills = SKILL_TREES[family][sibling]
        ranks.update({sibling_skills[0]: 3, sibling_skills[1]: 1, sibling_skills[2]: 1, sibling_skills[3]: 1})
    if sum(ranks.values()) > legal_family_budget(mastery_level):
        raise ValueError('skill_budget_exceeded')
    return finalize_actor_snapshot({
        'actor_id': actor_id,
        'name': f"{BRANCH_IDENTITIES[family][branch]}_lab",
        'level': level,
        'family': family,
        'mastery_level': mastery_level,
        'mastery_exp': 0,
        'skill_points': legal_family_budget(mastery_level) - sum(ranks.values()),
        'skill_ranks': ranks,
        'base_attributes': base_attributes,
        'attributes': attributes,
        **attributes,
        'hp': max_hp,
        'max_hp': max_hp,
        'mana': max_mana,
        'max_mana': max_mana,
        'weapon_item_id': weapon['item_id'],
        'weapon_name': weapon['item_id'],
        'weapon_min': int(weapon['damage_min']),
        'weapon_max': int(weapon['damage_max']),
        'weapon_type': str(weapon['weapon_type']),
        'damage_school': str(weapon['damage_school']),
        'offhand_profile': str(offhand.get('offhand_profile') or 'none'),
        'formation': resolve_default_player_formation_line(
            weapon_profile=family, offhand_profile=str(offhand.get('offhand_profile') or 'none'),
        ),
        'physical_defense': calc_physical_defense(attributes['vitality']) + int(bonuses.get('physical_defense', 0)),
        'magic_defense': calc_magic_defense(attributes['wisdom']) + int(bonuses.get('magic_defense', 0)),
        'accuracy': 100 + 2 * attributes['agility'] + attributes['intuition'] + int(bonuses.get('accuracy', 0)),
        'evasion': 100 + 2 * attributes['agility'] + attributes['luck'] + int(bonuses.get('evasion', 0)),
        'block_chance': min(40, max(0, int(bonuses.get('block_chance', 0)))),
        'magic_power': max(0, int(bonuses.get('magic_power', 0))),
        'healing_power': max(0, int(bonuses.get('healing_power', 0))),
        'equipment': equipment,
        'provenance': {
            'kind': 'legal_laboratory_snapshot', 'rules_version': RULES_VERSION,
            'level': level, 'mastery_level': mastery_level, 'preset': preset,
            'gear_set': gear_set,
            'starting_points': 6, 'earned_level_points': 3 * (level - 1),
            'cross_branch_mix': cross_branch_mix,
            'attribute_swap_to': attribute_swap_to,
            'attribute_swap_points': attribute_swap_points,
            'gear_item_ids': [item['item_id'] for item in equipment.values()],
            'gear_tier': LAB_GEAR_TIER, 'rarity': LAB_RARITY,
            'vendor_or_field_obtainable': True, 'gear_gold_cost': total_cost,
        },
    })


def build_enemy_roster(mob_ids: Iterable[str], *, formations: Iterable[str] | None = None) -> list[dict]:
    formation_values = list(formations or [])
    result = []
    for index, mob_id in enumerate(mob_ids, start=1):
        mob = get_mob(str(mob_id))
        if not mob:
            raise ValueError(f'unknown_mob:{mob_id}')
        formation = formation_values[index - 1] if index <= len(formation_values) else None
        result.append(resolve_enemy_snapshot(mob, unit_id=f'unit-{index}', formation=formation))
    return result


def build_mixed_enemy_roster(recipe_id: str) -> list[dict]:
    recipe = MIXED_ENCOUNTERS[recipe_id]
    return build_enemy_roster(
        (mob_id for mob_id, _formation in recipe['units']),
        formations=(formation for _mob_id, formation in recipe['units']),
    )


def _alive(entity: dict[str, Any]) -> bool:
    return int(entity.get('hp', 0)) > 0 and not bool(entity.get('dead'))


def _effects(entity: dict[str, Any], *kinds: str) -> list[dict[str, Any]]:
    allowed = set(kinds)
    return [effect for effect in entity.get('effects', []) if effect.get('kind') in allowed]


def _ready(actor: dict[str, Any], skill_id: str) -> bool:
    spec = SKILL_SPECS[skill_id]
    rank = int(actor.get('skill_ranks', {}).get(skill_id, 0))
    return bool(
        rank > 0 and not spec.passive and cooldown_remaining(actor, skill_id) == 0
        and int(actor.get('mana', 0)) >= rank_mana_cost(spec, rank)
    )


def _target_for(spec, actor, allies, opponents, skill_id: str):
    living_allies = [item for item in allies if _alive(item)]
    living_opponents = [item for item in opponents if _alive(item)]
    if spec.target == 'Self':
        return actor
    if spec.target == 'Ally':
        if not living_allies:
            return None
        if skill_id == 'insight':
            return min(living_allies, key=lambda item: (int(item.get('mana', 0)) / max(1, int(item.get('max_mana', 1))), str(item['actor_id'])))
        if skill_id == 'cleanse':
            return next((item for item in living_allies if _effects(item, 'poison', 'bleed', 'burn', 'weakness')), living_allies[0])
        formation_rank = {'front': 0, 'melee': 1, 'ranged': 2, 'support': 3}
        return min(living_allies, key=lambda item: (
            int(item['hp']) / max(1, int(item['max_hp'])),
            int(str(item['actor_id']) == str(actor['actor_id'])),
            formation_rank.get(item.get('formation'), 1),
            str(item['actor_id']),
        ))
    if spec.target == 'AllyOrEnemy':
        buffed = next((item for item in living_opponents if _effects(item, 'ward', 'barrier', 'attack_up')), None)
        debuffed = next((item for item in living_allies if _effects(item, 'weakness', 'slow', 'exposure', 'dawn_mark')), None)
        return buffed or debuffed or (living_opponents[0] if living_opponents else None)
    if not living_opponents:
        return None
    if spec.target == 'B':
        rank = {'front': 0, 'melee': 1, 'ranged': 2, 'support': 3}
        return max(enumerate(living_opponents), key=lambda pair: (rank.get(pair[1].get('formation'), 1), -pair[0]))[1]
    return living_opponents[0]


def _useful_support(skill_id: str, target: dict[str, Any] | None, actor: dict[str, Any], allies: list[dict]) -> bool:
    if target is None:
        return False
    if skill_id in {'heal', 'mend_self'}:
        return int(target['hp']) < int(target['max_hp']) * .82
    if skill_id == 'regeneration':
        return int(target['hp']) < int(target['max_hp']) * .92 and not _effects(target, 'regeneration')
    if skill_id == 'cleanse':
        return bool(_effects(target, 'poison', 'bleed', 'burn', 'weakness'))
    if skill_id in {'insight'}:
        return int(target.get('mana', 0)) <= int(target.get('max_mana', 0)) - 14
    if skill_id in {'quick_channel'}:
        return int(actor.get('mana', 0)) <= int(actor.get('max_mana', 0)) - 12
    if skill_id == 'resurrection':
        return not _effects(target, 'life_covenant') and not bool(target.get('death_prevention_used'))
    if skill_id in {'defensive_stance', 'dueling_ward', 'radiant_ward', 'aura_of_resolve'}:
        return not _effects(target, 'ward')
    if skill_id in {'sacred_shield', 'mana_shield', 'arcane_shield'}:
        return not _effects(target, 'barrier')
    if skill_id == 'parry':
        return not _effects(actor, 'parry')
    return True


def choose_visible_action(
    actor: dict[str, Any], allies: list[dict[str, Any]], opponents: list[dict[str, Any]],
    *, policy: str = 'branch_aware',
) -> dict[str, Any]:
    def normal_action() -> dict[str, Any]:
        target = next(item for item in opponents if _alive(item))
        return {'kind': 'normal', 'target_id': target['unit_id'], 'manual': True}

    if policy == 'normal_only':
        return normal_action()
    identity = str(actor.get('name', '')).removesuffix('_lab')
    living_opponents = [item for item in opponents if _alive(item)]
    if identity == 'executioner' and sum(item.get('formation') in {'front', 'melee'} for item in living_opponents) >= 2:
        if _ready(actor, 'cleave_through'):
            target = _target_for(SKILL_SPECS['cleave_through'], actor, allies, opponents, 'cleave_through')
            return {'kind': 'skill', 'skill_id': 'cleave_through', 'target_id': target['unit_id'], 'manual': True}
    if identity == 'duelist' and _effects(actor, 'reprisal') and _ready(actor, 'counterpulse'):
        target = _target_for(SKILL_SPECS['counterpulse'], actor, allies, opponents, 'counterpulse')
        return {'kind': 'skill', 'skill_id': 'counterpulse', 'target_id': target['unit_id'], 'manual': True}
    if identity == 'healer':
        wounded = min((item for item in allies if _alive(item)), key=lambda item: int(item['hp']) / max(1, int(item['max_hp'])))
        if int(wounded['hp']) * 2 < int(wounded['max_hp']) and _ready(actor, 'heal'):
            return {'kind': 'skill', 'skill_id': 'heal', 'target_id': wounded['actor_id'], 'manual': True}
    if identity in {'healer', 'protector', 'enchanter'} and int(actor.get('opportunity_index', 0)) % 2:
        return normal_action()
    rotation = list(BRANCH_ROTATIONS[identity])
    start = int(actor.get('opportunity_index', 0)) % len(rotation)
    ordered = rotation[start:] + rotation[:start]
    if policy == 'best_of_legal':
        damage_candidates = []
        for skill_id in ordered:
            spec = SKILL_SPECS[skill_id]
            target = _target_for(spec, actor, allies, opponents, skill_id)
            if _ready(actor, skill_id) and target and spec.kind in {'damage', 'poison'}:
                low, high = preview_damage_range(actor, target, coefficient=spec.power or 1, school=spec.school)
                damage_candidates.append(((low + high) / 2, skill_id, target))
        if damage_candidates:
            _score, skill_id, target = max(damage_candidates)
            return {'kind': 'skill', 'skill_id': skill_id, 'target_id': target.get('unit_id'), 'manual': True}
    for skill_id in ordered:
        if not _ready(actor, skill_id):
            continue
        spec = SKILL_SPECS[skill_id]
        target = _target_for(spec, actor, allies, opponents, skill_id)
        if spec.kind not in {'damage', 'poison', 'hostile_effect', 'dispel'} and not _useful_support(skill_id, target, actor, allies):
            continue
        if skill_id == 'blooded_resolve' and int(actor['hp']) >= int(actor['max_hp']) * .65:
            continue
        target_id = target.get('actor_id', target.get('unit_id')) if target else None
        return {'kind': 'skill', 'skill_id': skill_id, 'target_id': target_id, 'manual': True}
    return normal_action()


def _record(events: list[dict], metrics: dict[str, Any], player_ids: set[str], main_actor_id: str) -> None:
    for event in events:
        kind = str(event.get('kind') or '')
        actor_id = str(event.get('actor_id') or event.get('source_id') or '')
        target_id = str(event.get('target_id') or '')
        amount = int(event.get('hp_removed', event.get('amount', 0)) or 0)
        if kind in {'direct', 'dot', 'retaliation', 'poison_rupture', 'burn_consumed'} and actor_id in player_ids:
            metrics['party_damage'] += amount
            metrics['party_damage_by_cause'][kind] += amount
            if actor_id == main_actor_id:
                metrics['actor_damage'] += amount
                metrics['actor_damage_by_cause'][kind] += amount
        if kind == 'enemy_direct' and target_id in player_ids:
            metrics['damage_taken'] += amount
            metrics['prevention'] += int(event.get('barrier_absorbed', 0) or 0) + int(event.get('parried', 0) or 0)
            metrics['enemy_direct_actions'] += 1
            metrics['enemy_direct_hits'] += int(bool(event.get('hit')))
        if kind in {'heal', 'hot'} and target_id in player_ids:
            metrics['effective_healing'] += amount
        if kind == 'mana' and target_id in player_ids:
            metrics['mana_restored'] += amount
        if kind == 'controlled_skip':
            metrics['controlled_skips'] += 1
        if kind == 'intercept':
            metrics['intercepts'] += 1
        if event.get('timeout'):
            metrics['fallbacks'] += 1


def simulate_v1_encounter(
    main_actor: dict[str, Any], enemies: list[dict[str, Any]], *, seed: int,
    companions: list[dict[str, Any]] | None = None, policy: str = 'branch_aware',
    max_opportunities: int = MAX_OPPORTUNITIES, companions_first: bool = False,
) -> dict[str, Any]:
    main_state = finalize_actor_snapshot(main_actor)
    companion_states = [finalize_actor_snapshot(item) for item in (companions or [])]
    players = [*companion_states, main_state] if companions_first else [main_state, *companion_states]
    opponents = [finalize_actor_snapshot(item) for item in enemies]
    player_ids = {str(item['actor_id']) for item in players}
    main_actor_id = str(main_actor['actor_id'])
    initial_hp = sum(int(item['hp']) for item in players)
    initial_mana = sum(int(item['mana']) for item in players)
    metrics = {
        'party_damage': 0, 'actor_damage': 0, 'damage_taken': 0, 'prevention': 0,
        'effective_healing': 0, 'mana_restored': 0, 'controlled_skips': 0,
        'intercepts': 0, 'fallbacks': 0, 'enemy_direct_actions': 0,
        'enemy_direct_hits': 0, 'actions': Counter(), 'actor_actions': Counter(),
        'party_damage_by_cause': Counter(), 'actor_damage_by_cause': Counter(),
        'defeat_rounds': {}, 'events': [],
    }
    side_index = 0
    rounds = 0
    while rounds < max_opportunities and any(_alive(item) for item in players) and any(_alive(item) for item in opponents):
        rounds += 1
        for player_id in [str(item['actor_id']) for item in players if _alive(item)]:
            actor = next((item for item in players if str(item['actor_id']) == player_id and _alive(item)), None)
            if not actor or not any(_alive(item) for item in opponents):
                continue
            if player_id == main_actor_id:
                action = choose_visible_action(actor, players, opponents, policy=policy)
            else:
                target = next(item for item in opponents if _alive(item))
                action = {'kind': 'normal', 'target_id': target['unit_id'], 'manual': True}
            result = evaluate_action(
                actor, players, opponents, action,
                rng_seed=combat_seed(seed, side_index, player_id, action.get('target_id'), len(metrics['events'])),
                side_index=side_index,
            )
            if not result.get('accepted'):
                raise AssertionError(f"policy emitted illegal action: {result.get('reason')} {action}")
            players, opponents = result['allies'], result['opponents']
            for item in opponents:
                if not _alive(item):
                    metrics['defeat_rounds'].setdefault(str(item['unit_id']), rounds)
            label = action.get('skill_id') or action['kind']
            metrics['actions'][label] += 1
            if player_id == main_actor_id:
                metrics['actor_actions'][label] += 1
            metrics['events'].extend(result['events'])
            _record(result['events'], metrics, player_ids, main_actor_id)
        ticked = advance_affected_side(players, side_index=side_index)
        players = ticked['entities']
        metrics['events'].extend(ticked['events'])
        _record(ticked['events'], metrics, player_ids, main_actor_id)
        side_index += 1
        if not any(_alive(item) for item in opponents):
            break
        for enemy_id in [str(item['unit_id']) for item in opponents if _alive(item)]:
            enemy = next((item for item in opponents if str(item['unit_id']) == enemy_id and _alive(item)), None)
            if not enemy or not any(_alive(item) for item in players):
                continue
            action = choose_enemy_action(enemy, opponents)
            result = evaluate_enemy_action(
                enemy, opponents, players, action,
                rng_seed=combat_seed(seed, side_index, enemy_id, action.get('target_id'), len(metrics['events'])),
                side_index=side_index,
            )
            if not result.get('accepted'):
                raise AssertionError(f"enemy policy emitted illegal action: {result.get('reason')} {action}")
            opponents, players = result['allies'], result['players']
            metrics['events'].extend(result['events'])
            _record(result['events'], metrics, player_ids, main_actor_id)
        ticked = advance_affected_side(opponents, side_index=side_index)
        opponents = ticked['entities']
        for item in opponents:
            if not _alive(item):
                metrics['defeat_rounds'].setdefault(str(item['unit_id']), rounds)
        metrics['events'].extend(ticked['events'])
        _record(ticked['events'], metrics, player_ids, main_actor_id)
        side_index += 1

    winner = 'players' if any(_alive(item) for item in players) and not any(_alive(item) for item in opponents) else 'enemies'
    stalled = any(_alive(item) for item in players) and any(_alive(item) for item in opponents)
    main_final = next(item for item in players if str(item['actor_id']) == main_actor_id)
    actor_action_count = sum(metrics['actor_actions'].values())
    return {
        'rules_version': RULES_VERSION, 'seed': seed, 'winner': winner,
        'stalled': stalled, 'turns': rounds,
        'party_hp_remaining': sum(max(0, int(item['hp'])) for item in players),
        'actor_hp_remaining': max(0, int(main_final['hp'])),
        'party_mana_delta': sum(int(item['mana']) for item in players) - initial_mana,
        'unrecovered_hp_loss': initial_hp - sum(max(0, int(item['hp'])) for item in players),
        'normal_action_share': round(metrics['actor_actions']['normal'] / max(1, actor_action_count), 4),
        'consumables': 0,
        **{key: (dict(value) if isinstance(value, Counter) else value) for key, value in metrics.items() if key != 'events'},
        'event_count': len(metrics['events']),
        'events': metrics['events'],
        'final_players': players, 'final_enemies': opponents,
    }


def _wilson(successes: int, total: int) -> list[float]:
    if total <= 0:
        return [0.0, 0.0]
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]


def paired_difference(winner_values: list[float], other_values: list[float], *, lower_is_better: bool = False) -> dict[str, Any]:
    """Return the paired advantage of the declared winner over its sibling."""
    if len(winner_values) != len(other_values) or not winner_values:
        raise ValueError('paired_samples_required')
    diffs = [
        (other - winner) if lower_is_better else (winner - other)
        for winner, other in zip(winner_values, other_values)
    ]
    mean = statistics.fmean(diffs)
    std = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
    margin = 1.959963984540054 * std / math.sqrt(len(diffs))
    winner_mean = statistics.fmean(winner_values)
    other_mean = statistics.fmean(other_values)
    baseline = abs(other_mean)
    if baseline < 1:
        baseline = max(1, abs(winner_mean))
    return {
        'pairs': len(diffs), 'advantage_mean': round(mean, 4),
        'advantage_percent': round(100 * mean / baseline, 2),
        'ci95': [round(mean - margin, 4), round(mean + margin, 4)],
        'ci_excludes_zero': bool(mean - margin > 0),
    }


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    wins = sum(run['winner'] == 'players' and not run['stalled'] for run in runs)
    turns = sorted(int(run['turns']) for run in runs)
    return {
        'runs': len(runs), 'wins': wins, 'win_rate': round(wins / max(1, len(runs)), 4),
        'win_rate_ci95': _wilson(wins, len(runs)),
        'stalls_as_failures': sum(bool(run['stalled']) for run in runs),
        'median_turns': statistics.median(turns),
        'p90_turns': turns[min(len(turns) - 1, math.ceil(.9 * len(turns)) - 1)],
        'mean_damage': round(statistics.fmean(run['actor_damage'] for run in runs), 2),
        'mean_damage_taken': round(statistics.fmean(run['damage_taken'] for run in runs), 2),
        'mean_healing': round(statistics.fmean(run['effective_healing'] for run in runs), 2),
        'mean_prevention': round(statistics.fmean(run['prevention'] for run in runs), 2),
        'mean_party_hp_remaining': round(statistics.fmean(run['party_hp_remaining'] for run in runs), 2),
        'mean_mana_delta': round(statistics.fmean(run['party_mana_delta'] for run in runs), 2),
        'mean_normal_action_share': round(statistics.fmean(run['normal_action_share'] for run in runs), 4),
        'consumables': sum(int(run['consumables']) for run in runs),
        'fallbacks': sum(int(run['fallbacks']) for run in runs),
    }


def validate_lab_actor(actor: dict[str, Any]) -> list[str]:
    errors = []
    provenance = actor.get('provenance') or {}
    expected_points = 6 + 3 * (int(actor['level']) - 1)
    actual_points = sum(int(value) - 1 for value in actor['base_attributes'].values())
    if actual_points != expected_points:
        errors.append('attribute_budget')
    if sum(actor['skill_ranks'].values()) > legal_family_budget(int(actor['mastery_level'])):
        errors.append('skill_budget')
    if any(SKILL_SPECS[skill_id].family != actor['family'] for skill_id in actor['skill_ranks']):
        errors.append('family_ownership')
    ranks = {str(skill_id): int(rank) for skill_id, rank in actor['skill_ranks'].items()}
    mastery_level = int(actor['mastery_level'])
    if any(
        max(
            SKILL_SPECS[skill_id].unlock_mastery,
            RANK_REQUIREMENTS.get(rank, SKILL_SPECS[skill_id].unlock_mastery),
        ) > mastery_level
        for skill_id, rank in ranks.items()
    ):
        errors.append('mastery_gate')
    if any(rank < 1 or rank > MAX_SKILL_RANK for rank in ranks.values()):
        errors.append('rank_limit')
    capstones = [skill_id for skill_id, rank in ranks.items() if rank > 0 and SKILL_SPECS[skill_id].position == 4]
    if len(capstones) > 1:
        errors.append('dual_capstone')
    for capstone in capstones:
        branch = SKILL_SPECS[capstone].branch
        other_points = sum(
            rank for skill_id, rank in ranks.items()
            if SKILL_SPECS[skill_id].branch == branch and skill_id != capstone
        )
        if other_points < 8:
            errors.append('capstone_prerequisite')
    if actor.get('weapon_item_id') != f"field_{actor['family']}":
        errors.append('field_weapon')
    if provenance.get('gear_tier') != 1 or provenance.get('rarity') != 'common':
        errors.append('gear_budget')
    return errors


def _metric_value(run: dict[str, Any], metric: str) -> float:
    if metric == 'priority_target_round':
        return float(run['defeat_rounds'].get('unit-3', MAX_OPPORTUNITIES + 1))
    if metric == 'actor_damage_per_turn':
        return float(run['actor_damage']) / max(1, int(run['turns']))
    if metric == 'direct_damage':
        return float(run['actor_damage_by_cause'].get('direct', 0))
    if metric == 'mana_efficiency':
        return float(run['actor_damage']) / max(1, -int(run['party_mana_delta']))
    return float(run[metric])


def _scenario_enemies(spec: tuple[str, ...] | str) -> list[dict[str, Any]]:
    if isinstance(spec, str):
        return build_mixed_enemy_roster(spec.removeprefix('mixed:'))
    return build_enemy_roster(spec)


def _scenario_companions(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    companions = []
    for spec in specs:
        actor = build_legal_lab_actor(
            spec['family'], spec['branch'], actor_id=spec['actor_id'],
            level=spec['level'], mastery_level=spec['mastery_level'],
        )
        actor['name'] = spec.get('name', actor['name'])
        actor['formation'] = spec.get('formation', actor['formation'])
        if 'mana_fraction' in spec:
            actor['mana'] = int(actor['max_mana'] * float(spec['mana_fraction']))
        companions.append(actor)
    return companions


def _paired_scenario(config: dict[str, Any], seeds: Iterable[int]) -> dict[str, Any]:
    seed_values = tuple(int(seed) for seed in seeds)
    runs: dict[str, list[dict[str, Any]]] = {}
    for branch in ('A', 'B'):
        actor = build_legal_lab_actor(
            config['family'], branch, level=config.get('level', 6),
            mastery_level=config.get('mastery_level', 8),
        )
        companions = _scenario_companions(config.get('companions', []))
        runs[branch] = [
            simulate_v1_encounter(
                actor, _scenario_enemies(config['enemies']), seed=seed,
                companions=companions, max_opportunities=config.get('max_opportunities', MAX_OPPORTUNITIES),
                companions_first=config.get('companions_first', False),
            )
            for seed in seed_values
        ]
    gates = []
    for gate in config['gates']:
        winner = gate['winner']
        other = 'B' if winner == 'A' else 'A'
        comparison = paired_difference(
            [_metric_value(run, gate['metric']) for run in runs[winner]],
            [_metric_value(run, gate['metric']) for run in runs[other]],
            lower_is_better=gate.get('lower_is_better', False),
        )
        threshold = float(gate.get('threshold_percent', 10))
        gates.append({
            **gate, **comparison,
            'passes': comparison['advantage_percent'] >= threshold and comparison['ci_excludes_zero'],
        })
    return {
        'scenario_id': config['scenario_id'], 'family': config['family'],
        'declared_matchup': config['declared_matchup'],
        'enemy_source_ids': list(config['enemies']) if not isinstance(config['enemies'], str) else [config['enemies']],
        'level': config.get('level', 6), 'mastery_level': config.get('mastery_level', 8),
        'gear_set': 'common_t1_full', 'policy': 'branch_aware',
        'seeds': {'first': min(seed_values), 'last': max(seed_values), 'count': len(seed_values)},
        'max_opportunities': config.get('max_opportunities', MAX_OPPORTUNITIES),
        'companions': config.get('companions', []),
        'branches': {
            branch: {
                **summarize_runs(branch_runs),
                'mean_intercepts': round(statistics.fmean(run['intercepts'] for run in branch_runs), 2),
                'mean_controlled_skips': round(statistics.fmean(run['controlled_skips'] for run in branch_runs), 2),
                'mean_party_damage': round(statistics.fmean(run['party_damage'] for run in branch_runs), 2),
                'failing_seeds': [run['seed'] for run in branch_runs if run['winner'] != 'players' or run['stalled']],
            }
            for branch, branch_runs in runs.items()
        },
        'gates': gates,
    }


ROLE_SCENARIOS = (
    {
        'scenario_id': 'sword_1h_armored_sustain', 'family': 'sword_1h',
        'declared_matchup': 'Vanguard sustained damage; Guardian personal prevention and retaliation',
        'enemies': ('mountain_stone_golem',), 'max_opportunities': 4,
        'gates': (
            {'winner': 'B', 'metric': 'actor_damage', 'axis': 'sustained_damage'},
            {'winner': 'A', 'metric': 'prevention', 'axis': 'personal_prevention'},
        ),
    },
    {
        'scenario_id': 'sword_2h_homogeneous_front_pack', 'family': 'sword_2h',
        'declared_matchup': 'Executioner frontal multi-target damage in a real homogeneous pack',
        'enemies': ('white_wolf', 'white_wolf', 'white_wolf'), 'max_opportunities': 3,
        'gates': ({'winner': 'A', 'metric': 'actor_damage', 'axis': 'front_pack_damage'},),
    },
    {
        'scenario_id': 'sword_2h_telegraphed_single', 'family': 'sword_2h',
        'declared_matchup': 'Blademaster telegraphed single-target exchange',
        'enemies': ('troll_chief',),
        'gates': ({'winner': 'B', 'metric': 'unrecovered_hp_loss', 'axis': 'exchange_hp_loss', 'lower_is_better': True},),
    },
    {
        'scenario_id': 'axe_armored_sustain', 'family': 'axe_2h',
        'declared_matchup': 'Ravager bleed and armor-break sustain',
        'enemies': ('mountain_stone_golem', 'mountain_stone_golem'), 'max_opportunities': 8,
        'gates': ({'winner': 'B', 'metric': 'actor_damage', 'axis': 'armored_effective_damage'},),
    },
    {
        'scenario_id': 'axe_short_unarmored_burst', 'family': 'axe_2h',
        'declared_matchup': 'Berserker two-opportunity Rage burst and survival cost',
        'enemies': ('troll_chief',), 'max_opportunities': 2,
        'gates': ({'winner': 'A', 'metric': 'actor_damage', 'axis': 'short_burst_damage'},),
    },
    {
        'scenario_id': 'daggers_armored_sustain', 'family': 'daggers',
        'declared_matchup': 'Venom delayed effective damage across a sustained four-opportunity cycle on an armored target',
        'enemies': ('mountain_stone_golem',), 'max_opportunities': 4,
        'gates': ({'winner': 'A', 'metric': 'actor_damage_per_turn', 'axis': 'sustained_damage_per_opportunity'},),
    },
    {
        'scenario_id': 'daggers_opened_burst', 'family': 'daggers',
        'declared_matchup': 'Shadow direct damage after earning Opening',
        'enemies': ('troll_chief',), 'max_opportunities': 2,
        'gates': ({'winner': 'B', 'metric': 'direct_damage', 'axis': 'opened_direct_burst'},),
    },
    {
        'scenario_id': 'bow_priority_target', 'family': 'bow',
        'declared_matchup': 'Sniper back-line priority removal in the westwild mixed recipe',
        'enemies': 'mixed:westwild_n8_mixed',
        'gates': ({'winner': 'A', 'metric': 'priority_target_round', 'axis': 'priority_removal_round', 'lower_is_better': True},),
    },
    {
        'scenario_id': 'bow_slowed_multi', 'family': 'bow',
        'declared_matchup': 'Ranger bounded multi-target damage after Slow',
        'enemies': 'mixed:westwild_n8_mixed', 'max_opportunities': 3,
        'gates': ({'winner': 'B', 'metric': 'actor_damage', 'axis': 'slowed_multi_target_damage'},),
    },
    {
        'scenario_id': 'magic_staff_pack_exchange', 'family': 'magic_staff',
        'declared_matchup': 'Destruction pack damage; Control prevention and denial',
        'enemies': 'mixed:westwild_n8_mixed', 'max_opportunities': 3,
        'gates': (
            {'winner': 'A', 'metric': 'actor_damage', 'axis': 'pack_damage'},
            {'winner': 'B', 'metric': 'prevention', 'axis': 'damage_prevented'},
        ),
    },
    {
        'scenario_id': 'wand_mana_efficiency', 'family': 'wand',
        'declared_matchup': 'Arcanist effective damage per net mana spent',
        'enemies': ('mountain_stone_golem',), 'max_opportunities': 4,
        'gates': ({'winner': 'A', 'metric': 'mana_efficiency', 'axis': 'damage_per_net_mana'},),
    },
    {
        'scenario_id': 'wand_counter_exchange', 'family': 'wand',
        'declared_matchup': 'Duelist accepts and answers one visible caster exchange',
        'enemies': ('fire_elemental',), 'max_opportunities': 2,
        'gates': ({'winner': 'B', 'metric': 'actor_damage', 'axis': 'counter_exchange_damage'},),
    },
    {
        'scenario_id': 'holy_staff_sustained_group', 'family': 'holy_staff',
        'declared_matchup': 'Same-party Healer recovery under sustained group damage',
        'level': 10, 'mastery_level': 14,
        'enemies': ('mountain_stone_golem', 'mountain_stone_golem', 'mountain_stone_golem'),
        'companions': ({'family': 'sword_1h', 'branch': 'A', 'actor_id': 2, 'level': 10, 'mastery_level': 14, 'name': 'frontline'},),
        'gates': ({'winner': 'A', 'metric': 'unrecovered_hp_loss', 'axis': 'party_unrecovered_hp_loss', 'lower_is_better': True, 'threshold_percent': 20},),
    },
    {
        'scenario_id': 'holy_staff_mark_window', 'family': 'holy_staff',
        'declared_matchup': 'Same-party Dawn damage in its marked-target window',
        'level': 10, 'mastery_level': 14, 'max_opportunities': 3,
        'enemies': ('mountain_stone_golem', 'mountain_stone_golem'),
        'companions': ({'family': 'sword_1h', 'branch': 'A', 'actor_id': 2, 'level': 10, 'mastery_level': 14, 'name': 'frontline'},),
        'gates': ({'winner': 'B', 'metric': 'party_damage', 'axis': 'marked_window_party_damage'},),
    },
    {
        'scenario_id': 'holy_rod_targeted_protection', 'family': 'holy_rod',
        'declared_matchup': 'Protector interception versus Judgment personal pressure in the same party',
        'enemies': 'mixed:westwild_n8_mixed', 'companions_first': True,
        'companions': ({'family': 'sword_2h', 'branch': 'B', 'actor_id': 2, 'level': 6, 'mastery_level': 8, 'name': 'frontline', 'formation': 'front'},),
        'gates': (
            {'winner': 'A', 'metric': 'prevention', 'axis': 'targeted_ally_prevention'},
            {'winner': 'B', 'metric': 'actor_damage', 'axis': 'personal_damage'},
        ),
    },
    {
        'scenario_id': 'tome_party_mana', 'family': 'tome',
        'declared_matchup': 'Enchanter net party mana after its own costs',
        'level': 10, 'mastery_level': 14, 'max_opportunities': 8,
        'enemies': ('mountain_stone_golem', 'mountain_stone_golem'),
        'companions': (
            {'family': 'magic_staff', 'branch': 'A', 'actor_id': 2, 'level': 10, 'mastery_level': 14, 'name': 'caster_2', 'mana_fraction': 0},
            {'family': 'magic_staff', 'branch': 'A', 'actor_id': 3, 'level': 10, 'mastery_level': 14, 'name': 'caster_3', 'mana_fraction': 0},
        ),
        'gates': ({'winner': 'A', 'metric': 'party_mana_delta', 'axis': 'net_party_mana'},),
    },
    {
        'scenario_id': 'tome_mixed_school_cycle', 'family': 'tome',
        'declared_matchup': 'Synthesis personal damage over an equal-length mixed-school cycle',
        'enemies': 'mixed:westwild_n8_mixed', 'max_opportunities': 4,
        'gates': ({'winner': 'B', 'metric': 'actor_damage', 'axis': 'mixed_cycle_personal_damage', 'threshold_percent': 15},),
    },
)


def run_role_evidence(seeds: Iterable[int] = PAIR_SEEDS) -> dict[str, Any]:
    scenarios = [_paired_scenario(config, seeds) for config in ROLE_SCENARIOS]
    gates = [gate for scenario in scenarios for gate in scenario['gates']]
    return {
        'scenario_count': len(scenarios), 'gate_count': len(gates),
        'all_gates_pass': all(gate['passes'] for gate in gates),
        'scenarios': scenarios,
    }


def run_accessibility_evidence(seeds: Iterable[int] = PAIR_SEEDS) -> dict[str, Any]:
    seed_values = tuple(int(seed) for seed in seeds)
    enemy_ids = ('westwild_rabbit', 'forest_boar', 'forest_wolf')
    defense_support = {'guardian', 'control', 'duelist', 'healer', 'protector', 'enchanter'}
    branches = []
    for family in FAMILIES:
        for branch in ('A', 'B'):
            actor = build_legal_lab_actor(
                family, branch, level=3, mastery_level=3, gear_set='entry_weapon_only',
            )
            identity = BRANCH_IDENTITIES[family][branch]
            by_enemy = {}
            all_runs = []
            failing_seeds = []
            for enemy_id in enemy_ids:
                runs = [
                    simulate_v1_encounter(actor, build_enemy_roster((enemy_id,)), seed=seed)
                    for seed in seed_values
                ]
                by_enemy[enemy_id] = summarize_runs(runs)
                all_runs.extend(runs)
                failing_seeds.extend(
                    {'enemy_id': enemy_id, 'seed': run['seed']}
                    for run in runs if run['winner'] != 'players' or run['stalled']
                )
            opportunity_limit = 18 if identity in defense_support else 12
            wins = sum(run['winner'] == 'players' and not run['stalled'] for run in all_runs)
            branches.append({
                'family': family, 'branch': branch, 'identity': identity,
                'entry_skill_id': SKILL_TREES[family][branch][0],
                'level': 3, 'mastery_level': 3,
                'attribute_points_spent': sum(value - 1 for value in actor['base_attributes'].values()),
                'skill_points_spent': sum(actor['skill_ranks'].values()),
                'item_ids': actor['provenance']['gear_item_ids'],
                'gear_gold_cost': actor['provenance']['gear_gold_cost'],
                'actor_validation_errors': validate_lab_actor(actor),
                'runs': len(all_runs), 'win_rate': round(wins / len(all_runs), 4),
                'win_rate_ci95': _wilson(wins, len(all_runs)),
                'opportunity_limit': opportunity_limit, 'by_enemy': by_enemy,
                'passes': wins / len(all_runs) >= .90 and all(
                    summary['median_turns'] <= opportunity_limit for summary in by_enemy.values()
                ),
                'failing_seeds': failing_seeds,
            })
    return {
        'seeds': {'first': min(seed_values), 'last': max(seed_values), 'count': len(seed_values)},
        'enemy_ids': list(enemy_ids), 'branch_count': len(branches),
        'all_branches_pass': all(item['passes'] for item in branches),
        'branches': branches,
    }


def progression_combat_comparisons(
    seeds: Iterable[int] = PROGRESSION_SEEDS,
) -> list[dict[str, Any]]:
    """Compare sibling loadouts through real G2 combat at every J-stage."""
    seed_values = tuple(int(seed) for seed in seeds)
    if not seed_values:
        raise ValueError('progression_seeds_required')
    stages = (
        (1, 1, 'westwild_rabbit'),
        (3, 3, 'forest_boar'),
        (6, 8, 'forest_wolf'),
        (10, 14, 'mountain_stone_golem'),
        (15, 20, 'troll_chief'),
    )
    comparisons = []
    for family in FAMILIES:
        for level, mastery_level, enemy_id in stages:
            for gear_set in ('entry_weapon_only', 'common_t1_full'):
                branches = {}
                for branch in ('A', 'B'):
                    actor = build_legal_lab_actor(
                        family, branch, level=level, mastery_level=mastery_level,
                        gear_set=gear_set,
                    )
                    runs = [
                        simulate_v1_encounter(
                            actor, build_enemy_roster((enemy_id,)), seed=seed,
                            max_opportunities=12,
                        )
                        for seed in seed_values
                    ]
                    branches[branch] = {
                        'identity': BRANCH_IDENTITIES[family][branch],
                        'skill_ranks': actor['skill_ranks'],
                        'validation_errors': validate_lab_actor(actor),
                        'outcomes': summarize_runs(runs),
                    }
                comparisons.append({
                    'family': family, 'level': level,
                    'mastery_level': mastery_level, 'gear_set': gear_set,
                    'enemy_source_ids': [enemy_id],
                    'seeds': {
                        'first': min(seed_values), 'last': max(seed_values),
                        'count': len(seed_values),
                    },
                    'combat_authority': 'simulate_v1_encounter',
                    'branches': branches,
                })
    return comparisons


def snapshot_matrix() -> dict[str, Any]:
    stages = ((1, 1), (3, 3), (6, 8), (10, 14), (15, 20))
    snapshots = []
    for family in FAMILIES:
        for branch in ('A', 'B'):
            for level, mastery_level in stages:
                actor = build_legal_lab_actor(family, branch, level=level, mastery_level=mastery_level)
                snapshots.append({
                    'family': family, 'branch': branch, 'level': level,
                    'mastery_level': mastery_level, 'base_attributes': actor['base_attributes'],
                    'skill_ranks': actor['skill_ranks'],
                    'unspent_skill_points': actor['skill_points'],
                    'item_ids': actor['provenance']['gear_item_ids'],
                    'validation_errors': validate_lab_actor(actor),
                })
    cross_branch = []
    for family in ('sword_1h', 'daggers', 'magic_staff', 'holy_staff'):
        actor = build_legal_lab_actor(
            family, 'A', level=15, mastery_level=20, cross_branch_mix=True,
        )
        cross_branch.append({
            'family': family, 'allocation': actor['skill_ranks'],
            'points_spent': sum(actor['skill_ranks'].values()),
            'capstones': [
                skill_id for skill_id, rank in actor['skill_ranks'].items()
                if rank > 0 and SKILL_SPECS[skill_id].position == 4
            ],
            'validation_errors': validate_lab_actor(actor),
        })
    progression_comparisons = progression_combat_comparisons()
    stat_variants = []
    for family in FAMILIES:
        if family == 'daggers':
            target = 'luck'
        elif family in {'bow', 'wand'}:
            target = PROFILE_SECONDARY_SCALING[family][0]
        elif family in {'holy_staff', 'tome'}:
            target = 'wisdom'
        else:
            target = 'vitality'
        actor = build_legal_lab_actor(
            family, 'A', level=15, mastery_level=20, attribute_swap_to=target,
        )
        stat_variants.append({
            'family': family, 'swap_to': target, 'base_attributes': actor['base_attributes'],
            'swap_points': actor['provenance']['attribute_swap_points'],
            'validation_errors': validate_lab_actor(actor),
        })
    extremes = []
    for level in (50, 100):
        for family in FAMILIES:
            for branch in ('A', 'B'):
                actor = build_legal_lab_actor(family, branch, level=level, mastery_level=20)
                low, high = raw_power_range(actor)
                extremes.append({
                    'level': level, 'family': family, 'branch': branch,
                    'max_hp': actor['max_hp'], 'max_mana': actor['max_mana'],
                    'power_range': [low, high], 'physical_defense': actor['physical_defense'],
                    'magic_defense': actor['magic_defense'],
                    'validation_errors': validate_lab_actor(actor),
                })
    return {
        'independent_progression_axes': True,
        'stages': [{'level': level, 'mastery_level': mastery} for level, mastery in stages],
        'snapshot_count': len(snapshots), 'snapshots': snapshots,
        'cross_branch_m20_15_plus_6': cross_branch,
        'progression_comparison_count': len(progression_comparisons),
        'progression_comparisons': progression_comparisons,
        'stat_swap_variants': stat_variants,
        'extreme_formula_probes_not_balance_claims': extremes,
    }


ENCOUNTER_MATRIX = (
    ('entry_rabbit', ('westwild_rabbit',)),
    ('ordinary_boar', ('forest_boar',)),
    ('ordinary_wolf', ('forest_wolf',)),
    ('armored_construct', ('mountain_stone_golem',)),
    ('evasive_bat', ('cave_bat',)),
    ('magic_caster', ('skeleton_mage',)),
    ('poison_spider', ('swamp_spider',)),
    ('telegraphed_heavy', ('troll_chief',)),
    ('westwild_mixed', 'mixed:westwild_n8_mixed'),
    ('ashen_mixed', 'mixed:ashen_n3c1_mixed'),
    ('existing_white_wolf_pack', ('white_wolf', 'white_wolf', 'white_wolf')),
    ('existing_zombie_pack', ('zombie', 'zombie', 'zombie')),
)


def run_encounter_matrix(seeds: Iterable[int] = PAIR_SEEDS) -> dict[str, Any]:
    seed_values = tuple(int(seed) for seed in seeds)
    results = []
    for scenario_id, enemies in ENCOUNTER_MATRIX:
        for family in FAMILIES:
            for branch in ('A', 'B'):
                actor = build_legal_lab_actor(family, branch, level=6, mastery_level=8)
                runs = [
                    simulate_v1_encounter(actor, _scenario_enemies(enemies), seed=seed)
                    for seed in seed_values
                ]
                results.append({
                    'scenario_id': scenario_id, 'enemy_source_ids': (
                        list(enemies) if not isinstance(enemies, str) else [enemies]
                    ),
                    'family': family, 'branch': branch, 'level': 6, 'mastery_level': 8,
                    'gear_set': 'common_t1_full', 'policy': 'branch_aware',
                    **summarize_runs(runs),
                    'mean_party_hp_remaining': round(statistics.fmean(run['party_hp_remaining'] for run in runs), 2),
                    'mean_overheal': 0,
                    'failing_seeds': [
                        run['seed'] for run in runs if run['winner'] != 'players' or run['stalled']
                    ],
                })
    return {
        'seed_count_per_loadout': len(seed_values),
        'scenarios': [scenario_id for scenario_id, _enemies in ENCOUNTER_MATRIX],
        'result_count': len(results), 'results': results,
        'excluded': {
            'dark_treant': '500000 HP is not an ordinary-content benchmark; excluded by the frozen contract.',
        },
    }


def run_full_evidence(*, base_sha: str, head_sha: str, seeds: Iterable[int] = PAIR_SEEDS) -> dict[str, Any]:
    seed_values = tuple(int(seed) for seed in seeds)
    return {
        'schema_version': 1, 'rules_version': RULES_VERSION,
        'base_sha': base_sha, 'head_sha': head_sha,
        'rng': {'paired_seeds': list(seed_values), 'count': len(seed_values)},
        'authority': {
            'actor_builder': 'game.combat_identity_simulation.build_legal_lab_actor',
            'player_evaluator': 'game.combat_identity.evaluate_action',
            'enemy_evaluator': 'game.combat_identity.evaluate_enemy_action',
            'side_scheduler': 'game.combat_identity.advance_affected_side',
            'enemy_profiles': 'game.enemy_profiles.resolve_enemy_snapshot',
            'field_items': 'game.field_catalog.FIELD_ITEMS',
            'legacy_simulator_used': False,
        },
        'policy': {
            'normal_only': 'Always submit a legal normal action to the first living visible target.',
            'branch_aware': 'Visible HP/MP, intents, ranks, effects and cooldowns only; fixed setup/payoff priorities.',
            'best_of_legal': 'Preview current legal damage candidates only; never reads future RNG.',
            'local_policy_tuning': 'Rotation priority only; coefficients are separately recorded as bounded tuning.',
        },
        'snapshot_matrix': snapshot_matrix(),
        'accessibility': run_accessibility_evidence(seed_values),
        'roles': run_role_evidence(seed_values),
        'encounter_matrix': run_encounter_matrix(seed_values),
        'bounded_numerical_tuning': [
            {'skill_id': 'cleave_through', 'field': 'direct_power', 'old': 1.00, 'new': 1.15, 'relative_percent': 15.0},
            {'skill_id': 'frenzy_chain', 'field': 'direct_power', 'old': 1.60, 'new': 1.84, 'relative_percent': 15.0},
            {'skill_id': 'savage_chop', 'field': 'direct_power', 'old': 1.20, 'new': 1.02, 'relative_percent': -15.0},
            {'skill_id': 'last_roar', 'field': 'direct_power', 'old': 1.90, 'new': 1.62, 'relative_percent': -14.74},
            {'skill_id': 'bleeding_cut', 'field': 'direct_power', 'old': .85, 'new': .73, 'relative_percent': -14.12},
            {'skill_id': 'sunder_armor', 'field': 'direct_power', 'old': .90, 'new': .77, 'relative_percent': -14.44},
            {'skill_id': 'reopen_wounds', 'field': 'direct_power', 'old': 1.20, 'new': 1.38, 'relative_percent': 15.0},
            {'skill_id': 'ravage', 'field': 'direct_power', 'old': 1.80, 'new': 2.07, 'relative_percent': 15.0},
            {'skill_id': 'envenom_blades', 'field': 'poison_tick_power', 'old': .25, 'new': .2875, 'relative_percent': 15.0},
            {'skill_id': 'toxic_cut', 'field': 'direct_power', 'old': .90, 'new': 1.035, 'relative_percent': 15.0},
            {'skill_id': 'toxic_cut', 'field': 'poison_tick_power', 'old': .20, 'new': .23, 'relative_percent': 15.0},
            {'skill_id': 'widows_kiss', 'field': 'direct_power', 'old': 1.15, 'new': 1.3225, 'relative_percent': 15.0},
            {'skill_id': 'widows_kiss', 'field': 'power_per_poison', 'old': .20, 'new': .23, 'relative_percent': 15.0},
            {'skill_id': 'rupture_toxins', 'field': 'direct_power', 'old': 1.20, 'new': 1.38, 'relative_percent': 15.0},
            {'skill_id': 'rupture_toxins', 'field': 'remaining_tick_conversion', 'old': .80, 'new': .92, 'relative_percent': 15.0},
            {'skill_id': 'feint_step', 'field': 'direct_power', 'old': .65, 'new': .5525, 'relative_percent': -15.0},
            {'skill_id': 'shadow_chain', 'field': 'direct_power', 'old': 1.90, 'new': 1.615, 'relative_percent': -15.0},
        ],
    }


def main() -> None:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description='Generate Character Builds V1 evidence.')
    parser.add_argument('--base-sha', required=True)
    parser.add_argument('--head-sha', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    evidence = run_full_evidence(base_sha=args.base_sha, head_sha=args.head_sha)
    Path(args.output).write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
