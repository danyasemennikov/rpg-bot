import game.equipment_budget as equipment_budget_module
import pytest

from game.equipment_budget import (
    allocate_budget_to_stats,
    build_simulation_gear_preset,
    calculate_item_level_budget,
    calculate_slot_budget,
)


def test_item_level_budget_snapshots():
    assert calculate_item_level_budget(10) == 87
    assert calculate_item_level_budget(35) == 511
    assert calculate_item_level_budget(70) == 1965
    assert calculate_item_level_budget(95) == 3874
    assert calculate_item_level_budget(100) == 4362


def test_slot_budget_behaviors_and_validation():
    assert calculate_slot_budget(70, "weapon", "rare", 6) > calculate_slot_budget(70, "ring", "rare", 6)
    assert calculate_slot_budget(95, "weapon", "rare", 8) > calculate_slot_budget(95, "weapon", "rare", 0)
    assert calculate_slot_budget(70, "weapon", "rare", 6) > calculate_slot_budget(70, "weapon", "common", 6)
    with pytest.raises(ValueError):
        calculate_slot_budget(0, "weapon", "rare", 6)
    with pytest.raises(ValueError):
        calculate_slot_budget(70, "bad", "rare", 6)
    with pytest.raises(ValueError):
        calculate_slot_budget(70, "weapon", "bad", 6)
    with pytest.raises(ValueError):
        calculate_slot_budget(70, "weapon", "rare", 99)


def test_gear_preset_expectations():
    g = build_simulation_gear_preset("guardian_shield_1h", "route_exam")
    assert g["item_level"] == 95 and g["gear_tier"] == "T10"
    assert g["rarity"] == "rare" and g["enhancement_level"] == 8 and g["profile_id"] == "tank"
    assert g["total_budget"] > 0 and g["stat_bonuses"]["max_hp_bonus"] > 0 and g["stat_bonuses"]["defense_bonus"] > 0
    b = build_simulation_gear_preset("bow_sniper", "build_testing")
    assert b["stat_bonuses"]["attack_bonus"] > 0 and b["stat_bonuses"]["accuracy_bonus"] > 0 and b["stat_bonuses"]["crit_chance_bonus"] > 0
    h = build_simulation_gear_preset("holy_staff_solo", "identity_visible")
    assert h["stat_bonuses"]["healing_power_bonus"] > 0 and h["stat_bonuses"]["max_mana_bonus"] > 0


def test_profile_relationships():
    tank = allocate_budget_to_stats(2000, "tank")
    dps = allocate_budget_to_stats(2000, "physical_dps")
    healer = allocate_budget_to_stats(2000, "healer_support")
    assert tank["max_hp_bonus"] > dps["max_hp_bonus"]
    assert tank["defense_bonus"] > dps["defense_bonus"]
    assert dps["attack_bonus"] > tank["attack_bonus"]
    assert healer["healing_power_bonus"] > 0


def test_equipment_budget_module_imports_cleanly():
    assert equipment_budget_module.MAX_ENHANCEMENT_LEVEL == 15
