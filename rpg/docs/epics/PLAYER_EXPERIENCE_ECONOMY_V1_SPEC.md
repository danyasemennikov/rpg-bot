# PXE1 — Player Experience & Economy Deepening V1

**Contract:** PXE1-1 · **Mode:** design and source audit only · **Consolidated:** 2026-10-05 UTC

**Repository:** danyasemennikov/rpg-bot. **Verified `origin/main`: `3c5bfa62836c705a6327ce059f4e190b54ccf3e6`.** This is the merge of PR236. The MappingProxy repair is baseline, not PXE1 work. Inspection used a clean detached checkout; no implementation branch, PR, production edit, migration, or live game action was made. Source inspection and independent arithmetic are the evidence for this design; no new gameplay test pass or Telegram validation is claimed.

This is the single consolidated normative contract. Sections 1–20 and their tables include all accepted continuation corrections and the owner's final pre-live multiplayer PvP requirement; no earlier chat addendum is needed. Examples illustrate the same rules, not alternatives. Existing mechanics remain unchanged unless explicitly superseded here. Implementation must record any non-derivable deviation for architecture review rather than quietly redesigning it.

## 1. Executive product summary

The alpha has working mechanics but exposes their module boundaries, internal state and repetitive actions to players. Navigation occupies too much screen space, meaningful progress is easy to miss, world encounters have inconsistent start paths, and instantaneous gathering plus milestone-sized crafting XP compress the economy.

PXE1 makes **Location the contextual action hub**, **Journal the record of current pursuits**, **Character the home of builds**, and **Activities the home of professions**. Six fixed lower-menu buttons replace location-dependent keyboard growth. Every ordinary card answers where the player is, what matters, what can be done and what changed; optional detail retains the useful depth.

World combat stays shared. A visible 12-second PvE formation window starts the same persisted encounter for every eligible participant. PvP keeps its300-second preparation and supports a principal plus one approved ally on each side, with actual live membership after atomic roster lock. Map opens locally, destinations have previews, and travel becomes persistent and cancellable. Gathering becomes a bounded two-minute activity with one edited progress card. Profession tools have finite durability; upgrades and ordinary repairs consume low-tier materials, with premium guild assistance for missing repair inputs. Crafting advances through repeated useful production, with explicit relevance limits, while every existing profession level and XP value is preserved.

The four existing Chapter I assignments, their requirements and rewards remain. Free, fully durable starter tools and direct source shortcuts keep the introduction accessible without a preliminary tool grind. Final turn-in produces the chapter epilogue immediately, then an explicit handoff into independent Regional Opportunities. There is no Chapter II or mandatory regional sequence.

The implementation package is **one Draft PR**, with internal phases and one coordinated migration/cutover. This contract does not authorize implementation or merge in this audit task.

## 2. Current-code audit

### 2.1 Baseline, authority and reading reconciliation

The requested `rpg/CLAUDE.md` does not exist. Its current canonical adapter is `rpg/docs/CLAUDE.md`. Read after `rpg/AGENTS.md`, together with the requested foundation/current-state/roadmap/index, then the repository bootstrap, workflow and system map. The user-specified reading sequence was used where it differed from AGENTS' general sequence.

All repository references below are relative to the verified repository root. Immutable source links use [the audited tree](https://github.com/danyasemennikov/rpg-bot/tree/3c5bfa62836c705a6327ce059f4e190b54ccf3e6/rpg). File and symbol names identify implementation evidence, not suggested new authorities.

| Document located at current main | Authority and reconciliation |
|---|---|
| `rpg/AGENTS.md`; `rpg/docs/AI_WORKFLOW.md`, `AI_CONTEXT_BOOTSTRAP.md`, `DOCS_INDEX.md`, `systems/README.md` | Contributor workflow, authority separation and owner map. Design → frozen contract → implementation → independent review → owner merge. |
| `rpg/docs/CLAUDE.md` | Navigation adapter, not full technical truth. |
| `rpg/docs/foundation/GAME_FOUNDATION.md` | Classless, weapon-defined identities and opportunity-cost balance remain. Its provisional slots/formulas/future features do not override PR230/231. |
| `rpg/docs/PROJECT_STATE_CURRENT.md` | Current-state authority, but its baseline header still names PR234. Its human-validation paragraph records interruption/PR236 repair, while older roadmap/index/human-plan entries still say NOT RUN. Record those discrepancies; do not infer deployment. |
| `rpg/docs/ROADMAP_CURRENT.md` | Teleport activation and broader PvP remain deferred. PXE1 does not activate them. |
| `rpg/docs/systems/combat/LIVE_COMBAT_SIDE_TURN_SPEC.md` | Active supporting guardrails: shared encounter, 15-second side windows, prep joining, active roster lock. Its own header delegates exact affected-side scheduling/durability to merged code. Do not reinstate historical end-of-round effect timing. |
| `rpg/docs/archive/specs/COMBAT_CORE_V1_SPEC.md` | Explicitly superseded. PR231's snapshot/evaluator/order/result owners supersede its statements that group/target/effect support is future work. |
| `rpg/docs/CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md`; `archive/specs/WEAPON_BRANCHES_5_SKILLS_FINAL_DESIGN.md` | PR231 report plus `build_contract.py`/evaluator are current skill authority; archived branch design is historical. Ten families, twenty branches, 100 branch skills plus Power Strike remain. |
| `rpg/docs/archive/rollouts/OPEN_WORLD_GAMEPLAY_ROLLOUT_PHASE1.md` | Historical rollout; explicitly retains shared anchored world spawns. Later PEV1/RAV1 own expanded resource and named/mixed content. Tools were excluded then; PXE1 explicitly promotes them. |
| `rpg/docs/systems/world/WORLD_GRAPH_V1.md`, `WORLD_LOCATION_MAP_V1.md`, `WORLD_DATA_MODEL_V1.md` | Graph rationale, names/aliases and static-versus-dynamic ownership. Current `locations.py` owns exact edges and placement. No topology expansion. |
| `rpg/docs/systems/world/TRAVEL_AND_TELEPORT_V1.md` | Ordinary travel context; safe-hub teleport is a retained, disabled proposal. Its old working names are not current location labels. |
| `rpg/docs/foundation/LOOT_CRAFT_PROGRESSION_FOUNDATION.md` | Bulk/special distinction, material identity, long profession progression and permanent recipe knowledge remain. Tools were later work. Its level-100 gear tiers are not the new profession-tool bands. |
| `rpg/docs/epics/PROFESSIONS_ECONOMY_V1_SPEC.md`, `PROFESSIONS_ECONOMY_V1_REPORT.md`; `evidence/professions_economy_v1.json` | Merged PR233: 12 professions, 63 recipes, 28 mandatory resources, atomic receipts, owner-only harvest. Fast XP and unlimited repeated gathering were deliberate approved rules, now deliberately superseded. Evidence is historical, tested code `e29e4a368de625f6fb221871761f438f5a617f2c`, not this audit's test result. |
| `rpg/docs/epics/REGIONAL_ADVENTURES_V1_SPEC.md`, `REGIONAL_ADVENTURES_V1_REPORT.md`; `evidence/regional_adventures_v1.json`, `regional_adventures_v1_human.md` | Preserve 34 records, 7 independent projects, source reservations, immutable roster-lock bindings and T2 credit. RAV1's 90-second forming expiry is explicitly superseded. Historical broad runtime `ce88335267c6dbc05bef289e88deebd1fa28ea60`; repaired journey tests `43b5fb7a62f0265a89e20aeb9c3613f4605c56fc`. Old draft/unmerged phrases in report/evidence are provenance, not current merge state. |
| `rpg/docs/epics/PLAYABLE_ALPHA_VERTICAL_SLICE_V1.md` | Four assignments, starter kit and transactional objective bridges. Its old small craft XP and partial combat-reward limitations are superseded by PEV1 and PR230 respectively. |
| `rpg/docs/epics/FIELD_LOOT_AND_GEAR_PROGRESSION_V1.md`; `systems/gear/EQUIPMENT_ENHANCEMENT_PHASE1.md` | Existing field catalogue, gear instances, comparison, enhancement and settlement remain authorities; no gear durability rebalance. |
| `rpg/docs/foundation/PVP_RULESET_FOUNDATION.md` | Existing security, novice/respawn protection, numerical crime and death/loss rules remain. Its current singleton adapter boundary is explicitly superseded by owner-approved pre-live invitation-based2v2 maximum in section5.4, including precise group attribution/distribution and recovery. Larger/structured PvP remains deferred. |

### 2.2 Production ownership and verification map

| Subsystem | Current modules, handlers and important helpers | Persisted authority | Inspected test/contract surfaces |
|---|---|---|---|
| Lower menu / routing | `game/contextual_keyboard.py`: `_baseline_keyboard_rows`, `build_contextual_main_keyboard`; `bot.py`: text/command routing; `handlers/location.py`: `_send_lower_menu_sync_message` | No durable keyboard version; PTB message/UI state | `test_location_action_tokens.py`, `test_location_live_pvp_view.py`, RAV UI/review-repair tests |
| Location / Map / travel | `handlers/location.py`: `build_location_message`, `map_command`, `_build_route_map_text`, `_find_canonical_path`, `handle_location_buttons`; `game/locations.py`, `world_scaffolding.py` | `players.location_id`, `travel_revision`; `player_location_discovery`; no active journey table | `test_location_discovery_travel_migration.py`, `test_alpha_transactions_v1.py`, RAV map traversal |
| Anchored PvE | `game/pve_live.py`: create/load ordinary and mixed encounters, join/leave, `_prune_expired_forming_encounters`, `lock_open_world_pve_roster_for_runtime_start`, `ensure_runtime_for_battle`; `handlers/battle.py`: `start_battle`, `enter_open_world_pve_battle` | `pve_spawn_instances`, `pve_encounters`, `pve_encounter_participants`; JSON snapshots, source roster, lock, seeds/revisions | `test_world_pve_encounter_foundation.py`, `test_group_pve_runtime_enablement.py`, `test_solo_pve_runtime_handler_flow.py` |
| Live turns / pack UI | `game/live_combat_runtime.py`, `combat_orders.py`, `actor_snapshot.py`, `combat_identity.py`; `handlers/battle.py`: `_v1_action_buttons`, durable dispatch and timeout paths | `combat_orders_v1`, `combat_turn_results_v1`, encounter actor/enemy JSON, `battle_consumable_receipts_v1`, `pve_participant_departures_v1` | `test_character_builds_v1_durability.py`, group/mixed/combat-core tests, `test_live_combat_runtime_foundation.py` |
| Combat rewards / objectives | `game/pve_reward_settlement.py`: `_locked_roster`, `build_reward_plan`, T1/T2, `_v1_mastery_awards`; `regional_objectives.py`; `quest_board.py` | `pve_reward_settlements`, `player_gear_progress`, immutable `rav1_combat_bindings`, individual profession/mastery/contract rows | Itemization/settlement tests; RAV combat/objective/journey J11–J14; build durability manual-survivor test |
| PvP | `game/pvp_engagement.py`, `pvp_live.py`, `pvp_rules.py`, `pvp_state.py`, `pvp_turn_timing.py`, death/inventory policies; location handlers; `bot.pvp_tick` | `pvp_engagements`, `pvp_engagement_reinforcements`, `reason_context` battle JSON, `pvp_terminal_settlements_v1`, `pvp_log`, player legal state | `test_pvp_live_flow_v1.py`, `test_character_builds_v1_pvp_journey.py`, durability/PvP view tests |
| Chapter / board | `game/quest_board.py`: `register_contract_objective`, `_objective_progress`, `claim_completed_hunt_contract`; `starter_kit.py`; `handlers/chapter.py`, board renderer in location | `player_hunt_contracts`, `player_hunter_progress`, `player_contract_objectives`, `player_contract_history`, `player_starter_kits` | `test_playable_alpha_v1.py`, `test_quest_board_phase1.py`, `test_quest_board_battle_bridge.py`, alpha transactions |
| Regional / History | `regional_catalog.py`, `regional_opportunities.py`, `regional_adventures.py`, `regional_objectives.py`, `regional_schema.py`; `handlers/regional.py`, `handlers/chapter.py` | `rav1_projects`, `rav1_facts`, `rav1_claims`, `rav1_pins`, `rav1_combat_bindings`, economy receipts | RAV schema/transactions/UI/localization/review-repair/journey suites |
| Attributes / skills | `game/build_contract.py`, `build_progression.py`, `weapon_mastery.py`, `actor_snapshot.py`; `handlers/build.py`, `handlers/profile.py` | `players` attributes/budget/build and gear revisions; `weapon_mastery`, `player_skills`, `build_mutation_receipts`, build migration archives/notices/quarantine | `test_character_builds_v1_experimentation.py`, contract/UI/language/migration/journey suites |
| Gather / hunting | `gathering_foundation.py`, `gathering_progression.py`, `gathering_runtime.py`: `gather_resource`; `profession_resources.py`: `ENVIRONMENTAL_SOURCES`, `HARVEST_MANIFEST`; `hunting.py`: `_authority`, `harvest_victory`; location/chapter/profession handlers | `player_gathering_professions(telegram_id, profession_key, level, exp)`, `pve_harvest_claims`, both action receipt ledgers | `test_gathering_profession_*`, `test_professions_economy_v1_sources.py`, hunting/transactions/journeys |
| Craft / profession XP | `profession_recipes.py`, `crafting_foundation.py`, `crafting_runtime.py`, `profession_progression.py`, `recipe_knowledge.py`, `profession_schema.py`; `handlers/professions.py` | `player_crafting_professions(player_id, profession_key, level, exp)`, `player_recipe_knowledge`, `economy_schema_migrations`, `economy_action_receipts` | `test_professions_economy_v1_progression.py`, catalogue/knowledge/migration/economy/UI/journeys |
| Inventory / gear / shop | `handlers/inventory.py`: lists/details/comparison; `handlers/location.py`: shop/preview/buy; `game/gear_instances.py`, `gear_progression.py`, `gear_ui.py`, `field_catalog.py`, `equipment_stats.py`, `economy_actions.py` | `items`, `inventory`, `equipment`, `gear_instances`, `gear_mutation_receipts`, `player_gear_goals`, economy receipts | `test_inventory_metadata_integration.py`, itemization/gear journeys, PEV transactions/economy/UI |
| Tokens / startup / localization | `game/action_receipts.py`: `peaceful_player`, `issue_actions`, `consume_action`; `database.py`; `bot.initialize_runtime`; `game/i18n.py`, `locales/*.py` | `player_ui_actions`, `player_action_receipts`, owner-specific durable receipt tables | Alpha/PEV/RAV migration and token tests; locale parity tests |

`game/quests_data.py` is not the live Chapter I objective authority. Routing new progress there would create a second quest system.

### 2.3 Findings against manual observations

Classification codes: **P** presentation-only; **N** routing/navigation; **L** runtime/lifecycle; **S** persistence/schema; **E** balance/economy; **C** content/copy; **M** mixed.

| User area | Verified source finding / interpretation | Class | Frozen resolution |
|---|---|---|---|
| A lower menu | Eight baseline buttons + appended Journal + exits/gather/services. Journal exists in this revision, despite being missed in the playthrough. Sync messages are emitted. | M | Six fixed entries; one-time meaningful keyboard installation; contextual actions inline. |
| B compactness | Multiple independent list budgets; recipes and branch screens repeat metadata. | P | Shared presentation budgets, pagination, Summary/Details. |
| C technical language | Profile prints `location_id`; regional map prints `/go <id>`; build views use `M`; encounter/receipt surfaces expose technical identifiers. | C/P | Localized resolvers; diagnostics excluded from ordinary Details too. |
| D Nearby | Location's Nearby routes to a RAV-only list, so Chapter and city services are outside its aggregation. | N | One contextual aggregator over existing owners, not a new mutation owner. |
| E travel | 15 seconds per adjacent move; discovered long trip = hops ×15×3; handler sleeps then writes final location. No persistent cancellation/ETA. | M | Durable route, preview, 15h+3(h−1), stop at reached node. |
| F formation | Spawn forming is distinct from encounter `status='active'`; 90-second read-path cleanup expires it. `start_battle(open_runtime_now=True)` starts immediately; false path can wait without an auto-start job. | L/S | Explicit lifecycle version/deadline; job-owned start; reads cannot expire normal formation. |
| F group/roster | Join and lock already exist, but start and initialization cross transaction boundaries; lock does not comprehensively revalidate final player location/activity. | L | One atomic roster/snapshot/first-phase boundary and recovery. |
| F PvP | World/location engagements already exist. Prep is300seconds. Current conversion initializes attacker+defender only and expires accepted reinforcements, although shared side runtime accepts multiple actors. | M | Principal-approved invitations, ally acceptance, cap2per side; atomic promotion to real locked live actors; extend pair-specific authorization, batch execution and consequences under existing PvP owner. |
| F pack actions | `_v1_action_buttons` builds skill × recipient entries. | P/N | Action then target; one immutable revision/deadline throughout. |
| G attributes | Both preview and apply use safe-hub checks for all redistribution, conflating spending with reset. | L/N | Separate spend-only operation anywhere outside combat; resets stay in safe hubs. |
| H branches | Branch headings exist, but both five-skill lists share one long keyboard; locks use M-codes and coefficients. | P/C | One selected branch, full-language locks, evaluator-derived effects. |
| I/J inventory/compare | Eight item controls and wide category tabs; functional details exist; comparison has Back but no Equip. | P/N | Six-row list, category chooser, direct legal Equip. |
| K/L shop/sale | Buy list repeats entries; stack Sell Materials includes consumables; confirmation lacks useful result hierarchy. | M | Visible Buy/Sell modes; exact receipt summary and selective sale protection. |
| M/N recipes/professions | Twelve professions and 63 recipes are correctly owned but metadata dominates, quest-required recipe is not prioritized. | P/N | Task shortcut plus concise ingredients/effect/output/XP. |
| O crafting XP | `250*r`, clipped at recipe ceiling, is tested; 3+2+2+1 crafts can reach 20. This is policy, not an unexplained arithmetic bug. | E | Cost-based XP and relevance; unchanged 50L threshold and preserved rows. |
| P gathering | One RNG/action per Telegram message with no duration; durable economic result already exists. | L/S/E | Finite session and per-tick receipt, no second reward engine. |
| Q/R tools | Actual gear/inventory durability fields exist, but no profession-tool lifecycle. | S/E | Dedicated five-slot profession equipment, not combat gear. |
| S/T resource sinks | Existing 28 resources have stable IDs and explicit levels; existing cross-tier inputs are small. | E/C | Static resource tier metadata, 20 tool recipes, recurring low-tier repair inputs. |
| U objective feedback | Objective updates commit inside action owners but return no consistent display delta. | M | Same-transaction feedback facts, rendered after commit. |
| V board | Active state uses `progress_kills/required_kills` even for objective-only contracts; available list can include active definition. | P/N | Objective-derived summary; active first and excluded from available. |
| W Chapter | Final claim records history; Journal switches to regional home based on `chapter_homecoming`; epilogue is not immediate. | M | Atomic finale event and next-assignment handoff. |
| X/Y Journal/History | Regional home has eleven controls; `show_completed_history` still adds all live professions and current equipment goal. | P/N | Separate archival History, regional-only terminology and contextual shortcuts. |
| Z harvest | Applied settlement, owner eligibility, one unit/one claim, same location and 1,800 seconds are real safeguards. | P plus tool integration | Preserve entitlement; show selected resource/quantity/XP/quest change; consume knife wear atomically. |
| AA feedback | Ordinary join/equip/sale/claim paths use alerts inconsistently. | P | Routine edit/toast; objective compact card; major chapter/level message. |
| AB commands | Handlers exist for `/journal` etc.; no `set_my_commands` registration in `bot.py`. Actual account autocomplete was not inspected. | N | Register exact localized command list. |
| AC preserved patterns | Comparison, per-item actions, current-position marker, RAV independence and transaction owners are present. | Preserve | Build on these; no broad engine rewrite. |

### 2.4 Hidden integration blockers resolved by this contract

1. **Formation is currently represented by the linked spawn, not a dedicated encounter status.** Keep that model and add a version/deadline; do not introduce a competing encounter table.
2. **A forming owner can leave while others remain, but settlement requires the owner in the locked roster.** Transfer forming ownership deterministically before lock (section 5); do not reach terminal reward validation with an absent owner.
3. **No scheduled PvE formation start exists in bot startup.** The existing repeating job is for PvP; the new job must drive PvE deadlines even with no callback.
4. **Aggro uses a sleeping task and `in_battle=1` before encounter creation.** Replace this prelock with an atomic real encounter transition and durable visit threat deadlines; otherwise gathering/travel can race or remain stuck.
5. **Generic peaceful checks do not know travel/gather sessions.** Every mutation owner must use a connection-scoped activity check under the same SQLite write lock. A UI-only disable is insufficient.
6. **Telegram reply and inline keyboards occupy one `reply_markup` field.** Install the fixed lower keyboard on a meaningful welcome/status response, then send the contextual inline card. Do not attempt to put both markups on one message or repeatedly emit a keyboard-sync message. [Telegram Bot API](https://core.telegram.org/bots/api#sendmessage)
7. **Existing migration validators are strict and receipt versions are meaningful.** Add named PXE1 migration and distinct new receipt kinds; preserve old receipt bytes, catalogue versions and replay adapters.
8. **Existing tests intentionally assert 90-second expiry and fast XP.** Replace only those superseded expectations, add deadline-start and new arithmetic assertions; retain unrelated conservation, roster and recovery tests.

## 3. Information architecture

### 3.1 Exact permanent menu

Exactly **six buttons, three rows, two per row**, in this order:

| Row | ru | en | es |
|---|---|---|---|
| 1 | 📍 Локация · 🗺 Карта | 📍 Location · 🗺 Map | 📍 Lugar · 🗺 Mapa |
| 2 | 📖 Журнал · 🎒 Инвентарь | 📖 Journal · 🎒 Inventory | 📖 Diario · 🎒 Inventario |
| 3 | 👤 Персонаж · 🛠 Занятия | 👤 Character · 🛠 Activities | 👤 Personaje · 🛠 Oficios |

Use `resize_keyboard=True`, `one_time_keyboard=False`, `is_persistent=True` where supported by the existing PTB version. Telegram clients ultimately control viewport size; the acceptance gate is real phone/desktop fit, not a promised pixel height. [ReplyKeyboardMarkup](https://core.telegram.org/bots/api#replykeyboardmarkup)

No location exit, shop, gathering profession, quest, combat action, Help or Settings joins this keyboard. During travel or gathering, Location and Activities open the active status. During combat, Location opens encounter status; all other entries remain readable and illegal mutations explain why.

### 3.2 Exact submenu ownership

| Entry | Owned child surfaces |
|---|---|
| Location | Current context; ranked local actions; Encounters; Gather; Services; Exits; Nearby is an alias of this same hub. A list filter is local UI state, not a different Nearby product. |
| Map | Current region; destination preview; World Map; route details; active travel status. At Aster: Aster plus its six exits, then World Map. Old Mine opens Frostspine with the mine spur selected; South Shore opens its coast stub. |
| Journal | Current Chapter assignment until complete; active hunt and pinned regional pursuits; Regional Opportunities; History. Quest-required recipe and build/gear goal links are contextual shortcuts, not permanent duplicated dashboards. |
| Inventory | All, Gear, Supplies, Materials, Tools category chooser; item detail; compare/equip/use; advanced item actions; equipment catalogue; transaction records under More. |
| Character | Profile (default); Attributes; Weapon Skills; Build & Equipment; More → Help, Settings, Recovery. Build presets are not added. |
| Activities | Current activity (if any); Gathering; Crafting; Tools; Records. Gathering lists five profession records, with Hunting opening local harvest rather than environmental Gather. Crafting lists seven professions. |

Old Profile → Character/Profile; Stats → Character/Attributes; Skills → Character/Weapon Skills; Build → Character/Build & Equipment; Help and Settings → Character/More. Old guild/workshop → the same Activities/Crafting views, retaining local service validation. Old travel text → current destination preview, never auto-travel. Old gather text → session preview, never one instant roll. Old Nearby → Location. Old receipts/history controls → the appropriate Records or narrative History. All current and legacy ru/en/es labels remain recognized as aliases; labels from a previous language never execute an obsolete mutation.

**Keyboard migration:** persist last installed menu version/language. On first user interaction after upgrade, send a useful brief status such as “Aster · Your assignment is ready to turn in” with the new ReplyKeyboardMarkup, followed by the requested inline card. On `/start`, use the existing welcome/status message. On language change, attach it to the language-change confirmation. Mark installed only after successful send. No “Lower menu updated,” empty message, delete/repost loop, or per-location reinstall.

### 3.3 Compact-first standard

Ordinary summary: target ≤900 UTF-16 code units, ≤10 explicit text lines, **≤8 inline buttons and ≤6 inline rows**, maximum two per row. Lists: six entries per page; at most 12 buttons and 10 rows including pagination/Back. A selected branch has five skill entries. Long labels use a full-width row. Two-column labels target ≤18 visible characters; full-width labels ≤32. Never truncate a price, quantity, target identity or irreversible choice to satisfy a budget.

Summary → Details → Records/History preserves useful information. Long narrative/reference pages may reach 3,000 UTF-16 units; paginate longer content. Every callback ≤64 UTF-8 bytes, opaque mutation tokens, escaped dynamic HTML. These are application limits, deliberately below transport limits. Current SDK-compatible buttons suffice; no client or PTB upgrade is required for newer Telegram features.

Stable order: urgency, explicit quest relevance, current activity, then catalogue order and stable ID tie-break. Buttons contain the item/destination name once; do not repeat every list entry in both prose and a second large action label. State/count/price may appear beside that name. No raw IDs, instance numbers, command recipes, JSON, M-codes or coefficients in ordinary screens. Optional player Details may explain formulas in words; raw diagnostic identities belong only to explicit developer/admin surfaces.

## 4. Screen contracts

The following are realistic English mobile examples. Names reuse canonical translations. Values show the stated example state; displayed stats/costs always come from their owning preview. Square brackets denote inline buttons. Every screen has a deterministic Back route; persistent lower navigation is always the six buttons above.

### Location / Nearby / city

```text
📍 Hills · Westwild
Wolves prowl the slopes.
Elmor's Workshop · Wolves 1/2
🔥 Wolf pack · 2 players · starts in 8s
[Join wolf pack]
[Encounters] [Gather]
[Exits]      [More nearby]
```

```text
📍 Nearby · Hills
Your local actions
[Harvest wolf pelt · 1 available]
[Continue: Elmor's Workshop]
[Woodcutting] [Herbalism]
[Players here] [Back]
```

“Nearby” is a filtered/paginated rendering of Location data. It cannot say “nothing nearby” while a local turn-in, service or other legal action exists.

```text
📍 Aster · Safe haven
✅ Home from the Road is ready
[Turn in assignment]
[Shop]       [Quest board]
[Guild]      [Inn · 12 gold]
[Exits]      [More nearby]
```

### Map / regional map / destination / travel

```text
🗺 Aster
📍 You are here
Choose an exit to preview the road.
[Wheat Fields · 15s]
[Stone Road · 15s]
[Old Road · 15s]
[Next exits] [World Map]
```

```text
🗺 Westwild · page 1/2
📍 Elmor
✅ Turn-in awaits in Aster
[Aster · 1:45 · ✅]
[Copse · 15s]
[Grove · 33s]
[Hills · 51s]
[Meadows · 1:09]
[Wheat Fields · 1:27]
[Next] [World Map]
[Travel status] [Back]
```

```text
🧭 Aster
Elmor → Copse → Grove → Hills
→ Meadows → Wheat Fields → Aster
6 roads · 1:45 · no gold cost
Walking one road at a time: 1:30
✅ Home from the Road: turn in here
[Start walking · 1:45]
[Route details] [Back]
```

```text
🚶 Elmor → Aster
Reached: Grove
Total planned: 1:45 · Remaining: 1:02
Next: Hills
[Map] [Cancel travel]
```

Map remains a navigation/read surface during travel. Selecting another destination previews it but offers “Stop current trip” before a separate new start; it never silently replaces a trip.

### Encounter states and joining

```text
🐺 Wolf pack · 3 wolves
Available · Hills
[Attack] [Details]
[Back]
```

```text
🔥 Wolf pack is gathering
Hills · 1 player
Starts in 12s
Joining closes when combat starts.
[Join] [Details]
[Back]
```

```text
🔥 Wolf pack is gathering
You joined · 2 players
Starts in 8s
[Leave] [Participants]
[Location]
```

```text
⚔ Wolf pack · battle in progress
3 players · Round 2
The roster is closed.
[View status] [Other encounters]
```

```text
🐺 Wolf pack
Returns in 24s
[Refresh] [Other encounters]
```

### Pack combat / target selection

```text
⚔ Wolf pack · Round 2
Your side · 11s · 1/2 ready
You: 84/118 HP · 30/62 MP
Wolves: 3 alive
Last: Mara blocked a bite.
[Attack] [Skills]
[Guard] [Supplies]
[Flee] [Battle details]
```

```text
Power Strike · 12 MP · ready
Choose a target · 9s
[Wolf 1 · 18/42 HP]
[Wolf 2 · 42/42 HP]
[Wolf 3 · 30/42 HP]
[Back to actions]
```

### Journal / board / active and ready quests

```text
📖 Journal · Chapter I
Elmor's Workshop · 3/5 objectives
Next: craft a Trail Vest
[Open assignment]
[Required recipe] [Map]
[Regional Opportunities] [History]
```

```text
📋 Aster quest board
ACTIVE · Home from the Road
✅ 2/2 objectives
[Turn in]
AVAILABLE
[Hunting contracts · 6]
[Locked contracts] [Back]
```

```text
Elmor's Workshop
✓ Defeat wolves · 2/2
✓ Harvest pelts · 2/2
○ Craft Trail Vest · 0/1
✓ Cook a Field Ration · 1/1
○ Wear Trail Vest · 0/1
Report to: Elmor
[Required recipe] [Sources]
[Story] [Back]
```

```text
✅ Home from the Road
All 2 objectives complete
Turn in: Aster
[Turn in] [Details]
```

At another location the first control is `[Route to Aster]`, not an illegal claim.

```text
✅ Objective complete
Craft Trail Vest · 1/1
Next: equip your Trail Vest
[Open vest] [Assignment]
```

### Finale / open-world home

```text
🎉 Chapter I complete
The road to Elmor is behind you.
You fought, travelled, gathered,
crafted, equipped and traded.

Your next journey is yours to choose.
Explore regional stories, take contracts
or develop your equipment and skills.
[Explore opportunities] [Map]
[Journal] [Local contracts]
```

Append the existing localized epilogue in a deliberate narrative layer, up to the long-message budget. This is the one automatic finale event; History can replay it without granting rewards.

```text
🧭 Regional Opportunities
📍 Elmor · Choose your own direction
📌 The Lost Tool Roll · return to Mara
[Tracked pursuits] [Nearby]
[Regions] [Clues]
[Regional completed] [Discoveries]
[Local work] [Back]
```

### Character / attributes / branches / skill

```text
👤 Danya · Level 4
📍 Elmor · 189 gold
HP 118/154 · MP 50/74
XP 90/next level · 3 free points
One-handed sword · mastery 5
[Attributes] [Weapon skills]
[Build & equipment] [More]
```

Actual XP line renders the numeric threshold rather than the example phrase.

```text
Attributes · 3 free points
Strength 5       Agility 2
Intuition 1      Vitality 3
Wisdom 2         Luck 1
[Spend points]
[Reset at a safe hub] [Back]
```

Spend opens one attribute selector, then a +1/+all draft and one Apply. A second selector page avoids a twelve-button plus/minus grid.

```text
One-handed sword · mastery 5
[Guardian] [Vanguard]
Guardian: protect and counterattack
[✓ Rush · rank 1]
[＋ Defensive Stance · available]
[🔒 Shield Bash · no skill points]
[🔒 Parry · no skill points]
[🔒 Counter · mastery 8 required]
[Branch details] [Back]
```

```text
Power Strike · rank 1
A stronger strike against one enemy.
12 MP · cooldown: 3 opportunities
Against selected wolf: 22–28 damage
[Use] [Details]
[Back]
```

Damage is a sample preview, never a new fixed skill rule. Outside combat omit Use and use a neutral-target estimate explicitly labelled as such, or show the effect without an unsupported numeric estimate.

### Inventory / detail / comparison

```text
🎒 Inventory · Materials · 1/3
[Common herb ×12]
[Common wood ×8]
[Wolf pelt ×3]
[Iron ore ×4]
[Coal ×2]
[Wolf fang ×1]
[Next] [Categories]
[More]
```

```text
Trail Vest · Common · gear tier 1
Body · +0
Physical defence: 6
[Equip] [Compare]
[Improve] [More]
[Back]
```

```text
Trail Vest → empty body slot
Physical defence: 2 → 8 (+6)
[Equip] [Back]
```

The detail's base defence and comparison's effective totals are separately labelled; actual renderer values come from existing helpers.

### Shop Buy / Sell / result

```text
Shop · Elmor · 181 gold
[Buy ✓] [Sell]
[Small HP potion · 30 gold]
[Mana potion · 60 gold]
[Basic weapons]
[Starter tools · 12 gold each]
[Back]
```

```text
Sell items · Elmor · 181 gold
Quest: sell one spare item
[Wolf pelt ×3 · sell 1 for 8]
[Common herb ×12 · sell 1 for 3]
[Other categories] [Back]
```

```text
Sold Wolf Pelt ×1 · +8 gold
Balance: 189 · Pelts remaining: 2
✅ Sell a spare item: complete
✅ Home from the Road is ready
[Route to Aster] [Continue selling]
```

### Professions / recipe / source

```text
🛠 Crafting · page 1/2
Quest needs: Trail Vest
[Open required recipe]
[Medium armor · level 1]
[Alchemy · level 2]
[Cooking · level 1]
[Blacksmithing · level 6]
[Arcane engineering · level 1]
[Next] [Back]
```

```text
Trail Vest · Body · Common
Adds 6 base physical defence
Wolf pelt: 2/2 ✓
Common wood: 1/2 · need 1
Output: 1 vest · XP: 15 at your level
Craft at a guild · no gold fee
[Find common wood] [Details]
[Back]
```

When all conditions pass, `[Craft 1]` replaces the missing-input CTA and commits its fresh server intent. Learning an unknown recipe has a separately priced Learn preview.

```text
Common wood · Woodcutting level 1
Tier 1 axe or better
Nearby known sources:
[Copse · 15s · 40% per attempt]
[Grove · 33s · 35% per attempt]
[More sources] [Uses]
[Back]
```

### Gathering / tool / broken-tool recovery

```text
🪓 Woodcutting · Copse
Gathered: Common wood ×5
Profession XP: +50
Axe: 49/60 · Remaining: 0:32
[Stop] [Location]
```

```text
🪓 Regional axe · tool tier 2
Durability: 24/120
Gathers resource tiers 1–2
Repairs: 4 wood, 2 iron, 1 coal
and 10 gold · restores to 120
[Repair at guild] [Upgrade]
[Sources] [Back]
```

```text
🪓 Starter axe is worn out
Gathering stopped · kept 4 wood
Replacement: 12 gold in any safe hub
[Route to nearest safe hub]
[Craft a replacement] [Tools]
```

```text
Regional pick · broken · 0/120
Repair needs 4 wood, 2 iron, 1 coal
and 12 gold · you have no materials
Guild supplies all inputs: 96 gold total
Restores 120/120 · no XP
[Assisted repair · 96 gold]
[Find materials] [Back]
```

## 5. Exact encounter lifecycle contract

### 5.1 Authority, initiation and countdown

Keep **spawn** `idle → forming → active → respawning → idle`. Keep existing encounter statuses: forming uses `pve_encounters.status='active'` with its linked spawns `forming`; active uses the same encounter status with linked spawns `active` and a persisted lock. Terminal statuses and settlement remain current owners. All views use one derived phase helper; they must not interpret `status='active'` alone as roster lock.

New anchored PvE creation sets `lifecycle_version=1`, `formation_deadline_ms=server_now+12,000`, and `formation_revision=1` in the same IMMEDIATE transaction that reserves **every** required source and inserts the initiator as an active forming participant. Solo, normal pack, special and mixed encounters use this same path. No private per-player fallback is allowed for a canonical world spawn.

A stale Attack for a spawn already linked to a forming encounter opens that encounter and its Join action. It never silently creates a second fight or substitutes another special/mixed source. Concurrent Attack requests reserve one authoritative set; the loser gets current state. Existing ordinary pack grouping remains unchanged; no extra source count, scaling or loot multiplier.

**Always wait until the 12-second deadline. No ready button and no early start**, even solo. This is distinct from side-turn early completion. A player must be alive, at the exact canonical location, out of another PvE/PvP engagement and not travelling/gathering to initiate or join. Join validates everything again under the write lock and succeeds only with `now < deadline` and forming anchors. Baseline has no explicit PvE participant cap: PXE1 adds none; paginate participants and keep existing evaluator/target constraints. Dead/fled/left participants cannot rejoin the same encounter; they may enter a subsequent encounter.

Forming membership blocks peaceful economic mutations, travel and gathering. Read screens remain accessible. Leave is immediate and free while the persisted encounter is still forming and runtime initialization has not committed, including after a delayed/failed start deadline. Join still closes strictly at the deadline. Leave and Start serialize under the same SQLite writer: Leave-first removes the participant; Start-first makes the old Leave open active combat and its existing flee rules. The Leave path must not unconditionally start combat before checking authoritative phase. Leaving never extends the deadline or reopens Join. If the owner leaves, transfer `owner_player_id` to the remaining participant with earliest `(joined_at, player_id)`, rebuild the forming leader projection from that player's authoritative state, retain encounter/source IDs and seeds, and increment formation revision. The departed actor cannot receive rewards or harvest; the new owner inherits the existing single harvest role. If nobody remains, atomically mark encounter abandoned and release exactly its forming sources to idle. No respawn wait or reward for unstarted combat.

### 5.2 Deadline start, roster lock and recovery

Add a bot job every **1 second**, processing due encounters ordered by `(formation_deadline_ms, encounter_id)`, batches of 100 with continuation next tick. Also invoke the same due-event service before a relevant mutation; viewing a card does not create an alternative start implementation. The deadline is authoritative even if job delivery is late; join at equality is rejected.

Under one `BEGIN IMMEDIATE` transaction:

1. Reload encounter, phase/version/deadline and all reserved source rows. Already active returns the persisted start state; terminal returns terminal state.
2. Revalidate each forming participant's life, canonical location and competing authoritative activity/engagement. Remove invalid participants with explicit `left` status; repair owner as above. Empty roster abandons and releases sources.
3. Freeze the exact roster in `locked_roster_json`; create all participant actor snapshots at this boundary, including the owner's current build; preserve enemy/source identities and seed. Capture RAV1 bindings here, with existing creation-time RAV marker semantics.
4. Persist the first live phase, active side, deadline, revision, all actor/enemy states and source links; set players' battle flags; change all linked forming spawns to active. Persist `runtime_started_ms` and increment formation revision. **Commit all of this together.**
5. Populate the existing in-memory runtime from the committed state, then render cards. No Telegram call occurs in the transaction. A cache failure is recovered from SQLite without a second lock, RNG roll or RAV binding.

First side remains current initiation policy: player-initiated PvE starts player side, aggression starts enemy side. Existing affected-side effect scheduling, 15-second player side windows, deterministic action order, cooldowns and fallback semantics are unchanged. A second player opening their card must not reset the deadline/revision or rebuild the roster.

A due start is not a TTL expiry. Transient database failure rolls back and retries next tick; after three failures log an operational error and show “Preparing battle; retrying” on read. Keep reservation and membership until successful start or legal Leave. Do not expire valid encounters merely because Telegram failed. Invalid source/roster integrity marks the encounter `start_failed`, releases only verifiably linked forming sources, clears its memberships/flags in one transaction, records a recovery notice, and grants no outcome. Unknown state must not authorize rewards or reassign a source owned by another encounter.

On startup, recover prepared reward settlements first, then initialize PXE1 state before accepting actions. New-version due formations start once; future deadlines retain their remaining time. Pre-PXE1 anchored forming rows with coherent sources receive a fresh 12-second deadline at cutover and current snapshots at lock; do not revive already expired/terminal rows. Existing active battles keep their runtime, rules version, roster and reward authority. Existing legal non-anchored legacy encounters resume on their compatibility path; new public world combat never creates one.

The same 1-second job drives overdue **PvE side** deadlines via the existing durable submission/result path, including all participant terminal cleanup and T1/T2 settlement. Extract context-free orchestration from handlers only as needed. No parallel battle evaluator. Startup resolves one due side, opens the next phase with a fresh 15-second opportunity, and resumes normal scheduling; it does not replay hours of offline turns instantaneously.

### 5.3 Visibility, stale actions and rewards

Available: localized spawn name/count + Attack. Forming: name/count, participants, remaining seconds + Join for eligible outsiders or Leave for members. Active: name/count, round, participant count + View status; only a locked member can resume combat controls. Respawning: name and ceil(remaining seconds) + Refresh. All-state lists paginate six rows; filter by local location before pagination. Mixed-source contention says which opportunity is unavailable and offers other local activities, without exposing source IDs.

Formation countdown edits at creation, 8s, 4s and start (not every second). Status reads recalculate remaining time. Start delivers/edits each registered participant's combat card; a blocked chat does not stop world combat. Local observers see shared state when refreshing; do not broadcast every nearby fight to all players.

Old Attack/Join/Enter/Leave/turn buttons reload authority. If active, outsiders see “Battle already in progress”; members resume their current turn. If finished, show that player's eligible result or a public finished summary. Respawn never reuses an old encounter ID. A stale callback may navigate but cannot join a replacement encounter or submit an action to a newer revision.

Active roster is immutable. Flee uses `resolve_pve_flee_intent` and `pve_participant_departures_v1`; one player leaving cannot clear teammates. Defeat/resurrection and terminal party checks remain current behavior. T1 validates the persisted terminal snapshot and freezes each eligible survivor's rewards, source units and mastery. T2 applies once, including hunts and RAV1 bindings. Final-hit ownership is never used.

Preserve exact mastery policy: only an eligible surviving actor with manual contribution and a canonical weapon family; normal source 20 XP, elite/rare 40; player at least five character levels above source receives one quarter, minimum 5; sum capped at 80 per encounter. Family comes from combat snapshot, not later equipment. Fled, defeated and nonparticipant actors do not gain victory/objective credit. RAV eligibility is frozen at lock, not on a post-victory read; separate participants can advance different accepted projects.

Victory respawn remains **30 seconds**, retaining current settlement/source-release boundary. An individual successful flee removes only that participant and leaves a surviving group active. Last-participant flee and terminal solo/whole-party defeat both put linked anchored sources into **30-second respawn**, with no victory rewards. One participant's defeat does not end the surviving group's encounter. An empty unstarted formation instead releases sources immediately without respawn delay. A prepared/applied settlement remains the sole combat economic authority. Historical/unknown provenance retains the current review/fail-closed behavior.

### 5.4 Pre-live multiplayer PvP world encounters

**Owner-directed correction incorporated:** the earlier proposed 1v1-only PXE1 restriction is withdrawn. New PXE1 PvP encounters support **up to two humans per side**, including accepted reinforcements. Solo PvE, group PvE and PvP share the world-visible preparation → atomic locked roster → active side-turn → settlement model. PvP retains its own initiation, consent, legal and death policies.

#### 5.4.1 Verified reusable architecture and precise scope

The direct audit found that `LiveCombatRuntime.create_encounter` already accepts distinct participant lists for both sides, collects one order per eligible actor and resolves a stable ordered batch. The current PvP adapter, however, constructs singleton sides, selects `submitted_actions[0]`, authorizes only attacker/defender in `combat_orders.py`, expires accepted reinforcement rows on conversion and settles exactly one winner/loser. Those are **required adapter/authorization/settlement changes**, not existing group support. Reuse the shared evaluator, actor snapshots, side runtime, order/result receipts and existing engagement/reinforcement tables. No new combat engine or damage/armor coefficients.

No persistent party membership authority was found in the directly relevant joining path. Do not invent a party/guild relationship. Use the existing principal-issued invitation plus ally acceptance as two-party consent. The old unrestricted self-join path is replaced by invitation-authorized Join, not by removing pre-live joining.

#### 5.4.2 States and location visibility

| World phase | Persisted authority | Location/Nearby behavior |
|---|---|---|
| Initiation available | Existing legal local-player target projection; no engagement yet | Attack preview only if current legality permits; exact existing crime warning |
| Preparing | `pvp_engagements.engagement_state='pending'`, `world_model_version=1`, no locked roster | Local public card with two principal names, accepted counts `1/2` or `2/2`, seconds remaining and View; principals can Invite/Attempt escape; invited eligible ally can Join named side/Decline |
| Lock/start | One transaction; no player-accessible intermediate state | Preparing until commit; no empty or disappearing encounter |
| Active | Existing `converted_to_battle`, immutable `locked_roster_json`, persisted actor/side state | Counts, side/round and View status; each active member resumes their own controls; no Join |
| Resolving | Converted engagement with durable terminal side result but aggregate receipt not committed | Results pending; no gameplay mutation/rejoin for surviving members |
| Resolved | Existing `cancelled` plus group result `victory` or `draw` | Winner side or draw and per-viewer result; no invitation/Join; retain in local Recent encounters for60s, then archive |
| Escaped/cancelled before live | Existing `escaped` or `cancelled`, no lock | Named cancellation reason; all commitments released; no victory/death settlement |

PvP has no reusable monster spawn and therefore no spawn respawn timer. Defeated characters return to the existing regional safe hub with protection. The encounter itself is immutable history; a later legal attack creates a new engagement. Pending/live cards remain visible to other players at that canonical location, not just principals. Outsiders see names/counts/phase, not private inventory, detailed build or HP/MP; members see their normal combat detail. Mixed PvE/PvP location lists use the existing six-entry pagination.

#### 5.4.3 Exact joining, consent and cap

**Cap: two participants per side, four total.** The principal occupies one seat and at most one reinforcement occupies the other. Asymmetric2v1 is legal; there is no matching queue, equality requirement or damage compensation. This fits the existing one-ally-per-side presentation while exercising the actual multiple-actor runtime. Larger groups remain deferred.

Side A is `initiator`: original attacker plus their accepted ally. Side B is `defender`: original defender plus their accepted ally. Only that side's original principal may invite its ally. Reinforcements cannot invite, switch sides, expel teammates or transfer leadership. The principal chooses from currently eligible local players; the selected ally must explicitly accept the invitation naming that principal and side. Principal approval alone never enrolls another account. An uninvited observer sees “Invitation required” and View participants, not arbitrary Join either side. No cross-location invitation, party auto-enrollment or unrestricted public enlistment.

Invite and Accept both require: version1 pending engagement, `now < engagement_ready_at`, living principal and candidate at its exact canonical location, no candidate travel/gather/PvE/other active PvP, candidate distinct from both principals and all current members, valid side, free side seat and current security eligibility. A pending invitation reserves that side's spare seat but **does not make the candidate busy**; acceptance is the commitment point. A candidate may receive another encounter's invitation but can accept only one engagement. Acceptance atomically expires that candidate's other pending invitations. Unanswered invitations expire at the original deadline or earlier lock/cancellation.

Use `get_attack_block_reason` for **every prospective initiator-side → defender-side pair** at Invite, Accept and lock, with the current location/security/novice policy. Safe locations always block. In guarded locations, a voluntarily joining ally with active respawn protection is ineligible on either side; joining cannot silently consume their protection. In frontier/core-war, existing dangerous-reentry protection handling applies. Existing novice exceptions, including red-target handling, remain inside `pvp_rules.py`; no UI shortcut bypasses them. Voluntary reinforcement consent makes them a lawful target of the opposite locked side within this encounter only; it does not alter global flags or allow another outsider to attack them outside normal rules.

An initiator-side ally sees the exact illegal-aggression/infamy warning against the original defender before Accept. Side-B assistance is defensive participation, never an automatically illegal new attack. A neutral defender ally voluntarily entering cannot retroactively turn a previously lawful attack into a crime. Legal/crime context is frozen as described below; it is not recomputed from flags that this encounter itself changes.

Accepted allies become busy immediately through their existing reinforcement row and may **Leave freely while authoritatively preparing**, even past a delayed deadline, using the same writer serialization as PvE. Their row becomes `left`; no crime refund, side switch or rejoin to the same engagement. Declined/revoked/left invites cannot be reopened for that same ally/engagement, but the principal may invite a different eligible candidate before the original deadline. A principal can revoke an unanswered invitation, but cannot kick an accepted ally. Accepted count excludes pending invitations; show “1 invited” separately.

#### 5.4.4 Deadline, escape and atomic roster lock

Normal preparation is **300 seconds from existing `engagement_started_at`**, unchanged by Invite, Accept, Leave, refresh or restart. The existing PvP due-event job drives the deadline; no callback is needed and no read expires a viable engagement. No readiness/early-start button. Join/Accept at equality is rejected. A failed principal escape is the one preserved early-start exception.

Only the original attacker or defender may use **Attempt escape** while pending and strictly before the preparation deadline, with the current **50% success probability**. At/after deadline, process normal start and refresh instead of rolling escape. Bind the action to actor, engagement and state revision. Assign/persist a128-bit combat seed at engagement creation. Derive its single roll from `SHA256(decoded_seed || b":pvp-prep-escape:" || ASCII(request_token))`; first8bytes unsigned big-endian `n`, success iff `n < 2^63`. Persist/replay outcome in the same transaction. Success cancels the whole unstarted encounter as `escaped`, releases all accepted allies and invitations, keeps previously applied crime consequences, and grants no reward/loss. Failure invokes the same atomic start immediately with currently accepted eligible allies; unanswered invitations expire. Reject an outsider/ally escape callback. This explicitly closes the current handler's insufficient actor-validation surface.

The start transaction (`BEGIN IMMEDIATE`) reloads pending phase, deadline/escape authority and state revision; validates both principals and all accepted reinforcement rows; checks their other memberships/activities with this engagement excluded from its own busy check; and revalidates all prospective cross-side legal pairs. A missing/dead/relocated principal or now-blocked principal pair cancels the unstarted engagement, releases commitments and produces a reason, without refunding valid earlier crime. An invalid ally is expired and notified, not substituted. If a cross-pair block implicates two allies, remove the later-accepted one first (tie reinforcement row ID), then revalidate; never remove a principal to accommodate an ally. A side always retains its valid principal at lock.

Freeze roster order as principal first then accepted ally, bind each reinforcement row ID, side, approval/acceptance evidence and legal context, and build **all** current actor snapshots under the same connection. Persist roster, all actor states, the unchanged creation-time combat seed, active side A, revision and first 15-second deadline; promote accepted rows to `locked`; expire only unanswered/invalid invitations; set battle flags for every locked member; change engagement to converted; commit once. Do not call the old helper that expires every accepted row. Populate runtime caches only after commit. Concurrent Join/Leave/escape/start sees either preparation or the complete locked state, never half-built sides. Transient database failures roll back and retry through the same due-event service; do not expire a viable preparation. Corrupt roster/source evidence cancels only the verifiably owned unstarted commitments with a recovery notice, never constructs a partial live battle.

#### 5.4.5 Real multiple-human side execution

Rehydrate `side_a_participants`/`side_b_participants` from the locked roster, not just attacker/defender columns. All living active members of the current side may submit one order during the same **15-second** side window; resolve early only once every eligible actor has committed. Deadline fills each missing order with existing timeout Guard. Resolve the **entire** stable runtime batch, not its first entry. Each action uses its actor, the full current same-side/opposite-side entity arrays and selected legal target with `pve_passives_enabled=False` on every PvP snapshot. Current normal, Guard, Power Strike, Quick Shot, Fireball and Smite are the complete supported action set. No new skills, coefficients or group damage multiplier.

Advance affected-side effects **once after the complete side batch**, not once per actor. Keep deterministic per-order seeds and current cooldown/opportunity rules. Dead actors cannot act or be targeted. An order whose target died earlier in the batch becomes a logged no-cost Guard fallback; do not retarget or spend skill MP. Use the shared action→target UI. A submitted actor waits for their teammate, not a single principal `turn_owner`. Existing legacy role fields may be rendered for version0 only; version1 decisions use participant maps and active side.

The shared order authorization must admit any living locked participant on the current side, and reject invited/unaccepted/left/dead/outsider actors. A matching accepted invitation alone is insufficient after lock. One side becomes defeated when none of its locked actors remain alive; evaluate this after each resolved batch including its affected-side effects. Both empty means draw; otherwise the surviving side wins. No fresh roster entry can occur during active combat, including at round boundaries.

Update every PvP lookup and delivery wrapper, not only runtime creation: `get_pending_player_engagement`, reinforcement lookup, busy/mobility checks, manual-action labels, location renderer and `bot.pvp_tick` event recipients must use version1 membership/actor status. Broadcast preparation/start/side updates to the relevant committed members; after defeat send that actor their personal result and hub context, not a new combat prompt. A live teammate's card must not disappear when the original principal dies. Public viewers see status only on their own refresh.

**Active PvP has no voluntary flee operation in this bounded delivery**, preserving the current live PvP action surface. Preparation allies can Leave and principals can attempt the existing escape; after lock the UI removes those actions. A stale preparation Leave never becomes a guaranteed active escape. PvE keeps its existing active flee. Disconnect does not remove a PvP actor or exempt them from damage; missing orders use timeout Guard. Future active PvP retreat is deferred rather than invented as a cost-free death/loss bypass.

#### 5.4.6 Participant-specific crime, death and economic settlement

Freeze source legal snapshots before applying this encounter's flags. Original initiation uses the current legality/red-flag/infamy policy once in the create transaction. Each accepted initiator ally is treated as a co-aggressor against the **original defender's initiation snapshot**, using current `should_apply_red_flag` and `resolve_illegal_aggression_infamy` with their own pre-accept state and retaliation context; apply only the current-policy charge, once at acceptance. No duplicated charge at lock, restart or Leave. Defender allies receive no initiation crime merely for helping. Existing red flags/infamy are never cleared by participating or leaving.

Keep a deterministic cumulative **actual HP damage by source actor and victim** map in the existing battle JSON, including DOT source attribution and excluding overkill. For each defeated actor, credit the opposing locked actor with greatest cumulative damage, ties by locked roster order. This credit is for crime/log attribution, **not exclusive loot ownership**. New-version snapshots/effect sources must identify their locked source; invalid provenance blocks consequence settlement for recovery instead of guessing a killer.

A side-result write and every newly defeated participant's consequence receipt commit together under one SQLite writer. Before any next side or player action, apply each defeat exactly once: remove the actor from live eligibility, preserve its dead combat snapshot, debit its own vulnerable inventory once into a **receipt-backed encounter loss pool**, set their authoritative mana to remaining snapshot mana, respawn at their existing regional hub with **30% of current stored base max HP (floor, minimum1)**, clear their battle/activity flags, advance normal travel/visit revisions and apply **8-minute respawn protection**. Other actors remain in battle. The defeated account can recover/play in the hub and cannot rejoin this encounter. Gear, tools, protected items, character/profession/skill progress are never debited by this new loss pool.

For each defeated participant, retain current regional loss fractions: guarded **50%**, frontier **60%**, core-war **70%**, safe0 (new encounters cannot start there). Use current `resolve_item_death_vulnerability`. Freeze their aggregate current item quantities and prior30-minute repeat-kill counts against every opposite locked actor before this encounter's log rows. Scale is1 if the maximum prior pair count is0, .5 if1, .25 if≥2. Debit **`floor(quantity * regional_fraction * scale)`** once per vulnerable item, aggregating duplicate stacks. Loss does not multiply by opponent count. The pool records exact quantities and is not another inventory or ground-loot system.

At individual defeat, write one existing `pvp_log` pair row for the credited actor/victim and apply `resolve_kill_infamy_delta` once to a credited initiator-side actor, using that co-aggressor as initiator, original defender's frozen legal snapshot, and their victim-pair repeat count. Defender-side credited kills receive no new aggression infamy. Retain the current helper's numerical base/repeat/retaliation rules; do not charge every teammate for someone else's kill. Existing initiation charges are separate and never refunded. Orient log attacker/defender columns by sideA/sideB so retaliation queries retain their meaning. Record emitted log identity and crime amount in the participant receipt.

At terminal settlement, eligible loot recipients are **living, nondeparted members of the winning opposite side with at least one accepted manual combat order** (manual Guard counts); defeated players, outsiders, unaccepted/left allies and fallback-only accounts receive nothing. For each losing-side victim's pool and item, divide quantity equally among eligible recipients: base `floor(Q/N)`, then one extra to the first `Q mod N` recipients ordered by ascending SHA256 of `(combat_seed, victim_id, item_id, recipient_id)` using canonical JSON array UTF-8 encoding, numeric IDs and lexical digest order. No final-hit priority and no per-recipient copy of the entire pool. With no eligible recipient, a draw, or a victim on the winning side, the pool is recorded as destroyed; no item minting or refund. The sum granted plus destroyed equals the original debit for every item.

For each victim/eligible-recipient pair not already logged for credited damage, add one zero-XP/zero-gold `pvp_log` relationship row in aggregate settlement, preserving per-pair repeat deterrence for shared loot; do not duplicate the credited pair. This supplies existing repeat/retaliation readers with explicit relationships instead of a synthetic team ID. Terminal receipt records these pairs and all grants/destruction. The number of log rows is not the UI count of deaths: participant receipts count actual deaths once.

PvP creates **no new character XP, minted gold, weapon mastery, hunting/Chapter kill credit, RAV monster/project credit or harvest entitlement**; current PvP gives no such victory progression. Per-player result displays their own damage/death/loot/loss/crime outcome. Survivors retain exact snapshot HP/MP and are released once. Use new bounded consequence receipts described in section15 because the current terminal table's non-null single winner/loser cannot truthfully represent four actors, individual respawns and draws. Both versions remain under the existing PvP owner, not a parallel combat system.

#### 5.4.7 Stale actions, restart and migration

Every Invite/Accept/Decline/Revoke/Leave/escape binds requester, engagement, reinforcement row if relevant, operation and state revision through existing durable UI intents; successful pure membership operations store immutable outcomes in existing `economy_action_receipts` under `pvp_membership_pxe1`, and escape under `pvp_prep_escape_pxe1` (schema1/catalogue2, zero economic award). Replay those receipts before mutable state checks. Join must validate the principal-issued invitation, not just a client side string. Accepted counts/Join states are rebuilt from authority after stale clicks. No old callback can enroll into a newer engagement or change a locked side.

After restart, resume original preparation deadline and accepted commitments; do not add300seconds or expire accepted allies merely because the process restarted. Due preparations lock once; pending future invitations remain available. Rehydrate active roster, side deadlines, actor statuses and committed orders; resolve at most one overdue side before giving the next its normal fresh15seconds. Resume every participant's UI, including a reinforcement. Group terminal recovery queries version1 terminal side results and its group receipt; it cannot rely on the legacy result's singular `winner_id`. Per-defeat receipts prevent double respawn/debit/crime; aggregate receipt prevents double pool distribution. A receipt/inventory/flag failure rolls back together. A Telegram failure never releases membership or changes deadlines.

Cutover keeps **already-live version0 PvP** on its historical locked 1v1 path with original receipts/actions; no reinforcements are inserted mid-combat. Pending old engagements upgrade to version1, retain the original deadline, and mark old pending/accepted reinforcement rows expired with a localized re-invitation explanation: historical self-join does not prove the newly required principal approval. A coherent legacy `active` preparation row with no initialized live battle is treated as pending for this migration; an actual initialized live payload remains version0. Assign a seed only if none exists. New approved invitation rows use membership_version1 and may be accepted before the retained deadline; an overdue preparation starts with eligible principals only. Preserve historical rows and legal state. Cancellation or invalid startup releases all verifiably linked accepted commitments and produces a recovery notice; unknown cross-encounter ownership never authorizes a release.

#### 5.4.8 Telegram examples

```text
⚔ Danya versus Mara · Hills
Preparing · 2:14 remaining
Danya's side 1/2 · Mara's side 1/2
Mara invited you to help defend.
Risk: PvP defeat can lose field materials.
[Join Mara's side] [Decline]
[Participants] [Back]
```

```text
⚔ Danya versus Mara · Hills
Preparing · 0:42 remaining
Your side: Danya, Alex · 2/2
Other side: Mara · 1/2 · 1 invited
You joined Danya's side.
[Leave preparation] [Participants]
[Location]
```

```text
⚔ Danya's side versus Mara's side
Battle in progress · roster locked
2 versus 2 · Round 3
Your side · 11s · 1/2 orders ready
[Resume combat] [Participants]
[Battle details] [Location]
```

```text
⚔ Encounter resolved
Mara's side won · 1 survivor
You were defeated and returned to Elmor.
Lost: Common wood ×4
Respawn protection: 7:58
[Your result] [Location]
```

Uninvited viewers see `[View participants]` and the localized invitation-required explanation. Principal preparation detail uses `[Invite ally] [Attempt escape]`; a full side replaces Invite with Participants. An active outsider sees View status rather than Resume. Counts and countdowns always come from persisted membership/deadlines.

### 5.5 Compact combat action contract

PvE home: Attack, Skills, Guard, Supplies, Flee, Details. Active PvP home: Attack, Skills, Guard, Participants and Details; no unsupported live Flee or Supplies action. PvP preparation uses its separate invitation/escape/Leave controls. Skills lists at most six learned supported actions per page, each once, with rank and MP/cooldown; unavailable skills open an explanatory card rather than a committing token. Selecting a skill/action is **read-only**. Single-target actions always open valid-target choice, even when only one target exists. Self/party/pattern actions open one compact “Use” confirmation with their resolved scope. No selection spends MP or extends the side deadline.

Final target/Use invokes existing `issue_combat_intents`/durable order validation bound to actor, encounter, turn revision and deadline. Recheck ability, MP, cooldown, target life/membership/pattern. Invalid targets disappear on refresh; no silent retargeting after a stale choice. A timeout while choosing falls through current fallback and opens current status. Consumed duplicate orders return existing acknowledgment; conflicting second orders reject. Supplies retain current per-turn limits and atomic consumption. Battle Details holds full enemy/ally/status/log pages; last-resolution summary shows at most three meaningful lines.

## 6. Exact travel contract

### 6.1 Routes and prices

**Adjacent ordinary travel:** one canonical graph edge, **15 seconds**, zero gold; undiscovered adjacent destinations are legal. **Discovered long-route travel:** destination and every node of the chosen route must already be discovered. Find minimum-hop path on that induced discovered graph, using canonical neighbor order to break ties; do not use unseen nodes as a shortcut. If no discovered route exists, offer the next adjacent exploration step.

For `h ≥ 2` edges:

`T_long(h) = 15h + 3(h−1) seconds`.

The first edge costs 15 seconds; every subsequent edge costs 18. The extra 3 seconds is road-following convenience overhead, not a gold toll. No movement speed/build modifier is introduced. Preview freezes path, class, duration and topology version; start revalidates discovery, origin, legal state and travel revision. A changed route requires a fresh preview.

| Trip | Normal manual total | Discovered direct total | Current old direct |
|---|---:|---:|---:|
| 1 edge | 15s | Adjacent class: 15s | 15s |
| 2 edges | 30s | 33s | 90s |
| 6 edges | 90s | 105s | 270s |
| 10 edges | 150s | 177s | 450s |

**Elmor → Aster:** `hub_westwild → westwild_n5 → westwild_n4 → westwild_n3 → westwild_n2 → westwild_n1 → capital_city`, six edges; **1:45** direct versus **1:30** separate walks, replacing **4:30**. No teleport interpretation.

**Safe-hub teleport:** remains **disabled in PXE1**, with no active button, fee debit or new DB state. Preserve deferred design: only Aster/five safe hubs, physically discovered destination, from a safe hub, never during combat/PvP mobility lock; 20 gold capital↔hub and 35 hub↔hub remain historical proposed prices. Future activation needs its own accepted contract. The three classes are distinct even though only the first two are live.

### 6.2 Durable progress and cancellation

Start creates one running `player_travel_sessions` row and increments `players.travel_revision` in one transaction. `players.location_id` remains the last reached node; a player is present and vulnerable there while traversing the next edge. At each completed edge, the same service atomically updates location/discovery, completed-edge count, travel revision and next deadline. No speculative intermediate discovery. Open-world security and return-hub behavior continue to use current canonical location.

Cancel first reconciles due work through server cancellation time, then sets `cancelled`. End at **the last fully reached node**; partial edge progress is discarded. No teleport home, fraction stored, fee, refund or cooldown. A new trip pays its own full first-edge time. If final arrival already committed, cancel returns arrived. Each operation targets the exact session ID; an old Stop cannot cancel a newer session.

One active trip per player. Travel blocks new gather/craft/shop/gear/reset/quest mutations and voluntary encounter initiation/join. Read Map, Journal, Inventory, Character and recipe/source previews remain available. Spending already-earned attributes is allowed under section 13. Starting travel while gathering offers Stop gathering and then a fresh destination preview; never auto-stops and starts in one ambiguous click.

Restart resumes the persisted route, not an old coroutine. If an edge deadline passed while the bot was down, settle **at most that edge**, process its arrival hazard/context, then schedule the next edge from current server time. No multi-edge offline catch-up. UI recalculates ETA and says “Journey resumed.” A future deadline remains unchanged. Terminal/invalid journeys never resume; a changed or missing edge interrupts at last valid node, preserving completed discovery. Replays never increment location/revision twice.

### 6.3 Risk, scheduling and feedback

The 1-second world job processes travel, gathering and location threats through their domain services. Due events for one player are serialized under SQLite; event time order is authoritative, and a threat wins ties against a travel arrival/gather tick. This prevents a delayed worker from catching travel up past a threat that should have interrupted it.

Replace process-local location aggro tasks with `player_location_threats`: on a **real location arrival**, freeze one delay per eligible aggressive mob using the current inclusive **5–60 second** uniform rule, location/visit revision and character-level eligibility (`player.level ≤ mob.level+1`). A new `players.location_visit_revision` increments only on actual location changes; starting or cancelling travel does not change it. No new mob or extra roll on refresh. On threat due, revalidate location/visit, life, combat and level. If still legal, interrupt active travel/gather and reserve a real available canonical spawn into 12-second forming PvE with the enemy-first policy. If none is available, dismiss that threat; never make a private duplicate. Leaving the node makes old threat rows stale. Cancel at the same node does not reroll threats or provide protection. Startup processes pending threats rather than granting a new grace period.

PvP initiation against a travelling/gathering target follows existing legality first, then atomically interrupts that target's activity and creates the engagement. A voluntarily travelling/gathering attacker must stop first. No activity grants PvP immunity.

Edit the activity card at each edge and at most once every 10 seconds while visible, plus terminal transitions. Remaining time is calculated from authoritative deadlines whenever opened. Arrival produces one compact line with location name and, if relevant, ready turn-in CTA; otherwise the Location card. Route prose uses localized `pxe1.travel.flavor.<route_id>` and a neutral cross-route fallback, never lowercased destination descriptions. Queue/coalesce transport updates; Telegram failures cannot roll back location or restart a trip.

## 7. Exact gathering session contract

### 7.1 State and time

Environmental gathering covers **woodcutting, mining, herbalism and fishing**. Hunting remains the bounded post-victory action in section 8; it is not an inexhaustible location session.

State machine: `running → completed | cancelled | interrupted | broken`. Terminal states never return to running. A new explicit Start creates a new ID. No automatic restart, continuation queue, standing order or “repeat forever” button.

Start requires a living registered player, no forming/active combat or pending PvP engagement, no running travel or gathering, a current-location source for the selected profession, at least one source entry meeting both profession and tool gates, and a matching equipped tool with durability ≥1. Start costs no resource, gold or durability. All checks and insertion occur under one write transaction; the unique running-session index prevents two starts. Replaying the same start intent returns its session, even after it ends. A distinct Start while running opens the current session instead of creating another.

**One tick every 8 seconds, first tick after 8 seconds; maximum 120 seconds and 15 attempted ticks.** Maximum yield is **15 units total**, never 15 of each resource. If tool durability is `d`, the initial maximum number of attempts is `min(15,d)`; no repair/replacement can extend a running session. Full duration is shown as 2:00, with an earlier tool-exhaustion warning if applicable. The final due tick at exactly 120 seconds is eligible, then the session ends.

### 7.2 Roll, yield, XP and wear

Freeze the canonical location source rows filtered to the selected profession, in existing order, with their **unconditional** probabilities. Do not renormalize after filtering inaccessible resource tiers. Generate `u ∈ [0,1)` and select the first cumulative probability interval containing it; remainder is no find. A selected but profession/tool-locked resource also yields zero. Do not reroll, choose a lower resource, multiply yield by level, or award failure XP. One successful eligible result grants exactly **one** current item ID and the existing gathering XP formula in section 9. Profession level may advance within a session; evaluate its current value before each tick. Tool tier is fixed because replacement is prohibited while running.

Example, Old Mine mining: iron 65%, coal 30%, gem 5%. A tier-1 pick produces a gem-related failed attempt in that 5% interval, not 68.42% iron after normalization. At tier 3 and mining level 12, all three become eligible. The same rule applies to existing multi-profession source rows; each profession uses its own source list without normalization.

Persist a cryptographically random 128-bit seed once at start as 32 hex characters. Decode to the original **16 bytes**. For tick `i=1..15`, compute `SHA256(seed_bytes || b":gather:" || ASCII(decimal_tick_index))`, using unpadded decimal indices. Interpret the first **8 bytes as unsigned big-endian** integer `n`. Store probabilities as integer basis points (65%=6500); select the first cumulative interval for which **`n*10000 < cumulative_basis_points*2^64`**. This exactly defines the conceptual `u=n/2^64` without floating-point ambiguity. The schema-1/catalogue-2 source snapshot stores the profession and ordered entries of item ID, chance in basis points, required profession level and required tool tier. Filter by profession, never remove/renormalize locked resources. Algorithm version is 1. A crash retry cannot choose a different roll; no process-global RNG dependency.

**Every committed attempt consumes 1 durability**, including failure or a locked outcome. Wear cannot be negative or exceed remaining durability. At durability 1, the tick can succeed, wear reaches 0 and the session becomes `broken`; the awarded resource stays. No future tick executes. Tick order in one transaction: receipt replay check → validate session/location/life/activity/tool → deterministic roll → apply inventory/XP/objective credit → wear → update counters/deadline/state → persist receipt and feedback facts → commit. Each tick increments the tool revision and updates the session's expected tool revision atomically. Tick validation recognizes its own running session rather than rejecting it through the generic competing-activity guard. The whole transaction rolls back together on failure.

Use receipt kind `gather_tick_pxe1`, key `gather:<session_id>:<tick_index>`, payload schema 1. Store exact item/quantity, XP, profession before/after, tool revision/durability, objective deltas and resulting session state. A duplicate worker returns this receipt; it cannot regrant or re-wear. Existing instant-gather receipts keep their original payload and replay path. New old-style Gather callbacks open a session preview and grant nothing instantly.

### 7.3 Stop, interruption and recovery

Stop addresses one exact session. Reconcile ticks due **at or before the server receipt time of Stop**, with earlier hazards first, then cancel. Keep all committed yield, XP and wear; no partial tick result or partial wear. If it already ended, show that terminal summary. A stale Stop cannot stop a later session.

While gathering: read-only navigation and spend-only attributes are allowed. Travel, a new gather, craft, tool change/repair, shop transactions, equip/use outside combat, resets and quest claims are blocked until Stop. Gathering never relocates the player. Voluntary battle/join requires Stop; hostile aggro or a legal incoming PvP engagement atomically interrupts the session before reserving combat. Death interrupts before existing death/loss settlement; PXE1 adds no extra resource loss. Already-earned resources remain subject to the existing death policy, not special protection.

Logging out of Telegram is not a server event. A running server continues this finite session, including normal danger, for at most 120 seconds. **At process startup, all previously running gathering sessions become `interrupted` before workers accept input.** Preserve committed ticks; grant no offline/overdue ticks and do not deduct missed wear. “Gathering stopped when the game restarted; kept …” appears on the next visit. Do not resume from a cached coroutine. This deliberately differs from travel recovery.

If the live worker stalls briefly, process due events in chronological order, with the section 6 threat tie-break; there are at most 15 ticks to reconcile. Expired terminal sessions cannot produce a sixteenth tick. A transaction failure retries the same tick/seed. Invalid source snapshot or missing tool interrupts without granting that tick and records an operator diagnostic; the player sees localized recovery copy. One bot process owns startup and scheduled work; PXE1 does not introduce a multi-instance deployment model.

### 7.4 Presentation and economic limits

Use one activity message showing profession/location, gathered totals, total XP, durability, remaining time, Stop and Location. Edit at committed ticks (at most once per 8 seconds), coalescing multiple overdue updates, and at terminal transitions. Failures update time/durability without a new “failed” chat message. A hidden activity surface need not push every edit; opening it reconstructs authoritative totals. The terminal summary includes at most two quest changes and one next-action CTA.

Free T1 tools start full. Chapter I resource quantities, probabilities, objective scopes and recipe costs stay unchanged. Journal sources prioritize the legal high-probability source within the objective's allowed locations; for Caravan wood, Copse's 40% is preferable to the 15% roadside source if reachable. No pre-tutorial crafting, paid tool purchase, extra tutorial resource quota or special farmable pity reward is added.

Finite duration, finite wear, one activity, local risk, access gates and explicit fresh Start bound unattended output. This is economic friction, **not a claim that scripted accounts can be eliminated**. No CAPTCHA, premium bypass, renewable free-tool button or background auto-repeat. Environmental nodes remain renewable; no global depletion table or per-account daily quota is introduced.

## 8. Exact tool and durability contract

### 8.1 Representation and access

Tools are **special profession equipment**, one dedicated slot per gathering profession. They are not `items`, stack inventory, combat gear instances or weapon mastery families. `player_profession_tools` is their sole owner; Inventory → Tools and Activities → Tools are two views of the same five rows. No tool combat stat, weapon restriction, enhancement, salvage, sale, transfer, durability stacking or spare-tool bag is added.

| Profession | Tool | Crafting profession | Tier 1 / 2 / 3 / 4 access level |
|---|---|---|---|
| Woodcutting | Axe | Blacksmith | 1 / 6 / 12 / 18 |
| Mining | Pick | Blacksmith | 1 / 6 / 12 / 18 |
| Herbalism | Sickle | Blacksmith | 1 / 6 / 12 / 18 |
| Fishing | Rod | Arcane engineer | 1 / 6 / 12 / 18 |
| Hunting | Skinning knife | Blacksmith | 1 / 6 / 12 / 18 |

Normal extraction requires **current profession level ≥ resource.required_level**, **tool tier ≥ resource.tool_tier**, physical presence at its canonical source, legal activity state and durability. A higher tier supports **every lower tier**; there is no penalty to low-tier yield or XP beyond existing profession relevance. Character level is not a synthetic extraction requirement; world danger, geography and combat remain real constraints. Crafting a tool additionally requires its crafting-profession level, recipe knowledge, guild access and inputs. Crafting and gathering profession levels are separate.

Capacity is **`60 × tier`**: 60, 120, 180, 240. Tools have no hidden quality roll. Tier names are Starter, Regional, Expert, Master, each properly localized. Tool and resource tiers are explicitly labelled to distinguish them from level-100 combat gear tiers.

### 8.2 Acquisition, replacement and repair

New players receive all **five T1 tools, full durability, free once** as part of starter provisioning. Reveal the relevant tool when the Chapter first uses it; do not add five modal messages. Existing players receive the same five rows at migration, regardless of Chapter/profession progress, without changing the existing starter-kit record. Both paths use insert-if-missing only; `/start`, language changes and kit replay never refill or replace a tool.

Basic T1 replacements cost **12 gold each**, full durability, available in **all six existing safe hubs**. Use ordinary Shop → Starter tools where a general shop exists; at other hubs expose the same small Tools service under Services/Guild without pretending there is a full shop. No faction, level or quest prerequisite. No higher-tier vendor tools and no NPC buyback.

T1 tools **cannot be repaired**. Buy or craft a replacement. T2–T4 are repaired at any guild, using missing durability `m=capacity−durability` and tier `t`:

| Cost | Exact integer amount |
|---|---:|
| Common wood | `ceil(m*t/60)` |
| Iron ore | `ceil(m*t/120)` |
| Coal | `ceil(m*t/240)` |
| Gold | `ceil(m*t/20)` |

For `m=0`, no-op with zero costs and no receipt reward. Ordinary material-funded repair consumes the complete listed materials and base gold, restoring full capacity with no XP, permanent capacity loss or random failure. Example T2 at 24/120: **4 wood + 2 iron + 1 coal + 10 gold** restores 96. A fully broken T4 consumes **16 wood + 8 iron + 4 coal + 48 gold**. Repair does not consume or recreate a gear item.

If repair materials are insufficient, offer **guild-assisted repair** at the same guild. For each material `i`, `used_i=min(owned_i,required_i)` and `missing_i=required_i-used_i`. Exact total gold is **`base_gold + 3*sum(missing_i*baseline_sale_price_i)`**, using wood3/iron6/coal4 gold. Consume the quoted owned materials and total gold, restore full durability, grant zero XP. Guild-supplied materials are consumed directly and never enter inventory, objectives or a saleable output. No cancellation can extract them. With no materials, a broken T2 costs **96 gold**, and a broken T4 **384 gold**. A T2 at24/120 with2wood/1iron/1coal consumes those materials and **46 gold**.

The assisted preview shows exact consumed/supplied quantities, total gold and restored durability. Any changed inventory/tool revision or quote requires reconfirmation. Reuse `tool_repair_pxe1` with `repair_mode` (`materials` or `assisted`), exact quantities and price in the hashed intent/receipt, in the existing repair transaction; no new table/column/recipe. Assisted repair is only for damaged T2–T4 tools missing materials, outside all activities/combat. This prevents a maintenance deadlock when all higher-tier tools are broken and no repair materials remain, while the no-downgrade rule and costly gold recovery remain intact.

Crafting creates a full tool directly in its profession slot. First show the existing tool/tier/durability and the exact replacement. A fresh confirmed intent binds its revision. Same-tier replacement is legal; lower-tier replacement is disallowed when a higher-tier tool exists. Higher-tier replacement is an upgrade. The old tool is consumed with no salvage only in the committed craft transaction. No additional equip step or duplicate item grant. A T1 purchase cannot overwrite a T2+ tool; route to repair instead. Repair, purchase and crafting are disallowed during any running activity/combat.

When crossing from above 20% to **≤20% durability**, append one warning to the current result/activity card. Repair/replacement above 20% permits a later crossing warning; repeated reads do not send more. At 0, keep the broken tool row and tier; do not delete it or destroy progression. Show nearest safe hub, exact replacement/ordinary or assisted repair costs and ingredient sources. Free travel, normal combat and ordinary combat loot/sale remain available without a gathering tool. Earning 12 gold permits T1 replacement; a higher-tier tool instead requires its exact ordinary or premium assisted-repair quote. Thus zero materials cannot create an impossible extraction dependency. No unlimited emergency grants.

### 8.3 Hunting integration

Preserve the applied settlement's existing **owner-only**, eligible-survivor, canonical-location, **1,800-second** and one-claim conditions. The selected harvest is still **one unit total per eligible owner/encounter**, not one per enemy, one per participant or unlimited pack carcasses. Current deterministic option deduplication remains. RAV participation/objective credit is independent and is not silently made owner-only.

Eligible harvest now additionally requires a hunting knife of sufficient tier/level and ≥1 durability. Successful harvest atomically grants one resource, current hunting XP, quest credit and its existing durable claim while consuming **1 knife durability**. Failure of any prerequisite consumes neither entitlement nor wear; no RNG or timed session is added to this already combat-bounded action. A last-durability harvest succeeds and leaves a broken knife. Concurrent different-choice clicks compete for the same claim. An existing pre-upgrade claim replay returns its historical result and consumes no new wear. Old unclaimed rewards remain claimable within their original expiry, now using the additive starter knife.

### 8.4 Recipe and migration policy

Twenty recipes (five tools × four tiers) use the costs and bootstrap path in section 10. T1 recipes are permanently granted with starter provisioning; returning players get the five knowledge rows with the existing `grandfather` acquisition reason. T2/3/4 knowledge is bought once at guilds for **25/75/150 gold**, at crafting levels **6/12/18**. New accounts have 22 starter recipes instead of 17; no existing knowledge is removed. Capacity derives from immutable tier metadata; no per-tool catalogue or additional item IDs are required.

## 9. Exact profession XP contract

### 9.1 Thresholds and craft award

Both profession systems retain level cap **20** and **`XP_to_next(L)=50L`**. Total XP from level 1 to level `L` is **`25L(L−1)`**: 50 to level 2, 500 to 5, 750 to 6, 2,250 to 10 and 9,500 to 20. Character level and weapon mastery progression are not changed.

For a successful crafted unit, let `r` be the recipe's required crafting level and `V` the sum of its consumed ingredient quantities times their frozen current NPC material sale prices. XP policy 2 snapshots `V` as recipe metadata; future price changes cannot silently rebalance XP. No market or player price input. For the 20 tools use the normal recipe's `V`, including when a bootstrap commission is used.

**`B = min(10 + 5r, V)`**. Active recipes must have positive integer `V` and quantity-one outputs as currently defined. Let `g = current_profession_level − r`:

| Relevance | Multiplier implemented with integer division |
|---|---|
| `g ≤ 2` | `B` |
| `3 ≤ g ≤ 4` | `max(1, floor(B/2))` |
| `g ≥ 5`, below training ceiling | `max(1, floor(B/4))` |
| At or above recipe training ceiling, or level 20 | 0 |

Training ceilings remain **6 for r=1 or 2, 12 for r=6, 18 for r=12, 20 for r=18**. Clip positive XP to the XP still needed to reach that ceiling. Compute from the pre-craft level/XP; one unit has one award and cannot borrow the next relevance bracket partway through. Apply the existing carry loop. A successful craft with zero XP remains legal and produces its item/tool, with “Useful item; no profession XP at your level.”

Every fresh craft consumes its full ingredients and uses this rule. Repetition has **no first-craft multiplier, first-of-day reset, hidden counter, escalating failure or account-wide fatigue**. Its diminishing return is the explicit level gap and eventual training ceiling. Learning, previewing, failed craft, receipt replay, buying, repairing and selling grant zero craft XP. An objective completion adds no unlisted profession milestone XP. Level-up feedback is one compact event listing new level and newly accessible recipe band; it does not grant recipes automatically except the existing starter knowledge.

### 9.2 Concrete progression

Independent integer arithmetic, starting at level 1 / 0 XP and repeating one recipe:

| Recipe | Raw material value `V` | Full award `B` | Crafts to level 2 | Crafts to level 5 | Crafts to level 6 | T1-only to level 10 |
|---|---:|---:|---:|---:|---:|---|
| Trail Vest | 22 | 15 | 4 | 49 | 85 | Impossible; stops at 6 |
| Field Tonic | 9 | 9 | 6 | 83 | 145 | Impossible; stops at 6 |
| Field Ration | 8 | 8 | 7 | 87 | 150 | Impossible; stops at 6 |
| Any T1 tool | 28 | 15 | 4 | 49 | 85 | Impossible; stops at 6 |

These are production counts, not a requirement to manufacture useless copies. Quest crafts remain one unit with their original rewards; the player can mix useful recipes. At level 6, moving to meaningful r=6 work is required to continue efficiently. For example the existing medium helmet consumes 2 pelts + 1 dark wood + 1 fang (`V=38`, `B=38`), rewarding 38 XP at levels 6–8, then 19 at 9–10. Starting at level 6 / 0 XP, **51 helmets** reach level 10 / 1 XP. Thus one explicit level 1→10 medium-armor route is **85 vests + 51 helmets = 136 crafts**, plus learning the advanced recipe and supplying its materials. It cannot be replaced by 136 cheap starter crafts.

Current `250*r` gives a level-1 craft **250 XP**, moving a fresh profession to **level 3 / 100 XP**. Three r=1 crafts reach level 6; the current tested 3+2+2+1 crafts across bands can reach level 20. PXE1 removes this acceleration deliberately. The price cap prevents an 8-gold ration from giving the same 15 XP as a 22-gold vest. Higher bands retain meaningful XP and access beyond earlier ceilings; no reset is needed to benefit.

### 9.3 Gathering XP and existing players

Gathering keeps its existing successful-unit rule: **`B_g=8+2r`**, full for `current_level−r ≤4`, half (floor) at gap 5, zero at gap ≥6 or level 20. Failure yields zero. Thus required levels 1/2/6/8/12/18 have full awards **10/12/20/24/32/44**. Tool tier does not multiply XP. A failed locked gem tick earns zero mining XP. Existing owner-only harvest uses the same formula for hunting.

The migration copies/reuses current profession rows exactly: **no level reset, XP wipe, demotion, mass recalculation, skill reset or retroactive fee**. Knowledge, inventory and previously earned unlocks remain. A level-20 player can immediately work toward a high-tier tool without retraining, but is not gifted a T4 tool. Existing unusually large nonnegative XP is preserved; on the next positive authorized award, the existing carry loop may normalize it into levels and apply its existing level-20 cap behavior. Zero-award actions must not normalize/rewrite rows. Structurally invalid data violating existing range/identity contracts is reported for recovery, not silently zeroed. Old craft receipts replay their old XP/output; only a new action uses policy 2. There is no repetition ledger or new profession-progress table.

## 10. Resource economy and low-tier sink contract

### 10.1 Smallest resource model

Keep all existing item IDs and inventory quantities. Add static `resource_tier`/`required_tool_tier` metadata to the current resource authority, not a parallel runtime resource table and not hundreds of quality variants. Regional identity stays in source placement and existing IDs. For the 28 PEV1 resources, tier follows their established required-level band:

| Tier | Exact current IDs | Required level policy |
|---|---|---|
| 1 | `herb_common`, `shore_herbs`, `forest_mushroom`, `reed_bundle`, `wood_common`, `iron_ore`, `coal`, `stone_chunk`, `shore_fish`, `boar_meat`, `wolf_pelt`, `wolf_fang` | Existing values: 1 except fang 2 |
| 2 | `marsh_herb`, `herb_magic`, `wood_dark`, `salt_crystal`, `marsh_fish`, `spider_silk` | Existing 6, except magic herb 8 |
| 3 | `desert_plant`, `frostpine_wood`, `gem_common`, `oasis_fish`, `bear_hide` | 12 |
| 4 | `toxic_herb`, `ancient_bark`, `sunscar_ore`, `deep_marsh_fish`, `troll_sinew` | 18 |

The already-placed legacy `dry_reagent` and `marsh_mushroom` remain herbalism resources at existing fallback level 1, now explicitly marked tool tier 1. Do not change their inventory identities or pretend they are newly introduced PEV1 mandatory resources. Unknown historical inventory remains displayable/sellable under its existing metadata; it does not automatically become a gather source.

### 10.2 Frozen cross-tier tool recipes

For each tool profession `p` and tier `t=1..4`, recipe ID is `pxe_tool_<p>_<t>`. Its exact output variant is `{"kind":"tool","profession_key":p,"tool_tier":t,"quantity":1}`, with **no inventory item ID**. Validate mutually exclusive gear/consumable versus tool output variants. Crafting delegates tool installation only to `profession_tools.py` and never additionally invokes ordinary item delivery. Replacement/upgrade preserves the slot's commission-use mask; exceptional mask recovery consults committed commission receipts, never resets eligibility. Required crafting level is 1/6/12/18. All five tools share this material curve: wood for body/handle, iron for head/fittings, coal for forging, and progression materials for reinforcement. No fictional combat item is inserted as a tool proxy.

| Ingredient | T1 | T2 | T3 (mid-tier) | T4 (high-tier) |
|---|---:|---:|---:|---:|
| Common wood | 4 | 12 | 36 | 108 |
| Iron ore | 2 | 8 | 18 | 32 |
| Coal | 1 | 2 | 3 | 4 |
| Dark wood | 0 | 2 | 4 | 6 |
| Frostpine wood | 0 | 0 | 2 | 4 |
| Common gem | 0 | 0 | 1 | 2 |
| Ancient bark | 0 | 0 | 0 | 2 |
| Sunscar ore | 0 | 0 | 0 | 4 |
| Material NPC sale value | **28** | **112** | **315** | **778** |
| Crafting level / knowledge price | 1 / free | 6 / 25g | 12 / 75g | 18 / 150g |

For the supported four tiers, base wood is **`4×3^(t−1)`**, iron **`2t²`**, coal **`t`**, dark wood **`2(t−1)`** for t≥2, frostpine **`2(t−2)`** and gems **`t−2`** for t≥3, plus the fixed T4 bark/ore quantities. This is the complete PXE1 tier range; no T5–T8 rollout is implied by the scalable curve. Capacity grows linearly while initial material cost grows faster; the reason to upgrade is resource access and longer maintenance intervals, not an automatic low-tier yield multiplier.

The 63 existing active recipes, their input quantities, outputs, gear tiers and prices remain unchanged; add exactly **20**, for **83 active recipes**, retaining four inactive aliases. Existing high-band gear already mixes low and high materials. The new recurring repair sink adds low-tier demand without rewriting all gear balance. All prices in `V` use this baseline: wood 3, iron 6, coal 4, dark wood 10, frostpine 6, gem 35, bark 30, Sunscar ore 8 gold.

### 10.3 Circular-gate audit and explicit bootstrap

Without an alternate source, T2 axe needs dark wood that needs T2 axe; T3 axe/pick need frostpine and gems requiring T3 tools; T4 needs bark/ore requiring T4 tools. **Do not permit under-tier extraction, weaken the normal gate, or silently assume an existing player marketplace.** Existing ancient-bark combat drops are retained, but are not a universal bootstrap guarantee for every material.

Freeze one alternate path: **Guild bootstrap commission**, available only for **axe and pick**, once per player/tool/tier at T2, T3 and T4. The guild contributes the recipe's own-tier inputs directly to its crafting process; they never enter the player's inventory. The player pays all lower-tier inputs, **an additional twice the recipe's base common wood**, and **`20t²` gold**. Output, crafting XP and slot replacement use the same authoritative tool craft transaction. There is no separate vendor tool or loot grant.

| Commission | Player materials | Guild's immediately consumed contribution | Gold surcharge |
|---|---|---|---:|
| T2 axe or pick | 36 common wood, 8 iron, 2 coal | 2 dark wood | 80 |
| T3 axe or pick | 108 common wood, 18 iron, 3 coal, 4 dark wood | 2 frostpine wood, 1 gem | 180 |
| T4 axe or pick | 324 common wood, 32 iron, 4 coal, 6 dark wood, 4 frostpine wood, 2 gems | 2 ancient bark, 4 Sunscar ore | 320 |

Additional requirements: known target recipe, normal crafting level, corresponding gathering level 6/12/18, the exact preceding tool tier, and physical discovery of at least one **currently placed source for each contributed resource**. Discovery is existing visited-location state, not viewing the map. A currently available combat-drop location may satisfy a material's source visit only if it is an actual baseline source; the standard source resolver is authoritative. Show the missing source visits with travel previews. No extra random commission, waiting timer, quest chain or high-tier extraction exception.

Persist the three used bits on that tool's row; the bit is set in the same commit as debit/output/XP. It survives replacement, repair and any future tool-row recovery. A repeat request returns its receipt; a second fresh request for a used tier is rejected. Only woodcutting/mining rows can carry bits. Do not expose commission for sickle/rod/knife: after axe/pick upgrades their material inputs can be gathered normally. Ordinary crafting never needs a commission bit.

Constructive self-supply path: free T1 tools → gather starter inputs / raise blacksmithing and woodcutting to 6 → visit dark-wood source → commission T2 axe → gather dark wood → craft T2 pick and other tools. At level 12, visit frostpine and gem sources → commission T3 axe and pick as needed → harvest both normally → craft other T3 tools. Repeat for bark/ore at level 18. Lower-tier inputs remain obtainable with the preceding tools. Guild recipe knowledge and commission gold can be earned through existing combat/sales. This path has no dependency on an unimplemented trade system and every ordinary extraction respects adequate tool tier.

### 10.4 Sink strength, sale and inflation

An ordinary material-funded repair of a fully depleted T4 tool removes 16 starter wood, 8 starter iron, 4 starter coal and48gold: **160 gold of material opportunity cost plus direct gold combined** at current prices. Five such repairs remove80wood/40iron/20coal/240direct gold. Assisted repair consumes available materials and substitutes the exact premium gold sink for shortages; with no materials, five broken T4 repairs consume1920gold. Recipe learning, tool purchase and commission surcharges are further gold sinks. No repair generates XP or saleable output.

Keep current resource NPC sale prices and current ordinary shop stock. Tools have **no sale value or buyback**, so a 12-gold T1 replacement cannot be resold for its 28-gold craft inputs. No new NPC high-resource stock. The commission cannot be dismantled for its contributed materials. A higher-tier tool still consumes one wear per starter attempt, preserving starter-resource demand through both upgrades and maintenance.

No direct gold is minted by a gather tick; NPC sale is the existing conversion faucet. Conservative bound: 15 units × the highest current gather-material price of 35 = **525 gold gross per complete session**, before risk and costs, with no automatic next session. Actual source probabilities are much lower: Copse wood at 40% expects 6 units / 18 gold per 120 seconds; a T1 tool's 15 wear amortizes to 3 gold in replacement cost. Old Mine T1 mining expects `15×(.65×6+.30×4)=76.5` gross gold, with the locked gem interval still consuming time/wear. These are expected values, not guaranteed payouts. Do not promise equal profession profitability; balancing all regional prices is outside PXE1.

Implementation must validate existing craft→sell loops with the full baseline catalogue, especially output quantity, recipe aliases and tool output routing. Preserve the existing no-free-replay economy invariants. PXE1 adds sinks and bounded time; it does not add a market, taxes, auction house, resource quality rolls or resource decay.

## 11. Quest feedback contract

### 11.1 Facts and rendering

The current objective and settlement owners remain authoritative. Add a small **feedback fact projection**, written within the same transaction as the action, using the mutation's immutable receipt/settlement identity and player ID. It describes what changed; it is not another quest progress or reward ledger. Payload stores localization keys and typed values, never rendered text, so changing language works. Replaying an action returns its existing result/fact and cannot create a new completion event.

| Event | Exact player feedback | Transport and priority |
|---|---|---|
| Progress increment, still incomplete | `Common wood 2/3 (+1)`; at most two changed objectives, then `+N more · Journal` | Edit the triggering result/activity card; no new message or alert |
| One objective becomes complete | `✓ Gather common wood · 3/3`, then next incomplete objective in contract order | Same card; if no user-owned surface exists, one compact message after commit |
| All objectives become complete | `✅ <assignment> is ready · Turn in at <place>` | One compact result section; replaces weaker increment notification |
| Ready while at another place | `[Route to <place>] [Assignment]` | No illegal Claim button |
| Arrival at valid turn-in place | `✅ <assignment> can be turned in here` | Included in arrival/Location card, with top `[Turn in]`; no extra arrival popup |
| Claim committed | Existing gold/character XP/items, actual totals, completion title | Edit claim card; normal callback acknowledgment is non-modal |
| Next Chapter assignment unlocked | Localized next title and one-sentence hook, prerequisites already met | Same claim card with `[View next assignment]`; opening offers existing Accept, not silent acceptance |
| Chapter I final claim | Existing final rewards + immediate celebratory epilogue + open-world choices | One major narrative card; never gated behind later Journal navigation |
| Character/profession/mastery level up | Exact new level and at most two relevant unlocks | Coalesce within the action result; if several levels, show final level and Details |
| Stale/duplicate action | `Already completed` or `This screen changed; refreshed` | Short non-modal toast + current view; no duplicate reward message |

“Modal/major” here means a major **chat card**, not putting narrative in `query.answer(show_alert=True)`. Telegram alerts are reserved for a concise blocking condition when navigation cannot explain it. Routine join, equip, craft, sell, harvest and claim use an acknowledgment and result edit. Pure menu transitions silently acknowledge the callback.

Readiness is recomputed from the authoritative kill/objective state, including the currently equipped Trail Vest. The board must not substitute `0/0 kills` for a craft/sell assignment. Gear changes that remove a required currently equipped item can make an unclaimed assignment incomplete; show that state immediately. There is no permanent “equip once” credit unless the existing objective explicitly says so. A stale ready card cannot bypass claim validation.

### 11.2 Chapter flow and finale durability

Preserve, in order, the current four definitions: First Watch (2 rabbits, 3 herbs), Caravan (2 boars, 2 owner harvests, 3 wood), Outfitter (2 wolves, 2 owner harvests, craft vest/ration, currently wear vest), Homecoming (craft small health potion, sell one spare item). Preserve existing locations, prerequisites, XP/gold/items and the one active board-contract slot. “Next assignment” does not displace another active contract.

Final claim must atomically commit existing reward/history mutations and insert the unique event **`chapter_finale:chapter_homecoming`** for that player. Its payload references the existing epilogue and reward receipt data. Claim response edits the originating card into the finale immediately. On transport failure or crash after commit, a pending finale takes precedence on the next `/start`, Journal or Location opening; no reward rerun. `[Explore opportunities]`, `[Map]`, `[Journal]` or `[Local contracts]` acknowledges the event while navigating. History → Chapter I replays narrative only.

Semantic exactly-once is guaranteed for completion/rewards/event creation. Telegram cannot guarantee exactly-once creation of a new message after an ambiguous send timeout. Prefer editing the known claim/message ID and keep a persisted acknowledgment; if that message is gone, one replacement is allowed and identified by the same event. Do not claim database atomicity covers Telegram. An acknowledged finale never auto-pushes again. Existing already-completed characters get no forced retrospective finale; History includes it, and the UI migration marks their finale acknowledged.

Feedback consumers coalesce multiple facts from one action to the strongest result: finale → claim/level → ready → objective complete → increment. Preserve the actual reward breakdown behind Details. A feedback-delivery error never cancels rewards, modifies objectives or unlocks content twice. Retain pending major events across restart; minor facts can be acknowledged after incorporation in a result and need not be replayed as old chat spam.

## 12. Journal and quest information architecture

**During Chapter I**, Journal opens its current assignment: localized title, one-line purpose, each objective's actual progress, destination and strongest next step. Show Story separately. If none is accepted, show the next available Chapter assignment first; if a regular hunt occupies the existing slot, show it and explain how to finish/abandon before accepting Chapter work. Do not invent a second board slot. Regional projects retain their independent existing state and are accessible throughout their current eligibility rules.

**After Chapter I**, Journal opens **Regional Opportunities**, explicitly “Choose your own direction.” Its home has the eight controls shown in section 4, not eleven. No “Chapter II,” mandatory next region, linear progress percentage or claim that all 34 records are a new main quest. The seven regional projects retain independent activation/claims and current pin limits. “Tracked pursuits” shows the existing pinned project(s) and active board contract; it does not create a unified quest database.

| Surface/term | Contents and exclusion |
|---|---|
| Current assignment / Active contract | One current board contract, with Chapter treatment if applicable; not a duplicate available listing |
| Regional Opportunities | Current regional projects, leads and choices; existing 34-record catalogue and geography |
| Regional completed | Completed **regional** opportunities only; always labelled Regional, never ambiguous Completed |
| Discoveries | Existing regional discoveries/facts; physical map discovery remains on Map and is labelled Visited places when referenced |
| Local work | Available board contracts and local service/project actions; no fresh quest engine |
| History | Archive: completed Chapter story, completed board-contract records and completed regional stories, clearly grouped; no live professions, active gear goals or incomplete checklist |
| Profession shortcut | Only when an active objective needs a specific recipe/resource; opens Activities at that item/profession |
| Build shortcut | Only for an active equipment objective or a relevant free-point prompt; opens Character or selected Inventory item |

History defaults to six newest completion records, stable sort by completion time then identity; Chapter I is a single expandable story with its four preserved records. If legacy history lacks timestamps, keep canonical Chapter order and stable catalogue order under “Earlier records,” without invented dates. Regional archive links reuse their existing completion authority. Unknown historical IDs display a localized “Earlier completed assignment,” never a raw identifier and never erase the row.

Quest board order: active contract first (including ready state) → next eligible Chapter assignment if slot free → available regular contracts in existing rank/definition order. Exclude the active definition from Available. Objective-only assignments show `N/M objectives`, never `0/0 kills`. Abandon stays behind Details/More with its existing loss-of-progress confirmation and preserves completed history. Claim location and prerequisite validation stay in `quest_board.py`.

Location/Nearby uses one ranked projection: (1) pending finale, (2) current activity/combat resume, (3) local ready turn-in, (4) eligible unclaimed owner harvest ordered by earliest expiry, (5) joinable encounter ordered by deadline, (6) local step of active Chapter/pinned project, (7) local services in Shop/Board/Guild/Inn order, (8) eligible gathering, (9) exits. The summary exposes at most three priority action buttons, then grouped Encounters/Gather/Services/Exits/More as space allows under the eight-button cap; overflow is six-per-page. A category with no relevant entries is omitted. Disabled relevant actions show a specific reason in their detail rather than taking over the main card. Nearby must include Chapter, service and gathering context even where no RAV record exists.

## 13. Character and build UX contract

### 13.1 Profile and attribute spending

Profile shows name, level, friendly current location, gold, current/max HP and MP, numeric character XP threshold, free attribute points, equipped weapon family and mastery. During travel append destination/remaining time; do not replace current location with the destination early. Additional derived stats, security/legal state and equipment detail belong behind Details/Build & equipment. HP, MP, gold and XP remain their current owners' values.

Separate **spending earned free points** from **reset/redistribution**. New operation `spend_attributes` permits only nonnegative integer deltas over the six existing attributes, at least one positive, resulting values 1–100, total delta ≤ current unspent budget, no attribute decrease and no gear unequip. Allowed in any location and during travel/gathering, but never while dead, forming/active PvE, pending/active PvP or terminal settlement in progress. Learning/resetting skills is not included in this activity exception.

Flow: Attributes → choose attribute → +1 or spend all available up to attribute 100 → preview before/after, remaining points and changed derived caps → Apply/Back. A draft can change attribute before Apply; it is not saved character state. No per-point DB mutation until Apply. The existing `build_mutation_receipts` handles exactly-once application, with new operation kind and bound build/gear revisions, rules version and token. Revalidate under lock. A travel arrival can stale the location-bound preview; refresh it without spending twice. No new global unbound token mechanism is needed.

Use the existing attribute-budget invariant, `stat_points`, max-HP/max-MP/carry calculations and effective-cap preview. Increasing Vitality/Wisdom raises the cap but **does not heal/refill current HP/MP**; lowering via a legal reset uses the existing clamp. Spend increments build revision, not gear revision when gear did not change. Existing historical extra-budget migration policy remains untouched.

Attribute redistribution and family reset remain **free only at the six safe hubs**, outside all activities/combat. Their confirmation lists refunded points and any items that will be unequipped by changed requirements. Do not move or charge these operations in PXE1. Build migration/quarantine and reset receipt authority remain in `build_progression.py`.

### 13.2 Weapon skills and navigation

Weapon Skills opens the equipped family (unarmed gets its existing honest state), then two named branch selectors. Selecting a branch displays its one-sentence identity and exactly five skill rows. Switching branches replaces that list. Other families are a separate paginated chooser. Preserve ten families, twenty branches, 100 branch skills plus shared Power Strike; do not add classes, armor locks, offhand locks, prerequisites invented for UX or a new balance model.

Unlock positions require mastery **1, 2, 3, 5, 8**; rank 2 requires mastery **4**, rank 3 mastery **10**, maximum rank **3**. First acquisition of the fifth skill also requires **8 spent ranks in the same branch's other skills**. Each rank costs **1 family skill point**. Existing family budget is mastery level +1; mastery cap 20 and `20L` XP thresholds remain. Show combined unmet requirements in Details; the row uses the first reason in this stable order: mastery → same-branch investment → available points. Use “Requires sword mastery 8” and “Spend 8 points in this branch; 5/8,” never “M8” or a generic lock with no explanation.

Skill detail order: localized name/rank → role/effect in plain language → target pattern → MP cost/cooldown → actual effects or labelled contextual estimate → unlock/rank requirements → Learn/Upgrade if legal → Details/Back. Cooldown wording follows the existing opportunity/affected-side semantics; do not relabel it as wall-clock seconds. Coefficients and implementation tokens are excluded from ordinary summaries. Derive numeric effects from `build_contract.py` and the shared evaluator/preview; descriptions cannot carry independently hardcoded coefficients. If a safe estimate cannot be calculated without combat context, describe the effect, not fabricated damage.

Build & equipment links Equipment, Weapon family, Attributes and Reset options, with at most two contextual prompts (e.g. free points and unequipped weapon). Preserve existing valid mixed/hybrid builds and all legal equipment combinations. Combat execution uses section 5's action→target selector and durable snapshot; a UI branch switch never changes an active snapshot.

## 14. Inventory, shop and craft UX contract

### 14.1 Inventory and comparison

Inventory opens its last valid category/page within the current interaction, default All. Categories are All, Gear, Supplies, Materials and Tools, selected on a compact separate chooser. Tools render the dedicated rows, never count as sellable inventory items. Lists contain six entries; quantity/rarity/equipped marker are useful, instance IDs are not. Sort equipped gear first, then canonical item order and stable hidden instance identity. For several similar gear instances distinguish by localized enhancement/rarity/secondary summary; selecting one binds its exact instance.

Detail shows name/category, rarity, explicitly labelled gear tier, enhancement, applicable stats/effects/requirements and quantity. Main actions: Equip/Use when legal, Compare for gear, Improve when supported, More and Back; at most eight buttons. More retains current advanced mechanics, collection/catalogue, sale location shortcut and Records. Materials link Uses/Sources; supplies show effect and current restrictions. No useful existing per-item action is removed solely to shorten the list.

Compare shows current item → candidate, same-slot before/after **effective** stats and signed deltas, requirements and one main **Equip** button. It invokes the same authoritative equip preview/mutation as item detail with exact instance and revisions. No need to back out to equip. On success update comparison/inventory and display changed quest readiness. Missing slot is “Empty slot,” not an invalid ID. Cannot equip during travel/gather/combat; read comparison remains available. Do not auto-sell or destroy the replaced item.

### 14.2 Shop, buy and protected sale

Shop title includes location and gold. Keep two clear modes Buy/Sell on the same root; changing mode is read-only. Buy lists six item entries with unit price. Detail includes effect/gear requirements, owned quantity, total cost and **Buy 1**. Larger stack purchases use +1/+5 and explicit total on the same preview; quantity range 1–99, never above affordable/available limits. Gear-instance purchases remain quantity 1. No extra confirmation for an already explicit ordinary Buy 1. Exact intent binds item/quantity/unit price/catalogue/location. Revalidate funds, stock policy and delivery under the current economy transaction; receipt replay works after moving.

Sell uses the same real categories, with **Supplies separate from Materials**. A stack detail defaults to **1**, never the full stack. Quantity controls 1/+5/All show quantity, unit value, total proceeds and remaining count before a Sell button. All merely changes the preview; it never sells immediately. No bulk Sell Everything action. Gear sale targets one explicit instance.

Freeze accidental-sale policy:

| Case at commit | Required behavior |
|---|---|
| Equipped gear | Block; explicit Unequip through Inventory first |
| Existing nonsellable/quest-unique item | Block under current item policy; no override |
| Uncommon or rarer gear, enhancement >0, or final owned copy of a gear item | Second confirmation showing exact item and loss |
| Final owned unit of a consumable | Second confirmation; final common material alone does not trigger it |
| Any sale total ≥25 gold | Second confirmation showing quantity and total |
| Selected sale would remove material/gear needed for a current unfinished craft/equip/delivery objective | Second confirmation naming the affected assignment/recipe; existing nonsellable rule still blocks |
| Other common sale <25 gold | One explicit Sell from the quantity/price preview |

For ingredient protection, reserve the active objective's still-needed craft count times the canonical recipe ingredients, minus already owned usable outputs when the objective permits them; do not warn for completed historical Gather objectives that do not require possession. Protect only actual current obligations, not every ingredient in every known recipe. Recompute protection at final commit; a newly risky stale preview returns a fresh confirmation and sells nothing. The second confirmation binds exact revisions/quantity/price and expires under normal token TTL. No persistent favorite/lock system is introduced.

Successful buy/sale edits a compact result: item ×quantity, gold delta, new balance, remaining quantity and up to two objective changes, followed by Continue buying/selling and a ready-quest CTA if applicable. No modal “Success” plus a duplicate result message. Replay shows the same immutable transaction result and current navigation, not new objective credit.

### 14.3 Profession and recipe surfaces

Activities separates five Gathering and seven Crafting professions. Each row shows name, level and XP-to-next, with relevant tool state for gathering. Six per page; no full twelve-profession wall. Current quest-required profession/recipe is a top shortcut, not a reordered hidden mutation. Profession detail lists Known first, Available to learn second and Locked separately. Sort quest-relevant recipe first, then required level and stable catalogue order.

Recipe summary: localized output/name and quantity, meaningful use/effect, ingredient owned/needed counts, expected XP **at current level**, required service, and one of Craft 1 / Learn for exact gold / Find missing inputs / Route to guild. For multiple blockers prioritize knowledge → crafting level → location → ingredients, while Details shows all. Learning and crafting are separate paid intents; opening a recipe never learns it. Recipe Details holds output tier/rarity, training ceiling, complete stat requirements, recipe source and advanced output metadata in player language. It does not expose JSON/catalogue IDs.

Craft 1 is the only production quantity in PXE1; no bulk craft/autorepeat is added. Existing gear/consumable outputs use current delivery owners. Tool recipes display replacement and durability, with a confirmation if replacing an existing tool. A recipe's missing ingredient links to Sources, showing known reachable locations, profession/tool requirement and chance per attempt, then a travel preview. Undiscovered content is labelled as a regional lead only under current discovery rules; source help does not mark a place discovered or start travel/gathering automatically.

After craft, show exact output/quantity, consumed ingredients, profession XP and any objective or level transition. Gear results offer Compare/Equip directly. A newly crafted Trail Vest can therefore be equipped immediately from its result and complete the current objective; equipping still passes its own independent validation and receipt. All screen paths call the same mutation functions as legacy commands.

## 15. Data and schema contract

### 15.1 Versioning and conventions

Add one migration marker **`player_experience_economy_v1`** to the existing `economy_schema_migrations`; do not invent a second global migration ledger. `game/player_experience_schema.py` installs the additive PXE1 tables/columns inside one caller-owned transaction, after existing schema installers. Row/payload schema version is **1**. Static profession catalogue becomes **2**, craft XP policy becomes **2**; existing receipt envelope schema stays **1**, satisfying its actual CHECK constraint. Existing catalogue-1 receipt bytes and replay adapters are immutable. New raw intents made before cutover are stale; already applied requests must replay before current token/catalogue validation.

All new `player_id` columns reference `players(telegram_id)`. All new times are integer Unix UTC milliseconds; adapt existing second/timestamp owners at boundaries, without rewriting their stored times. IDs are random 32-hex strings for durable sessions/events, except deterministic feedback keys stated below. All revisions are nonnegative integers. SQLite foreign keys must be enabled. JSON validators reject unknown schema versions, malformed counters, unknown current resource IDs and impossible paths; old compatibility payloads remain routed to their versioned readers.

The following column lists are complete for new domain state. `NOT NULL` is the default unless explicitly marked nullable. `created_ms`/`updated_ms` are explicitly set by callers. No last-message text, resource balance, quest-progress total or reward total is duplicated into UI authority.

### 15.2 New persistent owners

| Table / owner | Columns and constraints | Keys and indexes |
|---|---|---|
| `player_travel_sessions` / `game/travel_runtime.py` | `session_id TEXT`; `player_id INTEGER`; `start_request_id TEXT`; `schema_version INTEGER CHECK=1`; `route_version INTEGER CHECK=1`; `route_class TEXT CHECK IN ('adjacent','discovered')`; `path_json TEXT` (ordered canonical IDs, length≥2); `edge_index INTEGER DEFAULT 0 CHECK≥0` (number of fully completed edges); `origin_location_id TEXT`; `destination_location_id TEXT`; `status TEXT CHECK IN ('running','arrived','cancelled','interrupted')`; `started_ms INTEGER`; `next_due_ms INTEGER` nullable at terminal; `expected_travel_revision INTEGER`; `revision INTEGER DEFAULT 1`; `terminal_reason TEXT` nullable; `created_ms INTEGER`; `updated_ms INTEGER` | PK session_id; UNIQUE(player_id,start_request_id); unique partial `(player_id) WHERE status='running'`; partial due index `(next_due_ms,session_id) WHERE status='running'`; history `(player_id,created_ms,session_id)` |
| `player_gathering_sessions` / `game/gathering_runtime.py` | `session_id TEXT`; `player_id INTEGER`; `start_request_id TEXT`; `schema_version INTEGER CHECK=1`; `rng_version INTEGER CHECK=1`; `catalog_version INTEGER CHECK=2`; `profession_key TEXT CHECK` one of four environmental professions; `location_id TEXT`; `location_visit_revision INTEGER`; `source_snapshot_json TEXT`; `seed TEXT` (32 hex); `tool_tier INTEGER CHECK 1..4`; `expected_tool_revision INTEGER`; `status TEXT CHECK IN ('running','completed','cancelled','interrupted','broken')`; `started_ms INTEGER`; `next_due_ms INTEGER` nullable at terminal; `ends_ms INTEGER` exactly started+120000; `last_tick INTEGER DEFAULT 0 CHECK 0..15`; `yield_total INTEGER DEFAULT 0 CHECK 0..15`; `result_json TEXT` (schema 1 accumulated item counts/XP/attempts for this session only); `revision INTEGER DEFAULT 1`; `terminal_reason TEXT` nullable; `created_ms INTEGER`; `updated_ms INTEGER` | PK session_id; UNIQUE(player_id,start_request_id); unique partial player_id where running; partial `(next_due_ms,session_id)` where running; history `(player_id,created_ms,session_id)` |
| `player_profession_tools` / `game/profession_tools.py` | `player_id INTEGER`; `profession_key TEXT CHECK` in five gathering professions; `tier INTEGER CHECK 1..4`; `durability INTEGER CHECK 0..60*tier`; `revision INTEGER DEFAULT 1`; `bootstrap_used_mask INTEGER DEFAULT 0 CHECK 0..7`; `schema_version INTEGER CHECK=1`; `created_ms INTEGER`; `updated_ms INTEGER`. Mask bits 0/1/2 represent T2/T3/T4 commission used; CHECK mask=0 unless woodcutting/mining | Composite PK(player_id,profession_key); no gear/inventory FK, no separate capacity column; PK supports all tool reads |
| `player_location_threats` / `game/location_threats.py` | `player_id INTEGER`; `visit_revision INTEGER`; `location_id TEXT`; `mob_id TEXT`; `schema_version INTEGER CHECK=1`; `due_ms INTEGER`; `status TEXT CHECK IN ('pending','triggered','dismissed')`; `encounter_id TEXT` nullable FK to pve_encounters; `reason TEXT` nullable; `created_ms INTEGER`; `updated_ms INTEGER` | PK(player_id,visit_revision,mob_id); partial `(due_ms,player_id,visit_revision,mob_id)` where pending; `(player_id,status)` |
| `player_feedback_events` / `game/player_feedback.py` | `player_id INTEGER`; `event_key TEXT`; `schema_version INTEGER CHECK=1`; `source_kind TEXT`; `source_id TEXT`; `event_kind TEXT CHECK IN ('progress','objective_complete','ready','claim','level_up','chapter_finale','recovery')`; `payload_json TEXT`; `state TEXT CHECK IN ('pending','presented','acknowledged')`; `chat_id INTEGER` nullable; `message_id INTEGER` nullable; `created_ms INTEGER`; `presented_ms INTEGER` nullable; `acknowledged_ms INTEGER` nullable | PK(player_id,event_key); `(player_id,state,created_ms,event_key)`; deterministic event key from source kind/id/event discriminator, finale exception fixed as section 11 |
| `player_pxe1_ui` / `game/player_ui.py` | `player_id INTEGER`; `schema_version INTEGER CHECK=1`; `menu_version INTEGER DEFAULT 0`; `menu_lang TEXT` nullable; `surface_kind TEXT` nullable; `surface_ref TEXT` nullable; `chat_id INTEGER` nullable; `message_id INTEGER` nullable; `surface_revision INTEGER DEFAULT 0`; `updated_ms INTEGER` | PK(player_id). At most one currently edited general surface; finale event may retain its own message target. Surface refs are projections, never activity/combat authority |
| `pvp_participant_settlements_pxe1` / `game/pvp_live.py` | `engagement_id INTEGER` FK pvp_engagements; `player_id INTEGER`; `schema_version INTEGER CHECK=1`; `turn_revision INTEGER CHECK>=0`; `result_json TEXT`; `status TEXT CHECK='applied'`; `created_ms INTEGER`. Result records immutable defeated actor/side, credited source, prior pair counts, scale, exact per-item debit/pool, crime delta/log ID, respawn/protection/HP/MP and source turn | PK(engagement_id,player_id); `(player_id,created_ms,engagement_id)`. Only version1 engagement deaths use this ledger; row, side result, debit and death relocation commit together |
| `pvp_group_settlements_pxe1` / `game/pvp_live.py` | `engagement_id INTEGER` PK/FK pvp_engagements; `schema_version INTEGER CHECK=1`; `terminal_turn_revision INTEGER CHECK>=0`; `result_json TEXT`; `status TEXT CHECK='applied'`; `created_ms INTEGER`. Result records victory/draw, nullable winning side, each locked player's outcome, referenced death pools, per-recipient grants/destroyed remainder, added relationship-log IDs and released actors | PK(engagement_id); no fabricated winner/loser pair; terminal result, pool distribution, survivor release and receipt commit together |

`result_json` is derived session accounting updated in the tick transaction; per-tick receipts remain the replay evidence. It cannot be used to grant its contents again. `edge_index` is constrained by the decoded path length and must agree with authoritative location; no SQL JSON-extension dependency is required. Receipt existence and session counters must agree at recovery. An inconsistency interrupts and produces a recovery notice, never “replays all accumulated rewards.”

### 15.3 Additive changes to existing owners

| Existing owner | Exact additions/change | Backfill and recovery |
|---|---|---|
| `players` | `location_visit_revision INTEGER NOT NULL DEFAULT 0 CHECK≥0` | Existing rows start 0; only actual relocation increments. Common arrival path handles travel, death return and supported recovery moves. Travel revision remains the existing stale-intent owner |
| `pve_encounters` | `lifecycle_version INTEGER NOT NULL DEFAULT 0 CHECK IN (0,1)`; `formation_deadline_ms INTEGER` nullable; `formation_revision INTEGER NOT NULL DEFAULT 0 CHECK≥0`; `runtime_started_ms INTEGER` nullable | Coherent linked-forming encounters upgraded to version 1 with fresh deadline/revision 1. Existing active/terminal/legacy rows keep version 0 and compatibility semantics. New anchored encounters use 1. Runtime started timestamp is informational once existing runtime snapshot is authoritative |
| `pve_encounters` index | `idx_pve_formation_due(formation_deadline_ms,encounter_id) WHERE lifecycle_version=1 AND runtime_started_ms IS NULL AND status='active'` | Queries must also require linked spawn(s) forming; no old TTL logic on these rows |
| `pvp_engagements` | `world_model_version INTEGER NOT NULL DEFAULT 0 CHECK IN (0,1)`; `locked_roster_json TEXT` nullable; `roster_locked_ms INTEGER` nullable. Reuse existing ready-at, combat_seed, rules_version, turn_revision and state_revision; seed assigned at new engagement creation for escape replay | New engagements and old pending engagements use1; already-live/terminal old engagements retain0. Partial index `idx_pvp_pxe1_due(engagement_ready_at,id) WHERE world_model_version=1 AND engagement_state='pending'`. Version1 lock JSON is immutable; no singleton owner substitution |
| `pvp_engagement_reinforcements` | `membership_version INTEGER NOT NULL DEFAULT 0 CHECK IN (0,1)`; use current side/inviter/ally/status/timestamps. New statuses include `locked`, `left`, `revoked`, `defeated`, `released` alongside existing pending/accepted/rejected/expired | Three unique partial indexes for version1: `(engagement_id,ally_id)` unconditionally; `(engagement_id,side)` where status in pending/accepted/locked; `(ally_id)` where status in accepted/locked. Add lookup `(engagement_id,membership_version,status)`. Keep old rows/version0; expire old pending memberships at pending-engagement cutover before installing new rules |
| Existing encounter status reader | Recognize new terminal reason/status `start_failed` and unstarted `abandoned`; participant departure uses existing `left` | Existing status is TEXT without restrictive CHECK; no table rebuild. Never treat these as victory or settlement-eligible |
| `player_recipe_knowledge` | Five additive starter/grandfather tool recipe rows per player; new catalogue version 2 rows | Preserve all existing rows, acquired reasons and prices; do not overwrite historical catalogue version 1 |
| `economy_action_receipts` | New action kinds `gather_tick_pxe1`, `tool_craft_pxe1`, `tool_repair_pxe1`, `tool_replace_pxe1`, `tool_commission_pxe1`, `pvp_membership_pxe1`, `pvp_prep_escape_pxe1`; new regular craft results carry `xp_policy_version=2`. Repair intent/result includes repair_mode, exact consumed/supplied quantities, gold and revisions | No columns/CHECK rebuild; envelope schema1/catalogue2 for fresh actions. PvP membership/escape receipts give no XP/items; they deduplicate commitment/crime/escape effects. Legacy replay first; kind/hash mismatch rejects |
| `build_mutation_receipts` / UI intents | New spend-only operation; revised payloads bind current revisions and correct action scope | No new columns. Preserve existing receipts and build rules version; add operation discriminator and operation payload version 1 |
| Current quest/settlement/gear owners | Connection-scoped feedback hook and activity validation; hunting tool debit inside existing claim transaction | No new objective/progression/reward table; no changed ownership or dual write after commit |

No schema change is required for ordinary Inventory items, gear instances/durability, mastery/skills, profession level/XP rows, RAV projects/facts/claims, board history/objectives, location discovery, existing PvP legal-player columns, `pvp_log`, combat orders/turn results or the legacy `pvp_terminal_settlements_v1` ledger. PvP adds four columns and two consequence ledgers as listed, because the existing terminal winner/loser columns are non-null and cannot encode individual deaths or group draws losslessly. New ledgers are receipts under the same PvP domain, not another encounter/runtime model. Version0 alone uses the old terminal ledger; version1 alone uses the new ledgers, including new1v1 encounters. All canonical world spawns/encounters remain in their existing tables.

PvP lock JSON schema1 contains ordered `side_a`/`side_b` lists of player IDs, principal roles, accepted reinforcement row IDs, inviter/acceptance provenance and frozen legal context. Existing `reason_context` JSON gains `world_model_version:1`, initiation/acceptance legal snapshots, per-member status and battle data: `participants_v1`, side arrays, `damage_by_target`, actor manual-contribution flags, pending/complete consequences, combat seed, side deadlines/revisions and terminal result `{terminal:true, winning_side:side_a|side_b|null, outcome:victory|draw}`. These typed fields are versioned payload extensions, not new SQL columns. Legal snapshots include the current helper inputs and pre-action retaliation/protection observations; gameplay renders them through localized keys. Never infer group victory from singular attacker_hp/defender_hp or winner_id.

Reinforcement lifecycle: pending→accepted→locked→defeated or released; pending→rejected/revoked/expired; accepted→left/expired; a cancelled unstarted engagement releases accepted rows and expires pending rows. Row statuses project the immutable locked roster after start, and must agree with actor/death receipts. Busy/mobility lookup for version1 includes accepted or living locked actors, **including allies**, and excludes already-settled defeated principals even while their teammates continue. Existing principal-only busy lookup remains for version0. Cross-role uniqueness (principal in one engagement versus ally in another) is checked under the writer lock; partial indexes alone are not sufficient.

### 15.4 Transaction and idempotency boundaries

All mutation services accept/use a **single connection under `BEGIN IMMEDIATE`** for validation, token consumption, debits/grants, progression/objectives, state transition, receipt and feedback insertion. Internal helpers must not commit or open another write transaction. This requires extracting connection-scoped internals from current multi-commit start/conversion paths, without duplicating their rules. Send/edit Telegram only after commit; update transport projection separately. No await/sleep/network request while holding a DB write lock.

| Operation | Authoritative atomic boundary / duplicate result |
|---|---|
| Travel Start | Current peaceful/activity/path/discovery validation + consume intent + new session + travel revision. Unique player/start request returns original session |
| Travel edge | Exact session revision + due time + earlier threats + location/discovery/visit and travel revision + next edge/state + arrival feedback. Same edge cannot commit twice |
| Travel/Gather Stop | Exact session, due-event reconciliation up to click time, terminal transition. Already terminal returns terminal state, never touches another session |
| Gather Start/tick | Start validation/insertion; each tick independently applies section 7 receipt boundary. Cross-table activity check prevents one travel plus one gather despite separate partial indexes |
| Tool craft/commission | Old slot revision + recipe/source/bit checks + all material/gold debit + full tool + irreversible commission bit if applicable + craft XP + receipt/feedback. No intermediate high material delivery |
| Tool repair/replace | Current durability/tier/revision + repair_mode and exact consumed/supplied inputs/gold + debit + tool revision/result + receipt. Assisted supplies never become inventory; no XP/HP/stat side effects |
| Owner harvest | Existing T2 authority + one claim + eligible tool + resource/XP/objective/wear + receipt; legacy duplicate detected before new gates |
| Forming create/join/leave/start | Existing source/participant/RAV rows plus section 5 lifecycle fields, snapshots and first phase all under the same writer lock |
| PvP create/invite/accept/leave/escape/start | Current principal approval, candidate consent, legal/activity/cap checks + commitment/crime changes + operation receipt; one atomic roster/snapshot/flags/start transition. Start-first rejects stale membership; Leave-first removes only accepted ally. No accepted reinforcement expiry at successful lock |
| PvP full side/defeat | Whole batch result and all newly defeated actors' pool debits, attribution/log/crime, respawn/protection and individual receipts commit in one writer transaction. Extend current `persist_turn_result` with caller-connection support, preserving existing standalone behavior/CAS; no nested commit. Duplicate side result returns its committed state without reapplying deaths |
| PvP terminal | Validate immutable locked roster and terminal result + all per-death pools + allocation/conservation + survivor state/release + extra relationship logs + aggregate receipt + cancelled/resolved engagement. Replays cannot use the legacy pair settlement path |
| Hostile interruption | Legal/source validation first; then activity terminal transition + encounter/engagement reservation/flags. Failed hostile creation rolls back interruption |
| Claim/quest feedback | Existing reward/history transaction + deterministic feedback event; no observer can grant a reward |
| Spend attributes | Existing budget, life/activity/combat/revision checks + monotonic deltas + derived caps + receipt/feedback |

The normal 900-second economic UI token lifetime remains. Stop/Resume activity controls bind player/session, and turn/formation controls bind encounter/revision/deadline; long-lived activity controls must not become unusable merely because an unrelated menu issued new tokens. Read-only buttons can reload current authority. Craft/sale/equip/tool previews use existing opaque 16-hex tokens under distinct operation kinds. Always compare server actor identity with token owner. Old callbacks cannot target a respawn, another player, replacement gear, a new session or a changed quantity. Receipt replay precedes current travel/location checks so a successfully completed action remains replayable after the player moves.

### 15.5 Migration, restart and safe cutover

Implementation cutover is one maintenance restart: stop input/workers, back up SQLite using its supported backup mechanism, run existing schema/migration validation and then the PXE1 migration transaction, validate foreign keys/row counts, start recovery, then expose new routes. Do not implement live dual-mode instant/timed gathering.

Migration is idempotent and insert-if-missing. It creates **eight tables**, adds **nine existing-table columns** (players1, PvE4, PvP engagement3, reinforcement1), seeds five tools and five knowledge rows per player, seeds the UI row, acknowledges historical completed-Chapter finales, and upgrades coherent existing anchored formations. Pending PvP upgrades and old-invite expiry follow section5.4.7, retaining original deadlines; already-live PvP remains version0 with no roster expansion. Existing ledger rows, inventories, discoveries, levels, active snapshots and completed content are never reset. A second run changes neither durability nor commission bits nor XP, and must not expire new version1 invitations or refresh a deadline. At cutover, existing non-safe visits get one initial set of threat deadlines, only if no rows for visit0 exist; safe places get none. Recovery subsequently uses stored visits rather than new grace periods.

Startup ordering after schema validation: recover existing prepared reward settlements using their normal owner; interrupt old running gathers; invalidate any impossible overlapping activity using the precedence **existing active combat → valid forming/PvP engagement → travel → gather**; recover due threats and at most one overdue travel edge in temporal order; start due valid formations; restore active combat deadlines through existing evaluator as section 5 specifies. In an overlap, preserve committed yields/location and interrupt lower-priority activity, never manufacture a combat result or refund a prior commit.

Restart does not replay minor notifications as a flood. Pending major feedback remains available. Missing/deleted Telegram messages cause a fresh status card on the next interaction, never a gameplay reset. Persistence failures keep intents unapplied/rollback-safe. Unknown corrupted domain rows are quarantined by a terminal interruption/recovery notice with logged diagnostic evidence; valid surrounding inventory/progression remains untouched. Do not convert corruption into free outputs.

The two new authoritative terminal statuses and catalogue-2 outputs mean running the old binary against the upgraded live DB is **not a supported rollback**. Before accepting new activity, recovery may restore the pre-cutover backup with the matching old binary; after new play, use a forward fix, preserving player actions. No destructive down-migration or silent database restore after players have earned new rewards.

## 16. I18n contract

All player text goes through current `game/i18n.py` and `locales/ru.py`, `en.py`, `es.py`. Reuse existing item/location/quest/family/skill keys and improve their player wording where needed; add PXE1 surface/state strings under the following exact families. Dynamic suffixes come only from validated current catalogue keys, never arbitrary historical input concatenated into visible text.

| Key family | Required suffixes / coverage |
|---|---|
| `pxe1.menu.*` | `location`, `map`, `journal`, `inventory`, `character`, `activities`, meaningful `welcome_status` |
| `pxe1.common.*` | `back`, `details`, `more`, `next`, `previous`, `page`, `refresh`, `continue`, `already_applied`, `screen_changed`, `unavailable`, `unknown_historical`, `safe_hub_required`, `stop_activity_first`, `combat_blocked`, `dead_blocked` |
| `pxe1.location.*` | `nearby`, `services`, `exits`, `players`, `ready_here`, `nothing_actionable`, `more_nearby`, `current_location`, localized security labels |
| `pxe1.map.*` | `region`, `world`, `you_are_here`, `visited_places`, `undiscovered`, `route_preview`, `no_known_route`, `source_lead` |
| `pxe1.travel.*` | `adjacent`, `discovered_route`, `start`, `stop`, `remaining`, `arrived`, `cancelled_at`, `interrupted`, `resumed`, `route_changed`; `flavor.<route_id>` and `flavor.neutral` |
| `pxe1.encounter.*` | `forming`, `starts_in`, `join`, `leave`, `participants`, `roster_locked`, `already_started`, `finished`, `respawning`, `preparing_retry`, `start_failed`, `leader_changed`, `resume`, `pvp_preparing`; `pvp_invite`, `pvp_invitation_required`, `pvp_join_named_side`, `pvp_decline`, `pvp_revoke`, `pvp_side_count`, `pvp_invited_count`, `pvp_side_full`, `pvp_principal_only`, `pvp_reinvite_required`, `pvp_protection_blocked`, `pvp_illegal_assist_warning`, `pvp_leave_preparation`, `pvp_escape_attempt`, `pvp_escape_success`, `pvp_escape_failed`, `pvp_no_live_escape`, `pvp_locked`, `pvp_waiting_for_ally`, `pvp_resolving`, `pvp_victory`, `pvp_draw`, `pvp_cancelled`, `pvp_personal_loss`, `pvp_personal_loot`, `pvp_personal_infamy`, `pvp_respawn_protection`, `pvp_recent`, `pvp_target_lost_guard` |
| `pxe1.combat.*` | `choose_action`, `choose_target`, `use_on_self`, `use_on_party`, `target_gone`, `turn_expired`, `waiting_for_allies`, `last_resolution`, `battle_details`; existing action names reused |
| `pxe1.gather.*` | `preview`, `start`, `collecting`, `attempts`, `gathered`, `xp_total`, `remaining`, `stop`, `completed`, `cancelled`, `interrupted`, `restart_stopped`, `no_eligible_resource`, `locked_result`, `source_probability` |
| `pxe1.tool.*` | `axe`, `pick`, `sickle`, `rod`, `knife`; `tier.1` through `.4`; `durability`, `tier_coverage`, `worn_warning`, `broken`, `replace`, `replacement_cost`, `repair`, `repair_cost`, `assisted_repair`, `assisted_repair_explanation`, `assisted_repair_quote`, `assisted_repair_no_gold`, `repair_quote_changed`, `full`, `upgrade`, `replace_confirm`, `no_downgrade`, `starter_granted`, `commission`, `commission_cost`, `commission_used`, `commission_visit_required`, `commission_previous_tier` |
| `pxe1.profession.*` | `gathering`, `crafting`, `level_xp`, `at_cap`, `known`, `learnable`, `locked`, `learn`, `craft_one`, `no_xp`, `training_ceiling`, `level_up`, `required_recipe`, `find_inputs`, `source_tool_gate`, `recipe_output`, `tool_output` |
| `pxe1.quest.*` | `progress`, `objective_complete`, `more_changes`, `ready`, `turn_in`, `route_to_turn_in`, `claimed`, `next_assignment`, `view_next`, `all_objectives`, `slot_occupied`, `readiness_lost` |
| `pxe1.journal.*` | `current_assignment`, `active_contract`, `opportunities`, `choose_direction`, `tracked`, `regions`, `clues`, `regional_completed`, `discoveries`, `local_work`, `history`, `earlier_records`, `chapter_archive`, `profession_shortcut`, `build_shortcut` |
| `pxe1.chapter.*` | `complete`, `epilogue_intro`, `choose_next`, `explore_opportunities`, `history_replay`; existing four story/title/reward keys preserved |
| `pxe1.character.*` | `profile`, `free_points`, `spend`, `spend_one`, `spend_available`, `apply_spend`, `spend_preview`, `reset_hub`, `build_equipment`, `weapon_family`, `mastery_required`, `branch_points_required`, `skill_points_required`, `rank`, `target_pattern`, `cooldown_opportunities`, `contextual_estimate`, `empty_slot` |
| `pxe1.inventory.*` / `pxe1.shop.*` | Five category names; `compare`, `equip`, `equipped`, `use`, `sources`, `uses`, `records`; `buy`, `sell`, `quantity`, `unit_price`, `total`, `remaining`, `balance`, `confirm_sale`, `last_copy`, `valuable_item`, `quest_needed`, `cannot_sell_equipped`, `purchase_result`, `sale_result`, `starter_tools` |
| `pxe1.command.*` | Description for every registered command below |

Freeze short core action translations, retaining normal capitalization conventions:

| English | Russian | Spanish |
|---|---|---|
| Stop | Остановить | Detener |
| Turn in | Сдать задание | Entregar |
| Join | Присоединиться | Unirse |
| Leave | Выйти | Salir |
| Gather | Собирать | Recolectar |
| Repair | Починить | Reparar |
| Guild-assisted repair | Ремонт с материалами гильдии | Reparar con ayuda del gremio |
| Invite ally | Пригласить союзника | Invitar aliado |
| Invitation required | Нужно приглашение | Se requiere invitación |
| Join {name}'s side | На сторону {name} | Unirse al bando de {name} |
| Attempt escape | Попытаться уйти | Intentar escapar |
| Replace | Заменить | Reemplazar |
| Spend points | Вложить очки | Asignar puntos |
| Regional completed | Выполнено в регионах | Completadas por región |
| History | История | Historial |
| Details | Подробнее | Detalles |

Long Regional completed translations use a full-width row; the eight-button home may therefore occupy five rows, still within budget. Translator inflection/plurals use numeric-aware variants for 1/2/5/21 and zero where applicable, not English suffix concatenation. Show durations as M:SS and integer gold/quantities. Item/location names use their existing localized resolver; do not lowercase arbitrary proper names to compose travel prose. Test ru/en/es at longest current item/skill/location names, not only short fixture labels. Unknown legacy records get explicit localized fallback; all known 83 recipes, 20 tool outputs, resource gates, branches and skills require real translations and placeholder parity.

Register localized BotCommand descriptions at startup for ru/en/es and the English default: **`start`, `location`, `map`, `journal`, `inventory`, `profile`, `activities`, `stats`, `skills`, `build`, `settings`, `help`**, in this order. Add the `/activities` handler; existing `/profile` remains the Character command alias. Existing `/go`, `/enc`, `/pvp`, `/unstuck` remain supported compatibility/advanced routes and are documented under Help rather than filling normal autocomplete. Commands never bypass activity, encounter or receipt checks. Registration errors are logged and retried on the next startup; they cannot prevent gameplay startup. Actual autocomplete is a manual acceptance check. [Telegram command registration](https://core.telegram.org/bots/api#setmycommands)

## 17. Exact file and module change map

Paths are beneath `rpg/`. “New” below is planned implementation ownership; no such production files are created by this audit. Keep explicit small procedural helpers, current imports and current owners. No generic event bus, scheduler framework, universal transaction engine or parallel combat architecture.

| File/module | Required responsibility/change | Must not become its responsibility |
|---|---|---|
| `bot.py` | Register fixed-menu aliases, `/activities`, localized commands; one 1-second PXE1 world job; ordered startup/recovery; route old callbacks to current surfaces | Economic calculations, combat evaluator, sleeping travel/session loops |
| `database.py` | Call additive installer in existing initialization order; include new fields in appropriate player reads/creation | Domain reward policy or destructive profession normalization |
| **new** `game/player_experience_schema.py` | Eight new tables, nine columns, indexes, marker, checked idempotent backfill including versioned PvP/pending invitation handling; delegate canonical grants/recovery to owners | Reimplement existing build/economy migrations or alter their historical markers |
| **new** `game/player_activity.py` | Connection-scoped read/validation of mutually exclusive travel/gather/combat/PvP; domain-specific interruption dispatch; reconcile due events for one player | A duplicate authoritative activity table or independent copies of legal/combat rules |
| **new** `game/world_activity_tick.py` | Small due-work coordinator using explicit owner functions, chronological per-player order, bounded batch handling and logging | RNG, tool pricing, settlement or transport calls inside transactions |
| **new** `game/travel_runtime.py` | Pure route preview/time plus durable session start/advance/stop/recovery; current graph/discovery helpers; common real-arrival call | Teleport activation, source geography expansion or direct inventory writes |
| **new** `game/location_threats.py` | Persistent visit deadlines; current aggression eligibility; same-connection hostile interruption and canonical encounter initiation | Private encounters, additional aggression rolls on reads, preemptive standalone battle flags |
| `game/locations.py`, `world_scaffolding.py` | Expose canonical route/source/service metadata to projections; preserve topology, aliases and dynamic/static separation | Journey persistence, UI text as map authority or expanded world content |
| `game/contextual_keyboard.py` | Exactly six fixed labels, legacy aliases and compact row helper | Per-location exits/services appended to reply keyboard |
| **new** `game/player_ui.py` | UI-state row, budgets/pagination, meaningful keyboard installation state, edited-surface coalescing and recovery | Gameplay decisions, success assumed from message send or stored rendered truth |
| `handlers/location.py` | Local-first Map, preview/active travel, unified Location/Nearby, concise encounter/services/board/shop/tool-service views; remove old sleep and aggro scheduling | Authoritative travel/gather/economic transactions or duplicated RAV/Chapter progress |
| `game/pve_live.py` | Lifecycle fields, no read-TTL expiry for PXE1, atomic create/join/leave/owner transfer/roster snapshot/start; source reservations/recovery and current live projection | A second shared-encounter table or changed combat coefficients |
| `handlers/battle.py` | All public initiators use forming; edited countdown/status; compact action→target UI; current-state stale recovery | Immediate private runtime creation or settlement grants from a callback |
| `game/live_combat_runtime.py`, `combat_orders.py`, `actor_snapshot.py` | Reuse multi-actor side initialization/batching; extend PvP intent authorization to living locked members/current side; connection-scoped turn-result persistence and snapshots for atomic boundary | New formulas, new classes, singleton principal-only authorization on version1 or duplicated skill catalogue |
| `game/pve_reward_settlement.py` | Preserve T1/T2; add committed feedback result fields; retain per-player eligibility and immutable bindings | Tool harvest grants as generic battle loot, final-hit ownership or roster expansion |
| `game/pvp_engagement.py`, `pvp_live.py`; location PvP renderer | Invitation-approved cap2-per-side membership, all-actor atomic lock/rehydration, full-batch execution, per-defeat pools/receipts, aggregate shared-loot settlement, actor-specific crime/log attribution, active/dead-ally busy lookup, escape actor validation and public phase projection | Arbitrary self-join, mid-combat roster growth, new combat formulas, synthetic singleton terminal winners or independent runtime engine |
| `game/pvp_rules.py`, `pvp_state.py`, `pvp_death_policy.py`, `pvp_inventory_policy.py` | Reuse current numeric legal/protection/loss rules; expose connection-scoped context reads for frozen individual liability and paired repeat counts; unchanged vulnerability classification | New security zones, flag exemptions for outsiders, multiplying death loss by team size or expanding vulnerable core gear |
| `game/gathering_runtime.py` | Persisted session/ticks/Stop/recovery using existing delivery/progression/objective helpers; legacy receipt reader | Instant fresh repeated Gather grants or separate XP rules |
| `game/gathering_foundation.py`, `gathering_progression.py` | Current source/profession validation, unchanged gathering XP, typed session preview input | Timing loops or tool-slot duplication |
| **new** `game/profession_tools.py` | Five slots, capacities, gates, wear/revision, starter/replacement, material/assisted repair quotes and commit, exact tool-only output installation, preserved commission bits/checks | Free inventory materials, repair XP, duplicate item delivery, combat gear/equipment power, market/trading or resource quality variants |
| `game/profession_resources.py` | Add static tier metadata and explicit legacy source metadata; sole source-order/probability authority | Fresh inventory IDs, duplicated geography in handlers or renormalized probabilities |
| `game/profession_recipes.py` | Catalogue 2, 20 exact tool recipes, output union extension, frozen material XP value and XP-policy metadata | Ingredient/output balance changes to the 63 existing recipes |
| `game/crafting_foundation.py`, `crafting_runtime.py`, `profession_progression.py` | New XP function, tool output delegation in existing transaction, price/source/receipt replay, recipe replacement preview | Granting a fake tool item as well as a tool row; duplicate receipt ledger |
| `game/recipe_knowledge.py`, `profession_schema.py` | Recognize additive tool knowledge and catalogue 2; retain strict existing migration/receipt validation and old replay adapters | Rewriting historical knowledge acquisition, recipe receipts or profession XP rows |
| `game/hunting.py` | Tool gate and wear inside existing one-claim owner-only harvest; richer committed feedback | Per-participant/per-enemy claim expansion or collection before T2 |
| `game/action_receipts.py`, `economy_actions.py` | Activity-aware validation with explicit spend exception; sale protection/revision checks; token-kind separation and old replay | UI-only safety checks or a universal reward refactor |
| **new** `game/player_feedback.py` | Typed same-transaction facts and deterministic event keys; priority/coalescing; durable finale acknowledgment | Quest objectives, rewards or an asynchronous economic event consumer |
| `game/quest_board.py`, `starter_kit.py` | Objective-derived board readiness, same-transaction feedback/finale, preserved four definitions; additive tool provisioning hook | Second active Chapter slot, extra Chapter or tutorial reward farming |
| `handlers/chapter.py`, `handlers/regional.py` | Chapter-first/Regional home, separate archive, immediate finale, contextual shortcuts and reduced buttons | Copying RAV state into Chapter tables |
| `game/regional_opportunities.py`, `regional_adventures.py`, `regional_objectives.py` | Read projection adapters and feedback deltas only where needed; preserve catalogue, bindings and claims | New regional content, changed project prerequisites or mandatory ordering |
| `game/build_progression.py`, `handlers/build.py`, `handlers/profile.py` | Spend-only operation and preview; profile, selected branch, friendly requirements and Details | Respec outside safe hubs, changed skill balance or running build migration again |
| `game/build_contract.py`, `weapon_mastery.py` | Read existing constants/effects; only small presentation adapters if necessary | Changing unlocks, budgets, mastery XP or skill coefficients |
| `handlers/inventory.py`, `game/gear_ui.py`, `equipment_stats.py` | Six-entry views, direct compare→Equip, honest base/effective stat labels, tool projection | Rewriting gear-instance authority or new combat durability |
| `handlers/professions.py` | Activities home, concise professions/recipes/sources/tools/commission previews and result cards | Local input debit or independent recipe requirements |
| `locales/ru.py`, `en.py`, `es.py`, `game/i18n.py` | Complete keys/placeholder parity, plural helpers where needed, friendly current-content descriptions | Raw-ID fallbacks for known content or locale-specific mechanics |
| `tests/test_pxe1_*.py` (new) plus directly affected existing tests | Section 18 behavior, races, recovery, arithmetic, rendering budgets and integration | Replacing all historical tests with new snapshots or checking only helper-level happy paths |
| Canonical docs/evidence in section 20 | Freeze supersessions, candidate results and real human evidence with exact revision | Claiming merge/deployment/human passes before they occur |

## 18. Automated acceptance plan

This section is a required implementation gate, **not a claim that tests were run in this audit**. Use Python 3.12 and the repository's current PTB dependency range. Isolate SQLite/test bot data; never point tests at a live game database. Use deterministic clocks/seeds, independent database connections for race tests, and deliberate failure injection at transactional boundaries. Assert persisted conservation/ownership and actual handler results, not only that a function was called.

### 18.1 Focused suites and decisive cases

| Proposed test file | Required behavior/evidence |
|---|---|
| `tests/test_pxe1_schema.py` | Empty/current populated DB migration; eight tables/nine columns/indexes; repeated equality; exact five full tools/new knowledge rows; inventories/gear/XP/mastery/Chapter/RAV/discovery/legal state preserved; marker rollback/FKs; old receipts; active version0 PvP preserved; pending PvP deadline retained, old unsupported consent expired exactly once, version1 invites survive rerun; coherent forming upgrade; historical finale acknowledgment; commission masks survive upgrade/replacement |
| `tests/test_pxe1_navigation_ui.py` | Exactly six lower entries/3×2 for ru/en/es; no dynamic additions; meaningful one-time installation, failed-send retry, no sync spam; every old label/command reaches current view; local Map/default current marker; Nearby includes Chapter/shop/gather with zero RAV entries; button/row/text/callback budgets and escaped dynamic text |
| `tests/test_pxe1_travel.py` | 15/33/105/177 seconds at 1/2/6/10 hops; graph tie order; discovered-only internal route; Elmor→Aster exact six nodes after origin; preview no mutation; duplicate start; competing starts; partial cancel; edge at click equality commits once; completed route Stop; stale Stop versus new session; route changed; no final teleport; no premature discovery; at-most-one restart edge; actual arrival visit revision only |
| `tests/test_pxe1_activity_conflicts.py` | Travel vs gather/craft/equip/shop/claim/learn/reset conflicts on two connections; spend-only exception; active/forming/PvP/death all block; threat at tie beats edge/tick; failed hostile creation leaves activity intact; successful threat creates one real encounter and interrupts once; cancel/restart/refresh cannot reroll threat; activity is not PvP immunity |
| `tests/test_pxe1_encounter_lifecycle.py` | Initiator plus second account share one encounter/reservations; always waits12seconds; automatic start; Join at deadline rejected; Leave after delayed deadline legal until start commits; Start-first versus Leave-first races; all mixed sources reserved once; owner transfer; empty abandon immediate release; last flee/whole-party defeat30s respawn without rewards; departed/dead/wrong-location excluded; invalid roster recovery; no partial snapshot/cache; startup once; no TTL disappearance; no late join or turn reset |
| `tests/test_pxe1_combat_ui.py` | Supported attacks/skills unchanged; skill list scales with skills rather than targets; one-target picker; self/party confirms where supported; dead/invalid target removed; stale choice no MP/item; in-batch dead target logged Guard/no charge; no silent retarget;6-entry pages; no IDs; PvP shows actual1v1/2v1/2v2 membership, invite-specific Join, side counts/waiting ally and no active Join/Leave/Flee |
| `tests/test_pxe1_gathering_sessions.py` | No instant grant;8s first/120s15th/no16th; zero/low/full durability; independent SHA256 known-vector tests for decoded16-byte seed, big-endian first8bytes, unpadded tick and integer basis-point boundaries; profession-filtered order with locked outcomes unrenormalized; one unit/XP/wear plus tool/session expected revisions; own session not rejected by busy guard; duplicate/crash determinism; Stop equality/stale Stop; logout bounded; restart no catch-up; one edited card |
| `tests/test_pxe1_tools_economy.py` |20costs/83recipes/four aliases/22starters; T1 12g replacement/no repair; ordinary repair formula/no-op; assisted zero-material T2=96g/T4=384g and partial T2=46g; all-higher-tools-broken recovery; no inventory supply/XP; stale/insufficient-funds/duplicate/failure atomicity; last-wear success; threshold warning; backward tool compatibility; exact no-item-ID output/no ordinary delivery; no downgrade; mask survives same-tier replacement/upgrade; knife one claim/wear; six bootstrap entitlements and acyclic path |
| `tests/test_pxe1_pvp_membership.py` | Real service paths for1v1/2v1/2v2; captain approval+ally consent; no self-join/forged inviter/cross-side/grief join; cap races; pending invite not busy; accepted busy including after lock; cross-engagement principal/ally race; all security/novice/respawn and cross-pair checks; individual crime charged once; unchanged300s; failed principal escape early-locks accepted allies; successful escape releases all; outsider/ally escape denied; deadline equality; Leave/start races; legacy Join must show authorized invitation flow |
| `tests/test_pxe1_pvp_runtime_settlement.py` | Both actors on both sides really execute; one shared15s side deadline; per-actor timeout/committed replay; no submitted_actions[0] truncation; affected-side tick once per batch; ally source damage attribution; one defeated actor respawns/releases while teammate continues; multiple pools with exact50/60/70% and repeat1/.5/.25; no multiplied loss; equal deterministic shares/remainders; no last-hit monopoly; dead/fallback-only exclusion; draw/no-recipient destruction; per-person logs/crime; no PvE objectives/mastery/XP; duplicate/CAS rollback; version0/1 receipt isolation; active/terminal restart including allies; side-result+death receipt atomicity |
| `tests/test_pxe1_progression.py` | 50L thresholds; craft B/value/relevance/ceilings at boundaries and clipping; all section9 counts including136-craft route; repeated recipe no reset bonus; zero-XP craft still delivers; gather XP unchanged; old high-level/XP rows preserved; old result replay unchanged; material value static despite runtime price fixture change |
| `tests/test_pxe1_quest_feedback.py` | Increment/complete/ready priority, one source key per event, gear-dependent readiness lost/revalidated; objective-only board no0/0; current contract excluded Available; arrival Turn in CTA; next assignment offered without autoaccept; finale inserted with final claim; fail precommit rolls all back; fail send postcommit keeps one event/reward and next interaction recovers; acknowledged no auto-repeat; historical players not forced; History contains no current professions/gear goals |
| `tests/test_pxe1_character_inventory_shop.py` | Spend outside hub, at cap100, no decrease/overspend, no heal, stale build/gear/travel revision, duplicate Apply; safe-only resets preserved; five-skill branch and every lock reason; compare→Equip exact instance; buy totals/quantity limits; Sell defaults1; risky sale matrix including threshold24/25; warning conditions rechecked after concurrent state change; equipped/nonsellable block; replay after travel and token cleanup; supply/material split |
| `tests/test_pxe1_journeys.py` | Full four-assignment fresh journey through public handler/service seams, final epilogue then Regional home; old completed-player journey; two-player shared pack/owner harvest/participant objective journey; cancel/resume travel, timed gather/tool break/replacement/craft path; ru/en/es path; no game.db side effects |

Retain and run the directly relevant existing suites: `test_world_pve_encounter_foundation.py`, `test_group_pve_runtime_enablement.py`, `test_solo_pve_runtime_handler_flow.py`, `test_character_builds_v1_durability.py`, `test_character_builds_v1_group_journeys.py`, `test_character_builds_v1_mixed_encounters.py`, `test_character_builds_v1_pvp_journey.py`, `test_pvp_live_flow_v1.py`, `test_location_live_pvp_view.py`, `test_location_action_tokens.py`, `test_location_discovery_travel_migration.py`, `test_alpha_transactions_v1.py`, `test_playable_alpha_v1.py`, quest-board tests, `test_professions_economy_v1_*`, gathering tests, inventory/itemization tests and the full `test_regional_adventures_*` group. RAV J11–J14 must prove immutable roster-lock binding, source attribution and independent per-player settlement survive the 12-second start.

Change old assertions **only for explicit supersessions**: dynamic keyboard, 90-second forming expiry, immediate public combat start, instant fresh gathering, no-tools catalogue count, `250*r` XP and unsafe all-or-nothing attribute restriction. Keep old receipt, survival/flee, direct/manual mastery, reward-plan, gear delivery, source reservation and objective invariants. New timed behavior requires advancing a fake clock through real tick ownership; replacing an old test with a direct inventory grant is not valid evidence.

### 18.2 Failure/race matrix

For every new economic operation test crash/failure (a) before debit, (b) after debit before grant, (c) after grant before receipt, (d) immediately after commit before Telegram, and (e) after UI-token deletion with an existing receipt. (a–c) leave no partial state; (d–e) return the same committed result, no duplicate output/XP/wear/gold/objective event. Test cross-player token theft and changed payload hash.

For PvE test join/start and leave/start concurrently, source-reservation collision across ordinary/mixed encounters, and T1/T2 crash/recovery. Each eligible participant receives only their own entitlement; no final-hit dependency; outsider/fled/dead exclusion matches existing policy; manual mastery does not leak to auto/fallback-only actions. Test owner harvest separately from multi-player combat rewards. Victory, last flee and whole-party defeat use30-second anchored respawn; empty unstarted formation releases immediately. For PvP test the explicit group consequence rules separately: all accepted allies execute, every death debits once, teammates continue, total grants+destruction exactly equal pools, and no PvE progression bridges fire.

Transport tests cover message-not-modified, message deleted, forbidden/blocked chat, temporary network failure and callback timeout. None rolls back committed gameplay or extends a turn/formation/session. Activity updates coalesce, and a newly opened menu is not overwritten by an old queued activity render: compare `surface_revision` before sending/editing.

### 18.3 Execution and evidence policy

During each internal implementation phase, run only its focused tests plus the adjacent owner regressions. Example commands, from `rpg/` after the proposed files exist:

```text
python -m pytest -q tests/test_pxe1_schema.py tests/test_pxe1_activity_conflicts.py
python -m pytest -q tests/test_pxe1_encounter_lifecycle.py tests/test_pxe1_combat_ui.py tests/test_group_pve_runtime_enablement.py tests/test_character_builds_v1_durability.py
python -m pytest -q tests/test_pxe1_pvp_membership.py tests/test_pxe1_pvp_runtime_settlement.py tests/test_pvp_live_flow_v1.py tests/test_character_builds_v1_pvp_journey.py
python -m pytest -q tests/test_pxe1_gathering_sessions.py tests/test_pxe1_tools_economy.py tests/test_pxe1_progression.py
python -m pytest -q tests/test_pxe1_navigation_ui.py tests/test_pxe1_quest_feedback.py tests/test_pxe1_character_inventory_shop.py tests/test_pxe1_journeys.py
```

Near the final coherent candidate, run **`python -m pytest -q`** once against that candidate, with sufficient time for the existing broad suite. Record revision, environment, exact command, pass/fail/subtest counts, duration and log path. Fix actual failures and rerun affected suites; a final broad pass must cover the resulting coherent candidate. Do not repeatedly run broad suites after documentation-only edits without a new reason. Do not borrow PEV1/RAV1 historical pass counts or PR236's focused success as PXE1 evidence. Contract and i18n drift tests should include every current catalogue entry, while human viewport validation remains distinct.

## 19. Human Telegram validation plan

**Required before calling the implementation ready: two real player accounts A/B for the Chapter/shared-PvE and baseline PvP checks, plus real accounts C/D for the full2v2 PvP reinforcement check.** Two accounts alone cannot demonstrate a reinforcement joining a PvP encounter whose two principal seats are already occupied; three prove2v1, four prove both sides. These must be actual Telegram accounts on the same test bot/world, not simulated participant rows. Use an ordinary Android/iOS-sized phone viewport (approximately360–430 logical pixels wide, default font), and Telegram Desktop or Web at a normal window size. Swap A/B surfaces for shared encounter checks. Fixtures may seed a separate advanced economy character, but cannot substitute for real invitation/acceptance/action UX.

Record the exact candidate commit and test-bot deployment revision separately, date, Telegram client/platform/version, language, state/setup, expected/actual result and screenshot/message link where appropriate. Do not publish bot tokens or account identifiers in public evidence. Use pass/fail/blocked/not run honestly; human execution is **NOT RUN in this audit**.

| Step | Actions | Required visible result |
|---|---|---|
| H01 — fresh phone entry | A registers fresh in ru; open each permanent entry; resize/reopen Telegram | Six buttons in three rows; no giant dynamic keyboard or “menu updated” spam; meaningful welcome; none of the six loses its route |
| H02 — contextual Aster | Open Location, Nearby, board, shop, guild; inspect Help autocomplete | Local services and actual Chapter opportunity present even with no regional lead; `/journal` and `/activities` discoverable; no raw IDs |
| H03 — Chapter start | Accept First Watch; follow Journal's local route/source controls, gather herbs and fight rabbits | Free full starter tools, no pre-tool grind; one 2-minute maximum gathering card; objective increments inline; available/forming battle visible |
| H04 — full four-assignment loop | Continue Caravan, Outfitter and Homecoming through actual movement, owner harvest, craft, equip and spare sale | Each original objective/reward/location preserved; craft vest gives normal small XP, compare→Equip works, objective-only Homecoming has no0/0; active assignment absent from Available |
| H05 — readiness/finale | Complete Homecoming away from Aster; arrive, turn in, then open Journal and History | Clear route first, Turn in on arrival, immediate one finale/epilogue card, independent Regional Opportunities next; no Chapter II; History is archival; reopening doesn't grant/reannounce finale |
| H06 — local/world map | Open Map from Elmor, mine, coast and an ordinary node; switch World Map; preview discovered Elmor→Aster | Region-first defaults, current marker, readable names, preview6edges/1:45, no raw `/go id`, no active teleport |
| H07 — travel cancel | Start a multi-edge route, cancel between nodes; use old Stop after starting another trip | Visible ETA; lands at last reached node, no destination teleport; old Stop reports old result and does not stop new journey; lower menu usable |
| H08 — travel restart | Restart test bot during an edge, wait past a deadline, reopen | Persisted route resumes with at most one overdue edge and clear updated ETA; no hours of catch-up or duplicate discovery/rewards |
| H09 — real shared formation | A and B stand at the same eligible spawn. A attacks; B opens Location and Join while timer is positive | Both see the same named pack, same participant count and deadline; timer starts live combat without another click; no disappearing encounter or duplicate personal fight. Capture both accounts before/after lock |
| H10 — lock/late/leave | Repeat: B leaves during forming, then repeat with B joining just before deadline. Inspect an outsider/old Join after start | Legal prestart leave, leader transfer if A leaves, same encounter for remaining player; active roster fixed; late/stale action gets clear current status |
| H11 — pack combat | Both choose normal attack and learned skills against multiple enemies; use action→target; allow one side timeout | Compact skill list, valid target page, visible MP/cooldown, no repeated skill per enemy, same side deadline; usable summaries on phone and desktop |
| H12 — per-player result | Win a group fight; compare A/B rewards/objectives; repeat with flee/death cases in controlled test world | Correct independent eligible rewards, no final-hit race, excluded participant gains nothing under existing rule; only current owner gets one legal harvest claim, others see honest explanation; source respawns |
| H13a — two-account PvP baseline | A initiates against B in a legal test location; inspect public Location, preparation, principal escape and prohibited safe-zone initiation | Real300s preparation, both named sides, ordinary1v1 live actions and current security; actor-bound50% escape; no private hidden encounter |
| H13b — real2v1 joining | A/B are principals; A invites C; C opens local encounter and accepts A's named side. Repeat with B inviting C instead. Attempt uninvited Join and stale/other-side callback | Only approved side is joinable; invite alone does not enroll/block C; accepted C is busy and visible; accepted2v1 starts automatically, C receives controls and their attack genuinely changes the opposing actor's HP |
| H13c — real2v2 lock | A invites C, B invites D; both accept before original deadline; capture all four accounts, then all submit actions; repeat one timeout | Counts2/2 on each side, four locked real actors, two orders per side, one15s deadline, no first-order truncation, one affected-side tick, no active Join/Leave; correct action→target and waiting-ally UI |
| H13d — group consequence/recovery | Defeat A while C remains, continue to terminal; repeat with another victim and guarded/frontier material fixtures. Restart during prep, live waiting and after a side/death commit. Attempt old Join/Leave/escape | A alone respawns with correct loss/protection and no lingering busy state; C continues; survivor shares/pools and crime are per player, not final hitter; no duplication after restart; no prior deadline reset; locked allies rehydrate; old tokens cannot affect current roster |
| H13e — prep leave/escape | C accepts then leaves before lock and during delayed startup; race against start; separately have principal fail/succeed escape while ally accepted | Leave-first releases only C, no rejoin; Start-first locks C and old Leave shows combat with no free escape. Failed principal escape starts all currently accepted actors; success cancels/release all without crime refund; C cannot invoke principal escape |
| H14 — gathering/Stop/restart | Run success/failure session, Stop before/at a tick, navigate away/back, leave Telegram, then separately restart server | One edited card, ≤15 total units, finite completion, committed yield retained, no instant-click farm; server restart interrupts without offline grants |
| H15 — break/recover | With controlled durability1, gather/harvest once; buy T1 replacement; inspect ordinary T2 repair. Then all higher tools broken/no materials; use assisted repair; repeat partial-input and old callback | Last attempt succeeds then breaks;12g T1 replacement;24/120 ordinary T2 costs4wood/2iron/1coal/10g; zero-material broken T2 assisted=96g and T4=384g; partial T2 example=46g; no supplied inventory/XP or duplicate charge, no forced downgrade |
| H16 — progression/tools | On separate advanced character use T3 tool at T1/T2/T3 source and try T4; inspect commission and normal upgrade; repeat used commission | Backward compatibility, honest tool/profession gates, exact upgrade costs and one-time bootstrap requirements; no recipe/tool raw IDs and no vendor T4 shortcut |
| H17 — character/build | Spend earned points in wilderness and while gathering; try in combat; reset at hub and outside; inspect both branches | Spend works where allowed, no healing; combat denies; respec hub-only; five skills per branch; friendly mastery/investment locks, no M-codes/coefficients wall |
| H18 — shop/inventory | Buy1, change quantity, sell common1, preview All, attempt last potion/valuable/enhanced/equipped gear sale | Clear modes/prices/balance/result; no automatic All sale; correct selective confirmation/block; exact instance compare/equip, useful advanced actions preserved |
| H19 — locale sweep | Repeat menu, Map/travel, formation/combat, gathering/tool, recipe, ready quest/finale archive and skill detail in en and es; retest long ru labels | No missing keys, raw IDs, clipped critical quantities, giant row or broken plurals; phone and desktop layouts both usable |
| H20 — stale/recovery sweep | Use old callbacks after move, respawn, skill change, sale, language change and session restart; delete an activity card | Meaningful current view or exact prior receipt; no duplicate spend/reward/XP; one recoverable activity surface; no stranded battle flags |

For both players to complete Chapter owner-harvest objectives, each must initiate their own required eligible victories (or be the valid transferred owner), with the other optionally joining. Do not report the deliberate owner-only harvest rule as missing shared combat rewards. For H09–H12, database traces may corroborate same encounter/roster and independent settlement, but **actual two-account Telegram behavior is mandatory evidence**.

Any missing fresh Chapter journey, actual two-account PvE formation→active check, real PvP reinforcement2v1/2v2 check, restart test or ru/en/es viewport check prevents implementation readiness. In particular, two-account PvP cannot be relabelled as group-PvP evidence. It does **not** prevent freezing this design-only contract; those are future execution gates, not unresolved product decisions.

## 20. Implementation packaging and documentation reconciliation

### 20.1 One coherent future Draft PR

Freeze **one Draft PR: “PXE1 — Player Experience & Economy Deepening V1.”** No hard technical boundary requires a second PR. Navigation, activity guards, timed gathering, tools, XP, encounter start and migrations must agree at cutover; separating them would create temporary combinations such as instant gathering with tool wear or running travel without economic guards. Size alone is not a split reason.

Internal commits/phases, kept within that Draft PR:

1. **Contract and additive schema:** copy this accepted contract into `docs/epics/PLAYER_EXPERIENCE_ECONOMY_V1_SPEC.md`; implement checked installer/version adapters and current-state preservation fixtures. New behavior remains inaccessible until integrated; no partial deployment.
2. **Shared activity and encounter lifecycle:** connection-scoped validation/interruptions, atomic PvE forming/start/owner transfer; invitation-approved PvP sides, multi-actor lock/batch/authorization, per-death and group receipts, version0 compatibility; deadline job/recovery and focused race/settlement tests.
3. **Travel and local context:** durable route/cancel/arrival threats, regional Map, unified Nearby and preview flows.
4. **Gathering, tools and economy:** finite ticks/receipts, all five tools, 20 recipes, bootstrap commissions, cross-tier costs, repairs, catalogue2/XP2 and unchanged historical receipt replay.
5. **Navigation, Journal and feedback:** six-button installation/aliases, command registration, objective facts, immediate finale/History/open-world IA and current-context shortcuts.
6. **Character, combat, inventory and commerce presentation:** spend-only attributes, selected skill branch, action→target combat, compare→Equip, shop/recipe/sale protection; all current advanced functionality retained.
7. **Integration and localization:** all ru/en/es keys, mobile budgets, comprehensive public-route guards, consistent result rendering and full fresh/returning-player journeys.
8. **Acceptance and evidence:** focused regressions, final broad suite, phone/desktop and two-account PvE plus three/four-account group-PvP validation, migration/rollback review, documentation reconciliation and exact candidate evidence.

Each phase is independently reviewable within the one PR, but the release unit is the integrated candidate. No production feature switch matrix, long-lived dual system, new dependencies or unrelated cleanup is required. Independent architecture review compares the actual candidate with this contract; the owner retains merge authority. This audit creates neither the PR nor an implementation branch.

### 20.2 Explicit supersessions

| Old rule / authority | New PXE1 rule | Why it changes | Authority after implementation |
|---|---|---|---|
| PEV1 deferred tools; open-world rollout excluded profession tools/durability | Five dedicated durable profession tools, four tiers, starter grants, replacement/repair and recipe gates | User explicitly promotes tools into the gameplay/economy loop | PXE1 spec sections7–10; concise scope amendment in PEV1 spec/report and `LOOT_CRAFT_PROGRESSION_FOUNDATION.md`. Archived rollout remains historical with a supersession pointer |
| PEV1 instantaneous unlimited repeated Gather | One finite120s session,8s ticks,15 attempts, atomic receipts, wear and explicit restart interruption | Remove autoclicker UX and bound unattended generation | PXE1 sections7/15; PEV1 spec gathering section marked superseded, current system map points to session owner |
| PEV1 `250*r` craft XP and tested rapid band progression | Cost-capped small XP, explicit relevance and existing training ceilings; preserve earned rows | Restore sustained crafting progression without wiping players | PXE1 section9; PEV1 progression section/table and report reconciliation note; broad profession foundation still owns long-term intent |
| PEV1 63 active recipes/17 starters; no tool outputs | 83 active/22 starters,20 tool outputs, catalogue2; all63 old recipes preserved | Tool acquisition and low-tier sinks require real recipes | PXE1 sections8–10/15; catalogue tests and PEV1 extension note |
| RAV1/current source 90s forming cleanup and mixed direct-start paths | Shared12s visible formation, job-driven atomic start, no expiry-on-read | Manual observed disappearance and invisible/immediate battles violate intended lifecycle | PXE1 section5; update active `LIVE_COMBAT_SIDE_TURN_SPEC.md`, RAV1 spec affected lifecycle paragraphs and system map; no combat coefficient rewrite |
| Existing forming owner departure can leave owner absent from roster | Deterministic prelock owner transfer; one existing owner harvest role | Reward-plan owner invariant must hold for valid remaining group | PXE1 section5; corresponding RAV/group ownership note, existing participant settlement remains authoritative |
| Current PvP adapter converts only attacker/defender, expires reinforcements, authorizes two actors and settles one winner/loser | Approved invitations and explicit acceptance; cap2per side; accepted allies lock as real actors, entire side batches execute, individual death/pool and aggregate result receipts | Owner explicitly requires the shared pre-live join model for PvP as well as PvE; the shared runtime already supports both multi-actor sides | PXE1 section5.4/15; update the current-adapter note in `PVP_RULESET_FOUNDATION.md`, `CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md`, system map and current-state/report limits. Retain larger/structured PvP deferral |
| Higher-tier repairs require every material and T1 cannot replace higher tools | Ordinary repair plus exact3×sale-price guild supply premium for missing inputs; same repair receipt, no inventory grant/XP | Avoid maintenance deadlock without wiping tool tier or creating free materials | PXE1 sections8/10/15; tool/economy report and acceptance evidence |
| Current handler `15*h*3` long travel and one sleeping final relocation | Persisted discovered route `15h+3(h−1)`, per-edge progress, Cancel and restart rule | Reduce convenience penalty and enable honest cancellable travel | PXE1 section6; update `TRAVEL_AND_TELEPORT_V1.md` ordinary/discovered travel section; teleport remains explicitly disabled |
| Process-local delayed aggression with preemptive battle flag | Durable per-visit threats and atomic real encounter creation/activity interruption | Travel/gather restart and concurrency require a single legal transition | PXE1 sections6/15; world system owner map; current aggression eligibility/5–60s preserved |
| Dynamic persistent menu plus sync messages | Exactly six stable entries with inline context and meaningful one-time migration | Keep Telegram viewport usable | PXE1 sections3/4; alpha/UI contract references and command documentation |
| Safe-hub check conflates free-point spend and redistribution | Spend-only anywhere outside combat; reset remains safe-hub-only | Spending earned progress should be available in the field | PXE1 section13; `CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md` explicit operation distinction; all budgets/skill rules preserved |
| Chapter epilogue effectively requires later Journal visit; History contains live extras | Immediate durable finale/handoff; narrative archive separated | Make completion perceptible and post-Chapter choices clear | PXE1 sections11/12; `PLAYABLE_ALPHA_VERTICAL_SLICE_V1.md` presentation extension; RAV home/History references |
| Current owner-only harvest, RAV lock bindings and T1/T2 settlements | **Retained**, with knife wear in existing harvest transaction | UI/economy work must preserve exact entitlement and deduplication | Existing PEV1/RAV1/combat settlement owners plus PXE1 integration notes; no supersession of reward ownership |

Do not rewrite archived design as if it originally specified PXE1. Add a dated forward pointer where needed, leaving historical evidence truthful. Do not rewrite unrelated foundations such as classlessness, opportunity-cost builds, damage/armor formulas, PvP criminality, world topology or future gear-level100 progression.

### 20.3 Documentation/evidence deliverables in the future PR

The future PR must include `docs/epics/PLAYER_EXPERIENCE_ECONOMY_V1_SPEC.md`, `PLAYER_EXPERIENCE_ECONOMY_V1_REPORT.md`, `docs/evidence/player_experience_economy_v1.json` and `player_experience_economy_v1_human.md`. The report maps each frozen section to implemented owner, migration and acceptance evidence, with any explicit deviations. The evidence JSON records baseline/candidate SHAs, commands/results, scenario statuses, known limitations and links; never store bot credentials or unredacted player identifiers.

Update `docs/DOCS_INDEX.md`, `docs/systems/README.md` and relevant sections of `docs/CLAUDE.md` to point to the new authority and actual owners. Reconcile `PROJECT_STATE_CURRENT.md` and `ROADMAP_CURRENT.md`: while the PR is open, describe PXE1 as candidate/unmerged and preserve the confirmed baseline. After verified merge, record the actual merge SHA/status through the normal workflow. Record deployment and human validation independently; merging a PR is not proof of either. Correct the existing PR234/PR236 and stale NOT RUN/document-status contradictions with evidence, not assumptions.

### 20.4 Scope closure and residual execution risks

No unresolved product decision blocks implementation of this contract. The primary execution risks are atomic encounter initialization, broad activity guards, migration/replay compatibility, Telegram update throttling and material-cost pacing in actual play. Each has an explicit owner and test/human gate above. The XP and tool numbers are frozen V1 decisions; future telemetry can motivate a later explicit balance revision, not an unrecorded “tune later” placeholder in this implementation.

Deferred: safe-hub teleport activation; PvP beyond2per side, unrestricted public side enrollment, active-phase reinforcements and active PvP retreat; structured arenas/guild wars/territory; Chapter II; additional mandatory narrative; world/dungeon/boss expansion; marketplace/auction/trading; resource quality proliferation; combat/weapon coefficient rebalance; classes/armor restrictions; combat gear durability rebalance; framework or destructive database rewrite. Invitation-approved pre-live group PvP specified here is **in scope**. Preserve current supported behavior outside the explicit supersessions.

**Audit completion evidence:** baseline main is `3c5bfa62836c705a6327ce059f4e190b54ccf3e6`; detached source checkout remained clean. The final pass inspected only directly relevant PvP/runtime/legal/receipt code and consolidated this output artifact; it did not restart the project audit. Independent arithmetic confirmed craft counts/tool values; assisted-repair examples are specified above. The complete file includes all continuation corrections, PvP A–N requirements, consequential schema/module/i18n/tests and one-PR packaging, with no dependency on earlier chat corrections. No implementation, live migration, branch, PR, production edit or live Telegram action was performed. Automated gameplay and human validation are future-candidate plans, not claimed completed runs.

VERDICT: CONTRACT_FROZEN
