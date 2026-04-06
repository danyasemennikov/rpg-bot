"""Regional/world scaffolding helpers (Phase 10).

Additive world identity contract for open-world content:
- explicit world/region/zone identities;
- zone role + encounter role normalization;
- future linkage hooks (dungeon bridge / world-boss governance / PvP rulesets);
- region flavor tags reusable by reward/gather/crafting foundations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from game.creature_loot_taxonomy import normalize_creature_taxonomy
from game.locations import get_location

ZoneRole = Literal['normal', 'elite', 'rare_spawn', 'regional_boss']
EncounterRole = Literal['normal', 'elite', 'rare_spawn', 'regional_boss']

ZONE_ROLES: tuple[ZoneRole, ...] = ('normal', 'elite', 'rare_spawn', 'regional_boss')
ENCOUNTER_ROLES: tuple[EncounterRole, ...] = ('normal', 'elite', 'rare_spawn', 'regional_boss')
DEFAULT_WORLD_ID = 'ashen_continent'
DEFAULT_ZONE_ROLE: ZoneRole = 'normal'
DEFAULT_ENCOUNTER_ROLE: EncounterRole = 'normal'

ENCOUNTER_ROLE_BY_SOURCE_CATEGORY = {
    'open_world_normal': 'normal',
    'open_world_elite': 'elite',
    'open_world_rare_spawn': 'rare_spawn',
    'open_world_regional_boss': 'regional_boss',
}

ENCOUNTER_ROLE_BY_TAXONOMY_CLASS = {
    'normal': 'normal',
    'elite': 'elite',
    'boss': 'regional_boss',
    'world_boss': 'regional_boss',
    'quest_target': 'normal',
}

ZONE_ROLE_PRIORITY: dict[ZoneRole, int] = {
    'normal': 1,
    'elite': 2,
    'rare_spawn': 3,
    'regional_boss': 4,
}


@dataclass(frozen=True)
class OpenWorldRegionIdentity:
    world_id: str
    macro_region_identity: str | None
    region_identity: str
    zone_identity: str
    zone_role: ZoneRole
    encounter_role: EncounterRole
    region_flavor_tags: tuple[str, ...]
    linked_dungeon_id: str | None = None
    world_boss_governance_id: str | None = None
    future_pvp_ruleset_id: str | None = None


def normalize_zone_role(value: str | None) -> ZoneRole:
    if value in ZONE_ROLES:
        return value  # type: ignore[return-value]
    return DEFAULT_ZONE_ROLE


def normalize_encounter_role(value: str | None) -> EncounterRole:
    if value in ENCOUNTER_ROLES:
        return value  # type: ignore[return-value]
    return DEFAULT_ENCOUNTER_ROLE


def resolve_open_world_encounter_role(
    *,
    source_category: str | None = None,
    creature_taxonomy: dict | None = None,
    explicit_encounter_role: str | None = None,
) -> EncounterRole:
    if explicit_encounter_role is not None:
        return normalize_encounter_role(explicit_encounter_role)

    if source_category in ENCOUNTER_ROLE_BY_SOURCE_CATEGORY:
        return normalize_encounter_role(ENCOUNTER_ROLE_BY_SOURCE_CATEGORY[source_category])

    taxonomy = normalize_creature_taxonomy(creature_taxonomy)
    return normalize_encounter_role(ENCOUNTER_ROLE_BY_TAXONOMY_CLASS.get(taxonomy.encounter_class))


def resolve_open_world_region_identity(
    *,
    location_id: str | None,
    source_category: str | None = None,
    creature_taxonomy: dict | None = None,
    explicit_encounter_role: str | None = None,
) -> OpenWorldRegionIdentity:
    location = get_location(location_id or '') or {}

    zone_role_from_location = normalize_zone_role(location.get('zone_role'))
    encounter_role = resolve_open_world_encounter_role(
        source_category=source_category,
        creature_taxonomy=creature_taxonomy,
        explicit_encounter_role=explicit_encounter_role,
    )
    encounter_role_as_zone = normalize_zone_role(encounter_role)
    chosen_zone_role = zone_role_from_location
    if ZONE_ROLE_PRIORITY[encounter_role_as_zone] > ZONE_ROLE_PRIORITY[chosen_zone_role]:
        chosen_zone_role = encounter_role_as_zone

    world_id = str(location.get('world_id') or DEFAULT_WORLD_ID)
    macro_region_raw = location.get('macro_region_id')
    macro_region_identity = str(macro_region_raw) if isinstance(macro_region_raw, str) and macro_region_raw else None
    region_identity = str(location.get('region_id') or location_id or 'open_world_unknown_region')
    zone_identity = str(location.get('zone_id') or location.get('id') or location_id or region_identity)
    region_flavor_tags = tuple(str(tag) for tag in location.get('region_flavor_tags', ()) if isinstance(tag, str))

    return OpenWorldRegionIdentity(
        world_id=world_id,
        macro_region_identity=macro_region_identity,
        region_identity=region_identity,
        zone_identity=zone_identity,
        zone_role=chosen_zone_role,
        encounter_role=encounter_role,
        region_flavor_tags=region_flavor_tags,
        linked_dungeon_id=location.get('linked_dungeon_id'),
        world_boss_governance_id=location.get('world_boss_governance_id'),
        future_pvp_ruleset_id=location.get('future_pvp_ruleset_id'),
    )
