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

EXPECTED_PR3_REFINEMENTS = {
    ("route_frostspine", "build_testing"): {"hp": 1.10, "damage": 1.03, "accuracy": 1.00, "evasion": 1.00, "defense": 1.06, "magic_defense": 1.06},
    ("route_frostspine", "route_exam"): {"hp": 1.10, "damage": 1.04, "accuracy": 1.00, "evasion": 1.00, "defense": 1.06, "magic_defense": 1.06},
    ("route_ashen_ruins", "build_testing"): {"hp": 1.10, "damage": 1.04, "accuracy": 1.04, "evasion": 1.00, "defense": 1.00, "magic_defense": 1.06},
    ("route_ashen_ruins", "route_exam"): {"hp": 1.10, "damage": 1.05, "accuracy": 1.05, "evasion": 1.00, "defense": 1.00, "magic_defense": 1.06},
    ("route_mireveil", "build_testing"): {"hp": 1.10, "damage": 1.02, "accuracy": 1.00, "evasion": 1.06, "defense": 1.00, "magic_defense": 1.03},
    ("route_mireveil", "route_exam"): {"hp": 1.10, "damage": 1.03, "accuracy": 1.00, "evasion": 1.06, "defense": 1.00, "magic_defense": 1.04},
    ("route_sunscar", "build_testing"): {"hp": 1.06, "damage": 1.03, "accuracy": 1.03, "evasion": 1.00, "defense": 1.00, "magic_defense": 1.00},
    ("route_sunscar", "route_exam"): {"hp": 1.03, "damage": 1.02, "accuracy": 1.02, "evasion": 1.00, "defense": 1.00, "magic_defense": 1.00},
}


def _pr4_data():
    report = build_default_alpha_simulation_report_v2_data()
    return report, report["pr4_multiseed_confidence"]


def test_pr4_confidence_data_shape_and_availability():
    _, confidence = _pr4_data()
    assert confidence["available"] is True
    for key in (
        "seeds",
        "compact_lane_counts",
        "multiseed_lane_counts",
        "lane_deltas",
        "stable_clusters",
        "unstable_clusters",
        "high_confidence_remaining_clusters",
    ):
        assert key in confidence
    assert isinstance(confidence["stable_clusters"], list)
    assert isinstance(confidence["unstable_clusters"], list)


def test_pr4_uses_multiple_seeds():
    _, confidence = _pr4_data()
    seeds = confidence["seeds"]
    assert {1, 2, 3}.issubset(set(seeds)) or len(seeds) >= 3
    assert len(set(seeds)) >= 3


def test_pr4_compact_pr3_baseline_preserved():
    _, confidence = _pr4_data()
    compact = confidence["compact_lane_counts"]
    assert compact["mob_pressure_lane"] == 41
    assert compact["route_expectation_lane"] == 44
    assert compact["bad_matchup_review_lane"] == 1


def test_pr4_lane_deltas_use_normalized_multiseed_fields():
    _, confidence = _pr4_data()
    required = {
        "compact",
        "seed_count",
        "expected_multiseed_total",
        "multiseed_total",
        "multiseed_per_seed_avg",
        "delta_vs_expected_total",
        "delta_per_seed_vs_compact",
        "interpretation",
    }
    for lane in ("mob_pressure_lane", "route_expectation_lane", "bad_matchup_review_lane", "inconclusive_lane"):
        assert required.issubset(confidence["lane_deltas"][lane].keys())
        assert confidence["lane_deltas"][lane]["seed_count"] == 3


def test_pr4_normalized_lane_interpretations_do_not_treat_seed_totals_as_raw_growth():
    _, confidence = _pr4_data()
    deltas = confidence["lane_deltas"]

    route_expectation = deltas["route_expectation_lane"]
    assert route_expectation["compact"] == 44
    assert route_expectation["multiseed_total"] == 132
    assert route_expectation["expected_multiseed_total"] == 132
    assert route_expectation["delta_vs_expected_total"] == 0
    assert route_expectation["interpretation"] == "stable_across_seeds"

    bad_matchup = deltas["bad_matchup_review_lane"]
    assert bad_matchup["compact"] == 1
    assert bad_matchup["multiseed_total"] == 3
    assert bad_matchup["expected_multiseed_total"] == 3
    assert bad_matchup["interpretation"] == "stable_across_seeds"

    mob_pressure = deltas["mob_pressure_lane"]
    assert mob_pressure["compact"] == 41
    assert mob_pressure["multiseed_total"] == 125
    assert mob_pressure["expected_multiseed_total"] == 123
    assert mob_pressure["delta_vs_expected_total"] == 2
    assert mob_pressure["multiseed_per_seed_avg"] == 41.67
    assert mob_pressure["delta_per_seed_vs_compact"] == 0.67
    assert mob_pressure["interpretation"] in {"stable_across_seeds", "slightly_higher_per_seed"}
    assert mob_pressure["interpretation"] != "higher_in_multiseed"


def test_pr4_rendered_v2_report_contains_summary_tables_and_disclaimers():
    report, _ = _pr4_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "## Balance V2 PR4 Expanded Sampling / Multi-seed Confidence Summary" in md
    assert "Lane comparison table" in md
    assert "PR4 multi-seed total" in md
    assert "expected total" in md
    assert "per-seed avg" in md
    assert "delta vs expected" in md
    assert "Multi-seed totals are raw totals across seeds; interpretation is normalized per seed." in md
    route_expectation_row = next(line for line in md.splitlines() if line.startswith("| route_expectation_lane |"))
    assert "higher_in_multiseed" not in route_expectation_row
    assert "High-confidence remaining mob_pressure clusters preview" in md
    assert "Unstable/noisy clusters preview" in md
    assert "diagnostic-only and does not tune balance numbers" in md
    assert "No new tuning knobs were added" in md


def test_pr4_checked_in_report_contains_section_and_pr3_counts():
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert "## Balance V2 PR4 Expanded Sampling / Multi-seed Confidence Summary" in content
    assert "Current mob_pressure_lane count: 41." in content
    assert "Current route_expectation_lane count: 44." in content
    assert "Current bad_matchup_review_lane count: 1." in content
    assert "Compact PR3 lane counts: mob_pressure_lane=41, route_expectation_lane=44, bad_matchup_review_lane=1" in content


def test_pr4_v1_smoke_guard_does_not_fake_counts():
    report = build_default_alpha_balance_report_data()
    md = render_alpha_balance_report_markdown(report)
    confidence = report["pr4_multiseed_confidence"]
    assert confidence["available"] is False
    assert "PR4 multi-seed confidence data is unavailable" in md
    assert "Lane comparison table" not in md
    assert "Compact PR3 lane counts: mob_pressure_lane=0" not in md
    assert "stable-cluster wording" in md


def test_pr4_sunscar_bad_matchup_remains_separated():
    report, confidence = _pr4_data()
    assert any(
        row.get("route_id") == "route_sunscar"
        and row.get("stage") == "route_exam"
        and row.get("archetype_id") == "pure_support_solo_overlay"
        and row.get("end_reason") == "player_death"
        and row.get("recommended_lane") == "bad_matchup_review_lane"
        for row in report["pressure_attribution_rows"]
    )
    assert confidence["compact_lane_counts"]["bad_matchup_review_lane"] == 1
    md = render_alpha_simulation_report_v2_markdown(report).lower()
    assert "not an automatic support buff or sunscar nerf" in md
    assert "automatic support buff" in md
    assert "sunscar nerf" in md
    assert "buffing support" not in md
    assert "nerfing sunscar" not in md


def test_pr4_no_tuning_knobs_added_or_changed_and_docs_preserve_non_goals():
    assert PR3_LATE_STAGE_MOB_PRESSURE_REFINEMENTS == EXPECTED_PR3_REFINEMENTS
    report_module = (Path(__file__).resolve().parents[1] / "game" / "combat_simulation_report.py").read_text(encoding="utf-8")
    assert "PR4_LATE_STAGE" not in report_module
    assert "PR4_TUNING" not in report_module
    for content in (
        REPORT_PATH.read_text(encoding="utf-8"),
        STATE_PATH.read_text(encoding="utf-8"),
        FOUNDATION_PATH.read_text(encoding="utf-8"),
    ):
        assert "no new tuning knobs" in content.lower()
        assert "no live gameplay/runtime" in content.lower()
        assert "no final balance" in content.lower() or "does not claim final balance" in content.lower()
        assert "targeting" in content and "teleport" in content and "live group combat" in content


def test_pr4_continuity_sections_still_exist():
    content = REPORT_PATH.read_text(encoding="utf-8")
    for marker in (
        "PR12 First Tuning Pass Summary",
        "PR13 Targeted Alpha Tuning Summary",
        "PR14 Target Expectation Calibration Summary",
        "PR15 Actionable Late-Stage Tuning Summary",
        "Balance V2 PR3 Controlled Late-Stage Mob Pressure Tuning Summary",
        "Balance Instrument V2 Observability Preview",
        "Balance Instrument V2 Pressure Attribution Preview",
    ):
        assert marker in content
