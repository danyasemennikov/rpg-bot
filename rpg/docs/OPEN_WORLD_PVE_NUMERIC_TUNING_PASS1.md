# Open-world PvE Numeric Tuning Pass 1 (PR 3K)

This pass follows the PR 3J numeric baseline and performs the first targeted numeric tuning update for numeric-ready open-world routes.

## Tuned routes
- route_westwild
- route_frostspine
- route_ashen_ruins
- route_mireveil

## Exclusions and scope limits
- route_sunscar excluded: actionable `no_pack_mobs_on_non_stub_route` remains unresolved.
- route_south_coast_stub and route_old_mine_stub remain smoke/sanity only.

## What was tuned
Tuned numeric mob profile fields only where needed for route coherence:
- `level`
- `hp`
- `damage_min`
- `damage_max`
- `defense` (available but not formula-changed)

## Intent summary
- Keep Westwild starter-safe and low-risk for ordinary solo mobs.
- Increase pack-pressure clarity for route pack mobs.
- Ensure elite anchors stay clearly stronger than ordinary route floors/ceilings.
- Keep progression coherence from Westwild into Frostspine / Ashen Ruins / Mireveil.

Level changes in this pass preserve pre-pass exp/gold values via explicit reward overrides; reward economy tuning remains out of scope.

## Explicit non-goals for PR 3K
- no combat formula changes
- no reward number changes
- no reward formula changes
- no spawn probability changes
- no new mobs
- no mob removals
- no mixed-mob packs
- no route topology changes
- no PvP behavior changes
- no skill targeting rollout changes
