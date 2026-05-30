from pathlib import Path

from game.combat_simulation_archetypes import (
    EXECUTABLE_POLICY_REGISTRY,
    get_expected_rotation_profile,
    list_alpha_archetype_ids,
    list_expected_rotation_profiles,
)
from game.combat_simulation_report import (
    build_alpha_balance_report_data,
    render_alpha_simulation_report_v2_markdown,
)
from game.mob_scaling import PR3_LATE_STAGE_MOB_PRESSURE_REFINEMENTS
from game.skills import get_skill


def _report():
    return build_alpha_balance_report_data()


def test_expected_rotation_profiles_exist_for_pr6_target_archetypes():
    for archetype_id in (
        "daggers_venom",
        "bow_sniper",
        "magic_staff_destruction",
        "holy_staff_solo",
        "axe_2h_bruiser",
        "daggers_evasion",
    ):
        profile = get_expected_rotation_profile(archetype_id)
        assert profile is not None
        assert profile["archetype_id"] == archetype_id
        assert profile["profile_id"]
        assert profile["rotation_family"]
        assert isinstance(profile["expected_skill_ids"], list)
        assert isinstance(profile["setup_skill_ids"], list)
        assert isinstance(profile["payoff_skill_ids"], list)
        assert isinstance(profile["sustain_skill_ids"], list)
        assert isinstance(profile["mana_sensitive"], bool)
        assert isinstance(profile["cooldown_sensitive"], bool)
        assert profile["notes"]


def test_expected_rotation_profile_skill_ids_are_implemented():
    for profile in list_expected_rotation_profiles():
        skill_ids = set(profile["expected_skill_ids"])
        skill_ids.update(profile["setup_skill_ids"])
        skill_ids.update(profile["payoff_skill_ids"])
        skill_ids.update(profile["sustain_skill_ids"])
        missing = sorted(skill_id for skill_id in skill_ids if not get_skill(skill_id))
        assert missing == []


def test_holy_staff_solo_uses_current_smite_payoff_without_missing_skill_gap():
    profile = get_expected_rotation_profile("holy_staff_solo")
    assert profile["expected_skill_ids"] == ["regeneration", "blessing", "heal", "smite"]
    assert profile["setup_skill_ids"] == ["blessing"]
    assert profile["payoff_skill_ids"] == ["smite"]
    assert profile["sustain_skill_ids"] == ["regeneration", "heal"]

    rows = {row["archetype_id"]: row for row in _report()["simulation_policy_skill_economy"]["policy_coverage_rows"]}
    holy_staff = rows["holy_staff_solo"]
    assert holy_staff["missing_expected_skill_ids"] == []
    assert "missing_expected_skill" not in holy_staff["artifact_reasons"]


def test_policy_coverage_rows_include_all_14_alpha_archetypes():
    pr6 = _report()["simulation_policy_skill_economy"]
    rows = pr6["policy_coverage_rows"]
    assert pr6["available"] is True
    assert len(rows) == 14
    assert {row["archetype_id"] for row in rows} == set(list_alpha_archetype_ids())


def test_metadata_only_policies_are_classified_separately_from_executable_policies():
    rows = {row["archetype_id"]: row for row in _report()["simulation_policy_skill_economy"]["policy_coverage_rows"]}
    assert rows["axe_2h_bruiser"]["policy_status"] == "executable"
    assert rows["axe_2h_bruiser"]["policy_executable"] is True
    assert rows["daggers_venom"]["policy_status"] == "metadata_only"
    assert rows["daggers_venom"]["policy_executable"] is False
    assert "metadata_only_policy" in rows["daggers_venom"]["artifact_reasons"]


def test_missing_expected_skills_are_reported_without_crashing(monkeypatch):
    import game.combat_simulation_report as report_module

    original_get_skill = report_module.get_skill

    def fake_get_skill(skill_id):
        if skill_id == "poison_blade":
            return None
        return original_get_skill(skill_id)

    monkeypatch.setattr(report_module, "get_skill", fake_get_skill)
    data = report_module.build_alpha_balance_report_data()["simulation_policy_skill_economy"]
    venom = next(row for row in data["policy_coverage_rows"] if row["archetype_id"] == "daggers_venom")
    assert "poison_blade" in venom["missing_expected_skill_ids"]
    assert "missing_expected_skill" in venom["artifact_reasons"]


def test_skill_economy_summary_exists_in_report_data():
    pr6 = _report()["simulation_policy_skill_economy"]
    rows = pr6["skill_economy_rows"]
    assert len(rows) == 14
    sample = rows[0]
    for key in (
        "mana_spent",
        "player_mana_remaining_pct",
        "skills_used_count",
        "normal_attacks_used",
        "guard_used",
        "damage_dealt_per_turn",
        "damage_taken_per_turn",
        "end_reason",
        "skill_use_rate",
        "normal_attack_fallback_rate",
        "mana_pressure_label",
        "skill_economy_label",
        "cooldown_observability_available",
    ):
        assert key in sample
    assert all(row["cooldown_observability_available"] is False for row in rows)


def test_markdown_pr6_section_and_non_goal_wording_exists():
    md = render_alpha_simulation_report_v2_markdown(_report())
    assert "## Balance V2 PR6 Simulation Policy & Skill Economy Clarification" in md
    assert "Diagnostic-only" in md
    assert "no live tuning" in md
    assert "No live gameplay/runtime/formula/equipment/live mob/economy/targeting/teleport/live group combat changes" in md
    assert "PR6 separates simulation policy artifacts from real skill economy risks" in md


def test_pvp_remains_proxy_only_and_tuning_remains_deferred():
    report = _report()
    pvp = report["unified_combat_budget_audit"]["pvp_budget_proxy_summary"]
    assert pvp["proxy_only"] is True
    assert pvp["real_duel_win_rates"] is False
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "PvP remains proxy-only" in md
    assert "route/mob/gear/PvP tuning remains deferred" in md


def test_pr5_audit_remains_420_rows():
    audit = _report()["unified_combat_budget_audit"]
    assert len(audit["audit_rows"]) == 420
    assert len({row["archetype_id"] for row in audit["audit_rows"]}) == 14
    assert len(audit["level_bands"]) == 6
    assert len(audit["gear_states"]) == 5


def test_no_pr3_pr4_tuning_knobs_changed_and_no_pr6_tuning_knobs_added():
    assert "pr6" not in " ".join(str(key) for key in PR3_LATE_STAGE_MOB_PRESSURE_REFINEMENTS.keys()).lower()
    assert all("pr6" not in key.lower() for key in EXECUTABLE_POLICY_REGISTRY)
    assert EXECUTABLE_POLICY_REGISTRY["aggressive_burst"]["executable"] is False
    assert EXECUTABLE_POLICY_REGISTRY["venom_setup"]["executable"] is False
    assert EXECUTABLE_POLICY_REGISTRY["sniper_precision"]["executable"] is False
    assert EXECUTABLE_POLICY_REGISTRY["solo_support_sustain"]["executable"] is False
    assert EXECUTABLE_POLICY_REGISTRY["evasion_tempo"]["executable"] is False


def test_policy_review_labels_are_semantically_narrow():
    rows = {row["archetype_id"]: row for row in _report()["simulation_policy_skill_economy"]["policy_coverage_rows"]}
    assert "burst_window_policy_review" not in rows["holy_staff_solo"]["artifact_reasons"]
    assert "support_solo_policy_review" in rows["holy_staff_solo"]["artifact_reasons"]
    assert "sustain_timing_policy_unknown" in rows["holy_staff_solo"]["artifact_reasons"]
    assert "burst_window_policy_review" in rows["sword_2h_burst"]["artifact_reasons"]
    assert "burst_window_policy_review" in rows["bow_sniper"]["artifact_reasons"]
    assert "burst_window_policy_review" in rows["magic_staff_destruction"]["artifact_reasons"]


def test_project_state_current_has_pr6_update():
    project_root = Path(__file__).resolve().parents[1]
    text = (project_root / "docs" / "PROJECT_STATE_CURRENT.md").read_text(encoding="utf-8")
    assert "Balance V2 PR6" in text
    assert "Simulation Policy & Skill Economy Clarification" in text
    assert "diagnostic/reporting-only" in text
