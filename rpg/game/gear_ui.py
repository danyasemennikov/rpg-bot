"""Read-only projections used by the existing inventory, journal, and guild UI."""

from __future__ import annotations

import json
from typing import Any

from database import get_connection
from game.field_catalog import (
    FIELD_ITEM_IDS,
    FIELD_ROUTE_POOLS,
    FIELD_VENDOR_LOCATIONS,
    get_field_category,
    list_field_items,
    source_routes_for_item,
)
from game.gear_instances import get_equipped_gear_instances, resolve_gear_instance_item_data
from game.items_data import get_item
from game.equipment_stats import aggregate_equipped_stat_bonuses, build_effective_player_stats

CATALOG_PAGE_SIZE = 8
COMPARISON_CHANNELS = (
    'damage_min', 'damage_max', 'physical_defense', 'magic_defense',
    'max_hp', 'max_mana', 'strength', 'agility', 'intuition', 'vitality',
    'wisdom', 'luck', 'accuracy', 'evasion', 'block_chance',
    'magic_power', 'healing_power',
)
ROUTE_SOURCE_HUBS = {
    'route_westwild': 'hub_westwild',
    'route_frostspine': 'hub_frostspine',
    'route_ashen_ruins': 'hub_ashen_ruins',
    'route_mireveil': 'hub_mireveil',
    'route_sunscar': 'hub_sunscar',
}


def catalog_page(category: str, page: int) -> dict:
    normalized = category if category in {'weapon', 'armor', 'offhand', 'accessories'} else 'weapon'
    item_ids = list_field_items(normalized)
    page_count = max(1, (len(item_ids) + CATALOG_PAGE_SIZE - 1) // CATALOG_PAGE_SIZE)
    normalized_page = max(0, min(page_count - 1, int(page)))
    start = normalized_page * CATALOG_PAGE_SIZE
    return {
        'category': normalized,
        'page': normalized_page,
        'page_count': page_count,
        'item_ids': item_ids[start:start + CATALOG_PAGE_SIZE],
    }


def get_field_source_manifest(item_id: str) -> dict:
    if item_id not in FIELD_ITEM_IDS:
        return {'vendors': (), 'curated_routes': (), 'universal_routes': (), 'stub_key': None}
    curated = source_routes_for_item(item_id)
    return {
        'vendors': FIELD_VENDOR_LOCATIONS,
        'curated_routes': curated,
        # Every full route can produce every field template through its 20% pool.
        'universal_routes': tuple(FIELD_ROUTE_POOLS),
        'stub_key': 'starter_stubs',
    }


def get_owned_gear_instance(player_id: int, instance_id: int, *, conn=None) -> dict | None:
    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()
    try:
        row = conn.execute('SELECT * FROM gear_instances WHERE id=? AND telegram_id=?',
                           (instance_id, player_id)).fetchone()
        return dict(row) if row else None
    finally:
        if owns_connection:
            conn.close()


def _bonus_dict(raw: Any) -> dict[str, int]:
    if isinstance(raw, dict):
        parsed = raw
    else:
        try:
            parsed = json.loads(raw or '{}')
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed = {}
    return {str(key): int(value) for key, value in parsed.items()} if isinstance(parsed, dict) else {}


def contribution_from_resolved_item(item: dict | None) -> dict[str, int]:
    item = item or {}
    values = {key: 0 for key in COMPARISON_CHANNELS}
    values['damage_min'] = int(item.get('damage_min', 0) or 0)
    values['damage_max'] = int(item.get('damage_max', 0) or 0)
    values['physical_defense'] = int(item.get('defense', 0) or 0)
    bonuses = item.get('resolved_stat_bonus')
    if not isinstance(bonuses, dict):
        bonuses = _bonus_dict(item.get('stat_bonus_json', '{}'))
    for key, raw in bonuses.items():
        if key in values:
            values[key] += int(raw or 0)
    return values


def resolve_template_preview(item_id: str) -> dict:
    item = get_item(item_id) or {}
    if item_id not in FIELD_ITEM_IDS:
        return dict(item)
    return resolve_gear_instance_item_data({
        'id': 0,
        'base_item_id': item_id,
        'slot_identity': item.get('slot_identity'),
        'item_tier': 1,
        'rarity': 'common',
        'secondary_rolls_json': '[]',
        'enhance_level': 0,
        'durability': 100,
        'max_durability': 100,
        'equipped_slot': None,
    })


def compare_instance_to_slot(player_id: int, instance_id: int, slot: str) -> dict | None:
    if slot not in {'weapon', 'offhand', 'helmet', 'chest', 'legs', 'boots', 'gloves', 'ring1', 'ring2', 'amulet'}:
        return None
    conn = get_connection()
    try:
        candidate = get_owned_gear_instance(player_id, instance_id, conn=conn)
        if not candidate:
            return None
        identity = str(candidate.get('slot_identity') or '')
        if identity != slot and not (identity == 'ring' and slot in {'ring1', 'ring2'}):
            return None
        candidate_contribution = contribution_from_resolved_item(resolve_gear_instance_item_data(candidate))

        current_item_id = None
        equipped_instances = get_equipped_gear_instances(player_id, conn=conn)
        current_instance = equipped_instances.get(slot)
        if current_instance:
            current_item_id = str(current_instance['base_item_id'])
            current_contribution = contribution_from_resolved_item(resolve_gear_instance_item_data(current_instance))
        else:
            equipment = conn.execute('SELECT * FROM equipment WHERE telegram_id=?', (player_id,)).fetchone()
            legacy_id = equipment[slot] if equipment else None
            legacy = conn.execute('SELECT item_id FROM inventory WHERE id=? AND telegram_id=?',
                                  (legacy_id, player_id)).fetchone() if legacy_id is not None else None
            current_item_id = str(legacy['item_id']) if legacy else None
            current_contribution = contribution_from_resolved_item(get_item(current_item_id) if current_item_id else None)

        player_row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (player_id,)).fetchone()
        if not player_row:
            return None
        before_bonuses = aggregate_equipped_stat_bonuses(player_id, conn=conn)
        after_bonuses = dict(before_bonuses)
        for key, value in current_contribution.items():
            if key not in {'damage_min', 'damage_max'}:
                after_bonuses[key] = int(after_bonuses.get(key, 0)) - int(value)
        candidate_already_equipped = bool(candidate.get('equipped_slot'))
        if not candidate_already_equipped or str(candidate.get('equipped_slot')) == slot:
            for key, value in candidate_contribution.items():
                if key not in {'damage_min', 'damage_max'}:
                    after_bonuses[key] = int(after_bonuses.get(key, 0)) + int(value)

        before_effective = build_effective_player_stats(dict(player_row), before_bonuses)
        after_effective = build_effective_player_stats(dict(player_row), after_bonuses)
        effective_key = {
            'physical_defense': 'effective_physical_defense',
            'magic_defense': 'effective_magic_defense',
            'accuracy': 'accuracy_bonus',
            'evasion': 'evasion_bonus',
            'block_chance': 'block_chance_bonus',
            'magic_power': 'magic_power_bonus',
            'healing_power': 'healing_power_bonus',
        }
        current_values = {key: 0 for key in COMPARISON_CHANNELS}
        candidate_values = {key: 0 for key in COMPARISON_CHANNELS}
        for key in COMPARISON_CHANNELS:
            if key in {'damage_min', 'damage_max'}:
                current_values[key] = current_contribution[key]
                candidate_values[key] = candidate_contribution[key]
                continue
            projection_key = effective_key.get(key, key)
            current_values[key] = int(before_effective.get(projection_key, 0))
            candidate_values[key] = int(after_effective.get(projection_key, 0))
        deltas = {key: candidate_values[key] - current_values[key] for key in COMPARISON_CHANNELS}
        return {
            'slot': slot,
            'candidate_item_id': str(candidate['base_item_id']),
            'current_item_id': current_item_id,
            'candidate': candidate_values,
            'current': current_values,
            'deltas': deltas,
        }
    finally:
        conn.close()
