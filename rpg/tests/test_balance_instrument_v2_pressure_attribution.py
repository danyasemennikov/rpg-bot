from pathlib import Path

from game.combat_simulation_report import (
    build_default_alpha_simulation_report_v2_data,
    render_alpha_simulation_report_v2_markdown,
)

DOCS_ROOT = Path(__file__).resolve().parents[1] / "docs"
REPORT_PATH = DOCS_ROOT / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md"
STATE_PATH = DOCS_ROOT / "PROJECT_STATE_CURRENT.md"
FOUNDATION_PATH = DOCS_ROOT / "BALANCE_FOUNDATION_ALPHA_TO_RELEASE.md"


def test_pressure_attribution_report_data_shape():
    report = build_default_alpha_simulation_report_v2_data()
    for key in (
        "pressure_attribution_rows",
        "pressure_attribution_counts",
        "recommended_lane_counts",
        "pressure_attribution_top_clusters",
        "recommended_lane_top_clusters",
    ):
        assert key in report
    assert isinstance(report["pressure_attribution_rows"], list)
    assert isinstance(report["pressure_attribution_counts"], dict)
    assert isinstance(report["recommended_lane_counts"], dict)


def test_pressure_attribution_rows_have_labels_lane_confidence_and_compact_evidence():
    report = build_default_alpha_simulation_report_v2_data()
    rows = report["pressure_attribution_rows"]
    assert rows
    assert any(row.get("attribution_labels") for row in rows)

    required_evidence = {
        "turns",
        "damage_dealt",
        "damage_taken",
        "player_hp_remaining_pct",
        "player_mana_remaining_pct",
        "mob_hp_removed_pct",
        "sample_tags",
        "mob_role",
        "encounter_level",
    }
    for row in rows:
        assert row.get("recommended_lane")
        assert row.get("confidence") in {"low", "medium", "high"}
        assert row.get("attribution_labels")
        assert required_evidence.issubset(set(row.get("evidence", {})))
        assert "turn_trace" not in row["evidence"]


def test_late_stage_pressure_role_overclean_not_all_sample_selection_lane():
    report = build_default_alpha_simulation_report_v2_data()
    pressure_rows = [
        row
        for row in report["pressure_attribution_rows"]
        if row["stage"] in {"build_testing", "route_exam"}
        and row.get("observed_label") == "strong"
        and row.get("winner") == "player"
        and row.get("evidence", {}).get("mob_role") == "pressure"
    ]
    assert pressure_rows
    assert any(row["recommended_lane"] in {"mob_pressure_lane", "encounter_level_lane"} for row in pressure_rows)
    assert not all(row["recommended_lane"] == "sample_selection_lane" for row in pressure_rows)


def test_pressure_role_normal_spawn_does_not_drive_sample_too_soft_primary_lane():
    report = build_default_alpha_simulation_report_v2_data()
    pressure_rows = [
        row
        for row in report["pressure_attribution_rows"]
        if row["stage"] in {"build_testing", "route_exam"}
        and row.get("evidence", {}).get("mob_role") == "pressure"
        and "normal_spawn" in row.get("evidence", {}).get("sample_tags", [])
        and row.get("observed_label") == "strong"
    ]
    assert pressure_rows
    for row in pressure_rows:
        assert "sample_too_soft" not in row["attribution_labels"]
        assert row["recommended_lane"] != "sample_selection_lane"


def test_early_stage_target_artifacts_are_not_direct_mob_pressure_only():
    report = build_default_alpha_simulation_report_v2_data()
    artifact_rows = [
        row
        for row in report["pressure_attribution_rows"]
        if row["stage"] in {"soft_entry", "identity_visible"}
        and row.get("observed_label") == "strong"
        and row.get("target_label") in {"hard", "very_hard", "normal_hard", "normal_hard_split", "hard_very_hard"}
    ]
    assert artifact_rows
    for row in artifact_rows:
        labels = set(row["attribution_labels"])
        assert labels & {"target_expectation_mismatch", "sample_too_soft"}
        assert not (row["recommended_lane"] == "mob_pressure_lane" and labels == {"mob_hp_too_low"})


def test_sunscar_pure_support_overpressure_is_bad_matchup_not_prescriptive():
    report = build_default_alpha_simulation_report_v2_data()
    rows = [
        row
        for row in report["pressure_attribution_rows"]
        if row["route_id"] == "route_sunscar"
        and row["stage"] == "route_exam"
        and row["archetype_id"] == "pure_support_solo_overlay"
        and row["end_reason"] == "player_death"
    ]
    assert rows
    assert any(
        "bad_matchup_overpressure" in row["attribution_labels"]
        or row["recommended_lane"] == "bad_matchup_review_lane"
        for row in rows
    )

    md = render_alpha_simulation_report_v2_markdown(report).lower()
    assert "buffing support" not in md
    assert "nerfing sunscar" not in md
    assert "automatic support buffs/sunscar nerfs" in md


def test_pressure_attribution_markdown_section_is_readable_and_not_giant_json():
    report = build_default_alpha_simulation_report_v2_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "## Balance Instrument V2 Pressure Attribution Preview" in md
    assert "Attribution counts:" in md
    assert "Recommended tuning lane counts:" in md
    assert "diagnostic likely causes, not final balance verdicts" in md
    assert "turn_trace" not in md.split("## Balance Instrument V2 Pressure Attribution Preview", 1)[1].split("## Representative Suspicious Fight Traces", 1)[0]
    assert "{\"" not in md


def test_checked_in_report_keeps_pr15_diagnostic_values_visible():
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert "Current raw/global overclean candidates: 87." in content
    assert "Actionable overclean candidates after PR15: 43." in content
    assert "Current early-stage target artifacts: 44." in content
    assert "route_sunscar / route_exam / pure_support_solo_overlay player_death" in content


def test_pressure_attribution_docs_record_non_goals_without_final_balance_claim():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (REPORT_PATH, STATE_PATH, FOUNDATION_PATH)
    ).lower()
    assert "no live gameplay/runtime systems" in combined or "no live route/mob/skill/reward/formula tuning" in combined
    assert "no tuning/formula/equipment/live mob changes" in combined or "does not change formulas, equipment budget" in combined
    assert "not final balance verdict" in combined or "does not claim final balance" in combined
    assert "final balance is complete" not in combined
    assert "final balance achieved" not in combined
