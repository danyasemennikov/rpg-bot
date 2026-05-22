# OPEN_WORLD_REWARD_THREAT_ALIGNMENT_V1

This pass follows PR 3A (open-world pack balance baseline) and PR 3B (route encounter composition).

## What this pass adds

- A small open-world reward/threat alignment metadata layer.
- Explicit route threat bands -> reward category/profile mapping.
- Explicit pack archetypes -> reward category/profile mapping helpers.
- Explicit spawn profile (`normal` / `elite` / `rare`) -> reward category alignment.
- Regression tests to prevent route/archetype/reward metadata drift.
- Unknown spawn profiles fall back to `open_world_normal` as a safe metadata default; `WORLD_SPAWN_PROFILES` remains explicitly locked by tests.

## Scope boundaries

- This pass is metadata + test alignment only.
- No reward number changes.
- No combat formula changes.
- No mixed-mob packs.
- No blanket skill rollout.
- Future numeric economy tuning belongs to a separate pass.
