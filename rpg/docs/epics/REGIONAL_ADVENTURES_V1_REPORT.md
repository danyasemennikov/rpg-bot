# Regional Adventures & Opportunities V1

- Status: Draft PR repair implemented; validation not run
- Contract: RAV1-1
- Frozen base: `ebd8f73ade53fcadb89942b703a947782276ea1c`
- Second-pass starting HEAD: `021dcdd8b3b125c1fc49ef3995594c515334b193`
- Previous repair code commit: `cbb258e0a759d3d93d4385fe8482d9e6b7e87960`
- Second static repair code commit: `4569226e5d41408e0711b6631509f3f2197d93a4`
- Candidate branch: `codex/regional-adventures-opportunities-v1`
- Pull request: #234, open Draft, unmerged, not deployed
- New tested code commit: NONE — tests were expressly prohibited in this repair pass
- Human validation: NOT RUN

## Frozen scope

The catalogue remains unchanged: 34 top-level records; seven projects; 18 steps;
22 objectives using exactly seven objective kinds; five short finite opportunities;
ten discoveries plus two auxiliary inspections; ten one-time claims; three standing
deliveries; six activated/repaired hunts and zero new hunt definitions; two named
targets; two new and two retained mixed encounters; seven service additions; three
permanent two-outcome choices plus the non-branching Sled method; and ru/en/es copy.

Finite rewards remain exactly 440 XP, 201 gold, two enhancement shards, three small
health potions, and one field ration. Standing batches remain 10/20/12 gold and zero
XP. The exact five RAV tables and the single migration marker are unchanged; only
startup semantic validation was strengthened.

## Independent-review repair packet

| Finding | Static repair | Test coverage authored | Execution |
|---|---|---|---|
| F1 | Combat marker and bindings now distinguish genuine legacy from corrupt/incompatible RAV encounters; all state-save paths preserve the immutable marker and settlement fails closed. | Marker loss/change/version, missing/corrupt bindings, legacy, solo/group/order/consumable/flee/T1 persistence and rollback cases. | NOT RUN |
| F2 | Expiry selection and guarded release now occur under one owning write transaction; activation and expiry are mutually serialized and active sources cannot survive an expiry mutation. | Two-connection expiry-first, activation-first, named/mixed, repeat pruning, active survival and exact-once release cases. | NOT RUN |
| F3 | Tentative business mutation now uses a savepoint under an outer `BEGIN IMMEDIATE`; rejection rolls back only the savepoint, consumes the authorized token, writes one durable receipt and commits while retaining serialization. | Rejection/rejection and rejection/replenishment races, full rollback, one receipt, identical replay and no-integrity-error cases. | NOT RUN |
| F4 | Startup validates completed-step evidence, ALL/ANY winners, future progress, choices and completed-state consistency without synthesizing repairs. | Corrupt semantic rows, valid intermediate/completed rows and unchanged-DB startup failure cases. | NOT RUN |
| F5 | Receipt recovery verifies owner, scoped operation, content, catalogue version, intent hash, token identity when present, and catalogue-derived immutable result/economic consistency. | Owner/operation/content/hash/version/result tampering and valid replay after token loss, move, revisions, restart and locale change. | NOT RUN |
| F6 | Choice option callbacks are read-only previews; only explicit Confirm uses the mutation token, and Back/Cancel mutates nothing. | All three choices, both outcomes and ru/en/es selection/cancel/confirm/stale/replay/restart/equal-reward paths. | NOT RUN |
| F7 | Pin token kinds are scoped by owner kind and ID, so concurrently visible project/hunt/gear actions do not invalidate one another. | Emitted hunt/gear/project controls, unpin, repin, refresh, fourth-pin rejection and restart. | NOT RUN |
| F8 | Journal Map uses map authority; details add exact destinations, useful navigation, hand-in quantities, named standing items, encounter risk, Sled method, cache reveal gating and resolved lead status. | Actual emitted controls, navigation, risk, hidden cache and presentation checks. | NOT RUN |
| F9 | Action/replay UI renders immutable receipt data in the current locale; player-visible raw recipe IDs were removed. | Success/rejection/restart/move/language/standing/choice/finite replay and raw-ID checks. | NOT RUN |
| F10 | J02/J04/J05/J12/J13/J14/J15/J17/J19 and economy/provenance assertions were repaired to exercise production UI and authorities. | J01–J20 remains 20 journey definitions / 39 planned parameter runs. | NOT RUN |

## Second narrow static repair (R1–R8)

| Repair | Static implementation | Test source authored/updated | Execution |
|---|---|---|---|
| R1 | Items-only Root Cache receipts now omit character progression exactly as the strict recovery validator requires, without weakening receipt identity checks. | Claim, post-commit response loss, original-token replay, deleted token, move, restart, locale switch, stored-result identity and exact-once item grant. | NOT RUN |
| R2 | Visible choice buttons now carry selection-only intents. A valid preview mints a separate Confirm mutation token; selection execution is rejected and rebuilding/Back invalidates pending Confirm authority. | Three choice projects, both options, ru/en/es, direct selection rejection, preview/Back nonmutation, stale Confirm, fresh Confirm, permanent replay/restart. | NOT RUN |
| R3 | Journal map callbacks canonicalize Capital and Old Mine into supported map authorities and emit only the five existing route keys. | Emitted buttons are passed to the production location/map handler for Capital, Old Mine and all five route contexts. | NOT RUN |
| R4 | Camp rewards stay hidden until bearings resolve; remote finite previews show owned/required/consumption/reward; source/recipe, Build/Equipment and Chapter I history controls route to existing authorities. | Camp secrecy, remote preview, source/recipe handler traversal, Build/Equipment navigation and completed Chapter I history. | NOT RUN |
| R5 | Pursuit pagination uses a bounded page size and a shared hard budget guard: at most 12 buttons, 10 rows and two buttons per row, with no silent list truncation. | Six/seven-project and hunt/gear/project combinations across first/middle/last pages and ru/en/es. | NOT RUN |
| R6 | RAV receipt list labels and details dispatch to the RAV current-locale renderer; non-RAV receipts retain the existing profession renderer. | Actual History button/list/detail traversal after restart and locale change, without raw IDs, missing keys or profession progression assumptions. | NOT RUN |
| R7 | The semantic-corruption INSERT now has correct arity, and the choice test reacquires selection/Confirm after Back while proving the old Confirm cannot commit. | Full F4 corruption matrix and all F6 project/option/locale combinations. | NOT RUN |
| R8 | Acceptance source now opens every board through production UI, includes Mireveil and a real novice rank denial, reserves the J14 ordinary source through emitted combat entry, authors event-controlled two-writer races, traverses J19 emitted navigation/receipt controls, covers the full replay matrix, and derives vendor/recipe arbitrage checks from authorities. Supplied checkpoints remain checked against recorded constants. | J02, J14, J19, synchronized named/mixed expiry races, finite/standing/choice/rejection replay, economy and checkpoint provenance. | NOT RUN |

Static inspection found no frozen-contract contradiction and no scope expansion.
`git diff --check` completed without errors before the repair commit. This is not a
test result and does not establish runtime correctness.

## Tests added or modified

- Added `tests/test_regional_adventures_review_repairs.py` for the focused F1–F9
  repair matrix, including controlled concurrency and emitted-callback paths.
- Modified `tests/test_regional_adventures_economy.py` so protected values and
  vendor/recipe availability are derived from live authorities.
- Modified `tests/test_regional_adventures_v1_journeys.py` for F10, production UI
  operation, recorded checkpoint hashes, local-session traces, matching combat
  bindings, production respawn lifecycle, contention/race cases and T2 rollback.
- Modified `tests/test_regional_adventures_transactions.py` so permanent choices
  use selection → preview → fresh Confirm.

No test, pytest collection, Python import, compile, journey, regression or broad-suite
command was run during this repair pass.

## Commands required in the next validation stage

All commands below are recorded as **NOT RUN**:

```powershell
python -m pytest -q tests/test_regional_adventures_review_repairs.py

python -m pytest -q tests/test_regional_adventures_contract.py tests/test_regional_adventures_schema.py tests/test_regional_adventures_transactions.py tests/test_regional_adventures_objectives.py tests/test_regional_adventures_combat.py tests/test_regional_adventures_world.py tests/test_regional_adventures_ui.py tests/test_regional_adventures_localization.py tests/test_regional_adventures_economy.py

python -m pytest -q tests/test_world_pve_encounter_foundation.py tests/test_itemization_regional_loot_v1.py tests/test_itemization_fix_packet_pr230.py tests/test_character_builds_v1_migration.py tests/test_character_builds_v1_durability.py tests/test_alpha_transactions_v1.py

$env:RAV1_EARNED_CHECKPOINT='<hash-verified earned checkpoint>'
$env:RAV1_PARTY_CHECKPOINT='<hash-verified party checkpoint>'
python -m pytest -q tests/test_regional_adventures_v1_journeys.py

python -m pytest -q
```

Expected recorded checkpoint SHA-256 values are:

- earned: `7EE968B9861312799D743FAF87D6AFC3F9D099640B06E68E7E94F8CAFDAC9E6C`
- party: `7510168AC9B5A03C06423CE9075906088E21CEF2CA4A3716016EB5153D393A7B`

The repaired journeys compare supplied checkpoints to those expected recorded hashes.
Checkpoint provenance verification for this repair candidate is NOT RUN.

## Review and limitations

The former `automated_acceptance: complete` claim is invalidated by the independent
FIX verdict and the later Astra `FIX BEFORE VALIDATION` static verdict; it remains
withdrawn. Automated acceptance is **PENDING VALIDATION**.
The historical results at `7846598682596234a6c1255b4faeba8689ad9200` do not validate
this repair commit. A new final broad suite is required only after focused and affected
regression validation stabilizes.

No merge, deployment, human Telegram validation, ready-for-review transition or new
independent review was performed. The remaining risk is entirely unexecuted runtime,
concurrency, callback, localization and acceptance validation of the authored repair.
