# Project State Current

This file is the source of truth for the currently confirmed merged state of the RPG bot project.

Do not record planned, discussed, or unmerged work as confirmed state.

Last updated after merge:
- PR: Route Identity Gameplay Pass 2
- Status: playable pressure/composition tuning pass 2
- Confirmed state below reflects current merged `main` after route identity gameplay pass 2

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
