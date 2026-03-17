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
from game.skill_engine import apply_player_buffs, apply_mob_effects


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

def process_turn(player: dict, mob: dict, battle_state: dict, lang: str = 'ru') -> dict:
    log = []
    mob_state = {'hp': battle_state['mob_hp'], 'defense': mob.get('defense', 0)}

    mob_state['effects'] = battle_state.get('mob_effects', [])
    eff_dmg, eff_log = apply_mob_effects(mob_state)
    if eff_dmg > 0:
        mob_state['hp'] = max(0, mob_state['hp'] - eff_dmg)
        log.append(eff_log)
    battle_state['mob_effects'] = mob_state.get('effects', [])

    player = dict(player)
    player['hp'] = battle_state['player_hp']
    player['weapon_type']   = battle_state.get('weapon_type', 'melee')
    player['weapon_damage'] = battle_state.get('weapon_damage', 10)

    if battle_state.get('blessing_turns', 0) > 0:
        mult = 1 + battle_state['blessing_value'] / 100
        for stat in ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck'):
            if stat in player:
                player[stat] = int(player[stat] * mult)

    def mob_is_stunned():
        return any(
            e['type'] in ('stun', 'freeze', 'slow')
            for e in battle_state.get('mob_effects', [])
        )

    def handle_mob_attack():
        if mob_is_stunned():
            log.append(t('battle.stunned', lang, mob_name=get_mob_name(mob['id'], lang)))
            return
        mob_result = mob_attack(mob, player)
        if battle_state.get('parry_active'):
            parry_dmg = int(mob_result['damage'] * battle_state.get('parry_value', 1.0))
            mob_state['hp'] = max(0, mob_state['hp'] - parry_dmg)
            battle_state['parry_active'] = False
            log.append(t('battle.parry_reflect', lang, damage=parry_dmg))
        elif mob_result.get('type') == 'dodge':
            player['hp'] = mob_result['player_hp']
            log.append(t('battle.player_dodge', lang))
        else:
            player['hp'] = mob_result['player_hp']
            log.append(t('battle.mob_attack', lang,
                         mob_name=get_mob_name(mob['id'], lang),
                         damage=mob_result['damage']))

    if battle_state['player_goes_first']:
        result = player_attack(player, mob_state)
        if battle_state.get('hunters_mark_turns', 0) > 0:
            bonus = int(result['damage'] * battle_state['hunters_mark_value'] / 100)
            result['damage'] += bonus
            mob_state['hp'] = max(0, mob_state['hp'] - bonus)
            battle_state['hunters_mark_turns'] -= 1
        if battle_state.get('vulnerability_turns', 0) > 0:
            bonus = int(result['damage'] * battle_state['vulnerability_value'] / 100)
            result['damage'] += bonus
            mob_state['hp'] = max(0, mob_state['hp'] - bonus)
            battle_state['vulnerability_turns'] -= 1
        if result.get('is_crit'):
            log.append(t('battle.attack_crit', lang, damage=result['damage']))
        else:
            log.append(t('battle.attack_hit', lang, damage=result['damage']))

        if not result['mob_dead']:
            handle_mob_attack()
    else:
        handle_mob_attack()

        if player['hp'] > 0:
            result = player_attack(player, mob_state)
            if battle_state.get('hunters_mark_turns', 0) > 0:
                bonus = int(result['damage'] * battle_state['hunters_mark_value'] / 100)
                result['damage'] += bonus
                mob_state['hp'] = max(0, mob_state['hp'] - bonus)
                battle_state['hunters_mark_turns'] -= 1
            if battle_state.get('vulnerability_turns', 0) > 0:
                bonus = int(result['damage'] * battle_state['vulnerability_value'] / 100)
                result['damage'] += bonus
                mob_state['hp'] = max(0, mob_state['hp'] - bonus)
                battle_state['vulnerability_turns'] -= 1
            if result.get('is_crit'):
                log.append(t('battle.attack_crit', lang, damage=result['damage']))
            else:
                log.append(t('battle.attack_hit', lang, damage=result['damage']))

    apply_player_buffs(battle_state)

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