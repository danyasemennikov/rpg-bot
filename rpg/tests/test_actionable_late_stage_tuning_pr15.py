import re
from pathlib import Path

from game.combat_simulation_report import build_default_alpha_simulation_report_v2_data, render_alpha_simulation_report_v2_markdown
from game.combat_simulation_matrix import PR15_ACTIONABLE_ROLE_REFINEMENTS
from game.mob_scaling import TARGETED_ROUTE_STAGE_PRESSURE_OVERRIDES

DOCS_ROOT = Path(__file__).resolve().parents[1] / "docs"
REPORT_PATH = DOCS_ROOT / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md"
STATE_PATH = DOCS_ROOT / "PROJECT_STATE_CURRENT.md"


def _section(content: str, heading: str, next_heading: str | None = None) -> str:
    start = content.find(heading)
    assert start != -1
    if next_heading is None:
        return content[start:]
    end = content.find(next_heading, start + len(heading))
    assert end != -1
    return content[start:end]


def test_pr15_section_exists_and_report_data_contains_actionable_count():
    report = build_default_alpha_simulation_report_v2_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "actionable_overclean_candidate_count" in report
    assert "## PR15 Actionable Late-Stage Tuning Summary" in md


def test_checked_in_report_pr15_baseline_and_improvement_counts():
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert "Previous PR14 actionable overclean baseline: 44." in content
    match = re.search(r"Current actionable overclean candidates: (\d+)\.", content)
    assert match is not None
    assert int(match.group(1)) < 44
    assert "Improvement vs PR14 actionable baseline: yes." in content


def test_early_artifact_and_raw_global_signals_remain_visible():
    report = build_default_alpha_simulation_report_v2_data()
    assert "early_stage_target_artifact_count" in report
    assert int(report["early_stage_target_artifact_count"]) > 0
    assert "global_overclean_candidate_count" in report
    assert int(report["global_overclean_candidate_count"]) >= int(report["actionable_overclean_candidate_count"])

    content = REPORT_PATH.read_text(encoding="utf-8")
    assert "Current early-stage target artifacts:" in content
    assert "Current raw/global overclean candidates:" in content
    assert "early_stage_target_artifact" in content
    assert "raw_global_overclean" in content


def test_pr14_and_pr13_sections_remain_present_and_pr13_table_scope_is_late_stage_only():
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert "## PR14 Target Expectation Calibration Summary" in content
    assert "## PR13 Targeted Tuning Candidates" in content
    section = _section(content, "## PR13 Targeted Tuning Candidates", "## PR13 Targeted Alpha Tuning Summary")
    assert "soft_entry" not in section
    assert "identity_visible" not in section
    assert "build_testing" in section or "route_exam" in section


def test_policy_guard_loop_zero_and_pack_proxy_present():
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert "policy_failure_guard_loop count: 0" in content
    assert "## Pack / Group Simulation Preview" in content
    assert "composite_pack_pressure_v1" in content


def test_pr15_tuning_is_bounded_and_pack_proxy_not_doubled():
    sunscar_exam = TARGETED_ROUTE_STAGE_PRESSURE_OVERRIDES[("route_sunscar", "route_exam")]
    assert sunscar_exam["hp"] <= 1.35
    assert sunscar_exam["damage"] <= 1.30
    assert sunscar_exam["accuracy"] <= 1.12

    report = build_default_alpha_simulation_report_v2_data()
    sunscar_exam_pack_hp = [
        run.get("final_pack_stats", {}).get("hp", 0)
        for run in report.get("pack_runs", [])
        if run.get("route_id") == "route_sunscar" and run.get("stage") == "route_exam"
    ]
    assert sunscar_exam_pack_hp
    assert max(sunscar_exam_pack_hp) < 3000


def test_pr15_overpressure_risk_is_documented_without_holy_staff_regression():
    report = build_default_alpha_simulation_report_v2_data()
    traces = list(report.get("suspicious_traces", []))
    assert not any(
        trace.get("route_id") == "route_sunscar"
        and trace.get("stage") == "route_exam"
        and trace.get("archetype_id") == "holy_staff_solo"
        and trace.get("end_reason") == "player_death"
        for trace in traces
    )
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert "Top remaining actionable clusters preview:" in content
    if any(trace.get("end_reason") == "player_death" for trace in traces):
        assert "New overpressure risk:" in content
        assert "not presented as a clean/final balance pass" in content


def test_pr15_solo_role_refinement_is_not_pack_pressure():
    assert ("route_sunscar", "route_exam", "pure_support_solo_overlay") in PR15_ACTIONABLE_ROLE_REFINEMENTS
    assert "full list available in report_data" in REPORT_PATH.read_text(encoding="utf-8")


def test_project_state_pr15_header_section_and_no_stale_pr14_header():
    content = STATE_PATH.read_text(encoding="utf-8")
    header = content.split("---", 1)[0]
    assert "PR: PR15: Actionable Late-Stage Underpressure Tuning Pass" in header
    assert "Status: simulation/reporting actionable late-stage tuning" in header
    assert "PR: PR14: Target Expectation Calibration Pass" not in header
    assert "### Actionable Late-Stage Underpressure Tuning Pass (PR15)" in content
    assert "actionable overclean baseline from PR14 was 44" in content
    assert "current checked-in compact report shows raw/global overclean candidates: 87" in content
    assert "current actionable overclean after PR15 is 43" in content
    assert "early-stage target artifacts remain 44" in content
    assert "route_sunscar / route_exam / pure_support_solo_overlay player_death" in content
    assert "PR15 is not a final/clean balance pass" in content


def test_project_state_pr13_uses_historical_baseline_wording():
    content = STATE_PATH.read_text(encoding="utf-8")
    section = _section(content, "### Targeted Alpha Tuning Pass (PR13)", "### First Real Tuning Pass (PR12)")
    assert "current checked-in compact report shows global overclean candidates remain 88" not in section
    assert "at PR13 time" in section
    assert "compact report baseline showed global overclean candidates 88" in section
    assert "late-stage targeted overclean audit flags 43" in section
    assert "later PR14/PR15 report current calibrated/current counts" in section


def test_no_live_or_non_goal_wording_regression():
    content = REPORT_PATH.read_text(encoding="utf-8") + "\n" + STATE_PATH.read_text(encoding="utf-8")
    required_phrases = [
        "No live gameplay/runtime changes.",
        "No Combat Core rewrite.",
        "No live pack/group runtime combat.",
        "no live gameplay/runtime systems were changed",
    ]
    for phrase in required_phrases:
        assert phrase in content
