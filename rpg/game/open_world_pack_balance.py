from __future__ import annotations

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
        'solo_mob_ids': ('westwild_rabbit', 'crow', 'forest_boar', 'forest_spider', 'bear', 'goblin_scout'),
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
