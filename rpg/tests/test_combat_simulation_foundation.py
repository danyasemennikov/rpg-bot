from game.combat_simulation import (
    AlwaysAttackPolicy,
    AlwaysGuardFallbackPolicy,
    SIM_ACTION_GUARD_FALLBACK,
    SimulationConfig,
    build_simulation_mob_preset,
    build_simulation_player_preset,
    simulate_single_combat,
)


def test_player_can_beat_weak_mob():
    player = build_simulation_player_preset(hp=130, max_hp=130, weapon_damage=24, strength=16, agility=12)
    mob = build_simulation_mob_preset("forest_wolf")

    result = simulate_single_combat(player, mob, policy=AlwaysAttackPolicy(), config=SimulationConfig(seed=7, max_turns=50))

    assert result.turns > 0
    assert result.winner == "player"
    assert result.mob_dead is True
    assert result.terminated_by_max_turns is False


def test_weak_player_can_lose_to_strong_mob():
    player = build_simulation_player_preset(hp=60, max_hp=60, weapon_damage=8, strength=4, vitality=4)
    mob = build_simulation_mob_preset("stone_golem")

    result = simulate_single_combat(player, mob, policy=AlwaysAttackPolicy(), config=SimulationConfig(seed=2, max_turns=50))

    assert result.winner == "mob"
    assert result.player_dead is True


def test_deterministic_same_seed_same_summary():
    player = build_simulation_player_preset()
    mob = build_simulation_mob_preset("forest_boar")
    config = SimulationConfig(seed=123, max_turns=40)

    r1 = simulate_single_combat(player, mob, policy=AlwaysAttackPolicy(), config=config)
    r2 = simulate_single_combat(player, mob, policy=AlwaysAttackPolicy(), config=config)

    summary1 = (r1.winner, r1.turns, r1.player_hp_remaining, r1.mob_hp_remaining, r1.actions_used)
    summary2 = (r2.winner, r2.turns, r2.player_hp_remaining, r2.mob_hp_remaining, r2.actions_used)
    assert summary1 == summary2


def test_max_turn_safety_terminates():
    player = build_simulation_player_preset(hp=500, max_hp=500, weapon_damage=1, strength=1)
    mob = build_simulation_mob_preset("stone_golem")

    result = simulate_single_combat(player, mob, policy=AlwaysAttackPolicy(), config=SimulationConfig(seed=11, max_turns=2))

    assert result.terminated_by_max_turns is True
    assert result.turns == 2
    assert result.winner == "none"


def test_guard_policy_runs_and_records_usage():
    player = build_simulation_player_preset(hp=120, max_hp=120, vitality=12)
    mob = build_simulation_mob_preset("forest_wolf")

    result = simulate_single_combat(player, mob, policy=AlwaysGuardFallbackPolicy(), config=SimulationConfig(seed=3, max_turns=5))

    assert result.actions_used[SIM_ACTION_GUARD_FALLBACK] > 0
    assert isinstance(result.log_tail, list)


def test_no_reward_fields_and_no_telegram_context_required():
    player = build_simulation_player_preset()
    mob = build_simulation_mob_preset("forest_boar")

    result = simulate_single_combat(player, mob, policy=AlwaysAttackPolicy(), config=SimulationConfig(seed=5, max_turns=30))

    assert not hasattr(result, "exp")
    assert not hasattr(result, "gold")
    assert not hasattr(result, "loot")
    assert isinstance(result.final_battle_state, dict)


def test_enemy_first_kill_before_player_attack_does_not_count_normal_attack():
    player = build_simulation_player_preset(hp=15, max_hp=15, vitality=1, agility=1, luck=1, weapon_damage=5)
    mob = build_simulation_mob_preset("stone_golem")

    result = simulate_single_combat(player, mob, policy=AlwaysAttackPolicy(), config=SimulationConfig(seed=9, max_turns=10))

    assert result.winner == "mob"
    assert result.player_dead is True
    assert result.final_battle_state.get("player_goes_first") is False
    assert result.actions_used["normal_attack"] == 0
