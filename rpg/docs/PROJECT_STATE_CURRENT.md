# Project State Current

This file is the source of truth for the currently confirmed merged state of the RPG bot project.

Do not record planned, discussed, or unmerged work as confirmed state.

Last updated after merge:
- PR: PR6: Alpha simulation report v2 diagnostic fidelity
- Status: alpha simulation/report diagnostic fidelity foundation
- Confirmed state below reflects current merged `main` after alpha simulation report v2 diagnostic fidelity

---

## Confirmed merged state

### World / Travel

- Full canonical world graph is live for ordinary travel.
- All canonical route nodes, branches, cross-links, and late nodes are reachable through ordinary travel.
- `capital_city` / Aster / Астер is the starter hub.
- `capital_city` has starter services:
  - shop
  - inn
  - quest_board
- New players spawn at `capital_city`.
- Discovery is canonical-id based.
- `capital_city` is discovered by default.
- Successful travel marks canonical destination discovery.
- Blocked travel does not mark discovery.
- Teleport is intentionally skipped and remains disabled.

### Legacy compatibility

Legacy aliases are preserved:

- `village -> hub_westwild`
- `dark_forest -> westwild_n7`
- `frontier_outpost -> hub_frostspine`
- `old_mines -> old_mine_entrance`

Legacy read paths and compatibility overlays remain supported.

### Open World Gameplay

- Open World Gameplay Rollout Phase 1 is implemented.
- Route Identity Gameplay Pass 1 is implemented:
  - full alpha routes have route-specific gameplay pressure metadata;
  - pressure expectations are depth-scaled through soft_entry / identity_visible / build_testing / route_exam;
  - route balance validation covers Westwild, Frostspine, Ashen Ruins, Mireveil, and Sunscar gameplay identity.
- Weapon-route matchup target metadata is implemented:
  - full alpha routes have design-target matchup metadata for route/weapon archetypes;
  - route reports expose matchup target labels for validation and future balance work;
  - the matchup matrix is metadata/reporting only, not direct runtime bonuses.
- Baseline route-aware PvE exists across the open world.
- Route Identity Gameplay Pass 2 is implemented:
  - full alpha routes have first-pass playable pressure/composition tuning;
  - route reports validate soft-entry safety, depth pressure, pressure density, and route-specific pressure archetypes;
  - weapon-route matchup targets remain metadata/reporting only and are not direct runtime bonuses.
- Baseline gathering surfaces exist across the open world.
- Route identity metadata is wired into world locations:
  - `world_id`
  - `region_id`
  - `zone_id`
  - `region_flavor_tags`
- Reward, gathering, and open-world metadata helpers can resolve representative route nodes.
- Old Mine remains a sparse stub, not an elite mini-dungeon or live boss anchor.
- South Coast remains a sparse coastal stub.

### Alpha Gate

Alpha release gate PR3P is implemented.

Alpha-ready routes:

- `route_westwild`
- `route_frostspine`
- `route_ashen_ruins`
- `route_mireveil`
- `route_sunscar`

Known blocked routes:
- none currently

Sparse stub routes:

- `route_south_coast_stub`
- `route_old_mine_stub`

Alpha readiness policy:

- Alpha readiness accepts route-specific combat pressure profiles.
- Pack pressure is required only where route identity requires it.
- `route_sunscar` is alpha-ready through `solo_elite_precision_skirmish`, not pack pressure.

### Combat / Systems

- Combat Core v1 is implemented.
- Weapon family rollout is implemented.
- Accuracy/Evasion is implemented.
- Equipment runtime hooks are implemented.
- Gear instances are implemented.
- Equipment enhancement phase 1 is implemented.
- Open-world PvE runtime foundations exist.
- Live PvP foundations exist.
- Targeting rollout is frozen.
- Headless Combat Simulation Foundation is implemented:
  - deterministic player-vs-mob simulations run through existing combat rails;
  - simulation results expose winner, turns, HP/mana, action, and safety metrics;
  - simulations do not grant rewards or mutate player progression;
  - route/class simulation matrix, final balance reports, and live AFK autopilot are deferred.
- Alpha Combat Simulation Archetype Presets are implemented:
  - full alpha validation archetypes have simulation preset metadata;
  - presets cover `soft_entry` / `identity_visible` / `build_testing` / `route_exam` power tiers;
  - archetype policy and preferred skill metadata exist for future reports;
  - smoke simulations can instantiate and run archetype presets through the headless simulation foundation;
  - route/class matrix reports, safe skill execution adapters, final balance reports, and live AFK autopilot remain deferred.
- Safe Simulation Skill Action Adapter is implemented:
  - headless simulations can execute selected player skills through existing skill/combat rails;
  - simulation skill levels, mana spending, and cooldowns are local to the simulation;
  - simulations do not read/write live player mastery or DB cooldown state when using simulation overrides;
  - route/class matrix reports, final balance reports, and live AFK autopilot remain deferred.
- Route Stage Simulation Matrix Foundation is implemented:
  - route × depth stage × archetype representative simulation runs can be generated;
  - matrix output includes raw runs and archetype summaries with win/death/turn/resource/action/skill metrics;
  - route-stage samples are deterministic representative solo samples from canonical route location data;
  - final balance reports, tuning recommendations, pack/group simulation matrices, and live AFK/autopilot remain deferred.
- Alpha Balance Report v1 is implemented:
  - route-stage simulation matrix data can be rendered into a diagnostic alpha route/class balance report;
  - report compares observed simulation pressure labels against route matchup target metadata where mapping exists;
  - report surfaces suspicious matchup candidates and limitations for future tuning;
  - no route, mob, skill, reward, formula, pack/group matrix, or live AFK/autopilot changes are included.
- Alpha Simulation Report v2 diagnostic fidelity is implemented:
  - report v2 exposes scenario/mob cards for representative route-stage samples;
  - report v2 exposes archetype/power-tier/loadout/skill/policy cards for simulation presets;
  - report v2 includes richer run and aggregate diagnostic metrics beyond win rate;
  - report v2 distinguishes death, timeout, no-progress, resource/policy issues where inferable;
  - report v2 includes capped representative suspicious fight traces;
  - no route, mob, skill, reward, formula, pack/group matrix, or live AFK/autopilot changes are included.

---

## Current focus

- Route-specific alpha pressure profile validation.
- Open-world route fairness for different build archetypes.
- Route/class balance.
- Route fairness for different builds.
- Alpha-ready loop stabilization.

---

## Explicit non-goals / deferred

Do not treat these as active scope unless a new accepted Decision Packet explicitly changes them:

- No route/mob/skill/reward/formula tuning.
- No Combat Core rewrite.
- No smart autobattle policy.
- No live AFK/autopilot.
- No group/pack simulation matrix.
- No targeting rollout.
- No teleport.
- No direct weapon-route bonuses.
- No resistance framework.
- No DB schema changes.

- Teleport phase 1.
- Dungeon runtime expansion.
- World boss runtime expansion.
- Castle/core-war systems.
- Broad targeting rollout.
- Full economy overhaul.
- Large combat formula rewrite.

---

## Standard local test command

From the `rpg` folder:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Universal Windows PowerShell fallback:

```powershell
$repo = if (Test-Path "C:\Users\User\Documents\GitHub\rpg-bot\rpg") { "C:\Users\User\Documents\GitHub\rpg-bot\rpg" } elseif (Test-Path "C:\Users\PC\Documents\GitHub\rpg-bot\rpg") { "C:\Users\PC\Documents\GitHub\rpg-bot\rpg" } elseif (Test-Path "C:\Users\35191\Documents\GitHub\rpg-bot\rpg") { "C:\Users\35191\Documents\GitHub\rpg-bot\rpg" } else { (Get-Location).Path }; Set-Location $repo; if (Test-Path "..\.venv\Scripts\python.exe") { ..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" } elseif (Test-Path ".\.venv\Scripts\python.exe") { .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" } else { py -3 -m unittest discover -s tests -p "test_*.py" }
```

---

## Update policy

Update this file in the same PR when a change modifies confirmed project state.

Examples of changes that must update this file:

- A route becomes alpha-ready.
- A known blocker is fixed or added.
- A major system is merged.
- A deferred system becomes active scope.
- A confirmed non-goal changes.
- A new standard test command is adopted.
- A rollout phase is completed.

Do not update this file for:

- Pure refactors with no state change.
- Test-only stabilization.
- Typo fixes.
- Internal cleanup that does not change confirmed project status.

If a PR does not update this file, its summary must explicitly say:

`PROJECT_STATE_CURRENT.md not updated: no confirmed project state change.`
