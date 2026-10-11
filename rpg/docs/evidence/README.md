# Checked acceptance evidence

- Status: Active catalogue
- Authority: Supporting measured evidence with exact provenance
- Last reconciled: 2026-10-03, against `adcc0baeee96c03852ed75c09e379b0c49be01d1`

Files in this directory are checked, compact acceptance artifacts. They identify the
exact rules commit, inputs, seeds, production authorities, and failed/stalled runs.
Human interpretation and rollout guidance live in the corresponding delivery report.

`regional_adventures_v1.json` records the RAV1-1 candidate's exact catalogue,
migration and transaction checks, earned J01–J20 production-history provenance,
focused and broad test results, and separate review/human/merge/deployment states.
`regional_adventures_v1_human.md` is the required human-session plan and remains
explicitly NOT YET RUN (human validation: NOT RUN) until observations are collected.
PR234 subsequently merged at `adcc0baeee96c03852ed75c09e379b0c49be01d1`, from
approved candidate `436a0c1015766c38215f74ddb7ccd844a6c5a669`. The JSON retains
historical candidate/test provenance and its then-current state boundaries; these
are not current merge status. Human sessions are outstanding post-merge validation,
not a merge blocker. Merge does not establish deployment.

`professions_economy_v1.json` preserves the PEV1-1 Stage 3 candidate's frozen base,
catalogue counts, migration checks, production-journey result, focused checks, and
single broad final-suite result. PR233 later merged at
`ebd8f73ade53fcadb89942b703a947782276ea1c`; the JSON remains historical candidate
evidence and is not rewritten as though it knew that outcome.

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


`player_experience_economy_v1.json` records the unmerged PXE1 candidate against
PR236. Its tests do not certify human Telegram behavior. The corresponding
`player_experience_economy_v1_human.md` explicitly remains NOT RUN. The RAV1 human
plan header is reconciled with the Session 1 interruption already recorded in current
state; this does not alter historical JSON or fabricate repair revalidation.
