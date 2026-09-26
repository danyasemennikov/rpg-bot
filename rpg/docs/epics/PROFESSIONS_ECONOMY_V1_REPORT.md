# Professions & Economy V1

- Status: Draft PR candidate; not merged and not deployed
- Contract: PEV1-1 Stage 3
- Frozen base: `27347ece2b17108a1aed1f6eb01f2a395480e6c9` (merged PR #232)
- Candidate branch: `codex/professions-economy-v1`
- Tested code commit: `2c552f8e8d5829b19b37fe50abffab2add2461c0`
- Draft PR: [#233](https://github.com/danyasemennikov/rpg-bot/pull/233)

## Delivered candidate

The candidate expands the playable economy to five gathering and seven crafting
professions, all capped at level 20. It defines one closed 63-recipe catalogue,
28 mandatory materials, permanent recipe knowledge, explicit learning prices and
crafting ceilings, and one runtime authority for environmental sources. The eight
new recovery outputs reuse the existing `potion` runtime: six mana-bearing or mixed
outputs are proved through battle-use, while both HP-only outputs are proved through
out-of-battle inventory-use.

The `professions_economy_v1` migration now recognizes only the exact frozen three-key
baseline or exact seven-key target structure. It verifies column order and constraints,
the primary-key index, foreign key, absence of unexpected triggers/dependencies, and
the marker/schema relationship. Incompatible structures and unexpected temp tables
fail closed. Injected failure after the rebuild rolls back DDL, data, and marker state.

Gather recovery now precedes mutable location/battle checks, while fresh requests bind
canonical location and travel revision. Valid consumed business rejections for the
economy mutations commit durable zero-mutation results; stale or foreign authorization
does not. Receipt and harvest history use true five-row pages with one-row lookahead;
harvest eligibility is filtered before pagination and stable unit identity controls
deduplication.

The journal exposes localized profession milestones, recipe state and learning cost,
owned/required ingredients, outputs, tier/rarity/secondary policy, recovery, sale and
XP ceilings. Durable results show consumed/granted items, instance IDs, exact rolls,
progression and recovery, with a Craft Again path. Known PEV1 content and errors have
parallel Russian, English and Spanish copy without internal IDs, JSON, policy tokens,
or Russian fallback in English/Spanish.

## Executable acceptance evidence

The shared production history no longer claims completion through enumerated journey
IDs. It asserts named outcomes derived from real actions: the Aster–Elmor chapter,
each profession chain, hunting/consumers, learning, conservation/receipts, gear,
localization, and regional acquisition. It passed in 361.41 seconds and proved:

- all 28 mandatory inputs acquired through real delivering actions;
- all 63 recipes crafted from earned inputs;
- all 12 professions at level 20;
- real source acquisition in Westwild, Frostspine, Ashen Ruins, Mireveil, and Sunscar;
- a crafted uncommon T5 sword compared/equipped, enhanced and advanced to T10 while
  preserving instance ID, its one secondary roll, and provenance;
- all eight new recovery outputs consumed through the existing battle/inventory paths;
- representative overview → source → learning → craft → result → recovery rendering
  in ru/en/es.

Migration and adversarial tests are explicitly fixture-labelled and are not presented
as production acquisition. They cover the frozen baseline, rollback/restart, prepared
settlement recovery, concurrent craft/sale/gift conservation, and localized missing,
locked, and stale results.

At tested code commit `2c552f8`, the consolidated repair matrix passed 30 tests in
7.90 seconds. The exact four short nodes from the original broad failures passed in
1.03 seconds; the fifth node is the green 361.41-second shared production history.
Machine-readable commands, node IDs, original reasons, exact repairs, results, and
tested commit are recorded in
[`../evidence/professions_economy_v1.json`](../evidence/professions_economy_v1.json).

## Astra repair disposition

Findings 1–11 are resolved: fail-closed migration, gather replay/travel revision,
durable business rejections, receipt pagination, harvest pagination/deduplication,
profession UX/results, complete localization, executable acceptance/traceability,
exact mastery regression assertions, PR232 documentation reconciliation, and frozen
environmental row ordering.

PR232 Documentation Architecture & Consolidation V1 is merged at the frozen base.
Its stale in-progress roadmap entry was removed. PR233 remains an unmerged Draft.
Repository merge state does not establish deployment or live operation.

## Broad suite and remaining risks

The single broad run at `f3b3b42` collected 1,755 tests: 1,750 passed and five failed
in 1131.51 seconds. Every observed failure now has an exact green focused rerun.
A second broad run was not performed because Astra explicitly allowed focused
verification for this bounded repair packet and no shared infrastructure was
materially redesigned.

The contract's explicit deferred items remain deferred. Durable receipts intentionally
grow without pruning. Free repeated gathering throughput was not balance-measured.
There are no contract deviations; merge, ready-for-review transition, and deployment
remain outside this repair pass.
