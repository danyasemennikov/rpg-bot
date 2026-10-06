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
