from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Callable

from game.combat import (
    apply_timeout_fallback_guard,
    init_battle,
    process_enemy_side_turn,
    process_turn,
)
from game.mobs import get_mob


SIM_ACTION_NORMAL_ATTACK = "normal_attack"
SIM_ACTION_GUARD_FALLBACK = "guard_fallback"


@dataclass
class SimulationConfig:
    seed: int = 1
    max_turns: int = 50
    lang: str = "ru"
    include_log_tail: bool = True


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


class ScriptedActionPolicy:
    def __init__(self, actions: list[str]):
        self.actions = list(actions)

    def choose_action(self, *, turn: int, battle_state: dict) -> str:
        if 1 <= turn <= len(self.actions):
            return self.actions[turn - 1]
        return SIM_ACTION_NORMAL_ATTACK


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

    def _run() -> SimulationResult:
        terminated_by_max_turns = False
        executed_turns = 0

        while executed_turns < cfg.max_turns:
            if battle_state.get("mob_hp", 0) <= 0 or battle_state.get("player_hp", 0) <= 0:
                break

            turn_number = int(battle_state.get("turn", 1))
            action = action_policy.choose_action(turn=turn_number, battle_state=battle_state)
            if action not in actions_used:
                action = SIM_ACTION_NORMAL_ATTACK
            actions_used[action] += 1

            if action == SIM_ACTION_NORMAL_ATTACK:
                process_turn(player_local, mob_local, battle_state, lang=cfg.lang)
            elif action == SIM_ACTION_GUARD_FALLBACK:
                apply_timeout_fallback_guard(battle_state, lang=cfg.lang)
                process_enemy_side_turn(
                    mob_local,
                    player_local,
                    battle_state,
                    lang=cfg.lang,
                    increment_turn=True,
                    tick_player_post_action_buffs=True,
                    tick_timed_trigger_buffs=True,
                )

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
