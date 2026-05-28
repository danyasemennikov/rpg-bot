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

    def _tick_skill_cooldowns() -> None:
        for sid, turns in list(simulation_cooldowns.items()):
            remaining = int(turns) - 1
            if remaining > 0:
                simulation_cooldowns[sid] = remaining
            else:
                simulation_cooldowns.pop(sid, None)

    def _run() -> SimulationResult:
        terminated_by_max_turns = False
        executed_turns = 0

        while executed_turns < cfg.max_turns:
            if battle_state.get("mob_hp", 0) <= 0 or battle_state.get("player_hp", 0) <= 0:
                break

            turn_number = int(battle_state.get("turn", 1))
            action = action_policy.choose_action(turn=turn_number, battle_state=battle_state)
            requested_skill_id = parse_simulation_skill_action(action)
            if action not in actions_used and requested_skill_id is None:
                action = SIM_ACTION_NORMAL_ATTACK

            if action == SIM_ACTION_NORMAL_ATTACK:
                if battle_state.get("player_goes_first", True):
                    process_player_attack_side_turn(
                        player_local,
                        mob_local,
                        battle_state,
                        lang=cfg.lang,
                    )
                    actions_used[SIM_ACTION_NORMAL_ATTACK] += 1
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
                    battle_state["turn"] = int(battle_state.get("turn", 0)) + 1
            elif action == SIM_ACTION_GUARD_FALLBACK:
                apply_timeout_fallback_guard(battle_state, lang=cfg.lang)
                actions_used[SIM_ACTION_GUARD_FALLBACK] += 1
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
                can_use = bool(skill_def) and skill_level > 0 and local_cd <= 0

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
                            battle_state.setdefault("skills_used", []).append(requested_skill_id)
                            simulation_cooldowns[requested_skill_id] = int(skill_def.get("cooldown", 0))
                        else:
                            process_player_attack_side_turn(player_local, mob_local, battle_state, lang=cfg.lang)
                            actions_used[SIM_ACTION_NORMAL_ATTACK] += 1
                    else:
                        process_player_attack_side_turn(player_local, mob_local, battle_state, lang=cfg.lang)
                        actions_used[SIM_ACTION_NORMAL_ATTACK] += 1
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
                                battle_state.setdefault("skills_used", []).append(requested_skill_id)
                                simulation_cooldowns[requested_skill_id] = int(skill_def.get("cooldown", 0))
                            else:
                                process_player_attack_side_turn(player_local, mob_local, battle_state, lang=cfg.lang)
                                actions_used[SIM_ACTION_NORMAL_ATTACK] += 1
                        else:
                            process_player_attack_side_turn(player_local, mob_local, battle_state, lang=cfg.lang)
                            actions_used[SIM_ACTION_NORMAL_ATTACK] += 1
                    battle_state["turn"] = int(battle_state.get("turn", 0)) + 1

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
            skills_used=list(battle_state.get("skills_used", [])),
            damage_dealt=max(0, int(mob_local.get("hp", 0)) - int(battle_state.get("mob_hp", 0))),
            damage_taken=max(0, int(player_local.get("hp", 0)) - int(battle_state.get("player_hp", 0))),
            final_battle_state=copy.deepcopy(battle_state),
            log_tail=list(battle_state.get("log", []))[-6:] if cfg.include_log_tail else [],
        )

    return _run_with_seed(cfg.seed, _run)
