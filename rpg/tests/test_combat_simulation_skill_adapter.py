from game.combat_simulation import (
    SimulationConfig,
    ScriptedActionPolicy,
    build_simulation_mob_preset,
    build_simulation_player_preset,
    make_simulation_skill_action,
    simulate_single_combat,
)
from game import combat
from game import combat_simulation


def test_skill_action_executes_and_records_usage():
    player = build_simulation_player_preset(mana=120, max_mana=120)
    mob = build_simulation_mob_preset("forest_boar")
    policy = ScriptedActionPolicy([make_simulation_skill_action("power_strike")])

    result = simulate_single_combat(
        player,
        mob,
        policy=policy,
        config=SimulationConfig(seed=12, max_turns=10, skill_levels={"power_strike": 2}),
    )

    assert result.turns > 0
    assert "power_strike" in result.skills_used
    assert result.actions_used["skill:power_strike"] > 0
    assert result.player_mana_remaining < player["mana"]
    assert not hasattr(result, "exp")
    assert not hasattr(result, "gold")
    assert not hasattr(result, "loot")


def test_simulation_does_not_write_db_cooldown(monkeypatch):
    from game import skill_engine

    def _boom(*args, **kwargs):
        raise AssertionError("db cooldown must not be called")

    monkeypatch.setattr(skill_engine, "set_skill_cooldown", _boom)

    player = build_simulation_player_preset(mana=120, max_mana=120)
    mob = build_simulation_mob_preset("forest_boar")
    result = simulate_single_combat(
        player,
        mob,
        policy=ScriptedActionPolicy([make_simulation_skill_action("power_strike")]),
        config=SimulationConfig(seed=13, max_turns=10, skill_levels={"power_strike": 2}),
    )
    assert result.actions_used["skill:power_strike"] >= 0


def test_simulation_not_dependent_on_live_skill_level(monkeypatch):
    from game import skill_engine

    def _raise(*args, **kwargs):
        raise AssertionError("live get_skill_level should not be used")

    monkeypatch.setattr(skill_engine, "get_skill_level", _raise)

    result = simulate_single_combat(
        build_simulation_player_preset(mana=120, max_mana=120),
        build_simulation_mob_preset("forest_boar"),
        policy=ScriptedActionPolicy([make_simulation_skill_action("power_strike")]),
        config=SimulationConfig(seed=14, max_turns=10, skill_levels={"power_strike": 2}),
    )
    assert result.actions_used["skill:power_strike"] >= 0


def test_local_cooldown_blocks_immediate_recast_and_falls_back():
    result = simulate_single_combat(
        build_simulation_player_preset(mana=200, max_mana=200),
        build_simulation_mob_preset("stone_golem"),
        policy=ScriptedActionPolicy([
            make_simulation_skill_action("power_strike"),
            make_simulation_skill_action("power_strike"),
            "normal_attack",
        ]),
        config=SimulationConfig(seed=15, max_turns=4, skill_levels={"power_strike": 2}),
    )
    assert result.actions_used["skill:power_strike"] == 1
    assert result.actions_used["normal_attack"] >= 1


def test_insufficient_mana_blocks_skill_and_falls_back():
    result = simulate_single_combat(
        build_simulation_player_preset(mana=1, max_mana=1),
        build_simulation_mob_preset("forest_boar"),
        policy=ScriptedActionPolicy([make_simulation_skill_action("power_strike")]),
        config=SimulationConfig(seed=16, max_turns=3, skill_levels={"power_strike": 2}),
    )
    assert result.actions_used["skill:power_strike"] == 0
    assert result.actions_used["normal_attack"] >= 1


def test_enemy_first_death_does_not_count_skill():
    result = simulate_single_combat(
        build_simulation_player_preset(hp=15, max_hp=15, vitality=1, agility=1, luck=1, weapon_damage=5, mana=120, max_mana=120),
        build_simulation_mob_preset("stone_golem"),
        policy=ScriptedActionPolicy([make_simulation_skill_action("power_strike")]),
        config=SimulationConfig(seed=9, max_turns=10, skill_levels={"power_strike": 2}),
    )
    assert result.winner == "mob"
    assert result.player_dead is True
    assert result.actions_used.get("skill:power_strike", 0) == 0
    assert "power_strike" not in result.skills_used


def test_skill_simulation_deterministic_with_seed():
    config = SimulationConfig(seed=25, max_turns=8, skill_levels={"power_strike": 2})
    policy = ScriptedActionPolicy([make_simulation_skill_action("power_strike"), "normal_attack"])
    r1 = simulate_single_combat(build_simulation_player_preset(mana=120, max_mana=120), build_simulation_mob_preset("forest_boar"), policy=policy, config=config)
    r2 = simulate_single_combat(build_simulation_player_preset(mana=120, max_mana=120), build_simulation_mob_preset("forest_boar"), policy=policy, config=config)
    assert (r1.winner, r1.turns, r1.actions_used, r1.skills_used) == (r2.winner, r2.turns, r2.actions_used, r2.skills_used)


def test_player_first_skill_resolves_enemy_side_once(monkeypatch):
    calls = {"enemy_response": 0}
    original = combat.resolve_enemy_response

    def _counted(*args, **kwargs):
        calls["enemy_response"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(combat, "resolve_enemy_response", _counted)

    simulate_single_combat(
        build_simulation_player_preset(mana=120, max_mana=120, agility=50),
        build_simulation_mob_preset("stone_golem"),
        policy=ScriptedActionPolicy([make_simulation_skill_action("power_strike")]),
        config=SimulationConfig(seed=41, max_turns=1, skill_levels={"power_strike": 2}),
    )
    assert calls["enemy_response"] == 1


def test_player_first_steady_aim_not_double_ticked_in_single_exchange():
    result = simulate_single_combat(
        build_simulation_player_preset(mana=120, max_mana=120, agility=50, weapon_profile="bow", weapon_type="ranged"),
        build_simulation_mob_preset("stone_golem"),
        policy=ScriptedActionPolicy([make_simulation_skill_action("steady_aim")]),
        config=SimulationConfig(seed=42, max_turns=1, skill_levels={"steady_aim": 2}),
    )
    assert result.final_battle_state.get("steady_aim_turns", 0) == 1


def test_redirect_path_uses_skill_level_override_in_process_skill_turn(monkeypatch):
    from game import skill_engine

    monkeypatch.setattr(combat, "resolve_target_pattern_id", lambda _skill: "fake_single_redirect")
    monkeypatch.setattr(combat, "get_target_pattern", lambda _pid: {"execution_mode": "single_redirect"})
    monkeypatch.setattr(combat, "select_targets_for_pattern", lambda units, _pattern, active_unit_id=None: [units[0]])

    def _raise(*args, **kwargs):
        raise AssertionError("live get_skill_level should not be read in redirect path")

    monkeypatch.setattr(skill_engine, "get_skill_level", _raise)

    player = build_simulation_player_preset(mana=100, max_mana=100)
    mob = build_simulation_mob_preset("forest_boar")
    battle_state = combat.init_battle(player, mob)
    battle_state["enemy_units"] = [{"unit_id": "u1", "hp": battle_state["mob_hp"], "max_hp": battle_state.get("mob_max_hp", battle_state["mob_hp"]), "mob_effects": [], "dead": False}]
    battle_state["active_enemy_unit_id"] = "u1"

    result = combat.process_skill_turn(
        "disarm",
        player,
        mob,
        battle_state,
        user_id=0,
        lang="ru",
        include_enemy_response=False,
        skill_level_override=2,
        cooldown_override=0,
        commit_cooldown_to_db=False,
    )
    assert result["success"] is True


def test_redirect_path_no_db_cooldown_write_when_disabled(monkeypatch):
    from game import skill_engine

    monkeypatch.setattr(combat, "resolve_target_pattern_id", lambda _skill: "fake_single_redirect")
    monkeypatch.setattr(combat, "get_target_pattern", lambda _pid: {"execution_mode": "single_redirect"})
    monkeypatch.setattr(combat, "select_targets_for_pattern", lambda units, _pattern, active_unit_id=None: [units[0]])

    def _boom(*args, **kwargs):
        raise AssertionError("set_skill_cooldown must not be called in redirect path")

    monkeypatch.setattr(skill_engine, "set_skill_cooldown", _boom)

    player = build_simulation_player_preset(mana=100, max_mana=100)
    mob = build_simulation_mob_preset("forest_boar")
    battle_state = combat.init_battle(player, mob)
    battle_state["enemy_units"] = [{"unit_id": "u1", "hp": battle_state["mob_hp"], "max_hp": battle_state.get("mob_max_hp", battle_state["mob_hp"]), "mob_effects": [], "dead": False}]
    battle_state["active_enemy_unit_id"] = "u1"

    result = combat.process_skill_turn(
        "disarm",
        player,
        mob,
        battle_state,
        user_id=0,
        lang="ru",
        include_enemy_response=False,
        skill_level_override=2,
        cooldown_override=0,
        commit_cooldown_to_db=False,
    )
    assert result["success"] is True
