import json

import pytest

from database import get_connection
from game.mobs import get_mob
from game.pve_live import (
    create_mixed_open_world_pve_encounter, process_due_pve_formations,
)
from game.regional_adventures import (
    execute_regional_action, get_project_state, issue_regional_action,
    start_project_in_transaction,
)
from game.regional_objectives import apply_combat_bindings


def _move(location):
    conn=get_connection(); conn.execute('UPDATE players SET location_id=?,travel_revision=travel_revision+1 WHERE telegram_id=1',(location,)); conn.commit(); conn.close()


def _act(content, operation, **kwargs):
    token=issue_regional_action(1,content,operation,**kwargs); assert token
    return execute_regional_action(1,token)


def _battle_state(mob_id):
    mob=get_mob(mob_id)
    return {'mob_id':mob_id,'mob_hp':mob['hp'],'mob_max_hp':mob['hp'],'player_hp':100,
            'player_max_hp':100,'player_mana':100,'player_max_mana':100,'log':[]}


def _start_due_formation(encounter_id):
    conn=get_connection()
    deadline=conn.execute('SELECT formation_deadline_ms FROM pve_encounters WHERE encounter_id=?',(encounter_id,)).fetchone()[0]
    conn.close()
    assert any(event['encounter_id']==encounter_id for event in process_due_pve_formations(now_ms=deadline))
    conn=get_connection()
    roster=json.loads(conn.execute('SELECT locked_roster_json FROM pve_encounters WHERE encounter_id=?',(encounter_id,)).fetchone()[0])
    conn.close()
    return roster['player_ids']


def _ferry_at_combat_step():
    _move('mireveil_n5'); _act('mv_ford_marks','inspect')
    _move('mireveil_n8'); _act('mv_channel_rope','inspect')
    _move('hub_mireveil'); _act('mv_ferry_crew','start')
    assert get_project_state(1,'mv_ferry_crew')['step_index'] == 1
    _move('mireveil_n6')


def test_roster_lock_captures_exact_mixed_binding_and_alive_t2_advances_once():
    _ferry_at_combat_step()
    encounter_id,status=create_mixed_open_world_pve_encounter(
        owner_player_id=1,recipe_id='rav1_mireveil_n6_crosscurrent',
        battle_state=_battle_state('giant_leech'))
    assert status == 'created' and _start_due_formation(encounter_id) == [1]
    conn=get_connection(); row=conn.execute('SELECT * FROM rav1_combat_bindings WHERE encounter_id=? AND player_id=1',(encounter_id,)).fetchone()
    bindings=json.loads(row['bindings_json']); assert len(bindings)==1
    assert bindings[0]['mixed_encounter_id']=='rav1_mireveil_n6_crosscurrent'
    source=json.loads(conn.execute('SELECT source_units_json FROM pve_encounters WHERE encounter_id=?',(encounter_id,)).fetchone()['source_units_json'])['units']
    plan={'eligible_recipient_ids':[1],'recipients':[{'player_id':1,'units':[{'unit_id':unit['unit_id']} for unit in source]}]}
    conn.execute('BEGIN IMMEDIATE'); advanced=apply_combat_bindings(conn,encounter_id=encounter_id,plan=plan); conn.commit(); conn.close()
    assert advanced == {1:['mv_ferry_crew']}
    assert get_project_state(1,'mv_ferry_crew')['step_index'] == 2


def test_defeated_recipient_binding_is_applied_without_progress():
    _ferry_at_combat_step()
    encounter_id,status=create_mixed_open_world_pve_encounter(
        owner_player_id=1,recipe_id='rav1_mireveil_n6_crosscurrent',battle_state=_battle_state('giant_leech'))
    assert status=='created'; _start_due_formation(encounter_id)
    conn=get_connection(); conn.execute('BEGIN IMMEDIATE')
    assert apply_combat_bindings(conn,encounter_id=encounter_id,plan={'eligible_recipient_ids':[],'recipients':[]}) == {}
    conn.commit()
    assert conn.execute('SELECT applied_at FROM rav1_combat_bindings WHERE encounter_id=?',(encounter_id,)).fetchone()['applied_at']
    conn.close(); assert get_project_state(1,'mv_ferry_crew')['step_index']==1


def test_acceptance_after_roster_lock_gets_no_old_encounter_credit():
    _move('mireveil_n5'); _act('mv_ford_marks','inspect')
    _move('mireveil_n8'); _act('mv_channel_rope','inspect')
    _move('mireveil_n6')
    encounter_id,status=create_mixed_open_world_pve_encounter(
        owner_player_id=1,recipe_id='rav1_mireveil_n6_crosscurrent',battle_state=_battle_state('giant_leech'))
    assert status=='created'; _start_due_formation(encounter_id)
    conn=get_connection(); assert json.loads(conn.execute('SELECT bindings_json FROM rav1_combat_bindings WHERE encounter_id=?',(encounter_id,)).fetchone()['bindings_json']) == []
    conn.close()
    # Exercise the domain start primitive directly: the public peaceful-action
    # guard correctly blocks project changes while the encounter is live, but
    # the binding invariant must still hold if acceptance happens later in the
    # same persisted history (for example after recovery/replay).
    conn=get_connection(); conn.execute('BEGIN IMMEDIATE')
    assert start_project_in_transaction(conn,1,'mv_ferry_crew')['step_index']==1
    conn.commit()
    source=json.loads(conn.execute('SELECT source_units_json FROM pve_encounters WHERE encounter_id=?',(encounter_id,)).fetchone()['source_units_json'])['units']
    plan={'eligible_recipient_ids':[1],'recipients':[{'player_id':1,'units':[{'unit_id':u['unit_id']} for u in source]}]}
    conn.execute('BEGIN IMMEDIATE'); assert apply_combat_bindings(conn,encounter_id=encounter_id,plan=plan)=={}; conn.commit(); conn.close()
    assert get_project_state(1,'mv_ferry_crew')['step_index']==1


def test_corrupt_or_missing_marked_binding_fails_closed():
    _ferry_at_combat_step()
    encounter_id,status=create_mixed_open_world_pve_encounter(
        owner_player_id=1,recipe_id='rav1_mireveil_n6_crosscurrent',battle_state=_battle_state('giant_leech'))
    assert status=='created'; _start_due_formation(encounter_id)
    conn=get_connection(); conn.execute('DELETE FROM rav1_combat_bindings WHERE encounter_id=?',(encounter_id,)); conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    with pytest.raises(RuntimeError, match='binding_missing'):
        apply_combat_bindings(conn,encounter_id=encounter_id,plan={'eligible_recipient_ids':[1],'recipients':[]})
    conn.rollback(); conn.close()
