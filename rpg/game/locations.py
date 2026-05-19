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
    'dark_forest': 'westwild_n7',
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

# Full canonical rollout: ordinary live travel now uses the complete
# WORLD_GRAPH topology. Teleport remains disabled below; these edges are
# plain neighboring-location travel only.
_LIVE_WORLD_GRAPH = {
    location_id: list(neighbors)
    for location_id, neighbors in _WORLD_GRAPH.items()
}

_LOCATION_NAMES = {
    'capital_city': '🏛️ Астер',
    'south_coast_shore': '🏖️ Южный берег',
    'old_mine_entrance': '⛏️ Старая шахта',
    'westwild_n1': '🌾 Пшеничные поля',
    'westwild_n2': '🌿 Луга',
    'westwild_n3': '⛰️ Холмы',
    'westwild_n4': '🌳 Лиственная роща',
    'westwild_n5': '🌲 Перелесок',
    'hub_westwild': '🏘️ Элмор',
    'westwild_n6': '🌲 Бор',
    'westwild_n7': '🌲 Тёмный лес',
    'westwild_n8': '🪨 Каменный ручей',
    'westwild_n9': '🌲 Глухая чаща',
    'westwild_n10': '🪵 Мшистый яр',
    'westwild_n11': '🌲 Шепчущий бор',
    'frostspine_n1': '🪨 Каменная дорога',
    'frostspine_n2': '🏔️ Предгорья',
    'frostspine_n3': '🏔️ Перевал',
    'frostspine_n4': '❄️ Склон',
    'frostspine_n5': '⛰️ Каменная гряда',
    'hub_frostspine': '🏕️ Карн',
    'frostspine_n6': '⛏️ Рудники',
    'frostspine_n7': '❄️ Ледяной перевал',
    'frostspine_n8': '❄️ Белый уступ',
    'frostspine_n9': '❄️ Снежный склон',
    'frostspine_n10': '❄️ Плато',
    'ashen_n1': '🛤️ Старая дорога',
    'ashen_n2': '🌉 Разбитый мост',
    'ashen_n3': '🪨 Каменный круг',
    'ashen_n3a1': '🏚️ Каменный двор',
    'ashen_n3a2': '⛪ Старый храм',
    'hub_ashen_ruins': '🏛️ Эмбер',
    'ashen_n3b1': '🏚️ Глухие руины',
    'ashen_n3b2': '🏛️ Реликтовый зал',
    'ashen_n3b2a1': '🔏 Зал печатей',
    'ashen_n3b2b1': '🌑 Скрытый ход',
    'ashen_n3c1': '🌿 Забытый сад',
    'ashen_n3c2': '⚰️ Старый склеп',
    'sunscar_n1': '🏜️ Пустошь',
    'sunscar_n2': '🏜️ Песчаные склоны',
    'sunscar_n3': '🏜️ Сухой овраг',
    'sunscar_n4': '🏜️ Каньон',
    'sunscar_n5': '🪨 Проход',
    'sunscar_n5a1': '💧 Оазис',
    'hub_sunscar': '🏜️ Мираж',
    'sunscar_n6': '🏜️ Дюны',
    'sunscar_n7': '🧂 Солончак',
    'sunscar_n8': '🏜️ Ущелье',
    'sunscar_n8a1': '🏕️ Брошенный лагерь',
    'sunscar_n8a2': '🪨 Каменные столбы',
    'sunscar_n9': '🏜️ Сухое русло',
    'sunscar_n10': '⛰️ Соляная гряда',
    'sunscar_n11': '⛰️ Плато',
    'mireveil_n1': '💧 Топкая дорога',
    'mireveil_n2': '💧 Низина',
    'mireveil_n3': '🌾 Камыши',
    'mireveil_n4': '💧 Заводь',
    'mireveil_n5': '🌉 Брод',
    'mireveil_n5a1': '🎣 Мостки',
    'hub_mireveil': '🛶 Вельм',
    'mireveil_n6': '☣️ Мутная вода',
    'mireveil_n7': '🌿 Заросли',
    'mireveil_n8': '🌿 Протока',
    'mireveil_n8a1': '🍄 Грибная топь',
    'mireveil_n8a2': '☣️ Омут',
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
# Teleport metadata exists in the data model, but this rollout intentionally
# keeps teleport disabled and exposes only ordinary graph travel.
_TELEPORT_HUBS: set[str] = set()

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


_ROUTE_CONTENT_IDENTITIES = {
    'core': {
        'world_id': 'ashen_continent',
        'region_id': 'capital_region',
        'region_flavor_tags': ['capital_services', 'starter_hub'],
    },
    'route_westwild': {
        'world_id': 'ashen_continent',
        'region_id': 'ember_valley',
        'region_flavor_tags': ['forest_wilds', 'beast_hunting', 'herb_growth', 'dark_wood'],
    },
    'route_frostspine': {
        'world_id': 'ashen_continent',
        'region_id': 'iron_pass',
        'region_flavor_tags': ['mountain_travel', 'stone_outcrops', 'ore_veins', 'cold_pass'],
    },
    'route_ashen_ruins': {
        'world_id': 'ashen_continent',
        'region_id': 'ashen_ruins',
        'region_flavor_tags': ['ancient_ruins', 'construct_remnants', 'arcane_debris', 'excavation_site'],
    },
    'route_sunscar': {
        'world_id': 'ashen_continent',
        'region_id': 'sunscar_badlands',
        'region_flavor_tags': ['desert_badlands', 'dry_scavenging', 'heat_scarred', 'venomous_wildlife'],
    },
    'route_mireveil': {
        'world_id': 'ashen_continent',
        'region_id': 'mireveil_marsh',
        'region_flavor_tags': ['swamp_mire', 'poison_wetlands', 'fungal_growth', 'wetland_scavenging'],
    },
    'route_south_coast_stub': {
        'world_id': 'ashen_continent',
        'region_id': 'south_coast',
        'region_flavor_tags': ['coastal_shoreline', 'fishing_lite', 'sea_wind'],
    },
}

_ROUTE_HUBS = {
    'route_westwild': 'hub_westwild',
    'route_frostspine': 'hub_frostspine',
    'route_ashen_ruins': 'hub_ashen_ruins',
    'route_sunscar': 'hub_sunscar',
    'route_mireveil': 'hub_mireveil',
}


WORLD_LOCATIONS = {}
for _location_id, _neighbors in _LIVE_WORLD_GRAPH.items():
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

    _content_identity = _ROUTE_CONTENT_IDENTITIES.get(_route_id, {})
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
        region_flavor_tags=_content_identity.get('region_flavor_tags'),
    )
    WORLD_LOCATIONS[_location_id].update({
        'world_id': _content_identity.get('world_id', 'radial_world_v1'),
        'region_id': _content_identity.get('region_id', _route_id),
    })
    WORLD_LOCATIONS[_location_id]['canonical_neighbors'] = list(_WORLD_GRAPH.get(_location_id, []))

# Keep existing battle/reward content on mapped nodes.
WORLD_LOCATIONS['south_coast_shore'].update({
    'description': 'Небольшая прибрежная полоса у столицы: лёгкая рыбалка, сбор береговых трав и пока без полноценной морской ветки.',
})
WORLD_LOCATIONS['capital_city'].update({
    'description': 'Столица королевства и главный безопасный узел дорог. Здесь можно отдохнуть, закупиться и взять первые задания.',
    'services': ['shop', 'inn', 'quest_board', 'craftsmen_guild'],
    'region_flavor_tags': ['capital_services', 'starter_hub'],
})
WORLD_LOCATIONS['hub_westwild'].update({
    'world_boss_governance_id': 'ember_valley_world_boss',
    'world_id': 'ashen_continent',
    'region_id': 'ember_valley',
    'zone_id': 'ember_village',
    'description': 'Мирные поля и деревня на краю тёмного леса. Здесь можно отдохнуть, закупиться и взять квесты.',
    'services': ['shop', 'inn', 'quest_board', 'craftsmen_guild'],
    'region_flavor_tags': ['civilized_frontier', 'ashen_farmland'],
})
WORLD_LOCATIONS['hub_frostspine'].update({
    'world_boss_governance_id': 'iron_pass_world_boss',
    'world_id': 'ashen_continent',
    'region_id': 'iron_pass',
    'zone_id': 'frontier_outpost',
    'description': 'Укреплённая застава у шахтного тракта. Здесь перевязывают раны и берут местные контракты.',
    'services': ['shop', 'inn', 'quest_board', 'craftsmen_guild'],
    'region_flavor_tags': ['mine_waystation', 'hunter_lodge'],
})
WORLD_LOCATIONS['hub_ashen_ruins'].update({
    'services': ['craftsmen_guild'],
})
WORLD_LOCATIONS['hub_sunscar'].update({
    'services': ['craftsmen_guild'],
})
WORLD_LOCATIONS['hub_mireveil'].update({
    'services': ['craftsmen_guild'],
})
WORLD_LOCATIONS['westwild_n4'].update({
    'description': 'Светлая лиственная роща на переходе от лугов к лесу. Здесь уже встречаются волки и первые пауки.',
    'zone_id': 'westwild_n4',
    'linked_dungeon_id': None,
    'world_boss_governance_id': None,
})
WORLD_LOCATIONS['old_mine_entrance'].update({
    'world_id': 'ashen_continent',
    'region_id': 'ember_valley',
    'zone_id': 'old_mines',
    'region_flavor_tags': ['ore_veins', 'construct_ruins', 'goblin_camps'],
    'zone_role': 'normal',
    'world_boss_governance_id': None,
    'linked_dungeon_id': None,
    'description': 'Старый шахтный вход с редкими пещерными тварями и простыми рудными жилами.',
    'level_min': 1,
    'level_max': 4,
    'mobs': ['mine_rat', 'cave_bat'],
    'world_special_spawns': [],
    'world_spawn_profiles': {
        'mine_rat': {'normal': 1},
        'cave_bat': {'normal': 1},
    },
    'gather': [
        ('iron_ore', 0.65, '⛏️ Железная руда'),
        ('coal', 0.30, '🪨 Уголь'),
    ],
})


# Open World Gameplay Rollout Phase 1: baseline route-aware PvE and gathering.
# The data below stays on the existing location-bound spawn/gather rails:
# - `mobs` + `world_spawn_profiles` feed anchored open-world spawn instances;
# - elite anchors are represented by elite spawn profiles only;
# - `gather` entries are ordinary gathering foundation surfaces.
_PHASE1_ELITE_ANCHOR_IDS = {
    'westwild_n7', 'westwild_n8', 'westwild_n10', 'westwild_n11',
    'frostspine_n6', 'frostspine_n8', 'frostspine_n10',
    'ashen_n3b1', 'ashen_n3b2', 'ashen_n3b2a1', 'ashen_n3c2',
    'sunscar_n6', 'sunscar_n8', 'sunscar_n8a2', 'sunscar_n10', 'sunscar_n11',
    'mireveil_n6', 'mireveil_n8', 'mireveil_n8a2', 'mireveil_n10',
}

_PHASE1_LOCATION_MOBS = {
    'south_coast_shore': ['shore_crab', 'seagull', 'shore_turtle'],
    'old_mine_entrance': ['mine_rat', 'cave_bat'],
    'westwild_n1': ['westwild_rabbit', 'crow'],
    'westwild_n2': ['westwild_rabbit', 'crow', 'forest_boar'],
    'westwild_n3': ['forest_boar', 'forest_wolf'],
    'westwild_n4': ['forest_wolf', 'forest_spider'],
    'westwild_n5': ['forest_boar', 'forest_spider', 'goblin_scout'],
    'westwild_n6': ['forest_wolf', 'bear', 'goblin_scout'],
    'westwild_n7': ['forest_wolf', 'forest_boar', 'forest_spider', 'bear', 'goblin_hunter'],
    'westwild_n8': ['bear', 'goblin_hunter', 'goblin_shaman'],
    'westwild_n9': ['goblin_hunter', 'goblin_shaman'],
    'westwild_n10': ['goblin_hunter', 'goblin_shaman', 'goblin_chief'],
    'westwild_n11': ['goblin_shaman', 'goblin_chief'],
    'frostspine_n1': ['mountain_rabbit', 'rock_lizard'],
    'frostspine_n2': ['mountain_rabbit', 'rock_lizard', 'white_wolf'],
    'frostspine_n3': ['white_wolf', 'cave_bat'],
    'frostspine_n4': ['cave_bat', 'stone_beetle'],
    'frostspine_n5': ['white_wolf', 'stone_beetle'],
    'frostspine_n6': ['stone_beetle', 'mountain_stone_golem'],
    'frostspine_n7': ['troll'],
    'frostspine_n8': ['troll', 'ice_troll'],
    'frostspine_n9': ['ice_troll', 'troll_chief'],
    'frostspine_n10': ['ice_troll', 'troll_chief'],
    'ashen_n1': ['zombie', 'skeleton_warrior'],
    'ashen_n2': ['zombie', 'skeleton_warrior'],
    'ashen_n3': ['skeleton_warrior', 'skeleton_mage'],
    'ashen_n3a1': ['skeleton_mage', 'ghost'],
    'ashen_n3a2': ['ghost', 'skeleton_guard'],
    'ashen_n3b1': ['skeleton_guard', 'cursed_knight'],
    'ashen_n3b2': ['cursed_knight', 'skeleton_priest'],
    'ashen_n3b2a1': ['skeleton_priest', 'temple_guardian'],
    'ashen_n3b2b1': ['ghost', 'cursed_knight'],
    'ashen_n3c1': ['zombie', 'ghost'],
    'ashen_n3c2': ['cursed_knight', 'temple_guardian'],
    'sunscar_n1': ['desert_beetle', 'desert_lizard'],
    'sunscar_n2': ['desert_lizard', 'scavenger'],
    'sunscar_n3': ['scavenger', 'scorpion'],
    'sunscar_n4': ['scorpion', 'snake'],
    'sunscar_n5': ['snake', 'scorpion'],
    'sunscar_n5a1': ['crocodile', 'snake'],
    'sunscar_n6': ['desert_elephant', 'scorpion'],
    'sunscar_n7': ['desert_elephant', 'snake'],
    'sunscar_n8': ['desert_elephant', 'fire_elemental'],
    'sunscar_n8a1': ['scavenger', 'earth_elemental'],
    'sunscar_n8a2': ['earth_elemental', 'air_elemental'],
    'sunscar_n9': ['fire_elemental', 'earth_elemental'],
    'sunscar_n10': ['earth_elemental', 'air_elemental'],
    'sunscar_n11': ['fire_elemental', 'air_elemental'],
    'mireveil_n1': ['swamp_toad', 'leech'],
    'mireveil_n2': ['leech', 'water_snake'],
    'mireveil_n3': ['water_snake', 'swamp_spider'],
    'mireveil_n4': ['swamp_toad', 'swamp_spider'],
    'mireveil_n5': ['leech', 'water_snake'],
    'mireveil_n5a1': ['water_snake', 'swamp_toad'],
    'mireveil_n6': ['giant_leech', 'slug'],
    'mireveil_n7': ['slug', 'drowned'],
    'mireveil_n8': ['giant_leech', 'drowned'],
    'mireveil_n8a1': ['slug', 'toxic_slime'],
    'mireveil_n8a2': ['toxic_slime', 'swamp_witch'],
    'mireveil_n9': ['drowned', 'swamp_witch'],
    'mireveil_n10': ['toxic_slime', 'old_witch'],
}

_PHASE1_GATHER = {
    'south_coast_shore': [('shore_fish', 0.70, '🎣 Прибрежная рыба'), ('shore_herbs', 0.20, '🌿 Береговые травы')],
    'old_mine_entrance': [('iron_ore', 0.65, '⛏️ Железная руда'), ('coal', 0.30, '🪨 Уголь')],
    'westwild_n1': [('herb_common', 0.55, '🌾 Полевые травы')],
    'westwild_n2': [('herb_common', 0.45, '🌿 Луговые травы'), ('wood_dark', 0.15, '🪵 Молодая древесина')],
    'westwild_n3': [('herb_common', 0.35, '🌿 Холмовые травы'), ('wood_dark', 0.25, '🪵 Лесная древесина')],
    'westwild_n4': [('herb_common', 0.35, '🌿 Лесные травы'), ('forest_mushroom', 0.25, '🍄 Лесные грибы'), ('wood_dark', 0.35, '🪵 Лиственная древесина')],
    'westwild_n5': [('herb_common', 0.35, '🌿 Травы перелеска'), ('wood_dark', 0.40, '🪵 Древесина перелеска')],
    'westwild_n6': [('forest_mushroom', 0.30, '🍄 Боровые грибы'), ('wood_dark', 0.45, '🪵 Боровая древесина')],
    'westwild_n7': [('forest_mushroom', 0.35, '🍄 Тёмные грибы'), ('wood_dark', 0.50, '🪵 Тёмная древесина')],
    'westwild_n8': [('herb_common', 0.25, '🌿 Ручейные травы'), ('stone_chunk', 0.30, '🪨 Ручейный камень'), ('wood_dark', 0.25, '🪵 Прибрежная древесина')],
    'westwild_n9': [('forest_mushroom', 0.40, '🍄 Глухие грибы'), ('herb_magic', 0.10, '✨ Дикий реагент')],
    'westwild_n10': [('forest_mushroom', 0.45, '🍄 Мшистые грибы'), ('herb_magic', 0.15, '✨ Мшистый реагент')],
    'westwild_n11': [('forest_mushroom', 0.50, '🍄 Шепчущие грибы'), ('wood_dark', 0.35, '🪵 Старая древесина')],
    'ashen_n3c1': [('herb_magic', 0.35, '✨ Садовый реагент'), ('herb_common', 0.30, '🌿 Дикие травы сада')],
    'sunscar_n1': [('dry_reagent', 0.45, '🌵 Сухие реагенты')],
    'sunscar_n2': [('dry_reagent', 0.35, '🌵 Сухие растения'), ('stone_chunk', 0.30, '🪨 Песчаник')],
    'sunscar_n3': [('dry_reagent', 0.30, '🌵 Овражные реагенты'), ('stone_chunk', 0.35, '🪨 Камень оврага')],
    'sunscar_n4': [('stone_chunk', 0.45, '🪨 Каньонный камень')],
    'sunscar_n5': [('stone_chunk', 0.40, '🪨 Камень прохода'), ('dry_reagent', 0.20, '🌵 Сухая трава')],
    'sunscar_n5a1': [('oasis_fish', 0.65, '🎣 Оазисная рыба'), ('desert_plant', 0.35, '🌵 Растения оазиса')],
    'sunscar_n6': [('desert_plant', 0.30, '🌵 Пустынные растения')],
    'sunscar_n7': [('salt_crystal', 0.55, '🧂 Соль солончака')],
    'sunscar_n8': [('stone_chunk', 0.45, '🪨 Камень ущелья')],
    'sunscar_n8a1': [('dry_reagent', 0.35, '🌵 Лагерные сухоцветы')],
    'sunscar_n8a2': [('stone_chunk', 0.50, '🪨 Каменные обломки')],
    'sunscar_n9': [('salt_crystal', 0.30, '🧂 Сухая соль'), ('stone_chunk', 0.30, '🪨 Русловой камень')],
    'sunscar_n10': [('salt_crystal', 0.45, '🧂 Соляные наросты'), ('stone_chunk', 0.35, '🪨 Соляная порода')],
    'sunscar_n11': [('dry_reagent', 0.30, '🌵 Платовые сухоцветы'), ('stone_chunk', 0.30, '🪨 Платовый камень')],
    'mireveil_n1': [('marsh_herb', 0.50, '🌿 Болотные травы')],
    'mireveil_n2': [('marsh_herb', 0.45, '🌿 Низинные травы')],
    'mireveil_n3': [('reed_bundle', 0.55, '🌾 Камыш')],
    'mireveil_n4': [('marsh_fish', 0.45, '🎣 Заводная рыба'), ('marsh_herb', 0.25, '🌿 Водные травы')],
    'mireveil_n5': [('marsh_fish', 0.40, '🎣 Бродовая рыба'), ('reed_bundle', 0.30, '🌾 Камыш брода')],
    'mireveil_n5a1': [('marsh_fish', 0.60, '🎣 Рыба у мостков')],
    'mireveil_n6': [('marsh_herb', 0.35, '🌿 Мутные травы')],
    'mireveil_n7': [('reed_bundle', 0.40, '🌾 Заросший камыш'), ('marsh_herb', 0.30, '🌿 Болотные растения')],
    'mireveil_n8': [('marsh_fish', 0.45, '🎣 Рыба протоки'), ('marsh_herb', 0.25, '🌿 Травы протоки')],
    'mireveil_n8a1': [('marsh_mushroom', 0.55, '🍄 Болотные грибы')],
    'mireveil_n8a2': [('toxic_herb', 0.45, '☣️ Ядовитые травы')],
    'mireveil_n9': [('marsh_mushroom', 0.35, '🍄 Грибы трясины'), ('toxic_herb', 0.25, '☣️ Токсичные травы')],
    'mireveil_n10': [('toxic_herb', 0.50, '☣️ Травы чёрной воды')],
}

_PHASE1_LEVEL_MAX_BY_LOCATION = {
    'south_coast_shore': 3,
    'old_mine_entrance': 4,
    'westwild_n1': 2, 'westwild_n2': 3, 'westwild_n3': 4, 'westwild_n4': 5, 'westwild_n5': 6,
    'westwild_n6': 7, 'westwild_n7': 8, 'westwild_n8': 8, 'westwild_n9': 9, 'westwild_n10': 10, 'westwild_n11': 10,
    'frostspine_n1': 2, 'frostspine_n2': 3, 'frostspine_n3': 4, 'frostspine_n4': 5, 'frostspine_n5': 6,
    'frostspine_n6': 7, 'frostspine_n7': 8, 'frostspine_n8': 9, 'frostspine_n9': 10, 'frostspine_n10': 10,
    'ashen_n1': 3, 'ashen_n2': 4, 'ashen_n3': 5, 'ashen_n3a1': 6, 'ashen_n3a2': 7,
    'ashen_n3b1': 8, 'ashen_n3b2': 9, 'ashen_n3b2a1': 10, 'ashen_n3b2b1': 9, 'ashen_n3c1': 6, 'ashen_n3c2': 10,
    'sunscar_n1': 3, 'sunscar_n2': 4, 'sunscar_n3': 5, 'sunscar_n4': 6, 'sunscar_n5': 6, 'sunscar_n5a1': 6,
    'sunscar_n6': 7, 'sunscar_n7': 8, 'sunscar_n8': 9, 'sunscar_n8a1': 8, 'sunscar_n8a2': 9,
    'sunscar_n9': 9, 'sunscar_n10': 10, 'sunscar_n11': 10,
    'mireveil_n1': 3, 'mireveil_n2': 4, 'mireveil_n3': 5, 'mireveil_n4': 5, 'mireveil_n5': 6, 'mireveil_n5a1': 6,
    'mireveil_n6': 7, 'mireveil_n7': 8, 'mireveil_n8': 8, 'mireveil_n8a1': 8, 'mireveil_n8a2': 9,
    'mireveil_n9': 9, 'mireveil_n10': 10,
}

_PHASE1_ELITE_MOB_OVERRIDES = {
    # Keep hunt_elite_boars truthfully backed by real spawn data after
    # dark_forest moved to the deeper westwild_n7 canonical node.
    'westwild_n7': 'forest_boar',
    # Frostspine's legacy stone_golem is intrinsically elite, so Phase 1 uses
    # the normal rollout golem for both normal and elite-anchor spawn profiles.
    'frostspine_n6': 'mountain_stone_golem',
}

_PHASE1_ELITE_MOB_BY_LOCATION = {
    location_id: _PHASE1_ELITE_MOB_OVERRIDES.get(location_id, _PHASE1_LOCATION_MOBS[location_id][-1])
    for location_id in _PHASE1_ELITE_ANCHOR_IDS
}

for _phase1_location_id, _phase1_mobs in _PHASE1_LOCATION_MOBS.items():
    WORLD_LOCATIONS[_phase1_location_id]['mobs'] = list(_phase1_mobs)
    WORLD_LOCATIONS[_phase1_location_id]['level_max'] = _PHASE1_LEVEL_MAX_BY_LOCATION.get(_phase1_location_id, 10)
    WORLD_LOCATIONS[_phase1_location_id]['world_spawn_profiles'] = {
        mob_id: {'normal': 1}
        for mob_id in _phase1_mobs
    }
    _elite_mob_id = _PHASE1_ELITE_MOB_BY_LOCATION.get(_phase1_location_id)
    if _elite_mob_id:
        WORLD_LOCATIONS[_phase1_location_id]['world_spawn_profiles'][_elite_mob_id] = {'normal': 1, 'elite': 1}

for _phase1_location_id, _phase1_gather in _PHASE1_GATHER.items():
    WORLD_LOCATIONS[_phase1_location_id]['gather'] = list(_phase1_gather)

# The legacy dark_forest semantic layer now consistently belongs to the
# deeper canonical node that carries the player-facing “Тёмный лес” name.
WORLD_LOCATIONS['westwild_n7'].update({
    'zone_id': 'dark_forest',
    'linked_dungeon_id': 'rootbound_hollow',
    'world_boss_governance_id': 'ember_valley_world_boss',
    'region_flavor_tags': ['beast_hunting', 'poison_herbs', 'dark_wood'],
    'description': 'Густой лес, пронизанный тьмой. Здесь рыщут волки, медведи и гоблинские охотники.',
})

# Old Mine remains a sparse stub, not an elite mini-dungeon or live boss anchor.
WORLD_LOCATIONS['old_mine_entrance'].update({
    'region_id': 'ember_valley',
    'zone_role': 'normal',
    'linked_dungeon_id': None,
    'world_boss_governance_id': None,
    'region_flavor_tags': ['ore_veins', 'construct_ruins', 'goblin_camps'],
    'world_special_spawns': [],
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
    raw_location_id = str(location_id or '').strip()
    if raw_location_id in LEGACY_LOCATION_RUNTIME_OVERRIDES:
        return list(LEGACY_LOCATION_RUNTIME_OVERRIDES[raw_location_id].get('neighbors', []))

    canonical_location_id = resolve_location_id(raw_location_id)
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
