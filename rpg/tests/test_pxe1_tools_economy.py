import json

import pytest

import database
from game.action_receipts import issue_actions
from game.player_experience_schema import grant_player_pxe1_starters
from game.profession_recipes import ACTIVE_RECIPES, recipe_intent_payload
from game.profession_tools import (
    commit_tool_maintenance, craft_tool, get_tool, install_tool, repair_costs, repair_quote,
)


@pytest.mark.parametrize('profession',['woodcutting','mining'])
def test_tier_two_commission_contributes_directly_once_and_preserves_mask(profession):
    from game.profession_schema import ensure_profession_rows
    conn = database.get_connection()
    conn.execute('BEGIN IMMEDIATE')
    grant_player_pxe1_starters(conn,1,now_ms=0,acquired_via='starter')
    ensure_profession_rows(conn,1)
    conn.execute("UPDATE players SET location_id='hub_westwild',gold=1000 WHERE telegram_id=1")
    conn.execute("UPDATE player_crafting_professions SET level=6 WHERE player_id=1 AND profession_key='blacksmith'")
    conn.execute('UPDATE player_gathering_professions SET level=6 WHERE telegram_id=1 AND profession_key=?',(profession,))
    recipe_id = f'pxe_tool_{profession}_2'
    conn.execute("INSERT INTO player_recipe_knowledge(player_id,recipe_id,catalog_version,acquired_via) VALUES (?,?,2,'guild')",(1,recipe_id))
    conn.execute("INSERT OR IGNORE INTO player_location_discovery(telegram_id,location_id) VALUES (1,'westwild_n6')")
    for item,quantity in {'wood_common':36,'iron_ore':8,'coal':2}.items():
        conn.execute('INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,?,?)',(item,quantity))
    conn.commit()
    payload = recipe_intent_payload(recipe_id,tool_revision=1,commission=True,replacement_confirmed=True)
    token = issue_actions(1,'craft',[payload])[payload]
    result = craft_tool(1,recipe_id,action_token=token)
    assert result['status']=='crafted' and result['gold_delta']==-80
    tool = get_tool(conn,1,profession)
    assert (tool['tier'],tool['durability'],tool['bootstrap_used_mask'])==(2,120,1)
    assert conn.execute("SELECT COALESCE(SUM(quantity),0) FROM inventory WHERE telegram_id=1 AND item_id='wood_dark'").fetchone()[0]==0
    assert craft_tool(1,recipe_id,action_token=token)['recovered']
    assert conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0]==920
    conn.execute('BEGIN IMMEDIATE')
    install_tool(conn,1,profession,3,expected_revision=tool['revision'],now_ms=1000)
    conn.commit()
    assert get_tool(conn,1,profession)['bootstrap_used_mask']==1
    conn.close()


def prepare(tier=2,durability=0,materials=None):
    conn = database.get_connection()
    conn.execute('BEGIN IMMEDIATE')
    grant_player_pxe1_starters(conn,1,now_ms=0,acquired_via='starter')
    conn.execute("UPDATE players SET location_id='hub_westwild',gold=1000 WHERE telegram_id=1")
    conn.execute("UPDATE player_profession_tools SET tier=?,durability=? WHERE player_id=1 AND profession_key='mining'", (tier,durability))
    for item,quantity in (materials or {}).items():
        conn.execute('INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,?,?)', (item,quantity))
    conn.commit()
    return conn


def test_all_twenty_tool_costs_and_no_item_variant():
    recipes = [r for r in ACTIVE_RECIPES if r.output_spec.kind=='tool']
    assert len(recipes)==20
    for recipe in recipes:
        tier = recipe.output_spec.tool_tier
        assert recipe.material_value=={1:28,2:112,3:315,4:778}[tier]
        assert recipe.output_spec.item_id is None
        assert dict(recipe.requirements)['wood_common']==4*3**(tier-1)


@pytest.mark.parametrize('tier,durability,materials,expected',[
    (2,0,{},96),(4,0,{},384),
    (2,24,{'wood_common':2,'iron_ore':1,'coal':1},46),
    (2,24,{'wood_common':4,'iron_ore':2,'coal':1},10),
])
def test_exact_repair_quote_commit_and_replay(tier,durability,materials,expected):
    conn = prepare(tier,durability,materials)
    quote = repair_quote(conn,1,'mining')
    assert quote['gold']==expected
    conn.close()
    payload = json.dumps(quote,sort_keys=True,separators=(',',':'))
    token = issue_actions(1,'tool_repair_pxe1',[payload])[payload]
    result = commit_tool_maintenance(1,action_token=token)
    assert result['gold_after']==1000-expected
    assert result['granted']==[] and result['progression']==[]
    assert commit_tool_maintenance(1,action_token=token)['recovered']
    conn = database.get_connection()
    assert get_tool(conn,1,'mining')['durability']==60*tier
    assert not conn.execute('SELECT 1 FROM inventory WHERE telegram_id=1').fetchone()
    conn.close()


def test_no_downgrade_mask_survives_and_exact_slot_craft():
    conn = prepare(1,0,{'wood_common':4,'iron_ore':2,'coal':1})
    conn.execute("UPDATE player_profession_tools SET bootstrap_used_mask=3 WHERE player_id=1 AND profession_key='mining'")
    conn.commit()
    revision = get_tool(conn,1,'mining')['revision']
    conn.close()
    payload = recipe_intent_payload('pxe_tool_mining_1',tool_revision=revision,replacement_confirmed=True)
    token = issue_actions(1,'craft',[payload])[payload]
    result = craft_tool(1,'pxe_tool_mining_1',action_token=token)
    assert result['status']=='crafted'
    assert result['granted']==[{'kind':'tool','profession_key':'mining','tool_tier':1,'quantity':1}]
    assert result['progression'][0]['xp_awarded']==15
    assert craft_tool(1,'pxe_tool_mining_1',action_token=token)['recovered']
    conn = database.get_connection()
    assert get_tool(conn,1,'mining')['bootstrap_used_mask']==3
    assert not conn.execute('SELECT 1 FROM inventory WHERE telegram_id=1').fetchone()
    conn.close()


def test_t1_no_repair_and_ordinary_integer_formula():
    with pytest.raises(ValueError,match='tool_t1_no_repair'):
        repair_costs(1,0)
    assert repair_costs(2,24)=={'materials':{'wood_common':4,'iron_ore':2,'coal':1},'gold':10,'restored':96}
    assert repair_costs(4,240)['gold']==0
