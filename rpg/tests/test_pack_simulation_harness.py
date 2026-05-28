from copy import deepcopy

from game.balance_audit import FLAG_MISSING_PACK_SAMPLE, audit_pack_sample_coverage
from game.mob_scaling import MOB_ROLE_MULTIPLIERS, ROLE_PACK_LEADER, ROLE_PACK_MEMBER
from game.mobs import MOBS
from game.pack_simulation import (
    PACK_REQUIRED_STAGES,
    PACK_SIMULATION_STATUS_COMPOSITE_V1,
    build_composite_pack_mob_for_simulation,
    collect_pack_samples,
    list_alpha_pack_samples,
    run_pack_simulation_matrix,
)


def test_pack_roles_exist_in_multipliers():
    assert ROLE_PACK_MEMBER in MOB_ROLE_MULTIPLIERS
    assert ROLE_PACK_LEADER in MOB_ROLE_MULTIPLIERS


def test_pack_samples_cover_alpha_routes_required_stages():
    routes = {"route_westwild", "route_frostspine", "route_ashen_ruins", "route_mireveil", "route_sunscar"}
    for r in routes:
        for stage in PACK_REQUIRED_STAGES:
            assert collect_pack_samples(r, stage)


def test_pack_sample_mob_ids_exist():
    for sample in list_alpha_pack_samples():
        for member in sample.members:
            assert member.mob_id in MOBS


def test_build_composite_pack_positive_and_metadata_and_no_mutation():
    sample = list_alpha_pack_samples()[0]
    before = deepcopy(MOBS)
    mob = build_composite_pack_mob_for_simulation(sample)
    assert mob["hp"] > 0 and mob["damage"] > 0
    assert mob["pack_simulation_status"] == PACK_SIMULATION_STATUS_COMPOSITE_V1
    assert mob["damage"] == mob["final_pack_stats"]["damage"]
    assert mob["damage_min"] == mob["damage"] == mob["damage_max"]
    assert mob["final_pack_stats"]["damage_min"] == mob["damage_min"]
    assert mob["final_pack_stats"]["damage_max"] == mob["damage_max"]
    assert mob["pack_aggregation"]["damage_range_source"] == "deterministic_composite_damage"
    assert MOBS == before


def test_run_pack_simulation_matrix_fields_present():
    data = run_pack_simulation_matrix(archetype_ids=("guardian_shield_1h",), seeds=(1,))
    assert data["pack_runs"]
    row = data["pack_runs"][0]
    for k in ("pack_id", "pack_member_count", "final_pack_stats", "winner", "turns", "observed_diagnostic_label_v2"):
        assert k in row


def test_pack_audit_coverage_missing_stage_emits_missing_pack_sample():
    samples = [s.__dict__ for s in list_alpha_pack_samples() if not (s.route_id == "route_westwild" and s.stage == "route_exam")]
    flags = audit_pack_sample_coverage(samples, ["route_westwild"], PACK_REQUIRED_STAGES)
    assert FLAG_MISSING_PACK_SAMPLE in {f.flag_id for f in flags}


def test_pack_audit_coverage_default_has_no_missing_pack_sample():
    samples = [s.__dict__ for s in list_alpha_pack_samples()]
    flags = audit_pack_sample_coverage(samples, ["route_westwild", "route_frostspine", "route_ashen_ruins", "route_mireveil", "route_sunscar"], PACK_REQUIRED_STAGES)
    assert FLAG_MISSING_PACK_SAMPLE not in {f.flag_id for f in flags}


def test_composite_damage_range_not_inherited_from_first_member_template():
    sample = next(s for s in list_alpha_pack_samples() if s.pack_id == "westwild_build_wolf_boar")
    mob = build_composite_pack_mob_for_simulation(sample)
    first_member = MOBS[sample.members[0].mob_id]
    inherited_min = first_member.get("damage_min")
    inherited_max = first_member.get("damage_max")
    if mob["damage"] != int(round((inherited_min + inherited_max) / 2)):
        assert (mob["damage_min"], mob["damage_max"]) != (inherited_min, inherited_max)
