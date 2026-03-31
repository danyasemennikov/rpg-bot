"""Open-world reward pools foundation (Phase 4).

Small contract that gives open-world sources a concrete reward pool profile:
- source surface identity (normal / elite / rare spawn / regional boss)
- bounded tier band
- bounded content identity (region + source identity)
- quality floor by source difficulty
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from game.items_data import get_item
from game.mobs import MOBS
from game.reward_policies import REWARD_FAMILIES_BY_SOURCE, resolve_content_tier_band

OpenWorldSourceCategory = Literal[
    'open_world_normal',
    'open_world_elite',
    'open_world_rare_spawn',
    'open_world_regional_boss',
]
OpenWorldQualityFloor = Literal['common', 'uncommon', 'rare', 'epic', 'legendary']

OPEN_WORLD_SOURCE_CATEGORIES: tuple[OpenWorldSourceCategory, ...] = (
    'open_world_normal',
    'open_world_elite',
    'open_world_rare_spawn',
    'open_world_regional_boss',
)

RARITY_ORDER: tuple[OpenWorldQualityFloor, ...] = (
    'common',
    'uncommon',
    'rare',
    'epic',
    'legendary',
)
RARITY_INDEX = {rarity: idx for idx, rarity in enumerate(RARITY_ORDER)}

OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY: dict[OpenWorldSourceCategory, str] = {
    'open_world_normal': 'open_world_normal_surface',
    'open_world_elite': 'open_world_elite_surface',
    'open_world_rare_spawn': 'open_world_rare_spawn_surface',
    'open_world_regional_boss': 'open_world_regional_boss_surface',
}

OPEN_WORLD_QUALITY_FLOOR_BY_SOURCE_CATEGORY: dict[OpenWorldSourceCategory, OpenWorldQualityFloor] = {
    'open_world_normal': 'common',
    'open_world_elite': 'uncommon',
    'open_world_rare_spawn': 'rare',
    'open_world_regional_boss': 'epic',
}

@dataclass(frozen=True)
class OpenWorldRewardPoolProfile:
    source_category: OpenWorldSourceCategory
    reward_pool_profile: str
    content_identity: str
    region_identity: str
    content_tier_band: int
    content_tier_band_min: int
    content_tier_band_max: int
    quality_floor: OpenWorldQualityFloor
    allowed_reward_families: tuple[str, ...]


def is_open_world_source_category(category: str | None) -> bool:
    return category in OPEN_WORLD_SOURCE_CATEGORIES

def resolve_open_world_region_identity(location_id: str | None) -> str:
    if isinstance(location_id, str) and location_id:
        return location_id
    return 'open_world_unknown_region'


def build_open_world_reward_pool_profile(
    *,
    source_category: str,
    source_id: str,
    mob_level: int,
    location_id: str | None,
) -> OpenWorldRewardPoolProfile | None:
    if not is_open_world_source_category(source_category):
        return None

    typed_category: OpenWorldSourceCategory = source_category  # type: ignore[assignment]
    tier_band = resolve_content_tier_band(mob_level)
    return OpenWorldRewardPoolProfile(
        source_category=typed_category,
        reward_pool_profile=OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY[typed_category],
        content_identity=source_id,
        region_identity=resolve_open_world_region_identity(location_id),
        content_tier_band=tier_band,
        content_tier_band_min=max(1, tier_band - 1),
        content_tier_band_max=min(10, tier_band + 1),
        quality_floor=OPEN_WORLD_QUALITY_FLOOR_BY_SOURCE_CATEGORY[typed_category],
        allowed_reward_families=REWARD_FAMILIES_BY_SOURCE[typed_category],
    )


def clamp_rarity_to_quality_floor(rarity: str, quality_floor: OpenWorldQualityFloor | str | None) -> str:
    if rarity not in RARITY_INDEX:
        rarity = 'common'
    if quality_floor not in RARITY_INDEX:
        return rarity
    if RARITY_INDEX[rarity] >= RARITY_INDEX[quality_floor]:
        return rarity
    return str(quality_floor)


def is_item_tier_band_allowed_for_open_world_profile(*, item_level: int, profile: OpenWorldRewardPoolProfile) -> bool:
    item_tier_band = resolve_content_tier_band(max(1, int(item_level)))
    return profile.content_tier_band_min <= item_tier_band <= profile.content_tier_band_max


def is_item_tier_band_allowed_for_bounds(*, item_level: int, tier_band_min: int, tier_band_max: int) -> bool:
    item_tier_band = resolve_content_tier_band(max(1, int(item_level)))
    return max(1, tier_band_min) <= item_tier_band <= min(10, tier_band_max)


def is_gear_item_allowed_for_open_world_content_identity(*, item_id: str, source_id: str) -> bool:
    source_mob = MOBS.get(source_id)
    if not source_mob:
        return True
    gear_ids = {loot_item_id for loot_item_id, _chance in source_mob.get('loot_table', ()) if _is_gear_item_id(loot_item_id)}
    if not gear_ids:
        return False
    return item_id in gear_ids


def _is_gear_item_id(item_id: str) -> bool:
    item = get_item(item_id) or {}
    return item.get('item_type') in {'weapon', 'armor', 'accessory'}
