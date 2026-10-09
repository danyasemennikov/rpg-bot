# Project State Current

- Status: Active
- Authority: Canonical for confirmed merged state
- Last reconciled: 2026-10-07, against `3c5bfa62836c705a6327ce059f4e190b54ccf3e6`
- Full prior snapshot: [archive/status/PROJECT_STATE_CURRENT_AT_PR231.md](archive/status/PROJECT_STATE_CURRENT_AT_PR231.md)

This current section is the only merged-state summary. Plans belong in
[ROADMAP_CURRENT.md](ROADMAP_CURRENT.md); delivery detail belongs in Epic reports;
measured artifacts retain their own commit provenance. Merge does not establish
deployment.

## Verified baseline

- [PR229 — Playable Alpha Vertical Slice V1](https://github.com/danyasemennikov/rpg-bot/pull/229): merged.
- [PR230 — Itemization, Regional Loot & Reliable Gear Progression V1](https://github.com/danyasemennikov/rpg-bot/pull/230): merged.
- [PR231 — Character Builds & Combat Identity V1](https://github.com/danyasemennikov/rpg-bot/pull/231): merged.
- [PR232 — Documentation Architecture & Consolidation V1](https://github.com/danyasemennikov/rpg-bot/pull/232): merged.
- [PR233 — Professions & Economy V1](https://github.com/danyasemennikov/rpg-bot/pull/233): merged.
- [PR234 — Regional Adventures & Opportunities V1](https://github.com/danyasemennikov/rpg-bot/pull/234): merged.
- PR234 merge: `adcc0baeee96c03852ed75c09e379b0c49be01d1`.
- [PR236 — restore live PvE combat start](https://github.com/danyasemennikov/rpg-bot/pull/236): merged 2026-10-04; verified PXE1 baseline/current `origin/main`: `3c5bfa62836c705a6327ce059f4e190b54ccf3e6`.

The repository establishes merge state only. Deployment, live-account smoke, and
production operation require separate evidence.

## Unmerged PXE1 candidate

[PXE1 frozen contract](epics/PLAYER_EXPERIENCE_ECONOMY_V1_SPEC.md) is implemented in
[Draft PR #237](https://github.com/danyasemennikov/rpg-bot/pull/237) on
`feat/pxe1-player-experience-economy-v1`; all seven bounded review repairs are validated; narrow independent re-review is pending.
Candidate behavior and measured results belong
to its report/evidence and [system owner map](systems/README.md#pxe1-candidate-owners).
They do not alter the confirmed baseline described below. PXE1 human Telegram validation
is **NOT RUN**; deployment is unverified; independent review of the prior HEAD returned FIX and narrow re-review is pending.

## Playable chapter and world

- The Aster–Elmor playable chapter connects registration/starter state, journal
  assignments, ordinary travel, combat, gathering, bounded hunting, crafting, sales,
  and chapter rewards.
- Ordinary travel uses the canonical world graph. Five routes are alpha-ready:
  `route_westwild`, `route_frostspine`, `route_ashen_ruins`, `route_mireveil`, and
  `route_sunscar`. The two sparse stubs are `route_south_coast_stub` and
  `route_old_mine_stub`.
- Teleport activation is disabled. The retained teleport document is deferred design,
  not live capability.

## Combat and character builds

- The canonical catalogue has 10 weapon families, 20 branches, and 100 canonical
  branch skills, plus universal Power Strike.
- Family-local mastery reaches M20. Skill ranks, legal branch allocation, reset,
  migration, and stale-preview/revision rails are implemented.
- A shared actor snapshot and action/effect evaluator serve durable PvE, the bounded
  PvP adapter, and production-aligned simulation paths.
- Historical balance reports remain diagnostics for their recorded baselines; they do
  not certify the final integrated PR231 main state.

## PvE

- Persistent participants and enemy units, durable orders/side results, explicit enemy
  profiles, and restart-safe state recovery are implemented.
- Group PvE supports real participants, named ally/party support, and bounded mixed
  encounters while preserving settlement and eligibility authorities.
- The current system is not a claim that every future expedition or structured-PvE
  feature is complete.

## Gear, loot, and progression

- PR230 supplies the 32-item field catalogue, deterministic vendors, five regional
  pools, rarity and dry-streak guarantees, instance-first comparison/mutation flows,
  enhancement/advancement bridges, and versioned two-stage PvE reward settlement.
- Legacy-review records remain owner-review evidence; ambiguous history is not
  automatically replayed or compensated.
- PR231 preserves the PR230 catalogue, ownership, reward provenance, settlement, and
  recovery guarantees while normalizing weapon identity through canonical families.

## Professions and economy

- Gathering profession persistence and progression are implemented, with the bounded
  level/XP/access rules represented by current runtime data.
- Hunting is bounded to implemented access, locations, eligible victories, extraction,
  and profession progression.
- PR233 supplies five gathering and seven crafting professions, 63 active recipes,
  28 mandatory materials, permanent recipe knowledge, durable economy receipts,
  and the bounded recovery and sale paths recorded in its delivery report.

## Regional adventures

- PR234 implements seven independent regional projects, discoveries and finite
  regional opportunities, three standing local jobs, surfaced/repaired existing
  hunts, named and mixed encounters, and three permanent local choices.
- The post-Chapter-I regional Journal adds no Chapter II or global campaign/finale.
- Existing combat settlement, hunt, profession, inventory, travel, equipment, and
  progression authorities remain canonical.
- Automated acceptance: COMPLETE. Historical broad-tested runtime:
  `ce88335267c6dbc05bef289e88deebd1fa28ea60`; repaired acceptance-test SHA:
  `43b5fb7a62f0265a89e20aeb9c3613f4605c56fc`; approved candidate:
  `436a0c1015766c38215f74ddb7ccd844a6c5a669`.
- Human Telegram validation: IN PROGRESS / interrupted by blocker in Session 1.
  HV1-B01 was observed on merged main
  `f581eb204b40f4d52ee2b709822c71906a7a8cd5`: Aster → First Patrol →
  `westwild_n1` / Wheat Fields → Attack: Rabbit x1 crashed before combat started
  because `start_battle` called `setdefault` on PTB's read-only `Application.user_data`.
  The repair changes PTB per-user state access to mutable `context.user_data`.
  Live Telegram revalidation of the repair is still pending.
  Session 1 remains incomplete; Returning solo and
  Two-player sessions remain outstanding. RAV1 is not fully playtested.
- Deployment is not established by merge. Exact validation results remain in
  [the delivery report](epics/REGIONAL_ADVENTURES_V1_REPORT.md) and historical evidence.

## PvP

- Existing engagement, legality/crime, death/loss, inventory, and outer policy remain
  authoritative.
- PR231 routes only normal attack, Guard, Power Strike, Quick Shot, Fireball, and Smite
  through the shared evaluator for supported V1 PvP.
- This bounded action set is not a claim of all-tree, group, or broader structured-PvP
  completion or balance.

## Current limits and evidence boundaries

- Teleport, castle/core-war systems, broader structured PvP, full economy overhaul,
  and other unapproved expansions remain deferred.
- PR231 checked evidence records its own rules commit and inputs. It does not
  independently validate later final-main integration changes or deployment.
- Macro progression-band differences across foundation/runtime documents remain an
  unresolved design question. This reconciliation does not choose a new band model.
- Operational validation, live latency/delivery, and broader play-balance conclusions
  require evidence beyond merge status.

## Navigation

- System owners: [systems/README.md](systems/README.md)
- Forward priorities: [ROADMAP_CURRENT.md](ROADMAP_CURRENT.md)
- Merged delivery records: [epics/README.md](epics/README.md)
- Evidence provenance: [evidence/README.md](evidence/README.md)
- Historical material: [archive/README.md](archive/README.md)

## Historical compatibility header markers

The lines below are retained only because legacy tests inspect text before the first
horizontal rule. They describe historical checkpoints and have **no authority** over
the current section above:

- PR: Codex Workflow Restoration (Docs only)
- Status: Balance V2 PR9 Availability-aware Profile Policy Selection
- Historical phrase: current merged main after Balance V2 PR9 Availability-aware Profile Policy Selection
- Historical phrase: prior PR218 test-suite SQLite isolation state
- Historical phrase: Balance V2 PR4 expanded sampling / multi-seed confidence diagnostics
- Historical phrase: Balance Instrument V2 Pressure Attribution / Lane Classifier
- Historical phrase: prior Balance Instrument V2 observability
- Historical phrase: PR15 actionable late-stage tuning
- Historical phrase: Balance V2 PR7 Profile-aware Simulation Policy Execution Pilot

---

## Confirmed merged state

> **Historical compatibility excerpt.** Everything from this heading through the next
> update-policy heading preserves old test-consumed wording and ordering. It is not a
> second current-state authority. See the current section above and the
> [full original snapshot](archive/status/PROJECT_STATE_CURRENT_AT_PR231.md) for context.

### PR228 / Gathering Profession Progression Baseline

Historical marker: persisted gathering XP/progression shipped before PR229.

### PR227 / Gathering Profession Persistence & Runtime Access Baseline

Historical marker: persisted gathering access shipped before PR228.

### PR226 / Alpha Core Loop Integration Baseline

Historical marker: the alpha core loop preceded the merged Epic trio.

### PR225 / Balance V2 PR13 Cooldown-Aware Normal Request Suppression

- Latest simulation-policy state: PR225 / Balance V2 PR13 Cooldown-Aware Normal Request Suppression.

### PR224 / Balance V2 PR12 Cooldown-Aware Shadow Policy Comparison

- Latest gameplay/balance diagnostic state: PR224 / Balance V2 PR12 Cooldown-Aware Shadow Policy Comparison.

### PR223 / Balance V2 PR11 Cooldown & Mana Policy Cause Attribution

- Latest gameplay/balance diagnostic state: PR223 / Balance V2 PR11 Cooldown & Mana Policy Cause Attribution.

### PR221 / Balance V2 PR10 Cooldown Fallback Diagnostic Breakdown

- Latest gameplay/balance diagnostic state: PR221 / Balance V2 PR10 Cooldown Fallback Diagnostic Breakdown.

### Balance V2 PR9 Availability-aware Profile Policy Selection

- Historical Status: Balance V2 PR9 Availability-aware Profile Policy Selection.

### PR218 Test Suite Baseline Stabilization / SQLite Runtime Test Isolation

- This PR did not change gameplay/balance diagnostic state; it stabilized the test baseline only.

### Codex Workflow Restoration

- PR: Codex Workflow Restoration (Docs only).
- This docs/workflow-only update did not change gameplay/balance diagnostic state.

### Balance V2 PR8 Simulation Action Resolution / Fallback Attribution

- Diagnostic/simulation/reporting-only action-resolution metadata was recorded.

### Balance V2 PR7 Profile-aware Simulation Policy Execution Pilot

- Diagnostic/simulation-only pilot covered exactly five historical archetype profiles.

### Balance V2 PR6: Simulation Policy & Skill Economy Clarification Pass

- Balance V2 PR6 Simulation Policy & Skill Economy Clarification was diagnostic/reporting-only.
- no new tuning knobs were added;
- no live gameplay/runtime systems were changed;
- no Combat Core/formula/equipment/live mob/economy/targeting/teleport/live group combat changes were made;
- the pass did not claim final balance.

### Balance V2 PR5: Progression-aware Unified PvE/PvP Combat Budget Audit

- Balance V2 PR5 Unified PvE/PvP Combat Budget Audit was simulation/reporting-only.
- no new tuning knobs were added;
- no live gameplay/runtime systems were changed;
- no Combat Core/formula/equipment/live mob/economy/targeting/teleport/live group combat changes were made.

### Balance V2 PR4: Expanded Sampling / Multi-seed Confidence Pass

- no new tuning knobs were added;
- no live gameplay/runtime changes were made;
- no final balance was claimed;
- targeting, teleport, and live group combat were unchanged.

### Balance V2 PR3: Controlled Late-Stage Mob Pressure Tuning Pass

- controlled simulation/reporting-only late-stage mob pressure tuning was applied;
- current mob_pressure_lane count after PR3 classifier cleanup is 41;
- route_expectation_lane count is 44;
- bad_matchup_review_lane count is 1;
- PR3 moved the classifier after semantic cleanup from the PR2 baseline;
- no formula/equipment/live mob/economy/targeting/teleport/live group combat changes were made.

### Balance Foundation Spec & Audit Skeleton (PR7)

- Balance Foundation Spec & Audit Skeleton is implemented:
  - historical release, tier, HP/damage/TTK, equipment-budget, enhancement, and
    encounter-scaling design markers were documented.

### Progression-aware Simulation Audit (PR8)

- Progression-aware simulation audit diagnostics are implemented:
  - historical audit rows and flags remained diagnostic-only.

### Equipment Budget Foundation (PR9)

- equipment budget foundation is implemented for simulation/reporting;

### Mob Encounter Scaling Foundation (PR10)

- formula-based mob encounter scaling is implemented for simulation/reporting;

### Pack/Group Simulation Harness (PR11)

- Pack/group simulation harness (PR11) is historical simulation/reporting evidence.

### Balance Instrument V2 Observability Foundation

- historical observability exposed bounded diagnostic metrics and traces.

### Balance Instrument V2 Pressure Attribution / Lane Classifier

- historical labels were diagnostic likely causes, not final balance verdicts.

### Actionable Late-Stage Underpressure Tuning Pass (PR15)

- actionable overclean baseline from PR14 was 44;
- current checked-in compact report shows raw/global overclean candidates: 87;
- current actionable overclean after PR15 is 43;
- early-stage target artifacts remain 44;
- representative overpressure risk remains visible: route_sunscar / route_exam / pure_support_solo_overlay player_death;
- PR15 is not a final/clean balance pass;
- No live gameplay/runtime changes.
- No Combat Core rewrite.
- No live pack/group runtime combat.

### Target Expectation Calibration Pass (PR14)

- historical target calibration separated early-stage artifacts from late-stage
  actionable diagnostics without changing live gameplay/runtime systems.

### Targeted Alpha Tuning Pass (PR13)

- at PR13 time, the compact report baseline showed global overclean candidates 88 and
  late-stage targeted overclean audit flags 43;
- later PR14/PR15 report current calibrated/current counts are tracked in the
  historical generated report;
- no live group combat, no targeting, no teleport, no economy overhaul, and no Combat
  Core rewrite were implemented.

### First Real Tuning Pass (PR12)

- PR12: First Real Tuning Pass remains historical baseline context.
- First Real Tuning Pass (PR12) used simulation/reporting-only stage-pressure changes.
- No live group/pack combat.
- No targeting rollout.
- No live route/mob/skill/reward/formula tuning outside accepted tuning PRs.
- PR12 includes simulation/reporting-only stage pressure tuning; live templates/runtime remain unchanged.

## Update policy

Update the authoritative current section when a merged change alters confirmed
capabilities, limitations, or the verified baseline. Do not append a per-PR chronology.
Keep plans in the roadmap, implementation detail in system/Epic documents, decisions in
the decisions log, and measurements in evidence with exact provenance.

The compatibility excerpt changes only when a fixed consumer is deliberately migrated
or a predicate must be preserved. It must never be read as current authority.
