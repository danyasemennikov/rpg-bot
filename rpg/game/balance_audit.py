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


def audit_repeated_template_depth_scaling(rows: list[dict[str, Any]]) -> list[BalanceAuditFlag]:
    flags: list[BalanceAuditFlag] = []
    grouped: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        template = row.get("mob_template") or row.get("mob_id")
        if not template:
            continue
        grouped.setdefault(str(template), []).append(row)

    for template_id, template_rows in grouped.items():
        if len(template_rows) < 2:
            continue

        stats_signatures: dict[tuple[Any, ...], list[int]] = {}
        for row in template_rows:
            depth = int(row.get("node_depth") or 0)
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
