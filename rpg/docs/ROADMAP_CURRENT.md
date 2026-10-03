# Current Roadmap

- Status: Active
- Authority: Canonical for forward priorities; not an implementation contract
- Last reconciled: 2026-10-03, against `adcc0baeee96c03852ed75c09e379b0c49be01d1`

Statuses used here:

- **Proposed:** a candidate direction that still needs design/audit and acceptance.
- **Accepted:** an approved direction with an explicit decision or frozen contract.
- **In progress:** accepted work with an active implementation or review candidate.

Merged capabilities belong in [PROJECT_STATE_CURRENT.md](PROJECT_STATE_CURRENT.md), not
in this roadmap.

## CURRENT

### RAV1 post-merge human validation

- Status: **accepted process**, outstanding after PR234 merged; implementation is
  complete and no longer an active candidate.
- Human Telegram validation: **NOT RUN**. Execute the existing
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
