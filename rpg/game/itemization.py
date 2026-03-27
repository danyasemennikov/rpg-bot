"""Itemization scaffolding: archetype identity, stat pools, and rarity budgets.

This module is intentionally data-driven and small. It does not replace the current
inventory/runtime system; it provides a clean foundation for future item content.
"""

from __future__ import annotations

import random
from typing import Iterable

from game.balance import normalize_armor_class, normalize_offhand_profile, normalize_weapon_profile

DEFAULT_RARITY = 'common'

VALID_RARITIES = (
    'common',
    'uncommon',
    'rare',
    'epic',
    'legendary',
    'unique',
)

# How many secondary stats an item can roll by rarity.
RARITY_SECONDARY_COUNT_RULES = {
    'common': 0,
    'uncommon': 1,
    'rare': 2,
    'epic': 3,
    'legendary': 4,
    # Unique items are curated manually later. Keep budget explicit and conservative.
    'unique': 4,
}

# Secondary stat pools by equipment identity.
SECONDARY_STAT_POOLS = {
    'armor_heavy': (
        'max_hp',
        'vitality',
        'physical_defense',
        'block_chance',
        'control_resistance',
        'anti_crit',
        'aggro_power',
    ),
    'armor_medium': (
        'agility',
        'accuracy',
        'evasion',
        'crit_chance',
        'physical_power',
        'max_hp',
        'physical_penetration',
    ),
    'armor_light': (
        'intuition',
        'wisdom',
        'max_mana',
        'mana_regen',
        'magic_power',
        'healing_power',
        'buff_power',
        'magic_defense',
        'tempo_bonus',
    ),
    'weapon_strength': (
        'physical_power',
        'strength',
        'vitality',
        'accuracy',
        'crit_damage',
        'armor_break',
    ),
    'weapon_agility': (
        'physical_power',
        'agility',
        'accuracy',
        'evasion',
        'crit_chance',
        'physical_penetration',
    ),
    'weapon_caster': (
        'magic_power',
        'intuition',
        'wisdom',
        'max_mana',
        'mana_regen',
        'cast_tempo',
        'healing_power',
    ),
    'offhand_shield': (
        'max_hp',
        'vitality',
        'physical_defense',
        'block_chance',
        'control_resistance',
        'anti_crit',
        'aggro_power',
    ),
    'offhand_focus': (
        'magic_power',
        'max_mana',
        'mana_regen',
        'cast_tempo',
        'accuracy',
        'magic_penetration',
    ),
    'offhand_censer': (
        'healing_power',
        'buff_power',
        'support_power',
        'max_mana',
        'mana_regen',
        'control_resistance',
    ),
    'accessory': (
        'strength',
        'agility',
        'intuition',
        'vitality',
        'wisdom',
        'luck',
        'max_hp',
        'max_mana',
        'accuracy',
        'evasion',
        'crit_chance',
        'physical_power',
        'magic_power',
        'healing_power',
        'buff_power',
        'physical_defense',
        'magic_defense',
        'control_resistance',
    ),
}

# Base archetypal stats (coarse scaffolding, not final balance values).
WEAPON_ARCHETYPE_BASE_STATS = {
    'sword_1h': {'damage_min': 11, 'damage_max': 16, 'physical_power': 6, 'accuracy': 3},
    'sword_2h': {'damage_min': 15, 'damage_max': 22, 'physical_power': 9, 'accuracy': 1},
    'axe_2h': {'damage_min': 16, 'damage_max': 24, 'physical_power': 10, 'crit_damage': 4},
    'daggers': {'damage_min': 8, 'damage_max': 13, 'physical_power': 5, 'crit_chance': 4, 'evasion': 2},
    'bow': {'damage_min': 9, 'damage_max': 15, 'physical_power': 6, 'accuracy': 5},
    'magic_staff': {'damage_min': 9, 'damage_max': 14, 'magic_power': 8, 'max_mana': 15},
    'holy_staff': {'damage_min': 8, 'damage_max': 13, 'magic_power': 6, 'healing_power': 5, 'max_mana': 12},
    'wand': {'damage_min': 8, 'damage_max': 12, 'magic_power': 6, 'cast_tempo': 3},
    'holy_rod': {'damage_min': 8, 'damage_max': 12, 'magic_power': 4, 'healing_power': 4, 'vitality': 2},
    'tome': {'damage_min': 7, 'damage_max': 11, 'magic_power': 5, 'healing_power': 2, 'max_mana': 10},
    'unarmed': {'damage_min': 3, 'damage_max': 5},
}

OFFHAND_ARCHETYPE_BASE_STATS = {
    'shield': {'defense': 7, 'max_hp': 20, 'block_chance': 5, 'physical_defense': 4},
    'focus': {'defense': 2, 'max_mana': 24, 'magic_power': 6, 'cast_tempo': 2},
    'censer': {'defense': 2, 'max_mana': 20, 'healing_power': 6, 'buff_power': 5},
    'none': {'defense': 0},
}

ARMOR_ARCHETYPE_BASE_STATS = {
    'heavy': {'defense': 10, 'max_hp': 20, 'physical_defense': 8, 'evasion': -2},
    'medium': {'defense': 7, 'physical_power': 3, 'accuracy': 2, 'evasion': 1, 'max_hp': 8},
    'light': {'defense': 5, 'max_mana': 18, 'magic_power': 4, 'healing_power': 3, 'magic_defense': 3},
}


WEAPON_POOL_BY_PROFILE = {
    'sword_1h': 'weapon_strength',
    'sword_2h': 'weapon_strength',
    'axe_2h': 'weapon_strength',
    'daggers': 'weapon_agility',
    'bow': 'weapon_agility',
    'magic_staff': 'weapon_caster',
    'holy_staff': 'weapon_caster',
    'wand': 'weapon_caster',
    'holy_rod': 'weapon_caster',
    'tome': 'weapon_caster',
    'unarmed': 'weapon_strength',
}

ARMOR_SLOT_IDENTITIES = {'helmet', 'chest', 'legs', 'boots', 'gloves', 'shoulders', 'cloak'}
ACCESSORY_SLOT_IDENTITIES = {'ring', 'amulet'}


def normalize_item_rarity(rarity: str | None) -> str:
    if rarity in VALID_RARITIES:
        return rarity
    return DEFAULT_RARITY


def infer_item_slot_identity(item: dict | None) -> str | None:
    if not item:
        return None

    explicit_slot = item.get('slot_identity')
    if explicit_slot:
        return explicit_slot

    item_type = item.get('item_type')
    if item_type == 'weapon':
        return 'weapon'
    if item_type == 'armor':
        if item.get('offhand_profile'):
            return 'offhand'
        return 'chest'
    if item_type == 'accessory':
        return item.get('accessory_type', 'ring')
    return None


def get_item_archetype_metadata(item: dict | None) -> dict:
    """Return normalized archetype identity without mutating source item."""
    if not item:
        return {
            'slot_identity': None,
            'rarity': DEFAULT_RARITY,
            'armor_class': None,
            'weapon_profile': 'unarmed',
            'offhand_profile': 'none',
        }

    slot_identity = infer_item_slot_identity(item)

    item_type = item.get('item_type')
    if item_type == 'weapon':
        weapon_type = item.get('weapon_type', 'melee')
        weapon_profile = normalize_weapon_profile(item.get('weapon_profile'), weapon_type)
    else:
        # Non-weapon items should never get a fake melee profile from fallback rules.
        weapon_profile = 'unarmed'

    metadata = {
        'slot_identity': slot_identity,
        'rarity': normalize_item_rarity(item.get('rarity')),
        'armor_class': normalize_armor_class(item.get('armor_class')),
        'weapon_profile': weapon_profile,
        'offhand_profile': normalize_offhand_profile(item.get('offhand_profile')),
    }
    return metadata


def get_secondary_pool_for_item(item: dict | None) -> tuple[str, ...]:
    metadata = get_item_archetype_metadata(item)
    slot_identity = metadata['slot_identity']

    if slot_identity == 'weapon':
        pool_key = WEAPON_POOL_BY_PROFILE[metadata['weapon_profile']]
        return SECONDARY_STAT_POOLS[pool_key]

    if slot_identity == 'offhand':
        offhand_pool_key = f"offhand_{metadata['offhand_profile']}"
        return SECONDARY_STAT_POOLS.get(offhand_pool_key, SECONDARY_STAT_POOLS['offhand_shield'])

    if slot_identity in ARMOR_SLOT_IDENTITIES:
        armor_class = metadata['armor_class'] or 'medium'
        return SECONDARY_STAT_POOLS[f'armor_{armor_class}']

    if slot_identity in ACCESSORY_SLOT_IDENTITIES:
        return SECONDARY_STAT_POOLS['accessory']

    return tuple()


def get_secondary_count_budget_for_rarity(rarity: str | None) -> int:
    normalized_rarity = normalize_item_rarity(rarity)
    return RARITY_SECONDARY_COUNT_RULES[normalized_rarity]


def get_base_archetype_stats_for_item(item: dict | None) -> dict:
    metadata = get_item_archetype_metadata(item)
    slot_identity = metadata['slot_identity']

    if slot_identity == 'weapon':
        return dict(WEAPON_ARCHETYPE_BASE_STATS[metadata['weapon_profile']])

    if slot_identity == 'offhand':
        return dict(OFFHAND_ARCHETYPE_BASE_STATS[metadata['offhand_profile']])

    if slot_identity in ARMOR_SLOT_IDENTITIES:
        armor_class = metadata['armor_class'] or 'medium'
        return dict(ARMOR_ARCHETYPE_BASE_STATS[armor_class])

    return {}


def roll_secondary_stats_for_item(
    item: dict | None,
    *,
    count: int | None = None,
    rng: random.Random | None = None,
) -> list[str]:
    """Roll unique secondary stat ids from the allowed pool.

    Deterministic in tests when `rng` is provided.
    """
    pool = list(get_secondary_pool_for_item(item))
    if not pool:
        return []

    rarity_count = get_secondary_count_budget_for_rarity((item or {}).get('rarity'))
    target_count = rarity_count if count is None else max(0, int(count))
    target_count = min(target_count, len(pool))

    random_source = rng if rng is not None else random
    return random_source.sample(pool, k=target_count)


def pool_contains_forbidden_combo(pool: Iterable[str], forbidden_stats: set[str]) -> bool:
    pool_set = set(pool)
    return forbidden_stats.issubset(pool_set)
