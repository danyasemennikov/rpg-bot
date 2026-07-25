from pathlib import Path

import pytest

from game.combat_simulation import (
    SIM_ACTION_NORMAL_ATTACK,
    SIMULATION_POLICY_CONTEXT_KEY,
    CooldownAwareShadowPolicy,
)
from game.combat_simulation_archetypes import (
    EXECUTABLE_POLICY_REGISTRY,
    PROFILE_POLICY_PILOT_ARCHETYPE_IDS,
)
from game.combat_simulation_matrix import (
    PROFILE_POLICY_ACTIONS,
    resolve_archetype_simulation_policy,
)
from game.combat_simulation_report import (
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


def _policy_state(*, hp=100, cooldowns=None, mana=100):
    return {
        "player_hp": hp,
        "player_max_hp": 100,
        SIMULATION_POLICY_CONTEXT_KEY: {
            "simulation_cooldowns": dict(cooldowns or {}),
            "player_mana": mana,
        },
    }


@pytest.fixture(scope="module")
def report_data():
    return build_default_alpha_simulation_report_v2_data()


def test_active_pilot_policy_keeps_ready_skill_and_suppresses_only_cooldown():
    policy = resolve_archetype_simulation_policy("daggers_evasion", "build_testing")["policy"]

    assert policy.choose_action(turn=1, battle_state=_policy_state()) == "skill:smoke_bomb"
    assert policy.choose_action(
        turn=1,
        battle_state=_policy_state(cooldowns={"smoke_bomb": 2}),
    ) == SIM_ACTION_NORMAL_ATTACK


def test_ready_but_unaffordable_skill_remains_requested_for_mana_diagnostics():
    policy = resolve_archetype_simulation_policy("daggers_evasion", "build_testing")["policy"]

    assert policy.choose_action(
        turn=1,
        battle_state=_policy_state(mana=0),
    ) == "skill:smoke_bomb"


def test_low_hp_branch_uses_the_same_cooldown_only_suppression():
    policy = resolve_archetype_simulation_policy("holy_staff_solo", "build_testing")["policy"]

    assert policy.choose_action(
        turn=1,
        battle_state=_policy_state(hp=20, mana=0),
    ) == "skill:heal"
    assert policy.choose_action(
        turn=1,
        battle_state=_policy_state(hp=20, cooldowns={"heal": 2}),
    ) == SIM_ACTION_NORMAL_ATTACK


def test_candidate_b_stays_inactive_and_five_pilot_scope_is_exact():
    assert set(PROFILE_POLICY_PILOT_ARCHETYPE_IDS) == PILOT_SET
    assert set(PROFILE_POLICY_ACTIONS) == PILOT_SET
    for archetype_id in PILOT_SET:
        policy = resolve_archetype_simulation_policy(archetype_id, "build_testing")["policy"]
        assert not isinstance(policy, CooldownAwareShadowPolicy)
        assert not hasattr(policy, "select_next_ready_skill")


def test_metadata_only_policies_remain_non_executable():
    for policy_id in METADATA_ONLY_POLICIES:
        assert EXECUTABLE_POLICY_REGISTRY[policy_id]["executable"] is False


def test_default_report_confirms_pr13_adoption_and_exact_pr12_parity(report_data):
    data = report_data["pr13_cooldown_aware_normal_suppression"]
    assert set(data["pilot_archetypes"]) == PILOT_SET
    assert data["candidate_a_adopted"] is True
    assert data["candidate_b_active"] is False
    assert data["historical_scenario_pair_count"] == 100
    assert data["historical_parity_mismatch_count"] == 0
    assert data["outcome_and_final_state_parity"] is True
    assert data["previous_cooldown_fallback_count"] == 61
    assert data["explicit_policy_normal_attack_count"] == 61
    assert data["active_cooldown_fallback_count"] == 0
    assert data["insufficient_mana_fallback_count"] == 4
    assert data["diagnostic_branch_status"] == "closed_unless_regression_blocker"


def test_default_report_is_deterministic_and_checked_in_markdown_matches(report_data):
    second = build_default_alpha_simulation_report_v2_data()
    assert second["pr13_cooldown_aware_normal_suppression"] == (
        report_data["pr13_cooldown_aware_normal_suppression"]
    )
    rendered = render_alpha_simulation_report_v2_markdown(report_data)
    report_path = Path(__file__).resolve().parents[1] / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md"
    assert report_path.read_text(encoding="utf-8") == rendered


def test_project_state_marks_pr225_latest_and_preserves_required_history():
    state = (
        Path(__file__).resolve().parents[1] / "docs" / "PROJECT_STATE_CURRENT.md"
    ).read_text(encoding="utf-8")
    assert "PR225 / Balance V2 PR13 Cooldown-Aware Normal Request Suppression" in state
    for marker in (
        "PR224 / Balance V2 PR12 Cooldown-Aware Shadow Policy Comparison",
        "PR223 / Balance V2 PR11 Cooldown & Mana Policy Cause Attribution",
        "PR221 / Balance V2 PR10 Cooldown Fallback Diagnostic Breakdown",
        "Balance V2 PR9 Availability-aware Profile Policy Selection",
        "Balance V2 PR8 Simulation Action Resolution / Fallback Attribution",
        "Balance V2 PR7",
        "Balance V2 PR6",
        "Balance V2 PR5",
        "PR218 Test Suite Baseline Stabilization / SQLite Runtime Test Isolation",
    ):
        assert marker in state
