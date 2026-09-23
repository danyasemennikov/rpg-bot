from __future__ import annotations

from pathlib import Path

from game.build_contract import (
    FAMILIES,
    MAX_MASTERY,
    POWER_STRIKE,
    PVP_SKILL_ALLOWLIST,
    RETIRED_SKILL_IDS,
    SKILL_SPECS,
    SKILL_TREES,
    legal_family_budget,
    mastery_exp_needed,
    rank_mana_cost,
    rank_multiplier,
    rank_percent,
    validate_frozen_catalogue,
)


def test_frozen_catalogue_has_exact_family_and_tree_shape():
    assert validate_frozen_catalogue() == ()
    assert len(FAMILIES) == 10
    assert len(SKILL_SPECS) == 100
    assert set(SKILL_TREES) == set(FAMILIES)
    assert all(set(tree) == {"A", "B"} for tree in SKILL_TREES.values())
    assert all(len(branch) == 5 for tree in SKILL_TREES.values() for branch in tree.values())
    assert len({skill for tree in SKILL_TREES.values() for branch in tree.values() for skill in branch}) == 100


def test_frozen_rank_mastery_and_pvp_rules():
    assert [mastery_exp_needed(level) for level in (1, 2, 10, 19, 20)] == [20, 40, 200, 380, 0]
    assert [legal_family_budget(level) for level in (1, 2, 10, MAX_MASTERY)] == [2, 3, 11, 21]
    assert [rank_multiplier(rank) for rank in (1, 2, 3)] == [1.0, 1.15, 1.3]
    assert [rank_percent(.15, rank) for rank in (1, 2, 3)] == [.15, .18, .21]
    assert PVP_SKILL_ALLOWLIST == {"power_strike", "quick_shot", "fireball", "smite"}
    assert POWER_STRIKE.family == "universal"
    assert "meteor" in RETIRED_SKILL_IDS


def test_utility_rank_discount_and_ordinary_costs_are_distinct():
    utility = SKILL_SPECS["dispel_script"]
    ordinary = SKILL_SPECS["fireball"]
    assert [rank_mana_cost(utility, rank) for rank in (1, 2, 3)] == [10, 8, 6]
    assert [rank_mana_cost(ordinary, rank) for rank in (1, 2, 3)] == [ordinary.mana] * 3


def test_delivery_report_indexes_every_skill_and_frozen_g_through_i_area():
    report = (
        Path(__file__).parents[1]
        / "docs"
        / "CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md"
    ).read_text(encoding="utf-8")
    assert all(f"`{skill_id}`" in report for skill_id in SKILL_SPECS)
    assert "Power Strike" in report
    assert all(
        f"| {section} " in report
        for section in (
            "G1", "G2", "G3", "G4", "G5", "G6", "G7",
            "H1", "H2", "H3", "H4",
            "I1", "I2", "I3", "I4",
        )
    )
