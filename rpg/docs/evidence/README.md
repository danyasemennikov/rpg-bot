# Checked acceptance evidence

Files in this directory are generated, compact acceptance artifacts. They identify
the exact rules commit, inputs, seeds, production authorities and failed/stalled
runs. Human interpretation and rollout guidance live in the corresponding report
under `docs/`.

`character_builds_combat_identity_v1.json` is interpreted by
`../CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md`. Its `head_sha` is the integrated runtime
checkpoint used to generate the matrix; later documentation-only commits do not
change that evidence authority.
