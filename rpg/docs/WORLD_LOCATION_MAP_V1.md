# WORLD_LOCATION_MAP_V1

## 1. Статус документа

Это **design / technical spec** следующего слоя мира после `WORLD_SKELETON_V1`, `WORLD_GRAPH_V1` и `TRAVEL_AND_TELEPORT_V1`.

Документ нужен, чтобы:
- зафиксировать **канонический location map** мира на node-level;
- перевести world design в **implementation-facing форму**;
- не переизобретать карту заново при переходе к `WORLD_DATA_MODEL_V1` и коду;
- сохранить уже принятые решения по topology, travel, teleport, PvP-risk и migration из текущего live slice.

Это **не код** и **не final data schema**, но уже почти прямой source of truth для следующего технического этапа.

---

## 2. Что этот документ считает уже зафиксированным

### 2.1. Общая форма мира
- Мир остаётся **radial world**.
- Центр карты — `capital_city`.
- Есть **5 полных веток**:
  - `route_westwild`
  - `route_frostspine`
  - `route_ashen_ruins`
  - `route_sunscar`
  - `route_mireveil`
- Есть **2 stub-ветки**:
  - `route_south_coast_stub`
  - `route_old_mine_stub`

### 2.2. Safe hubs
У каждой полной ветки есть branch-safe hub:
- `hub_westwild`
- `hub_frostspine`
- `hub_ashen_ruins`
- `hub_sunscar`
- `hub_mireveil`

Safe hubs:
- являются **ответвлением**, а не обязательной main-line остановкой;
- работают как local logistics anchors;
- используются для regional return-on-death;
- участвуют в teleport network phase 1.

### 2.3. Security tiers
На текущем этапе канонический боевой слой карты:
- `safe`
- `guarded`
- `frontier`

`core/war` пока не раскрашивается как обязательный активный tier для late nodes.
Вместо этого поздние узлы получают `core_war_candidate` через metadata tags.

### 2.4. Cross-links
- Первые межветочные links появляются **не раньше `N6`**.
- На `N8-N9` neighbor mesh сгущается.
- Редкие диагонали появляются **не раньше `N10`**.
- Диагоналей должно быть мало, чтобы не убить radial-читаемость карты.

### 2.5. Teleport phase 1
Телепорт phase 1:
- работает **только между safe nodes**;
- открывается только после **физического посещения** destination;
- по умолчанию открыт только `capital_city`;
- использует **named locations**, а не raw ids;
- не включает `south_coast_shore` и `old_mine_entrance`.

---

## 3. Рабочие правила по id и названиям

### 3.1. Internal ids
- Внутренние `location_id` должны быть простыми и стабильными.
- Игроку нельзя показывать raw id.
- У каждой локации есть отдельный `display_name`.
- Позже допустимы aliases для текстовых команд / teleport stones.

### 3.2. Naming template for regular nodes
- `westwild_n1`, `westwild_n2`, ...
- `frostspine_n1`, `frostspine_n2`, ...
- `sunscar_n1`, `sunscar_n2`, ...
- `mireveil_n1`, `mireveil_n2`, ...
- `ashen_n1`, `ashen_n2`, ...

Для ветвлений:
- `ashen_n3a1`
- `ashen_n3b2`
- `sunscar_n5a1`
- `mireveil_n8a2`

### 3.3. Naming style
- Хабы / города / деревни: **одно слово**, красиво, но без пафоса.
- Обычные локации: **1–2 слова**.
- Ближе к столице названия проще.
- Дальше можно чуть более fantasy-flavored, но без перегруза.

---

## 4. Зафиксированные display names и special nodes

- `capital_city` = **Астер / Aster**
- `hub_westwild` = **Элмор / Elmor**
- `hub_frostspine` = **Карн / Karn**
- `hub_ashen_ruins` = **Эмбер / Ember**
- `hub_sunscar` = **Мираж / Mirage**
- `hub_mireveil` = **Вельм / Velm**
- `south_coast_shore` = **Южный берег / South Shore**
- `old_mine_entrance` = **Старая шахта / Old Mine**

---

## 5. Migration logic from current live slice

Это **role-correct migration**, а не topology-exact mapping.

- `village` → legacy alias of `hub_westwild`
- `dark_forest` → legacy alias of `westwild_n4`
- `frontier_outpost` → legacy alias of `hub_frostspine`
- `old_mines` → legacy alias of `old_mine_entrance`

---

## 6. Route shapes and identities

### 6.1. `route_westwild`
- Почти прямая spine-ветка.
- Самый универсальный стартовый маршрут.
- Линия: поля → опушки → лес → глубокий бор.
- Основная identity: hunting / wood / herbs / hides.

### 6.2. `route_frostspine`
- Прямая ветка.
- Узкая, choke-heavy, более маршрутная.
- Основная identity: ore / minerals / stone / crystals.
- `old_mine_entrance` — side-branch от ранней части ветки.

### 6.3. `route_ashen_ruins`
- Короткая, но заметно более древовидная ветка.
- После первых узлов идёт развилка на hub-ветку, main progression и side dead-end pocket.
- Основная identity: relics / undead / holy-arcane materials / forgotten structures.

### 6.4. `route_sunscar`
- Умеренно ветвистая.
- Не “один сплошной песок”, а mix из badlands / canyon / oasis / deeper desert.
- Основная identity: dry alchemy / salt / resins / rare minerals.

### 6.5. `route_mireveil`
- Умеренно ветвистая.
- Вязкая, неприятная, resource-dense болотная линия.
- Основная identity: toxins / fungi / reeds / fish / swamp alchemy.

---

## 7. Exact security tiers

### 7.1. Safe
- `capital_city`
- `hub_westwild`
- `hub_frostspine`
- `hub_ashen_ruins`
- `hub_sunscar`
- `hub_mireveil`

### 7.2. Guarded
Ровно по одному guarded-return узлу после каждого safe hub:
- `westwild_n5`
- `frostspine_n5`
- `ashen_n3a2`
- `sunscar_n5a1`
- `mireveil_n5a1`

### 7.3. Frontier
Все остальные текущие overworld nodes:
- все main nodes вне safe / guarded;
- `south_coast_shore`;
- `old_mine_entrance`.

### 7.4. Core/war handling for now
Late nodes пока **не получают обязательный активный `core/war` tier**.
Они отмечаются через `core_war_candidate` в `world_tags`.

---

## 8. Tag taxonomy

Теги нужны не для игрока, а как короткий слой смысла для систем, баланса, data model и будущего кода.

### 8.1. `resource_tags`
- `trade`
- `crafting`
- `regional_goods`
- `small_game`
- `meat`
- `hides`
- `bones`
- `wood`
- `herbs`
- `mushrooms`
- `fish`
- `reeds`
- `fungi`
- `toxins`
- `glands`
- `ore`
- `coal`
- `stone`
- `crystals`
- `rare_metal`
- `relics`
- `arcane_dust`
- `holy_materials`
- `undead_trophies`
- `dry_alchemy`
- `salt`
- `resin`
- `rare_minerals`
- `shells`

### 8.2. `combat_tags`
- `open_ground`
- `roadside`
- `forest_edge`
- `deep_forest`
- `ambush`
- `predators`
- `mixed_cover`
- `ravine`
- `rocky`
- `choke_path`
- `cold`
- `cliffside`
- `snowfield`
- `exposure`
- `ruins`
- `ritual_site`
- `undead`
- `constructs`
- `cursed`
- `confined`
- `overgrown_ruins`
- `canyon`
- `arid`
- `open_dunes`
- `salt_flat`
- `ridge`
- `plateau`
- `marsh_edge`
- `slow_terrain`
- `muddy_ground`
- `water_edge`
- `toxic_water`
- `swamp_cover`
- `deep_swamp`
- `elite_pressure`

### 8.3. `world_tags`
- `capital`
- `safe_hub`
- `teleport_hub`
- `route_entry`
- `starter_friendly`
- `hub_branch`
- `guarded_return`
- `branch_node`
- `side_pocket`
- `dead_end`
- `crosslink_candidate`
- `late_crosslink_candidate`
- `core_war_candidate`
- `dungeon_anchor_candidate`
- `world_boss_candidate`
- `guild_pressure_high`
- `coast_stub`
- `mine_stub`
- `underworld_gateway_candidate`
- `apex_edge`

---

## 9. Location metadata contract

Ниже — рабочий контракт полей для будущей data model.

### 9.1. Required fields for phase 1
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

### 9.2. Strongly recommended already in phase 1
- `sort_order`
- `legacy_aliases`
- `description_key` or `description_stub`
- `travel_visible`

### 9.3. Future-facing fields
- `pvp_tier_override`
- `castle_allowed`
- `dungeon_anchor_id`
- `world_boss_anchor_id`
- `mob_pool_id`
- `encounter_profile_id`
- `gather_profile_id`
- `service_flags`
- `teleport_cost_override`
- `travel_requirements`

---

## 10. Canonical world graph

### 10.1. Core / stubs
- `capital_city` ↔ `westwild_n1`, `frostspine_n1`, `ashen_n1`, `sunscar_n1`, `mireveil_n1`, `south_coast_shore`
- `south_coast_shore` ↔ `capital_city`
- `old_mine_entrance` ↔ `frostspine_n1`

### 10.2. `route_westwild`
- `westwild_n1` ↔ `capital_city`, `westwild_n2`
- `westwild_n2` ↔ `westwild_n1`, `westwild_n3`
- `westwild_n3` ↔ `westwild_n2`, `westwild_n4`
- `westwild_n4` ↔ `westwild_n3`, `westwild_n5`
- `westwild_n5` ↔ `westwild_n4`, `westwild_n6`, `hub_westwild`
- `hub_westwild` ↔ `westwild_n5`
- `westwild_n6` ↔ `westwild_n5`, `westwild_n7`, `mireveil_n6`, `sunscar_n6`
- `westwild_n7` ↔ `westwild_n6`, `westwild_n8`
- `westwild_n8` ↔ `westwild_n7`, `westwild_n9`, `mireveil_n8`, `sunscar_n8`
- `westwild_n9` ↔ `westwild_n8`, `westwild_n10`, `mireveil_n9`, `sunscar_n9`
- `westwild_n10` ↔ `westwild_n9`, `westwild_n11`, `frostspine_n10`
- `westwild_n11` ↔ `westwild_n10`

### 10.3. `route_frostspine`
- `frostspine_n1` ↔ `capital_city`, `frostspine_n2`, `old_mine_entrance`
- `frostspine_n2` ↔ `frostspine_n1`, `frostspine_n3`
- `frostspine_n3` ↔ `frostspine_n2`, `frostspine_n4`
- `frostspine_n4` ↔ `frostspine_n3`, `frostspine_n5`
- `frostspine_n5` ↔ `frostspine_n4`, `frostspine_n6`, `hub_frostspine`
- `hub_frostspine` ↔ `frostspine_n5`
- `frostspine_n6` ↔ `frostspine_n5`, `frostspine_n7`, `mireveil_n6`, `ashen_n3b1`
- `frostspine_n7` ↔ `frostspine_n6`, `frostspine_n8`
- `frostspine_n8` ↔ `frostspine_n7`, `frostspine_n9`, `mireveil_n8`, `ashen_n3b2`
- `frostspine_n9` ↔ `frostspine_n8`, `frostspine_n10`, `mireveil_n9`, `ashen_n3b2a1`
- `frostspine_n10` ↔ `frostspine_n9`, `westwild_n10`

### 10.4. `route_ashen_ruins`
- `ashen_n1` ↔ `capital_city`, `ashen_n2`
- `ashen_n2` ↔ `ashen_n1`, `ashen_n3`
- `ashen_n3` ↔ `ashen_n2`, `ashen_n3a1`, `ashen_n3b1`, `ashen_n3c1`
- `ashen_n3a1` ↔ `ashen_n3`, `ashen_n3a2`
- `ashen_n3a2` ↔ `ashen_n3a1`, `hub_ashen_ruins`
- `hub_ashen_ruins` ↔ `ashen_n3a2`
- `ashen_n3b1` ↔ `ashen_n3`, `ashen_n3b2`, `frostspine_n6`, `sunscar_n6`
- `ashen_n3b2` ↔ `ashen_n3b1`, `ashen_n3b2a1`, `ashen_n3b2b1`, `frostspine_n8`, `sunscar_n8`
- `ashen_n3b2a1` ↔ `ashen_n3b2`, `frostspine_n9`, `sunscar_n9`
- `ashen_n3b2b1` ↔ `ashen_n3b2`, `mireveil_n10`
- `ashen_n3c1` ↔ `ashen_n3`, `ashen_n3c2`
- `ashen_n3c2` ↔ `ashen_n3c1`

### 10.5. `route_sunscar`
- `sunscar_n1` ↔ `capital_city`, `sunscar_n2`
- `sunscar_n2` ↔ `sunscar_n1`, `sunscar_n3`
- `sunscar_n3` ↔ `sunscar_n2`, `sunscar_n4`
- `sunscar_n4` ↔ `sunscar_n3`, `sunscar_n5`
- `sunscar_n5` ↔ `sunscar_n4`, `sunscar_n6`, `sunscar_n5a1`
- `sunscar_n5a1` ↔ `sunscar_n5`, `hub_sunscar`
- `hub_sunscar` ↔ `sunscar_n5a1`
- `sunscar_n6` ↔ `sunscar_n5`, `sunscar_n7`, `ashen_n3b1`, `westwild_n6`
- `sunscar_n7` ↔ `sunscar_n6`, `sunscar_n8`
- `sunscar_n8` ↔ `sunscar_n7`, `sunscar_n9`, `sunscar_n8a1`, `ashen_n3b2`, `westwild_n8`
- `sunscar_n8a1` ↔ `sunscar_n8`, `sunscar_n8a2`
- `sunscar_n8a2` ↔ `sunscar_n8a1`
- `sunscar_n9` ↔ `sunscar_n8`, `sunscar_n10`, `ashen_n3b2a1`, `westwild_n9`
- `sunscar_n10` ↔ `sunscar_n9`, `sunscar_n11`
- `sunscar_n11` ↔ `sunscar_n10`

### 10.6. `route_mireveil`
- `mireveil_n1` ↔ `capital_city`, `mireveil_n2`
- `mireveil_n2` ↔ `mireveil_n1`, `mireveil_n3`
- `mireveil_n3` ↔ `mireveil_n2`, `mireveil_n4`
- `mireveil_n4` ↔ `mireveil_n3`, `mireveil_n5`
- `mireveil_n5` ↔ `mireveil_n4`, `mireveil_n6`, `mireveil_n5a1`
- `mireveil_n5a1` ↔ `mireveil_n5`, `hub_mireveil`
- `hub_mireveil` ↔ `mireveil_n5a1`
- `mireveil_n6` ↔ `mireveil_n5`, `mireveil_n7`, `westwild_n6`, `frostspine_n6`
- `mireveil_n7` ↔ `mireveil_n6`, `mireveil_n8`
- `mireveil_n8` ↔ `mireveil_n7`, `mireveil_n9`, `mireveil_n8a1`, `westwild_n8`, `frostspine_n8`
- `mireveil_n8a1` ↔ `mireveil_n8`, `mireveil_n8a2`
- `mireveil_n8a2` ↔ `mireveil_n8a1`
- `mireveil_n9` ↔ `mireveil_n8`, `mireveil_n10`, `westwild_n9`, `frostspine_n9`
- `mireveil_n10` ↔ `mireveil_n9`, `ashen_n3b2b1`

---

## 11. Node-level location map

Ниже — каноническая таблица узлов в implementation-facing форме.

| location_id | display_name | route_id | security_tier | neighbors | resource_tags | combat_tags | world_tags | return_hub_id | teleport_enabled | teleport_group | discoverable | sort_order | legacy_aliases |
|---|---|---:|---|---|---|---|---|---|---:|---|---:|---:|---|
| `capital_city` | Астер | `core` | `safe` | `westwild_n1,frostspine_n1,ashen_n1,sunscar_n1,mireveil_n1,south_coast_shore` | `trade,crafting,regional_goods` |  | `capital,safe_hub,teleport_hub` | `capital_city` | `true` | `main_network` | `true` | `0` |  |
| `south_coast_shore` | Южный берег | `route_south_coast_stub` | `frontier` | `capital_city` | `fish,reeds,shells` | `open_ground,water_edge` | `coast_stub` | `capital_city` | `false` |  | `true` | `10` |  |
| `old_mine_entrance` | Старая шахта | `route_old_mine_stub` | `frontier` | `frostspine_n1` | `ore,stone,crystals` | `rocky,choke_path,confined` | `mine_stub,underworld_gateway_candidate` | `hub_frostspine` | `false` |  | `true` | `20` | `old_mines` |
| `westwild_n1` | Зелёный тракт | `route_westwild` | `frontier` | `capital_city,westwild_n2` | `herbs,small_game` | `open_ground,roadside` | `route_entry,starter_friendly` | `capital_city` | `false` |  | `true` | `101` |  |
| `westwild_n2` | Лесная опушка | `route_westwild` | `frontier` | `westwild_n1,westwild_n3` | `wood,herbs,small_game` | `forest_edge,roadside` | `starter_friendly` | `hub_westwild` | `false` |  | `true` | `102` |  |
| `westwild_n3` | Перелесье | `route_westwild` | `frontier` | `westwild_n2,westwild_n4` | `wood,herbs,hides` | `mixed_cover,predators` |  | `hub_westwild` | `false` |  | `true` | `103` |  |
| `westwild_n4` | Тёмный лес | `route_westwild` | `frontier` | `westwild_n3,westwild_n5` | `wood,mushrooms,hides` | `deep_forest,ambush,predators` |  | `hub_westwild` | `false` |  | `true` | `104` | `dark_forest` |
| `westwild_n5` | Олений дол | `route_westwild` | `guarded` | `westwild_n4,westwild_n6,hub_westwild` | `meat,hides,herbs` | `mixed_cover,predators` | `hub_branch,guarded_return` | `hub_westwild` | `false` |  | `true` | `105` |  |
| `hub_westwild` | Элмор | `route_westwild` | `safe` | `westwild_n5` | `trade,regional_goods` |  | `safe_hub,teleport_hub` | `hub_westwild` | `true` | `main_network` | `true` | `106` | `village` |
| `westwild_n6` | Высокий бор | `route_westwild` | `frontier` | `westwild_n5,westwild_n7,mireveil_n6,sunscar_n6` | `wood,mushrooms,hides` | `deep_forest,predators` | `crosslink_candidate` | `hub_westwild` | `false` |  | `true` | `107` |  |
| `westwild_n7` | Бурелом | `route_westwild` | `frontier` | `westwild_n6,westwild_n8` | `wood,mushrooms` | `deep_forest,ambush,mixed_cover` |  | `hub_westwild` | `false` |  | `true` | `108` |  |
| `westwild_n8` | Каменный ручей | `route_westwild` | `frontier` | `westwild_n7,westwild_n9,mireveil_n8,sunscar_n8` | `wood,herbs,stone` | `mixed_cover,choke_path` | `crosslink_candidate,dungeon_anchor_candidate` | `hub_westwild` | `false` |  | `true` | `109` |  |
| `westwild_n9` | Глухая чаща | `route_westwild` | `frontier` | `westwild_n8,westwild_n10,mireveil_n9,sunscar_n9` | `hides,mushrooms,herbs` | `deep_forest,ambush,predators` | `late_crosslink_candidate,core_war_candidate,guild_pressure_high` | `hub_westwild` | `false` |  | `true` | `110` |  |
| `westwild_n10` | Мшистый яр | `route_westwild` | `frontier` | `westwild_n9,westwild_n11,frostspine_n10` | `mushrooms,herbs,hides` | `ravine,ambush,deep_forest` | `core_war_candidate,world_boss_candidate` | `hub_westwild` | `false` |  | `true` | `111` |  |
| `westwild_n11` | Шепчущий бор | `route_westwild` | `frontier` | `westwild_n10` | `mushrooms,herbs,hides` | `deep_forest,predators,elite_pressure` | `apex_edge` | `hub_westwild` | `false` |  | `true` | `112` |  |
| `frostspine_n1` | Каменный путь | `route_frostspine` | `frontier` | `capital_city,frostspine_n2,old_mine_entrance` | `stone,ore` | `rocky,choke_path` | `route_entry` | `capital_city` | `false` |  | `true` | `201` |  |
| `frostspine_n2` | Предгорье | `route_frostspine` | `frontier` | `frostspine_n1,frostspine_n3` | `ore,stone` | `rocky,cliffside` |  | `hub_frostspine` | `false` |  | `true` | `202` |  |
| `frostspine_n3` | Узкий перевал | `route_frostspine` | `frontier` | `frostspine_n2,frostspine_n4` | `ore,stone` | `choke_path,cliffside,cold` |  | `hub_frostspine` | `false` |  | `true` | `203` |  |
| `frostspine_n4` | Холодный склон | `route_frostspine` | `frontier` | `frostspine_n3,frostspine_n5` | `ore,coal,stone` | `cold,cliffside,rocky` |  | `hub_frostspine` | `false` |  | `true` | `204` |  |
| `frostspine_n5` | Серый кряж | `route_frostspine` | `guarded` | `frostspine_n4,frostspine_n6,hub_frostspine` | `ore,coal,stone` | `cold,rocky,choke_path` | `hub_branch,guarded_return` | `hub_frostspine` | `false` |  | `true` | `205` |  |
| `hub_frostspine` | Карн | `route_frostspine` | `safe` | `frostspine_n5` | `trade,crafting,regional_goods` |  | `safe_hub,teleport_hub` | `hub_frostspine` | `true` | `main_network` | `true` | `206` | `frontier_outpost` |
| `frostspine_n6` | Рудный ход | `route_frostspine` | `frontier` | `frostspine_n5,frostspine_n7,mireveil_n6,ashen_n3b1` | `ore,coal,crystals` | `rocky,choke_path,confined` | `crosslink_candidate` | `hub_frostspine` | `false` |  | `true` | `207` |  |
| `frostspine_n7` | Ледяной перевал | `route_frostspine` | `frontier` | `frostspine_n6,frostspine_n8` | `ore,crystals` | `cold,choke_path,cliffside` |  | `hub_frostspine` | `false` |  | `true` | `208` |  |
| `frostspine_n8` | Белый уступ | `route_frostspine` | `frontier` | `frostspine_n7,frostspine_n9,mireveil_n8,ashen_n3b2` | `crystals,stone,ore` | `cold,cliffside,exposure` | `crosslink_candidate,dungeon_anchor_candidate` | `hub_frostspine` | `false` |  | `true` | `209` |  |
| `frostspine_n9` | Снежный склон | `route_frostspine` | `frontier` | `frostspine_n8,frostspine_n10,mireveil_n9,ashen_n3b2a1` | `crystals,ore,rare_metal` | `snowfield,cold,exposure` | `late_crosslink_candidate,core_war_candidate,guild_pressure_high` | `hub_frostspine` | `false` |  | `true` | `210` |  |
| `frostspine_n10` | Снежное плато | `route_frostspine` | `frontier` | `frostspine_n9,westwild_n10` | `rare_metal,crystals,stone` | `plateau,cold,exposure,elite_pressure` | `core_war_candidate,world_boss_candidate,apex_edge` | `hub_frostspine` | `false` |  | `true` | `211` |  |
| `ashen_n1` | Старая дорога | `route_ashen_ruins` | `frontier` | `capital_city,ashen_n2` | `relics` | `roadside,ruins` | `route_entry` | `capital_city` | `false` |  | `true` | `301` |  |
| `ashen_n2` | Разбитый мост | `route_ashen_ruins` | `frontier` | `ashen_n1,ashen_n3` | `relics,arcane_dust` | `ruins,choke_path` |  | `hub_ashen_ruins` | `false` |  | `true` | `302` |  |
| `ashen_n3` | Каменный круг | `route_ashen_ruins` | `frontier` | `ashen_n2,ashen_n3a1,ashen_n3b1,ashen_n3c1` | `relics,arcane_dust` | `ritual_site,cursed` | `branch_node` | `hub_ashen_ruins` | `false` |  | `true` | `303` |  |
| `ashen_n3a1` | Пустой двор | `route_ashen_ruins` | `frontier` | `ashen_n3,ashen_n3a2` | `relics,holy_materials` | `ruins,undead` | `hub_branch` | `hub_ashen_ruins` | `false` |  | `true` | `304` |  |
| `ashen_n3a2` | Старый храм | `route_ashen_ruins` | `guarded` | `ashen_n3a1,hub_ashen_ruins` | `holy_materials,relics` | `ruins,undead,cursed` | `guarded_return` | `hub_ashen_ruins` | `false` |  | `true` | `305` |  |
| `hub_ashen_ruins` | Эмбер | `route_ashen_ruins` | `safe` | `ashen_n3a2` | `trade,regional_goods` |  | `safe_hub,teleport_hub` | `hub_ashen_ruins` | `true` | `main_network` | `true` | `306` |  |
| `ashen_n3b1` | Тихие руины | `route_ashen_ruins` | `frontier` | `ashen_n3,ashen_n3b2,frostspine_n6,sunscar_n6` | `relics,arcane_dust,undead_trophies` | `ruins,undead` | `crosslink_candidate` | `hub_ashen_ruins` | `false` |  | `true` | `307` |  |
| `ashen_n3b2` | Реликтовый зал | `route_ashen_ruins` | `frontier` | `ashen_n3b1,ashen_n3b2a1,ashen_n3b2b1,frostspine_n8,sunscar_n8` | `relics,arcane_dust,holy_materials` | `ruins,constructs,undead,confined` | `crosslink_candidate,dungeon_anchor_candidate` | `hub_ashen_ruins` | `false` |  | `true` | `308` |  |
| `ashen_n3b2a1` | Зал печатей | `route_ashen_ruins` | `frontier` | `ashen_n3b2,frostspine_n9,sunscar_n9` | `relics,holy_materials,arcane_dust` | `ritual_site,constructs,cursed,elite_pressure` | `late_crosslink_candidate,core_war_candidate,world_boss_candidate` | `hub_ashen_ruins` | `false` |  | `true` | `309` |  |
| `ashen_n3b2b1` | Теневой ход | `route_ashen_ruins` | `frontier` | `ashen_n3b2,mireveil_n10` | `arcane_dust,undead_trophies,relics` | `confined,cursed,ambush` | `core_war_candidate,guild_pressure_high` | `hub_ashen_ruins` | `false` |  | `true` | `310` |  |
| `ashen_n3c1` | Забытый сад | `route_ashen_ruins` | `frontier` | `ashen_n3,ashen_n3c2` | `herbs,relics` | `overgrown_ruins,undead` | `side_pocket` | `hub_ashen_ruins` | `false` |  | `true` | `311` |  |
| `ashen_n3c2` | Старый склеп | `route_ashen_ruins` | `frontier` | `ashen_n3c1` | `undead_trophies,relics,holy_materials` | `confined,undead,cursed` | `side_pocket,dead_end,dungeon_anchor_candidate` | `hub_ashen_ruins` | `false` |  | `true` | `312` |  |
| `sunscar_n1` | Южный тракт | `route_sunscar` | `frontier` | `capital_city,sunscar_n2` | `dry_alchemy,small_game` | `open_ground,arid,roadside` | `route_entry` | `capital_city` | `false` |  | `true` | `401` |  |
| `sunscar_n2` | Красный склон | `route_sunscar` | `frontier` | `sunscar_n1,sunscar_n3` | `stone,resin` | `rocky,arid` |  | `hub_sunscar` | `false` |  | `true` | `402` |  |
| `sunscar_n3` | Каменная балка | `route_sunscar` | `frontier` | `sunscar_n2,sunscar_n4` | `stone,dry_alchemy` | `canyon,ambush` |  | `hub_sunscar` | `false` |  | `true` | `403` |  |
| `sunscar_n4` | Узкий каньон | `route_sunscar` | `frontier` | `sunscar_n3,sunscar_n5` | `stone,salt` | `canyon,choke_path,ambush` |  | `hub_sunscar` | `false` |  | `true` | `404` |  |
| `sunscar_n5` | Старый перевал | `route_sunscar` | `frontier` | `sunscar_n4,sunscar_n6,sunscar_n5a1` | `salt,dry_alchemy,rare_minerals` | `rocky,choke_path,arid` | `hub_branch` | `hub_sunscar` | `false` |  | `true` | `405` |  |
| `sunscar_n5a1` | Оазис | `route_sunscar` | `guarded` | `sunscar_n5,hub_sunscar` | `fish,reeds,dry_alchemy` | `water_edge,arid` | `guarded_return` | `hub_sunscar` | `false` |  | `true` | `406` |  |
| `hub_sunscar` | Мираж | `route_sunscar` | `safe` | `sunscar_n5a1` | `trade,regional_goods` |  | `safe_hub,teleport_hub` | `hub_sunscar` | `true` | `main_network` | `true` | `407` |  |
| `sunscar_n6` | Пески | `route_sunscar` | `frontier` | `sunscar_n5,sunscar_n7,ashen_n3b1,westwild_n6` | `dry_alchemy,salt` | `open_dunes,arid,exposure` | `crosslink_candidate` | `hub_sunscar` | `false` |  | `true` | `408` |  |
| `sunscar_n7` | Соляное поле | `route_sunscar` | `frontier` | `sunscar_n6,sunscar_n8` | `salt,dry_alchemy,rare_minerals` | `salt_flat,exposure,arid` |  | `hub_sunscar` | `false` |  | `true` | `409` |  |
| `sunscar_n8` | Каменный каньон | `route_sunscar` | `frontier` | `sunscar_n7,sunscar_n9,sunscar_n8a1,ashen_n3b2,westwild_n8` | `resin,rare_minerals,dry_alchemy` | `canyon,ambush,rocky` | `crosslink_candidate` | `hub_sunscar` | `false` |  | `true` | `410` |  |
| `sunscar_n8a1` | Старый лагерь | `route_sunscar` | `frontier` | `sunscar_n8,sunscar_n8a2` | `dry_alchemy,resin` | `roadside,ambush,arid` | `side_pocket` | `hub_sunscar` | `false` |  | `true` | `411` |  |
| `sunscar_n8a2` | Каменные столбы | `route_sunscar` | `frontier` | `sunscar_n8a1` | `rare_minerals,dry_alchemy` | `rocky,elite_pressure` | `side_pocket,dungeon_anchor_candidate` | `hub_sunscar` | `false` |  | `true` | `412` |  |
| `sunscar_n9` | Сухое русло | `route_sunscar` | `frontier` | `sunscar_n8,sunscar_n10,ashen_n3b2a1,westwild_n9` | `dry_alchemy,rare_minerals,salt` | `canyon,ambush,exposure` | `late_crosslink_candidate,core_war_candidate,dungeon_anchor_candidate` | `hub_sunscar` | `false` |  | `true` | `413` |  |
| `sunscar_n10` | Высокая гряда | `route_sunscar` | `frontier` | `sunscar_n9,sunscar_n11` | `rare_minerals,resin,salt` | `ridge,exposure,elite_pressure` | `core_war_candidate,world_boss_candidate,guild_pressure_high` | `hub_sunscar` | `false` |  | `true` | `414` |  |
| `sunscar_n11` | Высокое плато | `route_sunscar` | `frontier` | `sunscar_n10` | `rare_minerals,dry_alchemy` | `plateau,arid,elite_pressure` | `apex_edge` | `hub_sunscar` | `false` |  | `true` | `415` |  |
| `mireveil_n1` | Мокрый тракт | `route_mireveil` | `frontier` | `capital_city,mireveil_n2` | `reeds,fish,herbs` | `marsh_edge,slow_terrain,roadside` | `route_entry` | `capital_city` | `false` |  | `true` | `501` |  |
| `mireveil_n2` | Низина | `route_mireveil` | `frontier` | `mireveil_n1,mireveil_n3` | `reeds,fish` | `muddy_ground,slow_terrain` |  | `hub_mireveil` | `false` |  | `true` | `502` |  |
| `mireveil_n3` | Камыши | `route_mireveil` | `frontier` | `mireveil_n2,mireveil_n4` | `reeds,fish,fungi` | `swamp_cover,ambush` |  | `hub_mireveil` | `false` |  | `true` | `503` |  |
| `mireveil_n4` | Сырой берег | `route_mireveil` | `frontier` | `mireveil_n3,mireveil_n5` | `fish,reeds,fungi` | `water_edge,slow_terrain` |  | `hub_mireveil` | `false` |  | `true` | `504` |  |
| `mireveil_n5` | Старый брод | `route_mireveil` | `frontier` | `mireveil_n4,mireveil_n6,mireveil_n5a1` | `fish,reeds,glands` | `water_edge,choke_path,slow_terrain` | `hub_branch` | `hub_mireveil` | `false` |  | `true` | `505` |  |
| `mireveil_n5a1` | Рыбачий мосток | `route_mireveil` | `guarded` | `mireveil_n5,hub_mireveil` | `fish,reeds` | `water_edge` | `guarded_return` | `hub_mireveil` | `false` |  | `true` | `506` |  |
| `hub_mireveil` | Вельм | `route_mireveil` | `safe` | `mireveil_n5a1` | `trade,regional_goods` |  | `safe_hub,teleport_hub` | `hub_mireveil` | `true` | `main_network` | `true` | `507` |  |
| `mireveil_n6` | Гнилая вода | `route_mireveil` | `frontier` | `mireveil_n5,mireveil_n7,westwild_n6,frostspine_n6` | `toxins,fungi,fish` | `toxic_water,slow_terrain` | `crosslink_candidate` | `hub_mireveil` | `false` |  | `true` | `508` |  |
| `mireveil_n7` | Заросли | `route_mireveil` | `frontier` | `mireveil_n6,mireveil_n8` | `fungi,toxins,glands` | `swamp_cover,ambush,slow_terrain` |  | `hub_mireveil` | `false` |  | `true` | `509` |  |
| `mireveil_n8` | Ивовый берег | `route_mireveil` | `frontier` | `mireveil_n7,mireveil_n9,mireveil_n8a1,westwild_n8,frostspine_n8` | `fish,reeds,fungi` | `water_edge,swamp_cover` | `crosslink_candidate` | `hub_mireveil` | `false` |  | `true` | `510` |  |
| `mireveil_n8a1` | Грибной берег | `route_mireveil` | `frontier` | `mireveil_n8,mireveil_n8a2` | `fungi,toxins,herbs` | `toxic_water,swamp_cover` | `side_pocket` | `hub_mireveil` | `false` |  | `true` | `511` |  |
| `mireveil_n8a2` | Ядовитый пруд | `route_mireveil` | `frontier` | `mireveil_n8a1` | `toxins,glands,fungi` | `toxic_water,elite_pressure,slow_terrain` | `side_pocket,dungeon_anchor_candidate` | `hub_mireveil` | `false` |  | `true` | `512` |  |
| `mireveil_n9` | Трясина | `route_mireveil` | `frontier` | `mireveil_n8,mireveil_n10,westwild_n9,frostspine_n9` | `toxins,glands,reeds` | `deep_swamp,slow_terrain,ambush` | `late_crosslink_candidate,core_war_candidate,dungeon_anchor_candidate` | `hub_mireveil` | `false` |  | `true` | `513` |  |
| `mireveil_n10` | Чёрная вода | `route_mireveil` | `frontier` | `mireveil_n9,ashen_n3b2b1` | `toxins,fish,glands` | `toxic_water,deep_swamp,elite_pressure` | `core_war_candidate,world_boss_candidate,guild_pressure_high` | `hub_mireveil` | `false` |  | `true` | `514` |  |

---

## 12. Return-on-death binding rules

### 12.1. Main rule
Каждый non-safe узел должен иметь явный `return_hub_id`.

### 12.2. Early entries from capital
Для первых entry-nodes допустимо:
- `westwild_n1` → `capital_city`
- `frostspine_n1` → `capital_city`
- `ashen_n1` → `capital_city`
- `sunscar_n1` → `capital_city`
- `mireveil_n1` → `capital_city`
- `south_coast_shore` → `capital_city`

Это помогает не делать самый старт слишком жёстким.

### 12.3. Regional binding after route commitment
После явного углубления в ветку return идёт в её regional safe hub:
- westwild-line → `hub_westwild`
- frostspine-line → `hub_frostspine`
- ashen-line → `hub_ashen_ruins`
- sunscar-line → `hub_sunscar`
- mireveil-line → `hub_mireveil`
- `old_mine_entrance` → `hub_frostspine`

---

## 13. Teleport metadata rules

### 13.1. `teleport_enabled = true`
Только для:
- `capital_city`
- `hub_westwild`
- `hub_frostspine`
- `hub_ashen_ruins`
- `hub_sunscar`
- `hub_mireveil`

### 13.2. `teleport_group = main_network`
Только для main safe network.

### 13.3. Explicit exclusions from phase 1 network
- `south_coast_shore`
- `old_mine_entrance`
- все frontier nodes
- все future guild castles
- все dungeon / raid anchors

---

## 14. Practical conclusions from this document

После этого документа уже считается зафиксированным:

1. Канонический node-level graph мира.
2. Exact security tiers для текущего overworld.
3. Exact neighbors для всех текущих location ids.
4. First cross-links и rare late diagonals.
5. Core/war handling через candidate-tags, а не через premature hard rollout.
6. Migration from current live slice.
7. Location metadata contract для следующей data-model фазы.
8. Teleport-facing metadata, совместимая с `TRAVEL_AND_TELEPORT_V1`.
9. Return-on-death binding model, совместимая с PvP/world foundation.

---

## 15. Next document

Следующий логичный документ после этого:

# `WORLD_DATA_MODEL_V1`

Он уже должен зафиксировать:
- структуру location records;
- discovered locations state;
- teleport unlock state;
- return-on-death storage model;
- required fields/tables for travel and teleport;
- минимальный implementation-facing UI/callback contract.
