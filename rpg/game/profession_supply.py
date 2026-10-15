"""NPC supply and tool commissions; never profession XP or exam proof."""
import json
import time
from game.action_receipts import ActionRejected, peaceful_player, require_item_delivery
from game.profession_resources import RESOURCES
from game.profession_recipes import get_recipe
from game.profession_tools import get_tool, install_tool
from game.profession_state import get_state
from game.economy_actions import intent_hash, find_exact_receipt, store_receipt


def buy_material(conn, player_id, item_id, quantity, *, request_id):
    if not conn.in_transaction:
        raise RuntimeError('supply requires writer transaction')
    if item_id not in RESOURCES or type(quantity) is not int or not 1 <= quantity <= 1000:
        raise ActionRejected('invalid_material_quantity')
    fingerprint=intent_hash('profession_supply',player_id,{'item_id':item_id,'quantity':quantity})
    prior=find_exact_receipt(conn,player_id,request_id,'profession_supply',fingerprint)
    if prior:
        return prior
    player=peaceful_player(conn,player_id,service='craftsmen_guild')
    cost=3*RESOURCES[item_id].sell_price*quantity
    if player['gold']<cost:
        raise ActionRejected('insufficient_gold')
    from game.gear_instances import grant_item_to_player
    conn.execute('UPDATE players SET gold=gold-? WHERE telegram_id=?',(cost,player_id))
    require_item_delivery(grant_item_to_player(player_id,item_id,quantity,source='profession_supply',conn=conn),quantity)
    result={'status':'purchased','item_id':item_id,'quantity':quantity,'gold_delta':-cost,'gold_after':player['gold']-cost}
    store_receipt(conn,player_id,request_id,'profession_supply',fingerprint,result,catalog_version=3)
    return result


def commission_quote(conn,player_id,recipe_id):
    recipe=get_recipe(recipe_id)
    if not recipe or recipe.output_spec.kind!='tool':
        raise ActionRejected('invalid_tool')
    output=recipe.output_spec
    state=get_state(conn,player_id,output.profession_key,registered=True)
    if state['tier'] < recipe.tier:
        raise ActionRejected('profession_level_too_low')
    old=get_tool(conn,player_id,output.profession_key)
    if old and old['tier']>output.tool_tier:
        raise ActionRejected('tool_no_downgrade')
    consumed,supplied={},{}
    for item,needed in recipe.requirements:
        owned=conn.execute('SELECT COALESCE(SUM(quantity),0) FROM inventory WHERE telegram_id=? AND item_id=?',
                           (player_id,item)).fetchone()[0]
        consumed[item]=min(owned,needed)
        supplied[item]=needed-consumed[item]
    return {'recipe_id':recipe_id,'profession_key':output.profession_key,'tool_tier':output.tool_tier,
            'tool_revision':old['revision'] if old else 0,'consumed':consumed,'supplied':supplied,
            'gold':5*output.tool_tier+sum(3*RESOURCES[i].sell_price*q for i,q in supplied.items())}


def execute_commission(conn,player_id,recipe_id,*,expected_revision,confirmed,request_id,expected_quote=None):
    if not conn.in_transaction:
        raise RuntimeError('commission requires writer transaction')
    fingerprint=intent_hash('profession_commission',player_id,{
        'recipe_id':recipe_id,'tool_revision':expected_revision,'quote':expected_quote,'confirmed':confirmed})
    receipt_id='commission:'+request_id
    prior=find_exact_receipt(conn,player_id,receipt_id,'profession_commission',fingerprint)
    if prior is not None:
        return prior
    player=peaceful_player(conn,player_id,service='craftsmen_guild')
    quote=commission_quote(conn,player_id,recipe_id)
    if confirmed is not True or quote['tool_revision']!=expected_revision or quote!=expected_quote:
        raise ActionRejected('tool_quote_changed')
    if player['gold']<quote['gold']:
        raise ActionRejected('insufficient_gold')
    from game.crafting_runtime import _consume_recipe_materials
    _consume_recipe_materials(conn,player_id,{'bulk':quote['consumed'],'special':{}})
    conn.execute('UPDATE players SET gold=gold-? WHERE telegram_id=?',(quote['gold'],player_id))
    tool=install_tool(conn,player_id,quote['profession_key'],quote['tool_tier'],
                      expected_revision=expected_revision,now_ms=int(time.time()*1000))
    result={'status':'crafted','recipe_id':recipe_id,'mode':'npc_commission','progression':[],
            'consumed':[{'item_id':i,'quantity':q} for i,q in quote['consumed'].items()],
            'granted':[{'kind':'tool','quantity':1,'tool':tool}],
            'gold_delta':-quote['gold'],'gold_after':player['gold']-quote['gold'],'quote':quote}
    store_receipt(conn,player_id,receipt_id,'profession_commission',fingerprint,result,catalog_version=3)
    return result
