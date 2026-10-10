import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from database import get_connection
from game.player_feedback import acknowledge_feedback,present_pending_feedback,record_feedback
from game.quest_board import accept_hunt_contract,claim_completed_hunt_contract,list_hunt_contracts_for_player,register_contract_objective


def homecoming():
    conn = get_connection()
    conn.execute("INSERT INTO player_contract_history(player_id,contract_key) VALUES (1,'chapter_outfitter')")
    conn.commit()
    assert accept_hunt_contract(player_id=1,location_id='capital_city',contract_key='chapter_homecoming')[0]
    return conn


def test_objective_completion_ready_and_finale_same_action_receipts():
    conn = homecoming()
    conn.execute('BEGIN IMMEDIATE')
    register_contract_objective(conn,1,'craft','health_potion_small',1,'capital_city')
    register_contract_objective(conn,1,'sell','wood_common',1,'capital_city')
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM player_feedback_events WHERE event_kind='objective_complete'").fetchone()[0]==2
    assert conn.execute("SELECT COUNT(*) FROM player_feedback_events WHERE event_kind='ready'").fetchone()[0]==1
    assert 'chapter_homecoming' not in [c.contract_key for c in list_hunt_contracts_for_player(location_id='capital_city',player_id=1,lang='en')['available']]
    ok,reason,reward = claim_completed_hunt_contract(player_id=1,location_id='capital_city')
    assert ok and reason=='claimed'
    assert (reward['reward_gold'],reward['reward_exp'])==(40,80)
    finale = conn.execute("SELECT * FROM player_feedback_events WHERE event_key='chapter_finale:chapter_homecoming'").fetchone()
    assert finale['state']=='pending'
    before = tuple(conn.execute('SELECT exp,gold,level FROM players WHERE telegram_id=1').fetchone())
    assert not claim_completed_hunt_contract(player_id=1,location_id='capital_city')[0]
    assert tuple(conn.execute('SELECT exp,gold,level FROM players WHERE telegram_id=1').fetchone())==before
    assert conn.execute("SELECT COUNT(*) FROM player_feedback_events WHERE event_kind='chapter_finale'").fetchone()[0]==1
    conn.close()


def test_feedback_rollback_failed_delivery_recovery_and_acknowledgement():
    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    record_feedback(conn,1,event_key='rollback',source_kind='test',source_id='r',event_kind='progress',payload={'target':'wood_common','progress':1,'required':3})
    conn.rollback()
    assert not conn.execute('SELECT 1 FROM player_feedback_events').fetchone()
    conn.execute('BEGIN IMMEDIATE')
    record_feedback(conn,1,event_key='chapter_finale:chapter_homecoming',source_kind='chapter_claim',source_id='chapter_homecoming',event_kind='chapter_finale',payload={})
    conn.commit()
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError('offline')),edit_message_text=AsyncMock())
    with pytest.raises(RuntimeError):
        asyncio.run(present_pending_feedback(bot,1))
    assert conn.execute('SELECT state FROM player_feedback_events').fetchone()[0]=='pending'
    bot.send_message=AsyncMock(return_value=SimpleNamespace(message_id=12))
    assert asyncio.run(present_pending_feedback(bot,1))
    assert tuple(conn.execute('SELECT state,message_id FROM player_feedback_events').fetchone())==('presented',12)
    assert not asyncio.run(present_pending_feedback(bot,1))
    assert asyncio.run(present_pending_feedback(bot,1,recover_presented=True))
    assert bot.send_message.await_count==1 and bot.edit_message_text.await_count==1
    conn.execute('BEGIN IMMEDIATE')
    assert acknowledge_feedback(conn,1,'chapter_finale:chapter_homecoming')
    conn.commit()
    assert not asyncio.run(present_pending_feedback(bot,1,recover_presented=True))
    conn.close()


def test_finale_edits_claim_card_and_coalesces_earlier_minor_facts():
    conn = homecoming()
    conn.execute('BEGIN IMMEDIATE')
    register_contract_objective(conn,1,'craft','health_potion_small',1,'capital_city')
    register_contract_objective(conn,1,'sell','wood_common',1,'capital_city')
    conn.commit()
    assert claim_completed_hunt_contract(player_id=1,location_id='capital_city')[0]
    query = SimpleNamespace(message=SimpleNamespace(chat_id=1,message_id=42),edit_message_text=AsyncMock())
    bot = SimpleNamespace(send_message=AsyncMock())
    assert asyncio.run(present_pending_feedback(bot,1,originating_query=query))
    bot.send_message.assert_not_awaited()
    query.edit_message_text.assert_awaited_once()
    assert conn.execute("SELECT COUNT(*) FROM player_feedback_events WHERE state='pending'").fetchone()[0]==0
    assert conn.execute("SELECT message_id FROM player_feedback_events WHERE event_kind='chapter_finale'").fetchone()[0]==42
    conn.close()


def test_kill_feedback_is_localized_coalesced_and_acknowledged_only_after_presentation():
    from game.player_feedback import inline_feedback,acknowledge_presented_facts
    from game.quest_board import register_hunt_kill_progress
    assert accept_hunt_contract(player_id=1,location_id='capital_city',contract_key='chapter_first_watch')[0]
    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    register_hunt_kill_progress(player_id=1,mob_id='westwild_rabbit',location_id='westwild_n1',conn=conn)
    register_hunt_kill_progress(player_id=1,mob_id='westwild_rabbit',location_id='westwild_n1',conn=conn)
    conn.commit()
    text, keys = inline_feedback(1,'en','Victory')
    assert '2/2' in text and 'westwild_rabbit' not in text and len(keys)==2
    assert conn.execute("SELECT COUNT(*) FROM player_feedback_events WHERE state='pending'").fetchone()[0]==2
    acknowledge_presented_facts(1,keys)
    assert conn.execute("SELECT COUNT(*) FROM player_feedback_events WHERE state='pending'").fetchone()[0]==0
    conn.close()


def test_shared_character_reward_level_fact_uses_same_transaction():
    from game.progression_rewards import apply_progression_reward
    from game.balance import exp_to_next_level
    from unittest.mock import patch
    conn=get_connection()
    level=conn.execute('SELECT level FROM players WHERE telegram_id=1').fetchone()[0]
    conn.execute('UPDATE players SET exp=0 WHERE telegram_id=1');conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    with patch('game.player_feedback.record_feedback',side_effect=RuntimeError('feedback failure')):
        with pytest.raises(RuntimeError,match='feedback failure'):
            apply_progression_reward(conn,1,exp_to_next_level(level),3)
    conn.rollback()
    assert conn.execute('SELECT level FROM players WHERE telegram_id=1').fetchone()[0]==level
    assert conn.execute("SELECT COUNT(*) FROM player_feedback_events WHERE source_kind='character'").fetchone()[0]==0
    conn.execute('BEGIN IMMEDIATE')
    result=apply_progression_reward(conn,1,exp_to_next_level(level),3)
    conn.commit()
    assert result['level_after']==level+1
    fact=conn.execute("SELECT * FROM player_feedback_events WHERE source_kind='character'").fetchone()
    assert fact['state']=='pending' and json.loads(fact['payload_json'])=={'old_level':level,'new_level':level+1}
    conn.close()
