# Playable Alpha Vertical Slice V1 — Aster to Elmor

Implementation in this PR, pending Producer review and merge. This document describes
working runtime paths, not a claim that the branch is already deployed.

## Inspection and scope decision

Baseline: `origin/main` at `0abda2eba89e00c6c486f6a75cbb2f3a6b2d4440`
(merged PR228, following PR227 and PR226). The ordinary world graph, persisted PvE,
combat, gear instances, weapon skills, reward delivery, contracts and gathering were
already live. Registration created an empty equipment slot. Crafting had an atomic
foundation API but no Telegram workshop or persisted crafting profession progression.
Hunting had resource/access metadata and persisted profession rows but no extraction.
The contract board had a single active kill contract without a chapter history.

The reported startup defect was confirmed: `bot.main` called `init_db()` but never
`seed_items()`. An existing SQLite catalog could therefore lack PR228's `wood_common`
despite live gathering producing that ID. `initialize_runtime()` now upgrades schema
and inserts missing static catalog rows on every production start. Existing catalog
rows and player data are retained; this is not a rebalance of old database rows.

The chosen feature is a first expedition that pays for and supplies its own equipment.
It connects existing systems through four assignments in the existing one-contract
slot, rather than introducing another quest engine. Its territory is Aster, ordinary
Westwild nodes 1–5 and Elmor. Dangerous deeper routes remain available on their existing
rails, but are not required. No teleport or weapon family changes are included.

## Player journey and content

1. `/start`: six base attributes plus six distributable points, ru/en/es registration,
   and a journal introducing the road to Elmor. Aster's quartermaster offers one
   practice sword, bow or staff, three small health potions and two mana potions.
   These use existing weapon profiles and skill families. An empty weapon slot is
   equipped automatically; legacy equipment is preserved. The kit is once per player.
2. **First watch**, accepted/reported at Aster: two wheat-field rabbits and three
   herbs. Reward: 60 XP, 20 gold, two small health potions.
3. **Caravan provisions**, accepted at Aster or Elmor, reported at Elmor: two meadow
   boars, two meat extractions there, three common wood from nodes 2–5. Travel through
   hills, grove and copse using ordinary map/lower-menu paths. Reward: 100 XP, 35 gold.
4. **Elmor's workshop**, accepted/reported at Elmor: two hill wolves, two local pelt
   extractions, craft a trail vest and field ration, and equip the vest. Reward:
   100 XP, 45 gold. Craft materials remain useful; claiming does not consume them.
5. **Home from the road**, accepted at either hub, reported at Aster: craft a small
   health potion and sell one spare material at a shop. Reward: 80 XP, 40 gold and
   three enhancement shards. The journal points to ordinary hunting contracts,
   weapon skills, attribute spending and enhancement for the next expedition.

Each assignment also grants the existing 20 hunter points. Rewards use the existing
contract XP/level/gold and item delivery rails. Chapter assignments are one-time and
prerequisite-gated; ordinary repeatable hunt contracts remain available. Objectives
count after acceptance. Wearing the vest is checked from actual equipment at claim.

The craftsmen guild now opens a localized workshop at existing guild service hubs:

| Recipe | Profession / required level | Inputs | Output |
| --- | --- | --- | --- |
| Field tonic | Alchemy 1 | 3 common herbs | Small health potion |
| Trail ration | Cooking 1 | 1 boar meat, 1 herb | Ration restoring 40 HP |
| Trail vest | Medium armor 1 (Leatherworking UI) | 2 wolf pelts, 2 common wood | Level-1 medium chest, 6 base defense |
| Field mana | Alchemy 2 | 5 common herbs | Mana potion |

Crafting reuses recipe validation, material consumption and gear/stackable delivery.
The three live professions persist levels/XP, reuse the bounded gathering level curve
(20 cap, 50 × current level XP), and grant twice gathering action XP: 20–24 for these
recipes, discounted once trivial. Other crafting professions/recipes remain foundation
APIs. Food uses the existing consumable restoration rail. Shops can sell one owned
material per confirmation and Elmor stocks low-level potions and replacement weapons.

Hunting supplements ordinary loot: one extraction per owned victorious encounter,
at its location within 30 minutes, for boar meat or wolf pelt. Access, zone tier and
XP use existing hunting/gathering rules. Packs yield one extraction; additional group
participants do not receive extraction rights in this version.

## Persistence and transaction boundaries

Additive, idempotent schema creation introduces `player_starter_kits`,
`player_crafting_professions`, `player_contract_history`, `player_contract_objectives`,
`pve_harvest_claims`, `player_ui_actions` and `player_action_receipts`.
`players.travel_revision` defaults to zero. The old `last_seen` upgrade now adds a
nullable column then fills missing timestamps, avoiding SQLite's restriction on adding
a nonconstant default to an inhabited table. New characters initialize equipment,
discovery and profession rows in their creation transaction. Legacy profession rows
are initialized lazily without resetting progress.

`BEGIN IMMEDIATE` protects current player/location/PvE/PvP validation and mutation.
Starter items/equipment/receipt, gather item/XP/objective/request receipt, craft
inputs/output/XP/objective, harvest claim/item/XP/objective, sale item/gold/objective,
and contract rewards/history share their respective commits. UI craft, buy, sell,
consume, abandon and claim intents are random persisted tokens bound to owner, action,
location, travel revision and a 15-minute expiry. Rerendering that menu invalidates
its previous tokens. Duplicate gathering messages use a player/chat/message receipt.
Failures roll receipts back with the mutation, so a safe retry is possible.

Inventory consumables validate ownership and quantity. Battle consumables additionally
validate active encounter membership and persist restoration, participant projection,
item consumption and receipt together. Ordinary travel commits discovery alongside
the location/revision change and checks the original revision after the delay.

The persisted victory `active → resolving_victory` duplicate guard is preserved.
Its existing reward delivery still spans multiple transactions: a failure after a
partial victory mutation can leave an at-most-once partial reward. This PR does not
claim to solve that older boundary or replace Combat Core/live PvE/PvP.

## Acceptance evidence and limits

`tests/test_playable_alpha_v1.py` runs the full chapter for ru/en/es through production
Telegram handlers: ordinary 12-point character, actual live attacks, ordinary loot/XP,
gathering, extraction, adjacent travel, recipe callbacks, equipment, sales and claims.
It resets process-local PvE state mid-battle and resumes from SQLite. Only deterministic
RNG, ordinary spawn availability, travel delays and background aggro scheduling are
controlled; no stats, victory flags, completed objectives or rewards are injected.
Messages and callback sizes are checked against Telegram limits. Economic/progression
faults and duplicate victory/claim/harvest/craft/sale/consumable callbacks are exercised.

`tests/test_alpha_transactions_v1.py` covers fresh/legacy startup, missing static items,
unchanged legacy gear, failed registration, kit uniqueness, persisted profession gates,
material shortages, rollback after mutation, owner validation, stale travel intents,
safe retry, and battle projection persistence. Unit-only restoration fixtures are
separate from the ordinary-character acceptance journey.

Validation used Python 3.12 and python-telegram-bot 21.11.1:

- Clean baseline, once: **1530 passed, 276 subtests passed** (567.12 seconds).
- Full candidate, once: **1544 passed, 4 failed, 276 subtests passed** (678.34 seconds).
  Three old assertions assumed kill-only independent contracts or a mocked travel
  connection. The route smoke also exposed an overstrict service check: existing
  regional contracts declare authoritative board locations even where their Telegram
  service is not activated. Core accept/claim now preserve that contract scope while
  validating actual player position; no additional UI services were activated.
- Final focused recheck: **99 passed** (46.22 seconds), covering all affected release
  gate/route/PvP-view/contract tests, the three localized journeys and transaction tests.
  All observed failures are addressed. The full suite was not repeated after these
  narrow fixes, following the requested one-baseline/one-final-full testing policy.
- `python -m compileall -q rpg` and `git diff --check`: passed.

Adapted older tests now supply Telegram message IDs, current persisted location/level
and real callback tokens instead of trusting supplied UI snapshots or patching the
former gathering implementation location. Recheck command, from `rpg/`:

```text
python -m pytest tests/test_alpha_release_gate_pr3p.py tests/test_open_world_route_objectives_pr3n.py tests/test_location_live_pvp_view.py tests/test_playable_alpha_v1.py tests/test_alpha_transactions_v1.py tests/test_quest_board_phase1.py -q
```

Limits: no live Telegram account smoke test, production load test, or claim that every
build/party is balanced. Acceptance uses a sword with ordinary strength/vitality;
all three kits use existing weapon identities. No new corpse world objects, quality,
tools, talents, specialization, crafting market or deeper regional chapter is activated.
Receipt history grows with gathering usage and needs a future retention policy that
preserves the intended replay window. Balance playtesting and the existing partial
victory-reward failure boundary are the next review topics.
