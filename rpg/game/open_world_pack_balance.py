from __future__ import annotations

from game.locations import WORLD_LOCATIONS, WORLD_ROUTES
from game.targeting import normalize_formation_line, resolve_default_enemy_formation_line

ALLOWED_OPEN_WORLD_THREAT_BANDS: tuple[str, ...] = (
    'starter',
    'low',
    'low_mid',
    'mid',
    'mid_high',
    'high',
)

OPEN_WORLD_PACK_ENABLED_MOB_IDS: frozenset[str] = frozenset({
    'forest_wolf',
    'white_wolf',
    'leech',
    'zombie',
})

OPEN_WORLD_MOB_FORMATION_LINE_BY_MOB_ID: dict[str, str] = {
    # core / starter
    'shore_turtle': 'front',
    'forest_boar': 'front',
    'mountain_stone_golem': 'front',
    'temple_guardian': 'front',
    'desert_elephant': 'front',
    'crocodile': 'front',
    # melee
    'forest_wolf': 'melee',
    'white_wolf': 'melee',
    'zombie': 'melee',
    'leech': 'melee',
    'goblin_hunter': 'melee',
    'scorpion': 'melee',
    'drowned': 'melee',
    # ranged
    'goblin_scout': 'ranged',
    'skeleton_mage': 'ranged',
    'fire_elemental': 'ranged',
    'air_elemental': 'ranged',
    # support
    'goblin_shaman': 'support',
    'skeleton_priest': 'support',
    'swamp_witch': 'support',
    'old_witch': 'support',
}

OPEN_WORLD_ROUTE_ENCOUNTER_COMPOSITION: tuple[dict[str, object], ...] = (
    {
        'route_id': 'route_westwild',
        'solo_mob_ids': ('westwild_rabbit', 'crow', 'forest_boar', 'forest_spider', 'bear', 'goblin_scout', 'goblin_shaman'),
        'pack_mob_ids': ('forest_wolf',),
        'elite_anchor_mob_ids': ('goblin_hunter', 'goblin_chief'),
        'rare_anchor_mob_ids': (),
        'threat_band': 'low_mid',
        'encounter_mix_tags': ('forest_wilds', 'beast_pressure', 'goblin_patrols'),
        'content_tier_min': 1,
        'content_tier_max': 10,
    },
    {
        'route_id': 'route_frostspine',
        'solo_mob_ids': ('mountain_rabbit', 'rock_lizard', 'cave_bat', 'stone_beetle', 'troll', 'ice_troll', 'troll_chief'),
        'pack_mob_ids': ('white_wolf',),
        'elite_anchor_mob_ids': ('mountain_stone_golem',),
        'rare_anchor_mob_ids': (),
        'threat_band': 'mid_high',
        'encounter_mix_tags': ('mountain_travel', 'wolf_hunts', 'construct_anchors'),
        'content_tier_min': 2,
        'content_tier_max': 10,
    },
    {
        'route_id': 'route_ashen_ruins',
        'solo_mob_ids': ('skeleton_warrior', 'skeleton_mage', 'ghost', 'skeleton_guard', 'cursed_knight', 'skeleton_priest'),
        'pack_mob_ids': ('zombie',),
        'elite_anchor_mob_ids': ('temple_guardian',),
        'rare_anchor_mob_ids': (),
        'threat_band': 'mid',
        'encounter_mix_tags': ('ruins_undead', 'attrition_frontline'),
        'content_tier_min': 3,
        'content_tier_max': 10,
    },
    {
        'route_id': 'route_sunscar',
        'solo_mob_ids': ('desert_beetle', 'desert_lizard', 'scavenger', 'scorpion', 'snake', 'crocodile', 'desert_elephant', 'fire_elemental', 'earth_elemental', 'air_elemental'),
        'pack_mob_ids': (),
        'elite_anchor_mob_ids': ('air_elemental',),
        'rare_anchor_mob_ids': (),
        'threat_band': 'mid_high',
        'encounter_mix_tags': ('desert_badlands', 'elemental_hotspots'),
        'content_tier_min': 3,
        'content_tier_max': 10,
    },
    {
        'route_id': 'route_mireveil',
        'solo_mob_ids': ('swamp_toad', 'water_snake', 'swamp_spider', 'giant_leech', 'slug', 'toxic_slime', 'swamp_witch', 'old_witch'),
        'pack_mob_ids': ('leech',),
        'elite_anchor_mob_ids': ('drowned',),
        'rare_anchor_mob_ids': (),
        'threat_band': 'mid_high',
        'encounter_mix_tags': ('swamp_attrition', 'wetland_predators'),
        'content_tier_min': 3,
        'content_tier_max': 10,
    },
    {
        'route_id': 'route_south_coast_stub',
        'solo_mob_ids': ('shore_crab', 'seagull', 'shore_turtle'),
        'pack_mob_ids': (),
        'elite_anchor_mob_ids': (),
        'rare_anchor_mob_ids': (),
        'threat_band': 'starter',
        'encounter_mix_tags': ('coast_stub', 'sparse_content'),
        'content_tier_min': 1,
        'content_tier_max': 3,
    },
    {
        'route_id': 'route_old_mine_stub',
        'solo_mob_ids': ('mine_rat', 'cave_bat'),
        'pack_mob_ids': (),
        'elite_anchor_mob_ids': (),
        'rare_anchor_mob_ids': (),
        'threat_band': 'low',
        'encounter_mix_tags': ('mine_stub', 'sparse_content'),
        'content_tier_min': 1,
        'content_tier_max': 4,
    },
)

OPEN_WORLD_PACK_ARCHETYPES_BY_MOB_ID: dict[str, dict[str, object]] = {
    'forest_wolf': {
        'pack_archetype_id': 'beast_pack',
        'expected_size_min': 2,
        'expected_size_max': 4,
        'role_mix_hint': ('melee_pressure',),
        'threat_band': 'low',
    },
    'white_wolf': {
        'pack_archetype_id': 'beast_pack',
        'expected_size_min': 2,
        'expected_size_max': 4,
        'role_mix_hint': ('melee_pressure',),
        'threat_band': 'low_mid',
    },
    'zombie': {
        'pack_archetype_id': 'undead_cluster',
        'expected_size_min': 2,
        'expected_size_max': 4,
        'role_mix_hint': ('attrition_melee',),
        'threat_band': 'mid',
    },
    'leech': {
        'pack_archetype_id': 'swamp_predators',
        'expected_size_min': 2,
        'expected_size_max': 4,
        'role_mix_hint': ('swarm_attrition',),
        'threat_band': 'mid',
    },
    'goblin_hunter': {
        'pack_archetype_id': 'goblin_patrol',
        'expected_size_min': 1,
        'expected_size_max': 3,
        'role_mix_hint': ('melee_skirmisher', 'future_mixed_with_ranged_support'),
        'threat_band': 'mid',
    },
    'mountain_stone_golem': {
        'pack_archetype_id': 'construct_cluster',
        'expected_size_min': 1,
        'expected_size_max': 2,
        'role_mix_hint': ('frontline_blocker',),
        'threat_band': 'high',
    },
}


def resolve_enemy_formation_line_for_mob(mob_id: str, *, formation_line: str | None = None, fallback: str | None = None) -> str:
    normalized_explicit = normalize_formation_line(formation_line)
    if normalized_explicit:
        return normalized_explicit

    mapped_line = OPEN_WORLD_MOB_FORMATION_LINE_BY_MOB_ID.get(str(mob_id or '').strip())
    if mapped_line:
        return resolve_default_enemy_formation_line(formation_line=mapped_line)

    return resolve_default_enemy_formation_line(formation_line=fallback)


def get_open_world_pack_archetype_metadata(mob_id: str) -> dict[str, object]:
    metadata = OPEN_WORLD_PACK_ARCHETYPES_BY_MOB_ID.get(str(mob_id or '').strip())
    if not metadata:
        return {}
    return dict(metadata)


def get_pack_enabled_mob_ids() -> frozenset[str]:
    return OPEN_WORLD_PACK_ENABLED_MOB_IDS


def is_open_world_pack_enabled_mob(mob_id: str) -> bool:
    return str(mob_id or '').strip() in OPEN_WORLD_PACK_ENABLED_MOB_IDS


def get_open_world_route_encounter_compositions() -> tuple[dict[str, object], ...]:
    return tuple(dict(entry) for entry in OPEN_WORLD_ROUTE_ENCOUNTER_COMPOSITION)


def get_open_world_route_composition_by_route_id(route_id: str) -> dict[str, object]:
    normalized_route_id = str(route_id or '').strip()
    for entry in OPEN_WORLD_ROUTE_ENCOUNTER_COMPOSITION:
        if str(entry.get('route_id') or '').strip() == normalized_route_id:
            return dict(entry)
    return {}


def collect_open_world_route_mob_ids(route_id: str) -> set[str]:
    composition = get_open_world_route_composition_by_route_id(route_id)
    if not composition:
        return set()
    mob_ids: set[str] = set()
    for key in ('solo_mob_ids', 'pack_mob_ids', 'elite_anchor_mob_ids', 'rare_anchor_mob_ids'):
        for mob_id in composition.get(key, ()) or ():
            normalized_mob_id = str(mob_id or '').strip()
            if normalized_mob_id:
                mob_ids.add(normalized_mob_id)
    return mob_ids


def classify_open_world_route_mob_role(route_id: str, mob_id: str) -> str:
    composition = get_open_world_route_composition_by_route_id(route_id)
    if not composition:
        return 'unknown'
    normalized_mob_id = str(mob_id or '').strip()
    for key, role in (
        ('elite_anchor_mob_ids', 'elite_anchor'),
        ('rare_anchor_mob_ids', 'rare_anchor'),
        ('pack_mob_ids', 'pack'),
        ('solo_mob_ids', 'solo'),
    ):
        if normalized_mob_id in set(composition.get(key, ()) or ()):
            return role
    return 'unknown'


def get_expected_spawn_profile_for_route_mob(route_id: str, mob_id: str) -> str:
    role = classify_open_world_route_mob_role(route_id, mob_id)
    if role in ('solo', 'pack'):
        return 'normal'
    if role == 'elite_anchor':
        return 'elite'
    if role == 'rare_anchor':
        return 'rare'
    return 'normal'


def get_world_location_ids_by_route_id(route_id: str) -> tuple[str, ...]:
    normalized_route_id = str(route_id or '').strip()
    location_ids = sorted(
        location_id
        for location_id, location in WORLD_LOCATIONS.items()
        if str(location.get('route_id') or '').strip() == normalized_route_id
    )
    return tuple(location_ids)


def validate_open_world_spawn_profile_placement() -> list[str]:
    from game.open_world_reward_alignment import (
        ALLOWED_OPEN_WORLD_REWARD_CATEGORIES,
        OPEN_WORLD_SPAWN_PROFILE_TO_REWARD_CATEGORY,
        get_open_world_reward_category_for_spawn_profile,
    )

    errors: list[str] = []
    known_profiles = {'normal', 'elite', 'rare'}
    for canonical_profile in sorted(known_profiles):
        if canonical_profile not in OPEN_WORLD_SPAWN_PROFILE_TO_REWARD_CATEGORY:
            errors.append(f'missing explicit reward alignment for spawn profile {canonical_profile}')

    for route_id in WORLD_ROUTES:
        if route_id == 'core':
            continue
        if not get_world_location_ids_by_route_id(route_id):
            errors.append(f'route has no mapped world locations: {route_id}')

    for location_id, location in WORLD_LOCATIONS.items():
        for mob_id, profiles in (location.get('world_spawn_profiles') or {}).items():
            for profile in (profiles or {}):
                normalized_profile = str(profile or '').strip().lower()
                if normalized_profile not in known_profiles:
                    errors.append(f'unknown world spawn profile key {profile} at {location_id}:{mob_id}')
                    continue
                if normalized_profile not in OPEN_WORLD_SPAWN_PROFILE_TO_REWARD_CATEGORY:
                    errors.append(f'missing explicit reward alignment for discovered spawn profile {normalized_profile}')
                    continue
                explicit_category = OPEN_WORLD_SPAWN_PROFILE_TO_REWARD_CATEGORY.get(normalized_profile)
                if explicit_category not in ALLOWED_OPEN_WORLD_REWARD_CATEGORIES:
                    errors.append(
                        f'unknown reward category {explicit_category} in explicit alignment for spawn profile {normalized_profile}'
                    )
                resolved_category = get_open_world_reward_category_for_spawn_profile(normalized_profile)
                if resolved_category != explicit_category:
                    errors.append(
                        f'resolved reward category {resolved_category} mismatches explicit mapping {explicit_category} '
                        f'for spawn profile {normalized_profile}'
                    )

    for composition in OPEN_WORLD_ROUTE_ENCOUNTER_COMPOSITION:
        route_id = str(composition.get('route_id') or '').strip()
        route_locations = get_world_location_ids_by_route_id(route_id)
        route_spawn_profiles: dict[str, set[str]] = {}
        route_live_mobs: set[str] = set()
        for location_id in route_locations:
            location = WORLD_LOCATIONS.get(location_id, {})
            route_live_mobs.update(str(mob_id) for mob_id in location.get('mobs', []) if str(mob_id).strip())
            for mapped_mob_id, profiles in (location.get('world_spawn_profiles') or {}).items():
                normalized_mob_id = str(mapped_mob_id or '').strip()
                if not normalized_mob_id:
                    continue
                route_spawn_profiles.setdefault(normalized_mob_id, set()).update(
                    str(profile or '').strip().lower()
                    for profile in (profiles or {})
                    if str(profile or '').strip()
                )

        composition_mobs = collect_open_world_route_mob_ids(route_id)
        route_spawn_mobs = {mob_id for mob_id in route_spawn_profiles if str(mob_id or '').strip()}
        route_live_all = route_live_mobs | route_spawn_mobs

        for mob_id in composition_mobs:
            if mob_id not in route_live_mobs:
                errors.append(f'route composition mob {mob_id} is missing from route live content {route_id}')

        for mob_id in route_live_all:
            if mob_id not in composition_mobs:
                errors.append(f'route live mob {mob_id} is missing from route composition {route_id}')

        for pack_mob_id in composition.get('pack_mob_ids', ()) or ():
            normalized_mob_id = str(pack_mob_id or '').strip()
            if not is_open_world_pack_enabled_mob(normalized_mob_id):
                errors.append(f'route pack mob is not pack-enabled: {route_id}:{normalized_mob_id}')
            if not get_open_world_pack_archetype_metadata(normalized_mob_id):
                errors.append(f'route pack mob has no archetype metadata: {route_id}:{normalized_mob_id}')
            profiles = route_spawn_profiles.get(normalized_mob_id, set())
            if profiles and 'normal' not in profiles:
                errors.append(f'route pack mob lacks normal profile: {route_id}:{normalized_mob_id}:{sorted(profiles)}')

        for elite_mob_id in composition.get('elite_anchor_mob_ids', ()) or ():
            normalized_mob_id = str(elite_mob_id or '').strip()
            profiles = route_spawn_profiles.get(normalized_mob_id, set())
            if profiles and 'rare' in profiles and 'elite' not in profiles:
                errors.append(f'elite anchor is rare-only in route placement: {route_id}:{normalized_mob_id}:{sorted(profiles)}')

        for rare_mob_id in composition.get('rare_anchor_mob_ids', ()) or ():
            normalized_mob_id = str(rare_mob_id or '').strip()
            profiles = route_spawn_profiles.get(normalized_mob_id, set())
            if profiles and 'rare' not in profiles:
                errors.append(f'rare anchor lacks rare profile in route placement: {route_id}:{normalized_mob_id}:{sorted(profiles)}')

    return errors
