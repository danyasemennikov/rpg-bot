import hashlib
import json
from unittest.mock import patch

import database
from game.gathering_runtime import (
    _source_snapshot,commit_gathering_tick,gather_tick_roll,interrupt_gathering_at_startup,
    start_gathering_session,stop_gathering_session,
)
from game.player_experience_schema import grant_player_pxe1_starters


def start(*,durability=60,seed='00000000000000000000000000000000',location='old_mine_entrance',profession='mining',request='one'):
    conn = database.get_connection()
    conn.execute('BEGIN IMMEDIATE')
    grant_player_pxe1_starters(conn,1,now_ms=0,acquired_via='starter')
    conn.execute('UPDATE players SET location_id=? WHERE telegram_id=1', (location,))
    conn.execute('UPDATE player_profession_tools SET durability=? WHERE player_id=1 AND profession_key=?', (durability,profession))
    result = start_gathering_session(conn,1,profession,location_id=location,request_id=request,now_ms=1000,seed=seed)
    conn.commit()
    return conn,result['session']['session_id']


def test_no_instant_grant_and_fifteen_ticks_no_sixteenth():
    conn,session = start()
    assert not conn.execute('SELECT 1 FROM inventory WHERE telegram_id=1').fetchone()
    for tick in range(1,16):
        conn.execute('BEGIN IMMEDIATE')
        assert commit_gathering_tick(conn,session,now_ms=1000+tick*8000-1)['status']=='running'
        result = commit_gathering_tick(conn,session,now_ms=1000+tick*8000)
        conn.commit()
        assert result['tick_index']==tick
        assert result['tool']['durability']==60-tick
    assert result['status']=='completed'
    assert result['result']['attempts']==15
    assert sum(result['result']['items'].values())<=15
    conn.execute('BEGIN IMMEDIATE')
    assert commit_gathering_tick(conn,session,now_ms=1000000)['status']=='completed'
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM economy_action_receipts WHERE action_kind='gather_tick_pxe1'").fetchone()[0]==15
    conn.close()


def test_corrupt_accounting_or_source_interrupts_without_new_yield_or_wear():
    for corruption in ('missing_receipt','counter','source'):
        conn,session=start(request=corruption)
        conn.execute('BEGIN IMMEDIATE');commit_gathering_tick(conn,session,now_ms=9000);conn.commit()
        before=[tuple(r) for r in conn.execute('SELECT * FROM inventory')]
        tool_before=tuple(conn.execute("SELECT durability,revision FROM player_profession_tools WHERE player_id=1 AND profession_key='mining'").fetchone())
        if corruption=='missing_receipt':
            conn.execute('DELETE FROM economy_action_receipts WHERE request_id=?',(f'gather:{session}:1',))
        elif corruption=='counter':
            conn.execute('UPDATE player_gathering_sessions SET last_tick=0 WHERE session_id=?',(session,))
        else:
            row=conn.execute('SELECT source_snapshot_json FROM player_gathering_sessions WHERE session_id=?',(session,)).fetchone()
            source=json.loads(row[0]);source['entries'][0]['chance_bp']=6000
            conn.execute('UPDATE player_gathering_sessions SET source_snapshot_json=? WHERE session_id=?',(json.dumps(source),session))
        conn.commit();conn.execute('BEGIN IMMEDIATE')
        result=commit_gathering_tick(conn,session,now_ms=17000);conn.commit()
        assert result['status']=='interrupted'
        assert before==[tuple(r) for r in conn.execute('SELECT * FROM inventory')]
        assert tool_before==tuple(conn.execute("SELECT durability,revision FROM player_profession_tools WHERE player_id=1 AND profession_key='mining'").fetchone())
        assert conn.execute('SELECT state FROM player_feedback_events WHERE event_key=?',('recovery:gather:'+session,)).fetchone()[0]=='pending'
        conn.close()


def test_exact_decoded_seed_encoding_and_unrenormalized_locked_gem():
    snapshot = _source_snapshot('old_mine_entrance','mining')
    assert [e['chance_bp'] for e in snapshot['entries']]==[6500,3000,500]
    seed = '0123456789abcdef0123456789abcdef'
    for index in range(1,16):
        expected_n = int.from_bytes(hashlib.sha256(bytes.fromhex(seed)+b':gather:'+str(index).encode('ascii')).digest()[:8],'big')
        expected = 'iron_ore' if expected_n*10000<6500*(1<<64) else 'coal' if expected_n*10000<9500*(1<<64) else 'gem_common'
        assert gather_tick_roll(seed,index,snapshot)['item_id']==expected
    # A boundary comparison uses integers and a strict less-than relation.
    fake = type('Digest',(),{'digest':lambda self: ((1<<63).to_bytes(8,'big')+bytes(24))})()
    modified = {'schema_version':1,'catalog_version':2,'profession_key':'mining','entries':[
        {'item_id':'iron_ore','chance_bp':5000,'required_level':1,'required_tool_tier':1},
        {'item_id':'coal','chance_bp':5000,'required_level':1,'required_tool_tier':1}]}
    with patch('hashlib.sha256',return_value=fake):
        assert gather_tick_roll(seed,1,modified)['item_id']=='coal'


def test_locked_result_still_wears_tool_no_xp_and_last_attempt_stays_awarded():
    # Find a seed whose first interval is gem using the independent reference.
    seed = next(f'{i:032x}' for i in range(1000) if int.from_bytes(hashlib.sha256(bytes.fromhex(f'{i:032x}')+b':gather:1').digest()[:8],'big')*10000>=9500*(1<<64))
    conn,session = start(durability=1,seed=seed)
    conn.execute('BEGIN IMMEDIATE')
    result = commit_gathering_tick(conn,session,now_ms=9000)
    conn.commit()
    assert result['selected']['item_id']=='gem_common'
    assert result['granted']==[] and result['xp']==0
    assert result['status']=='broken' and result['tool']['durability']==0
    conn.close()


def test_stop_equality_keeps_due_tick_and_stale_stop_cannot_cancel_new_session():
    conn,session = start(durability=60)
    conn.execute('BEGIN IMMEDIATE')
    first = stop_gathering_session(conn,1,session,now_ms=9000)
    assert first['last_tick']==1 and first['status']=='cancelled'
    new = start_gathering_session(conn,1,'mining',location_id='old_mine_entrance',request_id='two',now_ms=9000)
    assert new['session']['session_id']!=session
    assert stop_gathering_session(conn,1,session,now_ms=99999)['session_id']==session
    assert conn.execute('SELECT status FROM player_gathering_sessions WHERE session_id=?', (new['session']['session_id'],)).fetchone()[0]=='running'
    conn.commit()
    conn.close()


def test_crash_retry_same_seed_no_duplicate_yield_or_wear_and_restart_no_catchup():
    conn,session = start()
    conn.execute('BEGIN IMMEDIATE')
    first = commit_gathering_tick(conn,session,now_ms=9000)
    conn.rollback()
    conn.execute('BEGIN IMMEDIATE')
    second = commit_gathering_tick(conn,session,now_ms=9000)
    assert first==second
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    assert interrupt_gathering_at_startup(conn,now_ms=999999)==1
    assert commit_gathering_tick(conn,session,now_ms=999999)['status']=='interrupted'
    conn.commit()
    assert conn.execute('SELECT durability FROM player_profession_tools WHERE player_id=1 AND profession_key=\'mining\'').fetchone()[0]==59
    conn.close()
