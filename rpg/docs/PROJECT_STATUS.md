# PROJECT_STATUS.md

## Назначение

Этот файл — **живой status-layer проекта**.

Он нужен для того, чтобы:
- быстро понять, что **точно смержено**;
- не путать confirmed status со старыми roadmap-фразами в исторических документах;
- иметь один короткий source of truth для нового чата, handoff и review.

Этот файл **не заменяет**:
- `AGENTS.md` — правила работы и ограничения для coding tasks;
- `GAME_FOUNDATION.md` — философию игры, баланса, оружия и билдов;
- `COMBAT_CORE_V1_SPEC.md` — архитектурную спецификацию combat core;
- `CLAUDE.md` — технический контекст проекта.

Но при расхождении по **актуальному merge-status** опираться нужно в первую очередь на этот файл.

---

## Приоритет источников при расхождении

1. confirmed merged status из этого файла;
2. актуальный код в репозитории;
3. `AGENTS.md`;
4. `COMBAT_CORE_V1_SPEC.md`;
5. `GAME_FOUNDATION.md`;
6. `CLAUDE.md`.

---

## Что точно смержено

### 1. Combat Core v1 / стабилизация ядра
Считать **подтверждённо смерженным**:
- enemy-response refactor;
- shared `resolve_enemy_response(...)`;
- normal attack / skill / failed flee используют общий enemy-response path;
- `apply_death(...)` fix;
- `apply_rewards(...)` now gives `+3 * levels_gained`;
- pre-turn ticking cleanup:
  - `apply_pre_enemy_response_ticks(...)`;
  - `apply_mob_effect_ticks(...)`;
  - normal attack сохраняет старый timing player buffs;
  - skill flow использует общий ticking helper;
- regression tests на боёвку были добавлены и были зелёные;
- старые мусорные `test_setup.py` и `test_skills.py` удалены;
- safe-refactor в `handlers/battle.py`:
  - helpers для victory/death cleanup;
  - post-skill combat resolution helper;
  - normal attack resolution helper;
  - shared “battle continues” update helper.

### 2. Combat Core v1 Phase B
Считать **подтверждённо смерженным**:
- `process_skill_turn(...)` в `game/combat.py`;
- `resurrection` с явной runtime duration-моделью;
- direct-damage modifiers централизованы;
- timed buffs/effects нормализованы в combat core;
- `parry` вынесен в explicit trigger-buff enemy-response path;
- `regeneration` нормализован как start-of-turn effect;
- `finalize_player_direct_damage_action(...)`;
- `resolve_normal_attack_action(...)`;
- normal attack и damage-skill выровнены по structured direct-damage contract;
- compatibility shim `apply_player_buffs(...)` удалён;
- `handlers/battle.py` очищен от critical combat math и оставлен orchestration/UI слоем;
- `save_battle(...)` упрощён до сигнатуры без лишнего `battle_state`.

### 3. Stage 1 — semantic hooks
Считать **подтверждённо смерженным**:
- `weapon_profile`;
- `armor_class`;
- `offhand_profile`;
- `damage_school`;
- `encumbrance`.

Ключевая модель:
- `damage_school` = `physical | magic | holy`;
- различие между луком, кинжалами, мечом и т.д. живёт в `weapon_profile`, а не в дроблении `damage_school`.

### 4. Stage 2A — formulas groundwork
Считать **подтверждённо смерженным**:
- `calc_final_damage(...)` semantic-aware;
- formulas используют `weapon_profile` / `damage_school`;
- смягчены агрессивные линейные формулы;
- dodge soft-falloff исправлен;
- `physical` school bonus больше не размывает weapon profiles;
- normal crit = `x2.0`;
- deliberate exception:
  - guaranteed crit path пока отдельно остаётся `x2.5`.

### 5. Stage 2B — armor/offhand formulas
Считать **подтверждённо смерженным**:
- `armor_class` реально влияет на бой;
- `offhand_profile` реально влияет на бой;
- `encumbrance` подключён как лёгкий tempo/dodge/offense hook;
- не введён грубый penalty вида “heavy cuts spell damage”.

### 6. Stage D1.1 — `sword_1h guardian/frontline slice`
Считать **подтверждённо смерженным**:
- первый vertical slice для `weapon_profile='sword_1h'`;
- используется пакет:
  - `sword_rush`
  - `parry`
  - `defensive_stance`
  - `counter`
- battle UI уже учитывает `weapon_profile`, а не только legacy `weapon_id`;
- есть мягкая shield-синергия для `parry` и `counter`;
- `counter` gated на `battle_state['weapon_profile'] == 'sword_1h'`;
- i18n для sword slice обновлён.

### 7. Stage D1.2 — `sword_1h vanguard/offensive slice`
Считать **подтверждённо смерженным**:
- `sword_1h` теперь считать собранным в два различимых подстиля:
  - defensive/frontline;
  - pressure/offensive;
- corrective pass по `counter` тоже смержен;
- shield = reliability;
- opening/vulnerability = payoff/punish;
- тесты зелёные.

### 8. Stage D2.1 — `daggers evasion/skirmisher slice`
Считать **подтверждённо смерженным**:
- dagger evasive/mobile/opportunism slice смержен;
- corrective pass тоже смержен;
- итог:
  - убран слишком общий flat damage steroid от dodge-buff окна;
  - `smoke_bomb` ослаблен до более безопасного evasive окна;
  - `backstab` читает opening через `slow`;
- тесты зелёные.

### 9. Equipment enhancement phase 1 (bootstrap acquisition)
Считать подтверждённым для текущего этапа:
- phase-1 заточка `+0..+15` использует временные bootstrap-сources для материалов;
- это intentional interim-решение для live usability;
- при следующем pass по мобам/луту источники должны быть переведены в системную tier/content-band модель.

---

## Что НЕ считать подтверждённо смерженным

Не считать смерженным без явного подтверждения пользователя:
- любые ранее предложенные `*_v2.py` файлы;
- broad redesign всех weapon families;
- полное расширение всех веток до `5 skills per branch`;
- любые schema changes;
- любые casual balance-переписывания “по пути”.

Отдельно:
- текущая локальная рабочая тема в другом чате: `D2.2 daggers poison / pressure slice`;
- но это **не надо считать автоматически смерженным**, пока пользователь явно это не подтвердит.

---

## Где проект находится сейчас по roadmap

Проект находится уже **не** на этапе “собираем фундамент боевой системы”, а на этапе:

# weapon-profile / skill-tree redesign поверх уже стабилизированного combat core

Это значит:
1. Combat Core v1 — считать фундаментально собранным;
2. formulas groundwork — считать позади;
3. armor/offhand semantic layer — считать подключённым;
4. сейчас активная стратегическая зона — redesign weapon families через маленькие vertical slice-ы.

На текущем подтверждённом статусе уже есть:
- `sword_1h` как первая weapon family с двумя различимыми подстилями;
- `daggers` как минимум с одним уже смерженным evasive/skirmisher slice.

---

## Почему redesign под 5 skills per branch уже актуален

Потому что:
1. weapon families уже стали главным местом боевой идентичности;
2. combat core и formulas уже достаточно стабилизированы, чтобы проектировать деревья поверх них;
3. `GAME_FOUNDATION.md` уже жёстко задаёт модель “оружие → ветки → архетип → билд”, а не “классы при создании персонажа”;
4. текущая практическая задача проекта — не чинить фундамент заново, а дособирать полноценные weapon trees.

Но это **design/spec задача**, а не giant implementation task.

---

## Жёсткие границы системы

1. `handlers/battle.py` должен оставаться orchestration/UI слоем.
2. Критическая боевая математика должна жить в:
   - `game/combat.py`
   - `game/balance.py`
   - `game/skill_engine.py`
3. Не возвращать combat math обратно в handler-слой.
4. Не менять casually:
   - reward flow;
   - cooldown reset behavior;
   - battle_state model.
5. Не делать schema changes без отдельного explicit task.
6. i18n обязателен для любого нового player-facing content.
7. `smallest coherent change` — базовое правило для coding tasks.
8. Не считать, что broad redesign всех оружий можно внедрять одним большим PR.

---

## Что считать текущей активной design-задачей

Текущая большая design-задача:

# полный redesign всех weapon branches под стандарт `5 skills per branch`

Что именно это значит:
- не внедрять всё сразу одним PR;
- не ломать identity уже существующих family/branches;
- расширить и дособрать ветки до более полной и выразительной формы;
- сохранить философию текущих направлений;
- собрать master spec, по которой потом можно будет внедрять family-by-family.

---

## Как использовать этот файл

- Для нового чата: сначала читать этот файл, потом `AGENTS.md`, `GAME_FOUNDATION.md`, `COMBAT_CORE_V1_SPEC.md`, `CLAUDE.md`.
- Для review: сначала сверять, не объявляется ли новым то, что пользователь ещё не подтвердил.
- Для Codex/handoff: использовать как короткий status snapshot, а не как место для архитектурных решений.
