import asyncio,json
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

import pytest
from database import get_connection,get_player
from game.i18n import t
from game.player_ui import validate_surface
from handlers.pvp_group import preparation_or_live_card,allies_card,handle_membership_choice,retry_preparation_delivery
from tests.test_pxe1_pvp_membership import prepare,membership_token,apply_choice


def buttons(keyboard): return [b for row in keyboard.inline_keyboard for b in row]


def query(actor,data):
    return SimpleNamespace(data=data,from_user=SimpleNamespace(id=actor),message=SimpleNamespace(chat_id=actor,message_id=42),
        edit_message_text=AsyncMock(),answer=AsyncMock())


def bot():
    return SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=80)),
        edit_message_text=AsyncMock(return_value=SimpleNamespace(message_id=80)))


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_escape_at_deadline_reports_expiry_without_claiming_a_roll(lang):
    from game.action_receipts import issue_actions
    from game.pvp_world import encoded
    from handlers.location import handle_location_buttons
    conn,e=prepare()
    conn.execute('UPDATE players SET lang=?',(lang,));conn.commit()
    payload=encoded({'schema_version':1,'catalog_version':2,'engagement_id':e,'state_revision':1})
    token=issue_actions(1,'pvp_prep_escape',[payload])[payload]
    q=query(1,f'pvp_escape_{e}_{token}')
    context=SimpleNamespace(user_data={},bot=bot())
    with patch('time.time',return_value=1300),patch('game.pvp_live._utc_now',return_value=datetime.fromtimestamp(1300,timezone.utc)):
        asyncio.run(handle_location_buttons(SimpleNamespace(callback_query=q),context))
    assert q.answer.call_args.args[0]==t('pxe1.combat.turn_expired',lang)
    assert conn.execute('SELECT engagement_state FROM pvp_engagements WHERE id=?',(e,)).fetchone()[0]=='converted_to_battle'
    assert not conn.execute('SELECT 1 FROM economy_action_receipts WHERE request_id=?',('ui:'+token,)).fetchone()
    assert conn.execute('SELECT used FROM player_ui_actions WHERE token=?',(token,)).fetchone()[0]==0
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_real_invite_accept_leave_callbacks_and_receipt_replay(lang):
    conn,e=prepare()
    conn.execute('UPDATE players SET lang=?',(lang,));conn.commit()
    transport=bot();context=SimpleNamespace(bot=transport)
    with patch('time.time',return_value=1001),patch('game.pvp_live._utc_now',return_value=datetime.fromtimestamp(1001,timezone.utc)):
        row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(e,)).fetchone()
        text,kb=preparation_or_live_card(row,dict(get_player(1)))
        validate_surface(text,kb)
        assert next(b for b in buttons(kb) if b.text==t('pxe1.membership.invite',lang)).callback_data==f'pvp_allies_{e}_0'
        before=row['reason_context']
        text,kb=allies_card(row,dict(get_player(1)))
        validate_surface(text,kb,list_view=True)
        assert conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?',(e,)).fetchone()[0]==before
        choices=[b for b in buttons(kb) if b.callback_data.startswith('pvp_member_')]
        assert len(choices)==4
        picked=next(b for b in choices if json.loads(conn.execute('SELECT payload FROM player_ui_actions WHERE token=?',(b.callback_data.removeprefix('pvp_member_'),)).fetchone()[0])['ally_id']==2)
        q=query(1,picked.callback_data)
        async def committed_before_edit(*args,**kwargs):
            other=get_connection()
            other.execute('BEGIN IMMEDIATE')
            assert other.execute('SELECT status FROM pvp_engagement_reinforcements WHERE ally_id=2').fetchone()[0]=='pending'
            assert other.execute("SELECT COUNT(*) FROM economy_action_receipts WHERE action_kind='pvp_membership_pxe1'").fetchone()[0]==1
            other.rollback();other.close()
        q.edit_message_text.side_effect=committed_before_edit
        asyncio.run(handle_membership_choice(SimpleNamespace(callback_query=q),context))
        row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(e,)).fetchone()
        text,kb=preparation_or_live_card(row,dict(get_player(2)))
        validate_surface(text,kb)
        join=next(b for b in buttons(kb) if b.text==t('pxe1.membership.join_side',lang,name=get_player(1)['name']))
        q=query(2,join.callback_data)
        asyncio.run(handle_membership_choice(SimpleNamespace(callback_query=q),context))
        assert conn.execute('SELECT status FROM pvp_engagement_reinforcements WHERE ally_id=2').fetchone()[0]=='accepted'
        text,kb=q.edit_message_text.call_args.args[0],q.edit_message_text.call_args.kwargs['reply_markup']
        leave=next(b for b in buttons(kb) if b.text==t('location.pvp_leave_prep',lang))
        asyncio.run(handle_membership_choice(SimpleNamespace(callback_query=query(2,leave.callback_data)),context))
        assert conn.execute('SELECT status FROM pvp_engagement_reinforcements WHERE ally_id=2').fetchone()[0]=='left'
        conn.execute("UPDATE players SET location_id='capital_city',travel_revision=travel_revision+1 WHERE telegram_id=2")
        conn.execute('DELETE FROM player_ui_actions');conn.commit()
        replay=query(2,join.callback_data)
        asyncio.run(handle_membership_choice(SimpleNamespace(callback_query=replay),context))
        assert replay.edit_message_text.call_args.args[0]==t('pxe1.membership.recovered',lang,outcome=t('pxe1.membership.accepted',lang))
        assert conn.execute('SELECT status FROM pvp_engagement_reinforcements WHERE ally_id=2').fetchone()[0]=='left'
        assert conn.execute("SELECT COUNT(*) FROM economy_action_receipts WHERE action_kind='pvp_membership_pxe1'").fetchone()[0]==3
    conn.close()


def test_invitation_delivery_retry_after_handler_transport_failure_preserves_tokens():
    conn,e=prepare();transport=bot()
    with patch('time.time',return_value=1001),patch('game.pvp_live._utc_now',return_value=datetime.fromtimestamp(1001,timezone.utc)):
        token=membership_token(conn,e,1,'invite',ally_id=2)
        q=query(1,'pvp_member_'+token);q.edit_message_text.side_effect=RuntimeError('offline')
        with pytest.raises(RuntimeError,match='offline'):
            asyncio.run(handle_membership_choice(SimpleNamespace(callback_query=q),SimpleNamespace(bot=transport)))
        transport.send_message.side_effect=[SimpleNamespace(message_id=81),RuntimeError('blocked ally'),SimpleNamespace(message_id=82)]
        asyncio.run(retry_preparation_delivery(transport))
        assert conn.execute('SELECT surface_kind FROM player_pxe1_ui WHERE player_id=2').fetchone() is None
        principal_tokens=[r[0] for r in conn.execute('SELECT token FROM player_ui_actions WHERE player_id=1')]
        transport.send_message.side_effect=None
        asyncio.run(retry_preparation_delivery(transport))
        assert conn.execute('SELECT surface_kind FROM player_pxe1_ui WHERE player_id=2').fetchone()[0]=='pvp'
        assert [r[0] for r in conn.execute('SELECT token FROM player_ui_actions WHERE player_id=1')]==principal_tokens
        assert transport.send_message.await_count==4
        assert conn.execute('SELECT COUNT(*) FROM pvp_engagement_reinforcements').fetchone()[0]==1
        assert conn.execute("SELECT COUNT(*) FROM economy_action_receipts WHERE action_kind='pvp_membership_pxe1'").fetchone()[0]==1
    conn.close()


def test_candidate_pages_do_not_hide_eligible_players_or_mutate_roster():
    conn,e=prepare()
    for player_id in range(10,37):
        conn.execute("INSERT INTO players(telegram_id,name,location_id,level,hp,max_hp,mana,max_mana,novice_protection) VALUES (?,'Candidate','westwild_n4',20,100,100,100,100,0)",(player_id,))
        conn.execute('INSERT INTO equipment(telegram_id) VALUES (?)',(player_id,))
    conn.commit()
    row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(e,)).fetchone()
    found=[]
    with patch('time.time',return_value=1001),patch('game.pvp_live._utc_now',return_value=datetime.fromtimestamp(1001,timezone.utc)):
        for page in range(6):
            text,kb=allies_card(row,dict(get_player(1)),page)
            validate_surface(text,kb,list_view=True)
            for b in buttons(kb):
                if b.callback_data.startswith('pvp_member_'):
                    found.append(json.loads(conn.execute('SELECT payload FROM player_ui_actions WHERE token=?',(b.callback_data.removeprefix('pvp_member_'),)).fetchone()[0])['ally_id'])
    assert set(found)=={2,3,4,5,*range(10,37)} and len(found)==31
    assert conn.execute('SELECT COUNT(*) FROM pvp_engagement_reinforcements').fetchone()[0]==0
    conn.close()


def test_legacy_raw_invite_callback_cannot_create_fresh_membership():
    from handlers.location import handle_location_buttons
    conn,e=prepare();q=query(1,f'pvp_invite_{e}_2')
    with patch('time.time',return_value=1001),patch('game.pvp_live._utc_now',return_value=datetime.fromtimestamp(1001,timezone.utc)):
        asyncio.run(handle_location_buttons(SimpleNamespace(callback_query=q,effective_user=q.from_user),
            SimpleNamespace(bot=bot(),user_data={},application=SimpleNamespace(bot_data={}))))
    assert conn.execute('SELECT COUNT(*) FROM pvp_engagement_reinforcements').fetchone()[0]==0
    assert conn.execute("SELECT COUNT(*) FROM economy_action_receipts WHERE action_kind='pvp_membership_pxe1'").fetchone()[0]==0
    q.edit_message_text.assert_awaited_once()
    conn.close()


def test_due_pvp_isolates_invalid_durable_order_and_advances_healthy_engagement():
    from game.combat_orders import submit_combat_order
    from game.pvp_world import create_preparation,lock_preparation
    from game.pvp_live import process_live_pvp_due_events
    conn,e=prepare()
    conn.execute('BEGIN IMMEDIATE')
    second=create_preparation(conn,attacker_id=4,defender_id=5,location_id='westwild_n4',now_ms=1000000)
    for engagement_id in (e,second): lock_preparation(conn,engagement_id=engagement_id,now_ms=1300000)
    submit_combat_order(encounter_kind='pvp',encounter_id=str(e),turn_revision=1,actor_id=1,
        action={'kind':'skill','skill_id':'sword_rush','target_id':777},target_id=777,
        deadline_at='1970-01-01T00:21:55+00:00',order_kind='manual',conn=conn)
    conn.commit()
    before=conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?',(e,)).fetchone()[0]
    with patch('game.pvp_live._utc_now',return_value=datetime.fromtimestamp(1315,timezone.utc)):
        events=process_live_pvp_due_events(now=datetime.fromtimestamp(1315,timezone.utc))
    assert [event['row']['id'] for event in events]==[second]
    assert conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?',(e,)).fetchone()[0]==before
    assert conn.execute("SELECT COUNT(*) FROM combat_turn_results_v1 WHERE encounter_id=?",(str(e),)).fetchone()[0]==0
    assert json.loads(conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?',(second,)).fetchone()[0])['battle']['turn_revision']==2
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_escape_closure_recovers_for_unseen_invited_and_accepted_allies(lang):
    from game.action_receipts import issue_actions
    from game.pvp_world import attempt_escape,encoded,escape_roll,invite,respond
    conn,e=prepare()
    conn.execute('BEGIN IMMEDIATE')
    invite(conn,engagement_id=e,principal_id=1,ally_id=2,now_ms=1001000)
    respond(conn,engagement_id=e,ally_id=2,accepted=True,now_ms=1002000)
    invite(conn,engagement_id=e,principal_id=777,ally_id=3,now_ms=1003000)
    conn.execute('UPDATE players SET lang=?',(lang,));conn.commit()
    revision=conn.execute('SELECT state_revision FROM pvp_engagements WHERE id=?',(e,)).fetchone()[0]
    payload=encoded({'schema_version':1,'catalog_version':2,'engagement_id':e,'state_revision':revision})
    for _ in range(256):
        token=issue_actions(1,'pvp_prep_escape',[payload])[payload]
        if escape_roll('01'*16,token): break
    assert escape_roll('01'*16,token)
    before=[tuple(r) for r in conn.execute('SELECT * FROM players ORDER BY telegram_id')]
    conn.execute('BEGIN IMMEDIATE')
    result=attempt_escape(conn,engagement_id=e,actor_id=1,token=token,now_ms=1004000)
    conn.commit()
    assert result['success']
    assert before==[tuple(r) for r in conn.execute('SELECT * FROM players ORDER BY telegram_id')]
    assert {r[0] for r in conn.execute("SELECT player_id FROM player_feedback_events WHERE event_key=?",(f'recovery:pvp:{e}:escaped',))}=={1,2,3,777}
    assert not conn.execute('SELECT 1 FROM player_pxe1_ui').fetchone()
    transport=bot()
    async def fail_one(chat_id,text,**kwargs):
        assert text==t('pxe1.encounter.pvp_escape_success',lang)
        if chat_id==2: raise RuntimeError('blocked ally')
        return SimpleNamespace(message_id=88)
    transport.send_message.side_effect=fail_one
    asyncio.run(retry_preparation_delivery(transport))
    assert conn.execute('SELECT state FROM player_feedback_events WHERE player_id=2 AND event_key=?',(f'recovery:pvp:{e}:escaped',)).fetchone()[0]=='pending'
    assert not conn.execute('SELECT 1 FROM player_pxe1_ui WHERE player_id=2').fetchone()
    transport.send_message.side_effect=None
    asyncio.run(retry_preparation_delivery(transport))
    assert conn.execute("SELECT COUNT(*) FROM player_feedback_events WHERE event_key=? AND state='pending'",(f'recovery:pvp:{e}:escaped',)).fetchone()[0]==0
    delivered=transport.send_message.await_count
    asyncio.run(retry_preparation_delivery(transport))
    assert transport.send_message.await_count==delivered
    conn.execute('BEGIN IMMEDIATE')
    assert attempt_escape(conn,engagement_id=e,actor_id=1,token=token,now_ms=999999999)==result
    conn.commit()
    assert conn.execute('SELECT COUNT(*) FROM player_feedback_events WHERE event_key=?',(f'recovery:pvp:{e}:escaped',)).fetchone()[0]==4
    conn.close()
