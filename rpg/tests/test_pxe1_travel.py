import json

import pytest

import database
from game.travel_runtime import (
    advance_travel_edge,preview_travel,start_travel_session,stop_travel_session,travel_duration_seconds,
)

ROUTE = ['hub_westwild','westwild_n5','westwild_n4','westwild_n3','westwild_n2','westwild_n1','capital_city']


def prepare():
    conn = database.get_connection()
    conn.execute("UPDATE players SET location_id='hub_westwild',level=20 WHERE telegram_id=1")
    conn.executemany('INSERT OR IGNORE INTO player_location_discovery(telegram_id,location_id) VALUES (1,?)', ((n,) for n in ROUTE))
    conn.commit()
    return conn


def test_exact_routes_and_preview_no_mutation():
    assert [travel_duration_seconds(h) for h in (1,2,6,10)]==[15,33,105,177]
    conn = prepare()
    before = conn.execute('SELECT travel_revision FROM players WHERE telegram_id=1').fetchone()[0]
    preview = preview_travel(conn,1,'capital_city')
    assert preview['path']==ROUTE and preview['duration_seconds']==105
    assert conn.execute('SELECT travel_revision FROM players WHERE telegram_id=1').fetchone()[0]==before
    assert not conn.execute('SELECT 1 FROM player_travel_sessions').fetchone()
    conn.close()


def test_startup_overlap_interrupts_not_due_travel_without_relocating_or_rewards():
    from game.player_activity import recover_activity_overlaps
    conn=prepare();conn.execute('BEGIN IMMEDIATE')
    session=start_travel_session(conn,1,preview_travel(conn,1,'capital_city'),request_id='overlap',now_ms=1000)
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=1')
    before=tuple(conn.execute('SELECT location_id,hp,mana,exp,gold FROM players WHERE telegram_id=1').fetchone())
    recover_activity_overlaps(conn,now_ms=2000);conn.commit()
    assert conn.execute('SELECT status FROM player_travel_sessions WHERE session_id=?',(session['session_id'],)).fetchone()[0]=='interrupted'
    assert before==tuple(conn.execute('SELECT location_id,hp,mana,exp,gold FROM players WHERE telegram_id=1').fetchone())
    assert conn.execute('SELECT state FROM player_feedback_events WHERE event_key=?',('recovery:travel:'+session['session_id'],)).fetchone()[0]=='pending'
    conn.close()


def test_only_discovered_intermediate_nodes_and_adjacent_exploration():
    conn = prepare()
    conn.execute("DELETE FROM player_location_discovery WHERE location_id='westwild_n3'")
    conn.commit()
    with pytest.raises(ValueError,match='no_known_route'):
        preview_travel(conn,1,'capital_city')
    conn.execute("UPDATE players SET location_id='westwild_n5' WHERE telegram_id=1")
    assert preview_travel(conn,1,'westwild_n6')['duration_seconds']==15
    conn.close()


def test_per_edge_cancel_equality_and_stale_stop():
    conn = prepare()
    preview = preview_travel(conn,1,'capital_city')
    conn.execute('BEGIN IMMEDIATE')
    session = start_travel_session(conn,1,preview,request_id='first',now_ms=1000)
    assert start_travel_session(conn,1,preview,request_id='first',now_ms=99999)['session_id']==session['session_id']
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    stopped = stop_travel_session(conn,1,session['session_id'],now_ms=16000)
    assert stopped['edge_index']==1 and stopped['status']=='cancelled'
    player = conn.execute('SELECT * FROM players WHERE telegram_id=1').fetchone()
    assert player['location_id']=='westwild_n5' and player['location_visit_revision']==1
    next_session = start_travel_session(conn,1,preview_travel(conn,1,'capital_city'),request_id='second',now_ms=16000)
    old = stop_travel_session(conn,1,session['session_id'],now_ms=999999)
    assert old==stopped
    assert conn.execute('SELECT edge_index FROM player_travel_sessions WHERE session_id=?', (next_session['session_id'],)).fetchone()[0]==0
    conn.commit()
    conn.close()


def test_restart_settles_at_most_one_edge_and_keeps_original_future_deadline():
    from game.world_activity_tick import reconcile_player_due_events
    conn = prepare()
    conn.execute('BEGIN IMMEDIATE')
    session = start_travel_session(conn,1,preview_travel(conn,1,'capital_city'),request_id='first',now_ms=1000)
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    reconcile_player_due_events(conn,1,now_ms=10000000,recovering=True)
    current = conn.execute('SELECT * FROM player_travel_sessions').fetchone()
    assert current['edge_index']==1 and current['next_due_ms']==10018000
    assert conn.execute('SELECT location_id FROM players WHERE telegram_id=1').fetchone()[0]=='westwild_n5'
    unchanged = dict(current)
    reconcile_player_due_events(conn,1,now_ms=10000000,recovering=True)
    assert dict(conn.execute('SELECT * FROM player_travel_sessions').fetchone())==unchanged
    conn.commit()
    conn.close()


def test_no_premature_discovery_for_adjacent_trip():
    conn = prepare()
    conn.execute("UPDATE players SET location_id='westwild_n5' WHERE telegram_id=1")
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    session = start_travel_session(conn,1,preview_travel(conn,1,'westwild_n6'),request_id='first',now_ms=1000)
    assert not conn.execute("SELECT 1 FROM player_location_discovery WHERE telegram_id=1 AND location_id='westwild_n6'").fetchone()
    advance_travel_edge(conn,session['session_id'],now_ms=16000)
    assert conn.execute("SELECT 1 FROM player_location_discovery WHERE telegram_id=1 AND location_id='westwild_n6'").fetchone()
    conn.commit()
    conn.close()
