from __future__ import annotations

from game.targeting import normalize_formation_line, resolve_default_enemy_formation_line

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
