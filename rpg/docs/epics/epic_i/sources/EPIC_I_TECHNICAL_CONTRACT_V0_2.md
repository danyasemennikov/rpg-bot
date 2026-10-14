# Epic I — Profession Tiers & Self-sufficient Crafting

**Адресная редакция технического контракта v0.2 — на повторное ревью Astra High**  
**Дата:** 2026-10-14 UTC  
**Репозиторий:** `danyasemennikov/rpg-bot`  
**Baseline `main`:** `36368178541510d0d6794117ef17843722c52846` (тот же exact SHA, независимо подтверждён Astra при ревью v0.1; перед кодированием перепроверить).  
**Статус:** `CONTRACT_REREVIEW_REQUIRED`; **не** `CONTRACT_READY`, **не** `FROZEN`, не разрешение на реализацию/PR/merge.  
**Объект замечаний:** `EPIC_I_ASTRA_TECHNICAL_REVIEW.md`, `CONTRACT_FIX_REQUIRED`, пункты F1–F6.

## 0. Sources, authority и статус решений

1. Решения владельца в [Issue #241](https://github.com/danyasemennikov/rpg-bot/issues/241) (включая [profession mastery / equip](https://github.com/danyasemennikov/rpg-bot/issues/241#issuecomment-6177452595)); четыре приложенных документа **V2.2** — источники содержательной модели, а не подтверждение запуска/runtime.
2. Отчёт Astra `EPIC_I_ASTRA_TECHNICAL_REVIEW.md` — точечная owner/caller карта и F1–F6; корректирует технические неопределённости v0.1.
3. Действующий код на exact SHA и `rpg/AGENTS.md`, `CLAUDE.md`, `GAME_FOUNDATION.md` с приоритетом более позднего решения владельца над конфликтующим старым текстом.

**Утверждённая продуктовая основа (НЕ обсуждать заново):** 12 профессий (5 gathering +7 crafting), восемь тиров ×15 P1–120; в альфе только I=P1–15 и II=P16–30; право изучить все рецепты тира сразу, фактическое знание отдельно; C не ограничивает profession XP/learn/craft/qualification; обе техники неэксклюзивны; экзамен на P15 (регистрация, две **разные** личные практики, третья операция контрольного образца, подтверждение мастера) → P16/XP0, звание, журнал, **один** выбранный II knowledge; P15/P30 XP halt без банка; старые тестовые данные не сохраняются; один большой Epic PR. При equip отдельно действуют C и постоянные атрибуты по требованиям предмета. Принцип бонусов внутри тира и дополнительных guild jobs утверждён.

**Только предложено, требует owner sign-off до freeze:** M1 — milestone levels/batch/timing/24 jobs; M2 — числовые equip minima и base-only policy; D4/M3 — конкретная безопасная guild economy, цены, XP/timing, refund и связанные параметры V2.2. Документ задаёт для этих пунктов **однозначный кандидат реализации** для проверки, но их запись здесь сама по себе не утверждает значения. F1–F5 — технические варианты, выбранные для review, не самостоятельное разрешение Sol импровизировать.

**Объём V2.2:** 153 craft-рецепта (69 I/84 II), **из них** 30 рецептов инструментов U1–U6; ещё 20 gathering manuals (10 I/10 II), 45 материалов (30+15), 12 экзаменов, T20 для 10 weapon families. V2.2 §§7–9 и Gap §5 остаются содержательным каталогом и BOM; не переписывать 153 строки без конкретной ошибки. D1 character XP C25, D2 enhancement, D3 group E50 и общий мир — не блокеры Epic I.

## 1. Progression, права и XP

- Внутренние 8 tier-диапазонов существуют как data-model, но runtime альфы активирует **только** I и II. Регистрация профессии — отдельный committed факт; auto-created DB row **не** означает регистрацию или использованные бесплатные vouchers.
- `can_learn = profession_registered ∧ profession_tier≥knowledge_tier ∧ !known ∧ valid_payment_or_voucher`. RL (recipe label) не сравнивать с числом P. Знания другой профессии, C, боевые objectives и A/B-эксклюзивы не проверять.
- `can_perform = registered ∧ owned_profession_tier≥recipe_or_source_tier ∧ required_knowledge_known ∧ authorized_inputs_for_mode ∧ valid_activity_and_authority`. **НЕТ** общего `own_inputs`: личная работа, paid job и экзамен имеют разные разрешённые источники (§4).
- Craft допустим даже если созданный gear нельзя надеть; equip не проверяет P. Профессии добычи не требуют владеть профессией изготовления их инструмента (NPC commission/loan).
- Нормативные проектные XP-пороги V2.2 Profession §4: `100+20*(P−1)` для P1..14, `300+30*(P−16)` для P16..29, суммарно 3220+6930=10150; результат каждого действия хранит `attempted/applied/discarded`, без overflow/bank. На P15 XP=0 до успешного экзамена, на P30 XP=0 навсегда в альфе. I-work после Tier II использует пониженную award V2.2; исходные training ceilings и minP-gates удаляются **во всех consumers**, а не переименовываются.
- Профессиональная операция, основанная на `guild_work` или `profession_exam`, не вызывает character XP и adventure/Chapter/region observers. `personal_adventure_craft` сохраняет право закрывать валидные adventure objectives. `crafting_runtime.py:362–371` и другие event dispatchers фильтруют **по provenance до observer**, не после выплаты. Результат не зависит от UI callback/token.

## 2. M1 — развитие внутри тиров (точная предложенная модель)

| P | Доступ/удобство для всех 12 | Craft (7) | Gathering (5) |
|---|---|---|---|
| 1 | Право изучать любые I знания; начальные vouchers V2.2 | Один личный craft за действие | I операции, guild loan U1 |
| **5** | Дополнительный тематический **paid guild job I**, не повышающий wage, XP/action и не блокирующий базовую работу | Две тематические операции внутри 4-stage job | Два типа материала внутри 15-stage job |
| **10** | Первый convenience milestone | Личный all-or-nothing batch **до 2** gear/consumable экземпляров | Personal material processing на **114000ms** вместо 120000 (–5%), не paid job/field |
| **15** | XP halt, guild examination | Рецепты I работают и без повышения | I материалы доступны |
| **16** | После экзамена целиком eligible Tier II | Весь Tier II, включая T20 и U6 | Все II источники через руководство II + U4 |
| **20** | Дополнительный тематический **paid guild job II**, wage базового тира | Две категории II recipes | Два вида II materials |
| **25** | Второй convenience milestone | Личный batch **до 4** вместо 2 | Personal processing на **108000ms** (–10%, вместо –5%, не суммировать) |
| **30** | XP halt, экзамена III нет | Продолжает производство | Продолжает добычу |

**Семантика:** P5/P20 открывают **новые заказы**, не право изучить рецепты. P10/P25 улучшают UX/время, не quality, stat budget, yield за действие, wage или XP за операцию. Batch не параллельный автоматический крафт. Длительности — предложение для M1: paid job всегда 120000ms, полевая добыча остаётся на своей текущей схеме 120s/RNG/wear. Повышение P или смена конфигурации **не ускоряет уже принятый заказ** (§4.3).

### 2.1. F1 — один атомарный личный craft batch (выбранный вариант)

**Решение для v0.2 review: all-or-nothing, без partial completion.** Внутри `personal` mode только для `gear` и `consumable` outputs; личный `tool` recipe — **строго count=1**, отдельная подтверждённая установка. Paid guild jobs, exam A/B/sample, NPC commission, gathering не используют этот personal batch.

1. Сервер выдаёт стабильный `batch_id` и immutable payload `{player,profession,recipe_id,count,knowledge/catalog/policy version, destination=inventory}` с server-signed или server-persisted fingerprint. Один token/intent не может сменить рецепт, count, mode, owner или destination. Повтор другого UI token **того же batch_id** возвращает тот же receipt; новый самостоятельный request допускается как новая операция, но не обязан автоматически дедуплицироваться по одинаковому содержимому.
2. При `BEGIN IMMEDIATE` заново сверить owner, recipe known, tier, amount и N×BOM и квоту **по P на старте транзакции**, затем выполнить `N` детерминированных child craft operations в **одной writer transaction**. Каждый child имеет стабильный `(batch_id,index)`/operation ID; outputs, resources, profession XP, expected observers и receipts коммитятся **одновременно одним commit**. Ни один child НЕ делает отдельный commit. Точный порядок XP/уровней такой же, как при N обычных последовательных действиях: на P15/P30 overflow discard, но остальные outputs пакета создаются.
3. Любая ошибка child, insufficient ingredients, stale state, constraint/revision mismatch, observer failure ⇒ rollback **всего** пакета. Нет частичного списания или частично изготовленных предметов. После commit потеря Telegram-ответа означает replay сохранённого результата, не повторное выполнение.
4. `crafting_runtime.py` должен выделить `execute_craft_operation(conn, ...)` без собственного `commit/close`; пользовательская единичная команда сама открывает transaction и вызывает тот же executor. `profession_tools.craft_tool` не вызывается внутри batch: tool crafting/installation и exam tool escrow идут отдельными writer modes (§4.2). Existing own-connection APIs без рефакторинга нельзя просто обернуть внешней transaction.
5. Preview показывает **полную** стоимость, N outputs, лимит и правило `ничего либо всё`. Version/revision recheck в commit; rejected batch не теряет материалы и не частично пишет XP. Child receipts используются для XP/proof/audit; **это не N отдельных транзакций**.

**Приёмка:** child2 из 2 / child4 из 4 падает; crash до commit; response loss после; duplicate token/replay; изменённый count; cap P14→15 внутри batch; результат и XP как N обычных операций при том же начальном состоянии; tool N>1 и job/exam batch отклоняются.

### 2.2. Milestone guild jobs — 24 точных определения (M1 proposal)

Общий шаблон: ID из таблицы стабилен; `unlock_P` проверяется по собственной профессии; job I допустим после P5 и для Tier II без дополнительного коэффициента, job II после P20; **не** новая лицензия на рецепты. Для maker-job требуется знать обе рецептурные записи (при их повторе знания не дублируются); NPC выдает inputs, а результат уходит в `paid_job escrow`, никакой установки tools. Plan maker: четыре последовательных stage по 30000ms, два craft attempts recipe A и два recipe B; уникальный `(job_id, stage_index)`. Для gathering: 15 stage по 8000ms, **первые 8** операций материала A и **последние 7** материала B; разные `source_operation_id`, всё в guild safe area. Задания могут использовать уже изученные игроком знания без ограничений C.

| Profession | P5 ID, Tier I `A → B` | P20 ID, Tier II `A → B` |
|---|---|---|
| woodcutting | `gj_wc_05`: `wood_common` → `wood_dark` | `gj_wc_20`: `a25_binding_resin` → `a25_heartwood` |
| mining | `gj_mn_05`: `iron_ore` → `stone_chunk` | `gj_mn_20`: `a25_layered_ore` → `a25_frost_quartz` |
| herbalism | `gj_hb_05`: `herb_common` → `reed_bundle` | `gj_hb_20`: `a25_relic_lichen` → `a25_bitterroot` |
| fishing | `gj_fs_05`: `shore_fish` → `marsh_fish` | `gj_fs_20`: `a25_oil_fish` → `a25_reed_perch` |
| hunting | `gj_ht_05`: `boar_meat` → `wolf_pelt` | `gj_ht_20`: `a25_resilient_sinew` → `a25_pale_silk` |
| blacksmith | `gj_bs_05`: `pe_sword_1h_01` → `pxe_tool_mining_1` | `gj_bs_20`: `pe_sword_1h_18` → `pe_shield_18` |
| arcane_engineer | `gj_ae_05`: `pe_wand_01` → `pxe_tool_fishing_1` | `gj_ae_20`: `pe_wand_18` → `pe_focus_18` |
| heavy_armor | `gj_ha_05`: `pe_heavy_chest_01` → `a25_H_01` | `gj_ha_20`: `pe_heavy_chest_18` → `a25_H_03` |
| medium_armor | `gj_ma_05`: `trail_vest` → `a25_M_01` | `gj_ma_20`: `pe_medium_chest_18` → `a25_M_03` |
| light_armor | `gj_la_05`: `pe_light_chest_01` → `a25_L_01` | `gj_la_20`: `pe_light_chest_18` → `a25_L_03` |
| alchemy | `gj_al_05`: `field_tonic` → `field_mana` | `gj_al_20`: `pe_alchemy_health_18` → `a25_clear_sight` |
| cooking | `gj_ck_05`: `trail_ration` → `pe_cooking_shore_01` | `gj_ck_20`: `pe_cooking_deep_18` → `a25_hunters_stew` |

В каждой из 24 программ две категории operations, но maker-output ссылается на один из **153** craft IDs, gathering — на один из **45** material IDs; stage provenance включает `source_operation_id`, recipe/material, owner, tier, policy. `a25_` aliases разрешаются через явно зафиксированный каталог V2.2, не сохраняются как «M01» в runtime. P5/P20 job **не** даёт повышенную оплату за сложность: Tier I=5g/120s, II=10g/120s, каждый по одному завершению, не 4 wage. Открытие job не является обещанием бесплатного знания — при нехватке knowledge показывать источник и цену обучения, не выдавать предмет за игрока.


## 3. F2/F3 + M2 — единый контракт требований экипировки

**Утверждённый принцип:** craft и профессии полностью независимы от C; каждый equip/retention требует C и атрибуты **самого предмета**. Значения M2 ниже остаются **кандидатом** на owner sign-off.

### 3.1. Canonical requirements resolver

Единственный `resolve_effective_equip_requirements(base_template, instance_tier?, family, policy_version)` возвращает `{req_level, req_strength,req_agility,req_intuition,req_wisdom, policy_version}`. У instance использовать **фактический** `item_tier` записи, не RL, P, рецепт или число в ID; effective field requirements не записывать в общий базовый `field_*` template, иначе T1 получил бы requirements T20. Формулы для кандидатной альфы:

- `req_level = max(template.req_level, integer_instance_T)` для tiered instances; legacy без instance — `template.req_level`. Для T1/5/10/15/20 числа соответствуют C1/C5/C10/C15/C20. Для нестандартных **положительных** T внутри 1..20 level=T; attr band — ближайший нижний известный tier (1,5,10,15,20).
- `req_attribute[stat] = max(template.req_stat, family_requirement[stat](T))`; правило только для известных `weapon/armor/offhand` families, остальные item types хранят existing explicit template minima. У ring/amulet дополнительный family minimum =0, но item-level requirement всё равно применяется.
- Действующие и будущие T>20 **не должны тихо считаться T20**: для tiered item `req_level≥T` сохраняется, family attribute policy для T>20 должна быть явно дополнена перед его реальным введением. Неподдерживаемое новое сочетание field family/T в alpha-creation/equip fail-closed с диагностикой; не вводить глобальный предел E50/C25/генерации мира этим локальным правилом.
- **Attribute source:** только persisted base `players.level` и постоянно распределённые `players.strength/agility/intuition/wisdom` после подтверждения allocation; **не** current equipment, кандидат, заменяемый slot, food/preparation, temporary buff, title и profession. Так чужой item bonus не становится requirement-bootstrap, а снятие любого предмета не инвалидирует другие requirements.
- Equip predicate `player.level≥req_level ∧ player.base_stats[each]≥req_each` плюс корректный slot/ownership/activity/revision. Он применяется также для **retention** уже надетого instance при tier change/attr reset/revalidation. `gear_instances`/`gear_progression`/`build_progression`/UI используют **один** resolver, не копии табличных проверок.

### 3.2. Предложение M2: числовые пороги

| Tier band T | 1 | 5 | 10 | 15 | 20 |
|---|---:|---:|---:|---:|---:|
| Минимум C | 1 | 5 | 10 | 15 | 20 |
| `W(T)` primary weapon attr | 1 | 4 | 7 | 10 | 13 |
| `A(T)` armor/offhand attr | 1 | 3 | 5 | 7 | 9 |

| Family | Дополнительное к explicit template требование |
|---|---|
| `sword_1h`, `sword_2h`, `axe_2h` | strength≥W(T) |
| `daggers`, `bow` | agility≥W(T) |
| `magic_staff`, `wand` | intuition≥W(T) |
| `holy_staff`, `holy_rod`, `tome` | wisdom≥W(T) |
| heavy armor (все слоты и варианты) | strength≥A(T) |
| medium armor (все слоты и варианты) | agility≥A(T) |
| light armor (все слоты и варианты) | wisdom≥A(T) |
| `shield` / `focus` / `censer` | strength / intuition / wisdom соответственно ≥A(T) |
| rings / amulets | family minimum=0, template minima сохраняются |

Класс/профессия/броневой тип игрока не вводят запрета. Нет ненужного req_vitality/req_luck. Числа могут быть изменены решением владельца и проверкой гибридных билдов **до freeze**, но функция, source attributes и absence of equip bonus-bootstrap не должны оставаться неоднозначными. В частности current base requirements сильнее предложенного band сохраняются по `max`.

### 3.3. F2: фактическая owner/writer matrix и atomic retention

| Фактический маршрут на SHA 3636817 | Обязательная унификация |
|---|---|
| `handlers/inventory.py` normal instance equip и ring1/ring2 → `game/gear_progression.py:384–414` | canonical resolver + committed equip check |
| inventory compare-equip → `gear_progression.apply_gear_intent` | та же проверка, preview не привилегирован |
| legacy inventory equip → `gear_progression.py:284–318` | template requirements, текущая base allocation, без обхода |
| starter auto-equip `starter_kit.py` → `gear_instances.py:591–625` | общий predicate, reject/skip invalid без потери стартового предмета |
| `gear_instances.py:553–568,628–637` low-level setters | internal-only или принудительная проверка внутри той же writer transaction; не утверждать наличие live caller без evidence |
| `handlers/location.py` → `gear_progression.py:472–493` tier advancement надетого instance | **recheck retention** после выбранного T; auto-unequip при недостатке C/attributes, в **той же** transaction |
| `tier_advancement.py:122–189` дополнительный tier writer | no bypass; применяется тот же next-tier effective req/retention, даже если live caller не найден |
| `build_progression.py:813–950` распределение/сброс stats | prospective base allocation; снять все переставшие соответствовать вещи **атомарно** с reset, корректно обновить revisions |
| inventory tooltips/compare/gear profile/equip feedback RU/EN/ES | отображать **effective instance requirements**, причину отклонения и warning будущего auto-unequip |

**Tier upgrade/advance:** preview учитывает новый T, re-read `player.base allocation`, bound instance `revision`, будущий cost и expected slot. Если после улучшения предмет становится недоступен (пример C1 T1→T5), это **не запрет изготовить/улучшить**: commit в одной transaction списывает стоимость, повышает T, снимает из `equipped_slot`/canonical equipment slot, обновляет revisions, сохраняет вещь у владельца. При cancel preview — ни upgrade, ни расхода. Stale preview/race — refuse без partial effects. Все combat snapshots получают валидную экипировку только после retention check; при обнаружении invalid old equipped state нормализовать **до** использования для расчётов. Clean DB не требует legacy migration, но нужна согласованная ре-валидация до использования уже сохранённой экипировки при restart/config change.

**Stat reset:** вычислить новое permanently allocated `base` **до** commit, определить предметы, которые не пройдут resolver, показать список auto-unequip; reset и unequip в единой transaction; не использовать скидку от предметных stats, временных эффектов или несуществующего loadout. Если reset отклонён, никакая вещь/баланс/points не меняются. При повышении base stats дальнейшие экипировки не обязаны сниматься.

**Equip QA:** C1/P16 T20 craft success, equip blocked; C20 + требуемый base succeeds; каждый primary under-minimum fails; buffs/other gear/current item bonus не помогают; ring slots, compare, legacy, starter и low-level writer не обходят check; tier upgrade equipped T1→T5 снимает; reset и restart stable; UI соответствует commit, без phantom loadout.


## 4. F4/F5 + D4/M3 — происхождение операций, гильдия и планировщик

### 4.1. Четыре раздельных режима, escrow и outcome

| Mode, server-owned enum | Inputs authority | Output destination | XP/proof | Extra limits |
|---|---|---|---|---|
| `personal` | owned inventory materials; one verified receipt per craft | gear instance / consumable inventory; **tool только install personal slot** | собственный profession XP; обычные adventure observers разрешены при соответствующем source | личный batch gear/consumable; tool только count1 |
| `paid_job` | NPC inputs, зарезервированные за конкретным job ID и stage | **NPC escrow**, не inventory/tool slot | только личный profession XP после stage, **нет** character XP, exam proof или adventure observers | wage по одному job claim, 15 gathering или 4 maker stages, 120s |
| `personal_processing` | purchased NPC lot за 2V/unit, job-scoped escrow; личная авторизованная операция | только финальный материал в inventory после полного набора stages | личный gathering XP per committed stage; нет wage/character XP | 15 stages, 120/114/108s; 3/2/1 material units для S/R/C |
| `profession_exam` | job/exam-owned loan inputs или проверенные личные купленные ингредиенты, которые server помечает в exam instance | proof-bound **exam escrow**, лично изготовленный tool не устанавливается | отдельные A/B/sample receipts; XP на P15 applied=0; **нет** wage/character XP/adventure observers | только три single operations, sample отдельно от A/B, подтверждение у мастера |
| `npc_commission` *(сервис, не craft XP mode)* | собственные материалы или их покупка у NPC | одна подтверждённая установка tool с revision | 0 profession XP, 0 exam proof | все 5 gathering tools U1..6, no maker profession requirement |

Слово «четыре» обозначает четыре **режима личной профессиональной операции**; `npc_commission` — независимый сервис установки, не пятый вариант получения crafting proof. Только сервер выбирает mode, owner, input/source и destination; callback не может подменить их. Один `operation_id` / `(job_id,stage_index)` отмечен idempotent внутри DB, не только callback.

**Tool specifics:** `personal` tool craft устанавливает **один** инструмент в соответствующий gathering slot после отдельного confirmation и revision check; нельзя иметь count2/4 как batch output. Для `paid_job` и `profession_exam` кузнечный mining U1 или инженерный fishing U1 — **output escrow record** `(tool_family,tier,qty,owner=NPC_or_exam)`, не установка и не износ личного инструмента. Не проверять, выучил ли кузнец mining или обладает ли он U6 mining для экзамена. Никакая loan-оснастка не появляется в inventory или field slot. Инструмент commission/repair/install обновляет реальный tool slot отдельной атомарной транзакцией; acquisition не выдаёт maker proof.

**Exam proof:** у зарегистрированного exam ID два различных A/B **operation/source identities** и третье независимое `operation_id` для sample. Sample **может использовать тот же recipe ID**, что и A — кузнец и бронники так спроектированы в V2.2 §7; нельзя требовать 3 различных recipe IDs. Receipt `{player,profession,exam_id,criterion,recipe_or_source,mode,operation_id,output_escrow_ref,policy_version}` фиксируется только после committed personal action. Bought finished item, чужой job, чужой receipt, NPC-commission outcome и покупка материалов без обработки не доказывают экзамен. Купленные лично входы для изготовления допустимы. Sample consumes/moves one escrow item once; final mentor confirm атомарно завершает экзамен P16/XP0/title/journal/choice II. `UNIQUE(player,profession,target_tier)` защищает и уже выполненный exam; выбор только из **неизвестных** II своей профессии. Zero-cost reattempt не создаёт новый reward identity.

### 4.2. Guild activity authority и сохранение времени

Новые `paid_job` и `personal_processing` регистрируются через общий `player_activity` owner вместе с **travel, field gathering, combat**. **Одновременно ровно одна активная длительная activity** на одного персонажа; во время её выполнения personal instant craft/другой guild/exam operation/новая field activity запрещены, кроме её собственного `complete_stage`/`claim`/`cancel` и авторизованных recovery actions. Открыть экран или посмотреть catalog можно. Start операции из старых owners должны уважать занятый activity slot; одной проверки `unique guild_job` недостаточно.

**At accept (single transaction):** создать immutable `{job_id,player,profession,mode,tier,required_knowledge,stage_plan, source/item IDs, result_qty, quote/cost, wage/yield/XP policy_version, mastery_snapshot, stage_duration_ms, total_duration_ms, accepted_ms, next_stage_earliest_ms, active_activity_revision, escrow ownership}`. Для maker paid job план — 4x30000ms; gather paid job — 15x8000ms; personal processing — 15x8000ms (P<10), 15x7600ms (P10–24), 15x7200ms (P25+). Права на II material/processing проверяются **при accept**. New P после accept/config/restart не переписывает текущий plan. Stage payload и owner/expected revision проверяются в transaction с записью StageReceipt.

**Ожидание и действия:** stage1 доступен не ранее `accept+stage_duration`; каждый следующий доступен не ранее `max(now_committed, preceding_stage_deadline)+stage_duration`, где `now_committed` — время **фактического** подтверждения предыдущего stage. Это исключает мгновенный «догон» всех 15 стадий после 120s отсутствия. Timer/`due_at` сами по себе не начисляют XP, золото или inventory; на каждом этапе требуется валидное личное действие. Late response может задержать, но не уменьшить duration. `stage_index` фиксируется один раз. После последней операции статус `ready_to_claim`, но activity slot до idempotent claim не освобождается; claim выдаёт wage **или** final inventory material, закрывает escrow/lock. Не выдавать ни pay, ни materials ранее claim. Restart/reconnect восстанавливают именно saved plan/next deadline; startup **не отменяет** guild job по образцу текущего field gathering.

**Cancel/refund (фиксированная предложенная policy M3):** cancel — явное server-validated действие, не disconnect. До первого committed stage personal processing — полный refund paid gold и закрытие escrow; после первого stage — **никакого refund**, completed stage XP/proof не откатывать, незавершённые inputs в escrow списать; incomplete personal processing output никогда не поступает в inventory. Paid job на cancel: **0 wage** и 0 inventory output, все NPC lot/outputs закрываются, но already committed personal profession XP не откатывается. После `ready_to_claim` отмена запрещена: доступен только claim. До confirm cancel UI показывает цену и необратимость; replay cancel/claim не создаёт второй refund/wage. При starter failed/no stage gold0 сохраняется возможность принять новый loan paid job.

**Field boundary:** старые field gathering sessions 120s/RNG/износ и их schema CHECK относятся к полю и не меняются mastery-guild длительностью. Для новой guild schema не наследовать `ends_ms=started_ms+120000`; stage timeline versioned. PvE/recovery/teleport следует существующим activity конфликтам, не убирая AC1 `/unstuck` и не добавляя auto-teleport.

### 4.3. D4/M3: однозначный кандидат экономики, но НЕ утверждённый баланс

Предложенная стартовая модель V2.2: без daily lock; оплата за полностью завершённый paid job **5g Tier I / 10g Tier II за 120s**, если P20 job — тот же wage своего тира. Один job = одна wage независимо от четырёх craft operations. **Personal processing** — предоплата `2×V×output_quantity`, гарантированно 3/2/1 единицы S/R/C за завершённую session, output в inventory, wage=0. **Готовый материал** у NPC `3×V` без XP/proof. I/II knowledge 8g/60g, бесплатные учебные vouchers и один бесплатный II choice при exam; starter/loan доступ на C1/gold0. Maker paid jobs требуют learned recipes, но все inputs предоставляет NPC, outputs NPC-owned. Sell output <= 60% reference value всех входов по V2.2. Tool commissions `5×U` + BOM/докупка по quote V2.2; экзамен бесплатный, inputs можно брать loan и retry без платы.

Это **намеренный повторяемый источник золота**, который потребует измерения gold/hour, craft XP/hour, pricing, buy→sell, P10/P25 throughput и отношения к field добыче. Отсутствие daily lock поддерживает полную самостоятельную P30 при C1; никаких дополнительных premium payout за milestones. Принцип безопасных guild jobs принят, **конкретные D4 и M3 параметры и refund policy ждут owner sign-off**. В случае изменения чисел Sol обязан использовать versioned snapshots для уже принятых jobs, а не менять их условия задним числом.


## 5. Fresh SQLite schema и обязательная owner matrix

**Никакой миграции прежних тестовых аккаунтов/DB**; новая игра корректно создаётся на чистой изолированной БД и выдерживает `init→ensure→restart`. Не трогать чужие локальные DB без явного owner решения. Старые P1..20, `training_ceiling` и U1..4 CHECK/schema validators не копировать в новый state. Sol в commit1 **показывает точный DDL и writer map** на тот же Epic branch; никакой новой отдельной PR.

| Authority | Реальные known owners / обязательные вызовы |
|---|---|
| Init/bootstrap | `database.py:96–107,345–357,394–410`; `game/alpha_schema.py:14–42`; `game/profession_schema.py:21–26,133,142–186,217–220`; `game/player_experience_schema.py:34–60,141–154,183–190` |
| XP / level / knowledge | `profession_progression.py`, `gathering_progression.py`, `profession_schema.py`, `recipe_knowledge.py`, `database.py` и все внешние SQL writers; единый source of truth P/XP/registration |
| Craft & tools | `profession_recipes.py:21–26`, `crafting_runtime.py:217–241,362–371,372–430`, `profession_tools.py:125–208`; validators U1–6, U1 durability90 **вместо старого cap60**, U4 240, U6 360; loan отдельно |
| Gather & activity | `gathering_runtime.py:153–157,253–290`, `hunting.py`, `profession_resources.py`, `player_activity.py:34–58`, `player_experience_schema.py` session validators; field vs guild разные durable owners |
| Guild | узкий новый owner без player-guild/auction; job/exam/escrow/receipts, `economy_actions.py`, observers | 
| Equip/effects | `gear_progression.py`, `tier_advancement.py`, `gear_instances.py`, `build_progression.py`, `starter_kit.py`, `handlers/inventory.py`, `handlers/location.py`, `field_catalog.py`, `items_data.py`, actor snapshot + item-use/evaluator |
| UI | profession/knowledge/recipe/equip handlers; RU/EN/ES locales; journal, mentor, quote, batch, retry/cancel/refund, effective requirements |

**Логические таблицы/constraints (Sol может встроить в существующий authority вместо дублирования):**

- `profession_state` PK(player,profession), `P` 1..30, `tier` согласован с P, `xp` и revision, отдельный `registered_at`; единственная writable P/XP authority или детерминированное read-only view для legacy reader.
- `profession_knowledge` UNIQUE(player,knowledge), provenance; registration vouchers UNIQUE(player,profession,voucher_slot), durable redeemed state.
- `profession_exam` UNIQUE(player,profession,target_tier), state A/B/sample/confirm; `profession_exam_proof` UNIQUE(exam,criterion), UNIQUE(operation_id), owner+mode+source; sample escrow ref; final selected reward.
- `guild_job` PK(job_id), immutable policy/mastery/stage plan/durations/quotes; partial UNIQUE(player) WHERE active/ready-to-claim; `guild_stage_receipt` UNIQUE(job_id,stage_index) with immutable `operation_id` and owner/time; `guild_escrow` inputs/outputs by job/exam and clear owner/destination, not ordinary inventory.
- `profession_operation_receipt` UNIQUE(operation_id), `attempted/applied/discarded`, item/gold delta and `origin_mode`. Personal batch UNIQUE(batch_id) + child UNIQUE(batch_id,index), fingerprint and one committed status. Interoperable with current receipts or one canonical replacement; no duplicate writers.
- `player_activity` enforces the cross-system single-long-activity constraint in one transaction across guild/travel/gather/combat; stage/claim/cancel revision-safe. Active guild job not merely a UI flag.
- Equipped instance tier/slot and character base allocation changes share transaction, rerun canonical requirements resolver; stale preview rejected; gear revisions incremented.

`profession_recipes.RecipeOutputSpec` / `player_experience_schema` / tool capacity and startup seed `ensure` **all** updated together; verify U1=90 vs former `60*tier` and added U5/U6. `row exists` != `registered`. Explicit query/tests find SQL writes bypassing canonical owner. Repeated clean `ensure` must not grant second recipes/vouchers/tool.

## 6. Non-negotiable runtime invariants

1. Craft batch all-or-nothing **one DB commit**, no child external transaction; intent idempotency independent of callbacks, no partial XP/outputs.
2. `mode` and `destination` are server-owned in immutable operation; NPC escrow never sellable, never a personal inventory sample; no tool-slot replacement from job/exam proof.
3. Exam proof personal action occurs **after registration**; A and B different operation identity, sample third operation (recipe may equal A); one mentor reward; P15/P30 applied XP halt.
4. `guild_work`/`profession_exam` never issue character XP/Chapter/adventure credits; ordinary personal adventure craft still may. No ghost observer transaction after a rollback.
5. Stage duration/plan/quote/mastery snapshot immutable after acceptance; no offline auto-XP; restart != cancel. Only one player long activity across guild/travel/field/combat; ordinary personal craft blocked while active.
6. Cancel before stage1 refunds personal processing price once; after stage1 no refund; paid job no wage unless complete; stage XP already earned persists; `ready_to_claim` claim-only.
7. Equip C/attributes derive from effective requirements and permanent base player stats; every writer, advance and reset uses it. Auto-unequip from advance/reset committed with tier/points/cost, no broken snapshot.
8. C1/gold0 in **all 12** professions reaches P30 with character XP=0 without killing, mandatory second profession, group, auction, Chapter or admin injections.
9. Full data closure: 153 craft (including 30 tools), 20 manuals, 45 materials, U1–6, 12 new consumable effects; source→knowledge→craft→use end-to-end; no phantom outputs.
10. RU/EN/ES reflect actual costs, milestones, exam state, effective equipment requirements and cancellation consequences; no future Tier III button.

## 7. One large Epic PR — internal commit sequence (not separate PRs)

1. `schema+owners`: full writer/DDL owner map, new clean DB init/bootstrap/ensure, P15/P30 XP policy, activity owner integration.
2. `catalog+knowledge`: exact 153/20/45/30, tool U1–6 checks, vouchers, recipe rights, material sources and commission.
3. `atomic craft`: conn-owned operation executor, all-or-nothing personal batch, separated output modes, tool placement/escrow.
4. `guild scheduler`: 4/15 stage plans, immutable time snapshots, personal processing, cancel/restart/claim, 24 jobs and paid economy.
5. `exams`: 12 registered exams, two personal practices + third sample, provenance, P16/0 confirm and one choice.
6. `equip authority`: effective requirements/base-only, every writer, advancement auto-unequip, reset and UI.
7. `effects+UX`: 12 consumable effects, one food/prep slot, real evaluator, locales RU/EN/ES, integration with existing services.
8. `QA+review`: targeted tests, clean C1 12 journeys, receipts/races, report evidence and Astra independent exact SHA review; corrections stay in same Draft PR.

**Только владелец утверждает контракт/freeze, выдаёт Sol разрешение на код, а затем merge.** Не запускать второй бот, не изменять прод SQLite, не требовать старой migration. Не объявлять `main` stable production.

## 8. Acceptance / targeted test matrix (после реализации, сейчас НЕ выполнена)

| Gate | Минимальные требования |
|---|---|
| CATALOG | 153 unique recipes=69 I+84 II **включая** 30 tool recipes; 20 manuals=10/10; 45 materials; все 10 weapon families T15/T20, BOM нет dangling; 12 new effects evaluator |
| PROGRESSION | P14→15 discarded overflow, P15 production no XP, exam→16/0, I-action on II low award, P29→30, no XP bank; progression perks не закрывают рецепты |
| BATCH/F1 | 1 vs N equivalence, child2/4 failure rollback, crash-before/response-after commit, replay token/fingerprint tamper, cap P15, no tool N>1, no exam/paid mode batch |
| EQUIP/F2/F3 | normal instance/ring/compare/legacy/starter/low-level setters, tier writers, attr reset, snapshot restart; equipped T1→T5 at C1 auto-unequip; independent hybrid stat allocations; UI matches authority |
| MODES/F4 | personal material craft; paid tool in exam/job escrow without personal gathering tool change; no bought finished proof; commission no XP/proof; 12 exams correct three operations including repeated recipe with new receipt; concurrent reward choice |
| GUILD/F5 | 120s paid; personal 120/114/108s and stage deadlines; delayed callbacks no catch-up, current P/config change after accept; cancel full/no refund boundary, ready_to_claim no cancel; restart, wage exactly once; cross-guild/travel/field/combat lock |
| INIT | fresh DB init→ensure→restart→ensure; no duplicated vouchers or XP writers; U1 durability90, U6 support, tool schema validators and no old strict P20 gate |
| ECONOMY | C1/gold0 recoverable through paid loan jobs; buy3V/processing2V, vendor sell cap, cost/budget no free-profit loop, no wage plus material; timed faucet measured before balance PASS |
| JOURNEY | all 12 professions C1/gold0 P1→15→exam→P16→P30, **character XP=0**, no admin materials/gold, no high-E kills; natural measured time, tools, resources and choices |
| UI/EFFECTS | RU/EN/ES guild jobs/exams/perks/equip errors; 12 actual food/alchemy effects, stacking, expiry/escape/settlement, no free healing or changed PvP allowlist |

Sol first verifies actual relevant test file paths, uses `python -m pytest -q <verified relevant paths>`, targeted unit/integration + synthetic natural journeys; real Telegram acceptance separately; do not invent file paths or pretend full suite ran. Evidence labels `STATIC`, `UNIT/INTEGRATION`, `SIMULATED`, `REAL_TELEGRAM`, `BLOCKED`, linked to exact HEAD. Four V2.2 do not get modified as part of this docs-only correction; only explicit deviations, if approved, should be reflected there before implementation.

## 9. Owner product choices still open (sign-off package)

| Code | What owner must approve for v0.2 freeze | Current **proposal**, not approved |
|---|---|---|
| **M1** | P5/P10/P20/P25 numbers, batch2/4, 24 precise jobs and personal-processing speed | §2 and §2.2, 120/114/108 seconds, no extra wage |
| **M2** | C=T and base-only permanent attr source, `W/A` minima incl. zero additional accessory minima, atomic unequip on upgrade/reset | §3, C1/5/10/15/20; W1/4/7/10/13; A1/3/5/7/9 |
| **D4/M3** | Continuous safe guild work without daily cap, 120s/5g/10g; NPC 2V/3V, 8g/60g recipe, 15/4 stage policy, exam loan and §4 cancel/refund | §4; performance and inflation to measure during Epic I/III |

**Status:** owner has approved broad guild-work and profession mastery principles, but not every value in this table. v0.2 selects unambiguous technical outcomes F1–F5 **for Astra re-review**. Owner can approve the table as one package or request exact substitutions. Changes in economy/versioned policy after implementation require explicit tuning; none of D1 (C25 XP), D2 (enhancement), D3 (E50 party) block Epic I.

## 10. Astra re-review → owner freeze → Sol handoff

**Ask Astra High in the same chat to review v0.2 as a diff against its prior F1–F6, without re-auditing 67 locations/E50:**

- For each F1–F6 return `RESOLVED`, `PARTIAL`, or `OPEN` with exact v0.2 heading/line and counterexample if needed. Particularly check batch connection ownership, all actual equip writers, base allocation/reset and writer revalidation, tool escrow, stage clocks/lock/cancel/recovery, catalog job IDs and versioned economic proposals.
- Confirm static M1 job catalog 24 definitions exists and all craft recipe IDs / gathering source material IDs belong to the correct profession and tier. V2.2 recipe list remains authoritative. Identify any under-specified state transition that still forces Sol to choose different user-visible outcomes.
- Return `CONTRACT_READY` **only** if F1–F5 technically unambiguous and no new P1 technical contradiction. Do **not** return `FROZEN` or implementation approval; explicitly list M1/M2/D4 pending owner sign-off (and note if a numeric suggestion conflicts with real stat budget).
- Preserve exact baseline and validation type `STATIC` for doc review; do not claim tests were run. No code changes, DB, pytest, Draft PR or merge until owner authorizes.

After `CONTRACT_READY` and owner approval of M1/M2/D4 numbers, freeze exact v0.2 SHA256 and issue Sol one big Epic implementation task. Sol first shows DDL and actual owner mapping in same Draft PR; Astra reviews exact subsequent SHA; owner alone merges.

## 11. Change ledger v0.1 → v0.2 (review F1–F6)

| Finding | Specific changed sections | Result for review |
|---|---|---|
| F1 atomic batch | §2.1, §4.1, §5, §8 | One transaction/all-or-nothing, tool single, no partial mode |
| F2 equip writers | §3.3, §5, §8 | `gear_progression`/starter/tier_advance/build/reset; tier upgrade auto-unequip |
| F3 attribute source | §3.1–3.2 | persisted base-only, resolver by actual T/family, reset prospective, table M2 |
| F4 input ownership/tool output | §4.1 | explicit mode/escrow/output, personal tool install versus NPC exam tool, proof identity |
| F5 time/activity/cancel | §4.2 | immutable stage plan + snapshots, no timer XP, player_activity lock, explicit refund and restart |
| F6 approval status | §0, §4.3, §9 | M1/M2/D4 explicit pending owner sign-off; static catalog ≠ runtime or balance approval |
