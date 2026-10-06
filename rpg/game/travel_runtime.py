"""Discovered-graph previews and durable one-edge-at-a-time travel."""

from collections import deque
import json
import secrets

from game.action_receipts import ActionRejected
from game.locations import get_location,get_location_neighbors,resolve_location_id
from game.player_activity import require_available


def travel_duration_seconds(edges: int) -> int:
    if isinstance(edges,bool) or not isinstance(edges,int) or edges<1:
        raise ValueError('invalid travel edge count')
    return 15*edges+3*(edges-1)


def preview_travel(conn, player_id: int, destination: str) -> dict:
    player = conn.execute('SELECT * FROM players WHERE telegram_id=?', (player_id,)).fetchone()
    if not player:
        raise ActionRejected('no_player')
    origin,destination = resolve_location_id(player['location_id']),resolve_location_id(destination)
    if not get_location(destination) or origin==destination:
        raise ActionRejected('invalid_destination')
    neighbors = [resolve_location_id(n) for n in get_location_neighbors(origin)]
    path = None
    if destination in neighbors:
        path,route_class = [origin,destination],'adjacent'
    else:
        discovered = {resolve_location_id(r['location_id']) for r in conn.execute('SELECT location_id FROM player_location_discovery WHERE telegram_id=?', (player_id,))}
        queue,seen = deque([[origin]]),{origin}
        while queue:
            candidate = queue.popleft()
            for node in get_location_neighbors(candidate[-1]):
                node = resolve_location_id(node)
                if node not in discovered or node in seen:
                    continue
                seen.add(node)
                next_path = candidate+[node]
                if node==destination:
                    path=next_path
                    break
                queue.append(next_path)
            if path:
                break
        route_class = 'discovered'
    if not path:
        raise ActionRejected('no_known_route')
    return {'schema_version':1,'route_version':1,'route_class':route_class,'path':path,
        'origin_location_id':origin,'destination_location_id':destination,
        'travel_revision':player['travel_revision'],'duration_seconds':travel_duration_seconds(len(path)-1)}


def start_travel_session(conn, player_id: int, preview: dict, *, request_id: str, now_ms: int) -> dict:
    prior = conn.execute('SELECT * FROM player_travel_sessions WHERE player_id=? AND start_request_id=?', (player_id,request_id)).fetchone()
    if prior:
        return dict(prior)
    require_available(conn,player_id)
    if preview_travel(conn,player_id,preview['destination_location_id'])!=preview:
        raise ActionRejected('route_changed')
    session_id = secrets.token_hex(16)
    revision = preview['travel_revision']+1
    conn.execute('UPDATE players SET travel_revision=? WHERE telegram_id=?', (revision,player_id))
    conn.execute('''INSERT INTO player_travel_sessions
        (session_id,player_id,start_request_id,schema_version,route_version,route_class,path_json,
         origin_location_id,destination_location_id,status,started_ms,next_due_ms,expected_travel_revision,created_ms,updated_ms)
         VALUES (?,?,?,1,1,?,?,?,?,'running',?,?,?,?,?)''',
        (session_id,player_id,request_id,preview['route_class'],json.dumps(preview['path']),preview['origin_location_id'],
         preview['destination_location_id'],now_ms,now_ms+15000,revision,now_ms,now_ms))
    return dict(conn.execute('SELECT * FROM player_travel_sessions WHERE session_id=?', (session_id,)).fetchone())


def advance_travel_edge(conn, session_id: str, *, now_ms: int, recovering: bool=False) -> dict:
    from game.location_threats import arrive_at_location
    session = conn.execute('SELECT * FROM player_travel_sessions WHERE session_id=?', (session_id,)).fetchone()
    if not session:
        raise ActionRejected('session_missing')
    if session['status']!='running' or session['next_due_ms']>now_ms:
        return dict(session)
    try:
        player = require_available(conn,session['player_id'],exclude_travel=session_id)
        path = json.loads(session['path_json'])
        edge = session['edge_index']
        if (session['schema_version']!=1 or session['route_version']!=1 or not isinstance(path,list)
                or len(path)<2 or not 0<=edge<len(path)-1 or path[0]!=session['origin_location_id']
                or path[-1]!=session['destination_location_id'] or resolve_location_id(player['location_id'])!=path[edge]
                or player['travel_revision']!=session['expected_travel_revision']
                or any(not get_location(n) for n in path)
                or any(b not in get_location_neighbors(a) for a,b in zip(path,path[1:]))):
            raise ActionRejected('route_changed')
    except (ActionRejected,ValueError,TypeError) as exc:
        conn.execute("UPDATE player_travel_sessions SET status='interrupted',terminal_reason=?,next_due_ms=NULL,revision=revision+1,updated_ms=? WHERE session_id=?", (str(exc),now_ms,session_id))
        return dict(conn.execute('SELECT * FROM player_travel_sessions WHERE session_id=?', (session_id,)).fetchone())
    arrival_ms = now_ms if recovering else session['next_due_ms']
    arrive_at_location(conn,session['player_id'],path[edge+1],now_ms=arrival_ms)
    edge += 1
    status = 'arrived' if edge==len(path)-1 else 'running'
    next_due = None if status=='arrived' else arrival_ms+18000
    conn.execute('''UPDATE player_travel_sessions SET edge_index=?,status=?,next_due_ms=?,
        expected_travel_revision=expected_travel_revision+1,revision=revision+1,updated_ms=? WHERE session_id=?''',
        (edge,status,next_due,now_ms,session_id))
    return dict(conn.execute('SELECT * FROM player_travel_sessions WHERE session_id=?', (session_id,)).fetchone())


def stop_travel_session(conn, player_id: int, session_id: str, *, now_ms: int) -> dict:
    session = conn.execute('SELECT * FROM player_travel_sessions WHERE player_id=? AND session_id=?', (player_id,session_id)).fetchone()
    if not session:
        raise ActionRejected('session_missing')
    if session['status']!='running':
        return dict(session)
    from game.world_activity_tick import reconcile_player_due_events
    reconcile_player_due_events(conn,player_id,now_ms=now_ms)
    conn.execute("UPDATE player_travel_sessions SET status='cancelled',next_due_ms=NULL,revision=revision+1,updated_ms=? WHERE player_id=? AND session_id=? AND status='running'", (now_ms,player_id,session_id))
    return dict(conn.execute('SELECT * FROM player_travel_sessions WHERE session_id=?', (session_id,)).fetchone())
