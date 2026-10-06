"""Persisted Telegram menu installation and compact surface delivery."""

from html import escape
import time

from database import get_connection
from game.contextual_keyboard import build_contextual_main_keyboard
from game.i18n import get_location_name,t

MENU_VERSION = 1


def _row(player_id):
    conn = get_connection()
    try:
        row = conn.execute('SELECT * FROM player_pxe1_ui WHERE player_id=?',(player_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def needs_menu(player_id,lang):
    row = _row(player_id)
    return not row or row['menu_version'] != MENU_VERSION or row['menu_lang'] != lang


def mark_menu_installed(player_id,lang):
    conn = get_connection()
    try:
        conn.execute('''INSERT INTO player_pxe1_ui(player_id,schema_version,menu_version,menu_lang,updated_ms)
            VALUES (?,1,?,?,?) ON CONFLICT(player_id) DO UPDATE SET
            menu_version=excluded.menu_version,menu_lang=excluded.menu_lang,updated_ms=excluded.updated_ms''',
            (player_id,MENU_VERSION,lang,int(time.time()*1000)))
        conn.commit()
    finally:
        conn.close()


async def install_menu_on_message(message,player):
    lang = player.get('lang','ru')
    if not needs_menu(player['telegram_id'],lang):
        return False
    text = t('pxe1.menu_home',lang,name=escape(player['name']),location=escape(get_location_name(player['location_id'],lang)))
    await message.reply_text(text,parse_mode='HTML',reply_markup=build_contextual_main_keyboard(lang=lang))
    mark_menu_installed(player['telegram_id'],lang)  # Failed transport leaves a retry.
    return True


def validate_surface(text,keyboard,*,list_view=False,long_detail=False):
    rows = list(getattr(keyboard,'inline_keyboard',()) or ())
    max_text = 3600 if long_detail else 900
    if len(text.encode('utf-16-le'))//2 > max_text or (not long_detail and len(text.splitlines())>10):
        raise ValueError('surface_text_budget')
    if len(rows)>(10 if list_view else 6) or sum(len(row) for row in rows)>(12 if list_view else 8):
        raise ValueError('surface_button_budget')
    for row in rows:
        if len(row)>2:
            raise ValueError('surface_row_budget')
        for button in row:
            if button.callback_data and len(button.callback_data.encode('utf-8'))>64:
                raise ValueError('surface_callback_budget')


async def present_surface(bot,player_id,text,keyboard,*,kind,ref,revision,chat_id=None):
    """Edit a current activity card. Persist successful delivery coordinates only."""
    validate_surface(text,keyboard)
    prior = _row(player_id) or {}
    same = prior.get('surface_kind')==kind and prior.get('surface_ref')==ref
    if same and prior.get('surface_revision')==revision and prior.get('message_id'):
        return False
    chat_id = chat_id or prior.get('chat_id') or player_id
    message = None
    if same and prior.get('message_id'):
        try:
            message = await bot.edit_message_text(text,chat_id=chat_id,message_id=prior['message_id'],reply_markup=keyboard,parse_mode='HTML')
        except Exception as exc:
            from telegram.error import BadRequest
            if isinstance(exc,BadRequest) and 'not modified' in str(exc).lower():
                message = prior['message_id']
            else:
                raise
    else:
        message = await bot.send_message(chat_id,text,reply_markup=keyboard,parse_mode='HTML')
    message_id = message if isinstance(message,int) else message.message_id
    conn = get_connection()
    try:
        conn.execute('''INSERT INTO player_pxe1_ui(player_id,schema_version,surface_kind,surface_ref,
            chat_id,message_id,surface_revision,updated_ms) VALUES (?,1,?,?,?,?,?,?)
            ON CONFLICT(player_id) DO UPDATE SET surface_kind=excluded.surface_kind,
            surface_ref=excluded.surface_ref,chat_id=excluded.chat_id,message_id=excluded.message_id,
            surface_revision=excluded.surface_revision,updated_ms=excluded.updated_ms''',
            (player_id,kind,ref,chat_id,message_id,revision,int(time.time()*1000)))
        conn.commit()
    finally:
        conn.close()
    return True
