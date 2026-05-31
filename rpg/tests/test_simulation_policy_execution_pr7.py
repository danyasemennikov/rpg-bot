from pathlib import Path

from game.combat_simulation import SimulationConfig, build_simulation_mob_preset, simulate_single_combat
from game.combat_simulation_archetypes import (
    EXECUTABLE_POLICY_REGISTRY,
    PROFILE_POLICY_PILOT_ARCHETYPE_IDS,
    build_archetype_player_preset,
    build_archetype_simulation_skill_levels,
    get_expected_rotation_profile,
    list_alpha_archetype_ids,
)
from game.combat_simulation_matrix import resolve_archetype_simulation_policy
from game.combat_simulation_report import build_alpha_balance_report_data, render_alpha_simulation_report_v2_markdown
from game.skills import get_skill
from game.unified_combat_budget_audit import build_unified_combat_budget_audit

PILOT_ARCHETYPES = set(PROFILE_POLICY_PILOT_ARCHETYPE_IDS)
METADATA_ONLY_POLICIES = {
    "aggressive_burst",
    "venom_setup",
    "evasion_tempo",
    "sniper_precision",
    "control_caster",
    "solo_support_sustain",
    "toolbox_balanced",
}


def test_pilot_archetypes_resolve_to_profile_executable_pilot_status():
    for archetype_id in PILOT_ARCHETYPES:
        resolved = resolve_archetype_simulation_policy(archetype_id, "build_testing")
        assert resolved["active_simulation_policy_status"] == "profile_executable_pilot"
        assert resolved["profile_policy_executable"] is True
        assert resolved["profile_policy_pilot"] is True


def test_non_pilot_metadata_only_policies_remain_metadata_fallback():
    for archetype_id in (set(list_alpha_archetype_ids()) - PILOT_ARCHETYPES):
        resolved = resolve_archetype_simulation_policy(archetype_id, "build_testing")
        if resolved["registry_policy_id"] in METADATA_ONLY_POLICIES:
            assert resolved["active_simulation_policy_status"] == "metadata_only_fallback"
            assert resolved["profile_policy_executable"] is False
            assert resolved["profile_policy_pilot"] is False


def test_metadata_only_registry_entries_remain_not_executable():
    for policy_id in METADATA_ONLY_POLICIES:
        assert EXECUTABLE_POLICY_REGISTRY[policy_id]["executable"] is False


def test_pilot_simulation_skill_levels_respect_stage_unlock_mastery():
    stage_level = 3
    for archetype_id in PILOT_ARCHETYPES:
        levels = build_archetype_simulation_skill_levels(archetype_id, "build_testing")
        assert levels
        for skill_id, skill_level in levels.items():
            skill_def = get_skill(skill_id)
            assert skill_def, skill_id
            assert stage_level >= int(skill_def.get("unlock_mastery", 1) or 1), skill_id
            assert skill_level == stage_level


def test_late_capstones_are_not_available_at_build_testing():
    blocked_at_build_testing = {
        "daggers_venom": {"rupture_toxins"},
        "bow_sniper": {"deadeye", "steady_aim"},
        "magic_staff_destruction": {"cataclysm", "flame_wave"},
        "holy_staff_solo": {"blessing"},
    }
    for archetype_id, blocked_skills in blocked_at_build_testing.items():
        levels = build_archetype_simulation_skill_levels(archetype_id, "build_testing")
        assert blocked_skills.isdisjoint(levels), archetype_id


def test_profile_policy_may_request_locked_skills_but_simulation_falls_back():
    levels = build_archetype_simulation_skill_levels("magic_staff_destruction", "build_testing")
    assert "cataclysm" not in levels
    policy = resolve_archetype_simulation_policy("magic_staff_destruction", "build_testing")["policy"]
    assert policy.choose_action(turn=4, battle_state={"player_hp": 100, "player_max_hp": 100}) == "skill:cataclysm"

    player = build_archetype_player_preset("magic_staff_destruction", "build_testing")
    mob = build_simulation_mob_preset("forest_wolf")
    mob.update({"hp": 5000, "damage": 1, "damage_min": 1, "damage_max": 1})
    result = simulate_single_combat(
        player,
        mob,
        policy=policy,
        config=SimulationConfig(seed=7, max_turns=4, skill_levels=levels, include_turn_trace=True),
    )
    turn_four = result.turn_trace[3]
    assert turn_four["chosen_action"] == "skill:cataclysm"
    assert turn_four["resolved_action"] == "normal_attack"


def test_pilot_simulations_show_visible_skill_use_not_only_normal_attacks():
    mob = build_simulation_mob_preset("forest_wolf")
    mob.update({"hp": 250, "damage": 1, "damage_min": 1, "damage_max": 1})
    for archetype_id in PILOT_ARCHETYPES:
        player = build_archetype_player_preset(archetype_id, "build_testing")
        levels = build_archetype_simulation_skill_levels(archetype_id, "build_testing")
        resolved = resolve_archetype_simulation_policy(archetype_id, "build_testing")
        result = simulate_single_combat(
            player,
            mob,
            policy=resolved["policy"],
            config=SimulationConfig(seed=7, max_turns=8, skill_levels=levels),
        )
        assert result.skills_used, archetype_id
        assert any(action.startswith("skill:") and count > 0 for action, count in result.actions_used.items()), archetype_id


def test_holy_staff_solo_policy_prefers_sustain_at_or_below_55_percent_hp():
    resolved = resolve_archetype_simulation_policy("holy_staff_solo", "build_testing")
    action = resolved["policy"].choose_action(
        turn=1,
        battle_state={"player_hp": 55, "player_max_hp": 100, "mob_hp": 100},
    )
    assert action in {"skill:heal", "skill:regeneration"}


def test_pr6_policy_coverage_and_skill_economy_counts_remain_14():
    pr6 = build_alpha_balance_report_data()["simulation_policy_skill_economy"]
    assert len(pr6["policy_coverage_rows"]) == 14
    assert len(pr6["skill_economy_rows"]) == 14


def test_pr5_audit_remains_420_rows():
    audit = build_unified_combat_budget_audit()
    assert len(audit["audit_rows"]) == 14 * 6 * 5


def test_report_rows_include_pr7_active_policy_fields():
    rows = {
        row["archetype_id"]: row
        for row in build_alpha_balance_report_data()["simulation_policy_skill_economy"]["policy_coverage_rows"]
    }
    for archetype_id in PILOT_ARCHETYPES:
        assert rows[archetype_id]["active_simulation_policy_status"] == "profile_executable_pilot"
        assert rows[archetype_id]["profile_policy_pilot"] is True
    assert rows["sword_2h_burst"]["policy_status"] == "metadata_only"
    assert rows["sword_2h_burst"]["active_simulation_policy_status"] == "metadata_only_fallback"


def test_pr7_markdown_section_exists_and_states_no_live_tuning():
    md = render_alpha_simulation_report_v2_markdown(build_alpha_balance_report_data())
    assert "## Balance V2 PR7 Profile-aware Simulation Policy Execution Pilot" in md
    assert "Diagnostic/simulation-only" in md
    assert "no live tuning" in md
    assert "Metadata-only registry policies were not globally flipped" in md
    assert "PR5 audit remains 420 rows" in md
    assert "PvP remains proxy-only" in md


def test_project_state_current_has_pr7_update_in_latest_header_and_confirmed_state():
    project_root = Path(__file__).resolve().parents[1]
    text = (project_root / "docs" / "PROJECT_STATE_CURRENT.md").read_text(encoding="utf-8")
    header = text.split("---", 1)[0]
    confirmed = text.split("## Confirmed merged state", 1)[1].split("### Balance V2 PR6", 1)[0]
    update_policy = text.split("## Update policy", 1)[1]

    assert "Balance V2 PR7 Profile-aware Simulation Policy Execution Pilot" in header
    assert "Balance V2 PR7 Profile-aware Simulation Policy Execution Pilot" in confirmed
    assert "Diagnostic/simulation-only pilot" in confirmed
    assert "Balance V2 PR7 Profile-aware Simulation Policy Execution Pilot" not in update_policy
