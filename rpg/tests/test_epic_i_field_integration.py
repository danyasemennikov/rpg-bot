import pytest
import database
from game.action_receipts import ActionRejected
from game.profession_schema import ensure_profession_rows
from game.profession_state import register_profession,get_state
from game.profession_tools import install_tool,require_tool
from game.recipe_knowledge import learn_knowledge
from game.gathering_runtime import _source_snapshot,gather_tick_roll,start_gathering_session,commit_gathering_tick


@pytest.mark.parametrize('level,applied',[(1,5),(15,0)])
def test_u1_accesses_tier_i_complex_material_and_records_cap_accounting(level,applied):
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE');ensure_profession_rows(conn,1)
        register_profession(conn,1,'mining');learn_knowledge(conn,1,'gp_mining_1_a')
        install_tool(conn,1,'mining',1,expected_revision=0,now_ms=0)
        conn.execute("UPDATE player_gathering_professions SET level=? WHERE telegram_id=1 AND profession_key='mining'",(level,))
        conn.execute("UPDATE players SET location_id='old_mine_entrance' WHERE telegram_id=1")
        snapshot=_source_snapshot('old_mine_entrance','mining')
        seed=next(f'{n:032x}' for n in range(1000) if gather_tick_roll(f'{n:032x}',1,snapshot)['item_id']=='gem_common')
        result=start_gathering_session(conn,1,'mining',location_id='old_mine_entrance',request_id='field',now_ms=0,seed=seed)
        tick=commit_gathering_tick(conn,result['session']['session_id'],now_ms=8000)
        assert tick['granted'][0]['item_id']=='gem_common'
        assert tick['xp']==applied
        fact=conn.execute('SELECT attempted,applied,discarded FROM profession_operation_receipts').fetchone()
        assert fact[:]==(5,applied,5-applied)
        assert require_tool(conn,1,'mining')['durability']==89
    finally:
        conn.rollback();conn.close()


def test_installed_tool_does_not_imply_registration_or_tier_entitlement():
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE');ensure_profession_rows(conn,1)
        install_tool(conn,1,'mining',6,expected_revision=0,now_ms=0)
        with pytest.raises(ActionRejected,match='profession_not_registered'):
            require_tool(conn,1,'mining')
        register_profession(conn,1,'mining')
        with pytest.raises(ActionRejected,match='tool_tier_locked'):
            require_tool(conn,1,'mining')
    finally:
        conn.rollback();conn.close()
