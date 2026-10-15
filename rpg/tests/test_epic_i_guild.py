import json
import pytest
import database
from game.action_receipts import ActionRejected
from game.profession_schema import ensure_profession_rows
from game.profession_state import register_profession,get_state
from game.recipe_knowledge import learn_knowledge
from game.profession_guild import accept_job,get_job,complete_stage,finish_job,MILESTONE_JOBS


def setup_profession(conn,key,knowledge,*,gold=0,level=1):
    ensure_profession_rows(conn,1)
    conn.execute('UPDATE players SET gold=? WHERE telegram_id=1',(gold,))
    register_profession(conn,1,key)
    learn_knowledge(conn,1,knowledge)
    table,column=('player_crafting_professions','player_id') if key=='blacksmith' else ('player_gathering_professions','telegram_id')
    conn.execute(f'UPDATE {table} SET level=? WHERE {column}=1 AND profession_key=?',(level,key))


@pytest.mark.parametrize('profession,source,knowledge,stages,duration',[
    ('mining','iron_ore','gp_mining_1_a',15,8000),
    ('blacksmith','pxe_tool_mining_1','pxe_tool_mining_1',4,30000)])
def test_paid_job_explicit_stages_restart_no_offline_catchup(profession,source,knowledge,stages,duration):
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE');setup_profession(conn,profession,knowledge)
        job=accept_job(conn,1,profession,source_id=source,request_id='start',now_ms=0)
        job_id=job['job_id']
        with pytest.raises(ActionRejected,match='guild_stage_not_due'):
            complete_stage(conn,1,job_id,stage_index=0,expected_revision=0,now_ms=duration-1)
        first=complete_stage(conn,1,job_id,stage_index=0,expected_revision=0,now_ms=120000)
        conn.commit();conn.close()
        conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
        job=get_job(conn,1,job_id)
        assert job['next_stage_earliest_ms']==120000+duration
        assert complete_stage(conn,1,job_id,stage_index=0,expected_revision=0,now_ms=200000)==first
        with pytest.raises(ActionRejected,match='guild_stage_not_due'):
            complete_stage(conn,1,job_id,stage_index=1,expected_revision=1,now_ms=120000)
        now=120000
        for index in range(1,stages):
            now+=duration
            complete_stage(conn,1,job_id,stage_index=index,expected_revision=index,now_ms=now)
        assert conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM inventory WHERE telegram_id=1').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM player_profession_tools WHERE player_id=1').fetchone()[0]==0
        assert conn.execute('SELECT exp FROM players WHERE telegram_id=1').fetchone()[0]==0
        with pytest.raises(ActionRejected,match='guild_claim_only'):
            finish_job(conn,1,job_id,claim=False,expected_revision=stages)
        result=finish_job(conn,1,job_id,claim=True,expected_revision=stages)
        assert result['gold_delta']==5 and result['granted']==[]
        assert finish_job(conn,1,job_id,claim=True,expected_revision=stages)==result
        assert conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0]==5
    finally:
        conn.rollback();conn.close()


@pytest.mark.parametrize('level,duration',[(1,120000),(10,114000),(25,108000)])
def test_processing_time_snapshot_and_cancel_boundaries(level,duration):
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE');setup_profession(conn,'mining','gp_mining_1_a',gold=100,level=level)
        job=accept_job(conn,1,'mining',mode='personal_processing',source_id='iron_ore',request_id='cancel0',now_ms=0)
        plan=json.loads(job['plan_json'])
        assert plan['total_duration_ms']==duration and plan['cost']==36
        assert finish_job(conn,1,job['job_id'],claim=False,expected_revision=0)['refund']==36
        assert finish_job(conn,1,job['job_id'],claim=False,expected_revision=0)['refund']==36
        assert conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0]==100
        job=accept_job(conn,1,'mining',mode='personal_processing',source_id='iron_ore',request_id='cancel1',now_ms=0)
        complete_stage(conn,1,job['job_id'],stage_index=0,expected_revision=0,now_ms=duration//15)
        xp=get_state(conn,1,'mining')['exp']
        assert finish_job(conn,1,job['job_id'],claim=False,expected_revision=1)['refund']==0
        assert get_state(conn,1,'mining')['exp']==xp
        assert conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0]==64
        assert conn.execute('SELECT COUNT(*) FROM inventory WHERE telegram_id=1').fetchone()[0]==0
    finally:
        conn.rollback();conn.close()


def test_catalog_and_acceptance_identity():
    assert len(MILESTONE_JOBS)==24
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE');setup_profession(conn,'mining','gp_mining_1_a',level=5)
        job=accept_job(conn,1,'mining',job_key='gj_mn_05',request_id='theme',now_ms=0)
        assert accept_job(conn,1,'mining',job_key='gj_mn_05',request_id='theme',now_ms=10000)==job
        with pytest.raises(ActionRejected,match='request_receipt_mismatch'):
            accept_job(conn,1,'mining',source_id='iron_ore',request_id='theme',now_ms=0)
        plan=json.loads(job['plan_json'])
        assert [s['source_id'] for s in plan['stages']]==['iron_ore']*8+['stone_chunk']*7
    finally:
        conn.rollback();conn.close()


def test_snapshot_survives_config_and_mastery_change(monkeypatch):
    import game.profession_guild as guild
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE');setup_profession(conn,'mining','gp_mining_1_a',level=9,gold=100)
        job=accept_job(conn,1,'mining',mode='personal_processing',source_id='iron_ore',request_id='snapshot',now_ms=0)
        conn.execute("UPDATE player_gathering_professions SET level=25 WHERE telegram_id=1 AND profession_key='mining'")
        monkeypatch.setattr(guild,'processing_duration_ms',lambda level:1)
        monkeypatch.setattr(guild,'work_xp',lambda **kwargs:10000)
        for index in range(15):
            complete_stage(conn,1,job['job_id'],stage_index=index,expected_revision=index,now_ms=(index+1)*8000)
        current=get_job(conn,1,job['job_id'])
        assert current['plan_json']==job['plan_json']
        assert get_state(conn,1,'mining')['exp']==45
        result=finish_job(conn,1,job['job_id'],claim=True,expected_revision=15)
        assert result['gold_delta']==0 and result['granted']==[{'item_id':'iron_ore','quantity':3}]
    finally:
        conn.rollback();conn.close()


def test_concurrent_stage_and_claim_each_apply_once():
    from concurrent.futures import ThreadPoolExecutor
    conn=database.get_connection()
    conn.execute('BEGIN IMMEDIATE');setup_profession(conn,'mining','gp_mining_1_a')
    job=accept_job(conn,1,'mining',source_id='iron_ore',request_id='race',now_ms=0)
    conn.commit();conn.close()
    def stage():
        writer=database.get_connection()
        try:
            writer.execute('BEGIN IMMEDIATE')
            result=complete_stage(writer,1,job['job_id'],stage_index=0,expected_revision=0,now_ms=8000)
            writer.commit();return result
        finally: writer.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:stage(),range(2)))
    assert results[0]==results[1]
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    assert get_state(conn,1,'mining')['exp']==3
    for index in range(1,15):
        complete_stage(conn,1,job['job_id'],stage_index=index,expected_revision=index,now_ms=(index+1)*8000)
    conn.commit();conn.close()
    def claim():
        writer=database.get_connection()
        try:
            writer.execute('BEGIN IMMEDIATE')
            result=finish_job(writer,1,job['job_id'],claim=True,expected_revision=15)
            writer.commit();return result
        finally: writer.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:claim(),range(2)))
    assert results[0]==results[1]
    conn=database.get_connection()
    try:
        assert conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0]==5
        assert conn.execute('SELECT COUNT(*) FROM guild_stage_receipt').fetchone()[0]==15
    finally: conn.close()
