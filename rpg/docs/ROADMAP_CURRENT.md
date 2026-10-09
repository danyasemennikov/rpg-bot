# Current Roadmap

- Status: Active
- Authority: Canonical for forward priorities; not an implementation contract
- Last reconciled: 2026-10-08, baseline `3c5bfa62836c705a6327ce059f4e190b54ccf3e6`; PXE1 Draft separately identified

Statuses used here:

- **Proposed:** a candidate direction that still needs design/audit and acceptance.
- **Accepted:** an approved direction with an explicit decision or frozen contract.
- **In progress:** accepted work with an active implementation or review candidate.

Merged capabilities belong in [PROJECT_STATE_CURRENT.md](PROJECT_STATE_CURRENT.md), not
in this roadmap.

## CURRENT

### PXE1 integrated candidate

- Status: **in progress — Draft review**, frozen [PXE1-1 contract](epics/PLAYER_EXPERIENCE_ECONOMY_V1_SPEC.md).
- One [Draft PR #237](https://github.com/danyasemennikov/rpg-bot/pull/237) on the existing candidate branch; no merge authorization.
- Independent narrow review of `5fea976` returned FIX for residual F2/F3. Five original findings are independently fixed;
  the second bounded repair is under validation. Human Telegram validation remains **NOT RUN** under the owner's explicit
  implementation handoff instructions; run the [PXE1 human plan](evidence/player_experience_economy_v1_human.md)
  separately before claiming live acceptance.

### RAV1 post-merge human validation

- Status: **accepted process**, outstanding after PR234 merged; implementation is
  complete and no longer an active candidate.
- Human Telegram validation: **IN PROGRESS / interrupted in Session 1** (HV1-B01). PR236 repaired start; live revalidation is unverified. Complete the existing
  [Fresh solo, Returning solo, and Two-player plan](evidence/regional_adventures_v1_human.md)
  and record observations against an exact build.
- This is post-merge validation, not an implementation or merge blocker. Automated
  acceptance is COMPLETE; merge does not establish deployment or full playtesting.
- Human validation does not create a Chapter II or global campaign/finale promise.

## NEXT / LATER

### Professions / economy follow-up assessment

- Status: **proposed**.
- Prerequisite: evaluate PR233 operational behavior and explicitly deferred economy
  expansion without reopening its frozen V1 contract.

### Structured PvE / expeditions

- Status: **proposed**.
- Prerequisite: a design that distinguishes expedition structure from the already
  implemented persistent/group PvE runtime.

### Alpha hardening / operational validation

- Status: **proposed, continuing direction**.
- Prerequisite: prioritize demonstrated migration, recovery, latency, live-delivery,
  and balance risks. Merge status alone does not establish deployment or production
  validation.

## DEFERRED

Each item is **proposed only** and requires explicit accepted scope before implementation:

- teleport activation;
- castle/core-war systems;
- broader structured PvP;
- a full economy overhaul;
- other unapproved large expansions.

Deferred does not mean rejected permanently. It means the repository has no current
accepted implementation contract for that scope.
