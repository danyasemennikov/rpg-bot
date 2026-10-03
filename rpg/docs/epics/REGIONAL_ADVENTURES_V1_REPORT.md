# Regional Adventures & Opportunities V1

- Status: automated acceptance complete; Draft PR remains open and not merge-ready
- Contract: RAV1-1
- Frozen base: `ebd8f73ade53fcadb89942b703a947782276ea1c`
- Validation starting HEAD: `8057b26bbc0b10deb1a4d30ea260d9b0cf82cad2`
- Historical authoritative broad-tested runtime SHA: `ce88335267c6dbc05bef289e88deebd1fa28ea60`
- Final repaired acceptance-test SHA: `43b5fb7a62f0265a89e20aeb9c3613f4605c56fc`
- Candidate branch: `codex/regional-adventures-opportunities-v1`
- Pull request: #234, open Draft, unmerged, not deployed
- Automated acceptance: COMPLETE
- Human validation: NOT RUN
- Merge ready: false

## Post-merge status — 2026-10-03

PR [#234](https://github.com/danyasemennikov/rpg-bot/pull/234) subsequently merged at
`adcc0baeee96c03852ed75c09e379b0c49be01d1`, from approved candidate
`436a0c1015766c38215f74ddb7ccd844a6c5a669`. Automated acceptance is COMPLETE;
human Telegram validation remains NOT RUN and outstanding after merge. Deployment
is not established. The original header and validation narrative below record the
historical candidate state, not current PR disposition. Broad/runtime and repaired
acceptance-test provenance remain at their original SHAs; no run is attributed to
the merge commit. The three-session human plan remains unchanged.

## Frozen scope confirmation

The catalogue remains unchanged: 34 top-level records; seven projects; 18 steps;
22 objectives using exactly seven objective kinds; five short finite opportunities;
ten discoveries plus two auxiliary inspections; ten one-time claims; three standing
deliveries; six activated/repaired hunts and zero new hunt definitions; two named
targets; two new and two retained mixed encounters; seven service additions; three
permanent two-outcome choices plus the non-branching Sled method; and ru/en/es copy.

Finite rewards remain exactly 440 XP, 201 gold, two enhancement shards, three small
health potions, and one field ration. Standing batches remain 10/20/12 gold and zero
XP. The exact five RAV tables and the single migration marker are unchanged.

Contract deviations: NONE. Scope expansion: NONE.

## Validation continuation and repairs

The interrupted machine state was recovered at the original validation starting HEAD.
No pytest process had been interrupted and no repair commit existed before recovery.
The first four validation stages were resumed without repeating conclusively green
work. Five bounded commits were added before this evidence successor:

| Commit | Purpose |
|---|---|
| `05e66d5330d875982f4340dc764ee55a3e20fe6c` | Align four validation fixtures and localized expectations with production authorities. |
| `1b165c37887a529939e19ba08725c423a8ebff4e` | Follow actual emitted board/location controls, prepare hand-ins at craftsmen guilds, and remove an impossible harvest assumption from J12. |
| `ce88335267c6dbc05bef289e88deebd1fa28ea60` | Permit genuine pre-RAV no-marker/no-table settlements while still failing closed for marked encounters without the binding table. |
| `603cd657f02ae0c412f3f01f847ca76a00f3e68c` | Record the first completed-validation report and machine evidence. |
| `43b5fb7a62f0265a89e20aeb9c3613f4605c56fc` | Restore legal J12 owner-only group-harvest acceptance coverage without changing production code. |

The only production change in this validation continuation is the final F1 legacy
compatibility guard in `game/regional_objectives.py`. All other continuation changes
are acceptance-test corrections.

The final V1 repair after the authoritative broad run is test-only. No production or
shared runtime file changed after `ce88335267c6dbc05bef289e88deebd1fa28ea60`.

## F1–F10 result matrix

| Finding | Fixed? | Production change | Focused coverage | Result |
|---|---:|---|---|---|
| F1 | YES | Marker/binding integrity fails closed; immutable marker persistence retained; genuine pre-RAV no-marker/no-binding/no-table recovery is accepted. | Marker loss/change/version, missing/corrupt bindings, absent table, legacy, save paths and rollback. | PASS |
| F2 | YES | Expiry selection and release are serialized under the owning write transaction. | Two-connection named/mixed expiry-first and activation-first cases. | PASS |
| F3 | YES | Business rejection uses a savepoint while the outer writer lock remains owned. | Rejection races, rollback, durable receipt and identical replay. | PASS |
| F4 | YES | Persisted project state is semantically validated without synthesis. | Invalid/valid state matrix and unchanged startup failure. | PASS |
| F5 | YES | Receipt recovery validates immutable owner, scope, content, version, hash and result identity. | Tampering and valid mutable-world replay matrix. | PASS |
| F6 | YES | Choice selection is non-mutating; only fresh explicit Confirm can commit. | All choices/options/locales, Back, stale Confirm, replay and restart. | PASS |
| F7 | YES | Pin tokens use distinct owner scopes. | Emitted project/hunt/gear controls, capacity, refresh and restart. | PASS |
| F8 | YES | Journal navigation, previews, risk, reveal gating and resolved states use production authorities. | Actual emitted controls and localized presentation. | PASS |
| F9 | YES | Replays render immutable committed results in the current locale without raw IDs. | Success/rejection/restart/move/locale and action-kind matrix. | PASS |
| F10 | YES | Acceptance journeys, economy and checkpoint provenance use production paths and authorities. | J01–J20, economy authorities and recorded hash constants. | PASS |

## R1–R8 result matrix

| Repair | Result | Evidence |
|---|---|---|
| R1 Root Cache replay consistency | PASS | Strict stored-result recovery and exact-once item grant coverage. |
| R2 selection-only choice authority | PASS | Selection/Back nonmutation and fresh Confirm coverage in three locales. |
| R3 supported map authorities | PASS | Capital, Old Mine and five route contexts traverse production handlers. |
| R4 secrecy, previews and navigation | PASS | Camp gating, remote quantities/rewards and source/recipe/build/history paths. |
| R5 Telegram button budget | PASS | Six-row pagination plus 12-button/10-row/two-per-row guard. |
| R6 localized RAV history | PASS | Restart/language-switch list and detail traversal. |
| R7 corrected F4/F6 tests | PASS | Semantic corruption matrix and stale/fresh Confirm flow. |
| R8 source-level acceptance gaps | PASS | Production boards, held sources, races, emitted navigation, replay, economy and provenance. |

The subsequent S1–S5 and D1–D2 static repairs are also covered by the executed repair
file, direct RAV matrix, journey suite, and final broad suite.

## Conclusive validation results

Environment: Windows, Python 3.12.10, pytest 9.1.1.

| Stage | Command | Result |
|---|---|---|
| Step 1 micro | Prescribed nine-node micro command from the validation prompt at `8057b26bbc0b10deb1a4d30ea260d9b0cf82cad2` | 27 passed in 406.15s |
| Step 2 repair file | `python -m pytest -q tests/test_regional_adventures_review_repairs.py` | 81 passed in 18.49s before the added legacy-table regression |
| Step 3 direct RAV | Nine prescribed direct RAV files | 37 passed in 7.79s |
| Step 4 shared | Eight prescribed shared regression files | 199 passed in 47.06s |
| Step 5 checkpoints | SHA-256 verification against recorded constants | PASS |
| Historical J01–J20 | `python -m pytest -q tests/test_regional_adventures_v1_journeys.py` at `ce883352...` | 39 passed in 138.29s |
| F1-selected coverage | Command included the migration node and repair file with `-k f1`; the filter deselected the migration node | 11 passed, 72 deselected in 2.91s |
| Post-F1 affected groups | Migration file plus full repair file | 87 passed in 18.81s |
| Historical final broad | `python -m pytest -q` at `ce883352...` | 1935 passed, 276 subtests passed in 1440.32s; retained, not rerun for V1 |
| V1 narrow J12 case | `python -m pytest -q 'tests/test_regional_adventures_v1_journeys.py::test_j12_optional_group_binding_contract[both_alive]'` | 1 passed in 6.22s |
| V1 complete J12 group | `python -m pytest -q tests/test_regional_adventures_v1_journeys.py::test_j12_optional_group_binding_contract` | 3 passed in 19.90s |
| Final repaired J01–J20 | `python -m pytest -q tests/test_regional_adventures_v1_journeys.py` at `43b5fb7...` | 39 passed in 156.70s |

The authoritative final broad log is:

`C:\Users\masha\Documents\Codex\2026-09-27\files-mentioned-by-the-user-rav1\work\validation-logs\rav1-final-broad-ce88335267c6dbc05bef289e88deebd1fa28ea60-rerun.log`

## J01–J20 acceptance provenance

| Journey | Cases | Acceptance purpose and production authority | Result |
|---|---:|---|---|
| J01 | 1 | Fresh post-Chapter-I onboarding, Journal and five-region entry through command/callback handlers. | PASS |
| J02 | 1 | Five region boards, emitted lower-menu board controls, all relevant hunts and real novice rank denial. | PASS |
| J03 | 1 | Different first-region solo completions and independently earned physical/magic character paths. | PASS |
| J04 | 1 | Stay-local Westwild/Mireveil sessions using production travel, gathering, crafting, hunts and actions. | PASS |
| J05 | 1 | Concurrent pursuits plus emitted project/hunt/gear pin controls, capacity and restart persistence. | PASS |
| J06 | 2 | Independent Ashen projects completed in both orders with stable rewards. | PASS |
| J07 | 1 | Explore-before-lead reconciliation, delayed starts, cache reveal and exact-once claim. | PASS |
| J08 | 1 | Low-profession route using Sled alternative, choices and finite hand-ins without illicit profession uplift. | PASS |
| J09 | 1 | Personal-practice craft evidence: pre-acceptance and gifted goods do not count; own fresh crafts do. | PASS |
| J10 | 1 | Legally earned/gifted ordinary goods, finite and standing deliveries, replay and insufficient-goods behavior. | PASS |
| J11 | 3 | Ordinary/named hunt overlap plus roster-lock acceptance boundary and no retroactive regional credit. | PASS |
| J12 | 3 | Both-alive/defeated/fled Ferry bindings and exclusion; after V1, legal production forest-boar group harvest proves owner exact-once grant and mutation-free non-owner rejection. | PASS |
| J13 | 1 | Named target lifecycle, production respawn, ordinary-target separation and Drifter hunt exclusion. | PASS |
| J14 | 1 | Production-held named/mixed sources, contention, expiry/activation serialization and exact release. | PASS |
| J15 | 1 | Permanent choices via selection/preview/Confirm, equal rewards, stale alternate rejection and outsider isolation. | PASS |
| J16 | 1 | Returning-player migration, valid legacy state preservation and startup semantic validation. | PASS |
| J17 | 11 | Delivery/choice/cache/standing atomic failure points, combat T2 recovery and separate-connection delivery races. | PASS |
| J18 | 3 | Arbitrary reward order and both full regional completion orders with exact frozen totals. | PASS |
| J19 | 3 | ru/en/es real handlers, emitted navigation/history/receipt controls, replay, limits and no raw IDs. | PASS |
| J20 | 1 | Resume after other resolutions, complete every finite record, restart and stable resolved presentation. | PASS |

Historical execution at `ce883352...` collected and passed 39 cases. The test-only V1
repair was separately validated at `43b5fb7...`: the complete J12 group passed three
cases and the complete journey file again collected and passed 39 cases. The historical
broad run did not execute the newly added J12 assertions.

## Failure classification history

| Stage | Failure | Classification | Resolution |
|---|---|---|---|
| Initial repair file | Four fixture/expectation failures | TEST BUG / STALE EXPECTATION | Corrected fixtures/localized authority assertions; full file green. |
| Initial J01–J20 | Four emitted-control/location/harvest assumptions | TEST BUG | Corrected production UI traversal and hand-in preparation; full suite green. |
| Broad at `1b165c3` | Pre-RAV prepared settlement saw no RAV binding table | REAL PRODUCTION DEFECT (F1) | Fixed in `ce88335`; focused and affected groups green. |
| First broad at `ce88335` | J03 produced no receipt during a prolonged 6h32m run | ENVIRONMENT / FIXTURE ISSUE; suspension/token-expiry is an inferred timing explanation, not directly proven | Exact node and full journey group passed afterward; a fresh uninterrupted broad run passed. |

## Checkpoint provenance

- Earned checkpoint: `7EE968B9861312799D743FAF87D6AFC3F9D099640B06E68E7E94F8CAFDAC9E6C`
- Party checkpoint: `7510168AC9B5A03C06423CE9075906088E21CEF2CA4A3716016EB5153D393A7B`

Both supplied files were hashed and compared with the independently recorded expected
constants. They were not rebuilt or treated as their own provenance authority.

The earned checkpoint provenance is production-path PEV1 registration, Chapter I,
travel, gathering, crafting, hunts, combat, gear and professions, with no injected RAV
state. The party checkpoint adds two independently earned Chapter-I characters used by
physical, magic, group, gift, race and isolation journeys.

Recorded accelerators are limited to mocked Telegram transport, zero sleep while
preserving travel adjacency and revision changes, controlled legal RNG selections, and
respawn-clock advancement through the production lifecycle.

## Review and limitations

Automated acceptance is COMPLETE. Runtime production state remains supported by the
authoritative broad result at `ce883352...`; the later test-only J12 coverage and full
journey file are green at `43b5fb7...`. Human Telegram validation remains NOT RUN. The
PR intentionally remains Draft, unmerged, not deployed, and not marked ready. No new
Astra or independent review was started.
