"""Migration preservation and failure tests against isolated SQLite files."""

import json
import sqlite3

import pytest

import database
from game.player_experience_schema import (
    MIGRATION_VERSION, TABLES, ensure_player_experience_schema,
    grant_player_pxe1_starters,
)


def install(conn, now_ms=1000):
    conn.execute('BEGIN IMMEDIATE')
    ensure_player_experience_schema(conn, now_ms=now_ms)
    conn.commit()


def snapshot(conn):
    return {table: [tuple(row) for row in conn.execute(f'SELECT * FROM {table} ORDER BY 1,2')]
            for table in TABLES}


def test_exact_additions_and_indexes():
    conn = database.get_connection()
    assert len(TABLES) == 8
    for table, additions in {
        'players': ['location_visit_revision'],
        'pve_encounters': ['lifecycle_version','formation_deadline_ms','formation_revision','runtime_started_ms'],
        'pvp_engagements': ['world_model_version','locked_roster_json','roster_locked_ms'],
        'pvp_engagement_reinforcements': ['membership_version'],
    }.items():
        columns = {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}
        assert set(additions) <= columns
    assert conn.execute('SELECT 1 FROM economy_schema_migrations WHERE version=?', (MIGRATION_VERSION,)).fetchone()
    assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    assert not conn.execute('PRAGMA foreign_key_check').fetchall()
    install(conn)
    conn.close()


def test_starter_grants_are_insert_only_and_survive_reinstallation():
    conn = database.get_connection()
    conn.execute('BEGIN IMMEDIATE')
    grant_player_pxe1_starters(conn, 1, now_ms=2000, acquired_via='starter')
    conn.execute("UPDATE player_profession_tools SET tier=3,durability=7,bootstrap_used_mask=3,revision=9 WHERE player_id=1 AND profession_key='mining'")
    conn.commit()
    before = snapshot(conn)
    install(conn, 999999)
    conn.execute('BEGIN IMMEDIATE')
    grant_player_pxe1_starters(conn, 1, now_ms=999999, acquired_via='grandfather')
    conn.commit()
    assert snapshot(conn) == before
    assert conn.execute('SELECT COUNT(*) FROM player_profession_tools WHERE player_id=1').fetchone()[0] == 5
    assert conn.execute("SELECT COUNT(*) FROM player_recipe_knowledge WHERE player_id=1 AND recipe_id LIKE 'pxe_tool_%'").fetchone()[0] == 5
    conn.close()


def test_marker_with_missing_table_fails_closed_and_rolls_back():
    conn = database.get_connection()
    conn.execute('DROP TABLE player_pxe1_ui')
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    with pytest.raises(RuntimeError, match='incomplete schema'):
        ensure_player_experience_schema(conn)
    assert conn.in_transaction
    assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='player_pxe1_ui'").fetchone()
    conn.rollback()
    conn.close()


def test_constraints_and_foreign_keys_are_enforced():
    conn = database.get_connection()
    for player, profession, tier, durability, mask in (
        (999999,'mining',1,60,0), (1,'mining',5,60,0), (1,'mining',1,61,0),
        (1,'fishing',1,60,1), (1,'mining',1,60,8),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute('''INSERT INTO player_profession_tools
                (player_id,profession_key,tier,durability,bootstrap_used_mask,schema_version,created_ms,updated_ms)
                VALUES (?,?,?,?,?,1,0,0)''', (player,profession,tier,durability,mask))
        conn.rollback()
    conn.close()


def test_caller_rollback_removes_marker_and_grants():
    conn = database.get_connection()
    conn.execute('DELETE FROM economy_schema_migrations WHERE version=?', (MIGRATION_VERSION,))
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    ensure_player_experience_schema(conn, now_ms=3000)
    assert conn.execute('SELECT COUNT(*) FROM player_profession_tools').fetchone()[0] == 10
    conn.rollback()
    assert conn.execute('SELECT COUNT(*) FROM player_profession_tools').fetchone()[0] == 0
    assert not conn.execute('SELECT 1 FROM economy_schema_migrations WHERE version=?', (MIGRATION_VERSION,)).fetchone()
    conn.close()


def test_pending_pvp_deadline_and_legacy_live_state_preserved():
    conn = database.get_connection()
    conn.execute('DELETE FROM economy_schema_migrations WHERE version=?', (MIGRATION_VERSION,))
    original_battle = json.dumps({'battle': {'state':'live','attacker_hp':40,'defender_hp':50}})
    for state, payload in [('pending', '{}'), ('active', original_battle)]:
        conn.execute('''INSERT INTO pvp_engagements(attacker_id,defender_id,location_id,
            engagement_started_at,engagement_ready_at,engagement_state,reason_context)
            VALUES (1,777,'westwild_n3','2026-10-05T00:00:00+00:00','2026-10-05T00:05:00+00:00',?,?)''', (state,payload))
    conn.execute("INSERT INTO pvp_engagement_reinforcements(engagement_id,side,inviter_id,ally_id,status) VALUES (1,'initiator',1,123,'accepted')")
    conn.commit()
    install(conn)
    pending, live = conn.execute('SELECT * FROM pvp_engagements ORDER BY id').fetchall()
    assert pending['world_model_version'] == 1
    assert pending['engagement_ready_at'] == '2026-10-05T00:05:00+00:00'
    assert len(pending['combat_seed']) == 32
    assert live['world_model_version'] == 0 and live['reason_context'] == original_battle
    assert conn.execute('SELECT status FROM pvp_engagement_reinforcements WHERE id=1').fetchone()[0] == 'expired'
    conn.execute("UPDATE pvp_engagement_reinforcements SET membership_version=1,status='accepted'")
    conn.commit()
    install(conn, 999999)
    assert conn.execute('SELECT status FROM pvp_engagement_reinforcements WHERE id=1').fetchone()[0] == 'accepted'
    conn.close()


def test_existing_authoritative_player_state_and_receipt_bytes_preserved():
    conn = database.get_connection()
    conn.execute('DELETE FROM economy_schema_migrations WHERE version=?', (MIGRATION_VERSION,))
    conn.execute("UPDATE players SET level=12,gold=432,hp=79,mana=31,infamy=7,travel_revision=8 WHERE telegram_id=1")
    conn.execute("INSERT INTO player_gathering_professions(telegram_id,profession_key,level,exp) VALUES (1,'mining',14,20001)")
    conn.execute("UPDATE player_crafting_professions SET level=18,exp=10001 WHERE player_id=1")
    conn.execute("INSERT INTO player_contract_history(player_id,contract_key) VALUES (1,'chapter_homecoming')")
    receipt = '{ "status": "crafted", "xp": 250, "historical": true }'
    conn.execute("INSERT INTO economy_action_receipts(player_id,request_id,action_kind,request_hash,schema_version,catalog_version,result_json) VALUES (1,'old','craft','hash',1,1,?)", (receipt,))
    conn.commit()
    preserved = ('players','inventory','equipment','gear_instances','player_crafting_professions',
                 'player_gathering_professions','player_contract_history','economy_action_receipts',
                 'player_location_discovery','weapon_mastery','player_skills')
    before = {t: [tuple(r) for r in conn.execute(f'SELECT * FROM {t}')] for t in preserved}
    install(conn)
    assert before == {t: [tuple(r) for r in conn.execute(f'SELECT * FROM {t}')] for t in preserved}
    finale = conn.execute("SELECT * FROM player_feedback_events WHERE player_id=1").fetchone()
    assert finale['state'] == 'acknowledged'
    assert finale['event_key'] == 'chapter_finale:chapter_homecoming'
    assert conn.execute("SELECT result_json FROM economy_action_receipts WHERE request_id='old'").fetchone()[0] == receipt
    conn.close()
