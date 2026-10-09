# PXE1 PR237 bounded independent-review corrections

Status: second bounded F2/F3 repair under validation; independent narrow review of `5fea976` returned FIX.
Five other original findings independently FIXED. Prior acceptance below is historical.
Date: 2026-10-09. Same [Draft PR #237](https://github.com/danyasemennikov/rpg-bot/pull/237).
Branch: `feat/pxe1-player-experience-economy-v1`.
Reviewed HEAD: `74389cb22ee6f49f584cc9c09a5f17cb792901c9`.
Correction code/test commit: `4ade6abf8db825097c9754ce204e564c96cdfa5b`.
Completed-side round follow-up / production candidate: `33dff106ec6b17563e575c56a88dceed78673cd0`.
Frozen contract retained unchanged. No migration/table/column, balance, scope or engine redesign.

The independent review returned **FIX** with four P1 and three P2 defects. Its
isolated probes reproduced **9 failures and 1 passing control in 2.90s** locally
before the changes. That raw run is `pxe1-review-before-pytest.log` in the workspace
`work/rpg-bot/rpg`. The review source is the supplied
`PXE1_PR237_INDEPENDENT_REVIEW.md`; these corrections address its seven findings.

## Finding resolution

| User ID / review ID | Root cause and bounded correction | Regression coverage |
|---|---|---|
| P1-1 / F1 | `handle_read_selection` queried nonexistent `group_rules_version`. It now uses real `world_model_version`, without changing schema. | Emitted 1v1/2v1/2v2 principal/ally Attack, Skills and Guard controls through target/confirmation and actual order commit in ru/en/es. Selection is read-only; expired/stale/version-zero tokens cannot spend resources. Retained version-zero suites run separately. |
| P1-2 / F2 | The validator required a deadline at a completed committed side. It now requires the matching side receipt and valid completed phase; malformed phases remain quarantined. Recovery preserves persisted round identity and persists a newly opened player-side deadline immediately. | Process exit after player/enemy side commit with exact round identity, second restart preserving deadline, terminal victory/death settlement replay, missing receipt/invalid phase/open-deadline corruption controls. |
| P1-3 / F3 | Resolution advanced runtime and projections before durability, retaining them on SQLite failure. Every failed attempt now discards runtime and reloads projections from SQLite, including ambiguous post-commit errors. An already-open enemy side is no longer opened twice. | Timeout and accepted attack/skill orders; faults before result, after vitals before commit, after commit; same-process retry and restart. Exact revisions, committed actor/enemy/effect snapshots, resources and receipt counts are checked. |
| P1-4 / F4 | Personal and terminal settlements left ally rows `locked`, reserving the unique active commitment forever. Settlement atomically marks historical membership `settled`; ongoing validation requires a matching death receipt for such members. Existing leaks reconcile at installation/acceptance in the caller writer. | Survivor accepts later engagement; defeated ally returns by real travel and accepts before original fight finishes; original terminal settlement preserves new commitment and immutable roster. Idempotent historical repair and existing race/rollback/membership tests. |
| P2-1 / F5 | Common timed arrival omitted dangerous-reentry protection consumption. Frontier/core-war arrivals clear it within the existing travel writer. | Normal, equality Stop and recovery frontier arrival; guarded/safe preservation; rollback and exactly one arrival revision. Retained travel/discovery tests. |
| P2-2 / F6 | Core Map listed only capital neighbors. It now includes selectable Aster except when already there. Existing discovery/travel preview remains authority. | Elmor → emitted World → Aster → six-edge 1:45 preview → Start in ru/en/es, no premature movement; unknown-route browsing preserves discoveries and current-place filtering. |
| P2-3 / F7 | Gather cards omitted wear/warning; broken-tool detail lacked useful route/quote/source guidance. Tick accounting persists the threshold fact; successful surface delivery acknowledges it. Cards show authoritative durability; recovery uses nearest canonical service/travel preview, exact maintenance quotes and material handbook controls. | 13→12→11, transport failure/coalescing, successful acknowledgment/no repeat, startup/reopening, 1→0 last yield, repair then new crossing, wilderness T1 replacement/material-funded/zero-material assisted repair and replay, all locales. |

`game/player_ui.py` also now enforces the frozen 3,000 UTF-16-unit detail budget,
with an explicit boundary regression. This resolves the review's smaller UI guard
limitation; it does not establish real-device usability.

## Candidate-specific validation

New repository regressions: `tests/test_pxe1_review_regressions.py`.
The original review probes are retained as regression cases and expanded through
real emitted callbacks, isolated SQLite, production mutation owners and injected
write/transport faults. Controlled combat/tool fixtures are focused tests, not
earned-progression or human evidence.

| Run | Exact invocation / scope | Completed result |
|---|---|---|
| Pre-fix independent reproduction | `python -m pytest -q <supplied test_independent_review.py> --tb=short` with RPG PYTHONPATH | 9 failed / 1 passed, 2.90s, expected reviewed-code failures |
| Initial F1 emitted chain | `python -m pytest -q tests/test_pxe1_review_regressions.py -k 'pvp_emitted or emitted_pvp' --tb=short` | 64 passed, 16.08s; later expanded principal coverage is included below |
| F1 retained neighbors | `python -m pytest -q tests/test_pxe1_pvp_membership_ui.py tests/test_location_live_pvp_view.py tests/test_pvp_live_flow_v1.py --tb=short` | 68 passed, 13.18s |
| Final F2/F3 boundary and world tick | `python -m pytest -q tests/test_pxe1_review_regressions.py -k pve tests/test_pxe1_pve_world_tick.py --tb=short` | 38 passed, 10.56s |
| F2/F3 retained neighbors | `python -m pytest -q tests/test_pxe1_pve_world_tick.py tests/test_pxe1_encounter_lifecycle.py tests/test_pxe1_combat_result_recovery.py tests/test_pxe1_combat_order_replay.py tests/test_solo_pve_runtime_adapter.py tests/test_group_pve_runtime_enablement.py --tb=short` | 70 passed, 14.11s |
| F4 membership reuse | `python -m pytest -q tests/test_pxe1_review_regressions.py -k 'ally or leak' --tb=short` | 3 passed, 1.13s |
| F4 retained neighbors | `python -m pytest -q tests/test_pxe1_pvp_group_runtime.py tests/test_pxe1_pvp_membership.py tests/test_pxe1_schema.py tests/test_pxe1_combat_result_recovery.py tests/test_pvp_live_flow_v1.py --tb=short` | 73 passed, 13.02s |
| F5 arrival boundaries | `python -m pytest -q tests/test_pxe1_review_regressions.py -k arrival --tb=short` | 10 passed, 2.16s |
| F5 travel neighbors | `python -m pytest -q tests/test_pxe1_travel.py tests/test_location_discovery_travel_migration.py --tb=short` | 21 passed / 113 subtests, 6.01s |
| F6 Map path | `python -m pytest -q tests/test_pxe1_review_regressions.py -k 'aster or elmor' --tb=short` | 7 passed, 1.68s |
| F6 neighbors | `python -m pytest -q tests/test_pxe1_local_surfaces.py tests/test_pxe1_travel.py --tb=short` | 26 passed, 6.66s |
| F7 wear and recovery | `python -m pytest -q tests/test_pxe1_review_regressions.py -k 'gather or wilderness_tool or repaired_tool or detail_guard' --tb=short` | 22 passed, 4.42s |
| Initial standalone new regressions (`4ade6ab`) | `python -m pytest -q tests/test_pxe1_review_regressions.py --tb=short` | **154 passed, 34.48s**, exit 0; all cases run again in the final focused and broad gates |
| Combined focused/compatibility | All `test_pxe1*.py`, shared runtime, retained PvP/build journey/economy/alpha transaction suites | **520 passed, 110.83s**, exit 0 on `33dff10`, including all 154 new cases; earlier 499/520 runs remain historical |
| Round restoration follow-up | Added exact round assertion at completed-side restart | Before: 1 failed / 1 passed, 1.45s; after: 38 passed, 10.69s |
| Repaired-candidate broad gate | **`python -m pytest -q`** | First attempt stopped (not PASS) for confirmed round-restoration repair; fresh repetition completed **1 failed / 2,390 passed / 276 subtests, 8808.88s**; J18 fixture-only correction is validated below, final repetition **2391 passed, 276 subtests passed in 1568.15s (0:26:08), exit 0** |

Exact raw log hashes and Git code/test identities are retained in
[automated evidence](../evidence/player_experience_economy_v1.json). Interrupted,
failed and earlier successful runs remain historical; none is silently replaced
by the repaired-candidate result.

## Evidence interpretation and handoff

The first correction-candidate broad run was deliberately stopped before the
expensive profession core after an additional F2 invariant check reproduced round
2 becoming round 1 on restart. Its raw output and consistent live observation are
preserved as incomplete evidence. Commit `33dff10` restores the round and adds the
assertion. The final broad gate runs on this follow-up candidate; its focused gate
has passed again. The stopped predecessor remains incomplete historical evidence.

The previous **2,237-test broad** and **41-test earned/RAV** results are credible
historical executions on the reviewed source, with disclosed completed-history
reuse. They missed these seven defects and do not validate the repaired source.
The old completed history has an incompatible production source hash after these
repairs. Its source guard remains intact. The required new gate must use valid
candidate evidence; cached historical progress cannot be relabeled or patched.

Human Telegram validation: **NOT RUN**. Prioritize H11–H13e combat/repeated
participation and failure recovery, H06 Map, H14–H16 tool wear/recovery and H19
locales within the existing human plan. Actual transport/device and sustained
scheduler behavior, deployment and live cutover remain unverified.

Independent review of reviewed HEAD: **COMPLETE / FIX**. Narrow independent
re-review of repaired HEAD: **PENDING**. Final broad completion is recorded below. The candidate is
**READY FOR NARROW INDEPENDENT RE-REVIEW**; this is not independent approval. This remains one unmerged
Draft PR; no merge or deployment is authorized.

## J18 comparison-input correction after the fresh broad gate

The fresh gate on `33dff10` completed normally, exit 1: **1 failed, 2390 passed,
276 subtests passed in 8808.88s**. All seven repair regressions passed. The fresh
core completed all eleven checks, all 83 recipes and all twelve profession caps.
Its whole database and provenance are preserved at workspace
`acceptance-recovery/review-237-corrections/33dff10-completed-earned`.
Source SHA-256: `6db9b9e96e253fef9ba424afacf63a39c5f3ae49901465efc02b9596d1f45929`.
Whole DB SHA-256: `b2cef94b8418b6b508d2bd939bd10d0d7a25fe4d413af03bee7de41135d624ac`.

J18 compared final absolute XP after separately earning two rations for each
order. Real preparatory boar combat can consume the newly crafted ration and
require another victory. The failed broad run differed by 12 XP. A read-only
trace showed both regional orders award 680 XP with matching starting states;
an emitted legal Guard/consumable variation reproduced unequal setup XP and
the unchanged final assertion failed (39.06s). Commit `d282be1d5fb3117cac65eb3d813af41856f27c37` earns the
stock once and clones that whole consistent SQLite state for both orders,
checking full prepared-player equality. No progress/items are injected; no
reward or final equality assertion is weakened. The same variation passes
in 34.63s after the correction.

This commit changes only the regional comparison test. Production, creator and
common history sources remain compatible with the complete fresh core above;
the strict source and whole-database guards remain intact. All 41 profession/regional
assertions pass again in 322.23s, exit 0; exact `python -m pytest -q` has repeated successfully with
this verified COMPLETE core explicitly supplied. Prior failure remains evidence,
and the final normally completed PASS is recorded below. Human Telegram remains NOT RUN; narrow
independent re-review remains pending. Never merge or deploy.

## Final repaired-candidate gate

Code/test candidate: `d282be1d5fb3117cac65eb3d813af41856f27c37`; production candidate `33dff10`.
Execution HEAD: `b78b0186b79e0816a63cc95c33009991c5e5c22f`.
Exact command: **`python -m pytest -q`**.
Normal observed exit: **0**. Terminal result: **2391 passed, 276 subtests passed in 1568.15s (0:26:08)**.
Raw log: `work/rpg-bot/rpg/pxe1-review-prepared-j18-final-broad-pytest.log`.
Log SHA-256: `c8c8632681e2e910958caa2f5f5e338671a6a45576594437b2f24bf38b7d53dc`.
`PXE1_EARNED_CHECKPOINT` explicitly supplied the whole verified COMPLETE core
described above. Production/creator/common history sources remained unchanged;
all collected assertions, including all 154 review regressions and corrected J18,
executed. This was compatible reuse, not another fresh core rebuild. Historical
failed/stopped runs and their distinct source/test candidates remain preserved.

Final focused gate: 520 passed in 110.83s at production candidate `33dff10`, all 154 review
cases included. Exact PowerShell discovery and Python invocation:

```powershell
$pxe1ReviewTests=@(Get-ChildItem -LiteralPath tests -Filter test_pxe1*.py | ForEach-Object { $_.FullName })
python -m pytest -q $pxe1ReviewTests tests/test_live_combat_runtime_foundation.py tests/test_pvp_live_flow_v1.py tests/test_character_builds_v1_pvp_journey.py tests/test_professions_economy_v1_transactions.py tests/test_alpha_transactions_v1.py --tb=short
```

All 41 profession/regional assertions also passed in 322.23s at `d282be1` before the full
repetition, with compatible complete-core reuse. The exact command and workspace
basetemp path are retained in JSON evidence. The frozen contract remains unchanged.
The first packet reported all seven fixed and completed its automated validation. Subsequent independent review found residual F2/F3. Human Telegram
is NOT RUN. Repaired-candidate independent review is PENDING. Real devices,
sustained scheduler operations, deployment and cutover remain unverified.
Historical first-packet handoff was ready for narrow review; that review returned FIX. Never merge or deploy.


## Second bounded repair — residual F2/F3 (2026-10-09)

Independent narrow review of `5fea976cd1b44a6a19e65d54cfc7df28b5969845`
returned FIX. F1/F4/F5/F6/F7 are independently confirmed fixed and are not
reimplemented. Exact unchanged reviewer matrix reproduced **10 failed / 8 passed,
11.67s** before edits. Raw log: `pxe1-second-review-before-pytest.log`.

F3 root cause: durable AI orders hydrated a ready runtime, but enemy orchestration
attempted to commit them again. `turn_not_collecting` prevented resolution forever
after revision 2/4 rollback. The enemy loop reuses matching accepted actions,
rejects conflicting actions, submits only missing actors and resolves the ready
side through the existing claim/CAS/transaction path. Accepted orders are immutable.

F2 root cause: normal enemy execution evaluated runtime revision 2/4/6 through
projection revision 1/3/5; recovery synchronized the projection first. The resolving
runtime revision, round and side now synchronize into all supplied projections
before evaluation. Uninterrupted and recovered execution use identical RNG seeds
and effect side indices. Full-receipt differential assertions additionally exposed
lost timeout source/previous player commit status, different instantaneous enemy
order deadlines, and stale compact vitals after periodic healing. Recovery retains
those accepted identities and publishes the same post-tick projection as normal
execution. Player timeout policy, formulas, shared N-v-M engine and CAS are retained.

Permanent coverage: `tests/test_pxe1_second_review_recovery.py`. The 36-case matrix
uses revisions 2/4/5, three fault boundaries, same-process/restart retry and solo/group
effects. It compares complete result JSON/state JSON, all player records, semantic
order rows (SQLite creation wall clock excluded between independent runs), complete
evaluator inputs/seeds/actions/results, events and effects. Existing rows including
creation timestamps remain immutable within each run. Repeated retries must leave
all durable state unchanged. Two additional three-enemy mixed-encounter probes
preserve a partially accepted order and submit exactly two missing orders.
Retained corrupt-state quarantine cases run in the adjacent focused suite.

Final production-source and broad validation are still pending at this checkpoint.
Old **2391 passed / 276 subtests** belongs exclusively to the previous candidate.
Changed production source invalidates its earned-history hash. The new final broad
gate must build fresh earned history after focused stabilization, with every strict
source/DB/recipe/cap/check safeguard retained. Human Telegram: NOT RUN. No merge.


### Second repair focused gate complete

Code/test candidate: `9d0a02a1a6ef5f6406ad43bf23f04382363ece72`. Final unchanged external probes: **28 passed,
14.03s**, exit 0 (`pxe1-second-review-external-final-pytest.log`); the exact reviewer
matrix is now **18/18**, retaining all eight original passing controls.
Final focused discovery selects every `tests/test_pxe1*.py`, plus live-runtime,
solo adapter/handler, group PvE, world encounter, retained PvP journey and transaction
neighbors: **698 passed in 166.31s**, normal exit 0. All 38 new permanent regressions
are included. Exact command and raw-log SHA256 are in JSON evidence.
Required exact `python -m pytest -q` follows on this stabilized production source
with a fresh earned core. It is not PASS until normal completion. Old historical
source/core cannot validate this candidate. Same Draft PR237; human NOT RUN.


### Fresh final broad gate started

Exact `python -m pytest -q`, execution HEAD `fcdfb3986c28e5f8493257ff15931e38d1fa3ae3`,
code/test candidate `9d0a02a1a6ef5f6406ad43bf23f04382363ece72`, source SHA256 `91096960d4c4b715eb6b389bd359d95c485bab7bc702398b0ebbd55897bb2c9c`.
Fresh earned core; checkpoint reuse variable absent. IN PROGRESS, no exit/PASS yet.
Raw log: `pxe1-second-review-final-broad-pytest.log`. The workspace observer records
PID, heartbeat, exact HEAD/status, read-only incomplete observations and only verified
complete core provenance at `acceptance-recovery/second-review-237/current-run.json`.
Continuation checkpoint: `PXE1_SECOND_REVIEW_CHECKPOINT.md`. Human NOT RUN; no merge.
