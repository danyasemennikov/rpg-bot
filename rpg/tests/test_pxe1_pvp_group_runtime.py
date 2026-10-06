import hashlib
import json
from unittest.mock import patch

import pytest
from database import get_connection
from game.action_receipts import ActionRejected
from game.combat_orders import replay_turn_result
from game.pvp_group_runtime import authorize_order, resolve_group_turn
from game.pvp_live import get_pending_player_engagement, is_player_busy_with_live_pvp
from game.pvp_world import encoded, invite, lock_preparation, respond
from tests.test_pxe1_pvp_membership import prepare


def locked(*, defenders=2):
    conn,e = prepare()
    conn.execute('BEGIN IMMEDIATE')
    invite(conn,engagement_id=e,principal_id=1,ally_id=2,now_ms=1001000)
    respond(conn,engagement_id=e,ally_id=2,accepted=True,now_ms=1002000)
    if defenders==2:
        invite(conn,engagement_id=e,principal_id=777,ally_id=3,now_ms=1001000)
        respond(conn,engagement_id=e,ally_id=3,accepted=True,now_ms=1002000)
    lock_preparation(conn,engagement_id=e,now_ms=1300000)
    context = json.loads(conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?',(e,)).fetchone()[0])
    for actor in context['battle']['participants_v1'].values():
        actor['accuracy']=100000
        actor['evasion']=0
        actor['physical_defense']=0
        actor['block_chance']=0
    context['battle']['participants_v1']['777']['hp']=1
    conn.execute('UPDATE pvp_engagements SET reason_context=? WHERE id=?',(encoded(context),e))
    conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (777,'wood_common',5),(777,'wood_common',6),(777,'health_potion_small',2)")
    conn.commit()
    return conn,e


def submit(conn,e,actor,action,now=1301000,**kwargs):
    conn.execute('BEGIN IMMEDIATE')
    result = resolve_group_turn(conn,engagement_id=e,actor_id=actor,action=action,now_ms=now,**kwargs)
    conn.commit()
    return result


def test_full_batch_dead_target_guard_and_individual_respawn():
    conn,e = locked()
    assert submit(conn,e,1,{'kind':'normal','target_id':777,'manual':True})[0]=='waiting'
    state,context = submit(conn,e,2,{'kind':'skill','skill_id':'power_strike','target_id':777,'manual':True})
    assert state=='resolved'
    battle = context['battle']
    assert battle['active_side']=='side_b'
    assert any(event['kind']=='target_dead_guard' and event['actor_id']==2 for event in battle['events_v1'])
    assert battle['participants_v1']['2']['mana']==100
    assert battle['damage_by_source']['777']['1']==1  # No overkill credit.
    death = json.loads(conn.execute('SELECT result_json FROM pvp_participant_settlements_pxe1 WHERE player_id=777').fetchone()[0])
    assert death['loss_pool']=={'wood_common':6}
    victim = conn.execute('SELECT * FROM players WHERE telegram_id=777').fetchone()
    assert victim['hp']==30 and victim['mana']==100
    assert victim['location_id']=='hub_westwild'
    assert victim['pvp_respawn_protection_until']==1781
    assert victim['in_battle']==0
    assert not is_player_busy_with_live_pvp(777)
    assert get_pending_player_engagement(3)['id']==e
    assert is_player_busy_with_live_pvp(3)
    assert not conn.execute('SELECT 1 FROM pvp_group_settlements_pxe1').fetchone()
    assert replay_turn_result(encounter_kind='pvp',encounter_id=str(e),turn_revision=1)['result']['deaths'][0]['player_id']==777
    conn.close()


def test_terminal_split_conservation_receipts_and_no_progression():
    conn,e = locked(defenders=1)
    before = {r['telegram_id']:(r['exp'],r['gold']) for r in conn.execute('SELECT telegram_id,exp,gold FROM players')}
    assert submit(conn,e,1,{'kind':'normal','target_id':777,'manual':True})[0]=='waiting'
    state,context = submit(conn,e,2,{'kind':'guard','target_id':2,'manual':True})
    assert state=='finished'
    result = json.loads(conn.execute('SELECT result_json FROM pvp_group_settlements_pxe1 WHERE engagement_id=?',(e,)).fetchone()[0])
    assert result['eligible_recipients']==[1,2]
    assert sum(g['quantity'] for g in result['grants'])==6
    assert result['destroyed']==[]
    assert {g['recipient_id']:g['quantity'] for g in result['grants']}=={1:3,2:3}
    assert len(result['relationships'])==1
    assert conn.execute('SELECT COUNT(*) FROM pvp_log').fetchone()[0]==2
    assert {r['telegram_id']:(r['exp'],r['gold']) for r in conn.execute('SELECT telegram_id,exp,gold FROM players')}==before
    assert conn.execute("SELECT quantity FROM inventory WHERE telegram_id=777 AND item_id='health_potion_small'").fetchone()[0]==2
    assert not any(r[0] for r in conn.execute('SELECT in_battle FROM players'))
    # Terminal retries cannot debit/grant/log again.
    assert submit(conn,e,None,None,now=999999999)[0]=='not_live'
    assert conn.execute('SELECT COUNT(*) FROM pvp_log').fetchone()[0]==2
    conn.close()


def test_atomic_death_group_and_side_receipt_rollback():
    conn,e = locked(defenders=1)
    submit(conn,e,1,{'kind':'normal','target_id':777,'manual':True})
    before = conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?',(e,)).fetchone()[0]
    def fail(stage):
        if stage=='after_side_result':
            raise RuntimeError('injected')
    conn.execute('BEGIN IMMEDIATE')
    with pytest.raises(RuntimeError,match='injected'):
        resolve_group_turn(conn,engagement_id=e,actor_id=2,action={'kind':'guard','target_id':2,'manual':True},now_ms=1301000,failure_hook=fail)
    conn.rollback()
    assert conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?',(e,)).fetchone()[0]==before
    assert not conn.execute('SELECT 1 FROM pvp_participant_settlements_pxe1').fetchone()
    assert not conn.execute('SELECT 1 FROM pvp_group_settlements_pxe1').fetchone()
    assert not conn.execute('SELECT 1 FROM pvp_log').fetchone()
    assert conn.execute("SELECT SUM(quantity) FROM inventory WHERE telegram_id=777 AND item_id='wood_common'").fetchone()[0]==11
    assert submit(conn,e,2,{'kind':'guard','target_id':2,'manual':True})[0]=='finished'
    conn.close()


def test_timeout_all_missing_orders_and_effect_tick_once_after_batch():
    conn,e = locked()
    context = json.loads(conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?',(e,)).fetchone()[0])
    for actor_id in ('1','2'):
        context['battle']['participants_v1'][actor_id]['effects']=[{'kind':'burn','source_id':777,'duration':3,'raw_tick':3,'created_side_index':0,'school':'magic','metadata':{'source_level':20}}]
    conn.execute('UPDATE pvp_engagements SET reason_context=? WHERE id=?',(encoded(context),e))
    conn.commit()
    state,context = submit(conn,e,None,None,now=1315000)
    assert state=='resolved'
    assert len([v for v in context['battle']['events_v1'] if v['kind']=='dot'])==2
    for actor_id in ('1','2'):
        assert context['battle']['participants_v1'][actor_id]['effects'][0]['duration']==2
    assert context['battle']['manual_actor_ids']==[]
    assert conn.execute('SELECT COUNT(*) FROM combat_orders_v1').fetchone()[0]==2
    conn.close()


def test_authorization_living_locked_side_and_invalid_provenance():
    conn,e = locked()
    row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(e,)).fetchone()
    battle = json.loads(row['reason_context'])['battle']
    authorize_order(conn,row,battle,2,{'kind':'guard','target_id':2})
    for outsider in (3,4,777):
        with pytest.raises(ActionRejected,match='not_your_turn'):
            authorize_order(conn,row,battle,outsider,{'kind':'guard','target_id':outsider})
    battle['participants_v1']['1']['effects']=[{'kind':'burn','source_id':9999,'duration':3,'raw_tick':200,'created_side_index':0,'school':'magic','metadata':{}}]
    context = json.loads(row['reason_context'])
    context['battle']=battle
    conn.execute('UPDATE pvp_engagements SET reason_context=? WHERE id=?',(encoded(context),e))
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    with pytest.raises(ActionRejected,match='invalid_damage_provenance'):
        resolve_group_turn(conn,engagement_id=e,now_ms=1315000)
    conn.rollback()
    assert not conn.execute('SELECT 1 FROM pvp_participant_settlements_pxe1').fetchone()
    conn.close()
