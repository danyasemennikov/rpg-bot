# OPEN_WORLD_PROGRESSION_LOOP_PASS1 (PR 3M)

This pass follows PR 3K (open-world PvE numeric tuning package 1) and PR 3L (open-world reward/loot sanity package 1).

## Goal

Validate the gameplay loop integration:

- open-world PvE rewards ->
- inventory/material intake ->
- equipment/enhancement compatibility ->
- effective player stat impact.

## Scope in pass 1

- route-level reward progression report/validator;
- open-world loot item metadata classification;
- enhancement material recognition in current reward paths;
- reward-to-inventory sanity through existing grant helpers;
- gear acquisition/equip/effective-stats smoke compatibility through existing systems;
- enhancement runtime smoke using existing material ids.

## Important boundaries

- No combat formula changes.
- No mob combat stat changes.
- No reward formula or global economy rewrite.
- No spawn probability changes.
- No new mobs.
- No route topology changes.
- No mixed-mob pack implementation.
- No skill targeting rollout changes.
- No PvP behavior changes.

## Sunscar status

`route_sunscar` remains excluded from numeric-ready progression assumptions.

Reason: actionable readiness gap `no_pack_mobs_on_non_stub_route` is still open and is not masked by PR 3M checks.

## Gear-drop status honesty

Pass 1 does **not** force direct gear drops on every route/mob.

Progression is validated via:

- material/enhancement flow from open-world loot;
- compatibility with already-existing gear acquisition/runtime systems.

Full direct route gear-drop tuning remains future work.
