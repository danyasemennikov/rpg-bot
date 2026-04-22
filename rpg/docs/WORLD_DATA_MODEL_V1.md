# WORLD_DATA_MODEL_V1

## 1. Статус документа

Это **implementation-facing design / technical spec** следующего слоя после `WORLD_LOCATION_MAP_V1`.

Документ нужен, чтобы:
- перевести уже зафиксированную карту мира в **каноническую data model**;
- разделить **статические world data** и **динамическое player/world state**;
- подготовить понятный путь к коду без giant refactor;
- не переизобретать topology, travel, teleport и migration-логику заново.

Это **не код** и **не финальная SQL migration**.
Это рабочий source of truth для следующего шага перед implementation.

---

## 2. На что опирается этот документ

`WORLD_DATA_MODEL_V1` строится поверх уже зафиксированного:

- `WORLD_SKELETON_V1`
- `WORLD_GRAPH_V1`
- `TRAVEL_AND_TELEPORT_V1`
- `WORLD_LOCATION_MAP_V1`

Считать уже принятым:

- мир остаётся **radial**;
- центр мира — `capital_city`;
- есть **5 full routes** и **2 stub routes`;
- safe hubs — **branch hubs**, а не обязательные stop points;
- phase 1 teleport работает **только между safe nodes**;
- `south_coast_shore` и `old_mine_entrance` не входят в teleport network phase 1;
- игроку нельзя показывать raw `location_id`;
- legacy ids из текущего live slice должны поддерживаться через migration-friendly alias layer.

---

## 3. Главный принцип data model

Самая важная граница:

### 3.1. Static world data
Это то, что является **source of truth мира** и не зависит от конкретного игрока:
- список routes;
- список locations;
- граф соседства;
- security tiers;
- teleport metadata;
- return hub rules;
- route/hub/stub identity;
- tags и world-role metadata.

### 3.2. Dynamic player/world state
Это то, что зависит от состояния игрока или runtime:
- текущая локация игрока;
- какие location/player открытия уже сделаны;
- какие teleport destinations игрок реально открыл;
- позже — active encounters, PvP states, guild control, dynamic events.

### 3.3. Почему это важно
Если смешать эти два слоя:
- карта начнёт расползаться по handlers и helper'ам;
- teleport/discovery станет грязным;
- legacy migration и UI начнут хардкодиться вручную;
- любой новый world feature станет дороже.

---

## 4. Scope этого этапа

## Входит
- канонический формат **route records**;
- канонический формат **location records**;
- канонический формат **legacy alias mapping**;
- правила discovery / teleport unlock read-path;
- разделение static world data vs dynamic DB state;
- минимальный набор helper contracts.

## Не входит
- mob pools;
- encounter generation;
- gather/crafting runtime;
- dungeon schema;
- guild castle runtime;
- world boss runtime;
- final SQL migrations;
- финальная файловая структура кода.

---

## 5. Канонические data concepts

На этом этапе достаточно зафиксировать 5 основных сущностей:

1. `WorldRoute`
2. `WorldLocation`
3. `WorldLegacyAlias`
4. `PlayerLocationDiscovery`
5. `PlayerCurrentLocation`

Этого достаточно, чтобы честно покрыть:
- travel;
- display names;
- discovery;
- teleport unlocks;
- death return;
- migration from current live slice.

---

## 6. `WorldRoute`

`WorldRoute` — это макро-ветка мира.

### Обязательные поля

- `route_id`
- `route_type`
- `display_name`
- `hub_location_id`
- `entry_location_id`
- `is_stub`
- `adjacent_route_ids`
- `sort_order`

### Поля по смыслу

#### `route_id`
Стабильный внутренний id.

Канонические значения phase 1:
- `core`
- `route_westwild`
- `route_frostspine`
- `route_ashen_ruins`
- `route_sunscar`
- `route_mireveil`
- `route_south_coast_stub`
- `route_old_mine_stub`

#### `route_type`
Рабочие значения:
- `core`
- `full`
- `stub`

#### `display_name`
Player-facing имя route-ветки, если потом понадобится показывать её в UI.

#### `hub_location_id`
Для full route — id регионального safe hub.
Для stub route — `null`.

#### `entry_location_id`
Первый world node ветки.

#### `is_stub`
Явный bool для удобства read-path.

#### `adjacent_route_ids`
Кольцевая логика соседства full routes.

#### `sort_order`
Стабильный порядок вывода.

### Пример

```python
{
    "route_id": "route_westwild",
    "route_type": "full",
    "display_name": "Westwild",
    "hub_location_id": "hub_westwild",
    "entry_location_id": "westwild_n1",
    "is_stub": False,
    "adjacent_route_ids": ["route_mireveil", "route_sunscar"],
    "sort_order": 10,
}
```

---

## 7. `WorldLocation`

Это главная сущность phase 1.

### 7.1. Обязательные поля phase 1

- `location_id`
- `route_id`
- `display_name`
- `security_tier`
- `neighbors`
- `resource_tags`
- `combat_tags`
- `world_tags`
- `return_hub_id`
- `teleport_enabled`
- `teleport_group`
- `discoverable`
- `sort_order`

### 7.2. Сильно рекомендуемые поля сразу

- `legacy_aliases`
- `description_key`
- `travel_visible`

### 7.3. Поля позже

- `mob_pool_id`
- `encounter_profile_id`
- `gather_profile_id`
- `dungeon_anchor_id`
- `world_boss_anchor_id`
- `castle_allowed`
- `teleport_cost_override`
- `travel_requirements`

---

## 8. Поля `WorldLocation` подробно

### `location_id`
Стабильный внутренний id.
Игроку напрямую не показывается.

### `route_id`
К какой ветке принадлежит location.

### `display_name`
Player-facing имя локации.
Позже может разойтись на i18n keys, но в spec-слое пока это каноническое human-readable имя.

### `security_tier`
На phase 1:
- `safe`
- `guarded`
- `frontier`

Поздние core/war-узлы пока держатся через `world_tags`, а не через обязательный активный tier.

### `neighbors`
Список соседних `location_id`, куда можно travel’ить напрямую.

Главное правило:
**source of truth графа должен быть один.**
Поэтому канонично хранить соседей прямо в location record, а не дублировать это и в location, и в отдельной edge-таблице одновременно.

### `resource_tags`
Что здесь логично добывается и за чем сюда ходят.

### `combat_tags`
Как локация ощущается в энкаунтерах и бою.

### `world_tags`
Системная роль локации:
- `safe_hub`
- `teleport_hub`
- `route_entry`
- `hub_branch`
- `guarded_return`
- `side_pocket`
- `dead_end`
- `crosslink_candidate`
- `core_war_candidate`
- `dungeon_anchor_candidate`
- и т.д.

### `return_hub_id`
Куда игрок возвращается после смерти в этой локации.

Это **явное поле**, а не неявная вычисляемая магия.
Так модель остаётся проще и честнее.

### `teleport_enabled`
Участвует ли location в teleport system phase 1.

### `teleport_group`
Для phase 1 достаточно:
- `main_network`
- `null`

Это лучше, чем хардкодить teleport-допуск в куче условий.

### `discoverable`
Можно ли вообще открывать location как узел карты.

### `sort_order`
Нужен для стабильного UI и predictable order в route views.

### `legacy_aliases`
Список старых ids, которые надо резолвить в этот узел.

### `description_key`
Заготовка под player-facing location descriptions.

### `travel_visible`
Показывать ли узел в обычном travel UI.

---

## 9. Канонический минимальный шаблон `WorldLocation`

```python
{
    "location_id": "westwild_n4",
    "route_id": "route_westwild",
    "display_name": "Тёмный лес",
    "security_tier": "frontier",
    "neighbors": ["westwild_n3", "westwild_n5"],
    "resource_tags": ["wood", "mushrooms", "hides"],
    "combat_tags": ["deep_forest", "ambush", "predators"],
    "world_tags": [],
    "return_hub_id": "hub_westwild",
    "teleport_enabled": False,
    "teleport_group": None,
    "discoverable": True,
    "sort_order": 40,
    "legacy_aliases": ["dark_forest"],
    "description_key": "location.desc.westwild_n4",
    "travel_visible": True,
}
```

---

## 10. `WorldLegacyAlias`

Это отдельная каноническая сущность логики совместимости.

### Зачем она нужна
Current live slice уже использует старые ids:
- `village`
- `dark_forest`
- `frontier_outpost`
- `old_mines`

Их нельзя просто забыть, иначе transition в новый world layer будет грязным.

### Канонический смысл
`WorldLegacyAlias` — это mapping:
`legacy_location_id -> canonical_location_id`

### Phase 1 canonical aliases

- `village` -> `hub_westwild`
- `dark_forest` -> `westwild_n4`
- `frontier_outpost` -> `hub_frostspine`
- `old_mines` -> `old_mine_entrance`

### Storage rule
Эта сущность должна быть **одним source of truth**, а не размазанной по if/else в handlers.

### Простой формат

```python
WORLD_LEGACY_LOCATION_ALIASES = {
    "village": "hub_westwild",
    "dark_forest": "westwild_n4",
    "frontier_outpost": "hub_frostspine",
    "old_mines": "old_mine_entrance",
}
```

---

## 11. Dynamic state: что остаётся в БД

### 11.1. `PlayerCurrentLocation`
Это уже фактически есть в модели игроков:
- у игрока хранится текущий `location_id`

На phase 1 этого достаточно.

### 11.2. `PlayerLocationDiscovery`
Нужна простая таблица открытия локаций.

Рекомендуемый минимальный контракт:

- `telegram_id`
- `location_id`
- `discovered_at`

### Зачем она нужна
Через неё можно честно и просто покрыть:
- открытие карты;
- visibility travel destinations;
- teleport unlock read-path.

### Почему не нужна отдельная teleport unlock table прямо сейчас
Потому что на phase 1 teleport unlock логично выводится так:

> teleport destination доступен, если  
> `location.teleport_enabled == True`  
> и игрок имеет discovery для этого location.

То есть отдельная `player_teleport_unlocks` пока только дублировала бы данные.

### Рекомендуемая таблица

```sql
CREATE TABLE player_location_discovery (
    telegram_id INTEGER NOT NULL,
    location_id TEXT NOT NULL,
    discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (telegram_id, location_id)
);
```

---

## 12. Что должно быть static data, а что dynamic state

### Static data
- routes
- locations
- alias map
- graph
- return hubs
- teleport groups
- tags
- display names / description keys

### Dynamic state
- player current location
- discovered locations
- later: active encounters, control states, seasonal states, etc.

### Главное правило
Если информация одинаковая для всех игроков и описывает сам мир —
это **static world data**.

Если информация зависит от того, что уже сделал конкретный игрок —
это **dynamic state**.

---

## 13. Phase 1 storage recommendation

Для текущего проекта самый здравый и дешёвый путь такой:

### 13.1. Static world data
Хранить в коде / data module как Python dictionaries / records.

Почему:
- мир пока в активной design/stabilization фазе;
- это проще править и ревьюить;
- не требует раннего расползания по SQL и migrations;
- хорошо подходит под текущий repo style.

### 13.2. Dynamic discovery state
Хранить в SQLite.

Почему:
- это уже player-specific runtime data;
- оно должно переживать рестарты;
- это естественно ложится в существующий DB layer.

### 13.3. Не делать сейчас
Не надо на этом этапе:
- тащить всю static world map в SQL;
- строить сложную normalized schema на 8 таблиц;
- делать отдельную edge table, если граф уже стабильно живёт в `neighbors`.

Это только усложнит phase 1.

---

## 14. Helper contracts

На уровне реализации потом понадобятся простые helper-функции.

### 14.1. Identity / resolution
- `resolve_location_id(raw_location_id) -> canonical_location_id`
- `get_location(location_id) -> WorldLocation`
- `get_route(route_id) -> WorldRoute`

### 14.2. Display
- `get_location_display_name(location_id, lang)`
- `get_location_description(location_id, lang)`

### 14.3. Graph / travel
- `get_location_neighbors(location_id) -> list[str]`
- `can_travel_between(src_id, dst_id) -> bool`
- `get_travel_destinations(location_id) -> list[str]`

### 14.4. Death return
- `get_return_hub(location_id) -> hub_location_id`

### 14.5. Discovery / teleport
- `mark_location_discovered(telegram_id, location_id)`
- `is_location_discovered(telegram_id, location_id) -> bool`
- `get_unlocked_teleport_destinations(telegram_id) -> list[str]`

### 14.6. Helper rule
Helper’ы должны **читать один канонический source of truth**,
а не пересобирать world logic вручную в каждом handler.

---

## 15. Teleport read-path

На phase 1 teleport model должна читаться так:

### Destination valid if
- `location.teleport_enabled == True`
- `location.teleport_group == "main_network"`
- player has discovery for that location

### Teleport usable from
- current location has `security_tier == "safe"`
- current location has `teleport_enabled == True`

### Explicit exclusions
Даже если location discoverable:
- `south_coast_shore`
- `old_mine_entrance`

не входят в teleport network phase 1.

---

## 16. Return-on-death read-path

Смерть в поле не должна вычисляться через “ближайшую точку по ощущениям”.

Правильный read-path:
- берём current `location_id`
- резолвим canonical location
- читаем `return_hub_id`
- переносим игрока туда

Это даёт:
- предсказуемость;
- простоту тестов;
- отсутствие скрытой логики по route distance.

---

## 17. Что НЕ надо делать в data model прямо сейчас

### Не надо
- вводить отдельную сущность `WorldEdge`, если edges дублируют `neighbors`
- вводить отдельную сущность `TeleportNode`, если teleport уже покрывается metadata полями location
- вводить отдельную таблицу `player_teleport_unlocks`, если unlock можно читать из discovery
- строить сразу огромную hierarchical region/zone/subzone schema
- смешивать mobs, gathering и encounter rules в первую world migration

### Почему
Потому что phase 1 задача намного уже:
сделать **чистую, понятную, migration-friendly основу мира**.

---

## 18. Phase 1 recommended file/data shape

На уровне кода потом разумно иметь что-то в таком духе:

- `WORLD_ROUTES`
- `WORLD_LOCATIONS`
- `WORLD_LEGACY_LOCATION_ALIASES`

И небольшие helper’ы поверх них.

### Пример верхнего уровня

```python
WORLD_ROUTES = {...}
WORLD_LOCATIONS = {...}
WORLD_LEGACY_LOCATION_ALIASES = {...}
```

Этого достаточно, чтобы:
- показать карту;
- валидировать travel;
- открыть location discovery;
- собирать teleport destinations;
- поддержать migration from live slice.

---

## 19. Минимальный implementation order

### Step A
Зафиксировать static world data module:
- routes
- locations
- aliases

### Step B
Перевести read-path текущих location ids через canonical resolver.

### Step C
Добавить `player_location_discovery`.

### Step D
Подключить travel UI к `neighbors` и `display_name`.

### Step E
Подключить teleport phase 1 к:
- `teleport_enabled`
- `teleport_group`
- discovery state

### Step F
Подключить death return через `return_hub_id`.

Это и есть минимальный coherent путь без giant refactor.

---

## 20. Что считать source of truth после этого документа

1. Static world map хранится отдельно от player runtime state.
2. `WorldLocation` — главная каноническая сущность мира phase 1.
3. Source of truth графа phase 1 — поле `neighbors` внутри location record.
4. Source of truth совместимости со старым live slice — единый legacy alias mapping.
5. Source of truth teleport eligibility — metadata fields локации + player discovery.
6. Source of truth return-on-death — явное поле `return_hub_id`.
7. Static world data phase 1 разумнее хранить в code/data layer, а не тащить в SQL.
8. Dynamic player discovery нужно хранить в SQLite.
9. Не нужно вводить отдельные teleport unlock tables и edge tables без реальной необходимости.
10. Этот документ является следующей implementation-facing базой после `WORLD_LOCATION_MAP_V1`.

---

## 21. Короткий итог

Если совсем по-честному, то для phase 1 мира реально нужны только три большие вещи:

- **канонический `WORLD_LOCATIONS`**
- **канонический `WORLD_ROUTES`**
- **простая `player_location_discovery`**

Плюс alias map для migration.

Всё остальное — либо helper layer, либо future expansion.
И это хорошо: модель остаётся достаточно сильной, чтобы на ней строить код, но не превращается в перегруженную архитектурную махину.
