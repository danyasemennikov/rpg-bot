# Open World Route Objectives — Pass 1 (PR 3N)

This pass follows PR 3K/3L/3M and adds a route-objective metadata layer wired to existing hunt contract workflows.

## Goal

Provide route-level objective direction via current quest board contracts:
- open location/route;
- see route-appropriate hunt objectives;
- kill targets (including elite anchors where applicable);
- progress + claim rewards through existing paths.

## What was added

- `game/open_world_route_objectives.py` provides route objective profiles and validation:
  - `build_route_objective_profile(route_id)`
  - `build_all_route_objective_profiles()`
  - `validate_open_world_route_objectives()`
- Profiles derive from existing route composition/readiness helpers (no duplicate manual route datasets).
- Numeric-ready routes now have player-facing curated/static contracts via existing quest board contracts:
  - route_westwild
  - route_frostspine
  - route_ashen_ruins
  - route_mireveil

## Coverage policy

- Numeric-ready routes (`route_westwild`, `route_frostspine`, `route_ashen_ruins`, `route_mireveil`) expose hunt coverage and route-truthful pack/elite objective signals.
- `route_sunscar` remains non-numeric-ready and continues to expose the actionable `no_pack_mobs_on_non_stub_route` warning.
- Stub routes (`route_south_coast_stub`, `route_old_mine_stub`) are treated as sparse/smoke content and do not require pack/elite completeness.

## Reward/economy posture

- Existing quest-board reward paths are reused.
- No global reward-formula or economy rewrite.
- Objective rewards remain modest and claimable via existing claim flow.

Route objective profiles remain a validation/report layer and are not a replacement for `game/quest_board.py`.
The single-active-contract architecture unchanged; this pass is not dynamic quest generation.

## Scope boundaries preserved

No changes were made to:
- no combat formula changes;
- no mob stat changes;
- no reward formula or global economy rewrite;
- no spawn probability changes;
- no mixed-mob packs;
- skill targeting rollout;
- no route topology changes;
- no pvp behavior changes;
- no new mobs;
- no new items;
- UI overhaul.

## Known limitations (unchanged)

- Current hunt contracts are still curated/static entries in `game/quest_board.py`.
- Route objective profiles are validation/report-oriented integration and do not replace the existing single-active-contract quest board architecture.
- route_sunscar remains non-numeric-ready while no_pack_mobs_on_non_stub_route is actionable.
- Stubs remain smoke/sanity only.
- No narrative campaign system was added.
