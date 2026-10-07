# PXE1 — Player Experience & Economy Deepening V1

Status: **IMPLEMENTING / unmerged candidate**. Frozen contract: PXE1-1.
Baseline: PR236 / `3c5bfa62836c705a6327ce059f4e190b54ccf3e6`.
Branch: `feat/pxe1-player-experience-economy-v1`. One future Draft PR; no merge.
Human Telegram validation: **NOT RUN**. Independent architecture review and deployment
are unverified. Exact measured runs belong to [evidence](../evidence/player_experience_economy_v1.json)
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

Current PvP locks actual accepted allies, executes every actor's order once, preserves
15-second deadlines, applies individual death receipts and terminal winning-side
pool distributions, and does not grant PvE XP/gold/quest credit. Historical outer
crime/loss/security policy is retained.

## Recovery and compatibility

Startup processes prepared rewards, interrupts running gathering, restores/validates
active combat, resolves preparations, then reconciles at most one travel/threat edge.
Malformed timestamps, snapshots and overlapping ownership quarantine locally without
synthetic grants/refunds; notices and undelivered combat cards remain retryable.
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
is running on that repaired code. No final pass is claimed. The earned profession
checkpoint is created once per pytest session from registration and all four Chapter
claims, then cloned whole for independent regional branches with SHA-256 provenance.
No old PEV1 checkpoint substitutes for current PXE1 history. Optional focused-repair
reuse of the completed current history verifies its whole-DB hash and all production/
history source hashes; it cannot modify progress or supply goods. Any actual use is
recorded separately from a fresh rebuild.

Human validation remains NOT RUN per the owner's explicit continuation instructions.
This limits Draft handoff to automated evidence; it is not live/release acceptance.
Independent Astra review is pending and the owner retains merge authority. No merge
or deployment is authorized. Teleport and larger structured PvP remain deferred.

Deviations from frozen runtime/product requirements: none identified so far; final
acceptance remains pending and any actual deviation must be recorded explicitly.
