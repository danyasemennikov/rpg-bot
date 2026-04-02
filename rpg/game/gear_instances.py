import json
import random
from typing import Any

from database import get_connection
from game.itemization import (
    get_generated_secondary_pool_for_item,
    get_secondary_count_budget_for_rarity,
    roll_generated_rarity,
)
from game.reward_source_metadata import (
    RewardSourceMetadata,
    classify_item_reward_family,
    is_reward_family_allowed_for_source,
)
from game.items_data import get_item, get_item_metadata
from game.enhancement_material_routing import resolve_enhancement_material_routing
from game.open_world_reward_pools import (
    clamp_rarity_to_quality_floor,
    is_gear_item_allowed_for_open_world_content_identity,
    is_item_tier_band_allowed_for_bounds,
    is_open_world_source_category,
)

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
ORDINARY_GENERATED_RARITIES = {'common', 'uncommon', 'rare', 'epic', 'legendary'}

TIER_BAND_STEP = 5
MAX_GENERATED_TIER = 50

SECONDARY_ROLL_BASE_RANGES = {
    'strength': (1, 2),
    'agility': (1, 2),
    'intuition': (1, 2),
    'vitality': (1, 2),
    'wisdom': (1, 2),
    'luck': (1, 2),
    'max_hp': (8, 16),
    'max_mana': (8, 16),
    'physical_defense': (1, 3),
    'magic_defense': (1, 3),
    'accuracy': (1, 3),
    'evasion': (1, 3),
    'block_chance': (1, 2),
    'magic_power': (2, 5),
    'healing_power': (2, 5),
}

MAX_ENHANCE_LEVEL = 15
ENHANCE_STAT_PER_LEVEL = 0.04
ENHANCE_REQUIREMENTS_BY_TARGET_LEVEL = {
    1: {'gold': 100, 'material_id': 'enhance_shard', 'material_qty': 1},
    2: {'gold': 180, 'material_id': 'enhance_shard', 'material_qty': 1},
    3: {'gold': 280, 'material_id': 'enhance_shard', 'material_qty': 1},
    4: {'gold': 420, 'material_id': 'enhance_shard', 'material_qty': 1},
    5: {'gold': 600, 'material_id': 'enhance_shard', 'material_qty': 1},
    6: {'gold': 850, 'material_id': 'enhancement_crystal', 'material_qty': 1},
    7: {'gold': 1200, 'material_id': 'enhancement_crystal', 'material_qty': 1},
    8: {'gold': 1600, 'material_id': 'enhancement_crystal', 'material_qty': 1},
    9: {'gold': 2100, 'material_id': 'enhancement_crystal', 'material_qty': 1},
    10: {'gold': 2700, 'material_id': 'power_essence', 'material_qty': 1},
    11: {'gold': 3500, 'material_id': 'power_essence', 'material_qty': 1},
    12: {'gold': 4500, 'material_id': 'power_essence', 'material_qty': 1},
    13: {'gold': 5700, 'material_id': 'ashen_core', 'material_qty': 1},
    14: {'gold': 7200, 'material_id': 'ashen_core', 'material_qty': 1},
    15: {'gold': 9000, 'material_id': 'ashen_core', 'material_qty': 1},
}
ENHANCE_OUTCOME_RULES_BY_TARGET_LEVEL = {
    1: {'success': 0.80, 'fail': 0.20, 'rollback': 0.0, 'break': 0.0},
    2: {'success': 0.80, 'fail': 0.20, 'rollback': 0.0, 'break': 0.0},
    3: {'success': 0.80, 'fail': 0.20, 'rollback': 0.0, 'break': 0.0},
    4: {'success': 0.55, 'fail': 0.30, 'rollback': 0.15, 'break': 0.0},
    5: {'success': 0.55, 'fail': 0.30, 'rollback': 0.15, 'break': 0.0},
    6: {'success': 0.55, 'fail': 0.30, 'rollback': 0.15, 'break': 0.0},
    7: {'success': 0.30, 'fail': 0.35, 'rollback': 0.30, 'break': 0.05},
    8: {'success': 0.30, 'fail': 0.35, 'rollback': 0.30, 'break': 0.05},
    9: {'success': 0.30, 'fail': 0.35, 'rollback': 0.30, 'break': 0.05},
    10: {'success': 0.20, 'fail': 0.30, 'rollback': 0.35, 'break': 0.15},
    11: {'success': 0.15, 'fail': 0.25, 'rollback': 0.35, 'break': 0.25},
    12: {'success': 0.10, 'fail': 0.20, 'rollback': 0.35, 'break': 0.35},
    13: {'success': 0.07, 'fail': 0.18, 'rollback': 0.30, 'break': 0.45},
    14: {'success': 0.04, 'fail': 0.16, 'rollback': 0.25, 'break': 0.55},
    15: {'success': 0.02, 'fail': 0.13, 'rollback': 0.20, 'break': 0.65},
}


def is_gear_item(item: dict | None) -> bool:
    return bool(item and item.get('item_type') in GEAR_ITEM_TYPES)


def is_gear_item_id(item_id: str) -> bool:
    return is_gear_item(get_item(item_id))


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
    conn=None,
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

    owns_connection = conn is None
    if owns_connection:
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
        if owns_connection:
            conn.commit()
        return int(cur.lastrowid)
    finally:
        if owns_connection:
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


def _normalize_secondary_rolls(raw_value: Any) -> list[dict[str, int | str]]:
    raw_rolls = _parse_secondary_rolls(raw_value)
    normalized: list[dict[str, int | str]] = []
    for entry in raw_rolls:
        if isinstance(entry, str):
            normalized.append({'stat': entry, 'value': 0})
            continue
        if not isinstance(entry, dict):
            continue
        stat_key = entry.get('stat') or entry.get('stat_key')
        if not isinstance(stat_key, str):
            continue
        normalized.append({'stat': stat_key, 'value': _safe_int(entry.get('value', 0))})
    return normalized


def _parse_stat_bonus_json(raw_bonus: Any) -> dict[str, int]:
    if isinstance(raw_bonus, dict):
        parsed = raw_bonus
    else:
        try:
            parsed = json.loads(raw_bonus or '{}')
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    if not isinstance(parsed, dict):
        return {}

    out: dict[str, int] = {}
    for key, value in parsed.items():
        out[str(key)] = _safe_int(value, 0)
    return out


def _tier_scale_multiplier(item_tier: int) -> float:
    normalized_tier = max(1, _safe_int(item_tier, 1))
    return 1.0 + max(0, normalized_tier - 1) * 0.08


def _secondary_strength_multiplier(item_tier: int) -> float:
    normalized_tier = max(1, _safe_int(item_tier, 1))
    return 1.0 + max(0, normalized_tier - 1) * 0.12


def _scale_stat_dict(base_stats: dict[str, int], item_tier: int) -> dict[str, int]:
    multiplier = _tier_scale_multiplier(item_tier)
    scaled: dict[str, int] = {}
    for stat_key, stat_value in base_stats.items():
        scaled[stat_key] = int(round(_safe_int(stat_value, 0) * multiplier))
    return scaled


def _clamp_enhance_level(value: Any) -> int:
    return min(MAX_ENHANCE_LEVEL, max(0, _safe_int(value, 0)))


def _enhance_multiplier(enhance_level: int) -> float:
    return 1.0 + (_clamp_enhance_level(enhance_level) * ENHANCE_STAT_PER_LEVEL)


def _apply_enhancement_to_value(value: int, enhance_level: int) -> int:
    if value <= 0:
        return max(0, value)
    return max(1, int(round(value * _enhance_multiplier(enhance_level))))


def get_enhance_requirements_for_target_level(target_level: int) -> dict[str, Any]:
    normalized_target = min(MAX_ENHANCE_LEVEL, max(1, _safe_int(target_level, 1)))
    req = ENHANCE_REQUIREMENTS_BY_TARGET_LEVEL.get(normalized_target, {})
    return {
        'gold': _safe_int(req.get('gold', 0), 0),
        'material_id': str(req.get('material_id', 'enhance_shard')),
        'material_qty': max(1, _safe_int(req.get('material_qty', 1), 1)),
    }


def get_enhance_outcome_chances_for_target_level(target_level: int) -> dict[str, float]:
    normalized_target = min(MAX_ENHANCE_LEVEL, max(1, _safe_int(target_level, 1)))
    raw = ENHANCE_OUTCOME_RULES_BY_TARGET_LEVEL.get(normalized_target, ENHANCE_OUTCOME_RULES_BY_TARGET_LEVEL[1])
    success = max(0.0, float(raw.get('success', 0.0)))
    fail = max(0.0, float(raw.get('fail', 0.0)))
    rollback = max(0.0, float(raw.get('rollback', 0.0)))
    break_chance = max(0.0, float(raw.get('break', 0.0)))
    total = success + fail + rollback + break_chance
    if total <= 0:
        return {'success': 1.0, 'fail': 0.0, 'rollback': 0.0, 'break': 0.0}
    return {
        'success': success / total,
        'fail': fail / total,
        'rollback': rollback / total,
        'break': break_chance / total,
    }


def resolve_enhancement_attempt_outcome(current_level: int, *, rng_roll: float | None = None) -> str:
    target_level = min(MAX_ENHANCE_LEVEL, max(1, _safe_int(current_level, 0) + 1))
    chances = get_enhance_outcome_chances_for_target_level(target_level)
    roll = random.random() if rng_roll is None else max(0.0, min(0.999999, float(rng_roll)))
    border_success = chances['success']
    border_fail = border_success + chances['fail']
    border_rollback = border_fail + chances['rollback']
    if roll < border_success:
        return 'success'
    if roll < border_fail:
        return 'fail'
    if roll < border_rollback:
        return 'rollback'
    return 'break'


def resolve_item_tier_band(level: int) -> int:
    """Maps source level to deterministic tier bands: 1 / 5 / 10 / 15 / ..."""
    normalized_level = max(1, _safe_int(level, 1))
    if normalized_level < TIER_BAND_STEP:
        return 1
    tier = (normalized_level // TIER_BAND_STEP) * TIER_BAND_STEP
    return min(MAX_GENERATED_TIER, max(1, tier))


def determine_shop_item_tier(item: dict, *, player_level: int, level_min: int | None = None) -> int:
    base_level = max(_safe_int(item.get('req_level', 1), 1), _safe_int(level_min, 1), _safe_int(player_level, 1))
    return resolve_item_tier_band(base_level)


def determine_mob_drop_item_tier(*, mob_level: int) -> int:
    return resolve_item_tier_band(mob_level)


def _roll_secondary_stat_value(stat_key: str, item_tier: int, rng: random.Random | None = None) -> int:
    min_roll, max_roll = SECONDARY_ROLL_BASE_RANGES.get(stat_key, (1, 1))
    random_source = rng if rng is not None else random
    rolled_base = random_source.randint(min_roll, max_roll)
    return max(1, int(round(rolled_base * _secondary_strength_multiplier(item_tier))))


def generate_secondary_rolls_for_item(
    item: dict,
    *,
    rarity: str,
    item_tier: int,
    rng: random.Random | None = None,
) -> list[dict[str, int | str]]:
    pool = list(get_generated_secondary_pool_for_item(item))
    if not pool:
        return []

    random_source = rng if rng is not None else random
    secondary_count = min(get_secondary_count_budget_for_rarity(rarity), len(pool))
    if secondary_count <= 0:
        return []

    selected_stats = random_source.sample(pool, k=secondary_count)
    return [
        {'stat': stat_key, 'value': _roll_secondary_stat_value(stat_key, item_tier, rng=random_source)}
        for stat_key in selected_stats
    ]


def resolve_gear_instance_item_data(instance_row: dict[str, Any]) -> dict[str, Any]:
    """Returns a resolved runtime view from base template + instance generation layers."""
    base_item = get_item(instance_row['base_item_id']) or {}
    base_bonus = _parse_stat_bonus_json(base_item.get('stat_bonus_json', '{}'))

    item_tier = max(1, _safe_int(instance_row.get('item_tier', 1), 1))
    instance_rarity = instance_row.get('rarity')
    if instance_rarity not in ORDINARY_GENERATED_RARITIES:
        instance_rarity = base_item.get('rarity', 'common')
    if instance_rarity not in ORDINARY_GENERATED_RARITIES:
        instance_rarity = 'common'

    enhance_level = _clamp_enhance_level(instance_row.get('enhance_level', 0))
    scaled_bonus = _scale_stat_dict(base_bonus, item_tier)
    secondary_rolls = _normalize_secondary_rolls(instance_row.get('secondary_rolls_json'))
    for roll in secondary_rolls:
        stat_key = str(roll['stat'])
        roll_value = _safe_int(roll['value'], 0)
        scaled_bonus[stat_key] = scaled_bonus.get(stat_key, 0) + roll_value
    scaled_bonus = {
        stat_key: _apply_enhancement_to_value(_safe_int(stat_value, 0), enhance_level)
        for stat_key, stat_value in scaled_bonus.items()
    }

    base_damage_min = max(0, int(round(_safe_int(base_item.get('damage_min', 0)) * _tier_scale_multiplier(item_tier))))
    base_damage_max = max(base_damage_min, int(round(_safe_int(base_item.get('damage_max', 0)) * _tier_scale_multiplier(item_tier))))
    base_defense = max(0, int(round(_safe_int(base_item.get('defense', 0)) * _tier_scale_multiplier(item_tier))))
    damage_min = _apply_enhancement_to_value(base_damage_min, enhance_level)
    damage_max = max(damage_min, _apply_enhancement_to_value(base_damage_max, enhance_level))
    defense = _apply_enhancement_to_value(base_defense, enhance_level)

    merged = dict(base_item)
    merged.update({
        'instance_id': instance_row['id'],
        'item_id': instance_row['base_item_id'],
        'enhance_level': enhance_level,
        'instance_rarity': instance_rarity,
        'item_tier': item_tier,
        'slot_identity': instance_row.get('slot_identity') or get_item_metadata(instance_row['base_item_id']).get('slot_identity'),
        'durability': instance_row.get('durability'),
        'max_durability': instance_row.get('max_durability'),
        'equipped_slot': instance_row.get('equipped_slot'),
        'secondary_rolls': secondary_rolls,
        'resolved_stat_bonus': scaled_bonus,
        'damage_min': damage_min,
        'damage_max': damage_max,
        'defense': defense,
    })
    return merged


def get_gear_instance_with_base_data(instance_row: dict[str, Any]) -> dict[str, Any]:
    return resolve_gear_instance_item_data(instance_row)


def enhance_gear_instance_once(telegram_id: int, instance_id: int, *, rng_roll: float | None = None) -> dict[str, Any]:
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT id, enhance_level FROM gear_instances WHERE telegram_id=? AND id=?',
            (telegram_id, instance_id),
        ).fetchone()
        if not row:
            return {'ok': False, 'reason': 'not_found'}

        current_level = _clamp_enhance_level(row['enhance_level'])
        if current_level >= MAX_ENHANCE_LEVEL:
            return {'ok': False, 'reason': 'max_level', 'enhance_level': current_level}

        target_level = current_level + 1
        req = get_enhance_requirements_for_target_level(target_level)
        player = conn.execute('SELECT gold FROM players WHERE telegram_id=?', (telegram_id,)).fetchone()
        if not player:
            return {'ok': False, 'reason': 'player_not_found'}
        current_gold = _safe_int(player['gold'], 0)
        if current_gold < req['gold']:
            return {'ok': False, 'reason': 'no_gold', 'need_gold': req['gold'], 'current_gold': current_gold}

        material_row = conn.execute(
            'SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (telegram_id, req['material_id']),
        ).fetchone()
        current_material = _safe_int(material_row['quantity'], 0) if material_row else 0
        if current_material < req['material_qty']:
            return {
                'ok': False,
                'reason': 'no_material',
                'material_id': req['material_id'],
                'need_material': req['material_qty'],
                'current_material': current_material,
            }

        conn.execute('UPDATE players SET gold=? WHERE telegram_id=?', (current_gold - req['gold'], telegram_id))
        new_qty = current_material - req['material_qty']
        if new_qty > 0:
            conn.execute('UPDATE inventory SET quantity=? WHERE id=?', (new_qty, material_row['id']))
        else:
            conn.execute('DELETE FROM inventory WHERE id=?', (material_row['id'],))

        outcome = resolve_enhancement_attempt_outcome(current_level, rng_roll=rng_roll)
        if outcome == 'success':
            resulting_level = target_level
            conn.execute(
                'UPDATE gear_instances SET enhance_level=? WHERE telegram_id=? AND id=?',
                (resulting_level, telegram_id, instance_id),
            )
        elif outcome == 'rollback':
            resulting_level = max(0, current_level - 1)
            conn.execute(
                'UPDATE gear_instances SET enhance_level=? WHERE telegram_id=? AND id=?',
                (resulting_level, telegram_id, instance_id),
            )
        elif outcome == 'break':
            resulting_level = None
            conn.execute('DELETE FROM gear_instances WHERE telegram_id=? AND id=?', (telegram_id, instance_id))
        else:
            resulting_level = current_level

        conn.commit()
        return {
            'ok': True,
            'outcome': outcome,
            'enhance_level_before': current_level,
            'enhance_level_after': resulting_level,
            'gold_cost': req['gold'],
            'material_id': req['material_id'],
            'material_qty': req['material_qty'],
        }
    finally:
        conn.close()


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


def _create_generated_gear_instance(
    telegram_id: int,
    item_id: str,
    *,
    conn=None,
    source: str = 'generic',
    source_level: int | None = None,
    source_metadata: RewardSourceMetadata | None = None,
    rng: random.Random | None = None,
) -> int:
    item = get_item(item_id) or {}
    if source == 'shop':
        item_tier = determine_shop_item_tier(item, player_level=_safe_int(source_level, item.get('req_level', 1)))
    elif source == 'mob_drop':
        item_tier = determine_mob_drop_item_tier(mob_level=_safe_int(source_level, item.get('req_level', 1)))
    else:
        item_tier = resolve_item_tier_band(max(_safe_int(item.get('req_level', 1)), _safe_int(source_level, 1)))

    rarity = roll_generated_rarity(rng=rng)
    if source_metadata is not None and source_metadata.quality_floor_rarity:
        rarity = clamp_rarity_to_quality_floor(rarity, source_metadata.quality_floor_rarity)
    secondary_rolls = generate_secondary_rolls_for_item(item, rarity=rarity, item_tier=item_tier, rng=rng)
    return create_gear_instance(
        telegram_id,
        item_id,
        conn=conn,
        item_tier=item_tier,
        rarity=rarity,
        secondary_rolls_json=json.dumps(secondary_rolls, ensure_ascii=False),
    )


def grant_item_to_player(
    telegram_id: int,
    item_id: str,
    quantity: int = 1,
    *,
    source: str = 'generic',
    source_level: int | None = None,
    source_metadata: RewardSourceMetadata | None = None,
    rng: random.Random | None = None,
    conn=None,
) -> dict[str, int]:
    if quantity <= 0:
        return {'gear_instances_created': 0, 'stackable_added': 0}

    if source_metadata is not None:
        reward_family = classify_item_reward_family(item_id)
        if not is_reward_family_allowed_for_source(source_metadata, reward_family):
            return {'gear_instances_created': 0, 'stackable_added': 0}

        if reward_family == 'enhancement_material':
            routing = resolve_enhancement_material_routing(item_id, source_metadata.source_category)
            if routing is not None and not routing.is_allowed:
                return {'gear_instances_created': 0, 'stackable_added': 0}

        if is_gear_item_id(item_id) and is_open_world_source_category(source_metadata.source_category):
            item = get_item(item_id) or {}
            item_level = _safe_int(item.get('req_level', 1), 1)
            if (
                source_metadata.content_tier_band_min is not None
                and source_metadata.content_tier_band_max is not None
                and not is_item_tier_band_allowed_for_bounds(
                    item_level=item_level,
                    tier_band_min=source_metadata.content_tier_band_min,
                    tier_band_max=source_metadata.content_tier_band_max,
                )
            ):
                return {'gear_instances_created': 0, 'stackable_added': 0}
            if not is_gear_item_allowed_for_open_world_content_identity(
                item_id=item_id,
                source_id=source_metadata.content_identity,
            ):
                return {'gear_instances_created': 0, 'stackable_added': 0}

    if is_gear_item_id(item_id):
        created = 0
        for _ in range(quantity):
            _create_generated_gear_instance(
                telegram_id,
                item_id,
                conn=conn,
                source=source,
                source_level=source_level,
                source_metadata=source_metadata,
                rng=rng,
            )
            created += 1
        return {'gear_instances_created': created, 'stackable_added': 0}

    owns_connection = conn is None
    if owns_connection:
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
        if owns_connection:
            conn.commit()
        return {'gear_instances_created': 0, 'stackable_added': quantity}
    finally:
        if owns_connection:
            conn.close()
