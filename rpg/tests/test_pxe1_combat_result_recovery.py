import asyncio,json
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

import pytest
from database import get_connection,get_player
from game.player_feedback import present_pending_feedback,inline_feedback
from game.player_ui import validate_surface
from handlers.combat_results import deliver_pending_results,result_card,handle_result_details
from tests.test_pxe1_combat_delivery import bot
from tests.test_pxe1_pvp_group_runtime import locked,submit


def test_pvp_failed_personal_death_delivery_retries_after_teammate_turn_and_restart():
    from game.pvp_live import _deliver_pxe1_pvp_event
    conn,e=locked();transport=bot()
    row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(e,)).fetchone()
    with patch('time.time',return_value=1301):
        asyncio.run(_deliver_pxe1_pvp_event(transport,{'row':row,'payload':json.loads(row['reason_context'])}))
        submit(conn,e,1,{'kind':'normal','target_id':777,'manual':True})
        status,context=submit(conn,e,2,{'kind':'guard','target_id':2,'manual':True})
        async def failed_actor(text,**kwargs):
            if kwargs['chat_id']==777: raise RuntimeError('blocked')
            return SimpleNamespace(message_id=80)
        transport.edit_message_text.side_effect=failed_actor
        asyncio.run(_deliver_pxe1_pvp_event(transport,{'row':row,'payload':context}))
        event=conn.execute("SELECT * FROM player_feedback_events WHERE player_id=777 AND source_kind='combat_result'").fetchone()
        assert event['state']=='pending'
        assert inline_feedback(777,'en','Location')[1]==[]
        status,context=submit(conn,e,3,{'kind':'guard','target_id':3,'manual':True})
        assert context['battle']['turn_revision']==3
        transport.edit_message_text.side_effect=None
        before=tuple(conn.execute('SELECT hp,mana,exp,gold,infamy FROM players WHERE telegram_id=777').fetchone())
        assert asyncio.run(present_pending_feedback(transport,777))
        assert conn.execute('SELECT state FROM player_feedback_events WHERE event_key=?',(event['event_key'],)).fetchone()[0]=='acknowledged'
        assert before==tuple(conn.execute('SELECT hp,mana,exp,gold,infamy FROM players WHERE telegram_id=777').fetchone())
        count=transport.edit_message_text.await_count
        assert not asyncio.run(deliver_pending_results(transport,player_id=777))
        assert transport.edit_message_text.await_count==count
        assert conn.execute('SELECT COUNT(*) FROM pvp_participant_settlements_pxe1').fetchone()[0]==1
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_personal_result_details_expose_all_owned_losses_and_reject_other_actor(lang):
    from game.i18n import get_item_name,t
    conn,e=locked()
    conn.execute('UPDATE players SET lang=? WHERE telegram_id=777',(lang,))
    for item in ('iron_ore','coal','gem_common'):
        conn.execute('INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (777,?,10)',(item,))
    conn.commit()
    submit(conn,e,1,{'kind':'normal','target_id':777,'manual':True})
    submit(conn,e,2,{'kind':'guard','target_id':2,'manual':True})
    event=dict(conn.execute("SELECT * FROM player_feedback_events WHERE player_id=777 AND source_kind='combat_result'").fetchone())
    with patch('time.time',return_value=1301):
        text,kb=result_card(event,dict(get_player(777)));validate_surface(text,kb)
        assert len(text.splitlines())<=10
        details=next(b.callback_data for row in kb.inline_keyboard for b in row if b.text==t('pxe1.details',lang))
        query=SimpleNamespace(data=details,from_user=SimpleNamespace(id=1),answer=AsyncMock(),edit_message_text=AsyncMock())
        asyncio.run(handle_result_details(SimpleNamespace(callback_query=query),SimpleNamespace()))
        query.edit_message_text.assert_not_awaited()
        query.from_user.id=777
        asyncio.run(handle_result_details(SimpleNamespace(callback_query=query),SimpleNamespace()))
        text=query.edit_message_text.call_args.args[0]
        for item in ('wood_common','iron_ore','coal','gem_common'):
            assert get_item_name(item,lang) in text and item not in text
        assert '777' not in text and '1301' not in text
        assert conn.execute('SELECT COUNT(*) FROM pvp_participant_settlements_pxe1').fetchone()[0]==1
    conn.close()


def test_pve_result_never_delivered_before_terminal_is_recovered_from_receipt_fact():
    from tests.test_pxe1_pve_world_tick import started
    from game.pve_live import load_active_pve_encounter,persist_solo_pve_encounter_state,_sync_v1_to_legacy_projection,process_due_pve_world_sides
    from handlers.combat_delivery import deliver_pve_updates
    encounter,_=started()
    state,mob=load_active_pve_encounter(encounter_id=encounter)
    for enemy in state['enemy_states_v1']: enemy['hp']=0;enemy['dead']=True
    _sync_v1_to_legacy_projection(state)
    assert persist_solo_pve_encounter_state(encounter_id=encounter,battle_state=state,mob=mob)
    process_due_pve_world_sides(now_ms=1014000)
    transport=bot();transport.send_message.side_effect=RuntimeError('blocked')
    with patch('time.time',return_value=1014):
        asyncio.run(deliver_pve_updates(transport,now_ms=1014000))
        conn=get_connection()
        event=conn.execute("SELECT * FROM player_feedback_events WHERE player_id=1 AND source_kind='combat_result'").fetchone()
        assert event['state']=='pending'
        assert conn.execute('SELECT 1 FROM player_pxe1_ui WHERE message_id IS NOT NULL').fetchone() is None
        transport.send_message.side_effect=None
        assert asyncio.run(present_pending_feedback(transport,1))
        assert conn.execute('SELECT state FROM player_feedback_events WHERE event_key=?',(event['event_key'],)).fetchone()[0]=='acknowledged'
        assert conn.execute('SELECT COUNT(*) FROM pve_reward_settlements').fetchone()[0]==1
        conn.close()


def test_successful_result_transport_then_ack_failure_keeps_visible_detail_tokens():
    conn,e=locked(defenders=1);transport=bot()
    submit(conn,e,1,{'kind':'normal','target_id':777,'manual':True})
    submit(conn,e,2,{'kind':'guard','target_id':2,'manual':True})
    with patch('time.time',return_value=1301):
        with patch('game.player_feedback.acknowledge_presented_facts',side_effect=RuntimeError('ack failed')):
            assert not asyncio.run(deliver_pending_results(transport,player_id=777))
        tokens=[r[0] for r in conn.execute("SELECT token FROM player_ui_actions WHERE player_id=777 AND kind='pxe1_combat_result'")]
        assert tokens
        assert asyncio.run(deliver_pending_results(transport,player_id=777))
        assert transport.send_message.await_count==1 and transport.edit_message_text.await_count==0
        assert [r[0] for r in conn.execute("SELECT token FROM player_ui_actions WHERE player_id=777 AND kind='pxe1_combat_result'")]==tokens
        assert not asyncio.run(deliver_pending_results(transport,player_id=777))
    conn.close()


def test_simultaneous_death_receipts_capture_whole_batch_personal_infamy():
    from game.pvp_group_runtime import settle_deaths
    conn,e=locked(defenders=1)
    row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(e,)).fetchone()
    context=json.loads(row['reason_context'])
    for actor_id in ('1','777'):
        context['battle']['participants_v1'][actor_id].update(hp=0,dead=True)
    context['battle']['damage_by_source']={'1':{'777':10},'777':{'1':10}}
    conn.execute('BEGIN IMMEDIATE')
    deaths=settle_deaths(conn,row,context,turn_revision=1,now_ms=1301000)
    conn.commit()
    own=next(d for d in deaths if d['player_id']==1)
    credited=next(d for d in deaths if d['credited_actor_id']==1)
    assert own['personal_infamy_delta']==context['crime_context']['1']['initiation_infamy']+credited['infamy_delta']
    assert json.loads(conn.execute('SELECT result_json FROM pvp_participant_settlements_pxe1 WHERE player_id=1').fetchone()[0])==own
    conn.close()
