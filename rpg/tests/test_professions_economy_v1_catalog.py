from collections import Counter

from game.items_data import get_item
from game.profession_recipes import ACTIVE_RECIPES, INACTIVE_RECIPE_IDS, STARTER_RECIPE_IDS
from game.profession_resources import MANDATORY_RESOURCE_IDS, NEW_MATERIAL_IDS, RESOURCES


def test_closed_catalog_counts_and_bands():
    assert len(ACTIVE_RECIPES) == 83
    assert len({r.recipe_id for r in ACTIVE_RECIPES}) == 83
    assert Counter(r.required_level for r in ACTIVE_RECIPES) == {1: 21, 2: 1, 6: 13, 12: 24, 18: 24}
    assert len(STARTER_RECIPE_IDS) == 22
    assert len(INACTIVE_RECIPE_IDS) == 4
    assert not set(INACTIVE_RECIPE_IDS) & {r.recipe_id for r in ACTIVE_RECIPES}


def test_resource_and_output_contract():
    assert len(MANDATORY_RESOURCE_IDS) == 28
    assert len(NEW_MATERIAL_IDS) == 5
    assert all(get_item(item_id)['sell_price'] == RESOURCES[item_id].sell_price for item_id in MANDATORY_RESOURCE_IDS)
    assert all(get_item(r.output_spec.item_id) for r in ACTIVE_RECIPES if r.output_spec.kind!='tool')
    assert all(r.output_spec.item_id is None for r in ACTIVE_RECIPES if r.output_spec.kind=='tool')
    assert sum(r.learning_gold for r in ACTIVE_RECIPES) == 5725
    assert len([r for r in ACTIVE_RECIPES if r.learning_gold]) == 61


def test_every_recipe_loses_value_when_sold():
    for recipe in ACTIVE_RECIPES:
        raw = sum(get_item(item_id)['sell_price'] * quantity for item_id, quantity in recipe.requirements)
        if recipe.output_spec.kind=='tool':
            assert recipe.output_spec.item_id is None  # Dedicated slots cannot be sold.
            continue
        assert get_item(recipe.output_spec.item_id)['sell_price'] < raw, recipe.recipe_id


def test_recovery_outputs_reuse_potion_runtime():
    new_ids = {'pe_mana_potion_medium','pe_health_potion_large','pe_mana_potion_large',
               'pe_shore_broth','pe_marsh_stew','pe_boar_feast','pe_oasis_meal','pe_deep_marsh_meal'}
    assert all(get_item(item_id)['item_type'] == 'potion' for item_id in new_ids)
    assert all(get_item(item_id).get('consumable_family') == 'food' for item_id in new_ids if 'meal' in item_id or 'broth' in item_id or 'stew' in item_id or 'feast' in item_id)
