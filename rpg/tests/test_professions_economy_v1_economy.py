from game.items_data import get_item
from game.profession_recipes import ACTIVE_RECIPES


def test_all_conversion_edges_are_strictly_negative_for_npc_resale():
    for recipe in ACTIVE_RECIPES:
        input_value = sum(get_item(item_id)['sell_price'] * quantity for item_id, quantity in recipe.requirements)
        output = recipe.output_spec
        if output.kind == 'tool':
            # Dedicated profession slots have no inventory item or NPC resale.
            assert output.item_id is None
            resale_value = 0
        else:
            resale_value = get_item(output.item_id)['sell_price']
        assert resale_value < input_value, recipe.recipe_id
