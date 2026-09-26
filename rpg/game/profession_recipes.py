"""Closed PEV1-1 catalog: exactly 63 active recipes and four inactive aliases."""

from __future__ import annotations

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class RecipeOutputSpec:
    kind: str
    item_id: str
    quantity: int = 1
    item_tier: int | None = None
    rarity: str = 'common'
    secondary_policy: str = 'not_applicable'


@dataclass(frozen=True)
class ProfessionRecipe:
    recipe_id: str
    profession_key: str
    required_level: int
    requirements: tuple[tuple[str, int], ...]
    output_spec: RecipeOutputSpec
    active: bool = True
    starter: bool = False
    learning_gold: int = 0
    training_ceiling: int = 6
    catalog_version: int = 1


def _band(level: int) -> tuple[int, str, str]:
    return {
        1: (1, 'common', 'none'),
        6: (5, 'common', 'none'),
        12: (5, 'uncommon', 'ordinary_one'),
        18: (10, 'uncommon', 'ordinary_one'),
    }[level]


def _price(level: int) -> int:
    return {1: 0, 2: 0, 6: 25, 12: 75, 18: 150}[level]


def _ceiling(level: int) -> int:
    return 6 if level <= 2 else {6: 12, 12: 18, 18: 20}[level]


def _gear(recipe_id: str, profession: str, level: int, requirements, output: str) -> ProfessionRecipe:
    tier, rarity, secondaries = _band(level)
    return ProfessionRecipe(
        recipe_id, profession, level, tuple(requirements),
        RecipeOutputSpec('gear', output, item_tier=tier, rarity=rarity, secondary_policy=secondaries),
        starter=level == 1, learning_gold=_price(level), training_ceiling=_ceiling(level),
    )


def _consumable(recipe_id: str, profession: str, level: int, requirements, output: str) -> ProfessionRecipe:
    return ProfessionRecipe(
        recipe_id, profession, level, tuple(requirements), RecipeOutputSpec('consumable', output),
        starter=level <= 2, learning_gold=_price(level), training_ceiling=_ceiling(level),
    )


WEAPON_INPUTS = {
    'sword_1h': {1: (('iron_ore', 3), ('coal', 1), ('wood_common', 1)), 12: (('iron_ore', 4), ('coal', 2), ('frostpine_wood', 2), ('wolf_fang', 1)), 18: (('sunscar_ore', 3), ('iron_ore', 3), ('coal', 3), ('ancient_bark', 1), ('troll_sinew', 1))},
    'sword_2h': {1: (('iron_ore', 4), ('coal', 2), ('wood_common', 1)), 12: (('iron_ore', 6), ('coal', 3), ('frostpine_wood', 2), ('wolf_fang', 1)), 18: (('sunscar_ore', 5), ('iron_ore', 4), ('coal', 4), ('ancient_bark', 1), ('troll_sinew', 1))},
    'axe_2h': {1: (('iron_ore', 4), ('coal', 2), ('wood_common', 1)), 12: (('iron_ore', 6), ('coal', 3), ('frostpine_wood', 2), ('wolf_fang', 1)), 18: (('sunscar_ore', 5), ('iron_ore', 4), ('coal', 4), ('ancient_bark', 1), ('troll_sinew', 1))},
    'daggers': {1: (('iron_ore', 3), ('coal', 1), ('wolf_pelt', 1)), 12: (('iron_ore', 4), ('coal', 2), ('bear_hide', 1), ('wolf_fang', 1)), 18: (('sunscar_ore', 3), ('iron_ore', 2), ('coal', 2), ('bear_hide', 1), ('troll_sinew', 1))},
    'bow': {1: (('wood_common', 4), ('reed_bundle', 2)), 12: (('frostpine_wood', 4), ('spider_silk', 2), ('gem_common', 1)), 18: (('ancient_bark', 3), ('frostpine_wood', 2), ('spider_silk', 3), ('troll_sinew', 1))},
    'magic_staff': {1: (('wood_common', 3), ('reed_bundle', 1), ('herb_common', 2)), 12: (('frostpine_wood', 3), ('spider_silk', 1), ('gem_common', 1), ('herb_magic', 1)), 18: (('ancient_bark', 2), ('gem_common', 2), ('spider_silk', 2), ('herb_magic', 2))},
    'wand': {1: (('wood_common', 2), ('reed_bundle', 1), ('herb_common', 2)), 12: (('frostpine_wood', 2), ('spider_silk', 1), ('gem_common', 1), ('herb_magic', 1)), 18: (('ancient_bark', 1), ('gem_common', 2), ('spider_silk', 2), ('herb_magic', 2))},
    'holy_staff': {1: (('wood_common', 3), ('reed_bundle', 1), ('shore_herbs', 2)), 12: (('frostpine_wood', 3), ('spider_silk', 1), ('gem_common', 1), ('shore_herbs', 2)), 18: (('ancient_bark', 2), ('gem_common', 2), ('spider_silk', 2), ('desert_plant', 2))},
    'holy_rod': {1: (('wood_common', 2), ('reed_bundle', 1), ('shore_herbs', 2)), 12: (('frostpine_wood', 2), ('spider_silk', 1), ('gem_common', 1), ('shore_herbs', 2)), 18: (('ancient_bark', 1), ('gem_common', 2), ('spider_silk', 2), ('desert_plant', 2))},
    'tome': {1: (('reed_bundle', 4), ('wolf_pelt', 1), ('herb_common', 2)), 12: (('reed_bundle', 4), ('spider_silk', 2), ('gem_common', 1), ('herb_magic', 1)), 18: (('reed_bundle', 6), ('spider_silk', 3), ('gem_common', 2), ('ancient_bark', 1))},
}

_recipes: list[ProfessionRecipe] = []
for family, levels in WEAPON_INPUTS.items():
    profession = 'blacksmith' if family in {'sword_1h', 'sword_2h', 'axe_2h', 'daggers'} else 'arcane_engineer'
    for level, requirements in levels.items():
        _recipes.append(_gear(f'pe_{family}_{level:02d}', profession, level, requirements, f'field_{family}'))

for recipe_id, profession, level, requirements, output in (
    ('pe_shield_06','blacksmith',6,(('iron_ore',4),('coal',2),('stone_chunk',2),('wolf_fang',1)),'field_shield'),
    ('pe_shield_12','blacksmith',12,(('iron_ore',5),('coal',2),('frostpine_wood',2),('bear_hide',1)),'field_shield'),
    ('pe_shield_18','blacksmith',18,(('sunscar_ore',4),('iron_ore',3),('coal',3),('troll_sinew',1)),'field_shield'),
    ('pe_focus_06','arcane_engineer',6,(('wood_dark',2),('stone_chunk',2),('reed_bundle',2)),'field_focus'),
    ('pe_focus_12','arcane_engineer',12,(('frostpine_wood',2),('gem_common',1),('spider_silk',2),('herb_magic',1)),'field_focus'),
    ('pe_focus_18','arcane_engineer',18,(('ancient_bark',2),('gem_common',2),('spider_silk',2),('toxic_herb',1)),'field_focus'),
    ('pe_censer_06','arcane_engineer',6,(('wood_dark',2),('stone_chunk',2),('shore_herbs',2)),'field_censer'),
    ('pe_censer_12','arcane_engineer',12,(('frostpine_wood',2),('gem_common',1),('spider_silk',2),('desert_plant',1)),'field_censer'),
    ('pe_censer_18','arcane_engineer',18,(('ancient_bark',2),('gem_common',2),('spider_silk',2),('desert_plant',2)),'field_censer'),
    ('pe_heavy_chest_01','heavy_armor',1,(('iron_ore',4),('coal',2)),'field_heavy_chest'),
    ('pe_heavy_helmet_06','heavy_armor',6,(('iron_ore',3),('coal',2),('stone_chunk',2)),'field_heavy_helmet'),
    ('pe_heavy_legs_12','heavy_armor',12,(('iron_ore',6),('coal',3),('gem_common',1)),'field_heavy_legs'),
    ('pe_heavy_chest_18','heavy_armor',18,(('sunscar_ore',6),('iron_ore',4),('coal',4),('troll_sinew',2)),'field_heavy_chest'),
    ('trail_vest','medium_armor',1,(('wolf_pelt',2),('wood_common',2)),'trail_vest'),
    ('pe_medium_helmet_06','medium_armor',6,(('wolf_pelt',2),('wood_dark',1),('wolf_fang',1)),'field_medium_helmet'),
    ('pe_medium_legs_12','medium_armor',12,(('bear_hide',3),('spider_silk',2),('frostpine_wood',1)),'field_medium_legs'),
    ('pe_medium_chest_18','medium_armor',18,(('bear_hide',4),('spider_silk',3),('ancient_bark',1),('troll_sinew',1)),'field_medium_chest'),
    ('pe_light_chest_01','light_armor',1,(('reed_bundle',4),('herb_common',2)),'field_light_chest'),
    ('pe_light_helmet_06','light_armor',6,(('reed_bundle',3),('spider_silk',1),('marsh_herb',1)),'field_light_helmet'),
    ('pe_light_legs_12','light_armor',12,(('spider_silk',3),('reed_bundle',3),('herb_magic',2)),'field_light_legs'),
    ('pe_light_chest_18','light_armor',18,(('spider_silk',4),('reed_bundle',4),('herb_magic',2),('toxic_herb',2)),'field_light_chest'),
):
    _recipes.append(_gear(recipe_id, profession, level, requirements, output))

for row in (
    ('field_tonic','alchemy',1,(('herb_common',3),),'health_potion_small'),
    ('field_mana','alchemy',2,(('herb_common',5),),'mana_potion'),
    ('pe_alchemy_health_06','alchemy',6,(('herb_common',3),('marsh_herb',2)),'health_potion'),
    ('pe_alchemy_mana_12','alchemy',12,(('herb_magic',2),('desert_plant',2)),'pe_mana_potion_medium'),
    ('pe_alchemy_health_18','alchemy',18,(('herb_common',4),('toxic_herb',2),('desert_plant',1)),'pe_health_potion_large'),
    ('pe_alchemy_mana_18','alchemy',18,(('herb_magic',3),('toxic_herb',2),('desert_plant',2)),'pe_mana_potion_large'),
    ('trail_ration','cooking',1,(('boar_meat',1),('herb_common',1)),'field_ration'),
    ('pe_cooking_shore_01','cooking',1,(('shore_fish',1),('shore_herbs',1)),'pe_shore_broth'),
    ('pe_cooking_marsh_06','cooking',6,(('marsh_fish',2),('marsh_herb',1),('salt_crystal',1)),'pe_marsh_stew'),
    ('pe_cooking_boar_12','cooking',12,(('boar_meat',3),('forest_mushroom',2),('salt_crystal',1)),'pe_boar_feast'),
    ('pe_cooking_oasis_12','cooking',12,(('oasis_fish',2),('desert_plant',1),('salt_crystal',1)),'pe_oasis_meal'),
    ('pe_cooking_deep_18','cooking',18,(('deep_marsh_fish',2),('boar_meat',2),('forest_mushroom',2),('salt_crystal',1)),'pe_deep_marsh_meal'),
):
    _recipes.append(_consumable(*row))

ACTIVE_RECIPES = tuple(_recipes)
RECIPE_BY_ID = {recipe.recipe_id: recipe for recipe in ACTIVE_RECIPES}
ACTIVE_RECIPE_IDS = tuple(RECIPE_BY_ID)
STARTER_RECIPE_IDS = tuple(recipe.recipe_id for recipe in ACTIVE_RECIPES if recipe.starter)
GRANDFATHERED_RECIPE_IDS = ('field_tonic', 'field_mana', 'trail_ration', 'trail_vest')
INACTIVE_RECIPE_IDS = (
    'alchemy_minor_health_potion', 'cooking_field_ration',
    'blacksmith_iron_sword', 'arcane_focus_orb',
)


def get_recipe(recipe_id: str) -> ProfessionRecipe | None:
    return RECIPE_BY_ID.get(recipe_id)


def recipe_intent_payload(recipe_id: str) -> str:
    return json.dumps(
        {'schema_version': 1, 'catalog_version': 1, 'recipe_id': recipe_id},
        sort_keys=True, separators=(',', ':'),
    )


def parse_recipe_intent(payload: str) -> str | None:
    try:
        value = json.loads(payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(value, dict) or value.get('schema_version') != 1 or value.get('catalog_version') != 1:
        return None
    recipe_id = value.get('recipe_id')
    return str(recipe_id) if isinstance(recipe_id, str) else None


def recipe_consumers(item_id: str) -> tuple[str, ...]:
    return tuple(r.recipe_id for r in ACTIVE_RECIPES if any(i == item_id for i, _ in r.requirements))


assert len(ACTIVE_RECIPES) == 63
assert len(STARTER_RECIPE_IDS) == 17
