# Project State Current

This file is the source of truth for the currently confirmed merged state of the RPG bot project.

Do not record planned, discussed, or unmerged work as confirmed state.

Last updated after merge:
- PR: Balance V2 PR4: Expanded Sampling / Multi-seed Confidence Pass
- Status: simulation/reporting multi-seed balance confidence diagnostics
- Confirmed state below reflects current merged main after Balance V2 PR4 expanded sampling / multi-seed confidence diagnostics and includes prior Balance V2 PR3 controlled late-stage mob pressure tuning, Balance Instrument V2 Pressure Attribution / Lane Classifier, prior Balance Instrument V2 observability, PR15 actionable late-stage tuning, PR14 target calibration, PR13 targeted tuning, and PR12 first tuning pass baseline context

---

## Confirmed merged state

### Balance V2 PR4: Expanded Sampling / Multi-seed Confidence Pass

- added simulation/reporting-only multi-seed confidence diagnostics for remaining PR3 pressure-lane signals;
- compact PR3 lane counts remain visible as the regression baseline;
- PR4 compares compact lane counts against bounded multi-seed confidence counts;
- report markdown shows high-confidence and unstable remaining clusters;
- Sunscar pure support overpressure remains separated as bad matchup review, not automatic support buff or Sunscar nerf;
- no new tuning knobs were added;
- no live gameplay/runtime systems were changed;
- no Combat Core/formula/equipment/live mob/economy/targeting/teleport/live group combat changes were made;
- PR4 does not claim final balance.

### Balance V2 PR3: Controlled Late-Stage Mob Pressure Tuning Pass

- controlled simulation/reporting-only late-stage mob pressure tuning was applied to PR2 mob_pressure_lane clusters;
- PR3 classifier cleanup made mob_hp_too_low use turn-speed/clean-win pressure instead of player-win mob_hp_removed_pct = 1.00 alone;
- current mob_pressure_lane count after PR3 classifier cleanup is 41; route_expectation_lane count is 44; bad_matchup_review_lane count is 1;
- PR3 moved the classifier after semantic cleanup from the PR2 mob_pressure_lane baseline of 43 to 41;
- tuning uses bounded route-stage pressure adjustments rather than formula/equipment/live mob template changes;
- early-stage route expectation artifacts remain separated from late-stage actionable pressure;
- Sunscar pure support overpressure remains treated as bad matchup review, not automatic support buff or Sunscar nerf;
- report markdown preserves PR12–PR15, Observability, and Pressure Attribution sections;
- no live gameplay/runtime systems were changed;
- no formula/equipment/live mob/economy/targeting/teleport/live group combat changes were made.

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

### Balance Foundation Spec & Audit Skeleton (PR7)

- Balance Foundation Spec & Audit Skeleton is implemented:
  - release cap 100 documented;
  - T1–T10 gear/level bands documented;
  - macro progression bands documented;
  - HP/damage/TTK philosophy documented;
  - stat scaling philosophy documented;
  - equipment budget requirements documented;
  - enhancement risk/reward philosophy documented;
  - mob encounter-level scaling philosophy documented;
  - initial diagnostic audit skeleton exists;
  - no route/mob/skill/reward/formula tuning or live behavior changes included.

### Progression-aware Simulation Audit (PR8)

- Progression-aware simulation audit diagnostics are implemented:
  - simulation report data exposes progression-aware audit rows;
  - report exposes assumed player level, macro band, gear tier, pending gear assumptions, mob/node context, target/observed labels, and audit flags where available;
  - audit flags remain diagnostic-only;
  - gear budget, mob encounter scaling, pack/group simulation, route/mob/skill/reward/formula tuning, and live behavior changes are not included.



### Equipment Budget Foundation (PR9)

- equipment budget foundation is implemented for simulation/reporting;
- item level budget formula exists for 1–100;
- slot budget weights exist;
- rarity multipliers exist;
- enhancement multiplier curve exists for +0..+15;
- archetype allocation profiles exist;
- simulation gear presets produce real calculated stat bonuses;
- report v2 exposes formula-budget gear assumptions;
- live equipment runtime, loot/crafting, mob scaling, tuning, and gameplay behavior are not changed.

### Mob Encounter Scaling Foundation (PR10)

- formula-based mob encounter scaling is implemented for simulation/reporting;
- encounter levels are assigned to route-stage simulation samples;
- mob roles are assigned for simulation/reporting;
- scaled final mob stats are produced from base template, encounter level, role, and route pressure modifiers;
- report v2 exposes scaled mob context;
- live mob templates/gameplay, rewards, loot/crafting, pack/group simulation, and tuning are not changed.





### Balance Instrument V2 Observability Foundation

- compact/expanded balance report modes exist;
- capped turn-by-turn suspicious fight traces are available in simulation/reporting;
- per-fight observability metrics are exposed for balance review;
- checked-in compact report still preserves PR15 diagnostic values: raw/global overclean 87, actionable overclean 43, early-stage target artifacts 44, and representative overpressure risk `route_sunscar / route_exam / pure_support_solo_overlay player_death`;
- no live gameplay/runtime systems were changed;
- no tuning/formula/equipment/live mob changes were made.

### Balance Instrument V2 Pressure Attribution / Lane Classifier

- suspicious/actionable simulation cases expose likely pressure attribution labels;
- report data includes pressure attribution counts and recommended tuning lane counts;
- report markdown includes a pressure attribution preview for balance review;
- labels are diagnostic likely causes, not final balance verdicts;
- checked-in compact report still preserves PR15 diagnostic values: raw/global overclean 87, actionable overclean 43, early-stage target artifacts 44, and representative overpressure risk `route_sunscar / route_exam / pure_support_solo_overlay player_death`;
- no live gameplay/runtime systems were changed;
- no tuning/formula/equipment/live mob changes were made.

### Actionable Late-Stage Underpressure Tuning Pass (PR15)

- actionable overclean baseline from PR14 was 44;
- current checked-in compact report shows raw/global overclean candidates: 87;
- current actionable overclean after PR15 is 43;
- early-stage target artifacts remain 44;
- early-stage target artifacts remain separated and visible;
- raw global overclean signal remains visible for transparency;
- representative overpressure risk remains visible: route_sunscar / route_exam / pure_support_solo_overlay player_death;
- PR15 is not a final/clean balance pass;
- PR15 changed only simulation/reporting targeted late-stage pressure knobs;
- no live gameplay/runtime systems were changed.

### Target Expectation Calibration Pass (PR14)

- raw global overclean candidate signal remains visible in report data and report markdown;
- actionable overclean metric was added through target expectation calibration;
- early-stage target expectation artifact bucket was added for `soft_entry` / `identity_visible`;
- late-stage actionable underpressure remains visible for `build_testing` / `route_exam`;
- no live gameplay/runtime systems were changed.

### Targeted Alpha Tuning Pass (PR13)

- overclean cluster rollups were added to report data (`overclean_rollups`, `overclean_top_clusters`);
- selected route/stage/archetype tuning targets are surfaced in the v2 report `PR13 Targeted Tuning Candidates` section;
- targeted simulation-only route-stage pressure overrides were added for late-stage underpressure clusters;
- PR13 introduced the global-vs-late-stage overclean split and late-stage-only targeted candidate table;
- at PR13 time, the compact report baseline showed global overclean candidates 88 and late-stage targeted overclean audit flags 43;
- later PR14/PR15 report current calibrated/current counts are tracked in the PR14/PR15 sections;
- global overclean remains a known underpressure signal;
- targeted route-stage pressure overrides were added for simulation/reporting-only late-stage tuning;
- pack proxy remains active as simulation/reporting-only (`composite_pack_pressure_v1`);
- no live group combat, no targeting, no teleport, no economy overhaul, and no Combat Core rewrite were implemented.

### First Real Tuning Pass (PR12)

- PR12: First Real Tuning Pass remains prior baseline context.
- simulation policy artifacts were reduced in report/simulation policy handling;
- guardian_shield_1h and holy_rod_paladin use simulation-only guard_then_attack policy;
- simulation-stage pressure modifiers were added for first controlled numeric alpha pressure tuning;
- report v2 now includes `PR12 First Tuning Pass Summary` with changed policy assumptions and diagnostic counts;
- changed policy and numeric knobs are documented in the report summary;
- pack proxy remains active as simulation/reporting-only (`composite_pack_pressure_v1`);
- no live group combat, no targeting, no teleport, no economy overhaul, and no Combat Core rewrite were implemented;
- no live gameplay runtime systems (loot/crafting/equipment runtime/economy) were changed by PR12.

### Pack/Group Simulation Harness (PR11)

- simulation/reporting-only pack pressure harness is implemented;
- pack samples exist for alpha routes at build_testing and route_exam;
- pack members use formula-based mob scaling;
- composite pack pressure proxy produces diagnostic final pack stats;
- report v2 exposes pack/group pressure context;
- live group combat, targeting, live spawning, rewards, loot/crafting, and tuning are not changed.
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

- No live route/mob/skill/reward/formula tuning outside accepted tuning PRs.
- PR12 includes simulation/reporting-only stage pressure tuning; live templates/runtime remain unchanged.
- No Combat Core rewrite.
- No smart autobattle policy.
- No live AFK/autopilot.
- No live group/pack combat.
- No full multi-target runtime pack combat; PR11 only has simulation/reporting composite pack pressure proxy.
- No targeting rollout.
- No live spawning changes.
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
