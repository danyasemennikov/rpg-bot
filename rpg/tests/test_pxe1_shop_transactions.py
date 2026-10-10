import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from database import get_connection,get_player
from game.action_receipts import ActionRejected,issue_actions
from game.build_progression import migrate_character_builds_v1
from game.gear_instances import grant_item_to_player
from game.gear_progression import apply_gear_intent,issue_gear_intent
from game.items_data import get_item
from game.player_ui import validate_surface
from game.sale_policy import sale_quote,sale_payload
from handlers.inventory import try_sell_inventory_item
from handlers.location import try_buy_curated_shop_item,CURATED_EQUIPMENT_VENDOR_STOCK
from handlers.shop_views import buy_list,buy_preview,sale_preview,sell_categories,sell_list,handle_shop_buttons,issue_sale


def seed(item_id='wood_common',quantity=10):
    migrate_character_builds_v1()
    from game.quest_board import _ensure_player_hunt_contract_table
    _ensure_player_hunt_contract_table()
    conn = get_connection()
    conn.execute("UPDATE players SET gold=10000,level=20,location_id='capital_city' WHERE telegram_id=1")
    result = grant_item_to_player(1,item_id,quantity=quantity,source='test',source_level=1,conn=conn)
    conn.commit()
    row = conn.execute('SELECT id FROM inventory WHERE telegram_id=1 AND item_id=?',(item_id,)).fetchone()
    conn.close()
    return row[0] if row else result['instance_ids'][0]


def quote(entry_id,quantity=1,kind='i'):
    conn = get_connection()
    try: return sale_quote(conn,1,kind,entry_id,quantity)
    finally: conn.close()


def sale_token(entry_id,quantity=1,confirmed=False):
    payload = sale_payload(quote(entry_id,quantity),confirmed=confirmed)
    return issue_actions(1,'sell',[payload])[payload]


def query(data):
    return SimpleNamespace(from_user=SimpleNamespace(id=1),data=data,answer=AsyncMock(),edit_message_text=AsyncMock())


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_shop_lists_and_default_quantity_previews(lang):
    entry = seed()
    player = {**dict(get_player(1)),'lang':lang}
    for builder in (buy_list,sell_categories,sell_list):
        text,keyboard = builder(player)
        validate_surface(text,keyboard,list_view=builder!=sell_categories)
        assert '[pxe1.' not in text and 'wood_common' not in text
    text,keyboard = sale_preview(player,f'i{entry}')
    validate_surface(text,keyboard)
    commit = next(b.callback_data for row in keyboard.inline_keyboard for b in row if ':commit:' in b.callback_data)
    conn = get_connection()
    payload = json.loads(conn.execute('SELECT payload FROM player_ui_actions WHERE token=?',(commit.split(':')[-1],)).fetchone()[0])
    assert payload['quote']['quantity']==1
    conn.close()
    all_callback = next(b.callback_data for row in keyboard.inline_keyboard for b in row if ':saleview:' in b.callback_data and b.callback_data.endswith(':10'))
    q = query(all_callback)
    asyncio.run(handle_shop_buttons(SimpleNamespace(callback_query=q),SimpleNamespace()))
    conn = get_connection()
    assert conn.execute('SELECT quantity FROM inventory WHERE id=?',(entry,)).fetchone()[0]==10
    conn.close()
    for stock in CURATED_EQUIPMENT_VENDOR_STOCK['capital_city']:
        text,keyboard = buy_preview(player,stock['item_id'])
        validate_surface(text,keyboard)
        assert '[profession_' not in text and '[pxe1.' not in text


@pytest.mark.parametrize('total,confirmation',[(24,False),(25,True)])
def test_sale_threshold_exactly_24_and_25(total,confirmation,monkeypatch):
    entry = seed(quantity=30)
    monkeypatch.setitem(get_item('wood_common'),'sell_price',1)
    token = sale_token(entry,total)
    result = try_sell_inventory_item(1,token)
    assert result['status']==('confirmation_required' if confirmation else 'sold')
    if confirmation:
        assert get_player(1)['gold']==10000
        result = try_sell_inventory_item(1,sale_token(entry,total,confirmed=True))
        assert result['status']=='sold'
    assert get_player(1)['gold']==10000+total


def test_final_consumable_and_common_material_policy():
    entry = seed('health_potion_small',1)
    token = sale_token(entry)
    result = try_sell_inventory_item(1,token)
    assert result['status']=='confirmation_required'
    assert 'last_consumable' in result['quote']['risks']
    result = try_sell_inventory_item(1,sale_token(entry,confirmed=True))
    assert result['status']=='sold'
    material = seed('wood_common',1)
    assert quote(material)['risks']==[]
    assert try_sell_inventory_item(1,sale_token(material))['status']=='sold'


def test_new_unfinished_craft_obligation_rechecks_at_sale_and_completed_gather_does_not():
    entry = seed('wood_common',2)
    token = sale_token(entry)
    conn = get_connection()
    conn.execute("INSERT INTO player_hunt_contracts(player_id,contract_key,status) VALUES (1,'chapter_outfitter','active')")
    conn.commit();conn.close()
    result = try_sell_inventory_item(1,token)
    assert result['status']=='confirmation_required'
    assert result['quote']['assignment']=='chapter_outfitter'
    assert get_player(1)['gold']==10000
    conn = get_connection()
    conn.execute("UPDATE player_hunt_contracts SET contract_key='chapter_caravan' WHERE player_id=1")
    conn.execute("INSERT INTO player_contract_objectives(player_id,contract_key,objective_key,progress) VALUES (1,'chapter_caravan','gather:wood_common',3)")
    conn.commit();conn.close()
    assert 'quest_needed' not in quote(entry)['risks']


def test_confirmed_quote_cannot_sell_changed_quantity_and_legacy_replay_after_cleanup_move():
    entry = seed('health_potion_small',1)
    token = sale_token(entry,confirmed=True)
    conn = get_connection()
    conn.execute('UPDATE inventory SET quantity=2 WHERE id=?',(entry,));conn.commit();conn.close()
    assert try_sell_inventory_item(1,token)['status']=='stale_action'
    conn = get_connection()
    conn.execute('UPDATE inventory SET quantity=1 WHERE id=?',(entry,));conn.commit();conn.close()
    token = sale_token(entry,confirmed=True)
    first = try_sell_inventory_item(1,token)
    assert first['status']=='sold'
    conn = get_connection()
    conn.execute('DELETE FROM player_ui_actions WHERE player_id=1')
    conn.execute("UPDATE players SET location_id='westwild_n1',travel_revision=travel_revision+1,in_battle=1 WHERE telegram_id=1")
    conn.commit();conn.close()
    replay = try_sell_inventory_item(1,token)
    assert replay['recovered'] and replay['gold_after']==first['gold_after']
    assert not try_sell_inventory_item(777,token).get('recovered')


@pytest.mark.parametrize('rarity,enhance,copies,risky',[('common',0,2,False),('uncommon',0,2,True),('common',1,2,True),('common',0,1,True)])
def test_gear_selective_confirmation_and_replay(rarity,enhance,copies,risky):
    instance = seed('field_sword_1h',copies)
    conn = get_connection()
    conn.execute('UPDATE gear_instances SET rarity=?,enhance_level=? WHERE id=?',(rarity,enhance,instance))
    conn.commit();conn.close()
    token = issue_gear_intent(1,'sale',instance)
    result = apply_gear_intent(1,'sale',token)
    assert result['status']==('confirmation_required' if risky else 'sold')
    if risky:
        token = issue_sale(1,result['quote'],confirmed=True)
        result = apply_gear_intent(1,'sale',token)
        assert result['status']=='sold'
    conn = get_connection()
    conn.execute("UPDATE players SET location_id='westwild_n1',in_battle=1 WHERE telegram_id=1")
    conn.execute('DELETE FROM player_ui_actions WHERE player_id=1');conn.commit();conn.close()
    assert apply_gear_intent(1,'sale',token)['recovered']


def test_equipped_gear_and_nonsellable_are_blocked(monkeypatch):
    instance = seed('field_sword_1h',1)
    conn = get_connection()
    conn.execute("UPDATE gear_instances SET equipped_slot='weapon' WHERE id=?",(instance,));conn.commit();conn.close()
    with pytest.raises(ActionRejected,match='equipped_item'): quote(instance,kind='g')
    assert issue_gear_intent(1,'sale',instance) is None
    entry = seed()
    monkeypatch.setitem(get_item('wood_common'),'sell_price',0)
    with pytest.raises(ActionRejected,match='not_sellable'): quote(entry)


def test_stack_buy_exact_quantity_and_replay_after_move_cleanup():
    seed()
    item_id = next(r['item_id'] for r in CURATED_EQUIPMENT_VENDOR_STOCK['capital_city'] if get_item(r['item_id'])['item_type']=='potion')
    price = get_item(item_id)['buy_price']
    payload = json.dumps({'schema_version':1,'catalog_version':2,'item_id':item_id,'quantity':6,
                          'unit_price':price,'location_id':'capital_city'})
    token = issue_actions(1,'shop_buy',[payload])[payload]
    first = try_buy_curated_shop_item(1,'capital_city',20,item_id,action_token=token)
    assert first['ok'] and first['quantity']==6 and first['price']==price*6
    conn = get_connection()
    conn.execute("UPDATE players SET location_id='westwild_n1',travel_revision=1,in_battle=1 WHERE telegram_id=1")
    conn.execute('DELETE FROM player_ui_actions WHERE player_id=1');conn.commit();conn.close()
    replay = try_buy_curated_shop_item(1,'westwild_n1',1,item_id,action_token=token)
    assert replay['recovered'] and replay['gold_after']==first['gold_after']
    assert not try_buy_curated_shop_item(777,'capital_city',20,item_id,action_token=token)['ok']


@pytest.mark.parametrize('quantity',[0,100,True])
def test_buy_quantity_limits_and_gear_quantity_one(quantity):
    seed()
    item_id = CURATED_EQUIPMENT_VENDOR_STOCK['capital_city'][0]['item_id']
    payload = json.dumps({'schema_version':1,'catalog_version':2,'item_id':item_id,'quantity':quantity,
                          'unit_price':get_item(item_id)['buy_price'],'location_id':'capital_city'})
    token = issue_actions(1,'shop_buy',[payload])[payload]
    assert not try_buy_curated_shop_item(1,'capital_city',20,item_id,action_token=token)['ok']
    assert get_player(1)['gold']==10000
