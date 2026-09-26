"""Lossless, idempotent PEV1-1 profession/economy schema migration."""

from __future__ import annotations

import sqlite3
import re

from game.profession_recipes import GRANDFATHERED_RECIPE_IDS, STARTER_RECIPE_IDS

MIGRATION_VERSION = 'professions_economy_v1'
CRAFTING_PROFESSION_KEYS = (
    'heavy_armor', 'medium_armor', 'light_armor', 'blacksmith',
    'arcane_engineer', 'alchemy', 'cooking',
)
GATHERING_PROFESSION_KEYS = ('herbalism', 'woodcutting', 'mining', 'fishing', 'hunting')


def _create_crafting_table(conn, name: str) -> None:
    conn.execute(f'''CREATE TABLE {name} (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        profession_key TEXT NOT NULL CHECK (profession_key IN (
            'heavy_armor', 'medium_armor', 'light_armor',
            'blacksmith', 'arcane_engineer', 'alchemy', 'cooking'
        )),
        level INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 20),
        exp INTEGER NOT NULL DEFAULT 0 CHECK (exp >= 0),
        PRIMARY KEY (player_id, profession_key)
    )''')


def _table_sql(conn, table: str) -> str | None:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return str(row['sql']) if row else None


def _quoted_members(sql: str, column: str) -> tuple[str, ...] | None:
    match = re.search(
        rf"check\s*\(\s*{re.escape(column)}\s+in\s*\((.*?)\)\s*\)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return None
    body = match.group(1)
    if re.sub(r"\s*'(?:[^']|'')*'\s*(?:,|$)", '', body).strip():
        return None
    return tuple(value.replace("''", "'") for value in re.findall(r"'((?:[^']|'')*)'", body))


def _normalized_check_expressions(sql: str) -> tuple[str, ...]:
    expressions: list[str] = []
    lower = sql.lower()
    cursor = 0
    while True:
        start = lower.find('check', cursor)
        if start < 0:
            break
        opening = lower.find('(', start + 5)
        if opening < 0:
            return ()
        depth = 0
        quote = False
        closing = -1
        for index in range(opening, len(sql)):
            char = sql[index]
            if char == "'":
                quote = not quote
            elif not quote and char == '(':
                depth += 1
            elif not quote and char == ')':
                depth -= 1
                if depth == 0:
                    closing = index
                    break
        if closing < 0:
            return ()
        expressions.append(re.sub(r'\s+', '', lower[opening + 1:closing]))
        cursor = closing + 1
    return tuple(expressions)


def _schema_kind(conn: sqlite3.Connection, table: str) -> str | None:
    """Return the one accepted table shape, or fail closed with ``None``."""
    sql = _table_sql(conn, table)
    if sql is None:
        return None

    columns = [
        (str(row['name']), str(row['type']).upper(), int(row['notnull']), row['dflt_value'], int(row['pk']))
        for row in conn.execute(f'PRAGMA table_info("{table}")')
    ]
    expected_columns = [
        ('player_id', 'INTEGER', 1, None, 1),
        ('profession_key', 'TEXT', 1, None, 2),
        ('level', 'INTEGER', 1, '1', 0),
        ('exp', 'INTEGER', 1, '0', 0),
    ]
    if columns != expected_columns:
        return None

    foreign_keys = [
        (str(row['table']), str(row['from']), str(row['to']), str(row['on_update']),
         str(row['on_delete']), str(row['match']))
        for row in conn.execute(f'PRAGMA foreign_key_list("{table}")')
    ]
    if foreign_keys != [('players', 'player_id', 'telegram_id', 'NO ACTION', 'NO ACTION', 'NONE')]:
        return None

    indexes = list(conn.execute(f'PRAGMA index_list("{table}")'))
    if len(indexes) != 1 or str(indexes[0]['origin']) != 'pk' or int(indexes[0]['unique']) != 1:
        return None
    index_columns = [str(row['name']) for row in conn.execute(
        f'PRAGMA index_info("{indexes[0]["name"]}")'
    )]
    if index_columns != ['player_id', 'profession_key']:
        return None

    triggers = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (table,)
    ).fetchall()
    if triggers:
        return None
    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        other = str(row['name'])
        if other == table:
            continue
        if any(str(fk['table']) == table for fk in conn.execute(f'PRAGMA foreign_key_list("{other}")')):
            return None

    members = _quoted_members(sql, 'profession_key')
    checks = _normalized_check_expressions(sql)
    non_membership_checks = tuple(check for check in checks if not check.startswith('profession_keyin('))
    if non_membership_checks != ('levelbetween1and20', 'exp>=0') or len(checks) != 3:
        return None
    if members == ('alchemy', 'cooking', 'medium_armor'):
        return 'baseline'
    if members == CRAFTING_PROFESSION_KEYS:
        return 'migrated'
    return None


def ensure_profession_schema(conn: sqlite3.Connection) -> None:
    """Run inside the caller's transaction; never commits internally."""
    conn.execute('''CREATE TABLE IF NOT EXISTS economy_schema_migrations (
        version TEXT PRIMARY KEY,
        applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    marker = conn.execute('SELECT 1 FROM economy_schema_migrations WHERE version=?', (MIGRATION_VERSION,)).fetchone()
    sql = _table_sql(conn, 'player_crafting_professions')
    if sql is None:
        _create_crafting_table(conn, 'player_crafting_professions')
        schema_kind = 'migrated'
    else:
        schema_kind = _schema_kind(conn, 'player_crafting_professions')
        if schema_kind is None:
            raise RuntimeError('unexpected player_crafting_professions schema')
    if schema_kind == 'baseline':
        if marker:
            raise RuntimeError('migration marker exists with frozen player_crafting_professions schema')
        if _table_sql(conn, 'player_crafting_professions_pev1_new') is not None:
            raise RuntimeError('unexpected pre-existing player_crafting_professions_pev1_new table')
        before = [tuple(row) for row in conn.execute(
            'SELECT player_id, profession_key, level, exp FROM player_crafting_professions ORDER BY 1,2'
        )]
        _create_crafting_table(conn, 'player_crafting_professions_pev1_new')
        conn.execute('''INSERT INTO player_crafting_professions_pev1_new
            (player_id, profession_key, level, exp)
            SELECT player_id, profession_key, level, exp FROM player_crafting_professions''')
        copied = [tuple(row) for row in conn.execute(
            'SELECT player_id, profession_key, level, exp FROM player_crafting_professions_pev1_new ORDER BY 1,2'
        )]
        if before != copied:
            raise RuntimeError('crafting profession preservation check failed')
        conn.execute('DROP TABLE player_crafting_professions')
        conn.execute('ALTER TABLE player_crafting_professions_pev1_new RENAME TO player_crafting_professions')
        if _schema_kind(conn, 'player_crafting_professions') != 'migrated':
            raise RuntimeError('migrated player_crafting_professions schema validation failed')

    conn.execute('''CREATE TABLE IF NOT EXISTS player_recipe_knowledge (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        recipe_id TEXT NOT NULL,
        acquired_via TEXT NOT NULL CHECK (acquired_via IN ('grandfather', 'starter', 'guild')),
        learned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        learned_location_id TEXT,
        gold_paid INTEGER NOT NULL DEFAULT 0 CHECK (gold_paid >= 0),
        catalog_version INTEGER NOT NULL CHECK (catalog_version >= 1),
        PRIMARY KEY (player_id, recipe_id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS economy_action_receipts (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        request_id TEXT NOT NULL,
        action_kind TEXT NOT NULL,
        request_hash TEXT NOT NULL,
        schema_version INTEGER NOT NULL CHECK (schema_version = 1),
        catalog_version INTEGER NOT NULL CHECK (catalog_version >= 1),
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, request_id)
    )''')
    conn.execute('''CREATE INDEX IF NOT EXISTS idx_economy_receipts_player_time
        ON economy_action_receipts(player_id, created_at, request_id)''')

    for row in conn.execute('SELECT telegram_id FROM players').fetchall():
        ensure_profession_rows(conn, int(row['telegram_id']))
    if not marker:
        conn.executemany('''INSERT OR IGNORE INTO player_recipe_knowledge
            (player_id, recipe_id, acquired_via, gold_paid, catalog_version)
            SELECT telegram_id, ?, 'grandfather', 0, 1 FROM players''',
            ((recipe_id,) for recipe_id in GRANDFATHERED_RECIPE_IDS))
        violations = conn.execute('PRAGMA foreign_key_check').fetchall()
        if violations:
            raise RuntimeError(f'foreign key violations after profession migration: {violations!r}')
        conn.execute('INSERT INTO economy_schema_migrations(version) VALUES (?)', (MIGRATION_VERSION,))


def ensure_profession_rows(conn, player_id: int) -> None:
    conn.executemany('''INSERT OR IGNORE INTO player_crafting_professions
        (player_id, profession_key, level, exp) VALUES (?, ?, 1, 0)''',
        ((int(player_id), key) for key in CRAFTING_PROFESSION_KEYS))
    conn.executemany('''INSERT OR IGNORE INTO player_gathering_professions
        (telegram_id, profession_key, level, exp) VALUES (?, ?, 1, 0)''',
        ((int(player_id), key) for key in GATHERING_PROFESSION_KEYS))


def grant_new_player_starters(conn, player_id: int) -> None:
    conn.executemany('''INSERT OR IGNORE INTO player_recipe_knowledge
        (player_id, recipe_id, acquired_via, gold_paid, catalog_version)
        VALUES (?, ?, 'starter', 0, 1)''',
        ((int(player_id), recipe_id) for recipe_id in STARTER_RECIPE_IDS))
