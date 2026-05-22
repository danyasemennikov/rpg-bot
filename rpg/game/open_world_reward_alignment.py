from __future__ import annotations

from game.open_world_pack_balance import (
    ALLOWED_OPEN_WORLD_THREAT_BANDS,
    get_open_world_pack_archetype_metadata,
)
from game.reward_policies import REWARD_FAMILIES_BY_SOURCE
from game.reward_source_metadata import OPEN_WORLD_SOURCE_CATEGORY_BY_SPAWN_PROFILE

ALLOWED_OPEN_WORLD_REWARD_CATEGORIES: tuple[str, ...] = tuple(
    category
    for category in (
        'open_world_normal',
        'open_world_elite',
        'open_world_rare_spawn',
        'open_world_regional_boss',
    )
    if category in REWARD_FAMILIES_BY_SOURCE
)

OPEN_WORLD_SPAWN_PROFILE_TO_REWARD_CATEGORY: dict[str, str] = {
    str(spawn_profile): str(category)
    for spawn_profile, category in OPEN_WORLD_SOURCE_CATEGORY_BY_SPAWN_PROFILE.items()
}

OPEN_WORLD_THREAT_BAND_TO_REWARD_PROFILE: dict[str, dict[str, str]] = {
    'starter': {
        'reward_category': 'open_world_normal',
        'reward_profile_id': 'starter_normal_surface',
    },
    'low': {
        'reward_category': 'open_world_normal',
        'reward_profile_id': 'low_normal_surface',
    },
    'low_mid': {
        'reward_category': 'open_world_normal',
        'reward_profile_id': 'low_mid_normal_surface',
    },
    'mid': {
        'reward_category': 'open_world_normal',
        'reward_profile_id': 'mid_normal_elite_capable_surface',
    },
    'mid_high': {
        'reward_category': 'open_world_elite',
        'reward_profile_id': 'mid_high_elite_capable_surface',
    },
    'high': {
        'reward_category': 'open_world_rare_spawn',
        'reward_profile_id': 'high_elite_rare_capable_surface',
    },
}


def get_open_world_reward_category_for_spawn_profile(spawn_profile: object) -> str:
    normalized = str(spawn_profile or '').strip().lower()
    return OPEN_WORLD_SPAWN_PROFILE_TO_REWARD_CATEGORY.get(normalized, 'open_world_normal')


def get_open_world_reward_profile_for_threat_band(threat_band: object) -> dict[str, str]:
    normalized = str(threat_band or '').strip().lower()
    return dict(OPEN_WORLD_THREAT_BAND_TO_REWARD_PROFILE.get(normalized, OPEN_WORLD_THREAT_BAND_TO_REWARD_PROFILE['starter']))


def get_open_world_pack_reward_alignment(mob_id: str) -> dict[str, object]:
    pack = get_open_world_pack_archetype_metadata(mob_id)
    if not pack:
        return {}
    threat_band = str(pack.get('threat_band') or '').strip().lower()
    threat_profile = get_open_world_reward_profile_for_threat_band(threat_band)
    return {
        'mob_id': str(mob_id or '').strip(),
        'pack_archetype_id': pack.get('pack_archetype_id'),
        'threat_band': threat_band,
        'reward_category': threat_profile.get('reward_category'),
        'reward_profile_id': threat_profile.get('reward_profile_id'),
        'expected_size_min': int(pack.get('expected_size_min', 0)),
        'expected_size_max': int(pack.get('expected_size_max', 0)),
    }


def validate_open_world_reward_alignment_metadata() -> list[str]:
    errors: list[str] = []
    for band in ALLOWED_OPEN_WORLD_THREAT_BANDS:
        profile = OPEN_WORLD_THREAT_BAND_TO_REWARD_PROFILE.get(band)
        if not profile:
            errors.append(f'missing threat band profile: {band}')
            continue
        category = profile.get('reward_category')
        if category not in ALLOWED_OPEN_WORLD_REWARD_CATEGORIES:
            errors.append(f'unknown reward category for threat band {band}: {category}')

    for spawn_profile, category in OPEN_WORLD_SPAWN_PROFILE_TO_REWARD_CATEGORY.items():
        if category not in ALLOWED_OPEN_WORLD_REWARD_CATEGORIES:
            errors.append(f'unknown reward category for spawn profile {spawn_profile}: {category}')

    return errors
