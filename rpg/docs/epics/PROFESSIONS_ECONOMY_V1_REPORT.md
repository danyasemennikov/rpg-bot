# Professions & Economy V1

- Status: Draft PR candidate; not merged and not deployed
- Contract: PEV1-1 Stage 3
- Frozen base: `27347ece2b17108a1aed1f6eb01f2a395480e6c9`
- Candidate branch: `codex/professions-economy-v1`
- Tested code commit: `95f5d2159d31663cc36165af3ccd1caa28636e68`
- Draft PR: [#233](https://github.com/danyasemennikov/rpg-bot/pull/233)

## Delivered candidate

The candidate expands the playable economy to five gathering and seven crafting
professions, all capped at level 20. It defines one closed 63-recipe catalogue,
28 mandatory materials, permanent recipe knowledge, explicit learning prices and
crafting ceilings, and one runtime authority for environmental sources. The eight
new recovery outputs are stackable `potion` items; heal/mana values live only in
`stat_bonus_json`, while food metadata remains descriptive.

The migration `professions_economy_v1` rebuilds the crafting-profession constraint
to exactly seven keys without changing retained rows, creates permanent knowledge
and durable economic-result receipt tables, grants only the four frozen grandfathered
recipes to existing players, and grants all 17 starters through normal new-player
initialization. The marker is written only after row-preservation and foreign-key
checks succeed.

Gather, settlement-authorized harvest, learning, crafting, stack sale, crystal
exchange, inn rest, direct gift, and out-of-battle consumable use use locked mutation
boundaries and durable language-neutral results. Valid consumed business rejections
are durable; stale or foreign intents do not authorize receipts. Lost responses
recover the committed result without repeating charges, grants, XP, objectives, or
generated gear rolls.

The professions journal is available from the chapter journal and craftsmen guild,
with six-row content pages, five-row harvest/receipt pages, eight-row inventory/sale
pages, short server-side callbacks, and parallel Russian, English, and Spanish copy.

## Acceptance boundary

Focused catalog, migration, progression, source, transaction, hunting, UI, and
neighbor-compatibility tests accompany the candidate. The shared production history
uses normal registration, travel, deterministic gathering rolls, real PvE reward
settlements, owner harvesting, legitimate material sales, paid/free learning,
crafting, equipping, enhancement, and receipt replay. Fixture-only migration and
adversarial checks are labeled separately.

Machine-readable evidence is recorded in
[`../evidence/professions_economy_v1.json`](../evidence/professions_economy_v1.json).
The final production history passed in 350.49 seconds and covered all 11 journey IDs,
28 mandatory materials, 63 recipes, and all 12 professions at level 20. The focused
PEV1/neighbor matrix passed 138 tests; post-broad compatibility repairs passed 62
tests plus 76 subtests, and the isolated real battle-consumable proof passed.

The single broad run collected 1,755 tests at `f3b3b42`: 1,750 passed and five
failed. The failures were repaired with narrow legacy-alias, frozen-policy expectation,
and acceptance-harness changes, then rerun focused. Per the contract's test budget,
the broad suite was not repeated because shared runtime infrastructure was not
materially redesigned. Merge and deployment remain explicitly outside this delivery.

## Deferred and risks

The contract's explicit deferred items remain deferred. Durable receipts intentionally
grow without pruning. Long production-history coverage reflects the frozen profession
curve and is materially slower than focused policy tests. No teleport, trade/escrow,
gold transfer, broader structured PvP, or unrelated content expansion is introduced.
The remaining validation risk is that the single local broad run predates the narrow
repair commit; every observed failure has a green focused rerun, but a second local
broad run was intentionally not performed.
