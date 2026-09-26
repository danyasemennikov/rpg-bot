from game.items_data import get_item
from game.profession_recipes import ACTIVE_RECIPES


def test_all_conversion_edges_are_strictly_negative_for_npc_resale():
    assert all(get_item(r.output_spec.item_id)['sell_price'] < sum(get_item(i)['sell_price']*q for i,q in r.requirements) for r in ACTIVE_RECIPES)
