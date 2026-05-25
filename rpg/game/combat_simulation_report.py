from __future__ import annotations

from collections import defaultdict
from typing import Any

from game.combat_simulation_archetypes import list_alpha_archetype_ids
from game.combat_simulation_matrix import (
    RouteStageMatrixConfig,
    list_alpha_simulation_route_ids,
    list_route_simulation_stages,
    run_route_stage_simulation_matrix,
)
from game.locations import ROUTE_MATCHUP_TARGET_PROFILES

ARCHETYPE_MATCHUP_KEY_MAP = {
    "guardian_shield_1h": "shield_defensive_1h",
    "sword_2h_burst": "sword_2h",
    "axe_2h_bruiser": "axe_2h",
    "daggers_venom": "daggers_venom",
    "daggers_evasion": "daggers_evasion",
    "bow_sniper": "bow_sniper",
    "bow_ranger": "bow_ranger",
    "magic_staff_destruction": "magic_staff_destruction",
    "magic_staff_control": "magic_staff_control",
    "wand_tempo": "wand",
    "holy_staff_solo": "holy_staff_solo_support",
    "holy_rod_paladin": "holy_rod_paladin",
    "tome_toolbox": "tome_toolbox",
    "pure_support_solo_overlay": "pure_support_solo_overlay",
}

TARGET_LABEL_TO_SCORE = {"strong": 1, "normal": 2, "hard": 3, "very_hard": 4}
TARGET_TABLE_LIMIT = 60
SUSPICIOUS_TABLE_LIMIT = 40


def resolve_archetype_matchup_key(archetype_id: str) -> str | None:
    return ARCHETYPE_MATCHUP_KEY_MAP.get(archetype_id)


def normalize_target_matchup_label(label: str) -> str:
    norm = str(label or "").strip().lower()
    aliases = {
        "normal_strong": "normal",
        "normal_hard": "hard",
        "hard_very_hard": "very_hard",
        "very_hard_playable": "very_hard",
        "normal_hard_split": "hard",
    }
    return aliases.get(norm, norm)


def _is_comparable_target_label(normalized_target_label: str) -> bool:
    return normalized_target_label in TARGET_LABEL_TO_SCORE


def compare_observed_pressure_to_target(observed_label: str, target_label: str) -> dict[str, str]:
    observed = str(observed_label or "").strip().lower()
    normalized_target = normalize_target_matchup_label(target_label)

    if observed == "inconclusive":
        return {"alignment": "inconclusive", "notes": "Observed signal is inconclusive in current sample."}

    if observed not in {"strong", "normal", "hard", "very_hard", "dead_or_blocked"}:
        return {"alignment": "inconclusive", "notes": "Observed pressure label is not comparable."}

    if not _is_comparable_target_label(normalized_target):
        return {"alignment": "inconclusive", "notes": "Missing comparable target pressure label."}

    if observed == "dead_or_blocked":
        if normalized_target == "very_hard":
            return {"alignment": "slightly_harder_than_target", "notes": "Observed dead-or-blocked under very-hard target."}
        return {"alignment": "critical_mismatch", "notes": "Observed dead-or-blocked above target expectation."}

    delta = TARGET_LABEL_TO_SCORE[observed] - TARGET_LABEL_TO_SCORE[normalized_target]
    if delta == 0:
        return {"alignment": "aligned", "notes": "Observed pressure aligns with target band."}
    if delta == 1:
        return {"alignment": "slightly_harder_than_target", "notes": "Observed pressure is one band harder than target."}
    if delta >= 2:
        return {"alignment": "harder_than_target", "notes": "Observed pressure is materially harder than target."}
    if delta == -1:
        return {"alignment": "slightly_easier_than_target", "notes": "Observed pressure is one band easier than target."}
    return {"alignment": "easier_than_target", "notes": "Observed pressure is materially easier than target."}


def _is_suspicious(summary: dict[str, Any], normalized_target: str) -> list[str]:
    observed = summary.get("observed_pressure_label")
    has_target = _is_comparable_target_label(normalized_target)
    reasons: list[str] = []

    if has_target and observed == "dead_or_blocked" and normalized_target != "very_hard":
        reasons.append("dead_or_blocked_above_target")
    if has_target and observed == "very_hard" and normalized_target in {"strong", "normal"}:
        reasons.append("very_hard_vs_low_target")
    if has_target and observed == "strong" and normalized_target in {"hard", "very_hard"}:
        reasons.append("strong_vs_high_target")

    if summary.get("timeouts", 0) / max(1, summary.get("runs", 1)) >= 0.4:
        reasons.append("timeout_heavy")
    if summary.get("death_rate", 0.0) >= 0.6 and summary.get("win_rate", 0.0) <= 0.3:
        reasons.append("high_death_low_win")
    return reasons




def _select_route_balanced_suspicious_preview(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if len(rows) <= limit:
        return list(rows)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(rows, key=lambda r: (r.get("route_id", ""), r.get("stage", ""), r.get("archetype_id", ""))):
        grouped[str(row.get("route_id", ""))].append(row)
    routes = sorted(grouped.keys())
    selected: list[dict[str, Any]] = []
    idx_by_route = {route: 0 for route in routes}
    while len(selected) < limit:
        progressed = False
        for route in routes:
            idx = idx_by_route[route]
            bucket = grouped[route]
            if idx < len(bucket):
                selected.append(bucket[idx])
                idx_by_route[route] += 1
                progressed = True
                if len(selected) >= limit:
                    break
        if not progressed:
            break
    return selected

def build_checked_in_alpha_balance_report_config() -> RouteStageMatrixConfig:
    return RouteStageMatrixConfig(
        route_ids=tuple(list_alpha_simulation_route_ids()),
        stages=tuple(list_route_simulation_stages()),
        archetype_ids=tuple(list_alpha_archetype_ids()),
        seeds=(1,),
        max_samples_per_route_stage=1,
        max_turns=50,
        include_raw_runs=False,
    )


def build_alpha_balance_report_data(matrix_result: dict | None = None, config: RouteStageMatrixConfig | None = None) -> dict:
    matrix = matrix_result if matrix_result is not None else run_route_stage_simulation_matrix(config)

    target_comparisons = []
    suspicious_matchups = []
    inconclusive_matchups = []
    missing_target_matchups = []

    route_rollups: dict[str, dict[str, Any]] = defaultdict(lambda: {"runs": 0, "wins": 0, "losses": 0, "timeouts": 0})
    archetype_rollups: dict[str, dict[str, Any]] = defaultdict(lambda: {"runs": 0, "wins": 0, "losses": 0, "timeouts": 0})

    for summary in matrix.get("summaries", []):
        route_id = summary["route_id"]
        archetype_id = summary["archetype_id"]

        for bucket in (route_rollups[route_id], archetype_rollups[archetype_id]):
            bucket["runs"] += summary["runs"]
            bucket["wins"] += summary["wins"]
            bucket["losses"] += summary["losses"]
            bucket["timeouts"] += summary["timeouts"]

        matchup_key = resolve_archetype_matchup_key(archetype_id)
        route_targets = (ROUTE_MATCHUP_TARGET_PROFILES.get(route_id, {}) or {}).get("target_matchups", {})
        target_label_raw = route_targets.get(matchup_key) if matchup_key else None
        normalized_target = normalize_target_matchup_label(target_label_raw)
        comparison = compare_observed_pressure_to_target(summary.get("observed_pressure_label", "inconclusive"), target_label_raw or "")

        row = {
            "route_id": route_id,
            "stage": summary["stage"],
            "archetype_id": archetype_id,
            "matchup_key": matchup_key,
            "target_label": target_label_raw,
            "normalized_target_label": normalized_target,
            "observed_label": summary.get("observed_pressure_label"),
            "alignment": comparison["alignment"],
            "notes": comparison["notes"],
            "win_rate": summary.get("win_rate", 0.0),
            "death_rate": summary.get("death_rate", 0.0),
            "timeouts": summary.get("timeouts", 0),
            "runs": summary.get("runs", 0),
        }
        target_comparisons.append(row)

        if row["observed_label"] == "inconclusive":
            inconclusive_matchups.append(row)
        if not _is_comparable_target_label(normalized_target):
            missing_target_matchups.append(row)

        reasons = _is_suspicious(summary, normalized_target)
        if reasons:
            suspicious_matchups.append({**row, "reasons": reasons})

    limitations = list(matrix.get("limitations", [])) + [
        "Alpha diagnostic signal only; not a final balance verdict.",
        "Observed-vs-target comparisons are coarse bands, not proof of tuning direction.",
        "Missing target metadata rows are treated as inconclusive, not mismatch verdicts.",
        "No pack/group runtime matrix in this report version.",
    ]

    return {
        "generated_for_routes": list(matrix.get("routes", [])),
        "stages": list(matrix.get("stages", [])),
        "archetypes": list(matrix.get("archetypes", [])),
        "run_count": int(matrix.get("run_count", 0)),
        "sample_count": int(matrix.get("sample_count", 0)),
        "limitations": limitations,
        "summaries": list(matrix.get("summaries", [])),
        "target_comparisons": target_comparisons,
        "suspicious_matchups": suspicious_matchups,
        "inconclusive_matchups": inconclusive_matchups,
        "missing_target_matchups": missing_target_matchups,
        "route_rollups": dict(route_rollups),
        "archetype_rollups": dict(archetype_rollups),
        "raw_data_pointers": {"source": "run_route_stage_simulation_matrix", "raw_runs_included": bool(matrix.get("runs"))},
    }


def render_alpha_balance_report_markdown(report_data: dict) -> str:
    lines = [
        "# Alpha Route/Class Balance Report v1",
        "",
        "## 1. Summary",
        "This is an alpha diagnostic report using representative solo route-stage samples.",
        "It is a signal artifact for future targeted tuning PRs and is not a final balance verdict.",
        "",
        "## 2. Methodology",
        "- Matrix source: route × stage × archetype deterministic simulation summaries.",
        f"- Routes: {', '.join(report_data.get('generated_for_routes', []))}",
        f"- Stages: {', '.join(report_data.get('stages', []))}",
        f"- Archetypes: {len(report_data.get('archetypes', []))}",
        f"- Total samples: {report_data.get('sample_count', 0)} | total runs: {report_data.get('run_count', 0)}",
        "",
        "## 3. Scope and Non-goals",
        "- No route/mob/skill/reward/formula tuning is performed in this report.",
        "- No live PvE/PvP behavior changes are introduced.",
        "- No pack/group runtime matrix yet.",
        "- No live AFK/autopilot or smart autobattle behavior.",
        "",
        "## 4. Matrix Configuration",
        "- Config is deterministic and representative (solo route-native samples).",
        "",
        "## 5. Route Overview",
        "| Route | Runs | Win Rate | Timeout Rate |",
        "|---|---:|---:|---:|",
    ]
    for route_id, rollup in sorted(report_data.get("route_rollups", {}).items()):
        runs = max(1, rollup["runs"])
        lines.append(f"| {route_id} | {rollup['runs']} | {rollup['wins'] / runs:.2f} | {rollup['timeouts'] / runs:.2f} |")

    lines += ["", "## 6. Archetype Overview", "| Archetype | Runs | Win Rate | Timeout Rate |", "|---|---:|---:|---:|"]
    for archetype_id, rollup in sorted(report_data.get("archetype_rollups", {}).items()):
        runs = max(1, rollup["runs"])
        lines.append(f"| {archetype_id} | {rollup['runs']} | {rollup['wins'] / runs:.2f} | {rollup['timeouts'] / runs:.2f} |")

    lines += ["", "## 7. Target vs Observed Matchup Signals"]
    alignment_counts: dict[str, int] = defaultdict(int)
    target_rows = list(report_data.get("target_comparisons", []))
    for row in target_rows:
        alignment_counts[str(row.get("alignment", "inconclusive"))] += 1
    lines.append("Alignment counts:")
    for key in ("aligned", "slightly_easier_than_target", "easier_than_target", "slightly_harder_than_target", "harder_than_target", "critical_mismatch", "inconclusive"):
        lines.append(f"- {key}: {alignment_counts.get(key, 0)}")
    if len(target_rows) > TARGET_TABLE_LIMIT:
        lines.append(f"Showing first {TARGET_TABLE_LIMIT} of {len(target_rows)} target comparison rows. Full comparison data is available from build_alpha_balance_report_data().")
        lines.append("This table is compact and should not be treated as complete raw output.")
    lines += ["| Route | Stage | Archetype | Target | Observed | Alignment |", "|---|---|---|---|---|---|"]
    for row in target_rows[:TARGET_TABLE_LIMIT]:
        lines.append(
            f"| {row['route_id']} | {row['stage']} | {row['archetype_id']} | {row.get('target_label') or 'n/a'} | {row.get('observed_label') or 'n/a'} | {row.get('alignment') or 'n/a'} |"
        )

    lines += ["", "## 8. Suspicious Matchup Candidates"]
    suspicious_rows = list(report_data.get("suspicious_matchups", []))
    suspicious_by_route: dict[str, int] = defaultdict(int)
    for row in suspicious_rows:
        suspicious_by_route[str(row.get("route_id", ""))] += 1
    lines.append("Suspicious candidates by route:")
    for route_id in sorted(suspicious_by_route.keys()):
        lines.append(f"- {route_id}: {suspicious_by_route[route_id]}")
    if len(suspicious_rows) > SUSPICIOUS_TABLE_LIMIT:
        lines.append(f"Showing first {SUSPICIOUS_TABLE_LIMIT} of {len(suspicious_rows)} suspicious candidates. Full suspicious candidate data is available from build_alpha_balance_report_data().")
        lines.append("Hidden rows are not resolved or dismissed; this is a compact preview only.")
    preview_rows = _select_route_balanced_suspicious_preview(suspicious_rows, SUSPICIOUS_TABLE_LIMIT)
    if not suspicious_rows:
        lines.append("No suspicious candidates triggered current threshold rules.")
    else:
        lines += ["| Route | Stage | Archetype | Observed | Target | Reasons |", "|---|---|---|---|---|---|"]
        for row in preview_rows:
            lines.append(
                f"| {row['route_id']} | {row['stage']} | {row['archetype_id']} | {row['observed_label']} | {row.get('target_label') or 'n/a'} | {', '.join(row.get('reasons', []))} |"
            )

    lines += [
        "",
        "## 9. Route Notes",
        "- Route notes should be used as directional investigation signals, not final conclusions.",
        "",
        "## 10. Archetype Notes",
        "- Archetype notes should guide follow-up targeted testing and tuning PR scope only.",
        "",
        "## 11. Limitations",
    ]
    for item in report_data.get("limitations", []):
        lines.append(f"- {item}")

    lines += [
        "",
        "## 12. Recommended Next Steps",
        "- Add pack/group simulation matrix before final balance decisions.",
        "- Increase seed/sample breadth for suspicious candidates.",
        "- Use targeted follow-up PRs for any actual tuning decisions.",
        "",
        "## 13. Raw Data Pointers",
        "- Source module: `game.combat_simulation_matrix.run_route_stage_simulation_matrix`.",
        f"- Raw runs included in current report data object: {report_data.get('raw_data_pointers', {}).get('raw_runs_included', False)}.",
    ]
    return "\n".join(lines) + "\n"


def build_default_alpha_balance_report_data() -> dict:
    return build_alpha_balance_report_data(config=build_checked_in_alpha_balance_report_config())
