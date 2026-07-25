from pathlib import Path

import pytest

from game.combat_simulation import (
    SIM_ACTION_GUARD_FALLBACK,
    SIM_ACTION_NORMAL_ATTACK,
    ScriptedActionPolicy,
    SimulationConfig,
    build_simulation_mob_preset,
    build_simulation_player_preset,
    make_simulation_skill_action,
    simulate_single_combat,
)
from game.combat_simulation_archetypes import (
    EXECUTABLE_POLICY_REGISTRY,
    PROFILE_POLICY_PILOT_ARCHETYPE_IDS,
)
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


def _sturdy_mob():
    mob = build_simulation_mob_preset("forest_wolf")
    mob.update({"hp": 5000, "damage": 1, "damage_min": 1, "damage_max": 1, "accuracy": 1})
    return mob


def _simulate(actions, *, skill_levels=None, mana=120, trace=True, max_trace_turns=10):
    return simulate_single_combat(
        build_simulation_player_preset(mana=mana, max_mana=max(1, mana)),
        _sturdy_mob(),
        policy=ScriptedActionPolicy(actions),
        config=SimulationConfig(
            seed=223,
            max_turns=len(actions),
            skill_levels=skill_levels or {},
            include_turn_trace=trace,
            max_trace_turns=max_trace_turns,
        ),
    )


@pytest.fixture(scope="module")
def report_data():
    return build_default_alpha_simulation_report_v2_data()


def test_direct_policy_guard_executes_normally_without_becoming_a_fallback():
    result = _simulate([SIM_ACTION_GUARD_FALLBACK])
    row = result.turn_trace[0]
    assert row["requested_action"] == SIM_ACTION_GUARD_FALLBACK
    assert row["resolved_action"] == SIM_ACTION_GUARD_FALLBACK
    assert row["action_resolution_status"] == "policy_chose_guard"
    assert row["fallback_reason"] is None
    assert result.actions_used[SIM_ACTION_GUARD_FALLBACK] == 1
    assert result.observability["policy_guard_action_count"] == 1
    assert result.observability["fallback_reason_counts"] == {}


def test_cooldown_pressure_is_attributed_by_skill_with_full_run_evidence():
    action = make_simulation_skill_action("sword_rush")
    result = _simulate(
        [action, action, action, action],
        skill_levels={"sword_rush": 1},
        trace=False,
    )
    obs = result.observability
    assert result.turn_trace == []
    assert obs["requested_skill_counts"] == {"sword_rush": 4}
    assert obs["resolved_skill_success_counts_by_skill"] == {"sword_rush": 1}
    assert obs["fallback_reason_counts_by_skill"] == {"sword_rush": {"skill_on_cooldown": 3}}
    assert obs["cooldown_fallback_counts_by_skill"] == {"sword_rush": 3}
    assert obs["cooldown_remaining_totals_by_skill"] == {"sword_rush": 6}
    assert obs["cooldown_remaining_maximums_by_skill"] == {"sword_rush": 3}


def test_skill_aggregates_are_not_limited_by_capped_turn_trace():
    action = make_simulation_skill_action("sword_rush")
    result = _simulate(
        [action, action, action, action],
        skill_levels={"sword_rush": 1},
        trace=True,
        max_trace_turns=1,
    )
    assert len(result.turn_trace) == 1
    assert result.observability["requested_skill_counts"]["sword_rush"] == 4
    assert result.observability["cooldown_fallback_counts_by_skill"]["sword_rush"] == 3


def test_insufficient_mana_is_attributed_by_skill_with_exact_deficit():
    result = _simulate(
        [make_simulation_skill_action("power_strike")],
        skill_levels={"power_strike": 1},
        mana=1,
        trace=False,
    )
    obs = result.observability
    assert obs["fallback_reason_counts_by_skill"] == {"power_strike": {"insufficient_mana": 1}}
    assert obs["insufficient_mana_fallback_counts_by_skill"] == {"power_strike": 1}
    assert obs["mana_deficit_totals_by_skill"] == {"power_strike": 14}
    assert obs["mana_deficit_maximums_by_skill"] == {"power_strike": 14}
    assert result.actions_used[SIM_ACTION_NORMAL_ATTACK] == 1


def test_pr11_report_totals_reconcile_and_guard_attribution_is_corrected(report_data):
    data = report_data["post_pr10_policy_pressure_diagnostics"]
    assert data["available"] is True
    assert data["policy_guard_action_count"] == 24
    assert data["true_guard_fallback_count"] == 0
    assert data["cooldown_fallback_count"] == sum(
        row["cooldown_fallback_count"] for row in data["cooldown_fallback_details_by_skill"]
    )
    assert data["insufficient_mana_count"] == sum(
        row["insufficient_mana_count"] for row in data["insufficient_mana_details_by_skill"]
    )
    assert data["skill_locked_or_unleveled_count"] == 0
    assert "guard_fallback_action" not in {
        reason
        for counts in data["fallback_reason_counts_by_skill"].values()
        for reason in counts
    }


def test_pr11_markdown_and_checked_in_report_preserve_prior_sections(report_data):
    root = Path(__file__).resolve().parents[1]
    rendered = render_alpha_simulation_report_v2_markdown(report_data)
    assert "## Balance V2 PR11 Cooldown & Mana Policy Cause Attribution" in rendered
    assert "## Balance V2 PR10 Cooldown Fallback Diagnostic Breakdown" in rendered
    assert "## Balance V2 PR9 Availability-aware Profile Policy Selection" in rendered
    assert "## Balance V2 PR8 Simulation Action Resolution / Fallback Attribution" in rendered
    assert "PR10's guard count contained deliberate guard-policy actions" in rendered
    assert (root / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md").read_text(encoding="utf-8") == rendered


def test_pr11_preserves_pr7_pr6_pr5_registry_and_project_state(report_data):
    pr6 = report_data["simulation_policy_skill_economy"]
    assert len(PROFILE_POLICY_PILOT_ARCHETYPE_IDS) == 5
    assert len(pr6["policy_coverage_rows"]) == 14
    assert len(pr6["skill_economy_rows"]) == 14
    assert len(report_data["unified_combat_budget_audit"]["audit_rows"]) == 420
    for policy_id in METADATA_ONLY_POLICIES:
        assert EXECUTABLE_POLICY_REGISTRY[policy_id]["executable"] is False

    state = (Path(__file__).resolve().parents[1] / "docs" / "PROJECT_STATE_CURRENT.md").read_text(encoding="utf-8")
    assert "Latest gameplay/balance diagnostic state: PR223 / Balance V2 PR11 Cooldown & Mana Policy Cause Attribution" in state
    assert "PR221 / Balance V2 PR10 Cooldown Fallback Diagnostic Breakdown" in state
    assert "Balance V2 PR9 Availability-aware Profile Policy Selection" in state
    assert "Balance V2 PR8 Simulation Action Resolution / Fallback Attribution" in state
    assert "PR218 Test Suite Baseline Stabilization / SQLite Runtime Test Isolation" in state
