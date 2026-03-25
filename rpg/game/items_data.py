# ============================================================
# items_data.py — все предметы игры
# ============================================================

ITEMS = {

    # ── ОРУЖИЕ ──────────────────────────────────────────────

    'wooden_sword': {
        'item_id': 'wooden_sword', 'name': '🗡️ Деревянный меч',
        'description': 'Простой меч из дерева. Лучше чем ничего.',
        'item_type': 'weapon', 'weapon_type': 'melee', 'weapon_profile': 'sword_1h',
        'rarity': 'common',
        'damage_min': 5, 'damage_max': 8, 'defense': 0, 'weight': 3,
        'req_level': 1, 'req_strength': 0, 'req_agility': 0,
        'req_intuition': 0, 'req_wisdom': 0,
        'buy_price': 50, 'sell_price': 10,
        'skills_json': '[]', 'stat_bonus_json': '{}',
    },
    'iron_sword': {
        'item_id': 'iron_sword', 'name': '⚔️ Железный меч',
        'description': 'Надёжный железный меч.',
        'item_type': 'weapon', 'weapon_type': 'melee', 'weapon_profile': 'sword_1h',
        'rarity': 'common',
        'damage_min': 12, 'damage_max': 18, 'defense': 0, 'weight': 4,
        'req_level': 3, 'req_strength': 5, 'req_agility': 0,
        'req_intuition': 0, 'req_wisdom': 0,
        'buy_price': 200, 'sell_price': 50,
        'skills_json': '[]', 'stat_bonus_json': '{"strength": 2}',
    },
    'short_bow': {
        'item_id': 'short_bow', 'name': '🏹 Короткий лук',
        'description': 'Лёгкий лук для быстрой стрельбы.',
        'item_type': 'weapon', 'weapon_type': 'ranged', 'weapon_profile': 'bow',
        'rarity': 'common',
        'damage_min': 8, 'damage_max': 14, 'defense': 0, 'weight': 2,
        'req_level': 1, 'req_strength': 0, 'req_agility': 3,
        'req_intuition': 0, 'req_wisdom': 0,
        'buy_price': 80, 'sell_price': 20,
        'skills_json': '[]', 'stat_bonus_json': '{"agility": 1}',
    },
    'magic_staff': {
        'item_id': 'magic_staff', 'name': '🔮 Магический посох',
        'description': 'Посох начинающего мага.',
        'item_type': 'weapon', 'weapon_type': 'magic', 'weapon_profile': 'magic_staff',
        'rarity': 'uncommon',
        'damage_min': 80, 'damage_max': 100, 'defense': 0, 'weight': 3,
        'req_level': 3, 'req_strength': 0, 'req_agility': 0,
        'req_intuition': 5, 'req_wisdom': 0,
        'buy_price': 300, 'sell_price': 80,
        'skills_json': '[]', 'stat_bonus_json': '{"intuition": 2}',
    },
    'holy_staff': {
        'item_id': 'holy_staff', 'name': '✨ Святой посох',
        'description': 'Посох жреца. Наносит урон светом и лечит союзников.',
        'item_type': 'weapon', 'weapon_type': 'light', 'weapon_profile': 'holy_staff',
        'rarity': 'uncommon',
        'damage_min': 10, 'damage_max': 16, 'defense': 0, 'weight': 3,
        'req_level': 3, 'req_strength': 0, 'req_agility': 0,
        'req_intuition': 0, 'req_wisdom': 5,
        'buy_price': 300, 'sell_price': 80,
        'skills_json': '[]', 'stat_bonus_json': '{"wisdom": 2}',
    },
    'holy_rod': {
        'item_id': 'holy_rod', 'name': '🪄 Священный жезл',
        'description': 'Боевой жезл паладина. Сочетает святую защиту и карающий свет.',
        'item_type': 'weapon', 'weapon_type': 'light', 'weapon_profile': 'holy_rod',
        'rarity': 'uncommon',
        'damage_min': 9, 'damage_max': 14, 'defense': 0, 'weight': 2,
        'req_level': 3, 'req_strength': 0, 'req_agility': 0,
        'req_intuition': 0, 'req_wisdom': 5,
        'buy_price': 290, 'sell_price': 75,
        'skills_json': '[]', 'stat_bonus_json': '{"wisdom": 2}',
    },
    'tome': {
        'item_id': 'tome', 'name': '📚 Том чародея',
        'description': 'Гримуар поддержки и смешанных школ. Даёт гибкость, а не максимальный профиль.',
        'item_type': 'weapon', 'weapon_type': 'magic', 'weapon_profile': 'tome',
        'rarity': 'uncommon',
        'damage_min': 8, 'damage_max': 13, 'defense': 0, 'weight': 2,
        'req_level': 3, 'req_strength': 0, 'req_agility': 0,
        'req_intuition': 3, 'req_wisdom': 3,
        'buy_price': 285, 'sell_price': 72,
        'skills_json': '[]', 'stat_bonus_json': '{"intuition": 1, "wisdom": 1}',
    },
    'dagger': {
        'item_id': 'dagger', 'name': '🗡️ Кинжал',
        'description': 'Быстрый и лёгкий кинжал.',
        'item_type': 'weapon', 'weapon_type': 'melee', 'weapon_profile': 'daggers',
        'rarity': 'common',
        'damage_min': 7, 'damage_max': 11, 'defense': 0, 'weight': 1,
        'req_level': 1, 'req_strength': 0, 'req_agility': 3,
        'req_intuition': 0, 'req_wisdom': 0,
        'buy_price': 60, 'sell_price': 15,
        'skills_json': '[]', 'stat_bonus_json': '{"agility": 2}',
    },

    # ── БРОНЯ ────────────────────────────────────────────────

    'leather_armor': {
        'item_id': 'leather_armor', 'name': '🥋 Кожаная броня',
        'description': 'Лёгкая броня из кожи.',
        'item_type': 'armor', 'weapon_type': None, 'armor_class': 'medium',
        'rarity': 'common',
        'damage_min': 0, 'damage_max': 0, 'defense': 5, 'weight': 4,
        'req_level': 1, 'req_strength': 0, 'req_agility': 0,
        'req_intuition': 0, 'req_wisdom': 0,
        'buy_price': 100, 'sell_price': 25,
        'skills_json': '[]', 'stat_bonus_json': '{}',
    },
    'iron_shield': {
        'item_id': 'iron_shield', 'name': '🛡️ Железный щит',
        'description': 'Надёжная защита.',
        'item_type': 'armor', 'weapon_type': None,
        'offhand_profile': 'shield', 'encumbrance': 2,
        'rarity': 'common',
        'damage_min': 0, 'damage_max': 0, 'defense': 8, 'weight': 6,
        'req_level': 3, 'req_strength': 5, 'req_agility': 0,
        'req_intuition': 0, 'req_wisdom': 0,
        'buy_price': 180, 'sell_price': 45,
        'skills_json': '[]', 'stat_bonus_json': '{"vitality": 1}',
    },

    # ── ЗЕЛЬЯ ────────────────────────────────────────────────

    'health_potion_small': {
        'item_id': 'health_potion_small', 'name': '🧪 Малое зелье HP',
        'description': 'Восстанавливает 30 HP.',
        'item_type': 'potion', 'weapon_type': None,
        'rarity': 'common',
        'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1,
        'req_level': 1, 'req_strength': 0, 'req_agility': 0,
        'req_intuition': 0, 'req_wisdom': 0,
        'buy_price': 30, 'sell_price': 5,
        'skills_json': '[]', 'stat_bonus_json': '{"heal": 30}',
    },
    'health_potion': {
        'item_id': 'health_potion', 'name': '❤️ Зелье HP',
        'description': 'Восстанавливает 80 HP.',
        'item_type': 'potion', 'weapon_type': None,
        'rarity': 'common',
        'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1,
        'req_level': 1, 'req_strength': 0, 'req_agility': 0,
        'req_intuition': 0, 'req_wisdom': 0,
        'buy_price': 80, 'sell_price': 15,
        'skills_json': '[]', 'stat_bonus_json': '{"heal": 80}',
    },
    'mana_potion': {
        'item_id': 'mana_potion', 'name': '🔵 Зелье маны',
        'description': 'Восстанавливает 50 маны.',
        'item_type': 'potion', 'weapon_type': None,
        'rarity': 'common',
        'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1,
        'req_level': 1, 'req_strength': 0, 'req_agility': 0,
        'req_intuition': 0, 'req_wisdom': 0,
        'buy_price': 60, 'sell_price': 12,
        'skills_json': '[]', 'stat_bonus_json': '{"mana": 50}',
    },

    # ── МАТЕРИАЛЫ ────────────────────────────────────────────

    'wolf_pelt':    {'item_id': 'wolf_pelt',    'name': '🐺 Шкура волка',     'description': 'Материал для крафта.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'common', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 8,  'skills_json': '[]', 'stat_bonus_json': '{}'},
    'wolf_fang':    {'item_id': 'wolf_fang',    'name': '🦷 Клык волка',      'description': 'Острый клык.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'common', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 12, 'skills_json': '[]', 'stat_bonus_json': '{}'},
    'boar_meat':    {'item_id': 'boar_meat',    'name': '🥩 Мясо кабана',     'description': 'Съедобное мясо.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'common', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 2, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 5,  'skills_json': '[]', 'stat_bonus_json': '{}'},
    'boar_tusk':    {'item_id': 'boar_tusk',    'name': '🐗 Бивень кабана',   'description': 'Прочный бивень.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'common', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 10, 'skills_json': '[]', 'stat_bonus_json': '{}'},
    'spider_silk':  {'item_id': 'spider_silk',  'name': '🕸️ Паучий шёлк',    'description': 'Прочная нить.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'uncommon', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 18, 'skills_json': '[]', 'stat_bonus_json': '{}'},
    'spider_venom': {'item_id': 'spider_venom', 'name': '☠️ Яд паука',        'description': 'Используется в крафте зелий.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'uncommon', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 25, 'skills_json': '[]', 'stat_bonus_json': '{}'},
    'ancient_bark': {'item_id': 'ancient_bark', 'name': '🪵 Древняя кора',    'description': 'Редкий материал.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'uncommon', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 2, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 30, 'skills_json': '[]', 'stat_bonus_json': '{}'},
    'treant_heart': {'item_id': 'treant_heart', 'name': '💚 Сердце трента',   'description': 'Пульсирует древней силой.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'rare', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 80, 'skills_json': '[]', 'stat_bonus_json': '{}'},
    'iron_ore':     {'item_id': 'iron_ore',     'name': '⛏️ Железная руда',  'description': 'Руда для крафта.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'common', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 3, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 6,  'skills_json': '[]', 'stat_bonus_json': '{}'},
    'goblin_ear':   {'item_id': 'goblin_ear',   'name': '👺 Ухо гоблина',     'description': 'Квестовый предмет.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'common', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 7,  'skills_json': '[]', 'stat_bonus_json': '{}'},
    'bat_wing':     {'item_id': 'bat_wing',     'name': '🦇 Крыло летучей мыши', 'description': 'Материал для зелий.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'common', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 9,  'skills_json': '[]', 'stat_bonus_json': '{}'},
    'stone_core':   {'item_id': 'stone_core',   'name': '🗿 Каменное ядро',   'description': 'Магический кристалл голема.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'rare', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 3, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 60, 'skills_json': '[]', 'stat_bonus_json': '{}'},
    'rat_tail':     {'item_id': 'rat_tail',     'name': '🐀 Хвост крысы',     'description': 'Квестовый предмет.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'common', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 4,  'skills_json': '[]', 'stat_bonus_json': '{}'},
    'worn_pickaxe': {'item_id': 'worn_pickaxe', 'name': '⛏️ Сломанная кирка', 'description': 'Почти бесполезна.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'common', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 3, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 3,  'skills_json': '[]', 'stat_bonus_json': '{}'},
    'coal':         {'item_id': 'coal',         'name': '🪨 Уголь',           'description': 'Топливо для кузни.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'common', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 2, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 4,  'skills_json': '[]', 'stat_bonus_json': '{}'},
    'gem_common':   {'item_id': 'gem_common',   'name': '💎 Обычный камень',  'description': 'Используется в крафте.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'uncommon', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 35, 'skills_json': '[]', 'stat_bonus_json': '{}'},
    'golem_fragment':{'item_id':'golem_fragment','name': '🗿 Фрагмент голема', 'description': 'Прочный материал.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'uncommon', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 2, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 22, 'skills_json': '[]', 'stat_bonus_json': '{}'},
    'rat_fur':      {'item_id': 'rat_fur',      'name': '🐀 Шкура крысы',     'description': 'Дешёвый материал.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'common', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 3,  'skills_json': '[]', 'stat_bonus_json': '{}'},
    'herb_common':  {'item_id': 'herb_common',  'name': '🌿 Обычная трава',    'description': 'Материал для крафта.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'common',   'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 3,  'skills_json': '[]', 'stat_bonus_json': '{}'},
    'herb_magic':   {'item_id': 'herb_magic',   'name': '✨ Магическая трава',  'description': 'Редкий магический ингредиент.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'uncommon', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 1, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 12, 'skills_json': '[]', 'stat_bonus_json': '{}'},
    'wood_dark':    {'item_id': 'wood_dark',    'name': '🌑 Тёмное дерево',    'description': 'Древесина из тёмного леса.', 'item_type': 'material', 'weapon_type': None, 'rarity': 'uncommon', 'damage_min': 0, 'damage_max': 0, 'defense': 0, 'weight': 2, 'req_level': 1, 'req_strength': 0, 'req_agility': 0, 'req_intuition': 0, 'req_wisdom': 0, 'buy_price': 0, 'sell_price': 10, 'skills_json': '[]', 'stat_bonus_json': '{}'},
}

def get_item(item_id: str) -> dict:
    return ITEMS.get(item_id)


def get_item_encumbrance(item: dict | None) -> int | None:
    """Возвращает semantic encumbrance или fallback на вес предмета."""
    if not item:
        return None
    return item.get('encumbrance', item.get('weight'))

print(f'✅ game/items_data.py создан! Предметов: {len(ITEMS)}')
