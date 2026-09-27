import sqlite3

import pytest

from database import get_connection
from game.regional_schema import MIGRATION_VERSION, TABLES, ensure_regional_schema, validate_table_schema


def test_clean_install_exact_shape_marker_and_restart():
    conn = get_connection()
    assert {row['name'] for row in conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'rav1_%'")} == set(TABLES)
    for table in TABLES:
        validate_table_schema(conn, table)
    assert conn.execute('SELECT COUNT(*) c FROM economy_schema_migrations WHERE version=?', (MIGRATION_VERSION,)).fetchone()['c'] == 1
    before = conn.total_changes
    ensure_regional_schema(conn)
    assert conn.total_changes == before
    conn.close()


def test_empty_partial_unmarked_install_completes_atomically():
    conn = get_connection()
    conn.execute('DELETE FROM economy_schema_migrations WHERE version=?', (MIGRATION_VERSION,))
    conn.execute('DROP TABLE rav1_combat_bindings')
    conn.execute('DROP TABLE rav1_pins')
    conn.commit()
    ensure_regional_schema(conn)
    assert {table for table in TABLES if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()} == set(TABLES)
    assert conn.execute('SELECT 1 FROM economy_schema_migrations WHERE version=?', (MIGRATION_VERSION,)).fetchone()
    conn.close()


def test_nonempty_unmarked_state_fails_closed_without_marker():
    conn = get_connection()
    conn.execute('DELETE FROM economy_schema_migrations WHERE version=?', (MIGRATION_VERSION,))
    conn.execute("INSERT INTO rav1_facts(player_id,fact_id,catalog_version,location_id) VALUES (1,'ww_root_marks',1,'westwild_n7')")
    conn.commit()
    with pytest.raises(RuntimeError, match='nonempty unmarked'):
        ensure_regional_schema(conn)
    assert not conn.execute('SELECT 1 FROM economy_schema_migrations WHERE version=?', (MIGRATION_VERSION,)).fetchone()
    assert conn.execute('SELECT fact_id FROM rav1_facts').fetchone()['fact_id'] == 'ww_root_marks'
    conn.close()


def test_marker_with_missing_or_incompatible_table_fails_closed():
    conn = get_connection()
    conn.execute('DROP TABLE rav1_pins')
    conn.commit()
    with pytest.raises(RuntimeError, match='marker exists'):
        ensure_regional_schema(conn)
    conn.close()


def test_unknown_row_version_is_rejected_on_restart():
    conn = get_connection()
    conn.execute('PRAGMA ignore_check_constraints=ON')
    conn.execute("INSERT INTO rav1_facts(player_id,fact_id,catalog_version,location_id) VALUES (1,'ww_root_marks',2,'westwild_n7')")
    conn.commit()
    with pytest.raises(RuntimeError, match='unknown RAV1 fact'):
        ensure_regional_schema(conn)
    conn.close()


def test_nested_caller_transaction_uses_savepoint_and_preserves_caller_work():
    conn = get_connection()
    conn.execute("UPDATE players SET gold=gold+1 WHERE telegram_id=1")
    ensure_regional_schema(conn)
    assert conn.in_transaction
    assert conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()['gold'] == 51
    conn.rollback()
    conn.close()
