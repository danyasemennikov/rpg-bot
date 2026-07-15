# AI Context Bootstrap

This document provides a compact but useful overview of the RPG bot project for AI assistants.
It is intended to bootstrap AI assistants with the current project state, rules, and constraints without relying on old chat memory.

## Project State
**GitHub `main` and `rpg/docs/PROJECT_STATE_CURRENT.md` are the ultimate source of truth for the project.**
Do not treat any planned, discussed, or unmerged work as confirmed state.

*Current confirmed state summary:*
- **Codex Workflow Restoration** is the latest workflow/docs state.
- **Balance V2 PR8 Simulation Action Resolution / Fallback Attribution** remains the latest gameplay/simulation/balance confirmed state before this docs migration.
- No gameplay/runtime/formula/equipment/mob/economy/targeting/teleport/cooldown reset/reward/live group combat changes were made by this workflow docs update.

## Workflow Rules
- The project follows the active Codex implementation workflow (`rpg/docs/AI_WORKFLOW.md`).
- ChatGPT / Design & Balance handles theory, design, and balance.
- ChatGPT / Producer / Specs handles implementation planning, PR scope, Codex prompts, and review guidance.
- **Codex** is the current implementation coding agent.
- Unrelated large scopes must not be mixed.
- Cheap tails should be fixed before merge.
- Do not replace existing rails with a new foundation unless necessary.

## Hard Constraints
- **Teleport remains skipped.**
- **Targeting rollout remains frozen.**
- Do not record planned/unmerged work as confirmed state.
- Do not change gameplay code, combat, balance, world, routes, rewards, equipment, PvP, targeting, teleport, economy, or runtime behavior unless explicitly requested and confirmed by a design decision packet.
- Do not claim that future workflow experiments are confirmed gameplay state.

## What Not to Assume
- Do not assume that the current database structure or legacy combat states should be casually replaced.
- Do not assume that theoretical design discussions mean that code has already been written.
- Do not assume that unmerged `*_v2.py` files exist or are active.
- Do not create external workflow files directly from the repository unless explicitly requested.

## Standard Test Command
To verify changes, use the standard test command from the `rpg` directory:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
```

Universal Windows PowerShell fallback:
```powershell
$repo = if (Test-Path "C:\Users\User\Documents\GitHub\rpg-bot\rpg") { "C:\Users\User\Documents\GitHub\rpg-bot\rpg" } elseif (Test-Path "C:\Users\PC\Documents\GitHub\rpg-bot\rpg") { "C:\Users\PC\Documents\GitHub\rpg-bot\rpg" } elseif (Test-Path "C:\Users\35191\Documents\GitHub\rpg-bot\rpg") { "C:\Users\35191\Documents\GitHub\rpg-bot\rpg" } else { (Get-Location).Path }; Set-Location $repo; if (Test-Path "..\.venv\Scripts\python.exe") { ..\.venv\Scripts\python.exe -m pytest -q } elseif (Test-Path ".\.venv\Scripts\python.exe") { .\.venv\Scripts\python.exe -m pytest -q } else { py -3 -m pytest -q }
```
