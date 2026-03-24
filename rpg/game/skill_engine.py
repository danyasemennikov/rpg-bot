# ============================================================
# skill_engine.py — логика применения скиллов в бою
# ============================================================

import os, sys, random
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.skills import get_skill, get_available_skills
from game.weapon_mastery import get_skill_level, get_skill_cooldown, set_skill_cooldown
from game.balance import (
    calc_final_damage,
    normalize_damage_school,
    calc_armor_class_caster_bonus_percent,
    calc_armor_class_support_bonus_percent,
    calc_offhand_caster_bonus_percent,
    calc_offhand_support_bonus_percent,
)
from game.i18n import t, get_skill_name

def build_skill_result_log(skill_result: dict, lang: str) -> str:
    """
    Строит человекочитаемый лог по структурированным данным skill_result.
    Для non-damage скиллов остаётся fallback на готовую строку `log`.
    """
    log_key = skill_result.get('log_key')
    log_params = skill_result.get('log_params', {})

    if not log_key:
        return skill_result.get('log', '')

    text = t(log_key, lang, **log_params)

    if skill_result.get('lifesteal_ratio', 0) > 0 and skill_result.get('heal', 0) > 0:
        text += t('skills.log_lifesteal', lang, hp=skill_result['heal'])

    for suffix in skill_result.get('log_suffixes', []):
        suffix_key = suffix.get('key')
        suffix_params = suffix.get('params', {})
        text += t(suffix_key, lang, **suffix_params)

    return text


def calc_skill_value(
    skill: dict,
    skill_level: int,
    player: dict,
    *,
    battle_state: dict | None = None,
) -> float:
    """
    Считает итоговое значение скилла с учётом уровня и статов.
    Используется для лечения, силы баффа и т.д.
    """
    base     = skill['base_value']
    lv_bonus = 1 + skill['level_bonus'] * (skill_level - 1)

    stat_val = 0
    if skill['scale_stat']:
        stat_val = player.get(skill['scale_stat'], 0) * skill['scale_mult']

    value = (base + stat_val) * lv_bonus

    if battle_state is None:
        return value

    armor_class = battle_state.get('armor_class')
    offhand_profile = battle_state.get('offhand_profile')
    skill_type = skill.get('type')
    semantic_bonus = 0.0

    if skill_type == 'heal':
        semantic_bonus += calc_armor_class_support_bonus_percent(armor_class)
        semantic_bonus += calc_offhand_support_bonus_percent(offhand_profile)
    elif skill_type == 'buff':
        semantic_bonus += calc_armor_class_support_bonus_percent(armor_class) * 0.5
        semantic_bonus += calc_offhand_support_bonus_percent(offhand_profile) * 0.4
    elif skill_type == 'damage':
        damage_school = normalize_damage_school(
            skill.get('damage_school'),
            weapon_profile=battle_state.get('weapon_profile', 'unarmed'),
            weapon_type=battle_state.get('weapon_type', 'melee'),
        )
        if damage_school in ('magic', 'holy'):
            semantic_bonus += calc_armor_class_caster_bonus_percent(armor_class)
            semantic_bonus += calc_offhand_caster_bonus_percent(offhand_profile)

    return value * (1 + semantic_bonus / 100)

def calc_skill_mana_cost(skill: dict, skill_level: int) -> int:
    """Стоимость маны растёт чуть с уровнем скилла."""
    return int(skill['mana_cost'] * (1 + 0.05 * (skill_level - 1)))

def precheck_skill_use(skill_id: str, player_mana: int, telegram_id: int, lang: str) -> dict:
    """
    Проверяет, можно ли начать skill-turn без изменения runtime-состояния.
    """
    skill = get_skill(skill_id)
    skill_level = get_skill_level(telegram_id, skill_id)

    if not skill:
        return {'success': False, 'log': t('skills.not_found', lang)}

    if skill_level == 0:
        return {'success': False, 'log': t('skills.not_learned_simple', lang)}

    cd = get_skill_cooldown(telegram_id, skill_id)
    if cd > 0:
        return {'success': False, 'log': t('skills.on_cooldown', lang, name=get_skill_name(skill_id, lang), cd=cd)}

    mana_cost = calc_skill_mana_cost(skill, skill_level)
    if player_mana < mana_cost and mana_cost > 0:
        return {'success': False, 'log': t('skills.no_mana', lang, cost=mana_cost)}

    return {'success': True, 'log': ''}

def use_skill(skill_id: str, player: dict, mob_state: dict,
              battle_state: dict, telegram_id: int, lang: str) -> dict:
    """
    Применяет скилл в бою.
    Возвращает результат: урон, лечение, эффекты, лог.
    """
    skill       = get_skill(skill_id)
    skill_level = get_skill_level(telegram_id, skill_id)

    if not skill:
        return {'success': False, 'log': t('skills.not_found', lang)}

    if skill_level == 0:
        return {'success': False, 'log': t('skills.not_learned_simple', lang)}

    # Проверка кулдауна
    cd = get_skill_cooldown(telegram_id, skill_id)
    if cd > 0:
        return {'success': False, 'log': t('skills.on_cooldown', lang, name=get_skill_name(skill_id, lang), cd=cd)}

    # Проверка маны
    mana_cost = calc_skill_mana_cost(skill, skill_level)
    if player.get('mana', 0) < mana_cost and mana_cost > 0:
        return {'success': False, 'log': t('skills.no_mana', lang, cost=mana_cost)}

    # Списываем ману
    player['mana'] = player.get('mana', 0) - mana_cost
    battle_state['player_mana'] = player['mana']

    result = {
        'success': True,
        'damage':  0,
        'heal':    0,
        'log':     '',
        'effects': [],
        'buff':    None,
        'direct_damage_skill': False,
        'log_key': None,
        'log_params': {},
        'log_suffixes': [],
        'lifesteal_ratio': 0.0,
        'damage_school': normalize_damage_school(
            None,
            weapon_profile=battle_state.get('weapon_profile', 'unarmed'),
            weapon_type=battle_state.get('weapon_type', 'melee'),
        ),
    }

    skill_type = skill['type']
    value      = calc_skill_value(skill, skill_level, player, battle_state=battle_state)
    weapon_type = battle_state.get('weapon_type', 'melee')
    weapon_profile = battle_state.get('weapon_profile', 'unarmed')
    profile_damage_school = normalize_damage_school(
        None,
        weapon_profile=weapon_profile,
        weapon_type=weapon_type,
    )

    # ── УРОН ────────────────────────────────
    if skill_type == 'damage':
        result['direct_damage_skill'] = True
        result['damage_school'] = normalize_damage_school(
            skill.get('damage_school'),
            weapon_profile=battle_state.get('weapon_profile', 'unarmed'),
            weapon_type=battle_state.get('weapon_type', 'melee'),
        )
        stats = {k: player.get(k, 1) for k in
                 ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck')}
        weapon_dmg  = battle_state.get('weapon_damage', 10)
        base_attack = calc_final_damage(
            weapon_dmg,
            stats,
            weapon_type,
            False,
            weapon_profile=weapon_profile,
            damage_school=profile_damage_school,
            armor_class=battle_state.get('armor_class'),
            offhand_profile=battle_state.get('offhand_profile'),
            encumbrance=battle_state.get('encumbrance'),
        )
        # value = % от базовой атаки * бонус уровня
        value = base_attack * (skill['base_value'] / 100) * (1 + skill['level_bonus'] * (skill_level - 1))

        hits = skill.get('hits', 1)

        if hits > 1:
            total = 0
            log_parts = []
            for i in range(hits):
                hit_dmg = int(value * random.uniform(0.9, 1.1))
                defense = mob_state.get('defense', 0)
                ignore  = skill.get('ignore_defense', 0)
                eff_def = defense * (1 - ignore)
                hit_dmg = max(1, hit_dmg - int(eff_def))
                total  += hit_dmg
                log_parts.append(str(hit_dmg))
            result['damage'] = total
            result['log_key'] = 'skills.log_damage_multi'
            result['log_params'] = {
                'name': get_skill_name(skill_id, lang),
                'hits': hits,
                'parts': ', '.join(log_parts),
                'total': total,
                'cost': mana_cost,
            }
        else:
            dmg     = int(value * random.uniform(0.9, 1.1))
            defense = mob_state.get('defense', 0)
            ignore  = skill.get('ignore_defense', 0)
            eff_def = defense * (1 - ignore)
            dmg     = max(1, dmg - int(eff_def))

            # Backstab — крит по уязвимой цели
            if skill_id == 'backstab':
                mob_effects = mob_state.get('effects', [])
                has_debuff = any(e['type'] in ('stun', 'freeze', 'poison', 'slow') for e in mob_effects)
                if has_debuff:
                    dmg = int(dmg * 2.0)
                    result['log_key'] = 'skills.log_backstab_crit'
                    result['log_params'] = {
                        'name': get_skill_name(skill_id, lang),
                        'dmg': dmg,
                        'cost': mana_cost,
                    }
                else:
                    result['log_key'] = 'skills.log_damage'
                    result['log_params'] = {
                        'name': get_skill_name(skill_id, lang),
                        'dmg': dmg,
                        'cost': mana_cost,
                    }
            else:
                result['log_key'] = 'skills.log_damage'
                result['log_params'] = {
                    'name': get_skill_name(skill_id, lang),
                    'dmg': dmg,
                    'cost': mana_cost,
                }

            result['damage'] = dmg

        # Sword rush — уязвимость цели
        if skill_id == 'sword_rush':
            battle_state['vulnerability_turns'] = 2
            battle_state['vulnerability_value'] = 25 + 3 * (skill_level - 1)
            result['log_key'] = 'skills.log_sword_rush'
            result['log_params'] = {
                'name': get_skill_name(skill_id, lang),
                'dmg': result['damage'],
                'cost': mana_cost,
            }

        # Пробивание
        if skill.get('piercing'):
            result['log_suffixes'].append({'key': 'skills.log_piercing', 'params': {}})

        # Вампиризм
        if skill.get('lifesteal'):
            result['lifesteal_ratio'] = skill['lifesteal']
            heal = int(result['damage'] * result['lifesteal_ratio'])
            result['heal']  = heal

        # Эффект при попадании
        if skill.get('effect') and result['damage'] > 0:
            eff_type, chance, duration = skill['effect']
            if random.random() < chance:
                stats = {k: player.get(k, 1) for k in
                         ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck')}
                base_attack = calc_final_damage(
                    battle_state.get('weapon_damage', 10), stats,
                    battle_state.get('weapon_type', 'melee'),
                    False,
                    weapon_profile=battle_state.get('weapon_profile', 'unarmed'),
                    damage_school=profile_damage_school,
                    armor_class=battle_state.get('armor_class'),
                    offhand_profile=battle_state.get('offhand_profile'),
                    encumbrance=battle_state.get('encumbrance'),
                )
                dot_value = max(1, int(base_attack * 0.3))
                result['effects'].append({
                    'type':     eff_type,
                    'turns':    duration,
                    'value':    dot_value,
                    'skill_id': skill_id,
                })
                result['log_suffixes'].append({
                    'key': 'skills.log_effect_ok',
                    'params': {'effect': t(f'skills.effect_{eff_type}', lang)},
                })

        result['log'] = build_skill_result_log(result, lang)

    # ── ЛЕЧЕНИЕ ────────────────────────────
    elif skill_type == 'heal':
        heal           = int(value)
        max_hp         = battle_state.get('player_max_hp', player.get('max_hp', 100))
        current_hp     = battle_state.get('player_hp', player.get('hp', 100))
        actual_heal    = min(heal, max_hp - current_hp)
        result['heal'] = actual_heal
        result['log']  = t('skills.log_heal', lang,
                            name=get_skill_name(skill_id, lang),
                            hp=actual_heal, cost=mana_cost)

    # ── БАФФ ───────────────────────────────
    elif skill_type == 'buff':
        # Берём duration из поля скилла, не из base_value
        duration = skill.get('duration', 2)

        result['log'] = t('skills.log_buff', lang,
                           name=get_skill_name(skill_id, lang),
                           turns=duration, cost=mana_cost)

        # Парирование
        if skill_id == 'parry':
            battle_state['parry_active'] = True
            battle_state['parry_value']  = value
            result['log'] = t('skills.log_parry', lang,
                               name=get_skill_name(skill_id, lang),
                               cost=mana_cost)

        # Защитная стойка
        elif skill_id == 'defensive_stance':
            battle_state['defense_buff_turns'] = duration
            battle_state['defense_buff_value'] = int(value)
            result['log'] = t('skills.log_defense', lang,
                               name=get_skill_name(skill_id, lang),
                               value=int(value), turns=duration, cost=mana_cost)

        # Берсерк
        elif skill_id == 'berserker':
            battle_state['berserk_turns']  = duration
            battle_state['berserk_damage'] = int(value)
            result['log'] = t('skills.log_berserker', lang,
                               name=get_skill_name(skill_id, lang),
                               value=int(value), cost=mana_cost)

        # Регенерация
        elif skill_id == 'regeneration':
            battle_state['regen_turns']  = duration
            battle_state['regen_amount'] = int(value)
            result['log'] = t('skills.log_regen', lang,
                               name=get_skill_name(skill_id, lang),
                               amount=int(value), turns=duration, cost=mana_cost)

        # Благословение
        elif skill_id == 'blessing':
            battle_state['blessing_turns'] = duration
            battle_state['blessing_value'] = int(value)
            result['log'] = t('skills.log_blessing', lang,
                               name=get_skill_name(skill_id, lang),
                               value=int(value), turns=duration, cost=mana_cost)

        # Воскрешение
        elif skill_id == 'resurrection':
            battle_state['resurrection_active'] = True
            battle_state['resurrection_hp']     = int(value)
            battle_state['resurrection_turns']  = duration
            result['log'] = t('skills.log_resurrection', lang,
                               name=get_skill_name(skill_id, lang),
                               value=int(value), cost=mana_cost)

        # Непробиваемый
        elif skill_id == 'sword_ultimate_b':
            battle_state['invincible_turns'] = duration
            result['log'] = t('skills.log_invincible', lang,
                               name=get_skill_name(skill_id, lang),
                               turns=duration, cost=mana_cost)

        # Огненный щит
        elif skill_id == 'fire_shield':
            stats = {k: player.get(k, 1) for k in
                     ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck')}
            base_attack = calc_final_damage(
                battle_state.get('weapon_damage', 10), stats,
                battle_state.get('weapon_type', 'melee'),
                False,
                weapon_profile=battle_state.get('weapon_profile', 'unarmed'),
                damage_school=profile_damage_school,
                armor_class=battle_state.get('armor_class'),
                offhand_profile=battle_state.get('offhand_profile'),
                encumbrance=battle_state.get('encumbrance'),
            )
            shield_value = max(1, int(base_attack * skill['base_value'] / 100))
            battle_state['fire_shield_turns'] = duration
            battle_state['fire_shield_value'] = shield_value
            result['log'] = t('skills.log_fire_shield', lang,
                               name=get_skill_name(skill_id, lang),
                               value=shield_value, turns=duration, cost=mana_cost)

        # Envenom
        elif skill_id == 'envenom':
            battle_state['envenom_active'] = True
            result['log'] = t('skills.log_envenom', lang,
                               name=get_skill_name(skill_id, lang),
                               cost=mana_cost)

        # Дымовая завеса / Отступление
        elif skill_id in ('smoke_bomb', 'retreat'):
            battle_state['dodge_buff_turns'] = duration
            battle_state['dodge_buff_value'] = int(skill['base_value'])
            result['log'] = t('skills.log_dodge_buff', lang,
                               name=get_skill_name(skill_id, lang),
                               value=int(skill['base_value']),
                               turns=duration, cost=mana_cost)

        # Орлиный глаз / Тень смерти
        elif skill_id in ('eagle_eye', 'dagger_ult_b'):
            battle_state['guaranteed_crit_turns'] = duration
            result['log'] = t('skills.log_guaranteed_crit', lang,
                               name=get_skill_name(skill_id, lang),
                               turns=duration, cost=mana_cost)

    # ── ДЕБАФФ / КОНТРОЛЬ ──────────────────
    elif skill_type in ('debuff', 'control'):
        effect_data = skill.get('effect')
        eff_type = None

        if effect_data:
            eff_type, chance, duration = effect_data
            if random.random() < chance:
                stats = {k: player.get(k, 1) for k in
                         ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck')}
                base_attack = calc_final_damage(
                    battle_state.get('weapon_damage', 10), stats,
                    battle_state.get('weapon_type', 'melee'),
                    False,
                    weapon_profile=battle_state.get('weapon_profile', 'unarmed'),
                    damage_school=profile_damage_school,
                    armor_class=battle_state.get('armor_class'),
                    offhand_profile=battle_state.get('offhand_profile'),
                    encumbrance=battle_state.get('encumbrance'),
                )
                dot_value = max(1, int(base_attack * skill['base_value'] / 100))
                result['effects'].append({
                    'type':     eff_type,
                    'turns':    duration,
                    'value':    dot_value,
                    'skill_id': skill_id,
                })
                result['log'] = t('skills.log_effect_applied', lang,
                                   name=get_skill_name(skill_id, lang),
                                   effect=t(f'skills.effect_{eff_type}', lang),
                                   turns=duration, cost=mana_cost)
            else:
                result['log'] = t('skills.log_effect_fail', lang,
                                   name=get_skill_name(skill_id, lang),
                                   cost=mana_cost)
        else:
            result['log'] = t('skills.log_buff', lang,
                               name=get_skill_name(skill_id, lang),
                               turns=0, cost=mana_cost)

        # Venom Storm — 3 стека яда
        if skill_id == 'venom_storm':
            stats = {k: player.get(k, 1) for k in
                     ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck')}
            base_attack = calc_final_damage(
                battle_state.get('weapon_damage', 10), stats,
                battle_state.get('weapon_type', 'melee'),
                False,
                weapon_profile=battle_state.get('weapon_profile', 'unarmed'),
                damage_school=profile_damage_school,
                armor_class=battle_state.get('armor_class'),
                offhand_profile=battle_state.get('offhand_profile'),
                encumbrance=battle_state.get('encumbrance'),
            )
            dot_value = max(1, int(base_attack * skill['base_value'] / 100))
            result['effects'] = []
            for _ in range(3):
                result['effects'].append({
                    'type':     'poison',
                    'turns':    3,
                    'value':    dot_value,
                    'skill_id': skill_id,
                })
            result['log'] = t('skills.log_venom_storm', lang,
                               name=get_skill_name(skill_id, lang),
                               dmg=dot_value, cost=mana_cost)

        # Spider Nest — payoff по уже отравленной цели с обменом burst на attrition
        elif skill_id == 'dagger_ult_a':
            mob_effects = battle_state.get('mob_effects', [])
            poison_index = next(
                (idx for idx, effect in enumerate(mob_effects) if effect.get('type') == 'poison'),
                None,
            )
            if poison_index is not None:
                consumed_poison = mob_effects.pop(poison_index)
                burst_damage = max(1, int(consumed_poison.get('value', 0) * 0.75))
                result['damage'] = burst_damage
                result['direct_damage_skill'] = True
                result['damage_school'] = normalize_damage_school(
                    skill.get('damage_school'),
                    weapon_profile=battle_state.get('weapon_profile', 'unarmed'),
                    weapon_type=battle_state.get('weapon_type', 'melee'),
                )
                result['log_key'] = 'skills.log_damage_effect'
                result['log_params'] = {
                    'name': get_skill_name(skill_id, lang),
                    'dmg': burst_damage,
                    'cost': mana_cost,
                }
                result['log_suffixes'].append({
                    'key': 'skills.log_effect_ok',
                    'params': {'effect': t('skills.effect_poison', lang)},
                })
                result['log'] = build_skill_result_log(result, lang)

        # Blizzard — снижение точности через dodge_buff
        elif skill_id == 'blizzard':
            battle_state['dodge_buff_turns'] = 3
            battle_state['dodge_buff_value'] = int(value)
            result['log'] = t('skills.log_blizzard', lang,
                               name=get_skill_name(skill_id, lang),
                               value=int(value), cost=mana_cost)

        # Hunter's Mark — метка охотника
        elif skill_id == 'hunters_mark':
            battle_state['hunters_mark_turns'] = 3
            battle_state['hunters_mark_value'] = int(value)
            result['log'] = t('skills.log_hunters_mark', lang,
                               name=get_skill_name(skill_id, lang),
                               value=int(value), cost=mana_cost)

        # Disarm — обезоруживание + урон
        elif skill_id == 'disarm':
            battle_state['disarm_turns'] = 2
            battle_state['disarm_value'] = int(value)
            stats = {k: player.get(k, 1) for k in
                     ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck')}
            base_attack = calc_final_damage(
                battle_state.get('weapon_damage', 10), stats,
                battle_state.get('weapon_type', 'melee'),
                False,
                weapon_profile=battle_state.get('weapon_profile', 'unarmed'),
                damage_school=profile_damage_school,
                armor_class=battle_state.get('armor_class'),
                offhand_profile=battle_state.get('offhand_profile'),
                encumbrance=battle_state.get('encumbrance'),
            )
            dmg = max(1, int(base_attack * random.uniform(0.9, 1.1)))
            result['damage'] = dmg
            result['direct_damage_skill'] = True
            result['damage_school'] = normalize_damage_school(
                skill.get('damage_school'),
                weapon_profile=battle_state.get('weapon_profile', 'unarmed'),
                weapon_type=battle_state.get('weapon_type', 'melee'),
            )
            result['log_key'] = 'skills.log_damage_effect'
            result['log_params'] = {
                'name': get_skill_name(skill_id, lang),
                'dmg': dmg,
                'cost': mana_cost,
            }
            result['log'] = build_skill_result_log(result, lang)

        # Envenom — удвоение следующего яда
        if battle_state.get('envenom_active') and eff_type == 'poison' and result['effects']:
            for effect in result['effects']:
                if effect.get('type') == 'poison':
                    effect['value'] *= 2
            battle_state['envenom_active'] = False

    # Устанавливаем кулдаун
    if skill['cooldown'] > 0:
        set_skill_cooldown(telegram_id, skill_id, skill['cooldown'])

    return result

def apply_mob_effects(mob_state: dict) -> tuple:
    """
    Применяет эффекты на моба (яд, горение и т.д.) в начале хода.
    Возвращает (урон_от_эффектов, лог).
    """
    total_dmg   = 0
    log_parts   = []
    effects     = mob_state.get('effects', [])
    new_effects = []

    for eff in effects:
        if eff['turns'] <= 0:
            continue

        if eff['type'] in ('poison', 'burn'):
            dmg        = eff['value']
            total_dmg += dmg
            emoji      = '☠️' if eff['type'] == 'poison' else '🔥'
            log_parts.append(f"{emoji} {dmg}")

        eff = dict(eff)
        eff['turns'] -= 1
        if eff['turns'] > 0:
            new_effects.append(eff)

    mob_state['effects'] = new_effects
    return total_dmg, ', '.join(log_parts)

def apply_player_buffs(battle_state: dict) -> str:
    """
    Compatibility shim: длительности player buffs тикаются в game/combat.py.
    """
    return ''

def get_battle_skills(
    telegram_id: int,
    weapon_id: str,
    mastery_level: int,
    weapon_profile: str | None = None,
) -> list:
    """
    Возвращает список скиллов доступных в бою с кулдаунами и уровнями.
    """
    available = get_available_skills(weapon_id, mastery_level, weapon_profile)
    result    = []

    for skill in available:
        skill_level = get_skill_level(telegram_id, skill['id'])
        if skill_level == 0:
            continue

        if skill['type'] == 'passive':
            continue

        cd = get_skill_cooldown(telegram_id, skill['id'])
        result.append({
            **skill,
            'skill_level':      skill_level,
            'cooldown_left':    cd,
            'mana_cost_actual': calc_skill_mana_cost(skill, skill_level),
        })

    return result

print('✅ game/skill_engine.py загружен!')
