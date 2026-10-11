"""Read current vendor obligations under the same writer as the sale owner."""

import json

from game.action_receipts import ActionRejected
from game.economy_actions import intent_hash
from game.field_catalog import is_field_item
from game.items_data import get_item

GEAR_TYPES = {'weapon', 'armor', 'accessory'}
EQUIPMENT_SLOTS = ('weapon','offhand','helmet','chest','legs','boots','gloves','ring1','ring2','amulet')


def owned_count(conn, player_id, item_id):
    stacks = conn.execute('SELECT COALESCE(SUM(quantity),0) FROM inventory WHERE telegram_id=? AND item_id=?',
                          (player_id,item_id)).fetchone()[0]
    instances = conn.execute('SELECT COUNT(*) FROM gear_instances WHERE telegram_id=? AND base_item_id=?',
                             (player_id,item_id)).fetchone()[0]
    return int(stacks)+int(instances)


def current_obligations(conn, player_id):
    """Only unfinished possession/craft obligations reserve saleable items."""
    from game.quest_board import _get_player_hunt_contract_state_with_conn
    from game.profession_recipes import ACTIVE_RECIPES
    state = _get_player_hunt_contract_state_with_conn(conn,player_id)
    if not state or state['status'] not in {'active','completed'}:
        return {},None
    reserved = {}
    for objective in state['contract'].objectives:
        remaining = max(0,objective.required-state.get('objective_progress',{}).get(objective.key,0))
        if not remaining:
            continue
        if objective.action in {'equip','delivery','deliver'}:
            reserved[objective.target] = max(reserved.get(objective.target,0),remaining)
        elif objective.action=='craft':
            # Craft credit requires actual production in the current owners. Owned
            # output does not satisfy that event, so its ingredients stay reserved.
            recipe = next((r for r in ACTIVE_RECIPES if r.output_spec.item_id==objective.target),None)
            if recipe:
                for item_id,quantity in recipe.requirements:
                    reserved[item_id] = reserved.get(item_id,0)+remaining*quantity
    return reserved,state['contract'].contract_key


def sale_quote(conn, player_id, entry_type, entry_id, quantity=1):
    if type(quantity) is not int or not 1<=quantity<=99 or entry_type not in {'i','g'}:
        raise ActionRejected('stale_action')
    player = conn.execute('SELECT location_id,travel_revision,gear_revision FROM players WHERE telegram_id=?',
                          (player_id,)).fetchone()
    if not player:
        raise ActionRejected('no_player')
    table,column = ('gear_instances','base_item_id') if entry_type=='g' else ('inventory','item_id')
    row = conn.execute(f'SELECT * FROM {table} WHERE id=? AND telegram_id=?',(entry_id,player_id)).fetchone()
    if not row:
        raise ActionRejected('stale_action')
    row = dict(row)
    item_id = row[column]
    item = get_item(item_id) or {}
    gear = item.get('item_type') in GEAR_TYPES
    count = 1 if entry_type=='g' else int(row['quantity'])
    if quantity>count or (gear and quantity!=1):
        raise ActionRejected('stale_action')
    equipped = row.get('equipped_slot')
    if entry_type=='i':
        equipment = conn.execute('SELECT * FROM equipment WHERE telegram_id=?',(player_id,)).fetchone()
        equipped = equipment and any(equipment[s]==entry_id for s in EQUIPMENT_SLOTS)
    if equipped:
        raise ActionRejected('equipped_item')
    unit_price = 5 if entry_type=='g' and is_field_item(item_id) else int(item.get('sell_price',0))
    if not item or unit_price<=0:
        raise ActionRejected('not_sellable')
    total_owned = owned_count(conn,player_id,item_id)
    reserved,assignment = current_obligations(conn,player_id)
    risks = []
    if gear:
        if row.get('rarity',item.get('rarity','common'))!='common' or int(row.get('enhance_level',0))>0:
            risks.append('valuable_item')
        if total_owned==quantity:
            risks.append('last_copy')
    elif item.get('item_type')=='potion' and total_owned==quantity:
        risks.append('last_consumable')
    if quantity*unit_price>=25:
        risks.append('large_total')
    if reserved.get(item_id,0)>0 and total_owned-quantity<reserved[item_id]:
        risks.append('quest_needed')
    relevant = {'row':row,'owned':total_owned,'reserved':reserved,'assignment':assignment,
                'player':dict(player)}
    return {'schema_version':1,'catalog_version':2,'entry_type':entry_type,'entry_id':int(entry_id),
            'item_id':item_id,'quantity':quantity,'stack_count':count,'remaining':count-quantity,
            'unit_price':unit_price,'total':unit_price*quantity,'risks':risks,
            'assignment':assignment if 'quest_needed' in risks else None,
            'location_id':player['location_id'],
            'state_hash':intent_hash('sale_state',player_id,relevant)}


def validate_sale_quote(conn, player_id, expected, *, confirmed=False):
    current = sale_quote(conn,player_id,expected['entry_type'],expected['entry_id'],expected['quantity'])
    if current['risks'] and (not confirmed or current!=expected):
        return {'status':'confirmation_required','quote':current}
    if current!=expected:
        raise ActionRejected('stale_action')
    return None


def sale_payload(quote, *, confirmed=False):
    return json.dumps({'schema_version':1,'catalog_version':2,'quote':quote,'confirmed':confirmed},
                      sort_keys=True,separators=(',',':'))
