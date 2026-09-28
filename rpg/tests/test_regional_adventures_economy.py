from game.crafting_runtime import LIVE_RECIPE_IDS, get_recipe
from game.items_data import ITEMS, get_item
from game.regional_catalog import STANDING_DELIVERIES


def _raw_sale_value(recipe, submitted_quantity):
    raw_batch = sum(
        get_item(req.item_id)['sell_price'] * req.quantity
        for req in recipe.material_requirements + recipe.special_ingredient_requirements
    )
    return raw_batch * submitted_quantity // recipe.output_quantity


def test_standing_payouts_do_not_exceed_submitted_or_raw_value():
    recipes_by_output = {}
    for recipe_id in LIVE_RECIPE_IDS:
        recipe = get_recipe(recipe_id)
        recipes_by_output.setdefault(recipe.output_item_id, []).append(recipe)
    for job in STANDING_DELIVERIES:
        submitted = sum(get_item(item_id)['sell_price'] * quantity for item_id, quantity in job.cost_items)
        raw = 0
        for item_id, quantity in job.cost_items:
            recipes = recipes_by_output.get(item_id, [])
            raw += min((_raw_sale_value(recipe, quantity) for recipe in recipes), default=get_item(item_id)['sell_price'] * quantity)
        assert job.reward.gold <= submitted <= raw


def test_no_vendor_or_alternate_recipe_creates_repeat_arbitrage():
    accepted = {item_id for job in STANDING_DELIVERIES for item_id, _quantity in job.cost_items}
    assert all(get_item(item_id)['buy_price'] == 0 for item_id in accepted)
    outputs={}
    for recipe_id in LIVE_RECIPE_IDS:
        recipe=get_recipe(recipe_id); outputs.setdefault(recipe.output_item_id,[]).append(recipe.recipe_id)
    for item_id in accepted:
        assert len(outputs.get(item_id, [])) <= 1
