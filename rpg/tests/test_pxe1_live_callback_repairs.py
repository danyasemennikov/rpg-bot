"""Transactional negative paths for LIVE-05, 07, 09 and 12."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

import pytest

from database import get_connection,get_player
from game.action_receipts import issue_actions
from game.i18n import t,get_location_name
from tests.test_pxe1_live_presentation_repairs import buttons,query


def run(handler,q,context=None):
    context=context or SimpleNamespace(user_data={},bot=SimpleNamespace(send_message=AsyncMock()))
    asyncio.run(handler(SimpleNamespace(callback_query=q),context))
    return context


def economic_state(conn):
    return {table:[tuple(r) for r in conn.execute(f'SELECT * FROM {table} ORDER BY 1')]
        for table in ('players','inventory','gear_instances','player_profession_tools',
            'economy_action_receipts','player_action_receipts','gear_mutation_receipts')}


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_live05_accept_and_claim_are_inline_and_duplicate_claim_grants_nothing(lang):
    from handlers.location import handle_location_buttons
    from game.quest_board import get_player_hunt_contract_state,register_contract_objective,register_hunt_kill_progress
    conn=get_connection();conn.execute('UPDATE players SET lang=? WHERE telegram_id=1',(lang,));conn.commit()
    q=query('quest_board_accept_chapter_first_watch');run(handle_location_buttons,q)
    assert not q.answer.call_args.kwargs.get('show_alert',False)
    assert get_player_hunt_contract_state(1)['contract_key']=='chapter_first_watch'
    conn.execute('BEGIN IMMEDIATE')
    register_hunt_kill_progress(player_id=1,mob_id='westwild_rabbit',location_id='westwild_n1',conn=conn)
    register_hunt_kill_progress(player_id=1,mob_id='westwild_rabbit',location_id='westwild_n1',conn=conn)
    register_contract_objective(conn,1,'gather','herb_common',3,'westwild_n1');conn.commit()
    assert get_player_hunt_contract_state(1)['status']=='completed'
    token=issue_actions(1,'contract_claim',['chapter_first_watch'])['chapter_first_watch']
    q=query('quest_board_claim_'+token);run(handle_location_buttons,q)
    assert not q.answer.call_args.kwargs.get('show_alert',False)
    claim_text=q.edit_message_text.call_args.args[0]
    assert t('pxe1.quest.claimed',lang,xp=60,gold=20) in claim_text
    assert t('pxe1.quest.ready',lang) not in claim_text
    assert t('location.quest_board_claim_hunter_points',lang,points=20) in claim_text
    assert 'alpha_assignment' in [b.callback_data for b in buttons(q.edit_message_text.call_args.kwargs['reply_markup'])]
    before=economic_state(conn)
    assert conn.execute("SELECT COUNT(*) FROM player_contract_history WHERE player_id=1 AND contract_key='chapter_first_watch'").fetchone()[0]==1
    run(handle_location_buttons,query('quest_board_claim_'+token))
    assert before==economic_state(conn)
    assert conn.execute("SELECT COUNT(*) FROM player_contract_history WHERE player_id=1 AND contract_key='chapter_first_watch'").fetchone()[0]==1
    conn.close()


def test_live05_claim_transport_failure_keeps_reward_once_and_fact_pending():
    from game.quest_board import accept_hunt_contract,register_contract_objective,register_hunt_kill_progress
    from handlers.location import handle_location_buttons
    assert accept_hunt_contract(player_id=1,location_id='capital_city',contract_key='chapter_first_watch')[0]
    conn=get_connection();conn.execute('BEGIN IMMEDIATE')
    for _ in range(2): register_hunt_kill_progress(player_id=1,mob_id='westwild_rabbit',location_id='westwild_n1',conn=conn)
    register_contract_objective(conn,1,'gather','herb_common',3,'westwild_n1');conn.commit()
    token=issue_actions(1,'contract_claim',['chapter_first_watch'])['chapter_first_watch']
    q=query('quest_board_claim_'+token);q.edit_message_text.side_effect=RuntimeError('offline')
    with pytest.raises(RuntimeError,match='offline'): run(handle_location_buttons,q)
    before=economic_state(conn)
    assert conn.execute("SELECT state FROM player_feedback_events WHERE event_key='claim:chapter_first_watch'").fetchone()[0]=='pending'
    run(handle_location_buttons,query('quest_board_claim_'+token))
    assert before==economic_state(conn)
    conn.close()


def test_live05_foreign_claim_token_and_wrong_board_do_not_grant():
    from handlers.location import handle_location_buttons
    from game.quest_board import accept_hunt_contract,register_contract_objective,register_hunt_kill_progress
    for pid in (1,777):
        assert accept_hunt_contract(player_id=pid,location_id='capital_city',contract_key='chapter_first_watch')[0]
    conn=get_connection();conn.execute('BEGIN IMMEDIATE')
    for _ in range(2): register_hunt_kill_progress(player_id=1,mob_id='westwild_rabbit',location_id='westwild_n1',conn=conn)
    register_contract_objective(conn,1,'gather','herb_common',3,'westwild_n1');conn.commit()
    token=issue_actions(1,'contract_claim',['chapter_first_watch'])['chapter_first_watch']
    before=economic_state(conn)
    run(handle_location_buttons,query('quest_board_claim_'+token,777))
    assert before==economic_state(conn)
    conn.execute("UPDATE players SET location_id='westwild_n1' WHERE telegram_id=1");conn.commit();before=economic_state(conn)
    run(handle_location_buttons,query('quest_board_claim_'+token))
    assert before==economic_state(conn)
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
@pytest.mark.parametrize('action',['preview','apply'])
def test_live07_outdoor_redistribution_explains_hub_and_creates_no_receipt(lang,action):
    from game.build_progression import migrate_character_builds_v1,attribute_redistribution_preview
    from game.build_progression import ATTRIBUTE_KEYS
    from handlers.build import handle_build_buttons,_localized_rejection
    migrate_character_builds_v1()
    player=dict(get_player(1));draft={k:player[k] for k in ATTRIBUTE_KEYS};draft['strength']-=1
    token=attribute_redistribution_preview(1,draft)['token'] if action=='apply' else None
    conn=get_connection();conn.execute("UPDATE players SET location_id='westwild_n2',lang=? WHERE telegram_id=1",(lang,));conn.commit()
    before=dict(get_player(1));receipts=[tuple(r) for r in conn.execute('SELECT * FROM build_mutation_receipts')]
    q=query('bv_attr_preview' if action=='preview' else 'bv_attr_apply_'+token)
    context=SimpleNamespace(user_data={'build_v1_attributes':draft})
    run(handle_build_buttons,q,context)
    # A fresh outdoor preview reports the hub rule; a hub-issued intent still
    # fails its original location binding after movement, before the hub guard.
    expected='safe_hub_required' if action=='preview' else 'stale_action'
    assert q.answer.call_args_list[0].args[0]==_localized_rejection(lang,expected)
    assert dict(get_player(1))==before
    assert receipts==[tuple(r) for r in conn.execute('SELECT * FROM build_mutation_receipts')]
    assert context.user_data['build_v1_attributes']=={k:before[k] for k in ATTRIBUTE_KEYS}
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_live09_old_repair_is_replaced_with_current_tools_and_receipts_replay(lang):
    from tests.test_pxe1_tools_economy import prepare
    from handlers.activities import tool_card,handle_activity_buttons
    from game.profession_tools import commit_tool_maintenance
    conn=prepare(2,24)
    conn.execute('UPDATE players SET lang=? WHERE telegram_id=1',(lang,));conn.commit()
    player=dict(get_player(1));_,kb=tool_card(player,'mining')
    old=next(b.callback_data for b in buttons(kb) if b.callback_data.startswith('px:repair:'))
    _,kb=tool_card(player,'mining');fresh=next(b.callback_data for b in buttons(kb) if b.callback_data.startswith('px:repair:'))
    assert fresh!=old
    assert commit_tool_maintenance(1,action_token=fresh.split(':')[-1])['status']=='repaired'
    before=economic_state(conn)
    q=query(old);run(handle_activity_buttons,q)
    assert q.edit_message_text.await_count==1
    assert any('120/120' in b.text for b in buttons(q.edit_message_text.call_args.kwargs['reply_markup']))
    assert '24/120' not in str(q.edit_message_text.call_args)
    assert before==economic_state(conn)
    run(handle_activity_buttons,query(fresh))
    assert before==economic_state(conn)
    run(handle_activity_buttons,query(old,777))
    assert before==economic_state(conn)
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_live09_old_sell_quote_refreshes_remaining_quantity_without_sale(lang):
    from tests.test_pxe1_shop_transactions import seed,quote,sale_token
    from handlers.shop_views import handle_shop_buttons,issue_sale
    from handlers.inventory import try_sell_inventory_item
    entry=seed(quantity=39)
    conn=get_connection();conn.execute('UPDATE players SET lang=? WHERE telegram_id=1',(lang,));conn.commit()
    token=issue_sale(1,quote(entry,39),confirmed=True)
    assert try_sell_inventory_item(1,sale_token(entry))['status']=='sold'
    before=economic_state(conn)
    q=query('px:shop:commit:i:'+token);run(handle_shop_buttons,q)
    text=q.edit_message_text.call_args.args[0]
    assert '×38' in text and '×39' not in text
    assert before==economic_state(conn)
    run(handle_shop_buttons,query('px:shop:commit:i:'+token,777))
    assert before==economic_state(conn)
    conn.close()


def test_live09_10_protected_gear_callback_refreshes_without_sale():
    from tests.test_pxe1_shop_transactions import seed
    from handlers.shop_views import handle_shop_buttons
    from game.gear_progression import issue_gear_intent
    entry=seed('field_sword_1h',2)
    token=issue_gear_intent(1,'sale',entry)
    conn=get_connection();conn.execute("UPDATE gear_instances SET equipped_slot='weapon' WHERE id=?",(entry,));conn.commit()
    before=economic_state(conn)
    for data in (f'px:shop:saleview:g{entry}:1','px:shop:commit:g:'+token):
        q=query(data);run(handle_shop_buttons,q)
        assert q.edit_message_text.await_count==1
        assert before==economic_state(conn)
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_live12_old_stop_renders_own_snapshot_and_never_stops_new_trip(lang):
    from game.travel_runtime import preview_travel,start_travel_session,stop_travel_session,advance_travel_edge
    from handlers.activities import handle_activity_buttons,activity_card
    conn=get_connection()
    path=['capital_city','westwild_n1','westwild_n2','westwild_n3','westwild_n4','westwild_n5','hub_westwild']
    conn.executemany('INSERT OR IGNORE INTO player_location_discovery(telegram_id,location_id) VALUES (1,?)',((p,) for p in path))
    conn.execute('UPDATE players SET lang=?,level=20 WHERE telegram_id=1',(lang,));conn.commit();conn.execute('BEGIN IMMEDIATE')
    first=start_travel_session(conn,1,preview_travel(conn,1,'hub_westwild'),request_id='old',now_ms=1000)
    old=stop_travel_session(conn,1,first['session_id'],now_ms=16000)
    assert old['edge_index']==1
    new=start_travel_session(conn,1,preview_travel(conn,1,'hub_westwild'),request_id='new',now_ms=16000)
    advance_travel_edge(conn,new['session_id'],now_ms=31000);conn.commit()
    before=economic_state(conn)
    new_before=dict(conn.execute('SELECT * FROM player_travel_sessions WHERE session_id=?',(new['session_id'],)).fetchone())
    assert get_player(1)['location_id']=='westwild_n2'
    q=query('px:stop:travel:'+old['session_id'])
    with patch('time.time',return_value=31): run(handle_activity_buttons,q)
    text=q.edit_message_text.call_args.args[0]
    assert t('pxe1.travel.position',lang,name=get_location_name('westwild_n1',lang)) in text
    assert t('pxe1.travel.position',lang,name=get_location_name('westwild_n2',lang)) not in text
    assert new_before==dict(conn.execute('SELECT * FROM player_travel_sessions WHERE session_id=?',(new['session_id'],)).fetchone())
    assert before==economic_state(conn)
    q=query('px:stop:travel:'+old['session_id'],777)
    with patch('time.time',return_value=31): run(handle_activity_buttons,q)
    q.edit_message_text.assert_not_awaited()
    assert before==economic_state(conn)
    assert new_before==dict(conn.execute('SELECT * FROM player_travel_sessions WHERE session_id=?',(new['session_id'],)).fetchone())
    for status,index in (('cancelled',1),('interrupted',2),('arrived',6)):
        text,_=activity_card(dict(get_player(1)),{**old,'status':status,'edge_index':index},'travel',now_ms=31000)
        assert t('pxe1.travel.position',lang,name=get_location_name(path[index],lang)) in text
    conn.close()
