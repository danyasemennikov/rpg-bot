from __future__ import annotations

from database import get_connection
from game.build_contract import FAMILIES, SKILL_SPECS
from game.build_progression import migrate_character_builds_v1
from game.i18n import get_skill_desc, get_skill_name
from handlers.build import (
    _KIND_LABELS,
    _SCHOOL_LABELS,
    _TARGET_LABELS,
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


def test_corrected_skill_descriptions_preserve_canonical_semantics_in_every_locale():
    required_fragments = {
        "en": {
            "power_strike": ("1.25P", "equipped weapon"),
            "counter": ("PvE", "0.40P", "Ward", "Parry"),
            "envenom_blades": ("normal attack", "0.2875P", "3 ticks"),
            "shadow_chain": ("1.615P", "0.80P", "+40", "1 opportunity"),
            "absolute_zero": ("selected active target", "Slow", "Chilled"),
            "resurrection": ("exactly 0.80H", "once per encounter"),
            "executioners_focus": ("+25%", "3 percentage points"),
            "masters_sequence": ("2.05P", "0.55P", "25% Ward"),
        },
        "ru": {
            "power_strike": ("1,25P", "экипированного оружия"),
            "counter": ("PvE", "0,40P", "Защита", "Парирование"),
            "envenom_blades": ("обычную атаку", "0,2875P", "3 тика"),
            "shadow_chain": ("1,615P", "0,80P", "+40", "1 возможность"),
            "absolute_zero": ("выбранной активной цели", "Замедление", "Охлаждение"),
            "resurrection": ("ровно в 0,80H", "один раз за бой"),
            "executioners_focus": ("+25%", "+3 п.п."),
            "masters_sequence": ("2,05P", "0,55P", "Защиту 25%"),
        },
        "es": {
            "power_strike": ("1,25P", "arma equipada"),
            "counter": ("PvE", "0,40P", "Guardia", "Parada"),
            "envenom_blades": ("ataque normal", "0,2875P", "3 pulsos"),
            "shadow_chain": ("1,615P", "0,80P", "+40", "1 oportunidad"),
            "absolute_zero": ("objetivo activo seleccionado", "Ralentización", "Enfriado"),
            "resurrection": ("exactamente en 0,80H", "una vez por encuentro"),
            "executioners_focus": ("+25%", "+3 puntos porcentuales"),
            "masters_sequence": ("2,05P", "0,55P", "Guarda del 25%"),
        },
    }
    for lang, skills in required_fragments.items():
        for skill_id, fragments in skills.items():
            description = get_skill_desc(skill_id, lang)
            missing = [fragment for fragment in fragments if fragment not in description]
            assert not missing, (lang, skill_id, missing, description)


def test_every_frozen_skill_preview_localizes_structured_contract_fields():
    migrate_character_builds_v1()
    assert set(_TARGET_LABELS["en"]) == {spec.target for spec in SKILL_SPECS.values()}
    assert set(_SCHOOL_LABELS["en"]) == {spec.school or "support" for spec in SKILL_SPECS.values()}
    assert set(_KIND_LABELS["en"]) == {spec.kind for spec in SKILL_SPECS.values()}

    for lang in ("ru", "en", "es"):
        for skill_id, spec in SKILL_SPECS.items():
            text, markup = build_skill_view(1, skill_id, lang)
            assert "[" not in text
            assert get_skill_desc(skill_id, lang) in text
            assert "parameters:" not in text and "параметры:" not in text and "parámetros:" not in text
            assert f"<b>{spec.target}</b>" not in text
            if lang != "en":
                assert f"<b>{spec.school or 'support'}</b>" not in text
                assert spec.description not in text
            if spec.power:
                ranked = spec.power
                formatted = f"{ranked:.4f}".rstrip("0").rstrip(".").removeprefix("0") + "P"
                assert formatted in text
            assert all(
                callback and len(callback.encode("utf-8")) <= 64
                for callback in _callbacks(markup)
            )


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
        assert "1.365P" in views[3][0]
        assert "PvP" in views[3][0]
        if lang != "en":
            assert all(f"· {family}" not in views[4][0] for family in FAMILIES)


def test_cleanse_and_aura_render_truthful_ranked_semantics_in_every_locale():
    migrate_character_builds_v1()
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO weapon_mastery
        (telegram_id, weapon_id, level, exp, skill_points, model_version)
        VALUES (1, 'holy_rod', 4, 0, 3, 1)"""
    )
    conn.execute(
        """INSERT OR REPLACE INTO player_skills (telegram_id, skill_id, level)
        VALUES (1, 'aura_of_resolve', 1)"""
    )
    conn.commit()
    conn.close()

    expected = {
        'en': {
            'target': 'one ally', 'cleanse': ('Poison', 'Bleed', 'Burn', 'Weakness', 'does not heal'),
            'aura': ('20%', '2 opportunities', 'Interception'), 'rank': 'Rank effect 2', 'ward': 'Ward',
        },
        'ru': {
            'target': 'один союзник', 'cleanse': ('Яд', 'Кровотечение', 'Ожог', 'Слабость', 'Не лечит'),
            'aura': ('20%', '2 возможности', 'Перехват'), 'rank': 'Эффект ранга 2', 'ward': 'Защита',
        },
        'es': {
            'target': 'un aliado', 'cleanse': ('Veneno', 'Sangrado', 'Quemadura', 'Debilidad', 'No cura'),
            'aura': ('20%', '2 oportunidades', 'Intercepción'), 'rank': 'Efecto del rango 2', 'ward': 'Guardia',
        },
    }
    for lang, copy in expected.items():
        cleanse, _ = build_skill_view(1, 'cleanse', lang)
        aura, _ = build_skill_view(1, 'aura_of_resolve', lang)
        assert f"<b>{copy['target']}</b>" in cleanse
        assert '<b>10</b>' in cleanse and '<b>3</b>' in cleanse
        assert all(fragment in cleanse for fragment in copy['cleanse'])
        assert f"<b>{copy['target']}</b>" in aura
        assert '<b>14</b>' in aura and '<b>4</b>' in aura
        assert all(fragment in aura for fragment in copy['aura'])
        assert copy['rank'] in aura
        assert f"{copy['ward']}: 23%" in aura


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
