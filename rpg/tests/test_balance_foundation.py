from pathlib import Path

import pytest

from game.balance_foundation import (
    BALANCE_MACRO_BANDS,
    MAX_RELEASE_LEVEL,
    TTK_TARGET_BANDS,
    build_simulation_stage_progression_context,
    resolve_simulation_stage_player_level,
    resolve_gear_tier_for_level,
    resolve_macro_band_for_level,
)


def test_release_cap_is_100():
    assert MAX_RELEASE_LEVEL == 100


def test_gear_tier_resolution_boundaries():
    assert resolve_gear_tier_for_level(1) == "T1"
    assert resolve_gear_tier_for_level(10) == "T1"
    assert resolve_gear_tier_for_level(11) == "T2"
    assert resolve_gear_tier_for_level(100) == "T10"


def test_invalid_release_levels_raise():
    with pytest.raises(ValueError):
        resolve_gear_tier_for_level(0)
    with pytest.raises(ValueError):
        resolve_gear_tier_for_level(101)


def test_macro_band_resolution_stable_known_values():
    assert resolve_macro_band_for_level(1) == "bootstrap"
    assert resolve_macro_band_for_level(35) == "specialization"
    assert resolve_macro_band_for_level(90) == "late game"
    assert resolve_macro_band_for_level(100) == "apex"
    assert len(BALANCE_MACRO_BANDS) == 7


def test_ttk_targets_include_normal_pressure_elite():
    assert "normal" in TTK_TARGET_BANDS
    assert "pressure" in TTK_TARGET_BANDS
    assert "elite_solo" in TTK_TARGET_BANDS


def test_balance_foundation_doc_exists_and_contains_required_tokens():
    doc = Path(__file__).resolve().parents[1] / "docs" / "BALANCE_FOUNDATION_ALPHA_TO_RELEASE.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8").lower()

    required_tokens = [
        "max release level",
        "t1",
        "t10",
        "hp",
        "damage",
        "ttk",
        "item level budget",
        "slot budget",
        "rarity",
        "enhancement",
        "modifier pools",
        "simulation gear presets",
        "encounter-level scaling",
        "pr8",
        "pr9",
        "pr10",
        "pr11",
        "pr12",
        "non-goals",
    ]

    for token in required_tokens:
        assert token in text


def test_simulation_stage_player_level_assumptions():
    assert resolve_simulation_stage_player_level("soft_entry") == 10
    assert resolve_simulation_stage_player_level("identity_visible") == 35
    assert resolve_simulation_stage_player_level("build_testing") == 70
    assert resolve_simulation_stage_player_level("route_exam") == 95
    assert resolve_simulation_stage_player_level("unknown_stage") is None


def test_simulation_stage_progression_context_route_exam():
    ctx = build_simulation_stage_progression_context("route_exam")
    assert ctx["assumed_player_level"] == 95
    assert ctx["macro_band"] == "apex"
    assert ctx["gear_tier"] == "T10"
    assert ctx["gear_rarity_assumption"] is None
    assert ctx["enhancement_assumption"] is None
    assert ctx["assumption_status"] is None


def test_project_state_current_pr11_header_and_future_prs_not_implemented():
    doc = Path(__file__).resolve().parents[1] / "docs" / "PROJECT_STATE_CURRENT.md"
    text = doc.read_text(encoding="utf-8")

    pr7_heading = "### Balance Foundation Spec & Audit Skeleton (PR7)"
    pr8_heading = "### Progression-aware Simulation Audit (PR8)"
    pr9_heading = "### Equipment Budget Foundation (PR9)"
    pr10_heading = "### Mob Encounter Scaling Foundation (PR10)"
    pr7_detail = "- Balance Foundation Spec & Audit Skeleton is implemented:"
    pr8_detail = "- Progression-aware simulation audit diagnostics are implemented:"
    pr9_detail = "- equipment budget foundation is implemented for simulation/reporting;"
    pr10_detail = "- formula-based mob encounter scaling is implemented for simulation/reporting;"

    assert pr7_heading in text
    assert pr8_heading in text
    assert pr7_detail in text
    assert pr8_detail in text
    assert pr9_heading in text
    assert pr10_heading in text

    assert text.index(pr7_heading) < text.index(pr8_heading)
    assert text.index(pr7_detail) < text.index(pr8_heading)
    assert text.index(pr8_detail) > text.index(pr8_heading)
    assert text.index(pr9_heading) < text.index(pr10_heading)
    assert text.index(pr9_detail) > text.index(pr9_heading)
    assert text.index(pr9_detail) < text.index(pr10_heading)
    assert text.index(pr10_detail) > text.index(pr10_heading)

    lower = text.lower()
    assert "equipment budget foundation (pr9)" in lower
    assert "mob encounter scaling foundation (pr10)" in lower
    assert "pack/group simulation harness (pr11)" in lower
    assert "- no group/pack simulation matrix." not in lower
    assert "pr12 is implemented" not in lower
