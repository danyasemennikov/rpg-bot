# Profession Progression V2 — Tier I–II

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

## 1. Оси прогрессии и действующие ограничения

| Ось | Значение | Что проверяет |
|---|---|---|
| C | Уровень персонажа 1–25 в альфе | Боевую прогрессию и самостоятельные equip requirements; не обучение ремеслу |
| P / профессиональный тир | P1–120, восемь диапазонов по 15 | Право изучать и применять рецепты своего тира; квалификацию на границе |
| RL | Редакционная метка recipe level 1–30 | Только принадлежность к диапазону I/II и отображение каталога; не дополнительный gate |
| T | `item_tier` экземпляра снаряжения, alpha до 20 | Бюджет статов, отдельный от RL, P и C |
| U | Качество инструмента 1–6 | Прочность/удобство; U1–3 для I, U4–6 для II |
| S/R/C-work | Простая/обычная/сложная работа | XP и количество результата за время, никогда required P внутри тира |

В baseline `ProfessionRecipe.required_level` сейчас действительно проверяет отдельные уровни, `training_ceiling` режет рост, tool/source tier выводится из численного P. Все три связи нужно заменить, а не оставить под новым названием. `recipe_tier`, `source_tier` и `required_profession_tier` — явные поля новой модели. RL допустим как метка каталога, но runtime не сравнивает его с текущим P.

`gear_instances.item_tier` масштабирует характеристики экземпляра. `resolve_gear_instance_item_data` сохраняет `req_level` и требования атрибутов базового шаблона; field templates в baseline имеют req_level=1. Поэтому T20 **не означает автоматически C20**. Новая профессия не добавляет ни C16 для изготовления, ни скрытый C16 для экзамена. Проверки экипировки остаются отдельным owner: предмет можно создать, хранить и передать в NPC-заказ, даже если конкретный персонаж не может его надеть. Изменение требований ношения — отдельное решение, не способ скрыто ограничить профессии.

## 2. Полная лестница тиров

| Тир | Диапазон | Рабочее звание | Статус |
|---|---|---|---|
| I | P1–15 | Ученик | Альфа; регистрация профессии у мастера без платы и требования C |
| II | P16–30 | Подмастерье | Альфа; экзамен I→II, не автоматический level-up |
| III | P31–45 | Ремесленник | Будущий контент |
| IV | P46–60 | Специалист | Будущий контент |
| V | P61–75 | Эксперт | Будущий контент |
| VI | P76–90 | Мастер | Будущий контент |
| VII | P91–105 | Великий мастер | Будущий контент |
| VIII | P106–120 | Хранитель ремесла | Будущий контент |

Звания локализуются отдельно для профессии: «Подмастерье-рудокоп», «Подмастерье-алхимик» и т.п. Они не дают боевых stats. Диапазоны утверждены; названия — редакционные предложения. Профиль показывает будущее III–VIII как перспективу, без активных кнопок или обещанных дат. Экзамены будущих границ сейчас не проектируются как готовая механика.

Каждая из 12 профессий регистрируется независимо. Обе техники A/B — направления обучения и применения, не взаимоисключающие фракции и не скрытые уровневые замки. Для семи crafting professions метка A/B описывает рецепт, но не требует отдельной лицензии поверх knowledge. Для gathering это два изучаемых руководства своего тира; оба доступны сразу по полученному тиру.

Сохранённые направления семи производственных профессий:

| Профессия | Техника A | Техника B | Практический выбор |
|---|---|---|---|
| Кузнец | Клинки и баланс | Крепёж и инструменты | Оружие четырёх melee families либо инструменты и щиты |
| Арканный инженер | Рамы и проводники | Фокусы и опоры | Шесть weapon families либо аксессуары, offhand и рыболовные инструменты |
| Латник | Опора | Устойчивость | Основной физический бюджет либо распределение части бюджета в magic defense |
| Кожевник | Меткость | Манёвренность | Точность либо уклонение/запас HP в пределах общего бюджета |
| Ткач | Резерв | Защитное плетение | MP/healing либо magic defense/HP |
| Алхимик | Восстановление | Подготовка и очищение | Лечение/восстановление либо подготовительные эффекты и cleanse |
| Повар | Походное питание | Питание под задачу | Восстановление между боями либо подготовка к выбранной роли |

Это рубрики каталога, а не два обязательных дерева талантов. Игрок свободно изучает рецепты обеих рубрик в полученном тире; переключение направления не удаляет знания, не требует отдельного экзамена и не даёт множителя XP. Конкретные изделия и эффекты заданы в §9; практические методы пяти добывающих профессий — в §8.

## 3. Доступ к рецептам и знаниям

`can_learn = profession_registered AND profession_tier >= recipe_tier AND recipe_not_known AND acquisition_paid_or_voucher`.

`can_craft = profession_tier >= recipe_tier AND recipe_known AND ingredients_available AND valid_activity`.

Ни C, ни сравнение P с RL, ни Chapter I, региональная репутация, вторая профессия, boss kill или техника-эксклюзив не входят в эти предикаты. Известный рецепт не даёт ингредиенты. Полный каталог I показывается на P1, II — сразу после экзамена на P16, включая RL30. На P16 доступны и рецепты U6, и вся линейка T20 при наличии материалов. Рост P16→30 не открывает рецепты заново: он развивает профессиональный статус, даёт цель и будущую готовность к III, а глубина игры — в знаниях, заказах, цепочках, инструментах и выборе изделий.

### Снабжение знаниями

- В Астере есть службы всех 12 профессиональных мастеров, без новых локаций и player-guild framework. Региональные хабы дублируют соответствующие службы, но не монополизируют рецепты.
- Обычная цена изучения: **8g за I, 60g за II** независимо от RL. Это стартовая балансная рекомендация; никакой надбавки «P28 ещё рано».
- При регистрации crafting профессии игрок **явно изучает два выбранных рецепта I** за две учебные квитанции; gathering — одно из двух руководств I. Это действие обучения, не автоматическое владение всем starter catalog. Остальные покупаются. Все 22 прежние starter-записи переходят в обычную логику knowledge; никакого grandfathering.
- Экзамен даёт ровно одно неизвестное знание II выбранной профессии: любой её craft-рецепт либо одно из двух gathering-руководств II. Выбор и выдача входят в подтверждение экзамена. Остальные доступны у мастера за 60g.
- Бесплатный рецепт от регионального проекта возможен как дополнительный источник того же knowledge ID, но никогда не единственный способ получить обязательный рецепт. Будущие редкие знания не входят в базовую alpha-цепочку. Бесплатные квитанции регистрации выдаются один раз на пару player/profession и считаются использованными при изучении выбранного знания; повторная регистрация или отмена UI не создаёт новые квитанции.

## 4. Профессиональный XP: новая формула и остановки

Предлагаемые пороги, без привязки к C:

```
XP_to_next(P) = 100 + 20*(P-1)    для P=1..14
XP_to_next(P) = 300 + 30*(P-16)   для P=16..29
P15: XP закрыт до экзамена
P30: конец доступной профессиональной прогрессии
```

P1→15 требует **3220 XP**; экзамен переводит в P16/XP0 без XP-платы; P16→30 требует **6930 XP**. Всего активного XP — **10150**. Overflow действия, достигшего P15 или P30, не накапливается и не переносится: состояние на границе имеет XP0; receipt показывает attempted/applied/discarded. Пока ожидается квалификация, работы всё ещё дают предметы и оплату, но applied XP=0. При входе в P16 нет скрытого банка. На P30 нет claim для III.

| Действие | Tier I S/R/C-work | Tier II S/R/C-work | Когда начисляется |
|---|---|---|---|
| Личная craft-операция, включая реальную работу по заказу | 6 /12 /18 | 12 /24 /36 | За committed изготовление, не за повторный claim, продажу или количество в stack |
| Gather/hunt processing tick | 3 /4 /5 | 6 /8 /10 | За совершённую операцию; в дикой добыче — за успешный tick, в гильдейской обработке — за проверенный этап работы |
| Покупка, учёба, NPC commission, repair, reward claim, exam confirmation | 0 | 0 | Не подменяют профессиональную практику |

Внутри своего тира нет decay по P или training ceiling: доступная простая работа способна довести до границы, сложная эффективнее за действие и дороже по входам. После получения II за I-работы применяется floor(base×0.2), минимум 1; это не новый gate. Одна immutable operation даёт XP один раз. Novelty-bonus и прежняя формула 50780 XP исключены из этой версии, чтобы не строить рост на дополнительном счётчике коллекции.

Рецептурная категория S/R/C-work явно указана в приложении. Она характеризует труд/стоимость, а не право учиться; её можно корректировать по измерениям без изменения тира. Деление/объединение партии не увеличивает XP: craft operation использует фиксированный recipe quantity, боевой reward не начисляет craft XP.

Гильдейская gathering-сессия содержит 15 этапов по 8s; текущий профиль даёт 45–75 XP за I либо 90–150 за II. Производственный заказ содержит четыре личных craft-операции по 30s с отдельными receipts, суммарно 120s; даёт 24–72 XP за I и 48–144 за II. Заготовки и изделия заказа принадлежат NPC. Нет XP за таймер без выполненной работы. Базовая оценка gather при средних 60/120 XP за 120s: около 223 минут непосредственно работы на обе шкалы; с экзаменом/покупками/перемещением ориентир **5–9 активных часов на выбранную профессию**, для самостоятельного craft с полным снабжением —8–14. Это гипотеза, не результат playtest.

## 5. Путь без боевого уровня и без другого игрока

Одного обещания «купить материалы» недостаточно при пустом кошельке. В безопасном `capital_city` доступна **гильдейская работа**: действующие NPC-службы, общий для всех каталог и физическая мастерская/садок/склад внутри существующего хаба. Это новая ограниченная профессиональная capability, не безопасная копия дикой локации и не изменение её roster.

### Три способа получить материал

1. **Оплачиваемый заказ гильдии.** NPC предоставляет защищённую партию входов и учебный инструмент. Игрок выполняет личные операции; output остаётся у NPC. За завершённые 120s —5g на I либо 10g на II. XP даётся только за операции, gold только один раз за весь заказ. Одна активная работа на персонажа; выбор нескольких профессий не позволяет запускать 12 таймеров параллельно. Тир заказа определяется его операциями, а не текущим P исполнителя: Tier I заказ у мастера II всё ещё платит 5g и даёт пониженную I-практику. В maker-заказе четыре операции одного тира по уже известным рецептам; переход к II не повышает оплату старой партии.
2. **Личная обработка партии.** Игрок выбирает нужный материал, оплачивает 2×reference value за единицу будущего результата, получает партию в escrow и лично обрабатывает её. За 120s гарантированно 3 единицы S, 2 R либо 1 C-work. Результат поступает в inventory, wage не начисляется; XP — за работу, а не покупку. Tier I/II проверяется по профессии обработчика; заемный U1/U4 доступен бесплатно и не продаётся. Ни скрытого RNG pass/fail, ни требования убить исходное существо.
3. **Покупка готового материала у NPC снабжения Астера.** Все 30 существующих и 15 новых материалов доступны за 3×reference value, без C и без требования владеть чужой профессией. XP и qualification proof не выдаются. Другой игрок/auction не нужен. Это медленнее и дороже собственной полевой добычи, но всегда доступно при заработанном gold.

В природе остаются прежние finite sources и owner harvest; сильные враги не упрощаются ради ремесленника. Богатые источники и E50 дают скорость, выбор и престиж, но не монополию на профессию. NPC stock для базовых материалов не имеет исчерпываемого общего лимита, который блокирует одиночного игрока; экономику ограничивают цена и время труда.

**Нулевая точка:** C1, gold0 → регистрация выбранной профессии → явное бесплатное обучение → оплачиваемая работа с NPC inputs/tool → покупка второго знания или личных inputs → практика до P15 → экзамен на loan inputs → P16/XP0 → работа II → P30. Для охотника NPC выдаёт лично закреплённую тушу/кокон на обработку; для рыбака — садок и учебный участок лова. Профессиональный результат добыт собственным действием. Покупка готовой шкуры не становится hunting proof. Источник `guild_work`/`profession_exam` не выполняет боевые и Chapter objectives и не вызывает character XP payout. Обычный личный craft вне этой цепочки отдельно может участвовать в приключенческом задании, если игрок его принял. В этой цепочке **character XP=0**: игрок вправе остаться C1 до P30 во всех 12 профессиях.

Работа гильдии не привязана к Chapter I, боевым J-проектам, посещению регионов или PvP. При отрицательном выборе метода/материала UI объясняет исправление; за него нет RNG-провала, платного retry или уничтожения экзамена. Результаты завершённых операций сохраняются после disconnect; повторный callback не выдаёт вторую плату. Обычные мировые действия сохраняют свои риски.

### Защита экономики

NPC escrow нельзя продать, вывести, вложить в чужой рецепт или засчитать как личный покупной sample. В оплачиваемом craft-контракте требуется уже изученный рецепт своей профессии; NPC не изготовляет вещь вместо игрока. Личный готовый товар продаётся по bounded price; общий sell всей партии ≤60% суммарной reference sell-value inputs. NPC buy3V и processing2V исключают buy→sell прибыль. Tool commissions не дают XP и не засчитываются maker exam. Инструмент, изготовленный лично для NPC-заказа или экзамена, сначала становится результатом job/exam escrow, а не заменяет инструмент в gathering-слоте игрока. Поэтому кузнецу не нужно изучать mining, чтобы изготовить и сдать контрольную кирку. Модель output destination обязана различать inventory/tool-slot и NPC escrow; это часть Epic I, а не существующая возможность current tool writer.

5g/10g за 120s —150/300g в час без учёта UI, не пассивный доход. Нельзя одновременно получить wage и готовый материал; повторное открытие UI, cancel и restart не сокращают оплачиваемую длительность. Это намеренный faucet труда, требующий измерения инфляции в Epic III. Отдельный daily cap не вводится: он нарушил бы самостоятельный непрерывный путь. Tier II рецепт 60g оплачивается шестью работами по 120s; экзаменный выбор бесплатен. Игрок не обязан выкупать весь каталог.

## 6. Добыча, инструменты и 45 материалов

Все старые ресурсы с required P≤15 относятся к I; пять старых P18 материалов — `ancient_bark`, `sunscar_ore`, `toxic_herb`, `deep_marsh_fish`, `troll_sinew` — к II. Остальные 25 — I. Все M01–M15 относятся к II. Точные material rows и гильдейские способы — Gap §5. Прежние D24/30/36 заменены категориями работы S/R/C, не перенесены в скрытый minP.

U1 даёт доступ ко всем Tier I источникам; U4 — ко всем Tier II. U2/U3/U5/U6 не открывают исключительные материалы и не нужны для экзамена. Одна известная gathering-инструкция текущего тира поддерживает все его материальные операции; вторая даёт другую организацию работы/выбор заказа, не повышает yield или XP скрытым множителем. На природе hunting остаётся owner-only, в гильдии появляется отдельный тип personally assigned specimen с собственным operation receipt.

| U | Профессиональный тир пользователя | Прочность (предложение) | BOM и роль |
|---|---|---:|---|
| 1 | I | 90 | Базовый инструмент, есть бесплатный учебный экземпляр для гильдии |
| 2 | I | 150 | Меньше остановок на ремонт, нет новых resource gates |
| 3 | I | 210 | Походный запас, тот же доступ I |
| 4 | II | 240 | Базовый инструмент всего II; BOM только из I-материалов |
| 5 | II | 300 | Дольше работает; изготовление из доступных U4 материалов |
| 6 | II | 360 | Максимум удобства альфы; не требуется собственный P30 |

Все 30 tool recipes (20 current +10 proposals) перечислены в приложении с пересмотренными BOM вместо прежнего экспоненциального wood grind. Blacksmith создаёт четыре семейства, arcane engineer — fishing. Свой craft проверяет тир/knowledge изготовителя, а использование — тир gathering профессии. Идентификатор профессии инструмента не становится требованием учить кузнеца.

NPC commission всех пяти инструментов: доступен U1–3 для gathering I и U4–6 для II, без знания crafting профессии, без посещения источника и без обязательного предыдущего U. Цена сервиса 5×U gold плюс BOM; недостающие inputs можно включить в quote по 3V. Замену/ремонт подтверждать с актуальной revision. U4 можно заказать сразу на P16 из I-материалов; U5/U6 потом из ресурсов, доступных U4. Бесплатный loan U1/U4 в гильдии гарантирует выход из состояния gold0/сломанный tool. Loan не переносится в полевую добычу и не дублируется в inventory.

## 7. Экзамен I→II: общий протокол

Единственный доступный экзамен этой альфы открывается на P15 у мастера выбранной профессии в Астере или доступном хабе. Регистрация бесплатна. Нельзя выполнить экзамен раньше P15 ради обхода XP, но можно заранее собрать золото и знания. Практические proof фиксируются **после регистрации** именно этого экзамена.

Состояния: `registered → practice_a_done + practice_b_done → sample_submitted → confirmed`. Две работы различаются recipe/source operation identity, а не количеством повторений. Контрольный образец — результат **третьей отдельной операции** из I, затем сдача одной единицы/экземпляра. Он не покупается готовым, не берётся из чужой награды и не совпадает с receipt двух практик. Сам метод deterministic; правильность определяется указанным действием и материалом, не редкостью или roll качества.

Мастер выдаёт нужные входы и loan tool для экзамена; они привязаны к exam escrow, выходы не продаются. Можно использовать свои купленные ingredients в maker trial, но craft обязан быть личным. При сдаче контрольный экземпляр списывается/закрепляется в escrow ровно один раз. UI заранее показывает расход. Для armor/weapon экзамена не требуется equip: достаточно изготовления и оценки. Для food/tonic не нужно намеренно терять HP/получать яд.

Подтверждение наставника предлагает любой неизвестный рецепт II своей профессии. Одна транзакция проверяет все proof, фиксирует звание и journal fact, устанавливает Tier II/P16/XP0, изучает выбранный рецепт и сохраняет receipt. Сбой сообщения не повторяет повышение и reward. Одновременные разные recipe choices не могут дать две книги: выигрывает один committed confirm, второй получает сохранённый результат. Неполный exam не повышает P; повторная попытка бесплатна. Отмена закрывает UI/текущий незавершённый этап, завершённые proof остаются у того же exam ID, а не порождают новый набор наград.

### Двенадцать собственных экзаменов

| Профессия | Практика A (I) | Практика B (I) | Контрольный образец (I) | Награда-звание |
|---|---|---|---|---|
| Лесоруб | Прямой распил wood_common из размеченного бревна | Выделить frostpine_wood без повреждения сердцевины | Отдельно подготовить 1 wood_dark с ровным срезом | Подмастерье-лесоруб |
| Рудокоп | Разделить железную жилу на ore и пустую породу | Выделить gem_common по видимым трещинам | Отдельно подготовить 1 stone_chunk заданной формы | Подмастерье-рудокоп |
| Травник | Разобрать herb_common и непригодные стебли | Собрать shore_herbs с сохранением корневища | Отдельно подготовить 1 marsh_herb по карточке признаков | Подмастерье-травник |
| Рыбак | Настроить глубину снасти и поймать shore_fish в учебном садке | Выбрать подходящую оснастку для marsh_fish | Отдельно обработать 1 oasis_fish без повреждения филе | Подмастерье-рыбак |
| Охотник | Снять wolf_pelt с лично выданной туши по линии разреза | Выделить spider_silk из выданного кокона | Отдельно разделать 1 boar_meat из контрольной туши | Подмастерье-охотник |
| Кузнец | Лично изготовить pe_sword_1h_01 | Лично изготовить pxe_tool_mining_1 | Третьей операцией сделать pe_sword_1h_01 и сдать этот instance | Подмастерье-кузнец |
| Арканный инженер | Лично изготовить pe_wand_01 | Лично изготовить pxe_tool_fishing_1 | Третьей операцией сделать pe_wand_01 и сдать instance | Подмастерье-инженер |
| Латник | Лично изготовить pe_heavy_chest_01 | Лично изготовить a25_H_01 boots | Третьей операцией сделать a25_H_01 и сдать instance | Подмастерье-латник |
| Кожевник | Лично изготовить trail_vest | Лично изготовить a25_M_01 boots | Третьей операцией сделать a25_M_01 и сдать instance | Подмастерье-кожевник |
| Ткач | Лично изготовить pe_light_chest_01 | Лично изготовить a25_L_01 boots | Третьей операцией сделать a25_L_01 и сдать instance | Подмастерье-ткач |
| Алхимик | Лично изготовить field_tonic | Лично изготовить field_mana | Третьей операцией сделать field_tonic для лечебницы | Подмастерье-алхимик |
| Повар | Лично изготовить trail_ration | Лично изготовить pe_cooking_shore_01 | Третьей операцией сделать pe_cooking_shore_01 и сдать порцию | Подмастерье-повар |

Все конкретные maker recipes в этой таблице принадлежат I. Если два начальных свободных выбора потрачены иначе, нужные знания покупаются по 8g; гильдейская работа по любому известному рецепту даёт этот gold без боя. Это покупка постоянного знания, не плата за retry экзамена. Gather-практики доступны через любое изученное руководство I, не требуют обеих техник. Нужные inputs доступны в exam escrow, так что умения других профессий не требуются.

## 8. Gathering-рецепты знаний: честный учёт награды экзамена

В текущих 83 craft recipes нет рецептов, владельцем которых является gathering профессия. Чтобы обещание «рецепт на выбор» работало для всех 12, вводится **20 записей gathering knowledge: 5 профессий ×2 техники ×2 тира**. Это изучаемые инструкции работы в существующей профессии, не ещё 20 craft outputs и не новые предметы. Из них 10 относятся к II и формируют по два выбора экзаменной награды. Нельзя выдавать охотнику рецепт кузнеца, который без второй профессии бесполезен.

| Knowledge ID | Профессия / тир | Инструкция |
|---|---|---|
| `gp_woodcutting_1_a` | woodcutting / 1 | Строевая заготовка |
| `gp_woodcutting_1_b` | woodcutting / 1 | Кора и связующие |
| `gp_woodcutting_2_a` | woodcutting / 2 | Раскрой сложной древесины |
| `gp_woodcutting_2_b` | woodcutting / 2 | Извлечение смол |
| `gp_mining_1_a` | mining / 1 | Рудная выборка |
| `gp_mining_1_b` | mining / 1 | Разбор кристаллов |
| `gp_mining_2_a` | mining / 2 | Слоистая руда |
| `gp_mining_2_b` | mining / 2 | Точная огранка сырья |
| `gp_herbalism_1_a` | herbalism / 1 | Лекарственный сбор |
| `gp_herbalism_1_b` | herbalism / 1 | Волокна и реагенты |
| `gp_herbalism_2_a` | herbalism / 2 | Работа с редкими травами |
| `gp_herbalism_2_b` | herbalism / 2 | Сохранение действующего вещества |
| `gp_fishing_1_a` | fishing / 1 | Пищевой улов |
| `gp_fishing_1_b` | fishing / 1 | Оснастка и обработка |
| `gp_fishing_2_a` | fishing / 2 | Глубоководный улов |
| `gp_fishing_2_b` | fishing / 2 | Масляные и плотные рыбы |
| `gp_hunting_1_a` | hunting / 1 | Разделка и шкуры |
| `gp_hunting_1_b` | hunting / 1 | Волокно и трофеи |
| `gp_hunting_2_a` | hunting / 2 | Работа с прочными тканями |
| `gp_hunting_2_b` | hunting / 2 | Чешуя и тонкое волокно |

Практическое различие A/B задаётся карточкой работы, а не статовой прибавкой:

| Профессия | Метод A | Метод B |
|---|---|---|
| Woodcutting | Разметка волокон → выбор линии распила → сортировка заготовки | Осмотр слоя → выбор глубины снятия → сохранение коры/связующего |
| Mining | Определение жилы → выбор точки отделения → сортировка руды | Осмотр трещин → отделение включения → проверка целостности |
| Herbalism | Распознавание растения → выбор зрелой части → подготовка сбора | Разделение частей → выбор режима обработки → сохранение волокна/реагента |
| Fishing | Определение глубины → настройка снасти → аккуратное извлечение | Выбор оснастки → оценка улова → разделка под заданное применение |
| Hunting | Разметка анатомических ориентиров → разделение тканей → подготовка шкуры/мяса | Выделение тонких частей → очистка волокна/трофея → проверка целостности |

Признаки и правильный способ видны в задании; ошибки исправляются без платного retry и случайного уничтожения партии. Методы используют один бюджет времени/выхода/XP, пригодны для всех материалов своего тира и не дают скрытого bonus. Их смысл — разные профессиональные действия и темы заказов. Полевой сбор сохраняет собственный RNG; эти детерминированные карточки описывают работу и экзамен при гильдии, а не превращают всю природу в гарантированную добычу.

Каждая инструкция своего тира допускает все его материалы; конкретная карточка операции выбирается по материалу. A/B дают разный подход и тематические заказы, не делают M15 исключительной собственностью одной техники. Обе можно изучить без потери первой. Суммарный реестр знаний: **153 craft-рецепта +20 gathering-инструкций =173**, из них 79 I и 94 II. Инструкции считаются отдельно, чтобы не выдавать старые 153 рецепта за уже существующий gathering catalog.

## 9. Реестр всех 153 craft-рецептов

Каждая строка ниже задаёт конечный recipe ID, профессию, старый номер для трассировки, новый RL/тир, work-category, output и полный BOM. `P прежн.` — только ссылка на baseline/V2.1, **не runtime requirement**. При RL16/18/22/24/26/28/30 recipe eligibility одинаково открывается на получении II. Никаких P32/P34/P36 recipes вне alpha не осталось. Existing IDs с числом 12/18 не переименовываются без причины; suffix не является проверкой уровня.

| Каталог | Tier I | Tier II | Всего |
|---|---:|---:|---:|
| 83 существующих | 59 | 24 | 83 |
| 70 предложенных | 10 | 60 | 70 |
| Craft итог | 69 | 84 | 153 |
| Gathering knowledge отдельно | 10 | 10 | 20 |
| Все изучаемые записи | 79 | 94 | 173 |

Old I — recipes с прежним required1/2/6/12; oldII — required18. Из новых I — armor rows01/02×3 и A01/A02/C01/C02. Остальные 60 — II; прежние 32→RL28, 34/36→RL30. RL4/8/16/22/24/26/28/30 остаётся меткой изделия, не временем доступа. Все I стоят 8g, II60g, если не выбран voucher. Старые learning25/75/150 и proposed120/220/350 заменены.

### 9.1. Все 83 существующих

| ID | Профессия | P прежн. | RL / Tier | Work | Output | BOM |
|---|---|---|---|---|---|---|
| `pe_sword_1h_01` | blacksmith | 1 | 1 / 1 | S | field_sword_1h / T1 common | iron_ore×3, coal×1, wood_common×1 |
| `pe_sword_1h_12` | blacksmith | 12 | 12 / 1 | C | field_sword_1h / T5 uncommon | iron_ore×4, coal×2, frostpine_wood×2, wolf_fang×1 |
| `pe_sword_1h_18` | blacksmith | 18 | 18 / 2 | S | field_sword_1h / T10 uncommon | sunscar_ore×3, iron_ore×3, coal×3, ancient_bark×1, troll_sinew×1 |
| `pe_sword_2h_01` | blacksmith | 1 | 1 / 1 | S | field_sword_2h / T1 common | iron_ore×4, coal×2, wood_common×1 |
| `pe_sword_2h_12` | blacksmith | 12 | 12 / 1 | C | field_sword_2h / T5 uncommon | iron_ore×6, coal×3, frostpine_wood×2, wolf_fang×1 |
| `pe_sword_2h_18` | blacksmith | 18 | 18 / 2 | S | field_sword_2h / T10 uncommon | sunscar_ore×5, iron_ore×4, coal×4, ancient_bark×1, troll_sinew×1 |
| `pe_axe_2h_01` | blacksmith | 1 | 1 / 1 | S | field_axe_2h / T1 common | iron_ore×4, coal×2, wood_common×1 |
| `pe_axe_2h_12` | blacksmith | 12 | 12 / 1 | C | field_axe_2h / T5 uncommon | iron_ore×6, coal×3, frostpine_wood×2, wolf_fang×1 |
| `pe_axe_2h_18` | blacksmith | 18 | 18 / 2 | S | field_axe_2h / T10 uncommon | sunscar_ore×5, iron_ore×4, coal×4, ancient_bark×1, troll_sinew×1 |
| `pe_daggers_01` | blacksmith | 1 | 1 / 1 | S | field_daggers / T1 common | iron_ore×3, coal×1, wolf_pelt×1 |
| `pe_daggers_12` | blacksmith | 12 | 12 / 1 | C | field_daggers / T5 uncommon | iron_ore×4, coal×2, bear_hide×1, wolf_fang×1 |
| `pe_daggers_18` | blacksmith | 18 | 18 / 2 | S | field_daggers / T10 uncommon | sunscar_ore×3, iron_ore×2, coal×2, bear_hide×1, troll_sinew×1 |
| `pe_bow_01` | arcane_engineer | 1 | 1 / 1 | S | field_bow / T1 common | wood_common×4, reed_bundle×2 |
| `pe_bow_12` | arcane_engineer | 12 | 12 / 1 | C | field_bow / T5 uncommon | frostpine_wood×4, spider_silk×2, gem_common×1 |
| `pe_bow_18` | arcane_engineer | 18 | 18 / 2 | S | field_bow / T10 uncommon | ancient_bark×3, frostpine_wood×2, spider_silk×3, troll_sinew×1 |
| `pe_magic_staff_01` | arcane_engineer | 1 | 1 / 1 | S | field_magic_staff / T1 common | wood_common×3, reed_bundle×1, herb_common×2 |
| `pe_magic_staff_12` | arcane_engineer | 12 | 12 / 1 | C | field_magic_staff / T5 uncommon | frostpine_wood×3, spider_silk×1, gem_common×1, herb_magic×1 |
| `pe_magic_staff_18` | arcane_engineer | 18 | 18 / 2 | S | field_magic_staff / T10 uncommon | ancient_bark×2, gem_common×2, spider_silk×2, herb_magic×2 |
| `pe_wand_01` | arcane_engineer | 1 | 1 / 1 | S | field_wand / T1 common | wood_common×2, reed_bundle×1, herb_common×2 |
| `pe_wand_12` | arcane_engineer | 12 | 12 / 1 | C | field_wand / T5 uncommon | frostpine_wood×2, spider_silk×1, gem_common×1, herb_magic×1 |
| `pe_wand_18` | arcane_engineer | 18 | 18 / 2 | S | field_wand / T10 uncommon | ancient_bark×1, gem_common×2, spider_silk×2, herb_magic×2 |
| `pe_holy_staff_01` | arcane_engineer | 1 | 1 / 1 | S | field_holy_staff / T1 common | wood_common×3, reed_bundle×1, shore_herbs×2 |
| `pe_holy_staff_12` | arcane_engineer | 12 | 12 / 1 | C | field_holy_staff / T5 uncommon | frostpine_wood×3, spider_silk×1, gem_common×1, shore_herbs×2 |
| `pe_holy_staff_18` | arcane_engineer | 18 | 18 / 2 | S | field_holy_staff / T10 uncommon | ancient_bark×2, gem_common×2, spider_silk×2, desert_plant×2 |
| `pe_holy_rod_01` | arcane_engineer | 1 | 1 / 1 | S | field_holy_rod / T1 common | wood_common×2, reed_bundle×1, shore_herbs×2 |
| `pe_holy_rod_12` | arcane_engineer | 12 | 12 / 1 | C | field_holy_rod / T5 uncommon | frostpine_wood×2, spider_silk×1, gem_common×1, shore_herbs×2 |
| `pe_holy_rod_18` | arcane_engineer | 18 | 18 / 2 | S | field_holy_rod / T10 uncommon | ancient_bark×1, gem_common×2, spider_silk×2, desert_plant×2 |
| `pe_tome_01` | arcane_engineer | 1 | 1 / 1 | S | field_tome / T1 common | reed_bundle×4, wolf_pelt×1, herb_common×2 |
| `pe_tome_12` | arcane_engineer | 12 | 12 / 1 | C | field_tome / T5 uncommon | reed_bundle×4, spider_silk×2, gem_common×1, herb_magic×1 |
| `pe_tome_18` | arcane_engineer | 18 | 18 / 2 | S | field_tome / T10 uncommon | reed_bundle×6, spider_silk×3, gem_common×2, ancient_bark×1 |
| `pe_shield_06` | blacksmith | 6 | 6 / 1 | R | field_shield / T5 common | iron_ore×4, coal×2, stone_chunk×2, wolf_fang×1 |
| `pe_shield_12` | blacksmith | 12 | 12 / 1 | C | field_shield / T5 uncommon | iron_ore×5, coal×2, frostpine_wood×2, bear_hide×1 |
| `pe_shield_18` | blacksmith | 18 | 18 / 2 | S | field_shield / T10 uncommon | sunscar_ore×4, iron_ore×3, coal×3, troll_sinew×1 |
| `pe_focus_06` | arcane_engineer | 6 | 6 / 1 | R | field_focus / T5 common | wood_dark×2, stone_chunk×2, reed_bundle×2 |
| `pe_focus_12` | arcane_engineer | 12 | 12 / 1 | C | field_focus / T5 uncommon | frostpine_wood×2, gem_common×1, spider_silk×2, herb_magic×1 |
| `pe_focus_18` | arcane_engineer | 18 | 18 / 2 | S | field_focus / T10 uncommon | ancient_bark×2, gem_common×2, spider_silk×2, toxic_herb×1 |
| `pe_censer_06` | arcane_engineer | 6 | 6 / 1 | R | field_censer / T5 common | wood_dark×2, stone_chunk×2, shore_herbs×2 |
| `pe_censer_12` | arcane_engineer | 12 | 12 / 1 | C | field_censer / T5 uncommon | frostpine_wood×2, gem_common×1, spider_silk×2, desert_plant×1 |
| `pe_censer_18` | arcane_engineer | 18 | 18 / 2 | S | field_censer / T10 uncommon | ancient_bark×2, gem_common×2, spider_silk×2, desert_plant×2 |
| `pe_heavy_chest_01` | heavy_armor | 1 | 1 / 1 | S | field_heavy_chest / T1 common | iron_ore×4, coal×2 |
| `pe_heavy_helmet_06` | heavy_armor | 6 | 6 / 1 | R | field_heavy_helmet / T5 common | iron_ore×3, coal×2, stone_chunk×2 |
| `pe_heavy_legs_12` | heavy_armor | 12 | 12 / 1 | C | field_heavy_legs / T5 uncommon | iron_ore×6, coal×3, gem_common×1 |
| `pe_heavy_chest_18` | heavy_armor | 18 | 18 / 2 | S | field_heavy_chest / T10 uncommon | sunscar_ore×6, iron_ore×4, coal×4, troll_sinew×2 |
| `trail_vest` | medium_armor | 1 | 1 / 1 | S | trail_vest / T1 common | wolf_pelt×2, wood_common×2 |
| `pe_medium_helmet_06` | medium_armor | 6 | 6 / 1 | R | field_medium_helmet / T5 common | wolf_pelt×2, wood_dark×1, wolf_fang×1 |
| `pe_medium_legs_12` | medium_armor | 12 | 12 / 1 | C | field_medium_legs / T5 uncommon | bear_hide×3, spider_silk×2, frostpine_wood×1 |
| `pe_medium_chest_18` | medium_armor | 18 | 18 / 2 | S | field_medium_chest / T10 uncommon | bear_hide×4, spider_silk×3, ancient_bark×1, troll_sinew×1 |
| `pe_light_chest_01` | light_armor | 1 | 1 / 1 | S | field_light_chest / T1 common | reed_bundle×4, herb_common×2 |
| `pe_light_helmet_06` | light_armor | 6 | 6 / 1 | R | field_light_helmet / T5 common | reed_bundle×3, spider_silk×1, marsh_herb×1 |
| `pe_light_legs_12` | light_armor | 12 | 12 / 1 | C | field_light_legs / T5 uncommon | spider_silk×3, reed_bundle×3, herb_magic×2 |
| `pe_light_chest_18` | light_armor | 18 | 18 / 2 | S | field_light_chest / T10 uncommon | spider_silk×4, reed_bundle×4, herb_magic×2, toxic_herb×2 |
| `field_tonic` | alchemy | 1 | 1 / 1 | S | health_potion_small ×1 | herb_common×3 |
| `field_mana` | alchemy | 2 | 2 / 1 | S | mana_potion ×1 | herb_common×5 |
| `pe_alchemy_health_06` | alchemy | 6 | 6 / 1 | R | health_potion ×1 | herb_common×3, marsh_herb×2 |
| `pe_alchemy_mana_12` | alchemy | 12 | 12 / 1 | C | pe_mana_potion_medium ×1 | herb_magic×2, desert_plant×2 |
| `pe_alchemy_health_18` | alchemy | 18 | 18 / 2 | S | pe_health_potion_large ×1 | herb_common×4, toxic_herb×2, desert_plant×1 |
| `pe_alchemy_mana_18` | alchemy | 18 | 18 / 2 | S | pe_mana_potion_large ×1 | herb_magic×3, toxic_herb×2, desert_plant×2 |
| `trail_ration` | cooking | 1 | 1 / 1 | S | field_ration ×1 | boar_meat×1, herb_common×1 |
| `pe_cooking_shore_01` | cooking | 1 | 1 / 1 | S | pe_shore_broth ×1 | shore_fish×1, shore_herbs×1 |
| `pe_cooking_marsh_06` | cooking | 6 | 6 / 1 | R | pe_marsh_stew ×1 | marsh_fish×2, marsh_herb×1, salt_crystal×1 |
| `pe_cooking_boar_12` | cooking | 12 | 12 / 1 | C | pe_boar_feast ×1 | boar_meat×3, forest_mushroom×2, salt_crystal×1 |
| `pe_cooking_oasis_12` | cooking | 12 | 12 / 1 | C | pe_oasis_meal ×1 | oasis_fish×2, desert_plant×1, salt_crystal×1 |
| `pe_cooking_deep_18` | cooking | 18 | 18 / 2 | S | pe_deep_marsh_meal ×1 | deep_marsh_fish×2, boar_meat×2, forest_mushroom×2, salt_crystal×1 |
| `pxe_tool_woodcutting_1` | blacksmith | 1 | 1 / 1 | S | U1 woodcutting | wood_common×4, iron_ore×2, coal×1 |
| `pxe_tool_woodcutting_2` | blacksmith | 6 | 6 / 1 | R | U2 woodcutting | wood_common×8, iron_ore×4, coal×2, wood_dark×2 |
| `pxe_tool_woodcutting_3` | blacksmith | 12 | 12 / 1 | C | U3 woodcutting | wood_common×12, iron_ore×6, coal×3, frostpine_wood×2, gem_common×1 |
| `pxe_tool_woodcutting_4` | blacksmith | 18 | 18 / 2 | S | U4 woodcutting | wood_common×16, iron_ore×8, coal×4, frostpine_wood×2, gem_common×1 |
| `pxe_tool_mining_1` | blacksmith | 1 | 1 / 1 | S | U1 mining | wood_common×4, iron_ore×2, coal×1 |
| `pxe_tool_mining_2` | blacksmith | 6 | 6 / 1 | R | U2 mining | wood_common×8, iron_ore×4, coal×2, wood_dark×2 |
| `pxe_tool_mining_3` | blacksmith | 12 | 12 / 1 | C | U3 mining | wood_common×12, iron_ore×6, coal×3, frostpine_wood×2, gem_common×1 |
| `pxe_tool_mining_4` | blacksmith | 18 | 18 / 2 | S | U4 mining | wood_common×16, iron_ore×8, coal×4, frostpine_wood×2, gem_common×1 |
| `pxe_tool_herbalism_1` | blacksmith | 1 | 1 / 1 | S | U1 herbalism | wood_common×4, iron_ore×2, coal×1 |
| `pxe_tool_herbalism_2` | blacksmith | 6 | 6 / 1 | R | U2 herbalism | wood_common×8, iron_ore×4, coal×2, wood_dark×2 |
| `pxe_tool_herbalism_3` | blacksmith | 12 | 12 / 1 | C | U3 herbalism | wood_common×12, iron_ore×6, coal×3, frostpine_wood×2, gem_common×1 |
| `pxe_tool_herbalism_4` | blacksmith | 18 | 18 / 2 | S | U4 herbalism | wood_common×16, iron_ore×8, coal×4, frostpine_wood×2, gem_common×1 |
| `pxe_tool_fishing_1` | arcane_engineer | 1 | 1 / 1 | S | U1 fishing | wood_common×4, iron_ore×2, coal×1 |
| `pxe_tool_fishing_2` | arcane_engineer | 6 | 6 / 1 | R | U2 fishing | wood_common×8, iron_ore×4, coal×2, wood_dark×2 |
| `pxe_tool_fishing_3` | arcane_engineer | 12 | 12 / 1 | C | U3 fishing | wood_common×12, iron_ore×6, coal×3, frostpine_wood×2, gem_common×1 |
| `pxe_tool_fishing_4` | arcane_engineer | 18 | 18 / 2 | S | U4 fishing | wood_common×16, iron_ore×8, coal×4, frostpine_wood×2, gem_common×1 |
| `pxe_tool_hunting_1` | blacksmith | 1 | 1 / 1 | S | U1 hunting | wood_common×4, iron_ore×2, coal×1 |
| `pxe_tool_hunting_2` | blacksmith | 6 | 6 / 1 | R | U2 hunting | wood_common×8, iron_ore×4, coal×2, wood_dark×2 |
| `pxe_tool_hunting_3` | blacksmith | 12 | 12 / 1 | C | U3 hunting | wood_common×12, iron_ore×6, coal×3, frostpine_wood×2, gem_common×1 |
| `pxe_tool_hunting_4` | blacksmith | 18 | 18 / 2 | S | U4 hunting | wood_common×16, iron_ore×8, coal×4, frostpine_wood×2, gem_common×1 |

### 9.2. Все 70 предложенных

| ID | Профессия | P прежн. | RL / Tier | Work | Output | BOM |
|---|---|---|---|---|---|---|
| `a25_H_01` | heavy_armor | 4 | 4 / 1 | S | field_heavy_boots / T1 common | iron_ore×2, coal×1, wood_common×1 |
| `a25_M_01` | medium_armor | 4 | 4 / 1 | S | field_medium_boots / T1 common | wolf_pelt×1, wood_common×2, reed_bundle×1 |
| `a25_L_01` | light_armor | 4 | 4 / 1 | S | field_light_boots / T1 common | reed_bundle×3, herb_common×1 |
| `a25_H_02` | heavy_armor | 8 | 8 / 1 | R | field_heavy_gloves / T5 common | iron_ore×3, coal×2, stone_chunk×1 |
| `a25_M_02` | medium_armor | 8 | 8 / 1 | R | field_medium_gloves / T5 common | wolf_pelt×2, spider_silk×1, wood_dark×1 |
| `a25_L_02` | light_armor | 8 | 8 / 1 | R | field_light_gloves / T5 common | reed_bundle×3, spider_silk×1, marsh_herb×1 |
| `a25_H_03` | heavy_armor | 16 | 16 / 2 | S | a25_heavy_resist_chest / T10 uncommon | iron_ore×6, coal×3, gem_common×1, frostpine_wood×2 |
| `a25_M_03` | medium_armor | 16 | 16 / 2 | S | a25_medium_survival_chest / T10 uncommon | bear_hide×3, spider_silk×2, wolf_fang×2 |
| `a25_L_03` | light_armor | 16 | 16 / 2 | S | a25_light_survival_chest / T10 uncommon | spider_silk×3, reed_bundle×4, herb_magic×2 |
| `a25_H_04` | heavy_armor | 22 | 22 / 2 | R | field_heavy_helmet / T15 uncommon | sunscar_ore×3, iron_ore×4, coal×3, gem_common×1 |
| `a25_M_04` | medium_armor | 22 | 22 / 2 | R | field_medium_helmet / T15 uncommon | bear_hide×2, spider_silk×2, ancient_bark×1 |
| `a25_L_04` | light_armor | 22 | 22 / 2 | R | field_light_helmet / T15 uncommon | spider_silk×3, herb_magic×2, reed_bundle×4, toxic_herb×1 |
| `a25_H_05` | heavy_armor | 24 | 24 / 2 | R | field_heavy_legs / T15 uncommon | M04×2, iron_ore×5, coal×3 |
| `a25_M_05` | medium_armor | 24 | 24 / 2 | R | field_medium_legs / T15 uncommon | M13×2, bear_hide×3, spider_silk×2 |
| `a25_L_05` | light_armor | 24 | 24 / 2 | R | field_light_legs / T15 uncommon | M07×2, spider_silk×3, reed_bundle×4 |
| `a25_H_06` | heavy_armor | 28 | 28 / 2 | C | field_heavy_boots / T20 uncommon | M04×2, sunscar_ore×3, coal×3 |
| `a25_M_06` | medium_armor | 28 | 28 / 2 | C | field_medium_boots / T20 uncommon | M01×2, bear_hide×3, spider_silk×2 |
| `a25_L_06` | light_armor | 28 | 28 / 2 | C | field_light_boots / T20 uncommon | M07×2, herb_magic×2, reed_bundle×4 |
| `a25_H_07` | heavy_armor | 32 | 28 / 2 | C | a25_heavy_precision_chest / T20 uncommon | M05×2, M04×2, iron_ore×6, coal×4 |
| `a25_M_07` | medium_armor | 32 | 28 / 2 | C | a25_medium_precision_chest / T20 uncommon | M14×2, M13×2, bear_hide×4, ancient_bark×1 |
| `a25_L_07` | light_armor | 32 | 28 / 2 | C | a25_light_support_chest / T20 uncommon | M14×2, M07×2, herb_magic×3, reed_bundle×5 |
| `a25_H_08` | heavy_armor | 36 | 30 / 2 | C | field_heavy_gloves / T20 uncommon | M06×1, M04×2, iron_ore×4, coal×3 |
| `a25_M_08` | medium_armor | 36 | 30 / 2 | C | field_medium_gloves / T20 uncommon | M15×1, M13×2, M03×1, spider_silk×3 |
| `a25_L_08` | light_armor | 36 | 30 / 2 | C | field_light_gloves / T20 uncommon | M09×1, M14×2, M03×1, reed_bundle×4 |
| `a25_sword_1h_24` | blacksmith | 24 | 24 / 2 | R | field_sword_1h / T15 uncommon | M04×2, iron_ore×4, coal×3, frostpine_wood×1 |
| `a25_sword_1h_30` | blacksmith | 30 | 30 / 2 | C | field_sword_1h / T20 uncommon | M05×2, M04×2, sunscar_ore×3, coal×4, M13×1 |
| `a25_sword_2h_24` | blacksmith | 24 | 24 / 2 | R | field_sword_2h / T15 uncommon | M04×3, iron_ore×5, coal×4, frostpine_wood×2 |
| `a25_sword_2h_30` | blacksmith | 30 | 30 / 2 | C | field_sword_2h / T20 uncommon | M05×3, M04×3, sunscar_ore×4, coal×4, M13×1 |
| `a25_axe_2h_24` | blacksmith | 24 | 24 / 2 | R | field_axe_2h / T15 uncommon | M04×3, iron_ore×5, coal×4, bear_hide×1 |
| `a25_axe_2h_30` | blacksmith | 30 | 30 / 2 | C | field_axe_2h / T20 uncommon | M05×3, M04×3, sunscar_ore×4, coal×4, M13×1 |
| `a25_daggers_24` | blacksmith | 24 | 24 / 2 | R | field_daggers / T15 uncommon | M04×2, iron_ore×3, coal×2, spider_silk×2 |
| `a25_daggers_30` | blacksmith | 30 | 30 / 2 | C | field_daggers / T20 uncommon | M05×2, M04×2, sunscar_ore×2, coal×3, M13×1 |
| `a25_bow_24` | arcane_engineer | 24 | 24 / 2 | R | field_bow / T15 uncommon | M01×2, frostpine_wood×4, spider_silk×3, M13×1 |
| `a25_bow_30` | arcane_engineer | 30 | 30 / 2 | C | field_bow / T20 uncommon | M02×3, M05×1, M13×2, spider_silk×3 |
| `a25_magic_staff_24` | arcane_engineer | 24 | 24 / 2 | R | field_magic_staff / T15 uncommon | M01×2, frostpine_wood×3, gem_common×2, herb_magic×2 |
| `a25_magic_staff_30` | arcane_engineer | 30 | 30 / 2 | C | field_magic_staff / T20 uncommon | M02×2, M05×2, M07×2, gem_common×1 |
| `a25_wand_24` | arcane_engineer | 24 | 24 / 2 | R | field_wand / T15 uncommon | M01×1, frostpine_wood×2, gem_common×2, herb_magic×2 |
| `a25_wand_30` | arcane_engineer | 30 | 30 / 2 | C | field_wand / T20 uncommon | M02×2, M05×1, M07×2, gem_common×1 |
| `a25_holy_staff_24` | arcane_engineer | 24 | 24 / 2 | R | field_holy_staff / T15 uncommon | M01×2, frostpine_wood×3, shore_herbs×4, gem_common×1 |
| `a25_holy_staff_30` | arcane_engineer | 30 | 30 / 2 | C | field_holy_staff / T20 uncommon | M02×2, M05×1, M07×2, desert_plant×2 |
| `a25_holy_rod_24` | arcane_engineer | 24 | 24 / 2 | R | field_holy_rod / T15 uncommon | M01×1, frostpine_wood×2, shore_herbs×3, gem_common×1 |
| `a25_holy_rod_30` | arcane_engineer | 30 | 30 / 2 | C | field_holy_rod / T20 uncommon | M02×2, M05×1, M07×2, desert_plant×1 |
| `a25_tome_24` | arcane_engineer | 24 | 24 / 2 | R | field_tome / T15 uncommon | M07×2, reed_bundle×5, spider_silk×3, gem_common×1 |
| `a25_tome_30` | arcane_engineer | 30 | 30 / 2 | C | field_tome / T20 uncommon | M14×2, M02×1, M07×2, reed_bundle×5 |
| `a25_precision_setting` | arcane_engineer | 24 | 24 / 2 | R | `a25_precision_ring`: accuracy/evasion для Westwild/Sunscar / T15 uncommon | M04×1, M01×1, gem_common×2 |
| `a25_reserve_setting` | arcane_engineer | 24 | 24 / 2 | R | `a25_reserve_amulet`: MP/magic defense для Ashen/Mireveil / T15 uncommon | M07×2, gem_common×2, reed_bundle×2 |
| `a25_support_setting` | arcane_engineer | 30 | 30 / 2 | C | `a25_support_amulet`: healing power/HP для группы / T20 uncommon | M05×2, M07×2, gem_common×2 |
| `a25_anchor_setting` | arcane_engineer | 30 | 30 / 2 | C | `a25_anchor_ring`: HP/accuracy для melee / T20 uncommon | M04×2, M13×2, gem_common×2 |
| `a25_resin_salve` | alchemy | 4 | 4 / 1 | S | a25_resin_salve ×1 | dry_reagent×2, herb_common×2 |
| `a25_antivenom` | alchemy | 8 | 8 / 1 | R | a25_antivenom ×1 | marsh_herb×2, shore_herbs×2, salt_crystal×1 |
| `a25_clear_sight` | alchemy | 16 | 16 / 2 | S | a25_clear_sight ×1 | dry_reagent×2, desert_plant×2, gem_common×1 |
| `a25_mana_infusion` | alchemy | 24 | 24 / 2 | R | a25_mana_infusion ×1 | M07×1, herb_magic×2, marsh_mushroom×2 |
| `a25_cleanse_draught` | alchemy | 30 | 30 / 2 | C | a25_cleanse_draught ×1 | M08×1, M10×1, toxic_herb×2 |
| `a25_balanced_elixir` | alchemy | 36 | 30 / 2 | C | a25_balanced_elixir ×1 | M09×1, M12×1, M03×1, herb_magic×2 |
| `a25_mushroom_soup` | cooking | 4 | 4 / 1 | S | a25_mushroom_soup ×1 | marsh_mushroom×2, herb_common×1, shore_fish×1 |
| `a25_dry_ration` | cooking | 8 | 8 / 1 | R | a25_dry_ration ×1 | boar_meat×2, dry_reagent×1, salt_crystal×1 |
| `a25_hunters_stew` | cooking | 16 | 16 / 2 | S | a25_hunters_stew ×1 | boar_meat×2, forest_mushroom×2, shore_herbs×2 |
| `a25_oil_fish_broth` | cooking | 24 | 24 / 2 | R | a25_oil_fish_broth ×1 | M10×1, marsh_mushroom×2, marsh_herb×1 |
| `a25_long_trail_meal` | cooking | 30 | 30 / 2 | C | a25_long_trail_meal ×1 | M11×1, M08×1, boar_meat×2, salt_crystal×1 |
| `a25_deepwater_supper` | cooking | 36 | 30 / 2 | C | a25_deepwater_supper ×1 | M12×1, M09×1, forest_mushroom×2, salt_crystal×1 |
| `a25_tool_woodcutting_5` | blacksmith | 26 | 26 / 2 | R | U5 woodcutting | wood_common×20, iron_ore×10, coal×5, M01×1, M04×1 |
| `a25_tool_woodcutting_6` | blacksmith | 34 | 30 / 2 | C | U6 woodcutting | wood_common×24, iron_ore×12, coal×6, M01×2, M04×2, M05×1 |
| `a25_tool_mining_5` | blacksmith | 26 | 26 / 2 | R | U5 mining | wood_common×20, iron_ore×10, coal×5, M01×1, M04×1 |
| `a25_tool_mining_6` | blacksmith | 34 | 30 / 2 | C | U6 mining | wood_common×24, iron_ore×12, coal×6, M01×2, M04×2, M05×1 |
| `a25_tool_herbalism_5` | blacksmith | 26 | 26 / 2 | R | U5 herbalism | wood_common×20, iron_ore×10, coal×5, M01×1, M04×1 |
| `a25_tool_herbalism_6` | blacksmith | 34 | 30 / 2 | C | U6 herbalism | wood_common×24, iron_ore×12, coal×6, M01×2, M04×2, M05×1 |
| `a25_tool_fishing_5` | arcane_engineer | 26 | 26 / 2 | R | U5 fishing | wood_common×20, iron_ore×10, coal×5, M01×1, M04×1 |
| `a25_tool_fishing_6` | arcane_engineer | 34 | 30 / 2 | C | U6 fishing | wood_common×24, iron_ore×12, coal×6, M01×2, M04×2, M05×1 |
| `a25_tool_hunting_5` | blacksmith | 26 | 26 / 2 | R | U5 hunting | wood_common×20, iron_ore×10, coal×5, M01×1, M04×1 |
| `a25_tool_hunting_6` | blacksmith | 34 | 30 / 2 | C | U6 hunting | wood_common×24, iron_ore×12, coal×6, M01×2, M04×2, M05×1 |

### 9.3. Свойства новых outputs и полезность

Шесть armor chest templates: rows03 — heavy_resist/medium_survival/light_survival; rows07 — heavy_precision/medium_precision/light_support, с префиксом `a25_`. Перенести 20% secondary budget в указанное направление, без увеличения total budget и без unique effects. Standard weapons/boots/gloves/helmet/legs используют текущий field template с указанным T. Новые рецепты не создают отдельную weapon family. Два поздних craft output шага T15/T20 доступны всем десяти семействам.

| ID | Практическое свойство |
|---|---|
| a25_resin_salve | Мазь: восстановление 25% maxHP только вне боя; дешёвый sink сухого реагента. Восстановление |
| a25_antivenom | Подготовка следующего боя: первые два poison effect короче на 1 возможность, минимум 1. Подготовка |
| a25_clear_sight | +8% accuracy rating на первые 3 возможности следующего боя; не гарантированное попадание. Подготовка |
| a25_mana_infusion | +12% maxMP на следующий бой; увеличивает ёмкость, но не заполняет MP бесплатно. Восстановление |
| a25_cleanse_draught | Снять один poison effect с себя в PvE за обычную боевую возможность. Подготовка |
| a25_balanced_elixir | +8% maxHP и maxMP на следующий бой, без мгновенного заполнения. Восстановление |
| a25_mushroom_soup | Вне боя восстановить 15% HP и 15% MP; доступное смешанное восстановление. Походное питание |
| a25_dry_ration | +6% maxHP на следующий бой без заполнения; ранний запас выносливости. Походное питание |
| a25_hunters_stew | +6% accuracy rating и +4% maxHP на следующий бой. Питание под задачу |
| a25_oil_fish_broth | +8% maxMP на следующий бой без заполнения; подготовка caster. Питание под задачу |
| a25_long_trail_meal | Вне боя восстановить 30% HP и 20% MP; быстрое дорогое снабжение вдали от inn. Походное питание |
| a25_deepwater_supper | +6% physical defense rating и +6% magic defense rating на следующий бой, не процент иммунитета. Питание под задачу |

Один food и один preparation slot; подтверждение замены; увеличение maxHP/MP не заполняет их бесплатно. Cleanse тратит обычную боевую возможность. Эти эффекты должны реально исполняться в evaluator, а не только описываться в каталоге. Craft/exam не требуют их применения на себе. Щит/focus/censer сохраняют свой путь advancement до T20; новых рецептов сверх 153 для симметрии не добавлять.

## 10. Новая схема и доказательство корректности

Для fresh DB нужны: единый profession state (player/profession/tier/P/XP/revision), knowledge, technique metadata, exam state/proof, sample escrow, guild job/input ownership, tool ownership/loan и operation/reward receipts. Это логические сущности; Sol сначала сопоставляет их действующим owners, затем представляет точный DDL без параллельных источников истины. Разрешено заменить устаревшие CHECK1..20 и schema validators; нет задачи переносить P16–20 тестовых персонажей или исторические receipts.

Новая история должна быть корректна: `operation_id` уникален и принадлежит игроку; `exam(player,profession,target_tier)` единственный; практики A/B/control не используют один operation повторно; выдача gold/knowledge/title и расход sample атомарны. Restart нового runtime восстанавливает новые jobs/exams и replay новых receipts. Это текущая надёжность системы, а не backward compatibility. Не нужны recognition path, grandfathered recipes, сохранение тестовых cutover snapshots, upgrade rehearsal старой схемы или компенсация старых покупок.

Старая локальная БД не удаляется этой design-работой. При реализации используется чистая изолированная тестовая БД; замена dev schema и локальный reset оформляются явно в Epic, без фонового удаления чужих файлов. Обновить seeds/fixtures вместе со схемой, чтобы тесты проверяли новую архитектуру, а не заставляли сохранять отменённые ограничения.

Затрагиваемые owners: `profession_progression.py`, `gathering_progression.py`, `profession_schema.py`, `database.py`, `profession_recipes.py`, `recipe_knowledge.py`, `profession_resources.py`, `profession_tools.py`, `crafting_runtime.py`, `gathering_runtime.py`, `hunting.py`, `economy_actions.py`, `resource_handbook.py`, profession/recipe handlers и RU/EN/ES. Узкая новая служба guild jobs/exams нужна, общий achievement/guild/auction framework — нет.

## 11. Acceptance новой системы

1. Для каждой из 12 профессий свежий C1/gold0, без Chapter I/боёв/других игроков, проходит 1→15, экзамен, 16→30; C и character XP остаются неизменными. Нет обязательного своего кузнеца, добытчика или gear trade.
2. На P1 все I recipes eligible, на P16 все II, включая RL30; знание и inputs остаются отдельными. Negative cases: чужая профессия, II доэкзамена, unknown recipe. На P17/P29 не появляется новое скрытое условие.
3. Пороговые cases P14→15, награда на P15, экзамен→P16/0, P29→30, XP на P30. Overflow не становится банком и claim не начисляет его позже.
4. Все 12 экзаменов проверяют две разные практики и отдельный sample из I. Bought finished item, чужой receipt, reused operation, незавершённая работа и двойной confirm не проходят. Retry/disconnect бесплатны и не теряют выполненный proof.
5. Все 153 BOM имеют sources/knowledge/consumer. Все 20 gather manuals доступны по tier. U4 bootstrap из I, U5/U6 из U4; loan и repair восстанавливают тупик gold0. Необязательные grades не превращаются в material gates.
6. Guild jobs: одна активность, корректный elapsed/commit, изоляция NPC escrow, один wage, без одновременно wage+materials, cancel/restart не размножает inputs. Купленные ингредиенты допускаются в maker trial, но не заменяют личный craft.
7. Fresh DB init→restart, новый exam/job restart, конкурентные операции и rollback не оставляют частичную выплату. Нужны focused unit/integration tests и реальные journeys; полный pytest в текущем проектировании не запускать.
8. Предмет создаётся при низком C; equip отдельно принимает/отклоняет по фактическим req fields. Food/tonic эффекты проходят targeted evaluator checks. RU/EN/ES показывают тир, знание, цену, материалы, proof и cap, без внутренних IDs.

## 12. Источники и передача реализации

Подтверждение владельца: [Issue #241](https://github.com/danyasemennikov/rpg-bot/issues/241#issuecomment-6172833671). Кодовая основа: [recipes](https://github.com/danyasemennikov/rpg-bot/blob/36368178541510d0d6794117ef17843722c52846/rpg/game/profession_recipes.py), [resources](https://github.com/danyasemennikov/rpg-bot/blob/36368178541510d0d6794117ef17843722c52846/rpg/game/profession_resources.py), [tools](https://github.com/danyasemennikov/rpg-bot/blob/36368178541510d0d6794117ef17843722c52846/rpg/game/profession_tools.py), [gear instance authority](https://github.com/danyasemennikov/rpg-bot/blob/36368178541510d0d6794117ef17843722c52846/rpg/game/gear_instances.py), [field catalog](https://github.com/danyasemennikov/rpg-bot/blob/36368178541510d0d6794117ef17843722c52846/rpg/game/field_catalog.py). Полный список крупных Epic — [Roadmap](ALPHA_1_25_IMPLEMENTATION_ROADMAP.md), источники 45 материалов — [Gap Matrix](CONTENT_GAP_MATRIX.md).

## Оставшиеся продуктовые решения

| ID | Действительно открытый выбор | Рекомендация / что зависит |
|---|---|---|
| D1 | Поведение character XP на C25: hard cap без банка либо ограниченный reserve | Hard cap без будущей конвертации, при сохранении gold/items; reserve потребует отдельной экономики. Это не вопрос профессионального P15/P30 — там остановка уже утверждена |
| D2 | Enhancement alpha: новые улучшения до +9 либо новый источник essence | +9 и T20; не вводить обязательный E50 reagent. Источник +10…+12 — отдельное продуктовое расширение |
| D3 | Целевой размер организованной группы для E46–50 и политика присоединения | Четыре C25, без масштабирования статов; подтвердить допустимость дополнительных участников и распределение reward budget |
| D4 | Роль безопасного гильдейского труда в экономике | Повторяемая оплачиваемая работа и медленная обработка материалов в Астере, без daily lock. Она гарантирует независимость от боя, но медленнее добычи в мире; не превращать её в бесплатную раздачу |

Конкретные 12 экзаменов, XP/цены/тайминги и budgets переданы как готовые рекомендации для ревью; их настройка не требует заново выбирать уже утверждённую модель тиров. Условия агрессии и предупреждений V2.1 также проходят ревью перед Epic II. Не переоткрывать P30/P120, сам экзамен, остановку XP, свободу профессий и техник или необходимость совместимости со старыми тестовыми данными.
