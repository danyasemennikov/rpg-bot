"""Additive PXE1 storage. The caller owns the single migration transaction."""

from __future__ import annotations

import json
import secrets
import sqlite3
import time

MIGRATION_VERSION = 'player_experience_economy_v1'
GATHERING_KEYS = ('woodcutting', 'mining', 'herbalism', 'fishing', 'hunting')

_DDL = {
    'player_travel_sessions': """CREATE TABLE player_travel_sessions (
        session_id TEXT NOT NULL PRIMARY KEY,
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        start_request_id TEXT NOT NULL,
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        route_version INTEGER NOT NULL CHECK(route_version=1),
        route_class TEXT NOT NULL CHECK(route_class IN ('adjacent','discovered')),
        path_json TEXT NOT NULL,
        edge_index INTEGER NOT NULL DEFAULT 0 CHECK(edge_index>=0),
        origin_location_id TEXT NOT NULL, destination_location_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('running','arrived','cancelled','interrupted')),
        started_ms INTEGER NOT NULL, next_due_ms INTEGER,
        expected_travel_revision INTEGER NOT NULL CHECK(expected_travel_revision>=0),
        revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>=0), terminal_reason TEXT,
        created_ms INTEGER NOT NULL, updated_ms INTEGER NOT NULL,
        UNIQUE(player_id,start_request_id))""",
    'player_gathering_sessions': """CREATE TABLE player_gathering_sessions (
        session_id TEXT NOT NULL PRIMARY KEY,
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        start_request_id TEXT NOT NULL,
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        rng_version INTEGER NOT NULL CHECK(rng_version=1),
        catalog_version INTEGER NOT NULL CHECK(catalog_version=2),
        profession_key TEXT NOT NULL CHECK(profession_key IN ('woodcutting','mining','herbalism','fishing')),
        location_id TEXT NOT NULL, location_visit_revision INTEGER NOT NULL CHECK(location_visit_revision>=0),
        source_snapshot_json TEXT NOT NULL, seed TEXT NOT NULL
          CHECK(length(seed)=32 AND seed NOT GLOB '*[^0-9a-f]*'),
        tool_tier INTEGER NOT NULL CHECK(tool_tier BETWEEN 1 AND 4),
        expected_tool_revision INTEGER NOT NULL CHECK(expected_tool_revision>=0),
        status TEXT NOT NULL CHECK(status IN ('running','completed','cancelled','interrupted','broken')),
        started_ms INTEGER NOT NULL, next_due_ms INTEGER, ends_ms INTEGER NOT NULL,
        last_tick INTEGER NOT NULL DEFAULT 0 CHECK(last_tick BETWEEN 0 AND 15),
        yield_total INTEGER NOT NULL DEFAULT 0 CHECK(yield_total BETWEEN 0 AND 15),
        result_json TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>=0),
        terminal_reason TEXT, created_ms INTEGER NOT NULL, updated_ms INTEGER NOT NULL,
        UNIQUE(player_id,start_request_id), CHECK(ends_ms=started_ms+120000))""",
    'player_profession_tools': """CREATE TABLE player_profession_tools (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        profession_key TEXT NOT NULL CHECK(profession_key IN ('woodcutting','mining','herbalism','fishing','hunting')),
        tier INTEGER NOT NULL CHECK(tier BETWEEN 1 AND 4),
        durability INTEGER NOT NULL CHECK(durability BETWEEN 0 AND 60*tier),
        revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>=0),
        bootstrap_used_mask INTEGER NOT NULL DEFAULT 0 CHECK(bootstrap_used_mask BETWEEN 0 AND 7),
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        created_ms INTEGER NOT NULL, updated_ms INTEGER NOT NULL,
        PRIMARY KEY(player_id,profession_key),
        CHECK(bootstrap_used_mask=0 OR profession_key IN ('woodcutting','mining')))""",
    'player_location_threats': """CREATE TABLE player_location_threats (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        visit_revision INTEGER NOT NULL CHECK(visit_revision>=0),
        location_id TEXT NOT NULL, mob_id TEXT NOT NULL,
        schema_version INTEGER NOT NULL CHECK(schema_version=1), due_ms INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending','triggered','dismissed')),
        encounter_id TEXT REFERENCES pve_encounters(encounter_id), reason TEXT,
        created_ms INTEGER NOT NULL, updated_ms INTEGER NOT NULL,
        PRIMARY KEY(player_id,visit_revision,mob_id))""",
    'player_feedback_events': """CREATE TABLE player_feedback_events (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id), event_key TEXT NOT NULL,
        schema_version INTEGER NOT NULL CHECK(schema_version=1), source_kind TEXT NOT NULL,
        source_id TEXT NOT NULL,
        event_kind TEXT NOT NULL CHECK(event_kind IN ('progress','objective_complete','ready','claim','level_up','chapter_finale','recovery')),
        payload_json TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('pending','presented','acknowledged')),
        chat_id INTEGER, message_id INTEGER, created_ms INTEGER NOT NULL,
        presented_ms INTEGER, acknowledged_ms INTEGER, PRIMARY KEY(player_id,event_key))""",
    'player_pxe1_ui': """CREATE TABLE player_pxe1_ui (
        player_id INTEGER NOT NULL PRIMARY KEY REFERENCES players(telegram_id),
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        menu_version INTEGER NOT NULL DEFAULT 0 CHECK(menu_version>=0), menu_lang TEXT,
        surface_kind TEXT, surface_ref TEXT, chat_id INTEGER, message_id INTEGER,
        surface_revision INTEGER NOT NULL DEFAULT 0 CHECK(surface_revision>=0),
        updated_ms INTEGER NOT NULL)""",
    'pvp_participant_settlements_pxe1': """CREATE TABLE pvp_participant_settlements_pxe1 (
        engagement_id INTEGER NOT NULL REFERENCES pvp_engagements(id),
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        turn_revision INTEGER NOT NULL CHECK(turn_revision>=0), result_json TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status='applied'), created_ms INTEGER NOT NULL,
        PRIMARY KEY(engagement_id,player_id))""",
    'pvp_group_settlements_pxe1': """CREATE TABLE pvp_group_settlements_pxe1 (
        engagement_id INTEGER NOT NULL PRIMARY KEY REFERENCES pvp_engagements(id),
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        terminal_turn_revision INTEGER NOT NULL CHECK(terminal_turn_revision>=0),
        result_json TEXT NOT NULL, status TEXT NOT NULL CHECK(status='applied'),
        created_ms INTEGER NOT NULL)""",
}
TABLES = tuple(_DDL)
_ADDITIONS = {
    'players': {'location_visit_revision': 'INTEGER NOT NULL DEFAULT 0 CHECK(location_visit_revision>=0)'},
    'pve_encounters': {
        'lifecycle_version': 'INTEGER NOT NULL DEFAULT 0 CHECK(lifecycle_version IN (0,1))',
        'formation_deadline_ms': 'INTEGER',
        'formation_revision': 'INTEGER NOT NULL DEFAULT 0 CHECK(formation_revision>=0)',
        'runtime_started_ms': 'INTEGER',
    },
    'pvp_engagements': {
        'world_model_version': 'INTEGER NOT NULL DEFAULT 0 CHECK(world_model_version IN (0,1))',
        'locked_roster_json': 'TEXT', 'roster_locked_ms': 'INTEGER',
    },
    'pvp_engagement_reinforcements': {
        'membership_version': 'INTEGER NOT NULL DEFAULT 0 CHECK(membership_version IN (0,1))',
    },
}
_INDEXES = {
    'idx_pxe1_travel_running': "UNIQUE INDEX idx_pxe1_travel_running ON player_travel_sessions(player_id) WHERE status='running'",
    'idx_pxe1_travel_due': "INDEX idx_pxe1_travel_due ON player_travel_sessions(next_due_ms,session_id) WHERE status='running'",
    'idx_pxe1_travel_history': 'INDEX idx_pxe1_travel_history ON player_travel_sessions(player_id,created_ms,session_id)',
    'idx_pxe1_gather_running': "UNIQUE INDEX idx_pxe1_gather_running ON player_gathering_sessions(player_id) WHERE status='running'",
    'idx_pxe1_gather_due': "INDEX idx_pxe1_gather_due ON player_gathering_sessions(next_due_ms,session_id) WHERE status='running'",
    'idx_pxe1_gather_history': 'INDEX idx_pxe1_gather_history ON player_gathering_sessions(player_id,created_ms,session_id)',
    'idx_pxe1_threat_due': "INDEX idx_pxe1_threat_due ON player_location_threats(due_ms,player_id,visit_revision,mob_id) WHERE status='pending'",
    'idx_pxe1_threat_player': 'INDEX idx_pxe1_threat_player ON player_location_threats(player_id,status)',
    'idx_pxe1_feedback_player': 'INDEX idx_pxe1_feedback_player ON player_feedback_events(player_id,state,created_ms,event_key)',
    'idx_pxe1_pvp_death_player': 'INDEX idx_pxe1_pvp_death_player ON pvp_participant_settlements_pxe1(player_id,created_ms,engagement_id)',
    'idx_pve_formation_due': "INDEX idx_pve_formation_due ON pve_encounters(formation_deadline_ms,encounter_id) WHERE lifecycle_version=1 AND runtime_started_ms IS NULL AND status='active'",
    'idx_pvp_pxe1_due': "INDEX idx_pvp_pxe1_due ON pvp_engagements(engagement_ready_at,id) WHERE world_model_version=1 AND engagement_state='pending'",
    'idx_pxe1_pvp_ally_once': 'UNIQUE INDEX idx_pxe1_pvp_ally_once ON pvp_engagement_reinforcements(engagement_id,ally_id) WHERE membership_version=1',
    'idx_pxe1_pvp_seat': "UNIQUE INDEX idx_pxe1_pvp_seat ON pvp_engagement_reinforcements(engagement_id,side) WHERE membership_version=1 AND status IN ('pending','accepted','locked')",
    'idx_pxe1_pvp_commitment': "UNIQUE INDEX idx_pxe1_pvp_commitment ON pvp_engagement_reinforcements(ally_id) WHERE membership_version=1 AND status IN ('accepted','locked')",
    'idx_pxe1_pvp_membership': 'INDEX idx_pxe1_pvp_membership ON pvp_engagement_reinforcements(engagement_id,membership_version,status)',
}


def _normalized(sql: str) -> str:
    return ''.join(sql.lower().split())


def _validate_tables(conn) -> None:
    # Compare SQLite's own canonical PRAGMA output, including CHECK/FK/key shape.
    expected = sqlite3.connect(':memory:')
    try:
        for name, ddl in _DDL.items():
            expected.execute(ddl)
            for pragma in ('table_info', 'foreign_key_list'):
                actual_rows = [tuple(row) for row in conn.execute(f'PRAGMA {pragma}("{name}")')]
                expected_rows = list(expected.execute(f'PRAGMA {pragma}("{name}")'))
                if actual_rows != expected_rows:
                    raise RuntimeError(f'incompatible PXE1 {name} {pragma}')
            actual = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
            if not actual or _normalized(actual['sql']) != _normalized(ddl):
                raise RuntimeError(f'incompatible PXE1 {name} constraints')
    finally:
        expected.close()


def grant_player_pxe1_starters(conn, player_id: int, *, now_ms: int, acquired_via: str) -> None:
    """INSERT only: repeated welcome/migration never repairs an existing tool."""
    conn.executemany('''INSERT OR IGNORE INTO player_profession_tools
        (player_id,profession_key,tier,durability,revision,bootstrap_used_mask,schema_version,created_ms,updated_ms)
        VALUES (?,?,1,60,1,0,1,?,?)''',
        ((player_id, key, now_ms, now_ms) for key in GATHERING_KEYS))
    conn.executemany('''INSERT OR IGNORE INTO player_recipe_knowledge
        (player_id,recipe_id,acquired_via,gold_paid,catalog_version) VALUES (?,?,?,0,2)''',
        ((player_id, f'pxe_tool_{key}_1', acquired_via) for key in GATHERING_KEYS))
    conn.execute('''INSERT OR IGNORE INTO player_pxe1_ui(player_id,schema_version,updated_ms)
        VALUES (?,1,?)''', (player_id, now_ms))


def _upgrade_formations(conn, now_ms: int) -> None:
    rows = conn.execute('''SELECT e.* FROM pve_encounters e
        WHERE e.lifecycle_version=0 AND e.status='active' AND e.locked_roster_json IS NULL
        AND EXISTS(SELECT 1 FROM pve_spawn_instances s
                   WHERE s.linked_encounter_id=e.encounter_id AND s.state='forming')''').fetchall()
    for row in rows:
        sources = conn.execute('SELECT * FROM pve_spawn_instances WHERE linked_encounter_id=?',
                               (row['encounter_id'],)).fetchall()
        if (not sources or any(s['state'] != 'forming' or s['location_id'] != row['location_id'] for s in sources)
                or row['anchor_spawn_instance_id'] not in {s['spawn_instance_id'] for s in sources}):
            continue
        conn.execute('''UPDATE pve_encounters SET lifecycle_version=1, formation_deadline_ms=?,
            formation_revision=1 WHERE encounter_id=?''', (now_ms + 12000, row['encounter_id']))


def _upgrade_pending_pvp(conn) -> None:
    for row in conn.execute("SELECT * FROM pvp_engagements WHERE world_model_version=0 AND engagement_state IN ('pending','active')").fetchall():
        try:
            payload = json.loads(row['reason_context'] or '{}')
        except (ValueError, TypeError):
            raise RuntimeError(f'invalid legacy PvP preparation payload: {row["id"]}')
        if not isinstance(payload, dict):
            raise RuntimeError(f'invalid legacy PvP preparation payload: {row["id"]}')
        if payload.get('battle'):
            continue  # Initialized legacy battles retain their historical 1v1 rules.
        from game.pvp_rules import is_recent_retaliation_context
        attacker = conn.execute('SELECT * FROM players WHERE telegram_id=?',(row['attacker_id'],)).fetchone()
        defender = conn.execute('SELECT * FROM players WHERE telegram_id=?',(row['defender_id'],)).fetchone()
        if not attacker or not defender:
            continue  # Lock recovery cancels unverifiable principal membership.
        payload.update(schema_version=1,catalog_version=2,flow='open_world_group')
        payload['crime_context'] = {str(row['attacker_id']): {
            'initiator_snapshot':dict(attacker),'original_defender_snapshot':dict(defender),
            'initiation_infamy':0,'red_flag_applied':False,
            'retaliation_context':is_recent_retaliation_context(attacker_id=row['attacker_id'],defender_id=row['defender_id'],conn=conn)}}
        conn.execute('''UPDATE pvp_engagements SET world_model_version=1, engagement_state='pending',
            reason_context=?,combat_seed=COALESCE(combat_seed,?) WHERE id=?''', (json.dumps(payload,ensure_ascii=False),secrets.token_hex(16), row['id']))
        conn.execute("""UPDATE pvp_engagement_reinforcements SET status='expired'
            WHERE engagement_id=? AND membership_version=0 AND status IN ('pending','accepted')""", (row['id'],))


def ensure_player_experience_schema(conn, *, now_ms: int | None = None) -> None:
    """No commits, no secondary connection, and no destructive down-migration."""
    if not conn.in_transaction:
        raise RuntimeError('PXE1 installer requires a caller-owned transaction')
    if conn.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
        raise RuntimeError('PXE1 requires foreign keys enabled')
    now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    conn.execute('SAVEPOINT pxe1_schema')
    try:
        present = {r['name'] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = set(_ADDITIONS) | {'pve_spawn_instances','economy_schema_migrations',
                                    'player_recipe_knowledge','economy_action_receipts','player_contract_history'}
        if not required <= present:
            raise RuntimeError(f'PXE1 prerequisites missing: {sorted(required-present)}')
        marked = conn.execute('SELECT 1 FROM economy_schema_migrations WHERE version=?', (MIGRATION_VERSION,)).fetchone()
        if marked and not set(TABLES) <= present:
            raise RuntimeError('PXE1 marker exists with incomplete schema')
        for name, ddl in _DDL.items():
            if name not in present:
                conn.execute(ddl)
        _validate_tables(conn)
        for table, additions in _ADDITIONS.items():
            columns = {r['name'] for r in conn.execute(f'PRAGMA table_info("{table}")')}
            for name, declaration in additions.items():
                if name not in columns:
                    if marked:
                        raise RuntimeError(f'PXE1 marker missing {table}.{name}')
                    conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {declaration}')
        for name, declaration in _INDEXES.items():
            existing = conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (name,)).fetchone()
            if existing:
                if _normalized(existing['sql']) != _normalized('CREATE ' + declaration):
                    raise RuntimeError(f'incompatible PXE1 index {name}')
            else:
                conn.execute('CREATE ' + declaration)
        if not marked:
            for player in conn.execute('SELECT telegram_id FROM players').fetchall():
                grant_player_pxe1_starters(conn, player['telegram_id'], now_ms=now_ms, acquired_via='grandfather')
            for player in conn.execute("SELECT player_id FROM player_contract_history WHERE contract_key='chapter_homecoming'").fetchall():
                conn.execute('''INSERT OR IGNORE INTO player_feedback_events
                    (player_id,event_key,schema_version,source_kind,source_id,event_kind,payload_json,state,created_ms,acknowledged_ms)
                    VALUES (?,'chapter_finale:chapter_homecoming',1,'chapter','chapter_homecoming','chapter_finale',
                            '{"schema_version":1,"historical":true}', 'acknowledged',?,?)''',
                    (player['player_id'], now_ms, now_ms))
            _upgrade_formations(conn, now_ms)
            _upgrade_pending_pvp(conn)
            from game.location_threats import seed_visit_threats
            for player in conn.execute('SELECT telegram_id FROM players').fetchall():
                seed_visit_threats(conn,player['telegram_id'],now_ms=now_ms)
            conn.execute('INSERT INTO economy_schema_migrations(version) VALUES (?)', (MIGRATION_VERSION,))
        violations = [tuple(row) for row in conn.execute('PRAGMA foreign_key_check')]
        if violations:
            raise RuntimeError(f'PXE1 foreign key violations: {violations!r}')
        conn.execute('RELEASE SAVEPOINT pxe1_schema')
    except Exception:
        conn.execute('ROLLBACK TO SAVEPOINT pxe1_schema')
        conn.execute('RELEASE SAVEPOINT pxe1_schema')
        raise
