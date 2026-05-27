from copy import deepcopy

from game.balance_audit import (
    BalanceAuditFlag,
    FLAG_MISSING_ENCOUNTER_LEVEL,
    FLAG_INVALID_NODE_DEPTH,
    FLAG_MISSING_MOB_ROLE,
    FLAG_MISSING_SIMULATION_GEAR_PRESET,
    FLAG_MISSING_MOB_SCALING_CONTEXT,
    FLAG_MISSING_FINAL_MOB_STATS,
    FLAG_POLICY_FAILURE_GUARD_LOOP,
    FLAG_UNSCALED_TEMPLATE_REUSED_ACROSS_DEPTHS,
    FLAG_WEAK_ROUTE_EXAM_SAMPLE,
    audit_progression_context_rows,
    audit_repeated_template_depth_scaling,
    audit_route_stage_sample_metadata,
    build_balance_audit_flag,
    summarize_balance_audit_flags,
)


def test_build_flag_returns_structured_dataclass():
    flag = build_balance_audit_flag(
        flag_id="missing_encounter_level",
        severity="warning",
        subject_type="sample_row",
        subject_id="row_1",
        message="missing",
        metadata={"k": "v"},
    )
    assert isinstance(flag, BalanceAuditFlag)
    assert flag.flag_id == "missing_encounter_level"
    assert flag.metadata == {"k": "v"}


def test_missing_encounter_and_mob_role_are_flagged():
    rows = [{"sample_id": "s1", "stage": "soft_entry", "balance_level": 5}]
    flags = audit_route_stage_sample_metadata(rows)
    flag_ids = {f.flag_id for f in flags}
    assert FLAG_MISSING_ENCOUNTER_LEVEL in flag_ids
    assert FLAG_MISSING_MOB_ROLE in flag_ids


def test_weak_route_exam_sample_is_flagged_when_no_pressure_or_elite_roles():
    rows = [
        {
            "sample_id": "s1",
            "stage": "route_exam",
            "balance_level": 70,
            "encounter_level": 70,
            "mob_role": "normal",
        }
    ]
    flags = audit_route_stage_sample_metadata(rows)
    assert any(f.flag_id == FLAG_WEAK_ROUTE_EXAM_SAMPLE for f in flags)


def test_unscaled_template_reused_across_depths_can_be_flagged():
    rows = [
        {
            "mob_template": "forest_boar",
            "node_depth": 2,
            "encounter_level": 20,
            "final_hp": 120,
            "final_attack": 18,
            "final_defense": 8,
        },
        {
            "mob_template": "forest_boar",
            "node_depth": 7,
            "encounter_level": 20,
            "final_hp": 120,
            "final_attack": 18,
            "final_defense": 8,
        },
    ]
    flags = audit_repeated_template_depth_scaling(rows)
    assert any(f.flag_id == FLAG_UNSCALED_TEMPLATE_REUSED_ACROSS_DEPTHS for f in flags)


def test_audit_functions_do_not_mutate_input_rows():
    rows = [
        {"sample_id": "s1", "stage": "soft_entry", "balance_level": 1},
        {
            "mob_template": "slime",
            "node_depth": 1,
            "encounter_level": 1,
            "final_hp": 10,
            "final_attack": 2,
            "final_defense": 1,
        },
    ]
    rows_before = deepcopy(rows)

    audit_route_stage_sample_metadata(rows)
    audit_repeated_template_depth_scaling(rows)

    assert rows == rows_before


def test_non_numeric_node_depth_does_not_raise():
    rows = [
        {
            "sample_id": "bad_depth",
            "mob_template": "forest_boar",
            "node_depth": "N7",
            "encounter_level": 20,
            "final_hp": 120,
            "final_attack": 18,
            "final_defense": 8,
        }
    ]

    flags = audit_repeated_template_depth_scaling(rows)
    assert isinstance(flags, list)


def test_valid_rows_still_audited_when_malformed_depth_row_exists():
    rows = [
        {
            "sample_id": "good_1",
            "mob_template": "forest_boar",
            "node_depth": 2,
            "encounter_level": 20,
            "final_hp": 120,
            "final_attack": 18,
            "final_defense": 8,
        },
        {
            "sample_id": "bad_depth",
            "mob_template": "forest_boar",
            "node_depth": "depth_5",
            "encounter_level": 20,
            "final_hp": 120,
            "final_attack": 18,
            "final_defense": 8,
        },
        {
            "sample_id": "good_2",
            "mob_template": "forest_boar",
            "node_depth": 7,
            "encounter_level": 20,
            "final_hp": 120,
            "final_attack": 18,
            "final_defense": 8,
        },
    ]

    flags = audit_repeated_template_depth_scaling(rows)
    flag_ids = {f.flag_id for f in flags}
    assert FLAG_UNSCALED_TEMPLATE_REUSED_ACROSS_DEPTHS in flag_ids


def test_invalid_node_depth_is_flagged_when_non_empty_and_non_numeric():
    rows = [
        {
            "sample_id": "bad_depth",
            "mob_template": "forest_boar",
            "node_depth": "unknown",
            "encounter_level": 20,
            "final_hp": 120,
            "final_attack": 18,
            "final_defense": 8,
        }
    ]

    flags = audit_repeated_template_depth_scaling(rows)
    assert any(f.flag_id == FLAG_INVALID_NODE_DEPTH for f in flags)


def test_summarize_balance_audit_flags_counts():
    flags = [
        build_balance_audit_flag("a", "warning", "x", "1", "m"),
        build_balance_audit_flag("a", "warning", "x", "2", "m"),
        build_balance_audit_flag("b", "warning", "x", "3", "m"),
    ]
    assert summarize_balance_audit_flags(flags) == {"a": 2, "b": 1}


def test_audit_progression_context_rows_flags_and_no_mutation():
    rows = [{"id": "r1", "stage": "route_exam", "assumed_player_level": 95, "target_label": "hard", "mob_role": None, "gear_rarity_assumption": "rare", "enhancement_assumption": 8, "assumption_status": "formula_budget_v1", "simulation_gear_preset": {"total_budget": 100, "slot_budgets": {"weapon": 10}, "stat_bonuses": {"max_hp_bonus": 1}}, "observed_diagnostic_label_v2": "policy_failure", "actions_used": {"guard_fallback": 5}}]
    before = deepcopy(rows)
    flags = audit_progression_context_rows(rows)
    ids = {f.flag_id for f in flags}
    assert FLAG_MISSING_ENCOUNTER_LEVEL in ids
    assert FLAG_MISSING_MOB_ROLE in ids
    assert FLAG_MISSING_SIMULATION_GEAR_PRESET not in ids
    assert FLAG_POLICY_FAILURE_GUARD_LOOP in ids
    assert rows == before


def test_audit_progression_context_rows_malformed_optional_values_do_not_raise():
    rows = [{"id": "bad_optional", "stage": 123, "assumed_player_level": "", "encounter_level": "", "actions_used": "not_a_dict"}]
    flags = audit_progression_context_rows(rows)
    assert isinstance(flags, list)


def test_audit_progression_context_rows_non_numeric_guard_values_do_not_raise():
    rows = [{
        "id": "bad_guard_values",
        "stage": "route_exam",
        "assumed_player_level": 95,
        "encounter_level": 95,
        "mob_role": "normal",
        "observed_diagnostic_label_v2": "policy_failure",
        "actions_used": {"guard_fallback": "N/A", "guard": "five"},
        "guard_action_rate": "not-a-number",
    }]
    flags = audit_progression_context_rows(rows)
    assert isinstance(flags, list)


def test_audit_progression_context_rows_numeric_string_guard_fallback_flags_guard_loop():
    rows = [{
        "id": "guard_string_numeric",
        "stage": "route_exam",
        "assumed_player_level": 95,
        "encounter_level": 95,
        "mob_role": "normal",
        "observed_diagnostic_label_v2": "policy_failure",
        "actions_used": {"guard_fallback": "3", "guard": "0"},
    }]
    flags = audit_progression_context_rows(rows)
    assert any(f.flag_id == FLAG_POLICY_FAILURE_GUARD_LOOP for f in flags)


def test_audit_progression_context_rows_malformed_guard_action_rate_does_not_raise():
    rows = [{
        "id": "bad_guard_rate",
        "stage": "route_exam",
        "assumed_player_level": 95,
        "encounter_level": 95,
        "mob_role": "normal",
        "observed_diagnostic_label_v2": "policy_failure",
        "actions_used": {},
        "guard_action_rate": {"bad": "shape"},
    }]
    flags = audit_progression_context_rows(rows)
    assert isinstance(flags, list)


def test_audit_progression_context_rows_formula_status_without_preset_is_flagged():
    rows = [{"id": "r2", "stage": "route_exam", "assumed_player_level": 95, "encounter_level": 95, "mob_role": "normal", "gear_rarity_assumption": "rare", "enhancement_assumption": 8, "assumption_status": "formula_budget_v1"}]
    flags = audit_progression_context_rows(rows)
    assert any(f.flag_id == FLAG_MISSING_SIMULATION_GEAR_PRESET for f in flags)


def test_audit_progression_context_rows_formula_status_empty_preset_is_flagged():
    rows = [{"id": "r3", "stage": "route_exam", "assumed_player_level": 95, "encounter_level": 95, "mob_role": "normal", "gear_rarity_assumption": "rare", "enhancement_assumption": 8, "assumption_status": "formula_budget_v1", "simulation_gear_preset": {}}]
    flags = audit_progression_context_rows(rows)
    assert any(f.flag_id == FLAG_MISSING_SIMULATION_GEAR_PRESET for f in flags)


def test_audit_progression_context_rows_formula_status_valid_preset_not_flagged():
    rows = [{"id": "r4", "stage": "route_exam", "assumed_player_level": 95, "encounter_level": 95, "mob_role": "normal", "gear_rarity_assumption": "rare", "enhancement_assumption": 8, "assumption_status": "formula_budget_v1", "simulation_gear_preset": {"total_budget": 10, "slot_budgets": {"weapon": 3}, "stat_bonuses": {"attack_bonus": 1}}}]
    flags = audit_progression_context_rows(rows)
    assert all(f.flag_id != FLAG_MISSING_SIMULATION_GEAR_PRESET for f in flags)


def test_audit_progression_rows_missing_scaling_context_flagged():
    rows = [{"id": "r_scale_missing", "stage": "route_exam", "assumed_player_level": 95, "encounter_level": 95, "mob_role": "normal", "final_mob_stats": {}}]
    flags = audit_progression_context_rows(rows)
    ids = {f.flag_id for f in flags}
    assert FLAG_MISSING_MOB_SCALING_CONTEXT in ids or FLAG_MISSING_FINAL_MOB_STATS in ids


def test_audit_progression_rows_valid_scaling_context_not_flagged():
    rows = [{"id": "r_scale_ok", "stage": "route_exam", "assumed_player_level": 95, "encounter_level": 95, "mob_role": "normal", "scaling_status": "formula_mob_scaling_v1", "final_mob_stats": {"hp": 999, "damage": 100}}]
    flags = audit_progression_context_rows(rows)
    ids = {f.flag_id for f in flags}
    assert FLAG_MISSING_MOB_SCALING_CONTEXT not in ids
    assert FLAG_MISSING_FINAL_MOB_STATS not in ids
