from game.crafting_runtime import LIVE_RECIPE_IDS, get_recipe
from game.items_data import ITEMS, get_item
from game.regional_catalog import STANDING_DELIVERIES


def _raw_sale_value(recipe_id):
    recipe=get_recipe(recipe_id)
    return sum(get_item(req.item_id)['sell_price']*req.quantity for req in recipe.material_requirements+recipe.special_ingredient_requirements)


def test_standing_payouts_do_not_exceed_submitted_or_raw_value():
    expected={'ww_ration_order':(10,10,16),'fs_forge_supplies':(20,20,20),'mv_stew_order':(12,12,32)}
    for job in STANDING_DELIVERIES:
        payout,submitted,raw=expected[job.content_id]
        assert job.reward.gold == payout <= submitted <= raw


def test_no_vendor_or_alternate_recipe_creates_repeat_arbitrage():
    accepted={'field_ration','iron_ore','coal','pe_marsh_stew'}
    assert all(get_item(item_id)['buy_price']==0 for item_id in accepted)
    outputs={}
    for recipe_id in LIVE_RECIPE_IDS:
        recipe=get_recipe(recipe_id); outputs.setdefault(recipe.output_item_id,[]).append(recipe.recipe_id)
    assert outputs['field_ration']==['trail_ration']
    assert outputs['pe_marsh_stew']==['pe_cooking_marsh_06']
    assert 'iron_ore' not in outputs and 'coal' not in outputs
    assert _raw_sale_value('trail_ration')==8
    assert _raw_sale_value('pe_cooking_marsh_06')==16
