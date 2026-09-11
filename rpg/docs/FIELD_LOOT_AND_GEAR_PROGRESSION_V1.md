# Field Loot and Gear Progression V1

Status: implemented on the Epic review branch; not confirmed merged behavior until the PR lands.

## Player loop

The field catalogue is available through the existing inventory, shop, journal, and craftsmen-guild flows. A player can inspect a template, compare its real runtime channels, select one persistent equipment goal, see its actual vendors and route pools, buy a deterministic tier-1 common copy, or chase generated instances in ordinary open-world combat.

Equipment goals are navigation preferences only. They never change drop chance, rarity, affixes, counters, or settlement output, and remain selected after the matching template is acquired.

Every instance mutation uses the existing persisted action-token rail. Previewed equip, unequip, enhancement, advancement, sale, purchase, and shard exchange actions are checked again under a SQLite write lock. Ownership, current location and travel revision, combat/PvP state, instance revision, player gear revision, slot, requirements, balances, materials, and the server-calculated cost reference are authoritative. A stale or duplicated action has no economic effect.

## Frozen catalogue and acquisition

All field items are level-1 templates. Field vendor output is always tier 1, common, +0, with no secondary rolls. Field gear always sells for 5 gold and never refunds upgrade materials.

| Family or slot group | Frozen base values | Vendor price |
|---|---|---:|
| One-handed sword | 11–16 physical, Strength 3, weight 2 | 45 |
| Two-handed sword | 15–22 physical, Strength 3, weight 4 | 45 |
| Two-handed axe | 16–24 physical, Strength 3, weight 4 | 45 |
| Daggers | 8–13 physical, Agility 3, weight 2 | 45 |
| Bow | 9–15 physical, Agility 3, weight 2 | 45 |
| Magic staff | 9–14 magic, Intuition 3, weight 3 | 45 |
| Wand | 8–12 magic, Intuition 3, weight 2 | 45 |
| Holy staff | 8–13 holy, Wisdom 3, weight 3 | 45 |
| Holy rod | 8–12 holy, Wisdom 3, weight 2 | 45 |
| Tome | 7–11 magic, Wisdom 3, weight 2 | 45 |
| Heavy armor | base defense 8, max HP 12, slot coefficients below | 20/60/40/20/20 |
| Medium armor | base defense 5, accuracy 2, evasion 1, slot coefficients below | 20/60/40/20/20 |
| Light armor | base defense 3, max mana 12, magic defense 2, slot coefficients below | 20/60/40/20/20 |
| Shield | defense 4, max HP 8, block 2 | 60 |
| Focus | defense 1, max mana 8, magic power 2 | 60 |
| Censer | defense 1, max mana 8, healing power 2 | 60 |
| Precision ring | accuracy 2, agility 1 | 60 |
| Guard ring | max HP 8, vitality 1 | 60 |
| Mind ring | max mana 8, intuition 1 | 60 |
| Prayer amulet | wisdom 1, healing power 2 | 80 |

Armor slot coefficients are helmet 0.4, chest 1.0, legs 0.6, boots 0.3, and gloves 0.3. Derived integer values use the runtime's existing rounding behavior. These 10 weapons, 15 armor pieces, three offhands, and four accessories form the exact 32-item catalogue.

All 32 templates are sold at `capital_city`, `hub_westwild`, and `hub_frostspine`; existing vendor stock remains present. The five curated route manifests differ:

| Route | Curated identity |
|---|---|
| Westwild | daggers, bow, medium armor, precision ring |
| Frostspine | swords, two-handed axe, heavy armor, shield, guard ring |
| Ashen Ruins | magic staff, wand, light armor, focus, mind ring |
| Mireveil | holy staff, tome, light armor, censer, prayer amulet |
| Sunscar | holy rod, bow, two-handed sword, medium armor, shield, precision ring |

An eligible drop selects from its regional pool 80% of the time and from the full catalogue 20% of the time. Starter stub routes use the full catalogue. The source UI is derived from these manifests and real world placement; it does not advertise unconfigured bosses or rares and never unlocks or teleports to an undiscovered location.

## Drop policy and guarantee

New encounters persist policy `field_loot_v1` and a reward seed when created. Active encounters created before this migration retain `legacy_v0` and finish through the new transactional settlement using their old loot table semantics.

| Spawn profile | Gear chance per defeated unit | Dry-streak increment | Generated rarity weights |
|---|---:|---:|---|
| normal | 8% | 1 | common 70%, uncommon 28%, rare 2% |
| elite | 35% | 3 | uncommon 70%, rare 29.5%, epic 0.5% |

The counter is personal and route-specific, persisted in the range 0–11. Any successful field gear roll resets it. When a failure would reach 12, that unit grants one guaranteed uncommon item with one generated secondary and resets the counter. Common, uncommon, rare, and epic items have exactly 0, 1, 2, and 3 secondaries from the existing runtime allowlist. This policy never generates legendary or unique items and never scales output from player level.

Non-gear loot, existing XP/gold curves, per-unit pack rewards, contract kill progress, cooldown reset, spawn consequences, and the owner's historical +10 mastery-per-encounter behavior are retained. Defeated participants receive no victory rewards; surviving participants receive personal rewards without a new split formula. The +10 owner mastery award is omitted when the owner is defeated.

## Equipment and progression behavior

The equipment aggregator is instance-first per slot, with legacy fallback only when that slot has no equipped instance. Resolved base defense from equipped armor or offhand is included in the physical-defense equipment channel exactly once. Magic defense remains separate. Tier and enhancement use the existing resolvers and do not write resolved values back to templates or secondary rolls.

All five armor slots, weapon, offhand, two rings, and amulet contribute at runtime. Ring comparisons explicitly target ring 1 or ring 2. Comparison reports damage range, physical and magic defense, HP/MP caps, attributes, accuracy, evasion, block, magic power, and healing power as signed deltas; it does not claim that mixed tradeoffs are simply better.

Tier advancement uses the live tier stops 5, 10, 15, and 20 and the existing cost resolver. It preserves instance ID, base template, rarity, exact rolls, enhancement, durability, and equipped slot. Enhancement retains the existing +0…+15 chance/cost table and never rerolls affixes. Cap changes clamp current HP/MP to the new effective cap without healing.

The post-Homecoming guild bridge exchanges 10 enhancement shards plus 25 gold for one enhancement crystal. It grants no crafting XP and advances no craft or sale objective.

Weapon mastery and skill lookup normalize each field item through its canonical `weapon_profile`; field item IDs do not create parallel mastery families. The touched skill-upgrade path now verifies that the skill belongs to the selected family and spends its point in the same transaction.

## Durable victory settlement

Victory processing uses two database transactions and contains no Telegram I/O:

1. T1 validates the persisted terminal victory, freezes the location/route, source units, eligible recipients, policy/seed, XP, gold, non-gear grants, exact gear specs and affixes, counter transitions, contract events, and mastery award. It persists the terminal snapshot and plan and marks the encounter `resolving_victory`.
2. T2 locks the prepared row, applies every recipient's progression and grants, counter, contract progress, mastery, cooldown reset, encounter/participant finalization, and spawn consequences, then stores the display result and marks the settlement `applied` in one commit.

One encounter has one settlement row. Delivery reads the persisted concrete plan and never rerolls. A retry of an applied settlement returns its stored result. Failure before T1 commit leaves the active encounter retryable. Failure after T1 leaves a prepared plan with no rewards. Any exception inside T2 rolls back XP, gold, stackables, instances, counters, contracts, mastery, locks, and finalization together. Failure after T2 commit may lose only the Telegram response; recent receipts expose the stored result.

Startup and `/start`, `/location`, and `/journal` perform bounded recovery of prepared settlements. Recovering one encounter does not clear another active PvE or PvP engagement. Recent rewards display the latest 20 player receipts, including the actual instances and whether the guarantee fired.

## Additive migration and legacy review

Migration creates or extends:

- `pve_reward_settlements`, including schema/policy versions and `prepared`, `applied`, or `legacy_review` state;
- `player_gear_progress` and `player_gear_goals`;
- `gear_mutation_receipts`;
- `players.gear_revision` and `gear_instances.revision`, both defaulting to 0;
- nullable instance settlement provenance and source metadata;
- encounter reward-policy and seed metadata.

The migration is idempotent. It does not recreate existing templates or instances, reroll stats, alter enhancement/durability/ownership, infer historical dry streaks, or select a goal. Startup static reconciliation inserts missing field templates without mass-replacing existing rows. Unknown historical item rows remain readable through the database fallback.

A pre-V1 encounter already stuck at `resolving_victory` without a plan is fundamentally ambiguous: the database cannot prove which rewards were delivered. Startup therefore creates a `legacy_review` record with the available encounter, battle, and mob evidence, excludes it from automatic settlement, and releases only its stale PvE lock when no other active engagement exists. `list_legacy_review_reports(player_id)` returns a bounded owner-readable evidence report. No automatic replay or compensation occurs; compensation requires a separate owner decision.

## Verification evidence

Focused coverage is in `tests/test_itemization_regional_loot_v1.py` plus the existing equipment, gear-transition, group/solo PvE, world encounter, mastery, tier-advancement, and action-token suites. It covers frozen values, localization parity, real source manifests, distribution constants, exact guarantee transitions, affix rules, vendor acquisition for all ten families, numeric starter-target diagnostics, Telegram limits, comparison, equipment aggregation, stale/foreign/busy mutations, atomic advancement/enhancement/sale/exchange, T1/T2 recovery and idempotency, every required T2 failure point, concurrent delivery, legacy migration/review, and safe legacy item display.

The ten-family diagnostic allocates the same 12 starting points (7 in the weapon's primary attribute and 1 in each other attribute) and runs ten deterministic fights per family against `forest_wolf`; every family wins all ten seeds. This is isolated numeric evidence, not a substitute for production handler journeys.

## Known risks and review focus

- Correctly activating legacy base defense increases survivability, and five contributing armor slots increase total possible defense.
- Personal group loot retains the existing multiplicative group economy, while guarantees may incentivize easy-kill optimization.
- Whole-encounter T2 holds the SQLite writer for more work than the legacy per-helper commits; contention is serialized and recovery is bounded, but production latency should be observed.
- Historical mastery aliases are normalized on access but are not merged or refunded in this Epic.
- The old magic staff remains a known numeric outlier outside this frozen catalogue.
- Live-account Telegram smoke remains recommended before an external playtest. Automated handler journeys and database tests do not prove bot-token/network delivery.

Independent review should concentrate on transaction boundaries and recovery under real historical databases, group defeat/mastery eligibility, spawn finalization, the physical-defense channel in both PvE and PvP snapshots, route/source discovery gates, and token invalidation across travel and competing callbacks.
