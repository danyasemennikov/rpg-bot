# RAV1-1 — Regional Adventures & Opportunities V1

Stage 2: final design and frozen implementation contract. Date: 2026-09-27.

This document freezes the product and implementation contract; it is not an implementation report. No repository files, branch, or PR are created by this stage. Sections A–AB form one contract. Tables and defaults are normative: a record inherits the stated defaults unless its row explicitly overrides them. Wording may be polished or translated without changing content, quantities, gates, outcomes, or mechanics.

## A. Baseline and authority

Repository: `danyasemennikov/rpg-bot`. Baseline: `ebd8f73ade53fcadb89942b703a947782276ea1c`, rechecked against GitHub main on 2026-09-27. PR #233, Professions & Economy V1, is merged at this SHA. This is a source-state statement, not evidence of deployment.

The Stage 1 source audit remains evidence; this contract supersedes all Stage 1 campaign proposals and freezes the corrected Stage 1B direction. The implementation must follow `rpg/AGENTS.md` and the existing architecture workflow: one coherent Draft PR, independent candidate review, then the owner's merge decision. Stage 2 neither executes gameplay tests nor claims human validation.

The final targeted audit confirms these integration points:

| Existing authority | Verified contract consequence |
|---|---|
| `game/quest_board.py` | Chapter I and hunts share existing active-contract state. Keep it; projects use separate storage. Five definitions exist without reachable boards. |
| `game/pve_live.py`, `lock_open_world_pve_roster_for_runtime_start` | An IMMEDIATE transaction finalizes the participant roster and changes linked spawns from forming to active. Capture project eligibility inside this transaction, before its commit. |
| `game/pve_reward_settlement.py` | Immutable source units, prepared reward plan and atomic T2 application already own combat rewards and hunt progress. Extend T2 with a narrow project observer. |
| `game/action_receipts.py` | Opaque 16-hex tokens bind player, action kind, location, travel revision and 900-second expiry. Refresh invalidates pending tokens of the same kind. |
| `game/economy_actions.py`, `game/crafting_runtime.py` | Durable language-neutral receipts and same-transaction production grants support repeat delivery and personal-craft observation. |
| `game/profession_schema.py` | `economy_schema_migrations` and `economy_action_receipts` already exist; reuse them without changing their existing rows or meanings. |
| `game/locations.py`, `game/enemy_profiles.py` | Canonical special spawns and atomic mixed reservations exist. All frozen combat compositions use mobs already placed at their locations. |
| `handlers/location.py` | Inn price is `INN_REST_COST_GOLD = 12`; travel is discovery/path/revision controlled. Reuse these authorities. |

Current source has no canonical Greyfang special spawn. `quests_data.py` is not a live authority. Existing docs that call PR233 unmerged are stale and must be reconciled in the eventual RAV1 PR.

## B. Product outcome

After Aster–Elmor onboarding, the Journal opens onto independent work, places, dangers and personal pursuits. A player may explore any region, remain local, follow two projects while hunting, pursue equipment or professions alone, or leave a story unfinished indefinitely. There is no Chapter II assignment, prescribed regional order, regional completion key, final region, or world finale.

The finite catalogue contains seven projects, two direct requests, ten discoveries and one independent cache. Three standing deliveries, existing hunts, ordinary combat, gathering, crafting and equipment progression give reasons to return after finite content is resolved. The Sunscar package is exploration and danger rather than another NPC-led regional story.

## C. Frozen principles and global defaults

1. All new content is available to a registered character subject only to its explicit local conditions. Chapter I completion is not a gameplay prerequisite. The post-Chapter-I Journal changes presentation, not entitlement. No region depends on another region's story.
2. Character level, mastery, professions, gear tier and route depth remain separate. No combined power score, regional level lock, or level-100 redesign.
3. Ordinary projects must be solo-viable through existing builds and equipment. Groups are optional. No objective needs concurrent population.
4. All project rewards and discoveries are personal. An NPC's response can differ between players; shared terrain, spawns and services do not branch.
5. Projects are lifetime finite and cannot be cancelled, reset or reaccepted. Leaving, unpinning or ignoring one is the only pause operation. Seven simultaneously active projects are valid; pins do not impose an acceptance limit.
6. Delivery accepts any legally owned qualifying stackable, including prior production and permitted transfers. Only the explicitly labelled practice task requires new personal production. No gear hand-in.
7. All peaceful mutations require the existing peaceful-player check, canonical location and travel revision. No clicking through a battle, travel race or wrong-location screen.
8. Rewards below are exact. Unspecified reward components are zero. No discovery gives XP, gold or items merely for opening a description. No reward scales with level, order, language or chosen outcome.
9. All finite content has no reset or cooldown. Standing deliveries have no timer and consume fresh goods each attempt. Named and mixed encounters use existing shared spawn lifecycle and 30-second post-victory respawn; forming expiry remains 90 seconds.
10. Every frozen record has ru/en/es presentation. Raw IDs are internal only. No acceptance based on Russian fallback.

## D. Exact content catalogue

### D1. Identity, ownership and record conventions

Stable IDs below are lifetime identities, not translated titles. `catalog_version=1` for every new definition. Project steps and objective IDs are scoped by project; keys are never reused with different semantics. Content text is under `rav1.content.<id>.*`; owner/landmark labels under `rav1.people.*` and `rav1.landmarks.*`. Journal aggregation derives status from the owning authority.

`P` means a project row; `F` a content fact; `C` a lifetime reward claim; `E` a durable economy receipt; `B` a combat eligibility binding. Their exact schemas appear in H. Every rewarded finite record has `C(player_id, content_id)`; a fresh callback never creates a new entitlement. Each project pays its entire listed reward when its last objective commits, not per step. Reward owner is the individual completing character. Combat loot is additional existing settlement loot, never duplicated by the project.

NPCs are fixed local people, not a dialogue engine: Mara, woodcutter (`mara`, Elmor); Iven, sled driver (`iven`, Karn and the stalled sled); Sera, archivist (`sera`, Ember); Oren, ferryman (`oren`, Velm); Lida, medic (`lida`, Velm). Frost standing supplies go to Karn's existing guild storekeeper, a role label without another named character. Sunscar has no new quest-giver. The same NPC appearing at a worksite is scene text, not a moving entity or escort simulation.

### D2. Projects — all objectives and transitions

Each numbered entry is one step. Steps are ordered; objectives within a step use the explicit ALL or ANY rule. Completion automatically opens the next step in the same transaction. `fact` objectives can consume earlier inspections; other events cannot consume earlier actions. `respond` is a local explicit button, not free-form dialogue. Inspection does not automatically accept a project.

| ID / title / region | Start and visibility | Exact steps | Completion reward | Purpose / durable record |
|---|---|---|---|---|
| `ww_tool_roll` — The Lost Tool Roll / Westwild | Public Elmor listing; accept from Mara at `hub_westwild`. No prerequisite. | 1 `recover`: `kill` objective `wolf`, one `forest_wolf` at `westwild_n3`, normal or elite, ordinary or special. A wolf dragged a meat-scented tool roll into its resting place; a qualifying victory after activation secures it as narrative evidence, not an inventory item. 2 `return`: `respond` objective `report` to Mara at `hub_westwild`. | 40 XP, 18 gold | A short return trip and legitimate hunt overlap. P+C; kill B/T2; final E. |
| `fs_jammed_sled` — The Jammed Sled / Frostspine | Public Karn listing; accept at `hub_frostspine` from Iven OR at `old_mine_entrance` beside the sled. | 1 `damage`: `fact` `inspect` requires `fs_sled_damage`. 2 `repair`: ANY of `deliver` objective `materials`, consume `wood_common` ×2 + `iron_ore` ×1 at `old_mine_entrance`; OR `kill` objective `clear_lizard`, one ordinary normal `rock_lizard` at `frostspine_n2`, to retrieve an abandoned repair brace beside its nest. Both approaches repair the runner; first completed wins. 3 `report`: `respond` `receipt` to Iven at `hub_frostspine`. | 70 XP, 30 gold, `enhance_shard` ×1 | Low-profession logistics with a combat alternative. P stores winning objective as `step_results.repair`; no outcome branch or extra choice UI. P+C+E, B if combat. |
| `ar_two_names` — Two Names on One Stone / Ashen Ruins | Public Ember listing; accept from Sera at `hub_ashen_ruins`. | 1 `evidence`: ALL of `fact` `temple`=`ar_temple_names` and `fact` `garden`=`ar_garden_ledger`, either inspection order, including before acceptance. 2 `record`: `choose` `attribution` at Sera in `hub_ashen_ruins`: `shared_credit` or `leave_unattributed`. | 50 XP, 20 gold | Interpretation, not combat gating. P+C+E; permanent choice and different local archival response. |
| `ar_unquiet_storehouse` — The Unquiet Storehouse / Ashen Ruins | Public Ember listing; accept from Sera at `hub_ashen_ruins` OR the sealed storehouse at `ashen_n3b1`. Independent of Two Names. | 1 `seal`: `fact` `mark`=`ar_storehouse_seal`. 2 `watch`: `kill` `guard`, one ordinary normal `skeleton_guard` at `ashen_n3b1`, after step activation; the watcher's defeat permits examination of an echo-bound household seal. 3 `disposition`: `choose` `seal_fate` at `hub_ashen_ruins`: `archive_seal` or `leave_seal`. | 80 XP, 30 gold | Local supernatural unease and an armored opponent; no summoned guardian or private dungeon. P+C+E+B. |
| `mv_ferry_crew` — The Missing Ferry Crew / Mireveil | Public Velm notice; accept from Oren at `hub_mireveil` OR the abandoned rope at `mireveil_n5`. | 1 `trail`: ALL of `fact` `ford`=`mv_ford_marks` and `fact` `channel`=`mv_channel_rope`, unordered and earlier inspections valid. 2 `clear`: `encounter` `channel_threat`, one victory over exact mixed ID `rav1_mireveil_n6_crosscurrent` at `mireveil_n6`, after activation. 3 `salvage`: `choose` `cargo` at `mireveil_n8`: `save_supplies` or `save_log`. The crew is found alive on a bank; only one damaged cargo bundle is recoverable. 4 `return`: `respond` `report` to Oren at `hub_mireveil`. | 100 XP, 40 gold, `health_potion_small` ×2 | Four-step travel, tactical fight, remembered practical choice. P+C+E+B. No escort or timed rescue. |
| `ss_camp_bearings` — Camp Bearings / Sunscar | Local camp notice at `sunscar_n8a1`; public regional lead names the abandoned camp but hides the cache. Accept there. | 1 `bearings`: ALL of `fact` `camp`=`ss_camp_marks` and `fact` `pillars`=`ss_pillar_shadow`, either order and before acceptance permitted. 2 `cache`: `respond` `open_cache` at `sunscar_n8a1`; preview reveals the exact reward and lifetime status. | 30 XP, 12 gold, `field_ration` ×1 | A landscape puzzle: the pillar shadow and camp marks identify a sheltered supply recess. No numeric puzzle, random code or NPC chain. P+C+E; cache entitlement belongs to this project only. |
| `mv_medic_practice` — Lida's Fresh Batch / Mireveil | Public optional specialist listing from Lida at `hub_mireveil`. Explicit label: personal alchemy practice, starter recipe, two new crafts. No level/knowledge gate on acceptance; blocked details show actual recipe requirements. | 1 `practice`: `craft` `fresh_tonics`, personally complete recipe `field_tonic` twice after activation, output `health_potion_small`, anywhere the existing craft authority legally allows it. 2 `hand_in`: `deliver` `tonics`, consume `health_potion_small` ×2 at `hub_mireveil`. Once process evidence exists, any owned matching potions may fulfill the hand-in. | 30 XP, 15 gold | Demonstrates process evidence without forcing advanced profession grinding. P+C+E; craft receipt observer. |

There are exactly **18 project steps** and **22 objective records**: Tool `wolf,report` (2), Sled `inspect,materials,clear_lizard,receipt` (4), Names `temple,garden,attribution` (3), Storehouse `mark,guard,seal_fate` (3), Ferry `ford,channel,channel_threat,cargo,report` (5), Camp `camp,pillars,open_cache` (3), Practice `fresh_tonics,tonics` (2).

### D3. Discoveries and auxiliary inspections

All inspections require being physically at the listed canonical location and peaceful. The Inspect button records `F(player, id)`, with no reward. Reinspection returns the same finding plus its recorded status. Local descriptions are visible on arrival; Journal lists the individual discovery only after inspection. Public leads can mention general places without granting F or location discovery. Discoveries are lifetime, nonrepeatable facts with repeat-readable prose. Objective progress is separately reconciled from F.

| ID / landmark / location | Canonical finding and mechanical use | Visibility / reason |
|---|---|---|
| `ww_greyfang_tracks` / Split-paw tracks / `westwild_n3` | A wolf with a split outer claw returns to these hills. Opens a Journal source link to Greyfang's existing hunt board; no spawn, accuracy or reward bonus. | Local; optional context for the named hunt. |
| `ww_root_marks` / Woodcutter's root marks / `westwild_n7` | Marks point to a dry recess beside the roots. Reveals `ww_root_cache`. Rootbound Hollow remains descriptive metadata, not a dungeon. | Secret: appears in Nearby only at this node; one optional cache. |
| `fs_survey_stone` / Survey stone / `frostspine_n4` | Road crews distinguished the pass from a mine spur; notes frostpine higher along the route and directs players to existing source information. No movement unlock. | Local; route and profession identity. |
| `ar_temple_names` / Recut memorial / `ashen_n3a2` | Two names occupy the same memorial line; the stone shows an old correction rather than a king's prophecy. Feeds Names. | Local, named by the accepted project. |
| `ar_garden_ledger` / Gardener's tally / `ashen_n3c1` | A weathered tally shows two workers maintaining the same garden in different seasons; attribution remains uncertain. Feeds Names. | Local; alternate evidence route and Ruins Patrol context. |
| `ar_storehouse_seal` / Household seal / `ashen_n3b1` | The storehouse repeats the sound of a door closing; a guard watches an ordinary household seal. Feeds Storehouse. | Local; bounded supernatural story. |
| `mv_ford_marks` / Ferry landing marks / `mireveil_n5` | Scrapes and cut rope indicate that the crew went toward the channel, not that they died. Feeds Ferry. | Local; organic project entry. |
| `mv_fungal_observation` / Fisher's note / `mireveil_n8a1` | Slugs and slime collect near the fungal side water; the note distinguishes ordinary marsh fishing from deeper, more demanding sources. Links existing fishing source details. | Local; optional discovery with no collection grind. |
| `ss_camp_marks` / Camp bearing marks / `sunscar_n8a1` | Cut marks align the camp's dry recess with the two pillars. Feeds Camp Bearings. | Local; first half of landscape puzzle. |
| `ss_pillar_shadow` / Pillar shadow / `sunscar_n8a2` | A fixed description of the pillar shadow confirms the bearing; no real-time day/night test. Mentions the Salt-Ridge Drifter. Feeds Camp Bearings. | Local; second half and optional named danger. |

Two additional **interaction** records create facts but are not marketed as discoveries or counted in the ten: `fs_sled_damage` at `old_mine_entrance` (split runner, spare brace near rock lizards at `frostspine_n2`); `mv_channel_rope` at `mireveil_n8` (rope tied safely above the channel, signs of survivors upstream and predators at `mireveil_n6`). Both can be inspected before acceptance, have zero rewards, use F+E, and are repeat-readable. Their exact semantic text is fixed here.

### D4. Direct finite requests and independent cache

| ID / title / owner | Location, visibility and eligibility | Atomic action / exact reward | Persistence / Journal / purpose |
|---|---|---|---|
| `ww_woodcutter_provisions` — Provisions for the Woodcutters / Mara | `hub_westwild`, public; no prerequisite | Consume `field_ration` ×2; award 20 XP, 18 gold. Prior craft/gifts count. | C+E, no P; Nearby/region detail until claimed, then Resolved. A finite service premium for everyday cooking. |
| `mv_medic_table` — The Medic's Table / Lida | `hub_mireveil`, public; independent of Ferry and Fresh Batch | Consume `herb_common` ×4; award 20 XP, 18 gold. Any legal goods. | C+E, no P; practical work with level-1 gathering available elsewhere and trade allowed. |
| `ww_root_cache` — The Dry Root Cache / landmark | `westwild_n7`; hidden until F `ww_root_marks`; physical presence required | Claim `health_potion_small` ×1 and `enhance_shard` ×1; 0 XP, 0 gold; consumes nothing | C+E, no P or new F. Secret one-time reward; visible in Resolved after claim. |

The five **short finite opportunities** are the three two-step short projects (Tool, Camp, Fresh Batch) plus these two direct requests. This is an editorial subset, not five additional records. The independent cache is counted separately.

### D5. Standing deliveries

| ID / title / receiver | Exact location / input per attempt | Payout | Availability and role |
|---|---|---|---|
| `ww_ration_order` — Woodcutters' Standing Order / Mara | `hub_westwild`; `field_ration` ×2 | 10 gold, 0 XP, no items | Public immediately; unrelated to the finite provisions request. Convenient local food resale with no conversion premium. |
| `fs_forge_supplies` — Forge Supply Basket / guild storekeeper | `hub_frostspine`; `iron_ore` ×2 + `coal` ×2 | 20 gold, 0 XP, no items | Public immediately; basic mining output at existing NPC sale value. No frostpine requirement. |
| `mv_stew_order` — Meals for the Landing / Oren | `hub_mireveil`; `pe_marsh_stew` ×2 | 12 gold, 0 XP, no items | Public immediately; optional advanced cooking use or delivery of acquired goods. No profession gate on hand-in. |

Each attempt is one new preview token and one E receipt. No acceptance record, stock quota, timer, cooldown, daily reset, streak, reputation, escrow or cumulative milestone. No profession XP on delivery. Cancelling the preview consumes nothing; retrying a committed token returns its prior result. New attempts require another full batch. Standing jobs never enter Resolved or occupy a hunt/project slot; show in Local Work.

### D6. Remaining catalogue ownership

Two named targets and four mixed recipes (two retained, two new) are specified in L–M. Five existing hunt activations are specified in L. Five regional summary records are specified in E. These references do not create duplicate reward owners, project instances or completion records. Flavor responses and public leads are fields of those records, not additional quest definitions.

## E. Regional manifests

All five region summaries are always readable after registration, shown together after onboarding. Fixed display order is the existing map order: Westwild, Frostspine, Ashen Ruins, Sunscar, Mireveil. This is a map order, not a recommendation or completion sequence. Every summary explicitly says its opportunities are independent.

| Region / summary record | Identity and public entry | Finite content and discoveries | Combat / economy / repeat / services | Return, risk, topology and exclusions |
|---|---|---|---|---|
| Westwild / `region_westwild` | Workers and hunters near Elmor; lead: “Recover a worker's tools, inspect wolf tracks, or provision the woodcutters.” Mara and existing Elmor/Aster hunt boards. | Tool; provisions; tracks and root marks; root cache. | Existing wolves, boars, spiders and Greyfang hunts; Bear Hunting Party retained. Ration order; ordinary wood/herbs/hunting; existing Elmor shop/inn/board/guild unchanged. | Repeat hunts, loot, supplies and deeper forest. Label “Early route; deeper packs and elites are optional.” Elmor branches from n5; wolves at n3, cache at n7, mixed at n8. No dungeon, forest campaign or new end boss. |
| Frostspine / `region_frostspine` | Transport repairs and sturdy opponents; lead: “Inspect a stranded sled near the old mine, supply Karn's forge, or hunt white wolves.” Iven and n5 board. | Sled; survey stone. | Activate white-wolf hunt at n5; retain mine hunts at Karn. New Stone at the Pass mixed at n6. Forge supplies; existing Karn shop/inn/board/guild. | Ore, coal, deeper frostpine/gems, hunt rank and optional armored fight. Label “Repair work has a basic-material or single-opponent route; the pass's armored pair is optional.” Old Mine is a spur from n1, Karn from n5, survey at n4; no invented mine-to-Karn shortcut. No full mine expansion or compulsory high mining level. |
| Ashen Ruins / `region_ashen_ruins` | Independent investigation and uneasy remains; lead: “Compare an old memorial with a garden tally, or examine a haunted storehouse.” Sera at Ember; Old Temple board. | Names and Storehouse in either order; temple, garden and seal discoveries. | Activate zombie hunt; retain Ruins Patrol. No new standing delivery or named boss. Existing guild plus new paid inn at Ember. | Other investigation, local records, undead combat and gear. Label “Undead begin above the earliest field creatures; inspection needs no fight, the storehouse guard is armored.” n3 branches a→temple→Ember, b→storehouse, c→garden. No branch is an endpoint; no final dungeon, relic-key campaign, reputation or universal mystery. |
| Mireveil / `region_mireveil` | Water routes, practical rescue and medicine; lead: “Follow a missing ferry crew, supply a medic, or bring meals to the landing.” Oren/Lida at Velm; boardwalk hunt board. | Ferry, Fresh Batch, Medic's Table; ford and fungal discoveries; channel auxiliary fact. | Activate leech hunt; new Crosscurrent Predators at n6. Stew order, fishing, herbalism and ordinary harvest; existing guild plus new inn at Velm. | Return to people, optional practice, work and deeper sources. Label “The ferry investigation includes two predators together; venom and draining attacks matter. Medicine practice is optional.” Hub off n5→n5a1; channel n8; fungal branch n8→n8a1→n8a2. No timed rescue, escort or mandatory advanced herbalism. |
| Sunscar / `region_sunscar` | Bearings, open ground and elusive danger; lead: “Read the abandoned camp's bearings, take scorpion work, or seek an elusive elemental.” Mirage board; camp landmark. | Camp Bearings; camp and pillar discoveries. | Activate two existing hunts; add Salt-Ridge Drifter at pillars. Existing desert gathering/cooking and ordinary field loot; no new standing delivery. Existing guild plus new inn and board at Mirage. | Elemental precision fight, hunts, camp revisit, salt and later oasis/desert materials. Label “Scorpions are closer to the approach; pillars and elemental hunts lie deeper. The named elemental is optional.” Hub off n5→oasis n5a1; camp/pillars branch from n8. No NPC storyline, regional finale, survival meter or compulsory oasis cooking. |

South Coast remains only `south_coast_shore`, with existing shore creatures, fishing/herbs and shore-broth source/recipe links. Old Mine remains only `old_mine_entrance`, existing rats/bats/ore/coal/gem sources and the sled scene. Neither receives a regional summary record, regional completion state, new route, new inn, dungeon or project chain. Location safety and PvP security classifications are unchanged everywhere; adding a board does not make a frontier site safe.

## F. Content architecture

Freeze four layers:

1. Existing `HuntContract`: Chapter I and conventional hunts; one active contract exactly as baseline. Keep all historical contract identities and existing claim/rank rules.
2. Small local-project runtime: seven fixed definitions, monotonic finite progress and three permanent choices. Its observers are ordinary function calls from authoritative transactions, not an event bus.
3. Lightweight interactions: inspect facts, direct hand-ins, one cache and standing jobs. No project row for a one-step interaction.
4. Opportunity read model: unions the preceding state plus existing gear/profession navigation. It may compute labels and sorting; it cannot write progress, completion, reward or location-discovery state.

Use plain frozen dataclasses or typed dictionaries and explicit procedural dispatch. No plugin registry, arbitrary predicate evaluator, script execution, universal dialogue tree, generic trigger framework, procedural generator or historical quest authority.

## G. Static project schema and transition limits

Exact definition fields:

```text
ProjectDefinition:
  project_id: stable ASCII ID from D2
  catalog_version: 1
  region_id: existing canonical region ID
  text_prefix: rav1.content.<project_id>
  start_locations: nonempty tuple of canonical location IDs from D2
  speaker_id: mara | iven | sera | oren | lida | null
  public: bool                         # Camp false; all other projects true
  steps: tuple[StepDefinition, ...]
  reward: {xp: int, gold: int, items: tuple[(existing_item_id, positive_qty)]}
StepDefinition:
  step_id: ID from D2
  mode: all | any                      # only Sled.repair uses any
  objectives: tuple[ObjectiveDefinition, ...]
ObjectiveDefinition:
  objective_id: ID from D2
  kind: fact | deliver | kill | encounter | craft | respond | choose
  required: positive int               # craft=2; all other scalar objectives=1
  locations: tuple[canonical IDs]      # empty only for craft=any legal craft location
  target: kind-specific record below
Targets:
  fact: {fact_id}
  deliver: {items: tuple[(item_id,qty)]}
  kill: {mob_id, profiles: tuple[normal|elite], special: any|ordinary}
  encounter: {mixed_encounter_id}
  craft: {recipe_id, output_item_id}
  respond: {action_id}                 # report, receipt or open_cache as enumerated
  choose: {choice_id, values: tuple[str,str]}
```

`fact.locations` must equal the fact definition's location even though evaluation can occur remotely after inspection. For `choose`, target values are exactly those in D2 and J. Respond and choice targets use the project speaker except the landmark cache. Recipe references resolve the existing PEV1 recipe, not an output-only match.

Project availability is hard-coded: registered player, not completed, local start location, peaceful. There is no free-form prerequisite field because this catalogue does not use one. Publicity and summaries do not add gates. Reward is always terminal; no separate repeatability or arbitrary aftermath-expression fields. Choice-dependent aftermath is an explicit lookup over the three frozen choices.

Maximums: four ordered steps; two objectives per step; one ANY step per project; one two-valued choice per project; no nested Boolean trees, optional hidden steps, timers, loops, project dependencies, repeat instances or branch graphs. Choices converge immediately into the same following step or the same terminal completion. Sled's ANY is a method selection, not a permanent world outcome. Frozen catalogue uses three choices and one ANY step. No unused objective kinds such as gather, harvest, possess, equip or visit are added.

All quantities and target locations are validated at startup. Unknown IDs, unavailable mob placements, nonexistent recipes/items, illegal special/profile combinations, duplicate objective IDs, invalid translations or invalid rewards make the catalogue invalid. Do not silently drop a bad record and run a partial world.

## H. Player persistence and migration

### H1. Five new tables, no existing-table rewrites

The following DDL specifies storage, not implementation code delivered by this stage. Every foreign key uses default NO ACTION; no cascade deletes. Application validators additionally enforce catalogue membership and exact JSON shapes. Connections performing RAV1 writes must enforce foreign keys; validate without altering existing unrelated data. Timestamps use existing SQLite UTC `CURRENT_TIMESTAMP` convention.

```sql
CREATE TABLE rav1_projects (
  player_id INTEGER NOT NULL REFERENCES players(telegram_id),
  project_id TEXT NOT NULL,
  catalog_version INTEGER NOT NULL CHECK (catalog_version = 1),
  state TEXT NOT NULL CHECK (state IN ('active','completed')),
  step_index INTEGER NOT NULL CHECK (step_index BETWEEN 0 AND 4),
  progress_json TEXT NOT NULL,
  choices_json TEXT NOT NULL,
  step_results_json TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT,
  PRIMARY KEY (player_id, project_id),
  CHECK ((state='active' AND completed_at IS NULL) OR
         (state='completed' AND completed_at IS NOT NULL))
);
CREATE TABLE rav1_facts (
  player_id INTEGER NOT NULL REFERENCES players(telegram_id),
  fact_id TEXT NOT NULL,
  catalog_version INTEGER NOT NULL CHECK (catalog_version = 1),
  location_id TEXT NOT NULL,
  discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (player_id, fact_id)
);
CREATE TABLE rav1_claims (
  player_id INTEGER NOT NULL REFERENCES players(telegram_id),
  content_id TEXT NOT NULL,
  catalog_version INTEGER NOT NULL CHECK (catalog_version = 1),
  request_id TEXT NOT NULL,
  reward_json TEXT NOT NULL,
  claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (player_id, content_id),
  UNIQUE (player_id, request_id)
);
CREATE TABLE rav1_pins (
  player_id INTEGER NOT NULL REFERENCES players(telegram_id),
  slot INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 3),
  owner_kind TEXT NOT NULL CHECK (owner_kind IN ('project','hunt','gear')),
  owner_id TEXT NOT NULL,
  PRIMARY KEY (player_id, slot),
  UNIQUE (player_id, owner_kind, owner_id)
);
CREATE TABLE rav1_combat_bindings (
  encounter_id TEXT NOT NULL REFERENCES pve_encounters(encounter_id),
  player_id INTEGER NOT NULL REFERENCES players(telegram_id),
  schema_version INTEGER NOT NULL CHECK (schema_version = 1),
  bindings_json TEXT NOT NULL,
  snapshot_hash TEXT NOT NULL,
  captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  applied_at TEXT,
  PRIMARY KEY (encounter_id, player_id)
);
```

Only PK/UNIQUE indexes above are added; per-player catalogue is bounded and does not need speculative status indexes. Encounter lookup uses the leading combat PK. Existing economy receipt player/time index handles result history. No new generic event log, project instance table, objective row table or migration table.

Project JSON is deliberately bounded:

* `progress_json`: all 22 possible scoped objective keys across the catalogue are defined statically; each project row contains only its own keys, in `step_id.objective_id` form, integer values from zero to required. For delivery the scalar is 0/1 for the whole basket. Initial values are zero, except reconciled prior facts. No inventory or narrative text in this JSON.
* `choices_json`: `{}` or the project's one `choice_id: value`; immutable once set. Sled has no choice entry.
* `step_results_json`: completed step ID to sorted list of objective IDs that satisfied it. An ANY step contains exactly its winning objective; ALL contains every objective. This preserves repair method and terminal history without another fact table.
* `step_index`: zero-based current step; when completed, exactly `len(steps)`. Runtime rejects inconsistent index/state/progress instead of repairing by inventing completion. Completed state requires its C record, and C for a project requires completed state, within the same commit.
* Revision increments once per transaction that changes a project's progress, step, choice or state. Several changes in one transaction still increment once. Re-reading, pinning and receipt replay do not change it.

Facts contain only the twelve enumerated inspections. Project completion is owned by P, one-time payout by C; they do not share F. `reward_json` records exact applied XP, gold, item quantities, resulting level/XP/gold and provenance, without localized text. `request_id` is `ui:<16hex>` for these claims. Claims are retained permanently. Economy receipts retain full operation/result and are also not deleted by RAV1.

Each B row contains a canonical JSON list, possibly empty, sorted by `(project_id, step_id, objective_id)`. Each entry stores `project_id`, `catalog_version`, `step_id`, `objective_id`, `kind`, and `source_unit_ids` sorted from the immutable combat source snapshot. An encounter objective additionally stores `mixed_encounter_id` and lists the entire required source roster. The SHA-256 is over canonical compact, sorted-key JSON including encounter ID, player ID, schema version and that list. It is checked on recovery; the list/hash never change after roster lock. `applied_at` is set only in the corresponding T2 application. No project revision is used to reject valid delayed combat credit merely because an unrelated UI pin changed.

### H2. Migration lifecycle

Add exactly one marker, `regional_adventures_v1`, in the existing `economy_schema_migrations`. Do not add a per-player migration flag, fake project rows or an implicit completion backfill. Run after existing PEV1 schema setup and after PvE tables exist, before registering/serving RAV1 callbacks. The RAV1 migration owns one IMMEDIATE transaction, or an explicit savepoint when the caller already owns the startup transaction; it never commits its caller's unrelated work.

Inside that boundary: verify baseline prerequisite schemas and marker compatibility; inspect whether each of the five table names exists; validate any existing table's exact columns, affinities, nullability, defaults, PK order, UNIQUE constraints, FKs and checks; create missing tables only in a clean first install; validate catalogue and existing RAV1 rows; validate relevant foreign keys; insert the marker last; commit. First install means marker absent and all five tables absent. Marker absent with some/all tables present is accepted only if every existing RAV1 table is the exact frozen shape and empty; create missing tables and finish atomically. Unexpected nonempty unmarked RAV1 state fails closed for investigation. Marker present requires all five exact tables and compatible rows. Unknown RAV schema/row versions, changed target IDs or incompatible constraints fail closed. A second startup validates and makes no data changes.

Exceptions roll back every RAV1 table/row/marker change in that attempt. A crash before commit leaves the previous state; after commit leaves a complete installation. Do not reset/drop/rename legacy tables, erase historical unknown items, drain prepared combat rewards as a migration shortcut, re-seed player rewards, or normalize away unexpected data.

Operational rollback is stop traffic, preserve a database backup, and revert application code only with the five additive tables and receipts retained. Do not downgrade or delete their rows. Old binaries may ignore RAV1 state; no RAV1 mutations may run while those binaries are active. Re-upgrade validates the retained state. Restoring a pre-upgrade backup after live player writes would lose those writes and is not the contract's rollback method.

## I. Exact objective semantics

All objective progress is personal, capped at required, monotonic and independent of pins. There is no cancellation/reaccept lifecycle for any type. Unknown versions fail closed; stale mutation previews re-render current state without changing it. One legitimate event can advance all independently active and explicitly matching objectives; that is not duplicate reward issuance. No observer manufactures inventory evidence.

| Kind | Authority and timing | Retroactivity / location / quantity | Replay and overlap |
|---|---|---|---|
| `fact` | F created by successful local Inspect transaction; evaluate existing F on project acceptance and step activation, and reconcile matching active projects in the same new-inspection transaction | Only the exact content fact counts; existing location discovery does not. Earlier RAV1 inspections count. One fact = scalar 1; inspection requires its exact node, evaluation may occur anywhere. No companion/group sharing. | F PK prevents duplicate discovery; progress is set/capped, not incremented repeatedly. One fact may satisfy each matching project; catalogue currently has one owner per fact. |
| `deliver` | Explicit confirmation; existing stackable inventory authority under IMMEDIATE lock; consume entire basket, update P or finite C/standing E as applicable | Current inventory qualifies regardless of acquisition time or legal giver. Exact item IDs/quantities, no substitutes, no partial deposit. Must be at objective/job node and currently active step. | Same E returns result; fresh token rechecks step/C and inventory. If two objectives need the same item, one submission consumes only its chosen basket and advances only that delivery objective. It does not broadcast possession or spend the same units twice. |
| `kill` | B eligibility at roster lock, credit only through successful authoritative PvE T2 | One qualifying source unit gives 1, capped; D2 defines exact mob/location/profile/special filters. No historical kill credit. Only alive eligible locked recipients receive progress; no proximity, party invitation or final-hit ownership shortcut. | Atomic T2 once; match source unit identity, not display name. A fight may also advance the existing hunt and another snapshotted project. Excess units do not carry into future steps. |
| `encounter` | B at roster lock; T2 verifies victory, exact mixed ID and its complete immutable source roster | Exactly one complete qualifying encounter gives 1. Separate single kills, a lookalike manually grouped roster or a different recipe do not count. Exact location; same recipient exclusions as kill. | One encounter credit, never one per enemy unit. No later acceptance/step activation can use the old encounter. |
| `craft` | Successful `craft_recipe` transaction, after recipe/output grant and normal profession XP, before receipt/commit; capture active matching objectives at entry under the same write lock | Requires actual crafter, `field_tonic`, exact successful output. Quantity is successful recipe executions: two executions, not quantity of owned potions. Existing recipe yields one; failed crafts count zero. Any legal crafting location; before-activation receipts never count. | Recovered receipt returns before the observer. Production and progress commit or roll back together. One successful craft can satisfy Chapter I's own craft condition and Fresh Batch if both legitimately active. No extra profession XP. |
| `respond` | Explicit local final action with active step and token-bound revision | One action; only stated node and owner/landmark. No earlier speech credit. Does not inspect new facts or demand an inventory story object. Camp cache response is its terminal reward claim. | E/C/P enforce once; reward failure rolls back response and project completion. Reopening dialogue is read-only. |
| `choose` | Preview, then irreversible confirmation in one peaceful IMMEDIATE transaction on active step | One of exactly two static values, one permanent value per project; exact scene location. No reward distinction. Preview/selection alone is not a choice. | P immutable choice, E and revision compare prevent double selection and stale alternate buttons. Same receipt returns committed outcome; different token shows the saved outcome without mutation. |

Event observers evaluate only the set active at the start of the authoritative event. Automatic transition cannot reuse that same kill/craft/response for a newly activated event objective. Only existing facts can be reconciled immediately on entering a step. All scalar objectives have required=1 except craft=2; delivery basket quantities are not progress counters.

## J. Lightweight scenes, facts and permanent choices

### J1. Interaction schema and fact separation

Lightweight definitions have exactly `content_id`, `catalog_version=1`, `kind` (`discovery`, `inspect`, `request`, `cache`, `standing`), `region_id`, `location_id`, `speaker_id|null`, `public`, `requires_fact_id|null`, `text_prefix`, `cost_items`, and `reward`. Fields that do not apply are empty/null; no arbitrary predicates. Only Root Cache uses `requires_fact_id`; only request/standing uses `cost_items`. Inspection/discovery rewards are zero. The exact records are D3–D5; no extra authored scenes are required.

Opening a public regional description or NPC conversation is read-only. Reading a hint need not be persisted: Leads derives all public hints plus any already known facts. Inspect is explicit and durable; pure flavor is repeat-readable. NPC start/report/choice buttons are embedded in their existing project or request record, not separate static interaction definitions.

Keep four different facts in the implementation and UI:

1. Existing **location discovery** permits existing map/travel features; only existing travel/location authority writes it.
2. **Content inspection** is F for the exact landmark, after an Inspect action.
3. **Reward claim** is C for exact finite content; it is not inferred from F or a fresh token.
4. **Project objective progress** is P, reconciled from F or authoritative post-activation events.

A player can have discovered `westwild_n7` without finding its root marks; have found its root marks without claiming its cache; and have claimed the cache without completing any local project.

### J2. Frozen choice narratives

| Choice / values | Preview responsibility and immediate result | Later local response / equivalence |
|---|---|---|
| `ar_two_names.attribution`: `shared_credit`, `leave_unattributed` | Sera explains the evidence does not prove sole authorship. Shared credit records both workers as contributors; unattributed preserves the evidence without assigning credit. Confirmation: “This becomes your permanent local record. Both choices give the same reward and keep every route and activity open.” | Shared: “Both names remain beside the garden's work.” Unattributed: “The evidence is kept; the credit remains open.” The memorial/world object is unchanged for everyone. Both award 50 XP/20 gold. |
| `ar_unquiet_storehouse.seal_fate`: `archive_seal`, `leave_seal` | Archive: Sera keeps a recorded household seal; leave: mark its resting place and leave it among the family's remains. No usable inventory item is created, transferred or withheld. Same irreversible/equal-reward confirmation. | Archive: “The household seal is catalogued here.” Leave: “Its place in the storehouse is recorded and respected.” Both award 80 XP/30 gold; echo flavor differs, no combat or access effect. |
| `mv_ferry_crew.cargo`: `save_supplies`, `save_log` | At the channel, explain that the crew is safe, the damaged cargo permits one salvage choice, and neither option changes combat power or pay. Supplies: salvaged rations help the landing; log: route notes preserve the crew's observations. Neither grants a tradeable quest item. Same confirmation. | Oren's final and later response thanks the player for provisions OR the route record. Both award the same final 100 XP/40 gold/two potions. The unchosen cargo is narrated as lost; all standing work, discoveries, routes and hunts remain available. |

These are the only permanent narrative choices. No choice unlocks a later paid opportunity in V1, avoiding an unbounded downstream branch. All alternatives remain ordinary accessible content except the already-resolved choice itself. Sled method gets an accurate report line (“replacement materials” or “recovered brace”) but no moral outcome flag.

## K. Combat and settlement integration

### K1. Snapshot boundary

When creating a new canonical anchored encounter under RAV1, add `rav1_credit_version: 1` to its existing durable battle payload. This is an additive payload field, not a settlement schema bump and not a new table column. Existing encounters lacking it are legacy and receive no RAV1 event credit. Non-anchored legacy/synthetic encounters never qualify. Do not backfill this marker on old encounters.

Inside `lock_open_world_pve_roster_for_runtime_start`, after validating the forming anchor, final roster and immutable source data, but before committing the forming→active transition, insert exactly one B row per locked player, including an empty list if nothing qualifies. Evaluate each player's active current-step kill/encounter objectives against canonical encounter location, source mob/profile/special identities and mixed ID. Store matching source unit IDs. Insertion and spawn/roster lock must commit together. Repeated runtime-start calls never overwrite the original bindings. No B is created merely on encounter creation or joining; accepting while still outside combat would count only if legally possible before lock, while accepting after lock cannot count.

Source-unit IDs come from the existing immutable `pve_encounters.source_units_json` descriptors; source metadata cannot be reconstructed from mutable world listings or translated mob names. A mixed binding covers the exact reserved roster. For a marked encounter, a missing/corrupt/unknown-version B for a locked participant is an integrity failure: fail closed before combat runtime starts, or before T2 writes on recovery. Do not silently substitute current objectives. An unmarked legacy encounter is skipped by RAV1 capture even if its roster locks after upgrade; its prepared settlement drains with its original rewards and no RAV1 progress. Every battle-payload save/projection path must preserve the creation-time RAV1 marker unchanged. Dropping or changing the marker on an encounter with B rows is an integrity error, not a way to bypass verification.

### K2. T1/T2 contract

Keep existing settlement version 1, source validation, reward policy, RNG plan, eligibility, mastery, dry-streak, gear and reward receipts. T1 prepares its existing immutable plan. It does not grant story progress. B is separate immutable eligibility evidence captured before combat, so no new mutable catalogue lookup can change who qualified after the fight.

Inside T2's existing IMMEDIATE transaction, after recipient/source validation and before the encounter is marked applied, call the RAV1 observer with the plan and B. Intersect the stored recipient with the existing alive eligible recipient list. Defeated/fled players receive no RAV1 combat progress, even if they entered the fight or dealt damage. Nonparticipants receive none. Each eligible party member can advance their own accepted matching project; there is no shared party project instance.

For each bound objective still active in the same step/version, credit only stored source unit IDs actually included in this victorious settlement. Unit objective increments per matching unit; encounter objective increments once after the entire exact recipe wins. A completed or superseded ANY step is skipped, not reopened. Apply progress/step transition and mark B applied in the same T2 commit as all existing rewards. No finite project in this catalogue ends on a combat objective, so there is no automatic project bounty paid by T2.

T2 replay returns its existing committed settlement and performs no observer again. A crash before commit rolls back combat rewards, project progress and B applied state; recovery reapplies all once. A crash after commit returns the old result. Unknown settlement policy/version remains an error under the existing rules. Do not change old hunt eligibility rules as an incidental rewrite; ordinary UI already prevents accepting a hunt during battle, and repeated applied settlement cannot generate new hunt credit.

Hunt + Tool may both advance from the same wolf, including Greyfang when both accepted definitions qualify. The fight pays combat loot once, the hunt later pays its existing bounty once per accepted hunt completion, and Tool pays its own 40/18 once when reported. Optional tracks give nothing material. There is no duplicate “Greyfang project bounty.” Craft overlap follows the same independent-objective principle with its own authority.

Harvest remains the existing owner-only, eligible-victory, location/time-limited operation with its existing one-claim receipt. Group project credit never grants a second harvest entitlement or bypasses hunting requirements.

## L. Hunt repairs and named targets

### L1. Five board activations

Add `quest_board` to exactly four existing service lists. Do not relocate their definitions to another hub. Targets, rank and rewards remain unchanged; target aliases must canonicalize through `resolve_location_id` in both availability and combat matching.

| Existing contract key | Board / service change | Exact valid target scope / profile | Required rank / XP / gold / hunter points |
|---|---|---|---|
| `hunt_frostspine_white_wolves` | `frostspine_n5`: add board | 4 `white_wolf`; n2, n3, n5 of Frostspine; baseline profile semantics unchanged | none / 105 / 48 / 24 |
| `hunt_ashen_zombie_clusters` | `ashen_n3a2`: add board | 4 `zombie`; `ashen_n1`, `ashen_n2`, `ashen_n3c1`; baseline profile semantics | none / 108 / 50 / 24 |
| `hunt_mireveil_leech_swarms` | `mireveil_n5a1`: add board | 5 `leech`; `mireveil_n1`, n2, n5; giant leeches do not substitute | none / 102 / 47 / 24 |
| `hunt_sunscar_scorpions` | `hub_sunscar`: add board | 4 `scorpion`; `sunscar_n3`, n4, n5 | none / 110 / 52 / 24 |
| `hunt_sunscar_air_elementals` | Same Mirage board | 2 elite `air_elemental`; `sunscar_n10`, n11 only | tracker (40 hunter points) / 120 / 58 / 30 |

No new hunt definitions, added rank levels or reward changes. Existing normal spawn counts already provide the listed species; elite air anchors exist at n10/n11. Board access is tested through actual location and contract handlers, not only `list_contracts`. Existing aliases `village→hub_westwild`, `frontier_outpost→hub_frostspine`, `old_mines→old_mine_entrance`, `dark_forest→westwild_n7` remain valid; no new aliases are introduced. The five board IDs above are already canonical.

### L2. Named targets

| Identity | Exact backing / availability | Gameplay / reward / Journal |
|---|---|---|
| Greyfang; special key `greyfang` | Add `world_special_spawns` entry at `westwild_n3`: `mob_id=forest_wolf`, `key=greyfang`, `spawn_profile=normal`, `count=1`. Stable spawn ID `spawn-westwild_n3-forest_wolf-special-greyfang`. Existing template/stats/AI; no named stat multiplier. | Distinguishes a special target from normal wolves. Existing `hunt_greyfang` boards Aster/Elmor; one kill; 120 XP, 70 gold, `wolf_fang` ×2, 45 hunter points, unchanged. Special key and location must match; an ordinary wolf never substitutes. |
| Salt-Ridge Drifter; special key `salt_ridge_drifter` | Add entry at `sunscar_n8a2`: `mob_id=air_elemental`, `key=salt_ridge_drifter`, `spawn_profile=elite`, `count=1`. Stable ID `spawn-sunscar_n8a2-air_elemental-special-salt_ridge_drifter`. | Optional evasive magic-damage opponent using existing air-elemental and elite behavior. No new hunt or finite bounty. Normal elite combat reward policy only; optional source lead from pillar discovery. Does not fulfill Sunscar's elite-air hunt because n8a2 is outside its explicit n10/n11 scope. |

Both spawns exist independently of notices, inspections, projects or previous kills; initial canonical ensure creates an idle instance. They are additional slots, not renames/replacements of ordinary normal/elite spawns. They use existing reservation, battle, release, forming expiry and respawn rules. No private copy, daily scheduler, guaranteed rare drop, unique equipment, enrage timer or server-wide announcement.

Fighting Greyfang before seeing/accepting its contract gives ordinary combat loot and any already accepted qualifying Tool progress. No bounty is banked; later acceptance requires a new qualifying fight. Repeated hunts remain repeatable under baseline rules, requiring reacceptance and another kill. Hunt claim and T2 receipts prevent double bounty/loot. Named display names are resolved by stable special key in ru/en/es; legacy stored names remain readable but never authoritative for matching.

## M. Authored encounters and shared availability

| Mixed ID | Canonical location / exact ordered units and formations | Status / context / purpose |
|---|---|---|
| `westwild_n8_mixed` | `westwild_n8`: `bear/front`, `goblin_hunter/melee`, `goblin_shaman/support` | Existing Bear Hunting Party, unchanged. Nearby and region detail explain heavy attacks/support target selection; optional, no project gate. |
| `ashen_n3c1_mixed` | `ashen_n3c1`: `zombie/melee`, `zombie/melee`, `skeleton_mage/ranged` | Existing Ruins Patrol, unchanged. Garden scene mentions it; optional, existing zombie hunt can progress from its two qualifying units. |
| `rav1_frostspine_n6_pass` | `frostspine_n6`: `mountain_stone_golem/front`, `stone_beetle/melee` | New Stone at the Pass. Optional armored/heavy-intent pair. No project, hunt or cache requires it. |
| `rav1_mireveil_n6_crosscurrent` | `mireveil_n6`: `giant_leech/melee`, `water_snake/melee` | New Crosscurrent Predators. Draining and venom pair; Ferry step 2 requires this exact recipe. No stat changes or new mechanics. |

Every source is an **ordinary normal-profile, non-special** existing local spawn. Exact baseline normal pools for the used species are: West n8 bear1/hunter2/shaman2; Ashen c1 zombie3/mage1; Frost n6 mountain-golem1/beetle2; Mire n6 giant-leech1/water-snake1. A recipe reserves only the quantities in its composition, leaving other slots independent. Retain every other existing species, normal count and elite slot at these nodes. New mixed recipes add zero ordinary spawn slots. In particular Frost's normal mountain golem is used, not the unrelated legacy oversized `stone_golem` template.

Use `list_location_available_mixed_encounters` and `create_mixed_open_world_pve_encounter`; reserve every exact source atomically under their existing transaction. Either all sources become linked to one encounter or none do. Selection cannot consume a special or elite source as a substitute. Units remain unavailable to ordinary fights while reserved. Victory rewards use each immutable source unit and the existing eligible-recipient policy; no extra “mixed completion” chest or reward multiplier.

Preview lists enemy count, levels, relevant armor/evasion/venom/drain/heavy behavior and whether it is an optional challenge or Ferry objective. Do not advertise guaranteed success or invent a combined readiness score. Ferry's two-normal-unit fight must pass solo production acceptance with a legitimate earned build; the other mixed fights may be harder optional fights and benefit from a partner. No ordinary activity forces one of the three optional mixed encounters.

If units are busy, expose the recipe with “Shared enemies are busy; refresh after the fight or choose another activity.” If respawning, show actual remaining time when available. Offer Refresh, Nearby and Journal. Preserve progress, never consume an entry fee, never reserve a partial roster, never silently create a private encounter. Existing finite forming TTL and respawn are sufficient for this bounded design; **no new trigger/reservation framework is authorized**. Concurrency tests must prove recovery from abandoned forming encounters. No guaranteed wait time while another player is actively fighting, no queue or priority entitlement.

## N. Supply transactions and repeat attempts

Every RAV1 mutation enters `BEGIN IMMEDIATE`, or uses the existing authoritative caller's transaction; it never commits a nested production/combat caller early. For a UI operation:

1. Look up a committed receipt for `(player_id, ui:<token>)` before checking present location, expiry or current project revision. Verify operation namespace and immutable stored intent; return its saved result if committed. A receipt is not permission to execute another operation.
2. Load and consume the pending token through `consume_action` using its exact scoped kind. Parse its server-stored payload, never a client-provided amount. Verify catalogue version, expected project revision/step where applicable, canonical current location, travel revision, peaceful eligibility and finite entitlement.
3. Re-read inventory under the write lock; require each entire basket. Decrement through the existing inventory transaction API or equivalent same-connection guarded updates. Fail if any decrement cannot be performed. No equipped gear, gear instances, substitute items or reservations.
4. Apply progress/fact/choice and any terminal reward, assert item grants delivered exactly, insert C if finite, write E with the authoritative result and commit all together. Failures roll back token use, costs, progress, choice, claims and rewards.

Persist business rejections after authorization using the existing receipt convention: insufficient goods, completed entitlement, incompatible current step. Such a committed rejected token cannot succeed later; the player opens a fresh preview. Unauthorized/stale/malformed tokens never alter state or issue rewards. A completed entitlement's fresh preview has no new claim button. A stale old button gives the saved completion/choice or a localized refresh action.

Finite and standing previews name receiver, item quantities, owned amounts, total payout, XP policy, and whether one-time or per-batch. Finite premium and standing resale are clearly distinct buttons and IDs. Partial hand-ins are not supported. Showing or cancelling a preview has no cost. Two fresh tokens for a lifetime request serialize: one succeeds, the second reports resolved. Two valid independent standing attempts may each succeed only if two full baskets exist. A single-token double click is one attempt.

Existing sale/gift actions and RAV1 delivery must share SQLite's inventory/write-lock correctness: all possible orders preserve nonnegative stacks and exactly one spend of each unit. Gifts remain governed by existing transfer restrictions; no new ability to transfer bound or unavailable goods. A giver's production never advances the recipient's Fresh Batch process counter. Restart recovery renders the immutable result in the viewer's current language.

## O. Exact rewards and economy limits

### O1. Finite reward ledger

| Lifetime claim ID | XP | Gold | Fixed items |
|---|---:|---:|---|
| `ww_tool_roll` | 40 | 18 | none |
| `fs_jammed_sled` | 70 | 30 | enhance_shard ×1 |
| `ar_two_names` | 50 | 20 | none |
| `ar_unquiet_storehouse` | 80 | 30 | none |
| `mv_ferry_crew` | 100 | 40 | health_potion_small ×2 |
| `ss_camp_bearings` | 30 | 12 | field_ration ×1 |
| `mv_medic_practice` | 30 | 15 | none |
| `ww_woodcutter_provisions` | 20 | 18 | none |
| `mv_medic_table` | 20 | 18 | none |
| `ww_root_cache` | 0 | 0 | health_potion_small ×1; enhance_shard ×1 |
| **Total** | **440** | **201** | **2 shards, 3 small HP potions, 1 ration** |

Ten lifetime payout entitlements; nine include XP/gold and one is items only. Discovery inspections have no reward entitlements. Camp's cache is already its project's single claim, not an eleventh payout. Claim identity never includes version, current step or request token in place of content ID: upgrades cannot reset a lifetime reward.

Use the existing progression semantics from `pve_reward_settlement._apply_progression`, extracted to a small shared helper if needed: threshold loop, +3 stat points and attribute budget per gained level, build revision when level changes, existing NULL handling. Do not update XP/level without build-budget compatibility. Grant fixed stackables through the existing item grant authority with same-connection delivery verification and provenance `{source:'rav1', catalog_version:1, content_id, player_id, request_id}`. No direct gear grants or reward selection UI are in RAV1. All gear remains PR230 field/vendor/crafting equipment with existing tier/rarity/secondary/provenance/comparison/duplicate behavior. No exclusive skill, recipe, legendary, set or unique reward.

### O2. Standing-job arithmetic from PEV1

All input resources below have `buy_price=0` and are absent as purchasable commodities; zero means not for sale, never free stock. Field ration and marsh stew likewise have no vendor purchase listing. Existing shops sell small HP potions for 30 gold at Aster/Elmor; none of the three standing jobs accepts them. No RAV1 job adds shop stock.

| Job | Raw-input NPC sale value per batch | Crafted-output resale | Vendor/input/conversion path | Fixed payout and invariant |
|---|---:|---:|---|---|
| Ration order: 2 rations | 2 × (boar_meat 5 + herb_common 3) = **16** | 2 × 5 = **10** | `trail_ration`, cooking 1, starter, one output per meat+herb. No purchasable ration or inputs; no alternative active recipe for this output. Recipe learning 0. | **10** ≤ output resale 10 and raw 16. Craft→hand-in has no premium over simply selling crafted food; material conversion loses 6 gold of raw resale opportunity. |
| Forge basket: 2 iron + 2 coal | 2 × 6 + 2 × 4 = **20** | Not crafted; same materials resell for **20** | Mining 1 sources at Old Mine; no vendor path, no smelting/reverse recipe producing these resources. No learning cost. | **20** = raw resale. No conversion creates materials; it is local sale convenience, not money creation. |
| Landing meals: 2 marsh stews | 2 × (2 marsh_fish at 4 + marsh_herb 4 + salt_crystal 4) = **32** | 2 × 6 = **12** | `pe_cooking_marsh_06`, cooking 6, one output per listed basket. Learn once for **25**, a sunk cost excluded from marginal input arithmetic. No vendor or alternate active recipe. Personal sources require fishing/herbalism/mining 6; transferred goods do not. | **12** ≤ output resale 12 and raw 32. Conversion loses 20 gold of raw resale opportunity; no commission premium. |

Existing gathering/crafting may legitimately train professions while producing these goods. The job adds **zero character XP, zero mastery XP, zero profession XP, zero hunter points**. Existing crafting XP is awarded once by craft authority and remains subject to its existing ceilings. Receipt replay never retriggers it. A player cannot submit gifted goods for profession progress.

Alternate legal acquisition includes combat rewards where existing tables provide goods, gifts and finite RAV1 rewards. Gift/loot acquisition cost to the recipient can be zero, but it transfers/creates only the existing finite physical units; delivery consumes them and pays no more than their ordinary NPC resale. A gift chain cannot multiply goods. Camp provides one ration once, insufficient for one standing batch by itself. There is no standing output item to cycle back into a job. Existing enhancement exchange is unrelated and cannot produce these inputs. Tests enumerate every active recipe/output and actual vendor stock, not merely the `buy_price` field.

Frozen economy invariant for each repeat delivery: payout is at most both its directly submitted goods' NPC sale value and the recursively expanded raw-input sale value, and no more than the cheapest legitimate repeatable NPC buy/conversion cost if one exists. At this baseline there is no purchasable path for any accepted batch. A future stock/recipe change violating this invariant must fail its contract test; do not silently raise payout or dynamically invent new prices. Learning costs do not justify a perpetual premium.

Finite requests deliberately differ: Provisions pays 18 for goods worth 10 resale/16 raw; Medic's Table pays 18 for herbs worth 12; each premium is lifetime bounded. Fresh Batch pays 15 for two potions worth 10 resale, after two real crafts using six herbs worth 18. Buying its final potions would cost 60 but still cannot replace the personal production evidence. Sled's material route spends goods worth 12; combat route spends no goods and still pays the same finite reward. These differences are transparent choice-of-effort costs, not repeat arbitrage.

### O3. Aggregate budget and valid orders

| Play style / claims | Added finite XP / gold / items | Bound and implication |
|---|---|---|
| Westwild local: Tool + Provisions + root cache | 60 / 36 / potion1 + shard1 | Ration input resale 10, raw16. Existing hunts/combat remain separate repeat progression. No region key follows. |
| Frostspine local: Sled | 70 / 30 / shard1 | Supply route costs raw12, combat alternative exists; forge basket is only resale thereafter. |
| Ashen local: Names + Storehouse, either order | 130 / 50 / none | Same total and access in both orders and all four combinations of local choices. |
| Mireveil local: Ferry + Medic's Table + Fresh Batch | 150 / 73 / potion2 | No ordinary content demands advanced production; practice is optional. Costs four herbs and two hand-in potions; actual new craft additionally consumes its own inputs. |
| Sunscar local: Camp | 30 / 12 / ration1 | The named target and hunts remain ordinary repeated combat, with no escalating first-clear bonus. |
| Fast noncombat tour: Names + Camp + both direct requests | 120 / 68 / ration1 | Requires travel/inspection and consumes rations2/herbs4. No XP for merely touching five hubs or ten landmarks. Adding optional Fresh Batch raises this to 150/83, only after actual crafts. |
| Every finite entitlement, any legal order | 440 / 201 / shards2, potions3, ration1 | Fixed item resale total = 30+15+5 = **50** gold; gross transferable value ≤251 gold before required inputs. No repeat of any first completion. |

The complete finite XP budget 440 is below the existing level-3→4 threshold `int(100*3**1.8)=722`. For a hypothetical level-1 character with no other XP, 440 crosses the first 100 and leaves level 2 with 340 XP, eight below its next threshold of 348; actual onboarding/combat adds its own XP and is not hidden in these totals. Reward addition commutes under the existing threshold system: route order changes timing, not total earned attribute budget or reward tier. All choices give identical rewards; all easy inspections pay zero. 201 gold is finite purchasing power, not an infinite income source. Production acceptance compares legal regional orders and records gear/build changes to detect an unintended shortcut; it does not assert all activities have equal time efficiency.

## P. Journal, catalogue and discovery UX

### P1. Home and six views

`/journal` retains Chapter I's existing progress presentation until it is complete, with a visible Opportunities link available throughout. After Chapter I, its default home is the RAV1 overview: current location, up to three pinned pursuits, active hunt summary if any, and six equal navigation choices. There is no automatic pin, auto-accepted project, featured next region, or “continue the main story” text. Completed onboarding remains accessible as history.

| View | Exact contents and order | Empty / blocked behavior |
|---|---|---|
| Nearby | Actionable/local content at the exact current location: active project actions, unclaimed public requests, local inspection buttons, available/busy authored encounters and a Local Work link. Hide undiscovered secrets except when physically at their discoverable node. Sort by category in this order, then stable content ID. | “No local action here. Browse the map, region notes or your pursuits.” Read-only descriptions remain available during combat; mutation buttons say Finish the current encounter. |
| Leads | Five public regional summaries and public content leads; known discoveries can add context links. Do not persist a separate rumor-heard flag. Sort map order, then content ID. | Show undiscovered destination as “Reach through the map”; no long-travel button until normal travel permits it. No completion checkmarks across regions. |
| Pursuits | All active projects in accepted-time/ID order, existing active hunt in a separately labelled block, existing current gear goal and profession links. Pinned status is an annotation, not filtering. | No project: “Choose local work, explore a place, or pursue equipment and professions.” Existing hunt slot conflict identifies the active contract and its ordinary management route. |
| Regions | Five peer summary cards, each opening the manifest's public activities, known local findings, services, source/recipe links and current statuses. Stubs appear only as source links from relevant content/map, not sixth/seventh regional campaigns. | List risks separately from hard requirements; no ordinal difficulty ladder, percentage or “region cleared.” |
| Resolved | Completed projects with chosen outcome and reward receipt, two claimed requests, claimed root cache, and inspected discoveries. Tabs/filters: Records (projects/requests/cache) and Findings (ten discoveries). Newest timestamp then stable ID. Auxiliary facts appear only inside their project's record. | “Your local records will appear here.” Reopening a record cannot reaccept, reset or claim again. |
| Local Work | Exactly three standing jobs, grouped by map order, with local/remote label, required goods/owned quantities and source/recipe links. Own current goods can be viewed remotely; submit only at receiver. Existing hunt-board navigation is a separate link. | Missing goods shows exact shortage; no personal profession gate on delivery. Optional recipe production shows its own actual knowledge/profession requirements. |

Home, detail pages, choice previews and region details are navigation surfaces, not additional top-level catalogue views. There are **six new top-level views**. Existing map, build, inventory, equipment comparison and professions screens remain their authorities; RAV1 adds links, not clones. Gear goal uses the existing post-Chapter-I goal and equipment flow. If already satisfied or no specific goal exists, show Equipment and Build rather than inventing a new permanent goal.

Pins: maximum three total across active projects, active hunt and current gear goal. Project owner ID is its stable ID, hunt owner ID is the current contract key, gear owner ID is literal `current`. Add goes to the lowest free slot; if full, show “Unpin a pursuit first,” no automatic eviction. Unpin leaves progress intact. No separate reorder operation in V1; unpin/re-pin is sufficient. On completion/claim, remove that finished pursuit's pin in its owning transaction where possible; if an old hunt/gear mutation does not touch pins, filter/prune invalid pins on the next explicit Journal/pin action without writing progress. A new hunt never inherits an old hunt's pin. Restart preserves active valid pins and all unpinned progress.

### P2. Availability and travel

Public summaries and boards describe work before acceptance. Only local interaction can accept or submit a project; remote Journal buttons lead to source/map, not remote mutation. Camp is publicly hinted at as exploration, while its cache contents appear only after bearings. Root Cache is secret until its exact fact. All ten discovery texts require actual Inspect to enter Findings; reading a regional summary cannot mark one found.

Active project details show exact current objectives, counted evidence, where to act, known sources and why an action is blocked. Completed project details show its saved outcome. Standing jobs show per-batch terms and never “complete.” Conventional hunts retain one-active semantics and clearly say Hunting Contract; projects clearly say Local Project. An active Chapter I contract occupies that existing slot, not a project slot.

No location ID is inserted into discovery from a Journal read, pin, rumor or acceptance. Navigation calls existing map/travel preflight and explains route requirements. Canonical aliases are resolved before display/matching. Existing neighbor travel, discovered long-travel, path timing and revision checks remain unchanged. A missing destination requires ordinary path exploration. No map link is an implicit teleport or bypass of the 15-second neighbor / existing longer-route timing rules.

Risk labels are information, not hard gates: actual enemy level/profile/behaviors; recipe/profession requirements for optional production; explicit multi-enemy count. Never conflate character level with profession or gear tier. Missing inventory, wrong location, unknown recipe, occupied hunt slot, active battle, busy spawn and stale preview each have different messages and recovery links. No generic “not ready for this region” denial.

### P3. Pagination and size

List pages contain six content rows, stable order, clamped zero-based page index, previous/next only when valid, and Back/Home. A full result remains accessible after page changes or completion removes a row. Text body ≤3,000 UTF-16 code units including escaped rendered text; split long record detail into Summary/Objectives/Record subpages rather than truncating critical costs or choices. Maximum 12 buttons and 10 rows per message, ≤2 buttons per row; use one wide row for long titles/choice labels. Localized button labels target ≤32 visible characters; semantic detail belongs in body text. Tests cover worst-case names/counts in all three locales.

## Q. Regional recovery and other services

Add only `inn` to `hub_ashen_ruins`, `hub_mireveil`, `hub_sunscar`. Reuse existing inn menu, token kind and `rest:12` payload, `_can_open_inn`, `rest_at_inn`, `INN_REST_COST_GOLD` and receipt/inventory-independent gold transaction. Price remains 12 gold per existing recovery action. Existing full/partial recovery rules and busy/location checks remain exact baseline behavior. No free heal on arrival, project start, completion, inspection or choice. No story prerequisite, discount, upgraded tier or service token.

Reuse existing localized recovery strings in ru/en/es and add only location/context labels if absent. Confirm previews and actual debits use the same price authority. A retry returns the same rest result and does not charge twice. Adding these services does not add a shop to these hubs. Four boards in L plus these three inns are exactly **seven location/service additions**: Frost n5 board, Old Temple board, Mire boardwalk board, Mirage board, Ember inn, Velm inn, Mirage inn. Existing guilds remain. No other service additions are authorized.

## R. Localization contract

### R1. Files and exact families

Use `rpg/locales/rav1_ru.py`, `rav1_en.py`, `rav1_es.py` with the existing i18n loading convention. Eighteen RAV1 key families, each present in every locale:

`rav1.nav`, `rav1.status`, `rav1.actions`, `rav1.errors`, `rav1.rewards`, `rav1.readiness`, `rav1.people`, `rav1.landmarks`, `rav1.regions`, `rav1.content`, `rav1.facts`, `rav1.choices`, `rav1.work`, `rav1.encounters`, `rav1.services`, `rav1.replay`, `rav1.help`, `rav1.progress`.

Existing hunt, item, location, profession, recipe and inn keys remain authoritative and are reused. Do not duplicate their names as divergent RAV1 translations. Special/mixed names may be stored using the existing label-dictionary format, but their ru/en/es text must agree with `rav1.encounters`. The new files contain full strings, not runtime English literals or Russian fallback aliases.

Required content key suffixes: every content record has `title`, `summary`; each project has `start`, `step.<step_id>`, `objective.<objective_id>`, `complete`; each discovery/inspection has `finding`; each request/cache has `preview`, `result`; each standing job has `terms`, `result`. NPC responses additionally provide the three choice aftermaths and Sled's two method responses. Shared templates provide counts, costs, reward lists, empty states, replay, owner mismatch, stale action, malformed callback, wrong location, in battle, insufficient goods/gold, unknown recipe, profession requirement, hunt slot/rank, busy/respawning target, already resolved, incompatible version and temporary atomic failure. No hidden raw `KeyError`/ID error text reaches players.

### R2. Frozen titles and names

| Identity | English | Русский | Español |
|---|---|---|---|
| Tool | The Lost Tool Roll | Потерянная сумка с инструментами | La bolsa de herramientas perdida |
| Sled | The Jammed Sled | Застрявшие сани | El trineo atascado |
| Names | Two Names on One Stone | Два имени на одном камне | Dos nombres en una piedra |
| Storehouse | The Unquiet Storehouse | Неспокойный склад | El almacén inquieto |
| Ferry | The Missing Ferry Crew | Пропавшая паромная команда | La tripulación desaparecida |
| Camp | Camp Bearings | Ориентиры лагеря | Las referencias del campamento |
| Practice | Lida's Fresh Batch | Свежая партия для Лиды | Un lote nuevo para Lida |
| Provisions | Provisions for the Woodcutters | Припасы для лесорубов | Provisiones para los leñadores |
| Medic | The Medic's Table | Стол лекаря | La mesa de la sanadora |
| Root cache | The Dry Root Cache | Сухой тайник под корнями | El escondite seco entre raíces |
| Ration order | Woodcutters' Standing Order | Постоянный заказ лесорубов | Encargo habitual de los leñadores |
| Forge basket | Forge Supply Basket | Припасы для кузницы | Suministros para la forja |
| Stew order | Meals for the Landing | Обеды для пристани | Comidas para el embarcadero |
| New Frost mixed | Stone at the Pass | Камень на перевале | Piedra en el paso |
| New Mire mixed | Crosscurrent Predators | Хищники на встречном течении | Depredadores de la contracorriente |
| Sun named | Salt-Ridge Drifter | Скиталец соляной гряды | Errante de la cresta salina |
| Mara / Iven / Sera / Oren / Lida | Mara / Iven / Sera / Oren / Lida | Мара / Ивен / Сера / Орен / Лида | Mara / Iven / Sera / Oren / Lida |

Greyfang uses the existing hunt's localized name; reconcile the new spawn label to that established name. NPC roles, ten landmark findings, both auxiliary findings, every scene beat and each outcome are semantically frozen in D and J. Translate those meanings in full; implementation is allowed wording/grammar polish, not new lore, objectives, threats, rewards or consequences. Thus translation work is not deferred content design. Use existing canonical location translations.

Choice buttons must distinguish shared credit / leave unattributed; archive seal / leave seal; save supplies / save log. All languages state permanence and equal material outcomes before confirmation. Required confirmation meaning: “This choice is permanent for this character. Rewards are the same. Routes and other activities remain open.” No translation may imply a lost power reward, global world change or hidden best answer.

Validate exact key-set and placeholder parity, lookup without fallback, all catalogue references, nonempty strings, formatting/escaping, no internal IDs rendered, and every navigation/error state. Real-handler ru/en/es journeys must inspect rendered text and button actions. Raw language-neutral receipt data is rendered through the current locale after restart or language change; never persist translated prose as state.

## S. Telegram callbacks and stale actions

Reserve prefix `rv:` and one handler registration restricted to it. Frozen callback forms:

* `rv:v:<view>:<page>:<region>` — read navigation. View codes `h,n,l,p,r,s,w`; region codes `all,ww,fs,ar,ss,mv`; page is decimal 0–999. Invalid combinations render home/error without mutation.
* `rv:d:<kind>:<id>` — read detail. Kind `p,d,i,w,e,r`; ID must be one of the static allowlisted records, ≤40 ASCII characters. Detail subpage uses `rv:t:<kind>:<id>:<tab>` with `tab=s,o,r`.
* `rv:a:<token>` — every RAV1 mutation, token exactly 16 lowercase hexadecimal characters. Maximum mutation callback length **21 bytes**. All forms must be measured as UTF-8 and be ≤64 bytes. No player ID, reward, cost, choice value or JSON in callback payload.

Use existing `player_ui_actions`. Scoped kind is `rav1:<content_id>:<operation>` for local mutations, `rav1:journal:pin` for pin menus; operation is `start`, `inspect`, `deliver`, `respond`, `choose`, `claim` or `pin`. Server payload is canonical JSON with `catalog_version`, `content_id`, `operation`, expected project `revision`/`step_id` when applicable, and the selected static choice/pin identity if applicable. It contains an intent, not authoritative prices. Authoritative definition supplies all costs/rewards. Existing stored location/travel revision/expiry apply. A choice confirmation screen issues its own token; a read callback selecting a preview cannot commit the choice.

Refreshing one content operation may invalidate its pending siblings, including the alternate choice; it must not invalidate another project's or another system's tokens. Existing `issue_actions` deletes by kind, so distinct scoped kinds are required. No in-memory `context.user_data` state is sufficient for authorization or pending rewards. Committed E receipts recover even when refresh removed the preview token; verify player/request/operation using persisted receipt, not attacker-provided values. A malformed/unknown token gets a short localized error; no uncaught exception or callback-query spinner remains.

Stale handling is non-destructive: committed token→stored result; changed project revision/step→current detail; wrong travel revision/location→current location and source link; expired unused token→new preview; already resolved→record. Do not silently accept a new choice or spend a different basket because the original intent became stale. Callback display timestamps and page index are not gameplay authority.

## T. Compatibility and preservation

Preserve all existing Chapter I history, active hunts/objectives/history, hunter rank/points, gear IDs/rolls/durability/provenance, inventory, attribute budget/build revision, mastery, professions/XP, recipe knowledge, economy receipts, travel/discovery/revision, PvP engagements and all prepared/applied PvE plans/results. No migration recomputes historical completions or grants regional credit from prior kills. Existing location discovery only supports map navigation; current inventory can satisfy the exact frozen delivery predicate. Existing RAV1 facts can support their declared retroactive inspection objectives; pre-RAV1 location presence cannot manufacture them.

No whole-system schema/version reset, rules-version bump, combat rebalance, recipe rebalance, altered XP curve, travel timing change or replacement of canonical location/mob IDs. Reuse existing migration and startup orchestration without suppressing failures. A RAV1 code deployment with an incompatible schema must stop initialization clearly and preserve the database, not serve partially available mutation handlers.

Pre-RAV1 active/forming/prepared encounters lacking the marker settle normally and grant zero RAV1 combat progress even if a matching project is accepted later. New marked encounters require the frozen bindings. Existing applied settlements are immutable and remain applied. Unknown historical static items remain preserved/readable under existing fallback, but cannot become new delivery inputs merely because their names resemble an accepted item.

## U. One Draft PR: internal workstreams and commit boundaries

All paths in this section are **future repository-relative design targets**, not files created or changed by Stage 2. Keep one coherent Draft PR. Commits may follow the boundaries below; none is a separately merged product increment. Ordinary function/class placement may be adjusted to repository style, but the authority boundaries, fields and product behavior are frozen.

| Workstream / recommended commit | Dependencies | Production files and work | Focused verification |
|---|---|---|---|
| 1. Additive storage and schema checks | Baseline reread | New `rpg/game/regional_schema.py`; integrate in existing `database.py` / `game/alpha_schema.py` startup after prerequisite schema. Five tables, marker, exact validators. No player backfill. | `test_regional_adventures_schema.py`: clean install, repeat startup, wrong shapes/versions, empty partial install, rollback, legacy preservation. |
| 2. Catalogue and finite transaction core | 1 | New `game/regional_catalog.py` with all 34 new top-level records and bounded schemas; new `game/regional_adventures.py` for explicit state transitions, facts, choices, claims, deliveries and pins. Reuse `action_receipts.py`, `economy_actions.py`, inventory grant/debit; extract shared progression helper to `game/progression_rewards.py` only if needed, preserving callers. | `test_regional_adventures_contract.py`, `test_regional_adventures_transactions.py`: all IDs/counts, graph limits, every terminal reward, revision/choice/ANY semantics, receipt and grant-failure atomicity. |
| 3. Narrow authoritative observers | 1–2 | New `game/regional_objectives.py`; same-transaction hook in `crafting_runtime.py`; capture in `pve_live.py`; T2 observer in `pve_reward_settlement.py`. Preserve current plan schema and source identities. | `test_regional_adventures_combat.py`, transaction nodes plus existing settlement/crafting/build-budget tests touching changed helpers. |
| 4. World access and encounters | 2–3 | `locations.py` seven services/two special entries; `enemy_profiles.py` two recipes; named labels in existing encounter rendering; `quest_board.py` only canonical reachability fixes if required, never new hunt system. | `test_regional_adventures_world.py`: live board handlers, alias/rank targets, canonical spawn instances, exact mixed reservations, zero unintended spawns, service price/replay. |
| 5. Journal and local interaction surfaces | 2–4 | New `game/regional_opportunities.py` read model; new `handlers/regional.py`; integrate `handlers/chapter.py`, `handlers/location.py`, `bot.py`. Link existing inventory/build/profession/map flows; do not fork them. | `test_regional_adventures_ui.py`: six views, start/detail/return, pins, pagination, empty/blocked/busy states, discovery/travel separation, malformed/stale tokens. |
| 6. Full localization and economy assertions | 2–5; keep translations current while implementing UI | Three new `locales/rav1_*.py`; existing locale loader/i18n registration; named/mixed labels. No item/recipe/pricing changes. | `test_regional_adventures_localization.py`, `test_regional_adventures_economy.py`: no fallback, placeholder/length parity, all three job inequalities, active vendor/recipe paths, finite budget. |
| 7. Earned production journeys and evidence | 1–6 | New `tests/test_regional_adventures_v1_journeys.py`, adapting actual baseline journey harness rather than new mock gameplay. Supporting fixtures remain tests only. Add evidence writer using captured runtime outputs. | Twenty journey definitions in W with listed parameters, real handlers, actual earned state, restart/race boundaries. |
| 8. Final reconciliation and review candidate | Green focused work, then final broad suite | Documentation/evidence in Y; review diff for scope, declarations and unchanged old assertions. | One broad suite, classify failures, targeted repair/retest; independent review of exact candidate SHA. |

New runtime modules named above are suggested file boundaries, not an excuse to construct frameworks. Business mutations are synchronous same-connection functions; Telegram handlers format and route. Catalogue validation can be colocated with its definitions. Do not spread a project's mechanics across ad hoc handler conditionals or let Journal directly write inventory.

## V. Test policy, scope and evidence discipline

During implementation, run only focused tests for the workstream and directly affected existing regressions. Use Python 3.12 and the repository's normal test dependencies/environment. Standard focused form from `rpg/` is `python -m pytest tests/test_regional_adventures_<area>.py -q`; collect actual node names once created and record the exact commands/results. Suggested filenames in U are not a claim those tests currently exist.

Require **one broad final `python -m pytest -q` run** near candidate readiness, including existing tests. Record candidate SHA, environment, duration, passed/failed/skipped counts, command and log reference. Do not run the broad suite after every commit. If it fails, classify each failure as RAV1 regression, pre-existing reproducible failure, nondeterminism, environment/dependency issue, or test defect. Supply evidence, repair within scope and rerun exact affected nodes. Repeat the broad run only if repair changes shared infrastructure sufficiently to invalidate the earlier broad result (database startup/transaction behavior, common progression, combat settlement, inventory, i18n/handler routing). Document that reason. A skipped required journey or unresolved correctness regression is not green.

Required focused categories:

1. Static contract: 34 records, 7 projects/18 steps/22 objectives, exact references/rewards, single ANY step, three choices, no cross-region story dependencies, all allowed types actually used, no extra types.
2. Migration: exact schema shapes/constraints/FKs/marker-last, compatible empty partial recovery, nonempty unmarked rejection, unknown-version fail-closed, repeated startup and injected failures without loss of old rows.
3. Atomicity/replay: each mutation's failures before/after consumption, reward grant, claim insert and receipt write; response loss after commit; rejected receipts; new tokens cannot reset lifetime rights.
4. Concurrency: two SQLite connections, same-token duplicate, different-token same finite claim, two standing batches, sale/gift/delivery interleavings, two choices, project progress versus stale preview, roster lock versus project acceptance.
5. Objective semantics: every kind, preinspection credit, no pre-craft/pre-kill credit, no event reuse into next step, cap quantities, exact ANY winner, two projects independent, hunt/project overlap.
6. Combat: pre-lock snapshot, normal/special/profile/location predicates, complete mixed identity, locked recipients, victory-only/defeat/flee, missing binding fail-closed, T1/T2 restart, legacy unmarked encounter behavior, owner-only harvest.
7. World/encounters: actual board menu access, rank and aliases, special slots separate from normal slots, full mixed reservations/no partial mutation, busy/respawn/expiry paths, no private instance fallback, all ordinary source counts unchanged.
8. Economy: full finite ledger, recipe/vendor acquisition enumeration, each standing bound, zero repeat character/profession XP, goods consumed once, exact grants, common progression helper parity and attribute budgets.
9. UI/locales: all navigation/empty/error states, up to three display-only pins, source and lawful travel links, post-onboarding default, no global percentage, language key/placeholder coverage, UTF-8 callback and body/button budgets.
10. Production journeys: all W definitions using runtime handlers/authorities and earned provenance; data fixtures used for schema/corruption unit tests cannot be cited as production play evidence.

Keep all existing regression assertions unless a narrowly documented product requirement necessarily changes a specific expected service/listing; update only that expectation and add its explicit new contract test. Never weaken reward, inventory, transaction, combat or progression assertions to obtain green. No direct SQL grants in production journeys; assertions may query DB state. Fault injection and thread scheduling instrumentation are test controls, not gameplay substitutes.

## W. Required automated production acceptance journeys

There are exactly **20 journey definitions**, J01–J20. Parameterized runs below are mandatory cases within those definitions, not additional catalogue/journey counts. Share genuinely earned prehistories to keep runtime bounded, with snapshots/checkpoints cloned only from recorded production histories. Record provenance and the source checkpoint hash for every reused history. Never label an injected unit-test fixture a fresh/advanced production account.

Use actual registration, travel, location, Journal, accept/inspect/choice/hand-in/craft/combat/claim handlers with mocked Telegram transport only. Domain transactions may be called by the same handler path or by the established production harness where the bot's normal handler delegates; receipt/token/eligibility cannot be bypassed. Record initial/final state, action sequence, receipts/encounter IDs, outcomes and assertions. For every accelerated clock/RNG segment, record the exact override and why it preserves rules.

| ID | Required scenario and cases | Required observable acceptance |
|---|---|---|
| J01 — Fresh onboarding | Register a new character, earn complete Aster–Elmor Chapter I using baseline gameplay, open `/journal`. | Existing onboarding rewards/history correct; no new active Chapter II or RAV1 project automatically created. All five summaries visible; player can choose Map, profession or gear without accepting a story. |
| J02 — Five-way choice | From that earned post-onboarding state, browse all five summaries and actual local entry surfaces using legal travel. | Each offers the distinct activity mix in E; public versus secret information correct; wrong-location actions blocked; Journal never grants destination discovery. Five hunt definitions can actually be reached on the four activated boards, with rank restrictions shown. |
| J03 — Different first regions and solo paths | Five checkpoint branches whose first accepted RAV1 project is respectively Tool, Sled, Names, Ferry, Camp. Complete each without completing other regions. Additional earned build cases must complete Storehouse and Ferry solo with one physical build and one magic build; use existing attribute/skill/equipment choices, no HP/damage injection. | All seven projects have at least one solo completion across J03/J08/J09/J06; no cross-region story requirement. Record preparation battles, gear, mastery, consumables and actual tactical actions. No mocked combat victory or mandatory second player. |
| J04 — Stay local | Begin from an earned arrival at Westwild and, in a separate case, Mireveil. Pursue local finite work, a local hunt, an optional activity and repeat work for a complete session trace. | Meaningful alternative actions without outside story tokens. Goods may already have been earned/transferred; no task silently requires new high-level production. After finite work, repeat combat/profession/work links remain. |
| J05 — Concurrent pursuits | Accept both Ashen projects and the reachable zombie hunt, pin/unpin/attempt fourth pin, inspect/advance each, restart runtime/DB connection. | Hunt slot independent of seven-project model; both projects progress unpinned; max three pins enforced without cancelling anything; state and chosen UI identities survive. |
| J06 — Reverse independent order | Earn two characters/checkpoints: Names then Storehouse, and Storehouse then Names. | Identical final rewards/access; each remains separately available; no implicit prerequisite from dialogue or project sorting. Record both completion orders. |
| J07 — Explore before lead | Inspect both Names evidence nodes before accepting; inspect Sun pillars then camp before accepting; inspect sled damage before starting Sled. | Only exact F permits later fact reconciliation; pre-existing location discovery alone does not. No immediate rewards for inspection. Camp still requires its local final cache action once. |
| J08 — Low-profession route | Complete Sled with combat alternative at unchanged baseline low professions; complete Names/Camp without gathering; deliver acquired goods to Medic's Table. | No grinding to profession 6/12/18 for ordinary content. Sled cannot charge goods after combat route wins. Optional production details do not become hand-in gates. |
| J09 — Personal practice | Craft a potion before Fresh Batch, accept, attempt hand-in, then personally craft twice via `field_tonic`; replay a craft receipt and receive a gifted potion; complete final delivery. | Earlier craft/gifted inventory gives no process progress; two new successful executions count exactly two; recipe knowledge and normal XP honored; final goods may be any legal potions once evidence is earned. |
| J10 — Ordinary delivery | Earn required goods through prior craft, gathering and another earned character's permitted gift; use finite Provisions/Medic requests and all three standing jobs, including marsh stew produced through actual learned recipe. | Each legal source accepted, exact consumption/reward, no personal profession gate on recipient, no double-pay/replay, no standing XP. Advanced cook's ingredients/learning/gold have earned trace. |
| J11 — Combat overlap | Accept Tool plus ordinary wolf hunt; in another case accept Tool plus Greyfang hunt. Fight through real canonical spawns and authoritative settlement, then replay/restart settlement and report/claim. | Both independent objectives advance once if matching. Combat loot once; Tool lifetime reward once; hunt reward only its existing claim. Acceptance after roster lock cannot gain credit from that encounter. |
| J12 — Optional group | Two earned players join canonical mixed encounter; cases both alive, one defeated, one fled. At least one case uses Ferry's exact two-unit recipe with projects accepted independently. | Alive eligible locked members receive their own credits/loot; defeated/fled do not. Only encounter owner can perform existing harvest. No player gains companion facts/choices or implicit acceptance. |
| J13 — Named canonical targets | Kill Greyfang before notice/acceptance; later accept and kill respawned Greyfang, claim, replay; also fight Salt-Ridge Drifter from the actual pillar special spawn. | Greyfang normal/special distinction and no retro bounty; independent ordinary wolves remain. Drifter is elite air with expected source identity and ordinary reward policy; no invented bounty or n10/n11 hunt credit. |
| J14 — Busy shared sources | Another earned participant holds one required source of Ferry mixed; test forming expiry and a completed battle/respawn. Also contend for Greyfang. | Understandable busy/respawn state, preserved project, useful alternate links; no partial reservation, duplicate special, private fight, stuck progress or lost cost. Once sources release, normal retry works. |
| J15 — Permanent local choices | Two earned characters choose opposite values for each of the three choice IDs; try stale alternate confirmation, fresh menu and restart. | Six outcome records across the two characters; correct local aftermaths, equal numeric rewards/access, immutable choices, unchanged other players/world. Sled methods separately preserve only method description. |
| J16 — Returning player migration | Build a baseline pre-RAV1 account through earned Chapter I/hunts/gear/professions/recipe knowledge. Leave an existing hunt and a real prepared PvE settlement; snapshot, apply RAV1 migration, resume. | Every preserved state in T matches except legitimately applied pending settlement changes. No fake project/history/kill credit. Old prepared plan pays once. New opportunities appear normally; repeated migration changes nothing. |
| J17 — Atomic boundaries | Parameterize delivery, choice, root cache, combat T2, standing attempt: inject failure before commit and response loss after commit; double-click; stale token; separate-connection sale/gift/hand-in races for delivery cases. Start each from a real earned checkpoint. | Either complete committed effect once or no effect. Exact receipt recovery; no negative stacks, double rewards, rerolled choices, partial progression or lost/duplicated grant. Failed transaction does not consume entitlement. |
| J18 — Arbitrary reward order | Same earned starting checkpoint: collect the noncombat-tour ledger in order Names→Camp→Provisions→Medic and reverse order; separately complete all finite claims in two valid regional orders using earlier earned traces. | Exact O totals, identical final XP/attribute budget for equal overall earned XP, fixed rewards at different current levels, no tier escalation or new activity unlocked by region completion. Isolate extra incidental combat/gather costs in evidence instead of pretending routes have identical costs. |
| J19 — ru/en/es real handlers | In every locale: post-onboarding Journal, Names evidence/choice, Medic delivery, Camp exploration/cache, named/mixed preview, standing repeat, inn, stale/wrong-location/insufficient-goods/busy-target errors and saved result after language change. | Complete localized text without fallback/internal IDs; valid buttons, costs/outcomes matching, ≤64-byte callbacks, body/page budgets. No alternate mechanics by language. |
| J20 — After resolution | Reopen every completed finite record, inspect again, request fresh reward tokens, browse Local Work/gear/professions, perform a new standing attempt, leave and resume another unfinished project after restart. | Finite claims remain resolved; ongoing state persists; repeat work consumes new goods and pays once; no next chapter, all-regions badge, finale or global completion percentage. |

Allowed accelerators: deterministic legal RNG selections, mocked Telegram network, travel/respawn clock shortening that still performs original adjacency/discovery/availability and revision checks. Exclude impossible source rolls, forced success of denied profession rolls, mocked reward/kill observers, auto-learn, arbitrary profession/character levels, injected XP/gold/materials/gear/completions, forced battle HP or fabricated settlement sources. Reusing an earned checkpoint is allowed; editing its gameplay state is not. Unit tests may construct pathological states for defensive checks but must be labelled unit/integration evidence, never production journeys.

Automated acceptance requires all 20 definitions and their cases green, focused invariant tests green, final broad suite result explained with no unresolved RAV1 regression, and independent review of the actual candidate. If a frozen ordinary fight cannot be completed solo with legitimately earned ordinary equipment/builds, that is a candidate failure to investigate, not permission to mark it optional or bypass it in a test. Any needed product redesign returns to contract review; it is not an implementation-side choice.

## X. Human Telegram validation plan

Human testing has **not happened in Stage 2**. It is required before using “fully playtested” or “alpha validated.” It is separate from automated merge readiness: a green automated candidate plus green final review can be merge-ready while human validation remains outstanding, subject to the owner's merge decision. Neither deployment nor human completion is inferred from a merged PR.

Run three sessions on the actual Telegram candidate/deployment, record build SHA and account provenance:

1. Fresh account: 60–90 minutes of onboarding and first open-world choices; continue in a second session if onboarding consumes the first. Ask the tester to pick activities unaided after opening Journal; do not prescribe a region. Record the first three opportunities noticed, first choice, whether they interpret pins as a limit, ability to name a non-story alternative, and later resumption.
2. Returning/advanced account: 60–90 minutes across two self-chosen regions, one previous stockpile hand-in, one local choice, one optional specialist/work opportunity, gear/profession navigation and a restart/revisit. Verify they are not forced to replay Chapter I or infer a hidden region order.
3. Two-player session: 45–60 minutes with an optional mixed fight and independently accepted projects, plus intentional shared-spawn contention and one player leaving. Observe join/eligibility/harvest explanations and how easily both find another activity during a busy spawn.

For each session record wall-clock time in travel, gathering, combat, inventory/menu reading, and actual decisions; number of resource clicks, abandoned/confusing opportunities, which rewards are attractive, recovery spending, story comprehension, chosen order, resumption success and shared-spawn wait/friction. Separate timed waits from active decision time. Capture anonymized message excerpts/screens and player comments, not credentials/Telegram tokens. One observer logs; prompts stay neutral.

Product flags requiring follow-up before alpha-validation language: players repeatedly infer a main quest/mandatory region order; cannot discover alternatives within five minutes of post-onboarding browsing; believe pins control acceptance; cannot resume a paused project; abandon ordinary content because of unexplained profession grinding; or spend over half a post-onboarding session repeatedly clicking resource collection without choosing that profession activity. A technically successful four-hour trace dominated by mandatory repeated gathering is a product failure. These observations require documented resolution or explicit product follow-up; passing automated objectives does not override them. Human absence alone is not an automatic merge blocker.

## Y. Documentation and evidence deliverables for the eventual PR

Minimum required updates, in the same RAV1 Draft PR:

| Future document | Exact reconciliation |
|---|---|
| `rpg/docs/PROJECT_STATE_CURRENT.md` | Set verified baseline to PR233 merged at the stated SHA; preserve earlier merged Epics. Add RAV1 as candidate/unmerged with actual candidate SHA and acceptance/human status, never as deployed/merged before evidence. |
| `rpg/docs/ROADMAP_CURRENT.md` | Mark PEV1 merged; replace any obsolete global-campaign next-Epic language with independent Regional Adventures; record RAV1 candidate scope and excluded future systems. No promised Chapter II. |
| `rpg/docs/DOCS_INDEX.md` | Link the new frozen spec, implementation report and evidence; identify the spec as product authority and report as observed candidate state. Remove stale pointers claiming PR233 is pending. |
| `rpg/docs/systems/README.md` | Add the four-layer RAV1 authority map, files and transaction boundaries; retain hunts/professions/combat authority links; identify the opportunity catalogue as read-only. Correct PEV1 merged status. |
| `rpg/docs/epics/README.md` | Index Regional Adventures V1 as candidate/unmerged; PEV1 merged; link spec/report and distinguish automated acceptance from human validation. |
| `rpg/docs/DECISIONS_LOG.md` | Add dated RAV1-1 freeze: nonlinear world, seven projects, bounded model, facts/claims separation, roster-lock/T2 credit, exact repeat economics, three inns/four boards, permanent equal-reward choices, human-testing distinction. Record verified PR233 merge correction without rewriting historical claims as though they were made earlier. |

Required new artifacts:

* `rpg/docs/epics/REGIONAL_ADVENTURES_V1_SPEC.md`: this complete frozen contract, with identifier RAV1-1 and baseline; no scope dilution.
* `rpg/docs/epics/REGIONAL_ADVENTURES_V1_REPORT.md`: implementation mapping by authority, actual files/schema changes, final counts, focused/broad results, declared limitations, review outcome, exact candidate SHA, merge/deployment/human status separately.
* `rpg/docs/evidence/regional_adventures_v1.json`: schema version 1; baseline/candidate SHA, environment, all J01–J20 IDs and mandatory case results, earned-history/checkpoint provenance, accelerators, relevant receipts/encounter source IDs and before/after assertions, reward totals, focused/broad command outcomes and log paths. No bot tokens/private user data.
* `rpg/docs/evidence/regional_adventures_v1_human.md`: the plan above and an honest “not yet run” status until actual sessions occur; later add dates, build, observations and unresolved issues. Do not fabricate screenshots or testimonials.

Correct any adjacent PEV1 report header still presenting an unmerged candidate as current status with a short verified-merge note linking PR233; retain its historical test results and original candidate provenance. Do not rewrite historical logs or claim they tested RAV1. No separate docs-only PR is needed. After actual RAV1 merge, a later verification can update merged state; the candidate PR cannot predeclare its own merge.

## Z. Explicit non-goals

No global main quest, regional story order, global finale, final region, five linear regional campaigns, global completion percentage, regional reputation bars, universal quest currency, dailies/streaks/energy, universal quest engine, procedural quests, revival of historical `quests_data.py` as authority, dialogue scripting engine, event bus, teleport activation, new world regions, South Coast/Old Mine full routes, dungeon/expedition runtime, raids, matchmaking, world-boss scheduler, castles/core war, mass PvP expansion, marketplace/auction/escrow, housing/farming, profession V2, crafting tools/quality/specialization, new weapon trees, major combat rebalance, level-100 redesign, legendary/set/unique escalation, or server-wide branching state.

Also excluded: escorts, timed rescues, real-time shadow puzzles, new day/night/weather requirements, project abandonment/reset/reaccept, repeated narrative instances, more hunt slots, gear hand-in, universal power scores, mandatory group content, private spawned quest enemies, spawn queues, guaranteed named rare drops, new item/recipe/mob templates, free recovery, vendor cloning, new currencies, hidden route unlock tokens, cross-region narrative prerequisites, automatic project assignment, grind-based discovery rewards, long-term telemetry infrastructure, and a Sol implementation prompt at this stage.

## AA. Exact counts and planning estimate

Counting rules prevent double counting: a short project is still one project; Camp's cache is its project reward; a mixed encounter recipe is not a new mob template; service additions count `(location, service)` pairs; nested steps/objectives/reward tuples/text keys are not top-level catalogue records. Existing hunt and mixed records referenced by new read views are not “new static records.”

| Contract quantity | Exact count / interpretation |
|---|---|
| Local projects | **7**: 4 substantial local activities plus 3 short projects |
| Project steps | **18** |
| Project objective records | **22**, using 7 kinds |
| Short finite opportunities | **5**: Tool, Camp, Fresh Batch, Provisions, Medic's Table; first 3 included in projects |
| Discoveries | **10**, plus **2** auxiliary inspection facts not counted as discoveries |
| One-time reward claims | **10**: 7 projects + 2 direct requests + 1 independent cache |
| Standing/repeatable deliveries | **3** |
| Conventional hunts repaired/activated | **6 total**: 5 inaccessible definitions activated + existing Greyfang repaired; **0 new hunt definitions** |
| Named targets | **2**: Greyfang and Salt-Ridge Drifter; 2 new special spawn entries, 1 newly authored named identity |
| Mixed/authored encounters added | **2**; **2 existing mixed recipes retained**, 4 total surfaced |
| Regional service additions | **7**: 3 inns + 4 boards across 6 locations |
| New objective types | **7** in the separate project model: fact, deliver, kill, encounter, craft, respond, choose; no changes to HuntContract's type system |
| Permanent local choices | **3**, two outcomes each; one additional non-branching Sled method selection |
| New static catalogue records | **34** = 7 project + 10 discovery + 2 auxiliary inspect + 2 direct request + 1 cache + 3 standing + 5 regional summary + 2 special target + 2 mixed recipe |
| New DB tables | **5** |
| New migration markers | **1**, in an existing migration table |
| New top-level Journal views | **6**; home/detail/preview are subordinate surfaces |
| Localization key families | **18**, with complete ru/en/es coverage |
| Required automated acceptance journeys | **20 definitions**, including mandatory parameterized cases in W |

Expected changed/added line ranges for one coherent PR, planning estimates rather than quotas:

| Area | Estimated line delta |
|---|---:|
| Production runtime code, integration, migration, read model and UI; excludes content/locales | 2,200–3,400 |
| Static content/data and world definitions; excludes translated prose | 650–950 |
| Localization across ru/en/es | 1,500–2,100 |
| Tests and generated evidence | 3,000–4,500 |
| Specification/report/canonical documentation reconciliation | 1,300–1,800 |
| **Total expected added/changed lines** | **8,650–12,750**, approximately 30–45 affected files |

This estimate is smaller than the earlier broad Stage 1B envelope because RAV1-1 removes secondary variants, quest gear, generic objective kinds, extra standing work and new spawn mechanics. The final diff size is not an acceptance target. Keep evidence compact and structured, avoid committing local databases or raw repetitive multi-megabyte logs, and do not omit correctness tests to fit a line budget.

## AB. Remaining blockers and freeze boundary

There is no unresolved owner decision. All catalogue identities, locations, gates, steps, objective meanings, repetitions, rewards, choices, storage, combat timing, service changes and acceptance obligations are frozen above. Ordinary coding choices, translations faithful to the frozen meaning, and test-fixture organization remain implementation work. Any change to product semantics or a failed solo/economy invariant requires an explicit contract amendment, not an undocumented implementation choice.

Stage 2 delivers design only. Automated implementation acceptance, candidate review, merge verification, deployment verification and human Telegram playtesting remain future work and must be reported separately.

RAV1-1 STATUS: FROZEN
