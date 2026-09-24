import database
from game.action_receipts import issue_actions
from game.crafting_runtime import craft_recipe
from game.seed import seed_items
from game.profession_recipes import recipe_intent_payload


def test_craft_replay_returns_exact_receipt_without_second_grant(tmp_path, monkeypatch):
    monkeypatch.setattr(database,'DB_PATH',str(tmp_path/'game.db')); database.init_db(); seed_items()
    database.create_player(3,'crafter','Crafter',dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'),2),lang='en')
    conn=database.get_connection(); conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (3,'herb_common',3)"); conn.commit(); conn.close()
    payload=recipe_intent_payload('field_tonic')
    token=issue_actions(3,'craft',[payload])[payload]
    first=craft_recipe(3,'',action_token=token); second=craft_recipe(3,'',action_token=token)
    assert first.status == second.status == 'crafted' and second.recovered
    conn=database.get_connection()
    assert conn.execute("SELECT quantity FROM inventory WHERE telegram_id=3 AND item_id='health_potion_small'").fetchone()['quantity'] == 1
    assert conn.execute("SELECT COUNT(*) c FROM economy_action_receipts WHERE player_id=3").fetchone()['c'] == 1
    conn.close()
