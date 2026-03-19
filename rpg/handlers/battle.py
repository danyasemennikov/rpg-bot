# ============================================================
# battle.py — обработчик боёв в Telegram
# ============================================================

import sys, json
sys.path.append('/content/rpg_bot')
import random

from game.skill_engine import get_battle_skills, use_skill
from game.weapon_mastery import get_mastery, add_mastery_exp, tick_cooldowns
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from database import get_player, get_connection
from game.mobs import get_mob
from game.combat import (
    init_battle, process_turn, calc_rewards,
    calc_death_penalty, hp_bar, resolve_enemy_response, apply_pre_enemy_response_ticks
)
from game.balance import exp_to_next_level, calc_max_hp
from game.items_data import get_item
from game.i18n import t, get_player_lang, get_item_name, get_skill_name, get_mob_name


# ────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ────────────────────────────────────────

def save_battle(telegram_id: int, battle_state: dict):
    """Сохраняем состояние боя в БД."""
    conn = get_connection()
    conn.execute(
        'UPDATE players SET in_battle=1 WHERE telegram_id=?',
        (telegram_id,)
    )
    conn.commit()
    conn.close()

def end_battle(telegram_id: int):
    """Заканчиваем бой."""
    conn = get_connection()
    conn.execute(
        'UPDATE players SET in_battle=0 WHERE telegram_id=?',
        (telegram_id,)
    )
    conn.commit()
    conn.close()

def add_to_inventory(telegram_id: int, item_id: str, quantity: int = 1):
    """Добавляет предмет в инвентарь."""
    conn = get_connection()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")

        existing = conn.execute(
            'SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (telegram_id, item_id)
        ).fetchone()

        if existing:
            conn.execute(
                'UPDATE inventory SET quantity=? WHERE id=?',
                (existing['quantity'] + quantity, existing['id'])
            )
        else:
            conn.execute(
                'INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)',
                (telegram_id, item_id, quantity)
            )
        conn.commit()
    finally:
        conn.close()

def apply_rewards(telegram_id: int, player: dict, rewards: dict) -> dict:
    new_exp  = player['exp'] + rewards['exp']
    new_gold = player['gold'] + rewards['gold']
    leveled_up = False
    new_level  = player['level']

    while new_exp >= exp_to_next_level(new_level):
        new_exp  -= exp_to_next_level(new_level)
        new_level += 1
        leveled_up = True

    levels_gained = new_level - player['level']
    stat_points = player['stat_points'] + (3 * levels_gained)

    conn = get_connection()
    try:
        conn.execute(
            '''UPDATE players SET
                exp=?, gold=?, level=?, stat_points=?
               WHERE telegram_id=?''',
            (new_exp, new_gold, new_level, stat_points, telegram_id)
        )
        conn.commit()
    finally:
        conn.close()

    # Сброс кулдаунов после боя
    conn2 = get_connection()
    conn2.execute('DELETE FROM skill_cooldowns WHERE telegram_id=?', (telegram_id,))
    conn2.commit()
    conn2.close()

    for item_id in rewards['loot']:
        add_to_inventory(telegram_id, item_id)

    return {
        'leveled_up': leveled_up,
        'new_level':  new_level,
        'new_exp':    new_exp,
        'new_gold':   new_gold,
    }

def apply_death(telegram_id: int, player: dict):
    """Применяет штраф смерти и возрождает в деревне."""
    penalty  = calc_death_penalty(player)
    new_exp  = max(0, player['exp'] - penalty['exp_loss'])
    new_gold = max(0, player['gold'] - penalty['gold_loss'])

    conn = get_connection()
    revive_hp = int(calc_max_hp(player['vitality']) * 0.30)

    conn.execute(
        '''UPDATE players SET
            exp=?, gold=?, hp=?,
            location_id='village', in_battle=0
           WHERE telegram_id=?''',
        (new_exp, new_gold, revive_hp, telegram_id)
    )
    conn.commit()
    conn.close()

    conn2 = get_connection()
    conn2.execute('DELETE FROM skill_cooldowns WHERE telegram_id=?', (telegram_id,))
    conn2.commit()
    conn2.close()

    return penalty

# ────────────────────────────────────────
# ОТОБРАЖЕНИЕ БОЯ
# ────────────────────────────────────────

def build_battle_message(player, mob, battle_state, log):
    lang = player.get('lang', 'ru')

    hp_bar_player = hp_bar(battle_state['player_hp'], battle_state['player_max_hp'])
    hp_bar_mob    = hp_bar(battle_state['mob_hp'],    mob['hp'])

    mana_pct = int(battle_state['player_mana'] / max(battle_state['player_max_mana'], 1) * 10)
    mana_bar = '🔵' * mana_pct + '⚫' * (10 - mana_pct)

    weapon_id   = battle_state.get('weapon_id', 'unarmed')
    weapon_name = get_item_name(weapon_id, lang) if weapon_id != 'unarmed' else t('battle.unarmed', lang)

    text  = f"⚔️ <b>{get_mob_name(mob['id'], lang)}</b>\n"
    text += f"{hp_bar_mob} {battle_state['mob_hp']}/{mob['hp']}\n\n"
    text += f"👤 <b>{t('battle.player_label', lang)}</b>\n"
    text += f"{hp_bar_player} {battle_state['player_hp']}/{battle_state['player_max_hp']}\n"
    text += f"🔵 {battle_state['player_mana']}/{battle_state['player_max_mana']}\n"
    text += f"🗡️ {weapon_name}\n"

    # Активные баффы
    buff_lines = []
    if battle_state.get('defense_buff_turns', 0) > 0:
        buff_lines.append(t('battle.buff_defense', lang,
            value=battle_state['defense_buff_value'],
            turns=battle_state['defense_buff_turns']))
    if battle_state.get('berserk_turns', 0) > 0:
        buff_lines.append(t('battle.buff_berserk', lang,
            value=battle_state['berserk_damage'],
            turns=battle_state['berserk_turns']))
    if battle_state.get('blessing_turns', 0) > 0:
        buff_lines.append(t('battle.buff_blessing', lang,
            value=battle_state['blessing_value'],
            turns=battle_state['blessing_turns']))
    if battle_state.get('regen_turns', 0) > 0:
        buff_lines.append(t('battle.buff_regen', lang,
            amount=battle_state['regen_amount'],
            turns=battle_state['regen_turns']))
    if battle_state.get('resurrection_active'):
        buff_lines.append(t('battle.buff_resurrection', lang))
    if battle_state.get('invincible_turns', 0) > 0:
        buff_lines.append(t('battle.buff_invincible', lang,
            turns=battle_state['invincible_turns']))

    if battle_state.get('dodge_buff_turns', 0) > 0:
        buff_lines.append(t('battle.buff_dodge', lang,
            value=battle_state['dodge_buff_value'],
            turns=battle_state['dodge_buff_turns']))

    if battle_state.get('guaranteed_crit_turns', 0) > 0:
        buff_lines.append(t('battle.buff_guaranteed_crit', lang,
            turns=battle_state['guaranteed_crit_turns']))

    if battle_state.get('hunters_mark_turns', 0) > 0:
        buff_lines.append(t('battle.buff_hunters_mark', lang,
            turns=battle_state['hunters_mark_turns']))

    if battle_state.get('vulnerability_turns', 0) > 0:
        buff_lines.append(t('battle.buff_vulnerability', lang,
            turns=battle_state['vulnerability_turns']))

    if battle_state.get('disarm_turns', 0) > 0:
        buff_lines.append(t('battle.buff_disarm', lang,
            turns=battle_state['disarm_turns']))

    if battle_state.get('fire_shield_turns', 0) > 0:
        buff_lines.append(t('battle.buff_fire_shield', lang,
            value=battle_state['fire_shield_value'],
            turns=battle_state['fire_shield_turns']))

    if buff_lines:
        text += '\n'.join(buff_lines) + '\n'

    # Лог последних ходов
    if log:
        text += '\n' + '\n'.join(
            f'▫️ {l}' for l in log[-4:] if isinstance(l, str)
        ) + '\n'

    # Кнопки
    keyboard = [[
        InlineKeyboardButton(t('battle.attack_btn', lang), callback_data=f"battle_attack_{mob['id']}"),
        InlineKeyboardButton(t('battle.flee_btn', lang),   callback_data=f"battle_flee_{mob['id']}"),
    ]]

    # Скиллы в бою
    weapon_id     = battle_state.get('weapon_id', 'unarmed')
    mastery_level = battle_state.get('mastery_level', 1)
    skills        = get_battle_skills(player['telegram_id'], weapon_id, mastery_level)

    if skills:
        for skill in skills:
            cd    = skill['cooldown_left']
            mana  = skill['mana_cost_actual']
            label = f"{get_skill_name(skill['id'], lang)} {t('common.level_short', lang)}{skill['skill_level']}"
            if cd > 0:
                label += f" ⏳{cd}"
            else:
                label += f" 🔵{mana}"
            keyboard.append([InlineKeyboardButton(
                label, callback_data=f"battle_skill_{skill['id']}|{mob['id']}"
            )])

    keyboard.append([InlineKeyboardButton(
        t('battle.potions_btn', lang), callback_data=f"battle_potions_{mob['id']}"
    )])

    return text, InlineKeyboardMarkup(keyboard)

# ────────────────────────────────────────
# НАЧАЛО БОЯ
# ────────────────────────────────────────

async def start_battle(update, context, mob_id: str, mob_first: bool = False):
    """Запускает бой — вызывается из location.py."""
    query = update.callback_query
    user  = query.from_user
    p     = dict(get_player(user.id))
    mob   = get_mob(mob_id)
    lang  = p.get('lang', 'ru')

    if not mob:
        await query.answer(t('battle.mob_not_found', lang), show_alert=True)
        return

    # Подтягиваем экипированное оружие
    eq = get_connection().execute(
        'SELECT weapon FROM equipment WHERE telegram_id=?', (user.id,)
    ).fetchone()

    if eq and eq['weapon']:
        inv_row = get_connection().execute(
            'SELECT * FROM inventory WHERE id=?', (eq['weapon'],)
        ).fetchone()
        if inv_row:
            weapon_item = get_item(inv_row['item_id'])
            if weapon_item:
                p['weapon_type']   = weapon_item['weapon_type']
                p['weapon_damage'] = random.randint(
                    weapon_item['damage_min'],
                    weapon_item['damage_max']
                )
                p['weapon_name'] = get_item_name(weapon_item['item_id'] if 'item_id' in weapon_item else inv_row['item_id'], lang)
            else:
                p['weapon_type']   = 'melee'
                p['weapon_damage'] = 10
                p['weapon_name']   = t('battle.unarmed', lang)
    else:
        p['weapon_type']   = 'melee'
        p['weapon_damage'] = 10
        p['weapon_name']   = t('battle.unarmed', lang)

    # Инициализируем бой
    battle_state = init_battle(p, mob, mob_first=mob_first)
    battle_state['weapon_type']   = p.get('weapon_type', 'melee')
    battle_state['weapon_damage'] = p.get('weapon_damage', 10)
    battle_state['weapon_name']   = p.get('weapon_name', t('battle.unarmed', lang))

    # Владение оружием
    eq = get_connection().execute(
        'SELECT weapon FROM equipment WHERE telegram_id=?', (user.id,)
    ).fetchone()
    actual_weapon_id = 'unarmed'
    if eq and eq['weapon']:
        inv_row = get_connection().execute(
            'SELECT item_id FROM inventory WHERE id=?', (eq['weapon'],)
        ).fetchone()
        if inv_row:
            actual_weapon_id = inv_row['item_id']

    mastery = get_mastery(user.id, actual_weapon_id)
    battle_state['weapon_id']     = actual_weapon_id
    battle_state['mastery_level'] = mastery['level']
    battle_state['mastery_exp']   = mastery['exp']

    # Если моб ходит первым — сразу обрабатываем его ход
    if mob_first:
        from game.combat import mob_attack
        mob_result = mob_attack(mob, p)
        p['hp']    = mob_result['player_hp']
        battle_state['player_hp'] = p['hp']
        battle_state['log']       = [t('battle.mob_attack', lang,
                                        mob_name=get_mob_name(mob['id'], lang),
                                        damage=mob_result['damage'])]

        if p['hp'] <= 0:
            penalty = apply_death(user.id, p)
            await query.edit_message_text(
                t('battle.death_first_strike', lang,
                  mob_name=get_mob_name(mob['id'], lang),
                  exp_loss=penalty['exp_loss'],
                  gold_loss=penalty['gold_loss']),
                parse_mode='HTML'
            )
            return

    # Сохраняем состояние в context
    context.user_data['battle']     = battle_state
    context.user_data['battle_mob'] = mob

    save_battle(user.id, battle_state)

    text, keyboard = build_battle_message(p, mob, battle_state, battle_state.get('log', []))
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')

# ────────────────────────────────────────
# КНОПКИ В БОЮ
# ────────────────────────────────────────

async def safe_edit(query, text, reply_markup=None, parse_mode='HTML'):
    """edit_message_text без краша если сообщение не изменилось."""
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as e:
        if 'Message is not modified' not in str(e):
            raise

async def _handle_victory_cleanup(
    query,
    context,
    user_id: int,
    player: dict,
    mob: dict,
    battle_state: dict,
    lang: str,
    levelup_before_loot: bool = False,
):
    """Общий post-victory cleanup для обычной атаки и скиллов."""
    rewards = calc_rewards(mob)
    result_reward = apply_rewards(user_id, player, rewards)
    end_battle(user_id)
    context.user_data.pop('battle', None)
    context.user_data.pop('battle_mob', None)

    weapon_id = battle_state.get('weapon_id', 'unarmed')
    mastery_result = add_mastery_exp(user_id, weapon_id, 10)
    mastery_text = _build_mastery_text(mastery_result, lang)

    victory_text = t('battle.victory', lang,
                     mob_name=get_mob_name(mob['id'], lang),
                     exp=rewards['exp'],
                     gold=rewards['gold'])

    levelup_text = ""
    if result_reward['leveled_up']:
        levelup_text = '\n\n' + t('battle.levelup', lang, level=result_reward['new_level'])

    loot_text = ""
    if rewards['loot']:
        loot_names = [get_item_name(i, lang) for i in rewards['loot']]
        loot_text = '\n' + t('battle.loot', lang, items=', '.join(loot_names))

    if levelup_before_loot:
        await safe_edit(query, victory_text + levelup_text + loot_text + mastery_text, parse_mode='HTML')
    else:
        await safe_edit(query, victory_text + loot_text + levelup_text + mastery_text, parse_mode='HTML')

async def _handle_death_or_resurrection(
    query,
    context,
    user_id: int,
    player: dict,
    mob: dict,
    battle_state: dict,
    lang: str,
    log: list,
    death_key: str = 'battle.death',
    clear_player_dead_flag: bool = False,
    answer_on_resurrection: bool = False,
) -> bool:
    """
    Общий путь завершения боя при смерти игрока.
    Возвращает True, если ветка (resurrection/death) была полностью обработана.
    """
    if battle_state.get('resurrection_active'):
        revive_hp = int(battle_state['player_max_hp'] * battle_state['resurrection_hp'] / 100)
        battle_state['player_hp'] = revive_hp
        if clear_player_dead_flag:
            battle_state['player_dead'] = False
        battle_state['resurrection_active'] = False
        log.append(t('battle.buff_resurrection_proc', lang, hp=revive_hp))
        context.user_data['battle'] = battle_state

        text, keyboard = build_battle_message(player, mob, battle_state, log)
        await safe_edit(query, text, reply_markup=keyboard, parse_mode='HTML')
        if answer_on_resurrection:
            await query.answer()
        return True

    penalty = apply_death(user_id, player)
    end_battle(user_id)
    context.user_data.pop('battle', None)
    context.user_data.pop('battle_mob', None)
    await safe_edit(query,
        t(death_key, lang, exp_loss=penalty['exp_loss'], gold_loss=penalty['gold_loss']),
        parse_mode='HTML'
    )
    return True

def _resolve_post_skill_combat_resolution(
    player: dict,
    mob: dict,
    battle_state: dict,
    log: list,
    lang: str,
    user_id: int,
) -> None:
    """Единый post-skill combat resolution: тики перед ответом и ответ моба."""
    log.extend(apply_pre_enemy_response_ticks(mob, battle_state))

    if battle_state['mob_hp'] > 0:
        player['hp'] = battle_state['player_hp']
        log.extend(resolve_enemy_response(mob, player, battle_state, lang=lang, user_id=user_id))

    battle_state['log'] = log[-6:]

async def _resolve_post_attack_combat_resolution(
    query,
    context,
    user_id: int,
    player: dict,
    mob: dict,
    battle_state: dict,
    lang: str,
) -> bool:
    """Единый post-attack combat resolution: victory/death/persist/render."""
    # Моб убит
    if battle_state['mob_dead']:
        await _handle_victory_cleanup(
            query=query,
            context=context,
            user_id=user_id,
            player=player,
            mob=mob,
            battle_state=battle_state,
            lang=lang,
            levelup_before_loot=False,
        )
        return True

    # Игрок убит
    if battle_state['player_dead']:
        await _handle_death_or_resurrection(
            query=query,
            context=context,
            user_id=user_id,
            player=player,
            mob=mob,
            battle_state=battle_state,
            lang=lang,
            log=battle_state['log'],
            death_key='battle.death',
            clear_player_dead_flag=True,
            answer_on_resurrection=False,
        )
        return True

    # Сохраняем HP и ману в БД после каждого хода
    conn = get_connection()
    conn.execute(
        'UPDATE players SET hp=?, mana=? WHERE telegram_id=?',
        (battle_state['player_hp'], battle_state['player_mana'], user_id)
    )
    conn.commit()
    conn.close()

    # Бой продолжается
    text, keyboard = build_battle_message(player, mob, battle_state, battle_state['log'])
    await safe_edit(query, text, reply_markup=keyboard, parse_mode='HTML')
    return False

async def handle_battle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    user  = query.from_user
    p     = dict(get_player(user.id))
    lang  = p.get('lang', 'ru')

    battle_state = context.user_data.get('battle')
    mob          = context.user_data.get('battle_mob')

    # Если состояние боя потеряно (перезапуск бота)
    if not battle_state or not mob:
        end_battle(user.id)
        conn = get_connection()
        conn.execute('DELETE FROM skill_cooldowns WHERE telegram_id=?', (user.id,))
        conn.commit()
        conn.close()

        await safe_edit(query, t('battle.state_lost', lang))
        return

    # ── Открыть зелья в бою ──
    if data.startswith('battle_potions_'):
        mob_id  = data.replace('battle_potions_', '')
        potions = get_connection().execute('''
            SELECT inv.id, inv.item_id, inv.quantity
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            WHERE inv.telegram_id=? AND i.item_type='potion'
        ''', (user.id,)).fetchall()

        if not potions:
            await query.answer(t('battle.no_potions', lang), show_alert=True)
            return

        keyboard = []
        for pot in potions:
            item = get_item(pot['item_id'])
            keyboard.append([InlineKeyboardButton(
                f"💊 {item['name']} x{pot['quantity']}",
                callback_data=f"battle_use_potion_{pot['id']}_{mob_id}"
            )])
        keyboard.append([InlineKeyboardButton(
            t('common.back', lang), callback_data=f"battle_back_{mob_id}"
        )])

        await safe_edit(query, 
            t('battle.choose_potion', lang),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        await query.answer()
        return

    # ── Использовать зелье в бою ──
    if data.startswith('battle_use_potion_'):
        rest   = data.replace('battle_use_potion_', '', 1)
        inv_id = int(rest.split('_')[0])
        mob_id = '_'.join(rest.split('_')[1:])

        conn    = get_connection()
        inv_row = conn.execute('SELECT * FROM inventory WHERE id=?', (inv_id,)).fetchone()
        conn.close()

        item  = get_item(inv_row['item_id'])
        bonus = json.loads(item['stat_bonus_json'])

        conn = get_connection()
        msg  = ""

        if 'heal' in bonus:
            heal = min(bonus['heal'], battle_state['player_max_hp'] - battle_state['player_hp'])
            battle_state['player_hp'] += heal
            conn.execute('UPDATE players SET hp=hp+? WHERE telegram_id=?', (heal, user.id))
            msg += t('battle.potion_heal', lang, amount=heal)

        if 'mana' in bonus:
            mana_gain = min(bonus['mana'], battle_state['player_max_mana'] - battle_state['player_mana'])
            battle_state['player_mana'] += mana_gain
            conn.execute('UPDATE players SET mana=mana+? WHERE telegram_id=?', (mana_gain, user.id))
            msg += t('battle.potion_mana', lang, amount=mana_gain)

        if inv_row['quantity'] > 1:
            conn.execute('UPDATE inventory SET quantity=quantity-1 WHERE id=?', (inv_id,))
        else:
            conn.execute('DELETE FROM inventory WHERE id=?', (inv_id,))

        conn.commit()
        conn.close()

        context.user_data['battle'] = battle_state
        await query.answer(msg or t('battle.potion_used', lang), show_alert=True)

        mob = context.user_data.get('battle_mob')
        text, keyboard = build_battle_message(p, mob, battle_state, [])
        await safe_edit(query, text, reply_markup=keyboard, parse_mode='HTML')
        return

    # ── Назад к бою ──
    if data.startswith('battle_back_'):
        mob = context.user_data.get('battle_mob')
        text, keyboard = build_battle_message(p, mob, battle_state, battle_state.get('log', []))
        await safe_edit(query, text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    # ── Использовать скилл ──
    if data.startswith('battle_skill_'):
        rest     = data.replace('battle_skill_', '', 1)
        skill_id, mob_id = rest.split('|', 1)

        mob = context.user_data.get('battle_mob')
        p['hp']   = battle_state['player_hp']
        p['mana'] = battle_state['player_mana']
        mob_state = {
            'hp':      battle_state['mob_hp'],
            'defense': mob.get('defense', 0),
            'effects': battle_state.get('mob_effects', []),
        }

        result = use_skill(skill_id, p, mob_state, battle_state, user.id, lang)

        if not result['success']:
            await query.answer(result['log'], show_alert=True)
            return

        log = battle_state.get('log', [])
        log.append(result['log'])

        if result['damage'] > 0:
            battle_state['mob_hp'] = max(0, battle_state['mob_hp'] - result['damage'])

        if result['heal'] > 0:
            battle_state['player_hp'] = min(
                battle_state['player_max_hp'],
                battle_state['player_hp'] + result['heal']
            )

        if result['effects']:
            if 'mob_effects' not in battle_state:
                battle_state['mob_effects'] = []
            battle_state['mob_effects'].extend(result['effects'])

        weapon_id = battle_state.get('weapon_id', 'unarmed')
        add_mastery_exp(user.id, weapon_id, 5)

        # Проверяем смерть моба после скилла
        if battle_state['mob_hp'] <= 0:
            context.user_data['battle'] = battle_state
            await _handle_victory_cleanup(
                query=query,
                context=context,
                user_id=user.id,
                player=p,
                mob=mob,
                battle_state=battle_state,
                lang=lang,
                levelup_before_loot=True,
            )
            return

        # Ход моба после скилла: pre-turn ticking + ответ врага + обновление лога
        _resolve_post_skill_combat_resolution(
            player=p,
            mob=mob,
            battle_state=battle_state,
            log=log,
            lang=lang,
            user_id=user.id,
        )

        tick_cooldowns(user.id)
        context.user_data['battle'] = battle_state

        conn = get_connection()
        conn.execute(
            'UPDATE players SET hp=?, mana=? WHERE telegram_id=?',
            (battle_state['player_hp'], battle_state['player_mana'], user.id)
        )
        conn.commit()
        conn.close()

        if battle_state['player_hp'] <= 0:
            await _handle_death_or_resurrection(
                query=query,
                context=context,
                user_id=user.id,
                player=p,
                mob=mob,
                battle_state=battle_state,
                lang=lang,
                log=log,
                death_key='battle.death',
                clear_player_dead_flag=False,
                answer_on_resurrection=True,
            )
            return

        text, keyboard = build_battle_message(p, mob, battle_state, battle_state['log'])
        await safe_edit(query, text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    # ── АТАКА ──
    if data.startswith('battle_attack_'):
        p['guaranteed_crit'] = False
        if battle_state.get('guaranteed_crit_turns', 0) > 0:
            p['guaranteed_crit'] = True
            battle_state['guaranteed_crit_turns'] -= 1

        battle_state = process_turn(p, mob, battle_state, lang, user_id=user.id)
        context.user_data['battle'] = battle_state

        tick_cooldowns(user.id)

        handled = await _resolve_post_attack_combat_resolution(
            query=query,
            context=context,
            user_id=user.id,
            player=p,
            mob=mob,
            battle_state=battle_state,
            lang=lang,
        )
        if handled:
            return

    # ── ПОБЕГ ──
    elif data.startswith('battle_flee_'):
        if random.randint(1, 100) <= 20:
            end_battle(user.id)
            conn = get_connection()
            conn.execute('DELETE FROM skill_cooldowns WHERE telegram_id=?', (user.id,))
            conn.commit()
            conn.close()
            context.user_data.pop('battle', None)
            context.user_data.pop('battle_mob', None)
            await safe_edit(query, 
                t('battle.flee_success', lang, mob_name=get_mob_name(mob['id'], lang)),
                parse_mode='HTML'
            )
            await query.answer()
            return
        else:
            p['hp'] = battle_state['player_hp']
            prev_hp = battle_state['player_hp']
            flee_log = resolve_enemy_response(mob, p, battle_state, lang=lang, user_id=user.id)
            new_hp = battle_state['player_hp']
            context.user_data['battle'] = battle_state

            if new_hp <= 0:
                penalty = apply_death(user.id, p)
                end_battle(user.id)
                context.user_data.pop('battle', None)
                context.user_data.pop('battle_mob', None)
                await safe_edit(query, 
                    t('battle.flee_death', lang,
                      mob_name=get_mob_name(mob['id'], lang),
                      exp_loss=penalty['exp_loss'],
                      gold_loss=penalty['gold_loss']),
                    parse_mode='HTML'
                )
                return

            damage_taken = max(0, prev_hp - new_hp)
            flee_fail_header = t('battle.flee_fail', lang,
                                  mob_name=get_mob_name(mob['id'], lang),
                                  damage=damage_taken)
            text, keyboard = build_battle_message(p, mob, battle_state, flee_log)
            await safe_edit(query, 
                flee_fail_header + '\n\n' + text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )


    try:
        await query.answer()
    except BadRequest:
        pass

# ────────────────────────────────────────
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ
# ────────────────────────────────────────

def _build_mastery_text(mastery_result: dict, lang: str) -> str:
    """Формирует текст о повышении мастерства оружия."""
    if not mastery_result.get('leveled_up'):
        return ""

    text = '\n' + t('battle.mastery_up', lang, level=mastery_result['new_level'])
    for skill in mastery_result.get('new_skills', []):
        text += '\n' + t('battle.skill_unlocked', lang, skill_name=get_skill_name(skill['id'], lang))
    return text

print('✅ handlers/battle.py создан!')
