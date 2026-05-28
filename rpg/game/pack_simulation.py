from __future__ import annotations

from dataclasses import dataclass

from game.balance_audit import audit_pack_sample_coverage, summarize_balance_audit_flags
from game.combat_simulation import SimulationConfig, build_simulation_mob_preset, simulate_single_combat
from game.combat_simulation_archetypes import build_archetype_player_preset, build_archetype_simulation_skill_levels, list_alpha_archetype_ids
from game.combat_simulation_matrix import ALPHA_SIMULATION_ROUTE_IDS, build_basic_archetype_simulation_policy
from game.mob_scaling import ROLE_PACK_LEADER, ROLE_PACK_MEMBER, build_scaled_mob_for_simulation

PACK_SIMULATION_STATUS_COMPOSITE_V1 = "composite_pack_pressure_v1"
PACK_REQUIRED_STAGES = ("build_testing", "route_exam")
PACK_SIMULTANEITY_DAMAGE_FACTOR = 0.75

@dataclass(frozen=True)
class PackMemberSpec:
    mob_id: str
    role: str = ROLE_PACK_MEMBER
    count: int = 1

@dataclass(frozen=True)
class PackSimulationSample:
    pack_id: str
    route_id: str
    stage: str
    location_id: str
    members: tuple[PackMemberSpec, ...]
    tags: tuple[str, ...] = ()


def list_alpha_pack_samples() -> list[PackSimulationSample]:
    return [
        PackSimulationSample("westwild_build_wolf_boar", "route_westwild", "build_testing", "westwild_n7", (PackMemberSpec("forest_wolf", count=2), PackMemberSpec("forest_boar", role=ROLE_PACK_LEADER))),
        PackSimulationSample("westwild_exam_bear_goblins", "route_westwild", "route_exam", "westwild_n9", (PackMemberSpec("goblin_scout", count=2), PackMemberSpec("bear", role=ROLE_PACK_LEADER))),
        PackSimulationSample("frost_build_wolves", "route_frostspine", "build_testing", "frostspine_n6", (PackMemberSpec("white_wolf", count=2), PackMemberSpec("stone_beetle", role=ROLE_PACK_LEADER))),
        PackSimulationSample("frost_exam_golem_pack", "route_frostspine", "route_exam", "frostspine_n9", (PackMemberSpec("white_wolf", count=2), PackMemberSpec("mountain_stone_golem", role=ROLE_PACK_LEADER))),
        PackSimulationSample("ashen_build_undead", "route_ashen_ruins", "build_testing", "ashen_n7", (PackMemberSpec("zombie", count=2), PackMemberSpec("skeleton_guard", role=ROLE_PACK_LEADER))),
        PackSimulationSample("ashen_exam_knight_host", "route_ashen_ruins", "route_exam", "ashen_n3b2a1", (PackMemberSpec("skeleton_mage"), PackMemberSpec("cursed_knight", role=ROLE_PACK_LEADER))),
        PackSimulationSample("mireveil_build_swarm", "route_mireveil", "build_testing", "mireveil_n7", (PackMemberSpec("swamp_spider", count=2), PackMemberSpec("water_snake", role=ROLE_PACK_LEADER))),
        PackSimulationSample("mireveil_exam_serpent", "route_mireveil", "route_exam", "mireveil_n9", (PackMemberSpec("leech", count=2), PackMemberSpec("water_snake", role=ROLE_PACK_LEADER))),
        PackSimulationSample("sunscar_build_scorpion", "route_sunscar", "build_testing", "sunscar_n7", (PackMemberSpec("scorpion", count=2), PackMemberSpec("snake", role=ROLE_PACK_LEADER))),
        PackSimulationSample("sunscar_exam_apex", "route_sunscar", "route_exam", "sunscar_n9", (PackMemberSpec("scorpion", count=2), PackMemberSpec("crocodile", role=ROLE_PACK_LEADER))),
    ]


def collect_pack_samples(route_id: str, stage: str) -> list[PackSimulationSample]:
    return [s for s in list_alpha_pack_samples() if s.route_id == route_id and s.stage == stage]


def build_composite_pack_mob_for_simulation(sample: PackSimulationSample) -> dict:
    member_stats = []
    for spec in sample.members:
        for _ in range(max(1, int(spec.count))):
            scaled = build_scaled_mob_for_simulation(spec.mob_id, sample.route_id, sample.stage, mob_role=spec.role)
            member_stats.append({"mob_id": spec.mob_id, "role": spec.role, "final_mob_stats": dict(scaled.get("final_mob_stats", {}))})
    hp = sum(m["final_mob_stats"].get("hp", 0) for m in member_stats)
    raw_damage = sum(m["final_mob_stats"].get("damage", 0) for m in member_stats)
    dmg = max(1, int(round(raw_damage * PACK_SIMULTANEITY_DAMAGE_FACTOR)))
    acc = max((m["final_mob_stats"].get("accuracy", 0) for m in member_stats), default=0)
    ev = max((m["final_mob_stats"].get("evasion", 0) for m in member_stats), default=0)
    df = int(round(sum(m["final_mob_stats"].get("defense", 0) for m in member_stats) / max(1, len(member_stats))))
    mdf = int(round(sum(m["final_mob_stats"].get("magic_defense", 0) for m in member_stats) / max(1, len(member_stats))))
    mob = build_simulation_mob_preset(member_stats[0]["mob_id"])
    mob.update({"id": f"pack::{sample.pack_id}", "name": f"Pack {sample.pack_id}", "hp": max(1, hp), "damage": dmg, "accuracy": acc, "evasion": ev, "defense": df, "magic_defense": mdf})
    mob["pack_id"] = sample.pack_id
    mob["route_id"] = sample.route_id
    mob["stage"] = sample.stage
    mob["location_id"] = sample.location_id
    mob["pack_member_count"] = len(member_stats)
    mob["pack_members"] = [{"mob_id": s.mob_id, "role": s.role, "count": s.count} for s in sample.members]
    mob["pack_member_final_stats"] = member_stats
    mob["pack_simulation_status"] = PACK_SIMULATION_STATUS_COMPOSITE_V1
    mob["pack_aggregation"] = {"method": "composite_pressure_v1", "damage_factor": PACK_SIMULTANEITY_DAMAGE_FACTOR, "defense_aggregation": "average", "magic_defense_aggregation": "average", "accuracy_aggregation": "max", "evasion_aggregation": "max"}
    mob["final_pack_stats"] = {"hp": mob["hp"], "damage": mob["damage"], "accuracy": acc, "evasion": ev, "defense": df, "magic_defense": mdf}
    return mob


def _label_pack_observed_v2(*, winner: str, terminated_by_max_turns: bool, turns: int, player_dead: bool, mob_dead: bool, damage_dealt: int, damage_taken: int) -> str:
    if terminated_by_max_turns:
        if damage_dealt <= 0 and damage_taken > 0:
            return "no_progress_stall"
        return "timeout_stall"
    if winner == "mob" or player_dead:
        return "death_blocked"
    if winner == "player" and mob_dead:
        if turns <= 10 and damage_taken <= max(1, int(0.5 * max(1, damage_dealt))):
            return "strong_clean"
        if turns <= 18:
            return "strong_but_risky"
        return "normal"
    return "inconclusive"


def run_pack_simulation_matrix(*, route_ids: tuple[str, ...] = ALPHA_SIMULATION_ROUTE_IDS, stages: tuple[str, ...] = PACK_REQUIRED_STAGES, archetype_ids: tuple[str, ...] | None = None, seeds: tuple[int, ...] = (1,), max_turns: int = 50) -> dict:
    archetypes = archetype_ids or tuple(list_alpha_archetype_ids())
    pack_samples = [s for s in list_alpha_pack_samples() if s.route_id in route_ids and s.stage in stages]
    pack_runs = []
    for sample in pack_samples:
        composite = build_composite_pack_mob_for_simulation(sample)
        for archetype_id in archetypes:
            for seed in seeds:
                player = build_archetype_player_preset(archetype_id, sample.stage)
                skill_levels = build_archetype_simulation_skill_levels(archetype_id, sample.stage)
                res = simulate_single_combat(player, composite, policy=build_basic_archetype_simulation_policy(archetype_id, sample.stage), config=SimulationConfig(seed=seed, max_turns=max_turns, include_log_tail=False, skill_levels=skill_levels))
                pack_runs.append({"route_id": sample.route_id, "stage": sample.stage, "archetype_id": archetype_id, "pack_id": sample.pack_id, "location_id": sample.location_id, "pack_member_count": composite["pack_member_count"], "pack_members": composite["pack_members"], "pack_member_final_stats": composite["pack_member_final_stats"], "final_pack_stats": composite["final_pack_stats"], "pack_simulation_status": composite["pack_simulation_status"], "winner": res.winner, "turns": res.turns, "terminated_by_max_turns": res.terminated_by_max_turns, "player_dead": res.player_dead, "mob_dead": res.mob_dead, "damage_dealt": res.damage_dealt, "damage_taken": res.damage_taken, "actions_used": dict(res.actions_used), "skills_used": list(res.skills_used), "observed_diagnostic_label_v2": _label_pack_observed_v2(winner=res.winner, terminated_by_max_turns=res.terminated_by_max_turns, turns=res.turns, player_dead=res.player_dead, mob_dead=res.mob_dead, damage_dealt=res.damage_dealt, damage_taken=res.damage_taken)})
    rollups = {"runs": len(pack_runs), "wins": sum(1 for r in pack_runs if r["winner"] == "player")}
    audit_flags = audit_pack_sample_coverage([s.__dict__ for s in pack_samples], tuple(route_ids), tuple(stages))
    return {"pack_runs": pack_runs, "pack_samples": [s.__dict__ for s in pack_samples], "pack_rollups": rollups, "pack_audit_flags": audit_flags, "pack_audit_flag_counts": summarize_balance_audit_flags(audit_flags)}
