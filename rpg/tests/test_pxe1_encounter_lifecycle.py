import json
import pytest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import database
from game.mobs import get_mob
from game.pve_live import (
    create_or_load_open_world_pve_encounter, ensure_runtime_for_battle,
    join_open_world_pve_encounter, leave_open_world_pve_encounter,
    list_location_active_pve_encounters, list_location_available_spawn_instances,
    load_active_pve_encounter, process_due_pve_formations, start_due_pve_formation,
)


def prepare():
    conn = database.get_connection()
    conn.execute("UPDATE players SET location_id='westwild_n1',hp=100,in_battle=0 WHERE telegram_id IN (1,777)")
    conn.commit()
    conn.close()
    spawn = next(s for s in list_location_available_spawn_instances(location_id='westwild_n1') if s['mob_id']=='westwild_rabbit')
    with patch('time.time', return_value=1000):
        encounter,status = create_or_load_open_world_pve_encounter(owner_player_id=1,location_id='westwild_n1',
            mob_id='westwild_rabbit',spawn_instance_id=spawn['spawn_instance_id'],
            battle_state={'mob_id':'westwild_rabbit','mob_hp':20,'mob_max_hp':20,'player_hp':100,'player_mana':100},mob=get_mob('westwild_rabbit'))
    assert status == 'created'
    return encounter,spawn


def test_always_twelve_seconds_and_atomic_automatic_start():
    encounter,_ = prepare()
    with patch('time.time', return_value=1005):
        assert join_open_world_pve_encounter(encounter_id=encounter,player_id=777) == (True,'joined')
    result = process_due_pve_formations(now_ms=1011999)
    assert result == []
    result = process_due_pve_formations(now_ms=1012000)
    assert result[0]['phase'] == 'active'
    assert result[0]['player_ids'] == [1,777]
    conn = database.get_connection()
    row = conn.execute('SELECT * FROM pve_encounters WHERE encounter_id=?', (encounter,)).fetchone()
    state = json.loads(row['battle_state_json'])
    assert row['runtime_started_ms'] == 1012000
    assert json.loads(row['locked_roster_json']) == {'player_ids':[1,777]}
    assert state['side_turn_state'] == 'collecting_orders'
    assert set(state['participant_states']) == {'1','777'}
    assert [r[0] for r in conn.execute('SELECT in_battle FROM players WHERE telegram_id IN (1,777)')] == [1,1]
    before = row['battle_state_json']
    conn.close()
    assert process_due_pve_formations(now_ms=9999999) == []
    state,mob = load_active_pve_encounter(encounter_id=encounter)
    runtime = ensure_runtime_for_battle(player_id=777,battle_state=state,mob=mob)
    assert runtime.turn_revision == json.loads(before)['turn_revision']
    assert state['side_deadline_at'] == json.loads(before)['side_deadline_at']


def test_mixed_reservation_rechecks_actor_activity_and_location_under_writer():
    from game.action_receipts import ActionRejected
    from game.pve_live import create_mixed_open_world_pve_encounter
    conn=database.get_connection()
    with pytest.raises(ActionRejected,match='wrong_location'):
        create_mixed_open_world_pve_encounter(owner_player_id=1,recipe_id='westwild_n8_mixed',battle_state={})
    conn.execute("UPDATE players SET location_id='westwild_n8',in_battle=1 WHERE telegram_id=1");conn.commit()
    with pytest.raises(ActionRejected,match='in_battle'):
        create_mixed_open_world_pve_encounter(owner_player_id=1,recipe_id='westwild_n8_mixed',battle_state={})
    assert conn.execute("SELECT COUNT(*) FROM pve_spawn_instances WHERE location_id='westwild_n8' AND linked_encounter_id IS NOT NULL").fetchone()[0]==0
    assert conn.execute('SELECT COUNT(*) FROM pve_encounters').fetchone()[0]==0
    conn.close()


def test_join_equality_rejected_leave_after_deadline_and_transfer():
    encounter,_ = prepare()
    with patch('time.time', return_value=1001):
        assert join_open_world_pve_encounter(encounter_id=encounter,player_id=777)[0]
    with patch('time.time', return_value=1012):
        assert join_open_world_pve_encounter(encounter_id=encounter,player_id=777) == (False,'locked')
        assert leave_open_world_pve_encounter(encounter_id=encounter,player_id=1) == (True,'left')
    conn = database.get_connection()
    assert conn.execute('SELECT owner_player_id FROM pve_encounters WHERE encounter_id=?', (encounter,)).fetchone()[0] == 777
    conn.close()
    assert process_due_pve_formations(now_ms=1013000)[0]['player_ids'] == [777]
    assert leave_open_world_pve_encounter(encounter_id=encounter,player_id=777) == (False,'locked')


def test_unstarted_abandon_releases_without_respawn_and_no_rejoin():
    encounter,_ = prepare()
    with patch('time.time', return_value=1001):
        assert join_open_world_pve_encounter(encounter_id=encounter,player_id=777)[0]
        assert leave_open_world_pve_encounter(encounter_id=encounter,player_id=777)[0]
        assert join_open_world_pve_encounter(encounter_id=encounter,player_id=777) == (False,'cannot_rejoin')
        assert leave_open_world_pve_encounter(encounter_id=encounter,player_id=1) == (True,'left_collapsed')
    conn = database.get_connection()
    assert conn.execute('SELECT status FROM pve_encounters WHERE encounter_id=?', (encounter,)).fetchone()[0] == 'abandoned'
    assert not conn.execute('SELECT 1 FROM pve_spawn_instances WHERE linked_encounter_id=?', (encounter,)).fetchone()
    conn.close()


def test_no_ttl_expiry_on_read():
    encounter,_ = prepare()
    conn = database.get_connection()
    conn.execute("UPDATE pve_encounters SET created_at=datetime('now','-1 hour') WHERE encounter_id=?", (encounter,))
    conn.commit()
    conn.close()
    assert any(e['encounter_id']==encounter for e in list_location_active_pve_encounters(location_id='westwild_n1'))


def test_atomic_start_rolls_back_all_flags_and_lock_on_binding_failure():
    encounter,_ = prepare()
    conn = database.get_connection()
    conn.execute('BEGIN IMMEDIATE')
    with patch('game.regional_objectives.capture_combat_bindings',side_effect=RuntimeError('injected')):
        try:
            start_due_pve_formation(conn,encounter_id=encounter,now_ms=1012000)
        except RuntimeError:
            conn.rollback()
    row = conn.execute('SELECT * FROM pve_encounters WHERE encounter_id=?', (encounter,)).fetchone()
    assert row['locked_roster_json'] is None and row['runtime_started_ms'] is None
    assert conn.execute('SELECT in_battle FROM players WHERE telegram_id=1').fetchone()[0] == 0
    conn.close()
    assert process_due_pve_formations(now_ms=1012000)[0]['phase'] == 'active'


def test_simultaneous_attack_reserves_one_source_on_independent_connections():
    encounter,spawn = prepare()
    def attack(pid):
        return create_or_load_open_world_pve_encounter(owner_player_id=pid,location_id='westwild_n1',
            mob_id='westwild_rabbit',spawn_instance_id=spawn['spawn_instance_id'],battle_state={},mob=get_mob('westwild_rabbit'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attack,[1,777]))
    assert results == [(encounter,'spawn_busy'),(encounter,'spawn_busy')]
