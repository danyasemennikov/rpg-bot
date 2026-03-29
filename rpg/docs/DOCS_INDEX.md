# DOCS_INDEX.md

## Что это за пакет

Это пакет новых рабочих документов для проекта Telegram RPG-бота.

Он собран как аккуратный **source-of-truth layer поверх старых docs**, без агрессивного переписывания исторических файлов.

### Что внутри

1. `PROJECT_STATUS.md`
   - актуальный confirmed merged status;
   - текущий roadmap-state;
   - жёсткие системные границы;
   - что считать активной design-задачей.

2. `WEAPON_BRANCHES_5_SKILLS_SPEC.md`
   - полный design-framework по weapon branches;
   - все 10 weapon families;
   - по 2 ветки на оружие;
   - по 5 skills на ветку;
   - existing/new/rework пометки;
   - master plan по глубине redesign и порядку внедрения.

3. `NEXT_CHAT_START_MESSAGE.md`
   - готовое стартовое сообщение для нового чата;
   - можно почти без правок вставить и продолжить работу.

4. `EQUIPMENT_ENHANCEMENT_PHASE1.md`
   - зафиксированные phase-1 правила заточки;
   - материалы по диапазонам `+1..+15`;
   - outcome-модель (успех/неудача/откат/поломка).

---

## Как этим пользоваться

### Если нужен новый чат по дизайну
1. Открыть `NEXT_CHAT_START_MESSAGE.md`.
2. Вставить целиком.
3. Продолжить уже предметную работу по одной family или по одной ветке.

### Если нужен быстрый truth по проекту
Сначала читать `PROJECT_STATUS.md`.

### Если нужно проектировать weapon trees
Сначала читать `WEAPON_BRANCHES_5_SKILLS_SPEC.md`.

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
4. `COMBAT_CORE_V1_SPEC.md`
5. `WEAPON_BRANCHES_5_SKILLS_SPEC.md`
6. `CLAUDE.md` как дополнительный техконтекст

---

## Что я бы обновлял в репозитории потом

Когда дойдёт дело до actual repo docs cleanup:
1. добавить `docs/PROJECT_STATUS.md`;
2. добавить `docs/WEAPON_BRANCHES_5_SKILLS_SPEC.md`;
3. сократить status-нагрузку в `CLAUDE.md`;
4. не смешивать combat-core spec с живым roadmap;
5. держать status и design-tree spec отдельными файлами.
