"""Shared pytest database isolation for runtime tests.

Most tests exercise live SQLite helpers through ``database.get_connection``.
Keep them off the developer ``game.db`` file so stale local data, locks, and
cross-test writes cannot leak into the baseline run.
"""

from __future__ import annotations

import os

import pytest

import database
from game.pve_live import _ensure_pve_encounter_table, _ensure_world_spawn_table
from game.seed import seed_items


@pytest.fixture(autouse=True)
def isolated_sqlite_db(tmp_path):
    """Run each test against its own initialized SQLite database file."""
    original_db_path = database.DB_PATH
    database.DB_PATH = os.fspath(tmp_path / "test_game.db")
    database.init_db()
    seed_items()
    _ensure_pve_encounter_table()
    _ensure_world_spawn_table()

    conn = database.get_connection()
    for telegram_id in (1, 777):
        conn.execute(
            """
            INSERT OR IGNORE INTO players (
                telegram_id, username, name, level, hp, max_hp, mana, max_mana,
                strength, agility, intuition, vitality, wisdom, luck, location_id
            ) VALUES (?, 'test_user', 'TestUser', 1, 100, 100, 100, 100, 10, 10, 10, 10, 10, 10, 'capital_city')
            """,
            (telegram_id,),
        )
        conn.execute("INSERT OR IGNORE INTO equipment (telegram_id) VALUES (?)", (telegram_id,))
    conn.commit()
    conn.close()

    try:
        yield
    finally:
        database.DB_PATH = original_db_path
