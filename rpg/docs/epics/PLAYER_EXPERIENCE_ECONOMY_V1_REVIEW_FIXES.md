# PXE1 PR237 bounded independent-review corrections

Status: implemented; repaired-candidate final validation in progress.
Date: 2026-10-09. Same [Draft PR #237](https://github.com/danyasemennikov/rpg-bot/pull/237).
Branch: `feat/pxe1-player-experience-economy-v1`.
Reviewed HEAD: `74389cb22ee6f49f584cc9c09a5f17cb792901c9`.
Correction code/test commit: `4ade6abf8db825097c9754ce204e564c96cdfa5b`.
Completed-side round follow-up / final code-test candidate: `33dff106ec6b17563e575c56a88dceed78673cd0`.
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
| All new regressions | `python -m pytest -q tests/test_pxe1_review_regressions.py --tb=short` | **154 passed, 34.48s**, exit 0 |
| Combined focused/compatibility | All `test_pxe1*.py`, shared runtime, retained PvP/build journey/economy/alpha transaction suites | **520 passed, 110.83s**, exit 0 on `33dff10`, including all 154 new cases; earlier 499/520 runs remain historical |
| Round restoration follow-up | Added exact round assertion at completed-side restart | Before: 1 failed / 1 passed, 1.45s; after: 38 passed, 10.69s |
| Repaired-candidate broad gate | **`python -m pytest -q`** | First attempt stopped (not PASS) for confirmed round-restoration repair; final candidate repetition **RUNNING** with fresh history |

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
re-review of repaired HEAD: **PENDING**. Final broad completion is required before
claiming **READY FOR NARROW INDEPENDENT RE-REVIEW**. This remains one unmerged
Draft PR; no merge or deployment is authorized.
