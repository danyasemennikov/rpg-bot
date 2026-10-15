# Epic I candidate implementation

This is an unmerged Draft PR record. `PROJECT_STATE_CURRENT.md` remains the
authority for confirmed merged state. Owner Issue #241 approves M1/M2/D4/M3;
the byte-preserved v0.2 contract and V2.2 sources are in `sources/`.

## Runtime owners

- Existing crafting/gathering tables hold the sole writable P/XP/registration
  state; `profession_state.py` owns progression. P15/P30 discard overflow.
- `profession_catalog_v3.json` holds 153 recipes; resources hold 45 materials;
  20 manuals authorize tiers. Registration gives explicit learning vouchers.
- `crafting_runtime.py` owns connection-scoped craft operations and one-commit
  batches. Jobs/exams own inputs and outputs through escrow, never inventory.
- `profession_guild.py` owns immutable 4/15-stage plans, explicit deadlines,
  paid work, processing, cancellation and claim. Existing activity projection
  includes active/claim-ready guild work and all starters serialize in SQLite.
- `profession_exams.py` owns twelve registered exams, A/B/sample provenance,
  P16 confirmation and one free Tier II knowledge choice.
- `equip_requirements.py` resolves actual T and permanent base attributes for
  every equip writer, advancement, reset and retained snapshot gear.
- `profession_consumables.py` owns pending food/preparation slots and immutable
  initial encounter bindings. Existing actors own runtime counters/effects.
  PvE/PvP roster locks bind preparation; previews do not consume it. PvE cleanse
  reserves an item in the durable order and spends one normal opportunity.
- Profession, guild, recipe, inventory and combat UI use RU/EN/ES strings.

Exact fresh DDL and writer boundaries are in `OWNER_DDL_MAP.md` and
`game/profession_epic_i.sql`. Old test database layouts are unsupported.

## Reproduce targeted evidence

Run from `rpg` with the repository Python dependencies installed:

```powershell
$epicTests = (Get-ChildItem tests/test_epic_i*.py).FullName
python -m pytest -q $epicTests tests/test_tier_advancement_phase8.py tests/test_equipment_runtime_integration.py tests/test_pxe1_combat_order_replay.py tests/test_pxe1_partial_timeout_recovery.py tests/test_pxe1_pve_world_tick.py tests/test_pxe1_pvp_group_runtime.py tests/test_pxe1_combat_ui.py tests/test_pxe1_travel.py --junitxml=epic_i_evidence.xml -o junit_family=legacy
```

The autouse fixture redirects every test to a disposable clean SQLite path.
The process-crash test passes this path explicitly to a short-lived Python
worker, which calls `os._exit` before commit. No Telegram poller is started.

`test_epic_i_earned_journeys.py` starts C1/gold0, registers one profession,
commits every earned stage, performs the exam, and reaches P30 with character
XP0. Its clock is simulated. JUnit properties retain elapsed policy time,
jobs, stages and earned gold. No admin resources are injected after startup.

`test_epic_i_recipe_execution.py` executes each of 153 recipes on an independent
funded fixture, checks concrete output and post-commit replay, and applies new
consumables. These fixtures are catalog/integration evidence, not earned paths.

`test_epic_i_acceptance_boundaries.py` executes all 24 milestone jobs, all 45
NPC supply/processing sources and 20 manuals. It verifies one-vs-N batches,
observer rollback, concurrent replay, crash/restart and actual travel/guild
activity arbitration. JUnit properties record policy throughput and one
deterministic field sample. These are simulated measurements, not wall-clock
balance or usability acceptance.

Consumable tests execute the current inventory and combat callback handlers
with mocked Telegram transport, actual SQLite transactions, shared evaluators
and restart. They cover replacement confirmation lost-response recovery, a
prior ally cleansing first, preparation binding, expiry and exit caps.

The final report must name its exact tested Git HEAD and independent review
SHA. Static manifest counts, pytest success, simulated paths and real Telegram
acceptance are separate claims. This candidate does not claim live Telegram,
mobile or wall-clock balance validation, merge or deployment.
