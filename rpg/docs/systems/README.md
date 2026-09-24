# System Documentation and Implementation Map

- Status: Active
- Authority: Canonical navigation map for current implementation ownership
- Last reconciled: 2026-09-23, against `ad5435e577e45e63da2ca57af2296203d88cedd5`

This map points to current code and the documents that explain it. Code remains the
exact implementation authority. Foundations express intent; Epic and pass reports
record delivery history.

## Combat and builds

- Current delivery boundary: [PR231 Character Builds & Combat Identity V1](../CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md)
- Supporting specs: [accuracy/evasion](combat/ACCURACY_EVASION_V1_SPEC.md),
  [live side-turn runtime](combat/LIVE_COMBAT_SIDE_TURN_SPEC.md), and the
  compatibility-retained [target pattern chapter](../TARGET_PATTERN_SYSTEM_V1.md)
- Current owners: `game/build_contract.py`, `game/build_progression.py`,
  `game/actor_snapshot.py`, `game/combat_identity.py`, `game/combat_orders.py`,
  `game/live_combat_runtime.py`, `game/combat.py`, `game/skill_engine.py`,
  `game/skills.py`, `game/weapon_mastery.py`, `handlers/battle.py`, and
  `handlers/build.py`
- Historical architecture/formula/weapon designs are catalogued in
  [archive/README.md](../archive/README.md); they do not override the V1 runtime.

## World and travel

- Durable topology: [world skeleton](../foundation/WORLD_SKELETON_V1.md)
- Supporting specs: [world graph](world/WORLD_GRAPH_V1.md),
  [location map](world/WORLD_LOCATION_MAP_V1.md),
  [data model](world/WORLD_DATA_MODEL_V1.md), and
  [travel/teleport](world/TRAVEL_AND_TELEPORT_V1.md)
- Current owners: `game/locations.py`, `game/world_scaffolding.py`,
  `game/contextual_keyboard.py`, and `handlers/location.py`
- Ordinary graph travel is implemented. Teleport design is retained but activation is
  deferred.

## Gear, itemization, and rewards

- Current delivery boundary: [PR230 Field Loot & Gear Progression V1](../epics/FIELD_LOOT_AND_GEAR_PROGRESSION_V1.md)
- Supporting spec: [equipment enhancement phase 1](gear/EQUIPMENT_ENHANCEMENT_PHASE1.md)
- Current owners: `game/field_catalog.py`, `game/itemization.py`,
  `game/gear_instances.py`, `game/gear_progression.py`, `game/gear_ui.py`,
  `game/equipment_stats.py`, `game/enhancement_material_routing.py`,
  `game/tier_advancement.py`, `game/pve_reward_settlement.py`,
  `handlers/inventory.py`, and `handlers/location.py`

## Professions and economy

- Design intent: [loot/crafting/progression foundation](../foundation/LOOT_CRAFT_PROGRESSION_FOUNDATION.md)
- Active frozen contract: [Professions & Economy V1](../epics/PROFESSIONS_ECONOMY_V1_SPEC.md)
- Draft candidate report: [PEV1-1 delivery record](../epics/PROFESSIONS_ECONOMY_V1_REPORT.md)
- Playable subset delivery: [PR229 vertical slice](../epics/PLAYABLE_ALPHA_VERTICAL_SLICE_V1.md)
- Current owners: `game/gathering_foundation.py`, `game/gathering_runtime.py`,
  `game/gathering_progression.py`, `game/resource_handbook.py`, `game/hunting.py`,
  `game/crafting_foundation.py`, `game/crafting_runtime.py`, `game/quest_board.py`,
  `game/profession_resources.py`, `game/profession_recipes.py`,
  `game/profession_schema.py`, `game/recipe_knowledge.py`,
  `game/economy_actions.py`, `handlers/professions.py`, and `handlers/location.py`
- The merged baseline remains the bounded PR229 subset. The active PEV1-1 candidate
  expands this boundary but is not merged or deployed.

## PvE and playable chapter

- Current delivery records: [PR229](../epics/PLAYABLE_ALPHA_VERTICAL_SLICE_V1.md),
  [PR230](../epics/FIELD_LOOT_AND_GEAR_PROGRESSION_V1.md), and
  [PR231](../CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md)
- Current owners: `game/pve_live.py`, `game/live_combat_runtime.py`,
  `game/combat_orders.py`, `game/enemy_profiles.py`,
  `game/pve_reward_settlement.py`, `game/starter_kit.py`,
  `game/quests_data.py`, `handlers/battle.py`, and `handlers/chapter.py`

## PvP

- Durable policy: [PvP ruleset foundation](../foundation/PVP_RULESET_FOUNDATION.md)
- Current bounded evaluator scope: [PR231 report](../CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md)
- Current owners: `game/pvp_rules.py`, `game/pvp_state.py`,
  `game/pvp_engagement.py`, `game/pvp_live.py`, `game/pvp_turn_timing.py`,
  `game/pvp_death_policy.py`, and `game/pvp_inventory_policy.py`
- Current V1 action support is bounded; broader structured PvP is deferred.

## Compatibility-retained historical pass documents

The following test-consumed paths remain in `docs/`. They are delivery/diagnostic
records for their pass, not current system specifications:

- [OPEN_WORLD_PACK_BALANCE_BASELINE.md](../OPEN_WORLD_PACK_BALANCE_BASELINE.md)
- [OPEN_WORLD_ENCOUNTER_COMPOSITION_V1.md](../OPEN_WORLD_ENCOUNTER_COMPOSITION_V1.md)
- [OPEN_WORLD_REWARD_THREAT_ALIGNMENT_V1.md](../OPEN_WORLD_REWARD_THREAT_ALIGNMENT_V1.md)
- [OPEN_WORLD_SPAWN_PROFILE_PLACEMENT_V1.md](../OPEN_WORLD_SPAWN_PROFILE_PLACEMENT_V1.md)
- [OPEN_WORLD_ROUTE_BALANCE_READINESS_V1.md](../OPEN_WORLD_ROUTE_BALANCE_READINESS_V1.md)
- [OPEN_WORLD_ROUTE_TUNING_PASS1.md](../OPEN_WORLD_ROUTE_TUNING_PASS1.md)
- [OPEN_WORLD_ROUTE_TUNING_PASS2.md](../OPEN_WORLD_ROUTE_TUNING_PASS2.md)
- [OPEN_WORLD_ROUTE_TUNING_PASS3.md](../OPEN_WORLD_ROUTE_TUNING_PASS3.md)
- [OPEN_WORLD_READINESS_GAP_CLOSURE_PR3I.md](../OPEN_WORLD_READINESS_GAP_CLOSURE_PR3I.md)
- [OPEN_WORLD_PVE_NUMERIC_TUNING_BASELINE_V1.md](../OPEN_WORLD_PVE_NUMERIC_TUNING_BASELINE_V1.md)
- [OPEN_WORLD_PVE_NUMERIC_TUNING_PASS1.md](../OPEN_WORLD_PVE_NUMERIC_TUNING_PASS1.md)
- [OPEN_WORLD_REWARD_LOOT_SANITY_PASS1.md](../OPEN_WORLD_REWARD_LOOT_SANITY_PASS1.md)
- [OPEN_WORLD_PROGRESSION_LOOP_PASS1.md](../OPEN_WORLD_PROGRESSION_LOOP_PASS1.md)
- [OPEN_WORLD_ROUTE_OBJECTIVES_PASS1.md](../OPEN_WORLD_ROUTE_OBJECTIVES_PASS1.md)
- [ALPHA_UX_ONBOARDING_RECOVERY_PASS1.md](../ALPHA_UX_ONBOARDING_RECOVERY_PASS1.md)
- [ALPHA_RELEASE_GATE_PR3P.md](../ALPHA_RELEASE_GATE_PR3P.md)

Historical generated balance reports are catalogued with their provenance in
[evidence/README.md](../evidence/README.md).
