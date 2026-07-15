# Project Analysis and Plan

## 1. Confirmed Merged State
The project has restored the active implementation workflow to Codex. ChatGPT / Producer / Specs handles architecture, design, PR scope, and review; Codex is the current implementation coding agent.

Functionally, the actual `main` branch codebase contains a fully working combat system and skill engine. Crucially, multiple weapon classes and families are already implemented and present in the runtime codebase (e.g., in `rpg/game/skills.py`), including bows, 2-handed swords, 2-handed axes, magic staffs, holy staffs, wands, holy rods, tomes, and venom daggers. The core combat foundation is stable and functional.

## 2. Current Active Focus
Derived strictly from `PROJECT_STATE_CURRENT.md`, the current active focus is on:
- Route-specific alpha pressure profile validation.
- Open-world route fairness for different build archetypes.
- Route/class balance.
- Route fairness for different builds.
- Alpha-ready loop stabilization.

## 3. Stale/Deprecated Docs Warnings
Older repository documentation may conflict with the current state or the restored Codex workflow:
- **Active Foundation Docs**: `rpg/docs/CLAUDE.md` and `rpg/docs/GAME_FOUNDATION.md` are active, canonical foundation documents and remain mandatory reading for medium/large or non-trivial tasks.
- Jules/Gemini workflow documents are historical/inactive unless explicitly marked current again. The project now follows `rpg/docs/AI_WORKFLOW.md` with Codex as implementation agent.
- Any legacy documentation claiming that major weapon families (like holy rods, staffs, or bows) are "missing" is strictly incorrect, as they are actively present in the codebase.

## 4. Real Next PR Candidates

### Candidate 1: Clarify Canonical Paths in AGENTS.md
- **Goal**: Clarify canonical paths to active foundation docs in `rpg/AGENTS.md` (update paths to point to `rpg/docs/CLAUDE.md` and `rpg/docs/GAME_FOUNDATION.md`).
- **Why now**: Resolves path discrepancies to ensure AI agents can successfully find mandatory reading files without confusion.
- **Likely files**: `rpg/AGENTS.md`
- **Non-goals**: No rewriting of other documentation, no deletion of core file references, no changes to any `.py` files.
- **Test expectations**: No runtime tests are executed because this is a docs-only PR.
- **Project state impact**: `PROJECT_STATE_CURRENT.md not updated: no confirmed project state change.`
- **Note**: This candidate is advisory only; do not implement it in this PR.

## 5. Non-goals
The project is explicitly avoiding the following right now:
- Editing any `.py` runtime files or tests.
- Proposing implementation of existing weapon families (bow, sword_2h, axe_2h, magic_staff, holy_staff, wand, holy_rod, tome, and Venom daggers are already in the code).
- Proposing "targeting rollout" (targeting is frozen).
- Proposing "teleport" (teleport is skipped).
- Proposing replacing the game foundation or adding massive subsystems.
