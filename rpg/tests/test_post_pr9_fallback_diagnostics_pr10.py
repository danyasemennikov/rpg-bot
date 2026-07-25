from pathlib import Path

from game.combat_simulation_archetypes import EXECUTABLE_POLICY_REGISTRY
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


def test_post_pr9_fallback_diagnostics_are_exposed_from_existing_observability():
    report = build_default_alpha_simulation_report_v2_data()
    data = report["post_pr9_fallback_diagnostics"]

    assert data["available"] is True
    assert data["skill_locked_or_unleveled_count"] == 0
    assert data["cooldown_fallback_count"] >= 0
    assert data["guard_fallback_count"] >= 0
    assert data["insufficient_mana_count"] >= 0
    assert data["fallback_counts_by_archetype"]
    assert data["fallback_counts_by_stage"]
    assert len(data["fallback_counts_by_pilot_archetype"]) == 5
    assert data["recommended_next_investigation"]


def test_pr10_renderer_and_checked_in_report_preserve_pr9_and_pr8():
    root = Path(__file__).resolve().parents[1]
    report = build_default_alpha_simulation_report_v2_data()
    markdown = render_alpha_simulation_report_v2_markdown(report)

    assert "## Balance V2 PR10 Cooldown Fallback Diagnostic Breakdown" in markdown
    assert "## Balance V2 PR9 Availability-aware Profile Policy Selection" in markdown
    assert "## Balance V2 PR8 Simulation Action Resolution / Fallback Attribution" in markdown
    assert "PR9 availability filtering remains intact" in markdown
    assert "`skill_locked_or_unleveled` remains 0 after filtering" in markdown
    assert (root / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md").read_text(encoding="utf-8") == markdown


def test_prior_balance_diagnostic_guards_remain_intact():
    report = build_default_alpha_simulation_report_v2_data()
    pr6 = report["simulation_policy_skill_economy"]
    pr8 = report["simulation_action_resolution"]

    assert len(pr6["policy_coverage_rows"]) == 14
    assert len(pr6["skill_economy_rows"]) == 14
    assert len(report["unified_combat_budget_audit"]["audit_rows"]) == 420
    assert len(pr8["pilot_policy_resolution_summary"]) == 5
    assert "fallback_reason_counts_by_archetype" in pr8
    assert "fallback_reason_counts_by_stage" in pr8
    for policy_id in METADATA_ONLY_POLICIES:
        assert EXECUTABLE_POLICY_REGISTRY[policy_id]["executable"] is False


def test_project_state_marks_pr10_as_latest_diagnostic_state():
    root = Path(__file__).resolve().parents[1]
    text = (root / "docs" / "PROJECT_STATE_CURRENT.md").read_text(encoding="utf-8")

    assert "PR221 / Balance V2 PR10 is the latest confirmed gameplay/balance diagnostic state." in text
    assert "PR9 remains prior availability-aware profile policy state." in text
    assert "PR8 action-resolution state remains preserved." in text
    assert "PR218 test baseline state remains preserved." in text
    assert "PR10 is diagnostic/simulation/reporting-only." in text
    assert "PR10 adds post-PR9 fallback breakdown diagnostics." in text
    assert "PR10 does not tune gameplay/runtime/balance numbers." in text
