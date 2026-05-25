from game.combat_simulation import build_simulation_mob_preset
from game.combat_simulation_archetypes import list_alpha_archetype_ids
from game.combat_simulation_matrix import (
    RouteStageMatrixConfig,
    collect_route_stage_samples,
    list_alpha_simulation_route_ids,
    list_route_simulation_stages,
    resolve_location_depth_stage,
    run_route_stage_simulation_matrix,
    validate_route_stage_sample_coverage,
)
from game.locations import WORLD_LOCATIONS


def test_route_stage_coverage_validation_and_lists():
    assert validate_route_stage_sample_coverage() == []
    assert set(list_alpha_simulation_route_ids()) == {
        "route_westwild", "route_frostspine", "route_ashen_ruins", "route_mireveil", "route_sunscar"
    }
    assert set(list_route_simulation_stages()) == {"soft_entry", "identity_visible", "build_testing", "route_exam"}
    assert "route_south_coast_stub" not in list_alpha_simulation_route_ids()
    assert "route_old_mine_stub" not in list_alpha_simulation_route_ids()


def test_no_cross_route_samples_for_all_route_stage_pairs():
    for route_id in list_alpha_simulation_route_ids():
        for stage in list_route_simulation_stages():
            for sample in collect_route_stage_samples(route_id, stage):
                assert WORLD_LOCATIONS[sample.location_id]["route_id"] == sample.route_id


def test_ashen_deep_stages_use_native_override_locations():
    for stage in ("build_testing", "route_exam"):
        samples = collect_route_stage_samples("route_ashen_ruins", stage)
        assert samples
        assert any("stage_override" in sample.sample_tags for sample in samples)
        for sample in samples:
            assert WORLD_LOCATIONS[sample.location_id]["route_id"] == "route_ashen_ruins"


def test_depth_stage_resolver_examples_and_hub_none():
    assert resolve_location_depth_stage("westwild_n1") == "soft_entry"
    assert resolve_location_depth_stage("westwild_n5") == "identity_visible"
    assert resolve_location_depth_stage("westwild_n8") == "build_testing"
    assert resolve_location_depth_stage("westwild_n10") == "route_exam"
    assert resolve_location_depth_stage("ashen_n3b2a1") == "identity_visible"
    assert resolve_location_depth_stage("sunscar_n8a2") == "build_testing"
    assert resolve_location_depth_stage("hub_westwild") is None


def _tiny_config(archetype_count: int = 2):
    return RouteStageMatrixConfig(
        route_ids=("route_westwild",),
        stages=("soft_entry",),
        archetype_ids=tuple(list_alpha_archetype_ids()[:archetype_count]),
        seeds=(1,),
        max_samples_per_route_stage=1,
        max_turns=50,
        include_raw_runs=True,
    )


def test_small_matrix_smoke_run_schema_and_counts():
    cfg = _tiny_config(2)
    result = run_route_stage_simulation_matrix(cfg)

    assert result["runs"]
    assert result["summaries"]
    assert "exp" not in result and "gold" not in result and "loot" not in result
    expected = len(cfg.archetype_ids) * len(cfg.seeds) * cfg.max_samples_per_route_stage
    assert result["run_count"] == expected

    required = {
        "route_id", "stage", "archetype_id", "location_id", "mob_id", "winner", "turns", "actions_used", "skills_used",
        "spawn_profile", "sample_tags", "sample_source_route_id",
    }
    for run in result["runs"]:
        assert required.issubset(set(run.keys()))
        assert run["sample_source_route_id"] == run["route_id"]


def test_tiny_matrix_is_deterministic_for_core_fields():
    cfg = _tiny_config(2)
    a = run_route_stage_simulation_matrix(cfg)
    b = run_route_stage_simulation_matrix(cfg)

    assert a["run_count"] == b["run_count"]
    core_a = [(r["winner"], r["turns"], r["actions_used"], r["skills_used"]) for r in a["runs"]]
    core_b = [(r["winner"], r["turns"], r["actions_used"], r["skills_used"]) for r in b["runs"]]
    assert core_a == core_b


def test_matrix_smoke_all_archetypes_single_route_stage_no_crash():
    cfg = RouteStageMatrixConfig(
        route_ids=("route_westwild",),
        stages=("soft_entry",),
        archetype_ids=tuple(list_alpha_archetype_ids()),
        seeds=(1,),
        max_samples_per_route_stage=1,
        max_turns=40,
        include_raw_runs=False,
    )
    result = run_route_stage_simulation_matrix(cfg)
    assert result["run_count"] == len(cfg.archetype_ids)
    assert len(result["summaries"]) == len(cfg.archetype_ids)


def test_matrix_run_does_not_mutate_simulation_inputs():
    mob_before = build_simulation_mob_preset("forest_boar")
    cfg = _tiny_config(1)
    first = run_route_stage_simulation_matrix(cfg)
    second = run_route_stage_simulation_matrix(cfg)
    mob_after = build_simulation_mob_preset("forest_boar")

    assert mob_before == mob_after
    assert first["runs"] == second["runs"]
