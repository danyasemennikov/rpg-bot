"""Per-visit threat deadlines and real canonical hostile reservations."""

import secrets

from game.locations import get_location, resolve_location_id
from game.mobs import get_mob


def seed_visit_threats(conn, player_id: int, *, now_ms: int, rng=None) -> None:
    player = conn.execute('SELECT * FROM players WHERE telegram_id=?', (player_id,)).fetchone()
    location_id = resolve_location_id(player['location_id'])
    location = get_location(location_id) or {}
    if location.get('safe'):
        return
    rng = rng or secrets.SystemRandom()
    for mob_id in location.get('mobs',[]):
        mob = get_mob(mob_id)
        if not mob or not mob.get('aggressive') or player['level']>mob['level']+1:
            continue
        existing = conn.execute('''SELECT 1 FROM player_location_threats WHERE player_id=?
            AND visit_revision=? AND mob_id=?''', (player_id,player['location_visit_revision'],mob_id)).fetchone()
        if existing:
            continue
        due_ms = now_ms+rng.randint(5,60)*1000
        conn.execute('''INSERT INTO player_location_threats(player_id,visit_revision,location_id,mob_id,
            schema_version,due_ms,status,created_ms,updated_ms) VALUES (?,?,?,?,1,?,'pending',?,?)''',
            (player_id,player['location_visit_revision'],location_id,mob_id,due_ms,now_ms,now_ms))


def arrive_at_location(conn, player_id: int, destination: str, *, now_ms: int) -> bool:
    from database import ensure_player_location_discovered
    destination = resolve_location_id(destination)
    player = conn.execute('SELECT location_id FROM players WHERE telegram_id=?', (player_id,)).fetchone()
    if not player or resolve_location_id(player['location_id'])==destination:
        return False
    if not get_location(destination):
        raise ValueError('invalid arrival')
    conn.execute('''UPDATE players SET location_id=?,travel_revision=travel_revision+1,
        location_visit_revision=location_visit_revision+1 WHERE telegram_id=?''', (destination,player_id))
    ensure_player_location_discovered(player_id,destination,conn=conn)
    conn.execute("UPDATE player_location_threats SET status='dismissed',reason='left_location',updated_ms=? WHERE player_id=? AND status='pending'", (now_ms,player_id))
    seed_visit_threats(conn,player_id,now_ms=now_ms)
    return True


def process_location_threat(conn, *, player_id: int, visit_revision: int, mob_id: str, now_ms: int) -> dict:
    from game.player_activity import player_activity,interrupt_peaceful_activity
    from game.pve_live import create_pve_encounter,ensure_location_pve_spawn_instances
    from game.combat import init_battle
    threat = conn.execute('''SELECT * FROM player_location_threats WHERE player_id=? AND visit_revision=? AND mob_id=?''',
                          (player_id,visit_revision,mob_id)).fetchone()
    if not threat or threat['status']!='pending' or threat['due_ms']>now_ms:
        return {'status':'unchanged'}
    player = conn.execute('SELECT * FROM players WHERE telegram_id=?', (player_id,)).fetchone()
    mob = get_mob(mob_id)
    activity = player_activity(conn,player_id)
    valid = (player and mob and player['hp']>0 and player['level']<=mob['level']+1
        and resolve_location_id(player['location_id'])==threat['location_id']
        and player['location_visit_revision']==visit_revision
        and (activity is None or activity['kind'] in {'travel','gather'}))
    encounter_id = None
    if valid:
        ensure_location_pve_spawn_instances(location_id=threat['location_id'],conn=conn)
        spawn = conn.execute("""SELECT * FROM pve_spawn_instances WHERE location_id=? AND mob_id=?
            AND state='idle' AND linked_encounter_id IS NULL ORDER BY spawn_instance_id LIMIT 1""", (threat['location_id'],mob_id)).fetchone()
        if spawn:
            encounter_id = 'pve-enc-'+secrets.token_hex(6)
            interrupt_peaceful_activity(conn,player_id,reason='hostile_encounter',now_ms=now_ms)
            conn.execute("UPDATE pve_spawn_instances SET state='forming',linked_encounter_id=? WHERE spawn_instance_id=? AND state='idle'", (encounter_id,spawn['spawn_instance_id']))
            state = init_battle(dict(player),mob,mob_first=True)
            state.update(location_id=threat['location_id'],mob_id=mob_id,active_side='side_b',spawn_profile=spawn['spawn_profile'])
            from game.pve_live import apply_world_spawn_profile_combat_scaling
            apply_world_spawn_profile_combat_scaling(battle_state=state,mob=mob,spawn_profile=spawn['spawn_profile'])
            create_pve_encounter(owner_player_id=player_id,side_a_player_ids=[player_id],battle_state=state,mob=mob,
                encounter_id=encounter_id,location_id=threat['location_id'],anchor_spawn_instance_id=spawn['spawn_instance_id'],conn=conn)
            conn.execute('UPDATE pve_encounters SET formation_deadline_ms=? WHERE encounter_id=?', (now_ms+12000,encounter_id))
    status = 'triggered' if encounter_id else 'dismissed'
    conn.execute('''UPDATE player_location_threats SET status=?,encounter_id=?,reason=?,updated_ms=?
        WHERE player_id=? AND visit_revision=? AND mob_id=?''',
        (status,encounter_id,None if encounter_id else 'no_eligible_source',now_ms,player_id,visit_revision,mob_id))
    return {'status':status,'encounter_id':encounter_id,'player_id':player_id}
