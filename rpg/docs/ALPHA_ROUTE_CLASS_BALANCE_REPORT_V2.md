# Alpha Route/Class Balance Report v2

## Summary
This is a diagnostic and non-final report for future tuning scope decisions.

## Methodology
- Deterministic representative solo route-stage simulations.
- Routes: route_westwild, route_frostspine, route_ashen_ruins, route_mireveil, route_sunscar
- Stages: soft_entry, identity_visible, build_testing, route_exam
- Runs: 280

## Scope and Non-goals
- No route/mob/skill/reward/formula tuning.
- No Combat Core rewrite.
- No smart autobattle and no live AFK/autopilot.
- No group/pack simulation matrix.

## Diagnostic Config
- checked-in compact config: seeds=(1), max_samples_per_route_stage=1, max_turns=50, include_raw_runs=True.

## Scenario Cards
| route_id | stage | location_id | mob_id | role | lvl | scaling | spawn_profile | sample_tags | final_mob_stats |
|---|---|---|---|---|---:|---|---|---|---|
| route_westwild | soft_entry | westwild_n1 | crow | normal | 10 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 25, 'damage': 4} |
| route_westwild | identity_visible | westwild_n3 | forest_boar | normal | 35 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 153, 'damage': 12} |
| route_westwild | build_testing | westwild_n6 | bear | normal | 70 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 461, 'damage': 47} |
| route_westwild | route_exam | westwild_n10 | bear | normal | 95 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 659, 'damage': 65} |
| route_frostspine | soft_entry | frostspine_n1 | mountain_rabbit | normal | 10 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 36, 'damage': 4} |
| route_frostspine | identity_visible | frostspine_n3 | cave_bat | normal | 35 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 69, 'damage': 12} |
| route_frostspine | build_testing | frostspine_n6 | mountain_stone_golem | normal | 70 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn, elite_available | {'hp': 1283, 'damage': 84} |
| route_frostspine | route_exam | frostspine_n10 | ice_troll | normal | 95 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 1334, 'damage': 125} |
| route_ashen_ruins | soft_entry | ashen_n1 | skeleton_warrior | normal | 10 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 79, 'damage': 14} |
| route_ashen_ruins | identity_visible | ashen_n3 | skeleton_mage | normal | 35 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 123, 'damage': 31} |
| route_ashen_ruins | build_testing | ashen_n3b1 | cursed_knight | normal | 70 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn, stage_override, elite_available | {'hp': 708, 'damage': 90} |
| route_ashen_ruins | route_exam | ashen_n3b2a1 | ghost | normal | 95 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn, stage_override | {'hp': 416, 'damage': 80} |
| route_mireveil | soft_entry | mireveil_n1 | leech | normal | 10 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 54, 'damage': 9} |
| route_mireveil | identity_visible | mireveil_n3 | swamp_spider | normal | 35 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 122, 'damage': 22} |
| route_mireveil | build_testing | mireveil_n6 | giant_leech | normal | 70 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 429, 'damage': 61} |
| route_mireveil | route_exam | mireveil_n10 | old_witch | normal | 95 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn, elite_available | {'hp': 1111, 'damage': 168} |
Showing first 16 of 20 scenario cards.

## Archetype Cards
| archetype_id | power_tier | hp | mana | skill levels | policy metadata | gear budget | policy warning |
|---|---|---:|---:|---|---|---|---|
| guardian_shield_1h | soft_entry | 236 | 55 | {'shield_bash': 1, 'defensive_stance': 1, 'parry': 1} | always_guard_fallback (exec=True) | {'gear_tier': 'T1', 'rarity': 'common', 'enhancement_level': 0, 'profile_id': 'tank', 'total_budget': 287, 'budget_status': 'formula_budget_v1'} | guard_heavy_risk |
| guardian_shield_1h | identity_visible | 1101 | 75 | {'shield_bash': 2, 'defensive_stance': 2, 'parry': 2} | always_guard_fallback (exec=True) | {'gear_tier': 'T4', 'rarity': 'uncommon', 'enhancement_level': 3, 'profile_id': 'tank', 'total_budget': 2040, 'budget_status': 'formula_budget_v1'} | guard_heavy_risk |
| guardian_shield_1h | build_testing | 5113 | 100 | {'shield_bash': 3, 'defensive_stance': 3, 'parry': 3} | always_guard_fallback (exec=True) | {'gear_tier': 'T7', 'rarity': 'rare', 'enhancement_level': 6, 'profile_id': 'tank', 'total_budget': 10375, 'budget_status': 'formula_budget_v1'} | guard_heavy_risk |
| guardian_shield_1h | route_exam | 11269 | 130 | {'shield_bash': 4, 'defensive_stance': 4, 'parry': 4} | always_guard_fallback (exec=True) | {'gear_tier': 'T10', 'rarity': 'rare', 'enhancement_level': 8, 'profile_id': 'tank', 'total_budget': 23171, 'budget_status': 'formula_budget_v1'} | guard_heavy_risk |
| sword_2h_burst | soft_entry | 140 | 55 | {'power_strike': 1} | aggressive_burst (exec=False) | {'gear_tier': 'T1', 'rarity': 'common', 'enhancement_level': 0, 'profile_id': 'physical_dps', 'total_budget': 287, 'budget_status': 'formula_budget_v1'} | n/a |
| sword_2h_burst | identity_visible | 415 | 75 | {'power_strike': 2} | aggressive_burst (exec=False) | {'gear_tier': 'T4', 'rarity': 'uncommon', 'enhancement_level': 3, 'profile_id': 'physical_dps', 'total_budget': 2040, 'budget_status': 'formula_budget_v1'} | n/a |
| sword_2h_burst | build_testing | 1627 | 100 | {'power_strike': 3} | aggressive_burst (exec=False) | {'gear_tier': 'T7', 'rarity': 'rare', 'enhancement_level': 6, 'profile_id': 'physical_dps', 'total_budget': 10375, 'budget_status': 'formula_budget_v1'} | n/a |
| sword_2h_burst | route_exam | 3483 | 130 | {'power_strike': 4} | aggressive_burst (exec=False) | {'gear_tier': 'T10', 'rarity': 'rare', 'enhancement_level': 8, 'profile_id': 'physical_dps', 'total_budget': 23171, 'budget_status': 'formula_budget_v1'} | n/a |
| axe_2h_bruiser | soft_entry | 224 | 55 | {'power_strike': 1} | always_attack (exec=True) | {'gear_tier': 'T1', 'rarity': 'common', 'enhancement_level': 0, 'profile_id': 'bruiser', 'total_budget': 287, 'budget_status': 'formula_budget_v1'} | n/a |
| axe_2h_bruiser | identity_visible | 941 | 75 | {'power_strike': 2} | always_attack (exec=True) | {'gear_tier': 'T4', 'rarity': 'uncommon', 'enhancement_level': 3, 'profile_id': 'bruiser', 'total_budget': 2040, 'budget_status': 'formula_budget_v1'} | n/a |
| axe_2h_bruiser | build_testing | 4254 | 100 | {'power_strike': 3} | always_attack (exec=True) | {'gear_tier': 'T7', 'rarity': 'rare', 'enhancement_level': 6, 'profile_id': 'bruiser', 'total_budget': 10375, 'budget_status': 'formula_budget_v1'} | n/a |
| axe_2h_bruiser | route_exam | 9335 | 130 | {'power_strike': 4} | always_attack (exec=True) | {'gear_tier': 'T10', 'rarity': 'rare', 'enhancement_level': 8, 'profile_id': 'bruiser', 'total_budget': 23171, 'budget_status': 'formula_budget_v1'} | n/a |
| daggers_venom | soft_entry | 138 | 55 | {'poison_blade': 1} | venom_setup (exec=False) | {'gear_tier': 'T1', 'rarity': 'common', 'enhancement_level': 0, 'profile_id': 'evasion_dps', 'total_budget': 287, 'budget_status': 'formula_budget_v1'} | n/a |
| daggers_venom | identity_visible | 462 | 75 | {'poison_blade': 2} | venom_setup (exec=False) | {'gear_tier': 'T4', 'rarity': 'uncommon', 'enhancement_level': 3, 'profile_id': 'evasion_dps', 'total_budget': 2040, 'budget_status': 'formula_budget_v1'} | n/a |
| daggers_venom | build_testing | 1908 | 100 | {'poison_blade': 3} | venom_setup (exec=False) | {'gear_tier': 'T7', 'rarity': 'rare', 'enhancement_level': 6, 'profile_id': 'evasion_dps', 'total_budget': 10375, 'budget_status': 'formula_budget_v1'} | n/a |
| daggers_venom | route_exam | 4122 | 130 | {'poison_blade': 4} | venom_setup (exec=False) | {'gear_tier': 'T10', 'rarity': 'rare', 'enhancement_level': 8, 'profile_id': 'evasion_dps', 'total_budget': 23171, 'budget_status': 'formula_budget_v1'} | n/a |
| daggers_evasion | soft_entry | 134 | 55 | {'counter': 1} | evasion_tempo (exec=False) | {'gear_tier': 'T1', 'rarity': 'common', 'enhancement_level': 0, 'profile_id': 'evasion_dps', 'total_budget': 287, 'budget_status': 'formula_budget_v1'} | n/a |
| daggers_evasion | identity_visible | 458 | 75 | {'counter': 2} | evasion_tempo (exec=False) | {'gear_tier': 'T4', 'rarity': 'uncommon', 'enhancement_level': 3, 'profile_id': 'evasion_dps', 'total_budget': 2040, 'budget_status': 'formula_budget_v1'} | n/a |
| daggers_evasion | build_testing | 1904 | 100 | {'counter': 3} | evasion_tempo (exec=False) | {'gear_tier': 'T7', 'rarity': 'rare', 'enhancement_level': 6, 'profile_id': 'evasion_dps', 'total_budget': 10375, 'budget_status': 'formula_budget_v1'} | n/a |
| daggers_evasion | route_exam | 4118 | 130 | {'counter': 4} | evasion_tempo (exec=False) | {'gear_tier': 'T10', 'rarity': 'rare', 'enhancement_level': 8, 'profile_id': 'evasion_dps', 'total_budget': 23171, 'budget_status': 'formula_budget_v1'} | n/a |
| bow_sniper | soft_entry | 140 | 55 | {'hunters_mark': 1} | sniper_precision (exec=False) | {'gear_tier': 'T1', 'rarity': 'common', 'enhancement_level': 0, 'profile_id': 'bow_dps', 'total_budget': 287, 'budget_status': 'formula_budget_v1'} | n/a |
| bow_sniper | identity_visible | 415 | 75 | {'hunters_mark': 2} | sniper_precision (exec=False) | {'gear_tier': 'T4', 'rarity': 'uncommon', 'enhancement_level': 3, 'profile_id': 'bow_dps', 'total_budget': 2040, 'budget_status': 'formula_budget_v1'} | n/a |
| bow_sniper | build_testing | 1627 | 100 | {'hunters_mark': 3} | sniper_precision (exec=False) | {'gear_tier': 'T7', 'rarity': 'rare', 'enhancement_level': 6, 'profile_id': 'bow_dps', 'total_budget': 10375, 'budget_status': 'formula_budget_v1'} | n/a |
| bow_sniper | route_exam | 3483 | 130 | {'hunters_mark': 4} | sniper_precision (exec=False) | {'gear_tier': 'T10', 'rarity': 'rare', 'enhancement_level': 8, 'profile_id': 'bow_dps', 'total_budget': 23171, 'budget_status': 'formula_budget_v1'} | n/a |
Showing first 24 of 56 archetype cards.

## Route Overview
| route_id | runs | win_rate | timeout_rate |
|---|---:|---:|---:|
| route_ashen_ruins | 56 | 0.86 | 0.11 |
| route_frostspine | 56 | 0.86 | 0.14 |
| route_mireveil | 56 | 0.86 | 0.14 |
| route_sunscar | 56 | 0.86 | 0.14 |
| route_westwild | 56 | 0.86 | 0.14 |

## Archetype Overview
| archetype_id | runs | win_rate | timeout_rate |
|---|---:|---:|---:|
| axe_2h_bruiser | 20 | 1.00 | 0.00 |
| bow_ranger | 20 | 1.00 | 0.00 |
| bow_sniper | 20 | 1.00 | 0.00 |
| daggers_evasion | 20 | 1.00 | 0.00 |
| daggers_venom | 20 | 1.00 | 0.00 |
| guardian_shield_1h | 20 | 0.00 | 0.95 |
| holy_rod_paladin | 20 | 0.00 | 0.95 |
| holy_staff_solo | 20 | 1.00 | 0.00 |
| magic_staff_control | 20 | 1.00 | 0.00 |
| magic_staff_destruction | 20 | 1.00 | 0.00 |
| pure_support_solo_overlay | 20 | 1.00 | 0.00 |
| sword_2h_burst | 20 | 1.00 | 0.00 |
| tome_toolbox | 20 | 1.00 | 0.00 |
| wand_tempo | 20 | 1.00 | 0.00 |

## Target vs Observed v2 Signals
This table shows a compact route-balanced suspicious preview, not the full target-vs-observed matrix.
Showing 40 route-balanced suspicious preview rows out of 120 suspicious candidates. Full target comparison data is available from build_alpha_balance_report_data(). Hidden rows are not resolved or dismissed.
| route | stage | archetype | target | observed_v1 | observed_diagnostic_label_v2 | reasons |
|---|---|---|---|---|---|---|
| route_ashen_ruins | build_testing | axe_2h_bruiser | hard | strong | strong_clean | strong_vs_high_target |
| route_frostspine | build_testing | bow_ranger | hard | strong | strong_clean | strong_vs_high_target |
| route_mireveil | build_testing | bow_sniper | hard | strong | strong_clean | strong_vs_high_target |
| route_sunscar | build_testing | axe_2h_bruiser | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_westwild | build_testing | guardian_shield_1h | normal | dead_or_blocked | policy_failure | dead_or_blocked_above_target, timeout_heavy, diagnostic_v2_flag, policy_failure_guard_loop |
| route_ashen_ruins | build_testing | bow_sniper | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_frostspine | build_testing | daggers_evasion | hard | strong | strong_clean | strong_vs_high_target |
| route_mireveil | build_testing | guardian_shield_1h | normal_strong | dead_or_blocked | policy_failure | dead_or_blocked_above_target, timeout_heavy, diagnostic_v2_flag, policy_failure_guard_loop |
| route_sunscar | build_testing | daggers_venom | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_westwild | build_testing | holy_rod_paladin | normal | dead_or_blocked | policy_failure | dead_or_blocked_above_target, timeout_heavy, diagnostic_v2_flag, policy_failure_guard_loop |
| route_ashen_ruins | build_testing | daggers_evasion | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_frostspine | build_testing | daggers_venom | normal_hard_split | strong | strong_clean | strong_vs_high_target |
| route_mireveil | build_testing | holy_rod_paladin | normal_strong | dead_or_blocked | policy_failure | dead_or_blocked_above_target, timeout_heavy, diagnostic_v2_flag, policy_failure_guard_loop |
| route_sunscar | build_testing | guardian_shield_1h | hard | dead_or_blocked | policy_failure | dead_or_blocked_above_target, timeout_heavy, diagnostic_v2_flag, policy_failure_guard_loop |
| route_westwild | build_testing | holy_staff_solo | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_ashen_ruins | build_testing | daggers_venom | very_hard | strong | strong_clean | strong_vs_high_target |
| route_frostspine | build_testing | guardian_shield_1h | strong | dead_or_blocked | policy_failure | dead_or_blocked_above_target, timeout_heavy, diagnostic_v2_flag, policy_failure_guard_loop |
| route_mireveil | build_testing | sword_2h_burst | hard | strong | strong_clean | strong_vs_high_target |
| route_sunscar | build_testing | holy_rod_paladin | hard | dead_or_blocked | policy_failure | dead_or_blocked_above_target, timeout_heavy, diagnostic_v2_flag, policy_failure_guard_loop |
| route_westwild | build_testing | pure_support_solo_overlay | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_ashen_ruins | build_testing | guardian_shield_1h | normal | dead_or_blocked | policy_failure | dead_or_blocked_above_target, timeout_heavy, diagnostic_v2_flag, policy_failure_guard_loop |
| route_frostspine | build_testing | holy_rod_paladin | strong | dead_or_blocked | policy_failure | dead_or_blocked_above_target, timeout_heavy, diagnostic_v2_flag, policy_failure_guard_loop |
| route_mireveil | identity_visible | bow_sniper | hard | strong | strong_clean | strong_vs_high_target |
| route_sunscar | build_testing | holy_staff_solo | hard_very_hard | strong | strong_clean | strong_vs_high_target |
| route_westwild | identity_visible | guardian_shield_1h | normal | dead_or_blocked | policy_failure | dead_or_blocked_above_target, timeout_heavy, diagnostic_v2_flag, policy_failure_guard_loop |
| route_ashen_ruins | build_testing | holy_rod_paladin | strong | dead_or_blocked | policy_failure | dead_or_blocked_above_target, timeout_heavy, diagnostic_v2_flag, policy_failure_guard_loop |
| route_frostspine | build_testing | magic_staff_control | hard | strong | strong_clean | strong_vs_high_target |
| route_mireveil | identity_visible | guardian_shield_1h | normal_strong | dead_or_blocked | policy_failure | dead_or_blocked_above_target, timeout_heavy, diagnostic_v2_flag, policy_failure_guard_loop |
| route_sunscar | build_testing | magic_staff_destruction | hard | strong | strong_clean | strong_vs_high_target |
| route_westwild | identity_visible | holy_rod_paladin | normal | dead_or_blocked | policy_failure | dead_or_blocked_above_target, timeout_heavy, diagnostic_v2_flag, policy_failure_guard_loop |
| route_ashen_ruins | identity_visible | axe_2h_bruiser | hard | strong | strong_clean | strong_vs_high_target |
| route_frostspine | build_testing | magic_staff_destruction | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_mireveil | identity_visible | holy_rod_paladin | normal_strong | dead_or_blocked | policy_failure | dead_or_blocked_above_target, timeout_heavy, diagnostic_v2_flag, policy_failure_guard_loop |
| route_sunscar | build_testing | pure_support_solo_overlay | very_hard_playable | strong | strong_clean | strong_vs_high_target |
| route_westwild | identity_visible | holy_staff_solo | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_ashen_ruins | identity_visible | bow_sniper | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_frostspine | build_testing | wand_tempo | hard | strong | strong_clean | strong_vs_high_target |
| route_mireveil | identity_visible | sword_2h_burst | hard | strong | strong_clean | strong_vs_high_target |
| route_sunscar | build_testing | tome_toolbox | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_westwild | identity_visible | pure_support_solo_overlay | normal_hard | strong | strong_clean | strong_vs_high_target |

## Suspicious Clusters
Suspicious rows: 120.

## Progression Audit Preview
This section is diagnostic-only and not a tuning verdict.
Gear assumptions use formula_budget_v1 simulation presets where available.
Flag counts:
- hard_target_tested_on_weak_sample: 44
- overclean_win: 80
- policy_failure_guard_loop: 40
| route | stage | archetype | lvl | gear | rarity | + | budget | profile | mob | role | encounter | scaled_hp | scaled_damage | target | observed_v2 | audit flags |
|---|---|---|---:|---|---|---:|---:|---|---|---|---:|---:|---:|---|---|---|
| route_westwild | soft_entry | guardian_shield_1h | 10 | T1 | common | +0 | 287 | tank | crow | normal | 10 | 25 | 4 | normal | policy_failure | policy_failure_guard_loop |
| route_westwild | soft_entry | sword_2h_burst | 10 | T1 | common | +0 | 287 | physical_dps | crow | normal | 10 | 25 | 4 | normal | strong_clean |  |
| route_westwild | soft_entry | axe_2h_bruiser | 10 | T1 | common | +0 | 287 | bruiser | crow | normal | 10 | 25 | 4 | strong | strong_clean |  |
| route_westwild | soft_entry | daggers_venom | 10 | T1 | common | +0 | 287 | evasion_dps | crow | normal | 10 | 25 | 4 | strong | strong_clean |  |
| route_westwild | soft_entry | daggers_evasion | 10 | T1 | common | +0 | 287 | evasion_dps | crow | normal | 10 | 25 | 4 | strong | strong_clean |  |
| route_westwild | soft_entry | bow_sniper | 10 | T1 | common | +0 | 287 | bow_dps | crow | normal | 10 | 25 | 4 | strong | strong_clean |  |
| route_westwild | soft_entry | bow_ranger | 10 | T1 | common | +0 | 287 | bow_dps | crow | normal | 10 | 25 | 4 | strong | strong_clean |  |
| route_westwild | soft_entry | magic_staff_destruction | 10 | T1 | common | +0 | 287 | magic_dps | crow | normal | 10 | 25 | 4 | normal | strong_clean |  |
| route_westwild | soft_entry | magic_staff_control | 10 | T1 | common | +0 | 287 | control_caster | crow | normal | 10 | 25 | 4 | normal | strong_clean |  |
| route_westwild | soft_entry | wand_tempo | 10 | T1 | common | +0 | 287 | magic_dps | crow | normal | 10 | 25 | 4 | normal | strong_clean |  |
| route_westwild | soft_entry | holy_staff_solo | 10 | T1 | common | +0 | 287 | healer_support | crow | normal | 10 | 25 | 4 | hard | strong_clean | overclean_win |
| route_westwild | soft_entry | holy_rod_paladin | 10 | T1 | common | +0 | 287 | paladin_hybrid | crow | normal | 10 | 25 | 4 | normal | policy_failure | policy_failure_guard_loop |
| route_westwild | soft_entry | tome_toolbox | 10 | T1 | common | +0 | 287 | toolbox_hybrid | crow | normal | 10 | 25 | 4 | normal | strong_clean |  |
| route_westwild | soft_entry | pure_support_solo_overlay | 10 | T1 | common | +0 | 287 | healer_support | crow | normal | 10 | 25 | 4 | hard | strong_clean | overclean_win |
| route_westwild | identity_visible | guardian_shield_1h | 35 | T4 | uncommon | +3 | 2040 | tank | forest_boar | normal | 35 | 153 | 12 | normal | policy_failure | policy_failure_guard_loop |
| route_westwild | identity_visible | sword_2h_burst | 35 | T4 | uncommon | +3 | 2040 | physical_dps | forest_boar | normal | 35 | 153 | 12 | normal | strong_clean |  |
| route_westwild | identity_visible | axe_2h_bruiser | 35 | T4 | uncommon | +3 | 2040 | bruiser | forest_boar | normal | 35 | 153 | 12 | strong | strong_clean |  |
| route_westwild | identity_visible | daggers_venom | 35 | T4 | uncommon | +3 | 2040 | evasion_dps | forest_boar | normal | 35 | 153 | 12 | strong | strong_clean |  |
| route_westwild | identity_visible | daggers_evasion | 35 | T4 | uncommon | +3 | 2040 | evasion_dps | forest_boar | normal | 35 | 153 | 12 | strong | strong_clean |  |
| route_westwild | identity_visible | bow_sniper | 35 | T4 | uncommon | +3 | 2040 | bow_dps | forest_boar | normal | 35 | 153 | 12 | strong | strong_clean |  |
Showing first 20 of 280 progression audit rows. Hidden rows are not resolved or dismissed.

## Representative Suspicious Fight Traces
Showing up to 10 route-balanced representative suspicious traces. Hidden traces are not resolved or dismissed.
| route_id | stage | archetype_id | location_id | mob_id | winner | end_reason | turns | actions_used | skills_used |
|---|---|---|---|---|---|---|---:|---|---|
| route_ashen_ruins | build_testing | guardian_shield_1h | ashen_n3b1 | cursed_knight | none | timeout | 50 | {'normal_attack': 0, 'guard_fallback': 50} | [] |
| route_frostspine | build_testing | guardian_shield_1h | frostspine_n6 | mountain_stone_golem | none | timeout | 50 | {'normal_attack': 0, 'guard_fallback': 50} | [] |
| route_mireveil | build_testing | guardian_shield_1h | mireveil_n6 | giant_leech | none | timeout | 50 | {'normal_attack': 0, 'guard_fallback': 50} | [] |
| route_sunscar | build_testing | guardian_shield_1h | sunscar_n6 | desert_elephant | none | timeout | 50 | {'normal_attack': 0, 'guard_fallback': 50} | [] |
| route_westwild | build_testing | guardian_shield_1h | westwild_n6 | bear | none | timeout | 50 | {'normal_attack': 0, 'guard_fallback': 50} | [] |
| route_ashen_ruins | build_testing | holy_rod_paladin | ashen_n3b1 | cursed_knight | none | timeout | 50 | {'normal_attack': 0, 'guard_fallback': 50} | [] |
| route_frostspine | build_testing | holy_rod_paladin | frostspine_n6 | mountain_stone_golem | none | timeout | 50 | {'normal_attack': 0, 'guard_fallback': 50} | [] |
| route_mireveil | build_testing | holy_rod_paladin | mireveil_n6 | giant_leech | none | timeout | 50 | {'normal_attack': 0, 'guard_fallback': 50} | [] |
| route_sunscar | build_testing | holy_rod_paladin | sunscar_n6 | desert_elephant | none | timeout | 50 | {'normal_attack': 0, 'guard_fallback': 50} | [] |
| route_westwild | build_testing | holy_rod_paladin | westwild_n6 | bear | none | timeout | 50 | {'normal_attack': 0, 'guard_fallback': 50} | [] |

## Diagnostic Label Definitions
strong_clean, strong_but_risky, normal, hard, very_hard, death_blocked, timeout_stall, no_progress_stall, resource_collapse, policy_failure, inconclusive.

## Limitations
- Representative solo samples only (route-stage mob snapshots).
- No pack/group runtime simulation matrix yet.
- No final balance conclusions yet.
- No route/mob/skill tuning performed.
- Alpha diagnostic signal only; not a final balance verdict.
- Observed-vs-target comparisons are coarse bands, not proof of tuning direction.
- Missing target metadata rows are treated as inconclusive, not mismatch verdicts.
- No pack/group runtime matrix in this report version.

## Recommended Next Steps
- Use this report to scope targeted follow-up tuning PRs only.

## Raw Data Pointers
- Source module: `game.combat_simulation_matrix.run_route_stage_simulation_matrix`.
- Raw runs included in current report data object: True.
