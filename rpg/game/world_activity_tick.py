"""Bounded due-work coordinator. Domain services own every transition."""

import logging

logger = logging.getLogger(__name__)


def reconcile_player_due_events(conn, player_id: int, *, now_ms: int, recovering: bool=False) -> list[dict]:
    from game.gathering_runtime import commit_gathering_tick
    from game.travel_runtime import advance_travel_edge
    from game.location_threats import process_location_threat
    results = []
    recovered_edge = False
    for _ in range(100):
        events = []
        for row in conn.execute("SELECT * FROM player_location_threats WHERE player_id=? AND status='pending' AND due_ms<=?", (player_id,now_ms)):
            events.append((row['due_ms'],0,row['mob_id'],'threat',dict(row)))
        if not (recovering and recovered_edge):
            for row in conn.execute("SELECT * FROM player_travel_sessions WHERE player_id=? AND status='running' AND next_due_ms<=?", (player_id,now_ms)):
                events.append((row['next_due_ms'],1,row['session_id'],'travel',dict(row)))
        if not recovering:
            for row in conn.execute("SELECT * FROM player_gathering_sessions WHERE player_id=? AND status='running' AND next_due_ms<=?", (player_id,now_ms)):
                events.append((row['next_due_ms'],2,row['session_id'],'gather',dict(row)))
        if not events:
            break
        _,_,_,kind,row = min(events,key=lambda e:e[:3])
        if kind=='threat':
            result = process_location_threat(conn,player_id=player_id,visit_revision=row['visit_revision'],mob_id=row['mob_id'],now_ms=now_ms)
        elif kind=='travel':
            result = advance_travel_edge(conn,row['session_id'],now_ms=now_ms,recovering=recovering)
            recovered_edge = True
        else:
            result = commit_gathering_tick(conn,row['session_id'],now_ms=now_ms)
        results.append(result)
    return results


def run_world_activity_tick(*, now_ms: int, limit: int=100, recovering: bool=False) -> list[dict]:
    from database import get_connection
    from game.pve_live import process_due_pve_formations,process_due_pve_world_sides
    conn = get_connection()
    try:
        players = conn.execute('''SELECT player_id FROM (
            SELECT player_id,due_ms AS due FROM player_location_threats WHERE status='pending'
            UNION ALL SELECT player_id,next_due_ms FROM player_travel_sessions WHERE status='running'
            UNION ALL SELECT player_id,next_due_ms FROM player_gathering_sessions WHERE status='running')
            WHERE due<=? GROUP BY player_id ORDER BY MIN(due),player_id LIMIT ?''', (now_ms,limit)).fetchall()
    finally:
        conn.close()
    results = []
    for player in players:
        conn = get_connection()
        try:
            conn.execute('BEGIN IMMEDIATE')
            results.extend(reconcile_player_due_events(conn,player['player_id'],now_ms=now_ms,recovering=recovering))
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception('PXE1 activity tick failed: player %s',player['player_id'])
        finally:
            conn.close()
    results.extend(process_due_pve_formations(now_ms=now_ms,limit=limit))
    results.extend(process_due_pve_world_sides(now_ms=now_ms,limit=limit))
    return results
