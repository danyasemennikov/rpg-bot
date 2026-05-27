from copy import deepcopy

from game.balance_audit import (
    BalanceAuditFlag,
    FLAG_MISSING_ENCOUNTER_LEVEL,
    FLAG_MISSING_MOB_ROLE,
    FLAG_UNSCALED_TEMPLATE_REUSED_ACROSS_DEPTHS,
    FLAG_WEAK_ROUTE_EXAM_SAMPLE,
    audit_repeated_template_depth_scaling,
    audit_route_stage_sample_metadata,
    build_balance_audit_flag,
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
