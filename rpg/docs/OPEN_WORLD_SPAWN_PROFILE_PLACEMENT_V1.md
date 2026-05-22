# Open-world spawn profile placement v1 (PR 3D)

This pass follows PR 3A/3B/3C and keeps the existing runtime spawn system intact.

## What is validated now

- Route composition metadata is checked against live `WORLD_LOCATIONS` route content and `world_spawn_profiles` data.
- Spawn profile placement is policy-validated for `normal / elite / rare` expectations by role:
  - solo mobs -> normal
  - pack mobs -> normal
  - elite anchors -> elite (where represented in world spawn profiles)
  - rare anchors -> rare (where represented)
- Spawn profile keys are validated against canonical world spawn profile keys and reward/threat alignment helpers.
- Covered route live mobs and `world_spawn_profiles` are expected to be represented in route composition metadata.

## Scope boundaries kept in this PR

- No reward number changes.
- No combat formula changes.
- No blanket skill rollout.
- Mixed-mob packs remain future work.
- Numeric economy tuning remains future work.

## Notes on representation

Elite/rare anchor validation follows the current source-of-truth representation in `WORLD_LOCATIONS` and existing route composition metadata. This PR does not migrate runtime storage or rewrite spawn acquisition paths.
