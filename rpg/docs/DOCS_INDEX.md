# DOCS_INDEX.md

## Что это за пакет

Это пакет новых рабочих документов для проекта Telegram RPG-бота.

Он собран как аккуратный **source-of-truth layer поверх старых docs**, без агрессивного переписывания исторических файлов.

### Что внутри

1. `CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md`
   - implementation and rollout report for the current Epic branch;
   - complete 100-skill and G–I coverage index;
   - migration, restart, production-journey, balance/J5 and PR229/PR230 evidence.

2. `PROJECT_STATUS.md`
   - актуальный confirmed merged status;
   - текущий roadmap-state;
   - жёсткие системные границы;
   - что считать активной design-задачей.

3. `WEAPON_BRANCHES_5_SKILLS_FINAL_DESIGN.md`
   - полный design-framework по weapon branches;
   - все 10 weapon families;
   - по 2 ветки на оружие;
   - по 5 skills на ветку;
   - existing/new/rework пометки;
   - master plan по глубине redesign и порядку внедрения.

4. `EQUIPMENT_ENHANCEMENT_PHASE1.md`
   - зафиксированные phase-1 правила заточки;
   - материалы по диапазонам `+1..+15`;
   - outcome-модель (успех/неудача/откат/поломка).

5. `FIELD_LOOT_AND_GEAR_PROGRESSION_V1.md`
   - review-branch specification for the 32-item field catalogue and regional pools;
   - versioned reward settlement, migration, recovery, and legacy-review guarantees;
   - frozen balance/acquisition evidence and focused reviewer risks.

---

## Как этим пользоваться

### Если нужен новый чат по дизайну
Использовать последовательность чтения ниже и явно указать, идёт ли речь о
confirmed main или о pending Epic branch.

### Если нужен быстрый truth по проекту
Сначала читать `PROJECT_STATUS.md`.

Для review текущей ветки Character Builds V1 затем читать
`CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md`. Pending-ветка не становится confirmed
merged state до фактического merge.

### Если нужно проектировать weapon trees
Сначала читать `WEAPON_BRANCHES_5_SKILLS_FINAL_DESIGN.md`. Для exact runtime V1
сверять его с `CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md` и `game/build_contract.py`.

---

## Как это соотносится со старыми docs

### Что остаётся главным
- `AGENTS.md` — правила работы, ограничения, coding discipline.
- `GAME_FOUNDATION.md` — философия игры, оружий, баланса, гибридов.
- `COMBAT_CORE_V1_SPEC.md` — архитектура боевого ядра.

### Что частично устарело по status-слою
- часть roadmap-фраз в `CLAUDE.md`;
- часть roadmap-формулировок внутри `COMBAT_CORE_V1_SPEC.md`.

Это **не значит**, что эти документы плохие.
Это значит, что в них устарела именно оперативная стадия проекта, а не фундаментальные решения.

---

## Рекомендуемая последовательность чтения теперь

Для нового design/review-чата:
1. `PROJECT_STATUS.md`
2. `AGENTS.md`
3. `GAME_FOUNDATION.md`
4. `CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md` для текущего Epic review
5. `COMBAT_CORE_V1_SPEC.md`
6. `WEAPON_BRANCHES_5_SKILLS_FINAL_DESIGN.md`
7. `CLAUDE.md` как дополнительный техконтекст

---

## Правило поддержки

- confirmed merge-state обновляется только в `PROJECT_STATE_CURRENT.md` после merge;
- pending implementation evidence живёт в соответствующем branch report;
- historical specs сохраняются, но получают явную ссылку на более новый runtime authority;
- combat-core architecture, live roadmap и branch evidence не смешиваются в один source of truth.
