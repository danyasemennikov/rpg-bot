# AGENTS.md

## Purpose
This repository contains a Telegram text MMORPG bot.

This file is the main instruction file for Codex and other coding agents.
Read this file first, then read `CLAUDE.md`, then read `GAME_FOUNDATION.md` before making important changes.

## Primary workflow
The working model for this repository is:
1. ChatGPT chat is used for architecture, balance, specifications, design decisions, and review.
2. Codex is used to implement approved changes in the codebase.
3. Do not assume any previously generated `*_v2.py` files or patches were merged unless the user explicitly says they were merged.
4. Until the user clearly confirms otherwise, assume the project files in the repository are still the original versions.

## Developer profile
The repository owner knows Python only at a basic level.
When making changes:
- prefer simple and readable code over clever abstractions;
- keep function names explicit;
- avoid unnecessary indirection and deep inheritance;
- add short comments only where they help a non-expert understand intent;
- do not rewrite large subsystems unless the task explicitly requires it.

## Project overview
Core stack:
- Python 3.12
- `python-telegram-bot`
- SQLite (`game.db` locally, but local DB files should not be committed)

High-level repository structure:
- `bot.py` — entry point and handler registration
- `database.py` — database access helpers
- `game/` — game logic
- `handlers/` — Telegram handlers
- `locales/` — i18n files
- `CLAUDE.md` — current technical/context file
- `GAME_FOUNDATION.md` — design and balance foundation

## Mandatory reading order for non-trivial tasks
For any medium or large task, read in this order:
1. `AGENTS.md`
2. `CLAUDE.md`
3. `GAME_FOUNDATION.md`
4. the target file(s)
5. directly related neighboring files

## Current design rules
Treat the following as approved project rules unless the user explicitly changes them.

### Combat and balance
- The game does **not** use rigid classes selected at character creation.
- Archetypes are formed through weapon choice, attributes, skill trees, and equipment.
- Pure specializations should be strongest in their narrow role.
- Hybrid builds must remain viable, but must not outperform pure builds in the pure build's main job.
- Balance should be achieved through trade-offs and opportunity cost, not arbitrary hard restrictions, unless a hard restriction is truly necessary.

### Equipment philosophy
- No artificial penalty system for "wrong armor" by default.
- No hard binding of offhand items to weapon classes by default.
- Those choices should self-balance through stat distribution, scaling, and opportunity cost.

### Progression
- Level cap target: 100.
- Default design assumption: 3 attribute points per level.
- Extra player power may also come from consumables, titles, runes/gems, upgrades, and rare/unique gear.

## Important implementation constraints

### i18n
All player-facing text must go through the i18n system.
Do not hardcode gameplay UI strings if an existing i18n path exists.
When adding new content:
- add code/data entry;
- add locale entries for all supported languages used by the repository.

### Battle state
Combat currently relies on `context.user_data['battle']`.
Do not casually replace this with a new state model unless the task explicitly calls for a migration.
Prefer incremental refactors.

### Cooldowns and rewards
Skill cooldown behavior and battle reward flow are already part of the current game loop.
Do not change cooldown reset behavior or post-battle reward logic unless the task explicitly asks for it.

### Database safety
- Avoid destructive schema changes unless explicitly requested.
- Prefer backward-compatible changes.
- If a schema change is required, explain it clearly in the final summary.
- Never invent tables or columns without checking the existing DB model and repository usage first.

## Editing rules
When implementing changes:
1. Make the smallest coherent change that actually solves the task.
2. Preserve existing public behavior unless the task says to change it.
3. Keep imports tidy.
4. Do not silently delete existing mechanics just because they look imperfect.
5. If you find a bug outside the requested area, mention it in the summary instead of expanding scope aggressively.

## How to respond after changes
After completing a task, provide:
1. what changed;
2. which files changed;
3. any important assumptions;
4. any follow-up risks or next recommended step.

## Good task style for this repository
Codex performs best here when the task includes:
- goal;
- files to inspect/edit;
- constraints;
- done criteria.

Preferred example shape:
- Goal: unify enemy turn logic in combat.
- Files: `game/combat.py`, `handlers/battle.py`, `game/skill_engine.py`.
- Constraints: keep current battle state structure and do not break existing callback flow.
- Done when: normal attacks and skill usage resolve enemy turns through the same pipeline.

## What to avoid
- Do not assume previous assistant-generated patches are already merged.
- Do not perform broad repo-wide refactors without explicit approval.
- Do not introduce complex frameworks or unnecessary dependencies.
- Do not replace readable procedural code with advanced patterns unless there is a clear payoff.
- Do not ignore `CLAUDE.md` or `GAME_FOUNDATION.md` when working on systems that touch gameplay.
