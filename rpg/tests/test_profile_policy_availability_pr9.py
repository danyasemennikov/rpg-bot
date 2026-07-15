from pathlib import Path

from game.combat_simulation import SimulationConfig, build_simulation_mob_preset, simulate_single_combat
from game.combat_simulation_archetypes import EXECUTABLE_POLICY_REGISTRY, PROFILE_POLICY_PILOT_ARCHETYPE_IDS, build_archetype_player_preset, build_archetype_simulation_skill_levels
from game.combat_simulation_matrix import resolve_archetype_simulation_policy
from game.combat_simulation_report import build_default_alpha_simulation_report_v2_data, render_alpha_simulation_report_v2_markdown
from game.unified_combat_budget_audit import build_unified_combat_budget_audit

PILOT_SET = {
    "daggers_venom",
    "daggers_evasion",
    "bow_sniper",
    "magic_staff_destruction",
    "holy_staff_solo",
}
METADATA_ONLY_POLICIES = {
    "aggressive_burst",
    "venom_setup",
    "evasion_tempo",
    "sniper_precision",
    "control_caster",
    "solo_support_sustain",
    "toolbox_balanced",
}


def test_pr9_pilot_set_remains_exactly_five():
    assert set(PROFILE_POLICY_PILOT_ARCHETYPE_IDS) == PILOT_SET


def test_profile_policy_skips_unavailable_expected_skills_and_reports_them():
    resolved = resolve_archetype_simulation_policy("magic_staff_destruction", "build_testing")
    policy = resolved["policy"]
    chosen = [policy.choose_action(turn=turn, battle_state={"player_hp": 100, "player_max_hp": 100}) for turn in range(1, 8)]
    assert "skill:cataclysm" not in chosen
    assert "skill:flame_wave" not in chosen
    assert "cataclysm" in resolved["skipped_profile_skill_ids"]
    assert "flame_wave" in resolved["unavailable_profile_skill_ids"]
    assert resolved["profile_policy_availability_status"] == "partial_profile_skills_available"


def test_profile_policy_still_uses_available_setup_payoff_and_sustain_skills():
    cases = {
        "daggers_venom": "skill:toxic_cut",
        "bow_sniper": "skill:aimed_shot",
        "holy_staff_solo": "skill:regeneration",
    }
    for archetype_id, expected_action in cases.items():
        resolved = resolve_archetype_simulation_policy(archetype_id, "build_testing")
        actions = [resolved["policy"].choose_action(turn=turn, battle_state={"player_hp": 40, "player_max_hp": 100}) for turn in range(1, 8)]
        assert expected_action in actions, archetype_id


def test_profile_policy_does_not_request_unavailable_skills_in_simulation_trace():
    archetype_id = "magic_staff_destruction"
    levels = build_archetype_simulation_skill_levels(archetype_id, "build_testing")
    player = build_archetype_player_preset(archetype_id, "build_testing")
    mob = build_simulation_mob_preset("forest_wolf")
    mob.update({"hp": 5000, "damage": 1, "damage_min": 1, "damage_max": 1})
    resolved = resolve_archetype_simulation_policy(archetype_id, "build_testing")
    result = simulate_single_combat(
        player,
        mob,
        policy=resolved["policy"],
        config=SimulationConfig(seed=7, max_turns=8, skill_levels=levels, include_turn_trace=True),
    )
    requested = {row["requested_skill_id"] for row in result.turn_trace if row.get("requested_skill_id")}
    assert requested <= set(levels)
    assert "cataclysm" not in requested


def test_no_profile_non_pilot_archetype_has_no_profile_policy_status():
    resolved = resolve_archetype_simulation_policy("axe_2h_bruiser", "build_testing")
    assert resolved["profile_policy_availability_status"] == "no_profile_policy"
    assert resolved["available_profile_skill_ids"] == []


def test_pr9_report_data_and_markdown_include_availability_diagnostics():
    report = build_default_alpha_simulation_report_v2_data()
    data = report["profile_policy_availability"]
    assert data["available"] is True
    assert "partial_profile_skills_available" in data["availability_status_counts"]
    assert data["total_skipped_profile_skill_references"] > 0
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "## Balance V2 PR9 Availability-aware Profile Policy Selection" in md
    assert "Profile policies now skip unavailable profile skills" in md
    assert "PR8 action-resolution and fallback attribution metadata remains intact" in md
    assert "PR6 remains 14/14" in md
    assert "PR5 remains 420" in md


def test_pr8_action_resolution_fields_remain_present_and_unlock_mastery_not_execution_gate():
    from game.combat_simulation import ScriptedActionPolicy, build_simulation_player_preset, make_simulation_skill_action

    player = build_simulation_player_preset(mana=120, max_mana=120, weapon_profile="bow", weapon_type="ranged")
    mob = build_simulation_mob_preset("forest_wolf")
    mob.update({"hp": 5000, "damage": 1, "damage_min": 1, "damage_max": 1, "accuracy": 1})
    result = simulate_single_combat(
        player,
        mob,
        policy=ScriptedActionPolicy([make_simulation_skill_action("steady_aim")]),
        config=SimulationConfig(seed=11, max_turns=1, skill_levels={"steady_aim": 2}, include_turn_trace=True),
    )
    row = result.turn_trace[0]
    for key in ("requested_action", "requested_skill_id", "resolved_action", "action_resolution_status", "fallback_reason", "skill_exists", "skill_level", "skill_unlock_mastery", "skill_visible", "cooldown_before", "mana_before", "mana_cost", "can_attempt_skill"):
        assert key in row
    assert row["action_resolution_status"] == "resolved_skill_success"
    assert row["skill_unlock_mastery"] > row["skill_level"]


def test_pr9_guard_counts_reports_and_metadata_registry():
    report = build_default_alpha_simulation_report_v2_data()
    pr6 = report["simulation_policy_skill_economy"]
    assert len(pr6["policy_coverage_rows"]) == 14
    assert len(pr6["skill_economy_rows"]) == 14
    assert len(build_unified_combat_budget_audit()["audit_rows"]) == 420
    for policy_id in METADATA_ONLY_POLICIES:
        assert EXECUTABLE_POLICY_REGISTRY[policy_id]["executable"] is False
    root = Path(__file__).resolve().parents[1]
    rendered = render_alpha_simulation_report_v2_markdown(report)
    assert (root / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md").read_text(encoding="utf-8") == rendered
    state = (root / "docs" / "PROJECT_STATE_CURRENT.md").read_text(encoding="utf-8")
    assert "Balance V2 PR9 Availability-aware Profile Policy Selection" in state
    assert "Status: Balance V2 PR9 Availability-aware Profile Policy Selection" in state
    assert "current merged main after Balance V2 PR9 Availability-aware Profile Policy Selection" in state
    assert "This PR did not change gameplay/balance diagnostic state; it stabilized the test baseline only." in state
    assert "This docs/workflow-only update did not change gameplay/balance diagnostic state." in state
