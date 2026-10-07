import json
from datetime import datetime,timezone

import pytest
from database import get_connection
from game.pvp_live import process_live_pvp_due_events,is_player_busy_with_live_pvp
from game.pvp_world import create_preparation,lock_preparation,encoded
from tests.test_pxe1_pvp_group_runtime import locked,submit


@pytest.mark.parametrize('corruption',['json','roster','missing_actor','missing_ally','deadline'])
def test_corrupt_active_pvp_releases_owned_members_preserves_death_and_advances_neighbor(corruption):
    conn,e=locked()
    submit(conn,e,1,{'kind':'normal','target_id':777,'manual':True})
    submit(conn,e,2,{'kind':'guard','target_id':2,'manual':True})
    death=conn.execute('SELECT result_json FROM pvp_participant_settlements_pxe1 WHERE engagement_id=?',(e,)).fetchone()[0]
    before={r['telegram_id']:tuple(r)[1:] for r in conn.execute('SELECT telegram_id,hp,mana,location_id,exp,gold,infamy FROM players')}
    inventory=[tuple(r) for r in conn.execute('SELECT * FROM inventory ORDER BY id')]
    conn.execute('BEGIN IMMEDIATE')
    other=create_preparation(conn,attacker_id=4,defender_id=5,location_id='westwild_n4',now_ms=1000000)
    lock_preparation(conn,engagement_id=other,now_ms=1300000)
    row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(e,)).fetchone()
    context=json.loads(row['reason_context'])
    if corruption=='json':
        conn.execute("UPDATE pvp_engagements SET reason_context='not-json' WHERE id=?",(e,))
    elif corruption=='roster':
        conn.execute("UPDATE pvp_engagements SET locked_roster_json='[]' WHERE id=?",(e,))
    else:
        if corruption=='missing_actor': del context['battle']['participants_v1']['2']
        elif corruption=='missing_ally':
            roster=json.loads(row['locked_roster_json']);roster['side_a']=roster['side_a'][:1]
            conn.execute('UPDATE pvp_engagements SET locked_roster_json=? WHERE id=?',(encoded(roster),e))
            del context['battle']['participants_v1']['2']
        else: context['battle']['side_deadline_at']='invalid-date'
        conn.execute('UPDATE pvp_engagements SET reason_context=? WHERE id=?',(encoded(context),e))
    raw=conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?',(e,)).fetchone()[0]
    conn.commit()
    events=process_live_pvp_due_events(now=datetime.fromtimestamp(1360,timezone.utc))
    assert [event['row']['id'] for event in events]==[other]
    row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(e,)).fetchone()
    assert row['engagement_state']=='cancelled'
    assert json.loads(row['reason_context'])['quarantined_reason_context']==raw
    assert conn.execute('SELECT result_json FROM pvp_participant_settlements_pxe1 WHERE engagement_id=?',(e,)).fetchone()[0]==death
    assert inventory==[tuple(r) for r in conn.execute('SELECT * FROM inventory ORDER BY id')]
    after={r['telegram_id']:tuple(r)[1:] for r in conn.execute('SELECT telegram_id,hp,mana,location_id,exp,gold,infamy FROM players')}
    assert before==after
    assert not any(is_player_busy_with_live_pvp(p) for p in (1,2,3,777))
    assert not any(conn.execute('SELECT in_battle FROM players WHERE telegram_id=?',(p,)).fetchone()[0] for p in (1,2,3,777))
    assert conn.execute("SELECT COUNT(*) FROM player_feedback_events WHERE source_kind='pvp' AND source_id=? AND event_kind='recovery'",(str(e),)).fetchone()[0]==4
    assert not conn.execute('SELECT 1 FROM pvp_group_settlements_pxe1 WHERE engagement_id=?',(e,)).fetchone()
    process_live_pvp_due_events(now=datetime.fromtimestamp(1360,timezone.utc))
    assert conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?',(e,)).fetchone()[0]==row['reason_context']
    conn.close()


def test_quarantine_does_not_release_other_owned_combat():
    from game.pvp_group_runtime import quarantine_live_group
    conn,e=locked()
    conn.execute('BEGIN IMMEDIATE')
    other=create_preparation(conn,attacker_id=4,defender_id=5,location_id='westwild_n4',now_ms=1000000)
    # Reproduce an impossible saved overlap for the recovery owner.
    conn.execute('UPDATE pvp_engagements SET attacker_id=1 WHERE id=?',(other,))
    row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(e,)).fetchone()
    quarantine_live_group(conn,row,reason='corrupt_live_state',now_ms=1315000)
    conn.commit()
    assert conn.execute('SELECT in_battle FROM players WHERE telegram_id=1').fetchone()[0]==1
    assert is_player_busy_with_live_pvp(1)
    assert conn.execute('SELECT engagement_state FROM pvp_engagements WHERE id=?',(other,)).fetchone()[0]=='pending'
    conn.close()


@pytest.mark.parametrize('stop',[False,True])
def test_gather_without_deadline_interrupts_without_yield_or_wear(stop):
    from tests.test_pxe1_gathering_sessions import start
    from game.gathering_runtime import stop_gathering_session
    from game.world_activity_tick import run_world_activity_tick
    conn,session=start()
    conn.execute('UPDATE player_gathering_sessions SET next_due_ms=NULL WHERE session_id=?',(session,));conn.commit()
    if stop:
        conn.execute('BEGIN IMMEDIATE');stop_gathering_session(conn,1,session,now_ms=9000);conn.commit()
    else: run_world_activity_tick(now_ms=9000)
    assert conn.execute('SELECT status FROM player_gathering_sessions WHERE session_id=?',(session,)).fetchone()[0]=='interrupted'
    assert conn.execute("SELECT durability FROM player_profession_tools WHERE player_id=1 AND profession_key='mining'").fetchone()[0]==60
    assert not conn.execute('SELECT 1 FROM inventory WHERE telegram_id=1').fetchone()
    assert not conn.execute("SELECT 1 FROM economy_action_receipts WHERE action_kind='gather_tick_pxe1'").fetchone()
    assert conn.execute('SELECT state FROM player_feedback_events WHERE event_key=?',('recovery:gather:'+session,)).fetchone()[0]=='pending'
    conn.close()


@pytest.mark.parametrize('corruption',['battle_json','declaration_shape','deadline','missing_reservation'])
def test_corrupt_formation_interrupts_locally_without_private_runtime_or_rewards(corruption):
    from tests.test_pxe1_encounter_lifecycle import prepare
    from game.pve_live import process_due_pve_formations
    encounter,_=prepare()
    conn=get_connection()
    before=tuple(conn.execute('SELECT hp,mana,location_id,exp,gold FROM players WHERE telegram_id=1').fetchone())
    if corruption=='battle_json': conn.execute("UPDATE pve_encounters SET battle_state_json='not-json' WHERE encounter_id=?",(encounter,))
    elif corruption=='declaration_shape': conn.execute("UPDATE pve_encounters SET source_units_json='{\"units\":[7]}' WHERE encounter_id=?",(encounter,))
    elif corruption=='deadline': conn.execute('UPDATE pve_encounters SET formation_deadline_ms=NULL WHERE encounter_id=?',(encounter,))
    else: conn.execute("UPDATE pve_spawn_instances SET linked_encounter_id=NULL,state='idle' WHERE linked_encounter_id=?",(encounter,))
    conn.commit()
    deadline=conn.execute('SELECT formation_deadline_ms FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0] or 0
    results=process_due_pve_formations(now_ms=deadline+1)
    assert results==[{'phase':'start_failed','player_ids':[],'encounter_id':encounter}]
    row=conn.execute('SELECT * FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()
    assert row['status']=='start_failed' and row['runtime_started_ms'] is None
    assert before==tuple(conn.execute('SELECT hp,mana,location_id,exp,gold FROM players WHERE telegram_id=1').fetchone())
    assert not conn.execute('SELECT 1 FROM pve_spawn_instances WHERE linked_encounter_id=?',(encounter,)).fetchone()
    assert not conn.execute('SELECT 1 FROM pve_reward_settlements WHERE encounter_id=?',(encounter,)).fetchone()
    assert conn.execute("SELECT COUNT(*) FROM player_feedback_events WHERE source_kind='pve' AND source_id=?",(encounter,)).fetchone()[0]==1
    assert process_due_pve_formations(now_ms=deadline+999999)==[]
    conn.close()
