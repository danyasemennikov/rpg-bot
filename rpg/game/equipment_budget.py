from __future__ import annotations

MAX_ENHANCEMENT_LEVEL = 15

RARITY_MULTIPLIERS = {
    "common": 1.00,
    "uncommon": 1.10,
    "rare": 1.25,
    "epic": 1.45,
    "legendary": 1.75,
    "unique": 2.05,
}

ENHANCEMENT_MULTIPLIERS = {
    0: 1.00, 1: 1.03, 2: 1.06, 3: 1.10, 4: 1.15, 5: 1.21, 6: 1.28, 7: 1.36,
    8: 1.45, 9: 1.55, 10: 1.66, 11: 1.78, 12: 1.91, 13: 2.05, 14: 2.20, 15: 2.36,
}

SLOT_BUDGET_WEIGHTS = {
    "weapon": 1.00,
    "armor": 0.90,
    "offhand": 0.55,
    "ring": 0.25,
    "amulet": 0.35,
}

SIMULATION_STAGE_GEAR_ASSUMPTIONS = {
    "soft_entry": {"item_level": 10, "rarity": "common", "enhancement_level": 0},
    "identity_visible": {"item_level": 35, "rarity": "uncommon", "enhancement_level": 3},
    "build_testing": {"item_level": 70, "rarity": "rare", "enhancement_level": 6},
    "route_exam": {"item_level": 95, "rarity": "rare", "enhancement_level": 8},
}

ARCHETYPE_PROFILE_MAP = {
    "guardian_shield_1h": "tank", "sword_2h_burst": "physical_dps", "axe_2h_bruiser": "bruiser",
    "daggers_venom": "evasion_dps", "daggers_evasion": "evasion_dps", "bow_sniper": "bow_dps",
    "bow_ranger": "bow_dps", "magic_staff_destruction": "magic_dps", "magic_staff_control": "control_caster",
    "wand_tempo": "magic_dps", "holy_staff_solo": "healer_support", "holy_rod_paladin": "paladin_hybrid",
    "tome_toolbox": "toolbox_hybrid", "pure_support_solo_overlay": "healer_support",
}

PROFILE_WEIGHTS = {
    "physical_dps": {"attack_bonus": 0.36, "accuracy_bonus": 0.24, "crit_chance_bonus": 0.12, "max_hp_bonus": 0.10, "defense_bonus": 0.10, "evasion_bonus": 0.08},
    "bow_dps": {"attack_bonus": 0.30, "accuracy_bonus": 0.24, "crit_chance_bonus": 0.12, "evasion_bonus": 0.14, "max_hp_bonus": 0.10, "defense_bonus": 0.10},
    "evasion_dps": {"attack_bonus": 0.30, "evasion_bonus": 0.24, "crit_chance_bonus": 0.12, "accuracy_bonus": 0.12, "max_hp_bonus": 0.12, "defense_bonus": 0.10},
    "bruiser": {"max_hp_bonus": 0.28, "attack_bonus": 0.24, "defense_bonus": 0.22, "accuracy_bonus": 0.10, "magic_defense_bonus": 0.10, "crit_chance_bonus": 0.06},
    "tank": {"max_hp_bonus": 0.34, "defense_bonus": 0.25, "magic_defense_bonus": 0.18, "block_chance_bonus": 0.08, "accuracy_bonus": 0.06, "attack_bonus": 0.09},
    "magic_dps": {"magic_power_bonus": 0.34, "max_mana_bonus": 0.28, "accuracy_bonus": 0.16, "max_hp_bonus": 0.08, "defense_bonus": 0.06, "crit_chance_bonus": 0.08},
    "control_caster": {"magic_power_bonus": 0.26, "max_mana_bonus": 0.28, "accuracy_bonus": 0.16, "defense_bonus": 0.14, "magic_defense_bonus": 0.10, "max_hp_bonus": 0.06},
    "healer_support": {"healing_power_bonus": 0.34, "max_mana_bonus": 0.30, "defense_bonus": 0.14, "magic_defense_bonus": 0.14, "max_hp_bonus": 0.08},
    "paladin_hybrid": {"max_hp_bonus": 0.25, "defense_bonus": 0.20, "healing_power_bonus": 0.16, "attack_bonus": 0.18, "block_chance_bonus": 0.08, "magic_defense_bonus": 0.13},
    "toolbox_hybrid": {"max_mana_bonus": 0.20, "magic_power_bonus": 0.20, "attack_bonus": 0.18, "defense_bonus": 0.16, "magic_defense_bonus": 0.14, "accuracy_bonus": 0.12},
}

STAT_SCALARS = {
    "max_hp_bonus": 1.4, "max_mana_bonus": 1.2, "attack_bonus": 0.12, "magic_power_bonus": 0.12,
    "healing_power_bonus": 0.11, "defense_bonus": 0.11, "magic_defense_bonus": 0.11,
    "accuracy_bonus": 0.07, "evasion_bonus": 0.06, "crit_chance_bonus": 0.008, "block_chance_bonus": 0.007,
}


def calculate_item_level_budget(item_level: int) -> int:
    if item_level < 1 or item_level > 100:
        raise ValueError("item_level must be in 1..100")
    return round(12 + 5.5 * item_level + 0.18 * item_level ** 2 + 0.002 * item_level ** 3)


def calculate_slot_budget(item_level: int, slot: str, rarity: str, enhancement_level: int) -> int:
    if enhancement_level < 0 or enhancement_level > MAX_ENHANCEMENT_LEVEL:
        raise ValueError("enhancement_level must be in 0..15")
    if rarity not in RARITY_MULTIPLIERS:
        raise ValueError(f"unknown rarity: {rarity}")
    normalized_slot = "ring" if str(slot).startswith("ring") else str(slot)
    if normalized_slot not in SLOT_BUDGET_WEIGHTS:
        raise ValueError(f"unknown slot: {slot}")
    return round(calculate_item_level_budget(item_level) * SLOT_BUDGET_WEIGHTS[normalized_slot] * RARITY_MULTIPLIERS[rarity] * ENHANCEMENT_MULTIPLIERS[enhancement_level])


def allocate_budget_to_stats(total_budget: int, profile_id: str) -> dict[str, int | float]:
    if total_budget < 0:
        raise ValueError("total_budget must be >= 0")
    if profile_id not in PROFILE_WEIGHTS:
        raise ValueError(f"unknown profile_id: {profile_id}")
    bonuses = {k: 0 for k in STAT_SCALARS}
    for stat, weight in PROFILE_WEIGHTS[profile_id].items():
        bonuses[stat] = round(total_budget * weight * STAT_SCALARS[stat], 2)
    return bonuses


def resolve_simulation_stage_gear_assumption(stage: str) -> dict | None:
    assumption = SIMULATION_STAGE_GEAR_ASSUMPTIONS.get(str(stage or "").strip())
    return dict(assumption) if assumption else None


def build_simulation_gear_preset(archetype_id: str, stage: str) -> dict:
    assumption = resolve_simulation_stage_gear_assumption(stage)
    if assumption is None:
        raise ValueError(f"Unknown simulation stage: {stage}")
    profile_id = ARCHETYPE_PROFILE_MAP.get(archetype_id, "toolbox_hybrid")
    budget_status = "formula_budget_v1"
    if archetype_id not in ARCHETYPE_PROFILE_MAP:
        budget_status = "formula_budget_v1_toolbox_fallback"
    slots = ("weapon", "armor", "offhand", "ring1", "ring2", "amulet")
    slot_budgets = {slot: calculate_slot_budget(assumption["item_level"], slot, assumption["rarity"], assumption["enhancement_level"]) for slot in slots}
    total_budget = sum(slot_budgets.values())
    return {
        "archetype_id": archetype_id,
        "stage": stage,
        "item_level": assumption["item_level"],
        "gear_tier": f"T{((assumption['item_level'] - 1) // 10) + 1}",
        "rarity": assumption["rarity"],
        "enhancement_level": assumption["enhancement_level"],
        "profile_id": profile_id,
        "slot_budgets": slot_budgets,
        "total_budget": total_budget,
        "stat_bonuses": allocate_budget_to_stats(total_budget, profile_id),
        "budget_status": budget_status,
    }
