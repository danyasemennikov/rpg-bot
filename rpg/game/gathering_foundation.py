"""Gathering professions foundation helpers (Phase 5).

Scope intentionally narrow:
- profession contract for gather surfaces;
- resource identity bridge (item -> profession/resource family);
- location gather normalization using existing region/tier hooks;
- foundation-level access checks (profession level + zone tier context).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from game.items_data import get_item_reward_tags
from game.locations import get_location
from game.open_world_reward_pools import resolve_open_world_region_identity
from game.reward_policies import resolve_content_tier_band

GatherProfessionKey = Literal['herbalism', 'woodcutting', 'mining', 'fishing', 'hunting']


@dataclass(frozen=True)
class GatheringProfessionContract:
    profession_key: GatherProfessionKey
    resource_families: tuple[str, ...]
    reward_families: tuple[str, ...]
    base_gather_surface: str
    supplemental_over_creature_loot: bool = False


@dataclass(frozen=True)
class GatherResourceIdentity:
    item_id: str
    profession_key: GatherProfessionKey
    resource_family: str
    reward_family: str
    base_gather_surface: str
    minimum_profession_level: int
    min_zone_tier_band: int
    max_zone_tier_band: int
    is_basic_resource: bool


@dataclass(frozen=True)
class LocationGatherSourceProfile:
    location_id: str
    region_identity: str
    zone_tier_band: int
    item_id: str
    chance: float
    profession_key: GatherProfessionKey
    resource_family: str
    minimum_profession_level: int
    min_zone_tier_band: int
    max_zone_tier_band: int
    is_basic_resource: bool


@dataclass(frozen=True)
class GatherAccessDecision:
    item_id: str
    profession_key: GatherProfessionKey
    required_profession_level: int
    player_profession_level: int
    zone_tier_band: int
    min_zone_tier_band: int
    max_zone_tier_band: int
    zone_allowed: bool
    level_allowed: bool

    @property
    def is_allowed(self) -> bool:
        return self.zone_allowed and self.level_allowed


GATHERING_PROFESSION_CONTRACTS: dict[GatherProfessionKey, GatheringProfessionContract] = {
    'herbalism': GatheringProfessionContract(
        profession_key='herbalism',
        resource_families=('herb_common', 'herb_magic', 'plant_fiber'),
        reward_families=('gathering_material', 'crafting_material'),
        base_gather_surface='open_world_herb_nodes',
    ),
    'woodcutting': GatheringProfessionContract(
        profession_key='woodcutting',
        resource_families=('wood', 'resin', 'bark'),
        reward_families=('gathering_material', 'crafting_material'),
        base_gather_surface='open_world_tree_nodes',
    ),
    'mining': GatheringProfessionContract(
        profession_key='mining',
        resource_families=('ore', 'fuel', 'gem'),
        reward_families=('gathering_material', 'crafting_material'),
        base_gather_surface='open_world_ore_nodes',
    ),
    'fishing': GatheringProfessionContract(
        profession_key='fishing',
        resource_families=('fish', 'shell', 'seaweed'),
        reward_families=('gathering_material', 'crafting_material'),
        base_gather_surface='water_nodes',
    ),
    'hunting': GatheringProfessionContract(
        profession_key='hunting',
        resource_families=('hide', 'meat', 'trophy_parts'),
        reward_families=('creature_loot', 'crafting_material'),
        base_gather_surface='creature_harvest',
        supplemental_over_creature_loot=True,
    ),
}

GATHER_RESOURCE_IDENTITY_BY_ITEM_ID: dict[str, GatherResourceIdentity] = {
    'herb_common': GatherResourceIdentity(
        item_id='herb_common',
        profession_key='herbalism',
        resource_family='herb_common',
        reward_family='gathering_material',
        base_gather_surface='open_world_herb_nodes',
        minimum_profession_level=1,
        min_zone_tier_band=1,
        max_zone_tier_band=3,
        is_basic_resource=True,
    ),
    'herb_magic': GatherResourceIdentity(
        item_id='herb_magic',
        profession_key='herbalism',
        resource_family='herb_magic',
        reward_family='gathering_material',
        base_gather_surface='open_world_herb_nodes',
        minimum_profession_level=8,
        min_zone_tier_band=1,
        max_zone_tier_band=5,
        is_basic_resource=False,
    ),
    'wood_dark': GatherResourceIdentity(
        item_id='wood_dark',
        profession_key='woodcutting',
        resource_family='wood',
        reward_family='gathering_material',
        base_gather_surface='open_world_tree_nodes',
        minimum_profession_level=10,
        min_zone_tier_band=1,
        max_zone_tier_band=5,
        is_basic_resource=False,
    ),
    'iron_ore': GatherResourceIdentity(
        item_id='iron_ore',
        profession_key='mining',
        resource_family='ore',
        reward_family='gathering_material',
        base_gather_surface='open_world_ore_nodes',
        minimum_profession_level=6,
        min_zone_tier_band=1,
        max_zone_tier_band=4,
        is_basic_resource=False,
    ),
    'coal': GatherResourceIdentity(
        item_id='coal',
        profession_key='mining',
        resource_family='fuel',
        reward_family='crafting_material',
        base_gather_surface='open_world_ore_nodes',
        minimum_profession_level=4,
        min_zone_tier_band=1,
        max_zone_tier_band=6,
        is_basic_resource=True,
    ),
    'gem_common': GatherResourceIdentity(
        item_id='gem_common',
        profession_key='mining',
        resource_family='gem',
        reward_family='crafting_material',
        base_gather_surface='open_world_ore_nodes',
        minimum_profession_level=12,
        min_zone_tier_band=1,
        max_zone_tier_band=8,
        is_basic_resource=False,
    ),
    # Creature-harvest explicit bridge for current craft-relevant materials.
    'wolf_pelt': GatherResourceIdentity(
        item_id='wolf_pelt',
        profession_key='hunting',
        resource_family='hide',
        reward_family='creature_loot',
        base_gather_surface='creature_harvest',
        minimum_profession_level=1,
        min_zone_tier_band=1,
        max_zone_tier_band=4,
        is_basic_resource=True,
    ),
    'wolf_fang': GatherResourceIdentity(
        item_id='wolf_fang',
        profession_key='hunting',
        resource_family='trophy_parts',
        reward_family='creature_loot',
        base_gather_surface='creature_harvest',
        minimum_profession_level=2,
        min_zone_tier_band=1,
        max_zone_tier_band=5,
        is_basic_resource=False,
    ),
    'boar_meat': GatherResourceIdentity(
        item_id='boar_meat',
        profession_key='hunting',
        resource_family='meat',
        reward_family='creature_loot',
        base_gather_surface='creature_harvest',
        minimum_profession_level=1,
        min_zone_tier_band=1,
        max_zone_tier_band=4,
        is_basic_resource=True,
    ),
    'boar_tusk': GatherResourceIdentity(
        item_id='boar_tusk',
        profession_key='hunting',
        resource_family='trophy_parts',
        reward_family='creature_loot',
        base_gather_surface='creature_harvest',
        minimum_profession_level=2,
        min_zone_tier_band=1,
        max_zone_tier_band=5,
        is_basic_resource=False,
    ),
    'spider_silk': GatherResourceIdentity(
        item_id='spider_silk',
        profession_key='hunting',
        resource_family='special_part',
        reward_family='creature_loot',
        base_gather_surface='creature_harvest',
        minimum_profession_level=4,
        min_zone_tier_band=1,
        max_zone_tier_band=6,
        is_basic_resource=False,
    ),
    'rat_fur': GatherResourceIdentity(
        item_id='rat_fur',
        profession_key='hunting',
        resource_family='hide',
        reward_family='creature_loot',
        base_gather_surface='creature_harvest',
        minimum_profession_level=1,
        min_zone_tier_band=1,
        max_zone_tier_band=4,
        is_basic_resource=True,
    ),
}

FALLBACK_PROFESSION_BY_MATERIAL_SUBTYPE: dict[str, GatherProfessionKey] = {
    'herb': 'herbalism',
    'wood': 'woodcutting',
    'ore': 'mining',
    'fuel': 'mining',
    'gem': 'mining',
    'fish': 'fishing',
    'hide': 'hunting',
    'meat': 'hunting',
    'fang_claw_horn': 'hunting',
}

DEFAULT_RESOURCE_FAMILY_BY_PROFESSION: dict[GatherProfessionKey, str] = {
    'herbalism': 'herb_common',
    'woodcutting': 'wood',
    'mining': 'ore',
    'fishing': 'fish',
    'hunting': 'trophy_parts',
}


def get_gathering_profession_contract(profession_key: GatherProfessionKey) -> GatheringProfessionContract:
    return GATHERING_PROFESSION_CONTRACTS[profession_key]


def resolve_gather_resource_identity(item_id: str) -> GatherResourceIdentity | None:
    explicit = GATHER_RESOURCE_IDENTITY_BY_ITEM_ID.get(item_id)
    if explicit is not None:
        return explicit

    tags = get_item_reward_tags(item_id)
    profession = FALLBACK_PROFESSION_BY_MATERIAL_SUBTYPE.get(tags.get('material_subtype', ''))
    if profession is None:
        return None

    reward_family = tags.get('reward_family') or 'crafting_material'
    contract = GATHERING_PROFESSION_CONTRACTS[profession]
    return GatherResourceIdentity(
        item_id=item_id,
        profession_key=profession,
        resource_family=tags.get('material_subtype') or DEFAULT_RESOURCE_FAMILY_BY_PROFESSION[profession],
        reward_family=reward_family,
        base_gather_surface=contract.base_gather_surface,
        minimum_profession_level=1,
        min_zone_tier_band=1,
        max_zone_tier_band=10,
        is_basic_resource=True,
    )


def resolve_required_profession_for_resource(item_id: str) -> GatherProfessionKey | None:
    identity = resolve_gather_resource_identity(item_id)
    return identity.profession_key if identity else None


def build_location_gather_source_profiles(location_id: str) -> tuple[LocationGatherSourceProfile, ...]:
    location = get_location(location_id) or {}
    zone_tier_band = resolve_content_tier_band(location.get('level_max', 1))
    region_identity = resolve_open_world_region_identity(location_id)

    profiles: list[LocationGatherSourceProfile] = []
    for raw in location.get('gather', ()):  # tuple[item_id, chance, display_name]
        item_id = raw[0]
        chance = float(raw[1])
        identity = resolve_gather_resource_identity(item_id)
        if identity is None:
            continue
        profiles.append(
            LocationGatherSourceProfile(
                location_id=location_id,
                region_identity=region_identity,
                zone_tier_band=zone_tier_band,
                item_id=item_id,
                chance=chance,
                profession_key=identity.profession_key,
                resource_family=identity.resource_family,
                minimum_profession_level=identity.minimum_profession_level,
                min_zone_tier_band=identity.min_zone_tier_band,
                max_zone_tier_band=identity.max_zone_tier_band,
                is_basic_resource=identity.is_basic_resource,
            )
        )
    return tuple(profiles)


def resolve_gather_access_decision(
    *,
    item_id: str,
    player_profession_level: int,
    zone_tier_band: int,
) -> GatherAccessDecision | None:
    identity = resolve_gather_resource_identity(item_id)
    if identity is None:
        return None

    normalized_zone_tier = max(1, min(10, int(zone_tier_band)))
    zone_allowed = identity.min_zone_tier_band <= normalized_zone_tier <= identity.max_zone_tier_band
    # High-danger zones should not be freely farmed by very low profession levels.
    zone_pressure = max(0, normalized_zone_tier - identity.min_zone_tier_band) * 2
    required_profession_level = identity.minimum_profession_level + zone_pressure
    level_allowed = int(player_profession_level) >= required_profession_level

    return GatherAccessDecision(
        item_id=item_id,
        profession_key=identity.profession_key,
        required_profession_level=required_profession_level,
        player_profession_level=int(player_profession_level),
        zone_tier_band=normalized_zone_tier,
        min_zone_tier_band=identity.min_zone_tier_band,
        max_zone_tier_band=identity.max_zone_tier_band,
        zone_allowed=zone_allowed,
        level_allowed=level_allowed,
    )
