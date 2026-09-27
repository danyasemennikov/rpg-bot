"""Shared atomic character XP/gold progression used by settlement and RAV1."""

from __future__ import annotations

from game.balance import exp_to_next_level


def apply_progression_reward(conn, player_id: int, exp_gain: int, gold_gain: int,
                             failure_hook=None) -> dict:
    row = conn.execute(
        """SELECT level, exp, gold, stat_points, attribute_budget, build_revision
           FROM players WHERE telegram_id=?""", (int(player_id),)
    ).fetchone()
    if not row:
        raise RuntimeError(f"reward_player_missing:{player_id}")
    old_level = int(row["level"])
    level = old_level
    exp_value = int(row["exp"]) + max(0, int(exp_gain))
    while exp_value >= exp_to_next_level(level):
        exp_value -= exp_to_next_level(level)
        level += 1
    levels_gained = level - old_level
    earned_points = levels_gained * 3
    stat_points = int(row["stat_points"]) + earned_points
    attribute_budget = (
        None if row["attribute_budget"] is None
        else int(row["attribute_budget"]) + earned_points
    )
    gold = int(row["gold"]) + int(gold_gain)
    conn.execute(
        """UPDATE players SET level=?, exp=?, stat_points=?, attribute_budget=?,
           build_revision=build_revision+?, gold=? WHERE telegram_id=?""",
        (level, exp_value, stat_points, attribute_budget, int(levels_gained > 0), gold, int(player_id)),
    )
    if failure_hook:
        failure_hook("after_xp_update")
        failure_hook("after_gold_update")
    return {
        "level_before": old_level, "level_after": level, "exp_after": exp_value,
        "gold_after": gold, "leveled_up": level > old_level,
        "stat_points_awarded": earned_points,
    }

