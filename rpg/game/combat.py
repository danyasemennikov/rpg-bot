# ============================================================
# combat.py — боевой движок
# ============================================================

import random
import sys
sys.path.append('/content/rpg_bot')

from game.balance import (
    calc_final_damage, calc_dodge_chance, calc_crit_chance,
    calc_physical_defense, calc_magic_defense,
    calc_crit_reduction, calc_action_priority
)
from game.i18n import t, get_mob_name
from game.skill_engine import (
    apply_player_buffs,
    apply_mob_effects,
    build_skill_result_log,
    use_skill,
)


# ────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ────────────────────────────────────────

def roll_crit(luck: int, agility: int = 0, enemy_luck: int = 0) -> bool:
    """Проверка на крит с учётом снижения от удачи врага."""
    crit_chance = calc_crit_chance(luck, agility)
    crit_reduction = calc_crit_reduction(enemy_luck) / 100
    final_chance = max(0, crit_chance - crit_reduction)
    return random.random() < final_chance

def roll_dodge(agility: int) -> bool:
    """Проверка на уклонение."""
    return random.random() < calc_dodge_chance(agility)

def get_weapon_type(player_equipment: dict) -> str:
    """Определяет тип оружия игрока. По умолчанию melee."""
    return player_equipment.get('weapon_type', 'melee')

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

    buff_log = apply_player_buffs(battle_state)
    if buff_log:
        log.append(buff_log)

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

    if battle_state.get('hunters_mark_turns', 0) > 0:
        bonus = int(damage * battle_state['hunters_mark_value'] / 100)
        damage += bonus
        battle_state['hunters_mark_turns'] -= 1
        modifiers_applied = True

    if battle_state.get('vulnerability_turns', 0) > 0:
        bonus = int(damage * battle_state['vulnerability_value'] / 100)
        damage += bonus
        battle_state['vulnerability_turns'] -= 1
        modifiers_applied = True

    return {
        'damage': damage,
        'modifiers_applied': modifiers_applied,
        'guaranteed_crit_applied': guaranteed_crit_applied,
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

    lifesteal_ratio = skill_result.get('lifesteal_ratio', 0)
    if lifesteal_ratio > 0:
        skill_result['heal'] = int(final_damage * lifesteal_ratio)

    skill_result['log'] = build_skill_result_log(skill_result, lang)


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
        damage_result = apply_direct_damage_action_modifiers(
            battle_state,
            direct_damage,
            can_consume_guaranteed_crit=True,
        )
        skill_result['damage'] = damage_result['damage']
        battle_state['mob_hp'] = max(0, battle_state['mob_hp'] - skill_result['damage'])
        finalize_direct_damage_skill_result(skill_result, lang)

    log = battle_state.get('log', [])
    log.append(skill_result['log'])

    if skill_result['heal'] > 0:
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

    mob_effects = battle_state.get('mob_effects', [])
    mob_stunned = any(e['type'] in ('stun', 'freeze', 'slow') for e in mob_effects)
    if mob_stunned:
        log.append(t('battle.stunned', lang, mob_name=get_mob_name(mob['id'], lang)))
        battle_state['player_hp'] = player['hp']
        return log

    if battle_state.get('parry_active'):
        mob_result = mob_attack(mob, player)
        parry_dmg = int(mob_result['damage'] * battle_state.get('parry_value', 1.0))
        battle_state['mob_hp'] = max(0, battle_state['mob_hp'] - parry_dmg)
        battle_state['parry_active'] = False
        log.append(t('battle.parry_reflect', lang, damage=parry_dmg))
        battle_state['player_hp'] = player['hp']
        return log

    mob_dodged = False
    if battle_state.get('invincible_turns', 0) > 0:
        mob_dodged = True
        battle_state['invincible_turns'] -= 1
        log.append(t('battle.invincible', lang))
    elif battle_state.get('dodge_buff_turns', 0) > 0:
        dodge_chance = battle_state.get('dodge_buff_value', 0) / 100
        if random.random() < dodge_chance:
            mob_dodged = True
            log.append(t('battle.player_dodge', lang))
        battle_state['dodge_buff_turns'] -= 1

    if mob_dodged:
        battle_state['player_hp'] = player['hp']
        return log

    mob_result = mob_attack(mob, player)
    if mob_result.get('type') == 'dodge':
        log.append(t('battle.player_dodge', lang))
        battle_state['player_hp'] = player['hp']
        return log

    mob_dmg = mob_result['damage']
    if battle_state.get('defense_buff_turns', 0) > 0:
        mob_dmg = int(mob_dmg * (1 - battle_state['defense_buff_value'] / 100))
    if battle_state.get('disarm_turns', 0) > 0:
        mob_dmg = int(mob_dmg * (1 - battle_state['disarm_value'] / 100))
        battle_state['disarm_turns'] -= 1

    player['hp'] = max(0, player['hp'] - mob_dmg)
    battle_state['player_hp'] = player['hp']
    log.append(t('battle.mob_attack', lang,
                 mob_name=get_mob_name(mob['id'], lang),
                 damage=mob_dmg))

    if battle_state.get('fire_shield_turns', 0) > 0:
        shield_dmg = battle_state['fire_shield_value']
        battle_state['mob_hp'] = max(0, battle_state['mob_hp'] - shield_dmg)
        battle_state['fire_shield_turns'] -= 1
        log.append(t('battle.fire_shield_reflect', lang, damage=shield_dmg))

    if user_id is not None and mob_dmg > 0:
        from game.weapon_mastery import get_skill_level
        counter_level = get_skill_level(user_id, 'counter')
        if counter_level > 0:
            counter_chance = 0.30 + 0.05 * (counter_level - 1)
            if random.random() < counter_chance:
                counter_dmg = int(mob_dmg * (0.5 + 0.1 * counter_level))
                battle_state['mob_hp'] = max(0, battle_state['mob_hp'] - counter_dmg)
                log.append(t('battle.counter_attack', lang, damage=counter_dmg))

    return log

# ────────────────────────────────────────
# ОДИН ХОД ИГРОКА
# ────────────────────────────────────────

def player_attack(player: dict, mob_state: dict) -> dict:
    """
    Игрок атакует моба.
    Возвращает словарь с результатом хода.
    """
    stats = {
        'strength':  player['strength'],
        'agility':   player['agility'],
        'intuition': player['intuition'],
        'vitality':  player['vitality'],
        'wisdom':    player['wisdom'],
        'luck':      player['luck'],
    }

    weapon_type   = player.get('weapon_type', 'melee')
    base_damage   = player.get('weapon_damage', 10)
    if player.get('guaranteed_crit'):
        is_crit = True
    else:
        is_crit = roll_crit(player['luck'], player['agility'])
    damage        = calc_final_damage(base_damage, stats, weapon_type, is_crit)

    # Снижаем урон на защиту моба
    mob_defense   = mob_state.get('defense', 0)
    final_damage  = apply_defense(damage, mob_defense)

    mob_state['hp'] = max(0, mob_state['hp'] - final_damage)

    return {
        'type':     'player_attack',
        'damage':   final_damage,
        'is_crit':  is_crit,
        'mob_dead': mob_state['hp'] <= 0,
        'mob_hp':   mob_state['hp'],
    }

# ────────────────────────────────────────
# ОДИН ХОД МОБА
# ────────────────────────────────────────

def mob_attack(mob: dict, player: dict) -> dict:
    """
    Моб атакует игрока.
    Возвращает словарь с результатом и новым HP игрока.
    """
    # Проверка уклонения
    dodged = roll_dodge(player['agility'])
    if dodged:
        return {
            'type':       'dodge',
            'damage':     0,
            'player_hp':  player['hp'],
        }

    # Урон моба
    base_damage = calc_mob_damage(mob)

    # Защита игрока зависит от типа урона моба
    if mob.get('weapon_type') == 'magic':
        defense = calc_magic_defense(player['wisdom'])
    else:
        defense = calc_physical_defense(player['vitality'])

    # Снижение физ урона от ловкости
    from game.balance import calc_physical_damage_reduction
    agi_reduction = calc_physical_damage_reduction(player['agility'])
    base_damage   = int(base_damage * (1 - agi_reduction / 100))

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
    priority_player = calc_action_priority(player['agility'], player['luck'])
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
        'berserk_turns':        0,
        'berserk_damage':       0,
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
        'hunters_mark_turns':   0,
        'hunters_mark_value':   0,
        'vulnerability_turns':  0,
        'vulnerability_value':  0,
        'disarm_turns':         0,
        'disarm_value':         0,
        'fire_shield_turns':    0,
        'fire_shield_value':    0,
        'envenom_active':       False,
        # Прочее
        'mob_effects':          [],
        'damage_taken':         0,
        'potions_used':         0,
        'skills_used':          [],
        'normal_attacks':       0,
        'buffs_used':           False,
        'weapon_id':            'unarmed',
        'weapon_type':          'melee',
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
    log.extend(apply_mob_effect_ticks(mob, battle_state))
    mob_state = {'hp': battle_state['mob_hp'], 'defense': mob.get('defense', 0)}

    player = dict(player)
    player['hp'] = battle_state['player_hp']
    player['weapon_type']   = battle_state.get('weapon_type', 'melee')
    player['weapon_damage'] = battle_state.get('weapon_damage', 10)

    if battle_state.get('blessing_turns', 0) > 0:
        mult = 1 + battle_state['blessing_value'] / 100
        for stat in ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck'):
            if stat in player:
                player[stat] = int(player[stat] * mult)

    should_force_crit = battle_state.get('guaranteed_crit_turns', 0) > 0
    player['guaranteed_crit'] = should_force_crit

    if battle_state['player_goes_first']:
        result = player_attack(player, mob_state)
        damage_result = apply_direct_damage_action_modifiers(
            battle_state,
            result['damage'],
            can_consume_guaranteed_crit=False,
        )
        adjusted_damage = damage_result['damage']
        bonus_damage = max(0, adjusted_damage - result['damage'])
        if bonus_damage > 0:
            mob_state['hp'] = max(0, mob_state['hp'] - bonus_damage)
            result['damage'] = adjusted_damage
            result['mob_dead'] = mob_state['hp'] <= 0

        if result.get('is_crit') and should_force_crit:
            battle_state['guaranteed_crit_turns'] -= 1

        if result.get('is_crit'):
            log.append(t('battle.attack_crit', lang, damage=result['damage']))
        else:
            log.append(t('battle.attack_hit', lang, damage=result['damage']))

        if not result['mob_dead']:
            battle_state['mob_hp'] = mob_state['hp']
            log.extend(resolve_enemy_response(mob, player, battle_state, lang=lang, user_id=user_id))
            mob_state['hp'] = battle_state['mob_hp']
    else:
        battle_state['mob_hp'] = mob_state['hp']
        log.extend(resolve_enemy_response(mob, player, battle_state, lang=lang, user_id=user_id))
        mob_state['hp'] = battle_state['mob_hp']

        if player['hp'] > 0:
            result = player_attack(player, mob_state)
            damage_result = apply_direct_damage_action_modifiers(
                battle_state,
                result['damage'],
                can_consume_guaranteed_crit=False,
            )
            adjusted_damage = damage_result['damage']
            bonus_damage = max(0, adjusted_damage - result['damage'])
            if bonus_damage > 0:
                mob_state['hp'] = max(0, mob_state['hp'] - bonus_damage)
                result['damage'] = adjusted_damage
                result['mob_dead'] = mob_state['hp'] <= 0

            if result.get('is_crit') and should_force_crit:
                battle_state['guaranteed_crit_turns'] -= 1

            if result.get('is_crit'):
                log.append(t('battle.attack_crit', lang, damage=result['damage']))
            else:
                log.append(t('battle.attack_hit', lang, damage=result['damage']))

    # Сохраняем прежний тайминг normal attack flow: player buffs тикают после exchange
    apply_player_buffs(battle_state)
    tick_post_action_timed_trigger_buffs(battle_state)

    battle_state['mob_dead']    = mob_state['hp'] <= 0
    battle_state['player_dead'] = player['hp'] <= 0
    battle_state['mob_hp']    = mob_state['hp']
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
