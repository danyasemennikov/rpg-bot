"""Diagnostic skeleton helpers for balance audit checks.

This module is reporting-only and must not raise runtime gameplay errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FLAG_MISSING_BALANCE_LEVEL = "missing_balance_level"
FLAG_MISSING_ENCOUNTER_LEVEL = "missing_encounter_level"
FLAG_MISSING_MOB_ROLE = "missing_mob_role"
FLAG_UNSCALED_TEMPLATE_REUSED_ACROSS_DEPTHS = "unscaled_template_reused_across_depths"
FLAG_WEAK_ROUTE_EXAM_SAMPLE = "weak_route_exam_sample"
FLAG_MISSING_PRESSURE_SAMPLE = "missing_pressure_sample"
FLAG_MISSING_ELITE_SAMPLE = "missing_elite_sample"
FLAG_MISSING_PACK_SAMPLE = "missing_pack_sample"
FLAG_INVALID_NODE_DEPTH = "invalid_node_depth"
FLAG_UNDERLEVELED_MOB_FOR_NODE = "underleveled_mob_for_node"
FLAG_OVERLEVELED_PLAYER_FOR_SAMPLE = "overleveled_player_for_sample"
FLAG_HARD_TARGET_TESTED_ON_WEAK_SAMPLE = "hard_target_tested_on_weak_sample"
FLAG_OVERCLEAN_WIN = "overclean_win"
FLAG_POLICY_FAILURE_GUARD_LOOP = "policy_failure_guard_loop"
FLAG_SUPPORT_OVERSTALL = "support_overstall"
FLAG_MISSING_SIMULATION_GEAR_PRESET = "missing_simulation_gear_preset"
FLAG_MISSING_MOB_SCALING_CONTEXT = "missing_mob_scaling_context"
FLAG_MISSING_FINAL_MOB_STATS = "missing_final_mob_stats"

PRESSURE_OR_HIGH_ROLES = {"pressure", "elite", "pack_member", "pack_leader", "boss"}


@dataclass(frozen=True)
class BalanceAuditFlag:
    flag_id: str
    severity: str
    subject_type: str
    subject_id: str
    message: str
    metadata: dict[str, Any]


def build_balance_audit_flag(
    flag_id: str,
    severity: str,
    subject_type: str,
    subject_id: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> BalanceAuditFlag:
    return BalanceAuditFlag(
        flag_id=flag_id,
        severity=severity,
        subject_type=subject_type,
        subject_id=subject_id,
        message=message,
        metadata=dict(metadata or {}),
    )


def audit_route_stage_sample_metadata(samples_or_rows: list[dict[str, Any]]) -> list[BalanceAuditFlag]:
    flags: list[BalanceAuditFlag] = []
    route_exam_roles: list[str] = []

    for idx, row in enumerate(samples_or_rows):
        row_id = str(row.get("sample_id") or row.get("id") or f"row_{idx}")
        stage = str(row.get("stage") or "")
        mob_role = row.get("mob_role")
        encounter_level = row.get("encounter_level")
        balance_level = row.get("balance_level")

        if balance_level in (None, ""):
            flags.append(
                build_balance_audit_flag(
                    FLAG_MISSING_BALANCE_LEVEL,
                    "warning",
                    "sample_row",
                    row_id,
                    "Balance level is missing in sample metadata.",
                    {"stage": stage},
                )
            )
        if encounter_level in (None, ""):
            flags.append(
                build_balance_audit_flag(
                    FLAG_MISSING_ENCOUNTER_LEVEL,
                    "warning",
                    "sample_row",
                    row_id,
                    "Encounter level is missing in sample metadata.",
                    {"stage": stage},
                )
            )
        if mob_role in (None, ""):
            flags.append(
                build_balance_audit_flag(
                    FLAG_MISSING_MOB_ROLE,
                    "warning",
                    "sample_row",
                    row_id,
                    "Mob role is missing in sample metadata.",
                    {"stage": stage},
                )
            )
        elif stage == "route_exam":
            route_exam_roles.append(str(mob_role))

    if route_exam_roles and not any(role in PRESSURE_OR_HIGH_ROLES for role in route_exam_roles):
        flags.append(
            build_balance_audit_flag(
                FLAG_WEAK_ROUTE_EXAM_SAMPLE,
                "warning",
                "route_exam",
                "route_exam_sample_set",
                "Route exam sample set has no pressure/elite/pack role coverage.",
                {"roles": sorted(set(route_exam_roles))},
            )
        )

    return flags


def _parse_numeric_depth(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and stripped.isdigit():
            return int(stripped)
        return None
    return None


def audit_repeated_template_depth_scaling(rows: list[dict[str, Any]]) -> list[BalanceAuditFlag]:
    flags: list[BalanceAuditFlag] = []
    grouped: dict[str, list[dict[str, Any]]] = {}

    for idx, row in enumerate(rows):
        template = row.get("mob_template") or row.get("mob_id")
        if not template:
            continue

        row_id = str(row.get("sample_id") or row.get("id") or f"row_{idx}")
        raw_depth = row.get("node_depth")
        parsed_depth = _parse_numeric_depth(raw_depth)

        if raw_depth not in (None, "") and parsed_depth is None:
            flags.append(
                build_balance_audit_flag(
                    FLAG_INVALID_NODE_DEPTH,
                    "warning",
                    "sample_row",
                    row_id,
                    "Node depth is not numeric and was skipped for repeated-template depth scaling audit.",
                    {
                        "mob_template": str(template),
                        "node_depth": raw_depth,
                    },
                )
            )
            continue

        grouped.setdefault(str(template), []).append({**row, "_parsed_node_depth": parsed_depth})

    for template_id, template_rows in grouped.items():
        if len(template_rows) < 2:
            continue

        stats_signatures: dict[tuple[Any, ...], list[int]] = {}
        for row in template_rows:
            depth = row.get("_parsed_node_depth")
            if depth is None:
                continue
            signature = (
                row.get("encounter_level"),
                row.get("final_hp"),
                row.get("final_attack"),
                row.get("final_defense"),
            )
            stats_signatures.setdefault(signature, []).append(depth)

        for signature, depths in stats_signatures.items():
            if len(depths) < 2:
                continue
            if max(depths) - min(depths) >= 2:
                flags.append(
                    build_balance_audit_flag(
                        FLAG_UNSCALED_TEMPLATE_REUSED_ACROSS_DEPTHS,
                        "warning",
                        "mob_template",
                        template_id,
                        "Mob template appears reused across shallow/deep nodes with identical scaling markers.",
                        {
                            "depths": sorted(depths),
                            "signature": {
                                "encounter_level": signature[0],
                                "final_hp": signature[1],
                                "final_attack": signature[2],
                                "final_defense": signature[3],
                            },
                        },
                    )
                )

    return flags


def summarize_balance_audit_flags(flags: list[BalanceAuditFlag]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for flag in flags:
        counts[flag.flag_id] = counts.get(flag.flag_id, 0) + 1
    return counts


def audit_pack_sample_coverage(pack_samples: list[dict[str, Any]], route_ids: list[str] | tuple[str, ...], required_stages: list[str] | tuple[str, ...]) -> list[BalanceAuditFlag]:
    flags: list[BalanceAuditFlag] = []
    for route_id in route_ids:
        for stage in required_stages:
            has_sample = any(str(s.get("route_id")) == str(route_id) and str(s.get("stage")) == str(stage) for s in pack_samples)
            if not has_sample:
                flags.append(
                    build_balance_audit_flag(
                        FLAG_MISSING_PACK_SAMPLE,
                        "warning",
                        "pack_route_stage",
                        f"{route_id}:{stage}",
                        "Missing required pack sample coverage.",
                        {"route_id": route_id, "stage": stage},
                    )
                )
    return flags


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except (TypeError, ValueError):
            return 0
    return 0


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except (TypeError, ValueError):
            return None
    return None


def audit_progression_context_rows(rows: list[dict[str, Any]]) -> list[BalanceAuditFlag]:
    flags: list[BalanceAuditFlag] = []
    for idx, row in enumerate(rows):
        row_id = str(row.get("sample_id") or row.get("id") or f"progression_row_{idx}")
        stage = str(row.get("stage") or "")
        player_level = row.get("assumed_player_level", row.get("player_level"))
        encounter_level = row.get("encounter_level")
        mob_role = row.get("mob_role")
        gear_rarity = str(row.get("gear_rarity_assumption") or "")
        enhancement = str(row.get("enhancement_assumption") or "")
        target = str(row.get("target_label") or row.get("normalized_target_label") or "").lower()
        observed_diag = str(row.get("observed_diagnostic_label_v2") or "").lower()
        actions_used = row.get("actions_used")
        winner = str(row.get("winner") or "").lower()
        turns = row.get("turns")
        damage_dealt = row.get("damage_dealt")
        archetype_id = str(row.get("archetype_id") or "").lower()
        clean_win = bool(row.get("clean_win"))
        if player_level in (None, ""):
            flags.append(build_balance_audit_flag(FLAG_MISSING_BALANCE_LEVEL, "warning", "sample_row", row_id, "Player level is missing in progression audit row.", {"stage": stage}))
        if encounter_level in (None, ""):
            flags.append(build_balance_audit_flag(FLAG_MISSING_ENCOUNTER_LEVEL, "warning", "sample_row", row_id, "Encounter level is missing in progression audit row.", {"stage": stage}))
        if mob_role in (None, ""):
            flags.append(build_balance_audit_flag(FLAG_MISSING_MOB_ROLE, "warning", "sample_row", row_id, "Mob role is missing in progression audit row.", {"stage": stage}))
        scaling_status = row.get("scaling_status")
        final_mob_stats = row.get("final_mob_stats")
        if scaling_status != "formula_mob_scaling_v1":
            flags.append(build_balance_audit_flag(FLAG_MISSING_MOB_SCALING_CONTEXT, "warning", "sample_row", row_id, "Mob scaling context is missing or not formula_mob_scaling_v1.", {"stage": stage, "scaling_status": scaling_status}))
        if not isinstance(final_mob_stats, dict) or not final_mob_stats:
            flags.append(build_balance_audit_flag(FLAG_MISSING_FINAL_MOB_STATS, "warning", "sample_row", row_id, "Final scaled mob stats are missing in progression audit row.", {"stage": stage}))
        gear_preset = row.get("simulation_gear_preset")
        assumption_status = str(row.get("assumption_status") or "")
        valid_status = assumption_status in {"formula_budget_v1", "formula_budget_v1_toolbox_fallback"}
        has_valid_preset = False
        if isinstance(gear_preset, dict):
            total_budget = gear_preset.get("total_budget")
            slot_budgets = gear_preset.get("slot_budgets")
            stat_bonuses = gear_preset.get("stat_bonuses")
            has_valid_preset = isinstance(total_budget, (int, float)) and total_budget > 0 and isinstance(slot_budgets, dict) and bool(slot_budgets) and isinstance(stat_bonuses, dict) and bool(stat_bonuses)
        if not (valid_status and has_valid_preset):
            flags.append(build_balance_audit_flag(FLAG_MISSING_SIMULATION_GEAR_PRESET, "warning", "sample_row", row_id, "Simulation gear preset assumptions are missing formula budget context.", {"gear_rarity_assumption": gear_rarity, "enhancement_assumption": enhancement, "assumption_status": assumption_status, "has_simulation_gear_preset": bool(gear_preset)}))
        if target in {"hard", "very_hard"} and str(mob_role or "").lower() == "normal" and stage in {"build_testing", "route_exam"}:
            flags.append(build_balance_audit_flag(FLAG_HARD_TARGET_TESTED_ON_WEAK_SAMPLE, "warning", "sample_row", row_id, "Hard target appears tested on a normal-role sample in a late stage.", {"stage": stage, "target_label": target}))
        if observed_diag == "policy_failure":
            guard_loop = False
            if isinstance(actions_used, dict):
                guard_loop = _safe_int(actions_used.get("guard_fallback", 0)) > 0 or _safe_int(actions_used.get("guard", 0)) > 0
            if not guard_loop:
                guard_rate = _safe_float(row.get("guard_action_rate"))
                guard_loop = bool(guard_rate is not None and guard_rate >= 0.65)
            if guard_loop:
                flags.append(build_balance_audit_flag(FLAG_POLICY_FAILURE_GUARD_LOOP, "warning", "sample_row", row_id, "Policy failure row appears guard-loop driven.", {"actions_used": actions_used}))
        if target in {"hard", "very_hard"} and winner == "player" and clean_win:
            flags.append(build_balance_audit_flag(FLAG_OVERCLEAN_WIN, "warning", "sample_row", row_id, "Win appears unusually clean against high target difficulty.", {"target_label": target}))
        if "support" in archetype_id and winner == "player":
            low_damage = isinstance(damage_dealt, (int, float)) and damage_dealt <= 25
            long_fight = isinstance(turns, int) and turns >= 35
            if low_damage and long_fight and clean_win:
                flags.append(build_balance_audit_flag(FLAG_SUPPORT_OVERSTALL, "warning", "sample_row", row_id, "Support archetype shows a conservative over-stall clean win pattern.", {"turns": turns, "damage_dealt": damage_dealt}))
    return flags
