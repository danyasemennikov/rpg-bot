"""Execute every recipe; fixture funding is catalog evidence, not earned progression."""
import json
import pytest
import database
from game.profession_recipes import ACTIVE_RECIPES
from game.profession_schema import ensure_profession_rows
from game.profession_state import register_profession
from game.recipe_knowledge import learn_knowledge
from game.crafting_runtime import execute_craft_operation
from game.profession_consumables import CONSUMABLES,use_payload,bind_next_battle
from game.action_receipts import issue_actions
from game.actor_snapshot import build_actor_snapshot
from handlers.inventory import use_inventory_consumable


@pytest.mark.parametrize('recipe',ACTIVE_RECIPES,ids=lambda r:r.recipe_id)
def test_every_frozen_recipe_delivers_real_output_and_replays_after_commit(recipe):
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    ensure_profession_rows(conn,1);register_profession(conn,1,recipe.profession_key)
    conn.execute('UPDATE players SET gold=1000,hp=20,mana=10 WHERE telegram_id=1')
    conn.execute('UPDATE player_crafting_professions SET level=16,exp=0 WHERE player_id=1 AND profession_key=?',(recipe.profession_key,))
    learn_knowledge(conn,1,recipe.recipe_id)
    for item,qty in recipe.requirements:
        conn.execute('INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,?,?)',(item,qty))
    result=execute_craft_operation(conn,1,recipe.recipe_id,operation_id='all-recipes',mode='personal',expected_tool_revision=0)
    output=recipe.output_spec
    assert result['status']=='crafted'
    assert sum(g['quantity'] for g in result['granted'])==output.quantity
    for item,qty in recipe.requirements:
        assert conn.execute('SELECT COALESCE(SUM(quantity),0) FROM inventory WHERE telegram_id=1 AND item_id=?',(item,)).fetchone()[0]==0
    if output.kind=='tool':
        row=conn.execute('SELECT tier FROM player_profession_tools WHERE player_id=1 AND profession_key=?',(output.profession_key,)).fetchone()
        assert row['tier']==output.tool_tier
    elif output.kind=='gear':
        rows=conn.execute('SELECT * FROM gear_instances WHERE telegram_id=1 AND base_item_id=?',(output.item_id,)).fetchall()
        assert len(rows)==output.quantity
        assert all(r['item_tier']==output.item_tier and r['rarity']==output.rarity and r['equipped_slot'] is None for r in rows)
    else:
        assert conn.execute('SELECT SUM(quantity) FROM inventory WHERE telegram_id=1 AND item_id=?',(output.item_id,)).fetchone()[0]==output.quantity
    conn.commit();conn.close()
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    assert execute_craft_operation(conn,1,recipe.recipe_id,operation_id='all-recipes',mode='personal',expected_tool_revision=0)==result
    assert conn.execute('SELECT COUNT(*) FROM profession_operation_receipts').fetchone()[0]==1
    conn.commit();conn.close()
    if output.item_id in CONSUMABLES:
        conn=database.get_connection()
        inv=conn.execute('SELECT id,quantity FROM inventory WHERE telegram_id=1 AND item_id=?',(output.item_id,)).fetchone()
        payload=use_payload(conn,1,inv['id'],inv['quantity']);conn.close()
        token=issue_actions(1,'use',[payload])[payload]
        used=use_inventory_consumable(1,token)
        assert used['status']==('consumable_wrong_context' if CONSUMABLES[output.item_id].get('cleanse') else 'used')
        if 'slot' in CONSUMABLES[output.item_id]:
            conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
            actor=bind_next_battle(conn,1,'pve','crafted-effect',build_actor_snapshot(1,conn=conn))
            assert actor['profession_consumables'][0]['item_id']==output.item_id
            conn.rollback();conn.close()

