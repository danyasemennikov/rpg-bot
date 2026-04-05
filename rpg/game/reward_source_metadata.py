"""Foundation metadata contract for reward sources and reward families.

Phase goal: keep this small/readable and integrate with current reward flow
without broad rewrites.
"""

from __future__ import annotations

from dataclasses import dataclass

from game.creature_loot_taxonomy import (
    encounter_class_to_source_category,
    normalize_creature_taxonomy,
    resolve_creature_loot_identity,
)
from game.dungeon_reward_framework import (
    build_dungeon_reward_surface_profile,
    normalize_dungeon_surface,
)
from game.items_data import get_item, get_item_reward_tags
from game.open_world_reward_pools import build_open_world_reward_pool_profile
from game.reward_policies import (
    DEFAULT_SOURCE_CATEGORY,
    REWARD_FAMILIES_BY_SOURCE,
    RewardFamily,
    RewardSourceCategory,
    resolve_content_tier_band,
)
ENHANCEMENT_MATERIAL_IDS = {
    'enhance_shard',
    'enhancement_crystal',
    'power_essence',
    'ashen_core',
}


@dataclass(frozen=True)
class RewardSourceMetadata:
    source_category: RewardSourceCategory
    content_tier: int
    content_identity: str
    channel_hint: str = 'combat'
    creature_body_type: str | None = None
    creature_special_trait: str | None = None
    creature_encounter_class: str | None = None
    creature_loot_identity: tuple[str, ...] = ()
    open_world_pool_profile: str | None = None
    open_world_region_identity: str | None = None
    dungeon_id: str | None = None
    dungeon_encounter_identity: str | None = None
    dungeon_reward_profile_identity: str | None = None
    dungeon_payoff_role: str | None = None
    power_essence_role: str | None = None
    dungeon_recipe_hook_enabled: bool = False
    dungeon_reagent_hook_enabled: bool = False
    boss_reagent_hook_enabled: bool = False
    future_set_crafting_input_hook_enabled: bool = False
    quality_floor_rarity: str | None = None
    content_tier_band_min: int | None = None
    content_tier_band_max: int | None = None


def normalize_reward_source_category(category: str | None) -> RewardSourceCategory:
    """Normalize raw source category with a safe fallback.

    Fallback prevents typo-driven empty allowlists from silently disabling loot.
    """
    if isinstance(category, str) and category in REWARD_FAMILIES_BY_SOURCE:
        return category  # type: ignore[return-value]
    return DEFAULT_SOURCE_CATEGORY


def resolve_allowed_reward_families(meta: RewardSourceMetadata) -> tuple[RewardFamily, ...]:
    normalized = normalize_reward_source_category(meta.source_category)
    return REWARD_FAMILIES_BY_SOURCE[normalized]


def classify_item_reward_family(item_id: str) -> RewardFamily:
    item = get_item(item_id)
    if item is None:
        # Keep unknown IDs permissive for legacy compatibility.
        return 'crafting_material'

    explicit_tags = get_item_reward_tags(item_id)
    explicit_family = explicit_tags.get('reward_family')
    if explicit_family in (
        'base_combat',
        'gear',
        'enhancement_material',
        'creature_loot',
        'gathering_material',
        'crafting_material',
        'recipe',
        'reagent',
        'quest_tagged',
        'prestige_or_apex',
    ):
        return explicit_family

    if item.get('item_type') in ('weapon', 'armor', 'accessory'):
        return 'gear'

    if item_id in ENHANCEMENT_MATERIAL_IDS:
        return 'enhancement_material'

    if item.get('item_type') == 'material':
        if item_id.startswith('herb_') or item_id.startswith('wood_'):
            return 'gathering_material'
        if item_id.endswith('_recipe') or item_id.startswith('recipe_'):
            return 'recipe'
        if item_id.endswith('_reagent') or item_id.startswith('reagent_'):
            return 'reagent'
        return 'creature_loot'

    return 'base_combat'


def is_reward_family_allowed_for_source(meta: RewardSourceMetadata, reward_family: RewardFamily) -> bool:
    return reward_family in resolve_allowed_reward_families(meta)


def build_open_world_combat_source_metadata(
    *,
    source_id: str,
    mob_level: int,
    source_category: str | None = DEFAULT_SOURCE_CATEGORY,
    creature_taxonomy: dict | None = None,
    location_id: str | None = None,
) -> RewardSourceMetadata:
    taxonomy = normalize_creature_taxonomy(creature_taxonomy)
    resolved_source_category = source_category
    if resolved_source_category is None:
        resolved_source_category = encounter_class_to_source_category(taxonomy.encounter_class)
    normalized_category = normalize_reward_source_category(resolved_source_category)
    open_world_profile = build_open_world_reward_pool_profile(
        source_category=normalized_category,
        source_id=source_id,
        mob_level=mob_level,
        location_id=location_id,
    )
    return RewardSourceMetadata(
        source_category=normalized_category,
        content_tier=resolve_content_tier_band(mob_level),
        content_identity=source_id,
        channel_hint='combat',
        creature_body_type=taxonomy.body_type,
        creature_special_trait=taxonomy.special_trait,
        creature_encounter_class=taxonomy.encounter_class,
        creature_loot_identity=resolve_creature_loot_identity(taxonomy),
        open_world_pool_profile=open_world_profile.reward_pool_profile if open_world_profile else None,
        open_world_region_identity=open_world_profile.region_identity if open_world_profile else None,
        quality_floor_rarity=open_world_profile.quality_floor if open_world_profile else None,
        content_tier_band_min=open_world_profile.content_tier_band_min if open_world_profile else None,
        content_tier_band_max=open_world_profile.content_tier_band_max if open_world_profile else None,
    )


def build_dungeon_combat_source_metadata(
    *,
    dungeon_id: str,
    encounter_identity: str,
    mob_level: int,
    source_category: str,
    creature_taxonomy: dict | None = None,
) -> RewardSourceMetadata:
    taxonomy = normalize_creature_taxonomy(creature_taxonomy)
    normalized_surface = normalize_dungeon_surface(source_category)
    profile = build_dungeon_reward_surface_profile(
        source_category=normalized_surface,
        dungeon_id=dungeon_id,
        encounter_identity=encounter_identity,
        mob_level=mob_level,
    )

    return RewardSourceMetadata(
        source_category=profile.source_category,
        content_tier=profile.content_tier_band,
        content_identity=encounter_identity,
        channel_hint='combat',
        creature_body_type=taxonomy.body_type,
        creature_special_trait=taxonomy.special_trait,
        creature_encounter_class=taxonomy.encounter_class,
        creature_loot_identity=resolve_creature_loot_identity(taxonomy),
        dungeon_id=profile.dungeon_id,
        dungeon_encounter_identity=profile.encounter_identity,
        dungeon_reward_profile_identity=profile.reward_profile_identity,
        dungeon_payoff_role=profile.payoff_role,
        power_essence_role=profile.power_essence_role,
        dungeon_recipe_hook_enabled=profile.dungeon_recipe_hook_enabled,
        dungeon_reagent_hook_enabled=profile.dungeon_reagent_hook_enabled,
        boss_reagent_hook_enabled=profile.boss_reagent_hook_enabled,
        future_set_crafting_input_hook_enabled=profile.future_set_crafting_input_hook_enabled,
        quality_floor_rarity=profile.quality_floor,
        content_tier_band_min=profile.content_tier_band_min,
        content_tier_band_max=profile.content_tier_band_max,
    )
