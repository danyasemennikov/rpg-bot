import re
from pathlib import Path

from game.combat_simulation_report import (
    build_default_alpha_balance_report_data,
    build_default_alpha_simulation_report_v2_data,
    render_alpha_balance_report_markdown,
    render_alpha_simulation_report_v2_markdown,
)
from game.mob_scaling import PR3_LATE_STAGE_MOB_PRESSURE_REFINEMENTS

DOCS_ROOT = Path(__file__).resolve().parents[1] / "docs"
REPORT_PATH = DOCS_ROOT / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md"
STATE_PATH = DOCS_ROOT / "PROJECT_STATE_CURRENT.md"
FOUNDATION_PATH = DOCS_ROOT / "BALANCE_FOUNDATION_ALPHA_TO_RELEASE.md"


def _section(content: str, heading: str, next_heading: str | None = None) -> str:
    start = content.find(heading)
    assert start != -1
    if next_heading is None:
        return content[start:]
    end = content.find(next_heading, start + len(heading))
    assert end != -1
    return content[start:end]


def test_pr3_v1_renderer_does_not_fake_zero_count_success_when_raw_runs_absent():
    report = build_default_alpha_balance_report_data()
    assert report.get("raw_data_pointers", {}).get("raw_runs_included") is False
    assert report.get("pressure_attribution_available") is False

    md = render_alpha_balance_report_markdown(report)
    section = _section(md, "## Balance V2 PR3 Controlled Late-Stage Mob Pressure Tuning Summary", "Suspicious candidates by route:")
    assert "Current mob_pressure_lane count: 0." not in section
    assert "Classifier movement vs PR2 baseline: decreased." not in section
    assert "unavailable" in section
    assert "raw runs are not included" in section


def test_pr3_v2_renderer_reports_authoritative_counts_when_raw_runs_available():
    report = build_default_alpha_simulation_report_v2_data()
    assert report.get("pressure_attribution_available") is True

    md = render_alpha_simulation_report_v2_markdown(report)
    section = _section(md, "## Balance V2 PR3 Controlled Late-Stage Mob Pressure Tuning Summary", "## Target vs Observed v2 Signals")
    assert "Previous PR2 mob_pressure_lane baseline: 43." in section
    assert "Current mob_pressure_lane count: 41." in section
    assert "Current route_expectation_lane count: 44." in section
    assert "Current bad_matchup_review_lane count: 1." in section
    assert "Classifier movement vs PR2 baseline: decreased." in section


def test_pr3_report_section_checked_in_and_rendered_non_final():
    report = build_default_alpha_simulation_report_v2_data()
    rendered = render_alpha_simulation_report_v2_markdown(report)
    checked_in = REPORT_PATH.read_text(encoding="utf-8")
    for content in (rendered, checked_in):
        assert "## Balance V2 PR3 Controlled Late-Stage Mob Pressure Tuning Summary" in content
        section = _section(content, "## Balance V2 PR3 Controlled Late-Stage Mob Pressure Tuning Summary", "## Target vs Observed v2 Signals")
        assert "simulation/reporting-only" in section
        assert "no final balance claim" in section
        assert "No live gameplay/runtime systems" in section


def test_pr3_lane_preservation_and_sunscar_bad_matchup_visibility():
    report = build_default_alpha_simulation_report_v2_data()
    assert report.get("pressure_attribution_available") is True
    assert "pressure_attribution_rows" in report
    assert "recommended_lane_counts" in report
    counts = report["recommended_lane_counts"]
    assert counts.get("route_expectation_lane", 0) > 0
    assert counts.get("mob_pressure_lane", 0) > 0
    assert counts.get("bad_matchup_review_lane", 0) > 0
    assert any(
        row.get("route_id") == "route_sunscar"
        and row.get("stage") == "route_exam"
        and row.get("archetype_id") == "pure_support_solo_overlay"
        and row.get("recommended_lane") == "bad_matchup_review_lane"
        for row in report["pressure_attribution_rows"]
    )


def test_pr3_tuning_effect_baseline_current_count_and_not_zero():
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert "Previous PR2 mob_pressure_lane baseline: 43." in content
    match = re.search(r"Current mob_pressure_lane count: (\d+)\.", content)
    assert match is not None
    current = int(match.group(1))
    assert current <= 43
    assert current > 0
    assert "mob_hp_too_low now uses turn-speed/clean-win pressure instead of mob_hp_removed_pct=1.00 alone" in content
    assert "Classifier movement vs PR2 baseline: decreased." in content


def test_pr3_early_stage_artifacts_stay_separated_from_tuning_backlog():
    report = build_default_alpha_simulation_report_v2_data()
    assert report.get("early_stage_target_artifact_count", 0) > 0
    content = REPORT_PATH.read_text(encoding="utf-8")
    section = _section(content, "## Balance V2 PR3 Controlled Late-Stage Mob Pressure Tuning Summary", "## Target vs Observed v2 Signals")
    assert "soft_entry / identity_visible target expectation artifacts remain separated" in section
    assert "not tuned as direct mob pressure backlog" in section
    assert all(stage in {"build_testing", "route_exam"} for _, stage in PR3_LATE_STAGE_MOB_PRESSURE_REFINEMENTS)


def test_pr3_sunscar_pure_support_death_visible_without_auto_buff_or_nerf_claim():
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert "route_sunscar / route_exam / pure_support_solo_overlay player_death" in content
    lowered = content.lower()
    assert "automatic support buff" in lowered
    assert "sunscar nerf" in lowered
    assert "buffing support" not in lowered
    assert "nerfing sunscar" not in lowered


def test_pr3_no_broad_new_death_wall_outside_known_bad_matchup():
    report = build_default_alpha_simulation_report_v2_data()
    death_rows = [
        row
        for row in report.get("pressure_attribution_rows", [])
        if row.get("winner") == "mob" or row.get("end_reason") == "player_death"
    ]
    outside_known = [
        row
        for row in death_rows
        if not (
            row.get("route_id") == "route_sunscar"
            and row.get("stage") == "route_exam"
            and row.get("archetype_id") == "pure_support_solo_overlay"
        )
    ]
    assert len(death_rows) <= 2
    assert not outside_known
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert "no broad new death wall observed" in content


def test_pr3_report_continuity_sections_remain_present():
    content = REPORT_PATH.read_text(encoding="utf-8")
    required = [
        "## PR12 First Tuning Pass Summary",
        "## PR13 Targeted Tuning Candidates",
        "## PR13 Targeted Alpha Tuning Summary",
        "## PR14 Target Expectation Calibration Summary",
        "## PR15 Actionable Late-Stage Tuning Summary",
        "## Balance Instrument V2 Observability Preview",
        "## Balance Instrument V2 Pressure Attribution Preview",
    ]
    for heading in required:
        assert heading in content


def test_pr3_docs_state_header_foundation_note_and_non_goals():
    state = STATE_PATH.read_text(encoding="utf-8")
    foundation = FOUNDATION_PATH.read_text(encoding="utf-8")
    header = state.split("---", 1)[0]
    assert "PR: Balance V2 PR4: Expanded Sampling / Multi-seed Confidence Pass" in header
    assert "Status: simulation/reporting multi-seed balance confidence diagnostics" in header
    assert "### Balance V2 PR3: Controlled Late-Stage Mob Pressure Tuning Pass" in state
    assert "controlled simulation/reporting-only late-stage mob pressure tuning was applied" in state
    assert "current mob_pressure_lane count after PR3 classifier cleanup is 41" in state
    assert "route_expectation_lane count is 44" in state
    assert "bad_matchup_review_lane count is 1" in state
    assert "PR3 moved the classifier after semantic cleanup" in state
    assert "no formula/equipment/live mob/economy/targeting/teleport/live group combat changes were made" in state
    assert "## Balance V2 PR3 Controlled Late-Stage Mob Pressure Tuning Pass Note" in foundation
    assert "Does not tune route expectation artifacts" in foundation
    assert "Does not automatically fix Sunscar pure support bad matchup" in foundation
    assert "Does not claim final balance" in foundation
