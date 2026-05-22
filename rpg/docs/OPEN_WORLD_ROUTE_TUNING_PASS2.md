# Open-world route tuning pass 2 (PR 3G)

This pass follows the PR 3E/3F route-readiness layers and is intentionally limited to:

- `route_frostspine`
- `route_old_mine_stub`

## Route intent in this pass

- `route_frostspine` is treated as the mountain combat route.
- `route_old_mine_stub` remains a sparse mining/dungeon-adjacent stub.
- Rare anchors on Frostspine may remain deferred when current route-local live data does not yet represent a rare anchor.

## Boundaries

This pass adds readiness-focused assertions and documentation only.

- no reward number changes
- no combat formula changes
- no new mobs/content
- no route topology changes
- no blanket skill rollout
- mixed-mob packs remain future work
- no dungeon runtime rewrite in this PR
