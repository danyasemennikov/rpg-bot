# WORLD_GRAPH_V1

## 1. Назначение документа

Этот документ переводит `WORLD_SKELETON_V1` в более прикладной **world graph draft**, пригодный как следующий шаг перед кодом.

Это всё ещё **design/technical spec**, а не implementation plan и не код.

Его задача:
- зафиксировать рабочие `region/route ids`;
- определить базовый порядок main nodes;
- определить расположение regional safe hubs;
- определить, где начинаются первые межветочные переходы;
- разложить по world graph security tiers;
- подготовить мир к последующей data-модели карты.

---

## 2. Главные design-правила WORLD_GRAPH_V1

1. Карта остаётся radial.
2. Все активные route-входы доступны из столицы.
3. Полные route’ы имеют ориентир 10–12 main nodes.
4. Safe hubs — ответвления, а не обязательные main-line stop points.
5. После safe hub есть только один `guarded` node.
6. First cross-links появляются примерно с 6-го main node.
7. Late-game mesh сгущается с 8–9-го node и усиливается к 10–12.
8. Побережье и шахта пока остаются stub-ветками с 1 доступной локацией.

---

## 3. Канонические route ids

## 3.1. Core node
- `capital_city`

## 3.2. Full routes
- `route_westwild` — степь → лес
- `route_frostspine` — горы
- `route_ashen_ruins` — руины
- `route_sunscar` — пустынная ветка
- `route_mireveil` — болота

## 3.3. Stub routes
- `route_south_coast_stub` — побережье
- `route_old_mine_stub` — шахта

---

## 4. Provisional macro layout

Это не точная карта в клетках, а логика соседства.

- **Север** — `route_frostspine`
- **Северо-восток** — `route_ashen_ruins`
- **Восток / юго-восток** — `route_sunscar`
- **Юг** — `route_south_coast_stub`
- **Юго-запад / запад** — `route_westwild`
- **Северо-запад / западнее гор** — `route_mireveil`
- `route_old_mine_stub` — ответвление от первого main node `route_frostspine`

### Route adjacency
Соседними считаются:
- `westwild` ↔ `mireveil`
- `mireveil` ↔ `frostspine`
- `frostspine` ↔ `ashen_ruins`
- `ashen_ruins` ↔ `sunscar`
- `sunscar` ↔ `westwild`

Это кольцевая логика соседства вокруг столицы, достаточная для первых midgame cross-links.

---

## 5. Main node band model

Для полной ветки используется такой рабочий band-каркас:

- `N1-N2` — low band
- `N3-N5` — early-mid band
- `N6-N8` — mid / deep-mid band
- `N9-N10` — late-mid / early-late band
- `N11-N12` — late / apex approach band

Не все route’ы обязаны использовать ровно 12 узлов. Для route’ов на 10–11 узлов band’ы схлопываются без ломания общей логики.

---

## 6. Standard structure for a full route

Базовый шаблон route:

- `N1` — выход из столицы / первая внешняя локация
- `N2` — ранняя dangerous локация
- `N3` — первая устойчивая branch identity
- `N4` — early-mid dangerous node
- `N5` — узел, от которого уходит региональный safe hub branch
- `N6` — первый node, где допустим соседний cross-link
- `N7` — mid progression node
- `N8` — более глубокий cross-link-capable node
- `N9` — late-mid contested node
- `N10` — early-late node
- `N11` — late node
- `N12` — apex approach node

Это **каркас**, а не обязательная жёсткая линейка.

---

## 7. Regional safe hubs

## 7.1. General rule
У каждой полной ветки есть один региональный safe hub.

Он:
- не лежит на магистрали;
- является коротким ответвлением примерно от `N5`;
- работает как anchor для regional return-on-death, logistics и nearby economy.

## 7.2. Canonical hub ids
- `hub_westwild`
- `hub_frostspine`
- `hub_ashen_ruins`
- `hub_sunscar`
- `hub_mireveil`

## 7.3. Stub routes
У stub-route’ов на текущем этапе собственного hub нет.

---

## 8. Stub routes in graph

## 8.1. South Coast
- доступна одна локация: `south_coast_shore`
- это отдельный radial exit из столицы
- сейчас route не продолжается дальше
- позже расширяется в coastal branch

## 8.2. Old Mine
- доступна одна локация: `old_mine_entrance`
- это side-branch от `route_frostspine:N1`
- сейчас route не продолжается глубже
- позже расширяется в underworld gateway line

---

## 9. Security tier mapping rules

## 9.1. Safe nodes
Всегда `safe`:
- `capital_city`
- все `hub_*`

## 9.2. Guarded nodes
У каждой полной ветки только один основной `guarded` segment сразу после safe hub.

Практически:
- segment между `hub_*` и примыкающим branch-return node — `guarded`
- при необходимости ближайший стартовый внешний node маршрута тоже может быть `guarded-lite` по альфе, но базово не цементируется сейчас

## 9.3. Frontier nodes
Основная масса main nodes в ветках — `frontier`

Это:
- главная масса open-world gameplay
- hunt/gather/resource gameplay
- основное пространство живого PvP-риска

## 9.4. Core / war nodes
В поздних band’ах часть узлов может получить `core/war` статус.

Рабочий стартовый принцип:
- кандидаты появляются с `N9+`
- особенно на nodes с сильным traffic, cross-links, rare resources, dungeon anchors и guild relevance

Точный список `core/war` nodes не фиксируется этим документом.

---

## 10. Cross-link rollout rules

## 10.1. First links
Первые межветочные переходы допустимы примерно с `N6`.

Это только links между **соседними** route’ами.

## 10.2. Expanded neighbor mesh
Начиная примерно с `N8-N9`, links между соседями становятся плотнее.

## 10.3. Diagonals
Редкие диагональные links допустимы только в late bands (`N10+`).

Их задача:
- уменьшать тупиковость мира;
- повышать PvP friction;
- создавать more dynamic late-game movement.

## 10.4. Constraint
Диагоналей должно быть мало.

Если их станет слишком много, world skeleton потеряет лучевую читаемость.

---

## 11. Route-specific role draft

## 11.1. route_westwild
**Shape:** наиболее ровная и понятная progression line.  
**Dominant resources:** hunt, organics, wood, herbs, mushrooms.  
**Low-tier role:** soft-default starter route.

## 11.2. route_frostspine
**Shape:** более узкая, вертикальная, choke-heavy.  
**Dominant resources:** ore, coal, stone, crystals, rare metals.  
**Special feature:** side access to `route_old_mine_stub`.

## 11.3. route_ashen_ruins
**Shape:** может быть чуть шире и ветвистее.  
**Dominant resources:** relics, holy/arcane materials, undead trophies.  
**Combat identity:** undead/relic-biased matchups.

## 11.4. route_sunscar
**Shape:** длиннее и разреженнее, с harsh-distance feel.  
**Dominant resources:** salt, ash, dry alchemy, resins, rare minerals.

## 11.5. route_mireveil
**Shape:** вязкая, неприятная, resource-dense.  
**Dominant resources:** toxins, fungi, reeds, fish, swamp alchemy, glands/venom.

---

## 12. Main implementation wave recommendation

`WORLD_GRAPH_V1` не задаёт giant rollout, но задаёт следующую разумную волну.

### Wave 1
- `capital_city`
- 5 route exits from capital
- `south_coast_shore`
- `old_mine_entrance`

### Wave 2
- first 3–4 nodes of each full route
- provisional route resource identity
- first dangerous open-world loops

### Wave 3
- `N5` branch-safe hubs for each full route
- security tier normalization around hubs
- return-on-death regional binding

### Wave 4
- first `N6+` neighbor cross-links
- initial midgame mesh

### Wave 5
- late-band nodes
- first diagonal late links
- `core/war` candidate nodes
- guild castle placement rules

Это не implementation plan с задачами по коду, а просто рекомендуемый порядок world graph rollout.

---

## 13. Что уже считать source of truth

1. Канонический центр карты — `capital_city`.
2. Полные route ids фиксируются как: `route_westwild`, `route_frostspine`, `route_ashen_ruins`, `route_sunscar`, `route_mireveil`.
3. Stub-route ids фиксируются как: `route_south_coast_stub`, `route_old_mine_stub`.
4. `route_old_mine_stub` — side-branch от `route_frostspine:N1`.
5. У каждой полной ветки есть `hub_*` как safe-hub ответвление от района `N5`.
6. Первые межветочные links начинаются не раньше `N6`.
7. Диагональные late links не появляются раньше `N10`.
8. Основной dangerous world в route bands считается `frontier`.
9. `core/war` концентрируется в high-tier mesh, а не в early-world routes.
10. Степь→лес — soft-default starter route, но не mandatory.

---

## 14. Что остаётся на следующую спецификацию

Следующий более узкий документ должен зафиксировать уже конкретнее:
- `location ids` всех main nodes;
- names/descriptions per node;
- which nodes are 10 vs 11 vs 12-length by route;
- exact cross-link pairs;
- exact safe hub branch node ids;
- node-level resource tags;
- node-level security tier tags;
- initial dungeon anchor placements;
- initial guild castle allowed flags;
- migration from old test geography.

Логичное имя следующего документа:

# `WORLD_LOCATION_MAP_V1`
