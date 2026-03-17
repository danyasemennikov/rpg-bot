# ============================================================
# locations.py — все локации игры
# ============================================================

LOCATIONS = {

    'village': {
        'id':          'village',
        'name':        '🏘️ Пепельная Деревня',
        'description': 'Мирные поля, тихая деревушка на краю тёмного леса. Здесь можно отдохнуть, закупиться и взять квесты.',
        'level_min':   1,
        'level_max':   999,  # безопасная зона
        'safe':        True,  # мобы не атакуют, нельзя умереть
        'mobs':        [],    # мобов нет
        'connections': ['dark_forest', 'old_mines'],  # куда можно пойти
        'services':    ['shop', 'inn', 'quest_board'],
        'gather':      [],    # ресурсы для сбора
    },

    'dark_forest': {
        'id':          'dark_forest',
        'name':        '🌲 Тёмный лес',
        'description': 'Густой лес, пронизанный тьмой. Здесь рыщут волки, а на деревьях затаились пауки.',
        'level_min':   1,
        'level_max':   5,
        'safe':        False,
        'mobs':        ['forest_wolf', 'forest_boar', 'forest_spider', 'dark_treant'],
        'connections': ['village'],
        'services':    [],
        'gather':      [
            ('herb_common',  0.40, '🌿 Обычная трава'),
            ('herb_magic',   0.10, '✨ Магическая трава'),
            ('wood_dark',    0.50, '🪵 Тёмное дерево'),
        ],
    },

    'old_mines': {
        'id':          'old_mines',
        'name':        '⛏️ Старые шахты',
        'description': 'Заброшенные шахты, населённые гоблинами и жуткими тварями. Богаты рудой, но таят в себе опасности.',
        'level_min':   3,
        'level_max':   8,
        'safe':        False,
        'mobs':        ['mine_rat', 'goblin_miner', 'cave_bat', 'stone_golem'],
        'connections': ['village'],
        'services':    [],
        'gather':      [
            ('iron_ore',     0.55, '⛏️ Железная руда'),
            ('coal',         0.35, '🪨 Уголь'),
            ('gem_common',   0.08, '💎 Обычный драгоценный камень'),
        ],
    },
}

def get_location(location_id: str) -> dict:
    return LOCATIONS.get(location_id)

def get_connected_locations(location_id: str) -> list:
    """Локации куда можно перейти."""
    loc = get_location(location_id)
    if not loc:
        return []
    return [LOCATIONS[lid] for lid in loc['connections'] if lid in LOCATIONS]

print('✅ game/locations.py создан!')
print(f'   Локаций в базе: {len(LOCATIONS)}')
