"""Dungeon reward framework foundation (Phase 9).

Small contract only:
- structured dungeon reward surfaces (trash / elite / boss);
- explicit dungeon identity hooks;
- bounded tier band + quality floor;
- reward-family allowlist per surface;
- foundation hooks for dungeon recipes / reagents / future set inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from game.reward_policies import REWARD_FAMILIES_BY_SOURCE, resolve_content_tier_band

DungeonSurface = Literal['dungeon_trash', 'dungeon_elite', 'dungeon_boss']
DungeonPayoffRole = Literal[
    'baseline_dungeon_feed',
    'structured_progression_step',
    'primary_dungeon_payoff',
]
DungeonQualityFloor = Literal['common', 'uncommon', 'rare', 'epic', 'legendary']
PowerEssenceRole = Literal['tiny_feed', 'meaningful_layer', 'primary_layer']


DUNGEON_SURFACES: tuple[DungeonSurface, ...] = (
    'dungeon_trash',
    'dungeon_elite',
    'dungeon_boss',
)
DEFAULT_DUNGEON_SURFACE: DungeonSurface = 'dungeon_trash'

DUNGEON_REWARD_PROFILE_ID_BY_SURFACE: dict[DungeonSurface, str] = {
    'dungeon_trash': 'dungeon_trash_surface',
    'dungeon_elite': 'dungeon_elite_surface',
    'dungeon_boss': 'dungeon_boss_surface',
}

DUNGEON_QUALITY_FLOOR_BY_SURFACE: dict[DungeonSurface, DungeonQualityFloor] = {
    'dungeon_trash': 'common',
    'dungeon_elite': 'uncommon',
    'dungeon_boss': 'rare',
}

DUNGEON_PAYOFF_ROLE_BY_SURFACE: dict[DungeonSurface, DungeonPayoffRole] = {
    'dungeon_trash': 'baseline_dungeon_feed',
    'dungeon_elite': 'structured_progression_step',
    'dungeon_boss': 'primary_dungeon_payoff',
}

POWER_ESSENCE_ROLE_BY_SURFACE: dict[DungeonSurface, PowerEssenceRole] = {
    'dungeon_trash': 'tiny_feed',
    'dungeon_elite': 'meaningful_layer',
    'dungeon_boss': 'primary_layer',
}


@dataclass(frozen=True)
class DungeonRewardSurfaceProfile:
    source_category: DungeonSurface
    dungeon_id: str
    encounter_identity: str
    reward_profile_identity: str
    content_tier_band: int
    content_tier_band_min: int
    content_tier_band_max: int
    quality_floor: DungeonQualityFloor
    allowed_reward_families: tuple[str, ...]
    payoff_role: DungeonPayoffRole
    power_essence_role: PowerEssenceRole
    dungeon_recipe_hook_enabled: bool
    dungeon_reagent_hook_enabled: bool
    boss_reagent_hook_enabled: bool
    future_set_crafting_input_hook_enabled: bool


def is_dungeon_surface(surface: str | None) -> bool:
    return surface in DUNGEON_SURFACES


def normalize_dungeon_surface(surface: str | None) -> DungeonSurface:
    if is_dungeon_surface(surface):
        return surface  # type: ignore[return-value]
    return DEFAULT_DUNGEON_SURFACE


def build_dungeon_reward_surface_profile(
    *,
    source_category: str | None,
    dungeon_id: str,
    encounter_identity: str,
    mob_level: int,
) -> DungeonRewardSurfaceProfile:
    typed_surface = normalize_dungeon_surface(source_category)
    tier_band = resolve_content_tier_band(mob_level)
    is_elite = typed_surface == 'dungeon_elite'
    is_boss = typed_surface == 'dungeon_boss'
    return DungeonRewardSurfaceProfile(
        source_category=typed_surface,
        dungeon_id=dungeon_id,
        encounter_identity=encounter_identity,
        reward_profile_identity=DUNGEON_REWARD_PROFILE_ID_BY_SURFACE[typed_surface],
        content_tier_band=tier_band,
        content_tier_band_min=max(1, tier_band - 1),
        content_tier_band_max=min(10, tier_band + 1),
        quality_floor=DUNGEON_QUALITY_FLOOR_BY_SURFACE[typed_surface],
        allowed_reward_families=REWARD_FAMILIES_BY_SOURCE[typed_surface],
        payoff_role=DUNGEON_PAYOFF_ROLE_BY_SURFACE[typed_surface],
        power_essence_role=POWER_ESSENCE_ROLE_BY_SURFACE[typed_surface],
        dungeon_recipe_hook_enabled=is_elite or is_boss,
        dungeon_reagent_hook_enabled=is_elite or is_boss,
        boss_reagent_hook_enabled=is_boss,
        future_set_crafting_input_hook_enabled=is_boss,
    )
