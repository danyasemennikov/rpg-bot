# OPEN_WORLD_GAMEPLAY_ROLLOUT_PHASE1

## Базовое PvE + gathering наполнение всей открытой карты

> **Статус:** согласованная design-spec перед implementation plan.  
> **Не код. Не Codex prompt.**  
> Следующий шаг после этого документа — отдельно собрать implementation plan и только потом промт для Codex.

---

## 0. Важная предпосылка

Эта спецификация исходит из того, что последний world-PR с **route-based identity profiles** уже смержен и считается актуальным состоянием:

- у canonical route nodes есть `world_id`, `region_id`, `region_flavor_tags`;
- новые узлы читаются reward/gathering helper’ами;
- legacy-compatible overrides сохранены.

Если этот PR **ещё не смержен**, то перед implementation rollout он становится обязательным precondition. Сам дизайн Phase 1 от этого не меняется.

---

# 1. Назначение этапа

## 1.1. Главная цель

**Open World Gameplay Rollout Phase 1** нужен, чтобы превратить уже открытый canonical world graph из навигационной карты в **базово играбельный открытый мир**:

- каждая non-safe локация получает осмысленный PvE-layer;
- маршруты получают понятную боевую и ресурсную identity;
- gathering перестаёт быть только набором тегов и становится реальным gameplay surface;
- reward metadata начинает работать на всём мире, а не только на старых узлах.

## 1.2. Что Phase 1 должен дать игроку

После этапа игрок должен чувствовать:

1. **Карта живая** — почти в любой открытой локации есть осмысленное PvE.
2. **Маршруты разные** — лес, горы, руины, пустыня и болота отличаются не только названием.
3. **Угрозы растут по мере углубления** — от простой фауны к региональным монстрам, элитам и мини-боссовым точкам.
4. **Сбор ресурсов географичен** — за разными вещами реально идут в разные ветки.
5. **Open world поддерживает экономику**, но не ломает будущие роли данжей и apex-контента.

---

# 2. Явные non-goals

В Phase 1 **не входят**:

- teleport phase 1;
- dungeon runtime / dungeon rollout;
- world boss runtime;
- полноценная rare-spawn экономика;
- расширение crafting recipes;
- overhaul professions;
- инструменты профессий как отдельная полноценная система;
- отдельный underworld layer;
- полноценная coastal/marine ветка;
- новый foundation вместо существующих rails.

Особенно важно:  
**мы не превращаем этот этап в giant “world content everything pass”**. Он широкий по покрытию, но чёткий по задаче.

---

# 3. Опора на уже существующие rails

Этап работает поверх того, что уже есть.

## 3.1. Open-world PvE runtime

Используем существующие:

- anchored spawn instances;
- location-bound spawn instances;
- lifecycle `idle → forming → active → respawning`;
- solo/group live PvE runtime.

Никаких параллельных “случайных боёв по отдельной таблице” не вводим.

## 3.2. Reward foundation

Используем текущие:

- `reward_source_metadata`;
- `reward_policies`;
- `open_world_reward_pools`;
- helper’ы для regional / zone / tier identity.

Open world не должен стать бесформенным глобальным лут-пулом.

## 3.3. Gathering foundation

Используем существующие профессии:

- herbalism;
- mining;
- woodcutting;
- fishing;
- hunting.

Но их **дизайн-трактовка уточняется** в рамках этой спецификации.

---

# 4. Общая модель PvE rollout

## 4.1. Мир заселяется через content packages, а не хаотичными ручными исключениями

Для Phase 1 нужно мыслить не “какой точный моб в каждой строке”, а тремя слоями:

### 1. Encounter family
Тематический тип угрозы внутри маршрута:
- лесная фауна;
- гоблины;
- тролли;
- нежить;
- элементали;
- болотные ведьмы и т.д.

### 2. Spawn package
Конкретный open-world PvE package:
- normal;
- pressure-normal;
- elite;
- mini-boss candidate, если он зафиксирован как future layer.

### 3. Location encounter profile
То, как конкретная локация подключает 1–3 пакета.

---

## 4.2. Категории PvE-содержания

### A. Normal open-world encounters
Обязательный слой почти для всех non-safe locations.

Роль:
- baseline XP/gold;
- common creature loot;
- baseline gear chance;
- material 1 feed.

### B. Pressure encounters
Чуть более опасные обычные спавны:
- засады;
- более неприятный состав;
- сильнее тематический акцент.

Важно:  
**Pressure ≠ elite.**  
Он не должен автоматически переходить на material 2 economy.

### C. Elite encounters
Отдельный enhanced open-world слой.

Роль:
- более высокий риск;
- лучший reward floor;
- основной open-world источник material 2;
- ощутимый bridge между простым фармом и structured PvE.

### D. Rare spawns / mini-bosses
На уровне дизайна — **предусмотрены**, но **не являются обязательным массовым implementation-layer Phase 1**.

Исключение: некоторые точки фиксируются как **будущие local boss candidates**, например:
- Лич в Ashen;
- морской змей на Южном берегу.

---

# 5. Прогрессия угроз по глубине ветки

Общий принцип:

| Глубина | Ожидаемая структура угроз |
|---|---|
| `N1–N2` | простая фауна, ранние угрозы, мягкий старт |
| `N3–N5` | маршрутная identity уже читается, появляются более опасные существа |
| `N6–N8` | основной mid-route слой, первые яркие фэнтезийные угрозы, первые элитки |
| `N9–N10` | поздние сильные мобы, contested gameplay, более тяжёлые элитные точки |
| `N11+` | apex-edge open-world tone, самая сильная текущая часть ветки |

---

# 6. Gathering model Phase 1

## 6.1. Профессии трактуются по способу добычи

### Herbalism / фактически foraging
Сбор с поверхности земли и растений без тяжёлого инструмента:

- травы;
- грибы как ресурс;
- камыш;
- пустынные сухие растения;
- соль на солончаках;
- shoreline plants;
- болотные реагенты.

### Mining
Всё, что добывается киркой:

- камень;
- руда;
- уголь;
- кристаллы;
- редкие металлы;
- редкие минералы.

### Woodcutting
Крупная растительная масса:

- деревья;
- древесина;
- кора;
- смола;
- в Sunscar — крупные кактусы / сухие смолистые растения как допустимый flavor.

### Fishing
Водная добыча:

- рыба;
- береговые и болотные находки;
- раковины как side-find.

### Hunting
**Не location surface**, а **post-kill extraction layer**.

Игрок убивает подходящее существо и получает дополнительный profession payoff:
- шкуры;
- мясо;
- кости;
- рога;
- яд;
- железы;
- хитин;
- слизистые части;
- мембраны и т.п.

---

## 6.2. Важные ограничения gathering rollout

1. **Не каждая локация обязана иметь gathering surface.**
2. Обычно:
   - 1 основная surface;
   - иногда 2;
   - больше — только там, где это реально оправдано.
3. `resource_tags` — это **identity layer**, а не автоматическое обещание, что любой тег становится кнопкой сбора.
4. `relics`, `arcane_dust`, `holy_materials`, `undead_trophies` в Phase 1 остаются **reward/PvE identity**, а не обычным gathering.
5. `glands`, `venom`, животные токсины — в первую очередь через mobs + hunting, не через herbalism.

---

# 7. Утверждённые маршруты и их содержательная роль

---

# 7.1. Westwild

## Поля → лес → гоблинская глубина

### Утверждённые названия
- `westwild_n1` — **Пшеничные поля**
- `westwild_n2` — **Луга**
- `westwild_n3` — **Холмы**
- `westwild_n4` — **Лиственная роща**
- `westwild_n5` — **Перелесок**
- `hub_westwild` — **Элмор**
- `westwild_n6` — **Бор**
- `westwild_n7` — **Тёмный лес**
- `westwild_n8` — **Каменный ручей**
- `westwild_n9` — **Глухая чаща**
- `westwild_n10` — **Мшистый яр**
- `westwild_n11` — **Шепчущий бор**

### Роль ветки
Westwild — самый понятный и универсальный стартовый route:
- мягкий вход;
- много живой фауны;
- постепенный уход от полей к лесу;
- после хаба раскрывается гоблинская глубина;
- сильнейшая классическая hunting-ветка.

### Утверждённый моб-набор по силе
**заяц → ворон → кабан → волк → лесной паук → гоблин-разведчик → медведь → гоблин-охотник → гоблин-шаман → гоблин-вожак**

### Elite points
- `westwild_n7` — **Тёмный лес**
- `westwild_n8` — **Каменный ручей**
- `westwild_n10` — **Мшистый яр**
- `westwild_n11` — **Шепчущий бор**

### Gathering identity
- herbalism: поля, травы, грибы;
- woodcutting: роща, лес, бор;
- mining-lite: только `Каменный ручей`;
- hunting: очень сильный по всей ветке.

### Особая implementation note
Из-за того, что **Тёмный лес** перенесён глубже, на `westwild_n7`, будущий implementation должен явно решить судьбу legacy alias:

- сейчас в source docs `dark_forest -> westwild_n4`;
- новая player-facing логика естественнее требует `dark_forest -> westwild_n7`.

Рекомендация: **перенести alias на `westwild_n7`**.

---

# 7.2. Frostspine

## Каменные подступы → высоты → тролли

### Утверждённые названия
- `frostspine_n1` — **Каменная дорога**
- `frostspine_n2` — **Предгорья**
- `frostspine_n3` — **Перевал**
- `frostspine_n4` — **Склон**
- `frostspine_n5` — **Каменная гряда**
- `hub_frostspine` — **Карн**
- `frostspine_n6` — **Рудники**
- `frostspine_n7` — **Ледяной перевал**
- `frostspine_n8` — **Белый уступ**
- `frostspine_n9` — **Снежный склон**
- `frostspine_n10` — **Плато**

### Роль ветки
Frostspine — главный mining-route:
- прямой;
- более узкий и choke-heavy;
- камень, руда, уголь, кристаллы, редкие металлы;
- после хаба — более серьёзные горные угрозы;
- тролли закреплены именно здесь.

### Утверждённый моб-набор по силе
**горный заяц → скальный ящер → белый волк → пещерная летучая мышь → каменный жук → каменный голем → тролль → ледяной тролль → тролль-вожак**

### Elite points
- `frostspine_n6` — **Рудники**
- `frostspine_n8` — **Белый уступ**
- `frostspine_n10` — **Плато**

### Gathering identity
- mining почти по всей ветке;
- hunting — вторичен;
- другие gathering surfaces не являются core.

---

# 7.3. Ashen Ruins

## Руины, нежить и мини-боссы

### Утверждённые названия
- `ashen_n1` — **Старая дорога**
- `ashen_n2` — **Разбитый мост**
- `ashen_n3` — **Каменный круг**
- `ashen_n3a1` — **Каменный двор**
- `ashen_n3a2` — **Старый храм**
- `hub_ashen_ruins` — **Эмбер**
- `ashen_n3b1` — **Глухие руины**
- `ashen_n3b2` — **Реликтовый зал**
- `ashen_n3b2a1` — **Зал печатей**
- `ashen_n3b2b1` — **Скрытый ход**
- `ashen_n3c1` — **Забытый сад**
- `ashen_n3c2` — **Старый склеп**

### Роль ветки
Ashen — самая PvE-biased ветка:
- relic/undead identity;
- разветвлённая topology;
- отдельная hub-ветка;
- опасная основная линия;
- полезный side pocket;
- почти отсутствие gathering.

### Утверждённый моб-набор по силе
**зомби → скелет-воин → скелет-маг → призрак → скелет-страж → проклятый рыцарь → скелет-жрец → храмовый страж**

### Мини-боссы / крупные точки
- **Хранитель руин**
- **Лич**

Лич — **не обычный моб**, а мини-боссовый образ.

### Elite / boss points
- `ashen_n3b1` — mini-boss / strong anchor: **Хранитель руин**
- `ashen_n3b2` — elite: **проклятый рыцарь**
- `ashen_n3b2a1` — mini-boss: **Лич**
- `ashen_n3c2` — elite: **проклятый рыцарь**

### Gathering identity
- только `ashen_n3c1 / Забытый сад` получает полноценное собирательство;
- relics / holy / arcane / undead identity остаются reward/PvE logic, не обычным gathering.

---

# 7.4. Sunscar

## Сухие земли → оазис → пустыня → элементали

### Утверждённые названия
- `sunscar_n1` — **Пустошь**
- `sunscar_n2` — **Песчаные склоны**
- `sunscar_n3` — **Сухой овраг**
- `sunscar_n4` — **Каньон**
- `sunscar_n5` — **Проход**
- `sunscar_n5a1` — **Оазис**
- `hub_sunscar` — **Мираж**
- `sunscar_n6` — **Дюны**
- `sunscar_n7` — **Солончак**
- `sunscar_n8` — **Ущелье**
- `sunscar_n8a1` — **Брошенный лагерь**
- `sunscar_n8a2` — **Каменные столбы**
- `sunscar_n9` — **Сухое русло**
- `sunscar_n10` — **Соляная гряда**
- `sunscar_n11` — **Плато**

### Роль ветки
Sunscar — сухой, но разнообразный route:
- не один сплошной песок;
- каньоны, соль, оазис, сухие русла, гряды;
- после хаба начинается качественно новый слой — элементали;
- gathering строится вокруг соли, сухих реагентов, минералов и точечного cactus/resin woodcutting flavor.

### Утверждённый моб-набор по силе
**пустынный жук → ящерица → падальщик → скорпион → змея → крокодил → пустынный слон → огненный элементаль → земляной элементаль → воздушный элементаль**

### Elite points
- `sunscar_n6` — **Дюны**
- `sunscar_n8` — **Ущелье**
- `sunscar_n8a2` — **Каменные столбы**
- `sunscar_n10` — **Соляная гряда**
- `sunscar_n11` — **Плато**

### Gathering identity
- herbalism/foraging:
  - соль;
  - сухие реагенты;
  - пустынная флора;
- mining:
  - камень;
  - редкие минералы;
- fishing:
  - только `Оазис`;
- woodcutting:
  - точечно через крупные кактусы / сухие смолистые растения.

---

# 7.5. Mireveil

## Болота → ведьмы → токсичная глубина

### Утверждённые названия
- `mireveil_n1` — **Топкая дорога**
- `mireveil_n2` — **Низина**
- `mireveil_n3` — **Камыши**
- `mireveil_n4` — **Заводь**
- `mireveil_n5` — **Брод**
- `mireveil_n5a1` — **Мостки**
- `hub_mireveil` — **Вельм**
- `mireveil_n6` — **Мутная вода**
- `mireveil_n7` — **Заросли**
- `mireveil_n8` — **Протока**
- `mireveil_n8a1` — **Грибная топь**
- `mireveil_n8a2` — **Омут**
- `mireveil_n9` — **Трясина**
- `mireveil_n10` — **Чёрная вода**

### Роль ветки
Mireveil — влажная resource-dense ветка:
- herbalism;
- fishing;
- очень сильный hunting payoff;
- после хаба раскрываются утопленники, ведьмы, слизи и токсичные существа.

### Утверждённый моб-набор по силе
**болотная жаба → пиявка → водяная змея → болотный паук → гигантская пиявка → слизень → утопленник → болотная ведьма → ядовитая слизь → старая ведьма**

### Elite points
- `mireveil_n6` — **Мутная вода**
- `mireveil_n8` — **Протока**
- `mireveil_n8a2` — **Омут**
- `mireveil_n10` — **Чёрная вода**

### Gathering identity
- herbalism:
  - болотные растения;
  - грибы как ресурс;
  - токсичные травы;
- fishing:
  - регулярно, но не в каждой локации;
- hunting:
  - один из самых сильных payoff’ов во всём мире.

---

# 7.6. South Coast stub

### Название
- `south_coast_shore` — **Южный берег**

### Роль
Небольшой fishing-lite узел у столицы:
- берег;
- ранняя рыбалка;
- немного прибрежной живности.

### Мобы
**краб → чайка → береговая черепаха**

### Будущий boss candidate
- **морской змей** — локальный мини-босс / future coastal boss candidate, **не обычный моб Phase 1**.

### Gathering
- fishing;
- береговое собирательство;
- раковины как fishing-side find.

---

# 7.7. Old Mine stub

### Название
- `old_mine_entrance` — **Старая шахта**

### Роль
Ранний mining-stub:
- ощущение пустоты;
- немного жизни в заброшенной шахте;
- задел на будущий underworld gateway.

### Мобы
**пещерная крыса → летучая мышь**

### Gathering
- mining:
  - руда;
  - камень;
  - немного кристаллов.

---

# 8. Сводка elite placements

| Route | Elite / boss points |
|---|---|
| **Westwild** | `n7`, `n8`, `n10`, `n11` |
| **Frostspine** | `n6`, `n8`, `n10` |
| **Ashen** | `n3b1`, `n3b2`, `n3b2a1`, `n3c2` |
| **Sunscar** | `n6`, `n8`, `n8a2`, `n10`, `n11` |
| **Mireveil** | `n6`, `n8`, `n8a2`, `n10` |
| **South Coast** | нет обязательной элиты; морской змей = future boss candidate |
| **Old Mine** | нет |

---

# 9. Reward / economy rules для rollout

## 9.1. Normal mobs
Дают:
- baseline open-world economy;
- basic XP/gold;
- creature loot;
- baseline gear flow;
- material 1 logic.

## 9.2. Elite encounters
Дают:
- более высокий risk/reward;
- лучший gear floor;
- material 2 logic;
- более ценные creature parts / route-appropriate rewards.

## 9.3. Mini-boss / future boss candidates
На уровне этой спецификации:
- фиксируем роль;
- не обязуемся массово реализовывать rare boss system в первом PR;
- допускаем, что отдельные узлы могут получить boss candidates в более позднем open-world deepening pass.

---

# 10. Как это должно ложиться в data/content layer

В implementation-facing логике Phase 1 нужен не giant refactor мира, а понятное расширение поверх уже существующего world foundation.

На уровне концептов этап должен привести к появлению:

- reusable **encounter profiles**;
- reusable **gather profiles**;
- привязки этих профилей к canonical locations;
- route-aware reward identity;
- сохранения current world graph / discovery / travel rails.

---

# 11. Implementation scope будущего PR

## 11.1. Рекомендуемый scope

Я бы **делал это одним достаточно широким, но coherent PR**:

> **Open World Gameplay Rollout Phase 1: populate all canonical overworld locations with baseline PvE + gathering profiles and reward-aware content identity.**

Почему одним PR:
- карта уже открыта целиком;
- route identity pass уже готовит для этого основу;
- если наполнить только половину мира, получим неестественный промежуточный live state;
- механика rollout единая для всех веток.

## 11.2. Что точно входит
1. Контентные профили PvE для всех non-safe overworld nodes.
2. Gathering profiles для согласованных локаций.
3. Elite placement по утверждённой схеме.
4. Reward metadata integration для новых content packages.
5. Route-aware mob package assignment.
6. Обновлённые display names согласованных локаций.
7. Проверка starter hunt contracts Westwild после изменения наполнения.
8. Решение по `dark_forest` alias после переноса Тёмного леса глубже.

## 11.3. Что точно не входит
- teleport;
- world bosses runtime;
- dungeon content;
- полноценный boss system rollout;
- profession tools;
- crafting expansion;
- rare spawn scheduler;
- глубокая economy rebalance;
- coastal expansion;
- underworld expansion.

---

# 12. Дешёвые соседние хвосты, которые лучше закрыть сразу

## 12.1. `dark_forest` alias
Нужно решить и привести в порядок одновременно с name/content rollout.

**Рекомендация:**  
`dark_forest -> westwild_n7`

## 12.2. Starter contracts Westwild
Проверить, что:
- Астерские стартовые hunt contracts всё ещё указывают на реально существующие ранние Westwild targets;
- target mobs соответствуют новой мягкой ранней progression;
- canonical location matching не ломается после rename/content pass.

## 12.3. Stub semantics
Убедиться, что:
- Южный берег не начинает жить как полноценная coastal ветка;
- Старая шахта не получает слишком много PvE и не превращается в самостоятельный подземный мини-регион.

---

# 13. Done criteria этапа

Этап можно считать завершённым, если:

1. Все non-safe overworld locations имеют осмысленное PvE-содержимое.
2. Все маршруты читаются как разные регионы по мобам и ресурсам.
3. Угрозы ощутимо усиливаются по мере углубления в ветку.
4. Gathering реально работает поверх route identities, а не остаётся декоративным тегом.
5. Reward/open-world metadata корректно видит новые content surfaces.
6. Elite layer существует, но не поглощает обычный open-world loop.
7. Ashen остаётся PvE-biased, а не превращается в archaeology-route раньше времени.
8. South Coast и Old Mine остаются stub-ветками.
9. Teleport не затрагивается.
10. Future rare/boss hooks не путаются с обязательным scope первого implementation PR.

---

# 14. Итоговая формула Phase 1

> **Open World Gameplay Rollout Phase 1**  
> =  
> **полное наполнение canonical overworld**  
> + **route-aware PvE packages**  
> + **gathering surfaces по понятной profession-логике**  
> + **elite open-world layer**  
> + **reward metadata integration**  
> − **без телепорта**  
> − **без данжей**  
> − **без полноценного boss/rare pass**  
> − **без расширения crafting/profession foundations**.
