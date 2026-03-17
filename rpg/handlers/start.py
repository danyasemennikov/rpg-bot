# ============================================================
# start.py — регистрация и выбор стартовых статов
# ============================================================

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_player, create_player, player_exists
from game.balance import calc_max_hp, calc_max_mana
from game.i18n import t, get_player_lang, DEFAULT_LANG

STAT_POINTS = 6

def _stats_list(lang: str) -> list:
    return [
        ('strength',  t('profile.strength',  lang, val='').split(':')[0].strip()),
        ('agility',   t('profile.agility',   lang, val='').split(':')[0].strip()),
        ('intuition', t('profile.intuition', lang, val='').split(':')[0].strip()),
        ('vitality',  t('profile.vitality',  lang, val='').split(':')[0].strip()),
        ('wisdom',    t('profile.wisdom',    lang, val='').split(':')[0].strip()),
        ('luck',      t('profile.luck',      lang, val='').split(':')[0].strip()),
    ]

def build_stats_keyboard(stats: dict, points_left: int, lang: str = 'ru') -> InlineKeyboardMarkup:
    keyboard = []
    for key, label in _stats_list(lang):
        val       = stats[key]
        btn_minus = InlineKeyboardButton(
            '➖' if val > 1 else '·',
            callback_data=f'stat_minus_{key}' if val > 1 else 'stat_noop'
        )
        btn_plus  = InlineKeyboardButton(
            '➕' if points_left > 0 else '·',
            callback_data=f'stat_plus_{key}' if points_left > 0 else 'stat_noop'
        )
        btn_label = InlineKeyboardButton(f'{label}: {val}', callback_data='stat_noop')
        keyboard.append([btn_minus, btn_label, btn_plus])

    if points_left == 0:
        keyboard.append([InlineKeyboardButton(
            '✅ ' + ('Начать игру!' if lang == 'ru' else 'Start game!' if lang == 'en' else '¡Comenzar!'),
            callback_data='stat_confirm'
        )])
    else:
        keyboard.append([InlineKeyboardButton(
            f"{'Осталось' if lang == 'ru' else 'Points left' if lang == 'en' else 'Puntos'}: {points_left}",
            callback_data='stat_noop'
        )])

    return InlineKeyboardMarkup(keyboard)

def stats_text(stats: dict, points_left: int, lang: str = 'ru') -> str:
    hp   = calc_max_hp(stats['vitality'])
    mana = calc_max_mana(stats['wisdom'])
    if lang == 'ru':
        return (
            f"⚔️ <b>Распредели стартовые очки</b>\n\n"
            f"Очков осталось: <b>{points_left}</b>\n\n"
            f"❤️ HP: <b>{hp}</b>  |  🔵 Мана: <b>{mana}</b>\n\n"
            f"Нажимай ➕ и ➖ чтобы распределить статы."
        )
    elif lang == 'en':
        return (
            f"⚔️ <b>Distribute starting points</b>\n\n"
            f"Points left: <b>{points_left}</b>\n\n"
            f"❤️ HP: <b>{hp}</b>  |  🔵 Mana: <b>{mana}</b>\n\n"
            f"Press ➕ and ➖ to distribute stats."
        )
    else:
        return (
            f"⚔️ <b>Distribuye los puntos iniciales</b>\n\n"
            f"Puntos restantes: <b>{points_left}</b>\n\n"
            f"❤️ HP: <b>{hp}</b>  |  🔵 Maná: <b>{mana}</b>\n\n"
            f"Presiona ➕ y ➖ para distribuir estadísticas."
        )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_player_lang(user.id)

    if player_exists(user.id):
        player = get_player(user.id)
        from handlers.profile import main_keyboard
        await update.message.reply_text(
            t('start.welcome', lang) if False else (
                f"👋 {'С возвращением' if lang == 'ru' else 'Welcome back' if lang == 'en' else 'Bienvenido de nuevo'}, "
                f"<b>{player['name']}</b>!\n\n"
                f"❤️ HP: {player['hp']}/{player['max_hp']}  "
                f"🔵 {t('common.mana', lang)}: {player['mana']}/{player['max_mana']}\n"
                f"⭐ {t('common.level', lang)}: {player['level']}  |  "
                f"💰 {t('common.gold', lang)}: {player['gold']}\n\n"
                f"{'Используй кнопки внизу!' if lang == 'ru' else 'Use the buttons below!' if lang == 'en' else '¡Usa los botones!'}"
            ),
            parse_mode='HTML',
            reply_markup=main_keyboard()
        )
        return

    context.user_data['registering'] = True
    context.user_data['reg_lang']    = lang
    await update.message.reply_text(
        t('start.welcome', lang),
        parse_mode='HTML'
    )

async def handle_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('registering'):
        return

    name = update.message.text.strip()
    lang = context.user_data.get('reg_lang', DEFAULT_LANG)

    if len(name) < 2:
        await update.message.reply_text(t('start.name_short', lang))
        return
    if len(name) > 20:
        await update.message.reply_text(t('start.name_long', lang))
        return

    context.user_data['reg_name']   = name
    context.user_data['reg_stats']  = {
        'strength': 1, 'agility': 1, 'intuition': 1,
        'vitality': 1, 'wisdom':  1, 'luck':      1
    }
    context.user_data['reg_points'] = STAT_POINTS

    stats  = context.user_data['reg_stats']
    points = context.user_data['reg_points']

    joke = (
        f"⚔️ {'Как-как' if lang == 'ru' else 'Wait what' if lang == 'en' else 'Espera'}, "
        f"<b>{name}</b>{'... серьёзно? Ну ладно' if lang == 'ru' else '... seriously? Okay then' if lang == 'en' else '... ¿en serio? Bueno'}.\n\n"
    )
    await update.message.reply_text(
        joke + stats_text(stats, points, lang),
        reply_markup=build_stats_keyboard(stats, points, lang),
        parse_mode='HTML'
    )

async def handle_stat_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data   = query.data
    lang   = context.user_data.get('reg_lang', DEFAULT_LANG)
    stats  = context.user_data.get('reg_stats')
    points = context.user_data.get('reg_points')
    name   = context.user_data.get('reg_name')

    if data == 'stat_noop':
        return

    if not stats:
        await query.edit_message_text(t('common.error', lang))
        return

    if data.startswith('stat_plus_'):
        key = data.replace('stat_plus_', '')
        if points > 0:
            stats[key] += 1
            context.user_data['reg_points'] -= 1

    elif data.startswith('stat_minus_'):
        key = data.replace('stat_minus_', '')
        if stats[key] > 1:
            stats[key] -= 1
            context.user_data['reg_points'] += 1

    elif data == 'stat_confirm':
        user = query.from_user
        create_player(user.id, user.username or '', name, stats)

        hp   = calc_max_hp(stats['vitality'])
        mana = calc_max_mana(stats['wisdom'])

        context.user_data.clear()

        await query.edit_message_text(
            t('start.created', lang, name=name),
        )

        from handlers.profile import main_keyboard
        await context.bot.send_message(
            chat_id=user.id,
            text=t('start.distribute', lang, name=name),
            reply_markup=main_keyboard()
        )
        return

    points = context.user_data['reg_points']
    joke   = (
        f"⚔️ {'Как-как' if lang == 'ru' else 'Wait what' if lang == 'en' else 'Espera'}, "
        f"<b>{name}</b>{'... серьёзно? Ну ладно' if lang == 'ru' else '... seriously? Okay then' if lang == 'en' else '... ¿en serio? Bueno'}.\n\n"
    )
    await query.edit_message_text(
        joke + stats_text(stats, points, lang),
        reply_markup=build_stats_keyboard(stats, points, lang),
        parse_mode='HTML'
    )

print('✅ handlers/start.py обновлён!')