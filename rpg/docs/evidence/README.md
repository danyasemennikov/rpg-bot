# Checked acceptance evidence

- Status: Active catalogue
- Authority: Supporting measured evidence with exact provenance
- Last reconciled: 2026-09-23, against `ad5435e577e45e63da2ca57af2296203d88cedd5`

Files in this directory are checked, compact acceptance artifacts. They identify the
exact rules commit, inputs, seeds, production authorities, and failed/stalled runs.
Human interpretation and rollout guidance live in the corresponding delivery report.

`character_builds_combat_identity_v1.json` is interpreted by
`../CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md`. Its `head_sha` is the integrated runtime
checkpoint used to generate the matrix:

- base: `c8768626e388babfed09adac83ddaf23f0daee71`;
- evidence head: `c547cf87e1a2ffa526a3e732cbb3658eca5953ec`;
- 200 paired seeds;
- 20 accessibility branches and 20 role gates;
- 240 encounter results;
- 100 progression/loadout comparisons;
- 17 bounded field adjustments across 14 skills.

The artifact was not regenerated for documentation consolidation. It supports the
recorded candidate and inputs; it does not independently validate every later
final-main integration change or prove deployment.

Historical generated diagnostics remain at compatibility paths and are unchanged:

- [Alpha route/class balance report V1](../ALPHA_ROUTE_CLASS_BALANCE_REPORT_V1.md)
- [Alpha route/class balance report V2](../ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md)

Their contents are historical evidence, not a current all-system balance certificate.
