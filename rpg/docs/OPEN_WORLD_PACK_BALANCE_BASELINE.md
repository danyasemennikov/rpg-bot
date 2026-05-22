# Open-world pack encounter balance baseline (PR 3A)

This is the first open-world content/balance pass after the targeting chapter lock from PR 2C11.

## What this baseline adds
- Explicit enemy formation-role metadata for existing live open-world mobs.
- Deterministic formation propagation into pack `enemy_units`.
- Lightweight pack archetype/threat metadata hooks for future tuning.

## Important scope boundaries
- Same-group pack claiming remains unchanged; this PR does not force mixed-mob pack spawning.
- Skill target-pattern rollout remains frozen (no blanket skill rollout in this PR).
- No combat formula changes.
- No PvP targeting behavior changes.
- No UI or repositioning changes.
- No numeric reward payout changes.

## Notes for future passes
- Mixed-composition packs can be introduced in a future focused content pass when runtime support is expanded.
- Archetype/threat metadata is intentionally minimal and acts as a tuning hook only.
