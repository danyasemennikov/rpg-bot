"""Shared reward policy constants/helpers.

Phase 4 cleanup goal:
- keep source category family policy in one place;
- keep content tier band mapping in one place.
"""

from __future__ import annotations

from typing import Literal

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


def resolve_content_tier_band(level: int) -> int:
    """Normalize raw level to 1..10 tier bands: 1-10 => 1, 11-20 => 2 ... 91-100 => 10."""
    normalized_level = max(1, int(level))
    return min(10, ((normalized_level - 1) // 10) + 1)
