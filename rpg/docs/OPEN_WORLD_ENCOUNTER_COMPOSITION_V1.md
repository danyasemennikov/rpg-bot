# Open-world encounter composition V1 (PR 3B)

This pass builds directly on PR 3A (`OPEN_WORLD_PACK_BALANCE_BASELINE.md`).

## What this adds

- Canonical route-level encounter composition metadata is now explicit.
- Pack eligibility is policy-driven through shared open-world balance helpers.
- Route composition now states intended solo mobs, same-group pack mobs, and elite/rare anchors.
- Route and pack archetype threat bands are explicit metadata for future balancing passes.

## Scope boundaries (intentionally unchanged)

- Mixed-mob packs are still **future work**. Same-group claiming semantics remain unchanged.
- No combat formula changes.
- No reward number changes.
- No PvP targeting behavior changes.
- No UI or repositioning changes.
- Skill targeting rollout remains chapter-locked: no blanket skill rollout in this PR.

## Notes

This metadata pass is meant to keep current canonical open-world content coherent while preserving all existing runtime mechanics and reward foundations.
