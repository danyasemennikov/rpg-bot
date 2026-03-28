import json
from typing import Any

from database import get_connection
from game.balance import calc_magic_defense, calc_max_hp, calc_max_mana, calc_physical_defense
from game.gear_instances import (
    get_equipped_gear_instances,
    resolve_equipped_item_ids_with_fallback,
    resolve_gear_instance_item_data,
)
from game.items_data import get_item

EQUIPMENT_SLOT_KEYS = (
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

RUNTIME_EQUIPMENT_STATS = {
    'max_hp',
    'max_mana',
    'physical_defense',
    'magic_defense',
    'accuracy',
    'evasion',
    'block_chance',
    'magic_power',
    'healing_power',
}




def _normalize_player_record(player: Any) -> dict[str, Any]:
    if isinstance(player, dict):
        return player
    if player is None:
        return {}
    try:
        normalized = dict(player)
    except (TypeError, ValueError):
        return {}
    return normalized if isinstance(normalized, dict) else {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_item_stat_bonus(item: dict | None) -> dict[str, int]:
    if not item:
        return {}

    raw_bonus = item.get('stat_bonus_json', '{}')
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


def get_equipped_item_ids(telegram_id: int) -> dict[str, str]:
    """Returns equipped item_id by slot, instance-first with legacy fallback."""
    return resolve_equipped_item_ids_with_fallback(telegram_id)


def aggregate_equipped_stat_bonuses(telegram_id: int) -> dict[str, int]:
    total: dict[str, int] = {}

    equipped_instances = get_equipped_gear_instances(telegram_id)
    occupied_slots = set(equipped_instances.keys())
    for instance_row in equipped_instances.values():
        resolved = resolve_gear_instance_item_data(instance_row)
        for stat_key, stat_value in resolved.get('resolved_stat_bonus', {}).items():
            total[stat_key] = total.get(stat_key, 0) + _safe_int(stat_value, 0)

    conn = get_connection()
    try:
        legacy = conn.execute('SELECT * FROM equipment WHERE telegram_id=?', (telegram_id,)).fetchone()
        if not legacy:
            return total

        for slot in EQUIPMENT_SLOT_KEYS:
            if slot in occupied_slots:
                continue
            inv_id = legacy[slot]
            if inv_id is None:
                continue
            inv_row = conn.execute(
                'SELECT item_id FROM inventory WHERE telegram_id=? AND id=?',
                (telegram_id, inv_id),
            ).fetchone()
            if not inv_row:
                continue
            item = get_item(inv_row['item_id'])
            for stat_key, stat_value in _parse_item_stat_bonus(item).items():
                total[stat_key] = total.get(stat_key, 0) + stat_value
    finally:
        conn.close()

    return total


def build_runtime_equipment_bonus_channels(equipment_bonuses: dict[str, int]) -> dict[str, int]:
    """
    Нормализует только runtime-поддерживаемые каналы бонусов экипировки.
    Центральная точка для интеграции рантайм-хуков.
    """
    normalized: dict[str, int] = {}
    for stat_key in RUNTIME_EQUIPMENT_STATS:
        normalized[stat_key] = _safe_int(equipment_bonuses.get(stat_key, 0))
    return normalized


def build_effective_player_stats(player: Any, equipment_bonuses: dict[str, int]) -> dict[str, int]:
    player = _normalize_player_record(player)
    runtime_bonus_channels = build_runtime_equipment_bonus_channels(equipment_bonuses)

    effective_strength = _safe_int(player.get('strength', 0)) + _safe_int(equipment_bonuses.get('strength', 0))
    effective_agility = _safe_int(player.get('agility', 0)) + _safe_int(equipment_bonuses.get('agility', 0))
    effective_intuition = _safe_int(player.get('intuition', 0)) + _safe_int(equipment_bonuses.get('intuition', 0))
    effective_vitality = _safe_int(player.get('vitality', 0)) + _safe_int(equipment_bonuses.get('vitality', 0))
    effective_wisdom = _safe_int(player.get('wisdom', 0)) + _safe_int(equipment_bonuses.get('wisdom', 0))
    effective_luck = _safe_int(player.get('luck', 0)) + _safe_int(equipment_bonuses.get('luck', 0))

    max_hp_bonus = runtime_bonus_channels['max_hp']
    max_mana_bonus = runtime_bonus_channels['max_mana']
    physical_defense_bonus = runtime_bonus_channels['physical_defense']
    magic_defense_bonus = runtime_bonus_channels['magic_defense']

    base_vitality = _safe_int(player.get('vitality', 0))
    base_wisdom = _safe_int(player.get('wisdom', 0))
    vitality_derived_max_hp_bonus = calc_max_hp(effective_vitality) - calc_max_hp(base_vitality)
    wisdom_derived_max_mana_bonus = calc_max_mana(effective_wisdom) - calc_max_mana(base_wisdom)

    effective_max_hp = max(
        1,
        _safe_int(player.get('max_hp', 1)) + max_hp_bonus + vitality_derived_max_hp_bonus,
    )
    effective_max_mana = max(
        0,
        _safe_int(player.get('max_mana', 0)) + max_mana_bonus + wisdom_derived_max_mana_bonus,
    )

    effective_physical_defense = (
        calc_physical_defense(effective_vitality) + physical_defense_bonus
    )
    effective_magic_defense = (
        calc_magic_defense(effective_wisdom) + magic_defense_bonus
    )

    return {
        'strength': effective_strength,
        'agility': effective_agility,
        'intuition': effective_intuition,
        'vitality': effective_vitality,
        'wisdom': effective_wisdom,
        'luck': effective_luck,
        'max_hp': effective_max_hp,
        'max_mana': effective_max_mana,
        'max_hp_bonus': max_hp_bonus,
        'max_mana_bonus': max_mana_bonus,
        'physical_defense_bonus': physical_defense_bonus,
        'magic_defense_bonus': magic_defense_bonus,
        'accuracy_bonus': runtime_bonus_channels['accuracy'],
        'evasion_bonus': runtime_bonus_channels['evasion'],
        'effective_physical_defense': effective_physical_defense,
        'effective_magic_defense': effective_magic_defense,
        'block_chance_bonus': runtime_bonus_channels['block_chance'],
        'magic_power_bonus': runtime_bonus_channels['magic_power'],
        'healing_power_bonus': runtime_bonus_channels['healing_power'],
    }


def get_player_effective_stats(telegram_id: int, player: Any) -> dict[str, Any]:
    player = _normalize_player_record(player)
    equipment_bonuses = aggregate_equipped_stat_bonuses(telegram_id)
    effective = build_effective_player_stats(player, equipment_bonuses)
    effective['equipment_bonuses'] = equipment_bonuses
    effective['runtime_equipment_bonuses'] = build_runtime_equipment_bonus_channels(equipment_bonuses)
    return effective


def clamp_player_resources_to_effective_caps(telegram_id: int, player: Any = None) -> dict[str, int | bool]:
    """
    Clamps current HP/Mana against effective caps derived from currently equipped gear.
    Returns clamped values and whether an UPDATE was executed.
    """
    loaded_player = player
    conn = get_connection()
    try:
        if loaded_player is None:
            row = conn.execute(
                'SELECT hp, mana, max_hp, max_mana, strength, agility, intuition, vitality, wisdom, luck '
                'FROM players WHERE telegram_id=?',
                (telegram_id,),
            ).fetchone()
            if not row:
                return {'changed': False, 'hp': 0, 'mana': 0, 'max_hp': 0, 'max_mana': 0}
            loaded_player = dict(row)

        loaded_player = _normalize_player_record(loaded_player)
        effective = get_player_effective_stats(telegram_id, loaded_player)
        clamped_hp = min(_safe_int(loaded_player.get('hp', 0)), effective['max_hp'])
        clamped_mana = min(_safe_int(loaded_player.get('mana', 0)), effective['max_mana'])
        changed = (
            clamped_hp != _safe_int(loaded_player.get('hp', 0))
            or clamped_mana != _safe_int(loaded_player.get('mana', 0))
        )
        if changed:
            conn.execute(
                'UPDATE players SET hp=?, mana=? WHERE telegram_id=?',
                (clamped_hp, clamped_mana, telegram_id),
            )
            conn.commit()

        return {
            'changed': changed,
            'hp': clamped_hp,
            'mana': clamped_mana,
            'max_hp': effective['max_hp'],
            'max_mana': effective['max_mana'],
        }
    finally:
        conn.close()
