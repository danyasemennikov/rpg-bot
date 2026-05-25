# Alpha Route/Class Balance Report v1

## 1. Summary
This is an alpha diagnostic report using representative solo route-stage samples.
It is a signal artifact for future targeted tuning PRs and is not a final balance verdict.

## 2. Methodology
- Matrix source: route × stage × archetype deterministic simulation summaries.
- Routes: route_westwild, route_frostspine, route_ashen_ruins, route_mireveil, route_sunscar
- Stages: soft_entry, identity_visible, build_testing, route_exam
- Archetypes: 14
- Total samples: 20 | total runs: 280

## 3. Scope and Non-goals
- No route/mob/skill/reward/formula tuning is performed in this report.
- No live PvE/PvP behavior changes are introduced.
- No pack/group runtime matrix yet.
- No live AFK/autopilot or smart autobattle behavior.

## 4. Matrix Configuration
- Config is deterministic and representative (solo route-native samples).

## 5. Route Overview
| Route | Runs | Win Rate | Timeout Rate |
|---|---:|---:|---:|
| route_ashen_ruins | 56 | 0.86 | 0.04 |
| route_frostspine | 56 | 0.86 | 0.07 |
| route_mireveil | 56 | 0.86 | 0.00 |
| route_sunscar | 56 | 0.86 | 0.05 |
| route_westwild | 56 | 0.86 | 0.14 |

## 6. Archetype Overview
| Archetype | Runs | Win Rate | Timeout Rate |
|---|---:|---:|---:|
| axe_2h_bruiser | 20 | 1.00 | 0.00 |
| bow_ranger | 20 | 1.00 | 0.00 |
| bow_sniper | 20 | 1.00 | 0.00 |
| daggers_evasion | 20 | 1.00 | 0.00 |
| daggers_venom | 20 | 1.00 | 0.00 |
| guardian_shield_1h | 20 | 0.00 | 0.40 |
| holy_rod_paladin | 20 | 0.00 | 0.45 |
| holy_staff_solo | 20 | 1.00 | 0.00 |
| magic_staff_control | 20 | 1.00 | 0.00 |
| magic_staff_destruction | 20 | 1.00 | 0.00 |
| pure_support_solo_overlay | 20 | 1.00 | 0.00 |
| sword_2h_burst | 20 | 1.00 | 0.00 |
| tome_toolbox | 20 | 1.00 | 0.00 |
| wand_tempo | 20 | 1.00 | 0.00 |

## 7. Target vs Observed Matchup Signals
Alignment counts:
- aligned: 84
- slightly_easier_than_target: 76
- easier_than_target: 80
- slightly_harder_than_target: 0
- harder_than_target: 0
- critical_mismatch: 40
- inconclusive: 0
Showing first 60 of 280 target comparison rows. Full comparison data is available from build_alpha_balance_report_data().
This table is compact and should not be treated as complete raw output.
| Route | Stage | Archetype | Target | Observed | Alignment |
|---|---|---|---|---|---|
| route_westwild | soft_entry | guardian_shield_1h | normal | dead_or_blocked | critical_mismatch |
| route_westwild | soft_entry | sword_2h_burst | normal_strong | strong | slightly_easier_than_target |
| route_westwild | soft_entry | axe_2h_bruiser | strong | strong | aligned |
| route_westwild | soft_entry | daggers_venom | strong | strong | aligned |
| route_westwild | soft_entry | daggers_evasion | strong | strong | aligned |
| route_westwild | soft_entry | bow_sniper | strong | strong | aligned |
| route_westwild | soft_entry | bow_ranger | strong | strong | aligned |
| route_westwild | soft_entry | magic_staff_destruction | normal_strong | strong | slightly_easier_than_target |
| route_westwild | soft_entry | magic_staff_control | normal | strong | slightly_easier_than_target |
| route_westwild | soft_entry | wand_tempo | normal | strong | slightly_easier_than_target |
| route_westwild | soft_entry | holy_staff_solo | normal_hard | strong | easier_than_target |
| route_westwild | soft_entry | holy_rod_paladin | normal | dead_or_blocked | critical_mismatch |
| route_westwild | soft_entry | tome_toolbox | normal | strong | slightly_easier_than_target |
| route_westwild | soft_entry | pure_support_solo_overlay | normal_hard | strong | easier_than_target |
| route_westwild | identity_visible | guardian_shield_1h | normal | dead_or_blocked | critical_mismatch |
| route_westwild | identity_visible | sword_2h_burst | normal_strong | strong | slightly_easier_than_target |
| route_westwild | identity_visible | axe_2h_bruiser | strong | strong | aligned |
| route_westwild | identity_visible | daggers_venom | strong | strong | aligned |
| route_westwild | identity_visible | daggers_evasion | strong | strong | aligned |
| route_westwild | identity_visible | bow_sniper | strong | strong | aligned |
| route_westwild | identity_visible | bow_ranger | strong | strong | aligned |
| route_westwild | identity_visible | magic_staff_destruction | normal_strong | strong | slightly_easier_than_target |
| route_westwild | identity_visible | magic_staff_control | normal | strong | slightly_easier_than_target |
| route_westwild | identity_visible | wand_tempo | normal | strong | slightly_easier_than_target |
| route_westwild | identity_visible | holy_staff_solo | normal_hard | strong | easier_than_target |
| route_westwild | identity_visible | holy_rod_paladin | normal | dead_or_blocked | critical_mismatch |
| route_westwild | identity_visible | tome_toolbox | normal | strong | slightly_easier_than_target |
| route_westwild | identity_visible | pure_support_solo_overlay | normal_hard | strong | easier_than_target |
| route_westwild | build_testing | guardian_shield_1h | normal | dead_or_blocked | critical_mismatch |
| route_westwild | build_testing | sword_2h_burst | normal_strong | strong | slightly_easier_than_target |
| route_westwild | build_testing | axe_2h_bruiser | strong | strong | aligned |
| route_westwild | build_testing | daggers_venom | strong | strong | aligned |
| route_westwild | build_testing | daggers_evasion | strong | strong | aligned |
| route_westwild | build_testing | bow_sniper | strong | strong | aligned |
| route_westwild | build_testing | bow_ranger | strong | strong | aligned |
| route_westwild | build_testing | magic_staff_destruction | normal_strong | strong | slightly_easier_than_target |
| route_westwild | build_testing | magic_staff_control | normal | strong | slightly_easier_than_target |
| route_westwild | build_testing | wand_tempo | normal | strong | slightly_easier_than_target |
| route_westwild | build_testing | holy_staff_solo | normal_hard | strong | easier_than_target |
| route_westwild | build_testing | holy_rod_paladin | normal | dead_or_blocked | critical_mismatch |
| route_westwild | build_testing | tome_toolbox | normal | strong | slightly_easier_than_target |
| route_westwild | build_testing | pure_support_solo_overlay | normal_hard | strong | easier_than_target |
| route_westwild | route_exam | guardian_shield_1h | normal | dead_or_blocked | critical_mismatch |
| route_westwild | route_exam | sword_2h_burst | normal_strong | strong | slightly_easier_than_target |
| route_westwild | route_exam | axe_2h_bruiser | strong | strong | aligned |
| route_westwild | route_exam | daggers_venom | strong | strong | aligned |
| route_westwild | route_exam | daggers_evasion | strong | strong | aligned |
| route_westwild | route_exam | bow_sniper | strong | strong | aligned |
| route_westwild | route_exam | bow_ranger | strong | strong | aligned |
| route_westwild | route_exam | magic_staff_destruction | normal_strong | strong | slightly_easier_than_target |
| route_westwild | route_exam | magic_staff_control | normal | strong | slightly_easier_than_target |
| route_westwild | route_exam | wand_tempo | normal | strong | slightly_easier_than_target |
| route_westwild | route_exam | holy_staff_solo | normal_hard | strong | easier_than_target |
| route_westwild | route_exam | holy_rod_paladin | normal | dead_or_blocked | critical_mismatch |
| route_westwild | route_exam | tome_toolbox | normal | strong | slightly_easier_than_target |
| route_westwild | route_exam | pure_support_solo_overlay | normal_hard | strong | easier_than_target |
| route_frostspine | soft_entry | guardian_shield_1h | strong | dead_or_blocked | critical_mismatch |
| route_frostspine | soft_entry | sword_2h_burst | strong | strong | aligned |
| route_frostspine | soft_entry | axe_2h_bruiser | strong | strong | aligned |
| route_frostspine | soft_entry | daggers_venom | normal_hard_split | strong | easier_than_target |

## 8. Suspicious Matchup Candidates
Suspicious candidates by route:
- route_ashen_ruins: 24
- route_frostspine: 32
- route_mireveil: 16
- route_sunscar: 32
- route_westwild: 16
Showing 40 route-balanced preview rows out of 120 suspicious candidates. Full suspicious candidate data is available from build_alpha_balance_report_data().
Hidden rows are not resolved or dismissed; this is a compact route-balanced preview only.
| Route | Stage | Archetype | Observed | Target | Reasons |
|---|---|---|---|---|---|
| route_ashen_ruins | build_testing | axe_2h_bruiser | strong | hard | strong_vs_high_target |
| route_frostspine | build_testing | bow_ranger | strong | hard | strong_vs_high_target |
| route_mireveil | build_testing | bow_sniper | strong | hard | strong_vs_high_target |
| route_sunscar | build_testing | axe_2h_bruiser | strong | normal_hard | strong_vs_high_target |
| route_westwild | build_testing | guardian_shield_1h | dead_or_blocked | normal | dead_or_blocked_above_target, timeout_heavy |
| route_ashen_ruins | build_testing | bow_sniper | strong | normal_hard | strong_vs_high_target |
| route_frostspine | build_testing | daggers_evasion | strong | hard | strong_vs_high_target |
| route_mireveil | build_testing | guardian_shield_1h | dead_or_blocked | normal_strong | dead_or_blocked_above_target, high_death_low_win |
| route_sunscar | build_testing | daggers_venom | strong | normal_hard | strong_vs_high_target |
| route_westwild | build_testing | holy_rod_paladin | dead_or_blocked | normal | dead_or_blocked_above_target, timeout_heavy |
| route_ashen_ruins | build_testing | daggers_evasion | strong | normal_hard | strong_vs_high_target |
| route_frostspine | build_testing | daggers_venom | strong | normal_hard_split | strong_vs_high_target |
| route_mireveil | build_testing | holy_rod_paladin | dead_or_blocked | normal_strong | dead_or_blocked_above_target, high_death_low_win |
| route_sunscar | build_testing | guardian_shield_1h | dead_or_blocked | hard | dead_or_blocked_above_target, high_death_low_win |
| route_westwild | build_testing | holy_staff_solo | strong | normal_hard | strong_vs_high_target |
| route_ashen_ruins | build_testing | daggers_venom | strong | very_hard | strong_vs_high_target |
| route_frostspine | build_testing | guardian_shield_1h | dead_or_blocked | strong | dead_or_blocked_above_target, high_death_low_win |
| route_mireveil | build_testing | sword_2h_burst | strong | hard | strong_vs_high_target |
| route_sunscar | build_testing | holy_rod_paladin | dead_or_blocked | hard | dead_or_blocked_above_target, high_death_low_win |
| route_westwild | build_testing | pure_support_solo_overlay | strong | normal_hard | strong_vs_high_target |
| route_ashen_ruins | build_testing | guardian_shield_1h | dead_or_blocked | normal | dead_or_blocked_above_target, high_death_low_win |
| route_frostspine | build_testing | holy_rod_paladin | dead_or_blocked | strong | dead_or_blocked_above_target, high_death_low_win |
| route_mireveil | identity_visible | bow_sniper | strong | hard | strong_vs_high_target |
| route_sunscar | build_testing | holy_staff_solo | strong | hard_very_hard | strong_vs_high_target |
| route_westwild | identity_visible | guardian_shield_1h | dead_or_blocked | normal | dead_or_blocked_above_target, timeout_heavy |
| route_ashen_ruins | build_testing | holy_rod_paladin | dead_or_blocked | strong | dead_or_blocked_above_target, high_death_low_win |
| route_frostspine | build_testing | magic_staff_control | strong | hard | strong_vs_high_target |
| route_mireveil | identity_visible | guardian_shield_1h | dead_or_blocked | normal_strong | dead_or_blocked_above_target, high_death_low_win |
| route_sunscar | build_testing | magic_staff_destruction | strong | hard | strong_vs_high_target |
| route_westwild | identity_visible | holy_rod_paladin | dead_or_blocked | normal | dead_or_blocked_above_target, timeout_heavy |
| route_ashen_ruins | identity_visible | axe_2h_bruiser | strong | hard | strong_vs_high_target |
| route_frostspine | build_testing | magic_staff_destruction | strong | normal_hard | strong_vs_high_target |
| route_mireveil | identity_visible | holy_rod_paladin | dead_or_blocked | normal_strong | dead_or_blocked_above_target, high_death_low_win |
| route_sunscar | build_testing | pure_support_solo_overlay | strong | very_hard_playable | strong_vs_high_target |
| route_westwild | identity_visible | holy_staff_solo | strong | normal_hard | strong_vs_high_target |
| route_ashen_ruins | identity_visible | bow_sniper | strong | normal_hard | strong_vs_high_target |
| route_frostspine | build_testing | wand_tempo | strong | hard | strong_vs_high_target |
| route_mireveil | identity_visible | sword_2h_burst | strong | hard | strong_vs_high_target |
| route_sunscar | build_testing | tome_toolbox | strong | normal_hard | strong_vs_high_target |
| route_westwild | identity_visible | pure_support_solo_overlay | strong | normal_hard | strong_vs_high_target |

## 9. Route Notes
- Route notes should be used as directional investigation signals, not final conclusions.

## 10. Archetype Notes
- Archetype notes should guide follow-up targeted testing and tuning PR scope only.

## 11. Limitations
- Representative solo samples only (route-stage mob snapshots).
- No pack/group runtime simulation matrix yet.
- No final balance conclusions yet.
- No route/mob/skill tuning performed.
- Alpha diagnostic signal only; not a final balance verdict.
- Observed-vs-target comparisons are coarse bands, not proof of tuning direction.
- Missing target metadata rows are treated as inconclusive, not mismatch verdicts.
- No pack/group runtime matrix in this report version.

## 12. Recommended Next Steps
- Add pack/group simulation matrix before final balance decisions.
- Increase seed/sample breadth for suspicious candidates.
- Use targeted follow-up PRs for any actual tuning decisions.

## 13. Raw Data Pointers
- Source module: `game.combat_simulation_matrix.run_route_stage_simulation_matrix`.
- Raw runs included in current report data object: False.

_Report generation config: seeds=(1,), max_samples_per_route_stage=1, max_turns=50, include_raw_runs=False._
