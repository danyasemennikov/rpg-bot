from __future__ import annotations

import copy

from game.combat_identity import (
    advance_affected_side,
    evaluate_action,
    hit_chance,
    legal_actions,
    mitigation_fraction,
)


def actor(**overrides):
    value = {
        "rules_version": "character_builds_combat_identity_v1",
        "actor_id": 1,
        "name": "Hero",
        "level": 10,
        "family": "bow",
        "skill_ranks": {},
        "cooldowns": {},
        "opportunity_index": 0,
        "hp": 500,
        "max_hp": 500,
        "mana": 100,
        "max_mana": 120,
        "strength": 10,
        "agility": 20,
        "intuition": 10,
        "vitality": 10,
        "wisdom": 10,
        "luck": 0,
        "accuracy": 300,
        "evasion": 100,
        "weapon_min": 50,
        "weapon_max": 50,
        "damage_school": "physical",
        "physical_defense": 0,
        "magic_defense": 0,
        "block_chance": 0,
        "magic_power": 0,
        "healing_power": 0,
        "formation": "ranged",
        "effects": [],
    }
    value.update(overrides)
    return value


def enemy(**overrides):
    value = actor(
        actor_id="enemy-1", family="unarmed", skill_ranks={}, hp=1000,
        max_hp=1000, mana=0, max_mana=0, weapon_min=10, weapon_max=10,
        accuracy=100, evasion=100, formation="front",
    )
    value.update(overrides)
    return value


def direct_event(result):
    return next(event for event in result["events"] if event["kind"] == "direct")


def test_accuracy_and_dynamic_mitigation_boundaries():
    assert hit_chance(actor(accuracy=0), enemy(evasion=1000)) == 50
    assert hit_chance(actor(accuracy=1000), enemy(evasion=0)) == 95
    low_level = mitigation_fraction(enemy(physical_defense=200), source_level=1, school="physical")
    high_level = mitigation_fraction(enemy(physical_defense=200), source_level=20, school="physical")
    assert low_level == .55
    assert 0 < high_level < low_level


def test_normal_attack_restores_six_mana_after_a_valid_attempt():
    hero = actor(mana=110)
    result = evaluate_action(hero, [hero], [enemy()], {"kind": "normal"}, rng_seed=3)
    assert result["accepted"] is True
    assert result["actor"]["mana"] == 116
    assert result["actor"]["opportunity_index"] == 1
    assert any(event.get("source") == "normal" and event["amount"] == 6 for event in result["events"])


def test_universal_power_strike_uses_the_shared_damage_evaluator():
    hero = actor(family="tome", skill_ranks={})
    result = evaluate_action(
        hero, [hero], [enemy()], {"kind": "skill", "skill_id": "power_strike"},
        rng_seed=3,
    )
    assert result["accepted"] is True
    assert direct_event(result)["skill_id"] == "power_strike"
    assert result["actor"]["mana"] < hero["mana"]


def test_target_lost_fallback_is_cost_and_cooldown_free_guard():
    hero = actor(family="magic_staff", skill_ranks={"fireball": 1}, mana=50)
    result = evaluate_action(
        hero, [hero], [enemy(hp=0, dead=True)],
        {"kind": "skill", "skill_id": "fireball", "target_id": "enemy-1"},
        rng_seed=2,
    )
    assert result["accepted"] is True
    assert result["fallback"] == "guard"
    assert result["actor"]["mana"] == 50
    assert "fireball" not in result["actor"]["cooldowns"]


def test_ranked_setup_is_consumed_only_after_landed_eligible_action():
    hero = actor(
        family="bow", skill_ranks={"steady_aim": 3},
        effects=[{
            "kind": "aim", "source_id": "1", "skill_id": "steady_aim",
            "duration": 2, "value": .31, "created_side_index": 0,
            "school": None, "raw_tick": None, "metadata": {},
        }],
    )
    with_setup = evaluate_action(hero, [hero], [enemy()], {"kind": "normal"}, rng_seed=3)
    without_setup = evaluate_action(
        actor(family="bow"), [actor(family="bow")], [enemy()],
        {"kind": "normal"}, rng_seed=3,
    )
    assert direct_event(with_setup)["hp_removed"] > direct_event(without_setup)["hp_removed"]
    assert not any(effect["kind"] == "aim" for effect in with_setup["actor"]["effects"])


def test_hunters_mark_increases_own_skill_direct_damage():
    marked = enemy(effects=[{
        "kind": "hunters_mark", "source_id": "1", "skill_id": "hunters_mark",
        "duration": 3, "value": .15, "created_side_index": 0,
        "school": None, "raw_tick": None, "metadata": {},
    }])
    hero = actor(skill_ranks={"quick_shot": 1})
    marked_result = evaluate_action(
        hero, [hero], [marked], {"kind": "skill", "skill_id": "quick_shot"}, rng_seed=3,
    )
    plain_result = evaluate_action(
        hero, [hero], [enemy()], {"kind": "skill", "skill_id": "quick_shot"}, rng_seed=3,
    )
    assert direct_event(marked_result)["hp_removed"] > direct_event(plain_result)["hp_removed"]


def test_ally_dispel_has_no_hit_roll_but_enemy_dispel_does():
    hero = actor(family="tome", skill_ranks={"dispel_script": 1})
    ally = actor(actor_id=2, effects=[{
        "kind": "slow", "source_id": "enemy", "skill_id": "slow",
        "duration": 2, "value": 0, "created_side_index": 0,
        "school": None, "raw_tick": None, "metadata": {},
    }])
    ally_result = evaluate_action(
        hero, [hero, ally], [enemy()],
        {"kind": "skill", "skill_id": "dispel_script", "target_id": 2}, rng_seed=3,
    )
    ally_event = direct_event(ally_result)
    assert ally_event["hit"] is True
    assert ally_event["hit_chance"] is None
    assert ally_event["hit_roll"] is None
    assert ally_event["removed"] == ["slow"]

    foe_result = evaluate_action(
        hero, [hero], [enemy(effects=copy.deepcopy(ally["effects"]))],
        {"kind": "skill", "skill_id": "dispel_script", "target_id": "enemy-1"}, rng_seed=3,
    )
    assert direct_event(foe_result)["hit_roll"] is not None


def test_mixed_school_action_has_one_crit_block_and_barrier_resolution():
    hero = actor(family="tome", skill_ranks={"synthesis": 1}, luck=100)
    foe = enemy(block_chance=40, effects=[{
        "kind": "barrier", "source_id": "enemy-1", "skill_id": "ward",
        "duration": 2, "value": 30, "created_side_index": 0,
        "school": None, "raw_tick": None, "metadata": {},
    }])
    result = evaluate_action(
        hero, [hero], [foe], {"kind": "skill", "skill_id": "synthesis"}, rng_seed=3,
    )
    event = direct_event(result)
    assert isinstance(event["crit"], bool)
    assert len(event["mixed_packets"]) == 2
    assert {packet["school"] for packet in event["mixed_packets"]} == {"magic", "holy"}
    assert "blocked" not in event["mixed_packets"][0]
    assert event["barrier_absorbed"] == 30


def test_lethal_fireball_does_not_attach_burn():
    hero = actor(family="magic_staff", skill_ranks={"fireball": 1}, weapon_min=500, weapon_max=500)
    result = evaluate_action(
        hero, [hero], [enemy(hp=1, max_hp=1)],
        {"kind": "skill", "skill_id": "fireball"}, rng_seed=3,
    )
    defeated = result["opponents"][0]
    assert defeated["hp"] == 0
    assert not any(effect["kind"] == "burn" for effect in defeated["effects"])


def test_periodic_tick_uses_current_ward_and_snapshotted_weakness_not_block():
    foe = enemy(
        hp=1000, block_chance=40,
        effects=[
            {"kind": "ward", "source_id": "enemy-1", "skill_id": "ward", "duration": 2,
             "value": .20, "created_side_index": 0, "school": None, "raw_tick": None, "metadata": {}},
            {"kind": "burn", "source_id": "1", "skill_id": "fireball", "duration": 2,
             "value": 0, "created_side_index": 0, "school": "magic", "raw_tick": 100,
             "metadata": {"source_level": 10, "weakness_snapshot": .20}},
        ],
    )
    ticked = advance_affected_side([foe], side_index=1)
    dot = next(event for event in ticked["events"] if event["kind"] == "dot")
    assert dot["amount"] == 64
    assert ticked["entities"][0]["hp"] == 936


def test_legal_actions_filters_family_and_pvp_allowlist():
    hero = actor(skill_ranks={"quick_shot": 1, "deadeye": 1, "fireball": 1})
    assert "quick_shot" in legal_actions(hero, pvp=True)
    assert "deadeye" not in legal_actions(hero, pvp=True)
    assert "fireball" not in legal_actions(hero, pvp=False)
