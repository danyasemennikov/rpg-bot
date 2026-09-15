# Character Builds & Combat Identity V1

## Status and authority

This document describes the implementation in the current Epic branch for review. It is not a claim that the branch has merged. The confirmed merged baseline remains the baseline recorded in `PROJECT_STATE_CURRENT.md` until the Draft PR is reviewed and merged.

The frozen Astra implementation contract is the product and architecture authority. Runtime constants in `game/build_contract.py`, the shared evaluator in `game/combat_identity.py`, and the checked evidence artifact in `docs/evidence/character_builds_combat_identity_v1.json` are the executable review surfaces.

- Baseline: `c8768626e388babfed09adac83ddaf23f0daee71`
- Integrated runtime/evidence checkpoint: `60225c2a1e605ce604c09da7f28c24188d08cb62`
- Rules version: `character_builds_combat_identity_v1`
- Scope: 10 weapon families, 20 branches, 100 canonical branch skills, plus universal Power Strike

## Product statement

Characters have no rigid class. Combat identity comes from the equipped weapon family, allocated attributes, learned branch ranks, and resolved equipment. Each weapon family has two distinct five-skill branches. Mastery earns family-local points, weapon switching preserves every family ledger, and free safe-hub resets make experimentation reversible.

PvE uses persistent participant and enemy state, real ally targeting, finite support effects, explicit enemy profiles, mixed formations, durable orders, and restart-safe side results. Supported V1 PvP uses the same actor snapshot and action evaluator for normal attack, Guard, Power Strike, Quick Shot, Fireball, and Smite while preserving the existing outer engagement, crime, loss, and loot rules.

`/build` exposes current identity, effective attributes, family mastery, branch progress, skill previews, reset and redistribution flows, equipment comparison, and the deliberately bounded PvP scope in Russian, English, and Spanish.

## Runtime and persistence map

| Concern | Canonical implementation |
|---|---|
| Catalogue, ranks, unlocks, targets, costs | `game/build_contract.py` |
| Resolved player state | `game/actor_snapshot.py`, `game/actor_state.py` |
| Shared action/effect evaluator | `game/combat_identity.py` |
| Durable orders and side results | `game/combat_orders.py`, `game/live_combat_runtime.py` |
| Persistent PvE participants/enemies | `game/pve_live.py`, `handlers/battle.py` |
| Enemy profiles and mixed rosters | `game/enemy_profiles.py`, `game/open_world_pack_balance.py` |
| Mastery, receipts, resets, migration | `game/weapon_mastery.py`, `game/build_progression.py` |
| Limited PvP adapter | `game/pvp_live.py` |
| Production-aligned simulation | `game/combat_identity_simulation.py` |
| Telegram build UX and locale boundary | `handlers/build.py`, `handlers/battle.py`, `locales/` |

The database changes are additive. Existing player, item, gear, encounter, settlement, PvP, profession, chapter, discovery, and economy records remain authoritative. Build and gear revisions invalidate stale peaceful previews. Combat orders and side results are uniquely scoped by encounter, revision, and actor.

## Deployment and migration

Production rollout is an offline migration boundary:

1. Stop public bot traffic and take a consistent SQLite backup, including any active WAL state. The backup is the rollback boundary.
2. From `rpg`, run a local dry run against a restored production copy:

   ```powershell
   ..\.venv\Scripts\python.exe -c "from game.build_progression import migrate_character_builds_v1; print(migrate_character_builds_v1(dry_run=True))"
   ```

3. Resolve any `legacy_review` reward records through the existing owner-review process. Do not fabricate rewards or force those players through a partial build migration.
4. Start the application normally. `bot.initialize_runtime()` initializes additive schema, reviews ambiguous legacy victories, recovers prepared settlements, and then calls the idempotent V1 migration before handlers accept traffic.
5. Inspect the post-start audit:

   ```powershell
   ..\.venv\Scripts\python.exe -c "from game.build_progression import build_migration_audit; print(build_migration_audit())"
   ```

6. Verify that the migration is active, invariant-failure lists are empty, and only expected owner-review records remain blocked before reopening traffic.

The migration archives original attributes, mastery, skills, and cooldowns; uses greatest alias/canonical mastery evidence rather than adding duplicates; converts the old mastery fraction to the V1 curve; refunds the legal `mastery + 1` family budget; retires old skills; grants universal rank-1 Power Strike; preserves inventory, gear instances, upgrades, currencies, professions, chapter and discovery state; and records a localized one-shot notice. Nonterminal old-rules PvE/PvP is cancelled with explicit `rules_updated` receipts and no invented outcome. Re-running migration cannot refund or cancel twice.

An old executable must not be started against an activated V1 database. Roll back by restoring the complete pre-rollout backup, not by deleting additive rows selectively.

## Coverage index: all canonical skills

Every row below is shape-checked by `test_character_builds_v1_contract.py`, executed through the shared evaluator by `test_character_builds_v1_combat_core.py` and the production-aligned simulation, reached through its ordinary branch journey in `test_character_builds_v1_journeys.py`, and included in the checked 200-seed accessibility/role evidence. Specialized support, mixed-roster, durability, gear, and PvP tests add the integration coverage named after this table.

| Family / branch | Identity | Canonical skill IDs |
|---|---|---|
| Sword 1H A | Guardian | `sword_rush`, `defensive_stance`, `shield_bash`, `parry`, `counter` |
| Sword 1H B | Vanguard | `driving_slash`, `expose_guard`, `press_the_line`, `punishing_cut`, `vanguard_surge` |
| Sword 2H A | Executioner | `heavy_swing`, `armor_split`, `executioners_focus`, `cleave_through`, `executioners_stroke` |
| Sword 2H B | Blademaster | `battle_stance`, `twin_cut`, `riposte_step`, `flowing_combo`, `masters_sequence` |
| Axe 2H A | Berserker | `rage_call`, `savage_chop`, `blooded_resolve`, `frenzy_chain`, `last_roar` |
| Axe 2H B | Ravager | `bleeding_cut`, `sunder_armor`, `brutal_overhead`, `reopen_wounds`, `ravage` |
| Daggers A | Venom | `envenom_blades`, `toxic_cut`, `crippling_venom`, `widows_kiss`, `rupture_toxins` |
| Daggers B | Shadow | `smoke_bomb`, `quick_slice`, `feint_step`, `backstab`, `shadow_chain` |
| Bow A | Sniper | `hunters_mark`, `aimed_shot`, `steady_aim`, `piercing_arrow`, `deadeye` |
| Bow B | Ranger | `quick_shot`, `hamstring_arrow`, `reposition`, `volley_step`, `rain_of_barbs` |
| Magic Staff A | Destruction | `fireball`, `arcane_surge`, `flame_wave`, `arcane_lance`, `cataclysm` |
| Magic Staff B | Control | `frost_bolt`, `ice_shackles`, `mana_shield`, `shatter`, `absolute_zero` |
| Wand A | Arcanist | `arcane_bolt`, `spell_echo`, `quick_channel`, `overload`, `arcane_barrage` |
| Wand B | Duelist | `dueling_ward`, `hex_bolt`, `mana_feint`, `counterpulse`, `duel_arc` |
| Holy Staff A | Healer | `heal`, `regeneration`, `cleanse`, `blessing`, `resurrection` |
| Holy Staff B | Dawn | `smite`, `judgment_mark`, `radiant_ward`, `sanctified_burst`, `halo_of_dawn` |
| Holy Rod A | Protector | `sacred_shield`, `mend_self`, `aura_of_resolve`, `aegis_strike`, `guardian_light` |
| Holy Rod B | Judgment | `judgment`, `radiant_strike`, `rod_consecration`, `punish_the_wicked`, `final_verdict` |
| Tome A | Enchanter | `arcane_shield`, `weaken`, `insight`, `dispel_script`, `grand_enchantment` |
| Tome B | Synthesis | `hybrid_missile`, `borrowed_flame`, `borrowed_grace`, `synthesis`, `forbidden_thesis` |

Universal Power Strike is covered separately for all equipped families and unarmed actors. The PvP allowlist entries `quick_shot`, `fireball`, and `smite` are exercised alongside it in the earned PvP journey.

## Coverage index: frozen G–I rules

| Contract area | Primary correctness and production evidence |
|---|---|
| G1 identity, attributes, attack/heal power and caps | `test_character_builds_v1_contract.py`, `test_character_builds_v1_combat_core.py`, `test_character_builds_v1_experimentation.py`, `test_character_builds_v1_gear_journey.py` |
| G2 hit, crit, mitigation, block, barrier and multihit order | `test_character_builds_v1_combat_core.py`, extreme probes in `test_character_builds_v1_simulation.py` |
| G3 opportunity timing, cooldowns, mana, effects and setup consumption | `test_character_builds_v1_combat_core.py`, `test_character_builds_v1_durability.py`, `test_character_builds_v1_group_journeys.py` |
| G4 resolved equipment, requirements and PR230 preservation | `test_character_builds_v1_gear_journey.py`, `test_character_builds_v1_experimentation.py`, `test_itemization_fix_packet_pr230.py`, `test_itemization_regional_loot_v1.py` |
| G5 mastery, ranks, family ledgers and safe experimentation | `test_character_builds_v1_journeys.py`, `test_character_builds_v1_migration.py`, `test_character_builds_v1_experimentation.py` |
| G6 explicit enemies, AI, real source identity and mixed encounters | `test_character_builds_v1_mixed_encounters.py`, `test_character_builds_v1_group_journeys.py`, `test_character_builds_v1_simulation.py` |
| G7 truthful `/build`, target selection and ru/en/es output | `test_character_builds_v1_ui.py`, `test_character_builds_v1_language_journeys.py` |
| H1 canonical actor/participant ownership | `test_character_builds_v1_combat_core.py`, `test_character_builds_v1_group_journeys.py`, `test_character_builds_v1_gear_journey.py` |
| H2 one action evaluator across PvE, PvP and simulation | `test_character_builds_v1_combat_core.py`, `test_character_builds_v1_durability.py`, `test_character_builds_v1_pvp_journey.py`, `test_character_builds_v1_simulation.py` |
| H3 supported PvP adapter and unchanged outer policy | `test_character_builds_v1_pvp_journey.py`, `test_pvp_live_flow_v1.py`, PvP cases in `test_character_builds_v1_durability.py` |
| H4 integration map | The complete Character Builds V1 test set plus PR229/PR230 regression suites |
| I1 additive persistence and invariants | `test_character_builds_v1_migration.py`, schema/invariant cases in `test_character_builds_v1_experimentation.py` |
| I2 initial migration and audit | `test_character_builds_v1_migration.py`, migration notice path in `test_character_builds_v1_language_journeys.py` |
| I3 transactional peaceful mutations | `test_character_builds_v1_migration.py`, `test_character_builds_v1_experimentation.py`, stale/error routes in `test_character_builds_v1_language_journeys.py` |
| I4 durable combat, restart and settlement handoff | `test_character_builds_v1_durability.py`, `test_character_builds_v1_group_journeys.py`, `test_character_builds_v1_pvp_journey.py`, `test_world_pve_encounter_foundation.py` |

## Restart and transaction evidence

- PvE UI intents are opaque, deadline-bound and single-use. Identical duplicate submissions are acknowledged; conflicting second orders fail closed.
- Timeout and manual submissions share the same durable uniqueness rail. Locked side results persist complete actor/enemy state before reward settlement starts.
- Runtime loss after a committed order reconstructs the pending side; an already applied side replays the stored result without rerolling or double-spending mana/cooldown/effects.
- Enemy-side periodic defeat persists terminal projection before T1 settlement.
- T1 freezes each eligible survivor's snapshotted family and explicit mastery grant. T2 retry applies once and cannot re-derive from later gear.
- Group owner and joiner use the same persisted snapshot/state authority. Late/reversed join order and roster reconstruction preserve monotonic turn revisions.
- PvP recovery preserves the committed Fireball order, Burn, cost and cooldown; finalization writes exactly one ordinary PvP log while leaving the outer frontier crime policy unchanged.
- Build learn/reset/redistribution receipts are idempotent. Stale level, gear, travel, old-message and battle-start races cannot overwrite current authority.
- Migration dry run rolls back fully; canonical/alias duplication uses greatest evidence; rerun is idempotent; invalid historic records remain owner-auditable.

## Ordinary production journeys

- All 20 branches start with ordinary registration/stat allocation, buy the real 45-gold family weapon, equip its real instance, earn mastery and rewards through live Westwild fights, learn through production receipts, reach M8, and use the capstone. Guardian, Venom, Healer and Synthesis continue to M14 and rank 3.
- The first chapter is replayed with V1 identities through production handlers and settlement.
- Earned owner/joiner group builds use real content, support recipients, mixed sources, enemy-side rotation and reversed join order.
- The gear journey earns a real uncommon field weapon and shard, inspects/compares/equips it, pays the real enhancement cost, and observes its rolled secondary and `+1` result in owner, joiner and PvP snapshots.
- The PvP journey uses four ordinarily registered/equipped/learned actors and the real frontier attack handler to prove normal attack, Guard, Power Strike, Quick Shot, Fireball/Burn and Smite/heal, plus illegal skill/target/stale/restart rejection.
- The language journey runs build discovery, branch learning, a canonical Heal preview, actual named-recipient selection, combat feedback, reset, stale/error, retired callback and migration notice routes independently in ru/en/es. It checks a 20-character HTML-sensitive name, escaping, missing keys, internal IDs, Cyrillic leaks into en/es, 4,096-character message limits and 64-byte callback limits.

These are exercised ordinary paths. The level/mastery matrix at levels `1/1`, `3/3`, `6/8`, `10/14`, and `15/20`, cross-branch M20 builds, stat swaps, and level 50/100 safety probes are explicitly synthetic laboratory evidence.

## Balance evidence and J5 changes

The checked JSON uses 200 paired seeds (`0..199`), production field item definitions, real enemy source IDs/profiles, the shared actor/effect evaluators, and the shared affected-side scheduler. It contains 20 passing accessibility rows, 20 passing role gates, 240 encounter-matrix results, explicit stalls/failing seeds, and no legacy simulator authority. `dark_treant` is excluded because its 500,000 HP is not ordinary-content evidence.

The only numerical tuning under J5 is recorded below and in the JSON. No other live formula, item, mob, reward, economy, or route number was tuned in this Epic.

| Skill | Field | Old | New | Relative change |
|---|---|---:|---:|---:|
| `cleave_through` | direct power | 1.00 | 1.15 | +15.00% |
| `frenzy_chain` | direct power | 1.60 | 1.84 | +15.00% |
| `savage_chop` | direct power | 1.20 | 1.02 | -15.00% |
| `last_roar` | direct power | 1.90 | 1.62 | -14.74% |
| `bleeding_cut` | direct power | 0.85 | 0.73 | -14.12% |
| `sunder_armor` | direct power | 0.90 | 0.77 | -14.44% |
| `reopen_wounds` | direct power | 1.20 | 1.38 | +15.00% |
| `ravage` | direct power | 1.80 | 2.07 | +15.00% |
| `rupture_toxins` | direct power | 1.20 | 1.38 | +15.00% |
| `backstab` | direct power | 1.30 | 1.49 | +14.62% |

## PR229 / PR230 regression safety

The implementation keeps PR229's chapter, travel, contract, gathering, crafting and ordinary production loop on the existing authorities. It keeps PR230's 32 field templates, vendors, regional sources, rarity/dry-streak policy, ten slots, instance ownership/rolls, enhancement/advancement, settlement RNG, reward provenance, and legacy-review behavior. Combat RNG is separate from frozen reward RNG. The earned chapter, content, group and gear journeys plus the existing PR229/PR230 suites are the regression evidence; no compatibility waiver is intended.

## Deliberate V1 limits

- PvP support is intentionally limited to normal attack, Guard, Power Strike, Quick Shot, Fireball and Smite. This is not a full group-PvP or all-tree balance claim.
- There are no saved build presets, action decks, new item slots, runes, sets, affix pools, resistances, threat subsystem, teleport redesign, or economy expansion.
- Branch labels do not grant hidden class bonuses. Armor/offhand identity remains descriptive; actual resolved stats are authoritative.
- Old checked balance reports remain historical. Only the V1 evidence artifact claims alignment with this evaluator and rules version.
- Final Draft PR validation must run on the exact candidate commit. This report does not authorize merge.
