# PXE1 — Player Experience & Economy Deepening V1

Status: **DRAFT / second bounded F2/F3 repair validation in progress / narrow re-review FIX / unmerged candidate**. Frozen contract: PXE1-1.
Baseline: PR236 / `3c5bfa62836c705a6327ce059f4e190b54ccf3e6`.
Branch: `feat/pxe1-player-experience-economy-v1`.
Single [Draft PR #237](https://github.com/danyasemennikov/rpg-bot/pull/237); no merge.
Human Telegram validation: **NOT RUN**. Independent review of `74389cb` is **COMPLETE / FIX**;
narrow re-review of `5fea976` is COMPLETE / FIX: residual F2/F3 remain. Second bounded repairs require new acceptance. Deployment is unverified. Exact measured runs belong to [evidence](../evidence/player_experience_economy_v1.json)
and the [execution log](PLAYER_EXPERIENCE_ECONOMY_V1_EXECUTION_LOG.md).

## Frozen section implementation map

| Contract section | Implementation and acceptance owners |
|---|---|
| 1–2 product / baseline | PR236 verified through Git and GitHub; one branch; frozen source contract retained |
| 3 information architecture / compact surfaces | `game/player_ui.py`, `locales/pxe1.py`; surface and locale parity tests |
| 4 six destinations / Nearby / region Map | `game/contextual_keyboard.py`, `handlers/world_views.py`, `handlers/location.py`; navigation/local surfaces |
| 5 PvE lifecycle / current group PvP | `game/pve_live.py`, `game/pvp_live.py`, `game/pvp_group_runtime.py`; lifecycle, membership, group, world-tick and collection tests |
| 6 durable travel / threats | `game/travel_runtime.py`, `game/location_threats.py`; travel, conflicts, migration and arrival fault tests |
| 7 finite gathering | `game/gathering_runtime.py`; SHA ticks, equality Stop, 15-attempt cap, restart interruption and fault rollback |
| 8 tools / commissions / repairs | `game/profession_tools.py`, `game/hunting.py`, `game/crafting_runtime.py`; tool/hunting/economy tests and earned ladder |
| 9 XP policy 2 | craft/gather progression owners; relevance/ceilings and historical receipt replay |
| 10 catalogue / economy | `game/profession_recipes.py`, `game/recipe_knowledge.py`; 83 active/22 starters, 20 tools, four aliases and unchanged 63 prior recipes |
| 11 objective feedback / finale | `game/player_feedback.py`, `game/quest_board.py`, `handlers/chapter.py`; same-writer facts and Chapter journeys |
| 12 Journal / History | `handlers/quest_views.py`, `handlers/regional.py`, `handlers/professions.py`; six-entry history paging and ru/en/es routes |
| 13 character / build | `handlers/character.py`, build progression; spend/reset guards, all 100 skills and next-rank detail |
| 14 combat / inventory / Shop / recipe UI | `handlers/combat_views.py`, `handlers/inventory_views.py`, `handlers/shop_views.py`, `handlers/recipe_views.py`; action→target, protected sale and exact craft receipts |
| 15 additive persistence / cutover | `game/player_experience_schema.py`, startup/due owners; preservation, replay and local quarantine |
| 16 i18n | 17 frozen ru/en/es families, format/plural parity, localized numbers/timers/short actions and public-surface sweeps |
| 17 implementation matrix | actual ownership in [system map](../systems/README.md#pxe1-candidate-owners) |
| 18 automated acceptance | focused checks, real earned profession/build/Chapter/group/RAV histories and final broad result in evidence |
| 19 human acceptance | [human plan](../evidence/player_experience_economy_v1_human.md), all statuses NOT RUN |
| 20 packaging / reconciliation | one branch/Draft; active docs and dated supersession pointers; historical evidence preserved |

## Exact additive schema

Installer marker: `player_experience_economy_v1` in the existing
`economy_schema_migrations` table. The caller owns one migration transaction;
checked schema shapes reject incompatible partial installs rather than overwriting.

Eight new tables (schema version 1): `player_travel_sessions`,
`player_gathering_sessions`, `player_profession_tools`, `player_location_threats`,
`player_feedback_events`, `player_pxe1_ui`, `pvp_participant_settlements_pxe1`,
`pvp_group_settlements_pxe1`.

Nine additive columns: `players.location_visit_revision`;
`pve_encounters.lifecycle_version`, `formation_deadline_ms`, `formation_revision`,
`runtime_started_ms`; `pvp_engagements.world_model_version`, `locked_roster_json`,
`roster_locked_ms`; `pvp_engagement_reinforcements.membership_version`.
Sixteen explicit indexes enforce running-session uniqueness, PvP invitation/seat/
commitment uniqueness, and due/history lookups. Exact names are recorded in evidence.
Existing encounter/order/side-result/T1/T2/knowledge/economy tables stay authoritative.
No level, XP, gear, knowledge, gold, inventory or prior receipt reset occurs.
Catalogue is 2; craft XP policy is 2; gathering RNG, source, travel route, membership,
settlement and UI schema versions are 1. Version-zero PvP/legacy receipt replay remains.

## Combat architecture review

Shared `LiveCombatRuntime`, actor evaluator, orders, target pages, timeout fallback,
affected-side resolution, death/victory and persistence operate on participant
collections. Tests cover unequal 3×7 and 17×23 rosters, 9-player actual PvE side
execution/settlement and paginated 17-allies/23-enemies surfaces in all three locales.
The maximum-two cap occurs only in current PvP content/adapter validation. Historical
version-zero attacker/defender conversion and singleton winner/loser receipts remain
legacy replay compatibility, not a generic engine rule. Summary representatives,
source anchors and single-target scopes do not constrain roster size; complete actor
lists remain available through paginated details.

Exact retained pair adapters for independent review are
`game/pvp_live.py::_ensure_live_runtime_for_battle`, `_init_live_battle_payload`,
`_runtime_side_for_player`, `_runtime_active_player_id` and
`_finalize_pvp_battle`. `advance_engagement_to_live_battle_if_ready` and
`resolve_live_battle_turn` dispatch world-model version 1 to collection-based
preparation/group owners before reaching those version-zero paths.
`game/combat_orders.py::consume_combat_intent` retains principal-only authorization
for version-zero PvP and dispatches version 1 to group authorization.
`game/pvp_group_runtime.py::locked_sides` enforces the frozen current-content
maximum-two policy and principal identity; it does not constrain the shared runtime.

Current PvP locks actual accepted allies, executes every actor's order once, preserves
15-second deadlines, applies individual death receipts and terminal winning-side
pool distributions, and does not grant PvE XP/gold/quest credit. Historical outer
crime/loss/security policy is retained.

## Recovery and compatibility

Startup processes prepared rewards, interrupts running gathering, restores/validates
active combat, resolves preparations, then reconciles at most one travel/threat edge.
Malformed timestamps, snapshots and overlapping ownership quarantine locally without
synthetic grants/refunds; notices and undelivered combat cards remain retryable.
Accepted PvE actor HP/MP projects to each living active participant's player row
inside the encounter CAS/side-result transaction, including background resolution.
Rollback, stale and duplicate results cannot restore earlier resources; individual
death receipts retain ownership of revived HP/MP.
Legacy read helpers can project an old partial PvE schema without hot-path DDL.
A denied encounter creation with an empty authoritative ID cannot enter legacy rewards.

Old instant menu-click tests were reconciled with emitted preview/Start intents and
actual due transactions. Historical forming TTL tests explicitly construct version-zero
rows; current 12-second formation is tested independently. Unit fault fixtures may
supply ingredients; earned acceptance histories inject no progression, materials,
gold, recipe knowledge or combat wins. Their accelerators are controlled clocks,
valid deterministic rolls and mocked Telegram transport.

## Maintenance cutover and rollback boundary

Deployment requires one maintenance restart: stop input/workers, create a consistent
SQLite backup using its supported backup API, run existing validation/migrations and
the PXE1 installer in the existing initialization order, check foreign keys and
preserved row counts, then run ordered recovery before enabling input. No live
migration or production backup/restore was performed for this candidate.

The installer provisions missing starter tool/knowledge/UI rows, acknowledges old
completed finales and upgrades only coherent anchored preparations; re-running it
preserves durability, commission masks, XP, receipts and original deadlines. Active
legacy PvP keeps version zero. New terminal statuses and catalogue outputs make the
old binary unsupported against an upgraded database. Before new play, an operator
may restore the matching pre-cutover backup/binary; after new actions, use a forward
fix that preserves them. There is no destructive down-migration.

## Validation and limitations

The first broad attempt on `ce2f51dd5e4c7c45faef107e38657099039ebdc5` completed with
2186 passed, 276 subtests passed, 5 failed and 40 setup errors. Retained fixture
repairs pass. The next fresh earned attempt completed with 1 passed and 40 setup
errors in 6526.18s; it exposed player vitals not reflecting accepted PvE actor damage.
The atomic resource projection repair passes 37 focused checks; a new clean history
reached a correct valuable-sale confirmation that the older Inn funding helper
failed to follow (1 passed / 40 setup errors, 1575.50s). That helper now uses the
real quantity/confirmation Shop flow; its failing-state diagnostic passes and another
fresh history exposed an early wolf-pack defeat while carried recovery potions
were unused. Harvesting now enables its existing battle-potion path for all mobs;
a clean four-assignment Chapter/potion journey passes (9.66s). The subsequent
fresh history failed normally (1 passed / 40 errors, 3730.28s) after a host pause
aged an immediate travel preview past its real 900-second expiry. Only the test
clock across that immediate preview/start pair is held fixed; its regression
reproduces the failure and preserves token expiry and actual 15-second travel.
A later fresh Chapter exposed the protected last-consumable sale guard (1 passed /
40 errors, 12.81s); the helper now follows actual Shop confirmation, as verified on
its whole failed state. The Chapter/Shop/clock candidate passes 25 fresh Chapter/Shop/
travel checks (13.44s); the changed common travel path also passes three earned
group journeys (170.76s). Its fresh full history reached all 83 recipes and all
twelve profession caps, then failed the recovery-output availability assertion
(1 passed / 40 errors, 6852.97s): later real fights had consumed earlier outputs.
The helper now earns replacements through actual learned recipes before the
retained eight-output/effect assertions. A whole-copy failing-state diagnostic
passes all eight effects and three locales (28.52s); it is not final acceptance.
Its fresh history then completed all core checks, 83 recipes, all twelve caps,
gear/eight recovery effects and three locales. The combined run failed normally:
37 passed / 4 failed in 7128.96s. Four regional scenarios exposed an old XP setup
assumption, spent meat stock, recovery rejecting committed flee, and a stale
combat flag after non-victory closure. The repair validates missing actors against
committed departure receipts while retaining the immutable lock, releases current
closure flags inside the writer without rewards/resource changes, and earns the
required regional setup through actual crafts/harvests. It passes 53 current
runtime regressions plus four whole-prior-party diagnostics (57 passed, 65.59s).
That completed old-source core is preserved, but changed production requires a
fresh history on `28664a7`. It completed all core checks and both profession tests,
but the combined result was 38 passed / 3 failed in 7481.45s. Two J17 delivery-race
setups omitted required boar meat. J18's reverse order used Sunscar's ration reward
to avoid one ordinary 12-XP boar victory, so player XP differed despite identical
finite claims. The test-only repair at `d5b9661` earns actual required ingredients
and the same two-ration stock before either compared order; it retains the original
race, conservation and exact player-state equality assertions. All three affected
cases pass in 61.95s using the whole verified COMPLETE current-source core.
Production/creator/common sources remain unchanged, so that complete history was
reused for the all-41 assertion rerun at HEAD `4629c1e`: **41 passed in 327.76s**.
This is explicitly distinct from a fresh history rebuild. Whole-DB/source hashes,
all eleven checks and exact provenance are preserved in the workspace and evidence.
The exact final `python -m pytest -q` suite completed normally at that same execution
HEAD: **2237 passed, 276 subtests passed in 1777.62s (0:29:37)**; exit code 0.
It explicitly reused the verified COMPLETE current-source history and executed all
collected tests. Its log SHA-256 is
`5c8d502209c843b0845af742242651b91a4489a791d45735d56cd90017066150`.
All seven recorded code/test tree identities match the subsequent documentation-only
HEAD; no production or test code changed after the final broad run. Automated
acceptance was complete for that historical reviewed source. The same branch was published as
[Draft PR #237](https://github.com/danyasemennikov/rpg-bot/pull/237); the subsequent independent review returned FIX as recorded below.
The earned profession
checkpoint is created once per pytest session from registration and all four Chapter
claims, then cloned whole for independent regional branches with SHA-256 provenance.
No old PEV1 checkpoint substitutes for current PXE1 history. Optional focused-repair
reuse of the completed current history verifies its whole-DB hash and all production/
history source hashes; it cannot modify progress or supply goods. Any actual use is
recorded separately from a fresh rebuild.

Human validation remains NOT RUN per the owner's explicit continuation instructions.
This limits Draft handoff to automated evidence; it is not live/release acceptance.
Independent Astra review of `74389cb` returned FIX; repaired code requires narrow re-review. The owner retains merge authority. No merge
or deployment is authorized. Teleport and larger structured PvP remain deferred.

The earlier claim of no runtime/product deviations is superseded by seven confirmed independent-review findings.
Their bounded repairs, root causes and candidate-specific validation are recorded in
[the correction report](PLAYER_EXPERIENCE_ECONOMY_V1_REVIEW_FIXES.md). Historical automated
results above apply to their recorded code; they do not establish repaired-candidate or live acceptance.

### First bounded review-repair validation (historical, superseded by narrow FIX verdict)

The first repair packet reported all seven fixed; independent review later reproduced residual F2/F3. Historical code/test candidate `d282be1d5fb3117cac65eb3d813af41856f27c37`,
production candidate `33dff10`, exact full command `python -m pytest -q`:
**2391 passed, 276 subtests passed in 1568.15s (0:26:08)**, normal exit 0. The focused gate
passed 520 tests in 110.83s; all 41 profession/regional assertions passed in 322.23s.
The fresh repaired-source core completed all 11 checks, 83 recipes and 12 caps;
the final test-only follow-up reuses that verified whole
compatible core explicitly. Prior stopped/failed histories remain preserved.
Root causes, exact commands, hashes and J18 comparison-input correction are in
the [bounded correction report](PLAYER_EXPERIENCE_ECONOMY_V1_REVIEW_FIXES.md).
That packet was submitted for narrow re-review, which returned FIX at `5fea976`. Human Telegram: NOT RUN. Unmerged Draft PR237; deployment/cutover unverified. Never merge.


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


### Second repair first broad attempt — stopped before fresh core

Execution `fcdfb39` / code-test `9d0a02a` produced a failure marker at the ordinary
synthesis journey. It was stopped before the expensive fresh earned core; **no
normal terminal pytest result and no PASS**. Log `pxe1-second-review-first-broad-stopped-pytest.log`,
SHA256 `6f8441ecee66ed2d022a8be61795f7eccb466eff8f5c2fa806a926c6682e4682`; elapsed observer time 963.51s. Retained whole isolated
SQLite state has 5 real victories, HP131/max190 and gold10 at the capital inn.
The exact cloned-state probe reproduces **1 failed in 1.13s**, `assert 10 >= 12`.
A standalone different-seed synthesis run passed (55.04s), confirming this ordinary
test assumed recovery funding rather than ensuring it for legal combat histories.

Test-only `0977db1a0278bf72e70069faaa2561a982106eeb` funds early recovery by selling owned earned material loot
through actual Shop preview/confirmation/mutation. No goods, gold, HP, XP or mastery
are supplied directly. Original 12-gold deduction, full HP/MP restoration, skill
proofs, exact mastery and conservation assertions remain. Exact same retained-state
probe then passed **1 passed in 0.91s**. Whole failure state is preserved outside
pytest rotation at `acceptance-recovery/second-review-237/failed-synthesis.sqlite3`.
Ordinary and group source consumers are being verified before the exact final broad
restart. This common test source is included in strict earned-history provenance,
so no old core is compatible; no expensive new core had been built in the stopped run.
Production F2/F3 code remains `9d0a02a`; unrelated systems/formulas are unchanged.


### Earned helper follow-up verified

At test-only candidate `0977db1a0278bf72e70069faaa2561a982106eeb`, ordinary and group
character-build source consumers completed: **26 passed in 625.96s (0:10:25)**, normal exit 0.
Exact invocation, raw log and SHA256 are retained in JSON evidence. This verifies
the real earned-loot inn funding follow-up without changing production F2/F3 code.
Exact fresh broad restart follows; no completed broad PASS is claimed yet.
