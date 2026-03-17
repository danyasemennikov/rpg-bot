# ============================================================
# mobs.py — все мобы игры
# ============================================================

# Структура моба:
# id, name, level, hp, damage_min, damage_max,
# weapon_type, exp_reward, gold_min, gold_max,
# aggressive (атакует сам), loot_table

MOBS = {

    # ── ТЁМНЫЙ ЛЕС (ур. 1-5) ────────────────────────────────

    'forest_wolf': {
        'id':          'forest_wolf',
        'name':        '🐺 Лесной волк',
        'level':       2,
        'hp':          45,
        'damage_min':  6,
        'damage_max':  10,
        'weapon_type': 'melee',
        'exp_reward':  20,
        'gold_min':    2,
        'gold_max':    5,
        'aggressive':  False,
        'loot_table':  [
            ('wolf_pelt',   0.60),   # 60% шанс
            ('wolf_fang',   0.25),
            ('health_potion_small', 0.10),
        ]
    },

    'forest_boar': {
        'id':          'forest_boar',
        'name':        '🐗 Лесной кабан',
        'level':       1,
        'hp':          60,
        'damage_min':  4,
        'damage_max':  7,
        'weapon_type': 'melee',
        'exp_reward':  12,
        'gold_min':    1,
        'gold_max':    3,
        'aggressive':  False,
        'loot_table':  [
            ('boar_meat',   0.75),
            ('boar_tusk',   0.20),
        ]
    },

    'forest_spider': {
        'id':          'forest_spider',
        'name':        '🕷️ Ядовитый паук',
        'level':       3,
        'hp':          35,
        'damage_min':  5,
        'damage_max':  8,
        'weapon_type': 'melee',
        'exp_reward':  25,
        'gold_min':    3,
        'gold_max':    6,
        'aggressive':  False,
        'effects':     [('poison', 0.40, 3)],  # 40% шанс яда на 3 хода
        'loot_table':  [
            ('spider_silk',  0.50),
            ('spider_venom', 0.30),
        ]
    },

    'dark_treant': {
        'id':          'dark_treant',
        'name':        '🌳 Тёмный трент',
        'level':       5,
        'hp':          500000,
        'damage_min':  10,
        'damage_max':  15,
        'weapon_type': 'melee',
        'exp_reward':  55,
        'gold_min':    8,
        'gold_max':    15,
        'aggressive':  False,
        'loot_table':  [
            ('ancient_bark',  0.55),
            ('treant_heart',  0.15),
            ('iron_sword',    0.05),   # редкий дроп оружия
        ]
    },

    # ── СТАРЫЕ ШАХТЫ (ур. 3-8) ──────────────────────────────

    'mine_rat': {
        'id':          'mine_rat',
        'name':        '🐀 Шахтная крыса',
        'level':       3,
        'hp':          30,
        'damage_min':  5,
        'damage_max':  9,
        'weapon_type': 'melee',
        'exp_reward':  18,
        'gold_min':    1,
        'gold_max':    4,
        'aggressive':  False,
        'loot_table':  [
            ('rat_tail',    0.50),
            ('rat_fur',     0.30),
        ]
    },

    'goblin_miner': {
        'id':          'goblin_miner',
        'name':        '👺 Гоблин-шахтёр',
        'level':       4,
        'hp':          55,
        'damage_min':  8,
        'damage_max':  13,
        'weapon_type': 'melee',
        'exp_reward':  35,
        'gold_min':    5,
        'gold_max':    12,
        'aggressive':  True,
        'loot_table':  [
            ('iron_ore',        0.60),
            ('goblin_ear',      0.40),
            ('worn_pickaxe',    0.15),
        ]
    },

    'cave_bat': {
        'id':          'cave_bat',
        'name':        '🦇 Пещерная летучая мышь',
        'level':       3,
        'hp':          25,
        'damage_min':  4,
        'damage_max':  7,
        'weapon_type': 'melee',
        'exp_reward':  15,
        'gold_min':    0,
        'gold_max':    2,
        'aggressive':  False,
        'loot_table':  [
            ('bat_wing',    0.45),
        ]
    },

    'stone_golem': {
        'id':          'stone_golem',
        'name':        '🗿 Каменный голем',
        'level':       8,
        'hp':          200,
        'damage_min':  20,
        'damage_max':  30,
        'weapon_type': 'melee',
        'exp_reward':  120,
        'gold_min':    15,
        'gold_max':    30,
        'aggressive':  False,
        'loot_table':  [
            ('stone_core',      0.40),
            ('golem_fragment',  0.25),
            ('iron_shield',     0.08),
        ]
    },
}

def get_mob(mob_id: str) -> dict:
    """Получить моба по ID. Возвращает копию чтобы не менять оригинал."""
    mob = MOBS.get(mob_id)
    if mob:
        return dict(mob)  # копия!
    return None

def get_mobs_for_location(mob_ids: list) -> list:
    """Получить список мобов для локации."""
    return [get_mob(mid) for mid in mob_ids if get_mob(mid)]

print('✅ game/mobs.py создан!')
print(f'   Мобов в базе: {len(MOBS)}')
