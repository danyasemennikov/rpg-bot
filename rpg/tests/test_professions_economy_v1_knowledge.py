import database
from game.action_receipts import issue_actions
from game.profession_recipes import GRANDFATHERED_RECIPE_IDS, STARTER_RECIPE_IDS, recipe_intent_payload
from game.recipe_knowledge import known_recipe_ids, learn_recipe
from game.seed import seed_items


def test_new_and_existing_bootstrap_differ(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path/'game.db')); database.init_db(); seed_items()
    database.create_player(2,'new','New',dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'),2),lang='en')
    assert set(known_recipe_ids(2)) == set(STARTER_RECIPE_IDS)
    assert set(GRANDFATHERED_RECIPE_IDS) <= set(STARTER_RECIPE_IDS)


def test_valid_learning_rejection_is_consumed_receipted_and_recoverable():
    database.create_player(8,'learner','Learner',dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'),2),lang='en')
    conn=database.get_connection()
    conn.execute("UPDATE players SET gold=0, location_id='capital_city' WHERE telegram_id=8")
    conn.execute("UPDATE player_crafting_professions SET level=6 WHERE player_id=8 AND profession_key='blacksmith'")
    conn.commit(); conn.close()
    payload=recipe_intent_payload('pe_shield_06')
    token=issue_actions(8,'learn',[payload])[payload]
    first=learn_recipe(8,'pe_shield_06',action_token=token)
    second=learn_recipe(8,'pe_shield_06',action_token=token)
    assert first['status'] == second['status'] == 'insufficient_gold'
    conn=database.get_connection()
    assert conn.execute("SELECT COUNT(*) c FROM economy_action_receipts WHERE player_id=8 AND action_kind='learn'").fetchone()['c'] == 1
    assert conn.execute("SELECT used FROM player_ui_actions WHERE token=?",(token,)).fetchone()['used'] == 1
    conn.close()
