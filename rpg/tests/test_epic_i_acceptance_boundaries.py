"""Focused runtime acceptance with funded fixtures, distinguished from journeys."""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from unittest.mock import patch

import pytest
import database
from game.action_receipts import ActionRejected
from game.profession_schema import ensure_profession_rows,GATHERING_PROFESSION_KEYS
from game.profession_state import register_profession,get_state
from game.profession_recipes import get_recipe
from game.profession_resources import RESOURCES
from game.recipe_knowledge import learn_knowledge
from game.profession_guild import MILESTONE_JOBS,accept_job,complete_stage,finish_job
from game.crafting_runtime import create_craft_batch,execute_craft_batch,execute_craft_operation


@pytest.mark.parametrize('definition',MILESTONE_JOBS.values(),ids=lambda d:d['job_key'])
def test_all_twenty_four_milestone_programs_execute_and_keep_output_in_escrow(definition):
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    key=definition['profession_key'];gather=key in GATHERING_PROFESSION_KEYS
    ensure_profession_rows(conn,1);register_profession(conn,1,key)
    table,column=('player_gathering_professions','telegram_id') if gather else ('player_crafting_professions','player_id')
    conn.execute(f'UPDATE {table} SET level=? WHERE {column}=1 AND profession_key=?',(definition['unlock_P'],key))
    conn.execute('UPDATE players SET gold=1000 WHERE telegram_id=1')
    tier=1 if definition['unlock_P']==5 else 2
    for knowledge in ([f'gp_{key}_{tier}_a'] if gather else definition['sources']):
        learn_knowledge(conn,1,knowledge)
    before=conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0]
    job=accept_job(conn,1,key,job_key=definition['job_key'],request_id='milestone',now_ms=0)
    plan=json.loads(job['plan_json']);count=15 if gather else 4
    assert len(plan['stages'])==count and plan['total_duration_ms']==120000
    for index in range(count):
        complete_stage(conn,1,job['job_id'],stage_index=index,expected_revision=index,now_ms=(index+1)*plan['stage_duration_ms'])
    result=finish_job(conn,1,job['job_id'],claim=True,expected_revision=count)
    assert result['gold_delta']==5*tier
    assert conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0]==before+5*tier
    assert conn.execute('SELECT COUNT(*) FROM inventory WHERE telegram_id=1').fetchone()[0]==0
    assert conn.execute('SELECT COUNT(*) FROM gear_instances WHERE telegram_id=1').fetchone()[0]==0
    assert conn.execute('SELECT COUNT(*) FROM player_profession_tools WHERE player_id=1').fetchone()[0]==0
    assert conn.execute("SELECT COUNT(*) FROM guild_escrow WHERE status<>'closed'").fetchone()[0]==0
    assert conn.execute('SELECT exp FROM players WHERE telegram_id=1').fetchone()[0]==0
    conn.rollback();conn.close()


def test_all_material_sources_buy_and_process_with_no_buy_sell_profit():
    from game.profession_supply import buy_material
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    ensure_profession_rows(conn,1);conn.execute('UPDATE players SET gold=1000000 WHERE telegram_id=1')
    for key in GATHERING_PROFESSION_KEYS:
        register_profession(conn,1,key)
        conn.execute('UPDATE player_gathering_professions SET level=25 WHERE telegram_id=1 AND profession_key=?',(key,))
        for tier in (1,2):learn_knowledge(conn,1,f'gp_{key}_{tier}_a')
    for resource in RESOURCES.values():
        bought=buy_material(conn,1,resource.item_id,1,request_id='buy:'+resource.item_id)
        assert bought['gold_delta']==-3*resource.sell_price
        job=accept_job(conn,1,resource.profession_key,mode='personal_processing',source_id=resource.item_id,request_id=resource.item_id,now_ms=0)
        plan=json.loads(job['plan_json'])
        assert plan['cost']==2*resource.sell_price*plan['result_qty']
        assert plan['wage']==0 and plan['total_duration_ms']==108000
        for index in range(15):complete_stage(conn,1,job['job_id'],stage_index=index,expected_revision=index,now_ms=(index+1)*7200)
        result=finish_job(conn,1,job['job_id'],claim=True,expected_revision=15)
        assert result['gold_delta']==0
        assert conn.execute('SELECT SUM(quantity) FROM inventory WHERE telegram_id=1 AND item_id=?',(resource.item_id,)).fetchone()[0]==1+plan['result_qty']
        assert resource.sell_price*(1+plan['result_qty'])<3*resource.sell_price+plan['cost']
    assert conn.execute('PRAGMA foreign_key_check').fetchall()==[]
    conn.rollback();conn.close()


def craft_fixture(recipe_id,count):
    recipe=get_recipe(recipe_id)
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    ensure_profession_rows(conn,1);register_profession(conn,1,recipe.profession_key)
    conn.execute('UPDATE players SET gold=1000 WHERE telegram_id=1')
    conn.execute('UPDATE player_crafting_professions SET level=25 WHERE player_id=1 AND profession_key=?',(recipe.profession_key,))
    learn_knowledge(conn,1,recipe_id)
    for item,qty in recipe.requirements:conn.execute('INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,?,?)',(item,qty*count))
    conn.commit();conn.close()


@pytest.mark.parametrize('recipe_id',('field_tonic','a25_M_07'))
@pytest.mark.parametrize('count',(2,4))
def test_batch_matches_n_single_operations_including_gear_rolls_and_xp(recipe_id,count):
    craft_fixture(recipe_id,count)
    snapshot=sqlite3.connect(':memory:')
    with sqlite3.connect(database.DB_PATH) as conn:conn.backup(snapshot)
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    batch=create_craft_batch(conn,1,recipe_id,count,batch_id='equivalent')
    result=execute_craft_batch(conn,1,batch['batch_id'])
    batched_state=dict(get_state(conn,1,get_recipe(recipe_id).profession_key))
    conn.commit();conn.close()
    with sqlite3.connect(database.DB_PATH) as conn:snapshot.backup(conn)
    snapshot.close()
    singles=[]
    for index in range(count):
        conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
        singles.append(execute_craft_operation(conn,1,recipe_id,operation_id=f'batch:equivalent:{index}',mode='personal'))
        conn.commit();conn.close()
    assert result['children']==singles
    conn=database.get_connection()
    assert dict(get_state(conn,1,get_recipe(recipe_id).profession_key))==batched_state
    conn.close()


def test_concurrent_batch_response_loss_and_observer_failure_are_atomic():
    craft_fixture('field_tonic',4)
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    batch=create_craft_batch(conn,1,'field_tonic',4)
    conn.commit();conn.close()
    # The first real observer performs a write before failing. Batch savepoint
    # must undo it even if the caller catches and commits the business envelope.
    def observer(conn,*args,**kwargs):
        conn.execute('UPDATE players SET gold=gold+1 WHERE telegram_id=1')
        raise RuntimeError('observer failed')
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    before=conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0]
    with patch('game.regional_objectives.observe_successful_craft',side_effect=observer):
        with pytest.raises(RuntimeError,match='observer failed'):execute_craft_batch(conn,1,batch['batch_id'])
    conn.commit();conn.close()
    conn=database.get_connection()
    assert conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0]==before
    assert conn.execute('SELECT COUNT(*) FROM profession_operation_receipts').fetchone()[0]==0
    conn.close()

    def commit():
        writer=database.get_connection();writer.execute('BEGIN IMMEDIATE')
        try:
            result=execute_craft_batch(writer,1,batch['batch_id']);writer.commit();return result
        finally:writer.close()
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:commit(),range(2)))
    assert results[0]==results[1]
    assert commit()==results[0]
    conn=database.get_connection()
    assert conn.execute('SELECT COUNT(*) FROM profession_operation_receipts').fetchone()[0]==4
    assert conn.execute("SELECT SUM(quantity) FROM inventory WHERE telegram_id=1 AND item_id='health_potion_small'").fetchone()[0]==4
    conn.close()


def test_process_crash_before_batch_commit_rolls_back_then_restart_executes_once():
    import subprocess
    import sys
    craft_fixture('field_tonic',4)
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    batch=create_craft_batch(conn,1,'field_tonic',4);conn.commit();conn.close()
    script="""import os,sys
import database
from game.crafting_runtime import execute_craft_batch
database.DB_PATH=sys.argv[1]
conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
execute_craft_batch(conn,1,sys.argv[2])
os._exit(17)
"""
    crash=subprocess.run([sys.executable,'-c',script,database.DB_PATH,batch['batch_id']],capture_output=True,text=True,timeout=30)
    assert crash.returncode==17,crash.stderr
    conn=database.get_connection()
    assert conn.execute('SELECT COUNT(*) FROM profession_operation_receipts').fetchone()[0]==0
    assert conn.execute('SELECT result_json FROM profession_batch').fetchone()[0] is None
    assert conn.execute("SELECT SUM(quantity) FROM inventory WHERE item_id='herb_common'").fetchone()[0]==12
    conn.execute('BEGIN IMMEDIATE')
    result=execute_craft_batch(conn,1,batch['batch_id']);conn.commit();conn.close()
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    assert execute_craft_batch(conn,1,batch['batch_id'])==result
    assert conn.execute('SELECT COUNT(*) FROM profession_operation_receipts').fetchone()[0]==4
    conn.rollback();conn.close()


def test_actual_travel_and_guild_starters_cannot_win_the_same_activity_slot():
    from game.travel_runtime import preview_travel,start_travel_session
    from game.player_activity import player_activity
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    ensure_profession_rows(conn,1);register_profession(conn,1,'mining');learn_knowledge(conn,1,'gp_mining_1_a')
    preview=preview_travel(conn,1,'westwild_n1');conn.commit();conn.close()
    def start(kind):
        writer=database.get_connection();writer.execute('BEGIN IMMEDIATE')
        try:
            if kind=='guild':result=accept_job(writer,1,'mining',source_id='iron_ore',request_id='race-start',now_ms=0)
            else:result=start_travel_session(writer,1,preview,request_id='race-start',now_ms=0)
            writer.commit();return kind,'accepted'
        except ActionRejected as exc:
            writer.rollback();return kind,str(exc)
        finally:writer.close()
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(start,('guild','travel')))
    assert sorted(value for kind,value in results)==['accepted','stop_activity_first']
    conn=database.get_connection()
    active=conn.execute("SELECT COUNT(*) FROM guild_job WHERE status IN ('active','ready_to_claim')").fetchone()[0]
    active+=conn.execute("SELECT COUNT(*) FROM player_travel_sessions WHERE status='running'").fetchone()[0]
    assert active==1 and player_activity(conn,1)['kind'] in ('guild','travel')
    conn.close()


@pytest.mark.parametrize('profession',GATHERING_PROFESSION_KEYS)
@pytest.mark.parametrize('tier',(1,2))
@pytest.mark.parametrize('technique',('a','b'))
def test_all_twenty_manuals_are_independent_working_entitlements(profession,tier,technique):
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    ensure_profession_rows(conn,1);register_profession(conn,1,profession)
    conn.execute('UPDATE players SET gold=1000 WHERE telegram_id=1')
    conn.execute('UPDATE player_gathering_professions SET level=? WHERE telegram_id=1 AND profession_key=?',(1 if tier==1 else 16,profession))
    knowledge=f'gp_{profession}_{tier}_{technique}'
    learn_knowledge(conn,1,knowledge)
    source=next(r.item_id for r in RESOURCES.values() if r.profession_key==profession and r.resource_tier==tier)
    job=accept_job(conn,1,profession,source_id=source,request_id='manual',now_ms=0)
    plan=json.loads(job['plan_json'])
    assert plan['required_knowledge']==[knowledge]
    assert complete_stage(conn,1,job['job_id'],stage_index=0,expected_revision=0,now_ms=8000)['applied']>0
    assert conn.execute('SELECT COUNT(*) FROM player_recipe_knowledge WHERE player_id=1').fetchone()[0]==1
    conn.rollback();conn.close()


def test_measured_policy_throughput_and_field_comparison(record_property):
    from game.profession_tools import install_tool
    from game.gathering_runtime import start_gathering_session,commit_gathering_tick
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    ensure_profession_rows(conn,1);register_profession(conn,1,'mining');learn_knowledge(conn,1,'gp_mining_1_a')
    conn.execute('UPDATE players SET gold=1000 WHERE telegram_id=1')
    rows=[]
    for level in (1,10,25):
        conn.execute('UPDATE player_gathering_professions SET level=?,exp=0 WHERE telegram_id=1 AND profession_key=\'mining\'',(level,))
        job=accept_job(conn,1,'mining',source_id='iron_ore',request_id=f'paid:{level}',now_ms=0)
        plan=json.loads(job['plan_json']);applied=0
        for index in range(15):applied+=complete_stage(conn,1,job['job_id'],stage_index=index,expected_revision=index,now_ms=(index+1)*8000)['applied']
        wage=finish_job(conn,1,job['job_id'],claim=True,expected_revision=15)['gold_delta']
        processing=accept_job(conn,1,'mining',mode='personal_processing',source_id='iron_ore',request_id=f'process:{level}',now_ms=0)
        pp=json.loads(processing['plan_json'])
        rows.append({'P':level,'paid_duration_ms':plan['total_duration_ms'],'paid_xp':applied,'gold_per_hour':wage*30,
                     'xp_per_hour':applied*30,'processing_ms':pp['total_duration_ms'],'processing_gold':pp['cost'],'processing_yield':pp['result_qty']})
        finish_job(conn,1,processing['job_id'],claim=False,expected_revision=0)
    assert [row['gold_per_hour'] for row in rows]==[150,150,150]
    assert [row['processing_ms'] for row in rows]==[120000,114000,108000]
    assert [row['paid_xp'] for row in rows]==[45,45,15] # old-tier work at P25 applies the 20% floor.
    conn.execute("UPDATE players SET location_id='old_mine_entrance' WHERE telegram_id=1")
    conn.execute("UPDATE player_gathering_professions SET level=1,exp=0 WHERE telegram_id=1 AND profession_key='mining'")
    install_tool(conn,1,'mining',1,expected_revision=0,now_ms=0)
    field=start_gathering_session(conn,1,'mining',location_id='old_mine_entrance',request_id='field-measurement',now_ms=0,seed='00'*16)
    xp=0;items={}
    for index in range(15):
        result=commit_gathering_tick(conn,field['session']['session_id'],now_ms=(index+1)*8000)
        xp+=result['xp']
        for granted in result['granted']:items[granted['item_id']]=items.get(granted['item_id'],0)+granted['quantity']
    record_property('evidence_kind','SIMULATED')
    record_property('policy_throughput',json.dumps(rows,sort_keys=True))
    record_property('field_sample',json.dumps({'duration_ms':120000,'seed':'00'*16,'profession_xp':xp,'items':items,
        'tool_wear':15,'vendor_reference':sum(RESOURCES[item].sell_price*qty for item,qty in items.items())},sort_keys=True))
    conn.rollback();conn.close()
