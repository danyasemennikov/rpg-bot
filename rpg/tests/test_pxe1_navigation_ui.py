import asyncio
from string import Formatter
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot import register_pxe1_commands
from database import get_connection,get_player
from game.contextual_keyboard import build_contextual_main_keyboard
from game.i18n import t
from game.locations import get_location_neighbors
from game.player_experience_schema import grant_player_pxe1_starters
from game.player_ui import install_menu_on_message,needs_menu,validate_surface
from handlers.activities import build_activities,tool_card,tool_list,travel_preview_card
from locales.pxe1 import PXE1_STRINGS


def test_integrated_frozen_families_have_real_locales_without_fallback():
    from game.i18n import validate_pxe1_surface_locales
    from locales.pxe1_surface_keys import COVERED_FAMILIES
    assert len(COVERED_FAMILIES)==17
    assert validate_pxe1_surface_locales()
    for lang in ('ru','en','es'):
        for suffix,legacy in (('location','keyboard.location'),('map','keyboard.map'),
                ('journal','chapter.journal'),('inventory','keyboard.inventory'),
                ('character','keyboard.profile'),('activities','keyboard.activities')):
            assert t('pxe1.menu.'+suffix,lang)==t(legacy,lang)
        assert t('pxe1.command.activities',lang)==t('pxe1.commands.activities',lang)


@pytest.mark.parametrize('corruption',['missing','placeholders','not_text'])
def test_integrated_frozen_family_validation_detects_missing_or_mismatched_translation(corruption):
    from copy import deepcopy
    from game.i18n import _load_lang,validate_pxe1_surface_locales
    locales={lang:deepcopy(_load_lang(lang)) for lang in ('en','ru','es')}
    character=locales['es']['pxe1']['character']
    if corruption=='missing': del character['rank']
    elif corruption=='placeholders': character['rank']='Rango {other}/3'
    else: character['rank']=3
    with pytest.raises(RuntimeError,match='PXE1'):
        validate_pxe1_surface_locales(locales)


@pytest.mark.parametrize('family',['location','map','travel','encounter','gather','quest','journal','chapter'])
def test_remaining_families_require_each_translation(family):
    from copy import deepcopy
    from game.i18n import _load_lang,validate_pxe1_surface_locales
    from locales.pxe1_surface_keys import COVERED_FAMILIES
    locales={lang:deepcopy(_load_lang(lang)) for lang in ('en','ru','es')}
    del locales['es']['pxe1'][family][COVERED_FAMILIES[family].split()[0]]
    with pytest.raises(RuntimeError,match='PXE1'):
        validate_pxe1_surface_locales(locales)


@pytest.mark.parametrize('number,ru_word',[(0,'очков'),(1,'очко'),(2,'очка'),(5,'очков'),(21,'очко')])
def test_numeric_copy_uses_language_rules(number,ru_word):
    assert t('pxe1.character.free_points','ru',count=number)==f'{number} свободн'+('ое ' if ru_word=='очко' else 'ых ')+ru_word
    assert t('pxe1.character.free_points','en',count=number)==f'{number} free '+('point' if number==1 else 'points')
    assert t('pxe1.character.free_points','es',count=number)==f'{number} '+('punto libre' if number==1 else 'puntos libres')
    for lang in ('ru','en','es'):
        assert '{' not in t('pxe1.character.skill_cost',lang,mana=5,cooldown=number)
        assert isinstance(t('pxe1.gather.action_label',lang,profession='🌿'),str)


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_six_fixed_entries_no_location_context(lang):
    expected = [[t('keyboard.location',lang),t('keyboard.map',lang)],
        [t('chapter.journal',lang),t('keyboard.inventory',lang)],
        [t('keyboard.profile',lang),t('keyboard.activities',lang)]]
    for location in ('capital_city','westwild_n1','mirefen_n4'):
        keyboard = build_contextual_main_keyboard({'location_id':location},lang)
        assert [[b.text for b in row] for row in keyboard.keyboard]==expected
        assert keyboard.is_persistent


def test_menu_only_after_success_and_once_per_language():
    player = dict(get_player(1))
    message = SimpleNamespace(reply_text=AsyncMock(side_effect=RuntimeError('transport')))
    with pytest.raises(RuntimeError):
        asyncio.run(install_menu_on_message(message,player))
    assert needs_menu(1,player['lang'])
    message.reply_text = AsyncMock()
    assert asyncio.run(install_menu_on_message(message,player))
    assert not asyncio.run(install_menu_on_message(message,player))
    assert message.reply_text.await_count==1
    assert t('keyboard.sync_updated',player['lang']) not in message.reply_text.call_args.args[0]
    player['lang']='es'
    assert asyncio.run(install_menu_on_message(message,player))
    assert message.reply_text.await_count==2


def test_commands_exact_order_localized_and_failures_nonfatal():
    bot = SimpleNamespace(set_my_commands=AsyncMock(side_effect=[RuntimeError('offline'),None,None,None]))
    asyncio.run(register_pxe1_commands(SimpleNamespace(bot=bot)))
    assert bot.set_my_commands.await_count==4
    expected = ['start','location','map','journal','inventory','profile','activities','stats','skills','build','settings','help']
    assert [call.kwargs['language_code'] for call in bot.set_my_commands.call_args_list]==[None,'ru','en','es']
    for call in bot.set_my_commands.call_args_list:
        assert [cmd.command for cmd in call.args[0]]==expected
        assert all(1<=len(cmd.description)<=256 for cmd in call.args[0])


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_current_activity_tool_and_route_surfaces_bounded_and_translated(lang):
    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    grant_player_pxe1_starters(conn,1,now_ms=0,acquired_via='starter')
    conn.execute("UPDATE players SET location_id='hub_westwild',lang=? WHERE telegram_id=1",(lang,))
    conn.execute("UPDATE player_profession_tools SET tier=4,durability=0 WHERE player_id=1 AND profession_key='mining'")
    conn.commit()
    conn.close()
    player = dict(get_player(1))
    destination = get_location_neighbors(player['location_id'])[0]
    for text,keyboard in (build_activities(player),tool_list(player),tool_card(player,'mining'),travel_preview_card(player,destination)):
        validate_surface(text,keyboard)
        assert '[pxe1.' not in text
        assert 'westwild_n1' not in text
        assert all('[pxe1.' not in button.text for row in keyboard.inline_keyboard for button in row)


def test_new_locale_keys_and_placeholder_parity():
    def flatten(d,prefix=''):
        result = {}
        for key,value in d.items():
            if isinstance(value,dict):
                result.update(flatten(value,prefix+key+'.'))
            else:
                result[prefix+key]={field for _,field,_,_ in Formatter().parse(value) if field}
        return result
    expected = flatten(PXE1_STRINGS['en'])
    assert flatten(PXE1_STRINGS['ru'])==expected
    assert flatten(PXE1_STRINGS['es'])==expected


def test_deleted_activity_card_replaced_once_and_other_transport_errors_keep_coordinates():
    from game.player_ui import present_surface
    from telegram.error import BadRequest
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO player_pxe1_ui(player_id,schema_version,surface_kind,surface_ref,chat_id,message_id,surface_revision,updated_ms) VALUES (1,1,'gather','test',1,40,1,0)")
    conn.commit();conn.close()
    bot = SimpleNamespace(edit_message_text=AsyncMock(side_effect=BadRequest('Message to edit not found')),
                          send_message=AsyncMock(return_value=SimpleNamespace(message_id=41)))
    assert asyncio.run(present_surface(bot,1,'Gathering',None,kind='gather',ref='test',revision=1,force_refresh=True))
    assert bot.send_message.await_count==1
    assert not asyncio.run(present_surface(bot,1,'Gathering',None,kind='gather',ref='test',revision=1))
    bot.edit_message_text.side_effect = RuntimeError('offline')
    with pytest.raises(RuntimeError,match='offline'):
        asyncio.run(present_surface(bot,1,'Gathering',None,kind='gather',ref='test',revision=2))
    conn = get_connection()
    assert conn.execute('SELECT message_id,surface_revision FROM player_pxe1_ui WHERE player_id=1').fetchone()[:]==(41,1)
    conn.close()


def test_gather_start_token_replays_terminal_session_without_starting_again():
    from handlers.activities import gathering_preview_card,handle_activity_buttons
    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    grant_player_pxe1_starters(conn,1,now_ms=1000,acquired_via='starter')
    conn.execute("UPDATE players SET location_id='westwild_n1' WHERE telegram_id=1")
    conn.commit();conn.close()
    text,keyboard = gathering_preview_card(dict(get_player(1)),'herbalism')
    validate_surface(text,keyboard)
    start = next(b.callback_data for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith('px:gatherstart:'))
    q = SimpleNamespace(from_user=SimpleNamespace(id=1),data=start,answer=AsyncMock(),edit_message_text=AsyncMock(),
                        message=SimpleNamespace(chat_id=1,message_id=50))
    asyncio.run(handle_activity_buttons(SimpleNamespace(callback_query=q),SimpleNamespace(user_data={})))
    conn = get_connection()
    session = dict(conn.execute('SELECT * FROM player_gathering_sessions WHERE player_id=1').fetchone())
    conn.execute("UPDATE player_gathering_sessions SET status='cancelled',next_due_ms=NULL WHERE session_id=?",(session['session_id'],))
    conn.execute('DELETE FROM player_ui_actions WHERE player_id=1')
    conn.commit();conn.close()
    asyncio.run(handle_activity_buttons(SimpleNamespace(callback_query=q),SimpleNamespace(user_data={})))
    conn = get_connection()
    assert conn.execute('SELECT COUNT(*) FROM player_gathering_sessions WHERE player_id=1').fetchone()[0]==1
    assert conn.execute('SELECT status FROM player_gathering_sessions WHERE session_id=?',(session['session_id'],)).fetchone()[0]=='cancelled'
    conn.close()
