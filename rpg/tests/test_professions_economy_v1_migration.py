import os
import sqlite3

import database
from game.profession_schema import CRAFTING_PROFESSION_KEYS, MIGRATION_VERSION


def test_migration_preserves_rows_and_is_idempotent(tmp_path, monkeypatch):
    path = tmp_path / 'game.db'; monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    conn = database.get_connection()
    conn.execute("INSERT INTO players(telegram_id,name) VALUES (1,'old')")
    conn.execute("INSERT INTO player_crafting_professions(player_id,profession_key,level,exp) VALUES (1,'alchemy',7,321)")
    conn.execute("DELETE FROM economy_schema_migrations WHERE version=?", (MIGRATION_VERSION,))
    conn.commit()
    # Already-wide unmarked recovery preserves exact state and completes the marker.
    from game.profession_schema import ensure_profession_schema
    conn.execute('BEGIN IMMEDIATE'); ensure_profession_schema(conn); conn.commit()
    assert tuple(conn.execute("SELECT level,exp FROM player_crafting_professions WHERE player_id=1 AND profession_key='alchemy'").fetchone()) == (7,321)
    assert {r['profession_key'] for r in conn.execute('SELECT profession_key FROM player_crafting_professions WHERE player_id=1')} == set(CRAFTING_PROFESSION_KEYS)
    before = conn.total_changes; conn.execute('BEGIN IMMEDIATE'); ensure_profession_schema(conn); conn.commit()
    assert conn.execute('SELECT COUNT(*) c FROM economy_schema_migrations WHERE version=?',(MIGRATION_VERSION,)).fetchone()['c'] == 1
    conn.close()
