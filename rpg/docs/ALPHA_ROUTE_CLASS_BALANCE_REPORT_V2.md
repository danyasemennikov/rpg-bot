# Alpha Route/Class Balance Report v2

## Summary
This is a diagnostic and non-final report for future tuning scope decisions.

## Methodology
- Deterministic representative solo route-stage simulations plus composite_pack_pressure_v1 pack proxy samples.
- Routes: route_westwild, route_frostspine, route_ashen_ruins, route_mireveil, route_sunscar
- Stages: soft_entry, identity_visible, build_testing, route_exam
- Runs: 280

## Scope and Non-goals
- No live route/mob/skill/reward/formula tuning.
- PR12 includes simulation/reporting-only stage pressure tuning.
- No Combat Core rewrite.
- No smart autobattle and no live AFK/autopilot.
- No live pack/group runtime combat.

## Diagnostic Config
- checked-in compact config: seeds=(1), max_samples_per_route_stage=1, max_turns=50, include_raw_runs=True.

## Scenario Cards
| route_id | stage | location_id | mob_id | role | lvl | scaling | spawn_profile | sample_tags | final_mob_stats |
|---|---|---|---|---|---:|---|---|---|---|
| route_westwild | soft_entry | westwild_n1 | crow | normal | 10 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 25, 'damage': 4} |
| route_westwild | identity_visible | westwild_n3 | forest_boar | normal | 35 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 166, 'damage': 12} |
| route_westwild | build_testing | westwild_n6 | bear | normal | 70 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 562, 'damage': 62} |
| route_westwild | route_exam | westwild_n10 | bear | normal | 95 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 891, 'damage': 100} |
| route_frostspine | soft_entry | frostspine_n1 | mountain_rabbit | normal | 10 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 36, 'damage': 4} |
| route_frostspine | identity_visible | frostspine_n3 | cave_bat | normal | 35 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 75, 'damage': 12} |
| route_frostspine | build_testing | frostspine_n6 | mountain_stone_golem | normal | 70 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn, elite_available | {'hp': 1860, 'damage': 112} |
| route_frostspine | route_exam | frostspine_n10 | ice_troll | normal | 95 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 2136, 'damage': 195} |
| route_ashen_ruins | soft_entry | ashen_n1 | skeleton_warrior | normal | 10 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 79, 'damage': 14} |
| route_ashen_ruins | identity_visible | ashen_n3 | skeleton_mage | normal | 35 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 133, 'damage': 33} |
| route_ashen_ruins | build_testing | ashen_n3b1 | cursed_knight | normal | 70 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn, stage_override, elite_available | {'hp': 950, 'damage': 132} |
| route_ashen_ruins | route_exam | ashen_n3b2a1 | ghost | normal | 95 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn, stage_override | {'hp': 595, 'damage': 138} |
| route_mireveil | soft_entry | mireveil_n1 | leech | normal | 10 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 54, 'damage': 9} |
| route_mireveil | identity_visible | mireveil_n3 | swamp_spider | normal | 35 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 132, 'damage': 24} |
| route_mireveil | build_testing | mireveil_n6 | giant_leech | normal | 70 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn | {'hp': 644, 'damage': 82} |
| route_mireveil | route_exam | mireveil_n10 | old_witch | normal | 95 | formula_mob_scaling_v1 | normal | representative, solo, normal_spawn, elite_available | {'hp': 1811, 'damage': 270} |
Showing first 16 of 20 scenario cards.

## Archetype Cards
| archetype_id | power_tier | hp | mana | skill levels | policy metadata | gear budget | policy warning |
|---|---|---:|---:|---|---|---|---|
| guardian_shield_1h | soft_entry | 236 | 55 | {'shield_bash': 1, 'defensive_stance': 1, 'parry': 1} | guard_then_attack (exec=True) | {'gear_tier': 'T1', 'rarity': 'common', 'enhancement_level': 0, 'profile_id': 'tank', 'total_budget': 287, 'budget_status': 'formula_budget_v1'} | n/a |
| guardian_shield_1h | identity_visible | 1101 | 75 | {'shield_bash': 2, 'defensive_stance': 2, 'parry': 2} | guard_then_attack (exec=True) | {'gear_tier': 'T4', 'rarity': 'uncommon', 'enhancement_level': 3, 'profile_id': 'tank', 'total_budget': 2040, 'budget_status': 'formula_budget_v1'} | n/a |
| guardian_shield_1h | build_testing | 5113 | 100 | {'shield_bash': 3, 'defensive_stance': 3, 'parry': 3} | guard_then_attack (exec=True) | {'gear_tier': 'T7', 'rarity': 'rare', 'enhancement_level': 6, 'profile_id': 'tank', 'total_budget': 10375, 'budget_status': 'formula_budget_v1'} | n/a |
| guardian_shield_1h | route_exam | 11269 | 130 | {'shield_bash': 4, 'defensive_stance': 4, 'parry': 4} | guard_then_attack (exec=True) | {'gear_tier': 'T10', 'rarity': 'rare', 'enhancement_level': 8, 'profile_id': 'tank', 'total_budget': 23171, 'budget_status': 'formula_budget_v1'} | n/a |
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
| daggers_venom | build_testing | 1908 | 100 | {'poison_blade': 3, 'envenom': 3, 'toxic_cut': 3} | venom_setup (exec=False) | {'gear_tier': 'T7', 'rarity': 'rare', 'enhancement_level': 6, 'profile_id': 'evasion_dps', 'total_budget': 10375, 'budget_status': 'formula_budget_v1'} | n/a |
| daggers_venom | route_exam | 4122 | 130 | {'poison_blade': 4, 'envenom': 4, 'toxic_cut': 4} | venom_setup (exec=False) | {'gear_tier': 'T10', 'rarity': 'rare', 'enhancement_level': 8, 'profile_id': 'evasion_dps', 'total_budget': 23171, 'budget_status': 'formula_budget_v1'} | n/a |
| daggers_evasion | soft_entry | 134 | 55 | {'smoke_bomb': 1} | evasion_tempo (exec=False) | {'gear_tier': 'T1', 'rarity': 'common', 'enhancement_level': 0, 'profile_id': 'evasion_dps', 'total_budget': 287, 'budget_status': 'formula_budget_v1'} | n/a |
| daggers_evasion | identity_visible | 458 | 75 | {'smoke_bomb': 2} | evasion_tempo (exec=False) | {'gear_tier': 'T4', 'rarity': 'uncommon', 'enhancement_level': 3, 'profile_id': 'evasion_dps', 'total_budget': 2040, 'budget_status': 'formula_budget_v1'} | n/a |
| daggers_evasion | build_testing | 1904 | 100 | {'smoke_bomb': 3, 'feint_step': 3} | evasion_tempo (exec=False) | {'gear_tier': 'T7', 'rarity': 'rare', 'enhancement_level': 6, 'profile_id': 'evasion_dps', 'total_budget': 10375, 'budget_status': 'formula_budget_v1'} | n/a |
| daggers_evasion | route_exam | 4118 | 130 | {'counter': 4, 'smoke_bomb': 4, 'feint_step': 4} | evasion_tempo (exec=False) | {'gear_tier': 'T10', 'rarity': 'rare', 'enhancement_level': 8, 'profile_id': 'evasion_dps', 'total_budget': 23171, 'budget_status': 'formula_budget_v1'} | n/a |
| bow_sniper | soft_entry | 140 | 55 | {'hunters_mark': 1} | sniper_precision (exec=False) | {'gear_tier': 'T1', 'rarity': 'common', 'enhancement_level': 0, 'profile_id': 'bow_dps', 'total_budget': 287, 'budget_status': 'formula_budget_v1'} | n/a |
| bow_sniper | identity_visible | 415 | 75 | {'hunters_mark': 2} | sniper_precision (exec=False) | {'gear_tier': 'T4', 'rarity': 'uncommon', 'enhancement_level': 3, 'profile_id': 'bow_dps', 'total_budget': 2040, 'budget_status': 'formula_budget_v1'} | n/a |
| bow_sniper | build_testing | 1627 | 100 | {'hunters_mark': 3, 'aimed_shot': 3} | sniper_precision (exec=False) | {'gear_tier': 'T7', 'rarity': 'rare', 'enhancement_level': 6, 'profile_id': 'bow_dps', 'total_budget': 10375, 'budget_status': 'formula_budget_v1'} | n/a |
| bow_sniper | route_exam | 3483 | 130 | {'hunters_mark': 4, 'aimed_shot': 4} | sniper_precision (exec=False) | {'gear_tier': 'T10', 'rarity': 'rare', 'enhancement_level': 8, 'profile_id': 'bow_dps', 'total_budget': 23171, 'budget_status': 'formula_budget_v1'} | n/a |
Showing first 24 of 56 archetype cards.

## Route Overview
| route_id | runs | win_rate | timeout_rate |
|---|---:|---:|---:|
| route_ashen_ruins | 56 | 1.00 | 0.00 |
| route_frostspine | 56 | 1.00 | 0.00 |
| route_mireveil | 56 | 1.00 | 0.00 |
| route_sunscar | 56 | 0.98 | 0.00 |
| route_westwild | 56 | 1.00 | 0.00 |

## Archetype Overview
| archetype_id | runs | win_rate | timeout_rate |
|---|---:|---:|---:|
| axe_2h_bruiser | 20 | 1.00 | 0.00 |
| bow_ranger | 20 | 1.00 | 0.00 |
| bow_sniper | 20 | 1.00 | 0.00 |
| daggers_evasion | 20 | 1.00 | 0.00 |
| daggers_venom | 20 | 1.00 | 0.00 |
| guardian_shield_1h | 20 | 1.00 | 0.00 |
| holy_rod_paladin | 20 | 1.00 | 0.00 |
| holy_staff_solo | 20 | 1.00 | 0.00 |
| magic_staff_control | 20 | 1.00 | 0.00 |
| magic_staff_destruction | 20 | 1.00 | 0.00 |
| pure_support_solo_overlay | 20 | 0.95 | 0.00 |
| sword_2h_burst | 20 | 1.00 | 0.00 |
| tome_toolbox | 20 | 1.00 | 0.00 |
| wand_tempo | 20 | 1.00 | 0.00 |

## PR12 First Tuning Pass Summary
- Pass status: first controlled tuning pass (not final balance).
- Changed policy assumptions:
  - defensive guard-loop simulation policy replaced with simulation-only guard-then-attack fallback for guardian_shield_1h and holy_rod_paladin.
- Changed numeric knobs:
  - added simulation-stage pressure modifiers:
    - soft_entry: baseline unchanged;
    - identity_visible: mild hp/damage pressure;
    - build_testing: moderate hp/damage pressure;
    - route_exam: stronger late-stage pressure.
  - simulation-only role escalation for hard/very_hard build_testing/route_exam matchup samples (pressure, and elite where elite_available on route_exam very_hard samples).
  - no live mob templates or live combat formulas changed.
- Policy artifact status:
  - policy_failure_guard_loop count: 0 (diagnostic simulation policy artifact, not a direct route tuning verdict).
  - current late-stage overclean audit flag count: 42.
  - previous PR12 policy-sanity global overclean baseline: 88.
  - this late-stage scoped flag count is not a comparable global overclean improvement metric.
  - suspicious rows: 88.
  - route win rates in compact deterministic run may still remain 1.00; treat this as remaining underpressure signal if observed.
- Remaining known issues:
  - broad overclean/underpressure signals may still remain and require route/archetype targeted follow-up tuning passes.
- Pack proxy status:
  - composite_pack_pressure_v1 remains active as simulation/reporting-only proxy; no live group combat/targeting added.

## PR13 Targeted Tuning Candidates
Diagnostic compact cluster view; use full report_data for complete candidate selection.
PR14 target expectation calibration below further separates raw global signal from actionable tuning backlog.
- global overclean candidates (strong_vs_high_target): 87.
- late-stage targeted candidates (build_testing/route_exam only): 43.
- top targeted late-stage clusters shown: 8 (limit=8).
- global diagnostic clusters are available in report_data as global_overclean_top_clusters.
| cluster_type | cluster_key | count |
|---|---|---:|
| route+stage | route_sunscar / build_testing | 8 |
| route+stage | route_sunscar / route_exam | 7 |
| route+stage | route_frostspine / build_testing | 6 |
| route+stage | route_frostspine / route_exam | 6 |
| route+stage | route_ashen_ruins / build_testing | 4 |
| route+stage | route_ashen_ruins / route_exam | 4 |
| route+stage | route_mireveil / build_testing | 2 |
| route+stage | route_mireveil / route_exam | 2 |

## PR13 Targeted Alpha Tuning Summary
- Previous PR12 global overclean baseline: 86.
- Current global overclean candidates: 87.
- Current late-stage overclean audit flags: 42.
- Late-stage audit scope: build_testing / route_exam only.
- Global overclean remains a known underpressure signal in compact deterministic output; PR15 success is measured against calibrated actionable late-stage count.
- Selected tuning targets: repeated build_testing/route_exam overclean clusters from route+stage rollups.
- Changed knobs (simulation/reporting-only): targeted route-stage pressure overrides in mob scaling, preserving route identity.
- PR13 adds candidate rollups and targeted tuning knobs, but compact global overclean remains unresolved.
- Remaining known underpressure: compact deterministic route win rates may remain 1.00 and further targeted passes can still be required.
- No live gameplay/runtime systems changed.

## PR14 Target Expectation Calibration Summary
- Raw global overclean candidates: 87.
- Actionable overclean candidates after target calibration: 43.
- Early-stage target expectation artifacts: 44.
- Late-stage actionable overclean: 43.
- Raw/global signal remains visible for transparency; calibration adds actionable separation only.
- Early-stage artifacts are diagnostic target-expectation mismatches, not resolved balance issues.
- Late-stage actionable cases remain the tuning backlog.
- This pass is simulation/reporting-only and does not tune live gameplay/runtime systems.
| bucket | count | meaning |
|---|---:|---|
| raw_global_overclean | 87 | Raw strong_vs_high_target candidates across all stages. |
| early_stage_target_artifact | 44 | soft_entry/identity_visible high-target overclean artifacts. |
| actionable_overclean | 43 | Calibrated actionable overclean candidates. |
| late_stage_actionable | 43 | Actionable overclean in build_testing/route_exam. |

## PR15 Actionable Late-Stage Tuning Summary
- Previous PR14 actionable overclean baseline: 44.
- Current actionable overclean candidates: 43.
- Actionable overclean candidates after PR15: 43.
- Current early-stage target artifacts: 44.
- Early-stage target artifacts remain separated: 44.
- Current raw/global overclean candidates: 87.
- Raw/global overclean candidates still visible: 87.
- Improvement vs PR14 actionable baseline: yes.
- Changed knobs: bounded simulation/reporting-only late-stage route-stage pressure overrides plus one solo-matrix actionable role refinement for the repeated Sunscar route_exam support overclean cluster.
- Top remaining actionable clusters preview: 8 of 43; full list available in report_data.
- No live gameplay/runtime changes.
- No live gameplay/runtime systems were changed.
- New overpressure risk: route_sunscar / route_exam / pure_support_solo_overlay player_death observed in representative suspicious traces; PR15 is not presented as a clean/final balance pass.
| top_remaining_cluster_preview | count |
|---|---:|
| route_sunscar / build_testing | 8 |
| route_sunscar / route_exam | 7 |
| route_frostspine / build_testing | 6 |
| route_frostspine / route_exam | 6 |
| route_ashen_ruins / build_testing | 4 |
| route_ashen_ruins / route_exam | 4 |
| route_mireveil / build_testing | 2 |
| route_mireveil / route_exam | 2 |

## Balance V2 PR3 Controlled Late-Stage Mob Pressure Tuning Summary
- Previous PR2 mob_pressure_lane baseline: 43.
- Current mob_pressure_lane count: 34.
- Current route_expectation_lane count: 44.
- Current bad_matchup_review_lane count: 1.
- Classifier movement vs PR2 baseline: decreased.
- Current result explanation: classifier moved after semantic cleanup; mob_hp_too_low now uses turn-speed/clean-win pressure instead of mob_hp_removed_pct=1.00 alone.
- This pass is simulation/reporting-only and makes no final balance claim.
- No live gameplay/runtime systems, Combat Core behavior, global formulas, equipment budget formulas, live mob templates, rewards/economy/loot/crafting runtime, targeting, teleport, or live group combat were changed.
- Early-stage soft_entry / identity_visible target expectation artifacts remain separated and are not tuned as direct mob pressure backlog.
- Sunscar pure_support_solo_overlay route_exam remains treated as bad matchup review, not an automatic support buff or Sunscar nerf.

Changed PR3 knobs (multipliers above existing simulation/reporting rails):
- route_ashen_ruins / build_testing: accuracy +4%, damage +4%, hp +10%, magic_defense +6%.
- route_ashen_ruins / route_exam: accuracy +5%, damage +5%, hp +10%, magic_defense +6%.
- route_frostspine / build_testing: damage +3%, defense +6%, hp +10%, magic_defense +6%.
- route_frostspine / route_exam: damage +4%, defense +6%, hp +10%, magic_defense +6%.
- route_mireveil / build_testing: damage +2%, evasion +6%, hp +10%, magic_defense +3%.
- route_mireveil / route_exam: damage +3%, evasion +6%, hp +10%, magic_defense +4%.
- route_sunscar / build_testing: accuracy +3%, damage +3%, hp +6%.
- route_sunscar / route_exam: accuracy +2%, damage +2%, hp +3%.

Top remaining mob_pressure_lane clusters:
- route_stage_lane / route_sunscar / build_testing / mob_pressure_lane: 7
- route_stage_lane / route_sunscar / route_exam / mob_pressure_lane: 7
- route_stage_lane / route_frostspine / route_exam / mob_pressure_lane: 5
- archetype_lane / axe_2h_bruiser / mob_pressure_lane: 4

New overpressure/death risk summary:
- New overpressure/death risk: no broad new death wall observed; known bad-matchup signal remains route_sunscar / route_exam / pure_support_solo_overlay player_death.

## Balance V2 PR4 Expanded Sampling / Multi-seed Confidence Summary
This section is diagnostic-only and does not tune balance numbers. Compact PR3 counts remain the checked-in regression baseline; PR4 confidence data is used to guide future tuning scope.
No final balance claim is made. No live runtime, Combat Core behavior, global formulas, equipment budget formulas, live mob templates, rewards/economy/loot/crafting, targeting, teleport, or live group combat changes are made here.
Sunscar pure_support_solo_overlay route_exam overpressure remains separated as bad_matchup_review_lane, not an automatic support buff or Sunscar nerf.
No new tuning knobs were added.
- Seeds: 1, 2, 3.
- Compact PR3 lane counts: mob_pressure_lane=34, route_expectation_lane=44, bad_matchup_review_lane=1.
- Multi-seed lane counts: mob_pressure_lane=114, route_expectation_lane=132, bad_matchup_review_lane=3, inconclusive_lane=15.

Lane comparison table:
Multi-seed totals are raw totals across seeds; interpretation is normalized per seed.
PR4 confidence uses the active report scope. Checked-in v2 uses full compact alpha scope; scoped callers get scoped confidence diagnostics, not full-alpha totals.
| lane | compact PR3 | PR4 multi-seed total | expected total | per-seed avg | delta vs expected | interpretation |
|---|---:|---:|---:|---:|---:|---|
| bad_matchup_review_lane | 1 | 3 | 3 | 1.0 | 0 | stable_across_seeds |
| inconclusive_lane | 9 | 15 | 27 | 5.0 | -12 | lower_per_seed |
| mob_pressure_lane | 34 | 114 | 102 | 38.0 | 12 | slightly_higher_per_seed |
| route_expectation_lane | 44 | 132 | 132 | 44.0 | 0 | stable_across_seeds |

High-confidence remaining mob_pressure clusters preview:
| route | stage | lane | count | seeds_seen | seed_presence_rate | confidence |
|---|---|---|---:|---|---:|---|
| route_sunscar | build_testing | mob_pressure_lane | 23 | 1, 2, 3 | 1.0 | high |
| route_sunscar | route_exam | mob_pressure_lane | 21 | 1, 2, 3 | 1.0 | high |
| route_frostspine | route_exam | mob_pressure_lane | 17 | 1, 2, 3 | 1.0 | high |
| route_ashen_ruins | route_exam | mob_pressure_lane | 12 | 1, 2, 3 | 1.0 | high |
| route_frostspine | build_testing | mob_pressure_lane | 12 | 1, 2, 3 | 1.0 | high |
| route_ashen_ruins | build_testing | mob_pressure_lane | 7 | 1, 2, 3 | 1.0 | high |
| route_westwild | build_testing | mob_pressure_lane | 6 | 1, 2, 3 | 1.0 | high |
| route_westwild | route_exam | mob_pressure_lane | 6 | 1, 2, 3 | 1.0 | high |

Unstable/noisy clusters preview:
| route | stage | lane | count | seeds_seen | seed_presence_rate | confidence |
|---|---|---|---:|---|---:|---|
| route_frostspine | route_exam | inconclusive_lane | 1 | 1 | 0.333 | low |
| route_mireveil | build_testing | inconclusive_lane | 1 | 1 | 0.333 | low |
| route_mireveil | route_exam | inconclusive_lane | 1 | 1 | 0.333 | low |
| route_sunscar | build_testing | inconclusive_lane | 1 | 1 | 0.333 | low |

PR4 confidence notes:
- Diagnostic-only: PR4 does not tune balance numbers or replace compact PR3 regression counts.
- Compact PR3 lane counts remain authoritative for checked-in regression comparisons.
- PR4 confidence uses the active report scope; checked-in v2 uses full compact alpha scope, and scoped callers get scoped confidence diagnostics instead of full-alpha totals.
- Bounded multi-seed config: seeds=(1, 2, 3), max_samples_per_route_stage=1, include_raw_runs=True, include_turn_trace=False.
- No live runtime, Combat Core, formula, equipment budget, live mob template, economy/reward/loot/crafting, targeting, teleport, or live group combat changes are made by this report layer.

## Balance V2 PR5 Unified Combat Budget Audit
Diagnostic-only: this section performs no tuning and makes no final balance claim.
All gear states are included: undergeared, baseline_expected, enhanced_expected, optimized, and overgeared_high_enhancement.
PvE and PvP/proxy budget coverage is included; PvP is a clearly labeled pvp_budget_proxy, not real duel win rates.
No live gameplay/runtime/formula/equipment/live mob/economy/targeting/teleport/live group combat changes are made.
- Mode: compact_checked_in.
- Coverage: 14 archetypes, 6 level bands, 5 gear states, 420 audit rows.
- PvE budget summary source: progression_gear_budget_grid_plus_existing_pve_route_pressure_reconciliation.
- PvP/proxy budget coverage: pvp_budget_proxy; proxy_only=True; real_duel_win_rates=False.
- PvP equal-budget baseline gear states: baseline_expected, enhanced_expected, optimized.
- PvP gear-gap/stress states: undergeared, overgeared_high_enhancement.

Top systemic findings:
- simulation_policy_artifact: 270 audit rows
- skill_economy_risk: 210 audit rows
- pvp_only_toxicity: 156 audit rows
- secondary_stat_concentration_risk: 150 audit rows
- enhancement_scaling_risk: 84 audit rows

Recommended tuning order:
- 1. Review PR4 route-pressure reconciliation before tuning mobs or routes.
- 2. Review overgeared/enhancement stress rows separately from PvP baseline rows.
- 3. Review PvP proxy burst/stall toxicity before any live duel ruleset changes.
- 4. Only after diagnostic review, use separate future PRs for actual tuning proposals.

PR4 route pressure reconciliation:
- Route pressure is reconciled as scoped mob_pressure_lane evidence only; PR5 does not convert PR4 lanes into tuning changes.
- Compact PR4 lane counts referenced: {'bad_matchup_review_lane': 1, 'inconclusive_lane': 9, 'mob_pressure_lane': 34, 'route_expectation_lane': 44}.
- Top suspect player-side archetype evidence:
  - axe_2h_bruiser: mob_pressure_count=4; route_ashen_ruins/build_testing=1; route_ashen_ruins/route_exam=1; route_sunscar/build_testing=1
  - holy_staff_solo: mob_pressure_count=4; route_sunscar/build_testing=1; route_sunscar/route_exam=1; route_westwild/build_testing=1
  - magic_staff_destruction: mob_pressure_count=4; route_frostspine/build_testing=1; route_frostspine/route_exam=1; route_sunscar/build_testing=1
  - daggers_venom: mob_pressure_count=3; route_ashen_ruins/route_exam=1; route_frostspine/route_exam=1; route_sunscar/route_exam=1
  - pure_support_solo_overlay: mob_pressure_count=3; route_sunscar/build_testing=1; route_westwild/build_testing=1; route_westwild/route_exam=1
  - bow_ranger: mob_pressure_count=2; route_frostspine/build_testing=1; route_frostspine/route_exam=1

Notes:
- Balance V2 PR5 is diagnostic-only and applies no tuning.
- All current alpha archetypes, six level bands, and five gear states are included.
- PvP coverage is a clearly labeled budget proxy, not real headless duel win rates; equal-budget baseline uses baseline_expected, enhanced_expected, and optimized only.
- No live gameplay/runtime/formula/equipment/live mob/economy/targeting/teleport/live group combat changes are made.

## Balance V2 PR6 Simulation Policy & Skill Economy Clarification
Diagnostic-only: PR6 performs no live tuning and makes no final balance claim.
No live gameplay/runtime/formula/equipment/live mob/economy/targeting/teleport/live group combat changes are made.
PR6 separates simulation policy artifacts from real skill economy risks before any future tuning branch uses PR5 budget rows.
PvP remains proxy-only; route/mob/gear/PvP tuning remains deferred.
- Policy coverage rows: 14.
- Skill economy rows: 14.
- Artifact reason counts: {'missing_expected_rotation_profile': 8, 'metadata_only_policy': 9, 'burst_window_policy_review': 3, 'support_solo_policy_review': 3, 'sustain_timing_policy_unknown': 1}.
- Skill economy label counts: {'normal_attack_fallback_dominant': 6, 'skill_rotation_visible': 6, 'limited_skill_use_visible': 2}.
- Cooldown observability: cooldown-blocked turn counts are not safely available, so rows set cooldown_observability_available=False pending follow-up instrumentation.

Top policy gaps:
- tome_toolbox: policy=toolbox_balanced status=metadata_only reasons=metadata_only_policy, missing_expected_rotation_profile, support_solo_policy_review; missing_expected_skills=none.
- sword_2h_burst: policy=aggressive_burst status=metadata_only reasons=metadata_only_policy, missing_expected_rotation_profile, burst_window_policy_review; missing_expected_skills=none.
- pure_support_solo_overlay: policy=solo_support_sustain status=metadata_only reasons=metadata_only_policy, missing_expected_rotation_profile, support_solo_policy_review; missing_expected_skills=none.
- holy_staff_solo: policy=solo_support_sustain status=metadata_only reasons=metadata_only_policy, support_solo_policy_review, sustain_timing_policy_unknown; missing_expected_skills=none.
- magic_staff_destruction: policy=aggressive_burst status=metadata_only reasons=metadata_only_policy, burst_window_policy_review; missing_expected_skills=none.
- magic_staff_control: policy=control_caster status=metadata_only reasons=metadata_only_policy, missing_expected_rotation_profile; missing_expected_skills=none.

Recommended next tuning branch:
- Resolve simulation policy artifacts before treating PR5 rows as live skill-economy tuning evidence.
- Keep PvP in proxy-only budget review until a safe duel adapter exists.
- Defer route, mob, gear, and PvP tuning until PR6 diagnostics identify whether gaps are policy artifacts or real economy risks.

## Balance V2 PR7 Profile-aware Simulation Policy Execution Pilot
Diagnostic/simulation-only pilot: PR7 performs no live tuning and changes no live gameplay/runtime formulas, skill numbers, weapons, armor, gear, enhancement, mobs, routes, rewards/economy, PvP rules, targeting, teleport, or live group combat.
Pilot archetypes: daggers_venom, daggers_evasion, bow_sniper, magic_staff_destruction, holy_staff_solo.
Metadata-only registry policies were not globally flipped; pilot execution is resolved only by the simulation policy resolver.
PR6 policy coverage remains 14 rows and PR6 skill economy remains 14 rows.
PR5 audit remains 420 rows (expected 420).
PvP remains proxy-only; route/mob/gear/PvP tuning remains deferred.

## Balance V2 PR8 Simulation Action Resolution / Fallback Attribution
Diagnostic/simulation-only: PR8 adds action-resolution and fallback attribution observability without live tuning.
No live gameplay/runtime formulas, skill numbers, weapons, armor, gear, enhancement, mobs, routes, rewards/economy, PvP rules, targeting, teleport, cooldown reset behavior, reward behavior, or live group combat were changed.
Fallback reasons are now attributed for simulator policy requests that resolve to skill use, normal_attack fallback, or guard fallback.
Metadata-only registry policies remain not globally flipped; pilot execution remains resolver-scoped only.
PR6 remains 14/14 policy coverage / skill economy rows.
PR5 remains 420 audit rows (expected 420).
PvP remains proxy-only; route/mob/gear/PvP tuning remains deferred.

Top fallback reasons:
- skill_locked_or_unleveled: 154
- guard_fallback_action: 24
- insufficient_mana: 1

Action resolution counts:
- policy_chose_normal_attack: 443
- resolved_skill_success: 216
- skill_locked_or_unleveled: 154
- guard_fallback_action: 24
- insufficient_mana: 1

Pilot fallback summary:
| archetype | requested_skills | resolved_skill_success | normal_attack_fallback | top_fallback_reasons |
|---|---:|---:|---:|---|
| daggers_venom | 54 | 34 | 20 | skill_locked_or_unleveled:19, insufficient_mana:1 |
| daggers_evasion | 83 | 38 | 45 | skill_locked_or_unleveled:45 |
| bow_sniper | 76 | 34 | 42 | skill_locked_or_unleveled:42 |
| magic_staff_destruction | 32 | 20 | 12 | skill_locked_or_unleveled:12 |
| holy_staff_solo | 66 | 30 | 36 | skill_locked_or_unleveled:36 |

## Target vs Observed v2 Signals
This table shows a compact route-balanced suspicious preview, not the full target-vs-observed matrix.
Showing 40 route-balanced suspicious preview rows out of 88 suspicious candidates. Full target comparison data is available from build_alpha_balance_report_data(). Hidden rows are not resolved or dismissed.
| route | stage | archetype | target | observed_v1 | observed_diagnostic_label_v2 | reasons |
|---|---|---|---|---|---|---|
| route_ashen_ruins | build_testing | axe_2h_bruiser | hard | strong | strong_clean | strong_vs_high_target |
| route_frostspine | build_testing | bow_ranger | hard | strong | strong_clean | strong_vs_high_target |
| route_mireveil | build_testing | bow_sniper | hard | strong | strong_clean | strong_vs_high_target |
| route_sunscar | build_testing | axe_2h_bruiser | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_westwild | build_testing | holy_staff_solo | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_ashen_ruins | build_testing | bow_sniper | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_frostspine | build_testing | daggers_evasion | hard | strong | strong_clean | strong_vs_high_target |
| route_mireveil | build_testing | sword_2h_burst | hard | strong | strong_clean | strong_vs_high_target |
| route_sunscar | build_testing | daggers_venom | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_westwild | build_testing | pure_support_solo_overlay | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_ashen_ruins | build_testing | daggers_evasion | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_frostspine | build_testing | daggers_venom | normal_hard_split | strong | strong_clean | strong_vs_high_target |
| route_mireveil | identity_visible | bow_sniper | hard | strong | strong_clean | strong_vs_high_target |
| route_sunscar | build_testing | guardian_shield_1h | hard | strong | strong_clean | strong_vs_high_target |
| route_westwild | identity_visible | holy_staff_solo | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_ashen_ruins | build_testing | daggers_venom | very_hard | strong | strong_clean | strong_vs_high_target |
| route_frostspine | build_testing | magic_staff_control | hard | strong | strong_clean | strong_vs_high_target |
| route_mireveil | identity_visible | sword_2h_burst | hard | strong | strong_clean | strong_vs_high_target |
| route_sunscar | build_testing | holy_rod_paladin | hard | strong | strong_clean | strong_vs_high_target |
| route_westwild | identity_visible | pure_support_solo_overlay | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_ashen_ruins | identity_visible | axe_2h_bruiser | hard | strong | strong_clean | strong_vs_high_target |
| route_frostspine | build_testing | magic_staff_destruction | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_mireveil | route_exam | bow_sniper | hard | strong | strong_clean | strong_vs_high_target |
| route_sunscar | build_testing | holy_staff_solo | hard_very_hard | strong | strong_clean | strong_vs_high_target |
| route_westwild | route_exam | holy_staff_solo | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_ashen_ruins | identity_visible | bow_sniper | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_frostspine | build_testing | wand_tempo | hard | strong | strong_clean | strong_vs_high_target |
| route_mireveil | route_exam | sword_2h_burst | hard | strong | strong_clean | strong_vs_high_target |
| route_sunscar | build_testing | magic_staff_destruction | hard | strong | strong_clean | strong_vs_high_target |
| route_westwild | route_exam | pure_support_solo_overlay | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_ashen_ruins | identity_visible | daggers_evasion | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_frostspine | identity_visible | bow_ranger | hard | strong | strong_clean | strong_vs_high_target |
| route_mireveil | soft_entry | bow_sniper | hard | strong | strong_clean | strong_vs_high_target |
| route_sunscar | build_testing | pure_support_solo_overlay | very_hard_playable | strong | strong_clean | strong_vs_high_target |
| route_westwild | soft_entry | holy_staff_solo | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_ashen_ruins | identity_visible | daggers_venom | very_hard | strong | strong_clean | strong_vs_high_target |
| route_frostspine | identity_visible | daggers_evasion | hard | strong | strong_clean | strong_vs_high_target |
| route_mireveil | soft_entry | sword_2h_burst | hard | strong | strong_clean | strong_vs_high_target |
| route_sunscar | build_testing | tome_toolbox | normal_hard | strong | strong_clean | strong_vs_high_target |
| route_westwild | soft_entry | pure_support_solo_overlay | normal_hard | strong | strong_clean | strong_vs_high_target |

## Suspicious Clusters
Suspicious rows: 88.

## Progression Audit Preview
This section is diagnostic-only and not a tuning verdict.
Gear assumptions use formula_budget_v1 simulation presets where available.
policy_failure_guard_loop is a simulation policy artifact flag, not a direct route tuning verdict.
Flag counts:
- overclean_win: 42
| route | stage | archetype | lvl | gear | rarity | + | budget | profile | mob | role | encounter | scaled_hp | scaled_damage | target | observed_v2 | audit flags |
|---|---|---|---:|---|---|---:|---:|---|---|---|---:|---:|---:|---|---|---|
| route_westwild | soft_entry | guardian_shield_1h | 10 | T1 | common | +0 | 287 | tank | crow | normal | 10 | 25 | 4 | normal | strong_clean |  |
| route_westwild | soft_entry | sword_2h_burst | 10 | T1 | common | +0 | 287 | physical_dps | crow | normal | 10 | 25 | 4 | normal | strong_clean |  |
| route_westwild | soft_entry | axe_2h_bruiser | 10 | T1 | common | +0 | 287 | bruiser | crow | normal | 10 | 25 | 4 | strong | strong_clean |  |
| route_westwild | soft_entry | daggers_venom | 10 | T1 | common | +0 | 287 | evasion_dps | crow | normal | 10 | 25 | 4 | strong | strong_clean |  |
| route_westwild | soft_entry | daggers_evasion | 10 | T1 | common | +0 | 287 | evasion_dps | crow | normal | 10 | 25 | 4 | strong | strong_clean |  |
| route_westwild | soft_entry | bow_sniper | 10 | T1 | common | +0 | 287 | bow_dps | crow | normal | 10 | 25 | 4 | strong | strong_clean |  |
| route_westwild | soft_entry | bow_ranger | 10 | T1 | common | +0 | 287 | bow_dps | crow | normal | 10 | 25 | 4 | strong | strong_clean |  |
| route_westwild | soft_entry | magic_staff_destruction | 10 | T1 | common | +0 | 287 | magic_dps | crow | normal | 10 | 25 | 4 | normal | strong_clean |  |
| route_westwild | soft_entry | magic_staff_control | 10 | T1 | common | +0 | 287 | control_caster | crow | normal | 10 | 25 | 4 | normal | strong_clean |  |
| route_westwild | soft_entry | wand_tempo | 10 | T1 | common | +0 | 287 | magic_dps | crow | normal | 10 | 25 | 4 | normal | strong_clean |  |
| route_westwild | soft_entry | holy_staff_solo | 10 | T1 | common | +0 | 287 | healer_support | crow | normal | 10 | 25 | 4 | hard | strong_clean |  |
| route_westwild | soft_entry | holy_rod_paladin | 10 | T1 | common | +0 | 287 | paladin_hybrid | crow | normal | 10 | 25 | 4 | normal | strong_clean |  |
| route_westwild | soft_entry | tome_toolbox | 10 | T1 | common | +0 | 287 | toolbox_hybrid | crow | normal | 10 | 25 | 4 | normal | strong_clean |  |
| route_westwild | soft_entry | pure_support_solo_overlay | 10 | T1 | common | +0 | 287 | healer_support | crow | normal | 10 | 25 | 4 | hard | strong_clean |  |
| route_westwild | identity_visible | guardian_shield_1h | 35 | T4 | uncommon | +3 | 2040 | tank | forest_boar | normal | 35 | 166 | 12 | normal | strong_clean |  |
| route_westwild | identity_visible | sword_2h_burst | 35 | T4 | uncommon | +3 | 2040 | physical_dps | forest_boar | normal | 35 | 166 | 12 | normal | strong_clean |  |
| route_westwild | identity_visible | axe_2h_bruiser | 35 | T4 | uncommon | +3 | 2040 | bruiser | forest_boar | normal | 35 | 166 | 12 | strong | strong_clean |  |
| route_westwild | identity_visible | daggers_venom | 35 | T4 | uncommon | +3 | 2040 | evasion_dps | forest_boar | normal | 35 | 166 | 12 | strong | strong_clean |  |
| route_westwild | identity_visible | daggers_evasion | 35 | T4 | uncommon | +3 | 2040 | evasion_dps | forest_boar | normal | 35 | 166 | 12 | strong | strong_clean |  |
| route_westwild | identity_visible | bow_sniper | 35 | T4 | uncommon | +3 | 2040 | bow_dps | forest_boar | normal | 35 | 166 | 12 | strong | strong_clean |  |
Showing first 20 of 280 progression audit rows. Hidden rows are not resolved or dismissed.

## Pack / Group Simulation Preview
Showing 20 route-stage-balanced pack preview rows out of 140 pack runs. Hidden rows are not resolved or dismissed.
| route | stage | pack_id | archetype | members | composite_hp | composite_damage | observed_v2 | proxy_status | winner | turns | audit flags |
|---|---|---|---|---:|---:|---:|---|---|---|---:|---|
| route_ashen_ruins | build_testing | ashen_build_undead | axe_2h_bruiser | 3 | 1460 | 156 | strong_clean | composite_pack_pressure_v1 | player | 4 | none |
| route_ashen_ruins | route_exam | ashen_exam_knight_host | axe_2h_bruiser | 2 | 2182 | 261 | strong_clean | composite_pack_pressure_v1 | player | 3 | none |
| route_frostspine | build_testing | frost_build_wolves | axe_2h_bruiser | 3 | 1407 | 106 | strong_clean | composite_pack_pressure_v1 | player | 4 | none |
| route_frostspine | route_exam | frost_exam_golem_pack | axe_2h_bruiser | 3 | 4761 | 251 | strong_clean | composite_pack_pressure_v1 | player | 5 | none |
| route_mireveil | build_testing | mireveil_build_swarm | axe_2h_bruiser | 3 | 970 | 102 | strong_clean | composite_pack_pressure_v1 | player | 3 | none |
| route_mireveil | route_exam | mireveil_exam_serpent | axe_2h_bruiser | 3 | 1360 | 132 | strong_clean | composite_pack_pressure_v1 | player | 2 | none |
| route_sunscar | build_testing | sunscar_build_scorpion | axe_2h_bruiser | 3 | 1008 | 178 | strong_clean | composite_pack_pressure_v1 | player | 3 | none |
| route_sunscar | route_exam | sunscar_exam_apex | axe_2h_bruiser | 3 | 2719 | 334 | strong_clean | composite_pack_pressure_v1 | player | 4 | none |
| route_westwild | build_testing | westwild_build_wolf_boar | axe_2h_bruiser | 3 | 860 | 68 | strong_clean | composite_pack_pressure_v1 | player | 3 | none |
| route_westwild | route_exam | westwild_exam_bear_goblins | axe_2h_bruiser | 3 | 1728 | 150 | strong_clean | composite_pack_pressure_v1 | player | 3 | none |
| route_ashen_ruins | build_testing | ashen_build_undead | bow_ranger | 3 | 1460 | 156 | strong_clean | composite_pack_pressure_v1 | player | 4 | none |
| route_frostspine | build_testing | frost_build_wolves | bow_ranger | 3 | 1407 | 106 | strong_clean | composite_pack_pressure_v1 | player | 4 | none |
| route_mireveil | build_testing | mireveil_build_swarm | bow_ranger | 3 | 970 | 102 | strong_clean | composite_pack_pressure_v1 | player | 2 | none |
| route_sunscar | build_testing | sunscar_build_scorpion | bow_ranger | 3 | 1008 | 178 | strong_clean | composite_pack_pressure_v1 | player | 4 | none |
| route_westwild | build_testing | westwild_build_wolf_boar | bow_ranger | 3 | 860 | 68 | strong_clean | composite_pack_pressure_v1 | player | 2 | none |
| route_ashen_ruins | build_testing | ashen_build_undead | bow_sniper | 3 | 1460 | 156 | strong_clean | composite_pack_pressure_v1 | player | 3 | none |
| route_frostspine | build_testing | frost_build_wolves | bow_sniper | 3 | 1407 | 106 | strong_clean | composite_pack_pressure_v1 | player | 3 | none |
| route_mireveil | build_testing | mireveil_build_swarm | bow_sniper | 3 | 970 | 102 | strong_clean | composite_pack_pressure_v1 | player | 3 | none |
| route_sunscar | build_testing | sunscar_build_scorpion | bow_sniper | 3 | 1008 | 178 | strong_clean | composite_pack_pressure_v1 | player | 3 | none |
| route_westwild | build_testing | westwild_build_wolf_boar | bow_sniper | 3 | 860 | 68 | strong_clean | composite_pack_pressure_v1 | player | 3 | none |

## Balance Instrument V2 Observability Preview
Simulation/reporting-only preview with capped turn traces; this does not tune formulas, equipment budgets, live mob templates, rewards/economy, targeting, teleport, or live group combat.
Report modes available in code/report-data builders: compact_regression and expanded_balance.
Per-fight percentage metrics are 0..1 fractions.
Showing 8 capped representative observability rows out of 280 raw compact runs.
| route | stage | archetype | mob | winner | end_reason | turns | damage_dealt | damage_taken | player_hp_remaining_pct | player_mana_remaining_pct | action_sequence |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---|
| route_sunscar | route_exam | pure_support_solo_overlay | air_elemental | mob | player_death | 19 | 3816 | 2845 | 0.00 | 1.00 | skill:regeneration, normal_attack, normal_attack, normal_attack, normal_attack, normal_attack... |
| route_ashen_ruins | build_testing | guardian_shield_1h | cursed_knight | player | player_win | 7 | 950 | 95 | 0.98 | 1.00 | normal_attack, normal_attack, guard_fallback, normal_attack, normal_attack, guard_fallback... |
| route_ashen_ruins | route_exam | guardian_shield_1h | ghost | player | player_win | 2 | 595 | 0 | 1.00 | 1.00 | normal_attack, normal_attack |
| route_frostspine | build_testing | guardian_shield_1h | mountain_stone_golem | player | player_win | 11 | 1860 | 215 | 0.96 | 1.00 | normal_attack, normal_attack, guard_fallback, normal_attack, normal_attack, guard_fallback... |
| route_frostspine | route_exam | guardian_shield_1h | ice_troll | player | player_win | 8 | 2136 | 385 | 0.97 | 1.00 | normal_attack, normal_attack, guard_fallback, normal_attack, normal_attack, guard_fallback... |
| route_mireveil | build_testing | guardian_shield_1h | giant_leech | player | player_win | 7 | 644 | 157 | 0.97 | 1.00 | normal_attack, normal_attack, guard_fallback, normal_attack, normal_attack, guard_fallback... |
| route_mireveil | route_exam | guardian_shield_1h | old_witch | player | player_win | 7 | 1811 | 194 | 0.98 | 1.00 | normal_attack, normal_attack, guard_fallback, normal_attack, normal_attack, guard_fallback... |
| route_sunscar | build_testing | guardian_shield_1h | desert_elephant | player | player_win | 8 | 1264 | 172 | 0.97 | 1.00 | normal_attack, normal_attack, guard_fallback, normal_attack, normal_attack, guard_fallback... |

Capped turn trace preview (3 cases, max rows already capped by SimulationConfig.max_trace_turns):

Case 1: route_sunscar / route_exam / pure_support_solo_overlay vs air_elemental
| turn | action | player hp/mana before -> after | mob hp before -> after | log/event summary |
|---:|---|---|---|---|
| 1 | skill:regeneration | 2845/8497 -> 2631/8457 | 4355 -> 4355 | ♻️ Регенерация — ❤️+142/ход на 4 хода 🔵-40; 🩸 🌪️ Воздушный элементаль атакует — <b>214</b> урона. |
| 2 | normal_attack | 2631/8457 -> 2773/8457 | 4355 -> 4143 | ♻️ Реген восстанавливает 142 HP.; ⚔️ Ты наносишь <b>212</b> урона. |
| 3 | normal_attack | 2773/8457 -> 2631/8457 | 4143 -> 3931 | ♻️ Реген восстанавливает 72 HP.; ⚔️ Ты наносишь <b>212</b> урона. |
| 4 | normal_attack | 2631/8457 -> 2559/8457 | 3931 -> 3719 | ♻️ Реген восстанавливает 142 HP.; ⚔️ Ты наносишь <b>212</b> урона. |
| 5 | normal_attack | 2559/8457 -> 2487/8457 | 3719 -> 3507 | n/a |
| 6 | normal_attack | 2487/8457 -> 2273/8457 | 3507 -> 3295 | ⚔️ Ты наносишь <b>212</b> урона.; 🩸 🌪️ Воздушный элементаль атакует — <b>214</b> урона. |

Case 2: route_ashen_ruins / build_testing / guardian_shield_1h vs cursed_knight
| turn | action | player hp/mana before -> after | mob hp before -> after | log/event summary |
|---:|---|---|---|---|
| 1 | normal_attack | 5113/100 -> 5113/100 | 950 -> 737 | ⚔️ Ты наносишь <b>213</b> урона.; 🌀 Ты уклоняешься от атаки! |
| 2 | normal_attack | 5113/100 -> 5047/100 | 737 -> 524 | ⚔️ Ты наносишь <b>213</b> урона.; 🩸 🛡️ Проклятый рыцарь атакует — <b>66</b> урона. |
| 3 | guard_fallback | 5047/100 -> 5047/100 | 524 -> 524 | 🛡️ Ты входишь в защитную стойку (авто-защита).; 🌀 Ты уклоняешься от атаки! |
| 4 | normal_attack | 5047/100 -> 5018/100 | 524 -> 311 | ⚔️ Ты наносишь <b>213</b> урона.; 🩸 🛡️ Проклятый рыцарь атакует — <b>29</b> урона. |
| 5 | normal_attack | 5018/100 -> 5018/100 | 311 -> 98 | ⚔️ Ты наносишь <b>213</b> урона.; 🌀 Ты уклоняешься от атаки! |
| 6 | guard_fallback | 5018/100 -> 5018/100 | 98 -> 98 | 🛡️ Ты входишь в защитную стойку (авто-защита).; 🌀 Ты уклоняешься от атаки! |

Case 3: route_ashen_ruins / route_exam / guardian_shield_1h vs ghost
| turn | action | player hp/mana before -> after | mob hp before -> after | log/event summary |
|---:|---|---|---|---|
| 1 | normal_attack | 11269/130 -> 11269/130 | 595 -> 207 | ⚔️ Ты наносишь <b>388</b> урона.; 🌀 Ты уклоняешься от атаки! |
| 2 | normal_attack | 11269/130 -> 11269/130 | 207 -> 0 | ⚔️ Ты наносишь <b>388</b> урона. |

## Balance Instrument V2 Pressure Attribution Preview
Simulation/reporting-only diagnostic preview. Labels are diagnostic likely causes, not final balance verdicts, and do not directly tune formulas, equipment budgets, live mob templates, rewards/economy, targeting, teleport, or live group combat.
This classifier points future review toward tuning lanes; it does not claim final balance or prescribe automatic support buffs/Sunscar nerfs.

Attribution counts:
- mob_hp_too_low: 64
- player_damage_too_high: 64
- resource_pressure_missing: 57
- mob_damage_too_low: 46
- sample_too_soft: 44
- target_expectation_mismatch: 44
- inconclusive: 9
- player_sustain_too_high: 3
- bad_matchup_overpressure: 1

Recommended tuning lane counts:
- route_expectation_lane: 44
- mob_pressure_lane: 34
- inconclusive_lane: 9
- bad_matchup_review_lane: 1

Top attribution clusters:
- archetype_attribution / axe_2h_bruiser / mob_hp_too_low: 8
- archetype_attribution / axe_2h_bruiser / player_damage_too_high: 8
- archetype_attribution / axe_2h_bruiser / resource_pressure_missing: 8
- archetype_attribution / daggers_venom / mob_hp_too_low: 8
- archetype_attribution / daggers_venom / player_damage_too_high: 8
- archetype_attribution / holy_staff_solo / resource_pressure_missing: 8
- archetype_attribution / magic_staff_destruction / mob_hp_too_low: 8
- archetype_attribution / magic_staff_destruction / player_damage_too_high: 8
- archetype_attribution / magic_staff_destruction / resource_pressure_missing: 8
- route_stage_attribution / route_sunscar / identity_visible / mob_damage_too_low: 8
- route_stage_attribution / route_sunscar / identity_visible / resource_pressure_missing: 8
- route_stage_attribution / route_sunscar / identity_visible / sample_too_soft: 8

Top recommended lane clusters:
- route_stage_lane / route_sunscar / identity_visible / route_expectation_lane: 8
- route_stage_lane / route_sunscar / soft_entry / route_expectation_lane: 8
- route_stage_lane / route_sunscar / build_testing / mob_pressure_lane: 7
- route_stage_lane / route_sunscar / route_exam / mob_pressure_lane: 7
- archetype_lane / daggers_venom / route_expectation_lane: 6
- route_stage_lane / route_frostspine / identity_visible / route_expectation_lane: 6
- route_stage_lane / route_frostspine / soft_entry / route_expectation_lane: 6
- route_stage_lane / route_frostspine / route_exam / mob_pressure_lane: 5
- archetype_lane / axe_2h_bruiser / mob_pressure_lane: 4
- archetype_lane / axe_2h_bruiser / route_expectation_lane: 4
- archetype_lane / bow_sniper / route_expectation_lane: 4
- archetype_lane / daggers_evasion / route_expectation_lane: 4

Representative attribution rows (40 shown of 88):
| route | stage | archetype | mob | target | observed | winner | labels | recommended_lane | confidence | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| route_ashen_ruins | build_testing | axe_2h_bruiser | cursed_knight | hard | strong | player | mob_hp_too_low, player_damage_too_high, resource_pressure_missing | mob_pressure_lane | medium | turns=3, hp_left=0.98, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=72, role=pressure, lvl=70 |
| route_ashen_ruins | build_testing | bow_sniper | cursed_knight | normal_hard | strong | player | inconclusive | inconclusive_lane | low | turns=5, hp_left=0.89, mana_left=0.51, mob_hp_removed=1.00, dmg_taken=176, role=pressure, lvl=70 |
| route_ashen_ruins | build_testing | daggers_evasion | cursed_knight | normal_hard | strong | player | inconclusive | inconclusive_lane | low | turns=8, hp_left=0.97, mana_left=0.26, mob_hp_removed=1.00, dmg_taken=53, role=pressure, lvl=70 |
| route_ashen_ruins | build_testing | daggers_venom | cursed_knight | very_hard | strong | player | inconclusive | inconclusive_lane | low | turns=5, hp_left=0.96, mana_left=0.43, mob_hp_removed=1.00, dmg_taken=66, role=pressure, lvl=70 |
| route_ashen_ruins | identity_visible | axe_2h_bruiser | skeleton_mage | hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=1, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=normal, lvl=35 |
| route_ashen_ruins | identity_visible | bow_sniper | skeleton_mage | normal_hard | strong | player | mob_hp_too_low, player_damage_too_high, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=3, hp_left=0.90, mana_left=0.72, mob_hp_removed=1.00, dmg_taken=43, role=normal, lvl=35 |
| route_ashen_ruins | identity_visible | daggers_evasion | skeleton_mage | normal_hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=3, hp_left=0.96, mana_left=0.72, mob_hp_removed=1.00, dmg_taken=20, role=normal, lvl=35 |
| route_ashen_ruins | identity_visible | daggers_venom | skeleton_mage | very_hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=1, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=normal, lvl=35 |
| route_ashen_ruins | route_exam | axe_2h_bruiser | ghost | hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing | mob_pressure_lane | medium | turns=1, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=pressure, lvl=95 |
| route_ashen_ruins | route_exam | bow_sniper | ghost | normal_hard | strong | player | mob_hp_too_low, player_damage_too_high | mob_pressure_lane | medium | turns=4, hp_left=0.96, mana_left=0.61, mob_hp_removed=1.00, dmg_taken=124, role=pressure, lvl=95 |
| route_ashen_ruins | route_exam | daggers_evasion | ghost | normal_hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high | mob_pressure_lane | medium | turns=3, hp_left=1.00, mana_left=0.70, mob_hp_removed=1.00, dmg_taken=0, role=pressure, lvl=95 |
| route_ashen_ruins | route_exam | daggers_venom | ghost | very_hard | strong | player | mob_hp_too_low, player_damage_too_high | mob_pressure_lane | medium | turns=3, hp_left=0.98, mana_left=0.54, mob_hp_removed=1.00, dmg_taken=66, role=pressure, lvl=95 |
| route_ashen_ruins | soft_entry | axe_2h_bruiser | skeleton_warrior | hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=2, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=normal, lvl=10 |
| route_ashen_ruins | soft_entry | bow_sniper | skeleton_warrior | normal_hard | strong | player | sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=4, hp_left=0.76, mana_left=0.64, mob_hp_removed=1.00, dmg_taken=33, role=normal, lvl=10 |
| route_ashen_ruins | soft_entry | daggers_evasion | skeleton_warrior | normal_hard | strong | player | sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=4, hp_left=0.84, mana_left=0.64, mob_hp_removed=1.00, dmg_taken=21, role=normal, lvl=10 |
| route_ashen_ruins | soft_entry | daggers_venom | skeleton_warrior | very_hard | strong | player | sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=4, hp_left=0.84, mana_left=0.73, mob_hp_removed=1.00, dmg_taken=22, role=normal, lvl=10 |
| route_frostspine | build_testing | bow_ranger | mountain_stone_golem | hard | strong | player | resource_pressure_missing | mob_pressure_lane | low | turns=5, hp_left=0.97, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=44, role=pressure, lvl=70 |
| route_frostspine | build_testing | daggers_evasion | mountain_stone_golem | hard | strong | player | inconclusive | inconclusive_lane | low | turns=10, hp_left=0.92, mana_left=0.26, mob_hp_removed=1.00, dmg_taken=161, role=pressure, lvl=70 |
| route_frostspine | build_testing | daggers_venom | mountain_stone_golem | normal_hard_split | strong | player | inconclusive | inconclusive_lane | low | turns=8, hp_left=0.95, mana_left=0.05, mob_hp_removed=1.00, dmg_taken=100, role=pressure, lvl=70 |
| route_frostspine | build_testing | magic_staff_control | mountain_stone_golem | hard | strong | player | mob_hp_too_low, player_damage_too_high, resource_pressure_missing | mob_pressure_lane | medium | turns=4, hp_left=0.88, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=125, role=pressure, lvl=70 |
| route_frostspine | build_testing | magic_staff_destruction | mountain_stone_golem | normal_hard | strong | player | mob_hp_too_low, player_damage_too_high, resource_pressure_missing | mob_pressure_lane | medium | turns=4, hp_left=0.85, mana_left=0.99, mob_hp_removed=1.00, dmg_taken=193, role=pressure, lvl=70 |
| route_frostspine | build_testing | wand_tempo | mountain_stone_golem | hard | strong | player | mob_hp_too_low, player_damage_too_high, resource_pressure_missing | mob_pressure_lane | medium | turns=4, hp_left=0.89, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=143, role=pressure, lvl=70 |
| route_frostspine | identity_visible | bow_ranger | cave_bat | hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=1, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=normal, lvl=35 |
| route_frostspine | identity_visible | daggers_evasion | cave_bat | hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=3, hp_left=0.98, mana_left=0.72, mob_hp_removed=1.00, dmg_taken=8, role=normal, lvl=35 |
| route_frostspine | identity_visible | daggers_venom | cave_bat | normal_hard_split | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=1, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=normal, lvl=35 |
| route_frostspine | identity_visible | magic_staff_control | cave_bat | hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=1, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=normal, lvl=35 |
| route_frostspine | identity_visible | magic_staff_destruction | cave_bat | normal_hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=1, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=normal, lvl=35 |
| route_frostspine | identity_visible | wand_tempo | cave_bat | hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=1, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=normal, lvl=35 |
| route_frostspine | route_exam | bow_ranger | ice_troll | hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing | mob_pressure_lane | medium | turns=4, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=pressure, lvl=95 |
| route_frostspine | route_exam | daggers_evasion | ice_troll | hard | strong | player | inconclusive | inconclusive_lane | low | turns=8, hp_left=0.98, mana_left=0.40, mob_hp_removed=1.00, dmg_taken=93, role=pressure, lvl=95 |
| route_frostspine | route_exam | daggers_venom | ice_troll | normal_hard_split | strong | player | mob_hp_too_low, player_damage_too_high | mob_pressure_lane | medium | turns=5, hp_left=0.97, mana_left=0.54, mob_hp_removed=1.00, dmg_taken=103, role=pressure, lvl=95 |
| route_frostspine | route_exam | magic_staff_control | ice_troll | hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing | mob_pressure_lane | medium | turns=2, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=pressure, lvl=95 |
| route_frostspine | route_exam | magic_staff_destruction | ice_troll | normal_hard | strong | player | mob_hp_too_low, player_damage_too_high, resource_pressure_missing | mob_pressure_lane | medium | turns=2, hp_left=0.96, mana_left=0.99, mob_hp_removed=1.00, dmg_taken=104, role=pressure, lvl=95 |
| route_frostspine | route_exam | wand_tempo | ice_troll | hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing | mob_pressure_lane | medium | turns=2, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=pressure, lvl=95 |
| route_frostspine | soft_entry | bow_ranger | mountain_rabbit | hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=1, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=normal, lvl=10 |
| route_frostspine | soft_entry | daggers_evasion | mountain_rabbit | hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=3, hp_left=0.98, mana_left=0.64, mob_hp_removed=1.00, dmg_taken=3, role=normal, lvl=10 |
| route_frostspine | soft_entry | daggers_venom | mountain_rabbit | normal_hard_split | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=1, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=normal, lvl=10 |
| route_frostspine | soft_entry | magic_staff_control | mountain_rabbit | hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=1, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=normal, lvl=10 |
| route_frostspine | soft_entry | magic_staff_destruction | mountain_rabbit | normal_hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=1, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=normal, lvl=10 |
| route_frostspine | soft_entry | wand_tempo | mountain_rabbit | hard | strong | player | mob_damage_too_low, mob_hp_too_low, player_damage_too_high, resource_pressure_missing, sample_too_soft, target_expectation_mismatch | route_expectation_lane | medium | turns=1, hp_left=1.00, mana_left=1.00, mob_hp_removed=1.00, dmg_taken=0, role=normal, lvl=10 |

## Representative Suspicious Fight Traces
Showing up to 10 route-balanced representative suspicious traces. Hidden traces are not resolved or dismissed.
| route_id | stage | archetype_id | location_id | mob_id | winner | end_reason | turns | actions_used | skills_used |
|---|---|---|---|---|---|---|---:|---|---|
| route_sunscar | route_exam | pure_support_solo_overlay | sunscar_n10 | air_elemental | mob | player_death | 19 | {'normal_attack': 18, 'guard_fallback': 0, 'skill:regeneration': 1} | ['regeneration'] |

## Diagnostic Label Definitions
strong_clean, strong_but_risky, normal, hard, very_hard, death_blocked, timeout_stall, no_progress_stall, resource_collapse, policy_failure, inconclusive.

## Limitations
- Representative solo route-stage samples only.
- Pack proxy samples are added at report-data layer, not in solo matrix output.
- No live pack/group runtime combat.
- No final balance conclusions yet.
- No live route/mob/skill tuning performed.
- Simulation-stage pressure tuning is diagnostic/reporting-only.
- Alpha diagnostic signal only; not a final balance verdict.
- Observed-vs-target comparisons are coarse bands, not proof of tuning direction.
- Missing target metadata rows are treated as inconclusive, not mismatch verdicts.
- No full multi-target pack runtime combat; pack section uses composite_pack_pressure_v1 diagnostic proxy.

## Recommended Next Steps
- Use this report to scope targeted follow-up tuning PRs only.

## Raw Data Pointers
- Source module: `game.combat_simulation_matrix.run_route_stage_simulation_matrix`.
- Raw runs included in current report data object: True.
