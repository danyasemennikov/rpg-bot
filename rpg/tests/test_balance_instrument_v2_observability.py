from pathlib import Path

from game.combat_simulation import (
    SIM_ACTION_NORMAL_ATTACK,
    ScriptedActionPolicy,
    SimulationConfig,
    build_simulation_mob_preset,
    build_simulation_player_preset,
    _safe_current_turn_log_events,
    make_simulation_skill_action,
    simulate_single_combat,
)
from game.combat_simulation_matrix import RouteStageMatrixConfig, run_route_stage_simulation_matrix
from game.combat_simulation_report import (
    _build_observability_preview_rows,
    build_balance_report_mode,
    build_default_alpha_simulation_report_v2_data,
    render_alpha_simulation_report_v2_markdown,
)

DOCS_ROOT = Path(__file__).resolve().parents[1] / "docs"
REPORT_PATH = DOCS_ROOT / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md"
STATE_PATH = DOCS_ROOT / "PROJECT_STATE_CURRENT.md"
FOUNDATION_PATH = DOCS_ROOT / "BALANCE_FOUNDATION_ALPHA_TO_RELEASE.md"


def _basic_player_and_mob():
    return build_simulation_player_preset(), build_simulation_mob_preset("forest_wolf")


def test_default_simulation_keeps_trace_lightweight_and_adds_observability():
    player, mob = _basic_player_and_mob()
    result = simulate_single_combat(player, mob, config=SimulationConfig(seed=7, max_turns=20))
    repeat = simulate_single_combat(player, mob, config=SimulationConfig(seed=7, max_turns=20))

    assert result.winner == repeat.winner
    assert result.turns == repeat.turns
    assert result.damage_dealt == repeat.damage_dealt
    assert result.turn_trace == []
    assert result.observability["damage_dealt"] == result.damage_dealt
    assert result.observability["damage_taken"] == result.damage_taken
    assert result.observability["end_reason"] in {"player_win", "player_death", "timeout", "no_winner"}


def test_turn_trace_enabled_is_capped_and_does_not_mutate_inputs():
    player, mob = _basic_player_and_mob()
    original_player = dict(player)
    original_mob = dict(mob)
    result = simulate_single_combat(
        player,
        mob,
        config=SimulationConfig(seed=3, max_turns=10, include_turn_trace=True, max_trace_turns=2),
    )

    assert 0 < len(result.turn_trace) <= 2
    row = result.turn_trace[0]
    for key in (
        "turn",
        "chosen_action",
        "resolved_action",
        "requested_skill_id",
        "player_before",
        "mob_before",
        "player_after_player_action",
        "mob_after_player_action",
        "player_after_enemy_action",
        "mob_after_enemy_action",
        "player_hp_delta",
        "player_mana_delta",
        "mob_hp_delta",
        "cooldowns_after",
        "log_events",
    ):
        assert key in row
    assert {"hp", "mana"}.issubset(row["player_before"])
    assert "hp" in row["mob_before"]
    assert player == original_player
    assert mob == original_mob




def test_current_turn_log_helper_handles_replaced_or_capped_logs():
    assert _safe_current_turn_log_events(["old1", "old2", "old3"], ["new current event"]) == ["new current event"]
    assert _safe_current_turn_log_events(["old1"], ["old1", "new event"]) == ["new event"]
    assert _safe_current_turn_log_events([], ["a|b\nnext"]) == ["a\\|b next"]


def test_multi_turn_trace_keeps_current_turn_log_events_after_first_turn():
    player = build_simulation_player_preset(weapon_damage=1, strength=1, agility=1, hp=500, max_hp=500)
    mob = build_simulation_mob_preset("forest_boar")
    mob.update({"hp": 200, "damage": 1})

    result = simulate_single_combat(
        player,
        mob,
        config=SimulationConfig(seed=1, max_turns=5, include_turn_trace=True, max_trace_turns=5),
    )

    assert len(result.turn_trace) >= 3
    assert any(row["log_events"] for row in result.turn_trace[1:])


def test_unavailable_skill_trace_resolves_to_actual_fallback_normal_attack():
    player, mob = _basic_player_and_mob()
    requested = make_simulation_skill_action("power_strike")
    result = simulate_single_combat(
        player,
        mob,
        policy=ScriptedActionPolicy([requested]),
        config=SimulationConfig(seed=19, max_turns=3, include_turn_trace=True, max_trace_turns=1),
    )

    row = result.turn_trace[0]
    assert row["chosen_action"].startswith("skill:")
    assert row["requested_skill_id"] == "power_strike"
    assert row["resolved_action"] == SIM_ACTION_NORMAL_ATTACK
    assert result.actions_used[SIM_ACTION_NORMAL_ATTACK] >= 1


def test_observability_metrics_are_stable_and_percentages_are_fractions():
    player, mob = _basic_player_and_mob()
    result = simulate_single_combat(player, mob, config=SimulationConfig(seed=11, max_turns=20))
    obs = result.observability
    for key in (
        "damage_dealt",
        "damage_taken",
        "damage_dealt_per_turn",
        "damage_taken_per_turn",
        "player_hp_remaining_pct",
        "player_mana_remaining_pct",
        "mob_hp_removed_pct",
        "mana_spent",
        "skills_used_count",
        "normal_attacks_used",
        "guard_used",
        "end_reason",
    ):
        assert key in obs
    for pct_key in ("player_hp_remaining_pct", "player_mana_remaining_pct", "mob_hp_removed_pct"):
        assert 0.0 <= obs[pct_key] <= 1.0


def test_matrix_can_include_observability_and_trace_without_bloating_default():
    default_matrix = run_route_stage_simulation_matrix(
        RouteStageMatrixConfig(
            route_ids=("route_westwild",),
            stages=("soft_entry",),
            archetype_ids=("guardian_shield_1h",),
            seeds=(1,),
            max_samples_per_route_stage=1,
        )
    )
    assert "observability" in default_matrix["runs"][0]
    assert "turn_trace" not in default_matrix["runs"][0]

    traced_matrix = run_route_stage_simulation_matrix(
        RouteStageMatrixConfig(
            route_ids=("route_westwild",),
            stages=("soft_entry",),
            archetype_ids=("guardian_shield_1h",),
            seeds=(1,),
            max_samples_per_route_stage=1,
            include_turn_trace=True,
            max_trace_turns=3,
        )
    )
    assert traced_matrix["runs"][0]["observability"]
    assert 0 < len(traced_matrix["runs"][0]["turn_trace"]) <= 3


def test_report_modes_are_explicit_and_expanded_mode_available():
    compact = build_balance_report_mode("compact_regression")
    expanded = build_balance_report_mode("expanded_balance")
    assert compact.name == "compact_regression"
    assert compact.matrix_config.include_turn_trace is True
    assert compact.matrix_config.max_trace_turns < expanded.matrix_config.max_trace_turns
    assert len(expanded.matrix_config.seeds) > len(compact.matrix_config.seeds)



def test_observability_preview_selection_prioritizes_suspicious_and_late_stage_balance():
    report = build_default_alpha_simulation_report_v2_data()
    rows = _build_observability_preview_rows(report)

    assert 0 < len(rows) <= 8
    assert any(
        row.get("route_id") == "route_sunscar"
        and row.get("stage") == "route_exam"
        and row.get("archetype_id") == "pure_support_solo_overlay"
        and row.get("winner") == "mob"
        for row in rows
    )
    assert len({row.get("route_id") for row in rows}) > 1
    assert any(row.get("stage") in {"build_testing", "route_exam"} for row in rows[1:])
    assert not all(
        row.get("route_id") == "route_westwild" and row.get("stage") == "soft_entry"
        for row in rows[1:]
    )


def test_rendered_and_checked_in_report_observability_sections_are_capped_and_preserved():
    report = build_default_alpha_simulation_report_v2_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    checked_in = REPORT_PATH.read_text(encoding="utf-8")
    for content in (md, checked_in):
        assert "## Balance Instrument V2 Observability Preview" in content
        assert "## PR12 First Tuning Pass Summary" in content
        assert "## PR13 Targeted Tuning Candidates" in content
        assert "## PR13 Targeted Alpha Tuning Summary" in content
        assert "## PR14 Target Expectation Calibration Summary" in content
        assert "## PR15 Actionable Late-Stage Tuning Summary" in content
        assert "Pack / Group Simulation Preview" in content
        assert "policy_failure_guard_loop count: 0" in content
        assert "No giant JSON dumps" not in content
    assert checked_in.count("Case ") <= 3
    assert "route_sunscar | route_exam | pure_support_solo_overlay" in md
    assert "route_sunscar | route_exam | pure_support_solo_overlay" in checked_in


def test_pr15_value_honesty_stays_stable_in_checked_in_report():
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert "Raw/global overclean candidates still visible: 87." in content
    assert "Actionable overclean candidates after PR15: 43." in content
    assert "Early-stage target artifacts remain separated: 44." in content
    assert "route_sunscar / route_exam / pure_support_solo_overlay player_death" in content


def test_non_goal_wording_in_report_and_docs():
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in (REPORT_PATH, STATE_PATH, FOUNDATION_PATH)
    )
    assert "no live gameplay/runtime systems were changed" in combined.lower()
    assert "No Combat Core rewrite" in combined
    assert "No live pack/group runtime combat" in combined
    assert "not a final balance" in combined.lower() or "does not claim final balance" in combined.lower()
