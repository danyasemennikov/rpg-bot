# PXE1 implementation execution log

Implementation is IN PROGRESS. This file preserves focused evidence between
continuations; it is not the final implementation report or acceptance evidence.

Baseline: `3c5bfa62836c705a6327ce059f4e190b54ccf3e6` (PR236).
Branch: `feat/pxe1-player-experience-economy-v1`.
Human Telegram validation: **NOT RUN**.
Final broad acceptance (`python -m pytest -q`): **NOT RUN**.
Draft PR: none at this checkpoint; no branch push or merge has occurred.

## Commerce/build continuation, candidate based on 15dc2a4

Completed as commit `66e2ba9c4cbef57039c6fce7897a95f956bdbc7d`.
Focused tests were run while implementing, before that commit:

- tools + recipes: 12 passed, 3.75s.
- shop + inventory + metadata: 4 failed / 24 passed, 6.82s; fixtures corrected
  for static item prices and hunting schema; rerun 28 passed, 6.44s.
- five adjacent legacy owner suites: 24 failed / 79 passed, 22.75s.
  Commerce receipt/shape/equipped-preview regressions were subsequently repaired;
  the timed-gather/travel and old Location assumptions remain to reconcile.
- expanded commerce/itemization regressions: 69 passed, 14.18s.
- recipe + character + feedback + tools: 3 failed / 28 passed, 7.98s;
  vest-craft fixture lacked the production new-player recipe starter grant.
- recipe + tools after fixture correction: 15 passed, 4.55s.
- recipe + tools + navigation + shop: 41 passed, 9.81s.
- recipe + navigation + character + gathering: 37 passed, 8.74s.
- expanded tool confirmation/all-skill coverage: 1 failed / 55 passed, 15.24s;
  assertion mistook localized Healing for the raw internal key heal.
- final affected character suite: 15 passed, 5.06s.

These are separate runs, not a combined final pass count.

## Combat continuation, candidate based on 66e2ba9

Implemented compact PvE/PvP home, read-only skill/action selection, explicit target
choice even for a single enemy, scope Use confirmation, paginated Supplies with
Use confirmation, persisted formation/combat delivery and participant results.
Formation delivery occurs at creation, 8s, 4s and start. Unchanged ticks preserve
selection tokens. Partial PvE defeat now releases only the defeated actor and
keeps JSON/database revisions consistent. Fresh manual PvE follows the shared
world consequence owner. PvP manual updates deliver to all committed actors;
recovered durable orders recheck the frozen action allowlist. Due PvP processing
is bounded to 100 due rows and isolates failures by engagement.

Focused progression (Python 3.12.10, pytest 9.1.1, isolated temporary SQLite):

- combat UI + PvE tick + navigation: 22 passed, 4.79s.
- initial transport coverage: 3 failed / 25 passed, 6.38s; corrected nonnegative
  UI revisions, production migration fixture, and fallback-only victory display.
  Affected rerun: 28 passed, 5.89s.
- combat/PvP focused rerun: 16 passed, 3.94s.
- adjacent combined suites: **7 failed / 68 passed, 15.35s**. One actual partial
  defeat revision defect was corrected. Six older journey assumptions remain:
  sleep-based aggro, old Buy callback shape (group and PvP journeys), Enter during
  formation (two group journeys), and mixed-encounter text on Location home.
- partial-defeat regression: 1 failed / 19 passed, 5.20s (test queried a nonexistent
  receipt column); corrected to the exact request ID.
- affected rerun: 31 passed, 11.16s.
- additional manual/delivery regression: 1 failed / 33 passed, 12.76s; found and
  fixed missing time import on manual world resolution.
- latest combat/delivery candidate command:
  `python -m pytest -q tests/test_pxe1_combat_delivery.py tests/test_pxe1_combat_ui.py tests/test_pxe1_pvp_group_runtime.py tests/test_pxe1_pve_world_tick.py tests/test_pxe1_navigation_ui.py`
  **34 passed, 7.43s**.
- affected passive-skill presentation:
  `python -m pytest -q tests/test_pxe1_character_spending.py`
  **15 passed, 4.84s**.
- One mistyped character suite filename collected no tests; it is not evidence.

## Remaining work

Phase 6 remains in progress. Finish inventory/recipe presentation details and
combat integration; bind/replay PvP membership operations and repair known
runtime/recovery compatibility gaps before Phase 7 integrated ru/en/es journeys.
Reconcile older journey fixtures to actual timed domain owners without weakening
rollback, replay, reward, mastery, or actor-membership checks. Run the full suite
only on the near-final coherent implementation candidate. Final report, schema
inventory, docs reconciliation, human NOT RUN artifact, push and one Draft PR
remain outstanding. No deviation has been accepted and no completion is claimed.
