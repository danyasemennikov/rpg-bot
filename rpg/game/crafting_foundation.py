"""Crafting professions foundation helpers (Phase 6).

Scope intentionally narrow:
- explicit crafting profession contracts;
- craft-side material identity layer;
- gather -> craft bridge via GatherResourceIdentity;
- bulk resource vs special ingredient contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from game.gathering_foundation import GatherResourceIdentity, resolve_gather_resource_identity
from game.items_data import get_item_reward_tags

CraftingProfessionKey = Literal[
    'heavy_armor',
    'medium_armor',
    'light_armor',
    'blacksmith',
    'arcane_engineer',
    'alchemy',
    'cooking',
]


@dataclass(frozen=True)
class CraftingProfessionContract:
    profession_key: CraftingProfessionKey
    output_families: tuple[str, ...]
    base_material_logic: tuple[str, ...]
    bulk_resource_groups: tuple[str, ...]
    special_ingredient_groups: tuple[str, ...]
    recipes_are_permanent: bool = True


@dataclass(frozen=True)
class CraftMaterialIdentity:
    item_id: str
    reward_family: str
    material_subtype: str
    origin_channel: str
    bulk_resource_group: str | None
    special_ingredient_group: str | None
    default_professions: tuple[CraftingProfessionKey, ...]
    gather_profession_key: str | None
    gather_resource_family: str | None

    @property
    def is_bulk_resource(self) -> bool:
        return self.bulk_resource_group is not None

    @property
    def is_special_ingredient(self) -> bool:
        return self.special_ingredient_group is not None


CRAFTING_PROFESSION_CONTRACTS: dict[CraftingProfessionKey, CraftingProfessionContract] = {
    'heavy_armor': CraftingProfessionContract(
        profession_key='heavy_armor',
        output_families=('heavy_armor',),
        base_material_logic=('metal_plates', 'forged_fasteners', 'smithing_fuel'),
        bulk_resource_groups=('ore', 'fuel'),
        special_ingredient_groups=('core', 'heart', 'trophy', 'monster_part'),
    ),
    'medium_armor': CraftingProfessionContract(
        profession_key='medium_armor',
        output_families=('medium_armor', 'leather_armor'),
        base_material_logic=('hide_panels', 'reinforced_stitches', 'hybrid_support_parts'),
        bulk_resource_groups=('hide', 'fiber', 'wood'),
        special_ingredient_groups=('heart', 'trophy', 'monster_part'),
    ),
    'light_armor': CraftingProfessionContract(
        profession_key='light_armor',
        output_families=('light_armor', 'cloth_armor'),
        base_material_logic=('fiber_weave', 'thread_binding', 'arcane_stitching'),
        bulk_resource_groups=('fiber', 'herb_base'),
        special_ingredient_groups=('essence', 'core', 'special_reagent'),
    ),
    'blacksmith': CraftingProfessionContract(
        profession_key='blacksmith',
        output_families=('metal_weapons', 'shields', 'metal_parts'),
        base_material_logic=('ore_smelting', 'forged_shapes', 'temper_with_fuel'),
        bulk_resource_groups=('ore', 'fuel', 'wood'),
        special_ingredient_groups=('core', 'trophy', 'monster_part', 'essence'),
    ),
    'arcane_engineer': CraftingProfessionContract(
        profession_key='arcane_engineer',
        output_families=('bows', 'staffs', 'wands', 'rods', 'tomes', 'foci', 'censers', 'arcane_ranged_gear'),
        base_material_logic=('wooden_or_arcane_frame', 'focus_components', 'infused_binding'),
        bulk_resource_groups=('wood', 'fiber', 'gem'),
        special_ingredient_groups=('core', 'essence', 'heart', 'monster_part'),
    ),
    'alchemy': CraftingProfessionContract(
        profession_key='alchemy',
        output_families=('potions', 'combat_consumables', 'processed_reagents'),
        base_material_logic=('herb_processing', 'solvent_binding', 'reagent_infusion'),
        bulk_resource_groups=('herb_base',),
        special_ingredient_groups=('venom', 'core', 'heart', 'essence', 'special_reagent'),
    ),
    'cooking': CraftingProfessionContract(
        profession_key='cooking',
        output_families=('food', 'long_buffs', 'edible_recovery'),
        base_material_logic=('raw_food_base', 'herb_seasoning', 'controlled_heat'),
        bulk_resource_groups=('meat', 'fish', 'herb_base', 'fuel'),
        special_ingredient_groups=('heart', 'trophy', 'special_reagent'),
    ),
}


EXPLICIT_CRAFT_IDENTITY_BY_ITEM_ID: dict[str, dict] = {
    # Gather-derived bulk materials
    'iron_ore': {'bulk_resource_group': 'ore', 'default_professions': ('heavy_armor', 'blacksmith')},
    'coal': {'bulk_resource_group': 'fuel', 'default_professions': ('heavy_armor', 'blacksmith', 'cooking')},
    'wood_dark': {'bulk_resource_group': 'wood', 'default_professions': ('medium_armor', 'blacksmith', 'arcane_engineer')},
    'herb_common': {'bulk_resource_group': 'herb_base', 'default_professions': ('alchemy', 'cooking')},
    'herb_magic': {'bulk_resource_group': 'herb_base', 'default_professions': ('alchemy', 'light_armor')},
    'gem_common': {'bulk_resource_group': 'gem', 'default_professions': ('arcane_engineer', 'blacksmith')},
    # Creature-derived bulk materials
    'wolf_pelt': {'bulk_resource_group': 'hide', 'default_professions': ('medium_armor',)},
    'rat_fur': {'bulk_resource_group': 'hide', 'default_professions': ('medium_armor',)},
    'spider_silk': {'bulk_resource_group': 'fiber', 'default_professions': ('light_armor', 'arcane_engineer')},
    'boar_meat': {'bulk_resource_group': 'meat', 'default_professions': ('cooking',)},
    'ancient_bark': {'bulk_resource_group': 'wood', 'default_professions': ('blacksmith', 'arcane_engineer')},
    # Special ingredients / rare monster parts
    'spider_venom': {'special_ingredient_group': 'venom', 'default_professions': ('alchemy',)},
    'stone_core': {'special_ingredient_group': 'core', 'default_professions': ('arcane_engineer', 'blacksmith')},
    'treant_heart': {'special_ingredient_group': 'heart', 'default_professions': ('alchemy', 'arcane_engineer')},
    'bat_wing': {'special_ingredient_group': 'monster_part', 'default_professions': ('alchemy', 'arcane_engineer')},
    'wolf_fang': {'special_ingredient_group': 'trophy', 'default_professions': ('medium_armor', 'blacksmith')},
    'boar_tusk': {'special_ingredient_group': 'trophy', 'default_professions': ('medium_armor', 'blacksmith')},
    'golem_fragment': {'special_ingredient_group': 'monster_part', 'default_professions': ('heavy_armor', 'blacksmith')},
    'goblin_ear': {'special_ingredient_group': 'trophy', 'default_professions': ('alchemy', 'cooking')},
}


BULK_GROUP_BY_GATHER_RESOURCE_FAMILY = {
    'ore': 'ore',
    'fuel': 'fuel',
    'gem': 'gem',
    'wood': 'wood',
    'resin': 'wood',
    'bark': 'wood',
    'herb_common': 'herb_base',
    'herb_magic': 'herb_base',
    'hide': 'hide',
    'meat': 'meat',
    'fish': 'fish',
    'shell': 'fish',
    'plant_fiber': 'fiber',
}

DEFAULT_CRAFT_PROFESSIONS_BY_GATHER_PROFESSION = {
    'herbalism': ('alchemy', 'cooking'),
    'woodcutting': ('arcane_engineer', 'blacksmith'),
    'mining': ('blacksmith', 'heavy_armor'),
    'fishing': ('cooking',),
    'hunting': ('medium_armor', 'cooking'),
}

SPECIAL_INGREDIENT_GROUP_BY_SUBTYPE = {
    'venom': 'venom',
    'core': 'core',
    'heart': 'heart',
    'humanoid_trophy': 'trophy',
    'fang_claw_horn': 'trophy',
    'essence': 'essence',
    'wing': 'monster_part',
    'construct_fragment': 'monster_part',
    'special_part': 'monster_part',
}

BULK_GROUP_BY_SUBTYPE = {
    'ore': 'ore',
    'wood': 'wood',
    'herb': 'herb_base',
    'fuel': 'fuel',
    'hide': 'hide',
    'meat': 'meat',
    'fish': 'fish',
    'gem': 'gem',
    'resin': 'wood',
}


def get_crafting_profession_contract(profession_key: CraftingProfessionKey) -> CraftingProfessionContract:
    return CRAFTING_PROFESSION_CONTRACTS[profession_key]


def resolve_crafting_material_identity(item_id: str) -> CraftMaterialIdentity | None:
    tags = get_item_reward_tags(item_id)
    gather_identity = resolve_gather_resource_identity(item_id)
    explicit = EXPLICIT_CRAFT_IDENTITY_BY_ITEM_ID.get(item_id, {})

    reward_family = str(tags.get('reward_family') or (gather_identity.reward_family if gather_identity else 'crafting_material'))
    material_subtype = str(tags.get('material_subtype') or (gather_identity.resource_family if gather_identity else ''))

    explicit_special_group = explicit.get('special_ingredient_group')
    explicit_bulk_group = explicit.get('bulk_resource_group')
    if explicit_special_group is not None:
        special_group = explicit_special_group
    elif explicit_bulk_group is not None:
        special_group = None
    else:
        special_group = SPECIAL_INGREDIENT_GROUP_BY_SUBTYPE.get(material_subtype)
    bulk_group = explicit_bulk_group
    if bulk_group is None and gather_identity is not None:
        bulk_group = BULK_GROUP_BY_GATHER_RESOURCE_FAMILY.get(gather_identity.resource_family)
    if bulk_group is None:
        bulk_group = BULK_GROUP_BY_SUBTYPE.get(material_subtype)

    origin_channel = _resolve_origin_channel(tags, gather_identity)

    default_professions = tuple(explicit.get('default_professions', ()))
    if not default_professions and gather_identity is not None:
        default_professions = tuple(DEFAULT_CRAFT_PROFESSIONS_BY_GATHER_PROFESSION.get(gather_identity.profession_key, ()))

    if not default_professions and not bulk_group and not special_group:
        return None

    return CraftMaterialIdentity(
        item_id=item_id,
        reward_family=reward_family,
        material_subtype=material_subtype,
        origin_channel=origin_channel,
        bulk_resource_group=bulk_group,
        special_ingredient_group=special_group,
        default_professions=default_professions,
        gather_profession_key=gather_identity.profession_key if gather_identity else None,
        gather_resource_family=gather_identity.resource_family if gather_identity else None,
    )


def _resolve_origin_channel(tags: dict, gather_identity: GatherResourceIdentity | None) -> str:
    reward_family = tags.get('reward_family')
    if gather_identity is not None:
        return 'gathering'
    if reward_family == 'creature_loot':
        return 'creature_loot'
    if reward_family == 'reagent':
        return 'reagent'
    if reward_family == 'enhancement_material':
        return 'enhancement'
    return 'unknown'
