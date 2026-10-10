import pytest

from game.profession_progression import apply_profession_xp, crafting_xp_for_success, xp_to_level
from game.profession_recipes import get_recipe


def repeat(recipe_id, target):
    recipe = get_recipe(recipe_id)
    level,exp,count = 1,0,0
    while level<target:
        xp = crafting_xp_for_success(current_level=level,current_exp=exp,
            recipe_level=recipe.required_level,material_value=recipe.material_value)
        assert xp>0
        result = apply_profession_xp(level,exp,xp)
        level,exp = result.new_level,result.new_exp
        count += 1
    return count,(level,exp)


@pytest.mark.parametrize('recipe,counts',[
    ('trail_vest',(4,49,85)),('field_tonic',(6,83,145)),('trail_ration',(7,87,150)),
    ('pxe_tool_mining_1',(4,49,85)),
])
def test_exact_frozen_production_counts(recipe,counts):
    assert tuple(repeat(recipe,target)[0] for target in (2,5,6)) == counts


def test_medium_armor_route_136_crafts():
    _,state = repeat('trail_vest',6)
    assert state==(6,0)
    recipe = get_recipe('pe_medium_helmet_06')
    for _ in range(51):
        xp = crafting_xp_for_success(current_level=state[0],current_exp=state[1],
            recipe_level=6,material_value=recipe.material_value)
        result = apply_profession_xp(*state,xp)
        state = result.new_level,result.new_exp
    assert state==(10,1)


@pytest.mark.parametrize('gap,expected',[(0,15),(2,15),(3,7),(4,7)])
def test_relevance(gap,expected):
    assert crafting_xp_for_success(current_level=1+gap,current_exp=0,recipe_level=1,material_value=22)==expected


def test_clip_and_zero_preserves_historical_exp():
    assert crafting_xp_for_success(current_level=5,current_exp=248,recipe_level=1,material_value=22)==2
    assert crafting_xp_for_success(current_level=6,current_exp=20001,recipe_level=1,material_value=22)==0
    assert apply_profession_xp(6,20001,0).new_exp==20001
    assert xp_to_level(1,0,20)==9500
