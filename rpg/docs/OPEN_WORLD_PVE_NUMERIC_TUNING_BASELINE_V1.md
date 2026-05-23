# OPEN WORLD PvE NUMERIC TUNING BASELINE V1 (PR 3J)

This document follows PR 3I and establishes the first **numeric PvE** tuning baseline for open-world routes that are readiness-valid.

## Scope

Numeric-ready major route scope for baseline validation:
- route_westwild
- route_frostspine
- route_ashen_ruins
- route_mireveil

Stub/sanity-only scope:
- route_south_coast_stub
- route_old_mine_stub

Excluded from numeric-ready pack-route tuning:
- route_sunscar (excluded while actionable `no_pack_mobs_on_non_stub_route` remains unresolved)

## What this baseline does

- Adds route-level numeric report generation for currently shipped mob numeric fields.
- Adds structural validation for numeric profile coherence and route summary bounds.
- Keeps sparse/stub routes in smoke/sanity reporting only.
- Preserves readiness-gated tuning behavior using PR 3I readiness gaps.

## Explicit non-goals and frozen constraints

- no combat formula changes
- no reward number changes
- no reward formula changes
- no new mobs
- no spawn probability changes
- no mixed-mob packs

Also unchanged in this PR:
- route topology
- skill targeting rollout policy
- PvP behavior

## Follow-up intent

Future PRs can apply exact route-by-route numeric adjustments using this report/validator baseline, while preserving the same systems boundaries.
