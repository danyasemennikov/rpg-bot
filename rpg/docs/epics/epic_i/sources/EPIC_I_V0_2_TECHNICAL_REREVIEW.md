# Epic I v0.2 — адресное повторное техническое ревью

**Вердикт: CONTRACT_READY.** F1–F6 закрыты на уровне технического контракта. Новых технических блокеров в проверенной дельте не выявлено. Параметры M1/M2/D4 остаются предложениями для утверждения владельцем; этот вердикт не присваивает FROZEN и не разрешает реализацию, создание PR или merge.

## Объект, область и доказательства

- [Контракт v0.2](C:/Users/masha/Downloads/EPIC_I_TECHNICAL_CONTRACT_V0_2.md), 273 строки; SHA256 `1CA72DA8D4EA0127B9F8221CBE90C50AE0B158D29A60403D0F91DA4FFBFBD984`.
- Основание: [предыдущий отчёт F1–F6](EPIC_I_ASTRA_TECHNICAL_REVIEW.md). Рассмотрены исправления этих замечаний, связанные инварианты/QA и все 24 milestone jobs.
- Локальный кодовый baseline подтверждён: `36368178541510d0d6794117ef17843722c52846`. Новой сверки удалённого main это ревью не заявляет. Перед реализацией требуется обычная проверка exact base.
- Каталожные источники: только необходимые таблицы [Profession V2.2](PROFESSION_PROGRESSION_V2_DESIGN.md) и [Gap §5](CONTENT_GAP_MATRIX.md). Мир, 67 локаций, E50 и четыре документа целиком повторно не аудировались.
- Evidence: **STATIC** — прочитан контракт, сопоставлены F1–F6 и относящиеся к ним code owners, выполнен отдельный разбор Markdown без импорта игровых модулей. [Машиночитаемая проверка 24 заказов](EPIC_I_V0_2_JOB_CATALOG_CHECK.json) содержит каждую ссылку и строку источника. Это не исполнение игровых сценариев и не проверка баланса.
- Контракт v0.2, исходный отчёт и V2.2 не изменены. Игровой код/БД, pytest, бот и PR не затрагивались.

В таблице ниже номера строк относятся к указанному точному файлу v0.2. RESOLVED означает достаточную определённость проектного контракта, а не наличие исправления в main.

## F1–F6: результат повторного ревью

| Finding | Статус | Свидетельство v0.2 | Почему закрыто |
|---|---|---|---|
| F1 — атомарность craft batch | **RESOLVED** | §2.1, строки 48–56; §5, 194; QA 232 | Выбран all-or-nothing: один writer connection/commit, стабильный batch ID и child IDs, весь расход/outputs/XP/observers/receipts откатывается при отказе. Лимит берётся по P на старте; child не commit/close. Replay и новый самостоятельный request различены. Tool/job/exam не используют personal batch. |
| F2 — реальные equip writers и retention | **RESOLVED** | §3.3, 118–134; owner matrix 185; QA 233 | Названы normal/ring/compare/legacy пути через gear_progression, starter, low-level setters, оба tier writers и reset. Повышение T надетой вещи повторно проверяет требования; upgrade и необходимое снятие атомарны. Определены stale preview, revision и нормализация до snapshot при restart/config change. |
| F3 — источник атрибутов и reset | **RESOLVED** | §3.1–3.2, 86–114; 127–132 | Выбраны persisted permanent base attributes без gear/buffs/title/P. Один resolver по фактическому T и family; template minima сохраняются через max. Для reset используется prospective allocation. M2 содержит конкретные W/A таблицы и поведение нестандартных T; будущие неподдерживаемые сочетания не получают молчаливый T20 fallback. |
| F4 — input authority, tool/exam escrow | **RESOLVED** | §1, 26–29; §4.1, 141–153; constraints 192–194 | own_inputs заменён authorized_inputs_for_mode. Personal tool — один install, paid/exam tool — escrow без личного gathering slot. NPC input допустим, NPC-made output не proof. A/B различаются identity, sample — третья операция, но может повторять recipe A. Reward choice/qualification атомарны, completed exam также защищён UNIQUE. |
| F5 — guild time/activity/cancel/restart | **RESOLVED** | §4.2, 157–165; 193–195; QA 235 | Сохранены policy/mastery/plan и длительность. Paid: 4×30s или 15×8s; processing: 15×8/7.6/7.2s. Нет offline catch-up и автоматического XP. Lock общий с travel/field/combat, закрывает instant craft/exam. Claim освобождает ready lock; refund/cancel описаны по состояниям; restart продолжает сохранённую работу. |
| F6 — статус экономических и mastery proposals | **RESOLVED** | §0, 18; §4.3, 169–171; §9, 245–251 | M1/M2/D4/M3 явно требуют sign-off. Выбранный технический кандидат не выдан за утверждённые числа или измеренный баланс. Утверждение principles отделено от утверждения конкретной модели и параметров. |

**Итог:** 6 RESOLVED, 0 PARTIAL, 0 OPEN. Не требуется заново выбирать устройство профессий, проводить общий аудит мира или передавать Sol выбор между разными пользовательскими исходами batch/cancel/equip.

## Проверка существенных границ поведения

### Транзакции и выдача результатов

При отказе child2/4 не остаётся частичной цены, XP, предметов или observer payout. При commit и потере ответа повтор того же batch возвращает receipt. Новый подтверждённый batch ID — отдельное действие с новой оплатой; одинаковые ингредиенты/recipe не являются глобальным ключом дедупликации. Внутренние child IDs нужны для результатов и аудита, не для отдельных commits. На P14→15 дальнейшие children продолжают производство, но не обходят halt и не запускают экзамен автоматически.

Разделение согласовано с известными ограничениями baseline: `crafting_runtime.py:217–241,372–419` и `profession_tools.py:125–208` сейчас имеют собственные transaction boundaries. v0.2 прямо требует conn-owned executor, а не внешнюю обёртку над прежними commits. Existing observers принимают conn (`crafting_runtime.py:362–371`); контракт включает их изменения в общий rollback и запрещает выдачу character XP для guild/exam до вызова observer.

### Экипировка, advancement и атрибуты

Точечно сверены ранее найденные owners: `gear_progression.apply_gear_intent` (384–414), его advance-ветка (472–493), `build_progression._required_unequips` (813+) и tool writer (159–180). v0.2 покрывает обнаруженные маршруты; исправление только вспомогательного gear_instances больше не считается достаточным.

Для C1, уже надевшего T1, переход к T5 приводит к созданию улучшенной вещи и снятию в одном commit, а не к обходу нового equip gate. Reset оценивает будущие base stats. Экипировка не помогает выполнить требования другой вещи или самой себя. UI обязан показывать тот же resolver result. Действующее ограничение ресурсов по новым effective caps при снятии остаётся обязанностью существующих gear/reset owners; новое поведение не разрешает сохранять лишние HP/MP после auto-unequip. На implementation review этот соседний эффект проверяется вместе с атомарностью.

M2 не содержит арифметического запрета гибридов: по ранее установленному budget `6+3×(C−1)` на C20 доступны 63 распределяемых пункта сверх базовых единиц. Два weapon primaries по13 требуют 24 пункта, дополнительный armor primary9 — ещё8; остаётся31. Это только проверка осуществимости распределения, не доказательство силы билда. Подбор конкретных minima и жизнеспособность light/intelligence hybrid остаются предметом будущих targeted snapshots/journeys после sign-off.

### Экзамен и инструменты

В экзамене NPC владеет входами, но игрок лично выполняет действие: это допустимый proof. Скопировать paid-job receipt в exam нельзя из-за mode/exam/criterion identity. Купленный готовый результат и commission также не proof. Третья операция может повторить рецепт первой — важное соответствие экзаменам V2.2; три различных recipe IDs не требуются.

Mining U1 кузнеца и fishing U1 инженера при paid/exam mode уходят в escrow. Они не заменяют имеющийся личный U6, не требуют второй профессии и не становятся полевым loan. Personal tool count>1 отклоняется. Общий craft batch от этого остаётся полезен всем семи производственным профессиям через их gear/consumable recipes.

### Guild activity, часы и restart

§4.2 определяет последовательную личную работу, а не один пассивный таймер. Например, paid gathering принят в t=0, первый stage доступен в t=8. Если пользователь подтвердил его только в t=120, второй доступен не ранее t=128; последующие 14 stages не коммитятся мгновенно. После reconnect применяется тот же сохранённый deadline. P10/P25 или смена конфигурации не ускоряют начатую работу.

До первого committed processing stage отмена возвращает цену один раз. После первого — сохраняет полученный profession XP, не возвращает оплату и не выдаёт материал. Paid cancel не выдаёт wage. После последнего stage разрешён только claim, который выдаёт один конечный outcome и снимает lock. Claim/cancel race решается транзакционной проверкой state/revision и receipt. Restart не является cancel; completed stage не требует повторного выполнения и не даёт повторного XP.

Два редакционных уточнения не меняют этот однозначный результат и не являются блокерами:

- В строке159 слово immutable относится к **принятому плану/цене/policy/mastery**, а `next_stage_earliest_ms`, stage cursor и activity revision — сохраняемое изменяемое состояние по алгоритму строки161. При оформлении DDL их следует так и разделить, а не объявлять курсор неизменяемым.
- «За 120s» в экономическом описании означает минимальное время оплачиваемой работы: §4.2 явно добавляет задержки личных действий. Предельные 150/300g в час не являются измеренным доходом пользователя. Для personal processing 114/108s аналогично — минимум, а не гарантия завершения к абсолютному due_at при отсутствии игрока.

## Отдельная сверка всех 24 milestone jobs

Результат: **STATIC PASS — 24/24**. Имеются 24 уникальных job IDs для 12 профессий, 12 Tier I/P5 и 12 Tier II/P20. Проверены все **48 ссылок A/B**: каждая существует, относится к указанной профессии и тиру; A≠B внутри каждой программы. Для 14 maker jobs проверен recipe ID, для 10 gathering jobs — material ID. Это не повторный аудит всех BOM и не утверждение готового runtime.

| Job | Профессия / тир | A → B | Каталог: строки | Результат |
|---|---|---|---|---|
| `gj_wc_05` | woodcutting / 1 | `wood_common` → `wood_dark` | Gap: 303, 304 | PASS |
| `gj_wc_20` | woodcutting / 2 | `a25_binding_resin` → `a25_heartwood` | Gap: 334, 335 | PASS |
| `gj_mn_05` | mining / 1 | `iron_ore` → `stone_chunk` | Gap: 307, 309 | PASS |
| `gj_mn_20` | mining / 2 | `a25_layered_ore` → `a25_frost_quartz` | Gap: 337, 338 | PASS |
| `gj_hb_05` | herbalism / 1 | `herb_common` → `reed_bundle` | Gap: 295, 302 | PASS |
| `gj_hb_20` | herbalism / 2 | `a25_relic_lichen` → `a25_bitterroot` | Gap: 340, 341 | PASS |
| `gj_fs_05` | fishing / 1 | `shore_fish` → `marsh_fish` | Gap: 313, 314 | PASS |
| `gj_fs_20` | fishing / 2 | `a25_oil_fish` → `a25_reed_perch` | Gap: 343, 344 | PASS |
| `gj_ht_05` | hunting / 1 | `boar_meat` → `wolf_pelt` | Gap: 317, 318 | PASS |
| `gj_ht_20` | hunting / 2 | `a25_resilient_sinew` → `a25_pale_silk` | Gap: 346, 347 | PASS |
| `gj_bs_05` | blacksmith / 1 | `pe_sword_1h_01` → `pxe_tool_mining_1` | Profession: 240, 307 | PASS |
| `gj_bs_20` | blacksmith / 2 | `pe_sword_1h_18` → `pe_shield_18` | Profession: 242, 272 | PASS |
| `gj_ae_05` | arcane_engineer / 1 | `pe_wand_01` → `pxe_tool_fishing_1` | Profession: 258, 315 | PASS |
| `gj_ae_20` | arcane_engineer / 2 | `pe_wand_18` → `pe_focus_18` | Profession: 260, 275 | PASS |
| `gj_ha_05` | heavy_armor / 1 | `pe_heavy_chest_01` → `a25_H_01` | Profession: 279, 328 | PASS |
| `gj_ha_20` | heavy_armor / 2 | `pe_heavy_chest_18` → `a25_H_03` | Profession: 282, 334 | PASS |
| `gj_ma_05` | medium_armor / 1 | `trail_vest` → `a25_M_01` | Profession: 283, 329 | PASS |
| `gj_ma_20` | medium_armor / 2 | `pe_medium_chest_18` → `a25_M_03` | Profession: 286, 335 | PASS |
| `gj_la_05` | light_armor / 1 | `pe_light_chest_01` → `a25_L_01` | Profession: 287, 330 | PASS |
| `gj_la_20` | light_armor / 2 | `pe_light_chest_18` → `a25_L_03` | Profession: 290, 336 | PASS |
| `gj_al_05` | alchemy / 1 | `field_tonic` → `field_mana` | Profession: 291, 292 | PASS |
| `gj_al_20` | alchemy / 2 | `pe_alchemy_health_18` → `a25_clear_sight` | Profession: 295, 378 | PASS |
| `gj_ck_05` | cooking / 1 | `trail_ration` → `pe_cooking_shore_01` | Profession: 297, 298 | PASS |
| `gj_ck_20` | cooking / 2 | `pe_cooking_deep_18` → `a25_hunters_stew` | Profession: 302, 384 | PASS |

Дополнительно:

- `a25_clear_sight` и `a25_hunters_stew` действительно являются recipe IDs V2.2, а не ошибочной ссылкой только на output item.
- `a25_H_03/M_03/L_03` относятся к II, хотя используют доступные I inputs: это допустимо, recipe tier не обязан равняться самому высокому material tier.
- Все десять новых gathering targets разрешены через конкретные item IDs Gap; runtime не должен использовать M01–M15 как неизвестные item IDs.
- Gathering plan 8A+7B =15 этапов. Maker plan 2A+2B =4; каждый stage расходует полный BOM соответствующего recipe из NPC escrow, outputs остаются NPC. Для crafting инструмента в этих программах применяется paid_job mode, не personal install.
- P5/P20 ограничивают дополнительные задания, а не знания или источники. Базовые работы остаются доступны на P1/P16; отсутствие одного из двух изученных рецептов блокирует только конкретный optional maker job. Для gathering достаточно соответствующего уже изученного руководства своего тира по V2.2; обе техники не становятся обязательными.

## Пакет параметров для утверждения владельцем

| Пакет | Что именно остаётся предложением |
|---|---|
| **M1** | P5/P20 и эти 24 дополнительных job-программы; P10/P25 batch2/4 для gear/consumables при одиночных personal tools; processing 120/114/108s, без ускорения paid jobs и без дополнительной wage. |
| **M2** | C=T; base-only requirement policy; W=1/4/7/10/13 и A=1/3/5/7/9 для T1/5/10/15/20; family mapping, нулевые дополнительные minima accessories, поведение промежуточных/неподдерживаемых T; auto-unequip при advance/reset. |
| **D4/M3** | Повторяемая безопасная работа без daily cap; минимум120s и wage5g/10g; 4/15 этапов и личное подтверждение без offline catch-up; processing2V, NPC buy3V, знания8g/60g, commission5×U+BOM; V2.2 XP/loan/exam inputs и связанные стартовые параметры; полный refund только до stage1, отсутствие refund после него и claim-only после завершения. |

Это три пакета sign-off, а не новый общий дизайн-цикл. Принципы профессий и независимости craft/equip повторного решения не требуют. Ускорение personal processing увеличивает потенциальные XP/материал в час на ~5.26%/~11.11% при тех же значениях за операцию; изменение чисел после принятия работы не меняет её snapshot. Одобрение стартовых параметров не равно экономической или боевой balance acceptance.

## Передача дальше

**CONTRACT_READY относится к точному v0.2 SHA256 выше и ограниченному техническому ревью F1–F6/24 jobs.** Перед реализацией владелец утверждает M1/M2/D4 и отдельно разрешает работу Sol. Статус FROZEN не присвоен. Если меняются только балансные числа в рамках уже выбранной семантики — проверить затронутые расчёты/таблицы; изменение модели атомарности, mode, equip или таймеров требует адресной повторной проверки соответствующего пункта.

Игра ещё не реализует этот контракт. Pytest, игровые сценарии, Telegram и балансные прогоны не запускались. Следующий implementation PR остаётся одним крупным Epic I; этот отчёт PR не создаёт.
