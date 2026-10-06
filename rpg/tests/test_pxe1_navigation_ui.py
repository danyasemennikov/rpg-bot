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
