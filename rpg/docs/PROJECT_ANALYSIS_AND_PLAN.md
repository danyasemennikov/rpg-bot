# Project Analysis and Plan

## 1. Confirmed Merged State
The project has successfully migrated to the new Google AI workflow (PR #213 is merged). The new workflow utilizes Gemini/Gems for design, balance, and review, while Jules serves as the designated implementation coding agent.

Functionally, the actual `main` branch codebase contains a fully working combat system and skill engine. Crucially, multiple weapon classes and families are already implemented and present in the runtime codebase (e.g., in `rpg/game/skills.py`), including bows, 2-handed swords, 2-handed axes, magic staffs, holy staffs, wands, holy rods, tomes, and venom daggers. The core combat foundation is stable and functional.

## 2. Current Active Focus
Derived strictly from `PROJECT_STATE_CURRENT.md`, the current active focus is on:
- Route-specific alpha pressure profile validation.
- Open-world route fairness for different build archetypes.
- Route/class balance.
- Route fairness for different builds.
- Alpha-ready loop stabilization.

## 3. Stale/Deprecated Docs Warnings
Older repository documentation may conflict with the current state or the new Google AI workflow:
- `rpg/AGENTS.md` currently references `CLAUDE.md` and `GAME_FOUNDATION.md` as mandatory reading, but these files no longer exist or are considered fully deprecated/removed.
- Any legacy documentation implying a single-agent workflow (like Claude alone) is stale. The project now strictly adheres to the workflow outlined in `rpg/docs/GOOGLE_AI_WORKFLOW.md` and `rpg/docs/AI_WORKFLOW.md`.
- Any legacy documentation claiming that major weapon families (like holy rods, staffs, or bows) are "missing" is strictly incorrect, as they are actively present in the codebase.

## 4. Real Next PR Candidates

### Candidate 1: Cleanup of Stale Documentation References
- **Goal**: Remove references to deleted/deprecated files (`CLAUDE.md`, `GAME_FOUNDATION.md`) from `rpg/AGENTS.md`.
- **Why now**: Ensures new AI agents do not get confused or loop while looking for missing mandatory reading files, aligning with the new workflow.
- **Likely files**: `rpg/AGENTS.md`
- **Non-goals**: No rewriting of other documentation, no changes to any `.py` files.
- **Test expectations**: No runtime tests are executed because this is a docs-only PR.
- **Project state impact**: `PROJECT_STATE_CURRENT.md not updated: no confirmed project state change.`

## 5. Non-goals
The project is explicitly avoiding the following right now:
- Editing any `.py` runtime files or tests.
- Proposing implementation of existing weapon families (bow, sword_2h, axe_2h, magic_staff, holy_staff, wand, holy_rod, tome, and Venom daggers are already in the code).
- Proposing "targeting rollout" (targeting is frozen).
- Proposing "teleport" (teleport is skipped).
- Proposing replacing the game foundation or adding massive subsystems.
