import json
from concurrent.futures import ThreadPoolExecutor

import database
from game.action_receipts import issue_actions
from game.crafting_runtime import craft_recipe
from game.economy_actions import gift_inventory_item, rest_at_inn
from game.gathering_runtime import gather_resource
from game.gear_progression import exchange_enhancement_crystal, issue_crystal_exchange_intent
from game.seed import seed_items
from game.profession_recipes import recipe_intent_payload
from game.recipe_knowledge import learn_recipe
from handlers.inventory import try_sell_inventory_item, use_inventory_consumable


class FixedRng:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


def _new_player(tmp_path, monkeypatch, player_id=30, location='old_mine_entrance'):
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / f'{player_id}.db'))
    database.init_db(); seed_items()
    database.create_player(player_id, f'p{player_id}', 'Gatherer',
                           dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'), 2), lang='en')
    conn = database.get_connection()
    conn.execute('UPDATE players SET location_id=? WHERE telegram_id=?', (location, player_id))
    conn.commit(); conn.close()
    return player_id


def test_craft_replay_after_new_preview_returns_exact_receipt_without_second_grant(tmp_path, monkeypatch):
    monkeypatch.setattr(database,'DB_PATH',str(tmp_path/'game.db')); database.init_db(); seed_items()
    database.create_player(3,'crafter','Crafter',dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'),2),lang='en')
    conn=database.get_connection(); conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (3,'herb_common',3)"); conn.commit(); conn.close()
    payload=recipe_intent_payload('field_tonic')
    token=issue_actions(3,'craft',[payload])[payload]
    first=craft_recipe(3,'',action_token=token)
    replacement_payload=recipe_intent_payload('field_mana')
    replacement_token=issue_actions(3,'craft',[replacement_payload])[replacement_payload]
    assert replacement_token != token
    second=craft_recipe(3,'',action_token=token)
    assert first.status == second.status == 'crafted' and second.recovered
    conn=database.get_connection()
    assert conn.execute("SELECT quantity FROM inventory WHERE telegram_id=3 AND item_id='health_potion_small'").fetchone()['quantity'] == 1
    assert conn.execute("SELECT COUNT(*) c FROM economy_action_receipts WHERE player_id=3").fetchone()['c'] == 1
    conn.close()


def test_catalogue_one_craft_replay_preserves_original_large_xp_after_cutover(tmp_path,monkeypatch):
    from game.economy_actions import intent_hash,store_receipt
    player_id=_new_player(tmp_path,monkeypatch,location='capital_city')
    conn=database.get_connection()
    receipt={'schema_version':1,'catalog_version':1,'action_kind':'craft','status':'crafted',
             'player_id':player_id,'location_id':'capital_city','recipe_id':'field_tonic',
             'consumed':[{'item_id':'herb_common','quantity':3}],
             'granted':[{'item_id':'health_potion_small','quantity':1,'instance_ids':[]}],
             'progression':[{'profession_key':'alchemy','xp_awarded':250}],
             'gold_delta':0,'gold_after':0,'details':{}}
    token='historical_consumed'
    store_receipt(conn,player_id,'ui:'+token,'craft',intent_hash('craft',player_id,{'recipe_id':'field_tonic'}),receipt,catalog_version=1)
    conn.execute("UPDATE players SET location_id='frostspine_n6',travel_revision=8,in_battle=1 WHERE telegram_id=?",(player_id,))
    conn.commit()
    tables=('players','inventory','player_crafting_professions','player_profession_tools','economy_action_receipts')
    before={table:[tuple(r) for r in conn.execute(f'SELECT * FROM {table}')] for table in tables}
    result=craft_recipe(player_id,'field_tonic',action_token=token)
    assert result.status=='crafted' and result.recovered and result.profession_xp==250
    assert result.crafted_item_id=='health_potion_small' and result.crafted_quantity==1
    assert before=={table:[tuple(r) for r in conn.execute(f'SELECT * FROM {table}')] for table in tables}
    assert json.loads(conn.execute('SELECT result_json FROM economy_action_receipts WHERE request_id=?',('ui:'+token,)).fetchone()[0])==receipt
    conn.close()


def _historical_gather(conn,player_id,request_id,status):
    """Fixture of a committed catalogue-1 result, not a fresh resource grant."""
    from game.economy_actions import store_receipt
    result={'schema_version':1,'catalog_version':1,'action_kind':'gather','status':status,
            'player_id':player_id,'location_id':'old_mine_entrance','consumed':[],
            'granted':[{'item_id':'iron_ore','quantity':1,'instance_ids':[],'gear_specs':[]}] if status=='gathered' else [],
            'progression':[{'profession_key':'mining','xp_awarded':10}] if status=='gathered' else [],
            'source':{'item_id':'gem_common'} if status=='denied' else {},
            'details':{'required_level':12} if status=='denied' else {},
            'gold_delta':0,'gold_after':0}
    store_receipt(conn,player_id,request_id,'gather','historical',result,catalog_version=1)
    return result


def test_gather_receipts_recover_success_empty_locked_and_legacy(tmp_path, monkeypatch):
    player_id=_new_player(tmp_path,monkeypatch)
    conn=database.get_connection()
    expected={status:_historical_gather(conn,player_id,'historical:'+status,status)
              for status in ('gathered','empty','denied')}
    conn.execute("INSERT INTO player_action_receipts(player_id,request_id) VALUES (?,'gather:30:legacy')",(player_id,))
    conn.execute("UPDATE players SET location_id='capital_city',travel_revision=99,in_battle=1 WHERE telegram_id=?",(player_id,))
    conn.commit()
    tables=('players','inventory','player_profession_tools','player_gathering_professions','economy_action_receipts')
    before={table:[tuple(r) for r in conn.execute(f'SELECT * FROM {table}')] for table in tables}
    for status,result in expected.items():
        replay=gather_resource(player_id,'mining',location_id='old_mine_entrance',
                               travel_revision=0,request_id='historical:'+status,rng=FixedRng(0.99))
        assert {k:v for k,v in replay.items() if k not in {'recovered','item_id'}}==result
        assert replay['recovered']
        if status=='gathered': assert replay['item_id']=='iron_ore'
        if status=='denied': assert replay['details']['required_level']==12
    assert gather_resource(player_id,'mining',location_id='frostspine_n6',request_id='gather:30:legacy')=={
        'status':'historical_receipt_unavailable','recovered':True}
    assert before=={table:[tuple(r) for r in conn.execute(f'SELECT * FROM {table}')] for table in tables}
    conn.close()


def test_gather_replay_precedes_travel_and_battle_rejection_without_duplication(tmp_path, monkeypatch):
    player_id=_new_player(tmp_path,monkeypatch,player_id=31)
    first=gather_resource(player_id,'mining',location_id='old_mine_entrance',
                          travel_revision=0,request_id='gather:31:1',rng=FixedRng(0.0))
    assert first['status']=='running'
    conn=database.get_connection()
    assert not conn.execute('SELECT 1 FROM inventory WHERE telegram_id=?',(player_id,)).fetchone()
    profession=tuple(conn.execute("SELECT level,exp FROM player_gathering_professions WHERE telegram_id=? AND profession_key='mining'",(player_id,)).fetchone())
    tool=tuple(conn.execute("SELECT * FROM player_profession_tools WHERE player_id=? AND profession_key='mining'",(player_id,)).fetchone())
    conn.execute("UPDATE players SET location_id='capital_city',travel_revision=1,in_battle=1 WHERE telegram_id=?",(player_id,))
    conn.commit()
    replay=gather_resource(player_id,'mining',location_id='old_mine_entrance',
                           travel_revision=0,request_id='gather:31:1',rng=FixedRng(0.99))
    assert replay['status']=='running' and replay['recovered']
    assert replay['session']==first['session']
    assert not conn.execute('SELECT 1 FROM inventory WHERE telegram_id=?',(player_id,)).fetchone()
    assert profession==tuple(conn.execute("SELECT level,exp FROM player_gathering_professions WHERE telegram_id=? AND profession_key='mining'",(player_id,)).fetchone())
    assert tool==tuple(conn.execute("SELECT * FROM player_profession_tools WHERE player_id=? AND profession_key='mining'",(player_id,)).fetchone())
    assert conn.execute('SELECT COUNT(*) FROM player_gathering_sessions WHERE player_id=?',(player_id,)).fetchone()[0]==1
    assert not conn.execute('SELECT 1 FROM economy_action_receipts WHERE player_id=?',(player_id,)).fetchone()
    conn.close()


def test_fresh_gather_rejects_stale_travel_revision_without_receipt(tmp_path, monkeypatch):
    player_id = _new_player(tmp_path, monkeypatch, player_id=32)
    conn = database.get_connection()
    conn.execute("UPDATE players SET location_id='capital_city',travel_revision=1 WHERE telegram_id=?", (player_id,))
    conn.commit(); conn.close()
    result = gather_resource(player_id, 'mining', location_id='old_mine_entrance',
                             travel_revision=0, request_id='gather:32:1', rng=FixedRng(0.0))
    assert result['status'] == 'stale_action'
    conn = database.get_connection()
    assert conn.execute("SELECT COUNT(*) c FROM economy_action_receipts WHERE player_id=?", (player_id,)).fetchone()['c'] == 0
    conn.close()


def test_valid_consumed_business_rejections_are_durable_and_foreign_tokens_are_not(tmp_path, monkeypatch):
    player_id = _new_player(tmp_path, monkeypatch, player_id=33, location='capital_city')
    database.create_player(34, 'foreign', 'Foreign',
        dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'), 2), lang='en')

    craft_payload = recipe_intent_payload('field_tonic')
    craft_token = issue_actions(player_id, 'craft', [craft_payload])[craft_payload]
    assert craft_recipe(34, '', action_token=craft_token).status == 'stale_action'
    assert craft_recipe(player_id, '', action_token=craft_token).status == 'missing_materials'
    assert craft_recipe(player_id, '', action_token=craft_token).recovered

    conn = database.get_connection()
    conn.execute("UPDATE player_crafting_professions SET level=6 WHERE player_id=? AND profession_key='alchemy'", (player_id,))
    conn.execute('UPDATE players SET gold=0 WHERE telegram_id=?', (player_id,))
    conn.commit(); conn.close()
    learn_payload = recipe_intent_payload('pe_alchemy_health_06')
    learn_token = issue_actions(player_id, 'learn', [learn_payload])[learn_payload]
    assert learn_recipe(player_id, 'pe_alchemy_health_06', action_token=learn_token)['status'] == 'insufficient_gold'
    assert learn_recipe(player_id, 'pe_alchemy_health_06', action_token=learn_token)['status'] == 'insufficient_gold'

    conn = database.get_connection()
    assert conn.execute("SELECT COUNT(*) c FROM economy_action_receipts WHERE player_id=34").fetchone()['c'] == 0
    assert conn.execute("SELECT COUNT(*) c FROM economy_action_receipts WHERE player_id=?", (player_id,)).fetchone()['c'] == 2
    conn.close()


def test_exchange_sale_use_inn_and_self_gift_rejections_commit_zero_mutation_receipts(tmp_path, monkeypatch):
    player_id = _new_player(tmp_path, monkeypatch, player_id=35, location='capital_city')
    conn = database.get_connection()
    conn.execute("INSERT INTO player_contract_history(player_id,contract_key) VALUES (?, 'chapter_homecoming')", (player_id,))
    conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (?,'herb_common',2)", (player_id,))
    conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (?,'health_potion_small',1)", (player_id,))
    rows = conn.execute('SELECT * FROM inventory WHERE telegram_id=? ORDER BY id', (player_id,)).fetchall()
    material, potion = rows[0], rows[1]
    conn.commit(); conn.close()

    exchange_token = issue_crystal_exchange_intent(player_id)
    assert exchange_enhancement_crystal(player_id, exchange_token)['status'] == 'no_material'
    assert exchange_enhancement_crystal(player_id, exchange_token)['recovered'] is True

    sale_payload = f"{material['id']}:{material['quantity']}"
    use_payload = f"{potion['id']}:{potion['quantity']}"
    sale_token = issue_actions(player_id, 'sell', [sale_payload])[sale_payload]
    use_token = issue_actions(player_id, 'use', [use_payload])[use_payload]
    inn_token = issue_actions(player_id, 'inn', ['rest:12'])['rest:12']
    gift_payload = json.dumps({'recipient_id': player_id, 'inventory_id': material['id'],
        'item_id': material['item_id'], 'quantity': material['quantity'],
        'enhance_level': material['enhance_level'], 'durability': material['durability']},
        sort_keys=True, separators=(',', ':'))
    gift_token = issue_actions(player_id, 'gift', [gift_payload])[gift_payload]

    conn = database.get_connection()
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=?', (player_id,))
    conn.commit(); conn.close()
    assert try_sell_inventory_item(player_id, sale_token)['status'] == 'in_battle'
    assert use_inventory_consumable(player_id, use_token)['status'] == 'in_battle'
    conn = database.get_connection(); conn.execute('UPDATE players SET in_battle=0, gold=0, hp=1 WHERE telegram_id=?', (player_id,)); conn.commit(); conn.close()
    assert rest_at_inn(player_id, inn_token)['status'] == 'inn_no_gold'
    assert gift_inventory_item(player_id, gift_token)['status'] == 'self_gift'

    conn = database.get_connection()
    assert conn.execute("SELECT quantity FROM inventory WHERE id=?", (material['id'],)).fetchone()['quantity'] == 2
    assert conn.execute("SELECT quantity FROM inventory WHERE id=?", (potion['id'],)).fetchone()['quantity'] == 1
    rejected = conn.execute("SELECT COUNT(*) c FROM economy_action_receipts WHERE player_id=? AND json_extract(result_json,'$.status')!='exchanged'", (player_id,)).fetchone()['c']
    assert rejected == 5
    conn.close()


def test_concurrent_craft_sale_and_gift_conserve_one_shared_stack(tmp_path, monkeypatch):
    player_id = _new_player(tmp_path, monkeypatch, player_id=36, location='capital_city')
    database.create_player(37, 'recipient', 'Recipient',
        dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'), 2), lang='en')
    conn = database.get_connection()
    conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (?,'herb_common',3)", (player_id,))
    row = conn.execute("SELECT * FROM inventory WHERE telegram_id=? AND item_id='herb_common'", (player_id,)).fetchone()
    gold_before = conn.execute('SELECT gold FROM players WHERE telegram_id=?', (player_id,)).fetchone()['gold']
    conn.commit(); conn.close()

    craft_payload = recipe_intent_payload('field_tonic')
    craft_token = issue_actions(player_id, 'craft', [craft_payload])[craft_payload]
    sale_payload = f"{row['id']}:3"
    sale_token = issue_actions(player_id, 'sell', [sale_payload])[sale_payload]
    gift_payload = json.dumps({'recipient_id':37,'inventory_id':row['id'],'item_id':'herb_common',
        'quantity':3,'enhance_level':row['enhance_level'],'durability':row['durability']},
        sort_keys=True, separators=(',', ':'))
    gift_token = issue_actions(player_id, 'gift', [gift_payload])[gift_payload]

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(lambda: craft_recipe(player_id, '', action_token=craft_token).status),
            pool.submit(lambda: try_sell_inventory_item(player_id, sale_token)['status']),
            pool.submit(lambda: gift_inventory_item(player_id, gift_token)['status']),
        ]
        statuses = [future.result() for future in futures]
    assert sum(status in {'crafted', 'sold', 'gifted'} for status in statuses) == 1

    conn = database.get_connection()
    sender_herbs = conn.execute("SELECT COALESCE(SUM(quantity),0) q FROM inventory WHERE telegram_id=? AND item_id='herb_common'", (player_id,)).fetchone()['q']
    recipient_herbs = conn.execute("SELECT COALESCE(SUM(quantity),0) q FROM inventory WHERE telegram_id=37 AND item_id='herb_common'").fetchone()['q']
    tonics = conn.execute("SELECT COALESCE(SUM(quantity),0) q FROM inventory WHERE telegram_id=? AND item_id='health_potion_small'", (player_id,)).fetchone()['q']
    gold_after = conn.execute('SELECT gold FROM players WHERE telegram_id=?', (player_id,)).fetchone()['gold']
    conn.close()
    outcomes = {
        'crafted': (sender_herbs, recipient_herbs, tonics, gold_after - gold_before),
        'sold': (sender_herbs, recipient_herbs, tonics, gold_after - gold_before),
        'gifted': (sender_herbs, recipient_herbs, tonics, gold_after - gold_before),
    }
    winner = next(status for status in statuses if status in outcomes)
    assert outcomes[winner] == {
        'crafted': (0, 0, 1, 0),
        'sold': (2, 0, 0, 3),
        'gifted': (2, 1, 0, 0),
    }[winner]
