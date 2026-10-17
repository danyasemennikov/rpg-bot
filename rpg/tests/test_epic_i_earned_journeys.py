"""SIMULATED clock, real committed SQLite actions and earned inputs only.

No admin money/material/XP is injected after the C1/gold0 starting condition.
This is not wall-clock playtesting or real Telegram acceptance.
"""
import json
import pytest
import database
from game.profession_state import PROFESSIONS,get_state,register_profession
from game.profession_schema import GATHERING_PROFESSION_KEYS
from game.profession_recipes import ACTIVE_RECIPES
from game.profession_resources import RESOURCES
from game.recipe_knowledge import learn_knowledge
from game.profession_guild import accept_job,complete_stage,finish_job,get_job
from game.profession_exams import EXAM_SOURCES,register_exam,perform_exam_action,confirm_exam


@pytest.mark.parametrize('profession',PROFESSIONS)
def test_c1_gold0_to_p30_earned_journey(profession,record_property):
    conn=database.get_connection()
    conn.execute('BEGIN IMMEDIATE')
    conn.execute('UPDATE players SET gold=0 WHERE telegram_id=1')
    register_profession(conn,1,profession,now_ms=0)
    gathering=profession in GATHERING_PROFESSION_KEYS
    if gathering:
        learn_knowledge(conn,1,f'gp_{profession}_1_a')
        source=max((r for r in RESOURCES.values() if r.profession_key==profession and r.resource_tier==1),
                   key=lambda r:('S','R','C').index(r.work_category)).item_id
    else:
        for knowledge in dict.fromkeys(EXAM_SOURCES[profession]):
            learn_knowledge(conn,1,knowledge)
        source=EXAM_SOURCES[profession][0]
    conn.commit()
    now=0
    jobs=0
    stages=0
    try:
        for cap in (15,30):
            while get_state(conn,1,profession)['level']<cap:
                conn.execute('BEGIN IMMEDIATE')
                job=accept_job(conn,1,profession,source_id=source,request_id=f'earned:{jobs}',now_ms=now)
                plan=json.loads(job['plan_json'])
                conn.commit()
                for index in range(len(plan['stages'])):
                    now+=plan['stage_duration_ms']
                    conn.execute('BEGIN IMMEDIATE')
                    complete_stage(conn,1,job['job_id'],stage_index=index,expected_revision=index,now_ms=now)
                    conn.commit()
                    stages+=1
                conn.execute('BEGIN IMMEDIATE')
                finish_job(conn,1,job['job_id'],claim=True,expected_revision=len(plan['stages']))
                conn.commit()
                jobs+=1
                assert jobs<1000,'journey does not converge'
                assert conn.execute('SELECT level,exp FROM players WHERE telegram_id=1').fetchone()[:]==(1,0)
            assert get_state(conn,1,profession)['exp']==0
            if cap==15:
                conn.execute('BEGIN IMMEDIATE')
                exam=register_exam(conn,1,profession,now_ms=now)
                conn.commit()
                for revision,criterion in enumerate(('a','b','sample')):
                    conn.execute('BEGIN IMMEDIATE')
                    perform_exam_action(conn,1,exam['exam_id'],criterion,expected_revision=revision,now_ms=now)
                    conn.commit()
                if gathering:
                    reward=f'gp_{profession}_2_a'
                    source=max((r for r in RESOURCES.values() if r.profession_key==profession and r.resource_tier==2),
                               key=lambda r:('S','R','C').index(r.work_category)).item_id
                else:
                    recipe=max((r for r in ACTIVE_RECIPES if r.profession_key==profession and r.tier==2),
                               key=lambda r:('S','R','C').index(r.work_category))
                    reward=source=recipe.recipe_id
                conn.execute('BEGIN IMMEDIATE')
                confirm_exam(conn,1,exam['exam_id'],reward,expected_revision=3)
                conn.commit()
                assert (get_state(conn,1,profession)['level'],get_state(conn,1,profession)['exp'])==(16,0)
        assert get_state(conn,1,profession)['level']==30
        assert conn.execute('SELECT COUNT(*) FROM profession_state WHERE player_id=1 AND registered_at IS NOT NULL').fetchone()[0]==1
        assert conn.execute('SELECT SUM(applied) FROM profession_operation_receipts WHERE player_id=1').fetchone()[0]==10150
        assert conn.execute('SELECT COUNT(*) FROM inventory WHERE telegram_id=1').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM pve_harvest_claims WHERE player_id=1').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM player_profession_tools WHERE player_id=1').fetchone()[0]==0
        assert conn.execute('PRAGMA foreign_key_check').fetchall()==[]
        record_property('evidence_kind','SIMULATED')
        record_property('profession',profession)
        record_property('elapsed_policy_ms',now)
        record_property('committed_stages',stages)
        record_property('paid_jobs',jobs)
        record_property('earned_gold',conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0])
    finally:
        conn.rollback();conn.close()
