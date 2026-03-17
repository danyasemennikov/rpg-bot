# ============================================================
# inventory.py — инвентарь игрока
# ============================================================

import sys, json, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_player, get_connection, is_in_battle
from game.items_data import get_item
from game.i18n import t, get_player_lang, get_item_name

RARITY_KEYS = {
    'common':    'rarity_common',
    'uncommon':  'rarity_uncommon',
    'rare':      'rarity_rare',
    'epic':      'rarity_epic',
    'legendary': 'rarity_legendary',
}

RARITY_NAME = {
    'ru': {'common': 'Обычный', 'uncommon': 'Необычный', 'rare': 'Редкий', 'epic': 'Эпический', 'legendary': 'Легендарный'},
    'en': {'common': 'Common',  'uncommon': 'Uncommon',  'rare': 'Rare',   'epic': 'Epic',      'legendary': 'Legendary'},
    'es': {'common': 'Común',   'uncommon': 'Poco común','rare': 'Raro',   'epic': 'Épico',     'legendary': 'Legendario'},
}

WEAPON_TYPE_NAME = {
    'ru': {'melee': 'Ближний бой', 'ranged': 'Дальний бой', 'magic': 'Магия', 'light': 'Свет'},
    'en': {'melee': 'Melee',       'ranged': 'Ranged',       'magic': 'Magic', 'light': 'Holy'},
    'es': {'melee': 'Cuerpo a cuerpo', 'ranged': 'A distancia', 'magic': 'Magia', 'light': 'Luz'},
}

STAT_NAMES = {
    'ru': {'strength': '💪 Сила', 'agility': '🤸 Ловкость', 'intuition': '🔮 Интуиция', 'vitality': '❤️ Живучесть', 'wisdom': '🧠 Мудрость', 'luck': '🍀 Удача'},
    'en': {'strength': '💪 Strength', 'agility': '🤸 Agility', 'intuition': '🔮 Intuition', 'vitality': '❤️ Vitality', 'wisdom': '🧠 Wisdom', 'luck': '🍀 Luck'},
    'es': {'strength': '💪 Fuerza', 'agility': '🤸 Agilidad', 'intuition': '🔮 Intuición', 'vitality': '❤️ Vitalidad', 'wisdom': '🧠 Sabiduría', 'luck': '🍀 Suerte'},
}

TABS = ['weapon', 'armor', 'potion', 'material']

def get_inventory(telegram_id: int, item_type: str = None) -> list:
    conn = get_connection()
    if item_type:
        rows = conn.execute('''
            SELECT inv.id, inv.item_id, inv.quantity, inv.enhance_level
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            WHERE inv.telegram_id=? AND i.item_type=?
        ''', (telegram_id, item_type)).fetchall()
    else:
        rows = conn.execute('''
            SELECT inv.id, inv.item_id, inv.quantity, inv.enhance_level
            FROM inventory inv
            WHERE inv.telegram_id=?
        ''', (telegram_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_equipped(telegram_id: int) -> dict:
    conn = get_connection()
    eq = conn.execute(
        'SELECT * FROM equipment WHERE telegram_id=?', (telegram_id,)
    ).fetchone()
    conn.close()
    return dict(eq) if eq else {}

def is_equipped(telegram_id: int, inv_id: int) -> bool:
    eq = get_equipped(telegram_id)
    return inv_id in eq.values()

def build_tab_keyboard(active_tab: str, lang: str) -> list:
    row = []
    for tab_key in TABS:
        label = t(f'inventory.tab_{tab_key}', lang)
        if tab_key == active_tab:
            row.append(InlineKeyboardButton(f"[{label}]", callback_data='inv_noop'))
        else:
            row.append(InlineKeyboardButton(label, callback_data=f'inv_tab_{tab_key}'))
    return row

def build_inventory_list(telegram_id: int, active_tab: str, lang: str = 'ru') -> tuple:
    items    = get_inventory(telegram_id, active_tab)
    eq       = get_equipped(telegram_id)
    keyboard = [build_tab_keyboard(active_tab, lang)]

    text = t('inventory.title', lang) + '\n\n'

    if not items:
        text += t('inventory.empty', lang) + '\n'
    else:
        for inv_row in items:
            item = get_item(inv_row['item_id'])
            if not item:
                continue

            rarity  = t(f"inventory.{RARITY_KEYS.get(item['rarity'], 'rarity_common')}", lang)
            enhance = f" +{inv_row['enhance_level']}" if inv_row['enhance_level'] > 0 else ""
            qty     = f" x{inv_row['quantity']}" if inv_row['quantity'] > 1 else ""
            eq_mark = t('inventory.equipped', lang) if inv_row['id'] in eq.values() else ""

            label = f"{rarity} {get_item_name(inv_row['item_id'], lang)}{enhance}{qty}{eq_mark}"
            keyboard.append([InlineKeyboardButton(
                label,
                callback_data=f"inv_item_{inv_row['id']}_{active_tab}"
            )])

    return text, InlineKeyboardMarkup(keyboard)

def build_item_detail(telegram_id: int, inv_id: int, back_tab: str, lang: str = 'ru') -> tuple:
    conn    = get_connection()
    inv_row = conn.execute(
        'SELECT * FROM inventory WHERE id=? AND telegram_id=?',
        (inv_id, telegram_id)
    ).fetchone()
    conn.close()

    if not inv_row:
        return t('inventory.item_not_found', lang), InlineKeyboardMarkup([[
            InlineKeyboardButton(t('inventory.back_btn', lang), callback_data=f"inv_tab_{back_tab}")
        ]])

    inv_row      = dict(inv_row)
    item         = get_item(inv_row['item_id'])
    eq           = get_equipped(telegram_id)
    equipped     = inv_row['id'] in eq.values()

    rarity_emoji = t(f"inventory.{RARITY_KEYS.get(item['rarity'], 'rarity_common')}", lang)
    rarity_name  = RARITY_NAME.get(lang, RARITY_NAME['ru']).get(item['rarity'], '')
    enhance      = f" <b>+{inv_row['enhance_level']}</b>" if inv_row['enhance_level'] > 0 else ""
    item_name    = get_item_name(inv_row['item_id'], lang)

    text = f"{rarity_emoji} <b>{item_name}{enhance}</b>\n{rarity_name}"

    if item['item_type'] == 'weapon':
        wtype = WEAPON_TYPE_NAME.get(lang, WEAPON_TYPE_NAME['ru']).get(item['weapon_type'], '')
        text += f" | {wtype} | Ур.{item['req_level']}\n\n"
        text += t('inventory.damage', lang, min=item['damage_min'], max=item['damage_max']) + '\n'
    elif item['item_type'] == 'armor':
        text += f" | Ур.{item['req_level']}\n\n"
        text += t('inventory.defense', lang, val=item['defense']) + '\n'
    else:
        text += '\n\n'

    text += t('inventory.weight', lang, val=item['weight']) + '\n'

    if inv_row['quantity'] > 1:
        text += t('inventory.quantity', lang, val=inv_row['quantity']) + '\n'

    # Требования
    stat_names = STAT_NAMES.get(lang, STAT_NAMES['ru'])
    reqs = []
    if item['req_strength']  > 0: reqs.append(f"{stat_names['strength']} {item['req_strength']}")
    if item['req_agility']   > 0: reqs.append(f"{stat_names['agility']} {item['req_agility']}")
    if item['req_intuition'] > 0: reqs.append(f"{stat_names['intuition']} {item['req_intuition']}")
    if item['req_wisdom']    > 0: reqs.append(f"{stat_names['wisdom']} {item['req_wisdom']}")
    if reqs:
        text += t('inventory.reqs', lang, val=', '.join(reqs)) + '\n'

    # Бонусы
    stat_bonus = json.loads(item['stat_bonus_json'])
    bonuses = [f"{stat_names.get(k, k)} +{v}" for k, v in stat_bonus.items() if k not in ('heal', 'mana')]
    if bonuses:
        text += t('inventory.bonuses', lang, val=', '.join(bonuses)) + '\n'

    if item['description']:
        text += f"\n<i>{item['description']}</i>\n"

    if equipped:
        text += f"\n<b>{t('inventory.equipped', lang)}</b>"

    # Кнопки
    keyboard = []
    if item['item_type'] == 'weapon':
        slot = 'weapon'
        if equipped:
            keyboard.append([InlineKeyboardButton(t('inventory.unequip_btn', lang), callback_data=f"inv_unequip_{inv_id}_{slot}_{back_tab}")])
        else:
            keyboard.append([InlineKeyboardButton(t('inventory.equip_btn', lang), callback_data=f"inv_equip_{inv_id}_{slot}_{back_tab}")])
    elif item['item_type'] == 'armor':
        slot = 'chest'
        if equipped:
            keyboard.append([InlineKeyboardButton(t('inventory.unequip_btn', lang), callback_data=f"inv_unequip_{inv_id}_{slot}_{back_tab}")])
        else:
            keyboard.append([InlineKeyboardButton(t('inventory.equip_btn', lang), callback_data=f"inv_equip_{inv_id}_{slot}_{back_tab}")])
    elif item['item_type'] == 'potion':
        keyboard.append([InlineKeyboardButton(t('inventory.use_btn', lang), callback_data=f"inv_use_{inv_id}_{back_tab}")])

    keyboard.append([
        InlineKeyboardButton(t('inventory.drop_btn', lang),     callback_data=f"inv_drop_{inv_id}_{back_tab}"),
        InlineKeyboardButton(t('inventory.transfer_btn', lang), callback_data=f"inv_transfer_{inv_id}"),
    ])
    keyboard.append([InlineKeyboardButton(t('inventory.back_btn', lang), callback_data=f"inv_tab_{back_tab}")])

    return text, InlineKeyboardMarkup(keyboard)

# ────────────────────────────────────────
# КОМАНДА /inventory
# ────────────────────────────────────────

async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p    = get_player(user.id)
    lang = get_player_lang(user.id)

    if not p:
        await update.message.reply_text(t('common.no_character', lang))
        return

    text, keyboard = build_inventory_list(user.id, 'weapon', lang)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')

# ────────────────────────────────────────
# КНОПКИ ИНВЕНТАРЯ
# ────────────────────────────────────────

async def handle_inventory_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    user  = query.from_user
    p     = dict(get_player(user.id))
    lang  = get_player_lang(user.id)

    if data == 'inv_noop':
        await query.answer()
        return

    # ── Смена вкладки ──
    if data.startswith('inv_tab_'):
        tab = data.replace('inv_tab_', '')
        text, keyboard = build_inventory_list(user.id, tab, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    # ── Детальный вид ──
    if data.startswith('inv_item_'):
        parts    = data.split('_')
        inv_id   = int(parts[2])
        back_tab = parts[3]
        text, keyboard = build_item_detail(user.id, inv_id, back_tab, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    # ── Экипировать ──
    if data.startswith('inv_equip_'):
        parts    = data.split('_')
        inv_id   = int(parts[2])
        slot     = parts[3]
        back_tab = parts[4]

        conn    = get_connection()
        inv_row = conn.execute('SELECT * FROM inventory WHERE id=?', (inv_id,)).fetchone()
        conn.close()
        item = get_item(inv_row['item_id'])

        if p['level']     < item['req_level']:     await query.answer(t('inventory.req_level',     lang, level=item['req_level']),     show_alert=True); return
        if p['strength']  < item['req_strength']:  await query.answer(t('inventory.req_strength',  lang, val=item['req_strength']),    show_alert=True); return
        if p['agility']   < item['req_agility']:   await query.answer(t('inventory.req_agility',   lang, val=item['req_agility']),     show_alert=True); return
        if p['intuition'] < item['req_intuition']: await query.answer(t('inventory.req_intuition', lang, val=item['req_intuition']),   show_alert=True); return
        if p['wisdom']    < item['req_wisdom']:    await query.answer(t('inventory.req_wisdom',    lang, val=item['req_wisdom']),      show_alert=True); return

        conn = get_connection()
        conn.execute(f'UPDATE equipment SET {slot}=? WHERE telegram_id=?', (inv_id, user.id))
        conn.commit()
        conn.close()

        await query.answer(t('inventory.equipped_ok', lang, name=get_item_name(inv_row['item_id'], lang)))
        text, keyboard = build_item_detail(user.id, inv_id, back_tab, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    # ── Снять ──
    if data.startswith('inv_unequip_'):
        parts    = data.split('_')
        inv_id   = int(parts[2])
        slot     = parts[3]
        back_tab = parts[4]

        conn = get_connection()
        conn.execute(f'UPDATE equipment SET {slot}=NULL WHERE telegram_id=?', (user.id,))
        conn.commit()
        conn.close()

        await query.answer(t('inventory.unequipped_ok', lang))
        text, keyboard = build_item_detail(user.id, inv_id, back_tab, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    # ── Использовать зелье ──
    if data.startswith('inv_use_'):
        parts    = data.split('_')
        inv_id   = int(parts[2])
        back_tab = parts[3]

        conn    = get_connection()
        inv_row = conn.execute('SELECT * FROM inventory WHERE id=?', (inv_id,)).fetchone()
        conn.close()
        item  = get_item(inv_row['item_id'])
        bonus = json.loads(item['stat_bonus_json'])

        conn = get_connection()
        msg  = ""

        if 'heal' in bonus:
            heal = min(bonus['heal'], p['max_hp'] - p['hp'])
            conn.execute('UPDATE players SET hp=hp+? WHERE telegram_id=?', (heal, user.id))
            msg += t('inventory.healed', lang, val=heal) + '\n'

        if 'mana' in bonus:
            mana_gain = min(bonus['mana'], p['max_mana'] - p['mana'])
            conn.execute('UPDATE players SET mana=mana+? WHERE telegram_id=?', (mana_gain, user.id))
            msg += t('inventory.mana_restored', lang, val=mana_gain) + '\n'

        if inv_row['quantity'] > 1:
            conn.execute('UPDATE inventory SET quantity=quantity-1 WHERE id=?', (inv_id,))
        else:
            conn.execute('DELETE FROM inventory WHERE id=?', (inv_id,))

        conn.commit()
        conn.close()

        await query.answer(msg or t('inventory.used_ok', lang), show_alert=True)
        text, keyboard = build_inventory_list(user.id, back_tab, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    # ── Выбросить ──
    if data.startswith('inv_drop_'):
        parts    = data.split('_')
        inv_id   = int(parts[2])
        back_tab = parts[3]

        if is_equipped(user.id, inv_id):
            await query.answer(t('inventory.drop_equipped', lang), show_alert=True)
            return

        conn    = get_connection()
        inv_row = conn.execute('SELECT * FROM inventory WHERE id=?', (inv_id,)).fetchone()
        item    = get_item(inv_row['item_id'])

        if inv_row['quantity'] > 1:
            conn.execute('UPDATE inventory SET quantity=quantity-1 WHERE id=?', (inv_id,))
        else:
            conn.execute('DELETE FROM inventory WHERE id=?', (inv_id,))
        conn.commit()
        conn.close()

        await query.answer(t('inventory.dropped', lang, name=get_item_name(inv_row['item_id'], lang)))
        text, keyboard = build_inventory_list(user.id, back_tab, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    # ── Передать ──
    if data.startswith('inv_transfer_'):
        inv_id = int(data.replace('inv_transfer_', ''))
        context.user_data['transfer_item'] = inv_id
        await query.edit_message_text(
            t('inventory.transfer_prompt', lang),
            parse_mode='HTML'
        )
        await query.answer()
        return

    await query.answer()

# ── Обработка ввода username для передачи ──
async def handle_transfer_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if 'transfer_item' not in context.user_data:
        return False

    inv_id   = context.user_data.pop('transfer_item')
    username = update.message.text.strip().lstrip('@')
    user     = update.effective_user
    lang     = get_player_lang(user.id)

    conn   = get_connection()
    target = conn.execute('SELECT * FROM players WHERE username=?', (username,)).fetchone()

    if not target:
        await update.message.reply_text(t('inventory.transfer_not_found', lang, username=username))
        conn.close()
        return True

    if target['telegram_id'] == user.id:
        await update.message.reply_text(t('inventory.transfer_self', lang))
        conn.close()
        return True

    inv_row = conn.execute(
        'SELECT * FROM inventory WHERE id=? AND telegram_id=?', (inv_id, user.id)
    ).fetchone()

    if not inv_row:
        await update.message.reply_text(t('inventory.item_not_found', lang))
        conn.close()
        return True

    item = get_item(inv_row['item_id'])

    existing = conn.execute(
        'SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id=?',
        (target['telegram_id'], inv_row['item_id'])
    ).fetchone()

    if existing:
        conn.execute('UPDATE inventory SET quantity=quantity+1 WHERE id=?', (existing['id'],))
    else:
        conn.execute(
            'INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?,?,1)',
            (target['telegram_id'], inv_row['item_id'])
        )

    if inv_row['quantity'] > 1:
        conn.execute('UPDATE inventory SET quantity=quantity-1 WHERE id=?', (inv_id,))
    else:
        conn.execute('DELETE FROM inventory WHERE id=?', (inv_id,))

    conn.commit()
    conn.close()

    await update.message.reply_text(
        t('inventory.transfer_ok', lang, name=get_item_name(inv_row['item_id'], lang), username=username),
        parse_mode='HTML'
    )
    return True

print('✅ handlers/inventory.py обновлён!')