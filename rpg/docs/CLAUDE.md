# RPG Bot Technical Context Adapter

- Status: Active
- Authority: Supporting navigation; not a merged-state or roadmap authority
- Last reconciled: 2026-09-23, against `ad5435e577e45e63da2ca57af2296203d88cedd5`
- Historical snapshot: [CLAUDE_AT_PR231.md](archive/status/CLAUDE_AT_PR231.md)

This familiar path is retained as a compact adapter. Start with
[DOCS_INDEX.md](DOCS_INDEX.md) and [PROJECT_STATE_CURRENT.md](PROJECT_STATE_CURRENT.md)
instead of treating this file as a complete technical specification.

## Repository shape

- `rpg/bot.py` initializes the Telegram application and handlers.
- `rpg/database.py` owns shared SQLite access and core persistence helpers.
- `rpg/game/` contains domain logic and data authorities.
- `rpg/handlers/` contains Telegram interaction boundaries.
- `rpg/locales/` contains Russian, English, and Spanish player-facing text.
- `rpg/tests/` contains automated contracts, including legacy documentation consumers.
- `rpg/docs/` contains current authorities, foundations, system maps, delivery records,
  evidence, and history separated by [DOCS_INDEX.md](DOCS_INDEX.md).

Core stack: Python 3.12, `python-telegram-bot`, and SQLite.

## Technical navigation

- Combat/builds: [systems/README.md#combat-and-builds](systems/README.md#combat-and-builds)
- World/travel: [systems/README.md#world-and-travel](systems/README.md#world-and-travel)
- Gear/itemization/rewards: [systems/README.md#gear-itemization-and-rewards](systems/README.md#gear-itemization-and-rewards)
- Professions/economy: [systems/README.md#professions-and-economy](systems/README.md#professions-and-economy)
- PvE/chapter: [systems/README.md#pve-and-playable-chapter](systems/README.md#pve-and-playable-chapter)
- PvP: [systems/README.md#pvp](systems/README.md#pvp)

## Stable contributor constraints

- All player-facing text follows the repository i18n path and language coverage.
- Preserve existing persistence, battle-state, settlement, and migration authorities
  unless an accepted task explicitly changes them.
- Prefer incremental, readable changes; the repository owner has basic Python
  experience.
- Plans and foundations do not prove runtime implementation. Inspect the current code.
- Merge, deployment, review approval, and validation evidence are separate facts.
- Follow task-specific validation instructions. There is no blanket rule that every
  documentation or audit task runs pytest.

## Current delivery context

PR229, PR230, and PR231 are merged at the reconciled baseline. The concise capability
summary is in [PROJECT_STATE_CURRENT.md](PROJECT_STATE_CURRENT.md); detailed migration,
validation, and limitations remain in [epics/README.md](epics/README.md). The checked
PR231 evidence retains its original commit provenance and does not independently prove
every later final-main integration change.

For older database tables, callbacks, skill lists, and repository snapshots, consult
the preserved [CLAUDE PR231 snapshot](archive/status/CLAUDE_AT_PR231.md) as historical
context only, then verify the current code.
