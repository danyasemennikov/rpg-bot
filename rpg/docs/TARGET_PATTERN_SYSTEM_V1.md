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
- Live skill rollout remains unchanged; no new real skills were assigned to dormant patterns.
- `target_shape` remains compatibility metadata.
- `target_pattern_id` is canonical going forward.
- Ordinary direct damage is recognized as `ordinary_single_enemy`, while existing active-enemy projection behavior remains unchanged.

## Non-goals
This system does **not** add UI, repositioning, new skill rollout, or PvP mass-battle targeting changes.
