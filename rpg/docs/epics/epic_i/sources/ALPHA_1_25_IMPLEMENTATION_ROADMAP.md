# Alpha 1–25 / Enemy 1–50 — Epic Roadmap V2.2

Редакция **V2.2 — C25 / E50 / профессиональные Tier I–II (P1–30)**. 2026-10-14 UTC. Готовый дизайн для ревью; реализация не разрешена этим документом.

Основа — четыре документа V2.1 и ранее изученный снимок `main` `36368178541510d0d6794117ef17843722c52846`. Повторный аудит мира не выполнялся. Последнее [решение владельца в Issue #241](https://github.com/danyasemennikov/rpg-bot/issues/241#issuecomment-6172833671) и текущий запрос имеют приоритет над прежним текстом Issue, memory и предположениями V2.1. Игра не запущена: старые тестовые уровни, рецепты, snapshots и БД не требуют совместимости. Корректность новой системы, чистая инициализация и отсутствие повторных выплат обязательны.

**Утверждено:** восемь тиров по 15 уровней, P1–120; в альфе I=P1–15 и II=P16–30. Тир сразу даёт право изучить весь свой диапазон рецептов; знание приобретается отдельно. Нет ограничений по C на профессии, craft и квалификацию. Все 12 профессий и обе техники доступны. На P15 XP останавливается; экзамен у мастера: регистрация → две разные работы → контрольный образец → подтверждение. Результат: Tier II/P16/XP0, звание, запись в журнале и один рецепт II на выбор. На P30 нет экзамена III.

**Сохранено:** общий мир без автоскейлинга; альфа C1–25/E1–50, полный релиз C100/E100+; 67 локаций и 78 новых видов V2.1. Численные настройки XP/цен/угроз ниже — рекомендации, а не уже измеренный баланс.

## Изменения относительно V2.1

| V2.1 | V2.2 |
|---|---|
| P40, ранги на P6/16/26/36, D24/30/36 | Утверждённые Tier I–II/P1–30; один экзамен на P15; третьего тира в альфе нет |
| Рецепты открываются на отдельных P | 153 craft-рецепта распределены по I/II; внутри тира дополнительных P-gates нет |
| Соло-путь предполагал подготовленного C25 | Путь всех 12 профессий от C1 без убийств, Chapter I и роста C; гильдейская работа в Астере и NPC снабжение |
| U5/P26 и U6/P34 открывали очередные ресурсы | U1–3 относятся к I, U4–6 к II; U1/U4 дают весь доступ своего тира, старшие инструменты улучшают удобство |
| Сохранение старых P20, recognition, grandfathering, перенос истории | Удалено; проектирование новой схемы для чистой БД и корректной новой истории действий |
| 19 отдельных PR | Три крупных Epic: профессии; мир и экспедиции; цели и завершение альфы |

Реестр 78 врагов, их уровни/роли/placements и граф 67 локаций не перепроектированы. Изменены только профессиональные подписи наград, способы получения материалов и зависимости реализации. Предыдущая редакция сохранена локально в `work/v21_before_profession_tiers` как справочная копия, не как требование к совместимости игрового состояния.

## 1. Три крупных законченных Epic

Вместо 19 PR предлагаются **три**. Внутри каждого — логические commits и контрольные точки; они не превращаются автоматически в отдельные PR. Каждый Epic поставляет целиком работающий пользовательский цикл. Код не реализуется и Draft PR не создаются в текущем проектировании.

```mermaid
flowchart LR
  P[Epic I: профессии и самостоятельное ремесло] --> W[Epic II: общий мир и экспедиции]
  P --> A[Epic III: цели и завершение альфы]
  W --> A
```

Первым рекомендуется **Epic I**: основная продуктовая модель уже утверждена; он закрывает наиболее изменившуюся архитектуру, все 153 рецепта, новый безбоевой путь и чистую БД. Не ждать E50, navigation или live multiplayer, чтобы профессиональная игра стала полноценной. D4 и конкретные параметры проходят ревью контракта Epic I. Заморозка относится только к одобренному scope этого Epic, не к спорным значениям всего проекта.

## 2. Epic I — Profession Tiers & Self-sufficient Crafting

**Один будущий Draft PR:** `feat(professions): complete tier I II progression and independent crafting`.

### Точный scope

- Все 12 профессий: восемь 15-уровневых тиров в модели, активны I/II; P15 freeze, экзамен, P16/0, P30 cap. Полная замена прежних P40/рангов и intra-tier gates.
- Семь crafting professions: все 83 current и 70 new recipes, явные tiers, knowledge, outputs, полные BOM, доступ ко всем рецептам тира сразу; 69 I/84 II. Все 70 входят в этот Epic, а не откладываются за будущих mobs.
- Пять gathering professions:20 изучаемых инструкций, две техники без исключения, все 45 материалов с source tier. Гильдейские supplies/jobs/personal processing в Астере, loan U1/U4, hunting specimen без обязательного убийства.
- 30 tool recipes: U1–3/I, U4–6/II, новый BOM/commission/repair/access без hidden P и чужой профессии. U4 из I, U5/U6 из доступных U4 inputs.
- 12 отдельных экзаменов по общему workflow: две разные личные работы и третья sample operation, расход образца, атомарное звание/journal/выбранный рецепт II. Бесплатные retry; без RNG pass/fail и C-gate.
- Новые consumable/preparation effects всех 12 предложенных food/alchemy outputs: реальное исполнение в evaluator, stacking/replace/cleanse lifecycle. Иначе каталог 70 не считается рабочим.
- Новый profession state/schema, knowledge, escrow и receipts; чистая БД, seeds/fixtures, UI и RU/EN/ES, handbook с честными способами приобретения. Никаких тестовых grandfathering/migration/recognition.

### Зависимости и существующие системы

Стартует от исследованного main с последующим уточнением exact base в контракте. Не зависит от 78 новых мобов, J/S, Chapter I, gear-instance trade или второго игрока. Использует существующие crafting/gathering/hunting/tools/economy/gear/recipe knowledge/activity owners; узко добавляет guild work и exam state, не создаёт общий guild/achievement framework.

Основные файлы: profession_progression, gathering_progression, profession_schema, database, profession_recipes, profession_resources, profession_tools, crafting_runtime, gathering_runtime, hunting, economy_actions, recipe_knowledge, resource_handbook; для эффектов items_data/actor_snapshot/combat_identity/current item-use handlers; UI profession/recipe views и locales. Поле `item_tier` и реальные equip requirements не заменять профессиональным тиром.

### Ожидаемый игровой результат

Новый персонаж C1/gold0 может выбрать любую профессию, заработать знания и материалы личной работой, сдать свой экзамен и достичь P30 без единого убийства, обязательной группы и роста C. Может изучить любой II-рецепт уже на P16 и изготовить T20 по BOM, даже если не удовлетворяет требованиям ношения. Обе техники остаются доступны.

### Acceptance criteria

1. Все 12 fresh journeys проходят C1→P15→exam→P16/0→P30, без скрытого Chapter/visit/kill/другой профессии. Никакие earned XP за работу не перескакивают P15.
2. Точные 69/84 craft и 10/10 gathering knowledge; 153 рецепта и 45 inputs разрешаются, 70 новых outputs работают. Tier II entitlement не равен автоматическому знанию.
3. Купленный finished sample, чужой proof, один receipt на две практики и повторный confirm отвергаются. Mentor confirmation не создаёт двух рецептов или титулов.
4. Новый state корректен на clean DB init/restart; concurrent jobs, испорченный payload и failure между расходом/наградой не дают частичного результата. Старые DB layouts не тестируются как supported upgrade path.
5. Zero-gold/broken-tool путь восстановим loan-работой. NPC escrow не извлекается; wage и materials не выдаются одновременно. В рамках одной профессии дорогой рецепт не требует дополнительного P.

### Целевые проверки

Focused progression/knowledge/recipe access; 12 exam scenarios и replay/concurrency; fresh schema/bootstrap; guild work elapsed/ownership/receipt; все 153 BOM и tool/source DAG; negative craft/equip separation; targeted consumable evaluator tests; RU/EN/ES; естественные profession journeys на точном head. Проверки C1 — без admin money/material/XP. Формальные boundary fixtures и реальное прохождение отмечаются отдельно. Полный pytest не является текущей design-задачей; при реализации выбирать релевантные suites по changed owners.

### Sol → Astra

Astra передаёт одобренные таблицы 153/45/20/12, правило остановок, exact base и review checklist. Sol сначала представляет DDL/owner mapping и конечную схему доступа, затем внутри **того же Draft PR** реализует: schema/policy → knowledge/catalog → guild work/tools → exams → effects/UI → evidence. Это commits, не шесть PR. До открытия runnable slice запрещено показывать неработающий Tier II как готовый.

Astra независимо проверяет diff, повторяет критические C1/P15/claim paths и targeted tests на exact head. Исправления Sol остаются в этом Epic. После устранения замечаний — verdict с ограничениями, затем только владелец решает merge. Новое main-state описание отражает реально проверенные возможности, не все планы альфы.

## 3. Epic II — Authored World & C25 Expeditions

**Один будущий Draft PR:** `feat(world): complete shared E1 E50 ecology and C25 expeditions`.

### Точный scope

- Все 78 новых видов из V2.1:53 ordinary, 10 elites, 10 minibosses, 5 bosses; размещение на тех же 67locations, пять региональных ecology, существующие safe hubs/cross-links.
- Общая authored aggression без player-level suppression/scaling; readable preview, один pending threat, durable warning/deadline, честный обратный путь и protection после escape. Числа 30/45/120/20s требуют проверки, не являются скрытой сменой графа.
- Реальные A/V/H/C и bounded S/W/D, persisted intent, контроль effect stacking, фазы bosses, пять G-compositions. Никаких бесконечных summons или трёх бесплатных ходов гидры.
- Все мировые M placements/богатые источники из V2.1, дополнения текущих species и полезные переносы Drifter/WW mixed. Recipe rights уже работают из Epic I; мир даёт дополнительную скорость/материалы.
- Статические alpha reward bands, min(E, 25) budget, T≤20, один budget состава, personal eligibility, отсутствие essence без решения D2. Четыре C25 как целевой boss party по D3, реальная проверка join/UI/orders/rewards.
- Перепроверка baseline hunts/projects и маршрутов на новом персонаже при более опасном мире; изменение их catalog references без переноса старых историй. Локализация всех существ/механик/угроз.

### Зависимости и системы

После Epic I: материалы, effects и T20 acquisitions уже реальные. До интеграции нужны решения D2/D3 и согласованные threat rules. Основные owners: locations/mobs/enemy_profiles/location_threats/travel_runtime/player_activity/pve_live/combat_identity/combat_orders/field_catalog/progression rewards/current loot settlement, resource sources, world/battle views/locales. Не переписывать generic combat engine, не вводить raid lobby или world scaling.

### Ожидаемый игровой результат

Одинаковый мир для всех: ближние дороги понятны, глубокие узлы действительно опасны, подготовленная группа C25 осваивает E46–50. Разведчик видит угрозу и может разумно отступить. Профессия C1 не зависит от посещения этих узлов; NPC снабжение Epic I не обесценивает богатую полевую добычу.

### Acceptance criteria

1. Все 78 identities/67 узлов соответствуют матрице; no actor-level phasing. Из 54 current +78 получается 132 definitions; 129 размещены, 3 unplaced не выдаются за активный контент.
2. Safe hubs не атакуют; при одинаковых условиях C1/C25/C100 получают одинаковые roster/stats/aggro rules. First warning и backedge работают при задержке/restart, reconnect не обнуляет агрессию, gathering не становится неуязвимостью.
3. Минимум G2/G5 E50 воспроизводимо проходимы двумя разными составами подготовленных C25 в заявленном T20 budget; нет требования C40/epic/+9. HP/defense/damage проверяются через реальные snapshots и текущий evaluator, не только через label50.
4. Группа из четырёх реальных клиентов: formation/join/targets/timeout/escape/restart/settlement и personal reward проходят. При отсутствии аккаунтов/устройств соответствующая evidence строка BLOCKED, не фиктивный PASS.
5. E50 не выдаёт T50 или double payout boss+adds; один spawn profile применяется один раз. Все обязательные профессии и базовая C25 progression обходятся без boss/group victory.

### Целевые проверки и передача

Scoped world graph/placements, threat/travel/activity races, evaluator/intent, source/reward policies, новые encounter receipts, targeted balance simulations с exact snapshots и несколькими seeds; natural entry/retreat каждого региона; real Telegram group/mobile отдельно. Численный G2 budget из V2.1 — стартовая гипотеза, не готовая evidence.

Astra передаёт неизменённый реестр 78/67, согласованные threat/party/reward rules и acceptance. Sol в одном Draft PR ведёт commits runtime угроз/AI → пять региональных наборов → G/rewards → локализация/evidence. Это внутренние подэтапы, не пять региональных PR. Astra независимо проверяет runtime и выборочные сцепленные пары локаций, затем все boss acceptance gates на точном head. Владелец мерджит после review; наличие красивого бестиария не закрывает multiplayer gate.

## 4. Epic III — Regional Goals & Alpha Completion

**Один будущий Draft PR:** `feat(alpha): regional goals progression economy and complete journeys`.

### Точный scope

- Пять личных J-проектов и пять S-заказов, производственные/боевые альтернативы, личные proofs, finite T15 reward choices, корректные XP/gold/time budgets. Они остаются приключением, а не пропуском в профессию.
- Character progression1–25, выбранная D1 политика XP на C25 во всех writers, ясный UI конца alpha без ложного финала. Guild job/exam receipts не дают character XP через сторонние observers.
- Полная связность 10 weapon families/T20, 7 существующих regional projects/11 hunts, новых цели/крафт/добыча/боссы; обычное NPC снабжение региональных хабов. Ни marketplace, ни новый item trade не требуется.
- Измерение и настройка общей экономики: оплачиваемый безопасный труд, field reward/yield, knowledge/commission/repair, prep consumables, enhancementD2; устранение конкретных тупиков, а не добавление новых подсистем.
- Журнал перспектив C26–100, E100+ и профессиональных III–VIII; без активного экзамена III и без фиктивных переходов. Полная точная evidence и обновление current-state/docs.

### Зависимости и системы

После Epic I+II, с D1/D2. Owners: quest_board/regional_catalog/regional_objectives/standing contracts, progression_rewards, economy_actions, field vendors/gear advancement, journal/recipe/world UI/locales. Изменения combat/source tuning проходят тот же authority, что предыдущие Epic, без параллельной системы наград.

### Ожидаемый игровой результат

Новый игрок находит осмысленные цели на каждом C-этапе и достигает C25/T20 без обязательной группы; профессиональный игрок независимо проходит P30. После caps остаются знания, сборки, ремесленные заказы и экспедиции. Безопасная гильдейская работа поддерживает самостоятельность, но не делает поле и реальные награды бессмысленными.

### Acceptance criteria и целевые проверки

Три естественных C1→25 билда, все 10 weapon families в acquisition/combat checks; все 12 profession journeys из Epic I повторяются только по затронутым изменениям и рискам; J/S finite/repeat claims, no bought proof XP, цены/доходы/ремонт/ноль gold; capC25 и P15/P30 не смешиваются. Проверки reward writers и региональных objective kinds — focused. Фактические time/XP/gold/deaths/MP/yield измеряются на exact head; цели 37–55h/5–9h не объявлять PASS без данных. Отдельно regression действующих recovery/settlement flows, куда добавлены новые факты.

Sol передаёт в том же Draft PR законченные цели, UI, настройки и evidence с raw scenario references. Astra независимо воспроизводит ключевые маршруты, проверяет изменения цены/источников/XP и статусы STATIC/SIMULATED/REAL_TELEGRAM/BLOCKED. Не пересчитывать уже выполненные тесты старого head как зелёные для нового. Если обнаружен дефект текущего Epic — исправить внутри него; unrelated defect не поглощать без причины. Только владелец решает merge.

## 5. Ledger и границы интеграции

| Epic | Craft recipes | Gathering knowledge | Новые materials | Новые mobs | Игровая завершённость |
|---|---:|---:|---:|---:|---|
| I | Переработка 83 +70 новых =153 | 20 | 15, всего 45 | 0 | Полные профессии I–II и ремесло безбоевого C1 |
| II | Использует 153 | Использует 20 | Полевые размещения тех же 15 | 78 | Общий мир E1–50 и 5 групповых вершин |
| III | Настраивает существующий каталог | Не добавляет новую квоту | Настройка экономики | Не меняет квоту | 5J+5S, связная C25 альфа и evidence |

Никакого отдельного PR только для повышения cap, отдельно для экзамена без inputs или для каталога без работающего effect. Если Epic становится тяжёлым для review, Sol предоставляет карту commits/owners и демонстрационные сценарии; автоматического дробления на 19 PR нет. Новый split возможен только при конкретном техническом препятствии и согласовании владельца.

Clean DB — рабочая основа всех Epic. Новые данные обязаны быть атомарными и восстанавливаться после restart; старые test-state tables не требуют upgrade path. Дизайн не разрешает сейчас удалять файлы/БД. Issue #240 recovery остаётся самостоятельной уже принятой задачей: этот план не отменяет её и не захватывает чужой PR. Issue #239 broad navigation остаётся после технического/контентного завершения и multiplayer acceptance; узкие подсказки/предупреждения этих Epic не равны запуску всего 239.

## 6. Рекомендация первого шага и открытые решения

Начинать с **Epic I** после ревью этого пакета: он основан на уже утверждённой системе тиров, убирает зависимости ремесла от боя и сразу даёт законченный игровой цикл. Контракт должен включать exact153/BOM, 20 руководств, 12 экзаменов, 45 источников, новый DDL и экономику D4. Нет необходимости предварительно утверждать каждый boss stat или делать отдельный docs-only Epic.

## Оставшиеся продуктовые решения

| ID | Действительно открытый выбор | Рекомендация / что зависит |
|---|---|---|
| D1 | Поведение character XP на C25: hard cap без банка либо ограниченный reserve | Hard cap без будущей конвертации, при сохранении gold/items; reserve потребует отдельной экономики. Это не вопрос профессионального P15/P30 — там остановка уже утверждена |
| D2 | Enhancement alpha: новые улучшения до +9 либо новый источник essence | +9 и T20; не вводить обязательный E50 reagent. Источник +10…+12 — отдельное продуктовое расширение |
| D3 | Целевой размер организованной группы для E46–50 и политика присоединения | Четыре C25, без масштабирования статов; подтвердить допустимость дополнительных участников и распределение reward budget |
| D4 | Роль безопасного гильдейского труда в экономике | Повторяемая оплачиваемая работа и медленная обработка материалов в Астере, без daily lock. Она гарантирует независимость от боя, но медленнее добычи в мире; не превращать её в бесплатную раздачу |

Конкретные 12 экзаменов, XP/цены/тайминги и budgets переданы как готовые рекомендации для ревью; их настройка не требует заново выбирать уже утверждённую модель тиров. Условия агрессии и предупреждений V2.1 также проходят ревью перед Epic II. Не переоткрывать P30/P120, сам экзамен, остановку XP, свободу профессий и техник или необходимость совместимости со старыми тестовыми данными.

## 7. Что проверено в этом проектировании

Согласованы четыре документа, ledger153/20/45/12, tier boundaries и dependencies; сохранены все строки бестиария и локаций V2.1. Перенос старых тестовых данных исключён. Static checks не являются проверкой новой игровой реализации. Код репозитория, игровая БД, PR и полный pytest не затрагивались.
