# ============================================================
# seed.py — заполняет БД начальными данными
# ============================================================

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection
from game.items_data import ITEMS
from game.profession_resources import MANDATORY_RESOURCE_IDS

PEV1_CONSUMABLE_IDS = (
    'health_potion_small', 'mana_potion', 'health_potion', 'field_ration',
    'pe_mana_potion_medium', 'pe_health_potion_large', 'pe_mana_potion_large',
    'pe_shore_broth', 'pe_marsh_stew', 'pe_boar_feast', 'pe_oasis_meal', 'pe_deep_marsh_meal',
)

def seed_items():
    conn = get_connection()
    count = 0
    for item in ITEMS.values():
        existing = conn.execute(
            'SELECT item_id FROM items WHERE item_id=?', (item['item_id'],)
        ).fetchone()
        if not existing:
            conn.execute('''
                INSERT INTO items (
                    item_id, name, description, item_type, weapon_type,
                    rarity, damage_min, damage_max, defense, weight,
                    req_level, req_strength, req_agility, req_intuition, req_wisdom,
                    buy_price, sell_price, skills_json, stat_bonus_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                item['item_id'], item['name'], item['description'],
                item['item_type'], item['weapon_type'], item['rarity'],
                item['damage_min'], item['damage_max'], item['defense'], item['weight'],
                item['req_level'], item['req_strength'], item['req_agility'],
                item['req_intuition'], item['req_wisdom'],
                item['buy_price'], item['sell_price'],
                item['skills_json'], item['stat_bonus_json']
            ))
            count += 1
    # Named V1 reconciliation: existing instances resolve their immutable
    # identity/rolls against this corrected central base on the next snapshot.
    staff = ITEMS['magic_staff']
    conn.execute('''UPDATE items SET damage_min=?, damage_max=?
        WHERE item_id='magic_staff' AND (damage_min<>? OR damage_max<>?)''',
        (staff['damage_min'], staff['damage_max'], staff['damage_min'], staff['damage_max']))
    # PEV1 deliberately reconciles only its versioned material/consumable whitelist.
    for item_id in MANDATORY_RESOURCE_IDS + PEV1_CONSUMABLE_IDS:
        item = ITEMS[item_id]
        conn.execute('''UPDATE items SET item_type=?, buy_price=?, sell_price=?,
            stat_bonus_json=?, weight=? WHERE item_id=?''',
            (item['item_type'], item['buy_price'], item['sell_price'],
             item['stat_bonus_json'], item['weight'], item_id))
    conn.commit()
    conn.close()
    print(f'✅ Загружено предметов: {count}')

if __name__ == '__main__':
    seed_items()
