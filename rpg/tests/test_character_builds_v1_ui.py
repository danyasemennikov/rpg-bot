from __future__ import annotations

from database import get_connection
from game.build_contract import FAMILIES, SKILL_SPECS
from game.build_progression import migrate_character_builds_v1
from game.i18n import get_skill_desc, get_skill_name
from handlers.build import (
    build_attributes_view,
    build_family_view,
    build_main_view,
    build_masteries_view,
    build_pvp_view,
    build_skill_view,
)
from handlers.battle import _render_v1_event


def _callbacks(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_all_frozen_skills_have_localized_name_and_description():
    for lang in ("ru", "en", "es"):
        for skill_id in SKILL_SPECS:
            assert get_skill_name(skill_id, lang) != skill_id
            assert get_skill_desc(skill_id, lang)


def test_build_views_are_localized_authoritative_and_callback_safe():
    migrate_character_builds_v1()
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO weapon_mastery
        (telegram_id, weapon_id, level, exp, skill_points, model_version)
        VALUES (1, 'bow', 10, 12, 7, 1)"""
    )
    conn.execute(
        "INSERT OR REPLACE INTO player_skills (telegram_id, skill_id, level) VALUES (1, 'quick_shot', 2)"
    )
    conn.commit()
    conn.close()

    for lang in ("ru", "en", "es"):
        views = [
            build_main_view(1, lang),
            build_masteries_view(1, lang),
            build_family_view(1, "bow", lang),
            build_skill_view(1, "quick_shot", lang),
            build_pvp_view(1, lang),
        ]
        attribute_text, attribute_markup, draft = build_attributes_view(1, lang)
        views.append((attribute_text, attribute_markup))
        assert set(draft) == {"strength", "agility", "intuition", "vitality", "wisdom", "luck"}
        for text, markup in views:
            assert "[" not in text
            assert all(callback and len(callback.encode("utf-8")) <= 64 for callback in _callbacks(markup))
        assert "1.05P" in views[3][0]
        assert "PvP" in views[3][0]


def test_each_family_tree_renders_both_frozen_branches():
    migrate_character_builds_v1()
    conn = get_connection()
    for family in FAMILIES:
        conn.execute(
            """INSERT OR REPLACE INTO weapon_mastery
            (telegram_id, weapon_id, level, exp, skill_points, model_version)
            VALUES (1, ?, 1, 0, 2, 1)""",
            (family,),
        )
    conn.commit()
    conn.close()
    for family in FAMILIES:
        text, markup = build_family_view(1, family, "en")
        assert "A ·" in text and "B ·" in text
        skill_buttons = [value for value in _callbacks(markup) if value.startswith("bv_skill_")]
        assert len(skill_buttons) == 10


def test_structured_battle_events_render_in_all_supported_locales():
    state = {
        "participant_states_v1": {"1": {"actor_id": 1, "name": "Hero"}},
        "enemy_states_v1": [{"unit_id": "enemy-1", "name": "Wolf"}],
    }
    event = {
        "kind": "direct", "actor_id": 1, "target_id": "enemy-1",
        "skill_id": "power_strike", "hit": True, "hp_removed": 17,
        "blocked": True, "barrier_absorbed": 3,
    }
    rendered = [_render_v1_event(event, state, lang) for lang in ("ru", "en", "es")]
    assert all(line and "17" in line and "3" in line for line in rendered)
    assert len(set(rendered)) == 3
