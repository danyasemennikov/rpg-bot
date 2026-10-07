"""The ordinary gathering roll, item, profession XP and objective in one commit."""

import json
import random

from database import get_connection, add_gathering_profession_exp
from game.action_receipts import ActionRejected, peaceful_player, record_request, require_item_delivery
from game.gathering_foundation import build_location_gather_source_profiles, resolve_gather_access_decision
from game.gathering_progression import gathering_profession_xp_for_success
from game.gear_instances import grant_item_to_player
from game.locations import resolve_location_id


def _result_shape(result: dict, *, recovered: bool) -> dict:
    shaped = {**result, 'recovered': recovered}
    if result.get('status') == 'gathered' and result.get('granted'):
        shaped['item_id'] = result['granted'][0]['item_id']
    return shaped


def recover_gather_result(player_id: int, request_id: str) -> dict | None:
    """Recover a committed message result without consulting mutable world state."""
    conn = get_connection()
    try:
        row = conn.execute('''SELECT action_kind, result_json FROM economy_action_receipts
            WHERE player_id=? AND request_id=?''', (player_id, request_id)).fetchone()
        if row is not None:
            if row['action_kind'] != 'gather':
                raise ValueError('request_receipt_mismatch')
            return _result_shape(json.loads(row['result_json']), recovered=True)
        legacy = conn.execute('SELECT 1 FROM player_action_receipts WHERE player_id=? AND request_id=?',
                              (player_id, request_id)).fetchone()
        return {'status': 'historical_receipt_unavailable', 'recovered': True} if legacy else None
    finally:
        conn.close()


def gather_resource(player_id: int, profession: str, *, location_id: str, request_id: str,
                    travel_revision: int | None = None, rng=None) -> dict:
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        from game.economy_actions import intent_hash, store_receipt
        receipt_row = conn.execute('''SELECT action_kind, result_json FROM economy_action_receipts
            WHERE player_id=? AND request_id=?''', (player_id, request_id)).fetchone()
        if receipt_row is not None:
            if receipt_row['action_kind'] != 'gather':
                raise ValueError('request_receipt_mismatch')
            conn.commit()
            return _result_shape(json.loads(receipt_row['result_json']), recovered=True)
        legacy = conn.execute('SELECT 1 FROM player_action_receipts WHERE player_id=? AND request_id=?',
                              (player_id, request_id)).fetchone()
        if legacy:
            conn.commit()
            return {'status': 'historical_receipt_unavailable', 'recovered': True}
        # Fresh requests enter the finite PXE1 session. Historical receipts above
        # keep their original item/XP payload and never charge new wear.
        result = start_gathering_session(conn,player_id,profession,location_id=location_id,
            request_id=request_id,travel_revision=travel_revision)
        conn.commit()
        return result
    except ActionRejected as exc:
        conn.rollback()
        return {'status': str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _source_snapshot(location_id: str, profession: str) -> dict:
    from decimal import Decimal
    from game.profession_resources import RESOURCES, location_sources
    entries = []
    for item,chance in location_sources(location_id):
        resource = RESOURCES.get(item)
        if resource and resource.profession_key==profession:
            basis = Decimal(str(chance))*10000
            if basis != int(basis):
                raise ValueError('noninteger source probability')
            entries.append({'item_id':item,'chance_bp':int(basis),
                'required_level':resource.required_level,'required_tool_tier':resource.required_tool_tier})
    if sum(e['chance_bp'] for e in entries)>10000:
        raise ValueError('invalid source probability total')
    return {'schema_version':1,'catalog_version':2,'profession_key':profession,'entries':entries}


def gather_tick_roll(seed: str, tick_index: int, snapshot: dict) -> dict | None:
    """Decoded 16-byte seed, decimal tick, big-endian integer intervals."""
    import hashlib
    from game.profession_resources import RESOURCES
    if (not isinstance(seed,str) or len(seed)!=32 or any(c not in '0123456789abcdef' for c in seed)
            or not 1<=tick_index<=15 or snapshot.get('schema_version')!=1
            or snapshot.get('catalog_version')!=2):
        raise ValueError('invalid gathering snapshot')
    entries = snapshot.get('entries')
    if not isinstance(entries,list) or not entries:
        raise ValueError('invalid gathering entries')
    cumulative = 0
    n = int.from_bytes(hashlib.sha256(bytes.fromhex(seed)+b':gather:'+str(tick_index).encode('ascii')).digest()[:8],'big')
    selected = None
    for entry in entries:
        if not isinstance(entry,dict): raise ValueError('invalid gathering source entry')
        resource = RESOURCES.get(entry.get('item_id'))
        chance = entry.get('chance_bp')
        if (not resource or resource.profession_key!=snapshot.get('profession_key')
                or not isinstance(chance,int) or isinstance(chance,bool) or not 0<chance<=10000
                or entry.get('required_level')!=resource.required_level
                or entry.get('required_tool_tier')!=resource.required_tool_tier):
            raise ValueError('invalid gathering source entry')
        cumulative += chance
        if selected is None and n*10000<cumulative*(1<<64):
            selected = entry
    if cumulative>10000:
        raise ValueError('invalid gathering intervals')
    return selected


def start_gathering_session(conn, player_id: int, profession: str, *, location_id: str,
                            request_id: str, travel_revision=None, now_ms=None, seed=None) -> dict:
    import secrets
    import time
    from game.player_activity import require_available
    from game.profession_tools import require_tool
    if not conn.in_transaction:
        raise RuntimeError('gather start requires caller transaction')
    now_ms = int(time.time()*1000) if now_ms is None else int(now_ms)
    previous = conn.execute('SELECT * FROM player_gathering_sessions WHERE player_id=? AND start_request_id=?', (player_id,request_id)).fetchone()
    if previous:
        return {'status':previous['status'],'session':dict(previous),'recovered':True}
    active = conn.execute("SELECT * FROM player_gathering_sessions WHERE player_id=? AND status='running'", (player_id,)).fetchone()
    if active:
        return {'status':'running','session':dict(active)}
    player = require_available(conn,player_id)
    location = resolve_location_id(player['location_id'])
    if location != resolve_location_id(location_id) or (travel_revision is not None and player['travel_revision']!=travel_revision):
        raise ActionRejected('stale_action')
    if profession not in {'woodcutting','mining','herbalism','fishing'}:
        raise ActionRejected('no_eligible_resource')
    snapshot = _source_snapshot(location,profession)
    conn.execute('INSERT OR IGNORE INTO player_gathering_professions(telegram_id,profession_key) VALUES (?,?)', (player_id,profession))
    level = conn.execute('SELECT level FROM player_gathering_professions WHERE telegram_id=? AND profession_key=?', (player_id,profession)).fetchone()[0]
    tool = require_tool(conn,player_id,profession)
    if not any(e['required_level']<=level and e['required_tool_tier']<=tool['tier'] for e in snapshot['entries']):
        raise ActionRejected('no_eligible_resource')
    seed = seed or secrets.token_hex(16)
    gather_tick_roll(seed,1,snapshot)  # Validate before committing an unusable session.
    session_id = secrets.token_hex(16)
    conn.execute('''INSERT INTO player_gathering_sessions
        (session_id,player_id,start_request_id,schema_version,rng_version,catalog_version,profession_key,
        location_id,location_visit_revision,source_snapshot_json,seed,tool_tier,expected_tool_revision,status,
        started_ms,next_due_ms,ends_ms,result_json,created_ms,updated_ms)
        VALUES (?,?,?,1,1,2,?,?,?,?,?,?,?,'running',?,?,?, ?,?,?)''',
        (session_id,player_id,request_id,profession,location,player['location_visit_revision'],json.dumps(snapshot),
         seed,tool['tier'],tool['revision'],now_ms,now_ms+8000,now_ms+120000,
         json.dumps({'schema_version':1,'items':{},'xp':0,'attempts':0,'max_attempts':min(15,tool['durability'])}),now_ms,now_ms))
    row = conn.execute('SELECT * FROM player_gathering_sessions WHERE session_id=?', (session_id,)).fetchone()
    return {'status':'running','session':dict(row),'recovered':False}


def commit_gathering_tick(conn, session_id: str, *, now_ms: int) -> dict:
    from game.economy_actions import find_receipt, intent_hash, store_receipt
    from game.player_activity import require_available
    from game.profession_tools import require_tool, wear_tool
    from game.quest_board import register_contract_objective
    session = conn.execute('SELECT * FROM player_gathering_sessions WHERE session_id=?', (session_id,)).fetchone()
    if not session:
        raise ActionRejected('session_missing')
    if session['status']!='running':
        return {'status':session['status'],'session':dict(session)}
    tick = int(session['last_tick'])+1
    player_id = int(session['player_id'])
    request_id = f'gather:{session_id}:{tick}'
    request_hash = intent_hash('gather_tick_pxe1',player_id,{'session_id':session_id,'tick':tick,'seed':session['seed']})
    try:
        if not isinstance(session['next_due_ms'],int):
            raise ValueError('invalid_gather_deadline')
        if now_ms<session['next_due_ms']:
            return {'status':session['status'],'session':dict(session)}
        # A future receipt beside an older session counter cannot occur in the
        # atomic tick. Quarantine it rather than repeatedly granting/replaying.
        if find_receipt(conn,player_id,request_id,'gather_tick_pxe1',request_hash):
            raise ValueError('gather_receipt_counter_mismatch')
        accounting = json.loads(session['result_json'])
        if not isinstance(accounting,dict):
            raise ValueError('invalid gathering accounting')
        if (not isinstance(accounting.get('items'),dict) or not isinstance(accounting.get('xp'),int)
                or isinstance(accounting.get('xp'),bool) or accounting['xp']<0
                or not isinstance(accounting.get('max_attempts'),int) or isinstance(accounting.get('max_attempts'),bool)
                or not 1<=accounting['max_attempts']<=15
                or any(not isinstance(n,int) or isinstance(n,bool) or n<=0 for n in accounting['items'].values())):
            raise ValueError('invalid gathering accounting')
        player = require_available(conn,player_id,exclude_gather=session_id)
        if (resolve_location_id(player['location_id'])!=session['location_id']
                or player['location_visit_revision']!=session['location_visit_revision']):
            raise ActionRejected('location_changed')
        tool = require_tool(conn,player_id,session['profession_key'])
        if tool['tier']!=session['tool_tier'] or tool['revision']!=session['expected_tool_revision']:
            raise ActionRejected('tool_changed')
        if (tick>15 or accounting.get('schema_version')!=1 or accounting.get('attempts')!=session['last_tick']
                or sum(accounting.get('items',{}).values())!=session['yield_total']):
            raise ValueError('invalid gathering accounting')
        receipts=conn.execute("SELECT * FROM economy_action_receipts WHERE player_id=? AND request_id GLOB ?",
            (player_id,f'gather:{session_id}:*')).fetchall()
        if len(receipts)!=session['last_tick']:
            raise ValueError('gather_receipt_counter_mismatch')
        if session['last_tick']:
            by_tick={r['request_id']:r for r in receipts}
            for prior_tick in range(1,tick):
                prior=by_tick.get(f'gather:{session_id}:{prior_tick}')
                expected_hash=intent_hash('gather_tick_pxe1',player_id,{'session_id':session_id,'tick':prior_tick,'seed':session['seed']})
                if not prior or prior['action_kind']!='gather_tick_pxe1' or prior['request_hash']!=expected_hash:
                    raise ValueError('gather_receipt_counter_mismatch')
                fact=json.loads(prior['result_json'])
                if fact['session_id']!=session_id or fact['tick_index']!=prior_tick:
                    raise ValueError('gather_receipt_counter_mismatch')
            if fact['result']!=accounting:
                raise ValueError('gather_receipt_counter_mismatch')
        elif accounting.get('items') or accounting.get('xp')!=0:
            raise ValueError('gather_receipt_counter_mismatch')
        snapshot = json.loads(session['source_snapshot_json'])
        if not isinstance(snapshot,dict) or snapshot.get('profession_key')!=session['profession_key']:
            raise ValueError('invalid gathering snapshot')
        if snapshot!=_source_snapshot(session['location_id'],session['profession_key']):
            raise ValueError('invalid gathering source provenance')
        selected = gather_tick_roll(session['seed'],tick,snapshot)
    except (ActionRejected,ValueError,TypeError,KeyError,AttributeError,RuntimeError) as exc:
        conn.execute("UPDATE player_gathering_sessions SET status='interrupted',terminal_reason=?,next_due_ms=NULL,revision=revision+1,updated_ms=? WHERE session_id=?", (str(exc),now_ms,session_id))
        from game.player_feedback import record_feedback
        record_feedback(conn,player_id,event_key='recovery:gather:'+session_id,source_kind='gather_session',
            source_id=session_id,event_kind='recovery',payload={'reason':str(exc)},now_ms=now_ms)
        return {'status':'interrupted','reason':str(exc),'session_id':session_id}
    profession = conn.execute('SELECT * FROM player_gathering_professions WHERE telegram_id=? AND profession_key=?', (player_id,session['profession_key'])).fetchone()
    eligible = selected and profession['level']>=selected['required_level'] and tool['tier']>=selected['required_tool_tier']
    granted,progression,xp = [],None,0
    if eligible:
        item = selected['item_id']
        require_item_delivery(grant_item_to_player(player_id,item,1,source='gathering',conn=conn),1)
        xp = gathering_profession_xp_for_success(current_profession_level=profession['level'],required_profession_level=selected['required_level'])
        progression = add_gathering_profession_exp(player_id,session['profession_key'],xp,conn=conn)
        from game.player_feedback import record_progression
        record_progression(conn,player_id,session['profession_key'],progression,request_id)
        register_contract_objective(conn,player_id,'gather',item,1,session['location_id'])
        accounting['items'][item] = accounting['items'].get(item,0)+1
        granted = [{'item_id':item,'quantity':1,'instance_ids':[],'gear_specs':[]}]
    updated_tool = wear_tool(conn,tool,now_ms=now_ms)
    accounting['attempts'] = tick
    accounting['xp'] += xp
    state = 'broken' if updated_tool['durability']==0 else 'completed' if tick>=accounting['max_attempts'] else 'running'
    next_due = session['started_ms']+(tick+1)*8000 if state=='running' else None
    conn.execute('''UPDATE player_gathering_sessions SET last_tick=?,yield_total=?,result_json=?,
        expected_tool_revision=?,status=?,next_due_ms=?,revision=revision+1,updated_ms=? WHERE session_id=?''',
        (tick,sum(accounting['items'].values()),json.dumps(accounting),updated_tool['revision'],state,next_due,now_ms,session_id))
    result = {'schema_version':1,'catalog_version':2,'action_kind':'gather_tick_pxe1','status':state,
        'player_id':player_id,'session_id':session_id,'tick_index':tick,'selected':selected,
        'granted':granted,'consumed':[],'gold_delta':0,'gold_after':player['gold'],'location_id':session['location_id'],
        'progression':[progression.__dict__] if progression else [],'tool':updated_tool,'xp':xp,'result':accounting}
    store_receipt(conn,player_id,request_id,'gather_tick_pxe1',request_hash,result,catalog_version=2)
    return result


def stop_gathering_session(conn, player_id: int, session_id: str, *, now_ms: int) -> dict:
    session = conn.execute('SELECT * FROM player_gathering_sessions WHERE session_id=? AND player_id=?', (session_id,player_id)).fetchone()
    if not session:
        raise ActionRejected('session_missing')
    if session['status']!='running':
        return dict(session)
    from game.world_activity_tick import reconcile_player_due_events
    reconcile_player_due_events(conn,player_id,now_ms=now_ms)
    session = conn.execute('SELECT * FROM player_gathering_sessions WHERE session_id=?', (session_id,)).fetchone()
    while session['status']=='running' and (session['next_due_ms'] is None or session['next_due_ms']<=now_ms):
        commit_gathering_tick(conn,session_id,now_ms=now_ms)
        session = conn.execute('SELECT * FROM player_gathering_sessions WHERE session_id=?', (session_id,)).fetchone()
    if session['status']=='running':
        conn.execute("UPDATE player_gathering_sessions SET status='cancelled',next_due_ms=NULL,revision=revision+1,updated_ms=? WHERE session_id=?", (now_ms,session_id))
    return dict(conn.execute('SELECT * FROM player_gathering_sessions WHERE session_id=?', (session_id,)).fetchone())


def interrupt_gathering_at_startup(conn, *, now_ms: int) -> int:
    sessions = conn.execute("SELECT player_id,session_id FROM player_gathering_sessions WHERE status='running'").fetchall()
    count = conn.execute("""UPDATE player_gathering_sessions SET status='interrupted',terminal_reason='restart',
        next_due_ms=NULL,revision=revision+1,updated_ms=? WHERE status='running'""", (now_ms,)).rowcount
    from game.player_feedback import record_feedback
    for session in sessions:
        record_feedback(conn,session['player_id'],event_key='recovery:gather:'+session['session_id'],
            source_kind='gather_session',source_id=session['session_id'],event_kind='recovery',
            payload={'reason':'restart','session_id':session['session_id']},now_ms=now_ms)
    return count
