"""Enhancement materials routing normalization (Phase 3 foundation).

Small contract only:
- identify enhancement material tier;
- resolve routing status for source category;
- distinguish normal path vs temporary fallback vs disallowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from game.items_data import get_item_reward_tags

EnhancementMaterialTier = Literal[1, 2, 3, 4]
EnhancementRoutingStatus = Literal['normal', 'temporary_fallback', 'disallowed']

ENHANCEMENT_MATERIAL_TIER_BY_ITEM_ID: dict[str, EnhancementMaterialTier] = {
    'enhance_shard': 1,
    'enhancement_crystal': 2,
    'power_essence': 3,
    'ashen_core': 4,
}

# Phase 3 normalized routing identity.
NORMAL_SOURCE_CATEGORIES_BY_TIER: dict[EnhancementMaterialTier, tuple[str, ...]] = {
    # Material 1: universal baseline + elite + quest + lower dungeon feed.
    1: (
        'open_world_normal',
        'open_world_elite',
        'open_world_rare_spawn',
        'open_world_regional_boss',
        'quest_reward',
        'dungeon_trash',
    ),
    # Material 2: elite/open-world bridge + stronger structured sources.
    2: (
        'open_world_elite',
        'open_world_rare_spawn',
        'open_world_regional_boss',
        'dungeon_elite',
        'dungeon_boss',
    ),
    # Material 3: dungeon-primary.
    3: (
        'dungeon_trash',
        'dungeon_elite',
        'dungeon_boss',
    ),
    # Material 4: apex-primary.
    4: (
        'world_boss',
    ),
}

# Explicit temporary bridge for current pre-full-content state.
TEMPORARY_FALLBACK_SOURCE_CATEGORIES_BY_TIER: dict[EnhancementMaterialTier, tuple[str, ...]] = {
    1: (),
    2: ('quest_reward',),
    # Conservative open-world surrogate while full dungeon rollout is incomplete.
    3: ('open_world_elite', 'open_world_rare_spawn', 'open_world_regional_boss'),
    # No easy open-world fallback; dungeon boss bridge only.
    4: ('dungeon_boss',),
}


@dataclass(frozen=True)
class EnhancementMaterialRoutingDecision:
    item_id: str
    tier: EnhancementMaterialTier
    source_category: str
    status: EnhancementRoutingStatus

    @property
    def is_allowed(self) -> bool:
        return self.status in {'normal', 'temporary_fallback'}


def get_enhancement_material_tier(item_id: str) -> EnhancementMaterialTier | None:
    """Resolve enhancement tier by explicit map with tag-based fallback."""
    explicit = ENHANCEMENT_MATERIAL_TIER_BY_ITEM_ID.get(item_id)
    if explicit is not None:
        return explicit

    reward_tags = get_item_reward_tags(item_id)
    if reward_tags.get('reward_family') != 'enhancement_material':
        return None

    subtype = reward_tags.get('material_subtype')
    subtype_to_tier = {
        'material_1': 1,
        'material_2': 2,
        'material_3': 3,
        'material_4': 4,
    }
    resolved = subtype_to_tier.get(subtype)
    return resolved if resolved in {1, 2, 3, 4} else None


def resolve_enhancement_material_routing(
    item_id: str,
    source_category: str,
) -> EnhancementMaterialRoutingDecision | None:
    """Return normalized routing decision for enhancement materials only."""
    tier = get_enhancement_material_tier(item_id)
    if tier is None:
        return None

    if source_category in NORMAL_SOURCE_CATEGORIES_BY_TIER[tier]:
        status: EnhancementRoutingStatus = 'normal'
    elif source_category in TEMPORARY_FALLBACK_SOURCE_CATEGORIES_BY_TIER[tier]:
        status = 'temporary_fallback'
    else:
        status = 'disallowed'

    return EnhancementMaterialRoutingDecision(
        item_id=item_id,
        tier=tier,
        source_category=source_category,
        status=status,
    )
