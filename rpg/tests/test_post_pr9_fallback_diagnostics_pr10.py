from pathlib import Path

from game.combat_simulation_archetypes import EXECUTABLE_POLICY_REGISTRY, PROFILE_POLICY_PILOT_ARCHETYPE_IDS
from game.combat_simulation_report import (
    build_default_alpha_simulation_report_v2_data,
    render_alpha_simulation_report_v2_markdown,
)


METADATA_ONLY_POLICIES = {
    "aggressive_burst",
    "venom_setup",
    "evasion_tempo",
    "sniper_precision",
    "control_caster",
    "solo_support_sustain",
    "toolbox_balanced",
}


def test_pr10_report_data_exposes_post_pr9_fallback_breakdowns():
    data = build_default_alpha_simulation_report_v2_data()["post_pr9_fallback_diagnostics"]
    assert data["available"] is True
    assert data["skill_locked_or_unleveled_count"] == 0
    for key in ("cooldown_fallback_count", "guard_fallback_count", "insufficient_mana_count"):
        assert isinstance(data[key], int)
        assert data[key] >= 0
    assert data["fallback_counts_by_archetype"]
    assert data["fallback_counts_by_stage"]
    assert set(data["fallback_counts_by_pilot_archetype"]) == set(PROFILE_POLICY_PILOT_ARCHETYPE_IDS)
    assert data["recommended_next_investigation"] in {
        "investigate_cooldown_and_mana_policy_behavior",
        "investigate_route_and_mob_pressure_context",
    }


def test_pr10_markdown_and_checked_in_report_preserve_pr9_and_pr8():
    root = Path(__file__).resolve().parents[1]
    report = build_default_alpha_simulation_report_v2_data()
    rendered = render_alpha_simulation_report_v2_markdown(report)
    assert "## Balance V2 PR10 Cooldown Fallback Diagnostic Breakdown" in rendered
    assert "## Balance V2 PR9 Availability-aware Profile Policy Selection" in rendered
    assert "## Balance V2 PR8 Simulation Action Resolution / Fallback Attribution" in rendered
    assert "skill_locked_or_unleveled remains 0 after filtering" in rendered
    assert (root / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md").read_text(encoding="utf-8") == rendered


def test_pr10_preserves_pr7_pr6_pr5_and_metadata_registry_guards():
    report = build_default_alpha_simulation_report_v2_data()
    pr6 = report["simulation_policy_skill_economy"]
    assert len(PROFILE_POLICY_PILOT_ARCHETYPE_IDS) == 5
    assert len(pr6["policy_coverage_rows"]) == 14
    assert len(pr6["skill_economy_rows"]) == 14
    assert len(report["unified_combat_budget_audit"]["audit_rows"]) == 420
    for policy_id in METADATA_ONLY_POLICIES:
        assert EXECUTABLE_POLICY_REGISTRY[policy_id]["executable"] is False


def test_project_state_marks_pr10_as_latest_diagnostic_state_and_preserves_baselines():
    root = Path(__file__).resolve().parents[1]
    state = (root / "docs" / "PROJECT_STATE_CURRENT.md").read_text(encoding="utf-8")
    assert "PR221 / Balance V2 PR10 Cooldown Fallback Diagnostic Breakdown" in state
    assert "Latest gameplay/balance diagnostic state: PR221 / Balance V2 PR10 Cooldown Fallback Diagnostic Breakdown" in state
    assert "Balance V2 PR9 Availability-aware Profile Policy Selection" in state
    assert "Balance V2 PR8 Simulation Action Resolution / Fallback Attribution" in state
    assert "PR218 Test Suite Baseline Stabilization / SQLite Runtime Test Isolation" in state
