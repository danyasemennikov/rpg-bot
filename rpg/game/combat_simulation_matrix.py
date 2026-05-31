from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from game.combat_simulation import (
    SIM_ACTION_NORMAL_ATTACK,
    ProfileAwareSimulationPolicy,
    ScriptedActionPolicy,
    SimulationConfig,
    build_simulation_mob_preset,
    make_simulation_skill_action,
    simulate_single_combat,
)
from game.combat_simulation_archetypes import (
    EXECUTABLE_POLICY_REGISTRY,
    PROFILE_POLICY_PILOT_ARCHETYPE_IDS,
    REQUIRED_POWER_TIERS,
    build_archetype_player_preset,
    build_archetype_simulation_skill_levels,
    get_archetype_metadata,
    list_alpha_archetype_ids,
)
from game.locations import ROUTE_MATCHUP_TARGET_PROFILES, WORLD_LOCATIONS
from game.mobs import MOBS
from game.skills import get_skill
from game.mob_scaling import (
    ROLE_ELITE,
    ROLE_NORMAL,
    SCALING_STATUS_FORMULA_V1,
    build_scaled_mob_for_simulation,
)

ALPHA_SIMULATION_ROUTE_IDS = (
    "route_westwild",
    "route_frostspine",
    "route_ashen_ruins",
    "route_mireveil",
    "route_sunscar",
)

ROUTE_SIMULATION_STAGES = ("soft_entry", "identity_visible", "build_testing", "route_exam")



ROUTE_STAGE_SAMPLE_LOCATION_OVERRIDES: dict[str, dict[str, tuple[str, ...]]] = {
    "route_ashen_ruins": {
        "build_testing": ("ashen_n3b1", "ashen_n3b2", "ashen_n3c1"),
        "route_exam": ("ashen_n3b2a1", "ashen_n3c2"),
    },
}

@dataclass(frozen=True)
class RouteStageMobSample:
    route_id: str
    stage: str
    location_id: str
    mob_id: str
    spawn_profile: str
    sample_tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RouteStageMatrixConfig:
    route_ids: tuple[str, ...] = ALPHA_SIMULATION_ROUTE_IDS
    stages: tuple[str, ...] = ROUTE_SIMULATION_STAGES
    archetype_ids: tuple[str, ...] = tuple(list_alpha_archetype_ids())
    seeds: tuple[int, ...] = (1, 2, 3)
    max_samples_per_route_stage: int = 2
    max_turns: int = 50
    include_raw_runs: bool = True
    include_turn_trace: bool = False
    max_trace_turns: int = 20


def list_alpha_simulation_route_ids() -> list[str]:
    return list(ALPHA_SIMULATION_ROUTE_IDS)


def list_route_simulation_stages() -> list[str]:
    return list(ROUTE_SIMULATION_STAGES)


def _extract_depth_node(location_id: str) -> int | None:
    norm = str(location_id or "").strip().lower()
    if norm.startswith("hub_") or "_n" not in norm:
        return None
    suffix = norm.split("_n", 1)[1]
    digits = ""
    for ch in suffix:
        if ch.isdigit():
            digits += ch
        else:
            break
    return int(digits) if digits else None


def resolve_location_depth_stage(location_id: str) -> str | None:
    depth_node = _extract_depth_node(location_id)
    if depth_node is None:
        return None
    if 1 <= depth_node <= 2:
        return "soft_entry"
    if 3 <= depth_node <= 5:
        return "identity_visible"
    if 6 <= depth_node <= 8:
        return "build_testing"
    if depth_node >= 9:
        return "route_exam"
    return None


def collect_route_stage_samples(route_id: str, stage: str, *, max_samples: int = 2) -> list[RouteStageMobSample]:
    if route_id not in ALPHA_SIMULATION_ROUTE_IDS or stage not in ROUTE_SIMULATION_STAGES:
        return []

    samples: list[RouteStageMobSample] = []
    override_locations = ROUTE_STAGE_SAMPLE_LOCATION_OVERRIDES.get(route_id, {}).get(stage, ())

    if override_locations:
        for location_id in override_locations:
            location = WORLD_LOCATIONS.get(location_id)
            if not location or location.get("route_id") != route_id:
                continue
            mobs = [str(m) for m in location.get("mobs", []) if m]
            if not mobs:
                continue
            spawn_profiles = location.get("world_spawn_profiles") or {}
            for mob_id in sorted(mobs):
                if mob_id not in MOBS:
                    continue
                sample_tags = ["representative", "solo", "normal_spawn", "stage_override"]
                if mob_id in spawn_profiles and "elite" in spawn_profiles[mob_id]:
                    sample_tags.append("elite_available")
                samples.append(RouteStageMobSample(route_id, stage, location_id, mob_id, "normal", sample_tags))
                if len(samples) >= max_samples:
                    return samples
        return samples

    for location_id in sorted(WORLD_LOCATIONS.keys()):
        location = WORLD_LOCATIONS[location_id]
        if location.get("route_id") != route_id:
            continue
        if resolve_location_depth_stage(location_id) != stage:
            continue
        mobs = [str(m) for m in location.get("mobs", []) if m]
        if not mobs:
            continue
        spawn_profiles = location.get("world_spawn_profiles") or {}
        for mob_id in sorted(mobs):
            if mob_id not in MOBS:
                continue
            sample_tags = ["representative", "solo", "normal_spawn"]
            if mob_id in spawn_profiles and "elite" in spawn_profiles[mob_id]:
                sample_tags.append("elite_available")
            samples.append(RouteStageMobSample(route_id, stage, location_id, mob_id, "normal", sample_tags))
            if len(samples) >= max_samples:
                return samples

    return samples


PROFILE_POLICY_STATUS_EXECUTABLE_PILOT = "profile_executable_pilot"
PROFILE_POLICY_STATUS_METADATA_FALLBACK = "metadata_only_fallback"

PROFILE_POLICY_ACTIONS: dict[str, list[str]] = {
    "daggers_venom": ["envenom", "poison_blade", "toxic_cut", "rupture_toxins", SIM_ACTION_NORMAL_ATTACK],
    "daggers_evasion": ["smoke_bomb", "feint_step", "quick_slice", "death_dance", SIM_ACTION_NORMAL_ATTACK],
    "bow_sniper": ["hunters_mark", "steady_aim", "aimed_shot", "deadeye", SIM_ACTION_NORMAL_ATTACK],
    "magic_staff_destruction": ["arcane_surge", "fireball", "flame_wave", "cataclysm", SIM_ACTION_NORMAL_ATTACK],
    "holy_staff_solo": ["blessing", "smite", SIM_ACTION_NORMAL_ATTACK],
}


def _skill_loop_actions(skill_ids_or_actions: list[str]) -> list[str]:
    actions: list[str] = []
    for item in skill_ids_or_actions:
        if item == SIM_ACTION_NORMAL_ATTACK:
            actions.append(item)
        elif item and get_skill(item):
            actions.append(make_simulation_skill_action(item))
    return actions or [SIM_ACTION_NORMAL_ATTACK]


def resolve_archetype_simulation_policy(archetype_id: str, power_tier: str) -> dict[str, Any]:
    metadata = get_archetype_metadata(archetype_id)
    pref_policy = metadata.get("preferred_policy_id")
    registry_item = EXECUTABLE_POLICY_REGISTRY.get(pref_policy, {})
    skill_levels = build_archetype_simulation_skill_levels(archetype_id, power_tier)

    if archetype_id in PROFILE_POLICY_PILOT_ARCHETYPE_IDS:
        actions = _skill_loop_actions(PROFILE_POLICY_ACTIONS.get(archetype_id, []))
        if archetype_id == "holy_staff_solo":
            policy = ProfileAwareSimulationPolicy(
                actions,
                low_hp_actions=_skill_loop_actions(["heal", "regeneration", SIM_ACTION_NORMAL_ATTACK]),
                low_hp_threshold=0.55,
            )
        else:
            policy = ProfileAwareSimulationPolicy(actions)
        return {
            "policy": policy,
            "active_simulation_policy_id": f"profile:{archetype_id}",
            "active_simulation_policy_status": PROFILE_POLICY_STATUS_EXECUTABLE_PILOT,
            "profile_policy_executable": True,
            "profile_policy_pilot": True,
            "registry_policy_id": pref_policy,
            "registry_policy_executable": bool(registry_item.get("executable")),
        }

    if registry_item and registry_item.get("executable"):
        return {
            "policy": registry_item["factory"](),
            "active_simulation_policy_id": pref_policy,
            "active_simulation_policy_status": "registry_executable",
            "profile_policy_executable": False,
            "profile_policy_pilot": False,
            "registry_policy_id": pref_policy,
            "registry_policy_executable": True,
        }

    chosen_skill = None
    for skill_id in metadata.get("preferred_skill_ids", []):
        if skill_id in skill_levels:
            chosen_skill = skill_id
            break

    actions = [SIM_ACTION_NORMAL_ATTACK, SIM_ACTION_NORMAL_ATTACK]
    if chosen_skill:
        actions = [make_simulation_skill_action(chosen_skill), SIM_ACTION_NORMAL_ATTACK, SIM_ACTION_NORMAL_ATTACK]
    return {
        "policy": ScriptedActionPolicy(actions),
        "active_simulation_policy_id": "basic_fallback",
        "active_simulation_policy_status": PROFILE_POLICY_STATUS_METADATA_FALLBACK,
        "profile_policy_executable": False,
        "profile_policy_pilot": False,
        "registry_policy_id": pref_policy,
        "registry_policy_executable": bool(registry_item.get("executable")),
    }


def build_basic_archetype_simulation_policy(archetype_id: str, power_tier: str):
    return resolve_archetype_simulation_policy(archetype_id, power_tier)["policy"]


def _label_observed_pressure(summary: dict[str, Any]) -> str:
    if summary["runs"] <= 0:
        return "inconclusive"
    if summary["wins"] == 0 and (summary["losses"] > 0 or summary["timeouts"] > 0):
        return "dead_or_blocked"
    if summary["win_rate"] >= 0.85 and summary["death_rate"] <= 0.15:
        return "strong"
    if summary["win_rate"] >= 0.6 and summary["death_rate"] <= 0.4:
        return "normal"
    if summary["win_rate"] >= 0.35:
        return "hard"
    if summary["win_rate"] < 0.35:
        return "very_hard"
    return "inconclusive"


def _resolve_sample_mob_role(sample: RouteStageMobSample) -> str:
    tags = {str(t).lower() for t in sample.sample_tags}
    if str(sample.spawn_profile).lower() == "elite" and "elite" in tags:
        return ROLE_ELITE
    return ROLE_NORMAL


_ARCHETYPE_MATCHUP_KEY_MAP = {
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


def _normalize_target_label(label: str) -> str:
    norm = str(label or "").strip().lower()
    aliases = {
        "normal_strong": "normal",
        "normal_hard": "hard",
        "hard_very_hard": "very_hard",
        "very_hard_playable": "very_hard",
        "normal_hard_split": "hard",
    }
    return aliases.get(norm, norm)


def _resolve_tuned_sample_mob_role(route_id: str, stage: str, archetype_id: str, sample: RouteStageMobSample) -> str:
    baseline = _resolve_sample_mob_role(sample)
    if stage not in {"build_testing", "route_exam"}:
        return baseline
    matchup_key = _ARCHETYPE_MATCHUP_KEY_MAP.get(archetype_id)
    if not matchup_key:
        return baseline
    target_raw = ((ROUTE_MATCHUP_TARGET_PROFILES.get(route_id, {}) or {}).get("target_matchups", {}) or {}).get(matchup_key, "")
    target = _normalize_target_label(target_raw)
    if target not in {"hard", "very_hard"}:
        return baseline
    tags = {str(t).lower() for t in sample.sample_tags}
    if stage == "route_exam" and target == "very_hard" and "elite_available" in tags:
        return ROLE_ELITE
    return "pressure"



PR15_ACTIONABLE_ROLE_REFINEMENTS: dict[tuple[str, str, str], dict[str, float]] = {
    # Simulation/reporting-only solo matrix refinement for the repeated Sunscar
    # route_exam actionable support overclean cluster. Pack proxy construction does
    # not use this layer, so it cannot inflate composite pack stats.
    ("route_sunscar", "route_exam", "pure_support_solo_overlay"): {"hp": 1.60, "damage": 1.22, "accuracy": 1.08},
}


def _pr15_accuracy_fallback_baseline(scaled_mob: dict) -> int:
    """Neutral combat accuracy rating contribution when mob accuracy is absent.

    Live combat treats absent mob["accuracy"] as an additive 0 and still resolves
    enemy hit chance from 100 + level * 2.  Because PR15 refinement is
    simulation/reporting-only and operates on scaled route-stage samples, prefer
    encounter_level before falling back to template level and finally level 1.
    """
    raw_level = scaled_mob.get("encounter_level", scaled_mob.get("level", 1))
    try:
        mob_level = int(raw_level or 1)
    except (TypeError, ValueError):
        mob_level = 1
    return 100 + mob_level * 2


def _apply_pr15_actionable_role_refinement(scaled_mob: dict, route_id: str, stage: str, archetype_id: str) -> dict:
    multipliers = PR15_ACTIONABLE_ROLE_REFINEMENTS.get((route_id, stage, archetype_id))
    if not multipliers:
        return scaled_mob
    adjusted = dict(scaled_mob)
    final_stats = dict(adjusted.get("final_mob_stats", {}))
    applied: dict[str, float] = {}
    skipped: dict[str, str] = {}
    for stat_key, multiplier in multipliers.items():
        source_value = final_stats.get(stat_key)
        if isinstance(source_value, (int, float)):
            value = int(round(source_value * multiplier))
        elif isinstance(adjusted.get(stat_key), (int, float)):
            source_value = adjusted[stat_key]
            value = int(round(source_value * multiplier))
        elif stat_key == "accuracy":
            baseline = _pr15_accuracy_fallback_baseline(adjusted)
            value = int(round(baseline * (float(multiplier) - 1.0)))
        else:
            skipped[stat_key] = "missing_final_stat_and_top_level_value"
            continue
        final_stats[stat_key] = max(1, value)
        adjusted[stat_key] = final_stats[stat_key]
        applied[stat_key] = multiplier
    if "damage" in applied:
        adjusted["damage_min"] = adjusted["damage"]
        adjusted["damage_max"] = adjusted["damage"]
    scale_components = dict(adjusted.get("scale_components", {}))
    scale_components["pr15_actionable_role_refinement"] = applied
    scale_components["pr15_actionable_role_refinement_skipped"] = skipped
    adjusted["scale_components"] = scale_components
    adjusted["final_mob_stats"] = final_stats
    return adjusted

def run_route_stage_simulation_matrix(config: RouteStageMatrixConfig | None = None) -> dict:
    cfg = config or RouteStageMatrixConfig()
    runs: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    sample_count = 0

    for route_id in cfg.route_ids:
        for stage in cfg.stages:
            samples = collect_route_stage_samples(route_id, stage, max_samples=cfg.max_samples_per_route_stage)
            sample_count += len(samples)
            for archetype_id in cfg.archetype_ids:
                metrics = {
                    "runs": 0, "wins": 0, "losses": 0, "timeouts": 0,
                    "turns_sum": 0, "php_sum": 0, "pmana_sum": 0, "dmg_dealt_sum": 0, "dmg_taken_sum": 0,
                    "skills_used_total": {}, "actions_used_total": {},
                }
                for sample in samples:
                    for seed in cfg.seeds:
                        player = build_archetype_player_preset(archetype_id, power_tier=stage)
                        mob_role = _resolve_tuned_sample_mob_role(route_id, stage, archetype_id, sample)
                        scaled_mob = build_scaled_mob_for_simulation(sample.mob_id, route_id, stage, mob_role=mob_role)
                        scaled_mob = _apply_pr15_actionable_role_refinement(scaled_mob, route_id, stage, archetype_id)
                        mob = build_simulation_mob_preset(sample.mob_id)
                        mob.update({k: v for k, v in scaled_mob.items() if k in ("hp", "damage", "accuracy", "evasion", "defense", "magic_defense", "damage_min", "damage_max")})
                        skill_levels = build_archetype_simulation_skill_levels(archetype_id, power_tier=stage)
                        policy_resolution = resolve_archetype_simulation_policy(archetype_id, stage)
                        result = simulate_single_combat(
                            player,
                            mob,
                            policy=policy_resolution["policy"],
                            config=SimulationConfig(
                                seed=seed,
                                max_turns=cfg.max_turns,
                                include_log_tail=False,
                                skill_levels=skill_levels,
                                include_turn_trace=cfg.include_turn_trace,
                                max_trace_turns=cfg.max_trace_turns,
                            ),
                        )
                        run_item = {
                            "route_id": route_id, "stage": stage, "archetype_id": archetype_id, "power_tier": stage,
                            "location_id": sample.location_id, "mob_id": sample.mob_id, "seed": seed,
                            "spawn_profile": sample.spawn_profile,
                            "sample_tags": list(sample.sample_tags),
                            "sample_source_route_id": str((WORLD_LOCATIONS.get(sample.location_id) or {}).get("route_id") or ""),
                            "encounter_level": scaled_mob.get("encounter_level"),
                            "mob_role": mob_role,
                            "scaling_status": scaled_mob.get("scaling_status", SCALING_STATUS_FORMULA_V1),
                            "base_mob_stats": dict(scaled_mob.get("base_mob_stats", {})),
                            "final_mob_stats": dict(scaled_mob.get("final_mob_stats", {})),
                            "scale_components": dict(scaled_mob.get("scale_components", {})),
                            "winner": result.winner, "turns": result.turns,
                            "terminated_by_max_turns": result.terminated_by_max_turns,
                            "player_dead": result.player_dead, "mob_dead": result.mob_dead,
                            "player_hp_remaining": result.player_hp_remaining,
                            "player_mana_remaining": result.player_mana_remaining,
                            "mob_hp_remaining": result.mob_hp_remaining,
                            "damage_dealt": result.damage_dealt, "damage_taken": result.damage_taken,
                            "actions_used": dict(result.actions_used), "skills_used": list(result.skills_used),
                            "observability": dict(result.observability),
                            "active_simulation_policy_id": policy_resolution.get("active_simulation_policy_id"),
                            "active_simulation_policy_status": policy_resolution.get("active_simulation_policy_status"),
                            "profile_policy_executable": policy_resolution.get("profile_policy_executable"),
                            "profile_policy_pilot": policy_resolution.get("profile_policy_pilot"),
                        }
                        if cfg.include_turn_trace and result.turn_trace:
                            run_item["turn_trace"] = list(result.turn_trace)
                        runs.append(run_item)
                        metrics["runs"] += 1
                        metrics["wins"] += 1 if result.winner == "player" else 0
                        metrics["losses"] += 1 if result.winner == "mob" else 0
                        metrics["timeouts"] += 1 if result.terminated_by_max_turns else 0
                        metrics["turns_sum"] += result.turns
                        metrics["php_sum"] += result.player_hp_remaining
                        metrics["pmana_sum"] += result.player_mana_remaining
                        metrics["dmg_dealt_sum"] += result.damage_dealt
                        metrics["dmg_taken_sum"] += result.damage_taken
                        for action_key, count in result.actions_used.items():
                            metrics["actions_used_total"][action_key] = metrics["actions_used_total"].get(action_key, 0) + int(count)
                        for skill_id in result.skills_used:
                            metrics["skills_used_total"][skill_id] = metrics["skills_used_total"].get(skill_id, 0) + 1

                if metrics["runs"] <= 0:
                    continue
                runs_count = metrics["runs"]
                summary = {
                    "route_id": route_id, "stage": stage, "archetype_id": archetype_id, "power_tier": stage,
                    "runs": runs_count, "wins": metrics["wins"], "losses": metrics["losses"], "timeouts": metrics["timeouts"],
                    "win_rate": metrics["wins"] / runs_count, "death_rate": metrics["losses"] / runs_count,
                    "avg_turns": metrics["turns_sum"] / runs_count,
                    "avg_player_hp_remaining": metrics["php_sum"] / runs_count,
                    "avg_player_mana_remaining": metrics["pmana_sum"] / runs_count,
                    "avg_damage_dealt": metrics["dmg_dealt_sum"] / runs_count,
                    "avg_damage_taken": metrics["dmg_taken_sum"] / runs_count,
                    "skills_used_total": dict(metrics["skills_used_total"]),
                    "actions_used_total": dict(metrics["actions_used_total"]),
                    "active_simulation_policy_status": resolve_archetype_simulation_policy(archetype_id, stage).get("active_simulation_policy_status"),
                }
                summary["observed_pressure_label"] = _label_observed_pressure(summary)
                summaries.append(summary)

    return {
        "routes": list(cfg.route_ids),
        "stages": list(cfg.stages),
        "archetypes": list(cfg.archetype_ids),
        "sample_count": sample_count,
        "run_count": len(runs),
        "runs": runs if cfg.include_raw_runs else [],
        "summaries": summaries,
        "limitations": [
            "Representative solo route-stage samples only.",
            "Pack proxy samples are added at report-data layer, not in solo matrix output.",
            "No live pack/group runtime combat.",
            "No final balance conclusions yet.",
            "No live route/mob/skill tuning performed.",
            "Simulation-stage pressure tuning is diagnostic/reporting-only.",
        ],
    }


def validate_route_stage_sample_coverage() -> list[str]:
    errors: list[str] = []
    if "core" in ALPHA_SIMULATION_ROUTE_IDS:
        errors.append("core route must not be included.")
    blocked = {"route_south_coast_stub", "route_old_mine_stub"}
    if blocked.intersection(ALPHA_SIMULATION_ROUTE_IDS):
        errors.append("stub routes must not be included.")
    for stage in ROUTE_SIMULATION_STAGES:
        if stage not in REQUIRED_POWER_TIERS:
            errors.append(f"stage {stage} does not map to required power tier")
    for route_id in ALPHA_SIMULATION_ROUTE_IDS:
        for stage in ROUTE_SIMULATION_STAGES:
            samples = collect_route_stage_samples(route_id, stage, max_samples=2)
            if not samples:
                errors.append(f"{route_id}@{stage}: missing samples")
                continue
            for sample in samples:
                if sample.location_id not in WORLD_LOCATIONS:
                    errors.append(f"{route_id}@{stage}: missing location {sample.location_id}")
                if sample.mob_id not in MOBS:
                    errors.append(f"{route_id}@{stage}: missing mob {sample.mob_id}")
                sample_route = str((WORLD_LOCATIONS.get(sample.location_id) or {}).get("route_id") or "")
                if sample_route and sample_route != route_id:
                    errors.append(f"{route_id}@{stage}: sample {sample.location_id} belongs to {sample_route}")
    return errors
