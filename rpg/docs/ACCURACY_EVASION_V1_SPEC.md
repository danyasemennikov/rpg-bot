# ACCURACY_EVASION_V1_SPEC.md

## 1. Назначение документа

Этот документ фиксирует дизайн системы **Accuracy / Evasion** для Telegram RPG-бота.

Цель системы:
- убрать риск неуязвимых уклонистов;
- сохранить fantasy уклончивых и техничных билдов;
- не заставлять melee-архетипы покупать чужой основной стат только ради базовой работоспособности;
- встроить hit / dodge rules в уже существующий единый turn pipeline;
- подготовить фундамент под будущее PvP и group combat без последующей полной переписи.

Это **design-spec**, а не numeric tuning document.  
Здесь фиксируются:
- роли Accuracy и Evasion;
- их место в боевой системе;
- общие правила расчёта;
- связи со статами, оружием и скиллами;
- ограничения, которые нельзя нарушать при внедрении.

---

## 2. Scope

В scope этого документа входит:
- hostile single-target hit logic;
- базовая модель Accuracy и Evasion;
- взаимодействие с weapon families;
- взаимодействие с status effects и skill tags;
- правила для turn-based боя;
- guardrails для PvE и PvP;
- безопасная рамка для последующего внедрения.

В scope **не входит**:
- финальный numeric tuning;
- точные коэффициенты формул;
- полный redesign skill trees;
- отдельная новая state-модель;
- broad refactor вне боевого resolution layer.

---

## 3. Главный принцип системы

Accuracy и Evasion становятся **отдельными боевыми secondary stats**, но они **не существуют отдельно от identity билда**.

Система строится не по модели:

- `Agility vs Intuition`

и не по модели

- `всё решают только вторички на шмоте`

А по модели:

- **weapon-native precision**
- **primary-stat-derived scaling**
- **gear secondaries**
- **skill/setup modifiers**
- **bounded hit formula with soft caps**

То есть итоговое попадание определяется не одним статом, а **контролируемой системой из нескольких слоёв**, где каждый архетип имеет свой естественный путь к точности и свой естественный способ защиты от вражеской точности.

---

## 4. Design goals

Система обязана выполнять следующие задачи.

### 4.1. Не допускать неуязвимых уклонистов
Пассивный Evasion не должен позволять строить билд, против которого равный по силе противник стабильно “не играет”.

### 4.2. Не ломать melee identity
Мили-билды не должны быть обязаны качать Intuition ради базовой способности попадать по evasive targets.

### 4.3. Сохранять различия weapon families
Разные семьи оружия должны иметь разные профили:
- кто-то лучше в raw accuracy;
- кто-то лучше в anti-evasion setup;
- кто-то хуже попадает в лоб, но лучше наказывает через окна;
- кто-то живёт за счёт tempo и defensive windows.

### 4.4. Работать в пошаговой боёвке
Miss/dodge в turn-based бою ощущается сильно, поэтому система не должна создавать частые пустые ходы.

### 4.5. Поддерживать PvP-ready foundation
Даже до полноценного PvP формулы уже должны ограничивать токсичные стратегии:
- вечный dodge;
- невозможность попасть без одного обязательного стата;
- слишком сильные длинные defensive loops.

### 4.6. Встраиваться в текущую архитектуру
Система должна жить в общем combat resolution, а не как хаотичные куски логики в handlers.

---

## 5. Термины

### Accuracy
Боевой offensive stat, который определяет надёжность попадания по hostile target.

### Evasion
Боевой defensive stat, который определяет способность цели избегать hostile targeted actions.

### Hit check
Проверка, проходит ли действие через слой Accuracy / Evasion.

### Action accuracy class
Класс точности самого действия:
- `precise`
- `standard`
- `heavy`
- `wide`
- опционально `unerring`

### Defensive window
Короткое временное состояние, в котором цель получает усиленную защиту от targeted actions.

### Setup
Подготовительное действие, создающее окно для более сильного payoff.

### Payoff
Действие, которое конвертирует подготовленное окно в урон, контроль или иное преимущество.

---

## 6. Core model

### 6.1. Общая идея
Каждое hostile action против цели проходит через общий hit layer.

На hit result влияют:
- Accuracy атакующего;
- Evasion цели;
- accuracy-class действия;
- активные modifiers и conditions;
- специальные skill tags.

### 6.2. Effective Accuracy
Итоговая точность атакующего собирается из:
- family baseline;
- action bonus;
- primary-stat scaling;
- gear Accuracy;
- buffs;
- conditions;
- skill-specific modifiers.

### 6.3. Effective Evasion
Итоговое уклонение цели собирается из:
- base Evasion;
- Agility-driven scaling;
- gear Evasion;
- buffs;
- defensive windows;
- situational modifiers;
- debuff reductions.

### 6.4. Принцип сравнения
Hit chance строится вокруг разницы:

`Effective Accuracy - Effective Evasion`

Но эта разница не должна скейлиться линейно бесконечно.  
Система обязана использовать:
- ограничение swing’а;
- diminishing returns;
- нижний floor;
- верхний cap.

---

## 7. Базовые правила hit resolution

### 7.1. Accuracy и Evasion применяются только там, где это логично
Не каждое действие обязано проходить одинаковую проверку.

Система должна различать:

#### `targeted`
Обычный targeted hostile action.  
Полноценная проверка Accuracy vs Evasion.

#### `wide_targeted`
Широкое или менее точное hostile action.  
Evasion учитывается частично.

#### `field/zone`
Поле, зона, lingering effect.  
Evasion либо учитывается слабо, либо не является основным защитным слоем.

#### `unerring`
Редкий тег для действий, которые intentionally bypass evasion.  
Используется очень ограниченно и только за явную цену.

### 7.2. Miss не должен быть слишком частым
В пошаговой игре miss — это потеря целого действия.  
Поэтому обычные действия против обычных целей должны попадать часто.

### 7.3. Evasion не должен полностью выключать бой
Даже dedicated evasive target должен оставаться уязвимым:
- для specialist accuracy families;
- для setup windows;
- для anti-evasion skills;
- для correct tactical play.

### 7.4. Accuracy не должен полностью убирать dodge
Даже specialist accuracy build не должен делать Evasion бесполезным stat’ом.  
Система должна сохранять полезность dodge как defensive identity.

---

## 8. Ограничения для пошаговой боёвки

Это критически важный раздел.

### 8.1. Пассивный постоянный dodge не может быть главным power budget уклончивой ветки
В turn-based бою длинный высокий пассивный dodge слишком токсичен.

### 8.2. Главная сила уклончивых веток должна быть в окнах, а не в постоянной неуязвимости
Сильные defensive effects должны быть:
- короткими;
- читаемыми;
- привязанными к timing;
- ограниченными по длительности и частоте.

### 8.3. Payoff-удары не должны сидеть на голом RNG
Если ветка требует setup и timing, то её payoff-удар обязан иметь controlled reliability:
- bonus accuracy;
- partial evasion ignore;
- особое правило против prepared target;
- или другой понятный stabilizer.

### 8.4. Бой не должен превращаться в серию пустых ходов
Игрок не должен регулярно терять 2–3 полных действия подряд только потому, что цель накопила слишком много raw Evasion.

---

## 9. Связь с primary stats

### 9.1. Agility
Agility — главный источник:
- Evasion;
- части Accuracy для agile / physical / tempo archetypes.

Agility **не должна** становиться статом “всё и сразу”.  
Она даёт:
- сильное влияние на Evasion;
- умеренное или family-dependent влияние на Accuracy;
- tempo identity.

Agility не должна одновременно:
- быть лучшей защитой;
- быть лучшей точностью;
- быть лучшим offensive scaler для всех.

### 9.2. Intuition
Intuition — главный Accuracy stat для:
- magic-focused families;
- части ranged families;
- caster/hybrid precision profiles.

Intuition не является обязательным anti-evasion stat для всех melee.

### 9.3. Strength
Strength не даёт сильный общий прямой бонус к Accuracy.  
Иначе силовые мили-билды получат слишком много “бесплатной надёжности”.

Путь Strength-based archetypes к попаданию должен идти через:
- family baseline;
- setup skills;
- punish windows;
- anti-evasion tags на отдельных skills.

### 9.4. Vitality
Vitality не должна давать прямую Accuracy или Evasion.  
Её роль:
- HP;
- стойкость;
- длинные размены;
- survival budget.

### 9.5. Wisdom
Wisdom не должна быть универсальным Accuracy stat.  
Support / holy builds не должны получать:
- ману;
- лечение;
- holy power;
- high reliability against all evasive targets
одновременно без цены.

### 9.6. Luck
Luck не должен быть главным постоянным источником Accuracy или Evasion.  
Его роль:
- crit;
- burst volatility;
- payoff enhancement;
- assassin-style spikes;
- niche interactions.

---

## 10. Weapon-family design rules

Здесь фиксируются не цифры, а **профили поведения**.

### 10.1. `daggers`
#### Общая роль
Высокий tempo, окна уязвимости, evasive play, точечный burst, высокая цена хорошего тайминга.

#### Design rule
`daggers` не должны жить за счёт бесконечного пассивного dodge.  
Их сила должна сидеть в:
- tempo;
- defensive windows;
- bait;
- setup -> payoff;
- burst conversion.

#### `Venom`
Линия давления и ослаблений.  
Она меньше зависит от raw Evasion и больше от:
- poison pressure;
- weaken / slow / attrition;
- payoff по already compromised target.

#### `Skirmisher`
Эта ветка **не определяется как “максимальный постоянный Evasion”**.  
Её правильное определение:

**уклончивая tempo-burst ветка, которая создаёт короткое defensive окно, вскрывает цель и конвертирует это окно в burst.**

Для `Skirmisher` обязательно:
- `Smoke Bomb` = short defensive window, а не длинная полубессмертность;
- `Feint Step` = setup / bait / opening tool;
- `Backstab` = payoff skill с повышенной надёжностью по prepared target;
- `Shadow Chain` = finisher по уже вскрытой цели, а не обычная лотерея на hit roll.

### 10.2. `sword_1h`
Надёжный melee baseline.

Должен иметь:
- выше среднего стабильность попадания;
- хороший control-based anti-evasion path;
- не лучший raw anti-evasion burst, но хороший practical reliability.

### 10.3. `bow`
Одна из главных natural accuracy families.

#### `Sniper`
Один из лучших профилей против evasive targets через:
- mark;
- precise shots;
- prepared payoff.

#### `Ranger`
Меньше raw precision, больше tempo-control reliability.

### 10.4. `sword_2h`
#### `Executioner`
Менее надёжен, но сильнее в тяжёлых окнах.

#### `Blademaster`
Один из лучших melee precision profiles:
- техника;
- sequence;
- стабильный hit behavior;
- хорошая игра против evasive targets без чужого stat tax.

### 10.5. `axe_2h`
Слабее в raw reliability против evasive targets.  
Компенсирует это через:
- pressure;
- armor break;
- punish windows;
- bleed / attrition;
- high value per landed hit.

Не должен получать bow-level reliability.

### 10.6. `magic_staff`
Один из сильнейших caster accuracy profiles.  
Но тяжёлые nukes могут быть менее точными, чем precise control / setup casts.

### 10.7. `holy_staff`
У offensive branch должен быть рабочий путь к точности через:
- family baseline;
- judgment / mark-like setup;
- precise holy payoff windows.

Healing/support branch не должен платить большим accuracy budget без необходимости.

### 10.8. `wand`
Очень хороший single-target precision caster profile.  
Один из лучших specialist anti-evasion casters.

### 10.9. `holy_rod`
Средний baseline, но сильная reliability в своих setup windows.  
Не должен получать бесплатно и tankiness, и support value, и high passive accuracy.

### 10.10. `tome`
Не specialist по raw hit chance.  
Его сила:
- adaptability;
- support accuracy buffs;
- enemy evasion debuffs;
- flexible hybrid play.

---

## 11. Action accuracy classes

Каждое hostile action должно иметь accuracy class.

### 11.1. `precise`
Высокая надёжность попадания.  
Используется для:
- aimed shots;
- prepared strikes;
- precision spells;
- payoff-ударов, которые должны чувствоваться “заслуженно надёжными”.

### 11.2. `standard`
Нормальный baseline.  
Используется для:
- обычных атак;
- большинства рабочих direct skills.

### 11.3. `heavy`
Тяжёлые коммит-удары.  
Ниже по надёжности, выше по payoff.

### 11.4. `wide`
Широкие, размашистые, конусные, полузональные действия.  
Меньше зависят от точной дуэли Accuracy vs Evasion.

### 11.5. `unerring`
Редкий тег.  
Используется только когда дизайн конкретного skill’а явно требует bypass evasion.

`unerring` не должен становиться массовой заплаткой на баланс.

---

## 12. Skill tags и framework-правила

Скиллы могут влиять на hit logic через framework tags.

Допустимые направления:
- `accuracy_bonus`
- `evasion_bonus`
- `accuracy_penalty`
- `evasion_penalty`
- `ignore_target_evasion_pct`
- `guaranteed_hit`
- `guaranteed_dodge`
- `mark_target`
- `judged_target`
- `prepared_strike`
- `wide_accuracy_mode`

### 12.1. Правило по anti-evasion design
Лучшие anti-evasion skills должны давать не только flat Accuracy, но и один из controlled tools:
- partial evasion ignore;
- special rules against marked target;
- accuracy class upgrade;
- target treated as exposed / off-balance.

Это лучше, чем просто бесконечно поднимать сырую Accuracy.

---

## 13. Buff / debuff interactions

### 13.1. `slow`
Должен умеренно снижать Effective Evasion или мешать tempo-defense.

### 13.2. `blind`
Должен снижать Effective Accuracy targeted actions.  
Штраф может быть разным для:
- physical targeted;
- ranged targeted;
- magic targeted;
- wide/zone skills.

### 13.3. `mark`
Главный clean anti-evasion setup.  
Должен:
- повышать reliability союзных payoff-ударов;
- или снижать Evasion цели;
- или давать special interaction для signature skills.

### 13.4. `accuracy up`
Обычный bounded buff к Effective Accuracy.

### 13.5. `evasion down`
Обычный bounded debuff к Effective Evasion.

### 13.6. `guaranteed_hit`
Редкий эффект.  
Обходит обычный hit roll, но не обязан автоматически обходить:
- immunity;
- block;
- parry;
если это отдельно не прописано.

### 13.7. `guaranteed_dodge`
Редкий эффект.  
Используется как:
- dodge next targeted attack;
- dodge during one very short window;
- one-action protection.

Не должен заменять нормальную evasion economy.

---

## 14. Defensive layers separation

Очень важно не смешивать разные защитные слои.

### Evasion
Защита от попадания targeted action.

### Block
Отдельный защитный слой, если попали.

### Parry
Отдельный reactive defense / counter layer.  
Не равен evasion.

### Immunity
Отдельный абсолютный слой, если он предусмотрен механикой.

### Damage mitigation
Работает после успешного попадания.

Система не должна сваливать:
- dodge,
- parry,
- block,
- immunity
в одну и ту же сущность.

---

## 15. Formula direction

Финальные цифры не фиксируются этим документом, но направление фиксируется.

### 15.1. Формула не должна быть бесконечно линейной
Нельзя использовать модель, где рост Accuracy или Evasion линейно и без потолка уводит chance в абсурд.

### 15.2. Обязательны
- diminishing returns;
- нижний floor;
- верхний cap;
- ограниченный swing.

### 15.3. Ориентиры по feeling
Система должна ощущаться так:
- обычная атака против обычной цели попадает часто;
- evasive target ощущается неприятным, но не ломает бой;
- specialist anti-evasion tools заметно помогают;
- тяжёлые удары чувствуют цену коммита;
- payoff после setup ощущается надёжнее, чем случайный raw attack.

### 15.4. Numeric tuning — отдельный этап
Точные значения:
- base hit chance;
- family baselines;
- stat coefficients;
- cap/floor;
- diminishing returns curve
должны фиксироваться отдельно при balance pass.

---

## 16. Gear rules

Accuracy и Evasion могут существовать как вторички на экипировке, но должны подчиняться архетипам предметов.

### 16.1. Gear не заменяет identity
Шмот должен:
- корректировать профиль;
- усиливать роль;
- поддерживать гибридизацию;
но не должен переписывать archetype с нуля.

### 16.2. Средняя броня
Главный дом для:
- Accuracy;
- Evasion;
- tempo-related physical secondaries.

### 16.3. Лёгкая броня
Может умеренно давать Evasion, но не должна становиться главным источником raw dodge для всех.

### 16.4. Тяжёлая броня
Почти не должна давать высокий Evasion.  
Не должна становиться полноценным источником dodge-танка.

### 16.5. Оружие
Оружие должно нести значимую часть family-specific accuracy identity.

### 16.6. Аксессуары
Аксессуары — главный инструмент точечной коррекции:
- немного поднять Accuracy;
- немного добрать Evasion;
- поддержать гибрид;
- усилить niche profile.

---

## 17. PvE guardrails

### 17.1. Обычные мобы
По обычным мобам равного уровня промахи должны быть редкими.

### 17.2. Evasive mobs
Такие враги должны:
- отличаться;
- требовать уважения;
- лучше наказываться правильным setup’ом;
но не должны превращать бой в серию пустых ходов.

### 17.3. Боссы
Босс не должен строиться вокруг постоянного высокого dodge, если это не специально созданный encounter-фэнтези.

### 17.4. Specialist tools
Mark, anti-evasion shots, precision spells и подобные механики должны быть полезными, но не обязательными для любого обычного PvE.

---

## 18. PvP guardrails

Даже до отдельной PvP-системы эта модель должна соблюдать следующие ограничения.

### 18.1. Нельзя допускать
- неуязвимых уклонистов;
- обязательный один meta-stat для всех;
- постоянные длинные dodge loops;
- билд, который одновременно имеет high passive evasion, strong burst и high safety без trade-off.

### 18.2. Допустимы
- короткие defensive windows;
- burst punish после setup;
- specialist anti-evasion families;
- высокая skill expression через timing.

### 18.3. Evasive build должен побеждать не за счёт “ты не играешь”
Он должен побеждать за счёт:
- bait;
- ритма;
- окна;
- позиционного преимущества в терминах пошаговой экономики;
- правильной конвертации шанса в урон.

---

## 19. Правила specifically для `daggers / Skirmisher`

Это отдельный зафиксированный раздел, чтобы позже не убить ветку “по дороге”.

### 19.1. Определение ветки
`Skirmisher` — это не ветка про максимальный пассивный Evasion.

`Skirmisher` — это ветка про:
- короткие evasive windows;
- bait;
- setup;
- вход в спину;
- burst-conversion;
- темповую дуэль.

### 19.2. Что нельзя делать с веткой
Нельзя строить силу ветки только через:
- высокий пассивный dodge;
- сырой raw Evasion stacking;
- длинные defensive баффы без цены.

### 19.3. Что обязательно должно быть у ветки
- короткое сильное defensive окно;
- хотя бы один reliable setup tool;
- хотя бы один payoff skill с controlled reliability;
- слабее длинный лобовой размен, чем у pressure/attrition веток;
- высокая награда за timing и sequence.

### 19.4. Что должно происходить с ключевыми skills
#### `Smoke Bomb`
Это short defensive window, а не длинная полунеуязвимость.

#### `Feint Step`
Это bait / reposition / setup, а не просто ещё один удар.

#### `Quick Slice`
Это рабочая tempo-кнопка, а не главный burst tool.

#### `Backstab`
Это signature payoff skill.  
Он не должен оставаться чистой лотереей после успешного setup.

#### `Shadow Chain`
Это finisher по уже открытой или надломленной цели.

---

## 20. Совместимость с текущей архитектурой

### 20.1. Общий принцип
Система должна быть встроена в общий combat resolution layer.

### 20.2. Что не надо делать
Не надо:
- тащить новую боевую математику в handlers;
- изобретать отдельную state-system;
- делать broad refactor battle_state без необходимости.

### 20.3. Что должно использоваться
Следует опираться на уже существующие semantic hooks:
- `weapon_profile`
- `armor_class`
- `offhand_profile`
- `damage_school`
- `encumbrance`

### 20.4. Где должна жить логика
#### `game/balance.py`
- formula helpers;
- derived stats;
- hit chance helpers;
- soft caps / DR.

#### `game/combat.py`
- общий hit check;
- action class handling;
- precedence order defensive layers;
- integration в turn pipeline.

#### `game/skill_engine.py`
- framework tags;
- skill result modifiers;
- setup/payoff interactions.

#### `handlers/*`
- только orchestration, UI, logging.

---

## 21. Safe rollout plan

Это не часть внедрения прямо сейчас, а зафиксированный безопасный порядок на потом.

### Шаг 1
Добавить formula helpers и derived stat layer без изменения skill trees.

### Шаг 2
Встроить общий `resolve_hit_check(...)` в combat resolution для normal attacks и direct hostile skills.

### Шаг 3
Подключить weapon-family baselines.

### Шаг 4
Подключить primary-stat scaling и gear-derived Accuracy/Evasion.

### Шаг 5
Подключить базовые conditions:
- mark
- blind
- slow
- accuracy up
- evasion down

### Шаг 6
Подключить skill tags:
- precise
- heavy
- wide
- guaranteed_hit
- guaranteed_dodge
- ignore_target_evasion_pct

### Шаг 7
Делать numeric tuning и regression pass.

---

## 22. Regression expectations

После внедрения система обязана проверяться на следующие типы кейсов:
- normal attack и direct skill используют один и тот же hit layer;
- равные обычные бойцы имеют высокий практический hit rate;
- dedicated evasion build не уводит equal matchup в абсурд;
- specialist accuracy families реально чувствуют преимущество;
- `Skirmisher` остаётся живой веткой и не теряет fantasy;
- payoff-скиллы после setup ощущаются надёжнее;
- `blind`, `mark`, `slow` ведут себя предсказуемо;
- `guaranteed_hit` и `guaranteed_dodge` имеют понятный precedence;
- DoT после успешного применения не рероллит hit каждый тик;
- AoE / wide / zone actions не ломаются из-за single-target evasion model.

---

## 23. Final design decision

Для проекта фиксируется следующее решение:

**Accuracy и Evasion являются отдельными боевыми secondary stats.  
Их итоговые значения формируются из weapon-family identity, профильных primary stats, gear secondaries и setup / skill modifiers.  
Counterplay между Accuracy и Evasion должен идти через bounded formulas, short defensive windows, specialist anti-evasion tools и setup -> payoff логику, а не через обязательный universal stat tax или бесконечный пассивный dodge.**
