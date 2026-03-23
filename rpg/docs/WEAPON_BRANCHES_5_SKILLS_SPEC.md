# WEAPON_BRANCHES_5_SKILLS_SPEC.md

## Назначение

Этот файл фиксирует **design-spec по всем weapon families** под новый стандарт:

# 5 skills per branch

Это **не implementation plan** и **не giant PR blueprint**.

Это документ про:
- структуру веток;
- fantasy и role identity;
- gameplay loop веток;
- trade-offs;
- понимание, какие skills уже хорошо ложатся в новую систему, а где нужны новые.

Главная цель файла:
- собрать weapon trees в целостную систему;
- сделать ветки более полными и вариативными;
- не размыть identity;
- дать понятную основу для дальнейшего family-by-family внедрения.

---

## 1. Общие правила для ветки на 5 skills

Ветка из 5 skills должна быть не просто “на 2 кнопки больше”, а полноценным мини-набором роли.

Нормальный каркас ветки:

1. **Entry / Setup skill**
   - открывает ротацию;
   - задаёт окно силы;
   - накладывает метку, стойку, яд, opening, shield-state, slow и т.д.

2. **Core repeatable skill**
   - рабочая кнопка ветки;
   - используется чаще всего;
   - не обязана быть самой сильной.

3. **Utility / Control / Survival skill**
   - защитный, контрольный, ресурсный или позиционный инструмент;
   - делает ветку не просто пакетом урона.

4. **Payoff / Conversion skill**
   - превращает setup в реальную выгоду;
   - consume mark / punish opening / explode poison / shatter slow / scale from shield.

5. **Capstone / High-commitment skill**
   - вершина фантазии ветки;
   - не обязательно “самая большая цифра”, но обязательно самый сильный identity-piece.

---

## 2. Power budget

Рекомендуемое распределение power budget внутри ветки:
- Setup — **15%**
- Core repeatable — **25%**
- Utility / Control / Survival — **20%**
- Payoff — **20%**
- Capstone — **20%**

### Почему так
Если все 5 кнопок будут одинаково сильными, игрок не почувствует форму ветки.
Если почти вся сила уедет в один “ульт”, ветка станет плоской.

Нужен баланс между:
- частотой использования;
- utility value;
- payoff moments;
- fantasy peak.

---

## 3. Как не ломать pacing

У каждой ветки должен быть свой боевой ритм.

Базовые типы ритма:

### 3.1. Tempo branch
- короткие окна;
- частые решения;
- меньше пик, выше гибкость.

### 3.2. Pressure branch
- стабильное давление;
- setup → payoff loops;
- средняя длина окна.

### 3.3. Commit branch
- редкие тяжёлые прожимы;
- высокая цена ошибки;
- высокий payoff при правильном использовании.

### Правило для одной family
Две ветки внутри одной weapon family **не должны иметь одинаковый темп**.
Иначе они будут ощущаться как перекрашенные версии одного дерева.

---

## 4. Как не превратить дерево в “больше кнопок = просто больше силы”

Жёсткие design-правила:

1. В ветке должно быть **не больше 2 чисто уронных кнопок**.
2. В ветке должна быть **минимум 1 utility/control/defensive** кнопка.
3. В ветке должна быть **минимум 1 setup → payoff связка**.
4. Capstone не должен быть просто “ещё один сильный удар”, если ветка уже burst-oriented.
5. Ветка не должна одновременно иметь:
   - лучший burst;
   - лучший sustain;
   - лучший safety.
6. Гибридные ветки не должны обгонять pure-ветки в их профильной задаче.

---

## 5. Статус пометок внутри документа

Для каждого skill используется одна из пометок:
- **existing** — уже хорошо известен и уже явно ложится в новую структуру;
- **existing concept** — идея уже есть в старых docs / логике ветки, но точный id или текущая реализация не зафиксированы здесь;
- **new** — новый skill, который логично добавить;
- **rework** — старый skill лучше переопределить, чем тащить как есть.

---

# 6. Weapon families

---

## 6.1. `sword_1h`

### Общая роль family
Фронтлайн, удержание, контроль, защитный бой, надёжный melee core.

### Ветка A — Guardian / Frontline
**Fantasy:** страж, защитник, удержание линии.  
**Gameplay identity:** лучшая стартовая ветка для tank/frontliner.  
**Rhythm:** pressure-control / defensive tempo.  
**Trade-offs:** высокий control и safety, но слабый пик урона.

#### Skills
1. **Sword Rush** — opener / engage / initial pressure  
   Статус: **existing**
2. **Defensive Stance** — core defensive posture / stability tool  
   Статус: **existing**
3. **Shield Bash** — control / hold / punish overextension  
   Статус: **new**
4. **Parry** — anti-burst timing tool  
   Статус: **existing**
5. **Counter** — payoff за правильный defensive timing  
   Статус: **existing**

#### Комментарий
Эта ветка уже ближе всех к новой модели. Ей нужен не второй “удар”, а один нормальный control/hold skill.

### Ветка B — Vanguard / Offensive
**Fantasy:** давит, вскрывает, наказывает opening.  
**Gameplay identity:** pressure sword, а не танк со щитом.  
**Rhythm:** pressure / commit windows.  
**Trade-offs:** выше темп и payoff, ниже надёжность.

#### Skills
1. **Driving Slash** — рабочий offensive opener  
   Статус: **new**
2. **Expose Guard** — setup через opening / vulnerability  
   Статус: **new**
3. **Press the Line** — tempo self-buff на короткое окно  
   Статус: **new**
4. **Punishing Cut** — payoff по opened/vulnerable target  
   Статус: **new**
5. **Vanguard Surge** — capstone pressure burst  
   Статус: **new**

#### Комментарий
Смысл ветки — не копировать blademaster, а быть именно offensive sword with payoff windows.

### Итог по family
- Уже имеет хороший фундамент.
- Требует **малого redesign** до полного стандарта 5 skills.

---

## 6.2. `daggers`

### Общая роль family
Ассасин, уклонение, крит, яды, tempo-punish, opportunism.

### Ветка A — Poison / Pressure
**Fantasy:** травит, душит, ломает эффективность врага.  
**Gameplay identity:** pressure assassin, а не burst-only killer.  
**Rhythm:** pressure / attrition.  
**Trade-offs:** слабее мгновенный пик, сильнее длинный бой.

#### Skills
1. **Envenom Blades** — яд на оружие / setup window  
   Статус: **new**
2. **Toxic Cut** — основной repeatable poison hit  
   Статус: **new**
3. **Crippling Venom** — slow / weaken / tempo debuff  
   Статус: **new**
4. **Backstab** — payoff по poisoned/slowed/opened target  
   Статус: **existing**
5. **Venom Burst** — explode / convert poison stacks  
   Статус: **new**

### Ветка B — Evasion / Skirmisher
**Fantasy:** уклонился, вышел в окно, наказал.  
**Gameplay identity:** мобильный оппортунист.  
**Rhythm:** tempo / burst windows.  
**Trade-offs:** высокий safety через окна, но зависимость от тайминга.

#### Skills
1. **Smoke Bomb** — evasive defensive window  
   Статус: **existing**
2. **Feint Step** — mobility / read / opening setup  
   Статус: **new**
3. **Quick Slice** — быстрый рабочий удар после tempo окна  
   Статус: **new**
4. **Backstab** — punish skill по slow/opening  
   Статус: **existing**
5. **Shadow Chain** — capstone multi-hit punish  
   Статус: **new**

### Итог по family
- Уже имеет подтверждённый evasive slice.
- Ближе всех к новой системе после `sword_1h`.
- Требует **малого/среднего redesign**.

---

## 6.3. `bow`

### Общая роль family
Ranged physical DPS, pressure from distance, target selection, tempo control.

### Ветка A — Sniper
**Fantasy:** отметил цель, подготовился, снял.  
**Gameplay identity:** лучший ranged single-target payoff.  
**Rhythm:** setup → commit payoff.  
**Trade-offs:** медленнее, уязвимее под pressure, зато сильный пик.

#### Skills
1. **Hunter’s Mark** — mark setup  
   Статус: **existing concept**
2. **Aimed Shot** — core precise shot  
   Статус: **existing concept**
3. **Steady Aim** — consistency / accuracy / crit preparation  
   Статус: **new**
4. **Piercing Arrow** — payoff по marked/armored target  
   Статус: **new**
5. **Deadeye** — capstone commit shot  
   Статус: **new**

### Ветка B — Ranger / Mobile
**Fantasy:** держит дистанцию, кайтит, ломает ритм врага.  
**Gameplay identity:** tempo archer.  
**Rhythm:** tempo / control.  
**Trade-offs:** ниже пик, выше удобство и контроль.

#### Skills
1. **Quick Shot** — core fast ranged pressure  
   Статус: **existing concept**
2. **Hamstring Arrow** — slow / kite setup  
   Статус: **new**
3. **Reposition** — defensive mobility tool  
   Статус: **new**
4. **Volley Step** — mobile multi-hit pressure  
   Статус: **new**
5. **Rain of Barbs** — capstone ranged tempo field  
   Статус: **new**

### Итог по family
- Foundation уже хорошо описывает обе роли.
- Требует **среднего redesign**.

---

## 6.4. `sword_2h`

### Общая роль family
Тяжёлый melee DPS через технику, burst windows, stance play, commit pressure.

### Ветка A — Executioner / Razing Blade
**Fantasy:** тяжёлые удары, бронепробой, добивание.  
**Gameplay identity:** commit-burst melee.  
**Rhythm:** commit.  
**Trade-offs:** высокий пик урона, меньше safety и utility.

#### Skills
1. **Heavy Swing** — базовый тяжёлый удар  
   Статус: **existing concept**
2. **Armor Split** — setup через penetration / defense break  
   Статус: **new**
3. **Executioner’s Focus** — self-buff на следующее окно урона  
   Статус: **new**
4. **Cleave Through** — payoff по wounded/debuffed target  
   Статус: **new**
5. **Executioner’s Stroke** — capstone finisher  
   Статус: **new**

### Ветка B — Blademaster
**Fantasy:** стойки, техника, серия, тайминг.  
**Gameplay identity:** skillful sustained melee.  
**Rhythm:** tempo / technique.  
**Trade-offs:** ниже лобовой burst, выше consistency.

#### Skills
1. **Battle Stance** — setup stance  
   Статус: **new**
2. **Twin Cut** — core combo strike  
   Статус: **new**
3. **Riposte Step** — defensive timing tool  
   Статус: **new**
4. **Flowing Combo** — payoff после стойки/серии  
   Статус: **new**
5. **Master’s Sequence** — capstone sequence attack  
   Статус: **new**

### Итог по family
- Идентичность хорошая.
- Риск пересечения с `sword_1h` и `axe_2h`, поэтому нужна аккуратная развязка ролей.
- Требует **среднего redesign**.

---

## 6.5. `axe_2h`

### Общая роль family
Варвар, bruiser, pressure through pain, anti-armor, heavy trading.

### Ветка A — Berserker
**Fantasy:** риск, ярость, жизнь через давление.  
**Gameplay identity:** агрессивный bruiser sustain/pressure.  
**Rhythm:** pressure / commit windows.  
**Trade-offs:** высокий sustained pressure, но реальная цена в безопасности.

#### Skills
1. **Rage Call** — self-buff через риск  
   Статус: **rework** (опирается на существующий `berserker`)
2. **Savage Chop** — core repeatable strike  
   Статус: **new**
3. **Blooded Resolve** — conditional sustain / pain-to-power tool  
   Статус: **new**
4. **Frenzy Chain** — payoff when enraged / low safety  
   Статус: **new**
5. **Last Roar** — capstone risky burst/sustain peak  
   Статус: **new**

### Ветка B — Ravager
**Fantasy:** рвёт броню, кровит, ломает жирных.  
**Gameplay identity:** anti-tank / anti-bruiser attrition.  
**Rhythm:** pressure / heavy hits.  
**Trade-offs:** меньше мобильности, больше crushing pressure.

#### Skills
1. **Bleeding Cut** — bleed setup  
   Статус: **existing concept**
2. **Sunder Armor** — armor break utility  
   Статус: **new**
3. **Brutal Overhead** — core heavy anti-armor hit  
   Статус: **new**
4. **Reopen Wounds** — payoff on bleed/armor break  
   Статус: **new**
5. **Ravage** — capstone anti-fat-target punish  
   Статус: **new**

### Итог по family
- Очень хорош для варварского архетипа.
- Нужно следить, чтобы не забрал и burst-мечника, и танка одновременно.
- Требует **среднего redesign**.

---

## 6.6. `magic_staff`

### Общая роль family
Pure offensive caster, артиллерийный маг, raw damage, прокаст, массовый урон.

### Ветка A — Destruction
**Fantasy:** артиллерия, raw power, максимум offensive output.  
**Gameplay identity:** лучший чистый offensive caster.  
**Rhythm:** commit casting.  
**Trade-offs:** высокий пик, слабая живучесть.

#### Skills
1. **Fireball** — базовый offensive cast  
   Статус: **existing concept**
2. **Arcane Surge** — setup offensive amplification  
   Статус: **new**
3. **Flame Wave** — multi-target pressure  
   Статус: **existing concept**
4. **Arcane Lance** — payoff single-target nuke  
   Статус: **new**
5. **Cataclysm** — capstone large commit cast  
   Статус: **new**

### Ветка B — Control
**Fantasy:** замедлил, остановил, выиграл дистанцией и темпом.  
**Gameplay identity:** safer control mage.  
**Rhythm:** tempo / control.  
**Trade-offs:** меньше raw damage, выше безопасность.

#### Skills
1. **Frost Bolt** — core slow application  
   Статус: **existing concept**
2. **Ice Shackles** — stronger control setup  
   Статус: **new**
3. **Mana Shield** — defensive utility  
   Статус: **new**
4. **Shatter** — payoff against slowed/frozen target  
   Статус: **new**
5. **Absolute Zero** — capstone control field  
   Статус: **new**

### Итог по family
- Старый Fire/Ice flavour стоит сохранить на уровне fantasy/skills.
- Но design-level рамка лучше описывается как Destruction / Control.
- Требует **среднего redesign**.

---

## 6.7. `holy_staff`

### Общая роль family
Pure healer / support caster / holy magic.

### Ветка A — Healing
**Fantasy:** главный хил, хоты, стабильность группы.  
**Gameplay identity:** лучший pure healer.  
**Rhythm:** sustain / support.  
**Trade-offs:** медленный соло-damage, высокая стабильность.

#### Skills
1. **Heal** — core single-target heal  
   Статус: **existing concept**
2. **Regeneration** — HoT / sustain setup  
   Статус: **existing**
3. **Cleanse** — debuff removal / anti-control utility  
   Статус: **new**
4. **Blessing** — throughput / support buff  
   Статус: **existing**
5. **Resurrection** — capstone safety trigger / comeback tool  
   Статус: **existing**

### Ветка B — Light
**Fantasy:** свет как защита и кара.  
**Gameplay identity:** support-damage holy caster.  
**Rhythm:** support / payoff windows.  
**Trade-offs:** хуже pure-heal throughput, выше solo comfort.

#### Skills
1. **Smite** — core holy hit  
   Статус: **existing concept**
2. **Radiant Ward** — shield-like protection  
   Статус: **new**
3. **Judgment Mark** — setup holy vulnerability  
   Статус: **new**
4. **Sanctified Burst** — payoff on judged target  
   Статус: **new**
5. **Halo of Dawn** — capstone support-damage pulse  
   Статус: **new**

### Итог по family
- Уже имеет несколько сильных existing anchors.
- Требует **малого/среднего redesign**.

---

## 6.8. `wand`

### Общая роль family
Темповый маг, быстрый кастер, single-target pressure, control through speed and sequencing.

### Ветка A — Arcanist
**Fantasy:** быстрые заклинания, серия, проки, магический темп.  
**Gameplay identity:** самый быстрый offensive caster.  
**Rhythm:** tempo.  
**Trade-offs:** ниже burst, выше частота решений.

#### Skills
1. **Arcane Bolt** — core spam cast  
   Статус: **new**
2. **Spell Echo** — setup proc / repeat effect  
   Статус: **new**
3. **Quick Channel** — cycle acceleration utility  
   Статус: **new**
4. **Overload** — payoff after short spell chain  
   Статус: **new**
5. **Arcane Barrage** — capstone rapid-cast burst window  
   Статус: **new**

### Ветка B — Duelist
**Fantasy:** маг-дуэлянт, timing, offhand, короткие циклы.  
**Gameplay identity:** single-target pressure caster with defense tricks.  
**Rhythm:** tempo / duel control.  
**Trade-offs:** меньше артиллерийского пика, больше гибкости в размене.

#### Skills
1. **Dueling Ward** — defensive setup  
   Статус: **new**
2. **Hex Bolt** — core duel pressure cast  
   Статус: **new**
3. **Mana Feint** — trick / disruption / timing utility  
   Статус: **new**
4. **Counterpulse** — payoff vs active/marked target  
   Статус: **new**
5. **Duel Arc** — capstone short-cycle punish  
   Статус: **new**

### Итог по family
- Концепт в foundation сильный, но реализация ещё сырая.
- Требует **глубокого redesign**.

---

## 6.9. `holy_rod` / `holy_wand`

### Общая роль family
Боевой жрец, паладин, защитный саппорт-гибрид, holy bruiser-support.

### Ветка A — Protector
**Fantasy:** щиты, self-heal, защитные ауры, front support.  
**Gameplay identity:** лучший дом для paladin / battle priest.  
**Rhythm:** sustain / protection.  
**Trade-offs:** не pure healer и не pure tank.

#### Skills
1. **Sacred Shield** — protective setup  
   Статус: **new**
2. **Mend Self** — self-heal / sustain core  
   Статус: **new**
3. **Aura of Resolve** — party/frontline utility  
   Статус: **new**
4. **Aegis Strike** — payoff that scales from active protection  
   Статус: **new**
5. **Guardian Light** — capstone protection burst  
   Статус: **new**

### Ветка B — Judicator / Punishing Light
**Fantasy:** карающий свет, устойчивый наказующий бой.  
**Gameplay identity:** holy bruiser with punishment windows.  
**Rhythm:** pressure / punish.  
**Trade-offs:** выше solo kill speed, ниже support ceiling.

#### Skills
1. **Judgment** — setup holy mark  
   Статус: **new**
2. **Radiant Strike** — core holy attack  
   Статус: **new**
3. **Consecration** — zone / tempo utility  
   Статус: **new**
4. **Punish the Wicked** — payoff on judged target  
   Статус: **new**
5. **Final Verdict** — capstone commit strike  
   Статус: **new**

### Итог по family
- Важнейший дом для paladin fantasy.
- Очень высокий риск сделать “умеет всё сразу”, поэтому нужен жёсткий trade-off control.
- Требует **глубокого redesign**.

---

## 6.10. `tome` / `grimoire`

### Общая роль family
Максимально гибкий magical toolbox, hybrid schools, support-control-experimenter.

### Ветка A — Enchanter / Support
**Fantasy:** баффер, дебаффер, магические щиты, управление темпом.  
**Gameplay identity:** toolbox support, не лучший heal и не лучший damage dealer.  
**Rhythm:** control / support.  
**Trade-offs:** высокая гибкость, низкий пик.

#### Skills
1. **Arcane Shield** — basic protective support tool  
   Статус: **new**
2. **Weaken** — debuff core  
   Статус: **new**
3. **Insight** — resource/tempo support buff  
   Статус: **new**
4. **Dispel Script** — utility strip / cleanse / deny  
   Статус: **new**
5. **Grand Enchantment** — capstone support window  
   Статус: **new**

### Ветка B — Researcher / Hybrid Schools
**Fantasy:** экспериментатор, собирает эффекты разных школ.  
**Gameplay identity:** главный дом для weird hybrid caster builds.  
**Rhythm:** adaptive / combo.  
**Trade-offs:** максимальная ширина, минимальный профильный пик.

#### Skills
1. **Hybrid Missile** — flexible offensive baseline  
   Статус: **new**
2. **Borrowed Flame** — magic-side setup  
   Статус: **new**
3. **Borrowed Grace** — holy-side support setup  
   Статус: **new**
4. **Synthesis** — payoff after mixed school usage  
   Статус: **new**
5. **Forbidden Thesis** — capstone hybrid conversion tool  
   Статус: **new**

### Итог по family
- Один из самых интересных design-узлов во всём проекте.
- Но именно здесь проще всего случайно сломать role boundaries.
- Требует **глубокого redesign**.

---

# 7. Existing skills, которые уже хорошо ложатся в новую модель

### Точно хорошо ложатся
- `sword_rush`
- `parry`
- `defensive_stance`
- `counter`
- `smoke_bomb`
- `backstab`
- `berserker` (скорее как rework anchor)
- `blessing`
- `regeneration`
- `resurrection`

### Existing concepts, которые почти наверняка стоит сохранить
- `Hunter’s Mark`
- базовые aimed / quick bow shots
- fire / ice staff identity
- базовые heal / smite / holy protection concepts

---

# 8. Где скорее всего придётся добавлять новые skills

Почти гарантированно новые skills понадобятся:
- у `bow` — для явной setup/payoff лестницы;
- у `sword_2h` — для разведения executioner и blademaster;
- у `axe_2h` — для ясного bruiser/anti-armor разделения;
- у `magic_staff` — для более глубокой разницы между raw damage и control;
- у `wand` — почти целиком;
- у `holy_rod` — почти целиком;
- у `tome` — почти целиком.

---

# 9. Где лучше rework / merge, а не просто плодить новые кнопки

### `sword_1h`
- не делать три полуветки сразу;
- жёстко держать две роли: Guardian и Vanguard.

### `daggers`
- не давать poison-ветке полный evasive package;
- safety должен жить в skirmisher-ветке.

### `magic_staff`
- старый Fire/Ice flavour можно сохранить,
  но системно лучше думать в рамках Destruction / Control.

### `axe_2h`
- `berserker` лучше не копировать как есть,
  а переработать в более ясный risk-reward anchor.

### `holy_staff` / `holy_rod`
- не раздавать одновременно лучший heal, лучший shield и сильный burst.

### `tome`
- не превращать в “псевдо-всё-оружие”;
- его сила должна быть в гибкости, а не в лучшем пике.

---

# 10. Master plan по глубине redesign

## Уже почти готовы
1. `sword_1h`
2. `daggers`

## Потребуют малого/среднего redesign
3. `holy_staff`
4. `bow`
5. `magic_staff`

## Потребуют среднего redesign
6. `axe_2h`
7. `sword_2h`

## Потребуют глубокого redesign
8. `wand`
9. `holy_rod`
10. `tome`

---

# 11. Рекомендуемый порядок будущего внедрения family-by-family

1. `sword_1h`
2. `daggers`
3. `bow`
4. `holy_staff`
5. `magic_staff`
6. `axe_2h`
7. `sword_2h`
8. `wand`
9. `holy_rod`
10. `tome`

### Почему такой порядок
- сначала families, где уже есть смерженные slice-ы и понятный фундамент;
- потом ranged / caster families с уже хорошим identity;
- в конце — самые гибридные и самые рискованные системы.

---

# 12. Как использовать этот файл дальше

Этот документ лучше использовать так:
- как design source of truth для нового чата;
- как основу для family-specific specs;
- как контрольный чеклист перед задачами для Codex;
- как фильтр против бессистемного разрастания skills.

Этот файл **не нужно** конвертировать в один giant implementation plan.
Его задача — задавать форму и порядок, а не толкать проект в один огромный PR.
