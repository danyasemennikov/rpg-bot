import json
from typing import Any

from database import get_connection
from game.balance import calc_magic_defense, calc_max_hp, calc_max_mana, calc_physical_defense
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
    """Returns equipped item_id by slot, supporting both legacy and slot-row layouts."""
    conn = get_connection()
    try:
        equipment_columns = {
            row['name']
            for row in conn.execute('PRAGMA table_info(equipment)').fetchall()
        }

        if {'slot', 'item_id'}.issubset(equipment_columns):
            rows = conn.execute(
                'SELECT slot, item_id FROM equipment WHERE telegram_id=?',
                (telegram_id,),
            ).fetchall()
            out: dict[str, str] = {}
            for row in rows:
                if row['slot'] in EQUIPMENT_SLOT_KEYS:
                    out[row['slot']] = row['item_id']
            return out

        equipped = conn.execute(
            'SELECT * FROM equipment WHERE telegram_id=?',
            (telegram_id,),
        ).fetchone()
        if not equipped:
            return {}

        out: dict[str, str] = {}
        for slot in EQUIPMENT_SLOT_KEYS:
            inv_id = equipped[slot]
            if inv_id is None:
                continue
            inv_row = conn.execute(
                'SELECT item_id FROM inventory WHERE telegram_id=? AND id=?',
                (telegram_id, inv_id),
            ).fetchone()
            if inv_row:
                out[slot] = inv_row['item_id']
        return out
    finally:
        conn.close()


def aggregate_equipped_stat_bonuses(telegram_id: int) -> dict[str, int]:
    equipped_item_ids = get_equipped_item_ids(telegram_id)
    total: dict[str, int] = {}

    for item_id in equipped_item_ids.values():
        item = get_item(item_id)
        for stat_key, stat_value in _parse_item_stat_bonus(item).items():
            total[stat_key] = total.get(stat_key, 0) + stat_value

    return total


def build_effective_player_stats(player: dict, equipment_bonuses: dict[str, int]) -> dict[str, int]:
    effective_strength = _safe_int(player.get('strength', 0)) + _safe_int(equipment_bonuses.get('strength', 0))
    effective_agility = _safe_int(player.get('agility', 0)) + _safe_int(equipment_bonuses.get('agility', 0))
    effective_intuition = _safe_int(player.get('intuition', 0)) + _safe_int(equipment_bonuses.get('intuition', 0))
    effective_vitality = _safe_int(player.get('vitality', 0)) + _safe_int(equipment_bonuses.get('vitality', 0))
    effective_wisdom = _safe_int(player.get('wisdom', 0)) + _safe_int(equipment_bonuses.get('wisdom', 0))
    effective_luck = _safe_int(player.get('luck', 0)) + _safe_int(equipment_bonuses.get('luck', 0))

    max_hp_bonus = _safe_int(equipment_bonuses.get('max_hp', 0))
    max_mana_bonus = _safe_int(equipment_bonuses.get('max_mana', 0))
    physical_defense_bonus = _safe_int(equipment_bonuses.get('physical_defense', 0))
    magic_defense_bonus = _safe_int(equipment_bonuses.get('magic_defense', 0))

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
        'accuracy_bonus': _safe_int(equipment_bonuses.get('accuracy', 0)),
        'evasion_bonus': _safe_int(equipment_bonuses.get('evasion', 0)),
        'effective_physical_defense': effective_physical_defense,
        'effective_magic_defense': effective_magic_defense,
        'block_chance_bonus': _safe_int(equipment_bonuses.get('block_chance', 0)),
        'magic_power_bonus': _safe_int(equipment_bonuses.get('magic_power', 0)),
        'healing_power_bonus': _safe_int(equipment_bonuses.get('healing_power', 0)),
    }


def get_player_effective_stats(telegram_id: int, player: dict) -> dict[str, Any]:
    equipment_bonuses = aggregate_equipped_stat_bonuses(telegram_id)
    effective = build_effective_player_stats(player, equipment_bonuses)
    effective['equipment_bonuses'] = equipment_bonuses
    return effective


def clamp_player_resources_to_effective_caps(telegram_id: int, player: dict | None = None) -> dict[str, int | bool]:
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
