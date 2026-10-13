# PXE1 live validation repairs — LIVE-01–LIVE-14

Status: **DRAFT_REVIEW**. All fourteen dispositions are **CODE_FIXED**. Real
Telegram acceptance of these repairs remains **PENDING**; automated checks do
not establish deployment, mobile UX, multiplayer acceptance or release readiness.

## Baseline and evidence

- Repository: `danyasemennikov/rpg-bot`.
- Remote `main` fetched and verified on 2026-10-13 UTC:
  `25cf3a1f917794c0b13949704b1877bdc8e4064d` (merged PR #237).
  Rechecked against `git ls-remote` before the implementation commit.
- Repair branch: `fix/pxe1-live-validation-defects`, based on that remote `main`.
- Code/test commit: `6bb5be5461c69a1bc49c9d4949e60e8b63c5b008`.
- Original live candidate: `806aee47ef6206812e1697db7d20faa312f2f400`;
  execution merge: `25cf3a1f917794c0b13949704b1877bdc8e4064d`.
- Primary evidence, read from the original validation output directory:
  `C:/Users/masha/Documents/Codex/2026-10-11/pxe1-full-real-telegram-gameplay-validation/outputs/`.
  The report completed on 2026-10-13, with 5 PASS, 9 FAIL, 1 PARTIAL and 9 BLOCKED
  across 24 frozen scenario rows. Those historical verdicts are unchanged.

Original file SHA-256 values (checked again before delivery):

| File | SHA-256 |
|---|---|
| `PXE1_REAL_TELEGRAM_VALIDATION_REPORT.md` | `66a8b0961349f6cc63be4b206497d17ed7ba5c58dc0dacdeffa3e6caedabcc57` |
| `PXE1_H01_H20_RESULTS.json` | `a4be9fa07c72cb3fada58b4b0fdfba5ea3f74b745503a9c7bb18645926ac3bf4` |

## Dispositions

The initial LIVE table below describes the original repairs. For LIVE-05, LIVE-09 and LIVE-10, the F1–F3 packet below supersedes its initial coverage and implementation details. Astra found those three LIVE dispositions PARTIAL at the reviewed HEAD; their new CODE_FIXED dispositions depend on the focused evidence below and await narrow re-review.

Paths below are relative to `rpg/`. P means
`tests/test_pxe1_live_presentation_repairs.py`; C means
`tests/test_pxe1_live_callback_repairs.py`. Every row needs the narrow real-client
retest described in the last column. No row is live-accepted by these tests.

| ID / status | Actual root cause | Changed behavior / files | Permanent regression coverage | Pending live check |
|---|---|---|---|---|
| LIVE-01 / CODE_FIXED | Confirmation sends HTML-bearing creation copy without a parse mode and reuses the pre-allocation prompt after allocation. | `handlers/start.py`: escape the name, render HTML, send the alpha introduction with the permanent menu after creation. Allocation and replay paths retained. | P `test_live01_*`: RU/EN/ES, special characters, exact six-point allocation, malformed confirmation, repeated confirmation and starter-tool preservation. | Fresh registration, including legitimately fresh RU entry; verify creation/introduction and completed allocation. |
| LIVE-02 / CODE_FIXED | Activities uses the formatted profession screen title as a plain Telegram button label. | `handlers/activities.py`, `locales/pxe1_surface_keys.py`: a plain RU/EN/ES profession label; same `pe_o:0` callback. | P `test_live02_*`: literal expected labels, no angle brackets, callback unchanged. | Open Activities in all three languages. |
| LIVE-03 / CODE_FIXED | Three hand-maintained Help inventories predate the registered PXE1 commands. | `game/player_commands.py`, `bot.py`, `locales/{ru,en,es}.py`, `locales/pxe1_surface_keys.py`: shared public-menu command inventory, plus retained registered compatibility/recovery commands in Help. Retire all three obsolete Help lists. | P `test_live03_*`: actual Help response, mocked command registration, AST comparison against all registered handlers; `/journal` and `/activities` present, `/quests` absent. | Compare `/help` with Telegram autocomplete in RU/EN/ES; compatibility/recovery commands remain callable. |
| LIVE-04 / CODE_FIXED | Preview and travel progress use invariant plural nouns. | `locales/pxe1_surface_keys.py`: existing plural resolver selects preview and progress forms by hops/total. Timing and edge calculations unchanged. | P `test_live04_*`: EN/ES 0,1,2,5,11,21; RU 0,1,2,4,5,11,12,14,21,22,25,111. Existing travel tests check exact durations/deadlines. | One-edge and multi-edge previews and travel progress in RU/EN/ES. |
| LIVE-05 / CODE_FIXED | Successful board acceptance and claim use blocking Telegram alerts for ordinary feedback. | `handlers/location.py`: acceptance toast; edited claim result with XP/gold, bonus items, hunter reputation/rank and level-up, plus next-assignment/board/Journal links. The initial acknowledgement filter omitted `chapter_objective`; F3 below supplies the complete contract-scoped predicate. Finale retains its existing major chat card. | C `test_live05_*`: real accept/objective/claim owners, RU/EN/ES, duplicate claim, foreign token, wrong board, failed transport with one grant and pending feedback. Existing quest/feedback tests cover finale and reward paths. | Accept and claim First Watch; inspect reward breakdown and navigation without an OK modal; repeat old claim. Also check a rank/level-up claim and finale. |
| LIVE-06 / CODE_FIXED | `pve_result` includes the settlement's level-up and `inline_feedback` appends the same pending fact. | `game/player_feedback.py`: omit exact feedback lines already on the result; keep their acknowledgement keys, including when no new line remains. No reward/progression owner changed. | P `test_live06_*`: actual progression fact plus PvE result, RU/EN/ES, with/without a separate profession level-up; one character line, both legitimate facts preserved, acknowledgement after display. Existing combat delivery/result recovery tests. | Victory crossing one character threshold; one notice and one SQL level-up; verify independent profession/quest feedback remains. |
| LIVE-07 / CODE_FIXED | Build preview ignores its returned rejection reason. | `handlers/build.py`: use the existing localized rejection mapper for redistribution preview/apply. Existing authority order and rollback retained; an old hub intent invalidated by movement still reports stale. | C `test_live07_*`: RU/EN/ES fresh outdoor preview and moved hub-issued apply; player attributes/draft/receipts unchanged. Existing character tests cover spending and combat restrictions. | Fresh outdoor redistribution Preview gives the safe-hub restriction; verify unchanged attributes and receipts. |
| LIVE-08 / CODE_FIXED | Post-Chapter Journal routes to regional home; its archive callback is misleadingly labelled Back, and Regional Completed has no Chapter history link. | `handlers/regional.py`, `locales/pxe1_surface_keys.py`: explicit Chapter history entry on home and Completed, using retained `alpha_history`/`alpha_history_chapter`. Separate regional records preserved. | P `test_live08_*`: fresh Journal → Completed → History → Chapter archive; full database dump unchanged in RU/EN/ES. Existing Journal tests retain eight home controls and archive grouping. | After finale open a fresh Journal, discover Chapter history from home and Completed; inspect four stories; no grants. |
| LIVE-09 / CODE_FIXED | Repair and sale rejection branches return after an alert without replacing the obsolete quote. | `handlers/activities.py`, `handlers/shop_views.py`: replace rejected quotes with current owned Tools/Sell/Buy lists. Fresh quotes require explicit selection. Mutations and receipt replay stay in existing owners. | C `test_live09_*`: retained 24/120 repair after fresh repair, replay of committed receipt, old All39 after selling one, foreign tokens and protected gear; canonical economic tables byte-for-value unchanged after rejected/replayed calls. | Retain repair A, execute B, click A: current durability, no charge. Retain All39, sell one, click old All39: current 38, no sale. Check equipped/protected rejection and successful-token replay. |
| LIVE-10 / CODE_FIXED | Sale rows and quote headings use the base item name, losing exact-entry metadata. | `handlers/shop_views.py`: common owned-entry label for rows and confirmation; localized rarity, enhancement, secondary rolls and equipped status, while callbacks/intents still bind the exact selected entry. Legacy gear supported by retained inventory resolvers. | P `test_live10_*`: equipped/common versus unequipped/uncommon +1 swords, RU/EN/ES labels and confirmation payload entry IDs. C `test_live09_10_*` and existing sale tests prove equipped/protected/last-item rails and replay. | Compare equipped and unequipped swords/rings, different rarity/+1 variants; confirmation clearly identifies the selected gear; equipped sale remains blocked. |
| LIVE-11 / CODE_FIXED | Local maps filter exclusively by route; the one-node coast has no remaining node to show and drops its real border neighbor. | `handlers/world_views.py`: append actual current-node border neighbors after the current regional node list. Existing `goto_` preview and travel authority used; no new topology/teleport. | P `test_live11_*`: coast offers actual Aster neighbor, current location/topology unchanged, RU/EN/ES. Existing local/mine/world-map budgets and travel discovery tests. | At South Coast Shore, Map → Aster exit → ordinary travel preview; retain region-first navigation. |
| LIVE-12 / CODE_FIXED | Terminal activity rendering reads the player's current location rather than that session's persisted path/edge index. | `handlers/activities.py`: terminal position uses saved `path_json[edge_index]`; running cards retain current location. Stop ownership/cancellation/deadlines untouched. | C `test_live12_*`: Trip1 stopped at Wheat, Trip2 reaches Meadows, old Stop still renders Wheat; new trip/session/economy unchanged; outsider rejected; cancelled/interrupted/arrived cards use their own snapshots in RU/EN/ES. Existing travel tests cover due equality/restart. | Reproduce old cancelled Stop while newer trip runs; old Wheat result and current Meadows progress remain distinct. |
| LIVE-13 / CODE_FIXED | Spanish lacks the actual Guard key consumed by combat views; i18n falls back to RU. | `locales/es.py`: `location.pvp_action_guard_btn` is `🛡 Defensa`. Same action binding/evaluator. | P `test_live13_*`: direct Spanish dictionary entry (no fallback), actual PvE menu/action card and durable Guard intent kind. Existing combat UI checks all three languages. | Open Spanish PvE action menu and confirm Guard; check timeout/action behavior unchanged. |
| LIVE-14 / CODE_FIXED | Missing EN/ES descriptions return a nonempty generic string interpolated with internal item ID. | `game/i18n.py`, `locales/professions.py`: neutral localized unavailable-description copy without IDs; valid descriptions and gear actions retained. | P `test_live14_*`: EN/ES absent/present translations and actual English Wooden Sword More card with unchanged unequip/enhance controls. Existing inventory tests. | English Wooden Sword → More: readable fallback, no `wooden_sword`; verify valid descriptions and equipment actions. |

## Original implementation validation (historical)

Original code/test commit `6bb5be5461c69a1bc49c9d4949e60e8b63c5b008`: **272 passed, 0 failed**, Python 3.12.10,
pytest 9.1.1, python-telegram-bot 21.11.1. Includes **74 new regression cases**
and **198 existing focused cases**. Tests use the repository's autouse fixture
with per-test temporary SQLite databases. Mock transports are unit evidence only.

Exact command, run from `rpg/`:

```text
python -m pytest tests/test_pxe1_live_presentation_repairs.py tests/test_pxe1_live_callback_repairs.py tests/test_pxe1_navigation_ui.py tests/test_pxe1_journal_surfaces.py tests/test_pxe1_feedback_journal.py tests/test_pxe1_local_surfaces.py tests/test_pxe1_travel.py tests/test_pxe1_tools_economy.py tests/test_pxe1_shop_transactions.py tests/test_pxe1_inventory_surfaces.py tests/test_pxe1_combat_ui.py tests/test_pxe1_combat_delivery.py tests/test_pxe1_combat_result_recovery.py tests/test_pxe1_character_spending.py tests/test_quest_board_phase1.py -q --tb=short --junitxml=../../pxe1-targeted-tests.xml
```

`git diff --check` passed. Complete production/test diff reviewed. The original reporting commit `26ad28013145f186b9cb5451543c3a2dcbde262b` changed documentation only. That 272-pass run is historical evidence for the reviewed candidate, not validation of the F1–F3 repairs below.

**No full pytest or broad acceptance suite was run. No complete H01–H20 gameplay
replay was performed. No Telegram poller was launched, no live deployment was
performed and no main-player database was opened or modified.** Original evidence
remains separate from this repair report.

## Limitations, exact retest scope and independent review

All feasible repairs completed; no PARTIAL/BLOCKED code repair remains. Retest only
the changed real-client flows above from H01, H02, H04, H05, H06, H07, H15, H17,
H18, H19 and H20, with RU/EN/ES and actual phone observation where relevant. Use
legitimately fresh isolated characters for registration and controlled prerequisites
for Chapter completion, duplicate gear and travel. Preserve this run's earned
history and original failed evidence. Capture before/after receipts for claim,
repair/sale, respec and stale Stop; do not infer state from cards alone.

Before an authorized retest, establish exclusive polling ownership in its isolated
environment; the historical report observed a reappearing original launcher.
This implementation task does not start or stop that production runtime.

Independent review should focus on post-edit feedback acknowledgement, compact
claim/result and long gear-label budgets, safe refresh after stale economic actions,
archive navigation and pagination, border exits preserving discovery gates, and
terminal travel provenance. Telegram edits can fail or refer to deleted messages;
database transactions are not undone by transport failures. Automated mock editing
does not prove Telegram toast/rendering or phone usability.

Nine previously blocked multiplayer scenarios (H09–H12 and H13a–H13e), actual
mobile acceptance and other historical coverage gaps remain outside this repair
task. They are not cleared by this PR; this report does not request their full replay.

No intentional gameplay, schema, topology, XP/reward, combat, sale-protection,
ownership or travel-timing change. Keep this PR Draft for independent architectural
review and owner approval; do not merge or mark Ready for Review.

`PROJECT_STATE_CURRENT.md not updated: no confirmed project state change.`
The existing current-state documentation still names its older reconciled baseline;
this Draft repair records verified Git state above without rewriting unrelated
historical implementation/acceptance reports or claiming the fixes are merged.

## PR #238 focused F1–F3 correction packet

Reviewed HEAD: `26ad28013145f186b9cb5451543c3a2dcbde262b`.
Implementation/test commit: `26e3f466131e1fb138b7f614c9b8a330bfb5fe75`.
Historical packet status: the narrow re-review of `6c098733e2f39d5e3fda0c805ede1fce121322e1` verified **F2 and F3 FIXED**, but returned **F1 FIX REQUIRED** for the two residual recovery cases. Their final correction packet follows below. Real Telegram retest remains **PENDING**. Same branch, Draft PR #238 into `main`.
No Issue #239 work or next development phase included.

The source review was read from
`C:/Users/masha/Documents/Codex/2026-10-13/pxe1-independent-acceptance-review-of-draft/outputs/PXE1_PR238_INDEPENDENT_REVIEW.md`.
Its external report and probes are preserved; they remain evidence for the reviewed
HEAD, including the three FIX REQUIRED findings. They are not rewritten as passes.

| Finding / affected LIVE IDs | Root cause and correction | Regression evidence | Disposition |
|---|---|---|---|
| F1 / LIVE-05 | Full reward details lived only in the original handler return value. Extend the existing claim feedback JSON in the reward transaction with actual bonus grant, hunter points/rank transition, level transition and owner-bound action token. Render both initial delivery and recovery from this snapshot. Bind known card coordinates before editing; preserve replacement coordinates before acknowledgement. Accept Telegram not-modified as successful presentation; replace confirmed deleted/uneditable cards; other transport errors retain pending facts. Replay the owned snapshot before any reward mutation, even after intent cleanup. Repeatable contracts receive distinct notification keys rather than overwriting an older snapshot. Legacy events render only their stored XP/gold; missing historical details are not invented. Finale retains its separate navigation/presented/acknowledged lifecycle and includes its stored claim breakdown. | `tests/test_pxe1_pr238_focused_repairs.py::test_f1_*`: Astra First Watch bonus/reputation/rank/level reproducer in RU/EN/ES; failed edit, same-token retry, fresh Journal and Location with new delivery context; deleted/uneditable/not-modified/unknown errors; failed replacement; successful edit or replacement then acknowledgement failure; retained message coordinates across recovery; owner/foreign tokens after intent cleanup; legacy payload; repeatable claims; finale navigation/replacement; feedback snapshot failure rolls back the reward transaction. Economic snapshots include hunter progress, contract state/history and receipt tables. | **PARTIAL at reviewed HEAD**; see final F1-A/F1-B packet below |
| F2 / LIVE-09, LIVE-10 | Sell pages counted six entries regardless of rendered label length. Keep full localized rarity/enhancement/secondary-roll/equipped labels and exact entry callbacks; form stable pages from sorted entries using both the six-row limit and actual escaped UTF-16 text length. The same bounded renderer serves stale/protected-sale recovery. No surface-limit increase or label truncation. | `test_f2_*`: reproduce exactly **916 UTF-16 units** for six Spanish legendary `amulet_of_kindled_prayer`, tier 50, +15, valid maximum four rolls **21/21/34/34**. RU/EN/ES pages stay ≤900; all six entries reachable once. Eighteen-instance varied-roll inventories verify distinguishable labels, middle-page previous/next, selected-instance previews and confirmation token IDs. Stale/equipped/foreign callbacks edit bounded current lists without changing gold/items/receipts. | **CODE_FIXED**, narrow review and long-button phone retest PENDING |
| F3 / LIVE-05 | The claimed-contract acknowledgement query omitted the actual producer `chapter_objective`. Capture that claim's objective/progress/readiness/claim and represented character-level keys, bounded by its source and creation time, then acknowledge only after the full result is successfully displayed. Leave other claims, contracts, profession facts and finales untouched. Suppress the pending claim's superseded minor facts in unrelated inline cards until its complete result is recovered. | Combined `test_f1_f3_*` and `test_f3_*`: actual producer events pending during edit; all claimed-contract facts acknowledged afterward; failed presentation/ack leaves pending facts; no old Herb/Rabbit replay on next inline feedback; unrelated contract/profession/finale events remain pending. | **CODE_FIXED**, narrow review and post-claim interaction retest PENDING |

Changed production files are limited to `game/quest_board.py`,
`game/player_feedback.py`, `handlers/location.py`, and `handlers/shop_views.py`.
The quest owner adds presentation metadata only; reward amounts, mutation order,
authorization, repeatability, receipts and gameplay rules are unchanged. No schema
change, new reward ledger, bot launch, deployment or production database access.

Historical F1–F3 validation at `6c098733e2f39d5e3fda0c805ede1fce121322e1`: **79 passed, 0 failed, 0 skipped, 41 deselected**, including
**41 new F1–F3 regression cases** and **38 directly affected existing cases**.
Python 3.12.10 / pytest 9.1.1 / python-telegram-bot 21.11.1. JUnit time 19.758 seconds.
The tested code/test tree is the implementation commit above; subsequent report
changes are documentation only. No full pytest or previous 272-case rerun performed.

Exact command from `rpg/`:

```text
python -m pytest tests/test_pxe1_pr238_focused_repairs.py tests/test_pxe1_feedback_journal.py tests/test_pxe1_shop_transactions.py tests/test_pxe1_live_callback_repairs.py::test_live05_accept_and_claim_are_inline_and_duplicate_claim_grants_nothing tests/test_pxe1_live_callback_repairs.py::test_live05_claim_transport_failure_keeps_reward_once_and_fact_pending tests/test_pxe1_live_callback_repairs.py::test_live05_foreign_claim_token_and_wrong_board_do_not_grant tests/test_pxe1_live_callback_repairs.py::test_live09_old_sell_quote_refreshes_remaining_quantity_without_sale tests/test_pxe1_live_callback_repairs.py::test_live09_10_protected_gear_callback_refreshes_without_sale tests/test_pxe1_live_presentation_repairs.py::test_live06_level_fact_is_shown_once_and_acknowledged_after_delivery tests/test_quest_board_phase1.py -q -k 'test_f or feedback or claim or sale or finale or objective_completion or live06 or protected_gear' --tb=short --junitxml=../../pxe1-f1-f3-targeted-tests.xml
```

Remaining narrow live scope: First Watch claim with bonus/reputation/rank/level,
failed/deleted-card recovery and retry through Journal/Location; no post-claim
objective replay; long four-roll gear Sell pages, exact-instance confirmation and
stale/equipped rejection in RU/EN/ES. Actual phone clipping and Telegram transport
latency remain unverified. Known-card edits are preferred, but an ambiguous timeout
creating a replacement message cannot provide exactly-once Telegram message creation;
the committed snapshot remains recoverable and rewards are never replayed. Old events
without stored bonus/rank metadata retain their available copy without fabricated
historical values. Astra should inspect scoped acknowledgement, payload compatibility,
replacement-coordinate persistence and UTF-16 pagination boundaries.

## Final residual F1-A / F1-B recovery corrections

Reviewed HEAD: `6c098733e2f39d5e3fda0c805ede1fce121322e1`.
Tested implementation commit: `bea8b88662f4d1743b2e4cd263562989194075e6`.
Current disposition: **F1-A CODE_FIXED; F1-B CODE_FIXED — ready for Astra's final
narrow re-review**. F2 and F3 retain **VERIFIED FIXED** from the prior narrow review;
they were not reopened, changed or retested in this packet. Real Telegram acceptance
remains **PENDING**. Keep existing PR #238 Draft into `main`.

The source narrow review was read from the same external evidence directory as the
first review, file `PXE1_PR238_F1_F3_NARROW_REREVIEW.md`. Its FIX REQUIRED verdict and
RU/EN/ES reproducers are preserved. Both exact new regression groups failed on the
reviewed code before correction: **6 failed**, representing two findings in three
languages. Earlier 272-pass and 79-pass results remain candidate-specific history.

| Finding | Root cause | Correction | Permanent regression |
|---|---|---|---|
| F1-A / CODE_FIXED | `_present_feedback_card` overwrote the saved replacement coordinates with the obsolete callback's original coordinates before retry. A successful replacement followed by acknowledgement failure therefore caused another complete reward card. | Prefer the persisted binding. Use the callback's edit method only when it refers to that same saved card, or when no binding exists. A retry of an old callback edits the saved replacement through the bot API; only a confirmed missing/uneditable current target permits another replacement. Retain the current binding through edit/send/ack failures. | `tests/test_pxe1_pr238_final_f1_repairs.py::test_f1a_successful_replacement_ack_failure_old_callback_reuses_saved_card` reproduces original 42 → replacement 100 → ack failure → original callback again, in RU/EN/ES: one successful send, edit target 100, no overwrite even during transport, one reward/history mutation. `test_f1a_transport_ack_combinations_*` and `test_f1a_old_callback_failures_*` cover original edit success/failure, replacement success/failure, acknowledgement success/failure, not-modified, repeated old callbacks, restart, and legitimate replacement of a subsequently missing saved target. |
| F1-B / CODE_FIXED | The claim acknowledgement set included all same-source character-level facts even when legacy claim payloads did not render them. | Separate level facts from the superseded-minor predicate. Build the claim card from its stored snapshot plus scoped durable level events, without consulting the player's current level. Avoid duplicate lines already in modern snapshots. Add acknowledgement keys only for level notifications actually present in the card. A level that exceeds the existing text/line budget remains pending for independent delivery. Use the same composition for the claim section of the finale. | `test_f1b_legacy_claim_displays_separate_durable_level_before_ack` uses a real committed First Watch and level event, downgrades only the claim payload to its legacy format, and deliberately changes current player level to 9: the stored level-2 notice appears once and remains pending during presentation, in RU/EN/ES. `test_f1b_legacy_level_stays_pending_*` covers failed presentation and failed acknowledgement; `test_f1b_level_that_does_not_fit_*` verifies no acknowledgement of an undisplayed level and successful later independent delivery. |

Production delta: **only `game/player_feedback.py`**. New permanent test module:
`tests/test_pxe1_pr238_final_f1_repairs.py`. No change to reward mutation owners,
economy rules, receipts, schema, Sell pagination, quest objective cleanup, world,
combat, Issue #239, merge or deployment. Tests compare canonical economic snapshots
including hunter reputation, contract state/history and receipt tables across retries.

Final focused result: **70 passed, 0 failed, 0 skipped, 21 deselected**, comprising
**45 new final-F1 cases** and **25 directly affected existing recovery/feedback cases**.
Runtime: 17.07 seconds (JUnit 16.915 seconds), Python 3.12.10, pytest 9.1.1, PTB 21.11.1.
Per-test temporary SQLite and mocked Telegram transports. The production/test tree
at the implementation commit above is exactly the tested tree; the subsequent report
commit changes documentation only. `git diff --check` passed.

Exact command from `rpg/`:

```text
python -m pytest tests/test_pxe1_pr238_final_f1_repairs.py tests/test_pxe1_pr238_focused_repairs.py tests/test_pxe1_feedback_journal.py -q -k 'not test_f2 and not test_f3 and not test_f1_f3' --tb=short --junitxml=../../pxe1-final-f1-targeted-tests.xml
```

No full pytest, 272-case suite, prior full 79-case command, F2/F3 validation, Telegram
poller, gameplay replay or production database access was performed in this packet.
Original real-client reports and independent review artifacts remain unchanged.

Remaining recovery risks: actual Telegram callback latency, deleted/uneditable and
not-modified responses still need narrow real-client observation. A send with an
ambiguous timeout can leave an unknown replacement ID; semantic reward exactly-once
does not guarantee exactly-once Telegram message creation. Successfully returned
replacement IDs are retained and reused by old callbacks. Legacy events without
bonus/rank metadata retain only their available stored details; no historical values
are invented. Scoped level facts that cannot fit remain pending and recoverable.
