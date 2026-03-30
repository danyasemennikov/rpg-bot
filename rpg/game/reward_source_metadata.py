"""Foundation metadata contract for reward sources and reward families.

Phase goal: keep this small/readable and integrate with current reward flow
without broad rewrites.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from game.creature_loot_taxonomy import (
    encounter_class_to_source_category,
    normalize_creature_taxonomy,
    resolve_creature_loot_identity,
)
from game.items_data import get_item, get_item_reward_tags

RewardSourceCategory = Literal[
    'open_world_normal',
    'open_world_elite',
    'open_world_rare_spawn',
    'open_world_regional_boss',
    'dungeon_trash',
    'dungeon_elite',
    'dungeon_boss',
    'world_boss',
    'quest_reward',
    # Placeholder for later-only surfaces.
    'event_reward',
]

RewardFamily = Literal[
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
]

REWARD_FAMILIES_BY_SOURCE: dict[RewardSourceCategory, tuple[RewardFamily, ...]] = {
    'open_world_normal': (
        'base_combat',
        'gear',
        'enhancement_material',
        'creature_loot',
        'crafting_material',
    ),
    'open_world_elite': (
        'base_combat',
        'gear',
        'enhancement_material',
        'creature_loot',
        'crafting_material',
        'reagent',
    ),
    'open_world_rare_spawn': (
        'base_combat',
        'gear',
        'enhancement_material',
        'creature_loot',
        'crafting_material',
        'reagent',
        'recipe',
    ),
    'open_world_regional_boss': (
        'base_combat',
        'gear',
        'enhancement_material',
        'creature_loot',
        'crafting_material',
        'reagent',
        'recipe',
        'prestige_or_apex',
    ),
    'dungeon_trash': (
        'base_combat',
        'gear',
        'enhancement_material',
        'creature_loot',
        'crafting_material',
        'reagent',
    ),
    'dungeon_elite': (
        'base_combat',
        'gear',
        'enhancement_material',
        'creature_loot',
        'crafting_material',
        'reagent',
        'recipe',
    ),
    'dungeon_boss': (
        'base_combat',
        'gear',
        'enhancement_material',
        'creature_loot',
        'crafting_material',
        'reagent',
        'recipe',
        'prestige_or_apex',
    ),
    'world_boss': (
        'base_combat',
        'gear',
        'enhancement_material',
        'creature_loot',
        'reagent',
        'recipe',
        'prestige_or_apex',
    ),
    'quest_reward': (
        'base_combat',
        'gear',
        'enhancement_material',
        'crafting_material',
        'gathering_material',
        'recipe',
        'reagent',
        'quest_tagged',
    ),
    'event_reward': (
        'base_combat',
        'gear',
        'enhancement_material',
        'creature_loot',
        'crafting_material',
        'gathering_material',
        'recipe',
        'reagent',
        'quest_tagged',
        'prestige_or_apex',
    ),
}

DEFAULT_SOURCE_CATEGORY: RewardSourceCategory = 'open_world_normal'
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
) -> RewardSourceMetadata:
    taxonomy = normalize_creature_taxonomy(creature_taxonomy)
    resolved_source_category = source_category
    if resolved_source_category is None:
        resolved_source_category = encounter_class_to_source_category(taxonomy.encounter_class)
    normalized_category = normalize_reward_source_category(resolved_source_category)
    return RewardSourceMetadata(
        source_category=normalized_category,
        content_tier=resolve_content_tier_band(mob_level),
        content_identity=source_id,
        channel_hint='combat',
        creature_body_type=taxonomy.body_type,
        creature_special_trait=taxonomy.special_trait,
        creature_encounter_class=taxonomy.encounter_class,
        creature_loot_identity=resolve_creature_loot_identity(taxonomy),
    )


def resolve_content_tier_band(level: int) -> int:
    """Normalize raw level to 1..10 tier bands: 1-10 => 1, 11-20 => 2 ... 91-100 => 10."""
    normalized_level = max(1, int(level))
    return min(10, ((normalized_level - 1) // 10) + 1)
