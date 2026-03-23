# WEAPON_BRANCHES_5_SKILLS_FINAL_DESIGN.md

## Назначение

Этот файл фиксирует **финальный дизайн-каркас weapon branches** под стандарт:

**2 ветки на weapon family, 5 skills на ветку.**

Это **design source of truth**, а не implementation plan.
Документ нужен, чтобы дальше спокойно идти в техничку family-by-family без постоянного переизобретения ролей, фантазии веток и состава skills.

---

## 1. Общие правила

### 1.1. Каркас любой ветки
Каждая ветка должна содержать:
1. **Setup / Entry skill** — открывает ротацию, создаёт окно силы.
2. **Core repeatable skill** — рабочая кнопка ветки.
3. **Utility / Control / Survival skill** — делает ветку не просто пакетом урона.
4. **Payoff skill** — конвертирует setup в выгоду.
5. **Capstone skill** — вершина fantasy и силы ветки.

### 1.2. Жёсткие ограничения
- В ветке не больше **2 чисто уронных** skills.
- В ветке минимум **1 utility / control / defensive** skill.
- В ветке минимум **1 setup -> payoff** связка.
- Одна ветка внутри family не должна быть просто “та же ветка, но с другими именами”.
- Pure ветки должны быть лучше гибридов в своей профильной роли.
- Гибриды должны брать **шириной и гибкостью**, а не лучшим пиком.

### 1.3. Ритмы веток
Внутри одной family ветки должны отличаться по ритму:
- **tempo** — короткие окна, частые решения;
- **pressure** — стабильное давление, setup -> payoff;
- **commit** — редкие тяжёлые прожимы, высокая цена ошибки.

### 1.4. Статусы skills
- **existing** — уже есть и хорошо ложится в новую модель.
- **existing concept** — концепт уже живёт в docs / старой логике.
- **new** — новый skill.
- **rework** — старый anchor, который лучше переработать.

---

# 2. Финальный дизайн по weapon families

## 2.1. `sword_1h`

### Общая роль family
Универсальный melee-фундамент: фронтлайн, стабильность, понятные размены, хороший старт для melee-билдов.

---

### Ветка A — **Guardian**
**Fantasy:** меч и щит, контроль размена, удержание линии.  
**Role:** defensive frontline / tanky bruiser.  
**Rhythm:** pressure-control / reactive.  
**Чем выигрывает:** стабильность, безопасность, контроль темпа, контр-игра.  
**Чем платит:** низкий burst, слабее дожим, зависимость от правильного тайминга.

#### Skills
1. **Sword Rush** — engage / opener  
   Статус: **existing**
2. **Defensive Stance** — defensive setup / stability  
   Статус: **existing**
3. **Shield Bash** — control + debuff + hold tool  
   Статус: **new**
4. **Parry** — reactive defense / anti-burst  
   Статус: **existing**
5. **Counter** — payoff punish after successful defense  
   Статус: **existing**

#### Важные правила
- `Shield Bash` должен быть **не stun-кнопкой**, а skill’ом про **stagger / off-balance / weaken**.
- Guardian не должен убивать быстрее offensive branches.
- Сила ветки — в безопасном темпе и наказании за лобовой заход в неё.

---

### Ветка B — **Vanguard**
**Fantasy:** наступающий мечник, вскрывает защиту и дожимает.  
**Role:** offensive pressure melee.  
**Rhythm:** pressure / commit.  
**Чем выигрывает:** вскрытие, темп, дожим, сильные payoff-окна.  
**Чем платит:** ниже безопасность и хуже длинный defensive exchange.

#### Skills
1. **Driving Slash** — offensive opener  
   Статус: **new**
2. **Expose Guard** — setup debuff / opening  
   Статус: **new**
3. **Press the Line** — short tempo self-buff  
   Статус: **new**
4. **Punishing Cut** — payoff hit into exposed target  
   Статус: **new**
5. **Vanguard Surge** — capstone pressure finisher  
   Статус: **new**

#### Важные правила
- Не тянуть сюда сильную reactive defense из Guardian.
- Ветка должна побеждать через давление и вскрытие, а не через “тоже стоит, но больнее бьёт”.

---

## 2.2. `daggers`

### Общая роль family
Высокий skill-expression, окна уязвимости, темп, яды, уклонение, точечный burst.

---

### Ветка A — **Venom**
**Fantasy:** травит, ломает эффективность цели, дожимает надломленного врага.  
**Role:** pressure assassin / attrition melee.  
**Rhythm:** pressure / attrition.  
**Чем выигрывает:** длительное давление, ослабление, сильная игра против жирных целей.  
**Чем платит:** слабее мгновенный burst, медленнее раскрытие.

#### Skills
1. **Envenom Blades** — poison setup  
   Статус: **new**
2. **Toxic Cut** — core poison strike  
   Статус: **new**
3. **Crippling Venom** — weaken / slow / anti-tempo debuff  
   Статус: **new**
4. **Widow’s Kiss** — payoff strike into poisoned / weakened / vulnerable target  
   Статус: **new**
5. **Rupture Toxins** — capstone poison conversion / burst  
   Статус: **new**

#### Важные правила
- `Backstab` сюда не тащить.
- Ветка должна убивать через накопленное давление, а не через критовый пик из ниоткуда.

---

### Ветка B — **Evasion / Skirmisher**
**Fantasy:** уклонился, поймал момент, ударил в спину, добил серией.  
**Role:** evasive assassin / tempo burst duelist.  
**Rhythm:** tempo / burst.  
**Чем выигрывает:** окна безопасности, высокий burst в правильный момент, очень живая ротация.  
**Чем платит:** сильная зависимость от тайминга и слабее затяжной лобовой бой.

#### Skills
1. **Smoke Bomb** — evasive defensive window  
   Статус: **existing**
2. **Feint Step** — bait / mobility / setup  
   Статус: **new**
3. **Quick Slice** — core tempo strike  
   Статус: **new**
4. **Backstab** — signature crit burst payoff  
   Статус: **existing**
5. **Shadow Chain** — capstone finishing sequence  
   Статус: **new**

#### Важные правила
- `Backstab` — фирменная burst-кнопка именно этой ветки.
- Ветка не должна иметь attrition-силу poison line.

---

## 2.3. `bow`

### Общая роль family
Физический ranged DPS, работа с дистанцией, mark-логика, контроль темпа и прицельный дожим.

---

### Ветка A — **Sniper**
**Fantasy:** отметил цель, выждал момент, снял.  
**Role:** single-target ranged payoff.  
**Rhythm:** setup -> commit payoff.  
**Чем выигрывает:** сильнейший точечный выстрел, mark-синергия, надёжный ranged finisher.  
**Чем платит:** медленнее, хуже при близком давлении, слабее в частом reposition.

#### Skills
1. **Hunter’s Mark** — mark setup  
   Статус: **existing concept**
2. **Aimed Shot** — core precise shot  
   Статус: **existing concept**
3. **Steady Aim** — consistency / crit prep / focus window  
   Статус: **new**
4. **Piercing Arrow** — payoff into marked or armored target  
   Статус: **new**
5. **Deadeye** — capstone commit shot  
   Статус: **new**

---

### Ветка B — **Ranger**
**Fantasy:** держит дистанцию, кайтит, ломает ритм преследователя.  
**Role:** tempo ranged control.  
**Rhythm:** tempo / control.  
**Чем выигрывает:** безопасная игра, дистанционный контроль, удобный соло-плей.  
**Чем платит:** ниже пик по одной цели, слабее clean finish, чем у Sniper.

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

#### Важные правила
- Sniper — про точность и commit.
- Ranger — про контроль дистанции и tempo.
- Ranger не должен убивать лучше Sniper, а Sniper не должен кайтить лучше Ranger.

---

## 2.4. `sword_2h`

### Общая роль family
Тяжёлый меч: техника, мощные коммит-удары, стойки, дисциплина, высокий melee-payoff.

---

### Ветка A — **Executioner**
**Fantasy:** тяжёлый клинок, бронепробой, добивание раненого врага.  
**Role:** commit burst melee.  
**Rhythm:** commit.  
**Чем выигрывает:** высокий пик урона, punishment windows, сильный finisher.  
**Чем платит:** ниже безопасность, слабее мелкие tempo-циклы.

#### Skills
1. **Heavy Swing** — base heavy strike  
   Статус: **existing concept**
2. **Armor Split** — defense break setup  
   Статус: **new**
3. **Executioner’s Focus** — next-hit power setup  
   Статус: **new**
4. **Cleave Through** — payoff into wounded / broken target  
   Статус: **new**
5. **Executioner’s Stroke** — capstone finisher  
   Статус: **new**

---

### Ветка B — **Blademaster**
**Fantasy:** мастер клинка, стойки, серия, техника, ритм.  
**Role:** skillful sustained melee.  
**Rhythm:** tempo / technique.  
**Чем выигрывает:** последовательность, стабильность, техничные размены.  
**Чем платит:** ниже лобовой burst-пик, чем у Executioner.

#### Skills
1. **Battle Stance** — stance setup  
   Статус: **new**
2. **Twin Cut** — core combo strike  
   Статус: **new**
3. **Riposte Step** — defensive timing reposition  
   Статус: **new**
4. **Flowing Combo** — payoff after stance / sequence  
   Статус: **new**
5. **Master’s Sequence** — capstone combo finisher  
   Статус: **new**

#### Важные правила
- `sword_2h` не должен пересекаться с `sword_1h` по defensive identity.
- Executioner — про тяжёлый commit.
- Blademaster — про техничный sustained loop.

---

## 2.5. `axe_2h`

### Общая роль family
Варварский bruiser: риск, ярость, тяжёлые размены, bleed, анти-броня.

---

### Ветка A — **Berserker**
**Fantasy:** ярость, сила через боль, агрессия как выживание.  
**Role:** risk-reward bruiser.  
**Rhythm:** pressure / commit.  
**Чем выигрывает:** высокий sustained pressure, опасные окна при низкой безопасности.  
**Чем платит:** риск, уязвимость, цена ошибки выше среднего.

#### Skills
1. **Rage Call** — risky self-buff  
   Статус: **rework**
2. **Savage Chop** — core brutal strike  
   Статус: **new**
3. **Blooded Resolve** — pain-to-power / conditional sustain  
   Статус: **new**
4. **Frenzy Chain** — payoff while enraged / pressured  
   Статус: **new**
5. **Last Roar** — capstone berserk peak  
   Статус: **new**

---

### Ветка B — **Ravager**
**Fantasy:** ломает броню, вскрывает плотные цели, разрывает раны.  
**Role:** anti-armor / anti-bruiser attrition.  
**Rhythm:** pressure / heavy hits.  
**Чем выигрывает:** ломает жирные цели, силён против защиты и длинных разменов.  
**Чем платит:** медленнее, грубее, слабее по мобильности.

#### Skills
1. **Bleeding Cut** — bleed setup  
   Статус: **existing concept**
2. **Sunder Armor** — armor break utility  
   Статус: **new**
3. **Brutal Overhead** — core anti-armor hit  
   Статус: **new**
4. **Reopen Wounds** — payoff on bleed / broken armor  
   Статус: **new**
5. **Ravage** — capstone anti-fat-target punish  
   Статус: **new**

#### Важные правила
- Berserker не должен становиться бессмертным через sustain.
- Ravager не должен красть explosive burst у Executioner.

---

## 2.6. `magic_staff`

### Общая роль family
Чистый offensive caster: raw damage, артиллерия, сильные spell-окна, массовый урон и control через магию.

---

### Ветка A — **Destruction**
**Fantasy:** огонь, аркан, взрывная мощь, максимум offensive output.  
**Role:** pure damage caster.  
**Rhythm:** commit casting.  
**Чем выигрывает:** лучший магический пик урона и сильный прокаст.  
**Чем платит:** слабая защита и уязвимость под давлением.

#### Skills
1. **Fireball** — core offensive cast  
   Статус: **existing concept**
2. **Arcane Surge** — offensive power setup  
   Статус: **new**
3. **Flame Wave** — multi-target pressure  
   Статус: **existing concept**
4. **Arcane Lance** — payoff nuke  
   Статус: **new**
5. **Cataclysm** — capstone big cast  
   Статус: **new**

---

### Ветка B — **Control**
**Fantasy:** лёд, замедление, сдерживание, выигрыш через темп и позицию.  
**Role:** safer control mage.  
**Rhythm:** tempo / control.  
**Чем выигрывает:** замедление, остановка темпа, лучшее выживание среди offensive mages.  
**Чем платит:** ниже чистый урон, слабее kill-pressure без setup.

#### Skills
1. **Frost Bolt** — core slow application  
   Статус: **existing concept**
2. **Ice Shackles** — stronger control setup  
   Статус: **new**
3. **Mana Shield** — defensive utility  
   Статус: **new**
4. **Shatter** — payoff into slowed / frozen target  
   Статус: **new**
5. **Absolute Zero** — capstone control field  
   Статус: **new**

#### Важные правила
- Fire/Ice flavour можно сохранять на уровне skills.
- Но системно ветки должны читаться как **Destruction** и **Control**.

---

## 2.7. `holy_staff`

### Общая роль family
Чистый holy caster: основной healer, holy support, светлая магия.

---

### Ветка A — **Healing**
**Fantasy:** главный хил, хоты, защита группы, стабильность.  
**Role:** pure healer / sustain support.  
**Rhythm:** sustain / support.  
**Чем выигрывает:** лучший общий healing throughput и надёжность.  
**Чем платит:** слабый solo damage, низкий offensive pressure.

#### Skills
1. **Heal** — core single-target heal  
   Статус: **existing concept**
2. **Regeneration** — HoT / sustain setup  
   Статус: **existing**
3. **Cleanse** — anti-debuff utility  
   Статус: **new**
4. **Blessing** — holy support buff  
   Статус: **existing**
5. **Resurrection** — capstone comeback / safety effect  
   Статус: **existing**

---

### Ветка B — **Light**
**Fantasy:** свет как защита и кара.  
**Role:** support-damage holy caster.  
**Rhythm:** support / payoff.  
**Чем выигрывает:** выше solo comfort, полезность вне pure-heal роли, holy pressure.  
**Чем платит:** слабее чистое лечение, чем у Healing.

#### Skills
1. **Smite** — core holy hit  
   Статус: **existing concept**
2. **Radiant Ward** — shield-like protection  
   Статус: **new**
3. **Judgment Mark** — holy vulnerability setup  
   Статус: **new**
4. **Sanctified Burst** — payoff into judged target  
   Статус: **new**
5. **Halo of Dawn** — capstone holy pulse  
   Статус: **new**

#### Важные правила
- Healing — лучший pure heal.
- Light — не должен одновременно лечить почти как Healing и дамажить как mage branch.

---

## 2.8. `wand`

### Общая роль family
Быстрый маг: короткие циклы, single-target pressure, sequencing, частые spell-решения.

---

### Ветка A — **Arcanist**
**Fantasy:** быстрые заклинания, проки, серия, магический темп.  
**Role:** fast offensive caster.  
**Rhythm:** tempo.  
**Чем выигрывает:** частота решений, проковая глубина, много коротких power-spikes.  
**Чем платит:** ниже один тяжёлый пик, чем у `magic_staff`.

#### Skills
1. **Arcane Bolt** — core quick cast  
   Статус: **new**
2. **Spell Echo** — proc setup / repeat effect  
   Статус: **new**
3. **Quick Channel** — cycle acceleration utility  
   Статус: **new**
4. **Overload** — payoff after short spell chain  
   Статус: **new**
5. **Arcane Barrage** — capstone rapid-cast burst window  
   Статус: **new**

---

### Ветка B — **Duelist**
**Fantasy:** маг-дуэлянт, трюки, тайминг, короткие контр-циклы.  
**Role:** single-target control-pressure caster.  
**Rhythm:** tempo / duel control.  
**Чем выигрывает:** лучше дуэли, контр-игра и точечное давление.  
**Чем платит:** ниже масштаб и массовый импакт.

#### Skills
1. **Dueling Ward** — defensive setup  
   Статус: **new**
2. **Hex Bolt** — core duel pressure cast  
   Статус: **new**
3. **Mana Feint** — trick / timing / disruption utility  
   Статус: **new**
4. **Counterpulse** — payoff punish into active target  
   Статус: **new**
5. **Duel Arc** — capstone short-cycle punish  
   Статус: **new**

#### Важные правила
- `wand` не должен дублировать `magic_staff` по роли artillery caster.
- Смысл family — скорость, sequencing и магическая техничность.

---

## 2.9. `holy_rod`

### Общая роль family
Боевой жрец / паладинский гибрид: holy protection, self-heal, frontline support, карающий свет.

---

### Ветка A — **Protector**
**Fantasy:** святые щиты, self-heal, ауры, передний саппорт.  
**Role:** paladin-style protection hybrid.  
**Rhythm:** sustain / protection.  
**Чем выигрывает:** живучесть, командная защита, гибкость на фронтлайне.  
**Чем платит:** не pure healer и не pure tank.

#### Skills
1. **Sacred Shield** — protective setup  
   Статус: **new**
2. **Mend Self** — self-heal core  
   Статус: **new**
3. **Aura of Resolve** — support aura utility  
   Статус: **new**
4. **Aegis Strike** — payoff scaling from active protection  
   Статус: **new**
5. **Guardian Light** — capstone protection burst  
   Статус: **new**

---

### Ветка B — **Judicator**
**Fantasy:** карающий свет, приговор, стойкий holy pressure.  
**Role:** holy bruiser / punishment hybrid.  
**Rhythm:** pressure / punish.  
**Чем выигрывает:** выше kill-pressure и ярче solo identity.  
**Чем платит:** ниже support ceiling и меньше сейва, чем у Protector.

#### Skills
1. **Judgment** — holy mark setup  
   Статус: **new**
2. **Radiant Strike** — core holy attack  
   Статус: **new**
3. **Consecration** — zone / tempo utility  
   Статус: **new**
4. **Punish the Wicked** — payoff into judged target  
   Статус: **new**
5. **Final Verdict** — capstone commit strike  
   Статус: **new**

#### Важные правила
- `holy_rod` — очень опасная family для баланса.
- Нельзя давать ей одновременно near-tank survivability, near-healer support и near-DPS burst.

---

## 2.10. `tome`

### Общая роль family
Гибкий magical toolbox: баффы, дебаффы, контроль, смешение школ, экспериментальный гибридный стиль.

---

### Ветка A — **Enchanter**
**Fantasy:** зачарования, ослабления, magical utility, поддержка союзников.  
**Role:** toolbox support.  
**Rhythm:** control / support.  
**Чем выигрывает:** гибкость, контроль темпа, сильная utility-роль.  
**Чем платит:** нет лучшего пика ни в дамаге, ни в лечении.

#### Skills
1. **Arcane Shield** — protective support tool  
   Статус: **new**
2. **Weaken** — debuff core  
   Статус: **new**
3. **Insight** — resource / tempo buff  
   Статус: **new**
4. **Dispel Script** — strip / cleanse / deny  
   Статус: **new**
5. **Grand Enchantment** — capstone support window  
   Статус: **new**

---

### Ветка B — **Researcher**
**Fantasy:** экспериментатор, смешивает куски разных школ.  
**Role:** hybrid-schools adaptive caster.  
**Rhythm:** adaptive / combo.  
**Чем выигрывает:** ширина, нестандартные сборки, гибридные синергии.  
**Чем платит:** самый низкий профильный пик среди caster families.

#### Skills
1. **Hybrid Missile** — flexible baseline cast  
   Статус: **new**
2. **Borrowed Flame** — magic-side setup  
   Статус: **new**
3. **Borrowed Grace** — holy-side setup  
   Статус: **new**
4. **Synthesis** — payoff after mixed school usage  
   Статус: **new**
5. **Forbidden Thesis** — capstone hybrid conversion  
   Статус: **new**

#### Важные правила
- `tome` не должен превращаться в “умеет всё лучше всех”.
- Его сила — в гибкости, а не в лучшем профиле.

---

# 3. Сводка по глубине redesign

## Ближе всех к готовности
1. `sword_1h`
2. `daggers`

## Средняя сложность
3. `bow`
4. `holy_staff`
5. `magic_staff`
6. `axe_2h`
7. `sword_2h`

## Самые рискованные / глубокие
8. `wand`
9. `holy_rod`
10. `tome`

---

# 4. Рекомендуемый порядок внедрения

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

### Почему так
- сначала families с уже понятными anchors;
- потом ranged / caster lines с хорошей ролью;
- в конце гибриды, где выше риск сломать role boundaries.

---

# 5. Что считать уже решённым

Следующие design-решения зафиксированы этим документом:
- `sword_1h / Guardian` получает **Shield Bash** как 3-й skill;
- `Shield Bash` — это **control + debuff**, а не hard stun;
- `daggers / Evasion` получает **Backstab** как signature burst skill;
- `daggers / Venom` не использует `Backstab`;
- payoff-удар poison-ветки фиксируется как **Widow’s Kiss**;
- poison capstone фиксируется как **Rupture Toxins**;
- `magic_staff` системно мыслится как **Destruction / Control**;
- `holy_staff` остаётся домом для pure-heal fantasy;
- `tome` и `holy_rod` считаются глубокими design-зонами с жёсткими trade-off ограничениями.

---

# 6. Как использовать этот файл дальше

Использовать как:
- основной design source of truth по weapon branches;
- основу для family-by-family technical specs;
- чеклист перед задачами для Codex;
- фильтр против случайного разрастания skills и пересечения ролей.

Этот файл **не нужно** превращать в giant implementation PR.
Правильный путь дальше: брать одну family, делать её technical spec, потом внедрять и тестировать отдельно.
