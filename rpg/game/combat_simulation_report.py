from __future__ import annotations

from collections import defaultdict
from typing import Any

from game.balance_audit import audit_progression_context_rows, summarize_balance_audit_flags
from game.balance_foundation import build_simulation_stage_progression_context
from game.combat_simulation_archetypes import (
    EXECUTABLE_POLICY_REGISTRY,
    build_archetype_player_preset,
    build_archetype_simulation_skill_levels,
    get_archetype_metadata,
    list_alpha_archetype_ids,
)
from game.combat_simulation_matrix import (
    RouteStageMatrixConfig,
    collect_route_stage_samples,
    list_alpha_simulation_route_ids,
    list_route_simulation_stages,
    run_route_stage_simulation_matrix,
)
from game.locations import ROUTE_MATCHUP_TARGET_PROFILES, WORLD_LOCATIONS
from game.mobs import MOBS

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
SCENARIO_PREVIEW_LIMIT = 16
ARCHETYPE_CARD_PREVIEW_LIMIT = 24
TRACE_LIMIT = 10
PROGRESSION_AUDIT_PREVIEW_LIMIT = 20


def build_smoke_alpha_balance_report_config() -> RouteStageMatrixConfig:
    return RouteStageMatrixConfig(
        route_ids=tuple(list_alpha_simulation_route_ids()),
        stages=tuple(list_route_simulation_stages()),
        archetype_ids=tuple(list_alpha_archetype_ids()),
        seeds=(1,),
        max_samples_per_route_stage=1,
        max_turns=50,
        include_raw_runs=False,
    )


def build_diagnostic_alpha_simulation_report_v2_config() -> RouteStageMatrixConfig:
    return RouteStageMatrixConfig(
        route_ids=tuple(list_alpha_simulation_route_ids()),
        stages=tuple(list_route_simulation_stages()),
        archetype_ids=tuple(list_alpha_archetype_ids()),
        seeds=(1, 2, 3),
        max_samples_per_route_stage=2,
        max_turns=50,
        include_raw_runs=True,
    )


def build_checked_in_alpha_balance_report_config() -> RouteStageMatrixConfig:
    return build_smoke_alpha_balance_report_config()


def build_checked_in_alpha_simulation_report_v2_config() -> RouteStageMatrixConfig:
    return RouteStageMatrixConfig(
        route_ids=tuple(list_alpha_simulation_route_ids()),
        stages=tuple(list_route_simulation_stages()),
        archetype_ids=tuple(list_alpha_archetype_ids()),
        seeds=(1,),
        max_samples_per_route_stage=1,
        max_turns=50,
        include_raw_runs=True,
    )


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
    if summary.get("observed_diagnostic_label_v2") in {"policy_failure", "death_blocked", "no_progress_stall", "timeout_stall"}:
        reasons.append("diagnostic_v2_flag")
    if summary.get("observed_diagnostic_label_v2") == "policy_failure" and summary.get("guard_action_rate", 0.0) >= 0.65 and (summary.get("normal_attack_rate", 0.0) + summary.get("skill_use_rate", 0.0)) <= 0.1:
        reasons.append("policy_failure_guard_loop")
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
            if idx < len(grouped[route]):
                selected.append(grouped[route][idx])
                idx_by_route[route] += 1
                progressed = True
                if len(selected) >= limit:
                    break
        if not progressed:
            break
    return selected




def _select_representative_suspicious_traces(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Route-first deterministic representative trace selection.

    Priority:
    1) route coverage (one per route where possible)
    2) then per-route label diversification in round-robin passes
    """
    if limit <= 0 or not rows:
        return []

    def _sort_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
        return (
            str(row.get("observed_diagnostic_label_v2", "")),
            str(row.get("stage", "")),
            str(row.get("archetype_id", "")),
            str(row.get("location_id", "")),
            str(row.get("mob_id", "")),
        )

    route_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        route_groups[str(row.get("route_id", ""))].append(row)

    route_ids = sorted(route_groups.keys())
    route_label_buckets: dict[str, dict[str, list[dict[str, Any]]]] = {}
    route_label_order: dict[str, list[str]] = {}

    for route_id in route_ids:
        label_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in sorted(route_groups[route_id], key=_sort_key):
            label = str(row.get("observed_diagnostic_label_v2", ""))
            label_buckets[label].append(row)
        route_label_buckets[route_id] = dict(label_buckets)
        route_label_order[route_id] = sorted(label_buckets.keys())

    selections: list[dict[str, Any]] = []

    # Pass 1: route coverage first
    for route_id in route_ids:
        labels = route_label_order[route_id]
        if not labels:
            continue
        first_label = labels[0]
        bucket = route_label_buckets[route_id][first_label]
        if bucket:
            selections.append(bucket.pop(0))
            if len(selections) >= limit:
                return selections

    # Pass 2+: route round-robin; rotate labels per route for diversification
    route_label_cursor = {route_id: 0 for route_id in route_ids}
    while len(selections) < limit:
        progressed = False
        for route_id in route_ids:
            labels = route_label_order[route_id]
            if not labels:
                continue
            start = route_label_cursor[route_id]
            picked = False
            for offset in range(len(labels)):
                label = labels[(start + offset) % len(labels)]
                bucket = route_label_buckets[route_id][label]
                if bucket:
                    selections.append(bucket.pop(0))
                    route_label_cursor[route_id] = (start + offset + 1) % len(labels)
                    progressed = True
                    picked = True
                    break
            if len(selections) >= limit:
                break
            if not picked:
                continue
        if not progressed:
            break

    return selections

def _guard_like_action_count(actions: dict[str, Any]) -> int:
    guard_like_keys = {"guard", "guard_fallback", "fallback_guard"}
    total = 0
    for key, value in actions.items():
        if str(key).strip().lower() in guard_like_keys:
            total += int(value)
    return total


def _enrich_run(run: dict[str, Any]) -> dict[str, Any]:
    actions = run.get("actions_used", {}) or {}
    total_actions = max(1, sum(int(v) for v in actions.values()))
    player = build_archetype_player_preset(run["archetype_id"], run["stage"])
    mob_hp_max = (MOBS.get(run["mob_id"], {}) or {}).get("hp")
    player_hp_max = player.get("max_hp")
    player_mana_max = player.get("max_mana")
    guard_like_count = _guard_like_action_count(actions)
    guard_action_rate = guard_like_count / total_actions
    normal_attack_rate = actions.get("normal_attack", 0) / total_actions
    skill_use_rate = len(run.get("skills_used", [])) / total_actions
    return {
        **run,
        "end_reason": "timeout" if run.get("terminated_by_max_turns") else ("player_death" if run.get("player_dead") else "mob_death"),
        "player_hp_remaining_pct": (run.get("player_hp_remaining", 0) / player_hp_max) if player_hp_max else None,
        "player_mana_remaining_pct": (run.get("player_mana_remaining", 0) / player_mana_max) if player_mana_max else None,
        "mob_hp_remaining_pct": (run.get("mob_hp_remaining", 0) / mob_hp_max) if mob_hp_max else None,
        "guard_action_rate": guard_action_rate,
        "guard_like_action_rate": guard_action_rate,
        "normal_attack_rate": normal_attack_rate,
        "skill_use_rate": skill_use_rate,
        "clean_win": run.get("winner") == "player" and run.get("player_hp_remaining", 0) >= (player_hp_max or 1) * 0.6,
        "low_hp_win": run.get("winner") == "player" and run.get("player_hp_remaining", 0) <= (player_hp_max or 1) * 0.2,
        "no_progress": run.get("winner") != "player" and run.get("damage_dealt", 0) <= max(8, (mob_hp_max or 40) * 0.2),
        "timeout_alive_stall": run.get("terminated_by_max_turns") and not run.get("player_dead") and not run.get("mob_dead"),
    }


def _label_diagnostic_v2(summary: dict[str, Any]) -> str:
    if summary["runs"] <= 0:
        return "inconclusive"
    if summary.get("guard_action_rate", 0.0) >= 0.65 and summary.get("no_progress_rate", 0.0) >= 0.4:
        return "policy_failure"
    if summary.get("death_rate", 0.0) >= 0.6 and summary.get("win_rate", 0.0) <= 0.3:
        return "death_blocked"
    if summary.get("timeout_alive_stall_rate", 0.0) >= 0.5 and summary.get("avg_mob_hp_remaining_pct", 0.0) > 0.5:
        return "no_progress_stall"
    if summary.get("timeout_alive_stall_rate", 0.0) >= 0.5:
        return "timeout_stall"
    if summary.get("win_rate", 0.0) >= 0.8 and summary.get("clean_win_rate", 0.0) >= 0.6:
        return "strong_clean"
    if summary.get("win_rate", 0.0) >= 0.7:
        return "strong_but_risky"
    if summary.get("win_rate", 0.0) >= 0.55:
        return "normal"
    if summary.get("win_rate", 0.0) >= 0.35:
        return "hard"
    return "very_hard"


def _build_scenario_cards(matrix: dict) -> list[dict[str, Any]]:
    cards = []
    seen = set()
    runs = matrix.get("runs") or []
    if runs:
        for run in runs:
            key = (run["route_id"], run["stage"], run["location_id"], run["mob_id"])
            if key in seen:
                continue
            seen.add(key)
            loc = WORLD_LOCATIONS.get(run["location_id"], {})
            mob = MOBS.get(run["mob_id"], {})
            cards.append({"route_id": run["route_id"], "stage": run["stage"], "location_id": run["location_id"], "mob_id": run["mob_id"], "spawn_profile": run.get("spawn_profile", "normal"), "sample_tags": list(run.get("sample_tags", [])), "location_name": loc.get("name") or loc.get("display_name"), "mob_stats": {k: mob[k] for k in ("hp", "damage", "accuracy", "evasion", "defense", "magic_defense", "aggression") if k in mob}})
    if cards:
        return cards
    # fallback when raw runs are unavailable
    for route_id in matrix.get("routes", []):
        for stage in matrix.get("stages", []):
            for sample in collect_route_stage_samples(route_id, stage, max_samples=2):
                cards.append({"route_id": sample.route_id, "stage": sample.stage, "location_id": sample.location_id, "mob_id": sample.mob_id, "spawn_profile": sample.spawn_profile, "sample_tags": list(sample.sample_tags), "location_name": (WORLD_LOCATIONS.get(sample.location_id, {}) or {}).get("name")})
    return cards


def _build_archetype_cards(archetype_ids: list[str], stages: list[str]) -> list[dict[str, Any]]:
    cards = []
    for archetype_id in archetype_ids:
        md = get_archetype_metadata(archetype_id)
        for stage in stages:
            preset = build_archetype_player_preset(archetype_id, stage)
            policy_id = md.get("preferred_policy_id")
            policy_registry = EXECUTABLE_POLICY_REGISTRY.get(policy_id, {})
            cards.append({
                "archetype_id": archetype_id,
                "power_tier": stage,
                "matchup_key": resolve_archetype_matchup_key(archetype_id),
                "hp": preset.get("max_hp"),
                "mana": preset.get("max_mana"),
                "weapon_profile": preset.get("weapon_profile"),
                "armor_class": preset.get("armor_class"),
                "offhand_profile": preset.get("offhand_profile"),
                "skill_levels": build_archetype_simulation_skill_levels(archetype_id, stage),
                "preferred_policy_id": policy_id,
                "policy_executable": bool(policy_registry.get("executable")),
                "policy_warning": "guard_heavy_risk" if policy_id == "always_guard_fallback" else "",
            })
    return cards


def _parse_node_depth_from_location_id(location_id: str) -> int | None:
    suffix = str(location_id or "").lower().split("_n", 1)
    if len(suffix) != 2:
        return None
    digits = ""
    for ch in suffix[1]:
        if ch.isdigit():
            digits += ch
        else:
            break
    return int(digits) if digits else None


def _build_progression_audit_rows(enriched_runs: list[dict[str, Any]], summaries: list[dict[str, Any]], target_comparisons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary_map = {(s["route_id"], s["stage"], s["archetype_id"]): s for s in summaries}
    target_map = {(t["route_id"], t["stage"], t["archetype_id"]): t for t in target_comparisons}
    rows = []
    for run in enriched_runs:
        stage_context = build_simulation_stage_progression_context(str(run.get("stage") or ""))
        key = (run.get("route_id"), run.get("stage"), run.get("archetype_id"))
        summary = summary_map.get(key, {})
        target = target_map.get(key, {})
        mob = MOBS.get(str(run.get("mob_id") or ""), {})
        rows.append({
            "route_id": run.get("route_id"),
            "stage": run.get("stage"),
            "archetype_id": run.get("archetype_id"),
            "location_id": run.get("location_id"),
            "mob_id": run.get("mob_id"),
            "mob_template": run.get("mob_id"),
            "node_depth": _parse_node_depth_from_location_id(str(run.get("location_id") or "")),
            "assumed_player_level": stage_context.get("assumed_player_level"),
            "player_level": stage_context.get("assumed_player_level"),
            "player_macro_band": stage_context.get("macro_band"),
            "gear_tier": stage_context.get("gear_tier"),
            "gear_rarity_assumption": stage_context.get("gear_rarity_assumption"),
            "enhancement_assumption": stage_context.get("enhancement_assumption"),
            "skill_level_summary": build_archetype_simulation_skill_levels(str(run.get("archetype_id") or ""), str(run.get("stage") or "")),
            "encounter_level": run.get("encounter_level"),
            "mob_role": run.get("mob_role"),
            "spawn_profile": run.get("spawn_profile"),
            "final_mob_stats": {k: mob[k] for k in ("hp", "damage", "accuracy", "evasion", "defense", "magic_defense") if k in mob},
            "target_label": target.get("normalized_target_label") or target.get("target_label"),
            "observed_label": target.get("observed_label"),
            "observed_diagnostic_label_v2": summary.get("observed_diagnostic_label_v2"),
            "winner": run.get("winner"),
            "end_reason": run.get("end_reason"),
            "turns": run.get("turns"),
            "actions_used": dict(run.get("actions_used", {})),
            "damage_dealt": run.get("damage_dealt"),
            "clean_win": run.get("clean_win"),
            "audit_flag_ids": [],
        })
    flags = audit_progression_context_rows(rows)
    row_flags: dict[str, list[str]] = defaultdict(list)
    for flag in flags:
        row_flags[flag.subject_id].append(flag.flag_id)
    for idx, row in enumerate(rows):
        row_id = f"progression_row_{idx}"
        row["id"] = row_id
        row["audit_flag_ids"] = row_flags.get(row_id, [])
    return rows


def build_alpha_balance_report_data(matrix_result: dict | None = None, config: RouteStageMatrixConfig | None = None) -> dict:
    matrix = matrix_result if matrix_result is not None else run_route_stage_simulation_matrix(config)
    enriched_runs = [_enrich_run(run) for run in matrix.get("runs", [])]
    runs_by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for run in enriched_runs:
        runs_by_key[(run["route_id"], run["stage"], run["archetype_id"])].append(run)

    summaries: list[dict[str, Any]] = []
    target_comparisons = []
    suspicious_matchups = []
    inconclusive_matchups = []
    missing_target_matchups = []

    route_rollups: dict[str, dict[str, Any]] = defaultdict(lambda: {"runs": 0, "wins": 0, "losses": 0, "timeouts": 0})
    archetype_rollups: dict[str, dict[str, Any]] = defaultdict(lambda: {"runs": 0, "wins": 0, "losses": 0, "timeouts": 0})

    for base_summary in matrix.get("summaries", []):
        row_runs = runs_by_key.get((base_summary["route_id"], base_summary["stage"], base_summary["archetype_id"]), [])
        run_count = max(1, len(row_runs))
        summary = dict(base_summary)
        summary["guard_action_rate"] = sum(r["guard_action_rate"] for r in row_runs) / run_count
        summary["normal_attack_rate"] = sum(r["normal_attack_rate"] for r in row_runs) / run_count
        summary["skill_use_rate"] = sum(r["skill_use_rate"] for r in row_runs) / run_count
        summary["no_progress_rate"] = sum(1 for r in row_runs if r["no_progress"]) / run_count
        summary["clean_win_rate"] = sum(1 for r in row_runs if r["clean_win"]) / run_count
        summary["low_hp_win_rate"] = sum(1 for r in row_runs if r["low_hp_win"]) / run_count
        summary["timeout_alive_stall_rate"] = sum(1 for r in row_runs if r["timeout_alive_stall"]) / run_count
        summary["avg_mob_hp_remaining_pct"] = sum((r["mob_hp_remaining_pct"] or 0.0) for r in row_runs) / run_count
        summary["observed_diagnostic_label_v2"] = _label_diagnostic_v2(summary)
        summaries.append(summary)

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
            "observed_diagnostic_label_v2": summary.get("observed_diagnostic_label_v2"),
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

    scenario_cards = _build_scenario_cards({**matrix, "runs": enriched_runs})
    archetype_cards = _build_archetype_cards(list(matrix.get("archetypes", [])), list(matrix.get("stages", [])))

    suspicious_traces = []
    summary_by_key = {(s["route_id"], s["stage"], s["archetype_id"]): s for s in summaries}
    for run in enriched_runs:
        key = (run["route_id"], run["stage"], run["archetype_id"])
        label = summary_by_key.get(key, {}).get("observed_diagnostic_label_v2", "inconclusive")
        if label in {"death_blocked", "timeout_stall", "no_progress_stall", "policy_failure"}:
            suspicious_traces.append({**run, "observed_diagnostic_label_v2": label})
    suspicious_traces = _select_representative_suspicious_traces(suspicious_traces, TRACE_LIMIT)

    progression_audit_rows = _build_progression_audit_rows(enriched_runs, summaries, target_comparisons)
    progression_audit_flags = audit_progression_context_rows(progression_audit_rows)
    return {
        "generated_for_routes": list(matrix.get("routes", [])),
        "stages": list(matrix.get("stages", [])),
        "archetypes": list(matrix.get("archetypes", [])),
        "run_count": int(matrix.get("run_count", 0)),
        "sample_count": int(matrix.get("sample_count", 0)),
        "limitations": limitations,
        "summaries": summaries,
        "target_comparisons": target_comparisons,
        "suspicious_matchups": suspicious_matchups,
        "inconclusive_matchups": inconclusive_matchups,
        "missing_target_matchups": missing_target_matchups,
        "route_rollups": dict(route_rollups),
        "archetype_rollups": dict(archetype_rollups),
        "scenario_cards": scenario_cards,
        "archetype_cards": archetype_cards,
        "suspicious_traces": suspicious_traces,
        "runs": enriched_runs,
        "progression_audit_rows": progression_audit_rows,
        "progression_audit_flags": progression_audit_flags,
        "progression_audit_flag_counts": summarize_balance_audit_flags(progression_audit_flags),
        "raw_data_pointers": {"source": "run_route_stage_simulation_matrix", "raw_runs_included": bool(matrix.get("runs"))},
    }


def render_alpha_balance_report_markdown(report_data: dict) -> str:
    # PR5 renderer behavior
    lines = ["# Alpha Route/Class Balance Report v1", "", "## 1. Summary", "This is an alpha diagnostic report using representative solo route-stage samples.", "It is a signal artifact for future targeted tuning PRs and is not a final balance verdict.", "", "## 2. Methodology", "- Matrix source: route × stage × archetype deterministic simulation summaries.", f"- Routes: {', '.join(report_data.get('generated_for_routes', []))}", f"- Stages: {', '.join(report_data.get('stages', []))}", f"- Archetypes: {len(report_data.get('archetypes', []))}", f"- Total samples: {report_data.get('sample_count', 0)} | total runs: {report_data.get('run_count', 0)}", "", "## 3. Scope and Non-goals", "- No route/mob/skill/reward/formula tuning is performed in this report.", "- No live PvE/PvP behavior changes are introduced.", "- No pack/group runtime matrix yet.", "- No live AFK/autopilot or smart autobattle behavior.", "", "## 4. Matrix Configuration", "- Config is deterministic and representative (solo route-native samples).", "", "## 5. Route Overview", "| Route | Runs | Win Rate | Timeout Rate |", "|---|---:|---:|---:|"]
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
        lines.append(f"| {row['route_id']} | {row['stage']} | {row['archetype_id']} | {row.get('target_label') or 'n/a'} | {row.get('observed_label') or 'n/a'} | {row.get('alignment') or 'n/a'} |")
    lines += ["", "## 8. Suspicious Matchup Candidates"]
    suspicious_rows = list(report_data.get("suspicious_matchups", []))
    suspicious_by_route: dict[str, int] = defaultdict(int)
    for row in suspicious_rows:
        suspicious_by_route[str(row.get("route_id", ""))] += 1
    lines.append("Suspicious candidates by route:")
    for route_id in sorted(suspicious_by_route.keys()):
        lines.append(f"- {route_id}: {suspicious_by_route[route_id]}")
    if len(suspicious_rows) > SUSPICIOUS_TABLE_LIMIT:
        lines.append(f"Showing {SUSPICIOUS_TABLE_LIMIT} route-balanced preview rows out of {len(suspicious_rows)} suspicious candidates. Full suspicious candidate data is available from build_alpha_balance_report_data().")
        lines.append("Hidden rows are not resolved or dismissed; this is a compact route-balanced preview only.")
    preview_rows = _select_route_balanced_suspicious_preview(suspicious_rows, SUSPICIOUS_TABLE_LIMIT)
    if not suspicious_rows:
        lines.append("No suspicious candidates triggered current threshold rules.")
    else:
        lines += ["| Route | Stage | Archetype | Observed | Target | Reasons |", "|---|---|---|---|---|---|"]
        for row in preview_rows:
            lines.append(f"| {row['route_id']} | {row['stage']} | {row['archetype_id']} | {row['observed_label']} | {row.get('target_label') or 'n/a'} | {', '.join(row.get('reasons', []))} |")
    lines += ["", "## 9. Route Notes", "- Route notes should be used as directional investigation signals, not final conclusions.", "", "## 10. Archetype Notes", "- Archetype notes should guide follow-up targeted testing and tuning PR scope only.", "", "## 11. Limitations"]
    for item in report_data.get("limitations", []):
        lines.append(f"- {item}")
    lines += ["", "## 12. Recommended Next Steps", "- Add pack/group simulation matrix before final balance decisions.", "- Increase seed/sample breadth for suspicious candidates.", "- Use targeted follow-up PRs for any actual tuning decisions.", "", "## 13. Raw Data Pointers", "- Source module: `game.combat_simulation_matrix.run_route_stage_simulation_matrix`.", f"- Raw runs included in current report data object: {report_data.get('raw_data_pointers', {}).get('raw_runs_included', False)}."]
    return "\n".join(lines) + "\n"


def render_alpha_simulation_report_v2_markdown(report_data: dict) -> str:
    lines = ["# Alpha Route/Class Balance Report v2", "", "## Summary", "This is a diagnostic and non-final report for future tuning scope decisions.", "", "## Methodology", "- Deterministic representative solo route-stage simulations.", f"- Routes: {', '.join(report_data.get('generated_for_routes', []))}", f"- Stages: {', '.join(report_data.get('stages', []))}", f"- Runs: {report_data.get('run_count', 0)}", "", "## Scope and Non-goals", "- No route/mob/skill/reward/formula tuning.", "- No Combat Core rewrite.", "- No smart autobattle and no live AFK/autopilot.", "- No group/pack simulation matrix.", "", "## Diagnostic Config", "- checked-in compact config: seeds=(1), max_samples_per_route_stage=1, max_turns=50, include_raw_runs=True.", "", "## Scenario Cards", "| route_id | stage | location_id | mob_id | spawn_profile | sample_tags | mob_stats |", "|---|---|---|---|---|---|---|"]
    scenario_cards = report_data.get("scenario_cards", [])
    for card in scenario_cards[:SCENARIO_PREVIEW_LIMIT]:
        lines.append(f"| {card['route_id']} | {card['stage']} | {card['location_id']} | {card['mob_id']} | {card['spawn_profile']} | {', '.join(card.get('sample_tags', []))} | {card.get('mob_stats', {})} |")
    if len(scenario_cards) > SCENARIO_PREVIEW_LIMIT:
        lines.append(f"Showing first {SCENARIO_PREVIEW_LIMIT} of {len(scenario_cards)} scenario cards.")

    lines += ["", "## Archetype Cards", "| archetype_id | power_tier | hp | mana | skill levels | policy metadata | policy warning |", "|---|---|---:|---:|---|---|---|"]
    archetype_cards = report_data.get("archetype_cards", [])
    for card in archetype_cards[:ARCHETYPE_CARD_PREVIEW_LIMIT]:
        lines.append(f"| {card['archetype_id']} | {card['power_tier']} | {card.get('hp')} | {card.get('mana')} | {card.get('skill_levels', {})} | {card.get('preferred_policy_id')} (exec={card.get('policy_executable')}) | {card.get('policy_warning') or 'n/a'} |")
    if len(archetype_cards) > ARCHETYPE_CARD_PREVIEW_LIMIT:
        lines.append(f"Showing first {ARCHETYPE_CARD_PREVIEW_LIMIT} of {len(archetype_cards)} archetype cards.")

    lines += ["", "## Route Overview", "| route_id | runs | win_rate | timeout_rate |", "|---|---:|---:|---:|"]
    for route_id, rollup in sorted(report_data.get("route_rollups", {}).items()):
        runs = max(1, rollup["runs"])
        lines.append(f"| {route_id} | {rollup['runs']} | {rollup['wins']/runs:.2f} | {rollup['timeouts']/runs:.2f} |")

    lines += ["", "## Archetype Overview", "| archetype_id | runs | win_rate | timeout_rate |", "|---|---:|---:|---:|"]
    for archetype_id, rollup in sorted(report_data.get("archetype_rollups", {}).items()):
        runs = max(1, rollup["runs"])
        lines.append(f"| {archetype_id} | {rollup['runs']} | {rollup['wins']/runs:.2f} | {rollup['timeouts']/runs:.2f} |")

    suspicious_rows = list(report_data.get("suspicious_matchups", []))
    suspicious_preview = _select_route_balanced_suspicious_preview(suspicious_rows, SUSPICIOUS_TABLE_LIMIT)
    lines += ["", "## Target vs Observed v2 Signals", "This table shows a compact route-balanced suspicious preview, not the full target-vs-observed matrix."]
    lines.append(
        f"Showing {len(suspicious_preview)} route-balanced suspicious preview rows out of {len(suspicious_rows)} suspicious candidates. "
        "Full target comparison data is available from build_alpha_balance_report_data(). Hidden rows are not resolved or dismissed."
    )
    lines += ["| route | stage | archetype | target | observed_v1 | observed_diagnostic_label_v2 | reasons |", "|---|---|---|---|---|---|---|"]
    for row in suspicious_preview:
        lines.append(f"| {row['route_id']} | {row['stage']} | {row['archetype_id']} | {row.get('target_label') or 'n/a'} | {row.get('observed_label')} | {row.get('observed_diagnostic_label_v2')} | {', '.join(row.get('reasons', []))} |")

    lines += ["", "## Suspicious Clusters", f"Suspicious rows: {len(suspicious_rows)}."]
    progression_rows = list(report_data.get("progression_audit_rows", []))
    progression_counts = dict(report_data.get("progression_audit_flag_counts", {}))
    lines += ["", "## Progression Audit Preview", "This section is diagnostic-only and not a tuning verdict."]
    if progression_counts:
        lines.append("Flag counts:")
        for flag_id in sorted(progression_counts.keys()):
            lines.append(f"- {flag_id}: {progression_counts[flag_id]}")
    else:
        lines.append("No progression audit flags were emitted.")
    lines += ["| route | stage | archetype | assumed_player_level | gear_tier | mob | node_depth | encounter_level | mob_role | target | observed_diagnostic_label_v2 | audit flags |", "|---|---|---|---:|---|---|---:|---|---|---|---|---|"]
    preview = progression_rows[:PROGRESSION_AUDIT_PREVIEW_LIMIT]
    for row in preview:
        lines.append(f"| {row.get('route_id')} | {row.get('stage')} | {row.get('archetype_id')} | {row.get('assumed_player_level')} | {row.get('gear_tier')} | {row.get('mob_id')} | {row.get('node_depth')} | {row.get('encounter_level')} | {row.get('mob_role')} | {row.get('target_label')} | {row.get('observed_diagnostic_label_v2')} | {', '.join(row.get('audit_flag_ids', []))} |")
    if len(progression_rows) > PROGRESSION_AUDIT_PREVIEW_LIMIT:
        lines.append(f"Showing first {PROGRESSION_AUDIT_PREVIEW_LIMIT} of {len(progression_rows)} progression audit rows. Hidden rows are not resolved or dismissed.")

    lines += ["", "## Representative Suspicious Fight Traces"]
    traces = report_data.get("suspicious_traces", [])
    if not traces:
        lines.append("No suspicious traces were detected for this deterministic compact run.")
    else:
        lines.append(f"Showing up to {TRACE_LIMIT} route-balanced representative suspicious traces. Hidden traces are not resolved or dismissed.")
        lines += ["| route_id | stage | archetype_id | location_id | mob_id | winner | end_reason | turns | actions_used | skills_used |", "|---|---|---|---|---|---|---|---:|---|---|"]
        for trace in traces[:TRACE_LIMIT]:
            lines.append(f"| {trace['route_id']} | {trace['stage']} | {trace['archetype_id']} | {trace['location_id']} | {trace['mob_id']} | {trace['winner']} | {trace['end_reason']} | {trace['turns']} | {trace.get('actions_used', {})} | {trace.get('skills_used', [])} |")

    lines += ["", "## Diagnostic Label Definitions", "strong_clean, strong_but_risky, normal, hard, very_hard, death_blocked, timeout_stall, no_progress_stall, resource_collapse, policy_failure, inconclusive.", "", "## Limitations"]
    for item in report_data.get("limitations", []):
        lines.append(f"- {item}")
    lines += ["", "## Recommended Next Steps", "- Use this report to scope targeted follow-up tuning PRs only.", "", "## Raw Data Pointers", "- Source module: `game.combat_simulation_matrix.run_route_stage_simulation_matrix`.", f"- Raw runs included in current report data object: {report_data.get('raw_data_pointers', {}).get('raw_runs_included', False)}."]
    return "\n".join(lines) + "\n"


def build_default_alpha_balance_report_data() -> dict:
    return build_alpha_balance_report_data(config=build_checked_in_alpha_balance_report_config())


def build_default_alpha_simulation_report_v2_data() -> dict:
    return build_alpha_balance_report_data(config=build_checked_in_alpha_simulation_report_v2_config())
