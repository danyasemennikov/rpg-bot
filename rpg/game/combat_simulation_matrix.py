from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from game.combat_simulation import (
    SIM_ACTION_NORMAL_ATTACK,
    ScriptedActionPolicy,
    SimulationConfig,
    build_simulation_mob_preset,
    make_simulation_skill_action,
    simulate_single_combat,
)
from game.combat_simulation_archetypes import (
    EXECUTABLE_POLICY_REGISTRY,
    REQUIRED_POWER_TIERS,
    build_archetype_player_preset,
    build_archetype_simulation_skill_levels,
    get_archetype_metadata,
    list_alpha_archetype_ids,
)
from game.locations import WORLD_LOCATIONS
from game.mobs import MOBS

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


def build_basic_archetype_simulation_policy(archetype_id: str, power_tier: str):
    _ = power_tier
    metadata = get_archetype_metadata(archetype_id)
    pref_policy = metadata.get("preferred_policy_id")
    registry_item = EXECUTABLE_POLICY_REGISTRY.get(pref_policy)
    if registry_item and registry_item.get("executable"):
        return registry_item["factory"]()

    skill_levels = build_archetype_simulation_skill_levels(archetype_id, power_tier)
    chosen_skill = None
    for skill_id in metadata.get("preferred_skill_ids", []):
        if skill_id in skill_levels:
            chosen_skill = skill_id
            break

    actions = [SIM_ACTION_NORMAL_ATTACK, SIM_ACTION_NORMAL_ATTACK]
    if chosen_skill:
        actions = [make_simulation_skill_action(chosen_skill), SIM_ACTION_NORMAL_ATTACK, SIM_ACTION_NORMAL_ATTACK]
    return ScriptedActionPolicy(actions)


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
                        mob = build_simulation_mob_preset(sample.mob_id)
                        skill_levels = build_archetype_simulation_skill_levels(archetype_id, power_tier=stage)
                        result = simulate_single_combat(
                            player,
                            mob,
                            policy=build_basic_archetype_simulation_policy(archetype_id, stage),
                            config=SimulationConfig(seed=seed, max_turns=cfg.max_turns, include_log_tail=False, skill_levels=skill_levels),
                        )
                        run_item = {
                            "route_id": route_id, "stage": stage, "archetype_id": archetype_id, "power_tier": stage,
                            "location_id": sample.location_id, "mob_id": sample.mob_id, "seed": seed,
                            "spawn_profile": sample.spawn_profile,
                            "sample_tags": list(sample.sample_tags),
                            "sample_source_route_id": str((WORLD_LOCATIONS.get(sample.location_id) or {}).get("route_id") or ""),
                            "winner": result.winner, "turns": result.turns,
                            "terminated_by_max_turns": result.terminated_by_max_turns,
                            "player_dead": result.player_dead, "mob_dead": result.mob_dead,
                            "player_hp_remaining": result.player_hp_remaining,
                            "player_mana_remaining": result.player_mana_remaining,
                            "mob_hp_remaining": result.mob_hp_remaining,
                            "damage_dealt": result.damage_dealt, "damage_taken": result.damage_taken,
                            "actions_used": dict(result.actions_used), "skills_used": list(result.skills_used),
                        }
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
            "Representative solo samples only (route-stage mob snapshots).",
            "No pack/group runtime simulation matrix yet.",
            "No final balance conclusions yet.",
            "No route/mob/skill tuning performed.",
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
