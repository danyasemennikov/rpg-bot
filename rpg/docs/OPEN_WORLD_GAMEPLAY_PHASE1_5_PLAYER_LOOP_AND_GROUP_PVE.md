# Open World Gameplay Phase 1.5
## Player Loop, Map Navigation, Pack Encounters & Side-vs-Side PvE Foundation

---

## 0. Status and phase placement

### Current merged project state before this phase

`Open World Gameplay Rollout Phase 1` is merged and considered the current source-of-truth state of the repository.

The canonical overworld now has:

- baseline open-world PvE population across the full ordinary-travel map;
- approved elite open-world anchors;
- route-aware gathering surfaces;
- updated world display names;
- `dark_forest` alias moved to `westwild_n7` with matching semantic metadata;
- sparse `old_mine_entrance` stub with preserved legacy-compatible identity;
- adjusted starter hunt contracts;
- normalized gathering material subtypes;
- route-depth-aware `level_max` metadata;
- truthful spawn-backed `hunt_elite_boars`;
- `stone_golem` normal/elite leak removed via `mountain_stone_golem`;
- per-kill reward location preservation for duplicated mobs.

### Why Phase 1.5 exists

Phase 1 made the world **populated in data**.

Phase 1.5 must make that world **readable, interactable, and structurally ready for deeper combat**:

- the player should see what is actually alive at the current location;
- the player should choose what to attack instead of pressing an abstract “search for battle” action;
- pack mobs should create real group encounters;
- PvE should expand from `players vs one mob` to `players vs multiple enemy units`;
- map/travel UX should become usable without teleport;
- gathering should remain available, but exact resource spoilers should leave the location message;
- combat architecture should prepare for future formations, line protection, limited AoE targeting, mass PvP, and larger side-vs-side encounters.

---

# 1. Phase goals

## 1.1. Player-facing goals

1. Turn `/location` into a real open-world situation screen.
2. Remove the abstract “search for battle” flow.
3. Show the **actual current count** of each available mob group in the location.
4. Let the player attack concrete targets through inline buttons.
5. Show active PvE/PvP encounters in the location compactly, with a command to inspect details.
6. Move ordinary travel and local professions into the persistent lower menu.
7. Add a readable text `/map` with branch-selection inline buttons.
8. Add distant `/go` travel to already-discovered locations through a slow automated route.
9. Remove entry level-gates from ordinary location travel:
   - levels remain danger guidance;
   - they do **not** block entry.
10. Remove exact gather-resource spoilers from `/location` and move resource knowledge into a crafter/craftsmen handbook service.

---

## 1.2. System goals

1. Add pack encounter mechanics for explicitly pack-behavior mobs.
2. Expand PvE runtime from:
   - `players vs one mob`
   to:
   - `players vs multiple enemy units`.
3. Build directly on the already-approved side-vs-side live combat architecture.
4. Introduce combat-line / formation foundation:
   - frontline;
   - melee line;
   - ranged line;
   - support line.
5. Introduce a target-resolver foundation suitable for:
   - line-based target access;
   - future AoE target caps;
   - mass PvP where one AoE must not hit 30 players at once.
6. Make rewards, hunt contracts, mastery, and spawn respawn behavior truthful for multi-enemy encounters.
7. Align aggro behavior with real available spawn instances and support aggressive packs.

---

# 2. Explicit non-goals

Phase 1.5 does **not** include:

- teleport phase 1;
- new world regions or new world graph nodes;
- new mob families beyond the already-approved Phase 1 content baseline;
- new gathering resource families beyond already-approved rails;
- boss runtime;
- rare-spawn scheduler;
- full raid implementation;
- manual formation editor for players;
- taunt/threat-table system;
- finished 30v30 PvP mode;
- broad reward economy rebalance;
- contribution-based reward splitting;
- full PvP UI redesign;
- hunting knife / full carcass-skinning loop;
- crafting expansion;
- travel ambush events or route interruptions during automated long travel.

---

# 3. `/location`: new location screen model

## 3.1. Core principle

`/location` must show:

> **the current live state of the location, not merely what could theoretically appear there.**

Mob visibility must be based on **actual available idle spawn instances**, not simply `location['mobs']`.

---

## 3.2. Sections shown in `/location`

Recommended order:

1. Location header:
   - name;
   - danger range / safe-zone label.
2. Location description.
3. Active hunt-contract progress line, if relevant to the current location.
4. Creatures nearby:
   - grouped current counts;
   - pack marker;
   - aggressive marker;
   - elite marker.
5. Active encounters:
   - compact row;
   - encounter id;
   - `/enc ID` or `/enc_ID`.
6. Nearby-player / PvP information:
   - no deep redesign in this phase.
7. Player status:
   - HP;
   - mana;
   - gold.

---

## 3.3. What `/location` must NOT show

The location message must not show:

- exact gather resources present in the location;
- local resource item names;
- travel directions;
- travel commands;
- map branch information.

---

## 3.4. Example `/location`

```text
📍 Тёмный лес | Ур. 1–8
Густой лес, пронизанный тьмой. Здесь рыщут волки, медведи и гоблинские охотники.

📜 Контракт: элитные кабаны — 0/1

Существа поблизости:
🐺 Волки — 3 🐾 стая
🐻 Медведь — 1
👺 Гоблин-охотник — 2
💀 Элитный кабан — 1

Активные схватки:
⚔️ #184 — Стая волков ×3, формируется — /enc 184
⚔️ #185 — Медведь, идёт бой — /enc_185

❤️ 96/120  🔵 34/40  💰 512
```

---

## 3.5. Inline buttons under `/location`

Inline buttons under the location message are used **only for attack actions against visible mob target groups**.

Example:

```text
[⚔️ Стая волков ×3]
[⚔️ Медведь] [⚔️ Гоблин-охотник]
[💀 Элитный кабан]
```

There are:

- no travel buttons under `/location`;
- no gathering buttons under `/location`.

---

# 4. Mob grouping in `/location`

## 4.1. Grouping key

Available spawn instances are grouped by:

```text
mob_id + spawn_profile + special_spawn_key
```

This prevents normal, elite, and special-spawn variants from being merged incorrectly.

---

## 4.2. Non-pack mobs

If three boars are available:

```text
🐗 Кабан — 3
```

The button remains singular:

```text
[⚔️ Кабан]
```

Pressing it starts an encounter with **one** available boar instance.

---

## 4.3. Pack mobs

If three wolves are available:

```text
🐺 Волки — 3 🐾 стая
```

Button:

```text
[⚔️ Стая волков ×3]
```

Pressing it starts an encounter against **all available idle wolves** in that grouped pack target.

---

## 4.4. Elite

```text
💀 Элитный кабан — 1
```

Button:

```text
[💀 Элитный кабан]
```

Elite pack mechanics are **not** introduced in Phase 1.5.

---

## 4.5. Aggressive mobs

Aggressive mobs are visible in the same block, for example:

```text
⚠️ 🧟 Зомби — 4 🐾 стая
```

The player may attack them first.

If the player does not, they may trigger the aggro flow, which Phase 1.5 aligns with actual spawn instances.

---

# 5. Persistent lower menu

## 5.1. Core principle

The lower persistent menu represents **contextual actions available from the current location/state**.

It contains:

1. ordinary neighboring travel buttons;
2. local profession actions;
3. hub/service buttons where applicable;
4. baseline permanent system buttons.

---

## 5.2. Neighbor travel buttons

Ordinary neighboring travel buttons appear in the **top rows** of the lower menu.

Example:

```text
[⬅️ Бор] [➡️ Каменный ручей]
```

They represent ordinary local travel, not map travel.

---

## 5.3. Local profession actions

If the current location exposes corresponding gather surfaces, show:

- `🌿 Собирать`
- `🪵 Рубить`
- `⛏️ Добывать`
- `🎣 Рыбачить`

Examples:

```text
[🌿 Собирать] [🪵 Рубить]
```

or

```text
[🌿 Собирать] [🎣 Рыбачить]
```

Important:

- these buttons tell the player that a **type of activity** is available;
- they do **not** reveal the exact item(s) obtainable there.

---

## 5.4. Hub/service buttons

In safe hubs, contextual service buttons appear in the lower menu:

- `🏪 Магазин`
- `🛏️ Таверна`
- `📜 Доска заказов`
- `🛠️ Гильдия ремесленников`

This is intended to remove service snapshot command clutter from the location message.

---

## 5.5. Baseline permanent buttons

Below context rows:

```text
[📍 Локация] [🗺️ Карта]
[🎒 Инвентарь] [👤 Профиль]
```

---

## 5.6. Full example lower menu

```text
[⬅️ Бор] [➡️ Каменный ручей]

[🌿 Собирать] [🪵 Рубить]

[📍 Локация] [🗺️ Карта]
[🎒 Инвентарь] [👤 Профиль]
```

---

# 6. Resource knowledge: craftsmen handbook

## 6.1. Why this exists

Exact gatherable resources are removed from `/location` to:

- make exploration more meaningful;
- avoid spoiling gathering through the location card;
- give value to world knowledge.

The player still needs a legal information source.

---

## 6.2. Recommended service model

Introduce a service such as:

- `🛠️ Гильдия ремесленников`
- or a directly equivalent resource-handbook service.

Recommended hub availability:

- Aster;
- Elmor;
- Karn;
- Ember;
- Mirage;
- Velm.

---

## 6.3. What the handbook shows

It should provide **human-readable directional knowledge**, not exact node ids:

- region;
- biome / terrain cue;
- sometimes route-depth cue.

Example:

```text
📖 Справочник ресурсов

🌿 Собирательство
• Соль — встречается в сухих землях Sunscar, особенно возле солончаков.
• Болотные растения — чаще ищут в глубине Mireveil.
• Травы и грибы — обычны в лесных участках Westwild.

🪵 Лесоруб
• Тёмная древесина — глубокие леса Westwild.

⛏️ Добыча
• Камень и руда — горный путь Frostspine.
• Шахтные залежи — у Старой шахты.

🎣 Рыбалка
• Южный берег подходит для простой прибрежной ловли.
```

### Implementation preference

Prefer a curated handbook read-model over dumping raw location `gather` profiles verbatim.

Tests may verify that the handbook does not mention resources absent from world gather rails, but the presentation itself should stay curated and human-readable.

---

# 7. `/map`: text map of the world

## 7.1. Core principle

`/map` is a dedicated screen, not a section of `/location`.

It provides:

- branch overview;
- readable route trees;
- branch selection buttons;
- access to long-route `/go` commands.

---

## 7.2. `/map` overview

```text
🗺️ Карта мира

От Астера расходятся дороги в разные части материка.
Выберите направление:
```

Inline buttons under the map message:

```text
[🌾 Западные земли] [🏔️ Горный путь]
[🏚️ Древние руины] [🏜️ Выжженные земли]
[☣️ Болота]
```

---

## 7.3. Branch map example: Westwild

```text
🗺️ Карта мира

🌾 Западные земли
От открытых полей у Астера — к глубокому лесу и чащам за Элмором.

🏛️ Астер
↓
🌾 Пшеничные поля — /go westwild_n1
↓
🌿 Луга — /go westwild_n2
↓
⛰️ Холмы — /go westwild_n3
↓
🌳 Лиственная роща — /go westwild_n4
↓
🌲 Перелесок — /go westwild_n5
├─ 🏘️ Элмор — /go hub_westwild
↓
🌲 Бор — /go westwild_n6
↓
🌲 Тёмный лес — /go westwild_n7
↓
🪨 Каменный ручей — /go westwild_n8
↓
🌲 Глухая чаща — /go westwild_n9
↓
🪵 Мшистый яр — /go westwild_n10
↓
🌲 Шепчущий бор — /go westwild_n11
```

Branch-selection inline buttons should remain available under branch maps as well, for easy switching.

---

## 7.4. Branch titles

Use human branch titles, not technical “Path: ...” labels:

- `🌾 Западные земли`
- `🏔️ Горный путь`
- `🏚️ Древние руины`
- `🏜️ Выжженные земли`
- `☣️ Болота`

A short second-line route mood/description is allowed and recommended.

---

# 8. Command format: spaces and underscores

## 8.1. Rule

Commands with arguments should accept both a space-separated and underscore-separated form.

Examples:

```text
/go westwild_n7
/go_westwild_n7
```

```text
/enc 184
/enc_184
```

```text
/map westwild
/map_westwild
```

The difference is user convenience only; both forms should resolve to the same behavior.

---

# 9. Long-route `/go` travel

## 9.1. `/go` behavior

`/go <location_id>` can do one of two things:

### A. Neighbor destination
Start ordinary local travel.

### B. Distant discovered destination
Start a **slow automated route** along ordinary world-graph edges.

---

## 9.2. Distant routes only to discovered locations

If the target location is not in the player discovery state:

```text
Эта дорога вам ещё неизвестна.
Сначала доберитесь туда обычным путём.
```

---

## 9.3. Travel time

Distant auto-route travel must be **meaningfully slower** than traveling manually node by node.

Fixed design target:

```text
long_route_travel_time = manual_route_time × 3
```

General rule:
- never below ×2;
- Phase 1.5 target value: **×3**.

---

## 9.4. No entry level gate

A player may enter any travel-reachable location regardless of character level.

`level_min / level_max` remain:

- danger guidance;
- display metadata;
- **not** travel access restrictions.

If the player walks into an area that is too dangerous, the player accepts that risk.

---

## 9.5. Not included yet

Phase 1.5 long travel does not yet include:

- route ambushes;
- route interruption;
- PvP interception along the route;
- step-by-step intermediate node stops.

---

# 10. Active encounters and `/enc`

## 10.1. In `/location`

Active encounters appear compactly:

```text
Активные схватки:
⚔️ #184 — Стая волков ×3, формируется — /enc 184
⚔️ #185 — Медведь, идёт бой — /enc_185
```

---

## 10.2. `/enc` command

Both forms work:

```text
/enc 184
/enc_184
```

---

## 10.3. PvE encounter detail

Example:

```text
⚔️ Энкаунтер #184
Стая волков ×3

Статус: формируется
Локация: Тёмный лес

Сторона игроков:
🛡️ Daniel

Сторона врагов:
🐺 Волки ×3
```

Buttons depend on state:

- join;
- leave;
- enter battle.

---

## 10.4. PvP encounter detail

Prefer `/enc` as a shared “inspect encounter” entry point where practical, but avoid broad PvP rewrites.

If the id resolves to PvP, reuse existing PvP detail rails where possible.

---

# 11. Pack encounter model

## 11.1. Pack mobs in Phase 1.5

Explicitly pack-enabled from the start:

- wolves;
- leeches;
- zombies.

All other mobs remain solo-behavior for now.

---

## 11.2. Pack behavior semantic

Use explicit content semantics such as:

```text
open_world_pack_behavior:
- solo
- pack_all_available
```

Phase 1.5:

- wolves → `pack_all_available`
- leeches → `pack_all_available`
- zombies → `pack_all_available`

---

## 11.3. Pack size

A pack encounter includes:

> **all available idle spawn instances in that grouped target within the current location.**

There is no soft cap on pack size in Phase 1.5.

Pack size is an intentional hardcore/risk element.

---

## 11.4. Snapshot integrity

If the player clicks a visible pack target after the actual pack composition changed, do not silently launch a different-sized fight.

Example:

- UI showed `Стая волков ×3`;
- by click time, one wolf is already claimed elsewhere.

The result must be a stale notice:

```text
Стая уже изменилась. Обновите локацию.
```

---

## 11.5. Atomic pack claim

Pack encounter creation must:

- atomically verify all expected spawn instance ids are still available;
- bind all of them to one encounter id;
- move the group into the appropriate pre-runtime encounter state;
- rollback the whole operation if any member is already unavailable.

---

# 12. Enemy Group PvE runtime

## 12.1. Target model

```text
side_a:
- players

side_b:
- one or more enemy units
```

---

## 12.2. `enemy_roster`

`battle_state` stores an `enemy_roster`.

Each enemy entry should carry:

- `enemy_slot_id`;
- `spawn_instance_id`;
- `mob_id`;
- `spawn_profile`;
- `special_spawn_key`;
- frozen mob snapshot;
- `hp`;
- `max_hp`;
- `effects`;
- `defeated`;
- `combat_line`.

---

## 12.3. Why frozen snapshots are required

Enemy combat data must be stable during the encounter, including after resume/reload.

Snapshots prevent:

- mid-fight changes if source mob templates are edited;
- scaling instability;
- special-spawn identity loss.

---

## 12.4. Side runtime

PvE live runtime should create:

```text
side_a_participants = player participants
side_b_participants = enemy roster participants
```

Each enemy unit receives a stable synthetic negative participant id.

---

# 13. Combat lines / formation foundation

## 13.1. Internal line model

| Line | Meaning |
|---|---|
| `1` | frontline |
| `2` | melee |
| `3` | ranged |
| `4` | support |

---

## 13.2. Default player placement

- frontline / tank builds → line 1;
- melee DD → line 2;
- ranged DD → line 3;
- support / heal → line 4.

---

## 13.3. Default enemy placement

- ordinary pack mobs in Phase 1.5 → line 1;
- future melee bruisers → line 1 or 2;
- future ranged enemies → line 3;
- future healers/support casters → line 4.

---

## 13.4. No manual formation UI yet

Phase 1.5:

- auto-assigns lines;
- prepares data/model;
- does not yet ship a full player-facing formation editor.

---

# 14. Target resolver foundation

## 14.1. Single-target actions

Normal attacks and single-target skills hit:

> **the first living enemy in the nearest occupied enemy line.**

In UI this enemy is marked with:

```text
🎯
```

---

## 14.2. Target movement

When the current target dies:

- targeting automatically advances to the next valid living enemy;
- if the nearest line is cleared, the next occupied deeper line opens.

---

## 14.3. Enemy targeting

Enemy attacks target:

> **the nearest occupied player-side line.**

This ensures:

- frontline protects backline;
- ranged/support are not hit before exposed.

---

# 15. AoE target-shape foundation and future mass PvP

## 15.1. Why this is needed now

Future large battles must avoid degenerate scaling:

- one AoE damaging all 30 opponents;
- one AoE heal restoring an entire 30-player side;
- tanks being irrelevant because enemies hit mages/support immediately.

---

## 15.2. Target shape contract

Skills/actions must resolve targets through a shared target resolver, not manual loops.

Foundation should be able to express:

- `single_front_target`;
- `all_enemies_in_small_pack`;
- future:
  - `front_line_cluster(max_targets=4)`;
  - `backline_single`;
  - `selected_line_cluster`;
  - `cross_line_pierce`.

---

## 15.3. What Phase 1.5 actually uses

- single-target actions → current `🎯` target;
- AoE skills in small pack PvE → all living enemies in that pack encounter.

---

## 15.4. What Phase 1.5 prepares for

- future AoE capped to a limited number of front-line units;
- future precision attacks into backline;
- future line-limited healing;
- future mass PvP without infinite target scaling.

---

# 16. Enemy-side resolution

## 16.1. Every living enemy acts

If three wolves are alive:

- wolf 1 acts;
- wolf 2 acts;
- wolf 3 acts.

---

## 16.2. Defeated enemy

A defeated enemy:

- is no longer targetable;
- no longer acts on enemy side;
- is removed/disabled from active enemy side order.

---

## 16.3. Reflect / counter / parry

Retaliatory damage must return to the **specific enemy unit that triggered it**, not merely to the current front target.

---

## 16.4. Per-enemy effects

Each enemy stores its own:

- DoT;
- stun/freeze;
- vulnerability/debuff windows;
- other mob-side effect state.

---

## 16.5. Tick discipline

Do not duplicate player buff-duration ticks by running a single-enemy helper once per enemy without separating phase effects.

Required separation:

- player post-action duration ticks: once per phase;
- enemy effect ticks: per enemy unit where appropriate.

---

# 17. Combat UI for group PvE

## 17.1. Top of battle screen

```text
⚔️ Стая волков ×3
Раунд 2 • Ваш ход • 11 сек.
```

---

## 17.2. Simple pack encounter enemy block

```text
Враги:
🎯 🐺 Волк
██████░░░░ 18/32

🐺 Волк — 32/32
🐺 Волк — 32/32
```

---

## 17.3. Mixed enemy formation block

Player-facing UI must not print dry labels like “1 линия / 2 линия”.

Use compact positional icons:

- `🛡️` frontline;
- `⚔️` melee;
- `🏹` ranged;
- `✨` support.

Example:

```text
Враги:
🛡️ 🎯 Скелет-страж
███████░░░ 64/90

🏹 Скелет-маг — 45/45
✨ Проклятый жрец — 52/52
```

---

## 17.4. Allies block

```text
Союзники:
🛡️ Roman — 121/140 ✅
⚔️ Daniel — 82/100 ⌛
🏹 Marta — 58/75 ✅
✨ Elia — 71/80 ✅
```

---

## 17.5. The current player's own status

The current player's own HP/mana should be displayed in fuller detail than other allies.

---

## 17.6. Battle logs

Aggregate repetitive multi-hit events.

Examples:

```text
▫️ Волки атакуют: 2 попадания, 1 промах, 18 урона.
```

```text
▫️ Огненная волна поражает волков ×3: 72 суммарного урона.
▫️ Повержены: волки ×2.
```

---

## 17.7. Battle buttons

```text
[⚔️ Атаковать] [🏃 Отступить]
[Рассечение ур.3 🔵12]
[Огненная волна ур.2 🔵18 • все]
[🧪 Зелья]
```

AoE buttons may use a compact marker such as `• все`.

---

# 18. Rewards, contracts, mastery, respawn

## 18.1. Rewards

Pack encounter rewards are calculated **per defeated enemy unit**.

For three wolves:

- 3 separate EXP/gold determinations;
- 3 separate loot-table rolls.

UI result is aggregated.

---

## 18.2. Group PvE reward policy

Keep the current full-credit policy:

- every surviving eligible participant receives the full aggregated reward bundle;
- contribution-based splitting is not introduced in this phase.

---

## 18.3. Hunt contracts

Hunt progress increments **per defeated enemy unit**.

Example:

- contract was `1/5 wolves`;
- player wins a wolf pack ×3;
- contract becomes `4/5`.

---

## 18.4. Respawn

All spawn instances bound to the encounter are moved through normal linked-encounter cleanup / respawn behavior after terminal completion.

---

## 18.5. Defeat outcome

Persistent wounded packs are not implemented.

If players lose:

- encounter resolves terminally;
- linked pack spawn instances follow existing respawn lifecycle rules.

---

## 18.6. Mastery

Victory mastery bonus scales with number of defeated enemy units.

Example:

- solo mob → +10;
- pack ×3 → +30.

Additionally, while touching victory cleanup, close the nearby correctness tail:

- all rewarded group participants should receive the victory mastery bonus;
- do not leave it owner-only if the current flow still behaves that way.

---

# 19. Aggro packs

## 19.1. Aggro source

Aggro must use **currently available aggressive spawn instances**, not a static location mob list.

---

## 19.2. Aggressive pack UI

If a pack detects the player:

```text
⚠️ Вас заметила стая волков ×3!
```

Buttons:

```text
[⚔️ Сражаться]
[🏃 Бежать]
```

---

## 19.3. Failed escape

On failed escape:

- a pack encounter is created;
- the enemy side acts first through live runtime;
- do not fake this with ad hoc handler damage outside runtime.

---

## 19.4. Join policy

Aggro encounters:

- start immediately;
- have no forming window;
- are not joinable in Phase 1.5.

Manual attacks on visible mobs/packs retain the ordinary forming/join flow.

---

# 20. Implementation split

## PR 1 — World Navigation & Local Action UX

### Included

- `/map` overview and branch maps;
- inline branch-selection buttons under map messages;
- `/map westwild` and `/map_westwild`;
- `/go id` and `/go_id`;
- long-route travel only to discovered locations;
- long-route travel time `manual route ×3`;
- remove level travel gate;
- preserve level range as danger display only;
- ordinary neighboring travel buttons moved into persistent lower menu;
- profession actions moved into lower menu:
  - gather;
  - woodcut;
  - mine;
  - fish;
- show only action types available in current location;
- remove exact gather-resource list from `/location`;
- remove generic inline gather button from `/location`;
- move hub service buttons into lower menu;
- add craftsmen guild / resource handbook service.

### Not included

- new mob target screen;
- pack encounter runtime;
- multi-enemy PvE;
- battle UI redesign.

---

## PR 2 — Enemy Group PvE Runtime & Formation Foundation

### Included

- pack behavior for wolves, leeches, zombies;
- pack = all idle spawn instances of that mob group at location;
- stale handling if composition changed after rendering;
- atomic multi-spawn encounter claim;
- `enemy_roster`;
- multi-enemy enemy side runtime;
- combat-line foundation;
- target resolver foundation;
- AoE target-shape foundation;
- group enemy actions;
- per-enemy effects;
- reflect/counter correctness;
- rewards/contracts/mastery/respawn for multi-enemy encounters;
- aggressive pack runtime behavior;
- group mastery correctness tail.

### Not included

- final new `/location` UX;
- final battle presentation polish;
- `/enc` player-facing polish.

---

## PR 3 — Location Encounter UX & Group Battle Presentation

### Included

- new `/location` creatures-nearby block;
- grouped mob counts;
- pack/aggressive/elite markers;
- inline attack buttons;
- active encounters in `/location` with `/enc`;
- `/enc id` and `/enc_id`;
- PvE encounter detail message;
- reuse PvP detail rails through `/enc` where practical;
- new group-PvE battle UI:
  - encounter title;
  - round / active side / timer;
  - current `🎯` target with full HP bar;
  - compact other enemies;
  - summary for 5+ living enemies;
  - compact ally display;
  - positional icons;
  - commit status;
  - aggregated logs;
  - compact AoE marker on relevant buttons;
- aggregated pack-victory message.

### Not included

- manual formation editor;
- mass PvP;
- boss encounters;
- new content expansion.

---

# 21. Cheap neighboring tails to close while implementing

1. Remove travel level-lock from UI and validation.
2. Remove gather-resource spoilers from `/location`.
3. When touching aggro, switch it from static mob lists to real available spawn instances.
4. When touching victory cleanup, fix owner-only group mastery bonus if it remains owner-only.
5. Preserve existing forming/join rails for manually initiated open-world PvE encounters.

---

# 22. Phase completion criteria

Phase 1.5 is complete when:

1. A player in a location sees the real active mob population and its meaningful traits.
2. The player chooses a concrete attack target.
3. Pack mobs create true group enemy encounters.
4. PvE runtime supports multiple enemy participants on enemy side.
5. Combat-line and target-resolver foundations are present for future mass-combat work.
6. `/map` is useful, and long-route travel is convenient but clearly slower than manual travel.
7. Gathering is accessible through local profession actions but not spoiled directly in `/location`.
8. Rewards, contracts, mastery, and respawn are truthful for multi-enemy encounters.
9. Aggressive packs do not spawn from stale/static data and resolve through the live runtime.
