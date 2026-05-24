# ALPHA RELEASE GATE PR3P

This document follows PR 3O and defines the first alpha release gate / stabilization pass.

## Scope

Alpha-ready routes:
- route_westwild
- route_frostspine
- route_ashen_ruins
- route_mireveil
- route_sunscar

Known non-ready / partial routes:
- route_south_coast_stub
- route_old_mine_stub

## Current playable alpha loop

- create character
- open location
- travel
- take contract
- fight route mobs
- claim reward
- inventory/materials
- equipment/enhancement
- recovery/unstuck

## Known limitations

- contracts are curated/static
- single-active-contract architecture unchanged
- no dynamic quest generation
- no mixed-mob packs
- no dungeon/world boss/rare boss readiness
- route-specific pressure readiness policy is active
- pack pressure is required only where route identity requires it
- Sunscar readiness is validated by solo_elite_precision_skirmish pressure

## Explicit non-goals

- no combat formula changes
- no mob stat changes
- no reward formula/global economy rewrite
- no spawn probability changes
- no new mobs/items
- no route topology changes
- no skill targeting rollout
- no mixed-mob spawning
- no UI rewrite
- no PvP behavior changes
