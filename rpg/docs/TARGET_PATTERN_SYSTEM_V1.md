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

## Runtime status
- Enemy-targeted direct-damage runtime resolves fanout and single-redirect pack targeting through the target pattern registry.
- Enemy-effect single_redirect runtime now exists for selected enemy debuff/control skills.
- Initial live rollout examples are tracked below; target_pattern_id is now used by selected real skills.
- `target_shape` remains compatibility metadata.
- `target_pattern_id` is canonical going forward.
- Ordinary direct damage is recognized as `ordinary_single_enemy`, while existing active-enemy projection behavior remains unchanged.

## Non-goals
This system does **not** add UI, repositioning, global fanout target-local behavior, or PvP mass-battle targeting changes.

## Current rollout (live examples)

- `flame_wave` now uses canonical `target_pattern_id='all_enemies_in_small_pack'` (no compatibility shape needed).
- `heavy_swing` now uses canonical `target_pattern_id='front_line_cluster'`.
- `arcane_lance` now uses canonical `target_pattern_id='back_line_single'`.
- Sniper payoff shots now use canonical `target_pattern_id='back_line_single'` with `target_local_resolution=True`:
  - `aimed_shot`
  - `piercing_arrow`
  - `deadeye`

- PR 2C8A foundation: added opt-in target-local payoff recomputation for `single_redirect` patterns via `target_local_resolution` metadata.
- PR 2C8B rollout: enabled this for `deadeye` as the first real target-dependent `single_redirect` skill.
- PR 2C8C rollout: extended the same direct-damage target-local flow to `aimed_shot` and `piercing_arrow`.
- `hunters_mark` now uses canonical `target_pattern_id='back_line_single'` as the first live enemy-effect single_redirect rollout.
- Sniper package is now coherent in pack fights:
  - `hunters_mark` marks the selected back-line target.
  - `aimed_shot`, `piercing_arrow`, and `deadeye` consume payoff on that selected back-line target.
- Fanout target-local payoff recomputation is now available only as opt-in behavior via `target_local_resolution=True`.

- PR 2C10: opt-in fanout target-local recomputation is now available for direct-damage fanout skills via `target_local_resolution=True`.
- PR 2C10 rollout: `cleave_through` is now on `front_line_cluster` with target-local payoff recomputation.
- Fanout target-local remains opt-in and does not change global fanout behavior.
