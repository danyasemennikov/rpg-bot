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
from game.gear_instances import generate_secondary_rolls_for_item
from game.items_data import get_item, get_item_metadata
from game.profession_recipes import (
    ACTIVE_RECIPES as PEV1_ACTIVE_RECIPES,
    ACTIVE_RECIPE_IDS as PEV1_ACTIVE_RECIPE_IDS,
    INACTIVE_RECIPE_IDS,
    parse_recipe_intent,
)
from game.profession_resources import RESOURCES

RequirementKind = Literal['bulk', 'special']
CraftStatus = Literal[
    'crafted',
    'recipe_not_found',
    'invalid_recipe_contract',
    'profession_level_too_low',
    'missing_materials',
    'craft_failed_atomic',
    'stale_action', 'in_battle', 'wrong_location', 'no_player',
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
    active: bool = True
    starter: bool = False
    learning_gold: int = 0
    training_ceiling: int = 6
    catalog_version: int = 1
    output_kind: str = 'consumable'
    item_tier: int | None = None
    output_rarity: str = 'common'
    secondary_policy: str = 'not_applicable'


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
    profession_xp: int = 0
    instance_ids: tuple[int, ...] = field(default_factory=tuple)
    recovered: bool = False

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

EARLY_RECIPES = (
    RecipeDefinition('field_tonic', 'health_potion_small', 1, 'alchemy', 1,
                     (RecipeRequirement('herb_common', 3, 'herb_base'),)),
    RecipeDefinition('trail_ration', 'field_ration', 1, 'cooking', 1,
                     (RecipeRequirement('boar_meat', 1, 'meat'), RecipeRequirement('herb_common', 1, 'herb_base'))),
    RecipeDefinition('trail_vest', 'trail_vest', 1, 'medium_armor', 1,
                     (RecipeRequirement('wolf_pelt', 2, 'hide'), RecipeRequirement('wood_common', 2, 'wood'))),
    RecipeDefinition('field_mana', 'mana_potion', 1, 'alchemy', 2,
                     (RecipeRequirement('herb_common', 5, 'herb_base'),)),
)
def _pev1_runtime_recipe(recipe) -> RecipeDefinition:
    bulk, special = [], []
    for item_id, quantity in recipe.requirements:
        group = RESOURCES[item_id].resource_group
        target = special if group in {'trophy', 'monster_part'} else bulk
        target.append(RecipeRequirement(item_id, quantity, group))
    return RecipeDefinition(
        recipe.recipe_id, recipe.output_spec.item_id, recipe.output_spec.quantity,
        recipe.profession_key, recipe.required_level, tuple(bulk), tuple(special),
        recipes_are_permanent=True, active=True, starter=recipe.starter,
        learning_gold=recipe.learning_gold, training_ceiling=recipe.training_ceiling,
        catalog_version=recipe.catalog_version, output_kind=recipe.output_spec.kind,
        item_tier=recipe.output_spec.item_tier, output_rarity=recipe.output_spec.rarity,
        secondary_policy=recipe.output_spec.secondary_policy,
    )


ACTIVE_RECIPES = tuple(_pev1_runtime_recipe(recipe) for recipe in PEV1_ACTIVE_RECIPES)
LIVE_RECIPE_IDS = tuple(PEV1_ACTIVE_RECIPE_IDS)
INACTIVE_RECIPE_BY_ID = {recipe.recipe_id: recipe for recipe in STARTER_RECIPES if recipe.recipe_id in INACTIVE_RECIPE_IDS}
RECIPE_BY_ID: dict[str, RecipeDefinition] = {
    **{recipe.recipe_id: recipe for recipe in ACTIVE_RECIPES},
    **INACTIVE_RECIPE_BY_ID,
}


def get_recipe(recipe_id: str) -> RecipeDefinition | None:
    return RECIPE_BY_ID.get(recipe_id) or INACTIVE_RECIPE_BY_ID.get(recipe_id)


def _craft_rejection(conn, *, player_id, player, request_id, receipt_hash, recipe, status, details=None):
    from game.economy_actions import store_receipt
    result = {'schema_version':1,'action_kind':'craft','status':status,'player_id':player_id,
              'location_id':player.get('location_id'),'recipe_id':recipe.recipe_id,
              'consumed':[],'granted':[],'gold_delta':0,'gold_after':player.get('gold',0),
              'progression':[],'source':{'catalog_version':1},'details':details or {}}
    if request_id:
        store_receipt(conn, player_id, request_id, 'craft', receipt_hash, result)
        conn.commit()
    return CraftResult(status=status, recipe_id=recipe.recipe_id,
                       profession_key=recipe.profession_key,
                       required_profession_level=recipe.minimum_profession_level)


def craft_recipe(telegram_id: int, recipe_id: str,
                 profession_levels: dict[CraftingProfessionKey, int] | None = None,
                 *, action_token: str | None = None, request_id: str | None = None,
                 rng=None) -> CraftResult:
    """Execute a recipe with locked validation and atomic delivery.

    The original explicit-level API remains for foundation callers. Live recipes
    always use persisted levels, even if a caller supplies a level dictionary.
    Telegram only submits a server-issued intent; it cannot select a locked recipe.
    """
    from game.action_receipts import ActionRejected, peaceful_player, consume_action, require_item_delivery
    from game.alpha_schema import ensure_crafting_professions
    from game.economy_actions import find_receipt, intent_hash, store_receipt
    from game.profession_progression import apply_profession_xp, crafting_xp_for_success

    conn = get_connection()
    recipe = None
    try:
        conn.execute('BEGIN IMMEDIATE')
        if action_token is not None:
            request_id = request_id or f'ui:{action_token}'
            token_row = conn.execute('''SELECT payload FROM player_ui_actions
                WHERE token=? AND player_id=? AND kind='craft' ''', (action_token, telegram_id)).fetchone()
            if token_row:
                recipe_id = parse_recipe_intent(str(token_row['payload'])) or ''
        recipe = get_recipe(recipe_id)
        if recipe is None or recipe_id not in LIVE_RECIPE_IDS:
            return CraftResult(status='recipe_not_found', recipe_id=recipe_id)
        receipt_hash = intent_hash('craft', telegram_id, {'recipe_id': recipe_id})
        if request_id:
            recovered = find_receipt(conn, telegram_id, request_id, 'craft', receipt_hash)
            if recovered is not None:
                conn.commit()
                if recovered.get('status') != 'crafted':
                    return CraftResult(status=recovered.get('status', 'craft_failed_atomic'), recipe_id=recipe_id,
                        profession_key=recipe.profession_key, recovered=True)
                granted = recovered.get('granted') or [{}]
                return CraftResult(status='crafted', recipe_id=recipe_id,
                    profession_key=recipe.profession_key, crafted_item_id=recipe.output_item_id,
                    crafted_quantity=recipe.output_quantity,
                    profession_xp=int((recovered.get('progression') or [{}])[0].get('xp_awarded', 0)),
                    instance_ids=tuple(granted[0].get('instance_ids') or ()), recovered=True)
        if action_token is not None:
            raw_payload = consume_action(conn, telegram_id, 'craft', action_token)
            if parse_recipe_intent(raw_payload) != recipe_id:
                raise ActionRejected('stale_action')
        if validate_recipe_contract(recipe):
            return CraftResult(status='invalid_recipe_contract', recipe_id=recipe_id)
        player = peaceful_player(conn, telegram_id, service='craftsmen_guild')
        ensure_crafting_professions(conn, telegram_id)
        profession = conn.execute('''SELECT level, exp FROM player_crafting_professions
            WHERE player_id=? AND profession_key=?''', (telegram_id, recipe.profession_key)).fetchone()
        player_level = profession['level']
        known = conn.execute('SELECT 1 FROM player_recipe_knowledge WHERE player_id=? AND recipe_id=?',
                             (telegram_id, recipe_id)).fetchone()
        if not known:
            return _craft_rejection(conn, player_id=telegram_id, player=player, request_id=request_id,
                receipt_hash=receipt_hash, recipe=recipe, status='recipe_not_found')
        if player_level < recipe.minimum_profession_level:
            result = _craft_rejection(conn, player_id=telegram_id, player=player, request_id=request_id,
                receipt_hash=receipt_hash, recipe=recipe, status='profession_level_too_low',
                details={'player_level':player_level,'required_level':recipe.minimum_profession_level})
            return CraftResult(**{**result.__dict__, 'player_profession_level': player_level})
        aggregated_requirements = _aggregate_recipe_requirements(recipe)
        missing = _find_missing_materials(telegram_id, aggregated_requirements, conn=conn)
        if missing:
            result = _craft_rejection(conn, player_id=telegram_id, player=player, request_id=request_id,
                receipt_hash=receipt_hash, recipe=recipe, status='missing_materials',
                details={'missing':[m.__dict__ for m in missing]})
            return CraftResult(**{**result.__dict__, 'missing_materials': tuple(missing)})
        _consume_recipe_materials(conn, telegram_id, aggregated_requirements)
        secondary_rolls = []
        gear_spec = None
        if recipe.output_kind == 'gear':
            if recipe.secondary_policy == 'ordinary_one':
                secondary_rolls = generate_secondary_rolls_for_item(
                    get_item(recipe.output_item_id) or {}, rarity=recipe.output_rarity,
                    item_tier=recipe.item_tier or 1, rng=rng,
                )
                secondary_rolls = secondary_rolls[:1]
            gear_spec = {'base_item_id': recipe.output_item_id, 'item_tier': recipe.item_tier,
                         'rarity': recipe.output_rarity, 'secondary_rolls': secondary_rolls,
                         'enhance_level': 0, 'durability': 100, 'max_durability': 100}
        grant = grant_item_to_player(
            telegram_id,
            recipe.output_item_id,
            recipe.output_quantity,
            source='crafting',
            gear_spec=gear_spec,
            provenance={'source': 'crafting', 'catalog_version': 1, 'recipe_id': recipe_id,
                        'profession_key': recipe.profession_key, 'crafter_player_id': telegram_id,
                        'location_id': player['location_id'], 'craft_request_id': request_id},
            rng=rng,
            conn=conn,
        )
        require_item_delivery(grant, recipe.output_quantity)
        crafted_quantity = int(grant.get('stackable_added', 0) + grant.get('gear_instances_created', 0))
        xp = crafting_xp_for_success(current_level=player_level, current_exp=profession['exp'],
                                     recipe_level=recipe.minimum_profession_level)
        progression = apply_profession_xp(player_level, profession['exp'], xp)
        if xp:
            conn.execute('''UPDATE player_crafting_professions SET level=?, exp=?
                WHERE player_id=? AND profession_key=?''',
                         (progression.new_level, progression.new_exp, telegram_id, recipe.profession_key))
        from game.quest_board import register_contract_objective
        register_contract_objective(conn, telegram_id, 'craft', recipe.output_item_id,
                                    crafted_quantity, player['location_id'])
        if request_id:
            receipt = {
                'schema_version': 1, 'action_kind': 'craft', 'status': 'crafted',
                'player_id': telegram_id, 'location_id': player['location_id'], 'recipe_id': recipe_id,
                'consumed': [{'item_id': item_id, 'quantity': quantity}
                             for kind in ('bulk', 'special') for item_id, quantity in aggregated_requirements[kind].items()],
                'granted': [{'item_id': recipe.output_item_id, 'quantity': crafted_quantity,
                             'instance_ids': grant.get('instance_ids', []), 'gear_specs': [gear_spec] if gear_spec else []}],
                'gold_delta': 0, 'gold_after': player['gold'],
                'progression': [{'profession_key': recipe.profession_key,
                    'old_level': progression.old_level, 'old_exp': progression.old_exp,
                    'new_level': progression.new_level, 'new_exp': progression.new_exp, 'xp_awarded': xp}],
                'source': {'catalog_version': 1}, 'details': {},
            }
            store_receipt(conn, telegram_id, request_id, 'craft', receipt_hash, receipt)
        conn.commit()
        return CraftResult(
            status='crafted',
            recipe_id=recipe.recipe_id,
            profession_key=recipe.profession_key,
            crafted_item_id=recipe.output_item_id,
            crafted_quantity=crafted_quantity,
            profession_xp=xp,
            instance_ids=tuple(grant.get('instance_ids', ())),
        )
    except ActionRejected as exc:
        conn.rollback()
        return CraftResult(status=str(exc), recipe_id=recipe_id)
    except Exception:
        conn.rollback()
        return CraftResult(
            status='craft_failed_atomic',
            recipe_id=recipe_id,
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
    if item.get('consumable_family') == 'food':
        return ('food', 'edible_recovery')
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


def _find_missing_materials(telegram_id: int, aggregated_requirements: dict[str, dict[str, int]], *, conn=None) -> list[MissingMaterial]:
    inventory = _get_inventory_quantities(telegram_id, conn=conn)
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


def _get_inventory_quantities(telegram_id: int, *, conn=None) -> dict[str, int]:
    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()
    try:
        rows = conn.execute('SELECT item_id, SUM(quantity) AS quantity FROM inventory WHERE telegram_id=? GROUP BY item_id', (telegram_id,)).fetchall()
        return {str(row['item_id']): int(row['quantity']) for row in rows}
    finally:
        if owns_connection:
            conn.close()


def _consume_recipe_materials(conn, telegram_id: int, aggregated_requirements: dict[str, dict[str, int]]):
    for requirement_kind in ('bulk', 'special'):
        for item_id, required_qty in aggregated_requirements[requirement_kind].items():
            rows = conn.execute(
                'SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id=? ORDER BY id',
                (telegram_id, item_id),
            ).fetchall()
            remaining = required_qty
            for row in rows:
                take = min(remaining, int(row['quantity']))
                if take <= 0:
                    continue
                if take == row['quantity']:
                    conn.execute('DELETE FROM inventory WHERE id=?', (row['id'],))
                else:
                    conn.execute('UPDATE inventory SET quantity=quantity-? WHERE id=?', (take, row['id']))
                remaining -= take
            if remaining:
                raise ValueError('materials_changed')
