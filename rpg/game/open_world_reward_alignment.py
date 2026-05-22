from __future__ import annotations

from game.open_world_pack_balance import (
    ALLOWED_OPEN_WORLD_THREAT_BANDS,
    get_open_world_pack_archetype_metadata,
)
from game.open_world_reward_pools import OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY
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
        'reward_profile_id': OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY['open_world_normal'],
        'threat_band_note': 'starter lane; normal rewards',
    },
    'low': {
        'reward_category': 'open_world_normal',
        'reward_profile_id': OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY['open_world_normal'],
        'threat_band_note': 'low lane; normal rewards',
    },
    'low_mid': {
        'reward_category': 'open_world_normal',
        'reward_profile_id': OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY['open_world_normal'],
        'threat_band_note': 'low-mid lane; normal rewards',
    },
    'mid': {
        'reward_category': 'open_world_normal',
        'reward_profile_id': OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY['open_world_normal'],
        'threat_band_note': 'mid lane; normal rewards (elite-capable threat metadata)',
    },
    'mid_high': {
        'reward_category': 'open_world_elite',
        'reward_profile_id': OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY['open_world_elite'],
        'threat_band_note': 'mid-high lane; elite-capable rewards metadata',
    },
    'high': {
        'reward_category': 'open_world_rare_spawn',
        'reward_profile_id': OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY['open_world_rare_spawn'],
        'threat_band_note': 'high lane; rare-capable rewards metadata',
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
        profile_id = profile.get('reward_profile_id')
        if category not in REWARD_FAMILIES_BY_SOURCE:
            errors.append(f'unknown reward category in policy for threat band {band}: {category}')
            continue
        if category not in ALLOWED_OPEN_WORLD_REWARD_CATEGORIES:
            errors.append(f'unknown open-world reward category for threat band {band}: {category}')
            continue

        expected_profile_id = OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY.get(category)
        if expected_profile_id is None:
            errors.append(f'missing pool profile registry for threat band {band} category {category}')
            continue
        if profile_id != expected_profile_id:
            errors.append(
                f'threat band {band} has mismatched reward_profile_id {profile_id}; expected {expected_profile_id}'
            )

    for spawn_profile, category in OPEN_WORLD_SPAWN_PROFILE_TO_REWARD_CATEGORY.items():
        if category not in REWARD_FAMILIES_BY_SOURCE:
            errors.append(f'unknown reward category in policy for spawn profile {spawn_profile}: {category}')
        elif category not in ALLOWED_OPEN_WORLD_REWARD_CATEGORIES:
            errors.append(f'unknown open-world reward category for spawn profile {spawn_profile}: {category}')

    return errors
