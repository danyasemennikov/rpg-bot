import asyncio
import sqlite3
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from database import (
    GATHERING_PROFESSION_KEYS,
    create_player,
    ensure_player_gathering_professions,
    get_connection,
    get_gathering_profession_state,
    list_gathering_profession_states,
)
from game.gathering_foundation import (
    build_location_gather_source_profiles,
    resolve_gather_access_decision,
)
from handlers.location import handle_lower_menu_gather_text


PLAYER_ID = 22701
STATS = {
    'strength': 5, 'agility': 5, 'intuition': 5,
    'vitality': 5, 'wisdom': 5, 'luck': 5,
}


def _create_player(location_id='westwild_n2'):
    create_player(PLAYER_ID, 'pr227', 'PR227', STATS)
    conn = get_connection()
    conn.execute('UPDATE players SET location_id=? WHERE telegram_id=?', (location_id, PLAYER_ID))
    conn.commit()
    conn.close()


def _profession_snapshot(profession_key):
    return dict(get_gathering_profession_state(PLAYER_ID, profession_key))


async def _gather(profession_key, roll, profiles=None):
    message = SimpleNamespace(text='Gather', reply_text=AsyncMock())
    update = SimpleNamespace(message=message, effective_user=SimpleNamespace(id=PLAYER_ID))
    profile_patch = (
        patch('handlers.location.build_location_gather_source_profiles', return_value=profiles)
        if profiles is not None else patch('handlers.location.build_location_gather_source_profiles', wraps=build_location_gather_source_profiles)
    )
    with (
        patch('handlers.location.looks_like_lower_gather_button', return_value=True),
        patch('handlers.location.resolve_lower_gather_profession_button', return_value=profession_key),
        patch('handlers.location.random.random', return_value=roll),
        patch('handlers.location.has_active_live_pvp_engagement', return_value=False),
        patch('handlers.location.is_in_battle', return_value=False),
        profile_patch,
        patch(
            'handlers.location.resolve_gather_access_decision',
            wraps=resolve_gather_access_decision,
        ) as access_mock,
    ):
        handled = await handle_lower_menu_gather_text(update, SimpleNamespace())
    return handled, message, access_mock


def test_new_player_bootstraps_exact_canonical_profession_state():
    _create_player()

    states = [dict(row) for row in list_gathering_profession_states(PLAYER_ID)]
    assert {row['profession_key'] for row in states} == set(GATHERING_PROFESSION_KEYS)
    assert len(states) == 5
    assert {(row['level'], row['exp']) for row in states} == {(1, 0)}


def test_ensure_is_idempotent_and_backfills_legacy_missing_rows():
    conn = get_connection()
    conn.execute(
        "INSERT INTO players (telegram_id, username, name) VALUES (?, 'legacy', 'Legacy')",
        (PLAYER_ID,),
    )
    conn.commit()
    conn.close()

    ensure_player_gathering_professions(PLAYER_ID)
    ensure_player_gathering_professions(PLAYER_ID)
    states = [dict(row) for row in list_gathering_profession_states(PLAYER_ID)]

    assert len(states) == 5
    assert {row['profession_key'] for row in states} == set(GATHERING_PROFESSION_KEYS)
    assert {(row['level'], row['exp']) for row in states} == {(1, 0)}


def test_unknown_profession_key_does_not_create_state():
    _create_player()
    assert get_gathering_profession_state(PLAYER_ID, 'alchemy') is None
    conn = get_connection()
    count = conn.execute(
        'SELECT COUNT(*) AS count FROM player_gathering_professions WHERE telegram_id=?',
        (PLAYER_ID,),
    ).fetchone()['count']
    conn.close()
    assert count == 5


def test_database_rejects_direct_unknown_profession_insert():
    _create_player()
    conn = get_connection()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                '''
                INSERT INTO player_gathering_professions (
                    telegram_id, profession_key, level, exp
                ) VALUES (?, 'alchemy', 1, 0)
                ''',
                (PLAYER_ID,),
            )
    finally:
        conn.close()


def test_accessible_roll_grants_one_item_without_profession_progression():
    _create_player()
    before = _profession_snapshot('herbalism')

    handled, _, access_mock = asyncio.run(_gather('herbalism', 0.0))

    assert handled
    access_mock.assert_called_once()
    conn = get_connection()
    quantity = conn.execute(
        "SELECT quantity FROM inventory WHERE telegram_id=? AND item_id='herb_common'",
        (PLAYER_ID,),
    ).fetchone()['quantity']
    conn.close()
    assert quantity == 1
    assert _profession_snapshot('herbalism')['level'] == before['level'] == 1
    assert _profession_snapshot('herbalism')['exp'] == before['exp'] == 0


def test_locked_roll_grants_nothing_does_not_reroll_and_level_unlocks_same_resource():
    _create_player(location_id='westwild_n9')

    handled, message, _ = asyncio.run(_gather('herbalism', 0.45))
    assert handled
    assert message.reply_text.await_count == 1
    conn = get_connection()
    assert conn.execute(
        "SELECT COUNT(*) AS count FROM inventory WHERE telegram_id=? AND item_id='herb_magic'",
        (PLAYER_ID,),
    ).fetchone()['count'] == 0
    assert conn.execute(
        "SELECT COUNT(*) AS count FROM inventory WHERE telegram_id=? AND item_id='forest_mushroom'",
        (PLAYER_ID,),
    ).fetchone()['count'] == 0
    conn.execute(
        "UPDATE player_gathering_professions SET level=8 WHERE telegram_id=? AND profession_key='herbalism'",
        (PLAYER_ID,),
    )
    conn.commit()
    conn.close()

    asyncio.run(_gather('herbalism', 0.45))
    conn = get_connection()
    assert conn.execute(
        "SELECT quantity FROM inventory WHERE telegram_id=? AND item_id='herb_magic'",
        (PLAYER_ID,),
    ).fetchone()['quantity'] == 1
    conn.close()
    assert _profession_snapshot('herbalism')['exp'] == 0


def test_zone_denied_roll_grants_nothing():
    _create_player()
    wood = next(
        profile for profile in build_location_gather_source_profiles('westwild_n2')
        if profile.item_id == 'wood_dark'
    )
    conn = get_connection()
    conn.execute(
        "UPDATE player_gathering_professions SET level=20 WHERE telegram_id=? AND profession_key='woodcutting'",
        (PLAYER_ID,),
    )
    conn.commit()
    conn.close()

    asyncio.run(_gather('woodcutting', 0.0, profiles=(replace(wood, zone_tier_band=6),)))

    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) AS count FROM inventory WHERE telegram_id=? AND item_id='wood_dark'",
        (PLAYER_ID,),
    ).fetchone()['count']
    conn.close()
    assert count == 0
