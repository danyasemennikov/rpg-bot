"""Static authority for Field Equipment V1 and its real acquisition sources."""

from __future__ import annotations

import json
import random
from typing import Iterable

FIELD_CATALOG_VERSION = 1
FIELD_REWARD_POLICY_VERSION = 'field_loot_v1'
LEGACY_REWARD_POLICY_VERSION = 'legacy_v0'
FIELD_MAX_TIER = 20
FIELD_DRY_STREAK_THRESHOLD = 12
FIELD_VENDOR_LOCATIONS = ('capital_city', 'hub_westwild', 'hub_frostspine')

WEAPON_SPECS = {
    'sword_1h': (11, 16, 'melee', 'physical', 'strength', 2),
    'sword_2h': (15, 22, 'melee', 'physical', 'strength', 4),
    'axe_2h': (16, 24, 'melee', 'physical', 'strength', 4),
    'daggers': (8, 13, 'melee', 'physical', 'agility', 2),
    'bow': (9, 15, 'ranged', 'physical', 'agility', 2),
    'magic_staff': (9, 14, 'magic', 'magic', 'intuition', 3),
    'wand': (8, 12, 'magic', 'magic', 'intuition', 2),
    'holy_staff': (8, 13, 'light', 'holy', 'wisdom', 3),
    'holy_rod': (8, 12, 'light', 'holy', 'wisdom', 2),
    'tome': (7, 11, 'magic', 'magic', 'wisdom', 2),
}

ARMOR_BASE = {
    'heavy': (8, {'max_hp': 12}, 3),
    'medium': (5, {'accuracy': 2, 'evasion': 1}, 2),
    'light': (3, {'max_mana': 12, 'magic_defense': 2}, 1),
}
ARMOR_SLOT_COEFFICIENTS = {
    'helmet': 0.4,
    'chest': 1.0,
    'legs': 0.6,
    'boots': 0.3,
    'gloves': 0.3,
}
ARMOR_BUY_PRICE = {'chest': 60, 'legs': 40, 'helmet': 20, 'boots': 20, 'gloves': 20}

OFFHAND_ACCESSORY_SPECS = {
    'field_shield': ('armor', 'offhand', 4, {'max_hp': 8, 'block_chance': 2}, 60, 3, 'shield'),
    'field_focus': ('armor', 'offhand', 1, {'max_mana': 8, 'magic_power': 2}, 60, 1, 'focus'),
    'field_censer': ('armor', 'offhand', 1, {'max_mana': 8, 'healing_power': 2}, 60, 1, 'censer'),
    'field_precision_ring': ('accessory', 'ring', 0, {'accuracy': 2, 'agility': 1}, 60, 1, None),
    'field_guard_ring': ('accessory', 'ring', 0, {'max_hp': 8, 'vitality': 1}, 60, 1, None),
    'field_mind_ring': ('accessory', 'ring', 0, {'max_mana': 8, 'intuition': 1}, 60, 1, None),
    'field_prayer_amulet': ('accessory', 'amulet', 0, {'wisdom': 1, 'healing_power': 2}, 80, 1, None),
}


def _base_item(item_id: str, *, item_type: str, weight: int, buy_price: int) -> dict:
    return {
        'item_id': item_id,
        'name': item_id,
        'description': 'Field equipment.',
        'item_type': item_type,
        'weapon_type': None,
        'rarity': 'common',
        'damage_min': 0,
        'damage_max': 0,
        'defense': 0,
        'weight': weight,
        'req_level': 1,
        'req_strength': 0,
        'req_agility': 0,
        'req_intuition': 0,
        'req_wisdom': 0,
        'buy_price': buy_price,
        'sell_price': 5,
        'skills_json': '[]',
        'stat_bonus_json': '{}',
        'field_catalog_version': FIELD_CATALOG_VERSION,
    }


def _build_field_items() -> dict[str, dict]:
    items: dict[str, dict] = {}
    for family, (damage_min, damage_max, weapon_type, school, requirement, weight) in WEAPON_SPECS.items():
        item_id = f'field_{family}'
        item = _base_item(item_id, item_type='weapon', weight=weight, buy_price=45)
        item.update({
            'weapon_type': weapon_type,
            'weapon_profile': family,
            'damage_school': school,
            'slot_identity': 'weapon',
            'damage_min': damage_min,
            'damage_max': damage_max,
            f'req_{requirement}': 3,
        })
        items[item_id] = item

    for armor_class, (base_defense, base_bonuses, weight) in ARMOR_BASE.items():
        for slot, coefficient in ARMOR_SLOT_COEFFICIENTS.items():
            item_id = f'field_{armor_class}_{slot}'
            item = _base_item(item_id, item_type='armor', weight=weight, buy_price=ARMOR_BUY_PRICE[slot])
            scaled_bonuses = {
                key: round(value * coefficient)
                for key, value in base_bonuses.items()
                if round(value * coefficient) != 0
            }
            item.update({
                'slot_identity': slot,
                'armor_class': armor_class,
                'defense': round(base_defense * coefficient),
                'stat_bonus_json': json.dumps(scaled_bonuses, sort_keys=True),
            })
            items[item_id] = item

    for item_id, (item_type, slot, defense, bonuses, price, weight, offhand_profile) in OFFHAND_ACCESSORY_SPECS.items():
        item = _base_item(item_id, item_type=item_type, weight=weight, buy_price=price)
        item.update({
            'slot_identity': slot,
            'defense': defense,
            'stat_bonus_json': json.dumps(bonuses, sort_keys=True),
        })
        if offhand_profile:
            item['offhand_profile'] = offhand_profile
        items[item_id] = item
    return items


FIELD_ITEMS = _build_field_items()
FIELD_ITEM_IDS = tuple(FIELD_ITEMS)
FIELD_WEAPON_IDS = tuple(item_id for item_id, item in FIELD_ITEMS.items() if item['item_type'] == 'weapon')
FIELD_ARMOR_IDS = tuple(
    item_id for item_id, item in FIELD_ITEMS.items()
    if item['item_type'] == 'armor' and item.get('slot_identity') != 'offhand'
)
FIELD_OFFHAND_IDS = ('field_shield', 'field_focus', 'field_censer')
FIELD_ACCESSORY_IDS = ('field_precision_ring', 'field_guard_ring', 'field_mind_ring', 'field_prayer_amulet')

FIELD_ROUTE_POOLS = {
    'route_westwild': (
        'field_daggers', 'field_bow',
        *(f'field_medium_{slot}' for slot in ARMOR_SLOT_COEFFICIENTS),
        'field_precision_ring',
    ),
    'route_frostspine': (
        'field_sword_1h', 'field_sword_2h', 'field_axe_2h',
        *(f'field_heavy_{slot}' for slot in ARMOR_SLOT_COEFFICIENTS),
        'field_shield', 'field_guard_ring',
    ),
    'route_ashen_ruins': (
        'field_magic_staff', 'field_wand',
        *(f'field_light_{slot}' for slot in ARMOR_SLOT_COEFFICIENTS),
        'field_focus', 'field_mind_ring',
    ),
    'route_mireveil': (
        'field_holy_staff', 'field_tome',
        *(f'field_light_{slot}' for slot in ARMOR_SLOT_COEFFICIENTS),
        'field_censer', 'field_prayer_amulet',
    ),
    'route_sunscar': (
        'field_holy_rod', 'field_bow', 'field_sword_2h',
        *(f'field_medium_{slot}' for slot in ARMOR_SLOT_COEFFICIENTS),
        'field_shield', 'field_precision_ring',
    ),
}
STUB_ROUTE_IDS = frozenset({'route_south_coast_stub', 'route_old_mine_stub'})

GEAR_CHANCE_BY_SPAWN_PROFILE = {'normal': 0.08, 'elite': 0.35}
DRY_STREAK_INCREMENT_BY_SPAWN_PROFILE = {'normal': 1, 'elite': 3}
RARITY_WEIGHTS_BY_SPAWN_PROFILE = {
    'normal': (('common', 0.70), ('uncommon', 0.28), ('rare', 0.02)),
    'elite': (('uncommon', 0.70), ('rare', 0.295), ('epic', 0.005)),
}


def is_field_item(item_id: str | None) -> bool:
    return str(item_id or '') in FIELD_ITEMS


def get_field_category(item_id: str) -> str:
    if item_id in FIELD_WEAPON_IDS:
        return 'weapon'
    if item_id in FIELD_ARMOR_IDS:
        return 'armor'
    if item_id in FIELD_OFFHAND_IDS:
        return 'offhand'
    return 'accessories'


def list_field_items(category: str | None = None) -> list[str]:
    if category not in {'weapon', 'armor', 'offhand', 'accessories'}:
        return list(FIELD_ITEM_IDS)
    return [item_id for item_id in FIELD_ITEM_IDS if get_field_category(item_id) == category]


def resolve_progress_route_id(location_id: str | None) -> str | None:
    from game.locations import WORLD_ROUTES, get_location

    location = get_location(location_id or '') or {}
    route_id = str(location.get('route_id') or '')
    route_type = str((WORLD_ROUTES.get(route_id) or {}).get('route_type') or '')
    if route_type == 'full':
        return route_id
    if route_id in STUB_ROUTE_IDS:
        return 'starter_stubs'
    return None


def get_curated_pool(route_id: str | None) -> tuple[str, ...]:
    if route_id == 'starter_stubs':
        return FIELD_ITEM_IDS
    return tuple(FIELD_ROUTE_POOLS.get(str(route_id or ''), ()))


def choose_field_item(route_id: str, rng: random.Random) -> str:
    curated = get_curated_pool(route_id)
    if not curated:
        raise ValueError(f'unknown_field_route:{route_id}')
    if route_id == 'starter_stubs' or rng.random() >= 0.80:
        return rng.choice(FIELD_ITEM_IDS)
    return rng.choice(curated)


def choose_weighted_rarity(spawn_profile: str, rng: random.Random) -> str:
    weights = RARITY_WEIGHTS_BY_SPAWN_PROFILE.get(spawn_profile)
    if not weights:
        raise ValueError(f'unsupported_field_spawn_profile:{spawn_profile}')
    roll = rng.random()
    cumulative = 0.0
    for rarity, weight in weights:
        cumulative += weight
        if roll < cumulative:
            return rarity
    return weights[-1][0]


def source_routes_for_item(item_id: str) -> tuple[str, ...]:
    if item_id not in FIELD_ITEMS:
        return ()
    return tuple(route_id for route_id, pool in FIELD_ROUTE_POOLS.items() if item_id in pool)


def validate_field_catalog() -> None:
    if len(FIELD_ITEMS) != 32:
        raise RuntimeError('field_catalog_must_contain_32_items')
    unknown = set().union(*(set(pool) for pool in FIELD_ROUTE_POOLS.values())) - set(FIELD_ITEM_IDS)
    if unknown:
        raise RuntimeError(f'field_catalog_unknown_pool_items:{sorted(unknown)}')
    slots = {item.get('slot_identity') for item in FIELD_ITEMS.values()}
    required = {'weapon', 'offhand', 'helmet', 'chest', 'legs', 'boots', 'gloves', 'ring', 'amulet'}
    if not required.issubset(slots):
        raise RuntimeError('field_catalog_missing_equipment_slots')


validate_field_catalog()
