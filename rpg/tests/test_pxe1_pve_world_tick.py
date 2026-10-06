import json
from datetime import datetime,timezone
from unittest.mock import patch

from database import get_connection
from game.build_progression import migrate_character_builds_v1
from game.pve_live import (
    _sync_v1_to_legacy_projection,apply_pxe1_pve_death,load_active_pve_encounter,
    persist_solo_pve_encounter_state,process_due_pve_formations,process_due_pve_world_sides,
)
from tests.test_pxe1_encounter_lifecycle import prepare


def started():
    migrate_character_builds_v1()
    encounter,spawn = prepare()
    process_due_pve_formations(now_ms=1012000)
    return encounter,spawn


def test_background_timeout_uses_actual_engine_and_durable_orders_without_context():
    encounter,_ = started()
    with patch('game.pve_live._utc_now',return_value=datetime.fromtimestamp(1027,timezone.utc)):
        assert process_due_pve_world_sides(now_ms=1026999)==[]
        results = process_due_pve_world_sides(now_ms=1027000)
    assert len(results)==1 and results[0]['phase']=='active'
    state,mob = load_active_pve_encounter(encounter_id=encounter)
    assert any(event['kind']=='guard' and event['timeout'] for event in state['combat_events_v1'])
    assert any(event['kind'].startswith('enemy') for event in state['combat_events_v1'])
    conn = get_connection()
    assert conn.execute("SELECT COUNT(*) FROM combat_turn_results_v1 WHERE encounter_kind='pve'").fetchone()[0]==2
    assert not conn.execute('SELECT 1 FROM pve_reward_settlements WHERE encounter_id=?',(encounter,)).fetchone()
    conn.close()


def test_background_terminal_victory_runs_existing_t1_t2_and_thirty_second_respawn():
    encounter,spawn = started()
    state,mob = load_active_pve_encounter(encounter_id=encounter)
    for enemy in state['enemy_states_v1']:
        enemy['hp']=0
        enemy['dead']=True
    _sync_v1_to_legacy_projection(state)
    assert persist_solo_pve_encounter_state(encounter_id=encounter,battle_state=state,mob=mob)
    results = process_due_pve_world_sides(now_ms=1013000)
    assert results[0]['phase']=='victory'
    conn = get_connection()
    assert conn.execute('SELECT status FROM pve_reward_settlements WHERE encounter_id=?',(encounter,)).fetchone()[0]=='applied'
    assert conn.execute('SELECT status FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0]=='victory'
    assert conn.execute('SELECT state FROM pve_spawn_instances WHERE spawn_instance_id=?',(spawn['spawn_instance_id'],)).fetchone()[0]=='respawning'
    assert not conn.execute('SELECT in_battle FROM players WHERE telegram_id=1').fetchone()[0]
    assert process_due_pve_world_sides(now_ms=999999999)==[]
    conn.close()


def test_background_defeat_receipt_replays_without_repeated_penalty():
    encounter,spawn = started()
    state,mob = load_active_pve_encounter(encounter_id=encounter)
    actor = state['participant_states_v1']['1']
    actor['hp']=0
    actor['dead']=True
    _sync_v1_to_legacy_projection(state)
    assert persist_solo_pve_encounter_state(encounter_id=encounter,battle_state=state,mob=mob)
    results = process_due_pve_world_sides(now_ms=1013000)
    assert results[0]['phase']=='death'
    conn = get_connection()
    before = tuple(conn.execute('SELECT exp,gold,hp,location_id,travel_revision,location_visit_revision FROM players WHERE telegram_id=1').fetchone())
    apply_pxe1_pve_death(1,encounter,now_ms=1014000)
    assert tuple(conn.execute('SELECT exp,gold,hp,location_id,travel_revision,location_visit_revision FROM players WHERE telegram_id=1').fetchone())==before
    assert conn.execute('SELECT status FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0]=='death'
    assert conn.execute('SELECT state FROM pve_spawn_instances WHERE spawn_instance_id=?',(spawn['spawn_instance_id'],)).fetchone()[0]=='respawning'
    conn.close()
