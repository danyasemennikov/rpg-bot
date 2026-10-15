import json
import pytest
import database
from game.action_receipts import ActionRejected
from game.profession_schema import ensure_profession_rows
from game.profession_state import register_profession, get_state
from game.recipe_knowledge import learn_knowledge
from game.crafting_runtime import create_craft_batch, execute_craft_batch
import game.crafting_runtime as crafting


def boundary_fixture(conn,*,level=10,exp=0):
    ensure_profession_rows(conn,1)
    register_profession(conn,1,'alchemy')
    learn_knowledge(conn,1,'field_tonic')
    conn.execute("UPDATE player_crafting_professions SET level=?,exp=? WHERE player_id=1 AND profession_key='alchemy'",(level,exp))
    conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,'herb_common',120)")


@pytest.mark.parametrize('count,level',[(2,10),(4,25)])
def test_last_child_failure_rolls_back_everything(monkeypatch,count,level):
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        boundary_fixture(conn,level=level)
        batch=create_craft_batch(conn,1,'field_tonic',count)
        before=dict(get_state(conn,1,'alchemy'))
        original=crafting.execute_craft_operation
        calls=[]
        def failing(*args,**kwargs):
            calls.append(1)
            if len(calls)==count:
                raise RuntimeError('child failure')
            return original(*args,**kwargs)
        monkeypatch.setattr(crafting,'execute_craft_operation',failing)
        with pytest.raises(RuntimeError,match='child failure'):
            execute_craft_batch(conn,1,batch['batch_id'])
        assert conn.execute("SELECT SUM(quantity) FROM inventory WHERE telegram_id=1 AND item_id='herb_common'").fetchone()[0]==120
        assert conn.execute('SELECT COUNT(*) FROM profession_operation_receipts').fetchone()[0]==0
        assert conn.execute("SELECT COUNT(*) FROM inventory WHERE item_id='health_potion_small'").fetchone()[0]==0
        assert dict(get_state(conn,1,'alchemy'))==before
    finally:
        conn.rollback();conn.close()


def test_replay_after_response_loss_and_p15_halt():
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        boundary_fixture(conn,level=14,exp=359)
        batch=create_craft_batch(conn,1,'field_tonic',2)
        result=execute_craft_batch(conn,1,batch['batch_id'])
        assert [p['applied'] for p in result['progression']]==[1,0]
        assert [p['discarded'] for p in result['progression']]==[5,6]
        assert get_state(conn,1,'alchemy')['level']==15
        conn.commit();conn.close()
        conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
        assert execute_craft_batch(conn,1,batch['batch_id'])==result
        assert conn.execute("SELECT SUM(quantity) FROM inventory WHERE telegram_id=1 AND item_id='herb_common'").fetchone()[0]==114
        assert conn.execute('SELECT COUNT(*) FROM profession_batch_child').fetchone()[0]==2
        with pytest.raises(ActionRejected,match='stale_action'):
            execute_craft_batch(conn,777,batch['batch_id'])
        with pytest.raises(ActionRejected,match='batch_fingerprint_mismatch'):
            execute_craft_batch(conn,1,batch['batch_id'],expected_fingerprint='tampered')
    finally:
        conn.rollback();conn.close()


def test_payload_tamper_and_tool_batch_rejected():
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE');boundary_fixture(conn)
        batch=create_craft_batch(conn,1,'field_tonic',2)
        payload=batch['payload'];payload['count']=4
        conn.execute('UPDATE profession_batch SET payload_json=? WHERE batch_id=?',(json.dumps(payload),batch['batch_id']))
        with pytest.raises(ActionRejected,match='batch_fingerprint_mismatch'):
            execute_craft_batch(conn,1,batch['batch_id'])
        with pytest.raises(ActionRejected,match='invalid_batch_recipe'):
            create_craft_batch(conn,1,'pxe_tool_mining_1',2)
    finally:
        conn.rollback();conn.close()
