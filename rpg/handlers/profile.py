# ============================================================
# profile.py — профиль персонажа и команда /help
# ============================================================

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from database import get_player, get_connection
from game.balance import exp_to_next_level, calc_max_hp, calc_max_mana, calc_carry_weight
from game.i18n import t, get_player_lang, get_item_name
from game.items_data import get_item, get_item_metadata
from game.equipment_stats import get_player_effective_stats

STAT_RESET_COST = 100  # стоимость сброса статов в золоте

EQUIP_SLOT_LABELS = {
    'ru': {'weapon': '⚔️ Оружие', 'offhand': '🛡️ Оффхенд', 'chest': '🧥 Тело'},
    'en': {'weapon': '⚔️ Weapon', 'offhand': '🛡️ Offhand', 'chest': '🧥 Chest'},
    'es': {'weapon': '⚔️ Arma', 'offhand': '🛡️ Mano secundaria', 'chest': '🧥 Pecho'},
}


def _format_equipped_identity(item_id: str, lang: str) -> str:
    metadata = get_item_metadata(item_id)
    parts = []
    if metadata.get('armor_class'):
        key = f"profile.identity.armor_class.{metadata['armor_class']}"
        label = t(key, lang)
        parts.append(label if label != f'[{key}]' else metadata['armor_class'].replace('_', ' '))
    if metadata.get('offhand_profile') and metadata['offhand_profile'] != 'none':
        key = f"profile.identity.offhand_profile.{metadata['offhand_profile']}"
        label = t(key, lang)
        parts.append(label if label != f'[{key}]' else metadata['offhand_profile'].replace('_', ' '))
    if metadata.get('slot_identity') == 'weapon':
        profile = metadata.get('weapon_profile', 'unarmed')
        key = f'profile.identity.weapon_profile.{profile}'
        label = t(key, lang)
        parts.append(label if label != f'[{key}]' else profile.replace('_', ' '))
    return f" ({', '.join(parts)})" if parts else ""


def _build_equipment_summary(telegram_id: int, lang: str) -> str:
    conn = get_connection()
    equipped = conn.execute(
        'SELECT weapon, offhand, chest FROM equipment WHERE telegram_id=?',
        (telegram_id,),
    ).fetchone()
    if not equipped:
        conn.close()
        return ''

    inventory_ids = [equipped['weapon'], equipped['offhand'], equipped['chest']]
    inventory_ids = [value for value in inventory_ids if value is not None]
    if not inventory_ids:
        conn.close()
        return ''

    placeholders = ','.join('?' * len(inventory_ids))
    inv_rows = conn.execute(
        f'SELECT id, item_id FROM inventory WHERE telegram_id=? AND id IN ({placeholders})',
        (telegram_id, *inventory_ids),
    ).fetchall()
    conn.close()

    by_inv_id = {row['id']: row['item_id'] for row in inv_rows}
    labels = EQUIP_SLOT_LABELS.get(lang, EQUIP_SLOT_LABELS['ru'])
    lines = []
    for slot in ('weapon', 'offhand', 'chest'):
        inv_id = equipped[slot]
        item_id = by_inv_id.get(inv_id)
        if not item_id:
            continue
        item = get_item(item_id)
        if not item:
            continue
        lines.append(
            f"{labels[slot]}: {get_item_name(item_id, lang)}{_format_equipped_identity(item_id, lang)}"
        )
    if not lines:
        return ''
    return "\n\n" + "\n".join(lines)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_player_lang(update.effective_user.id)
    await update.message.reply_text(
        t('help.title', lang) + '\n\n' + t('help.commands', lang),
        parse_mode='HTML'
    )

def main_keyboard(lang: str = 'ru'):
    from game.i18n import t
    return ReplyKeyboardMarkup([
        [t('keyboard.location', lang), t('keyboard.profile', lang)],
        [t('keyboard.inventory', lang), t('keyboard.skills', lang)],
        [t('keyboard.quests', lang), t('keyboard.stats', lang)],
        [t('keyboard.settings', lang), t('keyboard.help', lang)],
    ], resize_keyboard=True)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p    = get_player(user.id)
    lang = get_player_lang(user.id)

    if not p:
        await update.message.reply_text(t('common.no_character', lang))
        return

    exp_needed = exp_to_next_level(p['level'])
    effective_stats = get_player_effective_stats(user.id, p)
    effective_max_hp = effective_stats['max_hp']
    effective_max_mana = effective_stats['max_mana']
    exp_pct    = int((p['exp'] / exp_needed) * 10)
    exp_bar    = '█' * exp_pct + '░' * (10 - exp_pct)

    hp_pct  = int((p['hp'] / max(1, effective_max_hp)) * 10)
    hp_bar  = '█' * hp_pct + '░' * (10 - hp_pct)

    mp_pct  = int((p['mana'] / max(1, effective_max_mana)) * 10)
    mp_bar  = '█' * mp_pct + '░' * (10 - mp_pct)

    text = (
        f"{t('profile.title', lang, name=p['name'])}\n"
        f"{t('profile.level', lang, level=p['level'])}  |  📍 {p['location_id']}\n\n"
        f"❤️ HP:   {hp_bar} {p['hp']}/{effective_max_hp}\n"
        f"🔵 {t('common.mana', lang)}: {mp_bar} {p['mana']}/{effective_max_mana}\n"
        f"✨ {t('common.exp', lang)}: {exp_bar} {p['exp']}/{exp_needed}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{t('profile.strength',  lang, val=p['strength'])}\n"
        f"{t('profile.agility',   lang, val=p['agility'])}\n"
        f"{t('profile.intuition', lang, val=p['intuition'])}\n"
        f"{t('profile.vitality',  lang, val=p['vitality'])}\n"
        f"{t('profile.wisdom',    lang, val=p['wisdom'])}\n"
        f"{t('profile.luck',      lang, val=p['luck'])}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 {t('common.gold', lang)}: <b>{p['gold']}</b>  |  "
        f"🎒 {t('common.hp', lang)}: <b>{p['carry_weight']}</b>\n"
    )
    if p['stat_points'] > 0:
        text += f"\n🔸 {t('profile.stat_points', lang, val=p['stat_points'])} — /stats"
    text += _build_equipment_summary(user.id, lang)

    await update.message.reply_text(text, parse_mode='HTML')

# ─── Вспомогательные функции для меню статов ────────────────

def _build_stats_text(stats: dict, points: int, lang: str = 'ru') -> str:
    return (
        f"<b>{t('profile.stats_title', lang).replace('<b>', '').replace('</b>', '')}</b>\n\n"
        f"{t('profile.stat_points', lang, val=points)}\n\n"
        f"{t('profile.strength',  lang, val=stats['strength'])}\n"
        f"{t('profile.agility',   lang, val=stats['agility'])}\n"
        f"{t('profile.intuition', lang, val=stats['intuition'])}\n"
        f"{t('profile.vitality',  lang, val=stats['vitality'])}\n"
        f"{t('profile.wisdom',    lang, val=stats['wisdom'])}\n"
        f"{t('profile.luck',      lang, val=stats['luck'])}\n"
    )

def _build_stats_keyboard(stats: dict, points: int, lang: str = 'ru', has_gold_for_reset: bool = True) -> InlineKeyboardMarkup:
    STATS = [
        ('strength',  t('profile.strength',  lang, val='').split(':')[0].strip()),
        ('agility',   t('profile.agility',   lang, val='').split(':')[0].strip()),
        ('intuition', t('profile.intuition', lang, val='').split(':')[0].strip()),
        ('vitality',  t('profile.vitality',  lang, val='').split(':')[0].strip()),
        ('wisdom',    t('profile.wisdom',    lang, val='').split(':')[0].strip()),
        ('luck',      t('profile.luck',      lang, val='').split(':')[0].strip()),
    ]
    keyboard = []

    # Кнопки распределения — только если есть свободные очки
    if points > 0:
        for key, label in STATS:
            keyboard.append([
                InlineKeyboardButton('➖', callback_data=f'sp_minus_{key}'),
                InlineKeyboardButton(f'{label}: {stats[key]}', callback_data='sp_noop'),
                InlineKeyboardButton('➕', callback_data=f'sp_plus_{key}'),
            ])
        keyboard.append([InlineKeyboardButton(
            t('common.confirm', lang), callback_data='sp_confirm'
        )])
    else:
        for key, label in STATS:
            keyboard.append([
                InlineKeyboardButton(f'{label}: {stats[key]}', callback_data='sp_noop'),
            ])
        keyboard.append([InlineKeyboardButton(
            t('common.confirm', lang), callback_data='sp_confirm'
        )])

    # Кнопка сброса — всегда внизу
    keyboard.append([InlineKeyboardButton(
        t('profile.reset_btn', lang, cost=STAT_RESET_COST),
        callback_data='sp_reset_ask'
    )])

    return InlineKeyboardMarkup(keyboard)

def _calc_spent_points(p) -> int:
    """Считает сколько очков уже вложено в статы (сверх базовых 1)."""
    return (
        (p['strength']  - 1) +
        (p['agility']   - 1) +
        (p['intuition'] - 1) +
        (p['vitality']  - 1) +
        (p['wisdom']    - 1) +
        (p['luck']      - 1)
    )

# ─── Команда /stats и кнопка 📊 ─────────────────────────────

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открывает меню статов. Работает всегда, независимо от наличия очков."""
    user = update.effective_user
    p    = get_player(user.id)
    lang = get_player_lang(user.id)

    if not p:
        await update.message.reply_text(t('common.no_character', lang))
        return

    # Инициализируем состояние редактирования из актуальных данных БД
    context.user_data['stats_edit'] = {
        'strength':  p['strength'],
        'agility':   p['agility'],
        'intuition': p['intuition'],
        'vitality':  p['vitality'],
        'wisdom':    p['wisdom'],
        'luck':      p['luck'],
    }
    context.user_data['stats_points'] = p['stat_points']
    context.user_data['stats_lang']   = lang

    has_gold = p['gold'] >= STAT_RESET_COST

    await update.message.reply_text(
        _build_stats_text(context.user_data['stats_edit'], p['stat_points'], lang),
        reply_markup=_build_stats_keyboard(
            context.user_data['stats_edit'], p['stat_points'], lang, has_gold
        ),
        parse_mode='HTML'
    )

# ─── Обработчик inline-кнопок статов ────────────────────────

async def handle_stats_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    data   = query.data
    user   = query.from_user
    lang   = context.user_data.get('stats_lang', get_player_lang(user.id))

    stats  = context.user_data.get('stats_edit')
    points = context.user_data.get('stats_points', 0)

    # ── Ничего не делать ────────────────────────────────────
    if data == 'sp_noop':
        await query.answer()
        return

    # ── Если состояние потеряно — восстанавливаем из БД ─────
    if not stats:
        p = get_player(user.id)
        if not p:
            await query.answer(t('common.error', lang), show_alert=True)
            return
        context.user_data['stats_edit'] = {
            'strength':  p['strength'],
            'agility':   p['agility'],
            'intuition': p['intuition'],
            'vitality':  p['vitality'],
            'wisdom':    p['wisdom'],
            'luck':      p['luck'],
        }
        context.user_data['stats_points'] = p['stat_points']
        stats  = context.user_data['stats_edit']
        points = p['stat_points']

    # ── +1 к стату ──────────────────────────────────────────
    if data.startswith('sp_plus_'):
        if points <= 0:
            await query.answer("❌ Нет свободных очков!", show_alert=True)
            return
        key = data.replace('sp_plus_', '')
        stats[key] += 1
        context.user_data['stats_points'] -= 1
        points -= 1

    # ── -1 к стату ──────────────────────────────────────────
    elif data.startswith('sp_minus_'):
        key    = data.replace('sp_minus_', '')
        p_orig = get_player(user.id)
        if stats[key] <= p_orig[key]:
            await query.answer("❌ Нельзя опустить ниже текущего!", show_alert=True)
            return
        stats[key] -= 1
        context.user_data['stats_points'] += 1
        points += 1

    # ── Подтверждение распределения ─────────────────────────
    elif data == 'sp_confirm':

        conn = get_connection()
        conn.execute('''
            UPDATE players SET
                strength=?, agility=?, intuition=?,
                vitality=?, wisdom=?, luck=?,
                max_hp=?, max_mana=?, carry_weight=?,
                stat_points=?
            WHERE telegram_id=?
        ''', (
            stats['strength'], stats['agility'], stats['intuition'],
            stats['vitality'], stats['wisdom'], stats['luck'],
            calc_max_hp(stats['vitality']),
            calc_max_mana(stats['wisdom']),
            calc_carry_weight(stats['strength']),
            context.user_data['stats_points'],
            user.id
        ))
        conn.commit()
        conn.close()

        context.user_data.pop('stats_edit', None)
        context.user_data.pop('stats_points', None)
        context.user_data.pop('stats_lang', None)

        await query.edit_message_text(
            f"✅ <b>Статы сохранены!</b>\n\n"
            f"{t('profile.strength',  lang, val=stats['strength'])}\n"
            f"{t('profile.agility',   lang, val=stats['agility'])}\n"
            f"{t('profile.intuition', lang, val=stats['intuition'])}\n"
            f"{t('profile.vitality',  lang, val=stats['vitality'])}\n"
            f"{t('profile.wisdom',    lang, val=stats['wisdom'])}\n"
            f"{t('profile.luck',      lang, val=stats['luck'])}",
            parse_mode='HTML'
        )
        await query.answer("✅ Готово!")
        return

    # ── Запрос подтверждения сброса ──────────────────────────
    elif data == 'sp_reset_ask':
        p_fresh = get_player(user.id)
        if p_fresh['gold'] < STAT_RESET_COST:
            await query.answer(
                t('profile.reset_no_gold', lang, cost=STAT_RESET_COST),
                show_alert=True
            )
            return

        spent      = _calc_spent_points(p_fresh)
        total_back = spent + p_fresh['stat_points']

        confirm_text = t('profile.reset_ask', lang, cost=STAT_RESET_COST, points=total_back)

        keyboard = InlineKeyboardMarkup([
            [
            InlineKeyboardButton(t('profile.reset_confirm_btn', lang), callback_data='sp_reset_confirm'),
                InlineKeyboardButton(t('profile.reset_cancel_btn',  lang), callback_data='sp_reset_cancel'),
            ]
        ])
        await query.edit_message_text(confirm_text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    # ── Выполнить сброс ──────────────────────────────────────
    elif data == 'sp_reset_confirm':
        p_fresh = get_player(user.id)
        if p_fresh['gold'] < STAT_RESET_COST:
            await query.answer(
                t('profile.reset_no_gold', lang, cost=STAT_RESET_COST),
                show_alert=True
            )
            return

        spent      = _calc_spent_points(p_fresh)
        total_back = spent + p_fresh['stat_points']
        base_stat  = 1

        conn = get_connection()
        conn.execute('''
            UPDATE players SET
                strength=?, agility=?, intuition=?,
                vitality=?, wisdom=?, luck=?,
                max_hp=?, max_mana=?, carry_weight=?,
                stat_points=?,
                gold=gold-?
            WHERE telegram_id=?
        ''', (
            base_stat, base_stat, base_stat,
            base_stat, base_stat, base_stat,
            calc_max_hp(base_stat),
            calc_max_mana(base_stat),
            calc_carry_weight(base_stat),
            total_back,
            STAT_RESET_COST,
            user.id
        ))
        conn.commit()
        conn.close()

        new_stats = {s: base_stat for s in ('strength','agility','intuition','vitality','wisdom','luck')}
        context.user_data['stats_edit']   = new_stats
        context.user_data['stats_points'] = total_back

        p_after   = get_player(user.id)
        has_gold  = p_after['gold'] >= STAT_RESET_COST

        await query.edit_message_text(
            t('profile.reset_ok', lang, cost=STAT_RESET_COST, points=total_back)
            + _build_stats_text(new_stats, total_back, lang),
            reply_markup=_build_stats_keyboard(new_stats, total_back, lang, has_gold),
            parse_mode='HTML'
        )
        await query.answer(t('profile.reset_success', lang))
        return

    # ── Отмена сброса ────────────────────────────────────────
    elif data == 'sp_reset_cancel':
        p_fresh  = get_player(user.id)
        has_gold = p_fresh['gold'] >= STAT_RESET_COST
        await query.edit_message_text(
            _build_stats_text(stats, points, lang),
            reply_markup=_build_stats_keyboard(stats, points, lang, has_gold),
            parse_mode='HTML'
        )
        await query.answer("Отменено")
        return

    # ── Обновить сообщение после +/- ────────────────────────
    p_fresh  = get_player(user.id)
    has_gold = p_fresh['gold'] >= STAT_RESET_COST
    await query.edit_message_text(
        _build_stats_text(stats, context.user_data['stats_points'], lang),
        reply_markup=_build_stats_keyboard(stats, context.user_data['stats_points'], lang, has_gold),
        parse_mode='HTML'
    )
    await query.answer()


async def unstuck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_player_lang(user.id)
    conn = get_connection()
    conn.execute(
        'UPDATE players SET in_battle=0, location_id="village" WHERE telegram_id=?',
        (user.id,)
    )
    conn.commit()
    conn.close()
    context.user_data.pop('battle', None)
    context.user_data.pop('battle_mob', None)
    aggro_msg_id = context.user_data.pop('aggro_message_id', None)
    if aggro_msg_id:
        try:
            await context.bot.delete_message(chat_id=user.id, message_id=aggro_msg_id)
        except Exception:
            pass
    await update.message.reply_text(
        "🔧 " + ("Готово! Перенесён в деревню." if lang == 'ru' else "Done! Moved to village."),
        reply_markup=main_keyboard()
    )

print('✅ handlers/profile.py обновлён!')
