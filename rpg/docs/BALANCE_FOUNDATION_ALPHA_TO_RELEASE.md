# Balance Foundation: Alpha to Release

## Balance V2 PR6 Simulation Policy & Skill Economy Clarification Note

- Adds simulation/reporting-only policy coverage and skill economy diagnostics around PR5 budget interpretation.
- Separates simulation policy artifacts from real skill economy risks before any future tuning branch uses unified combat budget rows.
- Adds expected rotation profiles for selected alpha archetypes using implemented skill ids only; missing design-intended skills are reported as diagnostics rather than added as live skills.
- Adds concise skill economy labels from existing simulation observability, including mana pressure and normal-attack fallback rates.
- Cooldown-blocked turn counts remain follow-up instrumentation because they are not safely observable in current report rows.
- PvP remains proxy-only, and route/mob/gear/PvP tuning remains deferred.
- Does not tune weapon numbers, skill numbers, armor stats, gear formulas, enhancement curves, routes, mobs, rewards/economy/loot/crafting, targeting, teleport, or live group combat.
- Does not change live gameplay/runtime, Combat Core behavior, formulas, equipment budget formulas, live mob templates, economy/rewards, targeting, teleport, or live group combat.
- Does not add new tuning knobs and does not claim final balance.

## Balance V2 PR5 Progression-aware Unified PvE/PvP Combat Budget Audit Note

- Adds simulation/reporting-only unified combat budget diagnostics across all current alpha archetypes.
- Covers six progression level bands and five gear states from undergeared through overgeared_high_enhancement.
- Reuses existing item-level budget, slot weight, rarity multiplier, enhancement multiplier, and archetype/profile allocation formulas.
- Adds PvE budget summary and a clearly labeled PvP budget proxy; the proxy is not real headless PvP duel win-rate data.
- Reconciles PR4 route-pressure lanes as scoped late-stage mob_pressure_lane evidence only.
- Does not tune weapon numbers, skill numbers, armor stats, gear formulas, enhancement curves, routes, mobs, rewards/economy/loot/crafting, targeting, teleport, or live group combat.
- Does not change live gameplay/runtime, Combat Core behavior, formulas, equipment budget formulas, live mob templates, economy/rewards, targeting, teleport, or live group combat.
- Does not add new tuning knobs and does not claim final balance.

## Balance V2 PR4 Expanded Sampling / Multi-seed Confidence Pass Note

- Adds simulation/reporting-only multi-seed confidence diagnostics for remaining PR3 pressure-lane signals.
- Does not tune balance numbers.
- No new tuning knobs are added.
- Does not replace the compact PR3 regression baseline.
- Does not change live gameplay/runtime, formulas, equipment budget, live mob templates, economy/rewards, targeting, teleport, or live group combat.
- No live gameplay/runtime, formula, equipment budget, live mob template, economy/reward, targeting, teleport, or live group combat changes are made.
- Does not claim final balance.

## Balance V2 PR3 Controlled Late-Stage Mob Pressure Tuning Pass Note

- Implements controlled simulation/reporting-only late-stage mob pressure tuning.
- Uses PR2 pressure attribution lanes.
- Does not tune route expectation artifacts.
- Does not automatically fix Sunscar pure support bad matchup.
- Does not change live gameplay/runtime, formulas, equipment budgets, live mob templates, rewards/economy, targeting, teleport, or live group combat.
- Does not claim final balance.

## Balance Instrument V2 PR1 Observability Foundation Note

- Adds simulation/reporting-only observability foundation.
- Adds compact/expanded balance report mode support.
- Adds capped suspicious fight turn traces and per-fight observability metrics.
- Does not change live gameplay/runtime systems.
- Does not change formulas, equipment budgets, live mob templates, rewards, economy, targeting, teleport, or live group combat.
- Does not rewrite Combat Core.
- Does not add live pack/group runtime combat.
- Does not claim final balance.


## A. Purpose and Scope
This document defines the release-grade balance foundation for **level 1–100** progression.

This is a **specification and audit foundation**, not a live tuning patch. It does **not** change live combat, mobs, rewards, skills, equipment runtime, formulas, travel, PvP, PvE runtime, or player-facing gameplay behavior.

## B. Confirmed Release Cap
- **Max release level: 100**.
- Level 150 is future expansion-scale content and is **not** part of the current balance model.

## C. Level Bands and Gear Tiers
Release foundation uses 10-level gear tier bands:
- **T1:** 1–10
- **T2:** 11–20
- **T3:** 21–30
- **T4:** 31–40
- **T5:** 41–50
- **T6:** 51–60
- **T7:** 61–70
- **T8:** 71–80
- **T9:** 81–90
- **T10:** 91–100

## D. Macro Progression Bands
The model uses conservative macro progression bands:
- **bootstrap:** 1–10
- **frontier:** 11–20
- **specialization:** 21–35
- **structured midgame:** 36–55
- **late midgame:** 56–75
- **late game:** 76–90
- **apex:** 91–100

These are directional foundation bands for reporting and audit interpretation.

## E. HP Scale Philosophy
HP scale is directional and intentionally approximate (not final formulas):
- Level 1 average player around **100 HP**.
- Level 100 average DPS/caster roughly **tens of thousands HP**.
- Level 100 bruiser/paladin should be materially higher than average DPS/caster.
- Level 100 real tank with good gear can reach around **45k–60k+ HP**.

Exact final HP formulas are deferred to later tuning and budget PRs.

## F. Damage Scale Philosophy
Damage must scale with HP so high-level combat does not degrade into long low-pressure 60-turn fights.

Directional expected damage-per-turn behavior:
- low-level baseline should preserve clarity and readable pacing;
- midgame should show meaningful build divergence;
- high-level expected DPT should keep equal-level fights in target TTK ranges;
- burst windows and sustain windows should both matter;
- directional targets are not final formulas.

## G. TTK Targets
Equal-level directional TTK targets:
- old trivial mob: **1–2 turns**
- normal mob: **3–6 turns**
- pressure mob: **5–9 turns**
- elite solo: **8–15 turns**
- bad-matchup elite: **12–20 turns**
- pack: depends on AoE/control/sustain
- boss/group: separate future scale

## H. Stat Scaling Philosophy
- Levels **1–30**: stats are very noticeable.
- Levels **31–70**: stats define build direction.
- Levels **71–100**: stats still matter, but major power spikes increasingly come from gear quality, enhancement, rolls, item level, and build completion.
- Soft caps are required for dodge, crit, mitigation, and offensive scaling so late-game balance does not collapse.

## I. Equipment Power Model
PR7 does not implement the release-grade equipment budget. PR7 records the requirements explicitly.

Missing release-grade equipment budget components:
- item level budget;
- slot budget;
- weapon budget;
- armor budget;
- offhand budget;
- accessory budget;
- rarity multipliers;
- enhancement power curve;
- secondary modifier pools;
- expected gear by player level;
- expected gear by content tier;
- simulation gear presets.

Additional equipment philosophy constraints:
- gear tiers are 10-level bands;
- good gear identity can live forward through tier advancement;
- high-rarity items should be rare and expensive to carry forward;
- level 100 baseline must not assume full legendary/full +15/unique gear.

### What PR9 must define
- [ ] item-level budget curve by level band (1–100)
- [ ] per-slot budget allocations and slot weighting
- [ ] weapon vs armor vs offhand vs accessory budget split
- [ ] rarity multiplier ladder and rarity availability assumptions by tier
- [ ] enhancement power curve targets and expected fail/risk economics
- [ ] secondary modifier pool families and budget envelopes
- [ ] expected player gear baselines by level and content tier
- [ ] simulation gear presets aligned to baseline assumptions
- [ ] policy for carry-forward identity without invalidating tier upgrades
- [ ] level 100 baseline package that does not assume full best-in-slot perfection

## J. Enhancement Risk/Reward Philosophy
Enhancement phase 1 concept is retained as foundation direction:
- low enhancement should be safe and modest;
- high enhancement should be risky and meaningful;
- high + levels should not be cosmetic only;
- prefer smooth/geometric growth over sudden huge breakpoints.

PR7 does not change enhancement formulas.

## K. Mob Encounter-Level Scaling Philosophy
Future model direction:

final_mob_stats =
base_template
× encounter_level_curve
× role_multiplier
× route_pressure_modifier
× elite/boss modifier

Roles in scope direction:
- normal
- pressure
- elite
- pack_member
- pack_leader
- boss (later)

The same mob template can appear at different depths when final stats scale by encounter level.

## L. Simulation and Audit Requirements
Future audit/report rows should include:
- player level
- expected player band
- gear tier
- rarity assumption
- enhancement assumption
- skill level
- mob template
- encounter level
- mob role
- node depth
- final mob stats
- expected difficulty
- observed result
- reason for mismatch

Future diagnostic flags (planned catalog):
- underleveled_mob_for_node
- overleveled_player_for_sample
- unscaled_template_reused_across_depths
- hard_target_tested_on_weak_sample
- overclean_win
- policy_failure_guard_loop
- support_overstall
- missing_pack_sample
- missing_elite_sample

PR7 delivers only an initial skeleton flag surface, not the full report pipeline.
PR8 note (implemented diagnostic layer only):
- PR8 introduces progression-aware audit context in simulation reports.
- PR8 does not implement equipment budgets or encounter-level scaling.
- Gear rarity/enhancement assumptions were pending PR9 in PR8 and are now implemented in PR9 simulation/reporting scope.


## M. Release-grade Balance Arc
Implemented diagnostic/foundation steps:
- **PR8:** Progression-aware Simulation Audit
- **PR9:** Equipment Budget Foundation
- **PR10:** Mob Encounter Scaling Foundation
- **PR11:** Pack/Group Simulation Harness

Implemented tuning work:
- **PR12:** First Real Tuning Pass

PR11 note (implemented simulation/reporting foundation only):
- PR11 implements simulation/reporting-only pack/group pressure harness.
- It uses `composite_pack_pressure_v1` proxy.
- It does not implement live group combat, targeting, live spawning, tuning, rewards, loot, or Combat Core rewrite.
- PR12 remains responsible for first real tuning pass.

## N. Non-goals
PR7 non-goals:
- no one-shot rebalance;
- no route/mob tuning;
- no skill rebalance;
- no Combat Core rewrite;
- no live AFK/autopilot;
- no targeting;
- no teleport;
- no pack/group harness in PR7.


PR9 note (implemented simulation/reporting foundation only):
- PR9 implements item-level budget, slot weights, rarity multipliers, enhancement multipliers, archetype allocation profiles, and simulation gear presets for headless simulation/reporting.
- PR9 does not change live equipment runtime, loot/crafting/drop behavior, or player DB/equipment migration.
- PR9 did not implement mob encounter scaling; PR10 later implemented simulation/reporting encounter scaling.


PR10 note (implemented simulation/reporting foundation only):
- PR10 implements formula-based mob encounter scaling for simulation/reporting.
- Final simulation mob stats now use base template × encounter level curve × mob role multiplier × route pressure modifier.
- PR10 does not change live mob templates or live gameplay behavior.
- PR10 does not change rewards, loot/crafting, equipment runtime, or player DB.
- PR10 did not implement pack/group simulation; PR11 later implemented simulation/reporting composite pack pressure harness.
- PR10 is not the first real tuning pass; PR12 remains responsible.

PR12 note (implemented first controlled tuning pass):
- PR12 reduces simulation policy artifacts (guard-loop fallback behavior) before drawing tuning conclusions.
- PR12 adds a dedicated report summary section for changed policy assumptions/knobs and diagnostic counts.
- PR12 applies limited report-backed alpha tuning only, including simulation-stage pressure modifiers (soft_entry baseline, identity/build/route_exam pressure lift).
- PR12 does not implement Combat Core rewrite, targeting, live group combat, teleport, economy overhaul, or broad weapon-family rebalance.



PR13 note (implemented simulation/reporting tuning pass only):
- PR13 implements targeted simulation/reporting alpha tuning based on PR12 overclean clusters.
- It does not change live gameplay/runtime systems unless explicitly stated by the PR.
- It does not implement final balance.


PR14 note (implemented simulation/reporting target expectation calibration only):
- PR14 adds target expectation calibration buckets in simulation/reporting outputs so raw global overclean, actionable overclean, early-stage target artifacts, and late-stage actionable rows are separated.
- PR14 does not change live gameplay/runtime systems.
- PR14 does not claim final balance.

PR15 note (implemented actionable late-stage simulation/reporting tuning only):
- PR15 implements simulation/reporting-only actionable late-stage tuning based on PR14 calibrated actionable overclean.
- PR15 does not change live gameplay/runtime systems.
- PR15 does not claim final balance.


PR2 Balance Instrument V2 pressure attribution note (implemented simulation/reporting diagnostics only):
- Adds simulation/reporting-only pressure attribution / lane classifier.
- Uses PR1 observability metrics to classify likely causes.
- Labels are diagnostic likely causes, not final balance verdicts.
- Does not change live gameplay/runtime systems.
- Does not change formulas, equipment budget, live mob templates, rewards/economy, targeting, teleport, or live group combat.
- Does not claim final balance.

## Balance V2 PR7 Profile-aware Simulation Policy Execution Pilot

- Diagnostic/simulation-only pilot; no live tuning or gameplay/runtime changes.
- Profile-aware simulation policies are active only for pilot archetypes: `daggers_venom`, `daggers_evasion`, `bow_sniper`, `magic_staff_destruction`, `holy_staff_solo`.
- Metadata-only registry policies (`aggressive_burst`, `venom_setup`, `evasion_tempo`, `sniper_precision`, `control_caster`, `solo_support_sustain`, `toolbox_balanced`) were not globally flipped executable.
- PR6 policy coverage remains 14 archetypes and PR6 skill economy diagnostics remain 14 archetypes.
- PR5 audit remains 420 rows (14 archetypes × 6 level bands × 5 gear states).
- PvP remains proxy-only; route/mob/gear/PvP tuning remains deferred.
