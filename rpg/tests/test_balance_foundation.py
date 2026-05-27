from pathlib import Path

import pytest

from game.balance_foundation import (
    BALANCE_MACRO_BANDS,
    MAX_RELEASE_LEVEL,
    TTK_TARGET_BANDS,
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


def test_project_state_current_pr7_header_and_no_future_prs_marked_implemented():
    doc = Path(__file__).resolve().parents[1] / "docs" / "PROJECT_STATE_CURRENT.md"
    text = doc.read_text(encoding="utf-8")

    assert "PR7: Balance Foundation Spec & Audit Skeleton" in text
    assert "Balance Foundation Spec & Audit Skeleton is implemented" in text

    lower = text.lower()
    assert "pr8" not in lower
    assert "pr9" not in lower
    assert "pr10" not in lower
    assert "pr11" not in lower
    assert "pr12" not in lower
