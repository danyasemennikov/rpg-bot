"""Production route evidence for Character Builds V1 language parity."""

from __future__ import annotations

import asyncio
from html import escape
import re

import pytest

from database import get_connection, get_player
from game.build_contract import legal_family_budget
from game.build_progression import migrate_character_builds_v1
from game.i18n import get_skill_name
from game.pve_live import reset_solo_pve_runtime_store
from game.weapon_mastery import get_mastery
from handlers.build import build_command, handle_build_buttons, handle_legacy_build_button
from tests.test_character_builds_v1_journeys import ProductionJourney, _callbacks


LANGUAGE_COPY = {
    "en": {
        "title": "Character Build", "migration": "prior skill points were refunded",
        "target": "one ally", "school": "support", "normal": "Normal attack",
        "stale": "That build action is stale", "old": "This old button cannot mutate V1",
    },
    "ru": {
        "title": "Билд персонажа", "migration": "Прежние очки навыков возвращены",
        "target": "один союзник", "school": "поддержка", "normal": "Обычная атака",
        "stale": "Действие устарело", "old": "Старая кнопка не меняет V1",
    },
    "es": {
        "title": "Configuración del personaje", "migration": "puntos de habilidad anteriores se devolvieron",
        "target": "un aliado", "school": "apoyo", "normal": "Ataque normal",
        "stale": "La acción caducó", "old": "El botón antiguo no puede cambiar V1",
    },
}


def _button_texts(markup: object | None) -> list[str]:
    if not markup or not hasattr(markup, "inline_keyboard"):
        return []
    return [str(button.text) for row in markup.inline_keyboard for button in row]


def _rows(sql: str, args: tuple = ()) -> list[dict]:
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute(sql, args)]
    finally:
        conn.close()


async def _run_language_journey(lang: str, player_id: int) -> None:
    copy = LANGUAGE_COPY[lang]
    name = "<A&B> LongHero123"
    journey = ProductionJourney(player_id, lang=lang)
    await journey.register(primary="wisdom", name=name)

    # Registration renders the current journal and therefore initializes V1.
    # Recreate the persisted pre-activation shape so this journey exercises the
    # real bulk migration and its one-shot user notice.
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE players SET build_migration_version=0, build_notice_pending=0 WHERE telegram_id=?",
            (player_id,),
        )
        conn.execute("DELETE FROM player_build_notices WHERE player_id=?", (player_id,))
        conn.execute(
            "INSERT OR REPLACE INTO player_skills (telegram_id, skill_id, level) VALUES (?, 'heal', 1)",
            (player_id,),
        )
        conn.commit()
    finally:
        conn.close()

    reset_solo_pve_runtime_store()
    migration = migrate_character_builds_v1()
    assert migration["status"] == "active"
    route_start = len(journey.messages)

    await journey.text("/build", build_command)
    build_text = journey.messages[-1][0]
    assert copy["title"] in build_text
    assert copy["migration"] in build_text
    assert dict(get_player(player_id))["build_notice_pending"] == 0

    await journey.buy_and_equip_field_weapon("holy_staff")
    before_learning = len(journey.messages)
    receipt = await journey.learn("holy_staff", "heal")
    learning_messages = journey.messages[before_learning:]
    preview = next(text for text, _ in learning_messages if copy["target"] in text)
    assert get_skill_name("heal", lang) in preview
    assert copy["school"] in preview
    assert "1.00H" in preview
    assert "holy_staff" not in preview and "Ally" not in preview
    assert receipt["rank"] == 1

    conn = get_connection()
    try:
        conn.execute("UPDATE players SET hp=max_hp-20 WHERE telegram_id=?", (player_id,))
        conn.commit()
    finally:
        conn.close()
    await journey.travel("westwild_n1")
    before_combat = len(journey.messages)
    fight = await journey.fight(
        "westwild_rabbit",
        opening=(("skill", "heal"),),
    )
    combat_messages = journey.messages[before_combat:]
    target_buttons = [
        label
        for _, markup in combat_messages
        for label in _button_texts(markup)
        if get_skill_name("heal", lang) in label
    ]
    assert any(name in label for label in target_buttons)
    combat_text = "\n".join(text for text, _ in combat_messages)
    assert escape(name) in combat_text
    assert copy["normal"] in combat_text
    assert any(
        event.get("kind") == "heal" and event.get("amount", 0) > 0
        for action in fight["actions"] for event in action["events"]
    )

    await journey.travel("capital_city")
    await journey.callback("bv_reset_holy_staff", handle_build_buttons)
    reset_callback = next(
        value for value in _callbacks(journey.messages[-1][1])
        if value.startswith("bv_reset_apply_")
    )
    await journey.callback(reset_callback, handle_build_buttons)
    assert not _rows(
        "SELECT 1 FROM player_skills WHERE telegram_id=? AND skill_id='heal'",
        (player_id,),
    )
    mastery = get_mastery(player_id, "holy_staff")
    assert mastery["skill_points"] == legal_family_budget(mastery["level"])

    stale_query = await journey.callback("bv_reset_apply_missing", handle_build_buttons)
    assert copy["stale"] in str(stale_query.answer.await_args.args[0])
    legacy_query = await journey.callback("sk_retired", handle_legacy_build_button)
    assert copy["old"] in str(legacy_query.answer.await_args.args[0])

    route_messages = journey.messages[route_start:]
    rendered = "\n".join(text for text, _ in route_messages)
    assert not re.search(r"\[[a-z0-9_.]+\]", rendered)
    assert all(len(text) <= 4096 for text, _ in route_messages)
    assert all(
        len(callback.encode("utf-8")) <= 64
        for _, markup in route_messages for callback in _callbacks(markup)
    )
    assert not any(
        raw_id in text
        for text, _ in route_messages
        for raw_id in ("holy_staff", "basic_attack", "wrong_family", "safe_hub_required")
    )
    if lang != "ru":
        cyrillic = re.search(r"[А-Яа-яЁё]", rendered)
        assert not cyrillic, rendered[max(0, cyrillic.start() - 120):cyrillic.start() + 200]
    if lang != "en":
        assert "Character Build" not in rendered
        assert "Normal attack" not in rendered
        assert "one ally" not in rendered


@pytest.mark.parametrize("lang,player_id", (("ru", 9101), ("en", 9102), ("es", 9103)))
def test_build_and_combat_production_routes_are_complete_in_each_language(
    lang: str, player_id: int,
) -> None:
    asyncio.run(_run_language_journey(lang, player_id))
