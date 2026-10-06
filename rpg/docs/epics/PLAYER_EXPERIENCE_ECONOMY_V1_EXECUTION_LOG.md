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

## Membership continuation, candidate based on 0d459e9

Preparation Invite/Accept/Decline/Revoke/Leave now use requester-owned opaque
intents binding engagement revision and exact membership row. The existing
economy receipt owner stores immutable zero-reward outcomes; replay precedes
location, cleanup and roster checks. Invitations expose all eligible allies in
six-entry pages. Preparation delivery retries from persisted membership without
reissuing unchanged cards/tokens. Legacy raw membership buttons only reopen the
current version-1 card. Legacy initialized 1v1 fixtures use the version-0 creator;
the due query supports their stored deadline/turn-start fallback. The existing
character reward owner records level facts atomically, and victory presentation
uses its canonical level_after result.

Focused evidence (same isolated Python/SQLite environment):

- Initial combined run: collection error from an incorrectly indented compatibility
  fixture; no gameplay pass claimed. Corrected affected run: 74 passed, 14.59s.
- New callback/transport/page tests + membership + old 1v1: 1 failed / 50 passed,
  10.13s. Page fixture used a historical epoch without patching the candidate
  domain clock; corrected affected UI/feedback/delivery run: 15 passed, 4.48s.
- Expanded membership callbacks/runtime/compatibility/feedback/delivery + RAV
  transactions/combat: 4 failed / 75 passed, 16.19s. All failures were RAV fixtures
  attempting immediate fresh formation lock. They now advance the actual due
  formation owner while retaining binding, reward and fail-closed assertions.
- Expanded rerun: 1 failed / 78 passed, 16.34s (helper returned roster envelope
  rather than player_ids). Corrected affected RAV combat: 4 passed, 0.95s.
- New coverage includes real ru/en/es Invite→Accept→Leave callbacks, immutable
  replay after movement/token cleanup, commit before Telegram, retry after blocked
  delivery, 31 eligible candidates across six pages, rejecting raw enrollment,
  and isolating one corrupt durable PvP order from a healthy due engagement.

## Cutover/activity continuation, candidate based on 462db09

Validated type/null/default/CHECK shape for all nine added columns. Corrupt
legacy preparations and incoherent formations are locally quarantined with typed
recovery notices; valid rows still migrate and original preparation deadlines
stay intact. Unsupported old invitation consent gets a localized reinvite notice.
An unstarted formation crossing the rules cutover snapshots current actors/enemies
at lock and executes through the shared world owner; already-active legacy rows
retain their compatibility semantics. Mixed reservations now validate every
actor's location/activity under the writer. Startup stops lower-priority travel
without relocating players. Gather ticks check committed receipt/counter/accounting
agreement and source provenance; invalid sessions interrupt without another yield
or durability debit. Travel interruptions retain a durable recovery fact. Nearby
mixed labels show actual unit count and remain paginated beside individual spawns.

Focused evidence:

- Initial schema/lifecycle/world/feedback: 22 passed, 4.31s.
- Expanded migration fixtures: 1 failed / 26 passed, 5.21s. Fixture incorrectly
  performed the pre-PXE1 build cutover after creating a legacy encounter; corrected
  to the actual baseline ordering. Affected expanded run: 31 passed, 6.06s.
- Gather/travel/membership/schema/RAV/mixed: 1 failed / 39 passed, 7.51s; old
  mixed visibility assertion expected the entire encounter list on Location home.
  Updated to traverse actual Nearby encounter pages. Rerun: 40 passed, 8.93s.
- Expanded activity/death run: 2 failed / 48 passed, 11.68s. A misplaced mixed
  guard block was caught in the personal death function; moved to the reservation
  writer. Rerun: 1 failed / 24 passed, 7.81s; contention fixture's second claimant
  was in another location. Corrected both claimants to the actual local source.
  Affected lifecycle/world/death/mixed/RAV: 25 passed, 7.33s.
- Latest affected combined command:
  `python -m pytest -q tests/test_pxe1_schema.py tests/test_pxe1_feedback_journal.py tests/test_pxe1_gathering_sessions.py tests/test_pxe1_travel.py tests/test_pxe1_encounter_lifecycle.py tests/test_pxe1_pve_world_tick.py tests/test_pxe1_pvp_membership.py tests/test_pxe1_pvp_membership_ui.py tests/test_pxe1_combat_delivery.py tests/test_character_builds_v1_mixed_encounters.py tests/test_regional_adventures_combat.py`
  **72 passed, 17.16s**.

## Remaining work

Phase 6 remains in progress. Finish inventory/recipe presentation details and
combat integration; repair known
runtime/recovery compatibility gaps before Phase 7 integrated ru/en/es journeys.
Reconcile older journey fixtures to actual timed domain owners without weakening
rollback, replay, reward, mastery, or actor-membership checks. Run the full suite
only on the near-final coherent implementation candidate. Final report, schema
inventory, docs reconciliation, human NOT RUN artifact, push and one Draft PR
remain outstanding. No deviation has been accepted and no completion is claimed.
