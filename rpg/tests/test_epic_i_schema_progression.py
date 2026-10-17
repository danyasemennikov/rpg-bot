"""Clean-state and XP boundary tests; not gameplay acceptance."""
import sqlite3
import pytest
import database
from game.profession_progression import apply_profession_xp, profession_exp_needed
from game.profession_schema import ensure_profession_rows, ensure_profession_schema
from game.profession_state import register_profession, get_state, award_operation, PROFESSIONS
from game.player_activity import require_available
from game.action_receipts import ActionRejected


def test_exact_thresholds_and_halts():
    assert sum(profession_exp_needed(p) for p in range(1,15)) == 3220
    assert sum(profession_exp_needed(p) for p in range(16,30)) == 6930
    for level, exp, award, next_level, applied, discarded in (
        (14,359,18,15,1,17),(15,0,18,15,0,18),
        (29,689,36,30,1,35),(30,0,36,30,0,36),
        (1,0,100000,15,3220,96780),(16,0,100000,30,6930,93070)):
        result=apply_profession_xp(level,exp,award)
        assert (result.new_level,result.new_exp,result.applied,result.discarded)==(next_level,0,applied,discarded)


def test_rows_are_not_registration_and_ensure_does_not_grant_knowledge():
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        ensure_profession_schema(conn)
        for key in PROFESSIONS:
            assert get_state(conn,1,key)['registered_at'] is None
            register_profession(conn,1,key,now_ms=100)
            register_profession(conn,1,key,now_ms=200)
        assert conn.execute('SELECT COUNT(*) FROM profession_vouchers WHERE player_id=1').fetchone()[0]==19
        assert conn.execute('SELECT COUNT(*) FROM player_recipe_knowledge WHERE player_id=1').fetchone()[0]==0
        ensure_profession_schema(conn)
        conn.commit()
        conn.close()
        conn=database.get_connection()
        conn.execute('BEGIN IMMEDIATE')
        ensure_profession_schema(conn)
        assert conn.execute('SELECT COUNT(*) FROM profession_state WHERE player_id=1').fetchone()[0]==12
        assert conn.execute('PRAGMA foreign_key_check').fetchall()==[]
        for table,column in (('player_crafting_professions','player_id'),('player_gathering_professions','telegram_id')):
            key='alchemy' if column=='player_id' else 'mining'
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(f'UPDATE {table} SET level=31 WHERE {column}=1 AND profession_key=?',(key,))
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(f'UPDATE {table} SET level=15,exp=1 WHERE {column}=1 AND profession_key=?',(key,))
    finally:
        conn.rollback()
        conn.close()


def test_operation_replay_and_rollback():
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        ensure_profession_rows(conn,1)
        register_profession(conn,1,'mining')
        args=dict(operation_id='mine:one',mode='personal',source_id='iron_ore',attempted=3)
        first=award_operation(conn,1,'mining',**args)
        assert award_operation(conn,1,'mining',**args)==first
        assert get_state(conn,1,'mining')['exp']==3
        conn.rollback()
        assert conn.execute('SELECT COUNT(*) FROM profession_operation_receipts').fetchone()[0]==0
    finally:
        conn.close()


def test_guild_activity_blocks_existing_owners_until_claim():
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute("""INSERT INTO guild_job(job_id,player_id,profession_key,mode,status,plan_json,
            fingerprint,accepted_ms,next_stage_earliest_ms) VALUES ('job',1,'mining','paid_job',
            'ready_to_claim','{}','hash',0,8000)""")
        with pytest.raises(ActionRejected,match='stop_activity_first'):
            require_available(conn,1)
        assert require_available(conn,1,exclude_guild='job')['telegram_id']==1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""INSERT INTO guild_job(job_id,player_id,profession_key,mode,status,plan_json,
                fingerprint,accepted_ms,next_stage_earliest_ms) VALUES ('job2',1,'hunting','paid_job',
                'active','{}','hash',0,8000)""")
    finally:
        conn.rollback()
        conn.close()
