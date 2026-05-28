from pathlib import Path

from game.combat_simulation_report import build_default_alpha_simulation_report_v2_data, render_alpha_simulation_report_v2_markdown


def test_pr14_report_data_keys_and_bounds():
    report = build_default_alpha_simulation_report_v2_data()
    assert "actionable_overclean_candidate_count" in report
    assert "early_stage_target_artifact_count" in report
    assert "target_calibration_rollups" in report
    assert "global_overclean_candidate_count" in report
    assert int(report["actionable_overclean_candidate_count"]) <= int(report["global_overclean_candidate_count"])


def test_pr14_early_stage_vs_late_stage_actionable_semantics():
    report = build_default_alpha_simulation_report_v2_data()
    rows = list(report.get("target_comparisons", []))
    early = [
        r for r in rows
        if r.get("stage") in {"soft_entry", "identity_visible"}
        and r.get("normalized_target_label") in {"hard", "very_hard"}
        and r.get("observed_label") == "strong"
    ]
    assert early
    assert all(r.get("target_calibration_status") == "early_stage_target_expectation_artifact" for r in early)
    assert all(not r.get("is_actionable_overclean") for r in early)

    late = [
        r for r in rows
        if r.get("stage") in {"build_testing", "route_exam"}
        and r.get("normalized_target_label") in {"hard", "very_hard"}
        and r.get("observed_label") == "strong"
    ]
    assert late
    assert all(r.get("is_actionable_overclean") for r in late)


def test_pr14_markdown_and_project_state_updates_exist_and_honest():
    report = build_default_alpha_simulation_report_v2_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "## PR14 Target Expectation Calibration Summary" in md
    assert "simulation/reporting-only" in md
    assert "## PR13 Targeted Tuning Candidates" in md

    report_doc = (Path(__file__).resolve().parents[1] / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md").read_text(encoding="utf-8")
    assert "## PR14 Target Expectation Calibration Summary" in report_doc
    assert "global overclean remains unresolved" in report_doc.lower()
    assert "Pack / Group Simulation Preview" in report_doc
    assert "policy_failure_guard_loop count: 0" in report_doc

    state_doc = (Path(__file__).resolve().parents[1] / "docs" / "PROJECT_STATE_CURRENT.md").read_text(encoding="utf-8")
    assert "PR14: Target Expectation Calibration Pass" in state_doc
    assert "Target Expectation Calibration Pass (PR14)" in state_doc
    header = state_doc.split("---", 1)[0]
    assert "after PR14 target expectation calibration" in header
    assert "after PR13 targeted pass" not in header


def test_pr13_late_stage_clusters_scope_preserved():
    report = build_default_alpha_simulation_report_v2_data()
    for cluster in report.get("late_stage_targeted_top_clusters", []):
        key = list(cluster.get("key", []))
        assert len(key) >= 2
        assert key[1] in {"build_testing", "route_exam"}
