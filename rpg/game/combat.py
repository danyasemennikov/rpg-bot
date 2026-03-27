# ============================================================
# combat.py — боевой движок
# ============================================================

import random
import sys
sys.path.append('/content/rpg_bot')

from game.balance import (
    calc_final_damage, calc_dodge_chance, calc_crit_chance,
    calc_physical_defense, calc_magic_defense,
    calc_crit_reduction, calc_action_priority,
    calc_physical_damage_reduction,
    calc_armor_class_defense_multiplier,
    calc_offhand_defense_multiplier,
    calc_armor_class_dodge_bonus_percent,
    calc_encumbrance_dodge_penalty_percent,
    normalize_damage_school,
    get_player_accuracy_rating,
    get_player_evasion_rating,
    get_enemy_accuracy_rating,
    get_enemy_evasion_rating,
    resolve_hit_check,
)
from game.i18n import t, get_mob_name
from game.skills import get_skill
from game.skill_engine import (
    apply_mob_effects,
    build_skill_result_log,
    precheck_skill_use,
    use_skill,
)

SLOW_MISS_CHANCE = 0.35
DOT_EFFECT_TYPES = {'poison', 'burn', 'bleed'}


# ────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ────────────────────────────────────────

def roll_crit(luck: int, agility: int = 0, enemy_luck: int = 0) -> bool:
    """Проверка на крит с учётом снижения от удачи врага."""
    crit_chance = calc_crit_chance(luck, agility)
    crit_reduction = calc_crit_reduction(enemy_luck) / 100
    final_chance = max(0, crit_chance - crit_reduction)
    return random.random() < final_chance

def roll_dodge(
    agility: int,
    *,
    armor_class: str | None = None,
    encumbrance: int | float | None = None,
) -> bool:
    """Проверка на уклонение."""
    dodge_chance = calc_dodge_chance(agility)
    dodge_delta = calc_armor_class_dodge_bonus_percent(armor_class)
    dodge_delta -= calc_encumbrance_dodge_penalty_percent(encumbrance)
    final_dodge = dodge_chance + (dodge_delta / 100)
    final_dodge = min(0.60, max(0.0, final_dodge))
    return random.random() < final_dodge

def get_weapon_type(player_equipment: dict) -> str:
    """Определяет тип оружия игрока. По умолчанию melee."""
    return player_equipment.get('weapon_type', 'melee')


def get_weapon_profile(player_equipment: dict) -> str:
    """Определяет weapon_profile игрока. По умолчанию unarmed."""
    return player_equipment.get('weapon_profile', 'unarmed')

def calc_mob_damage(mob: dict) -> int:
    """Урон моба — рандом между min и max."""
    return random.randint(mob['damage_min'], mob['damage_max'])

def apply_defense(damage: int, defense: int) -> int:
    """Снижает урон на величину защиты. Минимум 1."""
    return max(1, damage - defense)

def hp_bar(current: int, maximum: int, length: int = 10) -> str:
    """Визуальная полоска HP."""
    filled = int((current / maximum) * length)
    filled = max(0, min(length, filled))
    return '█' * filled + '░' * (length - filled)

def apply_pre_enemy_response_ticks(mob: dict, battle_state: dict) -> list[str]:
    """Единый pre-turn ticking перед ответом врага."""
    log = []
    mob_state = {
        'hp': battle_state['mob_hp'],
        'defense': mob.get('defense', 0),
        'effects': battle_state.get('mob_effects', []),
    }

    eff_dmg, eff_log = apply_mob_effects(mob_state)
    if eff_dmg > 0:
        battle_state['mob_hp'] = max(0, battle_state['mob_hp'] - eff_dmg)
        log.append(eff_log)

    # Важно: для skill flow сохраняем прежний тайминг —
    # post-action баффы игрока тикают до enemy response.
    tick_post_action_player_buff_durations(battle_state)

    battle_state['mob_effects'] = mob_state.get('effects', [])
    return log


def apply_mob_effect_ticks(mob: dict, battle_state: dict) -> list[str]:
    """Mob-only ticking для normal attack flow (без player buffs)."""
    log = []
    mob_state = {
        'hp': battle_state['mob_hp'],
        'defense': mob.get('defense', 0),
        'effects': battle_state.get('mob_effects', []),
    }

    eff_dmg, eff_log = apply_mob_effects(mob_state)
    if eff_dmg > 0:
        battle_state['mob_hp'] = max(0, battle_state['mob_hp'] - eff_dmg)
        log.append(eff_log)

    battle_state['mob_effects'] = mob_state.get('effects', [])
    return log


def decrement_mob_non_dot_effects_after_response(battle_state: dict) -> None:
    """
    Post-enemy-response decrement target эффектов моба.
    DoT (poison/burn) здесь не тикаем — они остаются в pre-enemy phase.
    """
    mob_effects = battle_state.get('mob_effects', [])
    if not mob_effects:
        return

    new_effects = []
    for eff in mob_effects:
        turns = int(eff.get('turns', 0))
        if turns <= 0:
            continue

        eff_type = eff.get('type')
        if eff_type in DOT_EFFECT_TYPES:
            new_effects.append(eff)
            continue

        updated = dict(eff)
        updated['turns'] = turns - 1
        if updated['turns'] > 0:
            new_effects.append(updated)

    battle_state['mob_effects'] = new_effects


def has_active_mob_effect(battle_state: dict, *effect_types: str) -> bool:
    mob_effects = battle_state.get('mob_effects', [])
    target = set(effect_types)
    return any(e.get('type') in target and int(e.get('turns', 0)) > 0 for e in mob_effects)


def is_counter_opened_target(battle_state: dict) -> bool:
    """
    Runtime-проверка opened target для Guardian counter payoff.
    Без нового subsystem: читаем существующие runtime эффекты/флаги.
    """
    if has_active_mob_effect(
        battle_state,
        'off_balance',
        'vulnerable',
        'weak',
        'weaken',
        'weakened',
    ):
        return True

    return (
        battle_state.get('vulnerability_turns', 0) > 0
        or battle_state.get('weaken_turns', 0) > 0
        or battle_state.get('disarm_turns', 0) > 0
    )


def get_strongest_active_enemy_weakened_value(battle_state: dict) -> int:
    """
    Возвращает strongest active weakened-процент на мобе.
    Runtime source of truth: battle_state['mob_effects'].
    Legacy weaken_turns/weaken_value поддерживаем как fallback.
    """
    strongest_value = 0
    for eff in battle_state.get('mob_effects', []):
        if eff.get('type') not in ('weak', 'weaken', 'weakened'):
            continue
        if int(eff.get('turns', 0)) <= 0:
            continue
        strongest_value = max(strongest_value, int(eff.get('value', 0)))

    if strongest_value > 0:
        return strongest_value

    if battle_state.get('weaken_turns', 0) > 0:
        return max(0, int(battle_state.get('weaken_value', 0)))

    return 0


def apply_player_start_of_turn_regen(
    battle_state: dict,
    lang: str = 'ru',
) -> list[str]:
    """
    Явный start-of-turn тик регенерации игрока в Combat Core.
    """
    if battle_state.get('regen_turns', 0) <= 0:
        return []

    max_hp = battle_state.get('player_max_hp', 100)
    current_hp = battle_state.get('player_hp', 0)
    regen_amount = battle_state.get('regen_amount', 0)
    healed = max(0, min(regen_amount, max_hp - current_hp))

    battle_state['player_hp'] = min(max_hp, current_hp + regen_amount)
    battle_state['regen_turns'] -= 1

    if healed <= 0:
        return []

    return [t('battle.regen', lang, amount=healed)]


def tick_post_action_timed_trigger_buffs(
    battle_state: dict,
    *,
    skip_resurrection_tick: bool = False,
) -> None:
    """
    Тикает timed trigger баффы после полностью завершённого действия игрока.
    В этом PR обрабатываем только resurrection.
    """
    if skip_resurrection_tick:
        return

    if not battle_state.get('resurrection_active'):
        return

    if battle_state.get('resurrection_turns', 0) > 0:
        battle_state['resurrection_turns'] -= 1

    # Важно: если игрок умер в этом действии, не отключаем бафф до обработки
    # death/resurrection window в handler.
    if battle_state.get('resurrection_turns', 0) <= 0 and battle_state.get('player_hp', 0) > 0:
        battle_state['resurrection_turns'] = 0
        battle_state['resurrection_active'] = False


def tick_post_action_player_buff_durations(battle_state: dict) -> None:
    """
    Тикает post-action длительности оставшихся player buffs в Combat Core.
    Регенерация и resurrection здесь не обрабатываются.
    """
    for key in (
        'defense_buff_turns',
        'berserk_turns',
        'blessing_turns',
        'steady_aim_turns',
        'press_the_line_turns',
        'feint_step_turns',
        'arcane_surge_turns',
        'executioner_focus_turns',
        'battle_stance_turns',
        'spell_echo_turns',
        'quick_channel_turns',
        'berserk_defense_penalty_turns',
    ):
        if battle_state.get(key, 0) > 0:
            battle_state[key] -= 1

    # Berserker cleanup: normalize naturally expired/desynced state
    # so stale values do not survive when timers are inactive.
    berserk_turns = battle_state.get('berserk_turns', 0)
    penalty_turns = battle_state.get('berserk_defense_penalty_turns', 0)
    if berserk_turns <= 0:
        battle_state['berserk_turns'] = 0
        battle_state['berserk_damage'] = 0
    if penalty_turns <= 0 and (
        'berserk_defense_penalty_turns' in battle_state
        or 'berserk_defense_penalty' in battle_state
    ):
        battle_state['berserk_defense_penalty_turns'] = 0
        battle_state['berserk_defense_penalty'] = 0
    has_penalty_runtime = (
        'berserk_defense_penalty_turns' in battle_state
        or 'berserk_defense_penalty' in battle_state
    )
    if has_penalty_runtime and (
        (battle_state.get('berserk_turns', 0) > 0 and battle_state.get('berserk_defense_penalty_turns', 0) <= 0)
        or (battle_state.get('berserk_turns', 0) <= 0 and battle_state.get('berserk_defense_penalty_turns', 0) > 0)
    ):
        battle_state['berserk_turns'] = 0
        battle_state['berserk_damage'] = 0
        battle_state['berserk_defense_penalty_turns'] = 0
        battle_state['berserk_defense_penalty'] = 0

    if battle_state.get('defense_buff_turns', 0) <= 0:
        battle_state['defense_buff_source'] = None


def apply_direct_damage_action_modifiers(
    battle_state: dict,
    base_damage: int,
    *,
    can_consume_guaranteed_crit: bool,
) -> dict:
    """
    Применяет модификаторы только к прямому урону действия игрока.
    Возвращает итоговый урон и информацию, что именно было применено.
    """
    damage = max(0, base_damage)
    modifiers_applied = False
    guaranteed_crit_applied = False

    if damage <= 0:
        return {
            'damage': damage,
            'modifiers_applied': modifiers_applied,
            'guaranteed_crit_applied': guaranteed_crit_applied,
        }

    if can_consume_guaranteed_crit and battle_state.get('guaranteed_crit_turns', 0) > 0:
        damage = int(damage * 2.5)
        battle_state['guaranteed_crit_turns'] -= 1
        modifiers_applied = True
        guaranteed_crit_applied = True

    if battle_state.get('vulnerability_turns', 0) > 0:
        bonus = int(damage * battle_state['vulnerability_value'] / 100)
        damage += bonus
        battle_state['vulnerability_turns'] -= 1
        modifiers_applied = True

    if battle_state.get('press_the_line_turns', 0) > 0:
        bonus = int(damage * battle_state.get('press_the_line_value', 0) / 100)
        damage += bonus
        modifiers_applied = True

    if battle_state.get('berserk_turns', 0) > 0 and battle_state.get('berserk_damage', 0) > 0:
        damage += int(battle_state.get('berserk_damage', 0))
        modifiers_applied = True

    return {
        'damage': damage,
        'modifiers_applied': modifiers_applied,
        'guaranteed_crit_applied': guaranteed_crit_applied,
    }


def finalize_player_direct_damage_action(
    battle_state: dict,
    *,
    base_damage: int,
    can_consume_guaranteed_crit: bool,
    damage_school: str | None = None,
) -> dict:
    """
    Единый финальный этап direct-damage действия игрока:
    1) direct-damage модификаторы;
    2) применение финального урона к HP моба;
    3) structured-результат для вызывающей стороны.
    """
    mob_hp_before = battle_state.get('mob_hp', 0)
    modifier_result = apply_direct_damage_action_modifiers(
        battle_state,
        base_damage,
        can_consume_guaranteed_crit=can_consume_guaranteed_crit,
    )
    final_damage = modifier_result['damage']
    mob_hp_after = max(0, mob_hp_before - final_damage)
    battle_state['mob_hp'] = mob_hp_after

    return {
        'base_damage': base_damage,
        'damage': final_damage,
        'final_damage': final_damage,
        'damage_school': normalize_damage_school(
            damage_school,
            weapon_profile=battle_state.get('weapon_profile'),
            weapon_type=battle_state.get('weapon_type', 'melee'),
        ),
        'mob_hp_before': mob_hp_before,
        'mob_hp_after': mob_hp_after,
        'mob_dead': mob_hp_after <= 0,
        'modifiers_applied': modifier_result['modifiers_applied'],
        'guaranteed_crit_applied': modifier_result['guaranteed_crit_applied'],
    }


def finalize_direct_damage_skill_result(skill_result: dict, lang: str) -> None:
    """
    Финализирует structured-результат direct-damage скилла после модификаторов урона.
    """
    if not skill_result.get('direct_damage_skill'):
        return

    final_damage = skill_result.get('damage', 0)
    log_params = skill_result.get('log_params', {})
    original_total = log_params.get('total')
    log_key = skill_result.get('log_key')

    # Для multi-hit при модификаторах урона не показываем старые части ударов.
    # Переключаемся на честный итоговый лог с финальным уроном.
    if log_key == 'skills.log_damage_multi' and original_total is not None and original_total != final_damage:
        skill_result['log_key'] = 'skills.log_damage'
        skill_result['log_params'] = {
            'name': log_params.get('name', ''),
            'dmg': final_damage,
            'cost': log_params.get('cost', 0),
        }
        skill_result['log_suffixes'] = []
        log_params = skill_result['log_params']

    if 'dmg' in log_params:
        log_params['dmg'] = final_damage
    if 'total' in log_params:
        log_params['total'] = final_damage

    heal_from_damage_ratio = skill_result.get('heal_from_damage_ratio', 0)
    if heal_from_damage_ratio > 0:
        heal_cap_missing_hp = max(0, skill_result.get('heal_cap_missing_hp', 0))
        recomputed_heal = int(final_damage * heal_from_damage_ratio)
        skill_result['heal'] = min(recomputed_heal, heal_cap_missing_hp)
        if 'heal' in log_params:
            log_params['heal'] = skill_result['heal']

    lifesteal_ratio = skill_result.get('lifesteal_ratio', 0)
    if lifesteal_ratio > 0:
        skill_result['heal'] = int(final_damage * lifesteal_ratio)

    skill_result['log'] = build_skill_result_log(skill_result, lang)


def apply_post_hit_skill_actions(skill_result: dict, battle_state: dict) -> None:
    """
    Применяет узкие post-hit действия скилла только если direct hit реально прошёл.
    """
    if not skill_result.get('direct_damage_skill'):
        return

    action_result = skill_result.get('direct_damage_result', {})
    if action_result.get('final_damage', 0) <= 0:
        return

    for action in skill_result.get('post_hit_actions', []):
        action_type = action.get('type')

        if action_type == 'refresh_defense_buff':
            turns = int(action.get('turns', 0))
            value = int(action.get('value', 0))
            if turns > 0 and value > 0:
                battle_state['defense_buff_turns'] = turns
                battle_state['defense_buff_value'] = value
                battle_state['defense_buff_source'] = action.get('source')
                skill_result['log_key'] = action.get('log_key', skill_result.get('log_key'))
                existing_params = skill_result.get('log_params', {})
                skill_result.setdefault('log_params', {})
                skill_result['log_params']['name'] = existing_params.get('name', skill_result['log_params'].get('name', ''))
                skill_result['log_params']['cost'] = existing_params.get('cost', skill_result['log_params'].get('cost', 0))
                skill_result['log_params']['dmg'] = skill_result.get('damage', skill_result['log_params'].get('dmg', 0))
                skill_result['log_params']['value'] = value
                skill_result['log_params']['turns'] = turns
        elif action_type == 'consume_vulnerability':
            if battle_state.get('vulnerability_turns', 0) > 0:
                battle_state['vulnerability_turns'] = 0
                battle_state['vulnerability_value'] = 0
        elif action_type == 'consume_burn_and_blessing':
            mob_effects = battle_state.get('mob_effects', [])
            battle_state['mob_effects'] = [
                eff for eff in mob_effects
                if not (eff.get('type') == 'burn' and int(eff.get('turns', 0)) > 0)
            ]
            if battle_state.get('blessing_turns', 0) > 0:
                battle_state['blessing_turns'] = 0
                battle_state['blessing_value'] = 0
        elif action_type == 'consume_envenom_setup':
            battle_state['envenom_blades_active'] = False
            battle_state['envenom_active'] = False
        elif action_type == 'consume_poison_effects':
            mob_effects = battle_state.get('mob_effects', [])
            battle_state['mob_effects'] = [
                eff for eff in mob_effects
                if not (eff.get('type') == 'poison' and int(eff.get('turns', 0)) > 0)
            ]
        elif action_type == 'consume_steady_aim':
            if battle_state.get('steady_aim_turns', 0) > 0:
                battle_state['steady_aim_turns'] = 0
        elif action_type == 'consume_arcane_surge_setup':
            if battle_state.get('arcane_surge_turns', 0) > 0:
                battle_state['arcane_surge_turns'] = 0
                battle_state['arcane_surge_value'] = 0
        elif action_type == 'consume_spell_echo_setup':
            if battle_state.get('spell_echo_turns', 0) > 0:
                battle_state['spell_echo_turns'] = 0
                battle_state['spell_echo_value'] = 0
        elif action_type == 'consume_quick_channel_setup':
            if battle_state.get('quick_channel_turns', 0) > 0:
                battle_state['quick_channel_turns'] = 0
                battle_state['quick_channel_value'] = 0
        elif action_type == 'consume_dueling_ward_setup':
            if battle_state.get('defense_buff_turns', 0) > 0:
                battle_state['defense_buff_turns'] = 0
                battle_state['defense_buff_value'] = 0
                battle_state['defense_buff_source'] = None
        elif action_type == 'consume_executioner_focus':
            if battle_state.get('executioner_focus_turns', 0) > 0:
                battle_state['executioner_focus_turns'] = 0
                battle_state['executioner_focus_value'] = 0
        elif action_type == 'consume_battle_stance':
            if battle_state.get('battle_stance_turns', 0) > 0:
                battle_state['battle_stance_turns'] = 0
                battle_state['battle_stance_value'] = 0
        elif action_type == 'consume_berserk_setup':
            battle_state['berserk_turns'] = 0
            battle_state['berserk_damage'] = 0
            battle_state['berserk_defense_penalty_turns'] = 0
            battle_state['berserk_defense_penalty'] = 0


def resolve_enemy_targeted_direct_damage_skill_action(
    player: dict,
    mob: dict,
    battle_state: dict,
    skill_result: dict,
    *,
    lang: str = 'ru',
) -> dict:
    """
    Узкий helper для Accuracy/Evasion phase 2:
    hit-gate только для enemy-targeted direct-damage skills.
    """
    if not skill_result.get('direct_damage_skill'):
        return {'handled': False, 'is_hit': None, 'hit_check': None}
    if skill_result.get('target_kind') != 'enemy':
        return {'handled': False, 'is_hit': None, 'hit_check': None}

    guaranteed_hit = skill_result.get('guaranteed_hit') is True
    if guaranteed_hit:
        hit_check = {
            'outcome': 'guaranteed_hit',
            'is_hit': True,
            'hit_chance': 100,
            'roll': 0,
            'accuracy_rating': None,
            'evasion_rating': None,
            'guaranteed_hit': True,
        }
    else:
        base_accuracy = get_player_accuracy_rating(player, battle_state)
        accuracy_bonus = int(skill_result.get('accuracy_bonus', 0))
        adjusted_accuracy = base_accuracy + accuracy_bonus
        if skill_result.get('ignore_evasion') is True:
            evasion_rating = 0
        else:
            evasion_rating = get_enemy_evasion_rating(mob, battle_state)
        hit_check = resolve_hit_check(adjusted_accuracy, evasion_rating)

    if not hit_check['is_hit']:
        base_damage = skill_result.get('damage', 0)
        skill_result['damage'] = 0
        skill_result['effects'] = []
        skill_result['direct_damage_result'] = {
            'base_damage': base_damage,
            'damage': 0,
            'final_damage': 0,
            'damage_school': skill_result.get('damage_school'),
            'mob_hp_before': battle_state.get('mob_hp', 0),
            'mob_hp_after': battle_state.get('mob_hp', 0),
            'mob_dead': False,
            'modifiers_applied': False,
            'guaranteed_crit_applied': False,
            'hit_check': hit_check,
        }
        skill_result['log'] = t('battle.mob_dodge', lang)
        return {'handled': True, 'is_hit': False, 'hit_check': hit_check}

    action_result = finalize_player_direct_damage_action(
        battle_state,
        base_damage=skill_result.get('damage', 0),
        can_consume_guaranteed_crit=True,
        damage_school=skill_result.get('damage_school'),
    )
    action_result['hit_check'] = hit_check
    skill_result['damage'] = action_result['final_damage']
    skill_result['direct_damage_result'] = action_result
    apply_post_hit_skill_actions(skill_result, battle_state)
    finalize_direct_damage_skill_result(skill_result, lang)
    return {'handled': True, 'is_hit': True, 'hit_check': hit_check}


def resolve_enemy_damage_against_player(
    battle_state: dict,
    *,
    lang: str = 'ru',
    mob_result: dict | None = None,
    mob: dict | None = None,
    player: dict | None = None,
) -> dict:
    """
    Централизует defensive/timed buffs для прямого урона моба по игроку.
    Порядок:
    1) invincible_turns
    2) dodge_buff_turns
    3) если урон проходит: defense_buff_turns mitigation
    4) если урон проходит: disarm_turns mitigation
    5) fire_shield_turns в единой post-hit точке
    """
    log = []

    if mob_result is None:
        if battle_state.get('invincible_turns', 0) > 0:
            battle_state['invincible_turns'] -= 1
            log.append(t('battle.invincible', lang))
            return {
                'skip_mob_attack': True,
                'damage_landed': False,
                'player_damage': 0,
                'mob_reflect_damage': 0,
                'log': log,
            }

        if battle_state.get('dodge_buff_turns', 0) > 0:
            dodge_chance = battle_state.get('dodge_buff_value', 0) / 100
            battle_state['dodge_buff_turns'] -= 1
            if random.random() < dodge_chance:
                log.append(t('battle.player_dodge', lang))
                return {
                    'skip_mob_attack': True,
                    'damage_landed': False,
                    'player_damage': 0,
                    'mob_reflect_damage': 0,
                    'log': log,
                }

        if mob is not None and player is not None:
            hit_check = resolve_hit_check(
                get_enemy_accuracy_rating(mob, battle_state),
                get_player_evasion_rating(player, battle_state),
            )
            if not hit_check['is_hit']:
                log.append(t('battle.player_dodge', lang))
                return {
                    'skip_mob_attack': True,
                    'damage_landed': False,
                    'player_damage': 0,
                    'mob_reflect_damage': 0,
                    'hit_check': hit_check,
                    'log': log,
                }

        return {
            'skip_mob_attack': False,
            'damage_landed': False,
            'player_damage': 0,
            'mob_reflect_damage': 0,
            'hit_check': None,
            'log': log,
        }

    mob_dmg = mob_result.get('damage', 0)
    if battle_state.get('defense_buff_turns', 0) > 0:
        mob_dmg = int(mob_dmg * (1 - battle_state['defense_buff_value'] / 100))

    if battle_state.get('disarm_turns', 0) > 0:
        mob_dmg = int(mob_dmg * (1 - battle_state['disarm_value'] / 100))
        battle_state['disarm_turns'] -= 1

    if battle_state.get('berserk_defense_penalty_turns', 0) > 0:
        penalty = max(0, int(battle_state.get('berserk_defense_penalty', 0)))
        mob_dmg = int(mob_dmg * (1 + penalty / 100))

    weakened_value = get_strongest_active_enemy_weakened_value(battle_state)
    if weakened_value > 0:
        mob_dmg = int(mob_dmg * (1 - weakened_value / 100))

    shield_dmg = 0
    if battle_state.get('fire_shield_turns', 0) > 0:
        shield_dmg = battle_state['fire_shield_value']
        battle_state['fire_shield_turns'] -= 1

    return {
        'skip_mob_attack': False,
        'damage_landed': True,
        'player_damage': mob_dmg,
        'mob_reflect_damage': shield_dmg,
        'log': log,
    }


def tick_weaken_duration_after_enemy_response(battle_state: dict) -> None:
    """
    Уменьшает длительность weaken в конце enemy-response фазы
    независимо от того, попала ли атака моба.
    """
    if battle_state.get('weaken_turns', 0) > 0:
        battle_state['weaken_turns'] -= 1
        if battle_state['weaken_turns'] <= 0:
            battle_state['weaken_turns'] = 0
            battle_state['weaken_value'] = 0


def resolve_enemy_response_trigger_buffs(
    battle_state: dict,
    *,
    mob_result: dict,
    lang: str = 'ru',
) -> dict:
    """
    Централизует trigger-buff ответы на действие моба.
    Сейчас: parry как явный enemy-response trigger.
    """
    log = []

    if not battle_state.get('parry_active'):
        return {
            'triggered': False,
            'skip_player_damage': False,
            'log': log,
        }

    incoming_damage = max(0, int(mob_result.get('damage', 0)))
    parry_ratio = battle_state.get('parry_value', 1.0)
    if (
        battle_state.get('weapon_profile') == 'sword_1h'
        and battle_state.get('offhand_profile') == 'shield'
    ):
        parry_ratio *= 1.20
    parry_damage = int(incoming_damage * parry_ratio)

    battle_state['mob_hp'] = max(0, battle_state['mob_hp'] - parry_damage)
    battle_state['parry_active'] = False
    log.append(t('battle.parry_reflect', lang, damage=parry_damage))

    return {
        'triggered': True,
        'skip_player_damage': True,
        'log': log,
    }


def process_skill_turn(
    skill_id: str,
    player: dict,
    mob: dict,
    battle_state: dict,
    user_id: int,
    lang: str = 'ru',
) -> dict:
    """
    Обрабатывает ход игрока через скилл.
    Сохраняет текущий порядок шагов из handler-логики:
    use_skill -> применение результата -> pre-enemy ticks -> ответ моба.
    """
    precheck_result = precheck_skill_use(
        skill_id,
        battle_state.get('player_mana', 0),
        user_id,
        lang,
    )
    if not precheck_result.get('success'):
        return {
            'success': False,
            'skill_result': precheck_result,
            'battle_state': battle_state,
        }

    log = battle_state.get('log', [])
    log.extend(apply_player_start_of_turn_regen(battle_state, lang))

    player_state = dict(player)
    player_state['hp'] = battle_state['player_hp']
    player_state['mana'] = battle_state['player_mana']

    mob_state = {
        'hp': battle_state['mob_hp'],
        'defense': mob.get('defense', 0),
        'effects': battle_state.get('mob_effects', []),
    }

    skill_result = use_skill(skill_id, player_state, mob_state, battle_state, user_id, lang)
    if not skill_result.get('success'):
        return {
            'success': False,
            'skill_result': skill_result,
            'battle_state': battle_state,
        }

    direct_damage = skill_result.get('damage', 0)
    if direct_damage > 0:
        gate_result = resolve_enemy_targeted_direct_damage_skill_action(
            player_state,
            mob,
            battle_state,
            skill_result,
            lang=lang,
        )
        if not gate_result.get('handled'):
            action_result = finalize_player_direct_damage_action(
                battle_state,
                base_damage=direct_damage,
                can_consume_guaranteed_crit=True,
                damage_school=skill_result.get('damage_school'),
            )
            skill_result['damage'] = action_result['final_damage']
            skill_result['direct_damage_result'] = action_result
            apply_post_hit_skill_actions(skill_result, battle_state)
            finalize_direct_damage_skill_result(skill_result, lang)

    log.append(skill_result['log'])

    if skill_result['heal'] > 0 and not skill_result.get('heal_applied_runtime'):
        battle_state['player_hp'] = min(
            battle_state['player_max_hp'],
            battle_state['player_hp'] + skill_result['heal']
        )

    if skill_result['effects']:
        if 'mob_effects' not in battle_state:
            battle_state['mob_effects'] = []
        battle_state['mob_effects'].extend(skill_result['effects'])

    if battle_state['mob_hp'] > 0:
        log.extend(apply_pre_enemy_response_ticks(mob, battle_state))

    if battle_state['mob_hp'] > 0:
        player_state['hp'] = battle_state['player_hp']
        log.extend(resolve_enemy_response(mob, player_state, battle_state, lang=lang, user_id=user_id))

    tick_post_action_timed_trigger_buffs(
        battle_state,
        skip_resurrection_tick=(skill_id == 'resurrection'),
    )

    battle_state['mob_dead'] = battle_state['mob_hp'] <= 0
    battle_state['player_dead'] = battle_state['player_hp'] <= 0
    battle_state['log'] = log[-6:]

    return {
        'success': True,
        'skill_result': skill_result,
        'battle_state': battle_state,
    }



def resolve_enemy_response(
    mob: dict,
    player: dict,
    battle_state: dict,
    lang: str = 'ru',
    user_id: int | None = None,
) -> list[str]:
    """
    Единый ответ моба после действия игрока.
    Обновляет HP/эффекты в battle_state и возвращает лог строками.
    """
    log = []

    mob_stunned = has_active_mob_effect(battle_state, 'stun', 'freeze')
    if mob_stunned:
        log.append(t('battle.stunned', lang, mob_name=get_mob_name(mob['id'], lang)))
        battle_state['player_hp'] = player['hp']
        decrement_mob_non_dot_effects_after_response(battle_state)
        tick_weaken_duration_after_enemy_response(battle_state)
        return log

    if battle_state.get('parry_active'):
        hit_check = resolve_hit_check(
            get_enemy_accuracy_rating(mob, battle_state),
            get_player_evasion_rating(player, battle_state),
        )
        if not hit_check['is_hit']:
            log.append(t('battle.player_dodge', lang))
            battle_state['player_hp'] = player['hp']
            decrement_mob_non_dot_effects_after_response(battle_state)
            tick_weaken_duration_after_enemy_response(battle_state)
            return log

        mob_result = mob_attack(mob, player, allow_dodge=False)
        trigger_result = resolve_enemy_response_trigger_buffs(
            battle_state,
            mob_result=mob_result,
            lang=lang,
        )
        log.extend(trigger_result['log'])
        battle_state['player_hp'] = player['hp']
        decrement_mob_non_dot_effects_after_response(battle_state)
        tick_weaken_duration_after_enemy_response(battle_state)
        return log

    pre_damage_result = resolve_enemy_damage_against_player(
        battle_state,
        lang=lang,
        mob=mob,
        player=player,
    )
    log.extend(pre_damage_result['log'])
    if pre_damage_result['skip_mob_attack']:
        battle_state['player_hp'] = player['hp']
        decrement_mob_non_dot_effects_after_response(battle_state)
        tick_weaken_duration_after_enemy_response(battle_state)
        return log

    if has_active_mob_effect(battle_state, 'slow') and random.random() < SLOW_MISS_CHANCE:
        log.append(t('battle.mob_miss_slow', lang, mob_name=get_mob_name(mob['id'], lang)))
        battle_state['player_hp'] = player['hp']
        decrement_mob_non_dot_effects_after_response(battle_state)
        tick_weaken_duration_after_enemy_response(battle_state)
        return log

    mob_result = mob_attack(mob, player, allow_dodge=False)
    if mob_result.get('type') == 'dodge':
        log.append(t('battle.player_dodge', lang))
        battle_state['player_hp'] = player['hp']
        decrement_mob_non_dot_effects_after_response(battle_state)
        tick_weaken_duration_after_enemy_response(battle_state)
        return log

    damage_result = resolve_enemy_damage_against_player(
        battle_state,
        lang=lang,
        mob_result=mob_result,
    )
    log.extend(damage_result['log'])
    if not damage_result['damage_landed']:
        battle_state['player_hp'] = player['hp']
        decrement_mob_non_dot_effects_after_response(battle_state)
        tick_weaken_duration_after_enemy_response(battle_state)
        return log

    mob_dmg = damage_result['player_damage']
    player['hp'] = max(0, player['hp'] - mob_dmg)
    battle_state['player_hp'] = player['hp']
    log.append(t('battle.mob_attack', lang,
                 mob_name=get_mob_name(mob['id'], lang),
                 damage=mob_dmg))

    shield_dmg = damage_result['mob_reflect_damage']
    if shield_dmg > 0:
        battle_state['mob_hp'] = max(0, battle_state['mob_hp'] - shield_dmg)
        log.append(t('battle.fire_shield_reflect', lang, damage=shield_dmg))

    if user_id is not None and mob_dmg > 0:
        from game.weapon_mastery import get_skill_level
        counter_level = get_skill_level(user_id, 'counter')
        if counter_level > 0 and battle_state.get('weapon_profile') == 'sword_1h':
            counter_skill = get_skill('counter') or {}
            counter_chance = 0.16 + 0.04 * (counter_level - 1)
            opened_target = is_counter_opened_target(battle_state)
            defense_setup_active = battle_state.get('defense_buff_turns', 0) > 0

            if battle_state.get('offhand_profile') == 'shield':
                counter_chance += 0.10
            if defense_setup_active:
                counter_chance += 0.04

            if random.random() < counter_chance:
                counter_dmg = int(mob_dmg * (0.30 + 0.07 * counter_level))

                if opened_target and defense_setup_active:
                    counter_dmg = int(counter_dmg * counter_skill.get('payoff_opened_defense_mult', 1.40))
                    counter_log_key = 'battle.counter_attack_opened_defense'
                elif opened_target:
                    counter_dmg = int(counter_dmg * counter_skill.get('payoff_opened_mult', 1.30))
                    counter_log_key = 'battle.counter_attack_opened'
                elif defense_setup_active:
                    counter_dmg = int(counter_dmg * counter_skill.get('payoff_defense_setup_mult', 1.10))
                    counter_log_key = 'battle.counter_attack_defense'
                else:
                    counter_log_key = 'battle.counter_attack'

                battle_state['mob_hp'] = max(0, battle_state['mob_hp'] - counter_dmg)
                log.append(t(counter_log_key, lang, damage=counter_dmg))

    decrement_mob_non_dot_effects_after_response(battle_state)
    tick_weaken_duration_after_enemy_response(battle_state)
    return log

# ────────────────────────────────────────
# ОДИН ХОД ИГРОКА
# ────────────────────────────────────────

def player_attack(player: dict, mob_state: dict) -> dict:
    """
    Игрок атакует моба.
    Pure helper: только рассчитывает normal-attack урон и исход, без мутации mob_state.
    """
    stats = {
        'strength':  player['strength'],
        'agility':   player['agility'],
        'intuition': player['intuition'],
        'vitality':  player['vitality'],
        'wisdom':    player['wisdom'],
        'luck':      player['luck'],
    }

    weapon_type = player.get('weapon_type', 'melee')
    weapon_profile = player.get('weapon_profile')
    damage_school = player.get('damage_school')
    base_damage = player.get('weapon_damage', 10)
    if player.get('guaranteed_crit'):
        is_crit = True
    else:
        is_crit = roll_crit(player['luck'], player['agility'])
    damage = calc_final_damage(
        base_damage,
        stats,
        weapon_type,
        is_crit,
        weapon_profile=weapon_profile,
        damage_school=damage_school,
        armor_class=player.get('armor_class'),
        offhand_profile=player.get('offhand_profile'),
        encumbrance=player.get('encumbrance'),
    )

    # Снижаем урон на защиту моба
    mob_defense = mob_state.get('defense', 0)
    final_damage = apply_defense(damage, mob_defense)

    mob_hp_before = mob_state.get('hp', 0)
    mob_hp_after = max(0, mob_hp_before - final_damage)

    return {
        'type': 'player_attack',
        'damage': final_damage,
        'is_crit': is_crit,
        'mob_dead': mob_hp_after <= 0,
        'mob_hp': mob_hp_after,
    }


def resolve_normal_attack_action(
    player: dict,
    mob: dict,
    battle_state: dict,
    *,
    lang: str = 'ru',
) -> dict:
    """
    Явный helper normal attack действия игрока.
    Централизует:
    - вызов player_attack(...),
    - финализацию direct damage через finalize_player_direct_damage_action(...),
    - текущее поведение guaranteed-crit для normal attack,
    - формирование structured-результата для вызывающей стороны.
    """
    mob_state = {
        'hp': battle_state.get('mob_hp', 0),
        'defense': mob.get('defense', 0),
    }
    should_force_crit = battle_state.get('guaranteed_crit_turns', 0) > 0

    hit_check = resolve_hit_check(
        get_player_accuracy_rating(player, battle_state),
        get_enemy_evasion_rating(mob, battle_state),
    )
    if not hit_check['is_hit']:
        return {
            'damage': 0,
            'is_crit': False,
            'mob_dead': False,
            'mob_hp_after': battle_state.get('mob_hp', 0),
            'log_line': t('battle.mob_dodge', lang),
            'direct_damage_result': None,
            'hit_check': hit_check,
        }

    attack_result = player_attack(player, mob_state)
    action_result = finalize_player_direct_damage_action(
        battle_state,
        base_damage=attack_result['damage'],
        can_consume_guaranteed_crit=False,
        damage_school=battle_state.get('damage_school'),
    )

    is_crit = attack_result.get('is_crit', False)
    if is_crit and should_force_crit:
        battle_state['guaranteed_crit_turns'] -= 1

    if is_crit:
        log_line = t('battle.attack_crit', lang, damage=action_result['final_damage'])
    else:
        log_line = t('battle.attack_hit', lang, damage=action_result['final_damage'])

    return {
        'damage': action_result['final_damage'],
        'is_crit': is_crit,
        'mob_dead': action_result['mob_dead'],
        'mob_hp_after': action_result['mob_hp_after'],
        'log_line': log_line,
        'direct_damage_result': action_result,
        'hit_check': hit_check,
    }

# ────────────────────────────────────────
# ОДИН ХОД МОБА
# ────────────────────────────────────────

def mob_attack(mob: dict, player: dict, *, allow_dodge: bool = True) -> dict:
    """
    Моб атакует игрока.
    Возвращает словарь с результатом и новым HP игрока.
    """
    # Проверка уклонения
    if allow_dodge:
        dodged = roll_dodge(
            player['agility'],
            armor_class=player.get('armor_class'),
            encumbrance=player.get('encumbrance'),
        )
        if dodged:
            return {
                'type':       'dodge',
                'damage':     0,
                'player_hp':  player['hp'],
            }

    # Урон моба
    base_damage = calc_mob_damage(mob)

    incoming_school = normalize_damage_school(
        mob.get('damage_school'),
        weapon_profile=mob.get('weapon_profile'),
        weapon_type=mob.get('weapon_type', 'melee'),
    )

    # Защита игрока зависит от типа урона моба
    if incoming_school in ('magic', 'holy'):
        defense = calc_magic_defense(player['wisdom'])
    else:
        defense = calc_physical_defense(player['vitality'])
    defense_multiplier = (
        calc_armor_class_defense_multiplier(player.get('armor_class'))
        * calc_offhand_defense_multiplier(player.get('offhand_profile'))
    )
    defense = int(defense * defense_multiplier)

    # Снижение входящего урона от Ловкости — только против physical
    if incoming_school == 'physical':
        agi_reduction = calc_physical_damage_reduction(player['agility'])
        base_damage = int(base_damage * (1 - agi_reduction / 100))

    final_damage  = apply_defense(base_damage, defense)
    new_hp        = max(0, player['hp'] - final_damage)

    return {
        'type':       'mob_attack',
        'damage':     final_damage,
        'player_hp':  new_hp,
        'dodged':     False,
    }

# ────────────────────────────────────────
# ИНИЦИАЛИЗАЦИЯ БОЯ
# ────────────────────────────────────────

def init_battle(player: dict, mob: dict, mob_first: bool = False) -> dict:
    """
    Создаёт начальное состояние боя.
    mob_first=True если моб атакует первым (провал побега).
    """
    priority_player = calc_action_priority(
        player['agility'],
        player['luck'],
        armor_class=player.get('armor_class'),
        offhand_profile=player.get('offhand_profile'),
        encumbrance=player.get('encumbrance'),
    )
    priority_mob    = mob['level'] * 3  # мобы получают приоритет от уровня

    if mob_first:
        player_goes_first = False
    else:
        player_goes_first = priority_player >= priority_mob

    return {
        'player_hp':       player['hp'],
        'player_max_hp':   player['max_hp'],
        'player_mana':     player['mana'],
        'player_max_mana': player['max_mana'],
        'mob_hp':          mob['hp'],
        'mob_max_hp':      mob['hp'],
        'mob_id':          mob['id'],
        'mob_name':        mob['name'],
        'mob_level':       mob['level'],
        'player_goes_first': player_goes_first,
        'turn':            1,
        'log':             [],
        # Существующие баффы
        'parry_active':         False,
        'parry_value':          0.0,
        'defense_buff_turns':   0,
        'defense_buff_value':   0,
        'defense_buff_source':  None,
        'berserk_turns':        0,
        'berserk_damage':       0,
        'berserk_defense_penalty_turns': 0,
        'berserk_defense_penalty': 0,
        'blessing_turns':       0,
        'blessing_value':       0,
        'regen_turns':          0,
        'regen_amount':         0,
        'resurrection_active':  False,
        'resurrection_hp':      0,
        'resurrection_turns':   0,
        # Новые баффы
        'invincible_turns':     0,
        'dodge_buff_turns':     0,
        'dodge_buff_value':     0,
        'guaranteed_crit_turns':0,
        'steady_aim_turns':     0,
        'hunters_mark_turns':   0,
        'hunters_mark_value':   0,
        'vulnerability_turns':  0,
        'vulnerability_value':  0,
        'press_the_line_turns': 0,
        'press_the_line_value': 0,
        'arcane_surge_turns':   0,
        'arcane_surge_value':   0,
        'spell_echo_turns':     0,
        'spell_echo_value':     0,
        'quick_channel_turns':  0,
        'quick_channel_value':  0,
        'executioner_focus_turns': 0,
        'executioner_focus_value': 0,
        'battle_stance_turns':  0,
        'battle_stance_value':  0,
        'disarm_turns':         0,
        'disarm_value':         0,
        'weaken_turns':         0,
        'weaken_value':         0,
        'fire_shield_turns':    0,
        'fire_shield_value':    0,
        'envenom_active':       False,
        # Прочее
        'mob_effects':          [],
        'allies':               {},
        'damage_taken':         0,
        'potions_used':         0,
        'skills_used':          [],
        'normal_attacks':       0,
        'buffs_used':           False,
        'weapon_id':            'unarmed',
        'weapon_type':          'melee',
        'weapon_profile':       'unarmed',
        'armor_class':          None,
        'offhand_profile':      'none',
        'damage_school':        'physical',
        'encumbrance':          None,
        'weapon_damage':        10,
        'weapon_name':          '',
        'mastery_level':        1,
        'mastery_exp':          0,
    }

# ────────────────────────────────────────
# ОБРАБОТКА ПОЛНОГО ХОДА
# ────────────────────────────────────────

def process_turn(player: dict, mob: dict, battle_state: dict, lang: str = 'ru', user_id: int | None = None) -> dict:
    log = []
    log.extend(apply_player_start_of_turn_regen(battle_state, lang))
    log.extend(apply_mob_effect_ticks(mob, battle_state))
    player = dict(player)
    player['hp'] = battle_state['player_hp']
    player['weapon_type']   = battle_state.get('weapon_type', 'melee')
    player['weapon_profile'] = battle_state.get('weapon_profile', 'unarmed')
    player['weapon_damage'] = battle_state.get('weapon_damage', 10)
    player['armor_class'] = battle_state.get('armor_class')
    player['offhand_profile'] = battle_state.get('offhand_profile', 'none')
    player['encumbrance'] = battle_state.get('encumbrance')

    if battle_state.get('blessing_turns', 0) > 0:
        mult = 1 + battle_state['blessing_value'] / 100
        for stat in ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck'):
            if stat in player:
                player[stat] = int(player[stat] * mult)

    player['guaranteed_crit'] = battle_state.get('guaranteed_crit_turns', 0) > 0

    if battle_state['player_goes_first']:
        attack_result = resolve_normal_attack_action(player, mob, battle_state, lang=lang)
        log.append(attack_result['log_line'])

        if not attack_result['mob_dead']:
            log.extend(resolve_enemy_response(mob, player, battle_state, lang=lang, user_id=user_id))
    else:
        log.extend(resolve_enemy_response(mob, player, battle_state, lang=lang, user_id=user_id))

        if player['hp'] > 0:
            attack_result = resolve_normal_attack_action(player, mob, battle_state, lang=lang)
            log.append(attack_result['log_line'])

    # Сохраняем прежний тайминг normal attack flow: player buffs тикают после exchange
    tick_post_action_player_buff_durations(battle_state)
    tick_post_action_timed_trigger_buffs(battle_state)

    battle_state['mob_dead']    = battle_state['mob_hp'] <= 0
    battle_state['player_dead'] = player['hp'] <= 0
    battle_state['player_hp'] = player['hp']
    battle_state['turn']     += 1
    battle_state['log']       = log

    return battle_state

# ────────────────────────────────────────
# РАСЧЁТ НАГРАД
# ────────────────────────────────────────

def calc_rewards(mob: dict) -> dict:
    """Считает награду за победу над мобом."""
    gold = random.randint(mob['gold_min'], mob['gold_max'])
    exp  = mob['exp_reward']

    # Лут
    loot = []
    for item_id, chance in mob.get('loot_table', []):
        if random.random() < chance:
            loot.append(item_id)

    return {
        'exp':  exp,
        'gold': gold,
        'loot': loot,
    }

# ────────────────────────────────────────
# СМЕРТЬ ИГРОКА
# ────────────────────────────────────────

def calc_death_penalty(player: dict) -> dict:
    """Считает штраф за смерть."""
    exp_loss  = int(player['exp'] * 0.10)   # -10% опыта
    gold_loss = int(player['gold'] * 0.15)  # -15% золота
    return {
        'exp_loss':  exp_loss,
        'gold_loss': gold_loss,
    }

print('✅ game/combat.py создан!')
