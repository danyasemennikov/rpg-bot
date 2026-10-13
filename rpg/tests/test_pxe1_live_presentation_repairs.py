"""Regressions for LIVE-01–04, 06, 08, 10–11, 13–14; no live poller."""

import ast
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

import pytest

from database import get_connection,get_player
from game.i18n import t,get_item_description,get_location_name
from game.player_ui import validate_surface


def buttons(keyboard):
    return [b for row in keyboard.inline_keyboard for b in row]


def query(data,player_id=1):
    return SimpleNamespace(data=data,from_user=SimpleNamespace(id=player_id,username='test'),
        message=SimpleNamespace(chat_id=player_id,message_id=42),
        answer=AsyncMock(),edit_message_text=AsyncMock())


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_live01_registration_html_allocation_and_replay(lang):
    from handlers.start import handle_stat_buttons
    q=query('stat_confirm',999)
    context=SimpleNamespace(user_data={'reg_lang':lang,'reg_name':'<Hero & Co>',
        'reg_stats':dict(strength=7,agility=1,intuition=1,vitality=1,wisdom=1,luck=1),
        'reg_points':0},bot=SimpleNamespace(send_message=AsyncMock()))
    asyncio.run(handle_stat_buttons(SimpleNamespace(callback_query=q),context))
    player=dict(get_player(999))
    assert player['strength']==7 and sum(player[k] for k in ('strength','agility','intuition','vitality','wisdom','luck'))==12
    assert player['stat_points']==0 and context.user_data=={}
    created=q.edit_message_text.call_args
    assert created.kwargs['parse_mode']=='HTML' and '&lt;Hero &amp; Co&gt;' in created.args[0]
    welcome=context.bot.send_message.call_args_list[0].kwargs
    assert welcome['text']==t('start.alpha_intro',lang) and welcome['parse_mode']=='HTML'
    assert welcome['reply_markup'] is not None
    conn=get_connection()
    before=[tuple(r) for r in conn.execute('SELECT * FROM player_profession_tools WHERE player_id=999')]
    assert len(before)==5
    asyncio.run(handle_stat_buttons(SimpleNamespace(callback_query=q),context))
    assert dict(get_player(999))==player
    assert before==[tuple(r) for r in conn.execute('SELECT * FROM player_profession_tools WHERE player_id=999')]
    assert context.bot.send_message.await_count==2
    conn.close()


def test_live01_invalid_allocation_does_not_create_character():
    from handlers.start import handle_stat_buttons
    q=query('stat_confirm',999)
    context=SimpleNamespace(user_data={'reg_name':'Hero','reg_stats':dict(strength=1,agility=1,intuition=1,vitality=1,wisdom=1,luck=1),
        'reg_points':6},bot=SimpleNamespace(send_message=AsyncMock()))
    asyncio.run(handle_stat_buttons(SimpleNamespace(callback_query=q),context))
    assert get_player(999) is None
    context.bot.send_message.assert_not_awaited()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_live02_profession_button_is_plain_and_retains_callback(lang):
    from handlers.activities import build_activities
    _,keyboard=build_activities({**dict(get_player(1)),'lang':lang})
    label=next(b.text for b in buttons(keyboard) if b.callback_data=='pe_o:0')
    assert '<' not in label and '>' not in label
    assert label=={'ru':'🛠 Профессии','en':'🛠 Professions','es':'🛠 Profesiones'}[lang]


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_live03_help_matches_registered_public_menu_and_handlers(lang):
    from bot import register_pxe1_commands
    from handlers.profile import help_command
    from game.player_commands import PUBLIC_COMMANDS,HELP_COMMANDS
    conn=get_connection();conn.execute('UPDATE players SET lang=? WHERE telegram_id=1',(lang,));conn.commit();conn.close()
    message=SimpleNamespace(reply_text=AsyncMock())
    asyncio.run(help_command(SimpleNamespace(effective_user=SimpleNamespace(id=1),message=message),SimpleNamespace()))
    help_text=message.reply_text.call_args.args[0]
    assert '/quests' not in help_text and '/journal' in help_text and '/activities' in help_text
    menu=SimpleNamespace(bot=SimpleNamespace(set_my_commands=AsyncMock()))
    asyncio.run(register_pxe1_commands(menu))
    registered=next(c for c in menu.bot.set_my_commands.call_args_list if c.kwargs['language_code']==lang).args[0]
    assert [c.command for c in registered]==list(PUBLIC_COMMANDS)
    assert all(f'/{c.command} — {c.description}' in help_text for c in registered)
    source=Path(__file__).parents[1]/'bot.py'
    tree=ast.parse(source.read_text(encoding='utf-8'))
    handlers={node.args[0].value for node in ast.walk(tree) if isinstance(node,ast.Call)
        and isinstance(node.func,ast.Name) and node.func.id=='CommandHandler' and isinstance(node.args[0],ast.Constant)}
    assert set(HELP_COMMANDS)==handlers
    assert all(f'/{name} — ' in help_text for name in HELP_COMMANDS)


@pytest.mark.parametrize('lang,one,plural',[('en','edge','edges'),('es','tramo','tramos')])
@pytest.mark.parametrize('count',[0,1,2,5,11,21])
def test_live04_en_es_route_counts(lang,one,plural,count):
    word=one if count==1 else plural
    assert t('pxe1.map.route_preview',lang,hops=count,time='0:15')==f'{count} {word} · 0:15 · 0 '+('gold' if lang=='en' else 'oro')
    assert t('pxe1.travel.progress',lang,done=0,total=count).endswith(' '+word)


@pytest.mark.parametrize('count,word',[(0,'переходов'),(1,'переход'),(2,'перехода'),(4,'перехода'),(5,'переходов'),
    (11,'переходов'),(12,'переходов'),(14,'переходов'),(21,'переход'),(22,'перехода'),(25,'переходов'),(111,'переходов')])
def test_live04_russian_route_cases(count,word):
    assert t('pxe1.map.route_preview','ru',hops=count,time='0:15')==f'{count} {word} · 0:15 · 0 золота'
    assert t('pxe1.travel.progress','ru',done=0,total=count).endswith(' '+word)


@pytest.mark.parametrize('lang',['ru','en','es'])
@pytest.mark.parametrize('with_profession',[False,True])
def test_live06_level_fact_is_shown_once_and_acknowledged_after_delivery(lang,with_profession):
    from game.progression_rewards import apply_progression_reward
    from game.balance import exp_to_next_level
    from game.player_feedback import inline_feedback,acknowledge_presented_facts,record_feedback
    from handlers.combat_delivery import pve_result
    conn=get_connection();conn.execute('BEGIN IMMEDIATE')
    apply_progression_reward(conn,1,exp_to_next_level(1),0)
    if with_profession:
        record_feedback(conn,1,event_key='profession-test',source_kind='profession',source_id='test',event_kind='level_up',
            payload={'profession_key':'mining','new_level':2})
    conn.commit()
    player={**dict(get_player(1)),'lang':lang}
    settlement={'recipients':[{'player_id':1,'exp':100,'gold':0,'leveled_up':True,'level_after':2}]}
    text,_=pve_result(player,{'owner_player_id':1,'mob_id':'no_harvest'},None,None,settlement)
    text,keys=inline_feedback(1,lang,text)
    assert text.count(t('pxe1.character_level',lang,level=2))==1
    if with_profession:
        assert t('pxe1.profession_level',lang,name=t('professions.names.mining',lang),level=2) in text
        assert 'profession-test' in keys
    assert 'character_level:2' in keys
    assert conn.execute("SELECT state FROM player_feedback_events WHERE event_key='character_level:2'").fetchone()[0]=='pending'
    before=dict(get_player(1));acknowledge_presented_facts(1,keys)
    assert dict(get_player(1))==before and before['level']==2
    assert conn.execute("SELECT COUNT(*) FROM player_feedback_events WHERE state='pending'").fetchone()[0]==0
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_live08_fresh_journal_completed_and_chapter_archive_are_read_only(lang):
    from game.quest_board import get_chapter_contracts
    from handlers.chapter import build_journal,build_history
    from handlers.regional import _list_screen
    conn=get_connection()
    for contract in get_chapter_contracts():
        conn.execute('INSERT INTO player_contract_history(player_id,contract_key) VALUES (1,?)',(contract.contract_key,))
    conn.commit();player={**dict(get_player(1)),'lang':lang}
    before=list(conn.iterdump())
    _,home=build_journal(player)
    assert next(b.text for b in buttons(home) if b.callback_data=='alpha_history')==t('pxe1.journal.chapter_history',lang)
    _,completed=_list_screen(player,'s',0,'all')
    assert 'alpha_history' in [b.callback_data for b in buttons(completed)]
    _,archive=build_history(player)
    assert 'alpha_history_chapter' in [b.callback_data for b in buttons(archive)]
    story,kb=build_history(player,chapter_story=True)
    validate_surface(story,kb,long_detail=True)
    assert before==list(conn.iterdump())
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_live10_gear_rows_and_confirmation_identify_selected_instance(lang):
    from tests.test_pxe1_shop_transactions import seed,quote
    from handlers.shop_views import sell_list,sale_preview
    entry=seed('field_sword_1h',2)
    conn=get_connection()
    other=conn.execute('SELECT id FROM gear_instances WHERE telegram_id=1 AND id<>?',(entry,)).fetchone()[0]
    conn.execute("UPDATE gear_instances SET equipped_slot='weapon' WHERE id=?",(entry,))
    conn.execute("UPDATE gear_instances SET rarity='uncommon',enhance_level=1 WHERE id=?",(other,));conn.commit()
    player={**dict(get_player(1)),'lang':lang}
    _,keyboard=sell_list(player,'gear')
    equipped=next(b for b in buttons(keyboard) if b.callback_data==f'px:shop:saleview:g{entry}:1')
    enhanced=next(b for b in buttons(keyboard) if b.callback_data==f'px:shop:saleview:g{other}:1')
    assert equipped.text!=enhanced.text and t('inventory.equipped',lang) in equipped.text
    from handlers.inventory import RARITY_NAME
    assert '+1' in enhanced.text and RARITY_NAME[lang]['uncommon'] in enhanced.text
    for confirmation in (None,quote(other,kind='g')):
        text,kb=sale_preview(player,f'g{other}',confirmation_quote=confirmation)
        assert '+1' in text and RARITY_NAME[lang]['uncommon'] in text
        token=next(b.callback_data.split(':')[-1] for b in buttons(kb) if ':commit:' in b.callback_data)
        intent=json.loads(conn.execute('SELECT payload FROM player_ui_actions WHERE token=?',(token,)).fetchone()[0])
        assert intent['sale_quote']['entry_id']==other
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_live11_coast_map_exposes_real_aster_exit_without_movement(lang):
    from handlers.world_views import map_card
    from game.locations import get_location_neighbors,WORLD_LOCATIONS
    conn=get_connection();conn.execute("UPDATE players SET location_id='south_coast_shore' WHERE telegram_id=1");conn.commit()
    player={**dict(get_player(1)),'lang':lang};topology=json.dumps(WORLD_LOCATIONS,sort_keys=True)
    _,kb=map_card(player)
    destinations=[b.callback_data.removeprefix('goto_') for b in buttons(kb) if b.callback_data.startswith('goto_')]
    assert 'capital_city' in destinations and set(destinations)<=set(get_location_neighbors('south_coast_shore'))
    assert dict(get_player(1))['location_id']=='south_coast_shore'
    assert topology==json.dumps(WORLD_LOCATIONS,sort_keys=True)
    conn.close()


def test_live13_spanish_guard_has_local_translation_and_guard_intent():
    from game.i18n import _load_lang
    from tests.test_pxe1_pve_world_tick import started
    from game.pve_live import load_active_pve_encounter
    from handlers.combat_views import home,action_card
    assert _load_lang('es')['location']['pvp_action_guard_btn']=='🛡 Defensa'
    encounter,_=started();state,mob=load_active_pve_encounter(encounter_id=encounter)
    player={**dict(get_player(1)),'lang':'es'}
    with patch('time.time',return_value=1013):
        _,kb=home(player,mob,state)
        assert '🛡 Defensa' in [b.text for b in buttons(kb)] and 'Защита' not in str(kb)
        text,kb=action_card(player,state,'guard')
        assert 'Defensa' in text
        token=next(b.callback_data.removeprefix('battle_v1_') for b in buttons(kb) if b.callback_data.startswith('battle_v1_'))
        conn=get_connection();payload=json.loads(conn.execute('SELECT payload FROM player_ui_actions WHERE token=?',(token,)).fetchone()[0]);conn.close()
        assert payload['action']['kind']=='guard'


@pytest.mark.parametrize('lang',['en','es'])
def test_live14_item_description_fallback_has_no_id_and_keeps_valid_copy(lang,monkeypatch):
    from importlib import import_module
    translations=import_module('locales.items_'+lang).ITEM_DESCRIPTIONS
    monkeypatch.delitem(translations,'wooden_sword',raising=False)
    assert get_item_description('wooden_sword',lang)==t('professions.unknown_item_description',lang)
    assert 'wooden_sword' not in get_item_description('wooden_sword',lang)
    monkeypatch.setitem(translations,'wooden_sword','A readable description.')
    assert get_item_description('wooden_sword',lang)=='A readable description.'


def test_live14_english_equipment_more_card_keeps_actions_and_readable_fallback(monkeypatch):
    from tests.test_pxe1_shop_transactions import seed
    from handlers.inventory_views import item_card
    from locales.items_en import ITEM_DESCRIPTIONS
    monkeypatch.delitem(ITEM_DESCRIPTIONS,'wooden_sword',raising=False)
    instance=seed('wooden_sword')
    conn=get_connection()
    conn.execute("UPDATE gear_instances SET equipped_slot='weapon' WHERE id=?",(instance,));conn.commit()
    text,kb=item_card(1,f'g{instance}','gear','en',more=True)
    assert t('professions.unknown_item_description','en') in text and 'wooden_sword' not in text
    assert any(b.callback_data.startswith('inv_gunequip_') for b in buttons(kb))
    assert any(b.callback_data.startswith('inv_genh_') for b in buttons(kb))
    conn.close()
