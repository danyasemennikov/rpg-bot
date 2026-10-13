"""Exact F1-A/F1-B reproducers; recovery transport and acknowledgement matrix."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from telegram.error import BadRequest

from game.i18n import t
from game.player_feedback import present_pending_feedback
from handlers.location import handle_location_buttons
from tests.test_pxe1_live_presentation_repairs import query
from tests.test_pxe1_live_callback_repairs import run
from tests.test_pxe1_pr238_focused_repairs import (
    first_watch,transport,economic_state,claim_events,assert_breakdown,
)


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_f1a_successful_replacement_ack_failure_old_callback_reuses_saved_card(lang):
    conn,token=first_watch(lang);bot=transport()
    bot.send_message.side_effect=[SimpleNamespace(message_id=100),SimpleNamespace(message_id=101)]
    q=query('quest_board_claim_'+token)
    q.edit_message_text.side_effect=BadRequest("Message can't be edited")
    context=SimpleNamespace(bot=bot,user_data={})
    with patch('game.player_feedback.acknowledge_presented_facts',side_effect=RuntimeError('ack failed')):
        with pytest.raises(RuntimeError,match='ack failed'): run(handle_location_buttons,q,context)
    before=economic_state(conn)
    assert conn.execute("SELECT message_id FROM player_feedback_events WHERE event_kind='claim'").fetchone()[0]==100
    async def inspect_binding(*args,**kwargs):
        assert kwargs['message_id']==100
        assert conn.execute("SELECT message_id FROM player_feedback_events WHERE event_kind='claim'").fetchone()[0]==100
        assert all(e['state']=='pending' for e in claim_events(conn))
        assert_breakdown(args[0],lang)
    bot.edit_message_text.side_effect=inspect_binding
    run(handle_location_buttons,q,context)
    assert bot.send_message.await_count==1 and bot.edit_message_text.await_count==1
    assert q.edit_message_text.await_count==1
    assert all(e['state']=='acknowledged' for e in claim_events(conn))
    for _ in range(2): run(handle_location_buttons,q,context)
    assert not asyncio.run(present_pending_feedback(transport(),1))
    assert before==economic_state(conn)
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_f1b_legacy_claim_displays_separate_durable_level_before_ack(lang):
    conn,token=first_watch(lang);q=query('quest_board_claim_'+token)
    q.edit_message_text.side_effect=RuntimeError('offline')
    with pytest.raises(RuntimeError): run(handle_location_buttons,q)
    # Downgrade only the notification payload to the actual older format. The
    # rewards and separate level event were committed by the real quest owner.
    conn.execute("UPDATE player_feedback_events SET payload_json=?,chat_id=NULL,message_id=NULL WHERE event_kind='claim'",
        (json.dumps({'contract_key':'chapter_first_watch','reward_exp':60,'reward_gold':20}),))
    conn.execute('UPDATE players SET level=9 WHERE telegram_id=1')
    conn.commit();before=economic_state(conn);bot=transport()
    async def during_send(*args,**kwargs):
        text=args[1]
        assert text.count(t('pxe1.character_level',lang,level=2))==1
        assert t('pxe1.character_level',lang,level=9) not in text
        assert conn.execute("SELECT state FROM player_feedback_events WHERE event_key='character_level:2'").fetchone()[0]=='pending'
        return SimpleNamespace(message_id=100)
    bot.send_message.side_effect=during_send
    assert asyncio.run(present_pending_feedback(bot,1))
    assert conn.execute("SELECT state FROM player_feedback_events WHERE event_key='character_level:2'").fetchone()[0]=='acknowledged'
    assert before==economic_state(conn)
    assert not asyncio.run(present_pending_feedback(transport(),1))
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
@pytest.mark.parametrize('outcome',['not_modified','edit_failed','replacement_failed','replacement_ack_failed'])
def test_f1a_old_callback_failures_preserve_current_replacement_through_restart(lang,outcome):
    conn,token=first_watch(lang);q=query('quest_board_claim_'+token);bot=transport()
    q.edit_message_text.side_effect=BadRequest("Message can't be edited")
    context=SimpleNamespace(bot=bot,user_data={})
    with patch('game.player_feedback.acknowledge_presented_facts',side_effect=RuntimeError('ack failed')):
        with pytest.raises(RuntimeError): run(handle_location_buttons,q,context)
    before=economic_state(conn)
    if outcome=='not_modified':
        bot.edit_message_text.side_effect=BadRequest('Message is not modified')
        run(handle_location_buttons,q,context)
    elif outcome=='edit_failed':
        bot.edit_message_text.side_effect=RuntimeError('offline')
        with pytest.raises(RuntimeError): run(handle_location_buttons,q,context)
    else:
        bot.edit_message_text.side_effect=BadRequest('Message to edit not found')
        if outcome=='replacement_failed':
            bot.send_message.side_effect=RuntimeError('offline')
            with pytest.raises(RuntimeError): run(handle_location_buttons,q,context)
        else:
            bot.send_message.return_value=SimpleNamespace(message_id=200)
            with patch('game.player_feedback.acknowledge_presented_facts',side_effect=RuntimeError('ack failed')):
                with pytest.raises(RuntimeError): run(handle_location_buttons,q,context)
    assert bot.edit_message_text.call_args.kwargs['message_id']==100
    assert q.edit_message_text.await_count==1
    expected_id=200 if outcome=='replacement_ack_failed' else 100
    event=conn.execute("SELECT * FROM player_feedback_events WHERE event_kind='claim'").fetchone()
    assert event['message_id']==expected_id
    if outcome!='not_modified':
        assert all(e['state']=='pending' for e in claim_events(conn))
        resumed=transport()
        # Same obsolete callback again, with a new delivery context.
        run(handle_location_buttons,q,SimpleNamespace(bot=resumed,user_data={}))
        assert resumed.edit_message_text.call_args.kwargs['message_id']==expected_id
        assert_breakdown(resumed.edit_message_text.call_args.args[0],lang)
        resumed.send_message.assert_not_awaited()
    assert all(e['state']=='acknowledged' for e in claim_events(conn))
    assert before==economic_state(conn)
    assert not asyncio.run(present_pending_feedback(transport(),1))
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_f1b_level_that_does_not_fit_remains_pending_for_independent_delivery(lang):
    conn,token=first_watch(lang);q=query('quest_board_claim_'+token)
    q.edit_message_text.side_effect=RuntimeError('offline')
    with pytest.raises(RuntimeError): run(handle_location_buttons,q)
    conn.execute("UPDATE player_feedback_events SET payload_json=?,chat_id=NULL,message_id=NULL WHERE event_kind='claim'",
        (json.dumps({'contract_key':'chapter_first_watch','reward_exp':60,'reward_gold':20}),))
    conn.commit();before=economic_state(conn)
    line=t('pxe1.quest.claimed',lang,xp=60,gold=20)
    large=line+' '+('x'*(895-len(line.encode('utf-16-le'))//2-1))
    bot=transport()
    with patch('game.player_feedback.render_claim_feedback',return_value=large):
        assert asyncio.run(present_pending_feedback(bot,1))
    assert t('pxe1.character_level',lang,level=2) not in bot.send_message.call_args.args[1]
    assert conn.execute("SELECT state FROM player_feedback_events WHERE event_kind='claim'").fetchone()[0]=='acknowledged'
    assert conn.execute("SELECT state FROM player_feedback_events WHERE event_key='character_level:2'").fetchone()[0]=='pending'
    separate=transport();assert asyncio.run(present_pending_feedback(separate,1))
    assert separate.send_message.call_args.args[1]==t('pxe1.character_level',lang,level=2)
    assert before==economic_state(conn)
    assert conn.execute("SELECT state FROM player_feedback_events WHERE event_key='character_level:2'").fetchone()[0]=='acknowledged'
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
@pytest.mark.parametrize('scenario',[
    'edit_success_ack_success','edit_success_ack_failed','edit_failed',
    'replacement_success_ack_success','replacement_success_ack_failed','replacement_failed',
])
def test_f1a_transport_ack_combinations_keep_binding_and_single_grant(lang,scenario):
    conn,token=first_watch(lang);q=query('quest_board_claim_'+token);bot=transport()
    context=SimpleNamespace(bot=bot,user_data={})
    if scenario.startswith('replacement'):
        q.edit_message_text.side_effect=BadRequest('Message to edit not found')
    elif scenario=='edit_failed': q.edit_message_text.side_effect=RuntimeError('offline')
    if scenario=='replacement_failed': bot.send_message.side_effect=RuntimeError('offline')
    if scenario.endswith('ack_failed'):
        with patch('game.player_feedback.acknowledge_presented_facts',side_effect=RuntimeError('ack failed')):
            with pytest.raises(RuntimeError): run(handle_location_buttons,q,context)
    elif scenario in {'edit_failed','replacement_failed'}:
        with pytest.raises(RuntimeError): run(handle_location_buttons,q,context)
    else: run(handle_location_buttons,q,context)
    before=economic_state(conn)
    pending=scenario.endswith('ack_failed') or scenario in {'edit_failed','replacement_failed'}
    expected_id=100 if scenario in {'replacement_success_ack_success','replacement_success_ack_failed'} else 42
    event=conn.execute("SELECT * FROM player_feedback_events WHERE event_kind='claim'").fetchone()
    assert event['message_id']==expected_id and event['state']==('pending' if pending else 'acknowledged')
    # Repeated delivery attempts fail without changing the recovery binding.
    if pending:
        restarted=transport();restarted.edit_message_text.side_effect=RuntimeError('offline')
        with pytest.raises(RuntimeError): asyncio.run(present_pending_feedback(restarted,1))
        assert restarted.edit_message_text.call_args.kwargs['message_id']==expected_id
        restarted.send_message.assert_not_awaited()
        assert all(e['state']=='pending' for e in claim_events(conn))
        resumed=transport();resumed.edit_message_text.side_effect=BadRequest('Message is not modified')
        assert asyncio.run(present_pending_feedback(resumed,1))
        assert_breakdown(resumed.edit_message_text.call_args.args[0],lang)
        assert resumed.edit_message_text.call_args.kwargs['message_id']==expected_id
        resumed.send_message.assert_not_awaited()
    for _ in range(2): run(handle_location_buttons,q,context)
    assert all(e['state']=='acknowledged' for e in claim_events(conn))
    assert before==economic_state(conn)
    assert conn.execute("SELECT COUNT(*) FROM player_contract_history WHERE player_id=1 AND contract_key='chapter_first_watch'").fetchone()[0]==1
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
@pytest.mark.parametrize('failure',['edit_failed','ack_failed'])
def test_f1b_legacy_level_stays_pending_on_failed_display_or_ack(lang,failure):
    conn,token=first_watch(lang);q=query('quest_board_claim_'+token)
    q.edit_message_text.side_effect=RuntimeError('offline')
    with pytest.raises(RuntimeError): run(handle_location_buttons,q)
    conn.execute("UPDATE player_feedback_events SET payload_json=? WHERE event_kind='claim'",
        (json.dumps({'contract_key':'chapter_first_watch','reward_exp':60,'reward_gold':20}),))
    conn.commit();before=economic_state(conn);bot=transport()
    if failure=='edit_failed':
        bot.edit_message_text.side_effect=RuntimeError('offline')
        with pytest.raises(RuntimeError): asyncio.run(present_pending_feedback(bot,1))
    else:
        with patch('game.player_feedback.acknowledge_presented_facts',side_effect=RuntimeError('ack failed')):
            with pytest.raises(RuntimeError): asyncio.run(present_pending_feedback(bot,1))
    assert all(e['state']=='pending' for e in claim_events(conn))
    retry=transport();assert asyncio.run(present_pending_feedback(retry,1))
    assert retry.edit_message_text.call_args.args[0].count(t('pxe1.character_level',lang,level=2))==1
    assert before==economic_state(conn)
    assert all(e['state']=='acknowledged' for e in claim_events(conn))
    conn.close()
