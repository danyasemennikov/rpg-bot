import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from database import get_connection
from game.action_receipts import ActionRejected, issue_actions
from game.pvp_live import get_pending_player_engagement, is_player_busy_with_live_pvp
from game.pvp_world import (
    attempt_escape, create_preparation, encoded, escape_roll, invite,
    leave_or_revoke, lock_preparation, respond,
)


def prepare():
    conn = get_connection()
    conn.execute("UPDATE players SET location_id='westwild_n4',level=20,novice_protection=0 WHERE telegram_id IN (1,777)")
    for player_id in (2,3,4,5):
        conn.execute("INSERT INTO players(telegram_id,name,location_id,level,hp,max_hp,mana,max_mana,novice_protection) VALUES (?,'Ally','westwild_n4',20,100,100,100,100,0)", (player_id,))
        conn.execute('INSERT INTO equipment(telegram_id) VALUES (?)', (player_id,))
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    engagement_id = create_preparation(conn,attacker_id=1,defender_id=777,location_id='westwild_n4',now_ms=1000000,seed='01'*16)
    conn.commit()
    return conn,engagement_id


def test_invitation_consent_cap_and_no_rejoin():
    conn,e = prepare()
    conn.execute('BEGIN IMMEDIATE')
    with pytest.raises(ActionRejected,match='invitation_required'):
        respond(conn,engagement_id=e,ally_id=2,accepted=True,now_ms=1001000)
    invite(conn,engagement_id=e,principal_id=1,ally_id=2,now_ms=1001000)
    with pytest.raises(ActionRejected,match='side_full'):
        invite(conn,engagement_id=e,principal_id=1,ally_id=3,now_ms=1001000)
    conn.commit()
    assert not is_player_busy_with_live_pvp(2)
    conn.execute('BEGIN IMMEDIATE')
    respond(conn,engagement_id=e,ally_id=2,accepted=True,now_ms=1002000)
    conn.commit()
    assert is_player_busy_with_live_pvp(2)
    assert get_pending_player_engagement(2)['id'] == e
    conn.execute('BEGIN IMMEDIATE')
    leave_or_revoke(conn,engagement_id=e,actor_id=2,now_ms=1301000)
    with pytest.raises(ActionRejected,match='cannot_rejoin'):
        invite(conn,engagement_id=e,principal_id=1,ally_id=2,now_ms=1003000)
    invite(conn,engagement_id=e,principal_id=1,ally_id=3,now_ms=1003000)
    leave_or_revoke(conn,engagement_id=e,actor_id=1,ally_id=3,now_ms=1003000)
    conn.commit()
    assert not is_player_busy_with_live_pvp(2)
    conn.close()


def test_equality_lock_all_snapshots_and_rollback():
    conn,e = prepare()
    conn.execute('BEGIN IMMEDIATE')
    for principal,ally in ((1,2),(777,3)):
        invite(conn,engagement_id=e,principal_id=principal,ally_id=ally,now_ms=1001000)
        respond(conn,engagement_id=e,ally_id=ally,accepted=True,now_ms=1002000)
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    assert lock_preparation(conn,engagement_id=e,now_ms=1299999)[0]=='pending'
    with pytest.raises(ActionRejected,match='deadline_elapsed'):
        invite(conn,engagement_id=e,principal_id=1,ally_id=4,now_ms=1300000)
    with patch('game.pvp_world.build_actor_snapshot',side_effect=RuntimeError('snapshot failure')):
        with pytest.raises(RuntimeError):
            lock_preparation(conn,engagement_id=e,now_ms=1300000)
    conn.rollback()
    assert conn.execute('SELECT locked_roster_json FROM pvp_engagements WHERE id=?',(e,)).fetchone()[0] is None
    conn.execute('BEGIN IMMEDIATE')
    state,context = lock_preparation(conn,engagement_id=e,now_ms=1300000)
    conn.commit()
    assert state=='converted_to_battle'
    row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(e,)).fetchone()
    roster = json.loads(row['locked_roster_json'])
    assert [m['player_id'] for m in roster['side_a']]==[1,2]
    assert [m['player_id'] for m in roster['side_b']]==[777,3]
    assert set(context['battle']['participants_v1'])=={'1','2','777','3'}
    assert all(not a['pve_passives_enabled'] for a in context['battle']['participants_v1'].values())
    assert [r[0] for r in conn.execute("SELECT status FROM pvp_engagement_reinforcements WHERE engagement_id=? ORDER BY id",(e,))]==['locked','locked']
    with pytest.raises(ActionRejected,match='engagement_not_pending'):
        conn.execute('BEGIN IMMEDIATE')
        leave_or_revoke(conn,engagement_id=e,actor_id=2,now_ms=1300001)
    conn.rollback()
    conn.close()


def test_two_invitations_one_acceptance_expires_other_without_busy_invite():
    conn,e = prepare()
    conn.execute('BEGIN IMMEDIATE')
    second = create_preparation(conn,attacker_id=4,defender_id=5,location_id='westwild_n4',now_ms=1000000)
    invite(conn,engagement_id=e,principal_id=1,ally_id=2,now_ms=1001000)
    invite(conn,engagement_id=second,principal_id=4,ally_id=2,now_ms=1001000)
    conn.commit()
    def accept(engagement_id):
        c = get_connection()
        try:
            c.execute('BEGIN IMMEDIATE')
            respond(c,engagement_id=engagement_id,ally_id=2,accepted=True,now_ms=1002000)
            c.commit()
            return True
        except ActionRejected:
            c.rollback()
            return False
        finally:
            c.close()
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(accept,[e,second]))==[False,True]
    assert sorted(r[0] for r in conn.execute('SELECT status FROM pvp_engagement_reinforcements WHERE ally_id=2'))==['accepted','expired']
    conn.close()


def test_escape_exact_hash_actor_binding_and_replay():
    conn,e = prepare()
    payload = encoded({'schema_version':1,'catalog_version':2,'engagement_id':e,'state_revision':0})
    token = issue_actions(1,'pvp_prep_escape',[payload])[payload]
    expected = int.from_bytes(hashlib.sha256(bytes.fromhex('01'*16)+b':pvp-prep-escape:'+token.encode('ascii')).digest()[:8],'big') < 2**63
    assert escape_roll('01'*16,token)==expected
    conn.execute('BEGIN IMMEDIATE')
    with pytest.raises(ActionRejected,match='not_principal'):
        attempt_escape(conn,engagement_id=e,actor_id=2,token=token,now_ms=1001000)
    with patch('time.time',return_value=1000):
        result = attempt_escape(conn,engagement_id=e,actor_id=1,token=token,now_ms=1001000)
    conn.commit()
    assert result['success']==expected
    conn.execute('BEGIN IMMEDIATE')
    assert attempt_escape(conn,engagement_id=e,actor_id=1,token=token,now_ms=999999999)==result
    conn.commit()
    assert conn.execute("SELECT catalog_version FROM economy_action_receipts WHERE action_kind='pvp_prep_escape_pxe1'").fetchone()[0]==2
    conn.close()


def test_invalid_principal_cancels_invalid_ally_expires():
    conn,e = prepare()
    conn.execute('BEGIN IMMEDIATE')
    invite(conn,engagement_id=e,principal_id=1,ally_id=2,now_ms=1001000)
    respond(conn,engagement_id=e,ally_id=2,accepted=True,now_ms=1002000)
    conn.execute("UPDATE players SET location_id='capital_city' WHERE telegram_id=2")
    state,_ = lock_preparation(conn,engagement_id=e,now_ms=1300000)
    conn.commit()
    assert state=='converted_to_battle'
    assert conn.execute('SELECT status FROM pvp_engagement_reinforcements WHERE ally_id=2').fetchone()[0]=='expired'
    conn.close()
