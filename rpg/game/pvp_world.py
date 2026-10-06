"""PXE1 preparation and locked membership under the existing PvP owner.

Mutation helpers require the caller's SQLite writer. The old live-battle path
remains in pvp_live for world_model_version=0.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone

from game.action_receipts import ActionRejected, consume_action
from game.actor_snapshot import build_actor_snapshot
from game.build_contract import RULES_VERSION
from game.economy_actions import store_receipt
from game.locations import get_location_security_tier, resolve_location_id
from game.player_activity import interrupt_peaceful_activity, player_activity, require_available
from game.pvp_rules import (
    get_attack_block_reason, has_respawn_protection, is_aggression_illegal,
    is_recent_retaliation_context, resolve_illegal_aggression_infamy, should_apply_red_flag,
)


def encoded(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def iso(now_ms: int) -> str:
    return datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).isoformat()


def milliseconds(value: str) -> int:
    stamp = datetime.fromisoformat(value)
    return int(stamp.replace(tzinfo=stamp.tzinfo or timezone.utc).timestamp() * 1000)


def _writer(conn):
    if not conn.in_transaction:
        raise RuntimeError('PvP mutation requires a caller-owned writer')


def player(conn, player_id: int) -> dict:
    row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (player_id,)).fetchone()
    if not row:
        raise ActionRejected('missing_player')
    return dict(row)


def engagement(conn, engagement_id: int):
    row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
    if not row or row['world_model_version'] != 1:
        raise ActionRejected('engagement_missing')
    return row


def _pending(row, now_ms, *, before_deadline=True):
    if row['engagement_state'] != 'pending':
        raise ActionRejected('engagement_not_pending')
    if before_deadline and now_ms >= milliseconds(row['engagement_ready_at']):
        raise ActionRejected('deadline_elapsed')


def _side(row, principal_id):
    if principal_id == row['attacker_id']:
        return 'initiator'
    if principal_id == row['defender_id']:
        return 'defender'
    raise ActionRejected('not_principal')


def _local_available(conn, row, player_id, *, voluntary=False, now_ms):
    actor = require_available(conn, player_id, exclude_pvp=row['id'])
    if resolve_location_id(actor['location_id']) != row['location_id']:
        raise ActionRejected('not_same_location')
    if voluntary and get_location_security_tier(row['location_id']) == 'guarded' and has_respawn_protection(actor, now_ts=now_ms // 1000):
        raise ActionRejected('respawn_protection')
    return actor


def members(conn, row, *, status='accepted') -> dict[str, list[dict]]:
    sides = {'initiator': [{'player_id': row['attacker_id'], 'reinforcement_id': None}],
             'defender': [{'player_id': row['defender_id'], 'reinforcement_id': None}]}
    for invite in conn.execute('''SELECT * FROM pvp_engagement_reinforcements
            WHERE engagement_id=? AND membership_version=1 AND status=? ORDER BY responded_at,id''', (row['id'], status)):
        if invite['side'] not in sides or len(sides[invite['side']]) >= 2:
            raise ActionRejected('corrupt_membership')
        sides[invite['side']].append({'player_id': invite['ally_id'], 'reinforcement_id': invite['id'],
            'inviter_id': invite['inviter_id'], 'invited_at': invite['invited_at'], 'accepted_at': invite['responded_at']})
    return sides


def blocked_pair(conn, row, sides):
    for attacker in sides['initiator']:
        for defender in sides['defender']:
            reason = get_attack_block_reason(attacker=player(conn, attacker['player_id']),
                defender=player(conn, defender['player_id']), location_id=row['location_id'])
            if reason:
                return attacker, defender, reason
    return None


def _crime(conn, actor, target, location_id):
    retaliation = is_recent_retaliation_context(attacker_id=actor['telegram_id'], defender_id=target['telegram_id'], conn=conn)
    delta = resolve_illegal_aggression_infamy(attacker=actor, defender=target, location_id=location_id, conn=conn)
    flag = should_apply_red_flag(attacker=actor, defender=target, location_id=location_id)
    if delta or flag:
        conn.execute('UPDATE players SET infamy=infamy+?,red_flag=CASE WHEN ? THEN 1 ELSE red_flag END WHERE telegram_id=?',
                     (delta, flag, actor['telegram_id']))
    return {'initiator_snapshot': actor, 'original_defender_snapshot': target,
            'initiation_infamy': delta, 'red_flag_applied': flag, 'retaliation_context': retaliation}


def create_preparation(conn, *, attacker_id, defender_id, location_id, now_ms, seed=None):
    _writer(conn)
    location_id = resolve_location_id(location_id)
    attacker = require_available(conn, attacker_id)
    defender = player(conn, defender_id)
    target_activity = player_activity(conn, defender_id)
    if target_activity and target_activity['kind'] not in {'travel', 'gather'}:
        raise ActionRejected('defender_busy')
    if any(resolve_location_id(p['location_id']) != location_id for p in (attacker, defender)):
        raise ActionRejected('not_same_location')
    reason = get_attack_block_reason(attacker=attacker, defender=defender, location_id=location_id)
    if reason:
        raise ActionRejected(reason)
    seed = seed or secrets.token_hex(16)
    if len(seed) != 32 or len(bytes.fromhex(seed)) != 16:
        raise ActionRejected('invalid_seed')
    context = {'schema_version': 1, 'catalog_version': 2, 'flow': 'open_world_group', 'battle': None,
               'illegal_aggression': is_aggression_illegal(attacker=attacker, defender=defender, location_id=location_id),
               'crime_context': {str(attacker_id): _crime(conn, attacker, defender, location_id)}}
    # Interruption, crime and the reservation are one atomic hostile transition.
    interrupt_peaceful_activity(conn, defender_id, reason='incoming_pvp', now_ms=now_ms)
    conn.execute('UPDATE players SET pvp_respawn_protection_until=0 WHERE telegram_id=?', (attacker_id,))
    cur = conn.execute('''INSERT INTO pvp_engagements
        (attacker_id,defender_id,location_id,engagement_started_at,engagement_ready_at,
         engagement_state,reason_context,world_model_version,combat_seed)
        VALUES (?,?,?,?,?,'pending',?,1,?)''',
        (attacker_id, defender_id, location_id, iso(now_ms), iso(now_ms + 300000), encoded(context), seed))
    return cur.lastrowid


def invite(conn, *, engagement_id, principal_id, ally_id, now_ms):
    _writer(conn)
    row = engagement(conn, engagement_id)
    _pending(row, now_ms)
    side = _side(row, principal_id)
    _local_available(conn, row, principal_id, now_ms=now_ms)
    _local_available(conn, row, ally_id, voluntary=True, now_ms=now_ms)
    if ally_id in {row['attacker_id'], row['defender_id']}:
        raise ActionRejected('already_participant')
    if conn.execute('SELECT 1 FROM pvp_engagement_reinforcements WHERE engagement_id=? AND ally_id=? AND membership_version=1', (engagement_id, ally_id)).fetchone():
        raise ActionRejected('cannot_rejoin')
    if conn.execute("SELECT 1 FROM pvp_engagement_reinforcements WHERE engagement_id=? AND side=? AND membership_version=1 AND status IN ('pending','accepted','locked')", (engagement_id, side)).fetchone():
        raise ActionRejected('side_full')
    sides = members(conn, row)
    sides[side].append({'player_id': ally_id, 'reinforcement_id': -1})
    blocked = blocked_pair(conn, row, sides)
    if blocked:
        raise ActionRejected(blocked[2])
    conn.execute('''INSERT INTO pvp_engagement_reinforcements
        (engagement_id,side,inviter_id,ally_id,status,membership_version,invited_at)
        VALUES (?,?,?,?,'pending',1,?)''', (engagement_id, side, principal_id, ally_id, iso(now_ms)))
    conn.execute('UPDATE pvp_engagements SET state_revision=state_revision+1 WHERE id=?', (engagement_id,))


def respond(conn, *, engagement_id, ally_id, accepted, now_ms):
    _writer(conn)
    row = engagement(conn, engagement_id)
    _pending(row, now_ms)
    invitation = conn.execute("SELECT * FROM pvp_engagement_reinforcements WHERE engagement_id=? AND ally_id=? AND membership_version=1 AND status='pending'", (engagement_id, ally_id)).fetchone()
    if not invitation:
        raise ActionRejected('invitation_required')
    if accepted:
        side = _side(row, invitation['inviter_id'])
        if side != invitation['side']:
            raise ActionRejected('corrupt_membership')
        _local_available(conn, row, invitation['inviter_id'], now_ms=now_ms)
        actor = _local_available(conn, row, ally_id, voluntary=True, now_ms=now_ms)
        sides = members(conn, row)
        if len(sides[side]) != 1:
            raise ActionRejected('side_full')
        sides[side].append({'player_id': ally_id, 'reinforcement_id': invitation['id']})
        blocked = blocked_pair(conn, row, sides)
        if blocked:
            raise ActionRejected(blocked[2])
        context = json.loads(row['reason_context'])
        if side == 'initiator':
            target = context['crime_context'][str(row['attacker_id'])]['original_defender_snapshot']
            context['crime_context'][str(ally_id)] = _crime(conn, actor, target, row['location_id'])
        if get_location_security_tier(row['location_id']) in {'frontier','core_war'}:
            conn.execute('UPDATE players SET pvp_respawn_protection_until=0 WHERE telegram_id=?', (ally_id,))
        conn.execute("UPDATE pvp_engagement_reinforcements SET status='expired',responded_at=? WHERE ally_id=? AND membership_version=1 AND status='pending' AND id<>?", (iso(now_ms), ally_id, invitation['id']))
        conn.execute('UPDATE pvp_engagements SET reason_context=? WHERE id=?', (encoded(context), engagement_id))
    conn.execute('UPDATE pvp_engagement_reinforcements SET status=?,responded_at=? WHERE id=?', ('accepted' if accepted else 'rejected', iso(now_ms), invitation['id']))
    conn.execute('UPDATE pvp_engagements SET state_revision=state_revision+1 WHERE id=?', (engagement_id,))


def leave_or_revoke(conn, *, engagement_id, actor_id, ally_id=None, now_ms):
    _writer(conn)
    row = engagement(conn, engagement_id)
    _pending(row, now_ms, before_deadline=False)
    if ally_id is None:
        updated = conn.execute("UPDATE pvp_engagement_reinforcements SET status='left',responded_at=? WHERE engagement_id=? AND ally_id=? AND membership_version=1 AND status='accepted'", (iso(now_ms), engagement_id, actor_id))
    else:
        side = _side(row, actor_id)
        updated = conn.execute("UPDATE pvp_engagement_reinforcements SET status='revoked',responded_at=? WHERE engagement_id=? AND ally_id=? AND inviter_id=? AND side=? AND membership_version=1 AND status='pending'", (iso(now_ms), engagement_id, ally_id, actor_id, side))
    if updated.rowcount != 1:
        raise ActionRejected('membership_missing')
    conn.execute('UPDATE pvp_engagements SET state_revision=state_revision+1 WHERE id=?', (engagement_id,))


def apply_membership_intent(conn,*,actor_id,token,now_ms):
    """Consume a complete preparation choice and replay its immutable receipt."""
    from game.economy_actions import intent_hash
    _writer(conn)
    kind='pvp_membership_pxe1';request_id='ui:'+token
    prior=conn.execute('SELECT * FROM economy_action_receipts WHERE player_id=? AND request_id=?',(actor_id,request_id)).fetchone()
    if prior:
        result=json.loads(prior['result_json'])
        if (prior['action_kind']!=kind or result.get('actor_id')!=actor_id
                or prior['request_hash']!=intent_hash(kind,actor_id,result.get('intent',{}))):
            raise ActionRejected('stale_action')
        return {**result,'recovered':True}
    intent=json.loads(consume_action(conn,actor_id,kind,token))
    if intent.get('schema_version')!=1 or intent.get('catalog_version')!=2:
        raise ActionRejected('stale_action')
    row=engagement(conn,intent.get('engagement_id'))
    if row['state_revision']!=intent.get('state_revision'):
        raise ActionRejected('stale_action')
    operation=intent.get('operation')
    member=None
    if operation in {'accept','decline','revoke','leave'}:
        member=conn.execute('SELECT * FROM pvp_engagement_reinforcements WHERE id=? AND engagement_id=? AND membership_version=1',
                            (intent.get('reinforcement_id'),row['id'])).fetchone()
        if not member: raise ActionRejected('membership_missing')
        if operation in {'accept','decline','leave'} and member['ally_id']!=actor_id:
            raise ActionRejected('not_participant')
        if operation=='revoke' and (member['inviter_id']!=actor_id or member['ally_id']!=intent.get('ally_id')):
            raise ActionRejected('not_principal')
    if operation=='invite':
        invite(conn,engagement_id=row['id'],principal_id=actor_id,ally_id=intent.get('ally_id'),now_ms=now_ms)
        member=conn.execute('SELECT * FROM pvp_engagement_reinforcements WHERE engagement_id=? AND ally_id=? AND membership_version=1',
                            (row['id'],intent['ally_id'])).fetchone()
    elif operation in {'accept','decline'}:
        respond(conn,engagement_id=row['id'],ally_id=actor_id,accepted=operation=='accept',now_ms=now_ms)
    elif operation in {'leave','revoke'}:
        leave_or_revoke(conn,engagement_id=row['id'],actor_id=actor_id,ally_id=intent.get('ally_id') if operation=='revoke' else None,now_ms=now_ms)
    else: raise ActionRejected('invalid_action')
    current=engagement(conn,row['id'])
    member=conn.execute('SELECT * FROM pvp_engagement_reinforcements WHERE id=?',(member['id'],)).fetchone()
    result={'schema_version':1,'catalog_version':2,'action_kind':kind,'actor_id':actor_id,
        'engagement_id':row['id'],'reinforcement_id':member['id'],'ally_id':member['ally_id'],
        'operation':operation,'outcome':member['status'],'side':member['side'],
        'state_revision_before':row['state_revision'],'state_revision_after':current['state_revision'],
        'gold_delta':0,'granted':[],'consumed':[],'progression':[],'intent':intent}
    store_receipt(conn,actor_id,request_id,kind,intent_hash(kind,actor_id,intent),result,catalog_version=2)
    return result


def cancel_preparation(conn, row, *, reason, now_ms):
    context = json.loads(row['reason_context'])
    context['terminal_reason'] = reason
    conn.execute("UPDATE pvp_engagements SET engagement_state='cancelled',reason_context=?,state_revision=state_revision+1 WHERE id=?", (encoded(context), row['id']))
    conn.execute("UPDATE pvp_engagement_reinforcements SET status='expired',responded_at=? WHERE engagement_id=? AND membership_version=1 AND status IN ('accepted','pending')", (iso(now_ms), row['id']))
    return 'cancelled', context


def lock_preparation(conn, *, engagement_id, now_ms, failed_escape=False):
    _writer(conn)
    row = engagement(conn, engagement_id)
    if row['engagement_state'] != 'pending' or (not failed_escape and now_ms < milliseconds(row['engagement_ready_at'])):
        return row['engagement_state'], json.loads(row['reason_context'])
    try:
        for principal in (row['attacker_id'], row['defender_id']):
            _local_available(conn, row, principal, now_ms=now_ms)
        sides = members(conn, row)
        for side in sides.values():
            for member in side[1:]:
                try:
                    _local_available(conn, row, member['player_id'], voluntary=True, now_ms=now_ms)
                except ActionRejected:
                    conn.execute("UPDATE pvp_engagement_reinforcements SET status='expired',responded_at=? WHERE id=?", (iso(now_ms), member['reinforcement_id']))
        sides = members(conn, row)
        while blocked := blocked_pair(conn, row, sides):
            implicated = [m for m in blocked[:2] if m['reinforcement_id'] is not None]
            if not implicated:
                return cancel_preparation(conn, row, reason=blocked[2], now_ms=now_ms)
            remove = max(implicated, key=lambda m: (m.get('accepted_at') or '', m['reinforcement_id']))
            conn.execute("UPDATE pvp_engagement_reinforcements SET status='expired',responded_at=? WHERE id=?", (iso(now_ms), remove['reinforcement_id']))
            sides = members(conn, row)
    except ActionRejected as exc:
        return cancel_preparation(conn, row, reason=str(exc), now_ms=now_ms)
    context = json.loads(row['reason_context'])
    actors = {}
    for member in sides['initiator'] + sides['defender']:
        actor = build_actor_snapshot(member['player_id'], conn=conn)
        actor['pve_passives_enabled'] = False
        actors[str(member['player_id'])] = actor
    battle = {'state': 'live', 'rules_version': RULES_VERSION, 'world_model_version': 1,
        'combat_seed': row['combat_seed'], 'participants_v1': actors, 'events_v1': [],
        'active_side': 'side_a', 'turn_revision': 1, 'side_turn_state': 'collecting_orders',
        'side_deadline_at': iso(now_ms + 15000), 'damage_by_source': {}, 'manual_actor_ids': []}
    context['battle'] = battle
    roster = {'schema_version': 1, 'side_a': sides['initiator'], 'side_b': sides['defender']}
    conn.execute('''UPDATE pvp_engagements SET engagement_state='converted_to_battle',
        reason_context=?,locked_roster_json=?,roster_locked_ms=?,rules_version=?,turn_revision=1,
        state_revision=state_revision+1 WHERE id=? AND engagement_state='pending' ''',
        (encoded(context), encoded(roster), now_ms, RULES_VERSION, engagement_id))
    conn.execute("UPDATE pvp_engagement_reinforcements SET status=CASE WHEN status='accepted' THEN 'locked' ELSE 'expired' END WHERE engagement_id=? AND membership_version=1 AND status IN ('accepted','pending')", (engagement_id,))
    conn.executemany('UPDATE players SET in_battle=1 WHERE telegram_id=?', ((int(p),) for p in actors))
    return 'converted_to_battle', context


def escape_roll(seed, token):
    seed_bytes = bytes.fromhex(seed)
    if len(seed_bytes) != 16:
        raise ActionRejected('invalid_seed')
    n = int.from_bytes(hashlib.sha256(seed_bytes + b':pvp-prep-escape:' + token.encode('ascii')).digest()[:8], 'big')
    return n < 2**63


def attempt_escape(conn, *, engagement_id, actor_id, token, now_ms):
    _writer(conn)
    request_id = f'ui:{token}'
    prior = conn.execute('SELECT action_kind,result_json FROM economy_action_receipts WHERE player_id=? AND request_id=?', (actor_id, request_id)).fetchone()
    if prior:
        result = json.loads(prior['result_json'])
        if prior['action_kind'] != 'pvp_prep_escape_pxe1' or result['engagement_id'] != engagement_id:
            raise ActionRejected('stale_action')
        return result
    row = engagement(conn, engagement_id)
    _side(row, actor_id)
    _pending(row, now_ms, before_deadline=False)
    if now_ms >= milliseconds(row['engagement_ready_at']):
        state, _ = lock_preparation(conn, engagement_id=engagement_id, now_ms=now_ms)
        return {'engagement_id': engagement_id, 'state': state, 'rolled': False}
    intent = json.loads(consume_action(conn, actor_id, 'pvp_prep_escape', token))
    if intent != {'schema_version': 1, 'catalog_version': 2, 'engagement_id': engagement_id, 'state_revision': row['state_revision']}:
        raise ActionRejected('stale_action')
    success = escape_roll(row['combat_seed'], token)
    if success:
        conn.execute("UPDATE pvp_engagements SET engagement_state='escaped',state_revision=state_revision+1 WHERE id=?", (engagement_id,))
        conn.execute("UPDATE pvp_engagement_reinforcements SET status='expired',responded_at=? WHERE engagement_id=? AND membership_version=1 AND status IN ('pending','accepted')", (iso(now_ms), engagement_id))
        state = 'escaped'
    else:
        state, _ = lock_preparation(conn, engagement_id=engagement_id, now_ms=now_ms, failed_escape=True)
    result = {'schema_version': 1, 'catalog_version': 2, 'engagement_id': engagement_id,
              'actor_id': actor_id, 'state': state, 'success': success, 'rolled': True}
    store_receipt(conn, actor_id, request_id, 'pvp_prep_escape_pxe1', hashlib.sha256(encoded(intent).encode()).hexdigest(), result, catalog_version=2)
    return result
