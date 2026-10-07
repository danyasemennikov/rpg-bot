"""Connection-scoped activity projection; existing domain rows remain authority."""

from game.action_receipts import ActionRejected


def player_activity(conn, player_id: int, *, exclude_pve=None, exclude_pvp=None,
                    exclude_travel=None, exclude_gather=None) -> dict | None:
    player = conn.execute('SELECT * FROM players WHERE telegram_id=?', (player_id,)).fetchone()
    if not player:
        raise ActionRejected('no_player')
    if int(player['hp'] or 0) <= 0:
        return {'kind': 'dead', 'ref': None}
    rows = conn.execute('''SELECT e.encounter_id,e.status FROM pve_encounter_participants p
        JOIN pve_encounters e ON e.encounter_id=p.encounter_id
        WHERE p.player_id=? AND p.status='active' AND e.status IN ('active','forming','resolving_victory')
        ORDER BY e.encounter_id''', (player_id,)).fetchall()
    for row in rows:
        if row['encounter_id'] != exclude_pve:
            return {'kind': 'pve', 'ref': row['encounter_id']}
    rows = conn.execute('''SELECT e.* FROM pvp_engagements e
        WHERE e.engagement_state IN ('pending','active','converted_to_battle') AND
        (e.attacker_id=? OR e.defender_id=? OR EXISTS(
            SELECT 1 FROM pvp_engagement_reinforcements r WHERE r.engagement_id=e.id AND r.ally_id=?
            AND r.status IN ('accepted','locked'))) ORDER BY e.id''', (player_id,player_id,player_id)).fetchall()
    for row in rows:
        if row['id'] == exclude_pvp:
            continue
        if row['world_model_version'] == 1 and conn.execute('''SELECT 1 FROM pvp_participant_settlements_pxe1
            WHERE engagement_id=? AND player_id=?''', (row['id'],player_id)).fetchone():
            continue  # Individually settled deaths release even a defeated principal.
        return {'kind': 'pvp', 'ref': row['id']}
    if player['in_battle'] and exclude_pve is None and exclude_pvp is None:
        return {'kind': 'combat', 'ref': None}
    for table, kind, excluded in (
        ('player_travel_sessions','travel',exclude_travel),
        ('player_gathering_sessions','gather',exclude_gather),
    ):
        row = conn.execute(f"SELECT session_id FROM {table} WHERE player_id=? AND status='running'", (player_id,)).fetchone()
        if row and row['session_id'] != excluded:
            return {'kind': kind, 'ref': row['session_id']}
    return None


def require_available(conn, player_id: int, *, spend_attributes=False, **exclusions) -> dict:
    activity = player_activity(conn, player_id, **exclusions)
    if activity and not (spend_attributes and activity['kind'] in {'travel','gather'}):
        reason = 'dead' if activity['kind'] == 'dead' else (
            'stop_activity_first' if activity['kind'] in {'travel','gather'} else 'in_battle')
        raise ActionRejected(reason)
    return dict(conn.execute('SELECT * FROM players WHERE telegram_id=?', (player_id,)).fetchone())


def interrupt_peaceful_activity(conn, player_id: int, *, reason: str, now_ms: int) -> None:
    """Caller first validates the hostile transition and commits both together."""
    for table in ('player_travel_sessions','player_gathering_sessions'):
        conn.execute(f'''UPDATE {table} SET status='interrupted',terminal_reason=?,next_due_ms=NULL,
            revision=revision+1,updated_ms=? WHERE player_id=? AND status='running' ''',
            (reason,now_ms,player_id))


def recover_activity_overlaps(conn,*,now_ms):
    """Preserve committed combat/location; stop lower-priority travel on restart."""
    _recover_combat_preparation_overlaps(conn,now_ms=now_ms)
    from game.player_feedback import record_feedback
    for session in conn.execute("SELECT session_id,player_id FROM player_travel_sessions WHERE status='running'").fetchall():
        activity=player_activity(conn,session['player_id'],exclude_travel=session['session_id'])
        if activity and activity['kind'] not in {'travel','gather'}:
            conn.execute("""UPDATE player_travel_sessions SET status='interrupted',terminal_reason='activity_overlap',
                next_due_ms=NULL,revision=revision+1,updated_ms=? WHERE session_id=?""",(now_ms,session['session_id']))
            record_feedback(conn,session['player_id'],event_key='recovery:travel:'+session['session_id'],
                source_kind='travel_session',source_id=session['session_id'],event_kind='recovery',
                payload={'reason':'activity_overlap'},now_ms=now_ms)


def _recover_combat_preparation_overlaps(conn,*,now_ms):
    """An existing live fight owns its actors before unstarted commitments."""
    import json
    from game.pve_live import pve_world_phase,_interrupt_pxe1_formation,_quarantine_pxe1_active_encounter,_validate_pxe1_active_state
    from game.pvp_world import cancel_preparation,iso,milliseconds
    from game.pvp_group_runtime import quarantine_live_group,validate_live_group
    from game.build_contract import RULES_VERSION
    from game.player_experience_schema import _recovery_notice
    if not conn.in_transaction:
        raise RuntimeError('activity recovery requires a caller-owned writer')
    live_actors=set()
    live_candidates=[]
    for row in conn.execute("SELECT * FROM pve_encounters WHERE status IN ('active','resolving_victory')").fetchall():
        live=(row['status']=='resolving_victory' or row['runtime_started_ms'] is not None
              or row['lifecycle_version']==1 and row['locked_roster_json'] is not None
              or row['lifecycle_version']==0 and pve_world_phase(conn,row['encounter_id'])=='active')
        if live:
            members={r['player_id'] for r in conn.execute(
                "SELECT player_id FROM pve_encounter_participants WHERE encounter_id=? AND status='active'",(row['encounter_id'],))}
            if row['status']=='resolving_victory' or row['lifecycle_version']!=1 or row['rules_version']!=RULES_VERSION:
                live_actors.update(members)
            else:
                try: _validate_pxe1_active_state(row)
                except ValueError as exc:
                    _quarantine_pxe1_active_encounter(conn,row,now_ms=now_ms,reason=str(exc))
                    continue
                live_candidates.append((int(row['runtime_started_ms'] or 0),'pve',row['encounter_id'],row,members))
    for row in conn.execute("SELECT * FROM pvp_engagements WHERE engagement_state IN ('active','converted_to_battle')").fetchall():
        try:
            context=json.loads(row['reason_context'])
            live=row['engagement_state']=='converted_to_battle' or context.get('battle',{}).get('state')=='live'
        except (ValueError,TypeError,AttributeError):
            live=row['engagement_state']=='converted_to_battle'
        if not live:
            continue
        members={row['attacker_id'],row['defender_id']}
        members.update(r['ally_id'] for r in conn.execute(
            "SELECT ally_id FROM pvp_engagement_reinforcements WHERE engagement_id=? AND status='locked'",(row['id'],)))
        if row['world_model_version']==1:
            members.difference_update(r['player_id'] for r in conn.execute(
                'SELECT player_id FROM pvp_participant_settlements_pxe1 WHERE engagement_id=?',(row['id'],)))
        if row['world_model_version']!=1 or row['engagement_state']!='converted_to_battle' or row['rules_version']!=RULES_VERSION:
            live_actors.update(members)
        else:
            try: validate_live_group(conn,row)
            except ActionRejected as exc:
                quarantine_live_group(conn,row,now_ms=now_ms,reason=str(exc))
                continue
            live_candidates.append((int(row['roster_locked_ms'] or 0),'pvp',str(row['id']),row,members))
    # A frozen reward plan and legacy authority are preserved. Among current
    # live fights, the earliest committed roster keeps ownership of its actors.
    for _,kind,ref,row,members in sorted(live_candidates,key=lambda item:item[:3]):
        if members & live_actors:
            if kind=='pve':
                _quarantine_pxe1_active_encounter(conn,row,now_ms=now_ms,reason='activity_overlap')
            else:
                quarantine_live_group(conn,row,now_ms=now_ms,reason='activity_overlap')
        else:
            live_actors.update(members)
    preparations=[]
    for row in conn.execute("SELECT encounter_id FROM pve_encounters WHERE status='active' AND lifecycle_version=1 AND runtime_started_ms IS NULL").fetchall():
        full=conn.execute('SELECT * FROM pve_encounters WHERE encounter_id=?',(row['encounter_id'],)).fetchone()
        members={r['player_id'] for r in conn.execute(
            "SELECT player_id FROM pve_encounter_participants WHERE encounter_id=? AND status='active'",(row['encounter_id'],))}
        try: started=int(full['formation_deadline_ms'])-12000
        except (ValueError,TypeError): started=now_ms
        preparations.append((started,'pve',row['encounter_id'],full,members))
    for row in conn.execute("SELECT * FROM pvp_engagements WHERE world_model_version=1 AND engagement_state='pending'").fetchall():
        try: started=milliseconds(row['engagement_started_at'])
        except (ValueError,TypeError): started=now_ms
        preparations.append((started,'pvp',str(row['id']),row,set()))
    for _,kind,ref,row,members in sorted(preparations,key=lambda item:item[:3]):
        if kind=='pve':
            if members & live_actors:
                _interrupt_pxe1_formation(conn,ref,now_ms=now_ms,reason='activity_overlap')
            else:
                live_actors.update(members)
            continue
        if {row['attacker_id'],row['defender_id']} & live_actors:
            cancel_preparation(conn,row,reason='activity_overlap',now_ms=now_ms)
            continue
        for ally in conn.execute("SELECT * FROM pvp_engagement_reinforcements WHERE engagement_id=? AND membership_version=1 AND status='accepted'",(row['id'],)).fetchall():
            if ally['ally_id'] in live_actors:
                conn.execute("UPDATE pvp_engagement_reinforcements SET status='expired',responded_at=? WHERE id=?",(iso(now_ms),ally['id']))
                conn.execute('UPDATE pvp_engagements SET state_revision=state_revision+1 WHERE id=?',(row['id'],))
                _recovery_notice(conn,ally['ally_id'],domain='pvp',ref=row['id'],reason='activity_overlap',now_ms=now_ms)
        live_actors.update((row['attacker_id'],row['defender_id']))
        live_actors.update(r['ally_id'] for r in conn.execute(
            "SELECT ally_id FROM pvp_engagement_reinforcements WHERE engagement_id=? AND membership_version=1 AND status='accepted'",(row['id'],)))
