"""Exam boundary fixtures. Natural earned progression is tested separately."""
import pytest
import database
from game.action_receipts import ActionRejected
from game.profession_schema import ensure_profession_rows,GATHERING_PROFESSION_KEYS
from game.profession_state import register_profession,get_state
from game.profession_recipes import ACTIVE_RECIPES,GATHERING_MANUALS
from game.recipe_knowledge import learn_knowledge
from game.profession_exams import EXAM_SOURCES,register_exam,perform_exam_action,confirm_exam


def exam_fixture(conn,profession):
    ensure_profession_rows(conn,1)
    conn.execute('UPDATE players SET gold=0 WHERE telegram_id=1')
    register_profession(conn,1,profession,now_ms=0)
    gathering=profession in GATHERING_PROFESSION_KEYS
    if gathering:
        learn_knowledge(conn,1,f'gp_{profession}_1_a')
    else:
        for knowledge in dict.fromkeys(EXAM_SOURCES[profession]):
            learn_knowledge(conn,1,knowledge)
    table,column=('player_gathering_professions','telegram_id') if gathering else ('player_crafting_professions','player_id')
    conn.execute(f'UPDATE {table} SET level=15 WHERE {column}=1 AND profession_key=?',(profession,))
    return register_exam(conn,1,profession,now_ms=100)


def reward_choices(profession):
    if profession in GATHERING_PROFESSION_KEYS:
        return [k for k,v in GATHERING_MANUALS.items() if v['profession_key']==profession and v['tier']==2]
    return [r.recipe_id for r in ACTIVE_RECIPES if r.profession_key==profession and r.tier==2]


@pytest.mark.parametrize('profession',EXAM_SOURCES)
def test_exam_three_new_operations_and_single_promotion(profession):
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE');exam=exam_fixture(conn,profession)
        assert register_exam(conn,1,profession,now_ms=200)['exam_id']==exam['exam_id']
        with pytest.raises(ActionRejected,match='exam_practices_incomplete'):
            perform_exam_action(conn,1,exam['exam_id'],'sample',expected_revision=0,now_ms=200)
        for revision,criterion in enumerate(('a','b','sample')):
            first=perform_exam_action(conn,1,exam['exam_id'],criterion,expected_revision=revision,now_ms=200+revision)
            assert perform_exam_action(conn,1,exam['exam_id'],criterion,expected_revision=revision,now_ms=300)==first
        assert get_state(conn,1,profession)['level']==15 and get_state(conn,1,profession)['exp']==0
        assert conn.execute('SELECT COUNT(*) FROM profession_exam_proof').fetchone()[0]==3
        assert conn.execute('SELECT COUNT(DISTINCT operation_id) FROM profession_exam_proof').fetchone()[0]==3
        assert conn.execute('SELECT COUNT(*) FROM inventory WHERE telegram_id=1').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM player_profession_tools WHERE player_id=1').fetchone()[0]==0
        reward=reward_choices(profession)[0]
        first=confirm_exam(conn,1,exam['exam_id'],reward,expected_revision=3)
        assert confirm_exam(conn,1,exam['exam_id'],reward_choices(profession)[1],expected_revision=3)==first
        assert (get_state(conn,1,profession)['level'],get_state(conn,1,profession)['exp'])==(16,0)
        assert conn.execute("SELECT COUNT(*) FROM player_recipe_knowledge WHERE player_id=1 AND acquired_via='exam'").fetchone()[0]==1
        assert conn.execute('SELECT gold,exp FROM players WHERE telegram_id=1').fetchone()[:]==(0,0)
    finally:
        conn.rollback();conn.close()


def test_foreign_or_paid_proof_cannot_promote():
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE');exam=exam_fixture(conn,'blacksmith')
        for revision,criterion in enumerate(('a','b','sample')):
            perform_exam_action(conn,1,exam['exam_id'],criterion,expected_revision=revision,now_ms=200+revision)
        conn.execute("UPDATE profession_operation_receipts SET origin_mode='paid_job' WHERE operation_id=?",('exam:'+exam['exam_id']+':a',))
        with pytest.raises(ActionRejected,match='invalid_exam_proof'):
            confirm_exam(conn,1,exam['exam_id'],reward_choices('blacksmith')[0],expected_revision=3)
        assert get_state(conn,1,'blacksmith')['level']==15
        assert conn.execute("SELECT COUNT(*) FROM player_recipe_knowledge WHERE acquired_via='exam'").fetchone()[0]==0
    finally:
        conn.rollback();conn.close()


def test_concurrent_different_choices_return_same_certificate():
    from concurrent.futures import ThreadPoolExecutor
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    exam=exam_fixture(conn,'mining')
    for revision,criterion in enumerate(('a','b','sample')):
        perform_exam_action(conn,1,exam['exam_id'],criterion,expected_revision=revision,now_ms=200+revision)
    conn.commit();conn.close()
    def confirm(choice):
        writer=database.get_connection()
        try:
            writer.execute('BEGIN IMMEDIATE')
            result=confirm_exam(writer,1,exam['exam_id'],choice,expected_revision=3)
            writer.commit();return result
        finally:writer.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(confirm,reward_choices('mining')))
    assert results[0]==results[1]
    conn=database.get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM player_recipe_knowledge WHERE acquired_via='exam'").fetchone()[0]==1
        assert get_state(conn,1,'mining')['level']==16
    finally:conn.close()
