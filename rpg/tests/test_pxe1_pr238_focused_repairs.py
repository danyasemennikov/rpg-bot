"""Astra F1–F3 reproducers and bounded delivery/pagination regressions."""

import asyncio
import json
from html import escape
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

import pytest
from telegram.error import BadRequest

from database import get_connection,get_player
from game.action_receipts import issue_actions
from game.i18n import t,get_item_name
from game.player_feedback import present_pending_feedback
from handlers.location import handle_location_buttons
from handlers.shop_views import sell_list,handle_shop_buttons,sale_preview
from tests.test_pxe1_live_presentation_repairs import buttons,query
from tests.test_pxe1_live_callback_repairs import run,economic_state as economy_snapshot


def economic_state(conn):
    result=economy_snapshot(conn)
    for table in ('player_hunter_progress','player_contract_history','player_hunt_contracts'):
        if conn.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():
            result[table]=[tuple(row) for row in conn.execute(f'SELECT * FROM {table} ORDER BY 1')]
    return result


def first_watch(lang='ru'):
    from game.quest_board import (
        accept_hunt_contract,register_hunt_kill_progress,register_contract_objective,
        HUNTER_RANK_THRESHOLDS,_ensure_player_hunter_progress_table,
    )
    from game.balance import exp_to_next_level
    assert accept_hunt_contract(player_id=1,location_id='capital_city',contract_key='chapter_first_watch')[0]
    conn=get_connection()
    conn.execute('UPDATE players SET lang=?,exp=? WHERE telegram_id=1',(lang,exp_to_next_level(1)-1))
    _ensure_player_hunter_progress_table(conn)
    conn.execute('INSERT OR REPLACE INTO player_hunter_progress(player_id,hunter_points) VALUES (1,?)',(HUNTER_RANK_THRESHOLDS[1][1]-1,))
    for _ in range(2):
        register_hunt_kill_progress(player_id=1,mob_id='westwild_rabbit',location_id='westwild_n1',conn=conn)
    register_contract_objective(conn,1,'gather','herb_common',3,'westwild_n1');conn.commit()
    token=issue_actions(1,'contract_claim',['chapter_first_watch'])['chapter_first_watch']
    return conn,token


def transport():
    return SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=100)),edit_message_text=AsyncMock())


def assert_breakdown(text,lang):
    from game.quest_board import HUNTER_RANK_THRESHOLDS
    assert t('pxe1.quest.claimed',lang,xp=60,gold=20) in text
    assert t('location.quest_board_claim_bonus_item',lang,qty=2,item=get_item_name('health_potion_small',lang)) in text
    assert t('location.quest_board_claim_hunter_points',lang,points=20) in text
    assert t('location.quest_board_claim_rank_up',lang,rank=t('location.hunter_rank_'+HUNTER_RANK_THRESHOLDS[1][0],lang)) in text
    assert text.count(t('pxe1.character_level',lang,level=2))==1
    assert t('pxe1.quest.ready',lang) not in text and '1/2' not in text and '3/3' not in text


def claim_events(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM player_feedback_events WHERE source_id='chapter_first_watch'")]


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_f1_f3_failed_edit_restart_recovery_keeps_full_snapshot_and_single_grant(lang):
    conn,token=first_watch(lang)
    q=query('quest_board_claim_'+token);q.edit_message_text.side_effect=RuntimeError('offline')
    with pytest.raises(RuntimeError,match='offline'): run(handle_location_buttons,q)
    before=economic_state(conn)
    assert all(e['state']=='pending' for e in claim_events(conn))
    snapshot=json.loads(conn.execute("SELECT payload_json FROM player_feedback_events WHERE event_kind='claim'").fetchone()[0])
    assert snapshot['bonus_item']['quantity']==2 and snapshot['hunter_progress']['rank_up']
    # A fresh delivery context has no handler return value; only persisted facts.
    bot=transport()
    assert asyncio.run(present_pending_feedback(bot,1))
    call=bot.edit_message_text.call_args or bot.send_message.call_args
    text=call.args[0] if bot.edit_message_text.await_count else call.args[1]
    assert_breakdown(text,lang)
    assert all(e['state']=='acknowledged' for e in claim_events(conn))
    assert before==economic_state(conn)
    assert not asyncio.run(present_pending_feedback(transport(),1))
    run(handle_location_buttons,query('quest_board_claim_'+token))
    assert before==economic_state(conn)
    assert conn.execute("SELECT COUNT(*) FROM player_contract_history WHERE player_id=1 AND contract_key='chapter_first_watch'").fetchone()[0]==1
    conn.close()


@pytest.mark.parametrize('failure',['offline','not_modified','deleted','uneditable','ack_failed'])
def test_f1_callback_retry_transport_and_ack_failure_paths(failure):
    conn,token=first_watch('en');q=query('quest_board_claim_'+token);bot=transport()
    context=SimpleNamespace(bot=bot,user_data={})
    if failure=='offline':
        q.edit_message_text.side_effect=RuntimeError('offline')
        with pytest.raises(RuntimeError): run(handle_location_buttons,q,context)
    elif failure=='ack_failed':
        with patch('game.player_feedback.acknowledge_presented_facts',side_effect=RuntimeError('ack failed')):
            with pytest.raises(RuntimeError): run(handle_location_buttons,q,context)
        assert q.edit_message_text.await_count==1
    else:
        q.edit_message_text.side_effect=BadRequest({'not_modified':'Message is not modified',
            'deleted':'Message to edit not found','uneditable':"Message can't be edited"}[failure])
        run(handle_location_buttons,q,context)
        if failure in {'deleted','uneditable'}:
            assert_breakdown(bot.send_message.call_args.args[1],'en')
        else: bot.send_message.assert_not_awaited()
    before=economic_state(conn)
    if failure in {'offline','ack_failed'}:
        assert all(e['state']=='pending' for e in claim_events(conn))
        retry=query('quest_board_claim_'+token)
        if failure=='ack_failed': retry.edit_message_text.side_effect=BadRequest('Message is not modified')
        run(handle_location_buttons,retry,context)
        assert_breakdown(retry.edit_message_text.call_args.args[0],'en')
    assert all(e['state']=='acknowledged' for e in claim_events(conn))
    assert before==economic_state(conn)
    assert not asyncio.run(present_pending_feedback(transport(),1))
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_f3_success_acknowledges_only_claimed_contract_after_edit(lang):
    from game.player_feedback import record_feedback
    conn,token=first_watch(lang)
    conn.execute('BEGIN IMMEDIATE')
    for key,kind,source,ref,payload in (
        ('other-objective','progress','chapter_objective','other',{'contract_key':'other','target':'wood_common','progress':1,'required':2}),
        ('other-profession','level_up','profession','other',{'profession_key':'mining','new_level':2}),
        ('other-finale','chapter_finale','chapter_claim','other',{}),
    ):
        record_feedback(conn,1,event_key=key,source_kind=source,source_id=ref,event_kind=kind,payload=payload)
    conn.commit();q=query('quest_board_claim_'+token)
    async def during_edit(*args,**kwargs):
        assert all(e['state']=='pending' for e in claim_events(conn))
        assert_breakdown(args[0],lang)
    q.edit_message_text.side_effect=during_edit
    run(handle_location_buttons,q)
    assert all(e['state']=='acknowledged' for e in claim_events(conn))
    assert [r[0] for r in conn.execute("SELECT state FROM player_feedback_events WHERE event_key LIKE 'other-%'")]==['pending']*3
    # Excluding the independently pending finale, minor recovery must not replay
    # Rabbit/Herb objectives from the claimed contract.
    from game.player_feedback import inline_feedback
    from game.i18n import get_mob_name
    text,keys=inline_feedback(1,lang,'Result')
    assert get_item_name('herb_common',lang) not in text and get_mob_name('westwild_rabbit',lang) not in text
    assert 'other-objective' in keys and 'other-profession' in keys
    conn.close()


def test_f1_legacy_claim_event_remains_readable_without_inventing_missing_rewards():
    from game.player_feedback import record_feedback
    conn=get_connection();conn.execute('BEGIN IMMEDIATE')
    record_feedback(conn,1,event_key='claim:legacy',source_kind='chapter_claim',source_id='legacy',event_kind='claim',
        payload={'contract_key':'legacy','reward_exp':60,'reward_gold':20})
    conn.commit();bot=transport()
    assert asyncio.run(present_pending_feedback(bot,1))
    text=bot.send_message.call_args.args[1]
    assert text==t('pxe1.quest.claimed','ru',xp=60,gold=20)
    assert conn.execute('SELECT state FROM player_feedback_events').fetchone()[0]=='acknowledged'
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
@pytest.mark.parametrize('entry',['journal','location'])
def test_f1_fresh_entry_after_failed_claim_recovers_full_result(lang,entry):
    from handlers.chapter import journal_command
    from handlers.location import location_command
    conn,token=first_watch(lang)
    q=query('quest_board_claim_'+token);q.edit_message_text.side_effect=RuntimeError('offline')
    with pytest.raises(RuntimeError): run(handle_location_buttons,q)
    before=economic_state(conn)
    conn.execute('DELETE FROM player_ui_actions');conn.commit()
    bot=transport();context=SimpleNamespace(bot=bot,user_data={})
    update=SimpleNamespace(effective_user=SimpleNamespace(id=1),message=SimpleNamespace(reply_text=AsyncMock()))
    handler=journal_command if entry=='journal' else location_command
    asyncio.run(handler(update,context))
    assert_breakdown(bot.edit_message_text.call_args.args[0],lang)
    assert all(e['state']=='acknowledged' for e in claim_events(conn))
    assert before==economic_state(conn)
    assert not asyncio.run(present_pending_feedback(transport(),1))
    conn.close()


def test_f1_replacement_coordinates_survive_ack_failure_and_restart():
    conn,token=first_watch('en');q=query('quest_board_claim_'+token)
    q.edit_message_text.side_effect=BadRequest('Message to edit not found')
    bot=transport()
    with patch('game.player_feedback.acknowledge_presented_facts',side_effect=RuntimeError('ack failed')):
        with pytest.raises(RuntimeError): run(handle_location_buttons,q,SimpleNamespace(bot=bot,user_data={}))
    event=conn.execute("SELECT * FROM player_feedback_events WHERE event_kind='claim'").fetchone()
    assert event['state']=='pending' and event['message_id']==100
    before=economic_state(conn);restarted=transport()
    restarted.edit_message_text.side_effect=BadRequest('Message is not modified')
    assert asyncio.run(present_pending_feedback(restarted,1))
    assert restarted.edit_message_text.call_args.kwargs['message_id']==100
    restarted.send_message.assert_not_awaited()
    assert before==economic_state(conn) and all(e['state']=='acknowledged' for e in claim_events(conn))
    conn.close()


@pytest.mark.parametrize('failure',['replacement_failed','unknown_bad_request'])
def test_f1_unsuccessful_transport_leaves_full_result_pending(failure):
    conn,token=first_watch('en');q=query('quest_board_claim_'+token);bot=transport()
    q.edit_message_text.side_effect=BadRequest('Message to edit not found' if failure=='replacement_failed' else 'Invalid HTML')
    bot.send_message.side_effect=RuntimeError('offline')
    with pytest.raises((RuntimeError,BadRequest)):
        run(handle_location_buttons,q,SimpleNamespace(bot=bot,user_data={}))
    assert all(e['state']=='pending' for e in claim_events(conn))
    before=economic_state(conn);fresh=transport()
    assert asyncio.run(present_pending_feedback(fresh,1))
    assert_breakdown(fresh.edit_message_text.call_args.args[0],'en')
    assert before==economic_state(conn)
    conn.close()


def test_f1_committed_token_replay_is_owner_scoped_after_intent_cleanup():
    conn,token=first_watch('en');q=query('quest_board_claim_'+token)
    q.edit_message_text.side_effect=RuntimeError('offline')
    with pytest.raises(RuntimeError): run(handle_location_buttons,q)
    conn.execute('DELETE FROM player_ui_actions');conn.commit();before=economic_state(conn)
    foreign=query('quest_board_claim_'+token,777);run(handle_location_buttons,foreign)
    assert '+60' not in str(foreign.edit_message_text.call_args)
    assert all(e['state']=='pending' for e in claim_events(conn))
    retry=query('quest_board_claim_'+token);run(handle_location_buttons,retry)
    assert_breakdown(retry.edit_message_text.call_args.args[0],'en')
    assert before==economic_state(conn)
    conn.close()


def test_f1_repeatable_contract_keeps_separate_snapshots_and_token_replay():
    from game.quest_board import accept_hunt_contract,register_hunt_kill_progress
    from game.player_feedback import claim_feedback_event
    conn=get_connection();tokens=[]
    for _ in range(2):
        assert accept_hunt_contract(player_id=1,location_id='capital_city',contract_key='hunt_forest_wolves')[0]
        for _ in range(5): register_hunt_kill_progress(player_id=1,mob_id='forest_wolf',location_id='westwild_n3',conn=conn)
        conn.commit()
        token=issue_actions(1,'contract_claim',['hunt_forest_wolves'])['hunt_forest_wolves'];tokens.append(token)
        q=query('quest_board_claim_'+token);q.edit_message_text.side_effect=RuntimeError('offline')
        with pytest.raises(RuntimeError): run(handle_location_buttons,q)
    assert claim_feedback_event(1,tokens[0])['event_key']!=claim_feedback_event(1,tokens[1])['event_key']
    before=economic_state(conn)
    run(handle_location_buttons,query('quest_board_claim_'+tokens[1]))
    assert claim_feedback_event(1,tokens[0])['state']=='pending'
    assert claim_feedback_event(1,tokens[1])['state']=='acknowledged'
    run(handle_location_buttons,query('quest_board_claim_'+tokens[0]))
    assert before==economic_state(conn)
    conn.close()


def test_f1_finale_keeps_its_navigation_and_full_claim_without_clearing_unrelated_facts():
    from tests.test_pxe1_feedback_journal import homecoming
    from game.quest_board import register_contract_objective
    from game.player_feedback import record_feedback
    conn=homecoming();conn.execute('BEGIN IMMEDIATE')
    register_contract_objective(conn,1,'craft','health_potion_small',1,'capital_city')
    register_contract_objective(conn,1,'sell','wood_common',1,'capital_city')
    record_feedback(conn,1,event_key='other-profession',source_kind='profession',source_id='other',event_kind='level_up',
        payload={'profession_key':'mining','new_level':2})
    conn.commit()
    token=issue_actions(1,'contract_claim',['chapter_homecoming'])['chapter_homecoming']
    q=query('quest_board_claim_'+token);run(handle_location_buttons,q)
    text=q.edit_message_text.call_args.args[0]
    assert t('pxe1.chapter.complete','ru') in text and t('pxe1.quest.claimed','ru',xp=80,gold=40) in text
    assert 'px:finale:opportunities' in [b.callback_data for b in buttons(q.edit_message_text.call_args.kwargs['reply_markup'])]
    assert conn.execute("SELECT state FROM player_feedback_events WHERE event_key='other-profession'").fetchone()[0]=='pending'
    assert conn.execute("SELECT state FROM player_feedback_events WHERE event_kind='chapter_finale'").fetchone()[0]=='presented'
    assert conn.execute("SELECT state FROM player_feedback_events WHERE event_kind='claim'").fetchone()[0]=='acknowledged'
    conn.close()


def test_f1_deleted_presented_finale_retains_replacement_for_later_recovery():
    from game.player_feedback import record_feedback
    conn=get_connection();conn.execute('BEGIN IMMEDIATE')
    record_feedback(conn,1,event_key='chapter_finale:chapter_homecoming',source_kind='chapter_claim',source_id='chapter_homecoming',
                    event_kind='chapter_finale',payload={})
    conn.commit();assert asyncio.run(present_pending_feedback(transport(),1))
    bot=transport();bot.edit_message_text.side_effect=BadRequest('Message to edit not found')
    bot.send_message.return_value=SimpleNamespace(message_id=200)
    assert asyncio.run(present_pending_feedback(bot,1,recover_presented=True))
    assert tuple(conn.execute('SELECT state,message_id FROM player_feedback_events').fetchone())==('presented',200)
    again=transport();assert asyncio.run(present_pending_feedback(again,1,recover_presented=True))
    assert again.edit_message_text.call_args.kwargs['message_id']==200
    again.send_message.assert_not_awaited();conn.close()


def test_f1_snapshot_write_failure_rolls_back_claim_and_all_rewards():
    from game.quest_board import claim_completed_hunt_contract
    from game.player_feedback import record_feedback
    conn,token=first_watch();before=economic_state(conn)
    def fail_claim(*args,**kwargs):
        if kwargs['event_kind']=='claim': raise RuntimeError('snapshot unavailable')
        return record_feedback(*args,**kwargs)
    with patch('game.player_feedback.record_feedback',side_effect=fail_claim):
        result=claim_completed_hunt_contract(player_id=1,location_id='capital_city',action_token=token)
    assert result[:2]==(False,'reward_delivery_failed')
    assert before==economic_state(conn)
    assert not conn.execute("SELECT 1 FROM player_feedback_events WHERE event_kind='claim'").fetchone()
    conn.close()


def long_inventory(lang='es',count=6):
    from game.items_data import get_item
    from game.gear_instances import create_gear_instance,SECONDARY_ROLL_BASE_RANGES,_secondary_strength_multiplier
    from game.itemization import get_generated_secondary_pool_for_item
    stats=['physical_defense','magic_defense','magic_power','healing_power']
    assert set(stats)<=set(get_generated_secondary_pool_for_item(get_item('amulet_of_kindled_prayer')))
    rolls=[{'stat':s,'value':int(round(SECONDARY_ROLL_BASE_RANGES[s][1]*_secondary_strength_multiplier(50)))} for s in stats]
    assert [r['value'] for r in rolls]==[21,21,34,34]
    conn=get_connection();ids=[]
    for _ in range(count):
        row=create_gear_instance(1,'amulet_of_kindled_prayer',conn=conn,rarity='legendary',item_tier=50,enhance_level=15,secondary_rolls_json=json.dumps(rolls))
        ids.append(row)
    conn.execute('UPDATE players SET lang=? WHERE telegram_id=1',(lang,));conn.commit()
    return conn,ids


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_f2_exact_916_unit_inventory_all_entries_reachable_and_previews_truthful(lang):
    from handlers.shop_views import sale_entry_label,title
    from handlers.inventory import get_gear_inventory_entries
    from game.player_ui import validate_surface
    conn,ids=long_inventory(lang)
    player=dict(get_player(1));entries=get_gear_inventory_entries(1)
    original='\n'.join([title(player),t('pxe1.inventory.gear',lang)]+[sale_entry_label(player,row,'g')+' ×1' for row in entries])
    if lang=='es': assert len(original.encode('utf-16-le'))//2==916
    seen=[];page=0
    while True:
        text,kb=sell_list(player,'gear',page)
        validate_surface(text,kb,list_view=True)
        assert len(text.encode('utf-16-le'))//2<=900
        rows=[b for b in buttons(kb) if b.callback_data.startswith('px:shop:saleview:')]
        for b in rows:
            entry=int(b.callback_data.split(':')[3][1:]);seen.append(entry)
            preview,pkb=sale_preview(player,f'g{entry}')
            assert '+15' in preview and get_item_name('amulet_of_kindled_prayer',lang) in preview
            selected=next(row for row in entries if row['id']==entry)
            assert '<b>'+escape(sale_entry_label(player,selected,'g'))+'</b>' in preview
            token=next(b.callback_data.split(':')[-1] for b in buttons(pkb) if ':commit:' in b.callback_data)
            payload=json.loads(conn.execute('SELECT payload FROM player_ui_actions WHERE token=?',(token,)).fetchone()[0])
            assert payload['sale_quote']['entry_id']==entry
        next_page=f'px:shop:sell:gear:{page+1}'
        if next_page not in [b.callback_data for b in buttons(kb)]: break
        page+=1
        assert page<10
    assert seen==ids and len(seen)==len(set(seen))
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_f2_distinct_rolls_middle_page_and_confirmation_keep_exact_entries(lang):
    from game.player_ui import validate_surface
    from game.gear_progression import apply_gear_intent
    from handlers.shop_views import sale_entry_label
    from handlers.inventory import get_gear_inventory_entries
    conn,ids=long_inventory(lang,18)
    for index,entry_id in enumerate(ids):
        rolls=json.loads(conn.execute('SELECT secondary_rolls_json FROM gear_instances WHERE id=?',(entry_id,)).fetchone()[0])
        rolls[-1]['value']-=index%6
        conn.execute('UPDATE gear_instances SET secondary_rolls_json=? WHERE id=?',(json.dumps(rolls),entry_id))
    conn.commit();player=dict(get_player(1));labels={row['id']:sale_entry_label(player,row,'g') for row in get_gear_inventory_entries(1)}
    assert len({labels[entry_id] for entry_id in ids[:6]})==6
    text,kb=sell_list(player,'gear',1);validate_surface(text,kb,list_view=True)
    assert {'px:shop:sell:gear:0','px:shop:sell:gear:2'}<={b.callback_data for b in buttons(kb)}
    selected=next(b for b in buttons(kb) if ':saleview:' in b.callback_data)
    entry_id=int(selected.callback_data.split(':')[3][1:])
    assert selected.text==labels[entry_id]+' ×1'
    q=query(selected.callback_data);run(handle_shop_buttons,q)
    token=next(b.callback_data.split(':')[-1] for b in buttons(q.edit_message_text.call_args.kwargs['reply_markup']) if ':commit:' in b.callback_data)
    result=apply_gear_intent(1,'sale',token)
    assert result['status']=='confirmation_required'
    before=economic_state(conn)
    text,kb=sale_preview(player,f'g{entry_id}',confirmation_quote=result['quote'])
    validate_surface(text,kb)
    assert '<b>'+escape(labels[entry_id])+'</b>' in text
    assert before==economic_state(conn)
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
@pytest.mark.parametrize('failure',['stale','equipped','foreign'])
def test_f2_long_inventory_rejection_refresh_is_renderable_without_mutation(lang,failure):
    from game.gear_progression import issue_gear_intent
    from game.player_ui import validate_surface
    conn,ids=long_inventory(lang)
    if failure=='stale': data='px:shop:commit:g:invalid'
    else:
        token=issue_gear_intent(1,'sale',ids[0]);data='px:shop:commit:g:'+token
        if failure=='equipped':
            conn.execute("UPDATE gear_instances SET equipped_slot='amulet' WHERE id=?",(ids[0],));conn.commit()
    before=economic_state(conn);q=query(data,777 if failure=='foreign' else 1)
    run(handle_shop_buttons,q)
    assert q.answer.await_count==1 and q.edit_message_text.await_count==1
    validate_surface(q.edit_message_text.call_args.args[0],q.edit_message_text.call_args.kwargs['reply_markup'],list_view=True)
    assert before==economic_state(conn)
    conn.close()
