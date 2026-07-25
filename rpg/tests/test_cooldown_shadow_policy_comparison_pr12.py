from pathlib import Path

import pytest

import game.combat_simulation_report as report_module
from game.combat_simulation import (
    SIM_ACTION_NORMAL_ATTACK,
    SIMULATION_POLICY_CONTEXT_KEY,
    CooldownAwareShadowPolicy,
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
from game.combat_simulation_matrix import (
    COOLDOWN_AWARE_NEXT_READY_SKILL_POLICY_ID,
    COOLDOWN_AWARE_NORMAL_FALLBACK_POLICY_ID,
    PROFILE_POLICY_ACTIONS,
    RouteStageMatrixConfig,
    build_cooldown_shadow_policy,
    resolve_archetype_simulation_policy,
    run_cooldown_shadow_policy_comparison,
    run_route_stage_simulation_matrix,
)
from game.combat_simulation_report import (
    build_alpha_balance_report_data,
    build_default_alpha_simulation_report_v2_data,
    render_alpha_simulation_report_v2_markdown,
)


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


def _policy_state(*, hp=100, cooldowns=None, skill_levels=None, mana=100):
    return {
        "player_hp": hp,
        "player_max_hp": 100,
        SIMULATION_POLICY_CONTEXT_KEY: {
            "simulation_cooldowns": dict(cooldowns or {}),
            "skill_levels": dict(skill_levels or {}),
            "player_mana": mana,
        },
    }


def _shadow_policy(*, next_ready=False, low_hp_actions=None):
    return CooldownAwareShadowPolicy(
        [
            make_simulation_skill_action("sword_rush"),
            make_simulation_skill_action("power_strike"),
            SIM_ACTION_NORMAL_ATTACK,
        ],
        candidate_policy_id=(
            COOLDOWN_AWARE_NEXT_READY_SKILL_POLICY_ID
            if next_ready
            else COOLDOWN_AWARE_NORMAL_FALLBACK_POLICY_ID
        ),
        select_next_ready_skill=next_ready,
        low_hp_actions=low_hp_actions,
    )


@pytest.fixture(scope="module")
def report_data():
    return build_default_alpha_simulation_report_v2_data()


def test_existing_baseline_policy_action_selection_and_profile_actions_remain_unchanged():
    assert PROFILE_POLICY_ACTIONS == {
        "daggers_venom": ["envenom", "poison_blade", "toxic_cut", "rupture_toxins", "normal_attack"],
        "daggers_evasion": ["smoke_bomb", "feint_step", "quick_slice", "death_dance", "normal_attack"],
        "bow_sniper": ["hunters_mark", "steady_aim", "aimed_shot", "deadeye", "normal_attack"],
        "magic_staff_destruction": ["arcane_surge", "fireball", "flame_wave", "cataclysm", "normal_attack"],
        "holy_staff_solo": ["blessing", "smite", "normal_attack"],
    }
    resolved = resolve_archetype_simulation_policy("daggers_evasion", "build_testing")
    actions = [
        resolved["policy"].choose_action(
            turn=turn,
            battle_state={"player_hp": 100, "player_max_hp": 100},
        )
        for turn in range(1, 6)
    ]
    assert actions == [
        "skill:smoke_bomb",
        "skill:feint_step",
        "normal_attack",
        "skill:smoke_bomb",
        "skill:feint_step",
    ]


def test_temporary_simulation_policy_context_is_not_persisted():
    result = simulate_single_combat(
        build_simulation_player_preset(),
        build_simulation_mob_preset("forest_wolf"),
        config=SimulationConfig(seed=224, max_turns=1, skill_levels={"power_strike": 1}),
    )
    assert SIMULATION_POLICY_CONTEXT_KEY not in result.final_battle_state


def test_candidate_a_replaces_blocked_skill_with_normal_and_retains_ready_skill():
    policy = _shadow_policy()
    blocked = policy.choose_action(
        turn=1,
        battle_state=_policy_state(cooldowns={"sword_rush": 2}),
    )
    ready = _shadow_policy().choose_action(
        turn=1,
        battle_state=_policy_state(cooldowns={}),
    )
    assert blocked == SIM_ACTION_NORMAL_ATTACK
    assert ready == "skill:sword_rush"


def test_candidate_b_selects_next_ready_skill_or_normal_when_all_are_blocked():
    policy = _shadow_policy(next_ready=True)
    replacement = policy.choose_action(
        turn=1,
        battle_state=_policy_state(
            cooldowns={"sword_rush": 2},
            skill_levels={"sword_rush": 1, "power_strike": 1},
        ),
    )
    all_blocked = _shadow_policy(next_ready=True).choose_action(
        turn=1,
        battle_state=_policy_state(
            cooldowns={"sword_rush": 2, "power_strike": 1},
            skill_levels={"sword_rush": 1, "power_strike": 1},
        ),
    )
    assert replacement == "skill:power_strike"
    assert all_blocked == SIM_ACTION_NORMAL_ATTACK


def test_candidates_do_not_select_unavailable_profile_skills():
    candidate = build_cooldown_shadow_policy(
        "magic_staff_destruction",
        "build_testing",
        COOLDOWN_AWARE_NEXT_READY_SKILL_POLICY_ID,
    )
    assert "skill:cataclysm" not in candidate.actions
    assert "skill:flame_wave" not in candidate.actions
    for turn in range(1, 8):
        assert candidate.choose_action(
            turn=turn,
            battle_state=_policy_state(
                cooldowns={"arcane_surge": 3},
                skill_levels={"arcane_surge": 3, "fireball": 3},
            ),
        ) not in {"skill:cataclysm", "skill:flame_wave"}


def test_low_hp_next_ready_scan_remains_branch_local():
    policy = _shadow_policy(
        next_ready=True,
        low_hp_actions=[
            make_simulation_skill_action("heal"),
            make_simulation_skill_action("regeneration"),
            SIM_ACTION_NORMAL_ATTACK,
        ],
    )
    action = policy.choose_action(
        turn=1,
        battle_state=_policy_state(
            hp=40,
            cooldowns={"heal": 2},
            skill_levels={"heal": 1, "regeneration": 1},
        ),
    )
    assert action == "skill:regeneration"
    assert action not in policy.actions


def test_shadow_diagnostics_are_independent_of_capped_turn_trace():
    mob = build_simulation_mob_preset("forest_wolf")
    mob.update({"hp": 5000, "damage": 1, "damage_min": 1, "damage_max": 1, "accuracy": 1})
    policy = CooldownAwareShadowPolicy(
        [make_simulation_skill_action("sword_rush")],
        candidate_policy_id=COOLDOWN_AWARE_NORMAL_FALLBACK_POLICY_ID,
        select_next_ready_skill=False,
    )
    result = simulate_single_combat(
        build_simulation_player_preset(mana=200, max_mana=200),
        mob,
        policy=policy,
        config=SimulationConfig(
            seed=224,
            max_turns=4,
            skill_levels={"sword_rush": 1},
            include_turn_trace=True,
            max_trace_turns=1,
        ),
    )
    diagnostics = result.observability["shadow_policy_diagnostics"]
    assert len(result.turn_trace) == 1
    assert diagnostics["scheduled_action_count"] == 4
    assert diagnostics["scheduled_blocked_skill_count"] == 3
    assert diagnostics["proactive_normal_replacement_count"] == 3


def test_paired_runner_uses_identical_stable_scenario_identities():
    comparison = run_cooldown_shadow_policy_comparison(RouteStageMatrixConfig(
        route_ids=("route_westwild",),
        stages=("build_testing",),
        archetype_ids=tuple(sorted(PILOT_SET)),
        seeds=(1,),
        max_samples_per_route_stage=1,
        max_turns=50,
        include_turn_trace=False,
    ))
    assert comparison["scenario_pair_count"] == 5
    for pair in comparison["pairs"]:
        identity = pair["scenario_identity"]
        assert set(identity) == {"route", "stage", "archetype", "location", "mob", "seed"}
        assert pair["baseline"]["scenario_identity"] == identity
        assert pair["normal_fallback_candidate"]["scenario_identity"] == identity
        assert pair["next_ready_candidate"]["scenario_identity"] == identity


def _narrow_comparison_config():
    return RouteStageMatrixConfig(
        route_ids=("route_westwild",),
        stages=("build_testing",),
        archetype_ids=tuple(sorted(PILOT_SET)),
        seeds=(1,),
        max_samples_per_route_stage=1,
        max_turns=50,
        include_turn_trace=False,
    )


def test_supplied_narrow_matrix_and_matching_config_keep_pr12_scope_narrow():
    config = _narrow_comparison_config()
    matrix = run_route_stage_simulation_matrix(config)
    data = build_alpha_balance_report_data(
        matrix_result=matrix,
        config=config,
    )["pr12_cooldown_shadow_policy_comparison"]
    assert data["available"] is True
    assert data["scope_alignment_status"] == "aligned"
    assert data["comparison_config_source"] == "explicit_matching_config"
    assert data["unavailable_reason"] is None
    assert data["scenario_pair_count"] == 5


def test_supplied_matrix_without_config_does_not_launch_default_shadow_comparison(monkeypatch):
    matrix = run_route_stage_simulation_matrix(_narrow_comparison_config())

    def fail_if_called(_config):
        raise AssertionError("default PR12 shadow comparison must not run")

    monkeypatch.setattr(report_module, "run_cooldown_shadow_policy_comparison", fail_if_called)
    data = build_alpha_balance_report_data(
        matrix_result=matrix,
    )["pr12_cooldown_shadow_policy_comparison"]
    assert data["available"] is False
    assert data["scope_alignment_status"] == "unavailable"
    assert data["comparison_config_source"] == "none"
    assert data["unavailable_reason"] == "matching_matrix_config_required"
    assert data["scenario_pair_count"] == 0


def test_mismatched_explicit_config_cannot_produce_available_comparison(monkeypatch):
    matrix = run_route_stage_simulation_matrix(_narrow_comparison_config())
    mismatched_config = RouteStageMatrixConfig(
        route_ids=("route_frostspine",),
        stages=("build_testing",),
        archetype_ids=tuple(sorted(PILOT_SET)),
        seeds=(1,),
        max_samples_per_route_stage=1,
        max_turns=50,
        include_turn_trace=False,
    )

    def fail_if_called(_config):
        raise AssertionError("mismatched PR12 shadow comparison must not run")

    monkeypatch.setattr(report_module, "run_cooldown_shadow_policy_comparison", fail_if_called)
    data = build_alpha_balance_report_data(
        matrix_result=matrix,
        config=mismatched_config,
    )["pr12_cooldown_shadow_policy_comparison"]
    assert data["available"] is False
    assert data["scope_alignment_status"] == "mismatch"
    assert data["comparison_config_source"] == "explicit_config"
    assert data["unavailable_reason"] == "matrix_config_scope_mismatch"
    assert "routes" in data["scope_mismatches"]
    assert data["scenario_pair_count"] == 0


def test_checked_in_pr12_comparison_has_candidate_a_full_parity(report_data):
    data = report_data["pr12_cooldown_shadow_policy_comparison"]
    assert data["available"] is True
    assert data["scope_alignment_status"] == "aligned"
    assert data["comparison_config_source"] == "generated_matrix_config"
    assert data["unavailable_reason"] is None
    assert data["normal_fallback_parity_pair_count"] == data["scenario_pair_count"] == 100
    assert data["normal_fallback_parity_mismatch_count"] == 0
    assert data["normal_fallback_parity_mismatches"] == []


def test_pr12_report_data_and_checked_in_markdown_preserve_prior_guards(report_data):
    data = report_data["pr12_cooldown_shadow_policy_comparison"]
    assert data["blocked_skill_counts"] == {
        "hunters_mark": 16,
        "poison_blade": 1,
        "smite": 25,
        "smoke_bomb": 19,
    }
    assert data["normal_replacement_counts"] == {"normal_attack": 61}
    assert data["next_ready_replacement_skill_counts"] == {"feint_step": 12, "smoke_bomb": 8}
    assert data["recommended_next_investigation"] == "consider_cooldown_aware_normal_request_suppression_only"

    markdown = render_alpha_simulation_report_v2_markdown(report_data)
    for section in (
        "## Balance V2 PR12 Cooldown-Aware Shadow Policy Comparison",
        "## Balance V2 PR11 Cooldown & Mana Policy Cause Attribution",
        "## Balance V2 PR10 Cooldown Fallback Diagnostic Breakdown",
        "## Balance V2 PR9 Availability-aware Profile Policy Selection",
        "## Balance V2 PR8 Simulation Action Resolution / Fallback Attribution",
    ):
        assert section in markdown
    root = Path(__file__).resolve().parents[1]
    assert (root / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md").read_text(encoding="utf-8") == markdown

    assert report_data["post_pr10_policy_pressure_diagnostics"]["skill_locked_or_unleveled_count"] == 0
    assert set(PROFILE_POLICY_PILOT_ARCHETYPE_IDS) == PILOT_SET
    assert len(report_data["simulation_policy_skill_economy"]["policy_coverage_rows"]) == 14
    assert len(report_data["simulation_policy_skill_economy"]["skill_economy_rows"]) == 14
    assert len(report_data["unified_combat_budget_audit"]["audit_rows"]) == 420
    for policy_id in METADATA_ONLY_POLICIES:
        assert EXECUTABLE_POLICY_REGISTRY[policy_id]["executable"] is False


def test_project_state_marks_pr12_latest_and_preserves_pr11_through_pr8():
    state = (
        Path(__file__).resolve().parents[1] / "docs" / "PROJECT_STATE_CURRENT.md"
    ).read_text(encoding="utf-8")
    assert "Latest gameplay/balance diagnostic state: PR224 / Balance V2 PR12 Cooldown-Aware Shadow Policy Comparison" in state
    assert "PR223 / Balance V2 PR11 Cooldown & Mana Policy Cause Attribution" in state
    assert "PR221 / Balance V2 PR10 Cooldown Fallback Diagnostic Breakdown" in state
    assert "Balance V2 PR9 Availability-aware Profile Policy Selection" in state
    assert "Balance V2 PR8 Simulation Action Resolution / Fallback Attribution" in state
    assert "PR218 Test Suite Baseline Stabilization / SQLite Runtime Test Isolation" in state
