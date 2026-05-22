# Target Pattern System V1

## Purpose
This document stabilizes the targeting chapter after PRs **2C5–2C10**.

It defines canonical metadata, runtime support boundaries, and rollout policy.

## Core model
- `target_pattern_id` is the canonical targeting metadata.
- `target_shape` is compatibility metadata only.
- A **target selection pattern** decides which units are selected.
- An **execution_mode** decides how selected units are resolved.

## Supported execution modes
- `single`
- `single_redirect`
- `fanout`

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

## Runtime support status
- Direct-damage `fanout` is supported through the target pattern registry.
- Direct-damage `single_redirect` is supported through the target pattern registry.
- Enemy-effect/control `single_redirect` is supported through the target pattern registry.
- Ordinary direct damage still uses active-target projection unless a skill opts into a pattern.

## Target-local support status
- `single_redirect` target-local support exists via `target_local_resolution=True`.
- `fanout` target-local support exists via `target_local_resolution=True`.
- Target-local support is opt-in.
- No global fanout target-local behavior was added.

## Current rollout (live)
- `flame_wave` -> `all_enemies_in_small_pack`
- `heavy_swing` -> `front_line_cluster`
- `cleave_through` -> `front_line_cluster` + `target_local_resolution=True`
- `arcane_lance` -> `back_line_single`
- `hunters_mark` -> `back_line_single`
- `aimed_shot` -> `back_line_single` + `target_local_resolution=True`
- `piercing_arrow` -> `back_line_single` + `target_local_resolution=True`
- `deadeye` -> `back_line_single` + `target_local_resolution=True`

## Rollout policy (post-2C10)
- No blanket rollout and no mass assignment of target patterns.
- New `target_pattern_id` assignments happen only inside focused branch/balance/content passes.
- Each rollout must explicitly include:
  - metadata update;
  - truthful RU/EN/ES descriptions when behavior changes;
  - runtime tests for selected-target behavior;
  - payoff-locality tests for target-dependent behavior;
  - resource/cooldown single-spend tests when preview/recompute is involved;
  - explicit scope confirmation in PR description.

## Non-goals for this chapter close
- No UI or repositioning changes.
- No PvP mass-battle targeting changes.
- No enemy AI changes.
- No blanket skill rollout.
- No automatic pattern inference from skill flavor text.
