import pytest
import database
from game.profession_recipes import ACTIVE_RECIPES, GATHERING_MANUALS
from game.profession_resources import RESOURCES
from game.items_data import ITEMS
from game.profession_schema import ensure_profession_rows
from game.profession_state import register_profession, PROFESSIONS
from game.recipe_knowledge import learn_knowledge
from game.profession_tools import TOOL_CAPACITY


def test_catalog_closure_and_tool_bom():
    assert len(ACTIVE_RECIPES)==len({r.recipe_id for r in ACTIVE_RECIPES})==153
    assert [sum(r.tier==tier for r in ACTIVE_RECIPES) for tier in (1,2)]==[69,84]
    assert len(RESOURCES)==45
    assert len(GATHERING_MANUALS)==20
    assert sum(r.output_spec.kind=='tool' for r in ACTIVE_RECIPES)==30
    for recipe in ACTIVE_RECIPES:
        assert recipe.required_level==(1 if recipe.tier==1 else 16)
        assert recipe.learning_gold==(8 if recipe.tier==1 else 60)
        assert recipe.work_category in ('S','R','C')
        assert all(i in RESOURCES and type(q) is int and q>0 for i,q in recipe.requirements)
        if recipe.output_spec.kind=='tool':
            if recipe.output_spec.tool_tier==4:
                assert all(RESOURCES[i].resource_tier==1 for i,q in recipe.requirements)
        else:
            assert recipe.output_spec.item_id in ITEMS
            assert ITEMS[recipe.output_spec.item_id]['sell_price']*recipe.output_spec.quantity<=3*recipe.material_value//5
    assert TOOL_CAPACITY=={1:90,2:150,3:210,4:240,5:300,6:360}


@pytest.mark.parametrize('profession',PROFESSIONS)
def test_registration_explicit_learning_at_gold_zero(profession):
    conn=database.get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('UPDATE players SET gold=0 WHERE telegram_id=1')
        ensure_profession_rows(conn,1)
        register_profession(conn,1,profession)
        if profession in ('woodcutting','mining','herbalism','fishing','hunting'):
            choices=[k for k,v in GATHERING_MANUALS.items() if v['profession_key']==profession and v['tier']==1]
            free_count=1
        else:
            choices=[r.recipe_id for r in ACTIVE_RECIPES if r.profession_key==profession and r.tier==1]
            free_count=2
        for choice in choices[:free_count]:
            assert learn_knowledge(conn,1,choice)['gold_delta']==0
        for choice in choices[:free_count]:
            assert learn_knowledge(conn,1,choice)['status']=='already_known'
        assert conn.execute('SELECT COUNT(*) FROM profession_vouchers WHERE player_id=1 AND knowledge_id IS NOT NULL').fetchone()[0]==free_count
        assert conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0]==0
    finally:
        conn.rollback()
        conn.close()
