from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from typing import Any

from game.balance_audit import audit_progression_context_rows, summarize_balance_audit_flags
from game.balance_foundation import build_simulation_stage_progression_context
from game.combat_simulation_archetypes import (
    EXECUTABLE_POLICY_REGISTRY,
    PROFILE_POLICY_PILOT_ARCHETYPE_IDS,
    build_archetype_player_preset,
    build_archetype_simulation_skill_levels,
    get_archetype_metadata,
    get_expected_rotation_profile,
    list_alpha_archetype_ids,
)
from game.skills import get_skill
from game.combat_simulation_matrix import (
    RouteStageMatrixConfig,
    collect_route_stage_samples,
    list_alpha_simulation_route_ids,
    list_route_simulation_stages,
    resolve_archetype_simulation_policy,
    run_route_stage_simulation_matrix,
)
from game.locations import ROUTE_MATCHUP_TARGET_PROFILES, WORLD_LOCATIONS
from game.equipment_budget import build_simulation_gear_preset
from game.mob_scaling import PR3_LATE_STAGE_MOB_PRESSURE_REFINEMENTS
from game.mobs import MOBS
from game.pack_simulation import PACK_REQUIRED_STAGES, run_pack_simulation_matrix
from game.unified_combat_budget_audit import build_unified_combat_budget_audit

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
PACK_PREVIEW_LIMIT = 20
OBSERVABILITY_PREVIEW_LIMIT = 8
OBSERVABILITY_TRACE_CASE_LIMIT = 3
PRESSURE_ATTRIBUTION_ROW_LIMIT = 40
PRESSURE_ATTRIBUTION_CLUSTER_LIMIT = 12
PR13_TOP_CLUSTER_LIMIT = 8
LATE_STAGE_TARGETED_STAGES = {"build_testing", "route_exam"}
EARLY_TARGET_CALIBRATION_STAGES = {"soft_entry", "identity_visible"}
ACTIONABLE_TARGET_STAGES = {"build_testing", "route_exam"}
PR4_CONFIDENCE_SEEDS = (1, 2, 3)
PR4_CONFIDENCE_LANES = (
    "mob_pressure_lane",
    "route_expectation_lane",
    "bad_matchup_review_lane",
    "inconclusive_lane",
)
PR4_CLUSTER_PREVIEW_LIMIT = 8


@dataclass(frozen=True)
class BalanceReportMode:
    name: str
    matrix_config: RouteStageMatrixConfig
    description: str


def build_balance_report_mode(name: str = "compact_regression") -> BalanceReportMode:
    if name == "compact_regression":
        return BalanceReportMode(
            name="compact_regression",
            matrix_config=RouteStageMatrixConfig(
                route_ids=tuple(list_alpha_simulation_route_ids()),
                stages=tuple(list_route_simulation_stages()),
                archetype_ids=tuple(list_alpha_archetype_ids()),
                seeds=(1,),
                max_samples_per_route_stage=1,
                max_turns=50,
                include_raw_runs=True,
                include_turn_trace=True,
                max_trace_turns=6,
            ),
            description="Fast checked-in compact regression mode with capped suspicious fight traces.",
        )
    if name == "expanded_balance":
        return BalanceReportMode(
            name="expanded_balance",
            matrix_config=RouteStageMatrixConfig(
                route_ids=tuple(list_alpha_simulation_route_ids()),
                stages=tuple(list_route_simulation_stages()),
                archetype_ids=tuple(list_alpha_archetype_ids()),
                seeds=(1, 2, 3, 4, 5),
                max_samples_per_route_stage=2,
                max_turns=50,
                include_raw_runs=True,
                include_turn_trace=True,
                max_trace_turns=12,
            ),
            description="Expanded balance review mode with more seeds and capped traces; not used for the checked-in compact markdown by default.",
        )
    raise ValueError(f"Unknown balance report mode: {name}")

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
    return build_balance_report_mode("compact_regression").matrix_config


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


def _select_route_balanced_pack_preview(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if len(rows) <= limit:
        return list(rows)
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    sorted_rows = sorted(rows, key=lambda r: (r.get("route_id", ""), r.get("stage", ""), r.get("archetype_id", ""), r.get("pack_id", "")))
    bucketed: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in sorted_rows:
        bucketed[(str(row.get("route_id", "")), str(row.get("stage", "")))].append(row)

    # Pass 1: guarantee route+stage coverage where possible.
    for bucket_key in sorted(bucketed.keys()):
        if len(selected) >= limit:
            break
        row = bucketed[bucket_key][0]
        row_key = (str(row.get("route_id", "")), str(row.get("stage", "")), str(row.get("archetype_id", "")), str(row.get("pack_id", "")))
        if row_key not in seen:
            selected.append(row)
            seen.add(row_key)

    # Pass 2: route-balanced fill for remaining slots.
    grouped_by_route: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted_rows:
        grouped_by_route[str(row.get("route_id", ""))].append(row)
    routes = sorted(grouped_by_route.keys())
    idx_by_route = {route: 0 for route in routes}
    while len(selected) < limit:
        progressed = False
        for route in routes:
            while idx_by_route[route] < len(grouped_by_route[route]):
                row = grouped_by_route[route][idx_by_route[route]]
                idx_by_route[route] += 1
                row_key = (str(row.get("route_id", "")), str(row.get("stage", "")), str(row.get("archetype_id", "")), str(row.get("pack_id", "")))
                if row_key in seen:
                    continue
                selected.append(row)
                seen.add(row_key)
                progressed = True
                break
            if len(selected) >= limit:
                break
        if not progressed:
            break
    return selected



def _resolve_mob_hp_max_for_diagnostics(run: dict[str, Any]) -> tuple[int | float | None, str]:
    final_hp = (run.get("final_mob_stats") or {}).get("hp")
    if isinstance(final_hp, (int, float)) and final_hp > 0:
        return final_hp, "final_mob_stats"

    base_hp = (run.get("base_mob_stats") or {}).get("hp")
    if isinstance(base_hp, (int, float)) and base_hp > 0:
        return base_hp, "base_mob_stats"

    template_hp = (MOBS.get(run.get("mob_id"), {}) or {}).get("hp")
    if isinstance(template_hp, (int, float)) and template_hp > 0:
        return template_hp, "mobs_template"

    return None, "missing"

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
    mob_hp_max, mob_hp_source = _resolve_mob_hp_max_for_diagnostics(run)
    player_hp_max = player.get("max_hp")
    player_mana_max = player.get("max_mana")
    guard_like_count = _guard_like_action_count(actions)
    guard_action_rate = guard_like_count / total_actions
    normal_attack_rate = actions.get("normal_attack", 0) / total_actions
    skill_use_rate = len(run.get("skills_used", [])) / total_actions
    observability = dict(run.get("observability", {}))
    return {
        **run,
        "end_reason": observability.get("end_reason") or ("timeout" if run.get("terminated_by_max_turns") else ("player_death" if run.get("player_dead") else "player_win")),
        "player_hp_remaining_pct": (run.get("player_hp_remaining", 0) / player_hp_max) if player_hp_max else None,
        "player_mana_remaining_pct": (run.get("player_mana_remaining", 0) / player_mana_max) if player_mana_max else None,
        "mob_hp_remaining_pct": (run.get("mob_hp_remaining", 0) / mob_hp_max) if mob_hp_max else None,
        "mob_hp_max_for_diagnostics": mob_hp_max,
        "mob_hp_max_source": mob_hp_source,
        "guard_action_rate": guard_action_rate,
        "guard_like_action_rate": guard_action_rate,
        "normal_attack_rate": normal_attack_rate,
        "skill_use_rate": skill_use_rate,
        "clean_win": run.get("winner") == "player" and run.get("player_hp_remaining", 0) >= (player_hp_max or 1) * 0.6,
        "low_hp_win": run.get("winner") == "player" and run.get("player_hp_remaining", 0) <= (player_hp_max or 1) * 0.2,
        "no_progress": run.get("winner") != "player" and run.get("damage_dealt", 0) <= (max(8, mob_hp_max * 0.2) if mob_hp_max else 8),
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
            cards.append({"route_id": run["route_id"], "stage": run["stage"], "location_id": run["location_id"], "mob_id": run["mob_id"], "spawn_profile": run.get("spawn_profile", "normal"), "sample_tags": list(run.get("sample_tags", [])), "location_name": loc.get("name") or loc.get("display_name"), "mob_role": run.get("mob_role"), "encounter_level": run.get("encounter_level"), "scaling_status": run.get("scaling_status"), "base_mob_stats": run.get("base_mob_stats", {}), "final_mob_stats": run.get("final_mob_stats", {}), "mob_stats": {k: mob[k] for k in ("hp", "damage", "accuracy", "evasion", "defense", "magic_defense", "aggression") if k in mob}})
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
            gear_preset = preset.get("simulation_gear_preset", {})
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
                "gear_budget_summary": {
                    "gear_tier": gear_preset.get("gear_tier"),
                    "rarity": gear_preset.get("rarity"),
                    "enhancement_level": gear_preset.get("enhancement_level"),
                    "profile_id": gear_preset.get("profile_id"),
                    "total_budget": gear_preset.get("total_budget"),
                    "budget_status": gear_preset.get("budget_status"),
                },
            })
    return cards



def _classify_policy_status(policy_id: str | None, policy_registry: dict[str, Any]) -> str:
    if not policy_id or policy_id not in EXECUTABLE_POLICY_REGISTRY:
        return "unsupported_policy_label"
    if policy_registry.get("executable"):
        return "executable"
    return "metadata_only"


def _build_policy_coverage_rows(archetype_ids: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for archetype_id in archetype_ids:
        metadata = get_archetype_metadata(archetype_id)
        policy_id = metadata.get("preferred_policy_id")
        policy_registry = EXECUTABLE_POLICY_REGISTRY.get(policy_id, {})
        profile = get_expected_rotation_profile(archetype_id)
        expected_skill_ids = list((profile or {}).get("expected_skill_ids", []))
        missing_expected_skill_ids = [skill_id for skill_id in expected_skill_ids if not get_skill(skill_id)]
        setup_skill_ids = list((profile or {}).get("setup_skill_ids", []))
        payoff_skill_ids = list((profile or {}).get("payoff_skill_ids", []))
        sustain_skill_ids = list((profile or {}).get("sustain_skill_ids", []))
        policy_executable = bool(policy_registry.get("executable"))
        policy_status = _classify_policy_status(policy_id, policy_registry)
        policy_resolution = resolve_archetype_simulation_policy(archetype_id, "build_testing")
        active_policy_status = str(policy_resolution.get("active_simulation_policy_status") or "unknown")
        profile_policy_pilot = archetype_id in PROFILE_POLICY_PILOT_ARCHETYPE_IDS
        profile_policy_executable = bool(policy_resolution.get("profile_policy_executable"))
        reasons: list[str] = []
        if policy_status == "unsupported_policy_label":
            reasons.append("unsupported_policy_label")
        if policy_status == "metadata_only":
            reasons.append("metadata_only_policy")
        if not profile:
            reasons.append("missing_expected_rotation_profile")
        if missing_expected_skill_ids:
            reasons.append("missing_expected_skill")
        if profile and not (setup_skill_ids and payoff_skill_ids):
            reasons.append("missing_setup_payoff_rotation")
        role_tags = set(metadata.get("role_tags", []))
        is_burst_review = policy_id in {"aggressive_burst", "sniper_precision"} or "burst" in role_tags
        if not policy_executable and is_burst_review:
            reasons.append("burst_window_policy_review")
        if policy_id in {"solo_support_sustain", "toolbox_balanced"} or "support" in metadata.get("role_tags", []):
            reasons.append("support_solo_policy_review")
        if profile and (profile.get("mana_sensitive") is None):
            reasons.append("mana_policy_unknown")
        if profile and (profile.get("cooldown_sensitive") is None):
            reasons.append("cooldown_policy_unknown")
        if sustain_skill_ids and not policy_executable:
            reasons.append("sustain_timing_policy_unknown")
        rows.append({
            "archetype_id": archetype_id,
            "preferred_policy_id": policy_id,
            "policy_executable": policy_executable,
            "policy_status": policy_status,
            "active_simulation_policy_id": policy_resolution.get("active_simulation_policy_id"),
            "active_simulation_policy_status": active_policy_status,
            "profile_policy_executable": profile_policy_executable,
            "profile_policy_pilot": profile_policy_pilot,
            "expected_rotation_profile_id": (profile or {}).get("profile_id"),
            "expected_skill_count": len(expected_skill_ids),
            "available_expected_skill_count": len(expected_skill_ids) - len(missing_expected_skill_ids),
            "missing_expected_skill_ids": missing_expected_skill_ids,
            "uses_setup_payoff": bool(setup_skill_ids and payoff_skill_ids),
            "mana_sensitive": bool((profile or {}).get("mana_sensitive", False)),
            "cooldown_sensitive": bool((profile or {}).get("cooldown_sensitive", False)),
            "artifact_reasons": reasons,
        })
    return rows


def _label_mana_pressure(avg_remaining_pct: float, avg_mana_spent: float) -> str:
    if avg_mana_spent <= 0:
        return "no_mana_spend_observed"
    if avg_remaining_pct <= 0.15:
        return "high_mana_pressure"
    if avg_remaining_pct <= 0.35:
        return "moderate_mana_pressure"
    return "low_mana_pressure"


def _label_skill_economy(skill_use_rate: float, normal_attack_fallback_rate: float, mana_pressure_label: str) -> str:
    if skill_use_rate <= 0 and normal_attack_fallback_rate >= 0.75:
        return "normal_attack_fallback_dominant"
    if mana_pressure_label == "high_mana_pressure" and normal_attack_fallback_rate >= 0.5:
        return "mana_constrained_fallback_risk"
    if skill_use_rate >= 0.35:
        return "skill_rotation_visible"
    if skill_use_rate > 0:
        return "limited_skill_use_visible"
    return "skill_use_not_observed"


def _build_skill_economy_rows(enriched_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in enriched_runs:
        grouped[str(run.get("archetype_id"))].append(run)

    rows: list[dict[str, Any]] = []
    for archetype_id in sorted(grouped):
        runs = grouped[archetype_id]
        run_count = max(1, len(runs))
        total_turns = sum(max(1, int(run.get("turns", 0) or 0)) for run in runs)
        total_skills = 0
        total_normals = 0
        total_guard = 0
        mana_spent_total = 0.0
        mana_remaining_pct_total = 0.0
        damage_dealt_per_turn_total = 0.0
        damage_taken_per_turn_total = 0.0
        end_reason_counts: Counter[str] = Counter()
        for run in runs:
            obs = dict(run.get("observability") or {})
            actions = dict(run.get("actions_used") or {})
            total_skills += int(obs.get("skills_used_count", len(run.get("skills_used", []))))
            total_normals += int(obs.get("normal_attacks_used", actions.get("normal_attack", 0)))
            total_guard += int(obs.get("guard_used", actions.get("guard_fallback", 0)))
            mana_spent_total += float(obs.get("mana_spent", 0) or 0)
            mana_remaining_pct_total += float(obs.get("player_mana_remaining_pct", 0.0) or 0.0)
            damage_dealt_per_turn_total += float(obs.get("damage_dealt_per_turn", 0.0) or 0.0)
            damage_taken_per_turn_total += float(obs.get("damage_taken_per_turn", 0.0) or 0.0)
            end_reason_counts[str(obs.get("end_reason") or "unknown")] += 1
        action_denominator = max(1, total_skills + total_normals + total_guard)
        skill_use_rate = total_skills / action_denominator
        normal_attack_fallback_rate = total_normals / action_denominator
        mana_remaining_pct = mana_remaining_pct_total / run_count
        avg_mana_spent = mana_spent_total / run_count
        mana_pressure_label = _label_mana_pressure(mana_remaining_pct, avg_mana_spent)
        rows.append({
            "archetype_id": archetype_id,
            "run_count": len(runs),
            "mana_spent": avg_mana_spent,
            "player_mana_remaining_pct": mana_remaining_pct,
            "skills_used_count": total_skills,
            "normal_attacks_used": total_normals,
            "guard_used": total_guard,
            "damage_dealt_per_turn": damage_dealt_per_turn_total / run_count,
            "damage_taken_per_turn": damage_taken_per_turn_total / run_count,
            "end_reason": dict(end_reason_counts),
            "skill_use_rate": skill_use_rate,
            "normal_attack_fallback_rate": normal_attack_fallback_rate,
            "mana_pressure_label": mana_pressure_label,
            "skill_economy_label": _label_skill_economy(skill_use_rate, normal_attack_fallback_rate, mana_pressure_label),
            "cooldown_observability_available": False,
        })
    return rows


def build_simulation_policy_skill_economy_diagnostics(enriched_runs: list[dict[str, Any]], archetype_ids: list[str]) -> dict[str, Any]:
    policy_rows = _build_policy_coverage_rows(archetype_ids)
    economy_rows = _build_skill_economy_rows(enriched_runs)
    reason_counts: Counter[str] = Counter()
    for row in policy_rows:
        reason_counts.update(row.get("artifact_reasons", []))
    economy_label_counts = Counter(row.get("skill_economy_label") for row in economy_rows)
    top_policy_gaps = sorted(
        [row for row in policy_rows if row.get("artifact_reasons")],
        key=lambda row: (len(row.get("artifact_reasons", [])), row.get("archetype_id", "")),
        reverse=True,
    )[:8]
    return {
        "available": True,
        "policy_coverage_rows": policy_rows,
        "skill_economy_rows": economy_rows,
        "artifact_reason_counts": dict(reason_counts),
        "skill_economy_label_counts": dict(economy_label_counts),
        "top_policy_gaps": top_policy_gaps,
        "recommended_next_tuning_branch": [
            "Resolve simulation policy artifacts before treating PR5 rows as live skill-economy tuning evidence.",
            "Keep PvP in proxy-only budget review until a safe duel adapter exists.",
            "Defer route, mob, gear, and PvP tuning until PR6 diagnostics identify whether gaps are policy artifacts or real economy risks.",
        ],
        "notes": [
            "Balance V2 PR6 is diagnostic/reporting-only and applies no live tuning.",
            "No live gameplay/runtime/formula/equipment/live mob/economy/targeting/teleport/live group combat changes are made.",
            "Cooldown-blocked turn counts are not safely observable in current report rows; cooldown_observability_available=False is intentional follow-up scope.",
        ],
    }


def _merge_counter_from_runs(enriched_runs: list[dict[str, Any]], observability_key: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for run in enriched_runs:
        obs = dict(run.get("observability") or {})
        counts.update(dict(obs.get(observability_key) or {}))
    return counts


def _sorted_count_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: int(count) for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))}


def _build_grouped_fallback_counts(enriched_runs: list[dict[str, Any]], group_key: str) -> dict[str, dict[str, int]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for run in enriched_runs:
        key = str(run.get(group_key) or "unknown")
        obs = dict(run.get("observability") or {})
        grouped[key].update(dict(obs.get("fallback_reason_counts") or {}))
    return {key: _sorted_count_dict(grouped[key]) for key in sorted(grouped)}


def build_simulation_action_resolution_diagnostics(enriched_runs: list[dict[str, Any]]) -> dict[str, Any]:
    fallback_reason_counts = _merge_counter_from_runs(enriched_runs, "fallback_reason_counts")
    action_resolution_counts = _merge_counter_from_runs(enriched_runs, "action_resolution_counts")

    pilot_summary: list[dict[str, Any]] = []
    for archetype_id in PROFILE_POLICY_PILOT_ARCHETYPE_IDS:
        rows = [run for run in enriched_runs if str(run.get("archetype_id")) == archetype_id]
        requested = sum(int((run.get("observability") or {}).get("requested_skill_count", 0) or 0) for run in rows)
        successes = sum(int((run.get("observability") or {}).get("resolved_skill_success_count", 0) or 0) for run in rows)
        normal_fallbacks = sum(int((run.get("observability") or {}).get("normal_attack_fallback_count", 0) or 0) for run in rows)
        fallback_counts: Counter[str] = Counter()
        action_counts: Counter[str] = Counter()
        for run in rows:
            obs = dict(run.get("observability") or {})
            fallback_counts.update(dict(obs.get("fallback_reason_counts") or {}))
            action_counts.update(dict(obs.get("action_resolution_counts") or {}))
        pilot_summary.append({
            "archetype_id": archetype_id,
            "run_count": len(rows),
            "requested_skill_count": requested,
            "resolved_skill_success_count": successes,
            "normal_attack_fallback_count": normal_fallbacks,
            "fallback_reason_counts": _sorted_count_dict(fallback_counts),
            "action_resolution_counts": _sorted_count_dict(action_counts),
        })

    return {
        "available": True,
        "fallback_reason_counts": _sorted_count_dict(fallback_reason_counts),
        "action_resolution_counts": _sorted_count_dict(action_resolution_counts),
        "fallback_reason_counts_by_archetype": _build_grouped_fallback_counts(enriched_runs, "archetype_id"),
        "fallback_reason_counts_by_stage": _build_grouped_fallback_counts(enriched_runs, "stage"),
        "pilot_policy_resolution_summary": pilot_summary,
        "requested_skill_count_total": sum(int((run.get("observability") or {}).get("requested_skill_count", 0) or 0) for run in enriched_runs),
        "resolved_skill_success_count_total": sum(int((run.get("observability") or {}).get("resolved_skill_success_count", 0) or 0) for run in enriched_runs),
        "normal_attack_fallback_count_total": sum(int((run.get("observability") or {}).get("normal_attack_fallback_count", 0) or 0) for run in enriched_runs),
        "notes": [
            "Balance V2 PR8 is diagnostic/simulation/reporting-only and observes action resolution without changing live gameplay.",
            "Fallback reasons classify simulator policy requests that already resolved to normal_attack or guard fallback.",
            "Metadata-only registry policies remain metadata-only; simulation pilot resolution does not globally flip executable flags.",
        ],
    }


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
        stage = str(run.get("stage") or "")
        archetype_id = str(run.get("archetype_id") or "")
        stage_context = build_simulation_stage_progression_context(stage)
        gear_preset = build_simulation_gear_preset(archetype_id, stage)
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
            "gear_rarity_assumption": gear_preset.get("rarity"),
            "enhancement_assumption": gear_preset.get("enhancement_level"),
            "assumption_status": gear_preset.get("budget_status"),
            "simulation_gear_preset": gear_preset,
            "gear_budget_summary": {"total_budget": gear_preset.get("total_budget"), "profile_id": gear_preset.get("profile_id")},
            "skill_level_summary": build_archetype_simulation_skill_levels(str(run.get("archetype_id") or ""), str(run.get("stage") or "")),
            "encounter_level": run.get("encounter_level"),
            "mob_role": run.get("mob_role"),
            "spawn_profile": run.get("spawn_profile"),
            "scaling_status": run.get("scaling_status"),
            "base_mob_stats": dict(run.get("base_mob_stats", {})),
            "final_mob_stats": dict(run.get("final_mob_stats", {})),
            "route_pressure_modifier": dict((run.get("scale_components") or {}).get("route_modifier", {})),
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


def calibrate_target_expectation_row(row: dict[str, Any]) -> dict[str, Any]:
    stage = str(row.get("stage", ""))
    observed_label = str(row.get("observed_label", ""))
    normalized_target = str(row.get("normalized_target_label", ""))
    is_overclean_candidate = observed_label == "strong" and normalized_target in {"hard", "very_hard"}

    status = "not_applicable"
    actionable = False
    calibrated_target = normalized_target
    if is_overclean_candidate:
        if stage in EARLY_TARGET_CALIBRATION_STAGES:
            status = "early_stage_target_expectation_artifact"
        elif stage in ACTIONABLE_TARGET_STAGES:
            status = "actionable_overclean"
            actionable = True
        else:
            status = "non_actionable_stage"
    elif normalized_target in TARGET_LABEL_TO_SCORE:
        status = "comparable_non_overclean"

    return {
        **row,
        "raw_target_label": row.get("target_label"),
        "calibrated_target_label": calibrated_target,
        "actionable_target_label": calibrated_target if actionable else None,
        "target_calibration_status": status,
        "is_actionable_overclean": actionable,
    }



def _compact_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _pressure_evidence_for_run(run: dict[str, Any]) -> dict[str, Any]:
    observability = dict(run.get("observability", {}))
    return {
        "turns": int(run.get("turns") or 0),
        "damage_dealt": int(observability.get("damage_dealt", run.get("damage_dealt") or 0)),
        "damage_taken": int(observability.get("damage_taken", run.get("damage_taken") or 0)),
        "player_hp_remaining_pct": _compact_float(observability.get("player_hp_remaining_pct", run.get("player_hp_remaining_pct"))),
        "player_mana_remaining_pct": _compact_float(observability.get("player_mana_remaining_pct", run.get("player_mana_remaining_pct"))),
        "mob_hp_removed_pct": _compact_float(observability.get("mob_hp_removed_pct", 1.0 - (run.get("mob_hp_remaining_pct") or 0.0))),
        "sample_tags": list(run.get("sample_tags", []))[:5],
        "mob_role": run.get("mob_role"),
        "encounter_level": run.get("encounter_level"),
    }


def _format_pressure_evidence(evidence: dict[str, Any]) -> str:
    return (
        f"turns={evidence.get('turns')}, "
        f"hp_left={_format_pct(evidence.get('player_hp_remaining_pct'))}, "
        f"mana_left={_format_pct(evidence.get('player_mana_remaining_pct'))}, "
        f"mob_hp_removed={_format_pct(evidence.get('mob_hp_removed_pct'))}, "
        f"dmg_taken={evidence.get('damage_taken')}, "
        f"role={evidence.get('mob_role')}, lvl={evidence.get('encounter_level')}"
    )


def _primary_lane_for_pressure_labels(labels: list[str], evidence: dict[str, Any] | None = None, stage: str = "") -> str:
    label_set = set(labels)
    evidence = evidence or {}
    mob_role = str(evidence.get("mob_role") or "")
    is_late_pressure_role = stage in LATE_STAGE_TARGETED_STAGES and mob_role in {"pressure", "elite"}
    if "bad_matchup_overpressure" in label_set:
        return "bad_matchup_review_lane"
    if "policy_artifact" in label_set:
        return "archetype_policy_lane"
    if "target_expectation_mismatch" in label_set:
        return "route_expectation_lane"
    if "formula_signal" in label_set:
        return "formula_review_lane"
    if is_late_pressure_role and label_set & {"mob_hp_too_low", "mob_damage_too_low", "mob_accuracy_too_low", "resource_pressure_missing"}:
        return "mob_pressure_lane"
    if "sample_too_soft" in label_set:
        return "sample_selection_lane"
    if label_set & {"mob_hp_too_low", "mob_damage_too_low", "mob_accuracy_too_low", "resource_pressure_missing"}:
        return "mob_pressure_lane"
    if label_set & {"player_damage_too_high", "player_sustain_too_high"}:
        return "equipment_budget_lane"
    return "inconclusive_lane"


def _classify_pressure_attribution_run(run: dict[str, Any], target_row: dict[str, Any] | None) -> dict[str, Any] | None:
    target_row = target_row or {}
    stage = str(run.get("stage", ""))
    route_id = str(run.get("route_id", ""))
    archetype_id = str(run.get("archetype_id", ""))
    target_label = str(target_row.get("normalized_target_label") or target_row.get("target_label") or "")
    observed_label = str(target_row.get("observed_label") or "")
    calibration_status = str(target_row.get("target_calibration_status") or "")
    diagnostic_label = str(target_row.get("observed_diagnostic_label_v2") or "")
    evidence = _pressure_evidence_for_run(run)
    labels: list[str] = []

    winner = str(run.get("winner", ""))
    end_reason = str(run.get("end_reason", ""))
    turns = int(evidence.get("turns") or 0)
    damage_taken = int(evidence.get("damage_taken") or 0)
    hp_left = evidence.get("player_hp_remaining_pct")
    mana_left = evidence.get("player_mana_remaining_pct")
    sample_tags = {str(tag) for tag in evidence.get("sample_tags", [])}
    mob_role = str(evidence.get("mob_role") or "")
    has_high_target = target_label in {"hard", "very_hard"}
    is_player_win = winner == "player"
    is_overclean = observed_label == "strong" and has_high_target and is_player_win

    if (
        route_id == "route_sunscar"
        and stage == "route_exam"
        and archetype_id == "pure_support_solo_overlay"
        and end_reason == "player_death"
    ):
        labels.append("bad_matchup_overpressure")

    if diagnostic_label == "policy_failure" or run.get("guard_action_rate", 0.0) >= 0.65:
        labels.append("policy_artifact")

    if is_overclean:
        # A player victory usually removes 100% of mob HP, so mob_hp_removed_pct
        # is not enough by itself to prove low mob HP. Use fast-win pressure
        # instead so bounded PR3 HP/pressure tuning can move this classifier.
        fast_win_turn_limit = {"build_testing": 4, "route_exam": 5}.get(stage, 3)
        is_fast_win = 0 < turns <= fast_win_turn_limit
        if is_fast_win:
            labels.extend(["mob_hp_too_low", "player_damage_too_high"])
        if is_player_win and hp_left is not None and hp_left >= 0.85 and damage_taken <= 40 and has_high_target:
            labels.append("mob_damage_too_low")
        if is_player_win and mana_left is not None and mana_left >= 0.9 and has_high_target:
            labels.append("resource_pressure_missing")
        if damage_taken > 40 and hp_left is not None and hp_left >= 0.7 and any("heal" in s or "regen" in s for s in run.get("skills_used", [])):
            labels.append("player_sustain_too_high")
        explicit_soft_sample = bool(sample_tags & {"soft_sample", "weak_sample", "low_pressure_sample"})
        late_normal_role_sample = stage in LATE_STAGE_TARGETED_STAGES and mob_role not in {"pressure", "elite"} and "normal_spawn" in sample_tags
        if late_normal_role_sample or explicit_soft_sample:
            labels.append("sample_too_soft")
        if calibration_status == "early_stage_target_expectation_artifact" or stage in EARLY_TARGET_CALIBRATION_STAGES:
            labels.extend(["target_expectation_mismatch", "sample_too_soft"])

    if not labels and target_row.get("is_actionable_overclean"):
        labels.append("inconclusive")
    if not labels:
        return None

    labels = sorted(set(labels))
    if "bad_matchup_overpressure" in labels or "policy_artifact" in labels:
        confidence = "high"
    elif "target_expectation_mismatch" in labels or len(labels) >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "route_id": route_id,
        "stage": stage,
        "archetype_id": archetype_id,
        "mob_id": run.get("mob_id"),
        "seed": run.get("seed"),
        "target_label": target_row.get("target_label") or target_label or None,
        "observed_label": observed_label or None,
        "winner": winner,
        "end_reason": end_reason,
        "attribution_labels": labels,
        "recommended_lane": _primary_lane_for_pressure_labels(labels, evidence, stage),
        "confidence": confidence,
        "evidence": evidence,
    }


def _count_pressure_attributions(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update(str(label) for label in row.get("attribution_labels", []))
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _count_recommended_lanes(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("recommended_lane", "inconclusive_lane")) for row in rows)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _build_pressure_attribution_top_clusters(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: Counter[tuple[str, ...]] = Counter()
    for row in rows:
        for label in row.get("attribution_labels", []):
            clusters[("route_stage_attribution", str(row.get("route_id")), str(row.get("stage")), str(label))] += 1
            clusters[("archetype_attribution", str(row.get("archetype_id")), str(label))] += 1
    return [
        {"cluster_type": key[0], "key": key[1:], "count": count}
        for key, count in sorted(clusters.items(), key=lambda item: (-item[1], item[0]))[:PRESSURE_ATTRIBUTION_CLUSTER_LIMIT]
    ]


def _build_recommended_lane_top_clusters(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: Counter[tuple[str, ...]] = Counter()
    for row in rows:
        lane = str(row.get("recommended_lane", "inconclusive_lane"))
        clusters[("route_stage_lane", str(row.get("route_id")), str(row.get("stage")), lane)] += 1
        clusters[("archetype_lane", str(row.get("archetype_id")), lane)] += 1
    return [
        {"cluster_type": key[0], "key": key[1:], "count": count}
        for key, count in sorted(clusters.items(), key=lambda item: (-item[1], item[0]))[:PRESSURE_ATTRIBUTION_CLUSTER_LIMIT]
    ]



def _unavailable_pr4_multiseed_confidence_snapshot() -> dict[str, Any]:
    return {
        "available": False,
        "seeds": list(PR4_CONFIDENCE_SEEDS),
        "compact_lane_counts": {},
        "multiseed_lane_counts": {},
        "lane_deltas": {},
        "stable_clusters": [],
        "unstable_clusters": [],
        "high_confidence_remaining_clusters": [],
        "archetype_stability_clusters": [],
        "scope": {},
        "notes": [
            "PR4 multi-seed confidence data is unavailable in this report config. Use build_default_alpha_simulation_report_v2_data() / v2 report data for authoritative confidence diagnostics.",
        ],
    }


def _normalized_lane_delta_interpretation(compact_count: int, multiseed_total: int, seed_count: int) -> str:
    if seed_count <= 0:
        return "not_available"
    if compact_count == 0:
        return "stable_across_seeds" if multiseed_total == 0 else "higher_per_seed"

    multiseed_per_seed_avg = multiseed_total / seed_count
    ratio = multiseed_per_seed_avg / compact_count
    if 0.90 <= ratio <= 1.10:
        return "stable_across_seeds"
    if 1.10 < ratio <= 1.25:
        return "slightly_higher_per_seed"
    if ratio > 1.25:
        return "higher_per_seed"
    if 0.75 <= ratio < 0.90:
        return "slightly_lower_per_seed"
    return "lower_per_seed"


def _build_pr4_lane_deltas(
    compact_lane_counts: dict[str, int],
    multiseed_lane_counts: dict[str, int],
    *,
    seed_count: int,
) -> dict[str, dict[str, Any]]:
    lane_names = sorted(set(PR4_CONFIDENCE_LANES) | set(compact_lane_counts.keys()) | set(multiseed_lane_counts.keys()))
    deltas: dict[str, dict[str, Any]] = {}
    for lane in lane_names:
        compact_count = int(compact_lane_counts.get(lane, 0))
        multiseed_total = int(multiseed_lane_counts.get(lane, 0))
        expected_multiseed_total = compact_count * max(0, seed_count)
        multiseed_per_seed_avg = (multiseed_total / seed_count) if seed_count > 0 else 0.0
        delta_per_seed = multiseed_per_seed_avg - compact_count if seed_count > 0 else 0.0
        deltas[lane] = {
            "compact": compact_count,
            "seed_count": seed_count,
            "expected_multiseed_total": expected_multiseed_total,
            "multiseed_total": multiseed_total,
            "multiseed_per_seed_avg": round(multiseed_per_seed_avg, 2),
            "delta_vs_expected_total": multiseed_total - expected_multiseed_total,
            "delta_per_seed_vs_compact": round(delta_per_seed, 2),
            "interpretation": _normalized_lane_delta_interpretation(compact_count, multiseed_total, seed_count),
        }
    return deltas


def _build_pr4_cluster_stability(rows: list[dict[str, Any]], seeds: tuple[int, ...]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    expected_seed_count = max(1, len(set(seeds)))
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("route_id", "")), str(row.get("stage", "")), str(row.get("recommended_lane", "inconclusive_lane")))
        bucket = grouped.setdefault(key, {"key": key, "count": 0, "seeds_seen": set()})
        bucket["count"] += 1
        bucket["seeds_seen"].add(int(row.get("seed", 0) or 0))

    clusters: list[dict[str, Any]] = []
    for key, bucket in grouped.items():
        seeds_seen = sorted(seed for seed in bucket["seeds_seen"] if seed in seeds)
        seed_count = len(seeds_seen)
        if seed_count >= expected_seed_count:
            confidence = "high"
        elif seed_count == expected_seed_count - 1 and expected_seed_count >= 3:
            confidence = "medium"
        elif seed_count >= 2:
            confidence = "medium"
        else:
            confidence = "low"
        clusters.append(
            {
                "cluster_type": "route_stage_lane",
                "route_id": key[0],
                "stage": key[1],
                "recommended_lane": key[2],
                "key": key,
                "count": int(bucket["count"]),
                "seeds_seen": seeds_seen,
                "seed_presence_rate": round(seed_count / expected_seed_count, 3),
                "confidence": confidence,
            }
        )

    clusters = sorted(
        clusters,
        key=lambda row: (
            {"high": 0, "medium": 1, "low": 2}.get(str(row.get("confidence")), 9),
            -int(row.get("count", 0)),
            str(row.get("route_id")),
            str(row.get("stage")),
            str(row.get("recommended_lane")),
        ),
    )
    stable_clusters = [row for row in clusters if row.get("confidence") in {"high", "medium"}]
    unstable_clusters = sorted(
        [row for row in clusters if row.get("confidence") == "low"],
        key=lambda row: (-int(row.get("count", 0)), str(row.get("route_id")), str(row.get("stage")), str(row.get("recommended_lane"))),
    )
    high_confidence_remaining_clusters = [
        row for row in clusters if row.get("confidence") == "high" and row.get("recommended_lane") == "mob_pressure_lane"
    ]
    return stable_clusters, unstable_clusters, high_confidence_remaining_clusters


def _build_pr4_archetype_stability(rows: list[dict[str, Any]], seeds: tuple[int, ...]) -> list[dict[str, Any]]:
    expected_seed_count = max(1, len(set(seeds)))
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("archetype_id", "")), str(row.get("recommended_lane", "inconclusive_lane")))
        bucket = grouped.setdefault(key, {"key": key, "count": 0, "seeds_seen": set()})
        bucket["count"] += 1
        bucket["seeds_seen"].add(int(row.get("seed", 0) or 0))
    output: list[dict[str, Any]] = []
    for key, bucket in grouped.items():
        seeds_seen = sorted(seed for seed in bucket["seeds_seen"] if seed in seeds)
        rate = len(seeds_seen) / expected_seed_count
        confidence = "high" if rate >= 1.0 else "medium" if rate >= (2 / 3) else "low"
        output.append(
            {
                "cluster_type": "archetype_lane",
                "archetype_id": key[0],
                "recommended_lane": key[1],
                "key": key,
                "count": int(bucket["count"]),
                "seeds_seen": seeds_seen,
                "seed_presence_rate": round(rate, 3),
                "confidence": confidence,
            }
        )
    return sorted(output, key=lambda row: (-int(row.get("count", 0)), str(row.get("archetype_id")), str(row.get("recommended_lane"))))




def _pr4_scope_metadata(config: RouteStageMatrixConfig, scope_source: str) -> dict[str, Any]:
    return {
        "route_ids": list(config.route_ids),
        "stages": list(config.stages),
        "archetype_ids": list(config.archetype_ids),
        "max_samples_per_route_stage": int(config.max_samples_per_route_stage),
        "max_turns": int(config.max_turns),
        "scope_source": scope_source,
    }


def _build_pr4_confidence_config_from_scope(
    base_config: RouteStageMatrixConfig | None,
    matrix_scope: dict[str, Any] | None,
    seeds: tuple[int, ...],
) -> tuple[RouteStageMatrixConfig, str, list[str]]:
    notes: list[str] = []
    if base_config is not None:
        return (
            replace(
                base_config,
                seeds=tuple(seeds),
                include_raw_runs=True,
                include_turn_trace=False,
            ),
            "config",
            notes,
        )

    matrix_scope = matrix_scope or {}
    routes = tuple(str(route_id) for route_id in matrix_scope.get("routes", ()) if route_id)
    stages = tuple(str(stage) for stage in matrix_scope.get("stages", ()) if stage)
    archetypes = tuple(str(archetype_id) for archetype_id in matrix_scope.get("archetypes", ()) if archetype_id)
    if routes or stages or archetypes:
        notes.append("PR4 confidence scope was derived from matrix_result because no active RouteStageMatrixConfig was provided; max_samples_per_route_stage/max_turns use safe defaults.")
        return (
            RouteStageMatrixConfig(
                route_ids=routes or tuple(list_alpha_simulation_route_ids()),
                stages=stages or tuple(list_route_simulation_stages()),
                archetype_ids=archetypes or tuple(list_alpha_archetype_ids()),
                seeds=tuple(seeds),
                max_samples_per_route_stage=1,
                max_turns=50,
                include_raw_runs=True,
                include_turn_trace=False,
            ),
            "matrix_result_fallback",
            notes,
        )

    notes.append("PR4 confidence used the full alpha fallback scope because no active config or matrix scope was available.")
    return (
        RouteStageMatrixConfig(
            route_ids=tuple(list_alpha_simulation_route_ids()),
            stages=tuple(list_route_simulation_stages()),
            archetype_ids=tuple(list_alpha_archetype_ids()),
            seeds=tuple(seeds),
            max_samples_per_route_stage=1,
            max_turns=50,
            include_raw_runs=True,
            include_turn_trace=False,
        ),
        "default_full_alpha_fallback",
        notes,
    )


def build_pr4_multiseed_confidence_snapshot(
    *,
    compact_lane_counts: dict[str, int] | None = None,
    compact_pressure_rows: list[dict[str, Any]] | None = None,
    base_config: RouteStageMatrixConfig | None = None,
    matrix_scope: dict[str, Any] | None = None,
    seeds: tuple[int, ...] = PR4_CONFIDENCE_SEEDS,
) -> dict[str, Any]:
    """Build diagnostic-only PR4 multi-seed confidence data.

    Compact PR3 lane counts remain the checked-in regression baseline. The
    multi-seed data only compares stability of the remaining signals and does
    not tune balance numbers or replace the compact baseline.
    """
    _ = compact_pressure_rows
    compact_lane_counts = dict(compact_lane_counts or {})
    config, scope_source, scope_notes = _build_pr4_confidence_config_from_scope(base_config, matrix_scope, tuple(seeds))
    scope = _pr4_scope_metadata(config, scope_source)
    matrix = run_route_stage_simulation_matrix(config)
    if not matrix.get("runs"):
        unavailable = _unavailable_pr4_multiseed_confidence_snapshot()
        unavailable["compact_lane_counts"] = compact_lane_counts
        unavailable["scope"] = scope
        unavailable["notes"] = list(unavailable.get("notes", [])) + scope_notes
        return unavailable

    multiseed_report = build_alpha_balance_report_data(matrix_result=matrix, config=config, include_pr4_confidence=False)
    multiseed_rows = list(multiseed_report.get("pressure_attribution_rows", []))
    multiseed_lane_counts = dict(multiseed_report.get("recommended_lane_counts", {}))
    for lane in PR4_CONFIDENCE_LANES:
        compact_lane_counts.setdefault(lane, 0)
        multiseed_lane_counts.setdefault(lane, 0)

    stable_clusters, unstable_clusters, high_confidence_remaining_clusters = _build_pr4_cluster_stability(multiseed_rows, tuple(seeds))
    archetype_stability = _build_pr4_archetype_stability(multiseed_rows, tuple(seeds))
    return {
        "available": True,
        "seeds": list(seeds),
        "compact_lane_counts": compact_lane_counts,
        "multiseed_lane_counts": multiseed_lane_counts,
        "lane_deltas": _build_pr4_lane_deltas(compact_lane_counts, multiseed_lane_counts, seed_count=len(set(seeds))),
        "stable_clusters": stable_clusters,
        "unstable_clusters": unstable_clusters,
        "high_confidence_remaining_clusters": high_confidence_remaining_clusters,
        "archetype_stability_clusters": archetype_stability,
        "scope": scope,
        "run_count": int(matrix.get("run_count", 0)),
        "sample_count": int(matrix.get("sample_count", 0)),
        "notes": [
            "Diagnostic-only: PR4 does not tune balance numbers or replace compact PR3 regression counts.",
            "Compact PR3 lane counts remain authoritative for checked-in regression comparisons.",
            "PR4 confidence uses the active report scope; checked-in v2 uses full compact alpha scope, and scoped callers get scoped confidence diagnostics instead of full-alpha totals.",
            f"Bounded multi-seed config: seeds={tuple(seeds)}, max_samples_per_route_stage={config.max_samples_per_route_stage}, include_raw_runs=True, include_turn_trace=False.",
            "No live runtime, Combat Core, formula, equipment budget, live mob template, economy/reward/loot/crafting, targeting, teleport, or live group combat changes are made by this report layer.",
            *scope_notes,
        ],
    }


def build_alpha_balance_report_data(
    matrix_result: dict | None = None,
    config: RouteStageMatrixConfig | None = None,
    *,
    include_pr4_confidence: bool = False,
) -> dict:
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
    overclean_candidates = [
        row
        for row in target_comparisons
        if str(row.get("observed_label")) == "strong" and str(row.get("normalized_target_label")) in {"hard", "very_hard"}
    ]
    calibrated_target_comparisons = [calibrate_target_expectation_row(row) for row in target_comparisons]
    actionable_overclean_candidates = [row for row in calibrated_target_comparisons if row.get("is_actionable_overclean")]
    early_stage_target_artifacts = [
        row for row in calibrated_target_comparisons if row.get("target_calibration_status") == "early_stage_target_expectation_artifact"
    ]

    target_by_key = {
        (str(row.get("route_id")), str(row.get("stage")), str(row.get("archetype_id"))): row
        for row in calibrated_target_comparisons
    }
    pressure_attribution_rows = [
        row
        for row in (
            _classify_pressure_attribution_run(
                run,
                target_by_key.get((str(run.get("route_id")), str(run.get("stage")), str(run.get("archetype_id")))),
            )
            for run in enriched_runs
        )
        if row is not None
    ]
    pressure_attribution_rows = sorted(
        pressure_attribution_rows,
        key=lambda row: (
            str(row.get("route_id")),
            str(row.get("stage")),
            str(row.get("archetype_id")),
            str(row.get("mob_id")),
            str(row.get("recommended_lane")),
        ),
    )
    pressure_attribution_counts = _count_pressure_attributions(pressure_attribution_rows)
    recommended_lane_counts = _count_recommended_lanes(pressure_attribution_rows)
    pressure_attribution_top_clusters = _build_pressure_attribution_top_clusters(pressure_attribution_rows)
    recommended_lane_top_clusters = _build_recommended_lane_top_clusters(pressure_attribution_rows)

    def _rollup(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, ...], int] = defaultdict(int)
        for row in rows:
            grouped[tuple(str(row.get(k, "")) for k in keys)] += 1
        output = []
        for group_key, count in sorted(grouped.items(), key=lambda item: (-item[1], item[0])):
            output.append({"group_by": keys, "key": group_key, "count": count})
        return output

    global_overclean_candidate_count = len(overclean_candidates)
    actionable_overclean_candidate_count = len(actionable_overclean_candidates)
    early_stage_target_artifact_count = len(early_stage_target_artifacts)
    late_stage_overclean_candidate_count = sum(1 for row in overclean_candidates if str(row.get("stage", "")) in LATE_STAGE_TARGETED_STAGES)
    late_stage_actionable_overclean_count = sum(
        1 for row in actionable_overclean_candidates if str(row.get("stage", "")) in LATE_STAGE_TARGETED_STAGES
    )

    late_stage_overclean_candidates = [
        row for row in overclean_candidates if str(row.get("stage", "")) in LATE_STAGE_TARGETED_STAGES
    ]

    overclean_rollups = {
        "by_route": _rollup(overclean_candidates, ("route_id",)),
        "by_stage": _rollup(overclean_candidates, ("stage",)),
        "by_archetype": _rollup(overclean_candidates, ("archetype_id",)),
        "by_route_stage": _rollup(overclean_candidates, ("route_id", "stage")),
        "by_route_archetype": _rollup(overclean_candidates, ("route_id", "archetype_id")),
        "by_target_label": _rollup(overclean_candidates, ("normalized_target_label",)),
    }
    late_stage_overclean_rollups = {
        "by_route_stage": _rollup(late_stage_overclean_candidates, ("route_id", "stage")),
    }
    global_overclean_top_clusters = overclean_rollups["by_route_stage"][:PR13_TOP_CLUSTER_LIMIT]
    late_stage_targeted_top_clusters = late_stage_overclean_rollups["by_route_stage"][:PR13_TOP_CLUSTER_LIMIT]
    actionable_overclean_rollups = {
        "by_route": _rollup(actionable_overclean_candidates, ("route_id",)),
        "by_stage": _rollup(actionable_overclean_candidates, ("stage",)),
        "by_archetype": _rollup(actionable_overclean_candidates, ("archetype_id",)),
        "by_route_stage": _rollup(actionable_overclean_candidates, ("route_id", "stage")),
    }
    early_stage_target_artifact_rollups = {
        "by_route": _rollup(early_stage_target_artifacts, ("route_id",)),
        "by_stage": _rollup(early_stage_target_artifacts, ("stage",)),
        "by_archetype": _rollup(early_stage_target_artifacts, ("archetype_id",)),
        "by_route_stage": _rollup(early_stage_target_artifacts, ("route_id", "stage")),
    }
    actionable_overclean_top_clusters = actionable_overclean_rollups["by_route_stage"][:PR13_TOP_CLUSTER_LIMIT]
    early_stage_target_artifact_top_clusters = early_stage_target_artifact_rollups["by_route_stage"][:PR13_TOP_CLUSTER_LIMIT]

    limitations = list(matrix.get("limitations", [])) + [
        "Alpha diagnostic signal only; not a final balance verdict.",
        "Observed-vs-target comparisons are coarse bands, not proof of tuning direction.",
        "Missing target metadata rows are treated as inconclusive, not mismatch verdicts.",
        "No full multi-target pack runtime combat; pack section uses composite_pack_pressure_v1 diagnostic proxy.",
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
    pack_route_ids = tuple(matrix.get("routes", []))
    pack_archetype_ids = tuple(matrix.get("archetypes", []))
    scoped_pack_stages = tuple(s for s in matrix.get("stages", []) if s in PACK_REQUIRED_STAGES)
    pack_matrix = run_pack_simulation_matrix(
        route_ids=pack_route_ids if pack_route_ids else tuple(list_alpha_simulation_route_ids()),
        stages=scoped_pack_stages if scoped_pack_stages else tuple(),
        archetype_ids=pack_archetype_ids if pack_archetype_ids else tuple(list_alpha_archetype_ids()),
    )
    pr4_multiseed_confidence = _unavailable_pr4_multiseed_confidence_snapshot()
    if include_pr4_confidence:
        pr4_multiseed_confidence = build_pr4_multiseed_confidence_snapshot(
            compact_lane_counts=recommended_lane_counts,
            compact_pressure_rows=pressure_attribution_rows,
            base_config=config,
            matrix_scope=matrix,
        )
    unified_combat_budget_audit = build_unified_combat_budget_audit(
        mode="compact_checked_in",
        pressure_attribution_rows=pressure_attribution_rows,
    )
    simulation_policy_skill_economy = build_simulation_policy_skill_economy_diagnostics(
        enriched_runs,
        list(matrix.get("archetypes", [])) or list_alpha_archetype_ids(),
    )
    simulation_action_resolution = build_simulation_action_resolution_diagnostics(enriched_runs)
    return {
        "generated_for_routes": list(matrix.get("routes", [])),
        "stages": list(matrix.get("stages", [])),
        "archetypes": list(matrix.get("archetypes", [])),
        "run_count": int(matrix.get("run_count", 0)),
        "sample_count": int(matrix.get("sample_count", 0)),
        "limitations": limitations,
        "summaries": summaries,
        "target_comparisons": calibrated_target_comparisons,
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
        "pressure_attribution_available": bool(enriched_runs),
        "pressure_attribution_rows": pressure_attribution_rows,
        "pressure_attribution_counts": pressure_attribution_counts,
        "recommended_lane_counts": recommended_lane_counts,
        "pressure_attribution_top_clusters": pressure_attribution_top_clusters,
        "recommended_lane_top_clusters": recommended_lane_top_clusters,
        "global_overclean_candidate_count": global_overclean_candidate_count,
        "raw_global_overclean_candidate_count": global_overclean_candidate_count,
        "actionable_overclean_candidate_count": actionable_overclean_candidate_count,
        "early_stage_target_artifact_count": early_stage_target_artifact_count,
        "late_stage_overclean_candidate_count": late_stage_overclean_candidate_count,
        "late_stage_actionable_overclean_count": late_stage_actionable_overclean_count,
        "overclean_rollups": overclean_rollups,
        "global_overclean_top_clusters": global_overclean_top_clusters,
        "late_stage_targeted_top_clusters": late_stage_targeted_top_clusters,
        "overclean_top_clusters": late_stage_targeted_top_clusters,
        "actionable_overclean_top_clusters": actionable_overclean_top_clusters,
        "early_stage_target_artifact_top_clusters": early_stage_target_artifact_top_clusters,
        "target_calibration_rollups": {
            "actionable_overclean": actionable_overclean_rollups,
            "early_stage_target_artifact": early_stage_target_artifact_rollups,
        },
        "pack_runs": pack_matrix.get("pack_runs", []),
        "pack_samples": pack_matrix.get("pack_samples", []),
        "pack_rollups": pack_matrix.get("pack_rollups", {}),
        "pack_audit_flags": pack_matrix.get("pack_audit_flags", []),
        "pack_audit_flag_counts": pack_matrix.get("pack_audit_flag_counts", {}),
        "report_modes": {
            "compact_regression": build_balance_report_mode("compact_regression").description,
            "expanded_balance": build_balance_report_mode("expanded_balance").description,
        },
        "pr4_multiseed_confidence": pr4_multiseed_confidence,
        "unified_combat_budget_audit": unified_combat_budget_audit,
        "simulation_policy_skill_economy": simulation_policy_skill_economy,
        "simulation_action_resolution": simulation_action_resolution,
        "raw_data_pointers": {"source": "run_route_stage_simulation_matrix", "raw_runs_included": bool(matrix.get("runs"))},
    }





def _render_pr5_unified_combat_budget_audit_lines(report_data: dict[str, Any]) -> list[str]:
    audit = dict(report_data.get("unified_combat_budget_audit") or {})
    lines = ["", "## Balance V2 PR5 Unified Combat Budget Audit"]
    if not audit.get("available"):
        lines.append("- PR5 unified combat budget audit data is unavailable for this report config.")
        return lines

    rows = list(audit.get("audit_rows", []))
    pvp_proxy = dict(audit.get("pvp_budget_proxy_summary") or {})
    pve_summary = dict(audit.get("pve_budget_summary") or {})
    reconciliation = dict(audit.get("pr4_route_pressure_reconciliation") or {})
    archetype_count = len({str(row.get("archetype_id")) for row in rows})
    level_band_count = len(audit.get("level_bands", []))
    gear_state_count = len(audit.get("gear_states", []))
    lines += [
        "Diagnostic-only: this section performs no tuning and makes no final balance claim.",
        "All gear states are included: undergeared, baseline_expected, enhanced_expected, optimized, and overgeared_high_enhancement.",
        "PvE and PvP/proxy budget coverage is included; PvP is a clearly labeled pvp_budget_proxy, not real duel win rates.",
        "No live gameplay/runtime/formula/equipment/live mob/economy/targeting/teleport/live group combat changes are made.",
        f"- Mode: {audit.get('mode')}.",
        f"- Coverage: {archetype_count} archetypes, {level_band_count} level bands, {gear_state_count} gear states, {len(rows)} audit rows.",
        f"- PvE budget summary source: {pve_summary.get('source', 'n/a')}.",
        f"- PvP/proxy budget coverage: {pvp_proxy.get('summary_type', 'n/a')}; proxy_only={pvp_proxy.get('proxy_only')}; real_duel_win_rates={pvp_proxy.get('real_duel_win_rates')}.",
        f"- PvP equal-budget baseline gear states: {', '.join(pvp_proxy.get('pvp_equal_budget_baseline_gear_states', [])) or 'none'}.",
        f"- PvP gear-gap/stress states: {', '.join(pvp_proxy.get('pvp_gear_gap_stress_states', [])) or 'none'}.",
        "",
        "Top systemic findings:",
    ]
    for finding in list(audit.get("top_systemic_findings", []))[:5]:
        lines.append(f"- {finding}")
    if not audit.get("top_systemic_findings"):
        lines.append("- none")

    lines += ["", "Recommended tuning order:"]
    for item in list(audit.get("recommended_tuning_order", []))[:6]:
        lines.append(f"- {item}")
    if not audit.get("recommended_tuning_order"):
        lines.append("- none")

    lines += [
        "",
        "PR4 route pressure reconciliation:",
        f"- {reconciliation.get('interpretation', 'Diagnostic correlation only; no tuning is applied.')}",
        f"- Compact PR4 lane counts referenced: {reconciliation.get('compact_pr4_lane_counts', {})}.",
        "- Top suspect player-side archetype evidence:",
    ]
    suspect_preview = list(reconciliation.get("suspect_player_side_archetypes", []))[:6]
    if suspect_preview:
        for item in suspect_preview:
            clusters = "; ".join(
                f"{cluster.get('route_id')}/{cluster.get('stage')}={cluster.get('count')}"
                for cluster in list(item.get("route_stage_clusters", []))[:3]
            )
            lines.append(
                f"  - {item.get('archetype_id')}: mob_pressure_count={item.get('mob_pressure_count', 0)}; {clusters or 'no late mob_pressure clusters'}"
            )
    else:
        lines.append("  - none")

    lines += [
        "",
        "Notes:",
    ]
    for note in list(audit.get("notes", []))[:6]:
        lines.append(f"- {note}")
    return lines


def _format_pr3_refinement_summary() -> list[str]:
    if not PR3_LATE_STAGE_MOB_PRESSURE_REFINEMENTS:
        return ["- none"]
    lines: list[str] = []
    for (route_id, stage), knobs in sorted(PR3_LATE_STAGE_MOB_PRESSURE_REFINEMENTS.items()):
        changed = ", ".join(
            f"{key} +{(float(value) - 1.0) * 100:.0f}%"
            for key, value in sorted(knobs.items())
            if abs(float(value) - 1.0) > 0.0001
        )
        lines.append(f"- {route_id} / {stage}: {changed or 'identity preserved with neutral knobs'}.")
    return lines


def _pr3_top_remaining_mob_pressure_clusters(report_data: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for cluster in list(report_data.get("recommended_lane_top_clusters", [])):
        key = tuple(str(part) for part in cluster.get("key", ()))
        if key and key[-1] == "mob_pressure_lane":
            lines.append(f"- {cluster.get('cluster_type')} / {' / '.join(key)}: {cluster.get('count', 0)}")
        if len(lines) >= 6:
            break
    return lines or ["- none"]


def _pr3_overpressure_risk_summary(report_data: dict[str, Any]) -> str:
    deaths = [
        trace
        for trace in report_data.get("suspicious_traces", [])
        if trace.get("winner") == "mob" and trace.get("end_reason") == "player_death"
    ]
    if not deaths:
        return "- New overpressure/death risk: none observed in representative suspicious traces."
    known = []
    other = []
    for trace in deaths:
        item = f"{trace.get('route_id')} / {trace.get('stage')} / {trace.get('archetype_id')} player_death"
        if (
            trace.get("route_id") == "route_sunscar"
            and trace.get("stage") == "route_exam"
            and trace.get("archetype_id") == "pure_support_solo_overlay"
        ):
            known.append(item)
        else:
            other.append(item)
    if other:
        return f"- New overpressure/death risk: {', '.join(other[:3])}; known bad-matchup signal remains {', '.join(known[:1]) or 'not present in preview'}."
    return f"- New overpressure/death risk: no broad new death wall observed; known bad-matchup signal remains {', '.join(known[:1])}."


def _render_pr3_lane_summary_lines(report_data: dict[str, Any]) -> list[str]:
    lines = ["", "## Balance V2 PR3 Controlled Late-Stage Mob Pressure Tuning Summary"]
    pressure_available = bool(report_data.get("pressure_attribution_available"))
    if not pressure_available:
        lines += [
            "- PR3 pressure attribution lane counts are unavailable in this report config because raw runs are not included.",
            "- Use build_default_alpha_simulation_report_v2_data() / v2 report data with raw runs included for authoritative PR3 lane counts.",
            "- This pass remains simulation/reporting-only and makes no final balance claim.",
            "- No live gameplay/runtime systems, Combat Core behavior, global formulas, equipment budget formulas, live mob templates, rewards/economy/loot/crafting runtime, targeting, teleport, or live group combat were changed.",
        ]
        return lines

    pr2_mob_pressure_baseline = 43
    current_lane_counts = dict(report_data.get("recommended_lane_counts", {}))
    current_mob_pressure = int(current_lane_counts.get("mob_pressure_lane", 0))
    current_route_expectation = int(current_lane_counts.get("route_expectation_lane", 0))
    current_bad_matchup = int(current_lane_counts.get("bad_matchup_review_lane", 0))
    pr3_moved = current_mob_pressure < pr2_mob_pressure_baseline
    pr3_result_explanation = (
        "- Current result explanation: classifier moved after semantic cleanup; mob_hp_too_low now uses turn-speed/clean-win pressure instead of mob_hp_removed_pct=1.00 alone."
        if pr3_moved
        else "- Current result explanation: bounded route-stage pressure refinements are applied, but remaining mob_pressure rows are based on turn-speed/clean-win pressure rather than mob_hp_removed_pct=1.00 alone."
    )
    lines += [
        f"- Previous PR2 mob_pressure_lane baseline: {pr2_mob_pressure_baseline}.",
        f"- Current mob_pressure_lane count: {current_mob_pressure}.",
        f"- Current route_expectation_lane count: {current_route_expectation}.",
        f"- Current bad_matchup_review_lane count: {current_bad_matchup}.",
        f"- Classifier movement vs PR2 baseline: {'decreased' if pr3_moved else 'unchanged'}.",
        pr3_result_explanation,
        "- This pass is simulation/reporting-only and makes no final balance claim.",
        "- No live gameplay/runtime systems, Combat Core behavior, global formulas, equipment budget formulas, live mob templates, rewards/economy/loot/crafting runtime, targeting, teleport, or live group combat were changed.",
        "- Early-stage soft_entry / identity_visible target expectation artifacts remain separated and are not tuned as direct mob pressure backlog.",
        "- Sunscar pure_support_solo_overlay route_exam remains treated as bad matchup review, not an automatic support buff or Sunscar nerf.",
        "",
        "Changed PR3 knobs (multipliers above existing simulation/reporting rails):",
    ]
    lines.extend(_format_pr3_refinement_summary())
    lines += ["", "Top remaining mob_pressure_lane clusters:"]
    lines.extend(_pr3_top_remaining_mob_pressure_clusters(report_data))
    lines += ["", "New overpressure/death risk summary:", _pr3_overpressure_risk_summary(report_data)]
    return lines




def _format_pr4_cluster_row(cluster: dict[str, Any]) -> str:
    return (
        f"| {cluster.get('route_id', 'n/a')} | {cluster.get('stage', 'n/a')} | "
        f"{cluster.get('recommended_lane', 'n/a')} | {cluster.get('count', 0)} | "
        f"{', '.join(str(seed) for seed in cluster.get('seeds_seen', [])) or 'none'} | "
        f"{cluster.get('seed_presence_rate', 0)} | {cluster.get('confidence', 'n/a')} |"
    )


def _render_pr4_multiseed_confidence_lines(report_data: dict[str, Any], *, detailed: bool) -> list[str]:
    lines = ["", "## Balance V2 PR4 Expanded Sampling / Multi-seed Confidence Summary"]
    confidence = dict(report_data.get("pr4_multiseed_confidence") or {})
    if not confidence.get("available"):
        lines += [
            "- PR4 multi-seed confidence data is unavailable in this report config. Use build_default_alpha_simulation_report_v2_data() / v2 report data for authoritative confidence diagnostics.",
            "- No fake PR4 counts, stable-cluster wording, or decreased/increased conclusions are rendered for smoke/v1 configs without PR4 raw runs.",
        ]
        return lines
    if not detailed:
        lines += [
            "- PR4 multi-seed confidence data is available in the report data object, but this v1/smoke renderer does not print detailed PR4 counts.",
            "- Use render_alpha_simulation_report_v2_markdown() for the authoritative PR4 confidence diagnostics.",
        ]
        return lines

    compact_counts = dict(confidence.get("compact_lane_counts", {}))
    multiseed_counts = dict(confidence.get("multiseed_lane_counts", {}))
    high_conf = list(confidence.get("high_confidence_remaining_clusters", []))
    unstable = list(confidence.get("unstable_clusters", []))
    lines += [
        "This section is diagnostic-only and does not tune balance numbers. Compact PR3 counts remain the checked-in regression baseline; PR4 confidence data is used to guide future tuning scope.",
        "No final balance claim is made. No live runtime, Combat Core behavior, global formulas, equipment budget formulas, live mob templates, rewards/economy/loot/crafting, targeting, teleport, or live group combat changes are made here.",
        "Sunscar pure_support_solo_overlay route_exam overpressure remains separated as bad_matchup_review_lane, not an automatic support buff or Sunscar nerf.",
        "No new tuning knobs were added.",
        f"- Seeds: {', '.join(str(seed) for seed in confidence.get('seeds', []))}.",
        f"- Compact PR3 lane counts: mob_pressure_lane={compact_counts.get('mob_pressure_lane', 0)}, route_expectation_lane={compact_counts.get('route_expectation_lane', 0)}, bad_matchup_review_lane={compact_counts.get('bad_matchup_review_lane', 0)}.",
        f"- Multi-seed lane counts: mob_pressure_lane={multiseed_counts.get('mob_pressure_lane', 0)}, route_expectation_lane={multiseed_counts.get('route_expectation_lane', 0)}, bad_matchup_review_lane={multiseed_counts.get('bad_matchup_review_lane', 0)}, inconclusive_lane={multiseed_counts.get('inconclusive_lane', 0)}.",
        "",
        "Lane comparison table:",
        "Multi-seed totals are raw totals across seeds; interpretation is normalized per seed.",
        "PR4 confidence uses the active report scope. Checked-in v2 uses full compact alpha scope; scoped callers get scoped confidence diagnostics, not full-alpha totals.",
        "| lane | compact PR3 | PR4 multi-seed total | expected total | per-seed avg | delta vs expected | interpretation |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for lane, row in sorted(dict(confidence.get("lane_deltas", {})).items()):
        lines.append(
            f"| {lane} | {row.get('compact', 0)} | {row.get('multiseed_total', 0)} | "
            f"{row.get('expected_multiseed_total', 0)} | {row.get('multiseed_per_seed_avg', 0)} | "
            f"{row.get('delta_vs_expected_total', 0)} | {row.get('interpretation', 'not_available')} |"
        )
    lines += [
        "",
        "High-confidence remaining mob_pressure clusters preview:",
        "| route | stage | lane | count | seeds_seen | seed_presence_rate | confidence |",
        "|---|---|---|---:|---|---:|---|",
    ]
    if high_conf:
        for cluster in high_conf[:PR4_CLUSTER_PREVIEW_LIMIT]:
            lines.append(_format_pr4_cluster_row(cluster))
    else:
        lines.append("| n/a | n/a | mob_pressure_lane | 0 | none | 0 | n/a |")
    lines += [
        "",
        "Unstable/noisy clusters preview:",
        "| route | stage | lane | count | seeds_seen | seed_presence_rate | confidence |",
        "|---|---|---|---:|---|---:|---|",
    ]
    if unstable:
        for cluster in unstable[:PR4_CLUSTER_PREVIEW_LIMIT]:
            lines.append(_format_pr4_cluster_row(cluster))
    else:
        lines.append("| n/a | n/a | n/a | 0 | none | 0 | n/a |")
    lines += ["", "PR4 confidence notes:"]
    for note in list(confidence.get("notes", [])):
        lines.append(f"- {note}")
    return lines



def _render_pr6_simulation_policy_skill_economy_lines(report_data: dict[str, Any]) -> list[str]:
    data = dict(report_data.get("simulation_policy_skill_economy") or {})
    lines = ["", "## Balance V2 PR6 Simulation Policy & Skill Economy Clarification"]
    if not data.get("available"):
        lines.append("- PR6 simulation policy and skill economy diagnostics are unavailable for this report config.")
        return lines

    policy_rows = list(data.get("policy_coverage_rows", []))
    economy_rows = list(data.get("skill_economy_rows", []))
    lines += [
        "Diagnostic-only: PR6 performs no live tuning and makes no final balance claim.",
        "No live gameplay/runtime/formula/equipment/live mob/economy/targeting/teleport/live group combat changes are made.",
        "PR6 separates simulation policy artifacts from real skill economy risks before any future tuning branch uses PR5 budget rows.",
        "PvP remains proxy-only; route/mob/gear/PvP tuning remains deferred.",
        f"- Policy coverage rows: {len(policy_rows)}.",
        f"- Skill economy rows: {len(economy_rows)}.",
        f"- Artifact reason counts: {data.get('artifact_reason_counts', {})}.",
        f"- Skill economy label counts: {data.get('skill_economy_label_counts', {})}.",
        "- Cooldown observability: cooldown-blocked turn counts are not safely available, so rows set cooldown_observability_available=False pending follow-up instrumentation.",
        "",
        "Top policy gaps:",
    ]
    for row in list(data.get("top_policy_gaps", []))[:6]:
        reasons = ", ".join(row.get("artifact_reasons", [])) or "none"
        missing = ", ".join(row.get("missing_expected_skill_ids", [])) or "none"
        lines.append(f"- {row.get('archetype_id')}: policy={row.get('preferred_policy_id')} status={row.get('policy_status')} reasons={reasons}; missing_expected_skills={missing}.")
    if not data.get("top_policy_gaps"):
        lines.append("- none")
    lines += ["", "Recommended next tuning branch:"]
    for item in list(data.get("recommended_next_tuning_branch", []))[:4]:
        lines.append(f"- {item}")
    return lines


def _render_pr7_profile_aware_policy_pilot_lines(report_data: dict[str, Any]) -> list[str]:
    data = dict(report_data.get("simulation_policy_skill_economy") or {})
    policy_rows = list(data.get("policy_coverage_rows", []))
    audit_rows = list((report_data.get("unified_combat_budget_audit") or {}).get("audit_rows", []))
    pilot_ids = ", ".join(PROFILE_POLICY_PILOT_ARCHETYPE_IDS)
    return [
        "",
        "## Balance V2 PR7 Profile-aware Simulation Policy Execution Pilot",
        "Diagnostic/simulation-only pilot: PR7 performs no live tuning and changes no live gameplay/runtime formulas, skill numbers, weapons, armor, gear, enhancement, mobs, routes, rewards/economy, PvP rules, targeting, teleport, or live group combat.",
        f"Pilot archetypes: {pilot_ids}.",
        "Metadata-only registry policies were not globally flipped; pilot execution is resolved only by the simulation policy resolver.",
        f"PR6 policy coverage remains {len(policy_rows)} rows and PR6 skill economy remains {len(data.get('skill_economy_rows', []))} rows.",
        f"PR5 audit remains {len(audit_rows)} rows (expected 420).",
        "PvP remains proxy-only; route/mob/gear/PvP tuning remains deferred.",
    ]


def _render_pr8_simulation_action_resolution_lines(report_data: dict[str, Any]) -> list[str]:
    data = dict(report_data.get("simulation_action_resolution") or {})
    pr6 = dict(report_data.get("simulation_policy_skill_economy") or {})
    audit_rows = list((report_data.get("unified_combat_budget_audit") or {}).get("audit_rows", []))
    lines = [
        "",
        "## Balance V2 PR8 Simulation Action Resolution / Fallback Attribution",
        "Diagnostic/simulation-only: PR8 adds action-resolution and fallback attribution observability without live tuning.",
        "No live gameplay/runtime formulas, skill numbers, weapons, armor, gear, enhancement, mobs, routes, rewards/economy, PvP rules, targeting, teleport, cooldown reset behavior, reward behavior, or live group combat were changed.",
        "Fallback reasons are now attributed for simulator policy requests that resolve to skill use, normal_attack fallback, or guard fallback.",
        "Metadata-only registry policies remain not globally flipped; pilot execution remains resolver-scoped only.",
        f"PR6 remains {len(pr6.get('policy_coverage_rows', []))}/{len(pr6.get('skill_economy_rows', []))} policy coverage / skill economy rows.",
        f"PR5 remains {len(audit_rows)} audit rows (expected 420).",
        "PvP remains proxy-only; route/mob/gear/PvP tuning remains deferred.",
        "",
        "Top fallback reasons:",
    ]
    fallback_counts = dict(data.get("fallback_reason_counts") or {})
    if fallback_counts:
        for reason, count in list(fallback_counts.items())[:8]:
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- none: 0")
    action_counts = dict(data.get("action_resolution_counts") or {})
    lines += ["", "Action resolution counts:"]
    if action_counts:
        for status, count in list(action_counts.items())[:8]:
            lines.append(f"- {status}: {count}")
    else:
        lines.append("- none: 0")
    lines += ["", "Pilot fallback summary:"]
    pilot_rows = list(data.get("pilot_policy_resolution_summary") or [])
    if pilot_rows:
        lines += [
            "| archetype | requested_skills | resolved_skill_success | normal_attack_fallback | top_fallback_reasons |",
            "|---|---:|---:|---:|---|",
        ]
        for row in pilot_rows:
            fallback_summary = ", ".join(f"{k}:{v}" for k, v in list(dict(row.get("fallback_reason_counts") or {}).items())[:4]) or "none"
            lines.append(
                f"| {row.get('archetype_id')} | {row.get('requested_skill_count', 0)} | "
                f"{row.get('resolved_skill_success_count', 0)} | {row.get('normal_attack_fallback_count', 0)} | {fallback_summary} |"
            )
    else:
        lines.append("- none")
    return lines


def render_alpha_balance_report_markdown(report_data: dict) -> str:
    # PR5 renderer behavior
    lines = ["# Alpha Route/Class Balance Report v1", "", "## 1. Summary", "This is an alpha diagnostic report using representative solo route-stage samples.", "It is a signal artifact for future targeted tuning PRs and is not a final balance verdict.", "", "## 2. Methodology", "- Matrix source: route × stage × archetype deterministic simulation summaries.", f"- Routes: {', '.join(report_data.get('generated_for_routes', []))}", f"- Stages: {', '.join(report_data.get('stages', []))}", f"- Archetypes: {len(report_data.get('archetypes', []))}", f"- Total samples: {report_data.get('sample_count', 0)} | total runs: {report_data.get('run_count', 0)}", "", "## 3. Scope and Non-goals", "- No route/mob/skill/reward/formula tuning is performed in this report.", "- No live PvE/PvP behavior changes are introduced.", "- Pack proxy exists in v2/report data; no live/full multi-target runtime pack combat.", "- No live AFK/autopilot or smart autobattle behavior.", "", "## 4. Matrix Configuration", "- Config is deterministic and representative (solo route-native samples).", "", "## 5. Route Overview", "| Route | Runs | Win Rate | Timeout Rate |", "|---|---:|---:|---:|"]
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
    raw_global_candidates = int(report_data.get("global_overclean_candidate_count", 0))
    actionable_candidates = int(report_data.get("actionable_overclean_candidate_count", 0))
    early_stage_artifacts = int(report_data.get("early_stage_target_artifact_count", 0))
    late_stage_actionable = int(report_data.get("late_stage_actionable_overclean_count", 0))
    lines += [
        "",
        "## PR14 Target Expectation Calibration Summary",
        f"- Raw global overclean candidates: {raw_global_candidates}.",
        f"- Actionable overclean candidates after target calibration: {actionable_candidates}.",
        f"- Early-stage target expectation artifacts: {early_stage_artifacts}.",
        f"- Late-stage actionable overclean: {late_stage_actionable}.",
        "- Raw/global signal remains visible for transparency; calibration adds actionable separation only.",
        "- Early-stage artifacts are diagnostic target-expectation mismatches, not resolved balance issues.",
        "- Late-stage actionable cases remain the tuning backlog.",
        "- This pass is simulation/reporting-only and does not tune live gameplay/runtime systems.",
        "| bucket | count | meaning |",
        "|---|---:|---|",
        f"| raw_global_overclean | {raw_global_candidates} | Raw strong_vs_high_target candidates across all stages. |",
        f"| early_stage_target_artifact | {early_stage_artifacts} | soft_entry/identity_visible high-target overclean artifacts. |",
        f"| actionable_overclean | {actionable_candidates} | Calibrated actionable overclean candidates. |",
        f"| late_stage_actionable | {late_stage_actionable} | Actionable overclean in build_testing/route_exam. |",
    ]
    lines += ["", "## 8. Suspicious Matchup Candidates"]

    lines.extend(_render_pr3_lane_summary_lines(report_data))
    lines.extend(_render_pr4_multiseed_confidence_lines(report_data, detailed=False))
    lines.extend(_render_pr5_unified_combat_budget_audit_lines(report_data))
    lines.extend(_render_pr6_simulation_policy_skill_economy_lines(report_data))
    lines.extend(_render_pr7_profile_aware_policy_pilot_lines(report_data))
    lines.extend(_render_pr8_simulation_action_resolution_lines(report_data))

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
    lines += ["", "## 12. Recommended Next Steps", "- Expand pack proxy fidelity and targeted tuning follow-ups using v2 pack diagnostics.", "- Increase seed/sample breadth for suspicious candidates.", "- Use targeted follow-up PRs for any actual tuning decisions.", "", "## 13. Raw Data Pointers", "- Source module: `game.combat_simulation_matrix.run_route_stage_simulation_matrix`.", f"- Raw runs included in current report data object: {report_data.get('raw_data_pointers', {}).get('raw_runs_included', False)}."]
    return "\n".join(lines) + "\n"


def render_alpha_simulation_report_v2_markdown(report_data: dict) -> str:
    lines = ["# Alpha Route/Class Balance Report v2", "", "## Summary", "This is a diagnostic and non-final report for future tuning scope decisions.", "", "## Methodology", "- Deterministic representative solo route-stage simulations plus composite_pack_pressure_v1 pack proxy samples.", f"- Routes: {', '.join(report_data.get('generated_for_routes', []))}", f"- Stages: {', '.join(report_data.get('stages', []))}", f"- Runs: {report_data.get('run_count', 0)}", "", "## Scope and Non-goals", "- No live route/mob/skill/reward/formula tuning.", "- PR12 includes simulation/reporting-only stage pressure tuning.", "- No Combat Core rewrite.", "- No smart autobattle and no live AFK/autopilot.", "- No live pack/group runtime combat.", "", "## Diagnostic Config", "- checked-in compact config: seeds=(1), max_samples_per_route_stage=1, max_turns=50, include_raw_runs=True.", "", "## Scenario Cards", "| route_id | stage | location_id | mob_id | role | lvl | scaling | spawn_profile | sample_tags | final_mob_stats |", "|---|---|---|---|---|---:|---|---|---|---|"]
    scenario_cards = report_data.get("scenario_cards", [])
    for card in scenario_cards[:SCENARIO_PREVIEW_LIMIT]:
        lines.append(f"| {card['route_id']} | {card['stage']} | {card['location_id']} | {card['mob_id']} | {card.get('mob_role','normal')} | {card.get('encounter_level','')} | {card.get('scaling_status','')} | {card['spawn_profile']} | {', '.join(card.get('sample_tags', []))} | {card.get('final_mob_stats', {})} |")
    if len(scenario_cards) > SCENARIO_PREVIEW_LIMIT:
        lines.append(f"Showing first {SCENARIO_PREVIEW_LIMIT} of {len(scenario_cards)} scenario cards.")

    lines += ["", "## Archetype Cards", "| archetype_id | power_tier | hp | mana | skill levels | policy metadata | gear budget | policy warning |", "|---|---|---:|---:|---|---|---|---|"]
    archetype_cards = report_data.get("archetype_cards", [])
    for card in archetype_cards[:ARCHETYPE_CARD_PREVIEW_LIMIT]:
        lines.append(f"| {card['archetype_id']} | {card['power_tier']} | {card.get('hp')} | {card.get('mana')} | {card.get('skill_levels', {})} | {card.get('preferred_policy_id')} (exec={card.get('policy_executable')}) | {card.get('gear_budget_summary', {})} | {card.get('policy_warning') or 'n/a'} |")
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

    progression_counts = dict(report_data.get("progression_audit_flag_counts", {}))
    policy_guard_count = int(progression_counts.get("policy_failure_guard_loop", 0))
    overclean_count = int(progression_counts.get("overclean_win", 0))
    suspicious_count = len(report_data.get("suspicious_matchups", []))
    lines += [
        "",
        "## PR12 First Tuning Pass Summary",
        "- Pass status: first controlled tuning pass (not final balance).",
        "- Changed policy assumptions:",
        "  - defensive guard-loop simulation policy replaced with simulation-only guard-then-attack fallback for guardian_shield_1h and holy_rod_paladin.",
        "- Changed numeric knobs:",
        "  - added simulation-stage pressure modifiers:",
        "    - soft_entry: baseline unchanged;",
        "    - identity_visible: mild hp/damage pressure;",
        "    - build_testing: moderate hp/damage pressure;",
        "    - route_exam: stronger late-stage pressure.",
        "  - simulation-only role escalation for hard/very_hard build_testing/route_exam matchup samples (pressure, and elite where elite_available on route_exam very_hard samples).",
        "  - no live mob templates or live combat formulas changed.",
        "- Policy artifact status:",
        f"  - policy_failure_guard_loop count: {policy_guard_count} (diagnostic simulation policy artifact, not a direct route tuning verdict).",
        f"  - current late-stage overclean audit flag count: {overclean_count}.",
        "  - previous PR12 policy-sanity global overclean baseline: 88.",
        "  - this late-stage scoped flag count is not a comparable global overclean improvement metric.",
        f"  - suspicious rows: {suspicious_count}.",
        "  - route win rates in compact deterministic run may still remain 1.00; treat this as remaining underpressure signal if observed.",
        "- Remaining known issues:",
        "  - broad overclean/underpressure signals may still remain and require route/archetype targeted follow-up tuning passes.",
        "- Pack proxy status:",
        "  - composite_pack_pressure_v1 remains active as simulation/reporting-only proxy; no live group combat/targeting added.",
    ]
    overclean_rollups = dict(report_data.get("overclean_rollups", {}))
    top_clusters = list(report_data.get("late_stage_targeted_top_clusters", []))
    lines += ["", "## PR13 Targeted Tuning Candidates", "Diagnostic compact cluster view; use full report_data for complete candidate selection.", "PR14 target expectation calibration below further separates raw global signal from actionable tuning backlog."]
    global_candidates = int(report_data.get("global_overclean_candidate_count", 0))
    late_stage_candidates = int(report_data.get("late_stage_overclean_candidate_count", 0))
    lines.append(f"- global overclean candidates (strong_vs_high_target): {global_candidates}.")
    lines.append(f"- late-stage targeted candidates (build_testing/route_exam only): {late_stage_candidates}.")
    lines.append(f"- top targeted late-stage clusters shown: {min(len(top_clusters), PR13_TOP_CLUSTER_LIMIT)} (limit={PR13_TOP_CLUSTER_LIMIT}).")
    lines.append("- global diagnostic clusters are available in report_data as global_overclean_top_clusters.")
    lines += ["| cluster_type | cluster_key | count |", "|---|---|---:|"]
    if not top_clusters:
        lines.append("| route+stage | n/a | 0 |")
    else:
        for cluster in top_clusters:
            lines.append(f"| route+stage | {' / '.join(cluster.get('key', []))} | {cluster.get('count', 0)} |")

    pr13_overclean = int(progression_counts.get("overclean_win", 0))
    lines += [
        "",
        "## PR13 Targeted Alpha Tuning Summary",
        "- Previous PR12 global overclean baseline: 86.",
        f"- Current global overclean candidates: {global_candidates}.",
        f"- Current late-stage overclean audit flags: {pr13_overclean}.",
        "- Late-stage audit scope: build_testing / route_exam only.",
        "- Global overclean remains a known underpressure signal in compact deterministic output; PR15 success is measured against calibrated actionable late-stage count.",
        "- Selected tuning targets: repeated build_testing/route_exam overclean clusters from route+stage rollups.",
        "- Changed knobs (simulation/reporting-only): targeted route-stage pressure overrides in mob scaling, preserving route identity.",
        "- PR13 adds candidate rollups and targeted tuning knobs, but compact global overclean remains unresolved.",
        "- Remaining known underpressure: compact deterministic route win rates may remain 1.00 and further targeted passes can still be required.",
        "- No live gameplay/runtime systems changed.",
    ]


    raw_global_candidates = int(report_data.get("global_overclean_candidate_count", 0))
    actionable_candidates = int(report_data.get("actionable_overclean_candidate_count", 0))
    early_stage_artifacts = int(report_data.get("early_stage_target_artifact_count", 0))
    late_stage_actionable = int(report_data.get("late_stage_actionable_overclean_count", 0))
    lines += [
        "",
        "## PR14 Target Expectation Calibration Summary",
        f"- Raw global overclean candidates: {raw_global_candidates}.",
        f"- Actionable overclean candidates after target calibration: {actionable_candidates}.",
        f"- Early-stage target expectation artifacts: {early_stage_artifacts}.",
        f"- Late-stage actionable overclean: {late_stage_actionable}.",
        "- Raw/global signal remains visible for transparency; calibration adds actionable separation only.",
        "- Early-stage artifacts are diagnostic target-expectation mismatches, not resolved balance issues.",
        "- Late-stage actionable cases remain the tuning backlog.",
        "- This pass is simulation/reporting-only and does not tune live gameplay/runtime systems.",
        "| bucket | count | meaning |",
        "|---|---:|---|",
        f"| raw_global_overclean | {raw_global_candidates} | Raw strong_vs_high_target candidates across all stages. |",
        f"| early_stage_target_artifact | {early_stage_artifacts} | soft_entry/identity_visible high-target overclean artifacts. |",
        f"| actionable_overclean | {actionable_candidates} | Calibrated actionable overclean candidates. |",
        f"| late_stage_actionable | {late_stage_actionable} | Actionable overclean in build_testing/route_exam. |",
    ]

    pr15_baseline = 44
    pr15_improved = actionable_candidates < pr15_baseline
    remaining_backlog = list(report_data.get("actionable_overclean_top_clusters", []))
    overpressure_traces = [
        trace
        for trace in report_data.get("suspicious_traces", [])
        if trace.get("winner") == "mob" and trace.get("end_reason") == "player_death"
    ]
    preview_count = min(len(remaining_backlog), PR13_TOP_CLUSTER_LIMIT)
    lines += [
        "",
        "## PR15 Actionable Late-Stage Tuning Summary",
        f"- Previous PR14 actionable overclean baseline: {pr15_baseline}.",
        f"- Current actionable overclean candidates: {actionable_candidates}.",
        f"- Actionable overclean candidates after PR15: {actionable_candidates}.",
        f"- Current early-stage target artifacts: {early_stage_artifacts}.",
        f"- Early-stage target artifacts remain separated: {early_stage_artifacts}.",
        f"- Current raw/global overclean candidates: {raw_global_candidates}.",
        f"- Raw/global overclean candidates still visible: {raw_global_candidates}.",
        f"- Improvement vs PR14 actionable baseline: {'yes' if pr15_improved else 'no'}.",
        "- Changed knobs: bounded simulation/reporting-only late-stage route-stage pressure overrides plus one solo-matrix actionable role refinement for the repeated Sunscar route_exam support overclean cluster.",
        f"- Top remaining actionable clusters preview: {preview_count} of {actionable_candidates}; full list available in report_data.",
        "- No live gameplay/runtime changes.",
        "- No live gameplay/runtime systems were changed.",
    ]
    if overpressure_traces:
        risk_items = [
            f"{trace.get('route_id')} / {trace.get('stage')} / {trace.get('archetype_id')} player_death"
            for trace in overpressure_traces[:3]
        ]
        lines.append(f"- New overpressure risk: {', '.join(risk_items)} observed in representative suspicious traces; PR15 is not presented as a clean/final balance pass.")
    else:
        lines.append("- New overpressure risk: none observed in representative suspicious traces.")
    lines += ["| top_remaining_cluster_preview | count |", "|---|---:|"]
    if remaining_backlog:
        for cluster in remaining_backlog[:PR13_TOP_CLUSTER_LIMIT]:
            lines.append(f"| {' / '.join(cluster.get('key', []))} | {cluster.get('count', 0)} |")
    else:
        lines.append("| n/a | 0 |")

    lines.extend(_render_pr3_lane_summary_lines(report_data))
    lines.extend(_render_pr4_multiseed_confidence_lines(report_data, detailed=True))
    lines.extend(_render_pr5_unified_combat_budget_audit_lines(report_data))
    lines.extend(_render_pr6_simulation_policy_skill_economy_lines(report_data))
    lines.extend(_render_pr7_profile_aware_policy_pilot_lines(report_data))
    lines.extend(_render_pr8_simulation_action_resolution_lines(report_data))

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
    lines += ["", "## Progression Audit Preview", "This section is diagnostic-only and not a tuning verdict.", "Gear assumptions use formula_budget_v1 simulation presets where available."]
    lines.append("policy_failure_guard_loop is a simulation policy artifact flag, not a direct route tuning verdict.")
    if progression_counts:
        lines.append("Flag counts:")
        for flag_id in sorted(progression_counts.keys()):
            lines.append(f"- {flag_id}: {progression_counts[flag_id]}")
    else:
        lines.append("No progression audit flags were emitted.")
    lines += ["| route | stage | archetype | lvl | gear | rarity | + | budget | profile | mob | role | encounter | scaled_hp | scaled_damage | target | observed_v2 | audit flags |", "|---|---|---|---:|---|---|---:|---:|---|---|---|---:|---:|---:|---|---|---|"]
    preview = progression_rows[:PROGRESSION_AUDIT_PREVIEW_LIMIT]
    for row in preview:
        gp = row.get('simulation_gear_preset') or {}
        scaled = row.get('final_mob_stats') or {}
        lines.append(f"| {row.get('route_id')} | {row.get('stage')} | {row.get('archetype_id')} | {row.get('assumed_player_level')} | {row.get('gear_tier')} | {row.get('gear_rarity_assumption')} | +{row.get('enhancement_assumption')} | {gp.get('total_budget')} | {gp.get('profile_id')} | {row.get('mob_id')} | {row.get('mob_role')} | {row.get('encounter_level')} | {scaled.get('hp')} | {scaled.get('damage')} | {row.get('target_label')} | {row.get('observed_diagnostic_label_v2')} | {', '.join(row.get('audit_flag_ids', []))} |")
    if len(progression_rows) > PROGRESSION_AUDIT_PREVIEW_LIMIT:
        lines.append(f"Showing first {PROGRESSION_AUDIT_PREVIEW_LIMIT} of {len(progression_rows)} progression audit rows. Hidden rows are not resolved or dismissed.")

    pack_runs = list(report_data.get("pack_runs", []))
    pack_preview_rows = _select_route_balanced_pack_preview(pack_runs, PACK_PREVIEW_LIMIT)
    lines += ["", "## Pack / Group Simulation Preview", f"Showing {len(pack_preview_rows)} route-stage-balanced pack preview rows out of {len(pack_runs)} pack runs. Hidden rows are not resolved or dismissed.", "| route | stage | pack_id | archetype | members | composite_hp | composite_damage | observed_v2 | proxy_status | winner | turns | audit flags |", "|---|---|---|---|---:|---:|---:|---|---|---|---:|---|"]
    for run in pack_preview_rows:
        final_stats = run.get("final_pack_stats", {})
        lines.append(f"| {run.get('route_id')} | {run.get('stage')} | {run.get('pack_id')} | {run.get('archetype_id')} | {run.get('pack_member_count')} | {final_stats.get('hp')} | {final_stats.get('damage')} | {run.get('observed_diagnostic_label_v2', 'inconclusive')} | {run.get('pack_simulation_status')} | {run.get('winner')} | {run.get('turns')} | {', '.join(report_data.get('pack_audit_flag_counts', {}).keys()) or 'none'} |")

    observability_rows = _build_observability_preview_rows(report_data)
    lines += [
        "",
        "## Balance Instrument V2 Observability Preview",
        "Simulation/reporting-only preview with capped turn traces; this does not tune formulas, equipment budgets, live mob templates, rewards/economy, targeting, teleport, or live group combat.",
        "Report modes available in code/report-data builders: compact_regression and expanded_balance.",
        "Per-fight percentage metrics are 0..1 fractions.",
        f"Showing {len(observability_rows)} capped representative observability rows out of {len(report_data.get('runs', []))} raw compact runs.",
        "| route | stage | archetype | mob | winner | end_reason | turns | damage_dealt | damage_taken | player_hp_remaining_pct | player_mana_remaining_pct | action_sequence |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    if not observability_rows:
        lines.append("No observability preview rows are available for this report data object.")
    for run in observability_rows:
        obs = dict(run.get("observability", {}))
        lines.append(
            f"| {run.get('route_id')} | {run.get('stage')} | {run.get('archetype_id')} | {run.get('mob_id')} | "
            f"{run.get('winner')} | {obs.get('end_reason') or run.get('end_reason')} | {run.get('turns')} | "
            f"{obs.get('damage_dealt', run.get('damage_dealt'))} | {obs.get('damage_taken', run.get('damage_taken'))} | "
            f"{_format_pct(obs.get('player_hp_remaining_pct'))} | {_format_pct(obs.get('player_mana_remaining_pct'))} | {_format_action_sequence(run)} |"
        )

    trace_cases = [run for run in observability_rows if run.get("turn_trace")][:OBSERVABILITY_TRACE_CASE_LIMIT]
    lines += ["", f"Capped turn trace preview ({len(trace_cases)} cases, max rows already capped by SimulationConfig.max_trace_turns):"]
    for idx, run in enumerate(trace_cases, start=1):
        lines += [
            "",
            f"Case {idx}: {run.get('route_id')} / {run.get('stage')} / {run.get('archetype_id')} vs {run.get('mob_id')}",
            "| turn | action | player hp/mana before -> after | mob hp before -> after | log/event summary |",
            "|---:|---|---|---|---|",
        ]
        for row in list(run.get("turn_trace", [])):
            pb = row.get("player_before", {})
            pa = row.get("player_after_enemy_action", {})
            mb = row.get("mob_before", {})
            ma = row.get("mob_after_enemy_action", {})
            log_summary = "; ".join(str(event) for event in row.get("log_events", [])[:2]) or "n/a"
            lines.append(
                f"| {row.get('turn')} | {row.get('resolved_action') or row.get('chosen_action')} | "
                f"{pb.get('hp')}/{pb.get('mana')} -> {pa.get('hp')}/{pa.get('mana')} | "
                f"{mb.get('hp')} -> {ma.get('hp')} | {log_summary} |"
            )

    pressure_rows = list(report_data.get("pressure_attribution_rows", []))
    pressure_preview = pressure_rows[:PRESSURE_ATTRIBUTION_ROW_LIMIT]
    lines += [
        "",
        "## Balance Instrument V2 Pressure Attribution Preview",
        "Simulation/reporting-only diagnostic preview. Labels are diagnostic likely causes, not final balance verdicts, and do not directly tune formulas, equipment budgets, live mob templates, rewards/economy, targeting, teleport, or live group combat.",
        "This classifier points future review toward tuning lanes; it does not claim final balance or prescribe automatic support buffs/Sunscar nerfs.",
        "",
        "Attribution counts:",
    ]
    attribution_counts = dict(report_data.get("pressure_attribution_counts", {}))
    if attribution_counts:
        for label, count in attribution_counts.items():
            lines.append(f"- {label}: {count}")
    else:
        lines.append("- none: 0")
    lines += ["", "Recommended tuning lane counts:"]
    lane_counts = dict(report_data.get("recommended_lane_counts", {}))
    if lane_counts:
        for lane, count in lane_counts.items():
            lines.append(f"- {lane}: {count}")
    else:
        lines.append("- none: 0")

    lines += ["", "Top attribution clusters:"]
    for cluster in list(report_data.get("pressure_attribution_top_clusters", []))[:PRESSURE_ATTRIBUTION_CLUSTER_LIMIT]:
        lines.append(f"- {cluster.get('cluster_type')} / {' / '.join(cluster.get('key', ())) }: {cluster.get('count')}")
    if not report_data.get("pressure_attribution_top_clusters"):
        lines.append("- none")

    lines += ["", "Top recommended lane clusters:"]
    for cluster in list(report_data.get("recommended_lane_top_clusters", []))[:PRESSURE_ATTRIBUTION_CLUSTER_LIMIT]:
        lines.append(f"- {cluster.get('cluster_type')} / {' / '.join(cluster.get('key', ())) }: {cluster.get('count')}")
    if not report_data.get("recommended_lane_top_clusters"):
        lines.append("- none")

    lines += [
        "",
        f"Representative attribution rows ({len(pressure_preview)} shown of {len(pressure_rows)}):",
        "| route | stage | archetype | mob | target | observed | winner | labels | recommended_lane | confidence | evidence |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    if not pressure_preview:
        lines.append("No pressure attribution rows triggered current heuristic rules.")
    for row in pressure_preview:
        labels = ", ".join(row.get("attribution_labels", []))
        lines.append(
            f"| {row.get('route_id')} | {row.get('stage')} | {row.get('archetype_id')} | {row.get('mob_id')} | "
            f"{row.get('target_label')} | {row.get('observed_label')} | {row.get('winner')} | {labels} | "
            f"{row.get('recommended_lane')} | {row.get('confidence')} | {_format_pressure_evidence(row.get('evidence', {}))} |"
        )

    lines += ["", "## Representative Suspicious Fight Traces"]
    traces = report_data.get("suspicious_traces", [])
    lines.append(f"Showing up to {TRACE_LIMIT} route-balanced representative suspicious traces. Hidden traces are not resolved or dismissed.")
    lines += ["| route_id | stage | archetype_id | location_id | mob_id | winner | end_reason | turns | actions_used | skills_used |", "|---|---|---|---|---|---|---|---:|---|---|"]
    if not traces:
        lines.append("No suspicious traces were detected for this deterministic compact run.")
    else:
        for trace in traces[:TRACE_LIMIT]:
            lines.append(f"| {trace['route_id']} | {trace['stage']} | {trace['archetype_id']} | {trace['location_id']} | {trace['mob_id']} | {trace['winner']} | {trace['end_reason']} | {trace['turns']} | {trace.get('actions_used', {})} | {trace.get('skills_used', [])} |")

    lines += ["", "## Diagnostic Label Definitions", "strong_clean, strong_but_risky, normal, hard, very_hard, death_blocked, timeout_stall, no_progress_stall, resource_collapse, policy_failure, inconclusive.", "", "## Limitations"]
    for item in report_data.get("limitations", []):
        lines.append(f"- {item}")
    lines += ["", "## Recommended Next Steps", "- Use this report to scope targeted follow-up tuning PRs only.", "", "## Raw Data Pointers", "- Source module: `game.combat_simulation_matrix.run_route_stage_simulation_matrix`.", f"- Raw runs included in current report data object: {report_data.get('raw_data_pointers', {}).get('raw_runs_included', False)}."]
    return "\n".join(lines) + "\n"



def _format_pct(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "n/a"


def _format_action_sequence(run: dict[str, Any]) -> str:
    trace = list(run.get("turn_trace", []))
    if trace:
        actions = [str(row.get("resolved_action") or row.get("chosen_action") or "") for row in trace[:6]]
        suffix = "..." if int(run.get("turns", 0) or 0) > len(actions) else ""
        return ", ".join(a for a in actions if a) + suffix
    actions_used = dict(run.get("actions_used", {}))
    return ", ".join(f"{k}×{v}" for k, v in sorted(actions_used.items()) if int(v or 0) > 0) or "n/a"


def _build_observability_preview_rows(report_data: dict) -> list[dict[str, Any]]:
    suspicious = list(report_data.get("suspicious_traces", []))
    runs = list(report_data.get("runs", []))
    selected: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    def row_key(row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            row.get("route_id"),
            row.get("stage"),
            row.get("archetype_id"),
            row.get("location_id"),
            row.get("mob_id"),
            row.get("seed"),
        )

    def add_row(row: dict[str, Any]) -> bool:
        if len(selected) >= OBSERVABILITY_PREVIEW_LIMIT:
            return False
        key = row_key(row)
        if key in seen:
            return False
        selected.append(row)
        seen.add(key)
        return True

    def add_route_stage_balanced(rows: list[dict[str, Any]]) -> None:
        buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            buckets[(str(row.get("route_id", "")), str(row.get("stage", "")))].append(row)
        bucket_keys = sorted(buckets.keys())
        index_by_bucket = {key: 0 for key in bucket_keys}
        while len(selected) < OBSERVABILITY_PREVIEW_LIMIT:
            progressed = False
            for bucket_key in bucket_keys:
                bucket = buckets[bucket_key]
                while index_by_bucket[bucket_key] < len(bucket):
                    row = bucket[index_by_bucket[bucket_key]]
                    index_by_bucket[bucket_key] += 1
                    if add_row(row):
                        progressed = True
                        break
                if len(selected) >= OBSERVABILITY_PREVIEW_LIMIT:
                    break
            if not progressed:
                break

    # 1) Start with explicitly suspicious/overpressure rows.
    for run in suspicious:
        add_row(run)
        if len(selected) >= OBSERVABILITY_PREVIEW_LIMIT:
            return selected

    # 2) Prefer actionable late-stage examples next.
    late_stage_runs = [run for run in runs if str(run.get("stage", "")) in ACTIONABLE_TARGET_STAGES]
    add_route_stage_balanced(late_stage_runs)
    if len(selected) >= OBSERVABILITY_PREVIEW_LIMIT:
        return selected

    # 3) Fill with route/stage-balanced examples across all available routes.
    add_route_stage_balanced(runs)
    if len(selected) >= OBSERVABILITY_PREVIEW_LIMIT:
        return selected

    # 4) Final deterministic fallback to first raw runs.
    for run in runs:
        add_row(run)
        if len(selected) >= OBSERVABILITY_PREVIEW_LIMIT:
            break
    return selected

def build_default_alpha_balance_report_data() -> dict:
    return build_alpha_balance_report_data(config=build_checked_in_alpha_balance_report_config())


def build_default_alpha_simulation_report_v2_data() -> dict:
    return build_alpha_balance_report_data(
        config=build_checked_in_alpha_simulation_report_v2_config(),
        include_pr4_confidence=True,
    )
