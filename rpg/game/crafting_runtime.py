"""Phase 7 crafting runtime: recipe contract + validation + craft execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from database import get_connection
from game.crafting_foundation import (
    CRAFTING_PROFESSION_CONTRACTS,
    CraftingProfessionKey,
    resolve_crafting_material_identity,
)
from game.gear_instances import grant_item_to_player
from game.items_data import get_item, get_item_metadata

RequirementKind = Literal['bulk', 'special']
CraftStatus = Literal[
    'crafted',
    'recipe_not_found',
    'invalid_recipe_contract',
    'profession_level_too_low',
    'missing_materials',
    'craft_failed_atomic',
]


@dataclass(frozen=True)
class RecipeRequirement:
    item_id: str
    quantity: int
    expected_group: str | None = None


@dataclass(frozen=True)
class RecipeDefinition:
    recipe_id: str
    output_item_id: str
    output_quantity: int
    profession_key: CraftingProfessionKey
    minimum_profession_level: int
    material_requirements: tuple[RecipeRequirement, ...]
    special_ingredient_requirements: tuple[RecipeRequirement, ...] = ()
    category: str | None = None
    notes: str | None = None
    recipes_are_permanent: bool = True


@dataclass(frozen=True)
class MissingMaterial:
    item_id: str
    required: int
    available: int
    requirement_kind: RequirementKind


@dataclass(frozen=True)
class CraftResult:
    status: CraftStatus
    recipe_id: str
    profession_key: CraftingProfessionKey | None = None
    required_profession_level: int | None = None
    player_profession_level: int | None = None
    missing_materials: tuple[MissingMaterial, ...] = field(default_factory=tuple)
    crafted_item_id: str | None = None
    crafted_quantity: int = 0

    @property
    def is_success(self) -> bool:
        return self.status == 'crafted'


STARTER_RECIPES: tuple[RecipeDefinition, ...] = (
    RecipeDefinition(
        recipe_id='alchemy_minor_health_potion',
        output_item_id='health_potion_small',
        output_quantity=1,
        profession_key='alchemy',
        minimum_profession_level=1,
        material_requirements=(
            RecipeRequirement(item_id='herb_common', quantity=2, expected_group='herb_base'),
            RecipeRequirement(item_id='herb_magic', quantity=1, expected_group='herb_base'),
        ),
        special_ingredient_requirements=(
            RecipeRequirement(item_id='spider_venom', quantity=1, expected_group='venom'),
        ),
        category='starter_alchemy',
    ),
    RecipeDefinition(
        recipe_id='cooking_field_ration',
        output_item_id='health_potion_small',
        output_quantity=1,
        profession_key='cooking',
        minimum_profession_level=1,
        material_requirements=(
            RecipeRequirement(item_id='boar_meat', quantity=2, expected_group='meat'),
            RecipeRequirement(item_id='herb_common', quantity=1, expected_group='herb_base'),
            RecipeRequirement(item_id='coal', quantity=1, expected_group='fuel'),
        ),
        category='starter_cooking',
        notes='Temporary food-output bridge until dedicated food consumables are added.',
    ),
    RecipeDefinition(
        recipe_id='blacksmith_iron_sword',
        output_item_id='iron_sword',
        output_quantity=1,
        profession_key='blacksmith',
        minimum_profession_level=2,
        material_requirements=(
            RecipeRequirement(item_id='iron_ore', quantity=3, expected_group='ore'),
            RecipeRequirement(item_id='coal', quantity=1, expected_group='fuel'),
            RecipeRequirement(item_id='wood_dark', quantity=1, expected_group='wood'),
        ),
        special_ingredient_requirements=(
            RecipeRequirement(item_id='wolf_fang', quantity=1, expected_group='trophy'),
        ),
        category='starter_blacksmith',
    ),
    RecipeDefinition(
        recipe_id='arcane_focus_orb',
        output_item_id='apprentice_focus_orb',
        output_quantity=1,
        profession_key='arcane_engineer',
        minimum_profession_level=2,
        material_requirements=(
            RecipeRequirement(item_id='wood_dark', quantity=2, expected_group='wood'),
            RecipeRequirement(item_id='gem_common', quantity=1, expected_group='gem'),
        ),
        special_ingredient_requirements=(
            RecipeRequirement(item_id='stone_core', quantity=1, expected_group='core'),
        ),
        category='starter_arcane_engineer',
    ),
)

RECIPE_BY_ID: dict[str, RecipeDefinition] = {recipe.recipe_id: recipe for recipe in STARTER_RECIPES}


def get_recipe(recipe_id: str) -> RecipeDefinition | None:
    return RECIPE_BY_ID.get(recipe_id)


def craft_recipe(telegram_id: int, recipe_id: str, profession_levels: dict[CraftingProfessionKey, int]) -> CraftResult:
    recipe = get_recipe(recipe_id)
    if recipe is None:
        return CraftResult(status='recipe_not_found', recipe_id=recipe_id)

    contract_errors = validate_recipe_contract(recipe)
    if contract_errors:
        return CraftResult(
            status='invalid_recipe_contract',
            recipe_id=recipe_id,
            profession_key=recipe.profession_key,
        )

    player_level = int(profession_levels.get(recipe.profession_key, 0))
    if player_level < recipe.minimum_profession_level:
        return CraftResult(
            status='profession_level_too_low',
            recipe_id=recipe.recipe_id,
            profession_key=recipe.profession_key,
            required_profession_level=recipe.minimum_profession_level,
            player_profession_level=player_level,
        )

    aggregated_requirements = _aggregate_recipe_requirements(recipe)
    missing = _find_missing_materials(telegram_id, aggregated_requirements)
    if missing:
        return CraftResult(
            status='missing_materials',
            recipe_id=recipe.recipe_id,
            profession_key=recipe.profession_key,
            missing_materials=tuple(missing),
        )

    conn = get_connection()
    try:
        conn.execute('BEGIN')
        _consume_recipe_materials(conn, telegram_id, aggregated_requirements)
        grant = grant_item_to_player(
            telegram_id,
            recipe.output_item_id,
            recipe.output_quantity,
            source='crafting',
            conn=conn,
        )
        crafted_quantity = int(grant.get('stackable_added', 0) + grant.get('gear_instances_created', 0))
        conn.commit()
        return CraftResult(
            status='crafted',
            recipe_id=recipe.recipe_id,
            profession_key=recipe.profession_key,
            crafted_item_id=recipe.output_item_id,
            crafted_quantity=crafted_quantity,
        )
    except Exception:
        conn.rollback()
        return CraftResult(
            status='craft_failed_atomic',
            recipe_id=recipe.recipe_id,
            profession_key=recipe.profession_key,
        )
    finally:
        conn.close()


def validate_recipe_contract(recipe: RecipeDefinition) -> list[str]:
    errors: list[str] = []
    if recipe.profession_key not in CRAFTING_PROFESSION_CONTRACTS:
        errors.append(f'unknown profession {recipe.profession_key}')
        return errors

    output_item = get_item(recipe.output_item_id)
    if output_item is None:
        errors.append(f'unknown output item {recipe.output_item_id}')

    if recipe.output_quantity <= 0:
        errors.append('output quantity must be positive')

    if recipe.minimum_profession_level < 1:
        errors.append('minimum profession level must be >= 1')

    if not recipe.material_requirements and not recipe.special_ingredient_requirements:
        errors.append('recipe must include at least one material requirement')

    bulk_ids = {requirement.item_id for requirement in recipe.material_requirements}
    special_ids = {requirement.item_id for requirement in recipe.special_ingredient_requirements}
    cross_kind_duplicates = sorted(bulk_ids.intersection(special_ids))
    for item_id in cross_kind_duplicates:
        errors.append(f'{item_id}: duplicate requirement across bulk and special is not allowed')

    contract = CRAFTING_PROFESSION_CONTRACTS[recipe.profession_key]
    output_families = resolve_crafting_output_families(recipe.output_item_id)
    if not output_families:
        errors.append(f'{recipe.output_item_id}: output family is unknown for crafting contract')
    elif not any(output_family in contract.output_families for output_family in output_families):
        errors.append(
            f'{recipe.output_item_id}: output families {output_families} are not allowed for {recipe.profession_key}'
        )

    errors.extend(_validate_requirements(recipe.profession_key, contract.bulk_resource_groups, recipe.material_requirements, 'bulk'))
    errors.extend(_validate_requirements(recipe.profession_key, contract.special_ingredient_groups, recipe.special_ingredient_requirements, 'special'))
    return errors


def resolve_crafting_output_families(item_id: str) -> tuple[str, ...]:
    item = get_item(item_id)
    if item is None:
        return ()

    item_type = item.get('item_type')
    if item_type == 'potion':
        # Temporary bridge: current cooking starter output reuses a consumable potion item.
        return ('potions', 'edible_recovery')

    metadata = get_item_metadata(item_id)
    weapon_profile = metadata.get('weapon_profile')
    slot_identity = metadata.get('slot_identity')
    offhand_profile = metadata.get('offhand_profile')
    armor_class = metadata.get('armor_class')

    if item_type == 'weapon':
        if weapon_profile == 'bow':
            return ('bows',)
        if weapon_profile in {'magic_staff', 'holy_staff'}:
            return ('staffs',)
        if weapon_profile == 'wand':
            return ('wands',)
        if weapon_profile == 'holy_rod':
            return ('rods',)
        if weapon_profile == 'tome':
            return ('tomes',)
        if weapon_profile in {'sword_1h', 'sword_2h', 'axe_2h', 'daggers'}:
            return ('metal_weapons',)

    if slot_identity == 'offhand':
        if offhand_profile == 'shield':
            return ('shields',)
        if offhand_profile == 'focus':
            return ('foci',)
        if offhand_profile == 'censer':
            return ('censers',)

    if item_type == 'armor' and slot_identity in {'helmet', 'chest', 'legs', 'boots', 'gloves'}:
        if armor_class == 'heavy':
            return ('heavy_armor',)
        if armor_class == 'medium':
            return ('medium_armor',)
        if armor_class == 'light':
            return ('light_armor',)

    return ()


def _validate_requirements(
    profession_key: CraftingProfessionKey,
    allowed_groups: tuple[str, ...],
    requirements: tuple[RecipeRequirement, ...],
    requirement_kind: RequirementKind,
) -> list[str]:
    errors: list[str] = []
    for requirement in requirements:
        if requirement.quantity <= 0:
            errors.append(f'{requirement.item_id}: quantity must be positive')
            continue

        identity = resolve_crafting_material_identity(requirement.item_id)
        if identity is None:
            errors.append(f'{requirement.item_id}: missing crafting identity')
            continue

        if requirement_kind == 'bulk':
            group = identity.bulk_resource_group
            if group is None:
                errors.append(f'{requirement.item_id}: expected bulk material')
                continue
        else:
            group = identity.special_ingredient_group
            if group is None:
                errors.append(f'{requirement.item_id}: expected special ingredient')
                continue

        if group not in allowed_groups:
            errors.append(f'{requirement.item_id}: group {group} is not allowed for {profession_key}')

        if requirement.expected_group is not None and group != requirement.expected_group:
            errors.append(f'{requirement.item_id}: group {group} does not match expected {requirement.expected_group}')

        if identity.default_professions and profession_key not in identity.default_professions:
            errors.append(f'{requirement.item_id}: profession {profession_key} is outside material contract')
    return errors


def _aggregate_recipe_requirements(recipe: RecipeDefinition) -> dict[str, dict[str, int]]:
    aggregated = {'bulk': {}, 'special': {}}
    for requirement in recipe.material_requirements:
        aggregated['bulk'][requirement.item_id] = aggregated['bulk'].get(requirement.item_id, 0) + int(requirement.quantity)
    for requirement in recipe.special_ingredient_requirements:
        aggregated['special'][requirement.item_id] = (
            aggregated['special'].get(requirement.item_id, 0) + int(requirement.quantity)
        )
    return aggregated


def _find_missing_materials(telegram_id: int, aggregated_requirements: dict[str, dict[str, int]]) -> list[MissingMaterial]:
    inventory = _get_inventory_quantities(telegram_id)
    missing: list[MissingMaterial] = []
    for item_id, required_qty in aggregated_requirements['bulk'].items():
        available = inventory.get(item_id, 0)
        if available < required_qty:
            missing.append(MissingMaterial(item_id, required_qty, available, 'bulk'))
    for item_id, required_qty in aggregated_requirements['special'].items():
        available = inventory.get(item_id, 0)
        if available < required_qty:
            missing.append(MissingMaterial(item_id, required_qty, available, 'special'))
    return missing


def _get_inventory_quantities(telegram_id: int) -> dict[str, int]:
    conn = get_connection()
    try:
        rows = conn.execute('SELECT item_id, quantity FROM inventory WHERE telegram_id=?', (telegram_id,)).fetchall()
        return {str(row['item_id']): int(row['quantity']) for row in rows}
    finally:
        conn.close()


def _consume_recipe_materials(conn, telegram_id: int, aggregated_requirements: dict[str, dict[str, int]]):
    for requirement_kind in ('bulk', 'special'):
        for item_id, required_qty in aggregated_requirements[requirement_kind].items():
            row = conn.execute(
                'SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id=?',
                (telegram_id, item_id),
            ).fetchone()
            if not row:
                continue
            new_quantity = int(row['quantity']) - int(required_qty)
            if new_quantity > 0:
                conn.execute('UPDATE inventory SET quantity=? WHERE id=?', (new_quantity, row['id']))
            else:
                conn.execute('DELETE FROM inventory WHERE id=?', (row['id'],))
