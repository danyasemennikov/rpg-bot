from pathlib import Path

from game.combat_simulation_archetypes import list_alpha_archetype_ids
from game.combat_simulation_report import build_alpha_balance_report_data, render_alpha_simulation_report_v2_markdown
from game.combat_simulation_matrix import RouteStageMatrixConfig, run_route_stage_simulation_matrix
from game.equipment_budget import build_simulation_gear_preset
from game.mob_scaling import PR3_LATE_STAGE_MOB_PRESSURE_REFINEMENTS
from game.unified_combat_budget_audit import (
    GEAR_STATES,
    LEVEL_BANDS,
    RISK_TAG_IDS,
    build_progression_gear_state_preset,
    build_unified_combat_budget_audit,
)


def _small_report():
    config = RouteStageMatrixConfig(
        route_ids=("route_westwild",),
        stages=("soft_entry",),
        archetype_ids=("guardian_shield_1h", "sword_2h_burst"),
        seeds=(1,),
        max_samples_per_route_stage=1,
        max_turns=30,
        include_raw_runs=True,
    )
    return build_alpha_balance_report_data(run_route_stage_simulation_matrix(config), config=config)


def test_pr5_audit_includes_all_archetypes_level_bands_and_gear_states():
    audit = build_unified_combat_budget_audit()
    rows = audit["audit_rows"]
    assert {row["archetype_id"] for row in rows} == set(list_alpha_archetype_ids())
    assert {row["level_band_id"] for row in rows} == {band.id for band in LEVEL_BANDS}
    assert {row["gear_state_id"] for row in rows} == {state.id for state in GEAR_STATES}
    assert len(rows) == len(list_alpha_archetype_ids()) * len(LEVEL_BANDS) * len(GEAR_STATES)


def test_compact_checked_in_mode_is_bounded_and_deterministic():
    audit_one = build_unified_combat_budget_audit(mode="compact_checked_in")
    audit_two = build_unified_combat_budget_audit(mode="compact_checked_in")
    assert audit_one == audit_two
    assert audit_one["mode"] == "compact_checked_in"
    assert len(audit_one["audit_rows"]) == 14 * 6 * 5


def test_progression_gear_state_budget_generally_increases():
    archetype_id = "guardian_shield_1h"
    level_band_id = "midgame"
    budgets = {
        state.id: build_progression_gear_state_preset(archetype_id, level_band_id, state.id)["total_budget"]
        for state in GEAR_STATES
    }
    assert budgets["undergeared"] < budgets["baseline_expected"] < budgets["enhanced_expected"]
    assert budgets["enhanced_expected"] < budgets["optimized"] < budgets["overgeared_high_enhancement"]


def test_overgeared_high_enhancement_is_not_pvp_baseline_and_is_risk_flagged():
    audit = build_unified_combat_budget_audit()
    overgeared_rows = [row for row in audit["audit_rows"] if row["gear_state_id"] == "overgeared_high_enhancement"]
    assert overgeared_rows
    assert all(row["gear_preset_summary"]["pvp_equal_budget_baseline"] is False for row in overgeared_rows)
    assert all(row["gear_preset_summary"]["pvp_gear_gap_or_stress_probe"] is True for row in overgeared_rows)
    assert any("enhancement_scaling_risk" in row["risk_tags"] for row in overgeared_rows)
    assert any("pvp_only_toxicity" in row["risk_tags"] for row in overgeared_rows)


def test_report_data_shape_and_pr4_reconciliation_exists():
    report = _small_report()
    audit = report["unified_combat_budget_audit"]
    for key in (
        "available",
        "mode",
        "level_bands",
        "gear_states",
        "audit_rows",
        "risk_counts",
        "top_systemic_findings",
        "pve_budget_summary",
        "pvp_budget_proxy_summary",
        "pr4_route_pressure_reconciliation",
        "recommended_tuning_order",
        "notes",
    ):
        assert key in audit
    assert audit["available"] is True
    assert audit["pvp_budget_proxy_summary"]["summary_type"] == "pvp_budget_proxy"
    assert audit["pvp_budget_proxy_summary"]["real_duel_win_rates"] is False
    assert audit["pvp_budget_proxy_summary"]["pvp_equal_budget_baseline_gear_states"] == [
        "baseline_expected",
        "enhanced_expected",
        "optimized",
    ]
    assert audit["pvp_budget_proxy_summary"]["pvp_gear_gap_stress_states"] == [
        "undergeared",
        "overgeared_high_enhancement",
    ]
    assert audit["pr4_route_pressure_reconciliation"]["available"] is True


def test_markdown_pr5_section_and_non_goals_wording_exists():
    report = _small_report()
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "## Balance V2 PR5 Unified Combat Budget Audit" in md
    assert "Diagnostic-only" in md
    assert "performs no tuning" in md
    assert "All gear states are included" in md
    assert "PvE and PvP/proxy budget coverage" in md
    assert "PvP equal-budget baseline gear states: baseline_expected, enhanced_expected, optimized" in md
    assert "PvP gear-gap/stress states: undergeared, overgeared_high_enhancement" in md
    assert "Top systemic findings" in md
    assert "Recommended tuning order" in md
    assert "PR4 route pressure reconciliation" in md
    assert "No live gameplay/runtime/formula/equipment/live mob/economy/targeting/teleport/live group combat changes" in md


def test_route_pressure_tags_are_scoped_to_late_bands_and_baseline_like_gear():
    pressure_rows = [
        {
            "route_id": "route_westwild",
            "stage": "build_testing",
            "archetype_id": "guardian_shield_1h",
            "recommended_lane": "mob_pressure_lane",
        },
        {
            "route_id": "route_sunscar",
            "stage": "route_exam",
            "archetype_id": "sword_2h_burst",
            "recommended_lane": "mob_pressure_lane",
        },
        {
            "route_id": "route_westwild",
            "stage": "soft_entry",
            "archetype_id": "bow_ranger",
            "recommended_lane": "route_expectation_lane",
        },
    ]
    audit = build_unified_combat_budget_audit(pressure_attribution_rows=pressure_rows)
    total_rows = len(audit["audit_rows"])
    risk_counts = audit["risk_counts"]

    assert 0 < risk_counts["route_pressure_suspect_player_side"] < total_rows
    assert 0 < risk_counts["route_pressure_confirmed"] < total_rows

    route_tagged_rows = [
        row
        for row in audit["audit_rows"]
        if "route_pressure_suspect_player_side" in row["risk_tags"]
        or "route_pressure_confirmed" in row["risk_tags"]
    ]
    assert route_tagged_rows
    assert {row["level_band_id"] for row in route_tagged_rows} <= {"advanced", "endgame"}
    assert {row["gear_state_id"] for row in route_tagged_rows} <= {
        "baseline_expected",
        "enhanced_expected",
        "optimized",
    }
    assert not any(row["gear_state_id"] in {"undergeared", "overgeared_high_enhancement"} for row in route_tagged_rows)

    reconciliation = audit["pr4_route_pressure_reconciliation"]
    suspect_archetypes = reconciliation["suspect_player_side_archetypes"]
    assert suspect_archetypes
    assert all(isinstance(item, dict) for item in suspect_archetypes)
    assert all("mob_pressure_count" in item and "route_stage_clusters" in item for item in suspect_archetypes)
    assert not any(item.get("archetype_id") == "bow_ranger" for item in suspect_archetypes)


def test_pvp_equal_budget_baseline_excludes_gear_gap_and_stress_states():
    audit = build_unified_combat_budget_audit()
    pvp_summary = audit["pvp_budget_proxy_summary"]
    assert pvp_summary["pvp_equal_budget_baseline_gear_states"] == [
        "baseline_expected",
        "enhanced_expected",
        "optimized",
    ]
    assert pvp_summary["pvp_gear_gap_stress_states"] == ["undergeared", "overgeared_high_enhancement"]

    rows_by_state = {
        row["gear_state_id"]: row["gear_preset_summary"]
        for row in audit["audit_rows"]
        if row["archetype_id"] == "guardian_shield_1h" and row["level_band_id"] == "starter"
    }
    assert rows_by_state["undergeared"]["pvp_equal_budget_baseline"] is False
    assert rows_by_state["undergeared"]["pvp_gear_gap_or_stress_probe"] is True
    assert rows_by_state["baseline_expected"]["pvp_equal_budget_baseline"] is True
    assert rows_by_state["overgeared_high_enhancement"]["pvp_equal_budget_baseline"] is False


def test_no_pr3_pr4_tuning_knobs_changed_and_no_pr5_tuning_knobs_added():
    assert PR3_LATE_STAGE_MOB_PRESSURE_REFINEMENTS[("route_frostspine", "build_testing")]["hp"] == 1.10
    assert build_simulation_gear_preset("guardian_shield_1h", "soft_entry")["item_level"] == 10
    assert all("multiplier" not in risk_id and "knob" not in risk_id for risk_id in RISK_TAG_IDS)


def test_project_state_current_has_pr5_header_update():
    project_root = Path(__file__).resolve().parents[1]
    content = (project_root / "docs" / "PROJECT_STATE_CURRENT.md").read_text(encoding="utf-8")
    assert "Balance V2 PR5" in content
    assert "Unified PvE/PvP Combat Budget Audit" in content
