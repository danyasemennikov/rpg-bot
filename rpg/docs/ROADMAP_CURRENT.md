# Current Roadmap

- Status: Active
- Authority: Canonical for forward priorities; not an implementation contract
- Last reconciled: 2026-09-26, against `27347ece2b17108a1aed1f6eb01f2a395480e6c9`

Statuses used here:

- **Proposed:** a candidate direction that still needs design/audit and acceptance.
- **Accepted:** an approved direction with an explicit decision or frozen contract.
- **In progress:** accepted work with an active implementation or review candidate.

Merged capabilities belong in [PROJECT_STATE_CURRENT.md](PROJECT_STATE_CURRENT.md), not
in this roadmap.

## CURRENT

### Professions & Economy V1

- Status: **in progress** under frozen contract PEV1-1 Stage 3.
- Outcome: five gathering and seven crafting professions, 63 active recipes,
  28 mandatory materials, permanent knowledge, durable economic receipts, and
  complete ru/en/es professions journeys.
- Candidate record: [epics/PROFESSIONS_ECONOMY_V1_REPORT.md](epics/PROFESSIONS_ECONOMY_V1_REPORT.md).
- Completion: the single Draft PR has green focused and production-journey evidence.
  One broad suite was recorded before the repair pass; its five failures have green
  exact focused reruns, and a second broad run is not automatically required by the
  frozen test budget. Merge remains a separate user decision.

## NEXT

### Professions / Economy follow-up assessment

- Status: **proposed** only after PEV1-1 acceptance.
- Outcome: assess operational behavior, receipt retention, balance, and explicitly
  deferred economy expansion without reopening the frozen V1 contract.

## LATER

### Regional and content expansion

- Status: **proposed**.
- Prerequisite: explicit content scope and compatibility with the current Aster–Elmor
  slice, world topology, progression, and economy.

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
