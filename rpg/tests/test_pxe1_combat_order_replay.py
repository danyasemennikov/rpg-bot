import asyncio,json
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

import pytest
from database import get_connection,get_player
from game.combat_orders import consume_combat_intent,issue_combat_intents,recover_combat_intent
from game.player_ui import validate_surface
from tests.test_pxe1_pve_world_tick import started
from tests.test_pxe1_pvp_group_runtime import locked


def issue(kind):
    if kind=='pve':
        encounter,_=started()
        from game.pve_live import load_active_pve_encounter
        state,_=load_active_pve_encounter(encounter_id=encounter)
        actor,second=1,1013
        action={'kind':'guard','target_info':{'kind':'self','id':1}}
    else:
        conn,encounter=locked()
        state=json.loads(conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?',(encounter,)).fetchone()[0])['battle']
        conn.close()
        actor,second=2,1301
        action={'kind':'guard','target_id':actor,'manual':True}
    with patch('time.time',return_value=second):
        tokens=issue_combat_intents(actor,encounter_id=str(encounter),turn_revision=state['turn_revision'],
            deadline_at=state['side_deadline_at'],actions=[action],encounter_kind=kind)
    return encounter,actor,second,next(iter(tokens.values()))


def consume(actor,token,second):
    with patch('time.time',return_value=second),patch('game.combat_orders.datetime') as clock:
        clock.fromisoformat.side_effect=datetime.fromisoformat
        clock.now.return_value=datetime.fromtimestamp(second,timezone.utc)
        return consume_combat_intent(actor,token)


@pytest.mark.parametrize('kind',['pve','pvp'])
def test_order_ack_is_immutable_after_move_deadline_and_token_cleanup(kind):
    encounter,actor,second,token=issue(kind)
    first=consume(actor,token,second)
    assert first['accepted']
    conn=get_connection()
    order=conn.execute('SELECT * FROM combat_orders_v1 WHERE encounter_kind=? AND encounter_id=?',(kind,str(encounter))).fetchone()
    before=tuple(conn.execute('SELECT hp,mana,exp,gold,infamy FROM players WHERE telegram_id=?',(actor,)).fetchone())
    conn.execute('DELETE FROM player_ui_actions WHERE player_id=?',(actor,))
    conn.execute("UPDATE players SET location_id='capital_city',travel_revision=travel_revision+1 WHERE telegram_id=?",(actor,))
    conn.commit()
    assert consume(actor,token,second+100000)=={**first,'already_applied':True}
    assert recover_combat_intent(actor,token)=={**first,'already_applied':True}
    assert recover_combat_intent(777,token) is None
    assert before==tuple(conn.execute('SELECT hp,mana,exp,gold,infamy FROM players WHERE telegram_id=?',(actor,)).fetchone())
    assert tuple(order)==tuple(conn.execute('SELECT * FROM combat_orders_v1 WHERE encounter_kind=? AND encounter_id=?',(kind,str(encounter))).fetchone())
    result=json.loads(conn.execute('SELECT result_json FROM economy_action_receipts WHERE player_id=? AND request_id=?',(actor,'ui:'+token)).fetchone()[0])
    assert result['gold_delta']==0 and result['granted']==[] and result['progression']==[]
    conn.close()


@pytest.mark.parametrize('kind',['pve','pvp'])
def test_ack_insert_failure_rolls_back_order_and_consumption(kind):
    encounter,actor,second,token=issue(kind)
    with patch('game.economy_actions.store_receipt',side_effect=RuntimeError('injected')):
        with pytest.raises(RuntimeError,match='injected'): consume(actor,token,second)
    conn=get_connection()
    assert not conn.execute('SELECT 1 FROM combat_orders_v1 WHERE encounter_id=?',(str(encounter),)).fetchone()
    assert conn.execute('SELECT used FROM player_ui_actions WHERE token=?',(token,)).fetchone()[0]==0
    conn.close()
    assert consume(actor,token,second)['accepted']


@pytest.mark.parametrize('kind',['pve','pvp'])
def test_consumed_callback_acknowledges_without_executing_another_side_or_clearing_busy(kind):
    encounter,actor,second,token=issue(kind)
    assert consume(actor,token,second)['accepted']
    conn=get_connection()
    conn.execute('DELETE FROM player_ui_actions WHERE player_id=?',(actor,));conn.commit()
    before=tuple(conn.execute('SELECT hp,mana,exp,gold,in_battle FROM players WHERE telegram_id=?',(actor,)).fetchone())
    query=SimpleNamespace(from_user=SimpleNamespace(id=actor),data=('battle_v1_' if kind=='pve' else 'pvp_v1_')+token,
        answer=AsyncMock(),edit_message_text=AsyncMock(),message=SimpleNamespace(chat_id=actor,message_id=80))
    context=SimpleNamespace(user_data={},bot=SimpleNamespace(send_message=AsyncMock(),edit_message_text=AsyncMock()))
    if kind=='pve':
        from handlers.battle import handle_battle_buttons
        with patch('game.pve_live._utc_now',return_value=datetime.fromtimestamp(second,timezone.utc)),patch('time.time',return_value=second):
            asyncio.run(handle_battle_buttons(SimpleNamespace(callback_query=query),context))
    else:
        from handlers.location import handle_location_buttons
        with patch('game.pvp_live._utc_now',return_value=datetime.fromtimestamp(second,timezone.utc)),patch('time.time',return_value=second):
            asyncio.run(handle_location_buttons(SimpleNamespace(callback_query=query),context))
    assert before==tuple(conn.execute('SELECT hp,mana,exp,gold,in_battle FROM players WHERE telegram_id=?',(actor,)).fetchone())
    assert not conn.execute('SELECT 1 FROM combat_turn_results_v1 WHERE encounter_id=?',(str(encounter),)).fetchone()
    query.answer.assert_awaited_once()
    assert not query.answer.call_args.kwargs.get('show_alert')
    validate_surface(query.edit_message_text.call_args.args[0],query.edit_message_text.call_args.kwargs['reply_markup'])
    if kind=='pve':
        surface=conn.execute('SELECT * FROM player_pxe1_ui WHERE player_id=?',(actor,)).fetchone()
        assert surface['surface_kind']=='pve' and surface['surface_ref']==encounter
        assert surface['chat_id']==actor and surface['message_id']==80
    conn.close()


def test_unknown_old_battle_callback_cannot_clear_current_pvp_or_cooldowns():
    conn,e=locked()
    conn.execute("INSERT OR REPLACE INTO skill_cooldowns(telegram_id,skill_id,turns_left) VALUES (1,'power_strike',3)")
    conn.commit()
    before=tuple(conn.execute('SELECT hp,mana,in_battle FROM players WHERE telegram_id=1').fetchone())
    query=SimpleNamespace(from_user=SimpleNamespace(id=1),data='battle_v1_missing',answer=AsyncMock(),edit_message_text=AsyncMock())
    from handlers.battle import handle_battle_buttons
    asyncio.run(handle_battle_buttons(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={})))
    assert before==tuple(conn.execute('SELECT hp,mana,in_battle FROM players WHERE telegram_id=1').fetchone())
    assert conn.execute("SELECT turns_left FROM skill_cooldowns WHERE telegram_id=1 AND skill_id='power_strike'").fetchone()[0]==3
    assert conn.execute('SELECT engagement_state FROM pvp_engagements WHERE id=?',(e,)).fetchone()[0]=='converted_to_battle'
    conn.close()


@pytest.mark.parametrize('invalid',['no_mana','cooldown','target_gone'])
def test_pve_order_revalidates_snapshot_resources_and_explicit_target_under_writer(invalid):
    encounter,_=started()
    from game.pve_live import load_active_pve_encounter
    state,_=load_active_pve_encounter(encounter_id=encounter)
    enemy=state['enemy_states_v1'][0]['unit_id']
    action={'kind':'skill','skill_id':'power_strike','target_info':{'id':enemy}}
    conn=get_connection()
    if invalid=='no_mana': state['participant_states_v1']['1']['mana']=0
    elif invalid=='cooldown': state['participant_states_v1']['1']['cooldowns']['power_strike']=2
    else: action['target_info']['id']='missing-target'
    conn.execute('UPDATE pve_encounters SET battle_state_json=? WHERE encounter_id=?',(json.dumps(state),encounter));conn.commit()
    with patch('time.time',return_value=1013):
        token=next(iter(issue_combat_intents(1,encounter_id=encounter,turn_revision=state['turn_revision'],
            deadline_at=state['side_deadline_at'],actions=[action]).values()))
    result=consume(1,token,1013)
    assert not result['accepted']
    assert not conn.execute('SELECT 1 FROM combat_orders_v1 WHERE encounter_id=?',(encounter,)).fetchone()
    assert conn.execute('SELECT used FROM player_ui_actions WHERE token=?',(token,)).fetchone()[0]==0
    assert json.loads(conn.execute('SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0])==state
    conn.close()


def test_consumed_order_refresh_keeps_prior_delivery_coordinates_when_transport_fails():
    from game.player_ui import record_surface
    from handlers.battle import handle_battle_buttons
    encounter,actor,second,token=issue('pve')
    assert consume(actor,token,second)['accepted']
    record_surface(actor,kind='pve',ref=encounter,revision=1,chat_id=actor,message_id=35)
    conn=get_connection()
    before=tuple(conn.execute('SELECT * FROM player_pxe1_ui WHERE player_id=?',(actor,)).fetchone())
    query=SimpleNamespace(from_user=SimpleNamespace(id=actor),data='battle_v1_'+token,
        answer=AsyncMock(),edit_message_text=AsyncMock(side_effect=RuntimeError('offline')),
        message=SimpleNamespace(chat_id=actor,message_id=80))
    with patch('time.time',return_value=second):
        with pytest.raises(RuntimeError,match='offline'):
            asyncio.run(handle_battle_buttons(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={})))
    assert before==tuple(conn.execute('SELECT * FROM player_pxe1_ui WHERE player_id=?',(actor,)).fetchone())
    assert conn.execute('SELECT COUNT(*) FROM combat_orders_v1 WHERE encounter_id=?',(encounter,)).fetchone()[0]==1
    assert not conn.execute('SELECT 1 FROM combat_turn_results_v1 WHERE encounter_id=?',(encounter,)).fetchone()
    conn.close()
