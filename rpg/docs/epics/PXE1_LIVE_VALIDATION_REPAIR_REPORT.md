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
| LIVE-05 / CODE_FIXED | Successful board acceptance and claim use blocking Telegram alerts for ordinary feedback. | `handlers/location.py`: acceptance toast; edited claim result with XP/gold, bonus items, hunter reputation/rank and level-up, plus next-assignment/board/Journal links. Acknowledge the claimed contract's superseded minor facts only after successful edit. Finale retains its existing major chat card. | C `test_live05_*`: real accept/objective/claim owners, RU/EN/ES, duplicate claim, foreign token, wrong board, failed transport with one grant and pending feedback. Existing quest/feedback tests cover finale and reward paths. | Accept and claim First Watch; inspect reward breakdown and navigation without an OK modal; repeat old claim. Also check a rank/level-up claim and finale. |
| LIVE-06 / CODE_FIXED | `pve_result` includes the settlement's level-up and `inline_feedback` appends the same pending fact. | `game/player_feedback.py`: omit exact feedback lines already on the result; keep their acknowledgement keys, including when no new line remains. No reward/progression owner changed. | P `test_live06_*`: actual progression fact plus PvE result, RU/EN/ES, with/without a separate profession level-up; one character line, both legitimate facts preserved, acknowledgement after display. Existing combat delivery/result recovery tests. | Victory crossing one character threshold; one notice and one SQL level-up; verify independent profession/quest feedback remains. |
| LIVE-07 / CODE_FIXED | Build preview ignores its returned rejection reason. | `handlers/build.py`: use the existing localized rejection mapper for redistribution preview/apply. Existing authority order and rollback retained; an old hub intent invalidated by movement still reports stale. | C `test_live07_*`: RU/EN/ES fresh outdoor preview and moved hub-issued apply; player attributes/draft/receipts unchanged. Existing character tests cover spending and combat restrictions. | Fresh outdoor redistribution Preview gives the safe-hub restriction; verify unchanged attributes and receipts. |
| LIVE-08 / CODE_FIXED | Post-Chapter Journal routes to regional home; its archive callback is misleadingly labelled Back, and Regional Completed has no Chapter history link. | `handlers/regional.py`, `locales/pxe1_surface_keys.py`: explicit Chapter history entry on home and Completed, using retained `alpha_history`/`alpha_history_chapter`. Separate regional records preserved. | P `test_live08_*`: fresh Journal → Completed → History → Chapter archive; full database dump unchanged in RU/EN/ES. Existing Journal tests retain eight home controls and archive grouping. | After finale open a fresh Journal, discover Chapter history from home and Completed; inspect four stories; no grants. |
| LIVE-09 / CODE_FIXED | Repair and sale rejection branches return after an alert without replacing the obsolete quote. | `handlers/activities.py`, `handlers/shop_views.py`: replace rejected quotes with current owned Tools/Sell/Buy lists. Fresh quotes require explicit selection. Mutations and receipt replay stay in existing owners. | C `test_live09_*`: retained 24/120 repair after fresh repair, replay of committed receipt, old All39 after selling one, foreign tokens and protected gear; canonical economic tables byte-for-value unchanged after rejected/replayed calls. | Retain repair A, execute B, click A: current durability, no charge. Retain All39, sell one, click old All39: current 38, no sale. Check equipped/protected rejection and successful-token replay. |
| LIVE-10 / CODE_FIXED | Sale rows and quote headings use the base item name, losing exact-entry metadata. | `handlers/shop_views.py`: common owned-entry label for rows and confirmation; localized rarity, enhancement, secondary rolls and equipped status, while callbacks/intents still bind the exact selected entry. Legacy gear supported by retained inventory resolvers. | P `test_live10_*`: equipped/common versus unequipped/uncommon +1 swords, RU/EN/ES labels and confirmation payload entry IDs. C `test_live09_10_*` and existing sale tests prove equipped/protected/last-item rails and replay. | Compare equipped and unequipped swords/rings, different rarity/+1 variants; confirmation clearly identifies the selected gear; equipped sale remains blocked. |
| LIVE-11 / CODE_FIXED | Local maps filter exclusively by route; the one-node coast has no remaining node to show and drops its real border neighbor. | `handlers/world_views.py`: append actual current-node border neighbors after the current regional node list. Existing `goto_` preview and travel authority used; no new topology/teleport. | P `test_live11_*`: coast offers actual Aster neighbor, current location/topology unchanged, RU/EN/ES. Existing local/mine/world-map budgets and travel discovery tests. | At South Coast Shore, Map → Aster exit → ordinary travel preview; retain region-first navigation. |
| LIVE-12 / CODE_FIXED | Terminal activity rendering reads the player's current location rather than that session's persisted path/edge index. | `handlers/activities.py`: terminal position uses saved `path_json[edge_index]`; running cards retain current location. Stop ownership/cancellation/deadlines untouched. | C `test_live12_*`: Trip1 stopped at Wheat, Trip2 reaches Meadows, old Stop still renders Wheat; new trip/session/economy unchanged; outsider rejected; cancelled/interrupted/arrived cards use their own snapshots in RU/EN/ES. Existing travel tests cover due equality/restart. | Reproduce old cancelled Stop while newer trip runs; old Wheat result and current Meadows progress remain distinct. |
| LIVE-13 / CODE_FIXED | Spanish lacks the actual Guard key consumed by combat views; i18n falls back to RU. | `locales/es.py`: `location.pvp_action_guard_btn` is `🛡 Defensa`. Same action binding/evaluator. | P `test_live13_*`: direct Spanish dictionary entry (no fallback), actual PvE menu/action card and durable Guard intent kind. Existing combat UI checks all three languages. | Open Spanish PvE action menu and confirm Guard; check timeout/action behavior unchanged. |
| LIVE-14 / CODE_FIXED | Missing EN/ES descriptions return a nonempty generic string interpolated with internal item ID. | `game/i18n.py`, `locales/professions.py`: neutral localized unavailable-description copy without IDs; valid descriptions and gear actions retained. | P `test_live14_*`: EN/ES absent/present translations and actual English Wooden Sword More card with unchanged unequip/enhance controls. Existing inventory tests. | English Wooden Sword → More: readable fallback, no `wooden_sword`; verify valid descriptions and equipment actions. |

## Automated validation

Final code/test commit above: **272 passed, 0 failed**, Python 3.12.10,
pytest 9.1.1, python-telegram-bot 21.11.1. Includes **74 new regression cases**
and **198 existing focused cases**. Tests use the repository's autouse fixture
with per-test temporary SQLite databases. Mock transports are unit evidence only.

Exact command, run from `rpg/`:

```text
python -m pytest tests/test_pxe1_live_presentation_repairs.py tests/test_pxe1_live_callback_repairs.py tests/test_pxe1_navigation_ui.py tests/test_pxe1_journal_surfaces.py tests/test_pxe1_feedback_journal.py tests/test_pxe1_local_surfaces.py tests/test_pxe1_travel.py tests/test_pxe1_tools_economy.py tests/test_pxe1_shop_transactions.py tests/test_pxe1_inventory_surfaces.py tests/test_pxe1_combat_ui.py tests/test_pxe1_combat_delivery.py tests/test_pxe1_combat_result_recovery.py tests/test_pxe1_character_spending.py tests/test_quest_board_phase1.py -q --tb=short --junitxml=../../pxe1-targeted-tests.xml
```

`git diff --check` passed. Complete production/test diff reviewed. Final reporting
commit changes documentation only; code and tests remain identical to the tested
commit. The final branch/HEAD/PR identity is in the delivery handoff.

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
