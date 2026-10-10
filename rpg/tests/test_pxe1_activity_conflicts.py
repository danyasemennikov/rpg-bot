import pytest

import database
from game.action_receipts import peaceful_player
from game.location_threats import seed_visit_threats
from game.player_activity import require_available
from game.travel_runtime import preview_travel,start_travel_session
from game.world_activity_tick import reconcile_player_due_events


def test_activity_check_blocks_economy_but_allows_spend():
    conn = database.get_connection()
    conn.execute('BEGIN IMMEDIATE')
    start_travel_session(conn,1,preview_travel(conn,1,'westwild_n1'),request_id='first',now_ms=0)
    with pytest.raises(ValueError,match='stop_activity_first'):
        peaceful_player(conn,1)
    assert require_available(conn,1,spend_attributes=True)['telegram_id']==1
    conn.commit()
    # A second independent connection observes the same authoritative activity.
    other = database.get_connection()
    with pytest.raises(ValueError,match='stop_activity_first'):
        require_available(other,1)
    other.close()
    conn.close()


def test_threat_tie_interrupts_at_last_reached_node_without_duplicate_roll():
    conn = database.get_connection()
    conn.execute("UPDATE players SET location_id='westwild_n7',level=1 WHERE telegram_id=1")
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    session = start_travel_session(conn,1,preview_travel(conn,1,'westwild_n8'),request_id='first',now_ms=0)
    rng = type('ClockRng',(),{'randint':lambda self,a,b:15})()
    seed_visit_threats(conn,1,now_ms=0,rng=rng)
    before = [tuple(r) for r in conn.execute('SELECT * FROM player_location_threats')]
    seed_visit_threats(conn,1,now_ms=99999,rng=rng)
    assert [tuple(r) for r in conn.execute('SELECT * FROM player_location_threats')]==before
    assert before
    reconcile_player_due_events(conn,1,now_ms=15000)
    assert conn.execute('SELECT location_id FROM players WHERE telegram_id=1').fetchone()[0]=='westwild_n7'
    assert conn.execute('SELECT status FROM player_travel_sessions').fetchone()[0]=='interrupted'
    assert conn.execute("SELECT COUNT(*) FROM pve_encounters WHERE status='active'").fetchone()[0]==1
    conn.commit()
    conn.close()
