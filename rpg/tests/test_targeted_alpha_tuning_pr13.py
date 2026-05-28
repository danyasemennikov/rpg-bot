from pathlib import Path

from game.combat_simulation_report import build_default_alpha_simulation_report_v2_data, render_alpha_simulation_report_v2_markdown


def test_pr13_sections_and_rollups_exist():
    report = build_default_alpha_simulation_report_v2_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "## PR13 Targeted Tuning Candidates" in md
    assert "## PR13 Targeted Alpha Tuning Summary" in md
    assert "overclean_rollups" not in md  # internal key, not raw dump
    assert "overclean_rollups" in str(report.keys())
    assert "overclean_top_clusters" in report
    assert "global_overclean_candidate_count" in report
    assert "late_stage_overclean_candidate_count" in report


def test_top_clusters_non_empty_when_overclean_exists():
    report = build_default_alpha_simulation_report_v2_data()
    count = int(report.get("progression_audit_flag_counts", {}).get("overclean_win", 0))
    top = list(report.get("overclean_top_clusters", []))
    if count > 0:
        assert top


def test_checked_in_report_pr13_baseline_and_scope_wording():
    content = (Path(__file__).resolve().parents[1] / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md").read_text(encoding="utf-8")
    assert "Previous PR12 global overclean baseline: 86." in content
    assert "No route/mob/skill/reward/formula tuning." not in content
    assert "No live route/mob/skill/reward/formula tuning." in content
    assert "Current global overclean candidates:" in content
    assert "Current late-stage overclean audit flags:" in content
    assert "Late-stage audit scope: build_testing / route_exam only." in content
    assert "Global overclean did not improve yet" in content
    assert "86 -> 43" not in content
    assert "overclean improved vs baseline: yes" not in content
    assert "policy_failure_guard_loop count: 0" in content
    assert "Pack / Group Simulation Preview" in content
    assert "| n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 | {} | [] |" not in content


def test_global_vs_late_stage_counts_and_candidate_section_consistency():
    report = build_default_alpha_simulation_report_v2_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    global_count = int(report.get("global_overclean_candidate_count", 0))
    late_stage_count = int(report.get("late_stage_overclean_candidate_count", 0))
    assert global_count >= late_stage_count
    assert f"global overclean candidates (strong_vs_high_target): {global_count}." in md
    assert f"late-stage targeted candidates (build_testing/route_exam only): {late_stage_count}." in md
    assert "selected targeted clusters are limited to build_testing / route_exam" in md


def test_soft_entry_not_selected_targeted_and_route_identity_documented():
    report = build_default_alpha_simulation_report_v2_data()
    rollups = report.get("overclean_rollups", {})
    by_stage = {tuple(x.get("key", []))[0]: x.get("count", 0) for x in rollups.get("by_stage", []) if x.get("key")}
    assert by_stage.get("soft_entry", 0) <= by_stage.get("build_testing", 0)
    content = (Path(__file__).resolve().parents[1] / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md").read_text(encoding="utf-8")
    assert "targeted route-stage pressure overrides" in content
    assert "soft_entry/identity_visible rows shown here are global diagnostics only." in content
