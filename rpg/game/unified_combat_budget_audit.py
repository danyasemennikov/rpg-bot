from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from game.combat_simulation_archetypes import get_archetype_metadata, list_alpha_archetype_ids
from game.equipment_budget import (
    ARCHETYPE_PROFILE_MAP,
    PROFILE_WEIGHTS,
    allocate_budget_to_stats,
    calculate_slot_budget,
)


@dataclass(frozen=True)
class CombatBudgetLevelBand:
    id: str
    anchor_level: int


@dataclass(frozen=True)
class CombatBudgetGearState:
    id: str
    item_level_offset: int
    rarity: str
    enhancement_level: int
    allocation_quality: str
    allocation_multiplier: float
    pvp_equal_budget_baseline: bool


@dataclass(frozen=True)
class CombatBudgetAuditMode:
    id: str
    row_limit: int | None
    notes: str


LEVEL_BANDS = (
    CombatBudgetLevelBand("starter", 5),
    CombatBudgetLevelBand("identity", 20),
    CombatBudgetLevelBand("build_online", 35),
    CombatBudgetLevelBand("midgame", 55),
    CombatBudgetLevelBand("advanced", 75),
    CombatBudgetLevelBand("endgame", 95),
)

GEAR_STATES = (
    CombatBudgetGearState("undergeared", -8, "common", 0, "imperfect", 0.86, False),
    CombatBudgetGearState("baseline_expected", 0, "uncommon", 2, "normal", 1.00, True),
    CombatBudgetGearState("enhanced_expected", 3, "rare", 5, "role_aligned", 1.05, True),
    CombatBudgetGearState("optimized", 5, "epic", 7, "strong_role_aligned", 1.10, True),
    CombatBudgetGearState("overgeared_high_enhancement", 8, "legendary", 12, "stress_test", 1.14, False),
)

AUDIT_MODES = (
    CombatBudgetAuditMode("compact_checked_in", None, "Bounded deterministic checked-in audit: all alpha archetypes, all PR5 level bands, all PR5 gear states."),
    CombatBudgetAuditMode("full_audit", None, "Full deterministic audit over the same first-version PR5 budget grid."),
)

RISK_TAG_IDS = (
    "weapon_family_overbudget",
    "weapon_family_underbudget",
    "armor_budget_overbudget",
    "gear_scaling_spike",
    "enhancement_scaling_risk",
    "secondary_stat_concentration_risk",
    "skill_economy_risk",
    "pvp_burst_toxicity",
    "pvp_stall_toxicity",
    "pve_only_overperformance",
    "pvp_only_toxicity",
    "route_pressure_suspect_player_side",
    "route_pressure_confirmed",
    "simulation_policy_artifact",
)

SLOTS = ("weapon", "armor", "offhand", "ring1", "ring2", "amulet")
DPS_ROLE_TAGS = {"melee_dps", "burst", "assassin", "dot", "tempo", "ranged_dps", "caster", "magic_dps"}
DEFENSIVE_ROLE_TAGS = {"tank", "frontline", "bruiser", "sustain", "support", "healer", "control"}
SECONDARY_STATS = {"accuracy_bonus", "evasion_bonus", "crit_chance_bonus", "block_chance_bonus"}
MAJOR_STAT_LIMIT = 5
STAGE_TO_LEVEL_BAND = {"build_testing": "advanced", "route_exam": "endgame"}
ROUTE_PRESSURE_GEAR_STATES = {"baseline_expected", "enhanced_expected", "optimized"}


def list_level_bands() -> list[dict[str, Any]]:
    return [asdict(level_band) for level_band in LEVEL_BANDS]


def list_gear_states() -> list[dict[str, Any]]:
    return [asdict(gear_state) for gear_state in GEAR_STATES]


def list_audit_modes() -> list[dict[str, Any]]:
    return [asdict(mode) for mode in AUDIT_MODES]


def _level_band_by_id(level_band_id: str) -> CombatBudgetLevelBand:
    for level_band in LEVEL_BANDS:
        if level_band.id == level_band_id:
            return level_band
    raise ValueError(f"Unknown level_band_id: {level_band_id}")


def _gear_state_by_id(gear_state_id: str) -> CombatBudgetGearState:
    for gear_state in GEAR_STATES:
        if gear_state.id == gear_state_id:
            return gear_state
    raise ValueError(f"Unknown gear_state_id: {gear_state_id}")


def _audit_mode_by_id(mode: str) -> CombatBudgetAuditMode:
    for audit_mode in AUDIT_MODES:
        if audit_mode.id == mode:
            return audit_mode
    raise ValueError(f"Unknown audit mode: {mode}")


def _bounded_item_level(anchor_level: int, item_level_offset: int) -> int:
    return max(1, min(100, anchor_level + item_level_offset))


def _allocate_with_quality(total_budget: int, profile_id: str, allocation_multiplier: float) -> dict[str, int | float]:
    adjusted_budget = round(total_budget * allocation_multiplier)
    return allocate_budget_to_stats(adjusted_budget, profile_id)


def build_progression_gear_state_preset(archetype_id: str, level_band_id: str, gear_state_id: str) -> dict[str, Any]:
    """Build a diagnostic-only gear budget preset for PR5 progression audit rows.

    This reuses the existing equipment budget formulas and does not alter the
    existing build_simulation_gear_preset(archetype_id, stage) simulation rail.
    """
    level_band = _level_band_by_id(level_band_id)
    gear_state = _gear_state_by_id(gear_state_id)
    profile_id = ARCHETYPE_PROFILE_MAP.get(archetype_id, "toolbox_hybrid")
    budget_status = "formula_budget_v1_progression_audit"
    if archetype_id not in ARCHETYPE_PROFILE_MAP:
        budget_status = "formula_budget_v1_progression_audit_toolbox_fallback"

    item_level = _bounded_item_level(level_band.anchor_level, gear_state.item_level_offset)
    slot_budgets = {
        slot: calculate_slot_budget(item_level, slot, gear_state.rarity, gear_state.enhancement_level)
        for slot in SLOTS
    }
    total_budget = sum(slot_budgets.values())
    stat_bonuses = _allocate_with_quality(total_budget, profile_id, gear_state.allocation_multiplier)

    return {
        "archetype_id": archetype_id,
        "level_band_id": level_band.id,
        "anchor_level": level_band.anchor_level,
        "gear_state_id": gear_state.id,
        "item_level": item_level,
        "gear_tier": f"T{((item_level - 1) // 10) + 1}",
        "rarity": gear_state.rarity,
        "enhancement_level": gear_state.enhancement_level,
        "allocation_quality": gear_state.allocation_quality,
        "allocation_multiplier": gear_state.allocation_multiplier,
        "profile_id": profile_id,
        "slot_budgets": slot_budgets,
        "total_budget": total_budget,
        "stat_bonuses": stat_bonuses,
        "budget_status": budget_status,
        "pvp_equal_budget_baseline": gear_state.pvp_equal_budget_baseline,
        "pvp_gear_gap_or_stress_probe": not gear_state.pvp_equal_budget_baseline,
    }


def _major_stat_bonuses(stat_bonuses: dict[str, int | float]) -> dict[str, int | float]:
    positive = [(stat, value) for stat, value in stat_bonuses.items() if float(value or 0) > 0]
    positive.sort(key=lambda item: (-float(item[1]), item[0]))
    return dict(positive[:MAJOR_STAT_LIMIT])


def _stat_concentration_flags(preset: dict[str, Any]) -> list[str]:
    total_budget = max(1, int(preset.get("total_budget", 0)))
    profile_id = str(preset.get("profile_id", ""))
    weights = PROFILE_WEIGHTS.get(profile_id, {})
    flags: list[str] = []
    if weights:
        top_stat, top_weight = max(weights.items(), key=lambda item: item[1])
        if top_weight >= 0.34:
            flags.append(f"primary_stat_concentration:{top_stat}")
        secondary_weight = sum(weight for stat, weight in weights.items() if stat in SECONDARY_STATS)
        if secondary_weight >= 0.34:
            flags.append("secondary_stat_concentration")
    slot_budgets = dict(preset.get("slot_budgets", {}))
    if slot_budgets.get("weapon", 0) / total_budget >= 0.33:
        flags.append("weapon_slot_concentration")
    if slot_budgets.get("armor", 0) / total_budget >= 0.30:
        flags.append("armor_slot_concentration")
    return sorted(set(flags))


def _budget_baselines(rows_for_band_state: list[dict[str, Any]]) -> dict[str, float]:
    weapon_values = [float(row["gear_preset_summary"]["slot_budgets"].get("weapon", 0)) for row in rows_for_band_state]
    armor_values = [float(row["gear_preset_summary"]["slot_budgets"].get("armor", 0)) for row in rows_for_band_state]
    total_values = [float(row.get("total_budget", 0)) for row in rows_for_band_state]
    return {
        "weapon_avg": sum(weapon_values) / max(1, len(weapon_values)),
        "armor_avg": sum(armor_values) / max(1, len(armor_values)),
        "total_avg": sum(total_values) / max(1, len(total_values)),
    }


def _classify_row_risks(row: dict[str, Any], baselines: dict[str, float], route_pressure_row_keys: set[tuple[str, str]]) -> list[str]:
    tags: list[str] = []
    summary = row["gear_preset_summary"]
    slot_budgets = summary["slot_budgets"]
    role_tags = set(row.get("role_tags", []))
    major_stats = row.get("major_stat_bonuses", {})
    concentration_flags = set(row.get("stat_concentration_flags", []))
    gear_state_id = str(row.get("gear_state_id"))
    level_band_id = str(row.get("level_band_id"))
    archetype_id = str(row.get("archetype_id"))

    weapon_avg = max(1.0, baselines.get("weapon_avg", 1.0))
    armor_avg = max(1.0, baselines.get("armor_avg", 1.0))
    total_avg = max(1.0, baselines.get("total_avg", 1.0))
    weapon_ratio = float(slot_budgets.get("weapon", 0)) / weapon_avg
    armor_ratio = float(slot_budgets.get("armor", 0)) / armor_avg
    total_ratio = float(row.get("total_budget", 0)) / total_avg

    if weapon_ratio >= 1.22 and role_tags & DPS_ROLE_TAGS:
        tags.append("weapon_family_overbudget")
    if weapon_ratio <= 0.82 and role_tags & DPS_ROLE_TAGS:
        tags.append("weapon_family_underbudget")
    if armor_ratio >= 1.18 and row.get("armor_class") == "heavy":
        tags.append("armor_budget_overbudget")
    if total_ratio >= 1.30 or gear_state_id == "overgeared_high_enhancement":
        tags.append("gear_scaling_spike")
    if int(summary.get("enhancement_level", 0)) >= 10:
        tags.append("enhancement_scaling_risk")
    if "secondary_stat_concentration" in concentration_flags:
        tags.append("secondary_stat_concentration_risk")
    if (role_tags & {"healer", "support", "control"}) or float(major_stats.get("max_mana_bonus", 0) or 0) >= 0.18 * max(1, row.get("anchor_level", 1)):
        tags.append("skill_economy_risk")
    if role_tags & {"burst", "assassin"} and gear_state_id in {"optimized", "overgeared_high_enhancement"}:
        tags.append("pvp_burst_toxicity")
    if (role_tags & DEFENSIVE_ROLE_TAGS) and gear_state_id in {"optimized", "overgeared_high_enhancement"}:
        tags.append("pvp_stall_toxicity")
    if total_ratio >= 1.18 and gear_state_id in {"optimized", "overgeared_high_enhancement"}:
        tags.append("pve_only_overperformance")
    if gear_state_id == "overgeared_high_enhancement" or "pvp_burst_toxicity" in tags or "pvp_stall_toxicity" in tags:
        tags.append("pvp_only_toxicity")
    has_mapped_route_pressure = (archetype_id, level_band_id) in route_pressure_row_keys
    if has_mapped_route_pressure and gear_state_id in ROUTE_PRESSURE_GEAR_STATES:
        tags.append("route_pressure_suspect_player_side")
        tags.append("route_pressure_confirmed")
    policy = str(row.get("preferred_policy_id", ""))
    if policy not in {"always_attack", "always_guard_fallback", "guard_then_attack", "scripted_smoke"}:
        tags.append("simulation_policy_artifact")
    return sorted(set(tags), key=RISK_TAG_IDS.index)


def _summarize_pve_budget(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_level_band: dict[str, list[int]] = defaultdict(list)
    by_gear_state: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        by_level_band[str(row["level_band_id"])].append(int(row["total_budget"]))
        by_gear_state[str(row["gear_state_id"])].append(int(row["total_budget"]))
    return {
        "summary_type": "pve_budget_summary",
        "source": "progression_gear_budget_grid_plus_existing_pve_route_pressure_reconciliation",
        "level_band_avg_budget": {key: round(sum(values) / max(1, len(values)), 2) for key, values in sorted(by_level_band.items())},
        "gear_state_avg_budget": {key: round(sum(values) / max(1, len(values)), 2) for key, values in sorted(by_gear_state.items())},
    }


def _summarize_pvp_budget_proxy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pvp_rows = [row for row in rows if row["gear_preset_summary"].get("pvp_equal_budget_baseline")]
    stress_rows = [row for row in rows if row["gear_preset_summary"].get("pvp_gear_gap_or_stress_probe")]
    toxicity_tags = {"pvp_burst_toxicity", "pvp_stall_toxicity", "pvp_only_toxicity"}
    toxic_rows = [row for row in rows if toxicity_tags & set(row.get("risk_tags", []))]
    return {
        "summary_type": "pvp_budget_proxy",
        "proxy_only": True,
        "real_duel_win_rates": False,
        "reason": "No safe headless PvP duel adapter exists in current simulation rails; live PvP modules are runtime/database flows.",
        "pvp_equal_budget_baseline_gear_states": [state.id for state in GEAR_STATES if state.pvp_equal_budget_baseline],
        "pvp_gear_gap_stress_states": [state.id for state in GEAR_STATES if not state.pvp_equal_budget_baseline],
        "pvp_baseline_gear_states": [state.id for state in GEAR_STATES if state.pvp_equal_budget_baseline],
        "excluded_stress_gear_states": [state.id for state in GEAR_STATES if not state.pvp_equal_budget_baseline],
        "pvp_equal_budget_baseline_rows": len(pvp_rows),
        "pvp_gear_gap_stress_rows": len(stress_rows),
        "pvp_baseline_rows": len(pvp_rows),
        "stress_test_rows": len(stress_rows),
        "toxicity_proxy_rows": len(toxic_rows),
    }


def _route_pressure_reconciliation(pressure_rows: list[dict[str, Any]] | None) -> dict[str, Any]:
    pressure_rows = list(pressure_rows or [])
    lane_counts = Counter(str(row.get("recommended_lane", "inconclusive_lane")) for row in pressure_rows)
    route_counts = Counter(str(row.get("route_id", "unknown")) for row in pressure_rows)
    stage_counts = Counter(str(row.get("stage", "unknown")) for row in pressure_rows)

    mob_pressure_rows = [
        row
        for row in pressure_rows
        if row.get("recommended_lane") == "mob_pressure_lane"
        and str(row.get("stage", "")) in STAGE_TO_LEVEL_BAND
    ]
    archetype_counts = Counter(str(row.get("archetype_id", "unknown")) for row in mob_pressure_rows)
    cluster_counts = Counter(
        (str(row.get("archetype_id", "unknown")), str(row.get("route_id", "unknown")), str(row.get("stage", "unknown")))
        for row in mob_pressure_rows
    )
    route_pressure_row_key_tuples = {
        (str(row.get("archetype_id", "unknown")), STAGE_TO_LEVEL_BAND[str(row.get("stage", ""))])
        for row in mob_pressure_rows
    }
    route_pressure_row_keys = [
        {"archetype_id": archetype_id, "level_band_id": level_band_id}
        for archetype_id, level_band_id in sorted(route_pressure_row_key_tuples)
    ]

    suspect_archetypes = []
    for archetype_id, count in sorted(archetype_counts.items(), key=lambda item: (-item[1], item[0])):
        clusters = [
            {"route_id": route_id, "stage": stage, "count": cluster_count}
            for (cluster_arch, route_id, stage), cluster_count in sorted(
                cluster_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
            if cluster_arch == archetype_id
        ]
        suspect_archetypes.append(
            {
                "archetype_id": archetype_id,
                "mob_pressure_count": count,
                "route_stage_clusters": clusters[:5],
            }
        )

    return {
        "available": True,
        "source": "PR4 pressure attribution lanes when supplied by report_data; empty when standalone audit is built.",
        "compact_pr4_lane_counts": dict(sorted(lane_counts.items())),
        "pressure_evidence_counts": {
            "by_route_id": dict(sorted(route_counts.items())),
            "by_stage": dict(sorted(stage_counts.items())),
            "by_recommended_lane": dict(sorted(lane_counts.items())),
        },
        "route_stage_archetype_clusters": [
            {"archetype_id": archetype_id, "route_id": route_id, "stage": stage, "count": count}
            for (archetype_id, route_id, stage), count in sorted(cluster_counts.items(), key=lambda item: (-item[1], item[0]))[:20]
        ],
        "route_pressure_row_tag_keys": route_pressure_row_keys,
        "suspect_player_side_archetypes": suspect_archetypes,
        "interpretation": "Route pressure is reconciled as scoped mob_pressure_lane evidence only; PR5 does not convert PR4 lanes into tuning changes.",
    }


def _top_findings(risk_counts: dict[str, int]) -> list[str]:
    if not risk_counts:
        return ["No deterministic PR5 risk tags were emitted for the selected audit scope."]
    findings = []
    for risk_id, count in sorted(risk_counts.items(), key=lambda item: (-item[1], item[0]))[:5]:
        findings.append(f"{risk_id}: {count} audit rows")
    return findings


def build_unified_combat_budget_audit(
    *,
    mode: str = "compact_checked_in",
    pressure_attribution_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    audit_mode = _audit_mode_by_id(mode)
    pressure_reconciliation = _route_pressure_reconciliation(pressure_attribution_rows)
    route_pressure_row_keys = {
        (str(item.get("archetype_id")), str(item.get("level_band_id")))
        for item in pressure_reconciliation.get("route_pressure_row_tag_keys", [])
    }
    rows: list[dict[str, Any]] = []

    for archetype_id in list_alpha_archetype_ids():
        metadata = get_archetype_metadata(archetype_id)
        for level_band in LEVEL_BANDS:
            for gear_state in GEAR_STATES:
                preset = build_progression_gear_state_preset(archetype_id, level_band.id, gear_state.id)
                major_stats = _major_stat_bonuses(dict(preset["stat_bonuses"]))
                row = {
                    "archetype_id": archetype_id,
                    "level_band_id": level_band.id,
                    "anchor_level": level_band.anchor_level,
                    "gear_state_id": gear_state.id,
                    "weapon_profile": metadata.get("weapon_profile"),
                    "armor_class": metadata.get("armor_class"),
                    "offhand_profile": metadata.get("offhand_profile"),
                    "role_tags": list(metadata.get("role_tags", [])),
                    "preferred_policy_id": metadata.get("preferred_policy_id"),
                    "gear_preset_summary": {
                        "item_level": preset["item_level"],
                        "gear_tier": preset["gear_tier"],
                        "rarity": preset["rarity"],
                        "enhancement_level": preset["enhancement_level"],
                        "allocation_quality": preset["allocation_quality"],
                        "profile_id": preset["profile_id"],
                        "slot_budgets": dict(preset["slot_budgets"]),
                        "budget_status": preset["budget_status"],
                        "pvp_equal_budget_baseline": preset["pvp_equal_budget_baseline"],
                        "pvp_gear_gap_or_stress_probe": preset["pvp_gear_gap_or_stress_probe"],
                    },
                    "total_budget": preset["total_budget"],
                    "major_stat_bonuses": major_stats,
                    "stat_concentration_flags": _stat_concentration_flags(preset),
                    "risk_tags": [],
                }
                rows.append(row)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["level_band_id"]), str(row["gear_state_id"]))].append(row)
    baselines_by_key = {key: _budget_baselines(group_rows) for key, group_rows in grouped.items()}
    for row in rows:
        key = (str(row["level_band_id"]), str(row["gear_state_id"]))
        row["risk_tags"] = _classify_row_risks(row, baselines_by_key[key], route_pressure_row_keys)

    rows = sorted(rows, key=lambda row: (row["archetype_id"], row["anchor_level"], row["gear_state_id"]))
    if audit_mode.row_limit is not None:
        rows = rows[: audit_mode.row_limit]

    risk_counts = Counter(tag for row in rows for tag in row.get("risk_tags", []))
    risk_counts_dict = dict(sorted(risk_counts.items(), key=lambda item: (-item[1], item[0])))
    recommended_tuning_order = [
        "1. Review PR4 route-pressure reconciliation before tuning mobs or routes.",
        "2. Review overgeared/enhancement stress rows separately from PvP baseline rows.",
        "3. Review PvP proxy burst/stall toxicity before any live duel ruleset changes.",
        "4. Only after diagnostic review, use separate future PRs for actual tuning proposals.",
    ]

    return {
        "available": True,
        "mode": audit_mode.id,
        "level_bands": list_level_bands(),
        "gear_states": list_gear_states(),
        "audit_rows": rows,
        "risk_counts": risk_counts_dict,
        "top_systemic_findings": _top_findings(risk_counts_dict),
        "pve_budget_summary": _summarize_pve_budget(rows),
        "pvp_budget_proxy_summary": _summarize_pvp_budget_proxy(rows),
        "pr4_route_pressure_reconciliation": pressure_reconciliation,
        "recommended_tuning_order": recommended_tuning_order,
        "notes": [
            "Balance V2 PR5 is diagnostic-only and applies no tuning.",
            "All current alpha archetypes, six level bands, and five gear states are included.",
            "PvP coverage is a clearly labeled budget proxy, not real headless duel win rates; equal-budget baseline uses baseline_expected, enhanced_expected, and optimized only.",
            "No live gameplay/runtime/formula/equipment/live mob/economy/targeting/teleport/live group combat changes are made.",
        ],
    }
