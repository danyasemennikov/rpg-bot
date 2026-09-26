# Professions & Economy V1

- Status: Draft PR candidate; not merged and not deployed
- Contract: PEV1-1 Stage 3
- Frozen base: `27347ece2b17108a1aed1f6eb01f2a395480e6c9` (merged PR #232)
- Candidate branch: `codex/professions-economy-v1`
- Tested code commit: `e29e4a368de625f6fb221871761f438f5a617f2c`
- Earlier documentation-only commits: `52a854e` and `c9f6a4c`.
- The commit containing this refreshed report/evidence is the only post-tested-code
  commit and is documentation-only. Its exact pushed SHA is recorded in the Draft PR
  body and final handoff because a Git commit cannot embed its own ID.
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
receipt requests beyond the end clamp to the last page. Harvest eligibility is filtered
and paginated as five encounters before their choices are expanded. Choices deduplicate
by output item and retain the first stable eligible unit identity across mixed species.

Craft replay now recovers the matching committed owner/action/request receipt before
requiring the old preview token to survive a later preview refresh. Recipe details show
the exact positive XP award from the progression authority, including clipping near the
training ceiling, while preserving ceiling and zero-XP feedback.

The journal exposes localized profession milestones, recipe state and learning cost,
owned/required ingredients, outputs, tier/rarity/secondary policy, recovery, sale and
XP ceilings. Durable results show consumed/granted items, instance IDs, exact rolls,
progression and recovery, with a Craft Again path. Known PEV1 content and errors have
parallel Russian, English and Spanish copy without internal IDs, JSON, policy tokens,
generic known-content descriptions, or Russian fallback in English/Spanish. Historical
gather recovery uses the profession localization namespace that owns its status key.

## Executable acceptance evidence

The shared production history no longer claims completion through enumerated journey
IDs. It asserts named outcomes derived from real actions: the Aster–Elmor chapter,
each profession chain, hunting/consumers, learning, conservation/receipts, gear,
localization, and regional acquisition. Its final narrow-rereview run passed in
361.08 seconds and proved:

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
as production acquisition. They cover the frozen baseline, rollback/restart, preservation
of a prepared settlement and its successful recovery through the existing settlement
path after restart, concurrent craft/sale/gift conservation, and localized missing,
locked, and stale results. Representative ru/en/es navigation is also exercised through
the actual profession callback handler rather than renderer functions alone.

At tested code commit `e29e4a3`, the narrow repair matrix passed 23 tests in 6.44
seconds, the affected legacy regression matrix passed 15 tests in 3.91 seconds, and
the migration module passed 5 tests in 1.34 seconds. The four short original broad
failures each passed through their own executable command; the fifth is the green
361.08-second shared production history. Its first repair-time rerun exposed a flaky
underfunded troll-combat reserve; the evidence fixture now fixes the combat seed and
earns/crafts sufficient healing stock through production paths before the green rerun.
Machine-readable commands, node IDs, original reasons, exact repairs, results, and
tested commit are recorded in
[`../evidence/professions_economy_v1.json`](../evidence/professions_economy_v1.json).

## Astra repair disposition

Findings 1–11 are resolved: fail-closed migration, gather replay/travel revision,
durable business rejections, receipt pagination, harvest pagination/deduplication,
profession UX/results, complete localization, executable acceptance/traceability,
exact mastery regression assertions, PR232 documentation reconciliation, and frozen
environmental row ordering.

The subsequent narrow Astra findings are also resolved: craft replay after preview
replacement; encounter-first harvest pagination with output-level deduplication;
explicit known-content descriptions and historical gather localization; executable
prepared-settlement recovery and callback localization evidence; oversized receipt-page
clamping; exact positive/clipped recipe XP preview; and accurate current-state wording.

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
