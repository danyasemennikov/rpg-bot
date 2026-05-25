from pathlib import Path

from game.combat_simulation_archetypes import list_alpha_archetype_ids
from game.combat_simulation_matrix import RouteStageMatrixConfig, run_route_stage_simulation_matrix
from game.combat_simulation_report import (
    TARGET_TABLE_LIMIT,
    SUSPICIOUS_TABLE_LIMIT,
    _is_suspicious,
    build_alpha_balance_report_data,
    build_default_alpha_balance_report_data,
    compare_observed_pressure_to_target,
    render_alpha_balance_report_markdown,
    resolve_archetype_matchup_key,
)
from game.locations import ROUTE_MATCHUP_TARGET_PROFILES


def _tiny_cfg():
    return RouteStageMatrixConfig(
        route_ids=("route_westwild",),
        stages=("soft_entry",),
        archetype_ids=("guardian_shield_1h", "sword_2h_burst"),
        seeds=(1,),
        max_samples_per_route_stage=1,
        max_turns=50,
        include_raw_runs=True,
    )


def test_archetype_mapping_coverage_and_route_key_coverage():
    errors = []
    for archetype_id in list_alpha_archetype_ids():
        key = resolve_archetype_matchup_key(archetype_id)
        if not key:
            errors.append(f"missing mapping for {archetype_id}")
            continue
        for route_id, profile in ROUTE_MATCHUP_TARGET_PROFILES.items():
            target_matchups = profile.get("target_matchups", {})
            if key not in target_matchups:
                errors.append(f"{route_id}: missing target key {key} for {archetype_id}")
    assert not errors, f"Explicit coverage errors: {errors}"


def test_report_data_resolves_target_labels_for_westwild_tiny_config():
    matrix = run_route_stage_simulation_matrix(_tiny_cfg())
    report = build_alpha_balance_report_data(matrix_result=matrix)
    rows = {row["archetype_id"]: row for row in report["target_comparisons"]}

    guardian = rows["guardian_shield_1h"]
    sword = rows["sword_2h_burst"]

    assert guardian["matchup_key"] == "shield_defensive_1h"
    assert guardian["target_label"] == "normal"
    assert guardian["target_label"] not in {None, "n/a"}

    assert sword["matchup_key"] == "sword_2h"
    assert sword["target_label"] == "normal_strong"
    assert sword["target_label"] not in {None, "n/a"}


def test_comparison_helper_cases():
    assert compare_observed_pressure_to_target("strong", "strong")["alignment"] == "aligned"
    assert compare_observed_pressure_to_target("very_hard", "strong")["alignment"] in {
        "harder_than_target",
        "slightly_harder_than_target",
    }
    assert compare_observed_pressure_to_target("strong", "very_hard")["alignment"] in {
        "easier_than_target",
        "slightly_easier_than_target",
    }
    assert compare_observed_pressure_to_target("dead_or_blocked", "")["alignment"] == "inconclusive"
    assert compare_observed_pressure_to_target("dead_or_blocked", "normal")["alignment"] == "critical_mismatch"
    assert compare_observed_pressure_to_target("inconclusive", "normal")["alignment"] == "inconclusive"


def test_suspicious_target_reasons_require_valid_target():
    summary = {"observed_pressure_label": "dead_or_blocked", "timeouts": 0, "runs": 1, "death_rate": 0.1, "win_rate": 0.0}
    reasons = _is_suspicious(summary, "")
    assert "dead_or_blocked_above_target" not in reasons


def test_report_data_smoke_from_tiny_matrix():
    matrix = run_route_stage_simulation_matrix(_tiny_cfg())
    report = build_alpha_balance_report_data(matrix_result=matrix)
    assert report["summaries"]
    assert report["target_comparisons"]
    assert "suspicious_matchups" in report
    assert report["limitations"]
    assert "exp" not in report and "gold" not in report and "loot" not in report


def test_markdown_renderer_smoke():
    matrix = run_route_stage_simulation_matrix(_tiny_cfg())
    report = build_alpha_balance_report_data(matrix_result=matrix)
    md = render_alpha_balance_report_markdown(report)
    assert "Alpha Route/Class Balance Report v1" in md
    assert "Methodology" in md
    assert "Suspicious Matchup Candidates" in md
    assert "Limitations" in md
    assert "Scope and Non-goals" in md
    assert "final balance solved" not in md.lower()


def test_build_default_alpha_balance_report_data_smoke():
    report = build_default_alpha_balance_report_data()
    assert isinstance(report, dict)
    assert report["run_count"] > 0
    assert report["summaries"]
    assert report["target_comparisons"]




def test_markdown_discloses_target_truncation_when_applicable():
    report = build_default_alpha_balance_report_data()
    md = render_alpha_balance_report_markdown(report)
    if len(report["target_comparisons"]) > TARGET_TABLE_LIMIT:
        assert "Showing first" in md
        assert "target comparison rows" in md
        assert str(len(report["target_comparisons"])) in md


def test_markdown_discloses_suspicious_truncation_when_applicable():
    report = build_default_alpha_balance_report_data()
    md = render_alpha_balance_report_markdown(report)
    if len(report["suspicious_matchups"]) > SUSPICIOUS_TABLE_LIMIT:
        assert "route-balanced preview rows" in md
        assert "suspicious candidates" in md
        assert str(len(report["suspicious_matchups"])) in md


def test_markdown_includes_suspicious_counts_by_route():
    report = build_default_alpha_balance_report_data()
    md = render_alpha_balance_report_markdown(report)
    assert "Suspicious candidates by route" in md
    routes_with_suspicious = {row["route_id"] for row in report["suspicious_matchups"]}
    for route_id in routes_with_suspicious:
        assert f"- {route_id}:" in md

def test_checked_in_report_exists_and_sections():
    path = Path(__file__).resolve().parents[1] / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V1.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Alpha Route/Class Balance Report v1" in content
    assert "Methodology" in content
    assert "Scope and Non-goals" in content
    assert "Limitations" in content
    assert "Recommended Next Steps" in content
    assert "normal_strong" in content or "normal" in content
    assert "| route_westwild | soft_entry | guardian_shield_1h | normal |" in content
    assert "Suspicious candidates by route" in content
    default_report = build_default_alpha_balance_report_data()
    if len(default_report["target_comparisons"]) > TARGET_TABLE_LIMIT:
        assert "target comparison rows" in content
    if len(default_report["suspicious_matchups"]) > SUSPICIOUS_TABLE_LIMIT:
        assert "route-balanced preview rows" in content
        assert "suspicious candidates" in content
    assert "diagnostic report" in content.lower()
    assert "not a final balance verdict" in content.lower()
    assert "already applied tuning" not in content.lower()
