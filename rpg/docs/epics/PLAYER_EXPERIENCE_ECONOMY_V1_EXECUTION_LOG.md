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

## Personal-result continuation, candidate based on dd3ca10

Personal PvE deaths/T2 victories and PvP deaths/group survivor results now record
one delivery fact in the existing feedback table inside their consequence writer.
The immutable receipt remains the only reward/loss authority. Pending results
retry independently of later side revisions, initial Telegram coordinates or
restart. Generic inline/finale feedback cannot consume an unseen result fact.
Successful transport followed by acknowledgment failure preserves visible Details
tokens; replay acknowledges without another send or consequence. PvP results show
own damage, infamy, loss/loot names and private paginated Details in ru/en/es.
Simultaneous-death receipts capture the whole batch's personal infamy before their
first insert. Already-settled actors receive no later live prompts. Failed live
cards also retry from persisted authority. PvE death presentation uses its frozen
hub/HP/MP result rather than rewriting history after later movement.

Focused evidence:

- Initial result/runtime/feedback/RAV run: 24 passed, 5.92s.
- Expanded result recovery: 2 failed / 27 passed, 7.38s. Existing T2 query projected
  only status; included the full encounter row so lifecycle-specific delivery
  facts are recorded. Affected rerun: 29 passed, 6.95s.
- Wider adjacent run: **28 failed / 74 passed, 24.92s**. New result tests passed;
  old durability fixtures used fresh PvP in a safe zone, while PR230/pack fixtures
  retained immediate formation locks, 8-entry inventory pages, old category
  routes and instantaneous travel. Those integration failures remain open unless
  specifically repaired below; do not treat the combined run as a pass.
- Three durability compatibility fixtures now use the version-0 engagement
  creator, preserving their old-runtime recovery assertions. New result suites +
  durability + existing itemization/T2 rollback suites: **75 passed, 15.33s**.
- Latest personal-result, delivery, multiplayer runtime, feedback and legacy PvP:
  `python -m pytest -q tests/test_pxe1_combat_result_recovery.py tests/test_pxe1_combat_delivery.py tests/test_pxe1_pvp_group_runtime.py tests/test_pxe1_feedback_journal.py tests/test_pvp_live_flow_v1.py`
  **60 passed, 12.02s**, including simultaneous-death infamy finalization.

## Inventory/recipe continuation, candidate based on f4ca53d

Similar gear entries show their localized secondary rolls while retaining exact
owned-instance callbacks. Compact item details include category, legacy bonuses
and supply restrictions; blocked inventory potion use is omitted from the main
card. More retains every existing action, regroups controls to two per row, and
links catalogue, Records and Shop. Recipes show output quantity and effect,
current XP and guild service. A guild route chooses the nearest reachable guild
through the canonical discovered-route preview; opening it neither discovers a
node nor starts travel. Missing-input and tool-downgrade blockers are explicit.

Focused evidence:

- Initial affected inventory/recipe/shop: **30 passed, 8.97s**.
- Added ru/en/es distinct-roll, advanced-action, supply restriction, nearest-guild
  real callback and downgrade coverage: **42 passed, 10.89s**.
- Final affected inventory/recipe/shop/travel command:
  `python -m pytest -q tests/test_pxe1_inventory_surfaces.py tests/test_pxe1_recipe_surfaces.py tests/test_pxe1_shop_transactions.py tests/test_pxe1_travel.py`
  **48 passed, 11.71s**. `git diff --check` passed.

## Corrupt activity / delivery bound continuation, candidate based on 5600224

The due PvP owner now includes malformed version-1 JSON or missing/invalid live
deadlines instead of silently skipping busy actors. It validates stored roster,
locked invitation proof, participant identities and timing, then locally cancels
unverifiable live state. Quarantine preserves exact raw payload, committed death
receipts, inventory, HP/MP/location/progression, and other owned combat; it never
creates a victory, refund or loot share. Known members receive typed recovery
facts and an operator diagnostic is logged. Valid version-0 battles retain their
old path. Invalid durable orders remain unapplied and isolated from healthy due
engagements under the existing fail-closed policy.

Malformed due formations (payload, deadline, missing reservation) become
start_failed with owned forming sources released and no private runtime/reward.
Running gathers without a deadline interrupt with no new yield/wear, including
the Stop path. Combat delivery filters already successful revisions before its
batch bound, preventing old unchanged cards from starving newer failed delivery.

Focused evidence:

- Initial multiplayer/legacy validation: **50 passed, 10.04s**.
- Initial corruption + gathering/travel/runtime: **33 passed, 6.78s**.
- Expanded formation/result run: **9 failed / 33 passed, 8.35s**. The new
  validator incorrectly required enemy_units for supported solo projections and
  equated the collecting PvP revision with the last-applied row revision. Both
  were corrected to the established owner conventions; no fixture was weakened.
- Corrected expanded runtime/legacy run: **86 passed, 17.34s**.
- Added bounded-delivery regressions: **1 failed / 48 passed, 12.01s**; the new
  test called the real formation owner with player_id rather than owner_player_id.
  Fixed its signature and supplied the actual initial battle projection.
- Latest affected command:
  `python -m pytest -q tests/test_pxe1_activity_quarantine.py tests/test_pxe1_combat_delivery.py tests/test_pxe1_combat_result_recovery.py tests/test_pxe1_pvp_membership_ui.py tests/test_pxe1_encounter_lifecycle.py tests/test_character_builds_v1_mixed_encounters.py tests/test_regional_adventures_combat.py`
  **49 passed, 11.69s**.

## Existing itemization journeys, candidate based on 7533f4d

PR230 anchored fixtures now advance the actual due formation owner before
runtime/terminalization, while preserving source-tamper, rollback, reward,
participant exclusion, mastery and restart assertions. Old corrupt-overlap PvP
fixtures explicitly create version 0. Inventory traverses all 17 owned entries
as 6/6/5 and preserves exact page routing. Advanced sale uses the current Shop
preview/result flow, and Chapter acceptance opens the current board Details.
Regional chase opens Travel preview, explicitly starts, then advances its real
due session; no sleep simulates movement. Mocks now include the actual Bot
transport interface used for recovered results/finale. The pack fixture also
waits for its actual formation deadline. Paginated inventory shows Page N/M and
exports the six-entry constant. A legacy-rules battle uses its existing death
owner, avoiding an invalid attempt to read V1 actor state from a legacy snapshot.

Focused evidence:

- First PR230/pack/inventory reconciliation: **7 failed / 67 passed, 19.37s**;
  exposed legacy death-owner selection and old board/sale/travel/Bot fixtures.
- Expanded affected result run: **1 failed / 80 passed, 20.53s** (old Chapter
  material sale menu traversal). Corrected traversal: **1 failed / 80 passed,
  20.83s** (finale transport mock missing Bot). Corrected actual interface.
- Latest command:
  `python -m pytest -q tests/test_itemization_fix_packet_pr230.py tests/test_pack_runtime_pr2b1.py tests/test_pxe1_inventory_surfaces.py tests/test_pxe1_combat_result_recovery.py`
  **81 passed, 20.40s**. The earlier 28-failure adjacent run is not converted
  into a pass; only these specifically repaired suites have new evidence.

## Combat acknowledgment continuation, candidate based on 46294a3

PXE1 manual combat orders retain a bound schema-1/catalogue-2 acknowledgment in
the existing action-receipt owner, in the same writer as token consumption and
the authoritative combat order. It contains no grants, XP or gold change and
never evaluates/applies another side on replay. Consumed callbacks recover the
original acknowledgment before movement, deadline, turn or token-cleanup checks;
legacy version-0/V1 pre-PXE behavior is preserved. PvE consumption revalidates
the durable actor, explicit target/pattern, rank/family, MP and cooldown under the
writer using the shared pure evaluator, discarding its copies. Old missing
battle tokens now refresh a read view without clearing another combat or
cooldowns. Combat receipt history has localized action/status labels.

Focused evidence:

- New replay/transport/rollback + combat UI/durability/delivery:
  **34 passed, 7.58s**.
- Added under-writer no-MP/cooldown/vanished-target rejection + adjacent group
  runtime:
  `python -m pytest -q tests/test_pxe1_combat_order_replay.py tests/test_pxe1_combat_ui.py tests/test_character_builds_v1_durability.py tests/test_pxe1_combat_delivery.py tests/test_pxe1_pvp_group_runtime.py`
  **43 passed, 9.02s**. Full suite remains NOT RUN.

## Active PvE recovery continuation, candidate based on 5aac389

Malformed PXE1 active snapshots are now isolated by their existing encounter
owner. Invalid JSON, locked identities, actor/enemy state or deadlines terminate
as state_lost, preserve snapshot bytes and historical receipts, release only
owned activity flags, return owned anchored sources to their 30-second respawn,
and record personal recovery notices. Invalid terminal outcomes follow the same
path; transient settlement failures remain retryable. No reward, death penalty,
player build or inventory state is reconstructed or granted.

Focused evidence:

- Final combat guard hardening: **10 passed, 2.51s**.
- Active PvE quarantine and adjacent runtime/recovery: **44 passed, 9.72s**.
- `python -m pytest -q tests/test_pxe1_activity_quarantine.py tests/test_pxe1_pve_world_tick.py tests/test_pxe1_combat_delivery.py tests/test_pxe1_combat_result_recovery.py tests/test_pxe1_combat_order_replay.py tests/test_itemization_fix_packet_pr230.py --tb=short`
  **91 passed, 23.92s**. Full suite remains NOT RUN.

## Startup combat/preparation precedence, candidate based on 7571caf

Startup now preserves existing active PvE/PvP before conflicting future
preparations. A conflicting principal cancels the unstarted PvP engagement; a
conflicting accepted ally alone expires with a recovery notice and revision
change. A conflicting PXE1 PvE formation releases its own unstarted sources as
start_failed. Live snapshots, player state, prior crime and receipts remain
unchanged. Existing domain owners perform these transitions under the startup
writer. This does not claim all impossible cross-domain overlaps are resolved.

Added terminal-invalid-outcome quarantine and injected recovery-writer failure
checks: recovery rollback preserves every row and a later tick retries normally.

Focused evidence:

- `python -m pytest -q tests/test_pxe1_activity_quarantine.py tests/test_pxe1_travel.py tests/test_pxe1_pvp_membership.py tests/test_pxe1_encounter_lifecycle.py --tb=short`
  **44 passed, 7.88s**.
- `python -m pytest -q tests/test_pxe1_activity_quarantine.py tests/test_pxe1_travel.py tests/test_pxe1_pvp_membership.py tests/test_pxe1_encounter_lifecycle.py tests/test_pxe1_pve_world_tick.py tests/test_pxe1_combat_order_replay.py --tb=short`
  **60 passed, 11.86s**.

## Earned build and Chapter integration continuation

The shared earned-build harness uses actual travel preview/Start/world ticks,
automatic formation deadlines, read-only action selection followed by explicit
target/scope commitment, and the actual Bot send/edit interface. Turn evidence
reads committed snapshots rather than a discarded projection. All twenty
weapon branches retain actual earned M8/M14, skill-effect, reward, provenance,
mastery, actor, and reverse-join assertions. Regional callers of the shared
selector now await it and use current formation controls; their entire RAV1
history is still not validated because its PEV1 prerequisite needs repair.

Chapter journeys retain four original assignments/rewards, actual equip/craft,
claim and harvest rollback/replay. Gathering pins only a legal RNG seed, then
commits real 8-second ticks against unchanged SHA probabilities and stops the
session. No items, XP or objectives are injected. Shop uses its current preview
and receipt route. All three languages and four required builds complete
Chapter I. Skill Details restores the localized damage/support school. Harvest
lists now order eligible entitlements by earliest expiry, with stable ID ties.
The consumable proof creates its deficit within combat, avoiding a false
assumption that a level-up after victory leaves HP missing.

Focused evidence:

- Initial shared-harness reconciliation: **4 failed, 21 deselected, 2.01s**
  (old purchase dispatch/formation controls); then **2 failed, 2 passed,
  21 deselected, 5.92s** (stale evidence snapshot and edit mock signature).
  Corrected Guardian/Ranger/group subset: **4 passed, 21 deselected, 56.71s**.
- `python -m pytest -q tests/test_character_builds_v1_journeys.py tests/test_character_builds_v1_group_journeys.py --tb=short`
  **25 passed, 619.15s**.
- Language runs: **3 failed, 1.53s** (old title), **3 failed, 2.16s**
  (missing school), **3 failed / 15 passed, 6.72s** (nullable support school).
  Final language + character spending: **18 passed, 9.34s**.
- English Chapter: **1 passed, 6 deselected, 4.59s**.
- `python -m pytest -q tests/test_playable_alpha_v1.py tests/test_character_builds_v1_gear_journey.py tests/test_character_builds_v1_language_journeys.py --tb=short`
  **11 passed, 53.65s**.
- Earliest-expiry hunting + tool checks: **6 passed, 1.85s**.
- PEV1 history/consumable probe: **2 failed, 5.21s** (old 17 starter recipes;
  invalid post-level-up deficit assumption). Corrected actual combat consumable:
  **1 passed, 1 deselected, 2.28s**. The history test still fails on 17 versus
  frozen 22 starters; timed gathering/tool progression, 83 recipes and policy-2
  history remain to be reconciled without weakening earned-state assertions.

Full suite remains NOT RUN. Human Telegram validation remains NOT RUN.

## Canonical locale-family integration, candidate based on bd40fde

Added explicit canonical families for Menu, Common, Combat, Character, Command,
Tool, Profession, Inventory and Shop. Existing translated semantics are reused
through checked aliases; missing surface copy is authored separately in en/ru/es.
The installer runs after each complete locale has loaded. Legacy flat aliases
remain readable, and integrated controls now use canonical keys. The validator
checks every required suffix of these nine declared families directly, without
the runtime Russian fallback, and rejects missing/non-text values and unequal
placeholder sets. It intentionally does not claim coverage of the eight other
frozen families: Location, Map, Travel, Encounter, Gather, Quest, Journal and
Chapter. Their integration and numeric-aware wording remain outstanding.

Consumed PvE order refreshes now remember their successfully edited surface.
Failed transport leaves prior coordinates intact and never executes another
side. The existing receipt remains the acknowledgment authority.

Focused evidence:

- Initial canonical surfaces: **37 passed, 12.32s**.
- With strict missing/placeholder checks and combat replay: **51 passed, 14.30s**.
- A command named a nonexistent tools test file: **no tests ran, 0.00s**;
  corrected the filename rather than treating that command as acceptance.
- Canonical Tool/Profession + recipe/navigation/build/combat: **66 passed, 18.94s**.
- Adjacent tool/recipe/inventory/delivery/result recovery: **48 passed, 11.57s**.
- `python -m pytest -q tests/test_pxe1_navigation_ui.py tests/test_pxe1_tools_economy.py tests/test_pxe1_recipe_surfaces.py tests/test_pxe1_inventory_surfaces.py tests/test_pxe1_shop_transactions.py tests/test_pxe1_combat_ui.py tests/test_pxe1_character_spending.py tests/test_character_builds_v1_language_journeys.py tests/test_pxe1_combat_order_replay.py tests/test_pxe1_combat_delivery.py tests/test_pxe1_combat_result_recovery.py --tb=short`
  **116 passed, 28.74s**.
- Added failed-transport coordinate regression:
  `python -m pytest -q tests/test_pxe1_combat_order_replay.py tests/test_pxe1_navigation_ui.py --tb=short`
  **26 passed, 4.83s**.

## 2026-10-07 — full locale families and numeric wording

Completed all seventeen frozen families with explicit ru/en/es strings. Strict
validation now checks every required suffix and all four numeric variants,
including missing keys, non-text values and placeholder parity without fallback.
Live gathering uses the canonical nested family; its former flat action label
is preserved as `gather.action_label`. Journal, encounter, quest, travel and
personal-result surfaces use the canonical paths. Added safe/guarded/frontier/
war-zone labels, validated route flavor with neutral fallback, gathering M:SS
remaining time and dates on completed assignment history.

Evidence: two initial focused batches exposed missing Spanish legacy aliases
(16 failed / 22 passed, 8.87s and 8.77s); added explicit Spanish text after checking
all alias sources. Navigation/recipes/combat then **38 passed, 8.53s**. A mistyped
feedback filename ran no tests (0.00s), then the discovered navigation/gather/travel
files **40 passed, 6.11s**. Journal/feedback/PvP membership/personal results and all
Chapter variants: **41 passed, 45.80s**. Numeric checks include 0/1/2/5/21.

## 2026-10-07 — history, maintenance, escape and collection recovery

Candidate based on `0d25bc8`. Profession receipts now use six-entry pages,
actual historical dates, translated timed-gather/tool action labels, and explicit
unavailable-detail copy for unknown historical action/status IDs. Regional
Journal retains its eight destinations inside the frozen budget; lists preserve
all entries through paging and show recorded dates. Retired regional IDs use
Earlier records rather than raw IDs. Guild labels and zero-XP craft wording use
canonical locale keys.

An earned journey exposed a real production gap: tier-one replacement excluded
Aster because a regional-only hub helper was used. Replacement and its controls
now share the exact six safe build hubs; six menu-to-commit/replay cases prove
12 gold, full 60 durability and no duplicate debit.

Successful preparation escape writes recovery facts for principals, accepted
allies and pending invitees in the same transaction. Unseen invitees receive a
localized closure, delivery failures retain pending facts, and successful retry
acknowledges once. Escape at the deadline reports expiry and locks combat without
claiming a roll or creating an escape receipt.

Startup validates current active snapshots before assigning ownership. Frozen
reward plans and legacy combat are preserved. Current live fights reserve all
living committed actors in stable roster-lock order; later overlaps are locally
quarantined without rewriting receipts or resources. Unstarted commitments then
reserve actors in stable preparation order. Only an overlapping accepted ally
is expired where both principals remain valid. Repeat recovery is idempotent.

Generic combat audit: LiveCombatRuntime has no actor-count cap. Tests cover
3/7 and 17/23 side rosters, stable complete batches, independently defeated
actors, timeout order and resolve-once behavior. A nine-actor actual PvE journey
covers formation, authorization, resolution and T1/T2 victory settlement; all
nine recipients release correctly and replay does not grant again. Target and
detail pages cover 23 enemies and 17 allies in ru/en/es without changing combat
state or deadlines. The two-per-side checks remain solely in PXE1 PvP policy.
Historical version-zero PvP retains principal-pair authorization and terminal
winner/loser ownership by contract. Single-target fallback indices, source anchor
indices and bounded summary representatives are not roster caps; full actor
resolution and detail navigation iterate collections.

Focused evidence (separate runs, not a combined acceptance total):

- Existing profession/RAV fixtures initially exposed obsolete grouping, recipe
  ingredient routing and XP-policy assumptions: 4 failed / 25 passed, 5.92s;
  then 1 failed / 37 passed, 7.62s; 1 failed / 43 passed, 8.64s;
  1 failed / 43 passed, 8.54s. Corrected fixtures preserve actual ingredient
  navigation and exact clipped policy-2 XP; **59 passed, 12.92s**.
- Foundation/navigation/profession/regional history: **56 passed, 9.46s**.
- Escape unseen-invitee retry: **26 passed, 6.03s**.
- Nine-actor fixture initially expected arrival rather than canonical order:
  1 failed / 17 passed, 5.50s; corrected **5 passed, 1.91s**.
- Large roster UI and historical profession labels: **16 passed, 4.95s**.
- Activity recovery/schema/travel: **40 passed, 7.22s**.
- Duplicate ownership plus escape/feedback: **42 passed, 9.28s**.
- Legacy transactions/tools/regional UI: 2 failed / 27 passed, 6.81s;
  old instant-gather fixtures were replaced with explicit catalogue-one receipt
  replay and current no-instant-yield session assertions. Corrected transaction
  and regional-history suite: **15 passed, 6.92s**.
- Catalogue-one craft XP replay plus current XP/catalogue: **22 passed, 10.27s**.

Earned profession/RAV journey reconciliation is still running. It uses finite
SHA-derived sessions, real wear, repairs/replacements, physical source visits,
paid commissions, paid recipe learning and policy-2 crafts. No materials, gold,
knowledge or progression is injected. Initial runs failed at 12.62s (Aster
replacement), 13.68s (tier-two bootstrap) and 407.63s (repair consumed previously
collected ingredients). Production replacement was fixed; the journey now stages
all 20 tools and rechecks its full ingredient set after maintenance. The current
run is not yet acceptance evidence. Future tests share one current-run, hash-
verified earned checkpoint; old PEV1 checkpoint hashes cannot substitute for PXE1.


Further focused evidence: after validating saved snapshots before overlap
selection, quarantine **24 passed, 13.68s**. All 25 discovered PXE1 files ran
**3 failed / 274 passed, 123.67s**: three local-surface fixtures expected obsolete
raw PvP callbacks. They now inspect the actor-bound immutable membership
payloads; local surfaces/membership/quarantine **57 passed, 27.74s**.

Equipment catalogue pages now contain six entries. Category switching, receipts,
clear-goal and the existing gear-goal pin live behind More with two-column rows.
Tracked pursuits continues to show pinned regional projects and the active board
contract as frozen; gear pin mechanics remain accessible through Inventory.
Affected inventory/metadata/transition run exposed five older fixtures skipping
the first content row and expecting obsolete category/expanded-detail layout:
**5 failed / 32 passed, 23.08s**. Fixtures now read all emitted content rows,
canonical Gear routes and the actual More detail layer, retaining cross-model
exclusivity and enhancement/secondary metadata assertions. Catalogue controls,
gear-goal pin callback, inventory and transition: **33 passed, 24.87s**.


## 2026-10-07 — adjacent routes and malformed commit timestamps

All 25 discovered PXE1 test files passed on `6948487`: **280 passed,
179.35s**. This focused run is not the final broad-suite result.

Adjacent PR227/228 gathering tests now confirm a finite session and commit a
real eight-second SHA-derived tick, retaining XP scaling, level gates, cap,
empty-roll and grant-failure rollback checks. They no longer expect an instant
menu-click grant. Travel migration tests follow the emitted preview/Start
intent and actual due arrival; discovery changes only on arrival. Legacy PvP
presentation fixtures explicitly identify version zero, while movement guards
create real current pending/locked engagements. `/location` resumes a current
PvE encounter rather than expecting the obsolete blanket combat block.

These adjacent suites initially reported **35 failed / 57 passed / 101 subtests
passed, 73.00s**. Gathering reconciliation passed **25 tests, 12.42s**.
Travel/PvP reconciliation then reported **7 failed / 26 passed / 113 subtests
passed, 25.20s**, followed by legacy-PvP **5 failed / 13 passed, 11.33s**;
missing explicit fixture versions and the start-plus-arrival revision expectation
were corrected. Combined travel/PvP/gathering result: **58 passed / 113 subtests
passed, 34.54s**.

Startup now recognizes a locked PvE roster even when its commit timestamp is
missing. Current PvE/PvP validators reject null, malformed and negative commit
times before overlap sorting can throw. Six startup cases prove local quarantine,
unchanged resources/inventory/receipts, no synthetic settlement and idempotent
notices. Recovery/actual-side/settlement suite: **49 passed, 42.27s**.

Two in-flight profession journey runs were explicitly interrupted as superseded,
not reported as passed: the first retained expensive repeated tool-training
crafts; both loaded a funding helper that incorrectly sold the entire bark stack
on every requested-unit iteration. Current training uses ordinary recipes with
the same earned XP and a real finite session per batch. Funding now sells exactly
the requested amount through quantity-capped Shop previews/confirmation and
preserves the recipe reserve. The corrected current-run shared profession/RAV
checkpoint is being rebuilt from registration and all four actual Chapter claims;
no prior PEV1 database or progression grant substitutes for that history.

## 2026-10-07 — current UX and adjacent transaction reconciliation

Candidate based on `a819e7b`; source changes and fixtures were uncommitted during
these runs. Skill Details retain all original effect descriptions and current/next
rank structured profiles. The compact board retains hunter rank/points. Accepted
private regional projects remain reachable after unpinning; fresh characters still
see no hidden project link. Catalogue pages use six entries and bounded UTF-16 cards.

Adjacent fixtures now follow actual nested routes for assignments, recipe branches,
More controls, services and history. Real PvE formations wait to their saved deadline;
legacy TTL/read presentation fixtures identify their historical authority explicitly.
Partial old PvE detail schemas use read-only default projections with no hot DDL.
Denied creation cannot fall through an empty encounter ID into legacy victory rewards.
Gathering fault injection verifies item, XP, objective, tool wear, session accounting,
feedback and receipt rollback in the real tick writer; arrival failure verifies the
whole travel/discovery/threat transaction and exactly-once retry.

Focused history retained, including failed intermediate fixture runs:

- Fifteen adjacent combat/itemization/profession files: **1 failed / 220 passed,
  135.95s**; catalogue expectation corrected; affected inventory/catalogue:
  **50 passed, 35.56s**.
- Initial regional/quest/guild/build reconciliation: **45 failed / 128 passed,
  124.72s**. Build detail follow-up: **2 failed / 35 passed, 22.29s**; regional/build
  subset: **1 failed / 76 passed / 15 deselected, 50.61s**; regional UI selection:
  **15 failed / 67 deselected, 11.86s**; regional/build full: **7 failed / 85 passed,
  50.72s**. After current-profile, locale, handler-context and private-project fixes:
  **102 passed, 64.36s**.
- Quest board, guild, PXE1 Journal/local: **85 passed, 61.89s**.
- Initial critical source/alpha batch: **46 failed / 96 passed / 84 subtests passed,
  151.56s**. Context subset: **18 passed / 5 deselected, 12.29s**; tick/refresh
  selection: **2 failed / 1 passed / 20 deselected, 2.18s**.
- Source + lower menu after partial-schema fix: **23 failed / 62 passed, 16.43s**;
  due/legacy fixture reconciliation: **1 failed / 58 passed, 11.46s**.
- Actual alpha fault suite intermediate: **2 failed / 13 passed, 5.27s** (missing
  required location argument and a nonexistent unit-fixture column; corrected).
- Source/alpha/menu current run: **104 passed, 21.25s**.
- All 25 PXE1 files plus alpha release, solo handler, itemization repair, regional
  review and build UI: **1 failed / 475 passed, 104.22s**. An earlier invocation
  used a nonexistent test filename and collected no tests; it is not pass evidence.
- Durable threat handler follow-up: **1 failed / 58 passed, 11.96s** (fixture chose
  a non-aggressive wolf); corrected to the real eligible aggressive goblin hunter.
  Threat/current PvE/alpha regression: **59 passed, 12.04s**.

The previous process session disappeared at the actual execution boundary, with no
recoverable final journey result; no pass is claimed. A redirected restart revealed
that importing a session fixture into both modules caused two separately built
histories. That run was explicitly interrupted without acceptance evidence. The
checkpoint fixture is now defined once in conftest, calls one current earned-history
builder, and records any setup failure beside the temporary database. Profession and
RAV share its whole-db hash; current long acceptance is still running.

The source contract SHA-256 is `0c5b81abd67805a3839631001c050615b4c3ece49d3506640d1ee483f8598de3`; the repository copy matches byte-for-byte. Changed/new documentation links resolve locally.

Required documentation and human-plan artifacts are prepared with pending statuses.
PR236 merge/base was reverified via GitHub, and historical RAV interrupted human
status is distinguished from PXE1 human validation, which remains NOT RUN. No broad
suite, branch push, Draft PR, independent approval, merge or deployment is claimed.

The shared earned-history run stopped with **1 setup error, 794.52s** at the tier-three
woodcutting commission: ingredient gathering/maintenance spent the commission's
initial fee reserve. The harness now funds the exact final learning/commission fee
after gathering, protects required ingredients from funding sales, and still uses
real Shop sales or combat. No production fee/progression rule was changed. Schema
and documentation-consumer regression: **37 passed, 15.85s**.

A short in-flight earned rebuild was explicitly interrupted before acceptance to
reconcile a remaining J14 fixture: current forming encounters stay busy when their
creation timestamp is backdated, start at the saved 12-second deadline, and release
both sources on explicit non-victory closure/respawn. Local encounter controls are
now followed across the real six-entry category pages. The localized shortage case
sells its legitimately earned food surplus through protected Shop confirmation
before asserting insufficient goods, rather than assuming PEV1's tiny craft count.

The default session fixture still builds a fresh current history. After successful
production checks it additionally saves a whole immutable earned DB and JSON
provenance outside pytest's rotating temporary directories. Optional focused repair
reuse requires matching SHA-256 for both the database and all production/history
sources, every production check, all 83 recipes and all 12 professions at level 20.
It cannot load an old PEV1 checkpoint or modify earned state. Cached history is an
explicit test accelerator only, and any use must be named in the final evidence.

Build/Chapter/group/regional/board/guild acceptance reported **1 failed / 158 passed,
1084.97s**. All twenty ordinary branch journeys passed. The earned group-content
journey found two parked players with real hostile formations, generated by global
world ticks while other party members traveled. Their travel was correctly denied.
The transport harness now chooses the actual legal prelock Leave control before
travel, verifies no XP/gold grant, and never bypasses an active combat lock. An
in-flight profession rebuild was explicitly interrupted so its recorded source hash
cannot silently describe a changed harness. The completed history now verifies
unchanged source hashes from build entry to completion before saving provenance.

The affected earned-group regression now passes: **3 passed, 221.60s**, using
`python -m pytest -q tests/test_character_builds_v1_group_journeys.py --tb=short`.
The current fresh profession/regional build remains in progress; no result is claimed.

The next fresh profession setup reported **1 error, 346.21s**: a real desert-elephant
threat interrupted mining after three successful ticks. The fixture incorrectly
required a fourth receipt. It now verifies terminal hostile interruption and exact
retained tick/yield totals, uses the emitted legal prelock Leave control with no
XP/gold change, and continues earning the missing material through a new session.
Production threat priority and gathering behavior are unchanged.

Retained group/survival/mixed/PvP/token/travel/Chapter regression: **13 failed /
127 passed / 113 subtests passed, 95.95s**. Twelve failures were old synthetic
Location renderers missing current player location data; these explicitly exercise
the retained legacy projection now, keeping advanced snapshot routing and stale
command assertions. Current compact public surfaces retain their PXE1 coverage.
The earned PvP journey now uses the preparation's real 128-bit seed and collection
side ownership, follows current action→target controls (including token replacement)
and short resolved toasts. All original numerical skill effects, cooldowns, pair
relationship count, durable-order restart and finalization checks are retained.
A copied row marked dead no longer substitutes for authority; the journey earns a
real terminal defeat and verifies the stale action cannot charge or add orders.
Deterministic seeds were selected for successful hits through the unchanged pure
evaluator, with no snapshot/progression/win injection into the earned database.

Intermediate affected runs: **1 failed / 22 passed, 7.19s**; individual PvP repairs
reported **1 failed** at 2.43s, 2.58s, 2.63s, 3.80s, 7.49s, 7.80s and 8.76s.
Final affected regression: **23 passed, 20.98s**, using
`python -m pytest -q tests/test_character_builds_v1_pvp_journey.py tests/test_location_action_tokens.py --tb=short`.
The current earned profession/RAV history is still building; full suite is NOT RUN.

The retained map/Chapter-bridge/onboarding/gathering/crafting/rollout batch reported
**2 failed / 58 passed / 76 subtests passed, 28.36s**. A same-location Go request
incorrectly mapped its preview rejection to an unknown-route answer; the handler
now restores the localized already-here response without issuing a travel intent.
The synthetic duplicate-input recipe now declares its fixed material value (four
3g herbs plus one legacy25g venom), retaining aggregation/consumption assertions.
An intermediate fixture value lookup used venom outside the current 28-resource
catalogue: **1 failed / 27 passed, 9.67s**; corrected to the explicit static value.

The in-flight earned history had reached all gathering level18 and all tier-three
tools, but was explicitly stopped without pass evidence before the production UI
repair. No checkpoint from it is accepted. All automated scope is now represented
in the coherent candidate; the next full run builds a fresh current profession
history and covers all regional branches, rather than duplicating that long setup
in another preliminary run. Final documentation/results and the one Draft remain.

Affected same-location/crafting/travel regression: **28 passed, 6.20s**, using
`python -m pytest -q tests/test_map_and_long_route_phase1_5.py tests/test_crafting_runtime_phase7.py tests/test_pxe1_travel.py --tb=short`.

The near-final coherent candidate is `ce2f51dd5e4c7c45faef107e38657099039ebdc5`. The exact
`python -m pytest -q` full run is active, redirected to
`pxe1-final-broad-pytest.log`, with a fresh earned checkpoint and no reuse override.
No final result is claimed until this process completes. Code/test blob and tree
identities are retained in JSON so later evidence-only commits are distinguishable.

The unchanged final broad candidate reported four failures before the earned-history
setup. Diagnostic reproduction: **4 failed / 11 passed, 5.26s**, using
`python -m pytest -q tests/test_formation_metadata_rollout_pr2c2.py tests/test_inn_phase1.py --tb=short`.
Three retained formation mocks reference obsolete equipment reads or omit current
source reservation fields. The Inn test replaces the autouse database with a private
one but omits its regional migration. Candidate repairs remain pending until the
broad process completes; no final pass is claimed.

The proposed four fixture repairs were verified in copies outside the repository:
**15 passed, 4.02s**. Exact scratch-path command is recorded in JSON. Those copies
do not change the in-flight `ce2f51d` candidate and are not final acceptance; the
original test files will be repaired and rerun after the full process completes.

The first exact full command finished: **5 failed / 2186 passed / 40 errors /
276 subtests passed, 3492.79s (58m12s)** on `ce2f51d`. One earned setup failure
propagated to all 39 regional branches; those branches did not execute. Funding
sales consumed future unequipped armor, and the delayed equipment loop then
expected Equip on its already-equipped surviving weapon. The harness now equips
each strongest earned piece promptly, verifies its persisted slot and honors
already-equipped cards. Missing pieces are earned through normal crafts. No
production combat, funding, progression or equipment rule changed.

The fifth assertion failure assumed every recipe output had an NPC item record.
The unchanged strict-negative resale test now includes all 83 recipes and treats
dedicated tool slots as zero-resale outputs, checking their absent inventory item.
Diagnostic reproduction: **1 failed, 1.19s**. The applied formation/Inn/resale
regression passes: **16 passed, 5.10s**, using
`python -m pytest -q tests/test_formation_metadata_rollout_pr2c2.py tests/test_inn_phase1.py tests/test_professions_economy_v1_economy.py --tb=short`.

An attempted whole-copy gear diagnostic could not open the failed database after
pytest had rotated its temporary directory; it exited before backup or gear actions.
No partial history is accepted, and the creator changed, so the next profession/RAV
acceptance must rebuild fresh from registration. Logs retain the failed broad and
diagnostic results. The final broad command remains required on the repaired candidate.

The repaired candidate is `fb89ec23bcbfc09a1d46224cf905f26d3f78bdba`. A fresh
41-test earned acceptance is active with
`python -m pytest -q tests/test_professions_economy_v1_journeys.py tests/test_regional_adventures_v1_journeys.py --tb=short`,
logged in `pxe1-earned-repaired-fresh-pytest.log`. No source from the incomplete
previous history is reused. Its completed result and the repaired broad run remain pending.

## Work-limit preservation while acceptance continues

At the user's request, coherent code and test repairs are preserved at
`fb89ec23bcbfc09a1d46224cf905f26d3f78bdba`. Session 47464 continues the fresh
41-test command above; no completed result or PASS is claimed. Raw acceptance
output remains in `pxe1-earned-repaired-fresh-pytest.log`, and the first failed
broad result remains in `pxe1-final-broad-pytest.log`.

A consistent read-only SQLite backup was saved outside pytest rotation in the
workspace's `acceptance-recovery/fb89ec2-partial-earned/earned.sqlite3`, with
`partial-provenance.json`, at 2026-10-07T17:15:28.765203+00:00. Its SHA256 is
`e8d9df8f92fab2504090add14ada7f1cde67bbeefc07933ea78dd62ec56cdfb4`.
It is explicitly partial, diagnostic only, and cannot load as a completed earned
checkpoint. At backup, five gathering professions and six crafting professions
had reached 20; medium armor remained 16. Final recipe/forge/consumable/locale
checks and the 39 regional branches were still pending. The workspace checkpoint
records the exact continuation step. Work continues while tools remain available.

## Earned terminal result and atomic PvE vitals repair

The fresh `fb89ec2` 41-test run reached normal completion: **1 passed / 40 errors,
6526.18s (1h48m46s)**. This is FAILED, not platform-interrupted or acceptance PASS.
All twelve professions reached 20, all 83 recipes were crafted and the crafted
weapon was enhanced/advanced; the inventory consumable proof then failed. Its
shared setup error prevented 39 RAV branches from executing. The complete raw
output remains in `pxe1-earned-repaired-fresh-pytest.log`. A consistent whole failed
DB and `failure.txt` are preserved outside pytest rotation in the workspace's
`acceptance-recovery/fb89ec2-partial-earned-latest`; it is diagnostic only.

Diagnostics showed a real production defect: accepted combat actor HP fell during
wolf/troll fights, but the player's HP/MP row stayed at its prebattle values. The
PXE1 resolution branch bypassed the older continuing-handler write. The repaired
PvE owner projects each living active participant's HP/MP in the same transaction
as accepted encounter CAS writes and side-result receipts. Stale/duplicate results
do not write resources; failed transactions roll back both; defeated actors remain
owned by their individual death receipts. Current PvP/legacy rules do not change.

The repair is committed at `ca4331e47dee41a5256431f8116d9a3856609140`.
Focused acceptance: **37 passed, 8.47s**, using
`python -m pytest -q tests/test_pxe1_pve_world_tick.py tests/test_pxe1_combat_order_replay.py tests/test_pxe1_combat_result_recovery.py tests/test_character_builds_v1_durability.py --tb=short`,
log `pxe1-vitals-focused-pytest.log`.

A whole-copy diagnostic replenished missing previously consumed outputs through
real learned recipes, then executed all eight unchanged positive recovery effects
and ru/en/es navigation checks: **1 passed, 21.95s**, with the exact external-path
command in JSON and `pxe1-consumables-locale-repaired-diagnostic-pytest.log`.
This is not a completed acceptance history. Earlier guard/troll diagnostics and
their failures remain in workspace logs; no assertion was weakened.

Because production changed, session 98396 now runs a fresh registration-based
41-test history with the same two-module command and no checkpoint override,
logged in `pxe1-earned-vitals-repaired-fresh-pytest.log`. Its final result, the
39 regional branches and the repaired full broad run remain pending.

The affected repaired integration batch completed: **341 passed, 315.54s
(5m15s)**, all 25 discovered PXE1 modules plus solo runtime, alpha integration
and three actual earned group journeys. Exact expanded argv is recorded in JSON;
output is `pxe1-vitals-integration-pytest.log`. Source/test candidate remains
`ca4331e`; the observed `98f2eda` head adds evidence only. Active documentation
file links resolve, and the contract SHA256 still exactly matches the original.
The report names retained version-zero pair adapter symbols and current PvP
content-policy checks for independent review. The fresh 41-test history continues.

## Confirmed Inn funding in the earned history

The fresh vitals-repaired run completed normally: **1 passed / 40 errors,
1575.50s (26m15s)**. Actual damaged HP now persists and triggers legitimate Inn
recovery. During tier-three crafting, the older recovery funding helper exhausted
gold and submitted an immediate All material sale. The current valuable-sale guard
correctly returned `confirmation_required`; the helper incorrectly expected `sold`.
The raw result remains in `pxe1-earned-vitals-repaired-fresh-pytest.log` and its whole
failed DB/failure text in workspace `acceptance-recovery/ca4331e-partial-earned`.
No completed acceptance or RAV execution is claimed.

The creator now uses its existing actual Shop preview/explicit confirmation helper,
with a quantity of 1..99, to fund Inn recovery. No production behavior or assertions
were weakened. Whole-copy failing-state diagnostic: **1 passed, 0.93s**, verifying
confirmed sale receipt, exact sale income minus 12g Inn charge, restored effective
HP and original location. Exact external-path command is in JSON and the output is
`pxe1-inn-funding-repaired-diagnostic-pytest.log`; this is diagnostic only.

The harness repair is committed at `8a9e10c8bfe328ef31b133a776a42a770c10a13d`.
Because the creator changed, session 85414 now runs another fresh 41-test history
from registration, with no checkpoint override, logged in
`pxe1-earned-confirmed-recovery-fresh-pytest.log`. The prior 37/341 production
regressions retain their recorded candidate; their production dependencies did not
change. Fresh integrated history and final broad acceptance remain pending.

## Earned Chapter pack recovery

The confirmed-funding fresh history completed normally: **1 passed / 40 errors,
13.01s**, in `pxe1-earned-confirmed-recovery-fresh-pytest.log`. An early real
three-wolf pack defeated the character while five earned health potions remained
in inventory. The harvesting helper had enabled existing battle potion use only
for trolls. The unchanged no-death assertion correctly failed. Failed whole DB,
source provenance and failure text are saved in workspace
`acceptance-recovery/8a9e10c-partial-earned`; they are diagnostic only.

Harvesting fights now enable the existing earned battle-potion flow for every mob.
No equipment, goods, progression, HP or victories are injected and no assertion is
weakened. Focused clean Chapter history: **1 passed, 9.66s**, completing registration,
field weapon purchase/equip, all four Chapter claims and real battle potion proof.
Exact external-path command is recorded in JSON; output is
`pxe1-chapter-potions-focused-pytest.log`. This is not the full profession history.

The creator repair is committed at `d6453a54bbe9cd617750851f1e5d660c2238f030`.
Session 53588 runs the required fresh 41-test history with no checkpoint override,
logged in `pxe1-earned-battle-recovery-fresh-pytest.log`. Final history/39 RAV
branches and the repaired full broad command remain pending.

## Immediate travel clock and protected Chapter sale reconciliation

The fresh `d6453a5` run completed normally: **1 passed / 40 errors, 3730.28s**,
log `pxe1-earned-battle-recovery-fresh-pytest.log`. Its whole failed database is
preserved as workspace `acceptance-recovery/d6453a5-partial-earned`. An unused
travel token was issued at 22:21 UTC, expired after its real 900-second lifetime,
and was consumed only after the host resumed around 22:49 UTC. Production
correctly rejected it. This is a terminal failed run, not an inferred PASS or a
resumable partial history.

Only the synthetic immediate travel preview/start sequence now freezes its clock.
A one-hour host-pause regression first reproduces the same IndexError (1 failed,
1.24s), then passes together with all six production travel tests: **7 passed,
2.56s**. Actual 900-second token expiry, the 15-second edge, gold/XP conservation
and all existing journey assertions remain intact. Committed at
`2db8a7f526e241b5b5133dd72efd27318dbfef9a`. Three affected earned group journeys
also pass: **3 passed, 170.76s**, `pxe1-travel-clock-group-pytest.log`.

The next fresh history completed **1 passed / 40 errors, 12.81s** at its Chapter
sale (`pxe1-earned-clock-stable-fresh-pytest.log`). Its whole failed database is
preserved as `acceptance-recovery/2db8a7f-partial-earned`. The Chapter helper used
the obsolete immediate sale path; production correctly protected the last owned
small health potion. The helper now uses its existing actual Shop preview and
explicit confirmation flow. No production guard or acceptance assertion changed.
Committed at `0e52fa6078e669deb6fca8dc1d6c4e5a356b7b1e`.

A copied-state diagnostic verifies `last_consumable`, actual confirmed sale and
real Homecoming claim/all four Chapter assignments: **1 passed, 0.66s** in
`pxe1-chapter-protected-sale-diagnostic-pytest.log`. An earlier scratch diagnostic
incorrectly assumed a >=25g stack and failed while 18 unrelated focused checks
passed (14.09s); that result is retained separately. Clean fresh Chapter/potion,
Shop, clock-pause and travel regressions on the final helper candidate:
**25 passed, 13.44s**, `pxe1-clock-chapter-shop-focused-pytest.log`.

Session 28082 now runs another fresh two-module 41-test history from registration,
with `PXE1_EARNED_CHECKPOINT` absent, logged in
`pxe1-earned-protected-sale-fresh-pytest.log`. No failed partial database is reused.
Final profession/RAV acceptance and the final exact broad command remain pending.

## Remaining work

Continue profession and RAV earned journeys against 22 starter recipes, all 83
active recipes, real timed sessions, tool upgrades/commissions/wear/maintenance
and XP policy 2. Resolve remaining recovery/stale-action edges and verify generic
side-turn runtime with arbitrary actor collections; max two per side belongs to
PXE1 PvP content policy. Complete Phase 7 integration, run focused final checks,
then the full suite on the near-final coherent candidate. Reconcile final docs,
schema inventory and evidence, record human Telegram validation NOT RUN, push the
same branch and create exactly one Draft PR. No merge or completion is claimed.
