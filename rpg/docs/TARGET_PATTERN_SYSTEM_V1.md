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

## Compatibility
`target_shape` remains supported for compatibility.
`target_pattern_id` is the canonical targeting metadata going forward.

## Scope of this foundation
This V1 foundation adds registry/resolution/selector helpers only.
It does **not** add UI, repositioning, new skill rollout, or PvP mass-battle targeting changes.
