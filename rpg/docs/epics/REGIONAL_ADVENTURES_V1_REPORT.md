# Regional Adventures & Opportunities V1

- Status: automated acceptance complete; Draft PR remains open and not merge-ready
- Contract: RAV1-1
- Frozen base: `ebd8f73ade53fcadb89942b703a947782276ea1c`
- Validation starting HEAD: `8057b26bbc0b10deb1a4d30ea260d9b0cf82cad2`
- Final tested code SHA: `ce88335267c6dbc05bef289e88deebd1fa28ea60`
- Candidate branch: `codex/regional-adventures-opportunities-v1`
- Pull request: #234, open Draft, unmerged, not deployed
- Automated acceptance: COMPLETE
- Human validation: NOT RUN
- Merge ready: false

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
work. Three bounded commits were added:

| Commit | Purpose |
|---|---|
| `05e66d5330d875982f4340dc764ee55a3e20fe6c` | Align four validation fixtures and localized expectations with production authorities. |
| `1b165c37887a529939e19ba08725c423a8ebff4e` | Follow actual emitted board/location controls, prepare hand-ins at craftsmen guilds, and remove an impossible harvest assumption from J12. |
| `ce88335267c6dbc05bef289e88deebd1fa28ea60` | Permit genuine pre-RAV no-marker/no-table settlements while still failing closed for marked encounters without the binding table. |

The only production change in this validation continuation is the final F1 legacy
compatibility guard in `game/regional_objectives.py`. All other continuation changes
are acceptance-test corrections.

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
| Step 1 micro | Prescribed nine-node micro command from the validation prompt | 27 passed in 406.15s |
| Step 2 repair file | `python -m pytest -q tests/test_regional_adventures_review_repairs.py` | 81 passed in 18.49s before the added legacy-table regression |
| Step 3 direct RAV | Nine prescribed direct RAV files | 37 passed in 7.79s |
| Step 4 shared | Eight prescribed shared regression files | 199 passed in 47.06s |
| Step 5 checkpoints | SHA-256 verification against recorded constants | PASS |
| Step 6 J01–J20 | `python -m pytest -q tests/test_regional_adventures_v1_journeys.py` | 39 passed in 138.29s at final tested SHA |
| Post-F1 focused | Failing migration node plus F1 focused cases | 11 passed, 72 deselected in 2.91s |
| Post-F1 affected groups | Migration file plus full repair file | 87 passed in 18.81s |
| Step 7 final broad | `python -m pytest -q` | 1935 passed, 276 subtests passed in 1440.32s |

The authoritative final broad log is:

`C:\Users\masha\Documents\Codex\2026-09-27\files-mentioned-by-the-user-rav1\work\validation-logs\rav1-final-broad-ce88335267c6dbc05bef289e88deebd1fa28ea60-rerun.log`

## Failure classification history

| Stage | Failure | Classification | Resolution |
|---|---|---|---|
| Initial repair file | Four fixture/expectation failures | TEST BUG / STALE EXPECTATION | Corrected fixtures/localized authority assertions; full file green. |
| Initial J01–J20 | Four emitted-control/location/harvest assumptions | TEST BUG | Corrected production UI traversal and hand-in preparation; full suite green. |
| Broad at `1b165c3` | Pre-RAV prepared settlement saw no RAV binding table | REAL PRODUCTION DEFECT (F1) | Fixed in `ce88335`; focused and affected groups green. |
| First broad at `ce88335` | J03 UI token expired during a 6h32m suspended run | ENVIRONMENT / FIXTURE ISSUE | Exact node and full journey group green; fresh uninterrupted broad green. |

## Checkpoint provenance

- Earned checkpoint: `7EE968B9861312799D743FAF87D6AFC3F9D099640B06E68E7E94F8CAFDAC9E6C`
- Party checkpoint: `7510168AC9B5A03C06423CE9075906088E21CEF2CA4A3716016EB5153D393A7B`

Both supplied files were hashed and compared with the independently recorded expected
constants. They were not rebuilt or treated as their own provenance authority.

## Review and limitations

Automated acceptance is COMPLETE for the tested code SHA above. Human Telegram
validation remains NOT RUN. The PR intentionally remains Draft, unmerged, not deployed,
and not marked ready. No new Astra or independent review was started.
