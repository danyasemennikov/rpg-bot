# ============================================================
# locations.py — все локации игры
# ============================================================

LOCATIONS = {

    'village': {
        'id':          'village',
        'world_id':    'ashen_continent',
        'region_id':   'ember_valley',
        'zone_id':     'ember_village',
        'zone_role':   'normal',
        'region_flavor_tags': ['civilized_frontier', 'ashen_farmland'],
        'linked_dungeon_id': None,
        'world_boss_governance_id': 'ember_valley_world_boss',
        'future_pvp_ruleset_id': 'open_world_frontier',
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
        'world_id':    'ashen_continent',
        'region_id':   'ember_valley',
        'zone_id':     'dark_forest',
        'zone_role':   'normal',
        'region_flavor_tags': ['beast_hunting', 'poison_herbs', 'dark_wood'],
        'linked_dungeon_id': 'rootbound_hollow',
        'world_boss_governance_id': 'ember_valley_world_boss',
        'future_pvp_ruleset_id': 'open_world_frontier',
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
        'world_id':    'ashen_continent',
        'region_id':   'ember_valley',
        'zone_id':     'old_mines',
        'zone_role':   'elite',
        'region_flavor_tags': ['ore_veins', 'construct_ruins', 'goblin_camps'],
        'linked_dungeon_id': 'amber_catacombs',
        'world_boss_governance_id': 'ember_valley_world_boss',
        'future_pvp_ruleset_id': 'open_world_frontier',
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

MOB_LOCATION_INDEX: dict[str, str] = {}
for _location_id, _location_data in LOCATIONS.items():
    for _mob_id in _location_data.get('mobs', []):
        MOB_LOCATION_INDEX[_mob_id] = _location_id

def get_location(location_id: str) -> dict:
    return LOCATIONS.get(location_id)

def get_connected_locations(location_id: str) -> list:
    """Локации куда можно перейти."""
    loc = get_location(location_id)
    if not loc:
        return []
    return [LOCATIONS[lid] for lid in loc['connections'] if lid in LOCATIONS]


def get_mob_location_id(mob_id: str) -> str | None:
    return MOB_LOCATION_INDEX.get(mob_id)

print('✅ game/locations.py создан!')
print(f'   Локаций в базе: {len(LOCATIONS)}')
