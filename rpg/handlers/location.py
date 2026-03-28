# ============================================================
# location.py — отображение локации и агрессия мобов
# ============================================================

import sys, random, asyncio
sys.path.append('/content/rpg_bot')

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from database import get_player, get_connection, is_in_battle
from game.locations import get_location, get_connected_locations
from game.mobs import get_mob
from game.items_data import get_item
from game.i18n import t, get_player_lang, get_mob_name, get_location_name, get_location_desc, get_item_name

CURATED_EQUIPMENT_VENDOR_STOCK = {
    'village': [
        {'item_id': 'oak_guard_shield', 'level_min': 4},
        {'item_id': 'apprentice_focus_orb', 'level_min': 3},
        {'item_id': 'novice_censer', 'level_min': 3},
        {'item_id': 'militia_cuirass', 'level_min': 4},
        {'item_id': 'acolyte_robe', 'level_min': 4},
        {'item_id': 'band_of_precision', 'level_min': 5},
        {'item_id': 'ring_of_quiet_mind', 'level_min': 5},
    ],
}


def get_curated_shop_stock(location_id: str, player_level: int) -> list[dict]:
    """Возвращает доступный список витрины магазина для локации и уровня."""
    stock_rows = CURATED_EQUIPMENT_VENDOR_STOCK.get(location_id, [])
    available = []
    for row in stock_rows:
        item = get_item(row['item_id'])
        if not item:
            continue
        level_min = row.get('level_min', item.get('req_level', 1))
        if player_level < level_min:
            continue
        if item.get('buy_price', 0) <= 0:
            continue
        available.append({
            'item_id': row['item_id'],
            'level_min': level_min,
            'price': item['buy_price'],
        })
    return available


def _add_item_to_inventory(telegram_id: int, item_id: str, quantity: int = 1):
    conn = get_connection()
    existing = conn.execute(
        'SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id=?',
        (telegram_id, item_id),
    ).fetchone()
    if existing:
        conn.execute(
            'UPDATE inventory SET quantity=? WHERE id=?',
            (existing['quantity'] + quantity, existing['id']),
        )
    else:
        conn.execute(
            'INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)',
            (telegram_id, item_id, quantity),
        )
    conn.commit()
    conn.close()


def try_buy_curated_shop_item(telegram_id: int, location_id: str, player_level: int, item_id: str) -> dict:
    """Покупка предмета из витрины магазина. Возвращает статус операции."""
    stock_by_id = {
        row['item_id']: row
        for row in CURATED_EQUIPMENT_VENDOR_STOCK.get(location_id, [])
    }
    stock_row = stock_by_id.get(item_id)
    if not stock_row:
        return {'ok': False, 'reason': 'not_available'}

    item = get_item(item_id)
    if not item:
        return {'ok': False, 'reason': 'not_available'}

    level_min = stock_row.get('level_min', item.get('req_level', 1))
    if player_level < level_min:
        return {'ok': False, 'reason': 'level_required', 'required_level': level_min}

    price = item.get('buy_price', 0)
    conn = get_connection()
    player_row = conn.execute('SELECT gold FROM players WHERE telegram_id=?', (telegram_id,)).fetchone()
    if not player_row:
        conn.close()
        return {'ok': False, 'reason': 'not_available'}

    if player_row['gold'] < price:
        conn.close()
        return {'ok': False, 'reason': 'not_enough_gold', 'price': price}

    conn.execute(
        'UPDATE players SET gold=gold-? WHERE telegram_id=?',
        (price, telegram_id),
    )
    conn.commit()
    conn.close()

    _add_item_to_inventory(telegram_id, item_id, quantity=1)
    return {'ok': True, 'price': price}


def build_shop_message(player: dict, location: dict) -> tuple[str, InlineKeyboardMarkup]:
    lang = player.get('lang', 'ru')
    stock_rows = CURATED_EQUIPMENT_VENDOR_STOCK.get(location['id'], [])
    text = t('location.shop_title', lang) + '\n\n'
    keyboard = []

    if not stock_rows:
        text += t('location.shop_empty', lang)
    else:
        for stock_row in stock_rows:
            item = get_item(stock_row['item_id'])
            if not item:
                continue
            item_name = get_item_name(stock_row['item_id'], lang)
            req_level = stock_row.get('level_min', item.get('req_level', 1))
            price = item.get('buy_price', 0)
            text += t(
                'location.shop_entry',
                lang,
                name=item_name,
                level=req_level,
                price=price,
            ) + '\n'
            if player['level'] >= req_level:
                keyboard.append([InlineKeyboardButton(
                    t('location.shop_buy_btn', lang, name=item_name, price=price),
                    callback_data=f"shop_buy_{stock_row['item_id']}",
                )])

    keyboard.append([InlineKeyboardButton(t('location.shop_back_btn', lang), callback_data='shop_back')])
    return text, InlineKeyboardMarkup(keyboard)

# ────────────────────────────────────────
# ОТОБРАЖЕНИЕ ЛОКАЦИИ
# ────────────────────────────────────────

def build_location_message(player: dict, location: dict) -> tuple:
    """Возвращает (текст, клавиатура) для текущей локации."""
    lang = player.get('lang', 'ru')

    if location['safe']:
        lvl_range = t('location.safe_zone', lang)
    else:
        lvl_range = t('location.level_range', lang,
                      min=location['level_min'],
                      max=location['level_max'])

    text  = f"📍 <b>{get_location_name(location['id'], lang)}</b>  |  {lvl_range}\n"
    text += f"<i>{get_location_desc(location['id'], lang)}</i>\n\n"

    keyboard = []

    # ── Мобы ──
    if location['mobs']:
        text += t('location.mobs_nearby', lang) + '\n'
        for mob_id in location['mobs']:
            mob = get_mob(mob_id)
            if not mob:
                continue
            agr_tag  = t('location.aggressive_tag', lang) if mob['aggressive'] else ""
            lvl_diff = mob['level'] - player['level']

            if lvl_diff >= 3:
                diff = t('location.diff_deadly', lang)
            elif lvl_diff >= 1:
                diff = t('location.diff_hard', lang)
            elif lvl_diff == 0:
                diff = t('location.diff_normal', lang)
            elif lvl_diff >= -2:
                diff = t('location.diff_easy', lang)
            else:
                diff = t('location.diff_unknown', lang)

            text += f"{diff} {get_mob_name(mob_id, lang)}  {t('common.level_short', lang)}{mob['level']}{agr_tag}\n"
            keyboard.append([InlineKeyboardButton(
                t('location.attack_mob_btn', lang, name=get_mob_name(mob_id, lang)),
                callback_data=f"fight_{mob_id}"
            )])
        text += "\n"

    # ── Ресурсы ──
    if location['gather']:
        text += t('location.gather_title', lang) + " "
        text += ", ".join(get_item_name(g[0], lang) for g in location['gather']) + "\n"
        keyboard.append([InlineKeyboardButton(
            t('location.gather_btn', lang), callback_data="gather"
        )])
        text += "\n"

    # ── Сервисы ──
    service_buttons = []
    for service in location.get('services', []):
        if service == 'shop':
            service_buttons.append(InlineKeyboardButton(
                t('location.shop_btn', lang), callback_data="shop"
            ))
        elif service == 'inn':
            service_buttons.append(InlineKeyboardButton(
                t('location.inn_btn', lang), callback_data="inn"
            ))
        elif service == 'quest_board':
            service_buttons.append(InlineKeyboardButton(
                t('location.quests_btn', lang), callback_data="quests"
            ))
    if service_buttons:
        keyboard.append(service_buttons)

    # ── Переходы в другие локации ──
    connected = get_connected_locations(location['id'])
    if connected:
        text += t('location.travel_title', lang) + '\n'
        nav_buttons = []
        for conn_loc in connected:
            req_level = conn_loc['level_min']
            can_go    = player['level'] >= req_level or conn_loc['safe']
            if can_go:
                label = t('location.go_to_btn', lang, name=get_location_name(conn_loc['id'], lang))
                cb    = f"goto_{conn_loc['id']}"
            else:
                label = t('location.locked_btn', lang, name=get_location_name(conn_loc['id'], lang), req=req_level)
                cb    = f"locked_{conn_loc['id']}"
            nav_buttons.append(InlineKeyboardButton(label, callback_data=cb))
        keyboard.append(nav_buttons)

    # ── Статус игрока ──
    text += f"\n❤️ {player['hp']}/{player['max_hp']}  " \
            f"🔵 {player['mana']}/{player['max_mana']}  " \
            f"💰 {player['gold']}"

    return text, InlineKeyboardMarkup(keyboard)


# ────────────────────────────────────────
# КОМАНДА /location
# ────────────────────────────────────────

async def location_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p    = get_player(user.id)
    lang = p['lang'] if p else 'ru'
    if p and p['in_battle']:
        await update.message.reply_text(t('location.in_battle_block', lang))
        return

    if not p:
        await update.message.reply_text(t('common.no_character', lang))
        return

    if is_in_battle(user.id):
        await update.message.reply_text(t('location.in_battle', lang))
        return

    location = get_location(p['location_id'])
    if not location:
        await update.message.reply_text(t('location.not_found', lang))
        return

    text, keyboard = build_location_message(dict(p), location)
    msg = await update.message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')


# ────────────────────────────────────────
# ПЕРЕХОД МЕЖДУ ЛОКАЦИЯМИ
# ────────────────────────────────────────

async def handle_location_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data

    if data == 'noop':
        await query.answer()
        return

    user = query.from_user
    p    = get_player(user.id)
    lang = p['lang'] if p else 'ru'
    
    if p and p['in_battle']:
        await query.answer(t('location.in_battle_block', lang), show_alert=True)
        return

    if data == 'shop':
        location = get_location(p['location_id'])
        if not location:
            await query.answer(t('location.not_found', lang), show_alert=True)
            return
        if 'shop' not in location.get('services', []):
            await query.answer(t('location.shop_not_available', lang), show_alert=True)
            return

        text, keyboard = build_shop_message(dict(p), location)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data == 'shop_back':
        location = get_location(p['location_id'])
        if not location:
            await query.answer(t('location.not_found', lang), show_alert=True)
            return
        if 'shop' not in location.get('services', []):
            await query.answer(t('location.shop_not_available', lang), show_alert=True)
            return

        text, keyboard = build_location_message(dict(p), location)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('shop_buy_'):
        item_id = data.replace('shop_buy_', '', 1)
        location = get_location(p['location_id'])
        if not location:
            await query.answer(t('location.not_found', lang), show_alert=True)
            return
        if 'shop' not in location.get('services', []):
            await query.answer(t('location.shop_not_available', lang), show_alert=True)
            return

        result = try_buy_curated_shop_item(
            telegram_id=user.id,
            location_id=location['id'],
            player_level=p['level'],
            item_id=item_id,
        )
        if not result['ok']:
            if result['reason'] == 'level_required':
                await query.answer(t('location.shop_level_required', lang, level=result['required_level']), show_alert=True)
            elif result['reason'] == 'not_enough_gold':
                await query.answer(t('location.shop_no_gold', lang, price=result['price']), show_alert=True)
            else:
                await query.answer(t('location.shop_not_available', lang), show_alert=True)
            return

        player_after = dict(get_player(user.id))
        text, keyboard = build_shop_message(player_after, location)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer(t('location.shop_buy_ok', lang, name=get_item_name(item_id, lang), price=result['price']))
        return

    if data.startswith('goto_') and is_in_battle(user.id):
        await query.answer(t('location.in_battle_move', lang), show_alert=True)
        return

    if data.startswith('goto_'):
        new_loc_id = data.replace('goto_', '')
        new_loc    = get_location(new_loc_id)

        if not new_loc:
            await query.answer(t('location.not_found', lang), show_alert=True)
            return

        if not new_loc['safe'] and p['level'] < new_loc['level_min']:
            await query.answer(
                t('location.level_required', lang, level=new_loc['level_min']),
                show_alert=True
            )
            return

        await query.answer()

        # Сообщение о переходе
        await query.edit_message_text(
            t('location.traveling', lang,
                name=get_location_name(new_loc_id, lang),
                seconds=15,
                description=get_location_desc(new_loc_id, lang).lower()),
            parse_mode='HTML'
        )

        await asyncio.sleep(15)

        conn = get_connection()
        conn.execute(
            'UPDATE players SET location_id=? WHERE telegram_id=?',
            (new_loc_id, user.id)
        )
        conn.commit()
        conn.close()

        p = dict(get_player(user.id))
        text, keyboard = build_location_message(p, new_loc)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')

        if not new_loc['safe']:
            context.application.create_task(
                schedule_mob_aggro(context, user.id, new_loc, query.message.message_id)
            )


# ────────────────────────────────────────
# АГРЕССИЯ МОБОВ (таймер)
# ────────────────────────────────────────

async def schedule_mob_aggro(context, telegram_id: int, location: dict, message_id: int):
    aggressive_mobs = [
        get_mob(mid) for mid in location['mobs']
        if get_mob(mid) and get_mob(mid)['aggressive']
    ]
    tasks = [
        aggro_attack(context, telegram_id, mob, location['id'], random.randint(5, 60))
        for mob in aggressive_mobs
    ]
    await asyncio.gather(*tasks)


async def aggro_attack(context, telegram_id: int, mob: dict, location_id: str, delay: int):
    await asyncio.sleep(delay)

    p = get_player(telegram_id)
    if not p:
        return
    if p['location_id'] != location_id:
        return
    if p['in_battle']:
        return
    if p['level'] > mob['level'] + 1:
        return

    lang = get_player_lang(telegram_id)

    conn = get_connection()
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=?', (telegram_id,))
    conn.commit()
    conn.close()

    try:
        msg = await context.bot.send_message(
            chat_id=telegram_id,
            text=t('location.aggro_alert', lang,
                   mob_name=mob['name'],
                   level=mob['level'],
                   hp=mob['hp']),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    t('location.aggro_fight_btn', lang),
                    callback_data=f"fight_{mob['id']}"
                ),
                InlineKeyboardButton(
                    t('location.aggro_flee_btn', lang),
                    callback_data=f"flee_{mob['id']}"
                ),
            ]])
        )
        context.application.user_data.setdefault(telegram_id, {})['aggro_message_id'] = msg.message_id
    except Exception:
        pass


# ────────────────────────────────────────
# КНОПКИ БОЕВОГО ВЫЗОВА (fight_ / flee_)
# ────────────────────────────────────────

async def handle_combat_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    user  = query.from_user
    p     = get_player(user.id)
    lang  = p['lang'] if p else 'ru'

    if data.startswith('fight_first_'):
        mob_id = data.replace('fight_first_', '')
        from handlers.battle import start_battle
        await start_battle(update, context, mob_id, mob_first=True)

    elif data.startswith('fight_'):
        mob_id = data.replace('fight_', '')
        from handlers.battle import start_battle
        await start_battle(update, context, mob_id, mob_first=False)

    elif data.startswith('flee_'):
        mob_id = data.replace('flee_', '')
        mob    = get_mob(mob_id)

        if random.randint(1, 100) <= 20:
            conn = get_connection()
            conn.execute('UPDATE players SET in_battle=0 WHERE telegram_id=?', (user.id,))
            conn.commit()
            conn.close()
            try:
                await query.edit_message_text(
                    t('battle.flee_success', lang, mob_name=mob['name']),
                    parse_mode='HTML'
                )
            except BadRequest:
                pass
        else:
            try:
                await query.edit_message_text(
                    t('location.aggro_flee_fail', lang, mob_name=mob['name'],
                      level=mob['level'], hp=mob['hp']),
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            t('location.aggro_fight_first_btn', lang),
                            callback_data=f"fight_first_{mob['id']}"
                        ),
                    ]])
                )
            except BadRequest:
                pass

    await query.answer()

print('✅ handlers/location.py создан!')
