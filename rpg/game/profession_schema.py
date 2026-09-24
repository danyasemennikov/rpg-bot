"""Lossless, idempotent PEV1-1 profession/economy schema migration."""

from __future__ import annotations

import sqlite3

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


def _is_seven_key_schema(sql: str) -> bool:
    return all(f"'{key}'" in sql for key in CRAFTING_PROFESSION_KEYS)


def _is_frozen_schema(sql: str) -> bool:
    return all(f"'{key}'" in sql for key in ('alchemy', 'cooking', 'medium_armor')) and not _is_seven_key_schema(sql)


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
    elif not _is_seven_key_schema(sql):
        if marker or not _is_frozen_schema(sql):
            raise RuntimeError('unexpected player_crafting_professions schema')
        before = [tuple(row) for row in conn.execute(
            'SELECT player_id, profession_key, level, exp FROM player_crafting_professions ORDER BY 1,2'
        )]
        conn.execute('DROP TABLE IF EXISTS player_crafting_professions_pev1_new')
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
