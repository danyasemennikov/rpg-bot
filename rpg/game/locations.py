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
        'security_tier': 'safe',
        'is_regional_safe_hub': True,
        'name':        '🏘️ Пепельная Деревня',
        'description': 'Мирные поля, тихая деревушка на краю тёмного леса. Здесь можно отдохнуть, закупиться и взять квесты.',
        'level_min':   1,
        'level_max':   999,  # безопасная зона
        'safe':        True,  # мобы не атакуют, нельзя умереть
        'mobs':        [],    # мобов нет
        'connections': ['dark_forest', 'old_mines', 'frontier_outpost'],  # куда можно пойти
        'services':    ['shop', 'inn', 'quest_board'],
        'gather':      [],    # ресурсы для сбора
    },

    'frontier_outpost': {
        'id':          'frontier_outpost',
        'world_id':    'ashen_continent',
        'region_id':   'iron_pass',
        'zone_id':     'frontier_outpost',
        'zone_role':   'normal',
        'region_flavor_tags': ['mine_waystation', 'hunter_lodge'],
        'linked_dungeon_id': None,
        'world_boss_governance_id': 'iron_pass_world_boss',
        'future_pvp_ruleset_id': 'open_world_frontier',
        'security_tier': 'safe',
        'is_regional_safe_hub': True,
        'name':        '🏕️ Пограничная застава',
        'description': 'Укреплённая застава у шахтного тракта. Здесь перевязывают раны, берут местные контракты и готовятся к вылазкам.',
        'level_min':   1,
        'level_max':   999,
        'safe':        True,
        'mobs':        [],
        'connections': ['village', 'old_mines'],
        'services':    ['shop', 'inn', 'quest_board'],
        'gather':      [],
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
        'security_tier': 'guarded',
        'is_regional_safe_hub': False,
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
        'security_tier': 'frontier',
        'is_regional_safe_hub': False,
        'name':        '⛏️ Старые шахты',
        'description': 'Заброшенные шахты, населённые гоблинами и жуткими тварями. Богаты рудой, но таят в себе опасности.',
        'level_min':   3,
        'level_max':   8,
        'safe':        False,
        'mobs':        ['mine_rat', 'goblin_miner', 'cave_bat', 'stone_golem'],
        'world_spawn_profiles': {
            'mine_rat': {'normal': 2},
            'goblin_miner': {'normal': 1, 'elite': 1},
            'cave_bat': {'normal': 2, 'rare': 1},
            'stone_golem': {'normal': 1, 'elite': 1},
        },
        'world_special_spawns': [
            {
                'key': 'amber_colossus',
                'mob_id': 'stone_golem',
                'spawn_profile': 'elite',
                'count': 1,
            },
        ],
        'connections': ['village', 'frontier_outpost'],
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


SECURITY_TIERS: tuple[str, ...] = ('safe', 'guarded', 'frontier', 'core_war')
DEFAULT_SECURITY_TIER = 'safe'
FALLBACK_SAFE_HUB_ID = 'village'


def normalize_security_tier(value: str | None) -> str:
    if value in SECURITY_TIERS:
        return str(value)
    return DEFAULT_SECURITY_TIER


def get_location_security_tier(location_id: str | None) -> str:
    location = get_location(location_id or '') or {}
    explicit_tier = normalize_security_tier(location.get('security_tier'))
    if explicit_tier != DEFAULT_SECURITY_TIER:
        return explicit_tier
    if location.get('safe'):
        return 'safe'
    return explicit_tier


def resolve_region_safe_hub(
    *,
    location_id: str | None = None,
    region_id: str | None = None,
    world_id: str | None = None,
) -> str:
    resolved_location = get_location(location_id or '') or {}
    resolved_region_id = region_id or resolved_location.get('region_id')
    resolved_world_id = world_id or resolved_location.get('world_id')

    for hub_id, hub_data in LOCATIONS.items():
        if not hub_data.get('is_regional_safe_hub'):
            continue
        if resolved_region_id and hub_data.get('region_id') != resolved_region_id:
            continue
        if resolved_world_id and hub_data.get('world_id') != resolved_world_id:
            continue
        return hub_id

    return FALLBACK_SAFE_HUB_ID

print('✅ game/locations.py создан!')
print(f'   Локаций в базе: {len(LOCATIONS)}')
