import json
from typing import Any

from database import get_connection
from game.items_data import get_item, get_item_metadata

LEGACY_EQUIPMENT_SLOT_KEYS = (
    'weapon',
    'offhand',
    'helmet',
    'chest',
    'legs',
    'boots',
    'gloves',
    'ring1',
    'ring2',
    'amulet',
)


GEAR_ITEM_TYPES = {'weapon', 'armor', 'accessory'}


def is_gear_item(item: dict | None) -> bool:
    return bool(item and item.get('item_type') in GEAR_ITEM_TYPES)


def is_gear_item_id(item_id: str) -> bool:
    return is_gear_item(get_item(item_id))


def _resolve_instance_slot_identity(item_id: str) -> str | None:
    metadata = get_item_metadata(item_id)
    slot_identity = metadata.get('slot_identity')
    if slot_identity in {'weapon', 'offhand', 'helmet', 'chest', 'legs', 'boots', 'gloves', 'ring', 'amulet'}:
        return slot_identity

    item = get_item(item_id)
    if item and item.get('item_type') == 'weapon':
        return 'weapon'

    return None


def create_gear_instance(
    telegram_id: int,
    base_item_id: str,
    *,
    slot_identity: str | None = None,
    item_tier: int = 1,
    rarity: str | None = None,
    secondary_rolls_json: str = '[]',
    enhance_level: int = 0,
    durability: int = 100,
    max_durability: int = 100,
) -> int:
    item = get_item(base_item_id)
    if not is_gear_item(item):
        raise ValueError(f'Item {base_item_id} is not gear')

    resolved_slot = slot_identity or _resolve_instance_slot_identity(base_item_id)
    resolved_rarity = rarity or item.get('rarity', 'common')

    conn = get_connection()
    try:
        cur = conn.execute(
            '''INSERT INTO gear_instances (
                telegram_id, base_item_id, slot_identity, item_tier, rarity,
                secondary_rolls_json, enhance_level, durability, max_durability, equipped_slot
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)''',
            (
                telegram_id,
                base_item_id,
                resolved_slot,
                item_tier,
                resolved_rarity,
                secondary_rolls_json,
                enhance_level,
                durability,
                max_durability,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_player_gear_instances(telegram_id: int) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            '''SELECT id, telegram_id, base_item_id, slot_identity, item_tier, rarity,
                      secondary_rolls_json, enhance_level, durability, max_durability,
                      equipped_slot, created_at
               FROM gear_instances
               WHERE telegram_id=?
               ORDER BY id''',
            (telegram_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_equipped_gear_instances(telegram_id: int) -> dict[str, dict[str, Any]]:
    equipped: dict[str, dict[str, Any]] = {}
    for row in list_player_gear_instances(telegram_id):
        equipped_slot = row.get('equipped_slot')
        if equipped_slot in LEGACY_EQUIPMENT_SLOT_KEYS:
            equipped[equipped_slot] = row
    return equipped


def get_gear_instance_with_base_data(instance_row: dict[str, Any]) -> dict[str, Any]:
    base_item = get_item(instance_row['base_item_id']) or {}
    merged = dict(base_item)
    merged.update({
        'instance_id': instance_row['id'],
        'item_id': instance_row['base_item_id'],
        'enhance_level': instance_row.get('enhance_level', 0),
        'instance_rarity': instance_row.get('rarity', base_item.get('rarity', 'common')),
        'item_tier': instance_row.get('item_tier', 1),
        'slot_identity': instance_row.get('slot_identity') or get_item_metadata(instance_row['base_item_id']).get('slot_identity'),
        'durability': instance_row.get('durability'),
        'max_durability': instance_row.get('max_durability'),
        'equipped_slot': instance_row.get('equipped_slot'),
        'secondary_rolls': _parse_secondary_rolls(instance_row.get('secondary_rolls_json')),
    })
    return merged


def _parse_secondary_rolls(raw_value: Any) -> list[Any]:
    if isinstance(raw_value, list):
        return raw_value
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
            return parsed if isinstance(parsed, list) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    return []


def resolve_equipped_item_ids_with_fallback(telegram_id: int) -> dict[str, str]:
    equipped: dict[str, str] = {}
    equipped_instances = get_equipped_gear_instances(telegram_id)
    for slot, row in equipped_instances.items():
        equipped[slot] = row['base_item_id']

    conn = get_connection()
    try:
        legacy = conn.execute(
            'SELECT * FROM equipment WHERE telegram_id=?',
            (telegram_id,),
        ).fetchone()
        if not legacy:
            return equipped

        for slot in LEGACY_EQUIPMENT_SLOT_KEYS:
            if slot in equipped:
                continue
            inv_id = legacy[slot]
            if inv_id is None:
                continue
            inv_row = conn.execute(
                'SELECT item_id FROM inventory WHERE telegram_id=? AND id=?',
                (telegram_id, inv_id),
            ).fetchone()
            if inv_row:
                equipped[slot] = inv_row['item_id']
        return equipped
    finally:
        conn.close()


def set_gear_instance_equipped_slot(telegram_id: int, instance_id: int, equipped_slot: str | None):
    conn = get_connection()
    try:
        if equipped_slot is not None:
            conn.execute(
                'UPDATE gear_instances SET equipped_slot=NULL WHERE telegram_id=? AND equipped_slot=?',
                (telegram_id, equipped_slot),
            )
        conn.execute(
            'UPDATE gear_instances SET equipped_slot=? WHERE telegram_id=? AND id=?',
            (equipped_slot, telegram_id, instance_id),
        )
        conn.commit()
    finally:
        conn.close()


def _validate_slot_name(slot: str):
    if slot not in LEGACY_EQUIPMENT_SLOT_KEYS:
        raise ValueError(f'Unsupported equipment slot: {slot}')


def clear_slot_ownership_across_models(telegram_id: int, slot: str):
    _validate_slot_name(slot)
    conn = get_connection()
    try:
        conn.execute(f'UPDATE equipment SET {slot}=NULL WHERE telegram_id=?', (telegram_id,))
        conn.execute(
            'UPDATE gear_instances SET equipped_slot=NULL WHERE telegram_id=? AND equipped_slot=?',
            (telegram_id, slot),
        )
        conn.commit()
    finally:
        conn.close()


def equip_gear_instance_in_slot(telegram_id: int, instance_id: int, slot: str):
    _validate_slot_name(slot)
    clear_slot_ownership_across_models(telegram_id, slot)
    set_gear_instance_equipped_slot(telegram_id, instance_id, slot)


def equip_legacy_inventory_in_slot(telegram_id: int, inventory_id: int, slot: str):
    _validate_slot_name(slot)
    clear_slot_ownership_across_models(telegram_id, slot)
    conn = get_connection()
    try:
        conn.execute(f'UPDATE equipment SET {slot}=? WHERE telegram_id=?', (inventory_id, telegram_id))
        conn.commit()
    finally:
        conn.close()


def unequip_slot_across_models(telegram_id: int, slot: str):
    clear_slot_ownership_across_models(telegram_id, slot)


def grant_item_to_player(telegram_id: int, item_id: str, quantity: int = 1) -> dict[str, int]:
    if quantity <= 0:
        return {'gear_instances_created': 0, 'stackable_added': 0}

    if is_gear_item_id(item_id):
        created = 0
        for _ in range(quantity):
            create_gear_instance(telegram_id, item_id)
            created += 1
        return {'gear_instances_created': created, 'stackable_added': 0}

    conn = get_connection()
    try:
        existing = conn.execute(
            'SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (telegram_id, item_id),
        ).fetchone()
        if existing:
            conn.execute(
                'UPDATE inventory SET quantity=? WHERE id=?',
                (existing['quantity'] + quantity, existing['id']),
            )
        else:
            conn.execute(
                'INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)',
                (telegram_id, item_id, quantity),
            )
        conn.commit()
        return {'gear_instances_created': 0, 'stackable_added': quantity}
    finally:
        conn.close()
