# ============================================================
# settings.py — настройки игрока
# ============================================================

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_player
from game.i18n import t, get_player_lang, set_player_lang, SUPPORTED_LANGS

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p    = get_player(user.id)

    if not p:
        await update.message.reply_text(t('common.no_character','ru'))
        return

    lang = get_player_lang(user.id)
    text, keyboard = build_settings(user.id, lang)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')

def build_settings(telegram_id: int, lang: str) -> tuple:
    text = t('settings.title', lang) + '\n\n'
    text += f"{t('settings.current_lang', lang, lang_name=SUPPORTED_LANGS[lang])}\n"

    keyboard = []

    # Кнопки языков
    lang_row = []
    for code, name in SUPPORTED_LANGS.items():
        label = f"[{name}]" if code == lang else name
        lang_row.append(InlineKeyboardButton(
            label, callback_data=f"settings_lang_{code}"
        ))
    keyboard.extend([lang_row[i:i+2] for i in range(0,len(lang_row),2)])

    return text, InlineKeyboardMarkup(keyboard)

async def handle_settings_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    user  = query.from_user

    if data.startswith('settings_lang_'):
        new_lang = data.replace('settings_lang_', '')

        if new_lang not in SUPPORTED_LANGS:
            await query.answer('❌ Неизвестный язык', show_alert=True)
            return

        await query.answer()
        from handlers.profile import main_keyboard
        set_player_lang(user.id, new_lang)

        await context.bot.send_message(
            chat_id=user.id,
            text=t('settings.language_set', new_lang),
            reply_markup=main_keyboard(new_lang)
        )
        from game.player_ui import mark_menu_installed
        mark_menu_installed(user.id,new_lang)

        text, keyboard = build_settings(user.id, new_lang)
        try:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        except Exception:
            pass
        return

print('✅ handlers/settings.py создан!')
