# Epic I — независимое техническое ревью Astra High

Дата: 2026-10-14 UTC. Режим: **review-only / STATIC**.

**Вердикт: CONTRACT_FIX_REQUIRED.** v0.1 соответствует утверждённому направлению Epic I, но ещё не является однозначным implementation contract. До `CONTRACT_READY` нужны адресные уточнения транзакций, экипировки и гильдейского runtime, перечисленные ниже. После технических исправлений остаётся отдельное утверждение параметров владельцем; `CONTRACT_FROZEN`, разрешение на реализацию, merge и deployment этим отчётом не выдаются.

## 1. Точный объект и границы проверки

- Объект: `C:/Users/masha/Downloads/EPIC_I_TECHNICAL_CONTRACT_DRAFT.md`, **v0.1**, 208 строк.
- SHA256: `9F3C9BB87F989713904185C802E0AB077EC79B6550B3E8F99772585EEE0B1CD0`.
- Локальный HEAD и GitHub `main`, независимо прочитанный через `gh api repos/danyasemennikov/rpg-bot/commits/main`: **`36368178541510d0d6794117ef17843722c52846`**.
- Репозиторий: `C:/Users/masha/Documents/Codex/2026-10-14/files-pasted-by-the-user-alpha/work/rpg-bot`. В начале и в конце ревью `git status --porcelain` пуст.
- Прочитаны applicable `rpg/AGENTS.md`, документационные authorities по его порядку, relevant foundation, четыре V2.2, актуальные тело и комментарии Issue #241, включая **6177452595**.
- Статическая проверка: чтение владельцев и callers, поиск SQL writers; Python `ast.literal_eval` для литералов ресурсов и разбор markdown-таблиц. Игровые модули не импортировались, SQLite/runtime не запускались. Pytest, бот, Telegram, PR и игровые изменения не выполнялись. Исходный контракт не изменён.

Далее `Контракт:строка` означает исходный файл выше; `V2:строка` — `outputs/PROFESSION_PROGRESSION_V2_DESIGN.md`; `Gap:строка` — `outputs/CONTENT_GAP_MATRIX.md`. Кодовые пути начинаются от корня репозитория. Это ревью ограниченного Epic I, без повторного аудита мира, E50 и всей боевой системы.

## 2. Что действительно утверждено

Основные источники: [решение 6172833671](https://github.com/danyasemennikov/rpg-bot/issues/241#issuecomment-6172833671), [новое решение 6177452595](https://github.com/danyasemennikov/rpg-bot/issues/241#issuecomment-6177452595).

| Положение | Статус |
|---|---|
| 12 профессий, 8×15 уровней, alpha I/II=P1–30, будущие III–VIII | Утверждено |
| Весь каталог тира сразу eligible, знание отдельно, без hidden P/C gates | Утверждено |
| P15 freeze без банка, две разные личные работы + отдельный sample + mentor confirm, P16/XP0, title/journal и один II choice | Утверждено |
| Обе техники, независимость от боя/второй профессии, отсутствие миграции старого тестового прогресса | Утверждено |
| Дополнительные guild jobs и небольшие mastery/convenience benefits внутри тира | Утверждён принцип новым комментарием; это допустимый scope Epic I |
| Equip проверяет C и собственные attribute requirements вещи; профессия не участвует | Утверждён принцип; действующий код не считается достаточным исполнением |
| P5/P10/P20/P25, batch2/4, −5%/−10%, C=T, конкретные attribute minima | **Предложения**, не утверждённые константы |
| 120s, 5g/10g, 2V/3V, XP-формулы и конкретные программы 12 экзаменов V2.2 | Готовые предложения для review/approval; не измеренный баланс |
| D4: точная экономическая роль безопасного труда | Нужен явный sign-off предложенной модели; новое решение подтверждает наличие guild jobs, но не все детали D4 |

Замена мягкого C-ориентира из `GAME_FOUNDATION.md:983–999` отдельной проверкой C обоснована новым решением владельца. Это не разрешает классовые замки и штрафы за «неправильную броню». D1/D2/D3 не нужно переоткрывать для завершения технического контракта Epic I.

## 3. Findings, требующие исправления контракта

P1 — технический пробел, способный нарушить обещанный игровой результат/целостность. P2 — существенная конкретизация перед передачей Sol. Здесь речь о контракте, а не о доказанном дефекте ещё не написанной реализации.

### F1 — P1: не выбрана атомарность craft batch; receipts не заменяют transaction boundary

**Место:** Контракт:35–42, 146, 183.

В таблице обещаны отдельный committed result и `serial atomic commits`, затем Sol предлагается выбрать между полностью атомарным пакетом и частичным завершением. Это два разных пользовательских результата при нехватке материалов, остановке процесса и replay. Технический контракт пока не задаёт, что именно должно произойти.

**Код:** `rpg/game/crafting_runtime.py:217–241,246,372–419` открывает собственное соединение, фиксирует отдельную операцию и закрывает соединение. Ветка инструментов передаёт управление `profession_tools.craft_tool`, который также сам начинает и завершает транзакцию (`rpg/game/profession_tools.py:125–144,197–208`). Внешняя транзакция вокруг N вызовов нынешнего API не сделает их одним атомарным пакетом.

**Минимальное предлагаемое исправление:**

> Для личного batch выбрать all-or-nothing: один immutable batch request с player/profession/recipe/count/catalog-policy fingerprint; одна writer transaction, N child operation IDs и N результатов внутри неё; один commit. Child receipts не означают отдельный commit. При любой ошибке расход, outputs, XP, observers и receipts откатываются целиком. Replay возвращает сохранённый полный результат; тот же request с иным count/recipe отклоняется. Внутренний craft executor принимает caller-owned connection и не commit/close. Лимит batch проверяется по P в начале операции и не увеличивается посреди неё. Paid jobs и exam stages через personal batch не исполняются.

Это рекомендация архитектуры, не уже принятое решение. Вариант partial completion тоже реализуем, но требует durable batch ledger, child status, stable child IDs и точного resume/cancel UX; для пакетов 2/4 он сложнее без очевидной пользы. Уменьшение числа Telegram подтверждений — реальная, хотя небольшая, польза instant batch; не нужно приписывать ему ускорение серверного производства или бесплатный XP.

**Проверка в будущем PR:** отказ child2/4; crash до commit; lost response после commit; replay другим токеном того же request; подмена count; cap P15 внутри batch; сумма стоимости/outputs/XP как у N одиночных операций при том же начальном состоянии.

### F2 — P1: карта equip не называет реальные live writers и не закрывает повышение tier надетой вещи

**Место:** Контракт:73–100, 128, 166, 184.

Описание `gear_instances.equip_gear_instance_in_slot` верно, но это не единственный и не основной Telegram inventory writer. Исправление лишь перечисленного helper оставит основной путь с base requirements.

**Проверенные маршруты:**

| Маршрут | Фактический owner / доказательство |
|---|---|
| Обычный instance equip, ring1/ring2 | `handlers/inventory.py:747–769,1262–1268` → `game/gear_progression.py:384–414`, base-item req проверяются на 396,404–406 |
| Compare-equip | `handlers/inventory.py:1016–1018,1063–1068` → тот же `apply_gear_intent` |
| Legacy equip | `handlers/inventory.py:1294–1300` → `game/gear_progression.py:284–318`, base req на 304–306 |
| Starter auto-equip | `game/starter_kit.py:37–40` → `game/gear_instances.py:591–625` |
| Низкоуровневые setters | `gear_instances.py:553–568,628–637`; у setter нет requirement check, у legacy helper ещё и separate commit очистки слота. Production caller этих двух helpers в проверенном поиске не найден; не объявлять их доказанным пользовательским exploit |
| Повышение tier уже надетого instance | `handlers/location.py:1537,2204` → `gear_progression.py:472–493`: меняется `item_tier`, equipped slot сохраняется, predicate не вызывается |
| Дополнительный tier writer | `game/tier_advancement.py:122–189`; production caller в проверенном поиске не найден, API всё равно нужно сопоставить с новой policy |

**Конкретный обход будущей C=T policy:** C1 надевает T1, затем доступным advancement повышает до T5, оставаясь экипированным. Запрет нового equip T5 сам по себе этот маршрут не закрывает. Это вывод из writer-кода; игровое воспроизведение не выполнялось.

**Минимальное предлагаемое исправление:**

> Добавить `gear_progression.py`, `tier_advancement.py`, `build_progression.py`, `starter_kit.py` и современные inventory views в обязательную owner matrix. Predicate применяется ко всем equip writers и к изменениям, способным сделать уже надетую вещь невалидной. При advancement новая вещь может быть создана/улучшена независимо от C, но если её новые требования не выполнены, preview предупреждает о снятии, а commit атомарно повышает tier и снимает её, увеличивая revision и clamp ресурсов. Отмена preview ничего не расходует. Low-level setters либо становятся внутренними после проверки, либо проводят ту же проверку.

Не требуется создавать loadout subsystem: в v0.1 его существование не подтверждено. Требуется закрыть реально найденные writers, reset и reread состояния после restart. Для изменения requirement data определить revision/stale-preview и нормализацию невалидного equipped state до использования его в snapshot; без миграции старых тестовых персонажей.

### F3 — P1: источник атрибутов и изменение требований после reset пока неоднозначны

**Место:** Контракт:87–100, 198.

«Не учитывать бонус самого предмета» не выбирает между base attributes, суммой с остальным оборудованием, временными buffs и статами до/после замены слота. Эти модели по-разному допускают bootstrap от другого предмета и требуют разных правил при снятии вспомогательного gear. Formula `max(template, optional_instance)` тоже пока не определяет источник tier-dependent attribute minima: если записать T20 minimum в общий field template, его получат экземпляры T1 того же шаблона.

**Код:** нынешние writers читают raw `players` (`gear_instances.py:606–610`, `gear_progression.py:304–306,404–406`). Combat effective stats отдельно суммируют equipment bonuses (`game/equipment_stats.py:146–150`). Attribute reset имеет собственную проверку `_required_unequips` по предложенным base attributes и повторяет req extraction (`game/build_progression.py:813–867,895–950`). Простая замена только equip/UI оставит несовпадающий reset.

**Минимальное предлагаемое исправление:**

> Equip requirements сравниваются с canonical persisted level и permanent base attribute allocation персонажа, без equipment, food/preparation, временных эффектов, самого candidate и предмета в заменяемом слоте. Для reset используется prospective base allocation в той же transaction. Requirement resolver получает template identity/family/armor kind, фактический instance tier и versioned family policy; возвращает все требования одним объектом. Не вводить необязательные instance overrides в DB, если каталог их не использует. Existing более строгие template minima сохраняются через max. Распределение/снятие/перестановка вещей не создаёт зависимости между requirements других вещей.

Это рекомендуемая простая policy, соответствующая текущему источнику статов; она требует согласования вместе с M2. Она решает циклические бонусы без нового balance subsystem. Конкретное предложение таблицы — §6 отчёта.

### F4 — P1: `own_inputs` и универсальный personal batch не согласованы с NPC/exam escrow и tool slot

**Место:** Контракт:22,35–42,109–111,124–127,137–140,149.

Формальный `can_craft` требует `own_inputs`, тогда как оплачиваемые работы и экзамены обязаны использовать NPC-owned inputs. Кроме того, обещание N outputs для любого craft не определено для инструментов, которые не являются stack или gear instance: personal craft сегодня устанавливает один tool в специальный слот. Повторная установка не создаёт два хранимых инструмента.

**Код:** `crafting_runtime.py:232–240` выделяет инструменты в отдельный путь; `profession_tools.py:159–180` требует текущую tool revision, запрещает downgrade, подтверждает replacement и вызывает `install_tool`. `install_tool:46–65` обновляет одну строку слота; `player_experience_schema.py:50–60` — per-profession slot. Такой owner не может сам по себе выдать tool в job/exam escrow. V2 уже требует разделение назначения output (`V2:129,148–150,158,171–172`).

**Минимальное предлагаемое исправление:**

> Общий executor проверяет `authorized_inputs_for_mode`: personal — собственные ingredients; paid_job/exam — зарезервированные inputs конкретного принадлежащего игроку job/exam; commission — отдельный NPC outcome без maker XP/proof. Mode и destination назначаются сервером и входят в immutable intent/receipt. Для paid_job/exam tool output — escrow record с tool family/tier/quantity, без установки/износа/замены личного gathering slot и без требования изучить соответствующую gathering profession. Personal tool craft/commission — одна явно подтверждённая установка, N>1 запрещено. Personal batch2/4 применяется к gear/consumable recipes; tool recipes остаются одиночными. Все семь crafting профессий при этом имеют доступные batch recipes.

Исключение tools из batch — конкретная предлагаемая поправка M1; более сложный portable tool inventory не нужен для V2.2 и не должен появиться незаметно.

**Exam proof:** отделить владельца inputs от исполнителя действия. NPC inputs допустимы в личном экзаменном действии. Receipt требует player, profession, exam ID, criterion, recipe/source identity, mode, committed operation ID и output reference. Взять inventory item или paid-job escrow как доказательство нельзя. A/B — разные identity, sample — третий operation; sample может повторять recipe A/B (так прямо задано для кузнеца и бронников). Недопустимо ошибочно требовать три различных recipe IDs. Proof создаётся после регистрации и в transaction действия; sample custody/расход и final reward атомарны по протоколу V2:154–160.

### F5 — P1: mastery duration не привязана к сохранённому расписанию, activity authority и новой schema

**Место:** Контракт:35,39,44,118–140,148,181–183.

Сами −5%/−10% допустимы как предложение. Но контракт не выбирает момент применения скидки и расписание стадий: оставить 15×8s означает прежние 120s, а изменить только `due_at` даёт несовпадение stages и completion. Повторный quote/restart после повышения P или настройки duration не должен ускорять уже принятую работу. Ограничение одной строки `guild_job` не исключает одновременный обычный gather/travel/craft через старый activity owner.

**Код:** `game/gathering_runtime.py:153–157,253–256` фиксирует 8s/120s; `player_experience_schema.py:49` содержит `CHECK(ends_ms=started_ms+120000)`. Эти ограничения относятся к текущему полевому сбору, для которого v0.1 не разрешает mastery speedup. `player_activity.py:34–40,44–58` знает travel/gather/combat, но не guild work. `gathering_runtime.py:282–290` прерывает running field sessions при startup; это не готовый restart-resume нового guild runtime.

**Минимальное предлагаемое исправление:**

> При accept сохраняются mode, job tier, recipe/material/stage plan, XP/wage/yield/cost policy versions, mastery snapshot и integer `duration_ms`. Для personal processing предложение: 120000/114000/108000ms; 15 stage deadlines выводятся из сохранённой duration (8000/7600/7200ms для этих чисел). Paid job всегда 120000ms; gathering paid job — 15×8000ms, crafting paid job — 4×30000ms. Payload каждого этапа валидируется, один `(job_id,stage_index)` фиксируется один раз; один таймер без валидной операции не создаёт XP. Claim/reconnect/смена P/config не пересчитывают deadlines и не запускают следующий job автоматически. Guild work входит в `player_activity`, start/claim/cancel/recovery и due reconciliation; одновременно только одна разрешённая длительная активность на персонажа. Field 120s/RNG/wear сохраняются отдельно.

Дополнить точное правило cancel: завершённые операции/XP не повторяются, NPC escrow закрывается без inventory output; personal processing не допускает повторного refund после частичного исполнения. Конкретную refund policy нужно записать до реализации, не выводить из UI. Рекомендация — до первого committed этапа возврат полной оплаты, после первого этапа подтверждённая отмена без возврата; UI сообщает цену отмены заранее. Restart не равен cancel, новый job восстанавливается по сохранённой истории.

**Экономический эффект:** 120→114s увеличивает потенциальный XP/час и результат/час примерно на 5.26%, 120→108s — на 11.11%, даже без изменения XP на действие. Это ожидаемый эффект удобства, который нужно явно измерить; формулировка «не множитель XP» верна только на уровне одной операции. Paid gold/hour остаётся 150/300 до UI overhead.

### F6 — P2: V2.2 D4 и параметры нельзя представлять уже одобренными

**Место:** Контракт:104,114,197–201.

Основной текст корректно отмечает M1/M2 как proposals. Однако «принятые ID/BOM» и «D4 ... нуждается в балансной проверке, а не новом выборе принципа» могут создать впечатление, что конкретный V2.2 экономический пакет уже утверждён. В четырёх V2.2 D4 остаётся открытым; новое owner decision прямо оставляет time/economy effects proposals. Содержание guild jobs не нужно заново изобретать, но explicit sign-off выбранного варианта отсутствует.

**Минимальное исправление:**

> V2.2 — выбранная основа каталога и предлагаемая D4-модель для данного ревью. Не менять её без найденного дефекта или решения владельца. До freeze владелец подтверждает эту конкретную D4-модель и стартовые параметры M1/M2/M3; утверждение principles не равно утверждению чисел. Принятые для реализации значения фиксируются с version и допускают последующее измеренное tuning отдельным решением.

Это approval/data gap, а не требование нового общего дизайн-цикла. Нельзя считать его закрытым от того, что в будущем запланирован economy test.

## 4. Подтверждённые части и точечные уточнения, не требующие нового аудита

### Каталог и BOM — STATIC PASS ограниченной проверки

Разобраны все 153 рецептурные строки V2:240–397; статическая проверка дала:

| Проверка | Результат |
|---|---|
| Recipe IDs | 153 строки, 153 уникальных ID |
| Тиры | 69 I / 84 II |
| Current / new | 83 / 70 |
| Tools | 30 = 5×6, включены в 153, а не сверх них |
| Gathering manuals | 20 = 5×2×2; отдельны от craft |
| BOM references | Все материалы разрешились в 30 baseline IDs + M01–M15; положительные целые количества; неизвестных ссылок нет |
| U4 bootstrap | Все пять BOM используют только I: wood_common, iron_ore, coal, frostpine_wood, gem_common |
| T20 weapons | Все десять families присутствуют |
| XP арифметика V2 | 3220 + 6930 = 10150, пересчитано без runtime |

Базовые 30 материалов подтверждены `profession_resources.py:28–66`: 28 RESOURCE_ROWS плюс dry_reagent/marsh_mushroom. Gap:295–324 задаёт 30 safe routes, Gap:334–348 — новые 15 с reference V и alias→item ID. Цифра 83 в baseline подтверждается генераторами `profession_recipes.py:91–154` и assertions `profession_recipes.py:199–200`; V2 включает их переработку. Новые U5/U6 используют II-материалы из того же safe/U4 слоя — отдельного U5/U6-exclusive материала не найдено.

Это **не** исполнение 153 рецептов и не доказательство правильного combat/item-use эффекта. Новые templates/12 consumables ещё требуют реализации и targeted evaluator checks. Не следует подменять успешным подсчётом будущую source→knowledge→craft→use journey.

### XP и exam: основа достаточна при точном переносе V2

Контракт правильно запрещает XP bank и automatic P16. При реализации нельзя просто поднять max20→30: текущие `profession_progression.py:7–38,50–60` и `gathering_progression.py:8,25–49,52–95` имеют разные award policies и не знают P15 exam gate. Включить ссылкой V2:86–109 как нормативный proposed XP policy: threshold crossing на P15/P30 приводит к XP0; receipt хранит фактически applied/discarded, а не только requested award. Training ceilings и old per-P source/tool gates удаляются из действующих consumers.

Проверены ссылки maker exam на существующие/предложенные I rows, включая `a25_H_01/a25_M_01/a25_L_01`; material samples входят в I из Gap. Две разные практики и отдельная третья операция согласованы с новым owner decision. Для mining слово `ore` в V2:167 стоит нормализовать в точный `iron_ore` operation target; это не новый рецепт.

Не нужно создавать generic achievements: title/journal exam fact достаточно встроить в существующую узкую authority. Рекомендуемый constraint `UNIQUE(player,profession,target_tier)` сильнее «unique active»: повторно завершённый экзамен того же перехода не создаёт новую reward identity. Конкурирующие choices возвращают один committed выбор.

### Clean schema: разрешённая замена, обязательная карта bootstrap

Отсутствие полного DDL в v0.1 само по себе не blocker: V2 и roadmap разрешают Sol представить точную схему первым шагом в том же Epic PR. Но список owners нужно расширить проверенными файлами:

- `database.py:96–107,345–357,394–410`: gathering table, init chain, создание стартовых строк/знаний.
- `game/alpha_schema.py:14–42`: старый crafting CREATE с CHECK1..20 и вызов profession schema.
- `game/profession_schema.py:21–26,133,142–186,217–220`: CHECK1..20, строгий validator, knowledge provenance и автоматические rows.
- `game/player_experience_schema.py:34–60,141–154,183–190`: U1..4, durability≤60×tier, fixed120s, точная проверка schema, starter tools.
- `profession_recipes.py:21–26`, `crafting_runtime.py:422–430`: tool output validators U1..4.

U1 durability90 из V2 уже не помещается в текущие ≤60×tier, не только U5/U6. New schema/validators/seeds меняются согласованно; не нужен upgrade rehearsal старой БД, но **нужны clean init→restart и повторный ensure**. Если вводится unified profession state, все названные readers/writers переводятся на него или совместимое представление; не держать рядом два независимо изменяемых level/XP источника. Row existence не должна незаметно означать «профессия зарегистрирована и стартовые vouchers уже выданы».

### Нулевой C XP: включить provenance в фактические observers

Инвариант Контракт:152 верный, но его необходимо проверять на конкретной границе: `crafting_runtime.py:362–371` безусловно вызывает contract/regional observers. Для `guild_work`/`profession_exam` новые операции не должны выполнять боевые/Chapter/adventure objectives с character XP; обычный личный adventure craft сохраняет прежние права по V2:123. Речь не о глобальном отключении observers. Нужен explicit receipt provenance и фильтрация до отправки неподходящего события.

## 5. Обязательная минимальная матрица реализации после исправлений

Это будущие проверки; **в этом ревью они не запускались**.

1. **Progression:** P14→15 overflow→XP0; действия на P15 сохраняют production без XP; mentor confirm→16/0; I action после II получает пониженную награду; P29→30 overflow; действия на P30 не создают банк.
2. **Batch:** N одиночных vs один batch при тех же входах; crash/rollback/replay; invalid count; crafted gear/consumable output; запрет personal tool N>1; отсутствие job/exam batch shortcut.
3. **Exam:** 12 профессий; owner/registration/time/provenance; A/B distinct identity; отдельный sample operation допускает тот же recipe; NPC-supplied inputs допустимы, NPC-made output не доказательство; two reward choices concurrent; отказ Telegram после commit; повторная регистрация.
4. **Tools:** blacksmith mining exam с невыученным mining и со своим U6 mining slot; escrow tool не заменяет его. Аналогично arcane fishing. U4 from I, U5/U6 at P16, все пять commissions без кузнечной профессии и предыдущего U; loan никогда не становится полевым tool.
5. **Guild/time:** paid120s unchanged; personal120/114/108s согласно утверждённым данным; current P/config меняется после accept; cancel/refund/restart; одна активность across профессии/travel/gather/craft; no wage+materials; один stage→один XP; gold0 recovery.
6. **Equip:** каждый live маршрут из F2, ring slots, legacy и starter; C1 crafting T20 allowed / equip denied; недостаток каждого ненулевого req; candidate/self/other gear/buff не помогает при base-only policy; reset; equipped T1→T5 advance; preview соответствует commit и RU/EN/ES.
7. **Clean init:** новый init→ensure→restart с полной schema; U6/durability по новой policy; exactly-once vouchers; отсутствие двойных state writers.
8. **Catalog/effects:** 153/20/45/30, source/consumer closure; реальные 12 consumable effects, expiry/escape/settlement и no free healing; unchanged PvP allowlist.
9. **Journeys:** 12 свежих C1/gold0 без admin grants проходят P30; отдельные natural simulated и real Telegram evidence; времена/доходы/расходы измерены; character XP не изменяется. Никакого вывода о E50, multiplayer или релизе из этих результатов.

## 6. Конкретное предложение attribute policy для M2

**Предложение для review, не подтверждённый баланс.** Предпочтение — невысокие primary minima и base-only stat source из F3, без второго обязательного высокого стата и без требований к классу/профессии. Это оставляет гибридам бюджет на вторую специализацию и vitality.

| T | 1 | 5 | 10 | 15 | 20 |
|---|---:|---:|---:|---:|---:|
| C minimum | 1 | 5 | 10 | 15 | 20 |
| Primary weapon minimum W(T) | 1 | 4 | 7 | 10 | 13 |
| Armor/offhand minimum A(T) | 1 | 3 | 5 | 7 | 9 |

| Семейство / предмет | Предлагаемое требование |
|---|---|
| sword_1h | strength ≥ W(T) |
| sword_2h | strength ≥ W(T) |
| axe_2h | strength ≥ W(T) |
| daggers | agility ≥ W(T) |
| bow | agility ≥ W(T) |
| magic_staff | intuition ≥ W(T) |
| wand | intuition ≥ W(T) |
| holy_staff | wisdom ≥ W(T) |
| holy_rod | wisdom ≥ W(T) |
| tome | wisdom ≥ W(T) |
| heavy armor, все слоты и варианты | strength ≥ A(T) |
| medium armor, все слоты и варианты | agility ≥ A(T) |
| light armor, все слоты и варианты | wisdom ≥ A(T) |
| shield / focus / censer | соответственно strength / intuition / wisdom ≥ A(T) |
| rings / amulets, включая новые support/anchor | Дополнительный family attribute minimum = 0; сохранять explicit template minima; C requirement сохраняется |

Выбор weapon primary согласован с текущим `field_catalog.py:17–26`. Armor/offhand mapping — новая рекомендация, не вывод из damage scaling. Аксессуары без дополнительного family minimum оставляют место гибридной настройке; нулевое требование не означает обход более строгого explicit item requirement. Если владелец хочет ненулевой минимум у каждого аксессуара, нужна явная отдельная небольшая таблица, а не автоматическое чтение stat bonuses как requirements.

Для остальных T: C=T как proposed default; для attributes — явно выбрать интерполяцию/следующий band либо ограничить текущую catalog policy поддерживаемыми T. Нельзя непреднамеренно распространить новые T20 числа на будущий T50 или записать их в один общий T1 template. Предлагаемый простой alpha вариант — piecewise constant на нижнем известном band внутри 1..20, fail-closed для unsupported family/T до явной записи будущей policy; это **не** глобальный cap развития мира.

Арифметическая проверка доступности: `build_progression.py:181–182` задаёт budget `6+3×(C−1)` сверх базовых единиц. На C20 это 63 пункта. Два weapon primaries по13 используют 24 пункта; добавленный независимый armor primary9 — ещё8, остаётся31. Такой пример показывает отсутствие арифметического запрета на гибрид, **не** его боевую эффективность. Нужны будущие targeted snapshots/journeys для pure melee/ranged/caster/healer и strength+wisdom, agility+intuition, intuition+wisdom hybrids; нельзя объявлять этот пакет balance-approved по одной сумме.

Не нужно добавлять req_vitality/req_luck только ради симметрии: текущие item fields и writers используют четыре указанных атрибута. Если выбрать vitality для heavy armor, это допустимый отдельный выбор, но потребуется согласованное расширение schema/resolver/UI/reset; текущий отчёт не выдаёт его за существующую возможность.

## 7. Действительно необходимые вопросы владельцу

Сначала исправить техническую неоднозначность F1–F5 предложенными формулировками или явно выбранными эквивалентами. SQLite структуру, IDs, caller-owned transaction, дедупликацию и перечень writers Sol/Astra должны довести самостоятельно; перекладывать эти инженерные решения на владельца не требуется.

Затем достаточно трёх согласований конкретного пакета:

1. **M1:** утвердить ли P5/P20 дополнительные тематические jobs без повышенной оплаты, P10/P25 batch2/4 для gear/consumables (personal tools — одиночные), и −5%/−10% времени personal processing при неизменных paid jobs? Для P5/P20 в новой редакции дать 24 точных job definitions/operation identities, а не только названия тем из Контракт:50–61. Эти данные можно подобрать из существующих каталожных ID без нового мира.
2. **M2:** утвердить ли C=T и base-only атрибуты с конкретной таблицей §6, включая нулевые дополнительные accessory minima и atomic unequip при advance/reset? Если числа не подходят, нужны изменённые числа или один конкретный альтернативный профиль; принцип craft/equip заново не обсуждается.
3. **D4/M3:** утвердить ли именно предложенную V2.2 модель повторяемого безопасного труда без daily lock: 120s, 5g/10g, 15 gathering / 4 crafting stages, 2V/3V, XP/knowledge/tool стартовые параметры и бесплатный exam escrow? Это разрешение реализовать стартовые настройки с обязательными измерениями, а не признание баланса. В конкретный пакет включить явно описанную cancel/refund policy из F5.

Программы экзаменов, цены знаний/commission/durability и XP-таблицы можно утвердить вместе с этим пакетом ссылкой на точную V2.2 редакцию; отдельный длинный опрос по каждому числу не нужен. D1/D2/D3, новая навигация #239 и мир E50 не блокируют этот bounded contract review.

## 8. Handoff и критерий готовности

**Astra → автору контракта:** исправить F1–F5, дополнить проверенную owner matrix/schema constraints, обозначить D4/M1/M2/M3 proposals без ложной approval. Вставить точный milestone job appendix и requirement table, вместо передачи незаданных продуктовых правил Sol. Это правки одного контракта, не новый Epic и не требование перепроектировать V2.2.

**Условие `CONTRACT_READY`:** однозначные outcomes/ownership/time/equip semantics, все обязательные owner routes перечислены, параметры представлены конкретно и отмечен их статус; нет выбора принципиально разных runtime outcomes, оставленного на импровизацию реализации. **Условие freeze/передачи Sol:** владелец подтверждает конкретную редакцию и отдельно разрешает implementation. Затем один coherent Draft PR с внутренними commits и focused evidence.

Сейчас: **CONTRACT_FIX_REQUIRED; implementation не начата**. Подтверждённая основа каталога и решений достаточна, чтобы исправить документ адресно, без ещё одного общего аудита мира.
