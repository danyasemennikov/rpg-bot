from __future__ import annotations

import copy

from game.combat_simulation import (
    AlwaysAttackPolicy,
    AlwaysGuardFallbackPolicy,
    GuardThenAttackPolicy,
    ScriptedActionPolicy,
    SIM_ACTION_GUARD_FALLBACK,
    SIM_ACTION_NORMAL_ATTACK,
    make_simulation_skill_action,
)
from game.skills import get_skill
from game.equipment_budget import build_simulation_gear_preset


PROFILE_POLICY_PILOT_ARCHETYPE_IDS = (
    "daggers_venom",
    "daggers_evasion",
    "bow_sniper",
    "magic_staff_destruction",
    "holy_staff_solo",
)

REQUIRED_ARCHETYPE_IDS = (
    "guardian_shield_1h",
    "sword_2h_burst",
    "axe_2h_bruiser",
    "daggers_venom",
    "daggers_evasion",
    "bow_sniper",
    "bow_ranger",
    "magic_staff_destruction",
    "magic_staff_control",
    "wand_tempo",
    "holy_staff_solo",
    "holy_rod_paladin",
    "tome_toolbox",
    "pure_support_solo_overlay",
)

REQUIRED_POWER_TIERS = ("soft_entry", "identity_visible", "build_testing", "route_exam")

ENCUMBRANCE_BY_LOADOUT = {
    "light": 2,
    "medium": 5,
    "heavy": 8,
}

ALLOWED_OFFHAND_PROFILES = {"none", "shield", "focus", "censer", "orb", "tome"}

REQUIRED_PLAYER_FIELDS = (
    "hp", "max_hp", "mana", "max_mana", "strength", "agility", "intuition", "vitality", "wisdom", "luck",
    "weapon_damage", "weapon_type", "weapon_profile", "armor_class", "offhand_profile", "damage_school", "encumbrance",
    "equipment_physical_defense_bonus", "equipment_magic_defense_bonus", "equipment_accuracy_bonus", "equipment_evasion_bonus",
    "equipment_block_chance_bonus", "equipment_magic_power_bonus", "equipment_healing_power_bonus",
)

BASE_TIER_PRESETS = {
    "soft_entry": {"hp": 100, "mana": 55, "weapon_damage": 16, "primary_stat": 11, "secondary_stat": 9, "vitality": 10, "wisdom": 9, "luck": 8, "gear": 1},
    "identity_visible": {"hp": 130, "mana": 75, "weapon_damage": 22, "primary_stat": 16, "secondary_stat": 13, "vitality": 14, "wisdom": 12, "luck": 10, "gear": 3},
    "build_testing": {"hp": 175, "mana": 100, "weapon_damage": 30, "primary_stat": 23, "secondary_stat": 18, "vitality": 19, "wisdom": 16, "luck": 13, "gear": 6},
    "route_exam": {"hp": 240, "mana": 130, "weapon_damage": 38, "primary_stat": 30, "secondary_stat": 24, "vitality": 25, "wisdom": 20, "luck": 16, "gear": 9},
}

ARCHETYPE_METADATA = {
    "guardian_shield_1h": {"display_name": "Guardian (1H + Shield)", "weapon_profile": "sword_1h", "weapon_type": "melee", "damage_school": "physical", "armor_class": "heavy", "offhand_profile": "shield", "role_tags": ["tank", "frontline", "control"], "strengths": ["block", "survivability", "stability"], "weaknesses": ["lower_burst", "lower_mobility"], "preferred_policy_id": "guard_then_attack", "preferred_skill_ids": ["shield_bash", "defensive_stance", "parry"], "notes": "Validation archetype for defensive frontline pressure."},
    "sword_2h_burst": {"display_name": "Greatsword Burst", "weapon_profile": "sword_2h", "weapon_type": "melee", "damage_school": "physical", "armor_class": "medium", "offhand_profile": "none", "role_tags": ["melee_dps", "burst"], "strengths": ["single_target_damage", "finish_pressure"], "weaknesses": ["reduced_block", "lower_sustain"], "preferred_policy_id": "aggressive_burst", "preferred_skill_ids": ["power_strike"], "notes": "Future burst policy metadata only."},
    "axe_2h_bruiser": {"display_name": "Axe Bruiser", "weapon_profile": "axe_2h", "weapon_type": "melee", "damage_school": "physical", "armor_class": "medium", "offhand_profile": "none", "role_tags": ["bruiser", "sustain", "pressure"], "strengths": ["trade_efficiency", "durability"], "weaknesses": ["lower_accuracy", "predictable_tempo"], "preferred_policy_id": "always_attack", "preferred_skill_ids": ["power_strike"], "notes": "Baseline bruiser benchmark."},
    "daggers_venom": {"display_name": "Daggers Venom", "weapon_profile": "daggers", "weapon_type": "melee", "damage_school": "physical", "armor_class": "light", "offhand_profile": "none", "role_tags": ["assassin", "dot", "tempo"], "strengths": ["tempo", "dot_pressure"], "weaknesses": ["fragile", "low_block"], "preferred_policy_id": "venom_setup", "preferred_skill_ids": ["poison_blade"], "notes": "Preferred skills are metadata only in PR2."},
    "daggers_evasion": {"display_name": "Daggers Evasion", "weapon_profile": "daggers", "weapon_type": "melee", "damage_school": "physical", "armor_class": "light", "offhand_profile": "none", "role_tags": ["assassin", "evasion", "tempo"], "strengths": ["evasion", "initiative"], "weaknesses": ["low_hp", "low_armor"], "preferred_policy_id": "evasion_tempo", "preferred_skill_ids": ["counter"], "notes": "Evasion-biased rogue benchmark."},
    "bow_sniper": {"display_name": "Bow Sniper", "weapon_profile": "bow", "weapon_type": "ranged", "damage_school": "physical", "armor_class": "light", "offhand_profile": "none", "role_tags": ["ranged_dps", "precision", "burst"], "strengths": ["accuracy", "single_target_damage"], "weaknesses": ["weak_sustain", "low_block"], "preferred_policy_id": "sniper_precision", "preferred_skill_ids": ["hunters_mark"], "notes": "Sniper policy is future metadata."},
    "bow_ranger": {"display_name": "Bow Ranger", "weapon_profile": "bow", "weapon_type": "ranged", "damage_school": "physical", "armor_class": "medium", "offhand_profile": "none", "role_tags": ["ranged_dps", "mobile", "sustained"], "strengths": ["stability", "kiting"], "weaknesses": ["lower_peak_damage"], "preferred_policy_id": "always_attack", "preferred_skill_ids": ["power_strike"], "notes": "Baseline ranged sustained benchmark."},
    "magic_staff_destruction": {"display_name": "Magic Staff Destruction", "weapon_profile": "magic_staff", "weapon_type": "magic", "damage_school": "magic", "armor_class": "light", "offhand_profile": "focus", "role_tags": ["caster", "burst", "aoe"], "strengths": ["magic_power", "mana_pool"], "weaknesses": ["low_physical_defense", "fragile"], "preferred_policy_id": "aggressive_burst", "preferred_skill_ids": ["fireball"], "notes": "No runtime skill adapter added in PR2."},
    "magic_staff_control": {"display_name": "Magic Staff Control", "weapon_profile": "magic_staff", "weapon_type": "magic", "damage_school": "magic", "armor_class": "light", "offhand_profile": "focus", "role_tags": ["caster", "control", "tempo"], "strengths": ["control_windows", "resource_depth"], "weaknesses": ["lower_burst"], "preferred_policy_id": "control_caster", "preferred_skill_ids": ["ice_shard"], "notes": "Control policy is metadata only."},
    "wand_tempo": {"display_name": "Wand Tempo", "weapon_profile": "wand", "weapon_type": "magic", "damage_school": "magic", "armor_class": "light", "offhand_profile": "focus", "role_tags": ["caster", "tempo", "hybrid"], "strengths": ["initiative", "mana_efficiency"], "weaknesses": ["lower_peak_damage"], "preferred_policy_id": "always_attack", "preferred_skill_ids": ["arcane_bolt"], "notes": "Tempo caster benchmark."},
    "holy_staff_solo": {"display_name": "Holy Staff Solo", "weapon_profile": "holy_staff", "weapon_type": "holy", "damage_school": "holy", "armor_class": "light", "offhand_profile": "censer", "role_tags": ["support", "sustain", "solo"], "strengths": ["healing_power", "resource_stability"], "weaknesses": ["low_dps"], "preferred_policy_id": "solo_support_sustain", "preferred_skill_ids": ["blessing", "regeneration"], "notes": "Sustain policy is future metadata."},
    "holy_rod_paladin": {"display_name": "Holy Rod Paladin", "weapon_profile": "holy_rod", "weapon_type": "holy", "damage_school": "holy", "armor_class": "heavy", "offhand_profile": "shield", "role_tags": ["paladin", "hybrid", "frontline"], "strengths": ["defense", "holy_sustain"], "weaknesses": ["not_top_dps", "not_top_healing"], "preferred_policy_id": "guard_then_attack", "preferred_skill_ids": ["defensive_stance", "blessing"], "notes": "Defensive hybrid; deliberately non-peak."},
    "tome_toolbox": {"display_name": "Tome Toolbox", "weapon_profile": "tome", "weapon_type": "magic", "damage_school": "magic", "armor_class": "medium", "offhand_profile": "none", "role_tags": ["utility", "hybrid", "control"], "strengths": ["flexibility", "adaptability"], "weaknesses": ["not_peak_damage", "not_peak_sustain"], "preferred_policy_id": "toolbox_balanced", "preferred_skill_ids": ["power_strike"], "notes": "Generalist benchmark for future reports."},
    "pure_support_solo_overlay": {"display_name": "Pure Support Solo Overlay", "weapon_profile": "holy_staff", "weapon_type": "holy", "damage_school": "holy", "armor_class": "light", "offhand_profile": "censer", "role_tags": ["support", "overlay", "solo_validation"], "strengths": ["healing", "durability_over_time"], "weaknesses": ["very_low_damage"], "preferred_policy_id": "solo_support_sustain", "preferred_skill_ids": ["regeneration", "blessing", "resurrection"], "notes": "Validation-only overlay archetype."},
}


EXPECTED_ROTATION_PROFILES = {
    "axe_2h_bruiser": {
        "archetype_id": "axe_2h_bruiser",
        "profile_id": "axe_2h_bruiser_trade_sustain_v1",
        "rotation_family": "bruiser_trade_sustain",
        "expected_skill_ids": ["rage_call", "savage_chop", "blooded_resolve"],
        "setup_skill_ids": ["rage_call"],
        "payoff_skill_ids": ["savage_chop"],
        "sustain_skill_ids": ["blooded_resolve"],
        "mana_sensitive": True,
        "cooldown_sensitive": True,
        "notes": "Simulation interpretation profile only; checks whether bruiser budget rows depend on rage, damage, and self-sustain skill access.",
    },
    "daggers_venom": {
        "archetype_id": "daggers_venom",
        "profile_id": "daggers_venom_setup_payoff_v1",
        "rotation_family": "setup_payoff_dot",
        "expected_skill_ids": ["poison_blade", "envenom", "toxic_cut", "rupture_toxins"],
        "setup_skill_ids": ["poison_blade", "envenom"],
        "payoff_skill_ids": ["toxic_cut", "rupture_toxins"],
        "sustain_skill_ids": [],
        "mana_sensitive": True,
        "cooldown_sensitive": True,
        "notes": "Simulation interpretation profile only; separates venom setup/payoff expectations from ordinary attack fallback artifacts.",
    },
    "daggers_evasion": {
        "archetype_id": "daggers_evasion",
        "profile_id": "daggers_evasion_tempo_v1",
        "rotation_family": "evasion_tempo",
        "expected_skill_ids": ["smoke_bomb", "feint_step", "quick_slice", "death_dance"],
        "setup_skill_ids": ["smoke_bomb", "feint_step"],
        "payoff_skill_ids": ["quick_slice", "death_dance"],
        "sustain_skill_ids": [],
        "mana_sensitive": True,
        "cooldown_sensitive": True,
        "notes": "Simulation interpretation profile only; uses implemented dagger tempo skills rather than the old metadata-only counter placeholder.",
    },
    "bow_sniper": {
        "archetype_id": "bow_sniper",
        "profile_id": "bow_sniper_precision_v1",
        "rotation_family": "mark_precision_payoff",
        "expected_skill_ids": ["hunters_mark", "steady_aim", "aimed_shot", "deadeye"],
        "setup_skill_ids": ["hunters_mark", "steady_aim"],
        "payoff_skill_ids": ["aimed_shot", "deadeye"],
        "sustain_skill_ids": [],
        "mana_sensitive": True,
        "cooldown_sensitive": True,
        "notes": "Simulation interpretation profile only; separates precision setup assumptions from normal attack fallback.",
    },
    "magic_staff_destruction": {
        "archetype_id": "magic_staff_destruction",
        "profile_id": "magic_staff_destruction_burst_v1",
        "rotation_family": "caster_burst",
        "expected_skill_ids": ["arcane_surge", "fireball", "flame_wave", "cataclysm"],
        "setup_skill_ids": ["arcane_surge"],
        "payoff_skill_ids": ["fireball", "flame_wave", "cataclysm"],
        "sustain_skill_ids": [],
        "mana_sensitive": True,
        "cooldown_sensitive": True,
        "notes": "Simulation interpretation profile only; highlights mana/cooldown exposure for destruction burst rows.",
    },
    "holy_staff_solo": {
        "archetype_id": "holy_staff_solo",
        "profile_id": "holy_staff_solo_sustain_v1",
        "rotation_family": "solo_support_sustain",
        "expected_skill_ids": ["regeneration", "blessing", "heal", "smite"],
        "setup_skill_ids": ["blessing"],
        "payoff_skill_ids": ["smite"],
        "sustain_skill_ids": ["regeneration", "heal"],
        "mana_sensitive": True,
        "cooldown_sensitive": True,
        "notes": "Simulation interpretation profile only; support solo rows need sustain timing review before live tuning conclusions.",
    },
}


def get_expected_rotation_profile(archetype_id: str) -> dict | None:
    profile = EXPECTED_ROTATION_PROFILES.get(archetype_id)
    return copy.deepcopy(profile) if profile else None


def list_expected_rotation_profiles() -> list[dict]:
    return [copy.deepcopy(EXPECTED_ROTATION_PROFILES[archetype_id]) for archetype_id in sorted(EXPECTED_ROTATION_PROFILES)]

EXECUTABLE_POLICY_REGISTRY = {
    "always_attack": {"executable": True, "factory": lambda: AlwaysAttackPolicy(), "notes": "safe executable"},
    "always_guard_fallback": {"executable": True, "factory": lambda: AlwaysGuardFallbackPolicy(), "notes": "safe executable"},
    "guard_then_attack": {"executable": True, "factory": lambda: GuardThenAttackPolicy(guard_every_n_turns=3), "notes": "simulation-only anti-loop defensive policy"},
    "scripted_smoke": {"executable": True, "factory": lambda: ScriptedActionPolicy([make_simulation_skill_action("power_strike"), SIM_ACTION_GUARD_FALLBACK, SIM_ACTION_NORMAL_ATTACK]), "notes": "safe smoke policy"},
    "aggressive_burst": {"executable": False, "factory": None, "notes": "future metadata policy"},
    "venom_setup": {"executable": False, "factory": None, "notes": "future metadata policy"},
    "evasion_tempo": {"executable": False, "factory": None, "notes": "future metadata policy"},
    "sniper_precision": {"executable": False, "factory": None, "notes": "future metadata policy"},
    "control_caster": {"executable": False, "factory": None, "notes": "future metadata policy"},
    "solo_support_sustain": {"executable": False, "factory": None, "notes": "future metadata policy"},
    "toolbox_balanced": {"executable": False, "factory": None, "notes": "future metadata policy"},
}


def list_alpha_archetype_ids() -> list[str]:
    return list(REQUIRED_ARCHETYPE_IDS)


def list_simulation_power_tiers() -> list[str]:
    return list(REQUIRED_POWER_TIERS)


def get_archetype_metadata(archetype_id: str) -> dict:
    if archetype_id not in ARCHETYPE_METADATA:
        raise ValueError(f"Unknown archetype id: {archetype_id}")
    metadata = copy.deepcopy(ARCHETYPE_METADATA[archetype_id])
    metadata["id"] = archetype_id
    return metadata


def _tier_base_stats(power_tier: str) -> dict:
    if power_tier not in BASE_TIER_PRESETS:
        raise ValueError(f"Unknown power tier: {power_tier}")
    base = dict(BASE_TIER_PRESETS[power_tier])
    base["max_hp"] = base["hp"]
    base["max_mana"] = base["mana"]
    return base




def _apply_simulation_equipment_bonuses(player: dict, gear_preset: dict) -> None:
    bonuses = gear_preset.get("stat_bonuses", {})
    player["simulation_gear_preset"] = gear_preset
    player["equipment_stat_bonuses"] = dict(bonuses)
    player["hp"] += int(bonuses.get("max_hp_bonus", 0))
    player["max_hp"] += int(bonuses.get("max_hp_bonus", 0))
    player["mana"] += int(bonuses.get("max_mana_bonus", 0))
    player["max_mana"] += int(bonuses.get("max_mana_bonus", 0))
    player["weapon_damage"] += int(bonuses.get("attack_bonus", 0))
    player["equipment_physical_defense_bonus"] += int(bonuses.get("defense_bonus", 0))
    player["equipment_magic_defense_bonus"] += int(bonuses.get("magic_defense_bonus", 0))
    player["equipment_accuracy_bonus"] += int(bonuses.get("accuracy_bonus", 0))
    player["equipment_evasion_bonus"] += int(bonuses.get("evasion_bonus", 0))
    player["equipment_magic_power_bonus"] += int(bonuses.get("magic_power_bonus", 0))
    player["equipment_healing_power_bonus"] += int(bonuses.get("healing_power_bonus", 0))
    player["equipment_block_chance_bonus"] += int(bonuses.get("block_chance_bonus", 0))

def build_archetype_player_preset(archetype_id: str, power_tier: str) -> dict:
    metadata = get_archetype_metadata(archetype_id)
    base = _tier_base_stats(power_tier)
    gear = base["gear"]
    player = {
        "id": 0,
        "name": f"sim_{archetype_id}_{power_tier}",
        "hp": base["hp"], "max_hp": base["max_hp"], "mana": base["mana"], "max_mana": base["max_mana"],
        "strength": base["secondary_stat"], "agility": base["secondary_stat"], "intuition": base["secondary_stat"],
        "vitality": base["vitality"], "wisdom": base["wisdom"], "luck": base["luck"],
        "weapon_damage": base["weapon_damage"], "weapon_type": metadata["weapon_type"], "weapon_profile": metadata["weapon_profile"],
        "armor_class": metadata["armor_class"], "offhand_profile": metadata["offhand_profile"], "damage_school": metadata["damage_school"],
        "encumbrance": ENCUMBRANCE_BY_LOADOUT["medium"],
        "equipment_physical_defense_bonus": gear, "equipment_magic_defense_bonus": gear,
        "equipment_accuracy_bonus": gear, "equipment_evasion_bonus": gear,
        "equipment_block_chance_bonus": 0, "equipment_magic_power_bonus": 0, "equipment_healing_power_bonus": 0,
    }

    if archetype_id == "guardian_shield_1h":
        player.update(strength=base["primary_stat"], vitality=base["primary_stat"], weapon_damage=base["weapon_damage"] - 2, equipment_physical_defense_bonus=gear + 4, equipment_block_chance_bonus=gear + 6, equipment_evasion_bonus=max(0, gear - 1), encumbrance=ENCUMBRANCE_BY_LOADOUT["heavy"])
    elif archetype_id == "sword_2h_burst":
        player.update(strength=base["primary_stat"] + 1, agility=base["secondary_stat"], weapon_damage=base["weapon_damage"] + 4, equipment_physical_defense_bonus=max(0, gear - 1), encumbrance=ENCUMBRANCE_BY_LOADOUT["heavy"])
    elif archetype_id == "axe_2h_bruiser":
        player.update(strength=base["primary_stat"], vitality=base["primary_stat"] - 1, weapon_damage=base["weapon_damage"] + 2, hp=base["hp"] + 12, max_hp=base["hp"] + 12, encumbrance=ENCUMBRANCE_BY_LOADOUT["heavy"])
    elif archetype_id == "daggers_venom":
        player.update(agility=base["primary_stat"], luck=base["secondary_stat"] + 2, weapon_damage=base["weapon_damage"] + 1, hp=base["hp"] - 10, max_hp=base["hp"] - 10, equipment_evasion_bonus=gear + 2, equipment_accuracy_bonus=gear + 2, encumbrance=ENCUMBRANCE_BY_LOADOUT["light"])
    elif archetype_id == "daggers_evasion":
        player.update(agility=base["primary_stat"] + 1, luck=base["secondary_stat"] + 1, vitality=max(1, base["vitality"] - 2), weapon_damage=base["weapon_damage"], hp=base["hp"] - 14, max_hp=base["hp"] - 14, equipment_evasion_bonus=gear + 5, equipment_accuracy_bonus=gear + 1, encumbrance=ENCUMBRANCE_BY_LOADOUT["light"])
    elif archetype_id == "bow_sniper":
        player.update(agility=base["primary_stat"], intuition=base["primary_stat"] - 1, weapon_damage=base["weapon_damage"] + 3, equipment_accuracy_bonus=gear + 5, equipment_evasion_bonus=max(0, gear - 1), encumbrance=ENCUMBRANCE_BY_LOADOUT["light"])
    elif archetype_id == "bow_ranger":
        player.update(agility=base["primary_stat"], intuition=base["secondary_stat"] + 2, weapon_damage=base["weapon_damage"] + 1, hp=base["hp"] + 4, max_hp=base["hp"] + 4, equipment_accuracy_bonus=gear + 2, equipment_evasion_bonus=gear + 2)
    elif archetype_id == "magic_staff_destruction":
        player.update(intuition=base["primary_stat"] + 2, wisdom=base["secondary_stat"] + 2, mana=base["mana"] + 20, max_mana=base["mana"] + 20, hp=base["hp"] - 12, max_hp=base["hp"] - 12, weapon_damage=base["weapon_damage"] + 2, equipment_magic_defense_bonus=gear + 1, equipment_physical_defense_bonus=max(0, gear - 2), equipment_magic_power_bonus=gear + 7, encumbrance=ENCUMBRANCE_BY_LOADOUT["light"])
    elif archetype_id == "magic_staff_control":
        player.update(intuition=base["primary_stat"], wisdom=base["primary_stat"] - 1, mana=base["mana"] + 24, max_mana=base["mana"] + 24, weapon_damage=base["weapon_damage"], equipment_magic_power_bonus=gear + 4, equipment_accuracy_bonus=gear + 2, encumbrance=ENCUMBRANCE_BY_LOADOUT["light"])
    elif archetype_id == "wand_tempo":
        player.update(intuition=base["primary_stat"] - 1, wisdom=base["secondary_stat"] + 2, agility=base["secondary_stat"] + 2, weapon_damage=base["weapon_damage"] + 1, equipment_magic_power_bonus=gear + 3, equipment_accuracy_bonus=gear + 2, equipment_evasion_bonus=gear + 1, encumbrance=ENCUMBRANCE_BY_LOADOUT["light"])
    elif archetype_id == "holy_staff_solo":
        player.update(wisdom=base["primary_stat"] + 2, vitality=base["secondary_stat"] + 1, mana=base["mana"] + 18, max_mana=base["mana"] + 18, weapon_damage=base["weapon_damage"] - 3, hp=base["hp"] + 8, max_hp=base["hp"] + 8, equipment_magic_power_bonus=gear + 2, equipment_healing_power_bonus=gear + 7, encumbrance=ENCUMBRANCE_BY_LOADOUT["light"])
    elif archetype_id == "holy_rod_paladin":
        player.update(strength=base["secondary_stat"] + 2, wisdom=base["primary_stat"], vitality=base["primary_stat"], weapon_damage=base["weapon_damage"] - 1, hp=base["hp"] + 14, max_hp=base["hp"] + 14, equipment_block_chance_bonus=gear + 4, equipment_physical_defense_bonus=gear + 3, equipment_healing_power_bonus=gear + 3, encumbrance=ENCUMBRANCE_BY_LOADOUT["heavy"])
    elif archetype_id == "tome_toolbox":
        player.update(intuition=base["primary_stat"] - 1, wisdom=base["secondary_stat"] + 2, vitality=base["secondary_stat"] + 1, weapon_damage=base["weapon_damage"], hp=base["hp"] + 2, max_hp=base["hp"] + 2, mana=base["mana"] + 10, max_mana=base["mana"] + 10, equipment_magic_power_bonus=gear + 2, equipment_healing_power_bonus=gear + 2)
    elif archetype_id == "pure_support_solo_overlay":
        player.update(wisdom=base["primary_stat"] + 3, vitality=base["secondary_stat"] + 1, mana=base["mana"] + 26, max_mana=base["mana"] + 26, weapon_damage=base["weapon_damage"] - 5, hp=base["hp"] + 10, max_hp=base["hp"] + 10, equipment_magic_power_bonus=gear + 1, equipment_healing_power_bonus=gear + 9, equipment_physical_defense_bonus=max(0, gear - 1), encumbrance=ENCUMBRANCE_BY_LOADOUT["light"])

    gear_preset = build_simulation_gear_preset(archetype_id, power_tier)
    _apply_simulation_equipment_bonuses(player, gear_preset)
    return player


def _skill_available_at_simulation_stage(skill_id: str, stage_level: int) -> bool:
    skill_def = get_skill(skill_id)
    if not skill_def:
        return False
    return int(stage_level) >= int(skill_def.get("unlock_mastery", 1) or 1)


def build_archetype_simulation_skill_levels(archetype_id: str, power_tier: str) -> dict[str, int]:
    if power_tier not in REQUIRED_POWER_TIERS:
        raise ValueError(f"Unknown power tier: {power_tier}")
    metadata = get_archetype_metadata(archetype_id)
    tier_to_level = {
        "soft_entry": 1,
        "identity_visible": 2,
        "build_testing": 3,
        "route_exam": 4,
    }
    level = tier_to_level[power_tier]
    is_profile_pilot = archetype_id in PROFILE_POLICY_PILOT_ARCHETYPE_IDS
    skill_levels: dict[str, int] = {}
    for skill_id in metadata.get("preferred_skill_ids", []):
        if get_skill(skill_id) and (not is_profile_pilot or _skill_available_at_simulation_stage(skill_id, level)):
            skill_levels[skill_id] = level

    if is_profile_pilot:
        profile = get_expected_rotation_profile(archetype_id) or {}
        profile_skill_ids: list[str] = []
        for key in ("expected_skill_ids", "setup_skill_ids", "payoff_skill_ids", "sustain_skill_ids"):
            for skill_id in profile.get(key, []):
                if skill_id not in profile_skill_ids:
                    profile_skill_ids.append(skill_id)
        for skill_id in profile_skill_ids:
            if _skill_available_at_simulation_stage(skill_id, level):
                skill_levels[skill_id] = level

    return skill_levels


def validate_archetype_preset_coverage() -> list[str]:
    errors = []
    if set(REQUIRED_ARCHETYPE_IDS) - set(ARCHETYPE_METADATA.keys()):
        errors.append("Missing required archetypes in metadata registry.")
    if set(REQUIRED_POWER_TIERS) - set(BASE_TIER_PRESETS.keys()):
        errors.append("Missing required power tiers.")

    allowed_weapon_types = {"melee", "ranged", "magic", "holy"}
    allowed_damage_schools = {"physical", "magic", "holy"}
    allowed_armor_classes = {"heavy", "medium", "light", None}

    for archetype_id in REQUIRED_ARCHETYPE_IDS:
        if archetype_id not in ARCHETYPE_METADATA:
            errors.append(f"{archetype_id}: missing metadata")
            continue
        md = get_archetype_metadata(archetype_id)
        if not md.get("role_tags") or not md.get("strengths") or not md.get("weaknesses"):
            errors.append(f"{archetype_id}: missing role tags/strengths/weaknesses metadata")
        if "preferred_skill_ids" not in md or not isinstance(md["preferred_skill_ids"], list):
            errors.append(f"{archetype_id}: preferred_skill_ids metadata missing")

        for tier in REQUIRED_POWER_TIERS:
            preset = build_archetype_player_preset(archetype_id, tier)
            missing_fields = [f for f in REQUIRED_PLAYER_FIELDS if f not in preset]
            if missing_fields:
                errors.append(f"{archetype_id}@{tier}: missing fields {missing_fields}")
            if preset["weapon_type"] not in allowed_weapon_types:
                errors.append(f"{archetype_id}@{tier}: invalid weapon_type")
            if preset["damage_school"] not in allowed_damage_schools:
                errors.append(f"{archetype_id}@{tier}: invalid damage_school")
            if preset["armor_class"] not in allowed_armor_classes:
                errors.append(f"{archetype_id}@{tier}: invalid armor_class")
            if preset["offhand_profile"] not in ALLOWED_OFFHAND_PROFILES:
                errors.append(f"{archetype_id}@{tier}: invalid offhand_profile")
            encumbrance = preset.get("encumbrance")
            if encumbrance is not None and not isinstance(encumbrance, (int, float)):
                errors.append(f"{archetype_id}@{tier}: invalid encumbrance type")
    return errors
