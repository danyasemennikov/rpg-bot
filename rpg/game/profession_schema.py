"""Clean Epic I profession schema. Previous test-state layouts are unsupported."""
from pathlib import Path

MIGRATION_VERSION = 'profession_tiers_v3'
CRAFTING_PROFESSION_KEYS = ('heavy_armor','medium_armor','light_armor','blacksmith','arcane_engineer','alchemy','cooking')
GATHERING_PROFESSION_KEYS = ('herbalism','woodcutting','mining','fishing','hunting')


def create_profession_table(conn, table, player_column, keys, *, gathering=False):
    members = ','.join(repr(key) for key in keys)
    timestamp = ',updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP' if gathering else ''
    conn.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
        {player_column} INTEGER NOT NULL REFERENCES players(telegram_id),
        profession_key TEXT NOT NULL CHECK(profession_key IN ({members})),
        level INTEGER NOT NULL DEFAULT 1 CHECK(level BETWEEN 1 AND 30),
        exp INTEGER NOT NULL DEFAULT 0 CHECK(exp>=0 AND (level NOT IN (15,30) OR exp=0)),
        registered_at INTEGER,
        revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0){timestamp},
        PRIMARY KEY({player_column},profession_key))""")
    columns = {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}
    if not {'registered_at','revision'} <= columns:
        raise RuntimeError('Epic I requires a clean database; old profession layout unsupported')


def ensure_profession_schema(conn):
    create_profession_table(conn,'player_crafting_professions','player_id',CRAFTING_PROFESSION_KEYS)
    create_profession_table(conn,'player_gathering_professions','telegram_id',GATHERING_PROFESSION_KEYS,gathering=True)
    conn.execute("""CREATE TABLE IF NOT EXISTS economy_schema_migrations (
        version TEXT PRIMARY KEY,applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS player_recipe_knowledge (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),recipe_id TEXT NOT NULL,
        acquired_via TEXT NOT NULL CHECK(acquired_via IN ('voucher','guild','exam','regional')),
        learned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,learned_location_id TEXT,
        gold_paid INTEGER NOT NULL DEFAULT 0 CHECK(gold_paid>=0),
        catalog_version INTEGER NOT NULL CHECK(catalog_version>=1),PRIMARY KEY(player_id,recipe_id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS economy_action_receipts (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),request_id TEXT NOT NULL,
        action_kind TEXT NOT NULL,request_hash TEXT NOT NULL,
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        catalog_version INTEGER NOT NULL CHECK(catalog_version>=1),result_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(player_id,request_id))""")
    conn.execute('CREATE INDEX IF NOT EXISTS idx_economy_receipts_player_time ON economy_action_receipts(player_id,created_at,request_id)')
    # execute(), not executescript(): no implicit commit of the caller's writer.
    for statement in Path(__file__).with_name('profession_epic_i.sql').read_text(encoding='utf-8').split(';'):
        if statement.strip():
            conn.execute(statement)
    conn.execute("""CREATE VIEW IF NOT EXISTS profession_state AS
        SELECT player_id,profession_key,level,exp,registered_at,revision,(level-1)/15+1 AS tier
        FROM player_crafting_professions UNION ALL
        SELECT telegram_id,profession_key,level,exp,registered_at,revision,(level-1)/15+1
        FROM player_gathering_professions""")
    for row in conn.execute('SELECT telegram_id FROM players').fetchall():
        ensure_profession_rows(conn,row['telegram_id'])
    conn.execute('INSERT OR IGNORE INTO economy_schema_migrations(version) VALUES (?)',(MIGRATION_VERSION,))


def ensure_profession_rows(conn, player_id):
    for table,column,keys in (('player_crafting_professions','player_id',CRAFTING_PROFESSION_KEYS),
                              ('player_gathering_professions','telegram_id',GATHERING_PROFESSION_KEYS)):
        conn.executemany(f'INSERT OR IGNORE INTO {table}({column},profession_key) VALUES (?,?)',
                         ((player_id,key) for key in keys))


def grant_new_player_starters(conn, player_id):
    # Rows are not registration. Learning is an explicit voucher choice.
    ensure_profession_rows(conn,player_id)
