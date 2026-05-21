# Target Pattern System V1

## Purpose
Target Pattern System V1 standardizes target selection presets for:
- ordinary single-target enemy acquisition,
- single-target redirects,
- line cluster fanout,
- small-pack AoE fanout.

## Canonical formation lines
- `front`
- `melee`
- `ranged`
- `support`

## V1 target patterns
- `ordinary_single_enemy`
- `all_enemies_in_small_pack`
- `front_line_cluster`
- `back_line_single`
- `two_front_lines_2x2`
- `ranged_line_single`

## Pattern vs execution mode
A **target selection pattern** decides *which units are selected*.
An **execution mode** decides *how the skill resolves on selected units*:
- `single`
- `single_redirect`
- `fanout`

## Runtime status after PR 2C6
- Enemy-targeted direct-damage runtime now resolves fanout and single-redirect pack targeting through the target pattern registry.
- Initial live rollout examples are tracked below; target_pattern_id is now used by selected real skills.
- `target_shape` remains compatibility metadata.
- `target_pattern_id` is canonical going forward.
- Ordinary direct damage is recognized as `ordinary_single_enemy`, while existing active-enemy projection behavior remains unchanged.

## Non-goals
This system does **not** add UI, repositioning, new skill rollout, or PvP mass-battle targeting changes.

## Current rollout (live examples)

- `flame_wave` currently uses `all_enemies_in_small_pack` via compatibility `target_shape`.
- `heavy_swing` now uses canonical `target_pattern_id='front_line_cluster'`.
- `arcane_lance` now uses canonical `target_pattern_id='back_line_single'`.
- `deadeye` now uses canonical `target_pattern_id='back_line_single'` with `target_local_resolution=True`.

- PR 2C8A foundation: added opt-in target-local payoff recomputation for `single_redirect` patterns via `target_local_resolution` metadata.
- PR 2C8B rollout: enabled this for `deadeye` as the first real target-dependent `single_redirect` skill.
- Fanout target-local payoff recomputation remains out of scope and unchanged.
