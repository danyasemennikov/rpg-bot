"""PXE1 catalogue 2: preserve 63 recipes and add 20 dedicated tool outputs."""

from __future__ import annotations

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class RecipeOutputSpec:
    kind: str
    item_id: str | None = None
    quantity: int = 1
    item_tier: int | None = None
    rarity: str = 'common'
    secondary_policy: str = 'not_applicable'
    profession_key: str | None = None
    tool_tier: int | None = None

    def __post_init__(self):
        if self.kind == 'tool':
            if self.item_id is not None or self.quantity != 1 or self.tool_tier not in (1,2,3,4,5,6) or self.profession_key not in ('woodcutting','mining','herbalism','fishing','hunting'):
                raise ValueError('invalid tool output')
        elif self.kind not in ('gear','consumable') or not self.item_id or self.profession_key is not None or self.tool_tier is not None:
            raise ValueError('invalid item output')


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
    catalog_version: int = 2
    material_value: int = 0
    xp_policy_version: int = 3
    recipe_label: int = 1
    tier: int = 1
    work_category: str = 'S'


from pathlib import Path
from game.profession_resources import RESOURCES

CATALOG_VERSION = 3
_rows = json.loads(Path(__file__).with_name('profession_catalog_v3.json').read_text(encoding='utf-8'))['recipes']
ACTIVE_RECIPES = tuple(ProfessionRecipe(
    recipe_id=r['recipe_id'],profession_key=r['profession_key'],
    required_level=1 if r['tier']==1 else 16,
    requirements=tuple((i,q) for i,q in r['requirements']),output_spec=RecipeOutputSpec(**r['output_spec']),
    learning_gold=8 if r['tier']==1 else 60,training_ceiling=15 if r['tier']==1 else 30,
    catalog_version=3,xp_policy_version=3,recipe_label=r['recipe_label'],tier=r['tier'],
    work_category=r['work_category'],material_value=sum(RESOURCES[i].sell_price*q for i,q in r['requirements'])
) for r in _rows)
RECIPE_BY_ID = {r.recipe_id:r for r in ACTIVE_RECIPES}
ACTIVE_RECIPE_IDS = tuple(RECIPE_BY_ID)
STARTER_RECIPE_IDS = ()
GRANDFATHERED_RECIPE_IDS = ()
INACTIVE_RECIPE_IDS = ('alchemy_minor_health_potion','cooking_field_ration','blacksmith_iron_sword','arcane_focus_orb')
GATHERING_MANUALS = {
    f'gp_{profession}_{tier}_{technique}': {'knowledge_id':f'gp_{profession}_{tier}_{technique}',
        'profession_key':profession,'tier':tier,'technique':technique,'learning_gold':8 if tier==1 else 60}
    for profession in ('woodcutting','mining','herbalism','fishing','hunting')
    for tier in (1,2) for technique in ('a','b')
}


def get_recipe(recipe_id: str) -> ProfessionRecipe | None:
    return RECIPE_BY_ID.get(recipe_id)


def recipe_intent_payload(recipe_id: str, *, tool_revision: int | None=None,
                          commission: bool=False,replacement_confirmed: bool=False,
                          input_snapshot: dict | None=None) -> str:
    payload = {'schema_version':1,'catalog_version':3,'recipe_id':recipe_id}
    recipe = get_recipe(recipe_id)
    if recipe and recipe.output_spec.kind=='tool':
        payload.update(tool_revision=tool_revision,commission=commission,replacement_confirmed=replacement_confirmed)
        if input_snapshot is not None:
            payload['input_snapshot'] = input_snapshot
    return json.dumps(
        payload,
        sort_keys=True, separators=(',', ':'),
    )


def parse_recipe_intent(payload: str) -> str | None:
    try:
        value = json.loads(payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(value, dict) or value.get('schema_version') != 1 or value.get('catalog_version') != 3:
        return None
    recipe_id = value.get('recipe_id')
    return str(recipe_id) if isinstance(recipe_id, str) else None


def recipe_consumers(item_id: str) -> tuple[str, ...]:
    return tuple(r.recipe_id for r in ACTIVE_RECIPES if any(i == item_id for i, _ in r.requirements))


assert len(ACTIVE_RECIPES) == 153
assert len(GATHERING_MANUALS) == 20
