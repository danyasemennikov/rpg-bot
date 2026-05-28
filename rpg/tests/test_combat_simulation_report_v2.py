from pathlib import Path

from game.combat_simulation_matrix import RouteStageMatrixConfig, run_route_stage_simulation_matrix
from game.combat_simulation_report import (
    PACK_PREVIEW_LIMIT,
    SUSPICIOUS_TABLE_LIMIT,
    TARGET_TABLE_LIMIT,
    _is_suspicious,
    build_alpha_balance_report_data,
    build_default_alpha_balance_report_data,
    build_default_alpha_simulation_report_v2_data,
    build_checked_in_alpha_simulation_report_v2_config,
    build_diagnostic_alpha_simulation_report_v2_config,
    _select_route_balanced_suspicious_preview,
    _enrich_run,
    _label_diagnostic_v2,
    _select_representative_suspicious_traces,
    _select_route_balanced_pack_preview,
    render_alpha_balance_report_markdown,
    render_alpha_simulation_report_v2_markdown,
)


def _cfg(stages=("soft_entry", "identity_visible")):
    return RouteStageMatrixConfig(
        route_ids=("route_westwild",),
        stages=stages,
        archetype_ids=("guardian_shield_1h", "holy_rod_paladin"),
        seeds=(1,),
        max_samples_per_route_stage=1,
        include_raw_runs=True,
    )


def test_v1_renderer_regression_guard():
    report = build_default_alpha_balance_report_data()
    md = render_alpha_balance_report_markdown(report)
    assert "Alpha Route/Class Balance Report v1" in md
    assert "Target vs Observed Matchup Signals" in md
    assert "Suspicious candidates by route" in md
    assert ("normal_strong" in md) or (" normal |" in md)
    if len(report["suspicious_matchups"]) > SUSPICIOUS_TABLE_LIMIT:
        assert "route-balanced preview rows" in md
    if len(report["target_comparisons"]) > TARGET_TABLE_LIMIT:
        assert "Showing first" in md
    assert "not a final balance verdict" in md.lower()


def test_scenario_cards_fields():
    report = build_alpha_balance_report_data(run_route_stage_simulation_matrix(_cfg()))
    card = report["scenario_cards"][0]
    for key in ("route_id", "stage", "location_id", "mob_id", "spawn_profile", "sample_tags"):
        assert key in card


def test_archetype_cards_per_stage_and_fields():
    report = build_alpha_balance_report_data(run_route_stage_simulation_matrix(_cfg(stages=("soft_entry", "build_testing"))))
    tiers = {c["power_tier"] for c in report["archetype_cards"]}
    assert "soft_entry" in tiers and "build_testing" in tiers
    assert len(tiers) > 1
    for card in report["archetype_cards"]:
        assert card["archetype_id"]
        assert "hp" in card and "mana" in card
        assert "skill_levels" in card
        assert "preferred_policy_id" in card
        assert "gear_budget_summary" in card
        assert card["gear_budget_summary"].get("budget_status") in {"formula_budget_v1", "formula_budget_v1_toolbox_fallback"}


def test_rich_run_metrics_present_and_raw_runs_enabled_for_v2_default():
    report = build_default_alpha_simulation_report_v2_data()
    assert report["runs"]
    assert report["scenario_cards"]
    run = report["runs"][0]
    for key in ("end_reason", "player_hp_remaining_pct", "mob_hp_remaining_pct", "guard_action_rate", "normal_attack_rate", "skill_use_rate", "no_progress"):
        assert key in run
    assert "progression_audit_rows" in report
    assert "progression_audit_flags" in report
    assert "progression_audit_flag_counts" in report
    assert "pack_runs" in report
    assert "pack_rollups" in report
    audit_row = report["progression_audit_rows"][0]
    assert "assumed_player_level" in audit_row
    assert "gear_tier" in audit_row
    assert "audit_flag_ids" in audit_row
    assert "simulation_gear_preset" in audit_row
    assert audit_row["gear_rarity_assumption"] != "pending_pr9"


def test_suspicious_logic_regression_guard():
    summary = {"observed_pressure_label": "strong", "timeouts": 0, "runs": 10, "death_rate": 0.1, "win_rate": 0.9}
    assert "strong_vs_high_target" in _is_suspicious(summary, "hard")
    summary_timeout = {"observed_pressure_label": "normal", "timeouts": 5, "runs": 10, "death_rate": 0.1, "win_rate": 0.7}
    assert "timeout_heavy" in _is_suspicious(summary_timeout, "normal")
    summary_death = {"observed_pressure_label": "very_hard", "timeouts": 0, "runs": 10, "death_rate": 0.7, "win_rate": 0.2}
    reasons = _is_suspicious(summary_death, "normal")
    assert "high_death_low_win" in reasons
    assert "very_hard_vs_low_target" in reasons


def test_markdown_v2_checked_in_has_real_content():
    path = Path(__file__).resolve().parents[1] / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Alpha Route/Class Balance Report v2" in content
    assert ("route_westwild" in content) or ("route_frostspine" in content)
    assert "spawn_profile" in content
    assert "sample_tags" in content
    assert "guardian_shield_1h" in content
    assert "power_tier" in content
    assert "skill levels" in content.lower()
    assert "policy" in content.lower()
    assert "hp" in content.lower() and "mana" in content.lower()
    assert "Representative Suspicious Fight Traces" in content
    assert "winner" in content and "end_reason" in content and "turns" in content
    assert ("actions_used" in content) or ("action usage" in content.lower())
    assert ("skills_used" in content) or ("skill usage" in content.lower())
    assert "Progression Audit Preview" in content
    assert "formula_budget_v1" in content
    assert "Representative solo samples only" not in content
    assert "No pack/group runtime simulation matrix yet" not in content
    assert "No pack/group runtime matrix in this report version" not in content
    assert "composite_pack_pressure_v1 pack proxy" in content


def test_v2_renderer_smoke():
    report = build_default_alpha_simulation_report_v2_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "Alpha Route/Class Balance Report v2" in md
    assert "Progression Audit Preview" in md
    assert "Pack / Group Simulation Preview" in md
    assert "composite_pack_pressure_v1" in md
    assert "No pack/group runtime matrix in this report version" not in md
    assert "composite_pack_pressure_v1 diagnostic proxy" in md
    assert "diagnostic-only and not a tuning verdict" in md


def test_solo_matrix_limitations_are_solo_truthful():
    matrix = run_route_stage_simulation_matrix(_cfg(stages=("soft_entry",)))
    limitations = matrix.get("limitations", [])
    joined = " ".join(limitations)
    assert "Representative solo route-stage samples only." in limitations
    assert "Pack proxy samples are added at report-data layer, not in solo matrix output." in limitations
    assert "composite_pack_pressure_v1 pack proxy samples" not in joined


def test_pack_preview_observed_and_proxy_semantics_and_route_coverage():
    report = build_default_alpha_simulation_report_v2_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "observed_v2 | proxy_status" in md
    assert "composite_pack_pressure_v1 | composite_pack_pressure_v1" not in md
    assert "route_westwild" in md
    assert "route_frostspine" in md
    assert "route_ashen_ruins" in md
    assert "route_mireveil" in md
    assert "route_sunscar" in md
    assert "build_testing" in md and "route_exam" in md
    assert len(report.get("pack_runs", [])) > PACK_PREVIEW_LIMIT
    assert f"Showing {PACK_PREVIEW_LIMIT} route-stage-balanced pack preview rows out of" in md


def test_route_stage_balanced_pack_preview_fills_to_limit():
    report = build_default_alpha_simulation_report_v2_data()
    preview = _select_route_balanced_pack_preview(report["pack_runs"], PACK_PREVIEW_LIMIT)
    assert len(preview) == PACK_PREVIEW_LIMIT
    routes = {r["route_id"] for r in preview}
    assert {"route_westwild", "route_frostspine", "route_ashen_ruins", "route_mireveil", "route_sunscar"}.issubset(routes)
    assert {"build_testing", "route_exam"}.issubset({r["stage"] for r in preview})


def test_custom_report_soft_entry_scope_has_no_pack_runs():
    matrix = run_route_stage_simulation_matrix(_cfg(stages=("soft_entry",)))
    report = build_alpha_balance_report_data(matrix)
    assert report.get("pack_runs", []) == []


def test_custom_report_build_testing_scope_has_only_build_testing_pack_rows():
    matrix = run_route_stage_simulation_matrix(_cfg(stages=("build_testing",)))
    report = build_alpha_balance_report_data(matrix)
    pack_runs = report.get("pack_runs", [])
    assert pack_runs
    assert {r.get("stage") for r in pack_runs} == {"build_testing"}


def test_v2_progression_audit_preview_hidden_row_disclosure_when_capped():
    report = build_default_alpha_simulation_report_v2_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    if len(report["progression_audit_rows"]) > 20:
        assert "Showing first 20 of" in md
        assert "progression audit rows. Hidden rows are not resolved or dismissed." in md


def test_v2_suspicious_preview_disclosure_and_transparency():
    report = build_default_alpha_simulation_report_v2_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "compact route-balanced suspicious preview" in md
    assert str(len(report["suspicious_matchups"])) in md
    assert "Hidden rows are not resolved or dismissed" in md


def test_v2_suspicious_preview_route_transparent_when_limit_allows():
    report = build_default_alpha_simulation_report_v2_data()
    rows = report["suspicious_matchups"]
    routes = {r["route_id"] for r in rows}
    preview = _select_route_balanced_suspicious_preview(rows, SUSPICIOUS_TABLE_LIMIT)
    preview_routes = {r["route_id"] for r in preview}
    if len(routes) <= SUSPICIOUS_TABLE_LIMIT and rows:
        assert routes.issubset(preview_routes)


def test_v2_trace_disclosure_and_multiroute_bias_guard():
    report = build_default_alpha_simulation_report_v2_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "Representative Suspicious Fight Traces" in md
    assert "route-balanced representative suspicious traces" in md
    assert str(10) in md
    routes = {r["route_id"] for r in report["suspicious_traces"]}
    if len(report["suspicious_traces"]) > 1:
        assert len(routes) > 1


def test_v2_config_helper_naming_and_values():
    checked = build_checked_in_alpha_simulation_report_v2_config()
    diag = build_diagnostic_alpha_simulation_report_v2_config()
    assert checked.include_raw_runs is True
    assert checked.max_samples_per_route_stage == 1
    assert checked.seeds == (1,)
    assert diag.seeds == (1, 2, 3)
    assert diag.max_samples_per_route_stage == 2
    assert diag.include_raw_runs is True


def test_guard_fallback_counts_as_guard_like_action_rate():
    run = {
        "route_id": "route_westwild",
        "stage": "soft_entry",
        "archetype_id": "guardian_shield_1h",
        "location_id": "westwild_n1",
        "mob_id": "forest_wolf",
        "spawn_profile": "normal",
        "sample_tags": ["representative"],
        "winner": "mob",
        "turns": 50,
        "terminated_by_max_turns": True,
        "player_dead": False,
        "mob_dead": False,
        "player_hp_remaining": 100,
        "player_mana_remaining": 50,
        "mob_hp_remaining": 100,
        "damage_dealt": 0,
        "damage_taken": 10,
        "actions_used": {"guard_fallback": 50, "normal_attack": 0},
        "skills_used": [],
    }
    enriched = _enrich_run(run)
    assert enriched["guard_action_rate"] >= 0.9
    assert enriched["normal_attack_rate"] == 0
    assert enriched["skill_use_rate"] == 0


def test_policy_failure_label_from_guard_loop_summary():
    summary = {
        "runs": 10,
        "guard_action_rate": 0.95,
        "no_progress_rate": 0.8,
        "win_rate": 0.0,
        "death_rate": 0.0,
        "timeout_alive_stall_rate": 1.0,
    }
    assert _label_diagnostic_v2(summary) == "policy_failure"


def test_actual_report_guard_fallback_policy_failure_signal_present():
    report = build_default_alpha_simulation_report_v2_data()
    traces = [
        t
        for t in report["suspicious_traces"]
        if t["archetype_id"] in {"guardian_shield_1h", "holy_rod_paladin"}
        and t.get("actions_used", {}).get("guard_fallback", 0) >= 40
    ]
    if traces:
        assert any(t.get("observed_diagnostic_label_v2") == "policy_failure" for t in traces)


def test_checked_in_report_mentions_policy_failure_when_guard_fallback_traces_present():
    path = Path(__file__).resolve().parents[1] / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md"
    content = path.read_text(encoding="utf-8")
    if "guard_fallback" in content:
        assert "policy_failure" in content


def test_representative_trace_selection_is_route_first():
    rows = [
        {"route_id": "route_a", "observed_diagnostic_label_v2": "policy_failure", "stage": "s1", "archetype_id": "a1", "location_id": "l1", "mob_id": "m1"},
        {"route_id": "route_a", "observed_diagnostic_label_v2": "death_blocked", "stage": "s1", "archetype_id": "a1", "location_id": "l2", "mob_id": "m2"},
        {"route_id": "route_a", "observed_diagnostic_label_v2": "timeout_stall", "stage": "s1", "archetype_id": "a1", "location_id": "l3", "mob_id": "m3"},
        {"route_id": "route_b", "observed_diagnostic_label_v2": "policy_failure", "stage": "s1", "archetype_id": "a1", "location_id": "l1", "mob_id": "m1"},
        {"route_id": "route_b", "observed_diagnostic_label_v2": "death_blocked", "stage": "s1", "archetype_id": "a1", "location_id": "l2", "mob_id": "m2"},
        {"route_id": "route_b", "observed_diagnostic_label_v2": "timeout_stall", "stage": "s1", "archetype_id": "a1", "location_id": "l3", "mob_id": "m3"},
        {"route_id": "route_c", "observed_diagnostic_label_v2": "policy_failure", "stage": "s1", "archetype_id": "a1", "location_id": "l1", "mob_id": "m1"},
        {"route_id": "route_d", "observed_diagnostic_label_v2": "policy_failure", "stage": "s1", "archetype_id": "a1", "location_id": "l1", "mob_id": "m1"},
        {"route_id": "route_e", "observed_diagnostic_label_v2": "policy_failure", "stage": "s1", "archetype_id": "a1", "location_id": "l1", "mob_id": "m1"},
    ]
    limit = 6
    selected_a = _select_representative_suspicious_traces(rows, limit)
    selected_b = _select_representative_suspicious_traces(rows, limit)
    assert len(selected_a) <= limit
    assert selected_a == selected_b
    routes = {r["route_id"] for r in selected_a}
    assert {"route_a", "route_b", "route_c", "route_d", "route_e"}.issubset(routes)


def test_progression_rows_use_archetype_specific_profiles():
    report = build_default_alpha_simulation_report_v2_data()
    rows = report["progression_audit_rows"]

    def find_row(arch, stage):
        return next(r for r in rows if r["archetype_id"] == arch and r["stage"] == stage)

    g = find_row("guardian_shield_1h", "route_exam")
    b = find_row("bow_sniper", "build_testing")
    h = find_row("holy_staff_solo", "identity_visible")
    assert g["simulation_gear_preset"]["profile_id"] == "tank"
    assert b["simulation_gear_preset"]["profile_id"] == "bow_dps"
    assert h["simulation_gear_preset"]["profile_id"] == "healer_support"


def test_progression_rows_not_all_toolbox_fallback():
    report = build_default_alpha_simulation_report_v2_data()
    profiles = {r.get("simulation_gear_preset", {}).get("profile_id") for r in report["progression_audit_rows"]}
    assert profiles != {"toolbox_hybrid"}


def test_build_and_exam_rows_include_escalated_roles_when_targets_hard():
    report = build_default_alpha_simulation_report_v2_data()
    rows = report["progression_audit_rows"]
    scoped = [r for r in rows if r.get("stage") in {"build_testing", "route_exam"}]
    assert scoped
    assert any(str(r.get("mob_role")) in {"pressure", "elite"} for r in scoped)


def test_valid_formula_budget_rows_not_all_flagged_missing_preset():
    report = build_default_alpha_simulation_report_v2_data()
    valid_rows = [r for r in report["progression_audit_rows"] if r.get("assumption_status") == "formula_budget_v1"]
    assert valid_rows
    assert any("missing_simulation_gear_preset" not in r.get("audit_flag_ids", []) for r in valid_rows)


def test_progression_rows_include_mob_scaling_context_and_stats():
    report = build_default_alpha_simulation_report_v2_data()
    rows = report["progression_audit_rows"]
    assert rows
    assert all(r.get("encounter_level") is not None for r in rows)
    assert all(r.get("mob_role") for r in rows)
    assert all(r.get("scaling_status") == "formula_mob_scaling_v1" for r in rows)
    exam_normals = [r for r in rows if r.get("stage") == "route_exam" and r.get("mob_role") == "normal"]
    assert exam_normals
    assert any((r.get("final_mob_stats", {}).get("hp", 0) > r.get("base_mob_stats", {}).get("hp", 0)) for r in exam_normals)


def test_progression_flag_counts_no_global_missing_encounter_or_mob_role():
    report = build_default_alpha_simulation_report_v2_data()
    counts = report.get("progression_audit_flag_counts", {})
    assert counts.get("missing_encounter_level", 0) == 0
    assert counts.get("missing_mob_role", 0) == 0


def test_v2_markdown_contains_scaled_mob_context():
    report = build_default_alpha_simulation_report_v2_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "formula_mob_scaling_v1" in md
    assert "| route | stage | archetype | lvl | gear | rarity | + | budget | profile | mob | role | encounter | scaled_hp | scaled_damage | target | observed_v2 | audit flags |" in md


def test_v2_markdown_has_no_known_broken_separator_strings():
    report = build_default_alpha_simulation_report_v2_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "| route | stage | archetype | target | observed_v1 | observed_diagnostic_label_v2 | reasons |\n|---|---|---|---|---|---:|---|---|---|---|" not in md
    assert "| route_id | stage | archetype_id | location_id | mob_id | winner | end_reason | turns | actions_used | skills_used |\n|---|---|---|---|---|---:|---|---|---|---|---:|---|---|" not in md


def test_enrich_run_uses_final_scaled_hp_for_diagnostics():
    run = {
        "route_id": "route_westwild",
        "stage": "route_exam",
        "archetype_id": "guardian_shield_1h",
        "location_id": "westwild_n10",
        "mob_id": "bear",
        "winner": "mob",
        "terminated_by_max_turns": False,
        "player_dead": True,
        "mob_dead": False,
        "player_hp_remaining": 0,
        "player_mana_remaining": 20,
        "mob_hp_remaining": 500,
        "damage_dealt": 60,
        "actions_used": {"normal_attack": 10},
        "skills_used": [],
        "final_mob_stats": {"hp": 659, "damage": 65},
        "base_mob_stats": {"hp": 95},
    }
    enriched = _enrich_run(run)
    assert enriched["mob_hp_remaining_pct"] == 500 / 659
    assert enriched["no_progress"] is True
    assert enriched["mob_hp_max_source"] == "final_mob_stats"


def test_enrich_run_legacy_fallback_to_template_hp():
    run = {
        "route_id": "route_westwild",
        "stage": "soft_entry",
        "archetype_id": "guardian_shield_1h",
        "location_id": "westwild_n1",
        "mob_id": "bear",
        "winner": "mob",
        "terminated_by_max_turns": False,
        "player_dead": True,
        "mob_dead": False,
        "player_hp_remaining": 0,
        "player_mana_remaining": 0,
        "mob_hp_remaining": 95,
        "damage_dealt": 5,
        "actions_used": {"normal_attack": 1},
        "skills_used": [],
    }
    enriched = _enrich_run(run)
    assert enriched["mob_hp_max_source"] == "mobs_template"
    assert enriched["mob_hp_remaining_pct"] is not None


def test_default_report_runs_have_sane_mob_hp_remaining_pct_bound():
    report = build_default_alpha_simulation_report_v2_data()
    values = [r.get("mob_hp_remaining_pct") for r in report.get("runs", []) if isinstance(r.get("mob_hp_remaining_pct"), (int, float))]
    assert values
    assert all(v <= 1.05 for v in values)
