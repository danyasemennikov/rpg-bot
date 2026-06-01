from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Callable

from game.combat import (
    apply_timeout_fallback_guard,
    init_battle,
    process_enemy_side_turn,
    process_player_attack_side_turn,
    process_skill_turn,
)
from game.skills import get_skill
from game.skill_engine import calc_skill_mana_cost
from game.mobs import get_mob


SIM_ACTION_NORMAL_ATTACK = "normal_attack"
SIM_ACTION_GUARD_FALLBACK = "guard_fallback"
SIM_ACTION_SKILL_PREFIX = "skill:"


@dataclass
class SimulationConfig:
    seed: int = 1
    max_turns: int = 50
    lang: str = "ru"
    include_log_tail: bool = True
    skill_levels: dict[str, int] = field(default_factory=dict)
    include_turn_trace: bool = False
    max_trace_turns: int = 20


@dataclass
class SimulationResult:
    winner: str
    turns: int
    terminated_by_max_turns: bool
    player_hp_remaining: int
    player_mana_remaining: int
    mob_hp_remaining: int
    player_dead: bool
    mob_dead: bool
    seed: int
    actions_used: dict[str, int]
    skills_used: list[str]
    damage_dealt: int
    damage_taken: int
    final_battle_state: dict
    log_tail: list[str] = field(default_factory=list)
    turn_trace: list[dict] = field(default_factory=list)
    observability: dict = field(default_factory=dict)


class AlwaysAttackPolicy:
    def choose_action(self, *, turn: int, battle_state: dict) -> str:
        return SIM_ACTION_NORMAL_ATTACK


class AlwaysGuardFallbackPolicy:
    def choose_action(self, *, turn: int, battle_state: dict) -> str:
        return SIM_ACTION_GUARD_FALLBACK


class GuardThenAttackPolicy:
    """Simulation-only defensive policy.

    Uses periodic guard as a tactical action but avoids guard-only loops by
    defaulting to normal attacks on most turns.
    """

    def __init__(self, guard_every_n_turns: int = 3):
        self.guard_every_n_turns = max(2, int(guard_every_n_turns))

    def choose_action(self, *, turn: int, battle_state: dict) -> str:
        if turn % self.guard_every_n_turns == 0:
            return SIM_ACTION_GUARD_FALLBACK
        return SIM_ACTION_NORMAL_ATTACK


class ScriptedActionPolicy:
    def __init__(self, actions: list[str]):
        self.actions = list(actions)

    def choose_action(self, *, turn: int, battle_state: dict) -> str:
        if 1 <= turn <= len(self.actions):
            return self.actions[turn - 1]
        return SIM_ACTION_NORMAL_ATTACK


class ProfileAwareSimulationPolicy:
    """Conservative simulation-only profile policy.

    The policy follows a short visible rotation and falls back to normal attacks
    naturally when the simulator cannot execute a requested skill.  It only uses
    current battle-state HP for the optional sustain branch; it does not inspect
    future rolls or live player data.
    """

    def __init__(
        self,
        actions: list[str],
        *,
        low_hp_actions: list[str] | None = None,
        low_hp_threshold: float = 0.55,
    ):
        self.actions = list(actions)
        self.low_hp_actions = list(low_hp_actions or [])
        self.low_hp_threshold = float(low_hp_threshold)

    def _loop_action(self, actions: list[str], turn: int) -> str:
        if not actions:
            return SIM_ACTION_NORMAL_ATTACK
        return actions[(max(1, int(turn)) - 1) % len(actions)]

    def choose_action(self, *, turn: int, battle_state: dict) -> str:
        max_hp = max(1, int(battle_state.get("player_max_hp", battle_state.get("max_hp", 1)) or 1))
        current_hp = int(battle_state.get("player_hp", max_hp) or 0)
        if self.low_hp_actions and (current_hp / max_hp) <= self.low_hp_threshold:
            return self._loop_action(self.low_hp_actions, turn)
        return self._loop_action(self.actions, turn)


def make_simulation_skill_action(skill_id: str) -> str:
    return f"{SIM_ACTION_SKILL_PREFIX}{skill_id}"


def parse_simulation_skill_action(action: str) -> str | None:
    if not action.startswith(SIM_ACTION_SKILL_PREFIX):
        return None
    skill_id = action[len(SIM_ACTION_SKILL_PREFIX):].strip()
    return skill_id or None


def build_simulation_player_preset(**overrides) -> dict:
    player = {
        "id": 0,
        "name": "sim_player",
        "hp": 100,
        "max_hp": 100,
        "mana": 50,
        "max_mana": 50,
        "strength": 10,
        "agility": 10,
        "intuition": 10,
        "vitality": 10,
        "wisdom": 10,
        "luck": 10,
        "weapon_damage": 18,
        "weapon_type": "melee",
        "weapon_profile": "sword_1h",
        "armor_class": None,
        "offhand_profile": "none",
        "damage_school": "physical",
        "encumbrance": None,
        "equipment_physical_defense_bonus": 0,
        "equipment_magic_defense_bonus": 0,
        "equipment_accuracy_bonus": 0,
        "equipment_evasion_bonus": 0,
        "equipment_block_chance_bonus": 0,
        "equipment_magic_power_bonus": 0,
        "equipment_healing_power_bonus": 0,
    }
    player.update(overrides)
    return player


def build_simulation_mob_preset(mob_id: str) -> dict:
    mob = get_mob(mob_id)
    if not mob:
        raise ValueError(f"Unknown mob id: {mob_id}")
    return copy.deepcopy(mob)


def build_simulation_battle_state(player: dict, mob: dict) -> dict:
    battle_state = init_battle(player, mob)
    battle_state["weapon_type"] = player.get("weapon_type", "melee")
    battle_state["weapon_profile"] = player.get("weapon_profile", "unarmed")
    battle_state["weapon_damage"] = player.get("weapon_damage", 10)
    battle_state["armor_class"] = player.get("armor_class")
    battle_state["offhand_profile"] = player.get("offhand_profile", "none")
    battle_state["damage_school"] = player.get("damage_school", "physical")
    battle_state["encumbrance"] = player.get("encumbrance")

    for key in (
        "equipment_physical_defense_bonus",
        "equipment_magic_defense_bonus",
        "equipment_accuracy_bonus",
        "equipment_evasion_bonus",
        "equipment_block_chance_bonus",
        "equipment_magic_power_bonus",
        "equipment_healing_power_bonus",
    ):
        battle_state[key] = int(player.get(key, 0) or 0)

    for stat in ("strength", "agility", "intuition", "vitality", "wisdom", "luck"):
        battle_state[f"effective_{stat}"] = int(player.get(stat, 1) or 1)

    return battle_state



def _snapshot_combat_totals(battle_state: dict) -> dict[str, int]:
    return {
        "hp": int(battle_state.get("player_hp", 0)),
        "mana": int(battle_state.get("player_mana", 0)),
        "mob_hp": int(battle_state.get("mob_hp", 0)),
    }


def _sanitize_log_events(log_items: list, *, limit: int = 4, max_chars: int = 160) -> list[str]:
    output: list[str] = []
    for item in list(log_items)[:limit]:
        text = str(item).replace("|", "\\|").replace("\n", " ")
        if len(text) > max_chars:
            text = text[: max_chars - 3] + "..."
        output.append(text)
    return output


def _safe_current_turn_log_events(before: list, after: list, *, limit: int = 4, max_chars: int = 160) -> list[str]:
    after_items = list(after or [])
    if not after_items:
        return []

    before_items = list(before or [])
    if len(after_items) >= len(before_items) and after_items[:len(before_items)] == before_items:
        events = after_items[len(before_items):]
    else:
        events = after_items

    return _sanitize_log_events(events, limit=limit, max_chars=max_chars)


def _build_observability_summary(
    *,
    winner: str,
    turns: int,
    terminated_by_max_turns: bool,
    player_local: dict,
    mob_local: dict,
    battle_state: dict,
    actions_used: dict[str, int],
    skills_used: list[str],
    damage_dealt: int,
    damage_taken: int,
    action_resolution_counts: dict[str, int] | None = None,
    fallback_reason_counts: dict[str, int] | None = None,
    requested_skill_count: int = 0,
    resolved_skill_success_count: int = 0,
    normal_attack_fallback_count: int = 0,
) -> dict:
    player_max_hp = max(1, int(player_local.get("max_hp") or player_local.get("hp") or 1))
    player_max_mana = max(1, int(player_local.get("max_mana") or player_local.get("mana") or 1))
    mob_start_hp = max(1, int(mob_local.get("hp") or 1))
    player_hp_remaining = max(0, int(battle_state.get("player_hp", 0)))
    player_mana_remaining = max(0, int(battle_state.get("player_mana", 0)))
    mob_hp_remaining = max(0, int(battle_state.get("mob_hp", 0)))

    if winner == "player":
        end_reason = "player_win"
    elif winner == "mob":
        end_reason = "player_death"
    elif terminated_by_max_turns:
        end_reason = "timeout"
    else:
        end_reason = "no_winner"

    safe_turns = max(1, int(turns))
    return {
        "damage_dealt": int(damage_dealt),
        "damage_taken": int(damage_taken),
        "damage_dealt_per_turn": int(damage_dealt) / safe_turns,
        "damage_taken_per_turn": int(damage_taken) / safe_turns,
        "player_hp_remaining_pct": min(1.0, max(0.0, player_hp_remaining / player_max_hp)),
        "player_mana_remaining_pct": min(1.0, max(0.0, player_mana_remaining / player_max_mana)),
        "mob_hp_removed_pct": min(1.0, max(0.0, (mob_start_hp - mob_hp_remaining) / mob_start_hp)),
        "mana_spent": max(0, int(player_local.get("mana", 0)) - player_mana_remaining),
        "skills_used_count": len(skills_used),
        "normal_attacks_used": int(actions_used.get(SIM_ACTION_NORMAL_ATTACK, 0)),
        "guard_used": int(actions_used.get(SIM_ACTION_GUARD_FALLBACK, 0)),
        "end_reason": end_reason,
        "action_resolution_counts": dict(action_resolution_counts or {}),
        "fallback_reason_counts": dict(fallback_reason_counts or {}),
        "requested_skill_count": int(requested_skill_count),
        "resolved_skill_success_count": int(resolved_skill_success_count),
        "normal_attack_fallback_count": int(normal_attack_fallback_count),
    }

def _run_with_seed(seed: int, fn: Callable[[], SimulationResult]) -> SimulationResult:
    previous_state = random.getstate()
    random.seed(seed)
    try:
        return fn()
    finally:
        random.setstate(previous_state)


def simulate_single_combat(
    player: dict,
    mob: dict,
    *,
    policy=None,
    config: SimulationConfig | None = None,
) -> SimulationResult:
    cfg = config or SimulationConfig()
    action_policy = policy or AlwaysAttackPolicy()

    player_local = copy.deepcopy(player)
    mob_local = copy.deepcopy(mob)
    battle_state = build_simulation_battle_state(player_local, mob_local)

    actions_used = {SIM_ACTION_NORMAL_ATTACK: 0, SIM_ACTION_GUARD_FALLBACK: 0}
    simulation_cooldowns: dict[str, int] = {}
    turn_trace: list[dict] = []
    max_trace_turns = max(0, int(cfg.max_trace_turns))
    action_resolution_counts: dict[str, int] = {}
    fallback_reason_counts: dict[str, int] = {}
    requested_skill_count = 0
    resolved_skill_success_count = 0
    normal_attack_fallback_count = 0

    def _count_action_resolution(status: str, fallback_reason: str | None) -> None:
        action_resolution_counts[status] = action_resolution_counts.get(status, 0) + 1
        if fallback_reason:
            fallback_reason_counts[fallback_reason] = fallback_reason_counts.get(fallback_reason, 0) + 1

    def _build_skill_resolution_metadata(chosen_action: str, requested_skill_id: str | None) -> dict:
        skill_def = get_skill(requested_skill_id) if requested_skill_id else None
        skill_level = int(cfg.skill_levels.get(requested_skill_id, 0)) if requested_skill_id else 0
        cooldown_before = int(simulation_cooldowns.get(requested_skill_id, 0)) if requested_skill_id else 0
        mana_before = int(battle_state.get("player_mana", 0) or 0)
        mana_cost = calc_skill_mana_cost(skill_def, skill_level) if skill_def and skill_level > 0 else 0
        skill_exists = bool(skill_def)
        skill_unlock_mastery = int(skill_def.get("unlock_mastery", 0) or 0) if skill_def else None
        skill_visible = bool(skill_def and skill_level > 0 and skill_level >= int(skill_def.get("unlock_mastery", 0) or 0))
        can_attempt_skill = bool(skill_exists and skill_visible and cooldown_before <= 0 and (mana_cost <= 0 or mana_before >= mana_cost))
        return {
            "requested_action": chosen_action,
            "requested_skill_id": requested_skill_id,
            "resolved_action": "no_player_action",
            "action_resolution_status": "unknown_fallback",
            "fallback_reason": None,
            "skill_exists": skill_exists if requested_skill_id else None,
            "skill_level": skill_level if requested_skill_id else None,
            "skill_unlock_mastery": skill_unlock_mastery,
            "skill_visible": skill_visible if requested_skill_id else None,
            "cooldown_before": cooldown_before if requested_skill_id else None,
            "mana_before": mana_before,
            "mana_cost": mana_cost if requested_skill_id else None,
            "can_attempt_skill": can_attempt_skill if requested_skill_id else None,
        }

    def _classify_skill_guard_failure(meta: dict) -> str:
        if not meta.get("skill_exists"):
            return "skill_missing"
        if int(meta.get("skill_level") or 0) <= 0 or not meta.get("skill_visible"):
            return "skill_locked_or_unleveled"
        if int(meta.get("cooldown_before") or 0) > 0:
            return "skill_on_cooldown"
        if int(meta.get("mana_cost") or 0) > int(meta.get("mana_before") or 0):
            return "insufficient_mana"
        return "unknown_fallback"

    def _tick_skill_cooldowns() -> None:
        for sid, turns in list(simulation_cooldowns.items()):
            remaining = int(turns) - 1
            if remaining > 0:
                simulation_cooldowns[sid] = remaining
            else:
                simulation_cooldowns.pop(sid, None)

    def _run() -> SimulationResult:
        nonlocal requested_skill_count, resolved_skill_success_count, normal_attack_fallback_count

        terminated_by_max_turns = False
        executed_turns = 0

        while executed_turns < cfg.max_turns:
            if battle_state.get("mob_hp", 0) <= 0 or battle_state.get("player_hp", 0) <= 0:
                break

            turn_number = int(battle_state.get("turn", 1))
            trace_before = _snapshot_combat_totals(battle_state)
            log_before = list(battle_state.get("log", []))
            trace_after_player_action = dict(trace_before)
            chosen_action = action_policy.choose_action(turn=turn_number, battle_state=battle_state)
            action = chosen_action
            requested_skill_id = parse_simulation_skill_action(chosen_action)
            resolution_meta = _build_skill_resolution_metadata(chosen_action, requested_skill_id)
            invalid_policy_action = action not in actions_used and requested_skill_id is None
            if invalid_policy_action:
                action = SIM_ACTION_NORMAL_ATTACK
                resolution_meta["action_resolution_status"] = "invalid_policy_action_fallback"
                resolution_meta["fallback_reason"] = "invalid_policy_action_fallback"
            resolved_action = "no_player_action"

            if action == SIM_ACTION_NORMAL_ATTACK:
                if battle_state.get("player_goes_first", True):
                    process_player_attack_side_turn(
                        player_local,
                        mob_local,
                        battle_state,
                        lang=cfg.lang,
                    )
                    actions_used[SIM_ACTION_NORMAL_ATTACK] += 1
                    resolved_action = SIM_ACTION_NORMAL_ATTACK
                    if not invalid_policy_action:
                        resolution_meta["action_resolution_status"] = "policy_chose_normal_attack"
                    trace_after_player_action = _snapshot_combat_totals(battle_state)
                    if battle_state.get("mob_hp", 0) > 0:
                        process_enemy_side_turn(
                            mob_local,
                            player_local,
                            battle_state,
                            lang=cfg.lang,
                            tick_player_post_action_buffs=True,
                            tick_timed_trigger_buffs=True,
                            increment_turn=True,
                        )
                    else:
                        battle_state["turn"] = int(battle_state.get("turn", 0)) + 1
                else:
                    process_enemy_side_turn(
                        mob_local,
                        player_local,
                        battle_state,
                        lang=cfg.lang,
                    )
                    if battle_state.get("player_hp", 0) > 0:
                        process_player_attack_side_turn(
                            player_local,
                            mob_local,
                            battle_state,
                            lang=cfg.lang,
                        )
                        actions_used[SIM_ACTION_NORMAL_ATTACK] += 1
                        resolved_action = SIM_ACTION_NORMAL_ATTACK
                        if not invalid_policy_action:
                            resolution_meta["action_resolution_status"] = "policy_chose_normal_attack"
                        trace_after_player_action = _snapshot_combat_totals(battle_state)
                    else:
                        resolved_action = "enemy_first_player_dead"
                    battle_state["turn"] = int(battle_state.get("turn", 0)) + 1
            elif action == SIM_ACTION_GUARD_FALLBACK:
                apply_timeout_fallback_guard(battle_state, lang=cfg.lang)
                actions_used[SIM_ACTION_GUARD_FALLBACK] += 1
                resolved_action = SIM_ACTION_GUARD_FALLBACK
                resolution_meta["action_resolution_status"] = "guard_fallback_action"
                resolution_meta["fallback_reason"] = "guard_fallback_action"
                trace_after_player_action = _snapshot_combat_totals(battle_state)
                process_enemy_side_turn(
                    mob_local,
                    player_local,
                    battle_state,
                    lang=cfg.lang,
                    increment_turn=True,
                    tick_player_post_action_buffs=True,
                    tick_timed_trigger_buffs=True,
                )
            elif requested_skill_id is not None:
                action_key = make_simulation_skill_action(requested_skill_id)
                if action_key not in actions_used:
                    actions_used[action_key] = 0

                skill_level = int(cfg.skill_levels.get(requested_skill_id, 0))
                skill_def = get_skill(requested_skill_id)
                local_cd = int(simulation_cooldowns.get(requested_skill_id, 0))
                can_use = bool(resolution_meta.get("can_attempt_skill"))

                if battle_state.get("player_goes_first", True):
                    if can_use:
                        skill_turn = process_skill_turn(
                            requested_skill_id, player_local, mob_local, battle_state, 0, cfg.lang,
                            include_enemy_response=False,
                            tick_timed_trigger_buffs_now=False,
                            skill_level_override=skill_level,
                            cooldown_override=local_cd,
                            commit_cooldown_to_db=False,
                        )
                        if skill_turn.get("success"):
                            actions_used[action_key] += 1
                            resolved_action = action_key
                            resolution_meta["action_resolution_status"] = "resolved_skill_success"
                            battle_state.setdefault("skills_used", []).append(requested_skill_id)
                            simulation_cooldowns[requested_skill_id] = int(skill_def.get("cooldown", 0))
                        else:
                            process_player_attack_side_turn(player_local, mob_local, battle_state, lang=cfg.lang)
                            actions_used[SIM_ACTION_NORMAL_ATTACK] += 1
                            resolved_action = SIM_ACTION_NORMAL_ATTACK
                            reason = _classify_skill_guard_failure(resolution_meta)
                            if reason == "unknown_fallback":
                                reason = "skill_execution_failed"
                            resolution_meta["action_resolution_status"] = reason
                            resolution_meta["fallback_reason"] = reason
                    else:
                        process_player_attack_side_turn(player_local, mob_local, battle_state, lang=cfg.lang)
                        actions_used[SIM_ACTION_NORMAL_ATTACK] += 1
                        resolved_action = SIM_ACTION_NORMAL_ATTACK
                        reason = _classify_skill_guard_failure(resolution_meta)
                        resolution_meta["action_resolution_status"] = reason
                        resolution_meta["fallback_reason"] = reason
                    trace_after_player_action = _snapshot_combat_totals(battle_state)
                    if battle_state.get("mob_hp", 0) > 0:
                        process_enemy_side_turn(mob_local, player_local, battle_state, lang=cfg.lang, tick_player_post_action_buffs=True, tick_timed_trigger_buffs=True, increment_turn=True)
                    else:
                        battle_state["turn"] = int(battle_state.get("turn", 0)) + 1
                else:
                    process_enemy_side_turn(mob_local, player_local, battle_state, lang=cfg.lang)
                    if battle_state.get("player_hp", 0) > 0:
                        if can_use:
                            skill_turn = process_skill_turn(
                                requested_skill_id, player_local, mob_local, battle_state, 0, cfg.lang,
                                include_enemy_response=False,
                                skill_level_override=skill_level,
                                cooldown_override=local_cd,
                                commit_cooldown_to_db=False,
                            )
                            if skill_turn.get("success"):
                                actions_used[action_key] += 1
                                resolved_action = action_key
                                resolution_meta["action_resolution_status"] = "resolved_skill_success"
                                battle_state.setdefault("skills_used", []).append(requested_skill_id)
                                simulation_cooldowns[requested_skill_id] = int(skill_def.get("cooldown", 0))
                            else:
                                process_player_attack_side_turn(player_local, mob_local, battle_state, lang=cfg.lang)
                                actions_used[SIM_ACTION_NORMAL_ATTACK] += 1
                                resolved_action = SIM_ACTION_NORMAL_ATTACK
                                reason = _classify_skill_guard_failure(resolution_meta)
                                if reason == "unknown_fallback":
                                    reason = "skill_execution_failed"
                                resolution_meta["action_resolution_status"] = reason
                                resolution_meta["fallback_reason"] = reason
                        else:
                            process_player_attack_side_turn(player_local, mob_local, battle_state, lang=cfg.lang)
                            actions_used[SIM_ACTION_NORMAL_ATTACK] += 1
                            resolved_action = SIM_ACTION_NORMAL_ATTACK
                            reason = _classify_skill_guard_failure(resolution_meta)
                            resolution_meta["action_resolution_status"] = reason
                            resolution_meta["fallback_reason"] = reason
                    else:
                        resolved_action = "enemy_first_player_dead"
                    trace_after_player_action = _snapshot_combat_totals(battle_state)
                    battle_state["turn"] = int(battle_state.get("turn", 0)) + 1

            resolution_meta["resolved_action"] = resolved_action
            if resolution_meta.get("action_resolution_status") == "unknown_fallback" and resolved_action == SIM_ACTION_NORMAL_ATTACK:
                resolution_meta["fallback_reason"] = resolution_meta.get("fallback_reason") or "unknown_fallback"
            _count_action_resolution(
                str(resolution_meta.get("action_resolution_status") or "unknown_fallback"),
                resolution_meta.get("fallback_reason"),
            )
            if requested_skill_id is not None:
                requested_skill_count += 1
            if resolution_meta.get("action_resolution_status") == "resolved_skill_success":
                resolved_skill_success_count += 1
            if requested_skill_id is not None and resolved_action == SIM_ACTION_NORMAL_ATTACK and resolution_meta.get("fallback_reason"):
                normal_attack_fallback_count += 1

            trace_after_enemy_action = _snapshot_combat_totals(battle_state)
            if cfg.include_turn_trace and len(turn_trace) < max_trace_turns:
                turn_trace.append({
                    "turn": turn_number,
                    "chosen_action": chosen_action,
                    "requested_action": resolution_meta.get("requested_action"),
                    "resolved_action": resolved_action,
                    "action_resolution_status": resolution_meta.get("action_resolution_status"),
                    "fallback_reason": resolution_meta.get("fallback_reason"),
                    "requested_skill_id": requested_skill_id,
                    "skill_exists": resolution_meta.get("skill_exists"),
                    "skill_level": resolution_meta.get("skill_level"),
                    "skill_unlock_mastery": resolution_meta.get("skill_unlock_mastery"),
                    "skill_visible": resolution_meta.get("skill_visible"),
                    "cooldown_before": resolution_meta.get("cooldown_before"),
                    "mana_before": resolution_meta.get("mana_before"),
                    "mana_cost": resolution_meta.get("mana_cost"),
                    "can_attempt_skill": resolution_meta.get("can_attempt_skill"),
                    "player_before": {"hp": trace_before["hp"], "mana": trace_before["mana"]},
                    "mob_before": {"hp": trace_before["mob_hp"]},
                    "player_after_player_action": {"hp": trace_after_player_action["hp"], "mana": trace_after_player_action["mana"]},
                    "mob_after_player_action": {"hp": trace_after_player_action["mob_hp"]},
                    "player_after_enemy_action": {"hp": trace_after_enemy_action["hp"], "mana": trace_after_enemy_action["mana"]},
                    "mob_after_enemy_action": {"hp": trace_after_enemy_action["mob_hp"]},
                    "player_hp_delta": trace_after_enemy_action["hp"] - trace_before["hp"],
                    "player_mana_delta": trace_after_enemy_action["mana"] - trace_before["mana"],
                    "mob_hp_delta": trace_after_enemy_action["mob_hp"] - trace_before["mob_hp"],
                    "cooldowns_after": dict(simulation_cooldowns),
                    "log_events": _safe_current_turn_log_events(log_before, battle_state.get("log", [])),
                })

            _tick_skill_cooldowns()
            executed_turns += 1

        if battle_state.get("mob_hp", 0) > 0 and battle_state.get("player_hp", 0) > 0:
            terminated_by_max_turns = executed_turns >= cfg.max_turns

        player_dead = battle_state.get("player_hp", 0) <= 0
        mob_dead = battle_state.get("mob_hp", 0) <= 0

        if player_dead and mob_dead:
            winner = "none"
        elif mob_dead:
            winner = "player"
        elif player_dead:
            winner = "mob"
        else:
            winner = "none"

        skills_used = list(battle_state.get("skills_used", []))
        damage_dealt = max(0, int(mob_local.get("hp", 0)) - int(battle_state.get("mob_hp", 0)))
        damage_taken = max(0, int(player_local.get("hp", 0)) - int(battle_state.get("player_hp", 0)))
        observability = _build_observability_summary(
            winner=winner,
            turns=executed_turns,
            terminated_by_max_turns=terminated_by_max_turns,
            player_local=player_local,
            mob_local=mob_local,
            battle_state=battle_state,
            actions_used=actions_used,
            skills_used=skills_used,
            damage_dealt=damage_dealt,
            damage_taken=damage_taken,
            action_resolution_counts=action_resolution_counts,
            fallback_reason_counts=fallback_reason_counts,
            requested_skill_count=requested_skill_count,
            resolved_skill_success_count=resolved_skill_success_count,
            normal_attack_fallback_count=normal_attack_fallback_count,
        )
        return SimulationResult(
            winner=winner,
            turns=executed_turns,
            terminated_by_max_turns=terminated_by_max_turns,
            player_hp_remaining=int(battle_state.get("player_hp", 0)),
            player_mana_remaining=int(battle_state.get("player_mana", 0)),
            mob_hp_remaining=int(battle_state.get("mob_hp", 0)),
            player_dead=player_dead,
            mob_dead=mob_dead,
            seed=cfg.seed,
            actions_used=dict(actions_used),
            skills_used=skills_used,
            damage_dealt=damage_dealt,
            damage_taken=damage_taken,
            final_battle_state=copy.deepcopy(battle_state),
            log_tail=list(battle_state.get("log", []))[-6:] if cfg.include_log_tail else [],
            turn_trace=copy.deepcopy(turn_trace) if cfg.include_turn_trace else [],
            observability=observability,
        )

    return _run_with_seed(cfg.seed, _run)
