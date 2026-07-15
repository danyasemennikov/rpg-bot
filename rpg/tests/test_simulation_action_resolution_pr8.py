from pathlib import Path

from game.combat_simulation import (
    SIM_ACTION_NORMAL_ATTACK,
    ScriptedActionPolicy,
    SimulationConfig,
    build_simulation_mob_preset,
    build_simulation_player_preset,
    make_simulation_skill_action,
    simulate_single_combat,
)
from game.combat_simulation_archetypes import EXECUTABLE_POLICY_REGISTRY
from game.combat_simulation_report import (
    build_alpha_balance_report_data,
    build_default_alpha_simulation_report_v2_data,
    render_alpha_simulation_report_v2_markdown,
)
from game.unified_combat_budget_audit import build_unified_combat_budget_audit


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


def _simulate(actions, *, skill_levels=None, player_overrides=None, turns=None):
    player = build_simulation_player_preset(**(player_overrides or {}))
    return simulate_single_combat(
        player,
        _sturdy_mob(),
        policy=ScriptedActionPolicy(actions),
        config=SimulationConfig(
            seed=11,
            max_turns=turns or len(actions),
            skill_levels=skill_levels or {},
            include_turn_trace=True,
            max_trace_turns=10,
        ),
    )


def test_requested_normal_attack_is_attributed_as_policy_chose_normal_attack():
    result = _simulate([SIM_ACTION_NORMAL_ATTACK])
    row = result.turn_trace[0]
    assert row["requested_action"] == SIM_ACTION_NORMAL_ATTACK
    assert row["resolved_action"] == SIM_ACTION_NORMAL_ATTACK
    assert row["action_resolution_status"] == "policy_chose_normal_attack"
    assert row["fallback_reason"] is None
    assert result.observability["action_resolution_counts"] == {"policy_chose_normal_attack": 1}


def test_requested_visible_implemented_skill_is_attributed_as_resolved_skill_success():
    result = _simulate([make_simulation_skill_action("power_strike")], skill_levels={"power_strike": 1})
    row = result.turn_trace[0]
    assert row["requested_skill_id"] == "power_strike"
    assert row["resolved_action"] == "skill:power_strike"
    assert row["action_resolution_status"] == "resolved_skill_success"
    assert row["fallback_reason"] is None
    assert row["skill_exists"] is True
    assert row["skill_level"] == 1
    assert row["skill_visible"] is True
    assert row["can_attempt_skill"] is True
    assert result.observability["resolved_skill_success_count"] == 1


def test_requested_missing_skill_is_attributed_and_falls_back_to_normal_attack():
    result = _simulate([make_simulation_skill_action("missing_pr8_skill")])
    row = result.turn_trace[0]
    assert row["resolved_action"] == SIM_ACTION_NORMAL_ATTACK
    assert row["action_resolution_status"] == "skill_missing"
    assert row["fallback_reason"] == "skill_missing"
    assert row["skill_exists"] is False
    assert result.observability["fallback_reason_counts"]["skill_missing"] == 1
    assert result.observability["normal_attack_fallback_count"] == 1


def test_requested_locked_or_unleveled_skill_is_attributed_and_falls_back():
    result = _simulate([make_simulation_skill_action("power_strike")], skill_levels={})
    row = result.turn_trace[0]
    assert row["resolved_action"] == SIM_ACTION_NORMAL_ATTACK
    assert row["action_resolution_status"] == "skill_locked_or_unleveled"
    assert row["fallback_reason"] == "skill_locked_or_unleveled"
    assert row["skill_exists"] is True
    assert row["skill_level"] == 0
    assert row["skill_visible"] is False


def test_learned_positive_level_below_unlock_mastery_can_execute_direct_simulation():
    result = _simulate(
        [make_simulation_skill_action("steady_aim")],
        skill_levels={"steady_aim": 2},
        player_overrides={"mana": 120, "max_mana": 120, "weapon_profile": "bow", "weapon_type": "ranged"},
    )
    row = result.turn_trace[0]
    assert row["requested_skill_id"] == "steady_aim"
    assert row["resolved_action"] == "skill:steady_aim"
    assert row["action_resolution_status"] == "resolved_skill_success"
    assert row["fallback_reason"] is None
    assert row["skill_exists"] is True
    assert row["skill_level"] == 2
    assert row["skill_unlock_mastery"] > row["skill_level"]
    assert row["skill_visible"] is True
    assert row["can_attempt_skill"] is True
    assert "steady_aim" in result.skills_used


def test_requested_skill_on_cooldown_is_attributed_and_falls_back():
    result = _simulate(
        [make_simulation_skill_action("power_strike"), make_simulation_skill_action("power_strike")],
        skill_levels={"power_strike": 1},
        turns=2,
    )
    row = result.turn_trace[1]
    assert row["resolved_action"] == SIM_ACTION_NORMAL_ATTACK
    assert row["action_resolution_status"] == "skill_on_cooldown"
    assert row["fallback_reason"] == "skill_on_cooldown"
    assert row["cooldown_before"] > 0
    assert result.observability["fallback_reason_counts"]["skill_on_cooldown"] == 1


def test_requested_skill_with_insufficient_mana_is_attributed_with_mana_evidence():
    result = _simulate(
        [make_simulation_skill_action("power_strike")],
        skill_levels={"power_strike": 1},
        player_overrides={"mana": 1, "max_mana": 1},
    )
    row = result.turn_trace[0]
    assert row["resolved_action"] == SIM_ACTION_NORMAL_ATTACK
    assert row["action_resolution_status"] in {"insufficient_mana", "skill_execution_failed"}
    assert row["fallback_reason"] in {"insufficient_mana", "skill_execution_failed"}
    assert row["mana_before"] == 1
    assert row["mana_cost"] > row["mana_before"]
    assert row["can_attempt_skill"] is False


def test_turn_trace_and_observability_include_action_resolution_metadata():
    result = _simulate([make_simulation_skill_action("missing_pr8_skill")])
    row = result.turn_trace[0]
    for key in (
        "requested_action",
        "resolved_action",
        "fallback_reason",
        "skill_exists",
        "skill_level",
        "skill_unlock_mastery",
        "skill_visible",
        "cooldown_before",
        "mana_before",
        "mana_cost",
        "can_attempt_skill",
    ):
        assert key in row
    assert "fallback_reason_counts" in result.observability
    assert "action_resolution_counts" in result.observability
    assert "requested_skill_count" in result.observability
    assert "normal_attack_fallback_count" in result.observability


def test_report_data_exposes_simulation_action_resolution_and_pr8_markdown_section():
    report = build_default_alpha_simulation_report_v2_data()
    data = report["simulation_action_resolution"]
    assert data["available"] is True
    assert "fallback_reason_counts" in data
    assert "action_resolution_counts" in data
    assert "pilot_policy_resolution_summary" in data
    markdown = render_alpha_simulation_report_v2_markdown(report)
    assert "## Balance V2 PR8 Simulation Action Resolution / Fallback Attribution" in markdown
    assert "Metadata-only registry policies remain not globally flipped" in markdown
    assert "PR6 remains 14/14" in markdown
    assert "PR5 remains 420" in markdown


def test_checked_in_v2_report_matches_renderer_output_after_pr8():
    project_root = Path(__file__).resolve().parents[1]
    rendered = render_alpha_simulation_report_v2_markdown(build_default_alpha_simulation_report_v2_data())
    assert (project_root / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md").read_text(encoding="utf-8") == rendered


def test_pr6_pr5_pr7_and_metadata_registry_guards_remain_intact():
    report = build_alpha_balance_report_data()
    pr6 = report["simulation_policy_skill_economy"]
    assert len(pr6["policy_coverage_rows"]) == 14
    assert len(pr6["skill_economy_rows"]) == 14
    assert len(build_unified_combat_budget_audit()["audit_rows"]) == 420
    pilot_rows = [row for row in pr6["policy_coverage_rows"] if row["profile_policy_pilot"]]
    assert {row["archetype_id"] for row in pilot_rows} == {
        "daggers_venom",
        "daggers_evasion",
        "bow_sniper",
        "magic_staff_destruction",
        "holy_staff_solo",
    }
    assert all(row["active_simulation_policy_status"] == "profile_executable_pilot" for row in pilot_rows)
    for policy_id in METADATA_ONLY_POLICIES:
        assert EXECUTABLE_POLICY_REGISTRY[policy_id]["executable"] is False


def test_project_state_current_preserves_pr8_and_records_pr9_latest():
    project_root = Path(__file__).resolve().parents[1]
    text = (project_root / "docs" / "PROJECT_STATE_CURRENT.md").read_text(encoding="utf-8")
    assert "Balance V2 PR8 Simulation Action Resolution / Fallback Attribution" in text
    assert "PR: Codex Workflow Restoration (Docs only)" in text
    assert "Balance V2 PR8 Simulation Action Resolution / Fallback Attribution" in text
    assert "Balance V2 PR9 Availability-aware Profile Policy Selection" in text
