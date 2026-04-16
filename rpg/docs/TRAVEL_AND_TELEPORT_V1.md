# TRAVEL_AND_TELEPORT_V1

## 1. Назначение документа

Этот документ фиксирует **travel / fast travel / teleport rules** для мира из `WORLD_SKELETON_V1`, `WORLD_GRAPH_V1` и `WORLD_LOCATION_MAP_V1`.

Его задача:
- добавить игроку удобную логистику;
- не убить ценность маршрутов, PvP, региональных хабов и опасного мира;
- дать реалистичную Telegram-friendly модель интерфейса;
- подготовить следующий шаг к implementation-facing технической спецификации.

Это **design/technical spec**, а не код.

---

## 2. Главные принципы телепорта

### 2.1. Телепорт не должен ломать опасность мира
Мир вне хабов должен оставаться рискованным, а смерть должна возвращать игрока в региональный safe hub. Телепорт не должен превращаться в кнопку мгновенного извлечения добычи из frontier/core world. fileciteturn19file4 fileciteturn19file5

### 2.2. Телепорт — это логистика, а не замена путешествия
Основной способ открывать мир — обычный travel по graph.
Телепорт нужен для:
- сокращения рутинных возвратов;
- связности мира после открытия новых регионов;
- удобства торговли, профессий и встречи с друзьями;
- уменьшения бессмысленного долгого бэктрекинга.

### 2.3. Телепорт должен работать через named locations
Игрок должен видеть не abstract id, а понятные названия мест. Это хорошо сочетается с уже существующим location/i18n каркасом проекта. fileciteturn19file17

### 2.4. Telegram-friendly UX важнее симуляции
Игрок не должен вводить координаты или длинные команды руками.
Телепорт в phase 1 лучше реализовывать как:
- кнопку в интерфейсе локации;
- список доступных точек;
- понятную цену;
- понятную блокировку, если телепорт сейчас недоступен.

---

## 3. Phase 1 teleport model

## 3.1. Куда можно телепортироваться
В phase 1 игрок может телепортироваться **только между safe nodes**.

То есть valid destinations:
- `capital_city`
- `hub_westwild`
- `hub_frostspine`
- `hub_ashen_ruins`
- `hub_sunscar`
- `hub_mireveil`

Не разрешено телепортироваться прямо в:
- frontier nodes;
- core/war nodes;
- `south_coast_shore`;
- `old_mine_entrance`;
- guild castles;
- dungeon/raid anchors.

### Почему так
Это сохраняет:
- ценность маршрутов;
- риск вывоза полевой добычи;
- смысл PvP pressure на дорогах;
- важность реального открытия регионов. Такой подход лучше всего совместим с PvP-first foundation. fileciteturn19file4 fileciteturn19file13

---

## 4. Как телепорт открывается

## 4.1. Базовое правило unlock
Точка телепорта открывается **только после того, как игрок физически посетил эту safe location хотя бы один раз**.

### По умолчанию открыто сразу
- `capital_city`

### Открывается через открытие мира
- `hub_westwild`
- `hub_frostspine`
- `hub_ashen_ruins`
- `hub_sunscar`
- `hub_mireveil`

## 4.2. Что это даёт
Игрок не может в первый день просто перескочить полкарты.
Сначала он реально доходит до региона, а уже потом получает логистическое удобство.

---

## 5. Откуда можно использовать телепорт

## 5.1. Phase 1 rule
Телепорт можно использовать **только находясь в safe node**.

То есть phase 1 entry points:
- `capital_city`
- любой `hub_*`

## 5.2. Почему не из поля
Если разрешить телепорт из frontier/core world:
- игроки начнут выносить ресурсы без риска;
- travel pressure ослабнет;
- PvP-мир станет мягче, чем задуман foundation’ом. Это противоречило бы общей risk-логике мира. fileciteturn19file4

## 5.3. Что оставить на future phase
Позже допустимы отдельные механики вроде:
- дорогого recall-scroll;
- guild teleport beacon;
- underworld/coast relay;
- rare emergency extraction skill/item.

Но не в phase 1.

---

## 6. Когда телепорт запрещён

Телепорт недоступен, если:
- игрок в бою;
- игрок находится вне safe node;
- игрок под combat tag / active PvP pursuit state;
- игрок не открыл destination;
- destination временно недоступен по системным причинам.

Дополнительно допустимо потом запретить телепорт при некоторых special states:
- active contraband / war cargo;
- siege state;
- castle lockdown.

Но это не часть phase 1.

---

## 7. Цена телепорта

## 7.1. Рабочий стартовый дефолт
Чтобы не усложнять, в phase 1 берём простую модель:

- `capital_city` ↔ любой открытый региональный hub = **20 gold**
- один региональный hub ↔ другой региональный hub = **35 gold**

## 7.2. Почему именно просто
Сейчас важнее:
- читаемость;
- удобство;
- не убить маршруты;
- быстро дойти до рабочей реализации.

Сложная формула расстояния позже допустима, но на старте она не нужна.

## 7.3. Что цена должна делать
Цена должна быть:
- заметной в early-mid;
- не душной в mid-late;
- не настолько низкой, чтобы телепорт стал “всегда лучше пешего пути”.

---

## 8. Travel layers мира после введения телепорта

После ввода teleports travel делится на три слоя:

### 8.1. Exploration travel
Первичное открытие мира:
- всегда пешком / обычным travel;
- нужно, чтобы открыть hubs и маршруты.

### 8.2. Logistics travel
После открытия hub’ов:
- столица ↔ хабы;
- хаб ↔ хаб;
- быстрая логистика между регионами.

### 8.3. Field travel
Всё, что происходит между safe nodes:
- по-прежнему через обычную карту;
- по-прежнему с риском;
- по-прежнему с PvP friction;
- по-прежнему важно для gather/loot/world presence.

Это лучший компромисс между удобством и risk-based world design. fileciteturn19file6 fileciteturn19file7

---

## 9. Как телепорт сочетается с stub-ветками

## 9.1. Побережье
`south_coast_shore` пока **не входит** в teleport network.

Почему:
- это не safe hub;
- ветка ещё не раскрыта;
- пока это скорее early utility node, чем региональная логистическая точка.

Позже, когда coastal branch разовьётся, у неё появится свой hub и он войдёт в сеть.

## 9.2. Шахта
`old_mine_entrance` тоже **не входит** в teleport network phase 1.

Почему:
- это frontier side node;
- позже там должен открыться отдельный подземный слой;
- safe teleport туда сейчас преждевременен.

---

## 10. Как телепорт сочетается с guild castles

## 10.1. Phase 1
Guild castles **не являются teleport destinations**.

## 10.2. Почему
Если сразу разрешить телепорты в castles:
- castles начнут конкурировать с regional safe hubs слишком рано;
- логистика карты станет грязнее;
- баланс public/private castle utility будет трудно держать.

## 10.3. Future phase
Позже можно добавить отдельный guild travel layer:
- teleport только для членов гильдии;
- public access castle, если владелец открыл его как service point;
- fee / tax / cooldown.

Но это не phase 1.

---

## 11. UI/UX contract for Telegram

## 11.1. Где появляется кнопка
Кнопка `Телепорт` должна появляться только в safe nodes:
- в столице;
- в региональных hubs.

## 11.2. Что открывает игрок
После нажатия игрок видит:
- список открытых destinations;
- цену для каждой точки;
- пометку текущей локации;
- заблокированные точки можно не показывать или показывать как “не открыто”.

## 11.3. Как лучше подавать destinations
Формат списка:
- название локации;
- краткая пометка региона;
- цена.

Пример логики, не как final UI text:
- Астерион — текущая локация
- Рябиновая Слобода — 20g
- Каменностраж — 20g
- Пристанище Пепла — 20g

## 11.4. Что не надо делать
Не надо требовать:
- ручной ввод id;
- текстовые команды с длинными именами;
- координаты;
- запоминание route ids игроком.

Telegram-friendly путь — кнопки и callback’и.

---

## 12. Implementation-facing model (без кода)

Минимально телепорт требует таких концептов:

### 12.1. Location metadata
У safe nodes должны быть признаки вроде:
- `is_safe_hub`
- `teleport_enabled`
- `teleport_group = main_network`

### 12.2. Player unlock state
Игроку нужно хранить, какие teleport destinations он уже открыл.

Это может быть:
- отдельная таблица discovered safe hubs;
- или discovered locations с фильтрацией по teleport-enabled nodes.

### 12.3. UI routing
В location UI нужен отдельный flow:
- открыть teleport menu;
- выбрать destination;
- подтвердить цену;
- переместить игрока.

### 12.4. i18n
Все display names и UI strings должны идти через существующий i18n-layer проекта. Это естественно ложится на текущую структуру `locations.py` + `locales/locations_*`. fileciteturn19file17

---

## 13. Что уже считать source of truth

1. Каждая main location должна иметь уникальное имя.
2. Каждая location должна иметь стабильный `location_id`.
3. Phase 1 teleport работает только между safe nodes.
4. Телепорт не работает из frontier/core world.
5. Телепорт unlock’ается только после физического посещения destination.
6. `capital_city` открыта для телепорта по умолчанию.
7. Региональные `hub_*` открываются как teleport destinations после первого визита.
8. `south_coast_shore` и `old_mine_entrance` не входят в teleport network phase 1.
9. Guild castles не являются teleport destinations в phase 1.
10. Телепорт в phase 1 использует простую gold-cost модель: 20g capital↔hub, 35g hub↔hub.
11. Telegram UX должен строиться через кнопки и список destinations, а не через ручной ввод.

---

## 14. Что оставить на следующую фазу

Следующий слой детализации может уже отдельно решать:
- cooldown на телепорт или его отсутствие;
- special recall consumables;
- public guild-castle travel;
- coast/underworld teleport network;
- late-game relay nodes;
- siege / war teleport restrictions;
- contraband / cargo anti-extract rules;
- advanced distance-based pricing.

---

## 15. Следующий шаг после этого документа

После `WORLD_LOCATION_MAP_V1` и `TRAVEL_AND_TELEPORT_V1` следующий практический документ уже должен быть почти code-facing:

# `WORLD_DATA_MODEL_V1`

Там уже надо фиксировать:
- обязательные поля у location records;
- required tags for travel/teleport/security/resource identity;
- discovered-location / teleport-unlock state;
- return-on-death regional binding model;
- минимальный callback/UI contract для travel и teleport.

