# ============================================================
# locations.py — canonical static world data (phase 1)
# ============================================================

from __future__ import annotations


WORLD_ROUTES = {
    'core': {
        'route_id': 'core',
        'route_type': 'core',
        'display_name': 'Core',
        'hub_location_id': 'capital_city',
        'entry_location_id': 'capital_city',
        'is_stub': False,
        'adjacent_route_ids': [],
        'sort_order': 0,
    },
    'route_westwild': {
        'route_id': 'route_westwild',
        'route_type': 'full',
        'display_name': 'Westwild',
        'hub_location_id': 'hub_westwild',
        'entry_location_id': 'westwild_n1',
        'is_stub': False,
        'adjacent_route_ids': ['route_mireveil', 'route_sunscar'],
        'sort_order': 10,
    },
    'route_frostspine': {
        'route_id': 'route_frostspine',
        'route_type': 'full',
        'display_name': 'Frostspine',
        'hub_location_id': 'hub_frostspine',
        'entry_location_id': 'frostspine_n1',
        'is_stub': False,
        'adjacent_route_ids': ['route_mireveil', 'route_ashen_ruins'],
        'sort_order': 20,
    },
    'route_ashen_ruins': {
        'route_id': 'route_ashen_ruins',
        'route_type': 'full',
        'display_name': 'Ashen Ruins',
        'hub_location_id': 'hub_ashen_ruins',
        'entry_location_id': 'ashen_n1',
        'is_stub': False,
        'adjacent_route_ids': ['route_frostspine', 'route_sunscar'],
        'sort_order': 30,
    },
    'route_sunscar': {
        'route_id': 'route_sunscar',
        'route_type': 'full',
        'display_name': 'Sunscar',
        'hub_location_id': 'hub_sunscar',
        'entry_location_id': 'sunscar_n1',
        'is_stub': False,
        'adjacent_route_ids': ['route_ashen_ruins', 'route_westwild'],
        'sort_order': 40,
    },
    'route_mireveil': {
        'route_id': 'route_mireveil',
        'route_type': 'full',
        'display_name': 'Mireveil',
        'hub_location_id': 'hub_mireveil',
        'entry_location_id': 'mireveil_n1',
        'is_stub': False,
        'adjacent_route_ids': ['route_westwild', 'route_frostspine'],
        'sort_order': 50,
    },
    'route_south_coast_stub': {
        'route_id': 'route_south_coast_stub',
        'route_type': 'stub',
        'display_name': 'South Coast',
        'hub_location_id': None,
        'entry_location_id': 'south_coast_shore',
        'is_stub': True,
        'adjacent_route_ids': [],
        'sort_order': 60,
    },
    'route_old_mine_stub': {
        'route_id': 'route_old_mine_stub',
        'route_type': 'stub',
        'display_name': 'Old Mine',
        'hub_location_id': None,
        'entry_location_id': 'old_mine_entrance',
        'is_stub': True,
        'adjacent_route_ids': [],
        'sort_order': 70,
    },
}

WORLD_LEGACY_LOCATION_ALIASES = {
    'village': 'hub_westwild',
    'dark_forest': 'westwild_n4',
    'frontier_outpost': 'hub_frostspine',
    'old_mines': 'old_mine_entrance',
}


LEGACY_REGION_SAFE_HUB_OVERRIDES = {
    'village': 'village',
    'dark_forest': 'village',
    'frontier_outpost': 'frontier_outpost',
    'old_mines': 'village',
}

LEGACY_LOCATION_RUNTIME_OVERRIDES = {
    'village': {
        'id': 'village',
        'location_id': 'village',
        'connections': ['dark_forest', 'old_mines', 'frontier_outpost'],
        'neighbors': ['dark_forest', 'old_mines', 'frontier_outpost'],
        'return_hub_id': 'hub_westwild',
    },
    'frontier_outpost': {
        'id': 'frontier_outpost',
        'location_id': 'frontier_outpost',
        'connections': ['village', 'old_mines'],
        'neighbors': ['village', 'old_mines'],
        'return_hub_id': 'hub_frostspine',
    },
    'dark_forest': {
        'id': 'dark_forest',
        'location_id': 'dark_forest',
        'security_tier': 'guarded',
        'connections': ['village'],
        'neighbors': ['village'],
    },
    'old_mines': {
        'id': 'old_mines',
        'location_id': 'old_mines',
        'connections': ['village', 'frontier_outpost'],
        'neighbors': ['village', 'frontier_outpost'],
        'return_hub_id': 'hub_westwild',
    },
}


def _world_node(
    *,
    location_id: str,
    route_id: str,
    display_name: str,
    security_tier: str,
    neighbors: list[str],
    return_hub_id: str,
    teleport_enabled: bool = False,
    teleport_group: str | None = None,
    legacy_aliases: list[str] | None = None,
    region_flavor_tags: list[str] | None = None,
) -> dict:
    return {
        'id': location_id,
        'location_id': location_id,
        'route_id': route_id,
        'world_id': 'radial_world_v1',
        'region_id': route_id,
        'zone_id': location_id,
        'zone_role': 'normal',
        'linked_dungeon_id': None,
        'world_boss_governance_id': None,
        'future_pvp_ruleset_id': 'open_world_frontier',
        'display_name': display_name,
        'security_tier': security_tier,
        'neighbors': list(neighbors),
        # backward-compatible keys used by existing handlers
        'connections': list(neighbors),
        'name': display_name,
        'description': display_name,
        'level_min': 1,
        'level_max': 999,
        'safe': security_tier == 'safe',
        'mobs': [],
        'services': [],
        'gather': [],
        'teleport_enabled': teleport_enabled,
        'teleport_group': teleport_group,
        'return_hub_id': return_hub_id,
        'legacy_aliases': list(legacy_aliases or []),
        'region_flavor_tags': list(region_flavor_tags or []),
        'is_regional_safe_hub': location_id.startswith('hub_'),
    }


_WORLD_GRAPH = {
    'capital_city': ['westwild_n1', 'frostspine_n1', 'ashen_n1', 'sunscar_n1', 'mireveil_n1', 'south_coast_shore'],
    'south_coast_shore': ['capital_city'],
    'old_mine_entrance': ['frostspine_n1'],
    'westwild_n1': ['capital_city', 'westwild_n2'],
    'westwild_n2': ['westwild_n1', 'westwild_n3'],
    'westwild_n3': ['westwild_n2', 'westwild_n4'],
    'westwild_n4': ['westwild_n3', 'westwild_n5'],
    'westwild_n5': ['westwild_n4', 'westwild_n6', 'hub_westwild'],
    'hub_westwild': ['westwild_n5'],
    'westwild_n6': ['westwild_n5', 'westwild_n7', 'mireveil_n6', 'sunscar_n6'],
    'westwild_n7': ['westwild_n6', 'westwild_n8'],
    'westwild_n8': ['westwild_n7', 'westwild_n9', 'mireveil_n8', 'sunscar_n8'],
    'westwild_n9': ['westwild_n8', 'westwild_n10', 'mireveil_n9', 'sunscar_n9'],
    'westwild_n10': ['westwild_n9', 'westwild_n11', 'frostspine_n10'],
    'westwild_n11': ['westwild_n10'],
    'frostspine_n1': ['capital_city', 'frostspine_n2', 'old_mine_entrance'],
    'frostspine_n2': ['frostspine_n1', 'frostspine_n3'],
    'frostspine_n3': ['frostspine_n2', 'frostspine_n4'],
    'frostspine_n4': ['frostspine_n3', 'frostspine_n5'],
    'frostspine_n5': ['frostspine_n4', 'frostspine_n6', 'hub_frostspine'],
    'hub_frostspine': ['frostspine_n5'],
    'frostspine_n6': ['frostspine_n5', 'frostspine_n7', 'mireveil_n6', 'ashen_n3b1'],
    'frostspine_n7': ['frostspine_n6', 'frostspine_n8'],
    'frostspine_n8': ['frostspine_n7', 'frostspine_n9', 'mireveil_n8', 'ashen_n3b2'],
    'frostspine_n9': ['frostspine_n8', 'frostspine_n10', 'mireveil_n9', 'ashen_n3b2a1'],
    'frostspine_n10': ['frostspine_n9', 'westwild_n10'],
    'ashen_n1': ['capital_city', 'ashen_n2'],
    'ashen_n2': ['ashen_n1', 'ashen_n3'],
    'ashen_n3': ['ashen_n2', 'ashen_n3a1', 'ashen_n3b1', 'ashen_n3c1'],
    'ashen_n3a1': ['ashen_n3', 'ashen_n3a2'],
    'ashen_n3a2': ['ashen_n3a1', 'hub_ashen_ruins'],
    'hub_ashen_ruins': ['ashen_n3a2'],
    'ashen_n3b1': ['ashen_n3', 'ashen_n3b2', 'frostspine_n6', 'sunscar_n6'],
    'ashen_n3b2': ['ashen_n3b1', 'ashen_n3b2a1', 'ashen_n3b2b1', 'frostspine_n8', 'sunscar_n8'],
    'ashen_n3b2a1': ['ashen_n3b2', 'frostspine_n9', 'sunscar_n9'],
    'ashen_n3b2b1': ['ashen_n3b2', 'mireveil_n10'],
    'ashen_n3c1': ['ashen_n3', 'ashen_n3c2'],
    'ashen_n3c2': ['ashen_n3c1'],
    'sunscar_n1': ['capital_city', 'sunscar_n2'],
    'sunscar_n2': ['sunscar_n1', 'sunscar_n3'],
    'sunscar_n3': ['sunscar_n2', 'sunscar_n4'],
    'sunscar_n4': ['sunscar_n3', 'sunscar_n5'],
    'sunscar_n5': ['sunscar_n4', 'sunscar_n6', 'sunscar_n5a1'],
    'sunscar_n5a1': ['sunscar_n5', 'hub_sunscar'],
    'hub_sunscar': ['sunscar_n5a1'],
    'sunscar_n6': ['sunscar_n5', 'sunscar_n7', 'ashen_n3b1', 'westwild_n6'],
    'sunscar_n7': ['sunscar_n6', 'sunscar_n8'],
    'sunscar_n8': ['sunscar_n7', 'sunscar_n9', 'sunscar_n8a1', 'ashen_n3b2', 'westwild_n8'],
    'sunscar_n8a1': ['sunscar_n8', 'sunscar_n8a2'],
    'sunscar_n8a2': ['sunscar_n8a1'],
    'sunscar_n9': ['sunscar_n8', 'sunscar_n10', 'ashen_n3b2a1', 'westwild_n9'],
    'sunscar_n10': ['sunscar_n9', 'sunscar_n11'],
    'sunscar_n11': ['sunscar_n10'],
    'mireveil_n1': ['capital_city', 'mireveil_n2'],
    'mireveil_n2': ['mireveil_n1', 'mireveil_n3'],
    'mireveil_n3': ['mireveil_n2', 'mireveil_n4'],
    'mireveil_n4': ['mireveil_n3', 'mireveil_n5'],
    'mireveil_n5': ['mireveil_n4', 'mireveil_n6', 'mireveil_n5a1'],
    'mireveil_n5a1': ['mireveil_n5', 'hub_mireveil'],
    'hub_mireveil': ['mireveil_n5a1'],
    'mireveil_n6': ['mireveil_n5', 'mireveil_n7', 'westwild_n6', 'frostspine_n6'],
    'mireveil_n7': ['mireveil_n6', 'mireveil_n8'],
    'mireveil_n8': ['mireveil_n7', 'mireveil_n9', 'mireveil_n8a1', 'westwild_n8', 'frostspine_n8'],
    'mireveil_n8a1': ['mireveil_n8', 'mireveil_n8a2'],
    'mireveil_n8a2': ['mireveil_n8a1'],
    'mireveil_n9': ['mireveil_n8', 'mireveil_n10', 'westwild_n9', 'frostspine_n9'],
    'mireveil_n10': ['mireveil_n9', 'ashen_n3b2b1'],
}

_LOCATION_NAMES = {
    'capital_city': '🏛️ Астер',
    'south_coast_shore': '🏖️ Южный берег',
    'old_mine_entrance': '⛏️ Старая шахта',
    'westwild_n1': '🌿 Зелёный тракт',
    'westwild_n2': '🌲 Лесная опушка',
    'westwild_n3': '🌲 Перелесье',
    'westwild_n4': '🌲 Тёмный лес',
    'westwild_n5': '🦌 Олений дол',
    'hub_westwild': '🏘️ Элмор',
    'westwild_n6': '🌲 Высокий бор',
    'westwild_n7': '🌲 Бурелом',
    'westwild_n8': '🪨 Каменный ручей',
    'westwild_n9': '🌲 Глухая чаща',
    'westwild_n10': '🪵 Мшистый яр',
    'westwild_n11': '🌲 Шепчущий бор',
    'frostspine_n1': '🪨 Каменный путь',
    'frostspine_n2': '🏔️ Предгорье',
    'frostspine_n3': '🏔️ Узкий перевал',
    'frostspine_n4': '❄️ Холодный склон',
    'frostspine_n5': '⛰️ Серый кряж',
    'hub_frostspine': '🏕️ Карн',
    'frostspine_n6': '⛏️ Рудный ход',
    'frostspine_n7': '❄️ Ледяной перевал',
    'frostspine_n8': '❄️ Белый уступ',
    'frostspine_n9': '❄️ Снежный склон',
    'frostspine_n10': '❄️ Снежное плато',
    'ashen_n1': '🛤️ Старая дорога',
    'ashen_n2': '🌉 Разбитый мост',
    'ashen_n3': '🪨 Каменный круг',
    'ashen_n3a1': '🏚️ Пустой двор',
    'ashen_n3a2': '⛪ Старый храм',
    'hub_ashen_ruins': '🏛️ Эмбер',
    'ashen_n3b1': '🏚️ Тихие руины',
    'ashen_n3b2': '🏛️ Реликтовый зал',
    'ashen_n3b2a1': '🔏 Зал печатей',
    'ashen_n3b2b1': '🌑 Теневой ход',
    'ashen_n3c1': '🌿 Забытый сад',
    'ashen_n3c2': '⚰️ Старый склеп',
    'sunscar_n1': '☀️ Южный тракт',
    'sunscar_n2': '🪨 Красный склон',
    'sunscar_n3': '🪨 Каменная балка',
    'sunscar_n4': '🏜️ Узкий каньон',
    'sunscar_n5': '🪨 Старый перевал',
    'sunscar_n5a1': '💧 Оазис',
    'hub_sunscar': '🏜️ Мираж',
    'sunscar_n6': '🏜️ Пески',
    'sunscar_n7': '🧂 Соляное поле',
    'sunscar_n8': '🏜️ Каменный каньон',
    'sunscar_n8a1': '🏕️ Старый лагерь',
    'sunscar_n8a2': '🪨 Каменные столбы',
    'sunscar_n9': '🏜️ Сухое русло',
    'sunscar_n10': '⛰️ Высокая гряда',
    'sunscar_n11': '⛰️ Высокое плато',
    'mireveil_n1': '💧 Мокрый тракт',
    'mireveil_n2': '💧 Низина',
    'mireveil_n3': '🌾 Камыши',
    'mireveil_n4': '💧 Сырой берег',
    'mireveil_n5': '🌉 Старый брод',
    'mireveil_n5a1': '🎣 Рыбачий мосток',
    'hub_mireveil': '🛶 Вельм',
    'mireveil_n6': '☣️ Гнилая вода',
    'mireveil_n7': '🌿 Заросли',
    'mireveil_n8': '🌿 Ивовый берег',
    'mireveil_n8a1': '🍄 Грибной берег',
    'mireveil_n8a2': '☣️ Ядовитый пруд',
    'mireveil_n9': '☣️ Трясина',
    'mireveil_n10': '☣️ Чёрная вода',
}

_MISSING_CANONICAL_LOCATION_NAMES = [
    location_id
    for location_id in _WORLD_GRAPH
    if location_id not in _LOCATION_NAMES
]
if _MISSING_CANONICAL_LOCATION_NAMES:
    missing_ids = ', '.join(sorted(_MISSING_CANONICAL_LOCATION_NAMES))
    raise ValueError(f'Missing canonical display names for: {missing_ids}')

_GUARDED_IDS = {'westwild_n5', 'frostspine_n5', 'ashen_n3a2', 'sunscar_n5a1', 'mireveil_n5a1'}
_SAFE_IDS = {'capital_city', 'hub_westwild', 'hub_frostspine', 'hub_ashen_ruins', 'hub_sunscar', 'hub_mireveil'}
_TELEPORT_HUBS = _SAFE_IDS

_RETURN_HUB_OVERRIDES = {
    'capital_city': 'capital_city',
    'south_coast_shore': 'capital_city',
    'westwild_n1': 'capital_city',
    'frostspine_n1': 'capital_city',
    'ashen_n1': 'capital_city',
    'sunscar_n1': 'capital_city',
    'mireveil_n1': 'capital_city',
    'old_mine_entrance': 'hub_frostspine',
}

_ROUTE_HUBS = {
    'route_westwild': 'hub_westwild',
    'route_frostspine': 'hub_frostspine',
    'route_ashen_ruins': 'hub_ashen_ruins',
    'route_sunscar': 'hub_sunscar',
    'route_mireveil': 'hub_mireveil',
}


WORLD_LOCATIONS = {}
for _location_id, _neighbors in _WORLD_GRAPH.items():
    if _location_id == 'capital_city':
        _route_id = 'core'
    elif _location_id == 'south_coast_shore':
        _route_id = 'route_south_coast_stub'
    elif _location_id == 'old_mine_entrance':
        _route_id = 'route_old_mine_stub'
    elif _location_id.startswith('westwild_') or _location_id == 'hub_westwild':
        _route_id = 'route_westwild'
    elif _location_id.startswith('frostspine_') or _location_id == 'hub_frostspine':
        _route_id = 'route_frostspine'
    elif _location_id.startswith('ashen_') or _location_id == 'hub_ashen_ruins':
        _route_id = 'route_ashen_ruins'
    elif _location_id.startswith('sunscar_') or _location_id == 'hub_sunscar':
        _route_id = 'route_sunscar'
    else:
        _route_id = 'route_mireveil'

    _security_tier = 'frontier'
    if _location_id in _SAFE_IDS:
        _security_tier = 'safe'
    elif _location_id in _GUARDED_IDS:
        _security_tier = 'guarded'

    _return_hub = _RETURN_HUB_OVERRIDES.get(_location_id)
    if not _return_hub:
        _return_hub = _ROUTE_HUBS.get(_route_id, 'capital_city')

    _legacy_aliases = [
        alias_id
        for alias_id, canonical_id in WORLD_LEGACY_LOCATION_ALIASES.items()
        if canonical_id == _location_id
    ]

    WORLD_LOCATIONS[_location_id] = _world_node(
        location_id=_location_id,
        route_id=_route_id,
        display_name=_LOCATION_NAMES.get(_location_id, _location_id.replace('_', ' ').title()),
        security_tier=_security_tier,
        neighbors=_neighbors,
        return_hub_id=_return_hub,
        teleport_enabled=_location_id in _TELEPORT_HUBS,
        teleport_group='main_network' if _location_id in _TELEPORT_HUBS else None,
        legacy_aliases=_legacy_aliases,
    )

# Keep existing battle/reward content on mapped nodes.
WORLD_LOCATIONS['hub_westwild'].update({
    'world_boss_governance_id': 'ember_valley_world_boss',
    'world_id': 'ashen_continent',
    'region_id': 'ember_valley',
    'zone_id': 'ember_village',
    'description': 'Мирные поля и деревня на краю тёмного леса. Здесь можно отдохнуть, закупиться и взять квесты.',
    'services': ['shop', 'inn', 'quest_board'],
    'region_flavor_tags': ['civilized_frontier', 'ashen_farmland'],
})
WORLD_LOCATIONS['hub_frostspine'].update({
    'world_boss_governance_id': 'iron_pass_world_boss',
    'world_id': 'ashen_continent',
    'region_id': 'iron_pass',
    'zone_id': 'frontier_outpost',
    'description': 'Укреплённая застава у шахтного тракта. Здесь перевязывают раны и берут местные контракты.',
    'services': ['shop', 'inn', 'quest_board'],
    'region_flavor_tags': ['mine_waystation', 'hunter_lodge'],
})
WORLD_LOCATIONS['westwild_n4'].update({
    'linked_dungeon_id': 'rootbound_hollow',
    'world_boss_governance_id': 'ember_valley_world_boss',
    'world_id': 'ashen_continent',
    'region_id': 'ember_valley',
    'zone_id': 'dark_forest',
    'region_flavor_tags': ['beast_hunting', 'poison_herbs', 'dark_wood'],
    'description': 'Густой лес, пронизанный тьмой. Здесь рыщут волки, а на деревьях затаились пауки.',
    'level_max': 5,
    'mobs': ['forest_wolf', 'forest_boar', 'forest_spider', 'dark_treant'],
    'gather': [
        ('herb_common', 0.40, '🌿 Обычная трава'),
        ('herb_magic', 0.10, '✨ Магическая трава'),
        ('wood_dark', 0.50, '🪵 Тёмное дерево'),
    ],
})
WORLD_LOCATIONS['old_mine_entrance'].update({
    'world_id': 'ashen_continent',
    'region_id': 'ember_valley',
    'zone_id': 'old_mines',
    'region_flavor_tags': ['ore_veins', 'construct_ruins', 'goblin_camps'],
    'zone_role': 'elite',
    'world_boss_governance_id': 'ember_valley_world_boss',
    'linked_dungeon_id': 'amber_catacombs',
    'description': 'Заброшенные шахты, населённые гоблинами и жуткими тварями. Богаты рудой, но таят в себе опасности.',
    'level_min': 3,
    'level_max': 8,
    'mobs': ['mine_rat', 'goblin_miner', 'cave_bat', 'stone_golem'],
    'world_special_spawns': [
        {
            'key': 'amber_colossus',
            'mob_id': 'stone_golem',
            'spawn_profile': 'elite',
            'count': 1,
        },
    ],
    'world_spawn_profiles': {
        'mine_rat': {'normal': 2},
        'goblin_miner': {'normal': 1, 'elite': 1},
        'cave_bat': {'normal': 2, 'rare': 1},
        'stone_golem': {'normal': 1, 'elite': 1},
    },
    'gather': [
        ('iron_ore', 0.55, '⛏️ Железная руда'),
        ('coal', 0.35, '🪨 Уголь'),
        ('gem_common', 0.08, '💎 Обычный драгоценный камень'),
    ],
})

# Backward-compatible name used across the codebase.
LOCATIONS = WORLD_LOCATIONS

MOB_LOCATION_INDEX: dict[str, str] = {}
for _location_id, _location_data in LOCATIONS.items():
    for _mob_id in _location_data.get('mobs', []):
        MOB_LOCATION_INDEX[_mob_id] = _location_id


SECURITY_TIERS: tuple[str, ...] = ('safe', 'guarded', 'frontier', 'core_war')
DEFAULT_SECURITY_TIER = 'safe'
FALLBACK_SAFE_HUB_ID = 'hub_westwild'


def resolve_location_id(raw_location_id: str | None) -> str:
    location_id = str(raw_location_id or '').strip()
    if not location_id:
        return FALLBACK_SAFE_HUB_ID
    return WORLD_LEGACY_LOCATION_ALIASES.get(location_id, location_id)


def get_route(route_id: str) -> dict | None:
    return WORLD_ROUTES.get(route_id)


def get_location(location_id: str) -> dict | None:
    raw_location_id = str(location_id or '').strip()
    canonical_location_id = resolve_location_id(raw_location_id)
    location = LOCATIONS.get(canonical_location_id)
    if not location:
        return None
    if raw_location_id in LEGACY_LOCATION_RUNTIME_OVERRIDES:
        resolved = dict(location)
        resolved.update(LEGACY_LOCATION_RUNTIME_OVERRIDES[raw_location_id])
        resolved['canonical_id'] = canonical_location_id
        return resolved
    return location


def get_location_neighbors(location_id: str) -> list[str]:
    canonical_location_id = resolve_location_id(location_id)
    location = LOCATIONS.get(canonical_location_id)
    if not location:
        return []
    return list(location.get('neighbors', []))


def get_connected_locations(location_id: str) -> list[dict]:
    """Локации куда можно перейти."""
    connected_locations: list[dict] = []
    for neighbor_id in get_location_neighbors(location_id):
        neighbor_location = get_location(neighbor_id)
        if neighbor_location:
            connected_locations.append(neighbor_location)
    return connected_locations


def get_return_hub(location_id: str | None) -> str:
    location = get_location(location_id or '')
    if not location:
        return FALLBACK_SAFE_HUB_ID
    return str(location.get('return_hub_id') or FALLBACK_SAFE_HUB_ID)


def get_mob_location_id(mob_id: str) -> str | None:
    return MOB_LOCATION_INDEX.get(mob_id)


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
    raw_location_id = str(location_id or '').strip()
    if raw_location_id in LEGACY_REGION_SAFE_HUB_OVERRIDES:
        return LEGACY_REGION_SAFE_HUB_OVERRIDES[raw_location_id]
    if raw_location_id:
        return get_return_hub(raw_location_id)

    normalized_region_id = str(region_id or '').strip()
    normalized_world_id = str(world_id or '').strip()
    for hub_id, hub_data in LOCATIONS.items():
        if not hub_data.get('is_regional_safe_hub'):
            continue
        if normalized_region_id and str(hub_data.get('region_id') or '') != normalized_region_id:
            continue
        if normalized_world_id and str(hub_data.get('world_id') or '') != normalized_world_id:
            continue
        return hub_id

    return FALLBACK_SAFE_HUB_ID
