from copy import deepcopy

import pytest

from game.mob_scaling import (
    build_scaled_mob_for_simulation,
    build_scaled_mob_stats,
    calculate_encounter_level_from_stage,
    calculate_mob_level_scale,
)
from game.mobs import MOBS


def test_encounter_level_resolution():
    assert calculate_encounter_level_from_stage("soft_entry") == 10
    assert calculate_encounter_level_from_stage("identity_visible") == 35
    assert calculate_encounter_level_from_stage("build_testing") == 70
    assert calculate_encounter_level_from_stage("route_exam") == 95
    assert calculate_encounter_level_from_stage("unknown") is None


def test_level_scaling_curve_and_validation():
    low = calculate_mob_level_scale(10)
    high = calculate_mob_level_scale(95)
    assert high["hp"] > low["hp"]
    assert high["damage"] > low["damage"]
    with pytest.raises(ValueError):
        calculate_mob_level_scale(0)
    with pytest.raises(ValueError):
        calculate_mob_level_scale(101)




def test_level_scaling_accepts_numeric_string_same_as_int():
    assert calculate_mob_level_scale("10") == calculate_mob_level_scale(10)

def test_role_scaling_order():
    base = {"id": "x", "hp": 100, "damage": 20}
    n = build_scaled_mob_stats(base, encounter_level=70, mob_role="normal", route_id="route_westwild")
    p = build_scaled_mob_stats(base, encounter_level=70, mob_role="pressure", route_id="route_westwild")
    e = build_scaled_mob_stats(base, encounter_level=70, mob_role="elite", route_id="route_westwild")
    b = build_scaled_mob_stats(base, encounter_level=70, mob_role="boss", route_id="route_westwild")
    assert n["hp"] < p["hp"] < e["hp"] < b["hp"]
    assert n["damage"] < p["damage"] < e["damage"]


def test_route_modifiers_change_scaled_outputs():
    base = {"id": "x", "hp": 100, "damage": 20, "accuracy": 10, "defense": 8}
    west = build_scaled_mob_stats(base, encounter_level=70, mob_role="normal", route_id="route_westwild")
    frost = build_scaled_mob_stats(base, encounter_level=70, mob_role="normal", route_id="route_frostspine")
    sun = build_scaled_mob_stats(base, encounter_level=70, mob_role="normal", route_id="route_sunscar")
    assert frost["hp"] != west["hp"] or frost["defense"] != west["defense"]
    assert sun["damage"] != west["damage"] or sun["accuracy"] != west["accuracy"]


def test_build_scaled_mob_for_simulation_does_not_mutate_mobs_and_has_metadata():
    mob_id = "bear"
    before = deepcopy(MOBS[mob_id])
    scaled = build_scaled_mob_for_simulation(mob_id, "route_westwild", "route_exam")
    assert MOBS[mob_id] == before
    assert scaled["encounter_level"] == 95
    assert scaled["mob_role"] == "normal"
    assert scaled["scaling_status"] == "formula_mob_scaling_v1"
    assert isinstance(scaled.get("base_mob_stats"), dict)
    assert isinstance(scaled.get("final_mob_stats"), dict)
