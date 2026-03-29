# ============================================================
# skills_ui.py — интерфейс прокачки скиллов
# ============================================================

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_player
from game.skills import get_skill, get_weapon_tree, SKILL_TREES
from game.weapon_mastery import (
    get_mastery, get_skill_level, upgrade_skill, mastery_exp_needed, get_all_masteries_grouped
)
from game.items_data import get_item
from game.gear_instances import resolve_equipped_item_ids_with_fallback
from game.i18n import t, get_player_lang, get_item_name, get_skill_name
from game.skills import normalize_weapon_family_key

STAT_NAMES = {
    'ru': {'strength': '💪 Сила', 'agility': '🤸 Ловкость', 'intuition': '🔮 Интуиция', 'vitality': '❤️ Живучесть', 'wisdom': '🧠 Мудрость', 'luck': '🍀 Удача'},
    'en': {'strength': '💪 Strength', 'agility': '🤸 Agility', 'intuition': '🔮 Intuition', 'vitality': '❤️ Vitality', 'wisdom': '🧠 Wisdom', 'luck': '🍀 Luck'},
    'es': {'strength': '💪 Fuerza', 'agility': '🤸 Agilidad', 'intuition': '🔮 Intuición', 'vitality': '❤️ Vitalidad', 'wisdom': '🧠 Sabiduría', 'luck': '🍀 Suerte'},
}

BRANCH_KEYS = {
    'A':    'branch_a',
    'B':    'branch_b',
    'base': 'branch_base',
}

def get_equipped_weapon(telegram_id: int, lang: str = 'ru') -> tuple:
    unarmed_name = t('skills.unarmed', lang)
    equipped = resolve_equipped_item_ids_with_fallback(telegram_id)
    weapon_item_id = equipped.get('weapon')
    if not weapon_item_id:
        return 'unarmed', unarmed_name

    item = get_item(weapon_item_id)
    if not item:
        return 'unarmed', unarmed_name
    family_id = normalize_weapon_family_key(item.get('weapon_profile') or weapon_item_id)
    return family_id, _get_weapon_family_name(family_id, lang)

def _get_weapon_family_name(weapon_id: str, lang: str) -> str:
    if weapon_id == 'base':
        return t('skills.base_skills', lang)
    if weapon_id == 'unarmed':
        return t('skills.unarmed', lang)
    profile_key = f'profile.identity.weapon_profile.{weapon_id}'
    profile_name = t(profile_key, lang)
    if not profile_name.startswith('['):
        return profile_name
    return get_item_name(weapon_id, lang)

def build_skills_main(telegram_id: int, lang: str = 'ru') -> tuple:
    text = t('skills.title', lang) + '\n\n'

    weapon_id, weapon_name = get_equipped_weapon(telegram_id, lang)
    text += t('skills.weapon_label', lang, name=weapon_name) + '\n\n'

    keyboard = []

    masteries = get_all_masteries_grouped(telegram_id)

    known_weapons = {m['weapon_id'] for m in masteries}
    if weapon_id != 'unarmed' and weapon_id not in known_weapons:
        from game.weapon_mastery import create_mastery
        create_mastery(telegram_id, weapon_id)
        masteries = list(masteries) + [get_mastery(telegram_id, weapon_id)]

    for m in masteries:
        m      = dict(m)
        if m['weapon_id'] == 'base':
            continue
        w_name = _get_weapon_family_name(m['weapon_id'], lang)
        level  = m['level']
        exp    = m['exp']
        needed = mastery_exp_needed(level)
        points = m['skill_points']

        bar_filled = int(exp / needed * 8) if needed > 0 else 8
        bar = '█' * bar_filled + '░' * (8 - bar_filled)

        equipped_tag = " ✅" if m['weapon_id'] == weapon_id else ""
        points_tag   = f" 🔸{points}" if points > 0 else ""

        text += (
            f"{w_name}{equipped_tag}\n"
            + t('skills.mastery_level', lang, level=level) + f" [{bar}] {exp}/{needed}\n"
            + t('skills.skill_points', lang, points=points) + f"{points_tag}\n\n"
        )

        keyboard.append([InlineKeyboardButton(
            t('skills.tree_btn', lang, name=w_name, level=level) + points_tag,
            callback_data=f"sk_tree_{m['weapon_id']}"
        )])

    keyboard.append([InlineKeyboardButton(
        t('skills.base_skills', lang), callback_data="sk_tree_base"
    )])

    return text, InlineKeyboardMarkup(keyboard)

def build_skill_tree(telegram_id: int, weapon_id: str, lang: str = 'ru') -> tuple:
    if weapon_id == 'base':
        tree    = {'base': SKILL_TREES['base']['base']}
        mastery = {'level': 99, 'skill_points': 0}
        w_name  = t('skills.base_skills', lang)
    else:
        tree    = get_weapon_tree(weapon_id)
        mastery = get_mastery(telegram_id, weapon_id)
        w_name  = _get_weapon_family_name(weapon_id, lang)

    mastery_level = mastery['level']
    skill_points  = mastery['skill_points']

    text = f"⚔️ <b>{w_name}</b>\n"
    if weapon_id != 'base':
        text += t('skills.mastery_info', lang, level=mastery_level, points=skill_points) + '\n\n'

    keyboard = []

    for branch, skill_ids in tree.items():
        branch_key  = BRANCH_KEYS.get(branch, branch)
        branch_name = t(f'skills.{branch_key}', lang)
        text += f"\n<b>{branch_name}</b>\n"

        for skill_id in skill_ids:
            skill = get_skill(skill_id)
            if not skill:
                continue

            skill_level = get_skill_level(telegram_id, skill_id)
            unlocked    = mastery_level >= skill['unlock_mastery']
            max_level   = skill['max_level']

            if not unlocked:
                text += t('skills.locked', lang, name=get_skill_name(skill_id, lang), level=skill['unlock_mastery']) + '\n'
                keyboard.append([InlineKeyboardButton(
                    t('skills.locked', lang, name=get_skill_name(skill_id, lang), level=skill['unlock_mastery']),
                    callback_data='sk_noop'
                )])
            elif skill_level == 0:
                text += t('skills.not_learned', lang, name=get_skill_name(skill_id, lang)) + '\n'
                keyboard.append([InlineKeyboardButton(
                    t('skills.learn_btn', lang, name=get_skill_name(skill_id, lang)),
                    callback_data=f"sk_upgrade_{weapon_id}|{skill_id}"
                )])
            elif skill_level >= max_level:
                text += t('skills.max_level', lang, name=get_skill_name(skill_id, lang), level=skill_level, max=max_level) + '\n'
                keyboard.append([InlineKeyboardButton(
                    t('skills.max_level', lang, name=get_skill_name(skill_id, lang), level=skill_level, max=max_level),
                    callback_data=f"sk_info_{skill_id}"
                )])
            else:
                text += t('skills.can_upgrade', lang, name=get_skill_name(skill_id, lang), level=skill_level, max=max_level) + '\n'
                keyboard.append([InlineKeyboardButton(
                    t('skills.upgrade_btn', lang, name=get_skill_name(skill_id, lang), level=skill_level, next=skill_level+1),
                    callback_data=f"sk_upgrade_{weapon_id}|{skill_id}"
                )])

    keyboard.append([InlineKeyboardButton(t('skills.back_btn', lang), callback_data="sk_main")])
    return text, InlineKeyboardMarkup(keyboard)

def build_skill_info(telegram_id: int, skill_id: str, weapon_id: str, lang: str = 'ru') -> tuple:
    skill       = get_skill(skill_id)
    skill_level = get_skill_level(telegram_id, skill_id)

    if not skill:
        return t('skills.skill_not_found', lang), InlineKeyboardMarkup([[
            InlineKeyboardButton(t('skills.back_btn', lang), callback_data=f"sk_tree_{weapon_id}")
        ]])

    from game.skill_engine import calc_skill_value, calc_skill_mana_cost
    player = dict(get_player(telegram_id))

    text  = f"{'✅' if skill_level > 0 else '⭕'} <b>{skill['name']}</b>\n"
    text += f"{skill['description']}\n\n"
    text += f"Уровень: <b>{skill_level}/{skill['max_level']}</b>\n"
    text += f"Мана: <b>{calc_skill_mana_cost(skill, max(skill_level,1))}</b>\n"

    if skill['cooldown'] > 0:
        text += t('skills.cooldown', lang, turns=skill['cooldown']) + '\n'
    else:
        text += t('skills.no_cooldown', lang) + '\n'

    if skill['scale_stat']:
        stat_name = STAT_NAMES.get(lang, STAT_NAMES['ru']).get(skill['scale_stat'], skill['scale_stat'])
        text += t('skills.scale_stat', lang, stat=stat_name) + '\n'

    if skill_level > 0:
        val = calc_skill_value(skill, skill_level, player)
        text += '\n' + t('skills.current_effect', lang, val=int(val)) + '\n'

    if skill_level < skill['max_level']:
        next_val = calc_skill_value(skill, skill_level + 1, player)
        text += t('skills.next_level', lang, val=int(next_val)) + '\n'

    keyboard = []
    mastery  = get_mastery(telegram_id, weapon_id)

    if skill_level < skill['max_level'] and mastery['level'] >= skill['unlock_mastery']:
        if mastery['skill_points'] > 0:
            keyboard.append([InlineKeyboardButton(
                t('skills.upgrade_cost', lang),
                callback_data=f"sk_upgrade_{weapon_id}|{skill_id}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                t('skills.no_points', lang), callback_data='sk_noop'
            )])

    keyboard.append([InlineKeyboardButton(
        t('skills.back_btn', lang), callback_data=f"sk_tree_{weapon_id}"
    )])
    return text, InlineKeyboardMarkup(keyboard)

# ────────────────────────────────────────
# КОМАНДА /skills
# ────────────────────────────────────────

async def skills_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p    = get_player(user.id)
    lang = get_player_lang(user.id)

    if not p:
        await update.message.reply_text(t('common.no_character', lang))
        return

    text, keyboard = build_skills_main(user.id, lang)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')

# ────────────────────────────────────────
# КНОПКИ
# ────────────────────────────────────────

async def handle_skills_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    user  = query.from_user
    lang  = get_player_lang(user.id)

    if data == 'sk_noop':
        await query.answer()
        return

    if data == 'sk_main':
        text, keyboard = build_skills_main(user.id, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('sk_tree_'):
        weapon_id = data.replace('sk_tree_', '', 1)
        text, keyboard = build_skill_tree(user.id, weapon_id, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('sk_info_'):
        skill_id  = data.replace('sk_info_', '', 1)
        skill     = get_skill(skill_id)
        weapon_id = skill['weapon_id'] if skill else 'base'
        text, keyboard = build_skill_info(user.id, skill_id, weapon_id, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('sk_upgrade_'):
        rest = data.replace('sk_upgrade_', '', 1)
        weapon_id, skill_id = rest.split('|', 1)

        result = upgrade_skill(user.id, weapon_id, skill_id)

        if not result['success']:
            await query.answer(f"❌ {result['reason']}", show_alert=True)
            return

        await query.answer(
            t('skills.upgraded', lang, name=result['skill_name'], level=result['new_level']),
            show_alert=True
        )
        text, keyboard = build_skill_tree(user.id, weapon_id, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    await query.answer()

print('✅ handlers/skills_ui.py обновлён!')
