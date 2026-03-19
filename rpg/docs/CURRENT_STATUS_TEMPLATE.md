# CURRENT_STATUS.md

## Project
Telegram RPG bot

## Working mode
- Use ChatGPT chat for architecture, balance, specifications, and review.
- Use Codex for implementation in the repository.
- Do not assume any suggested patch is merged unless explicitly confirmed by the user.

## Main context files
- `CLAUDE.md`
- `GAME_FOUNDATION.md`
- `AGENTS.md`

## Repository
- Repo URL: <paste repo URL here>
- Current working branch/PR: <paste branch or PR here>

## Implemented
- Enemy-response unification refactor is merged:
  - shared `resolve_enemy_response(...)`
  - normal attack path uses shared enemy response
  - skill path uses shared enemy response
  - failed flee uses shared enemy response
- `apply_death(...)` commit fix is merged
- `apply_rewards(...)` now gives stat points per level gained

## Not yet done
- Pre-turn ticking is still duplicated:
  - `process_turn(...)`
  - skill branch in `handlers/battle.py`
- Balance formulas are not yet reworked to the new design foundation
- Current skills and data still need gradual cleanup after combat-flow stabilization

## Current source of truth
- Treat the current repository state as source of truth
- If a new Codex patch is proposed, review it before merge

## Next task
<describe the next task here>

## Notes
- User knows Python poorly, so explanations and code changes should stay simple and readable
- Prefer small safe incremental refactors over large rewrites
