"""Boundary fixtures use injected resources; these are not natural journeys."""
import pytest
import database
from game.action_receipts import ActionRejected
from game.profession_schema import ensure_profession_rows
from game.profession_state import register_profession
from game.profession_recipes import ACTIVE_RECIPES
from game.recipe_knowledge import learn_knowledge
from game.profession_supply import buy_material,commission_quote,execute_commission
from game.profession_tools import TOOL_CAPACITY
from game.crafting_runtime import execute_craft_operation


def test_buy_replay_and_strict_identity():
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('UPDATE players SET gold=100 WHERE telegram_id=1')
        first=buy_material(conn,1,'iron_ore',2,request_id='ui:buy')
        assert first['gold_delta']==-36
        assert buy_material(conn,1,'iron_ore',2,request_id='ui:buy')==first
        with pytest.raises(ActionRejected,match='request_receipt_mismatch'):
            buy_material(conn,1,'iron_ore',3,request_id='ui:buy')
        assert conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0]==64
    finally:
        conn.rollback();conn.close()


@pytest.mark.parametrize('profession',('woodcutting','mining','herbalism','fishing','hunting'))
def test_commission_all_grades_without_maker_or_previous_tool(profession):
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        ensure_profession_rows(conn,1)
        register_profession(conn,1,profession)
        conn.execute('UPDATE player_gathering_professions SET level=16 WHERE telegram_id=1 AND profession_key=?',(profession,))
        conn.execute('UPDATE players SET gold=100000 WHERE telegram_id=1')
        for tier in (1,2,3,4,5,6):
            rid=f'pxe_tool_{profession}_{tier}' if tier<=4 else f'a25_tool_{profession}_{tier}'
            quote=commission_quote(conn,1,rid)
            result=execute_commission(conn,1,rid,expected_revision=quote['tool_revision'],confirmed=True,
                request_id=str(tier),expected_quote=quote)
            assert result['progression']==[]
            assert result['granted'][0]['tool']['durability']==TOOL_CAPACITY[tier]
            assert execute_commission(conn,1,rid,expected_revision=quote['tool_revision'],confirmed=True,
                request_id=str(tier),expected_quote=quote)==result
        assert conn.execute('SELECT COUNT(*) FROM profession_operation_receipts').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM player_recipe_knowledge').fetchone()[0]==0
    finally:
        conn.rollback();conn.close()


def test_every_catalog_recipe_has_executable_personal_output():
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        ensure_profession_rows(conn,1)
        conn.execute('UPDATE players SET gold=1000000 WHERE telegram_id=1')
        for profession in {r.profession_key for r in ACTIVE_RECIPES}:
            register_profession(conn,1,profession)
        conn.execute('UPDATE player_crafting_professions SET level=16 WHERE player_id=1')
        for recipe in ACTIVE_RECIPES:
            learn_knowledge(conn,1,recipe.recipe_id)
            for item,quantity in recipe.requirements:
                conn.execute('INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,?,?)',(item,quantity))
            tool_revision=None
            if recipe.output_spec.kind=='tool':
                old=conn.execute('SELECT revision FROM player_profession_tools WHERE player_id=1 AND profession_key=?',
                    (recipe.output_spec.profession_key,)).fetchone()
                tool_revision=old['revision'] if old else 0
            result=execute_craft_operation(conn,1,recipe.recipe_id,operation_id='catalog:'+recipe.recipe_id,
                mode='personal',expected_tool_revision=tool_revision)
            assert result['status']=='crafted',recipe.recipe_id
            assert sum(g['quantity'] for g in result['granted'])==1
            if recipe.recipe_id in ('a25_M_03','a25_M_07'):
                from game.gear_instances import resolve_gear_instance_item_data
                instance_id=result['granted'][0]['instance_ids'][0]
                instance=dict(conn.execute('SELECT * FROM gear_instances WHERE id=?',(instance_id,)).fetchone())
                # Ignore random secondary rolls: verify the template allocation.
                instance['secondary_rolls_json']='[]'
                bonuses=resolve_gear_instance_item_data(instance)['resolved_stat_bonus']
                if recipe.recipe_id=='a25_M_03':
                    assert bonuses=={'accuracy':3,'evasion':1,'max_hp':1}
                else:
                    assert bonuses=={'accuracy':6,'evasion':2}
        assert conn.execute('SELECT COUNT(*) FROM profession_operation_receipts').fetchone()[0]==153
    finally:
        conn.rollback();conn.close()
