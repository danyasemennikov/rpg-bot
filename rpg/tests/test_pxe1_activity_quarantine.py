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


@pytest.mark.parametrize('corruption',['json','roster','actor','enemy','deadline'])
def test_corrupt_active_pve_interrupts_with_owned_respawn_and_preserves_player_state(corruption):
    from tests.test_pxe1_pve_world_tick import started
    from game.pve_live import process_due_pve_world_sides
    encounter,source=started()
    conn=get_connection()
    row=conn.execute('SELECT * FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()
    if corruption=='json': raw='not-json'
    else:
        state=json.loads(row['battle_state_json'])
        if corruption=='actor': del state['participant_states_v1']['1']
        elif corruption=='enemy': state['enemy_states_v1']=[7]
        elif corruption=='deadline': state['side_deadline_at']='invalid-date'
        raw=json.dumps(state)
    conn.execute('UPDATE pve_encounters SET battle_state_json=? WHERE encounter_id=?',(raw,encounter))
    if corruption=='roster': conn.execute("UPDATE pve_encounters SET locked_roster_json='[]' WHERE encounter_id=?",(encounter,))
    conn.commit()
    before=tuple(conn.execute('SELECT hp,mana,location_id,exp,gold,build_revision,gear_revision FROM players WHERE telegram_id=1').fetchone())
    results=process_due_pve_world_sides(now_ms=1013000)
    assert results==[{'encounter_id':encounter,'phase':'state_lost'}]
    row=conn.execute('SELECT * FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()
    assert row['status']=='state_lost' and row['battle_state_json']==raw
    assert before==tuple(conn.execute('SELECT hp,mana,location_id,exp,gold,build_revision,gear_revision FROM players WHERE telegram_id=1').fetchone())
    assert conn.execute('SELECT in_battle FROM players WHERE telegram_id=1').fetchone()[0]==0
    assert not conn.execute('SELECT 1 FROM pve_reward_settlements WHERE encounter_id=?',(encounter,)).fetchone()
    spawn=conn.execute('SELECT * FROM pve_spawn_instances WHERE spawn_instance_id=?',(source['spawn_instance_id'],)).fetchone()
    assert spawn['state']=='respawning' and spawn['linked_encounter_id'] is None
    assert spawn['respawn_available_at']=='1970-01-01 00:17:23'
    assert conn.execute("SELECT COUNT(*) FROM player_feedback_events WHERE source_kind='pve' AND source_id=? AND event_kind='recovery'",(encounter,)).fetchone()[0]==1
    assert process_due_pve_world_sides(now_ms=1014000)==[]
    conn.close()


@pytest.mark.parametrize('owner_id',[1,2])
def test_startup_preserves_active_pve_over_future_pvp_principal_or_ally_commitment(owner_id):
    from unittest.mock import patch
    from game.build_progression import migrate_character_builds_v1
    from game.mobs import get_mob
    from game.pve_live import create_or_load_open_world_pve_encounter,list_location_available_spawn_instances,process_due_pve_formations
    from game.pvp_world import invite,respond
    from game.player_activity import recover_activity_overlaps
    from tests.test_pxe1_pvp_membership import prepare
    conn,engagement=prepare()
    conn.execute('BEGIN IMMEDIATE')
    invite(conn,engagement_id=engagement,principal_id=1,ally_id=2,now_ms=1001000)
    respond(conn,engagement_id=engagement,ally_id=2,accepted=True,now_ms=1002000)
    # Create both real owners, then restore the impossible saved overlap.
    conn.execute("UPDATE pvp_engagements SET engagement_state='cancelled' WHERE id=?",(engagement,))
    conn.execute("UPDATE players SET location_id='westwild_n1' WHERE telegram_id=?",(owner_id,))
    conn.commit()
    migrate_character_builds_v1()
    spawn=next(s for s in list_location_available_spawn_instances(location_id='westwild_n1') if s['mob_id']=='westwild_rabbit')
    with patch('time.time',return_value=1000):
        encounter,status=create_or_load_open_world_pve_encounter(owner_player_id=owner_id,location_id='westwild_n1',mob_id='westwild_rabbit',
            spawn_instance_id=spawn['spawn_instance_id'],battle_state={'mob_id':'westwild_rabbit','mob_hp':20,'mob_max_hp':20,'player_hp':100,'player_mana':100},mob=get_mob('westwild_rabbit'))
    assert status=='created'
    process_due_pve_formations(now_ms=1012000)
    conn.execute("UPDATE pvp_engagements SET engagement_state='pending' WHERE id=?",(engagement,));conn.commit()
    before=tuple(conn.execute('SELECT * FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone())
    player_before=tuple(conn.execute('SELECT * FROM players WHERE telegram_id=?',(owner_id,)).fetchone())
    receipts=list(conn.execute('SELECT * FROM economy_action_receipts'))
    conn.execute('BEGIN IMMEDIATE');recover_activity_overlaps(conn,now_ms=1013000);conn.commit()
    assert before==tuple(conn.execute('SELECT * FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone())
    assert player_before==tuple(conn.execute('SELECT * FROM players WHERE telegram_id=?',(owner_id,)).fetchone())
    assert receipts==list(conn.execute('SELECT * FROM economy_action_receipts'))
    row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(engagement,)).fetchone()
    assert row['engagement_state']==('cancelled' if owner_id==1 else 'pending')
    assert conn.execute('SELECT status FROM pvp_engagement_reinforcements WHERE engagement_id=? AND ally_id=2',(engagement,)).fetchone()[0]=='expired'
    revision=row['state_revision']
    conn.execute('BEGIN IMMEDIATE');recover_activity_overlaps(conn,now_ms=1014000);conn.commit()
    assert conn.execute('SELECT state_revision FROM pvp_engagements WHERE id=?',(engagement,)).fetchone()[0]==revision
    conn.close()


def test_startup_preserves_live_pvp_over_future_owned_pve_formation():
    from game.player_activity import recover_activity_overlaps
    from tests.test_pxe1_encounter_lifecycle import prepare
    encounter,spawn=prepare()
    conn=get_connection()
    conn.execute("UPDATE pve_encounters SET status='abandoned' WHERE encounter_id=?",(encounter,));conn.commit();conn.close()
    conn,engagement=locked()
    conn.execute("UPDATE pve_encounters SET status='active',formation_deadline_ms=9999999999 WHERE encounter_id=?",(encounter,));conn.commit()
    before=tuple(conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(engagement,)).fetchone())
    players=[tuple(r) for r in conn.execute('SELECT * FROM players ORDER BY telegram_id')]
    receipts=[tuple(r) for r in conn.execute('SELECT * FROM economy_action_receipts')]
    conn.execute('BEGIN IMMEDIATE');recover_activity_overlaps(conn,now_ms=1301000);conn.commit()
    assert before==tuple(conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(engagement,)).fetchone())
    assert players==[tuple(r) for r in conn.execute('SELECT * FROM players ORDER BY telegram_id')]
    assert receipts==[tuple(r) for r in conn.execute('SELECT * FROM economy_action_receipts')]
    assert conn.execute('SELECT status FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0]=='start_failed'
    source=conn.execute('SELECT * FROM pve_spawn_instances WHERE spawn_instance_id=?',(spawn['spawn_instance_id'],)).fetchone()
    assert source['state']=='idle' and source['linked_encounter_id'] is None
    assert conn.execute("SELECT COUNT(*) FROM player_feedback_events WHERE source_kind='pve' AND source_id=?",(encounter,)).fetchone()[0]==1
    conn.close()


def test_invalid_terminal_pve_outcome_quarantines_owned_sources_without_reward():
    from game.pve_live import _sync_v1_to_legacy_projection,load_active_pve_encounter,persist_solo_pve_encounter_state,process_due_pve_world_sides
    from tests.test_pxe1_pve_world_tick import started
    encounter,source=started()
    state,mob=load_active_pve_encounter(encounter_id=encounter)
    for enemy in state['enemy_states_v1']:
        enemy.update(hp=0,dead=True)
    _sync_v1_to_legacy_projection(state)
    assert persist_solo_pve_encounter_state(encounter_id=encounter,battle_state=state,mob=mob)
    conn=get_connection()
    declaration=json.loads(conn.execute('SELECT source_units_json FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0])
    declaration['units'][0]['spawn_instance_id']='another-encounters-source'
    conn.execute('UPDATE pve_encounters SET source_units_json=? WHERE encounter_id=?',(json.dumps(declaration),encounter));conn.commit()
    before=tuple(conn.execute('SELECT * FROM players WHERE telegram_id=1').fetchone())
    assert process_due_pve_world_sides(now_ms=1013000)==[{'encounter_id':encounter,'phase':'state_lost'}]
    after=tuple(conn.execute('SELECT * FROM players WHERE telegram_id=1').fetchone())
    columns=[d[0] for d in conn.execute('SELECT * FROM players').description]
    assert {k:v for k,v in zip(columns,before) if k!='in_battle'}=={k:v for k,v in zip(columns,after) if k!='in_battle'}
    assert not conn.execute('SELECT 1 FROM pve_reward_settlements WHERE encounter_id=?',(encounter,)).fetchone()
    assert conn.execute('SELECT state FROM pve_spawn_instances WHERE spawn_instance_id=?',(source['spawn_instance_id'],)).fetchone()[0]=='respawning'
    conn.close()


def test_active_pve_recovery_failure_rolls_back_every_owned_transition_and_retries():
    from unittest.mock import patch
    from game.pve_live import process_due_pve_world_sides
    from tests.test_pxe1_pve_world_tick import started
    encounter,source=started()
    conn=get_connection();conn.execute("UPDATE pve_encounters SET battle_state_json='corrupt' WHERE encounter_id=?",(encounter,));conn.commit()
    tables=('players','pve_encounters','pve_encounter_participants','pve_spawn_instances','economy_action_receipts','player_feedback_events')
    before={table:[tuple(r) for r in conn.execute('SELECT * FROM '+table)] for table in tables}
    with patch('game.player_experience_schema._recovery_notice',side_effect=RuntimeError('recovery writer failure')):
        assert process_due_pve_world_sides(now_ms=1013000)==[]
    assert before=={table:[tuple(r) for r in conn.execute('SELECT * FROM '+table)] for table in tables}
    assert process_due_pve_world_sides(now_ms=1014000)==[{'encounter_id':encounter,'phase':'state_lost'}]
    conn.close()
