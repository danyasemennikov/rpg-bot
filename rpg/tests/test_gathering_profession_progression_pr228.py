from itertools import count
_message_ids = count(1)
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from database import (
    add_gathering_profession_exp,
    create_player,
    get_connection,
    get_gathering_profession_state,
)
from game.gathering_foundation import (
    build_location_gather_source_profiles,
    resolve_gather_access_decision,
    resolve_gather_resource_identity,
)
from game.gathering_progression import (
    MAX_GATHERING_PROFESSION_LEVEL,
    apply_gathering_profession_progression,
    gathering_profession_exp_needed,
    gathering_profession_xp_for_success,
)
from game.items_data import get_item
from game.resource_handbook import build_resource_handbook_index
from handlers.location import handle_lower_menu_gather_text


PLAYER_ID = 22801
STATS = {
    'strength': 5, 'agility': 5, 'intuition': 5,
    'vitality': 5, 'wisdom': 5, 'luck': 5,
}


def _create_player(location_id='westwild_n2'):
    create_player(PLAYER_ID, 'pr228', 'PR228', STATS)
    conn = get_connection()
    conn.execute(
        "UPDATE players SET location_id=?, lang='en' WHERE telegram_id=?",
        (location_id, PLAYER_ID),
    )
    conn.commit()
    conn.close()


def _set_profession(profession_key, *, level, exp=0):
    conn = get_connection()
    conn.execute(
        '''
        UPDATE player_gathering_professions SET level=?, exp=?
        WHERE telegram_id=? AND profession_key=?
        ''',
        (level, exp, PLAYER_ID, profession_key),
    )
    conn.commit()
    conn.close()


def _profession(profession_key):
    return dict(get_gathering_profession_state(PLAYER_ID, profession_key))


async def _gather(profession_key, roll=0.0):
    message = SimpleNamespace(text='Gather', message_id=next(_message_ids), reply_text=AsyncMock())
    update = SimpleNamespace(message=message, effective_user=SimpleNamespace(id=PLAYER_ID))
    with (
        patch('handlers.location.looks_like_lower_gather_button', return_value=True),
        patch('handlers.location.resolve_lower_gather_profession_button', return_value=profession_key),
        patch('handlers.location.random.random', return_value=roll),
        patch('handlers.location.has_active_live_pvp_engagement', return_value=False),
        patch('handlers.location.is_in_battle', return_value=False),
    ):
        handled = await handle_lower_menu_gather_text(update, SimpleNamespace())
    return handled, message


def test_progression_contract_and_multiple_level_application():
    assert MAX_GATHERING_PROFESSION_LEVEL == 20
    assert [gathering_profession_exp_needed(level) for level in (1, 2, 5, 10, 19)] == [50, 100, 250, 500, 950]

    exact = apply_gathering_profession_progression(
        profession_key='herbalism', current_level=1, current_exp=40, xp_awarded=10,
    )
    assert (exact.new_level, exact.new_exp, exact.levels_gained) == (2, 0, 1)

    multiple = apply_gathering_profession_progression(
        profession_key='mining', current_level=1, current_exp=0, xp_awarded=200,
    )
    assert (multiple.new_level, multiple.new_exp, multiple.levels_gained) == (3, 50, 2)
    assert multiple.exp_needed == 150


@pytest.mark.parametrize(
    ('required_level', 'player_level', 'expected_xp'),
    [
        (1, 1, 10), (1, 5, 10), (1, 6, 5), (1, 9, 5), (1, 10, 2),
        (6, 6, 20), (6, 10, 20), (6, 11, 10), (6, 15, 5),
    ],
)
def test_xp_scaling_boundaries(required_level, player_level, expected_xp):
    assert gathering_profession_xp_for_success(
        current_profession_level=player_level,
        required_profession_level=required_level,
    ) == expected_xp


def test_database_progression_levels_caps_and_keeps_professions_independent():
    _create_player()
    _set_profession('herbalism', level=1, exp=40)
    exact = add_gathering_profession_exp(PLAYER_ID, 'herbalism', 10)
    assert (exact.old_level, exact.new_level, exact.new_exp) == (1, 2, 0)
    assert _profession('woodcutting')['level'] == 1
    assert _profession('woodcutting')['exp'] == 0

    _set_profession('mining', level=1, exp=0)
    multiple = add_gathering_profession_exp(PLAYER_ID, 'mining', 200)
    assert (multiple.new_level, multiple.new_exp, multiple.levels_gained) == (3, 50, 2)

    _set_profession('fishing', level=19, exp=940)
    capped = add_gathering_profession_exp(PLAYER_ID, 'fishing', 20)
    assert capped.at_cap
    assert (capped.new_level, capped.new_exp, capped.exp_needed) == (20, 0, None)
    at_cap = add_gathering_profession_exp(PLAYER_ID, 'fishing', 999)
    assert at_cap.xp_awarded == 0
    assert (_profession('fishing')['level'], _profession('fishing')['exp']) == (20, 0)


def test_unknown_profession_cannot_mutate_state():
    _create_player()
    assert add_gathering_profession_exp(PLAYER_ID, 'alchemy', 100) is None
    conn = get_connection()
    count = conn.execute(
        'SELECT COUNT(*) AS count FROM player_gathering_professions WHERE telegram_id=?',
        (PLAYER_ID,),
    ).fetchone()['count']
    conn.close()
    assert count == 5


def test_successful_accessible_gather_grants_item_xp_and_progress_feedback():
    _create_player()
    handled, message = asyncio.run(_gather('woodcutting'))
    assert handled
    conn = get_connection()
    quantity = conn.execute(
        "SELECT quantity FROM inventory WHERE telegram_id=? AND item_id='wood_common'",
        (PLAYER_ID,),
    ).fetchone()['quantity']
    conn.close()
    assert quantity == 1
    assert _profession('woodcutting')['exp'] == 10
    feedback = message.reply_text.await_args.args[0]
    assert 'Common Wood' in feedback
    assert '+10 profession XP' in feedback
    assert 'Lv. 1: 10/50' in feedback


def test_success_can_level_profession_and_emits_level_up_feedback():
    _create_player()
    _set_profession('woodcutting', level=1, exp=40)
    _, message = asyncio.run(_gather('woodcutting'))
    assert (_profession('woodcutting')['level'], _profession('woodcutting')['exp']) == (2, 0)
    assert 'profession level 2!' in message.reply_text.await_args.args[0]
    assert '0/100' in message.reply_text.await_args.args[0]


def test_denied_dark_wood_grants_neither_item_nor_xp_and_does_not_reroll():
    _create_player(location_id='westwild_n6')
    with patch('game.gathering_runtime.grant_item_to_player') as grant_mock:
        _, message = asyncio.run(_gather('woodcutting'))
    grant_mock.assert_not_called()
    assert _profession('woodcutting')['exp'] == 0
    assert message.reply_text.await_count == 1

    _set_profession('woodcutting', level=6)
    asyncio.run(_gather('woodcutting'))
    conn = get_connection()
    quantity = conn.execute(
        "SELECT quantity FROM inventory WHERE telegram_id=? AND item_id='wood_dark'",
        (PLAYER_ID,),
    ).fetchone()['quantity']
    conn.close()
    assert quantity == 1
    assert _profession('woodcutting')['exp'] == 20


def test_failed_roll_and_item_grant_failure_do_not_award_xp():
    _create_player()
    asyncio.run(_gather('woodcutting', roll=0.99))
    assert _profession('woodcutting')['exp'] == 0

    with patch('game.gathering_runtime.grant_item_to_player', side_effect=RuntimeError('grant failed')):
        with pytest.raises(RuntimeError, match='grant failed'):
            asyncio.run(_gather('woodcutting'))
    assert _profession('woodcutting')['exp'] == 0


def test_capped_profession_still_gathers_item_and_banks_no_xp():
    _create_player()
    _set_profession('woodcutting', level=20, exp=123)
    _, message = asyncio.run(_gather('woodcutting'))
    conn = get_connection()
    quantity = conn.execute(
        "SELECT quantity FROM inventory WHERE telegram_id=? AND item_id='wood_common'",
        (PLAYER_ID,),
    ).fetchone()['quantity']
    conn.close()
    assert quantity == 1
    assert _profession('woodcutting')['exp'] == 0
    feedback = message.reply_text.await_args.args[0]
    assert '+0 profession XP' in feedback
    assert 'maximum' in feedback
    assert '/1000' not in feedback


def test_starter_wood_identity_locations_access_and_handbook_ladder():
    item = get_item('wood_common')
    assert item['item_type'] == 'material'
    assert item['rarity'] == 'common'
    identity = resolve_gather_resource_identity('wood_common')
    assert (
        identity.profession_key,
        identity.resource_family,
        identity.reward_family,
        identity.base_gather_surface,
        identity.minimum_profession_level,
        identity.min_zone_tier_band,
        identity.max_zone_tier_band,
        identity.is_basic_resource,
    ) == ('woodcutting', 'wood', 'gathering_material', 'open_world_tree_nodes', 1, 1, 4, True)

    expected_chances = {
        'westwild_n2': 0.15, 'westwild_n3': 0.25,
        'westwild_n4': 0.35, 'westwild_n5': 0.40,
    }
    for location_id, chance in expected_chances.items():
        wood = [p for p in build_location_gather_source_profiles(location_id) if p.profession_key == 'woodcutting']
        assert [(p.item_id, p.chance) for p in wood] == [('wood_common', chance)]

    dark_identity = resolve_gather_resource_identity('wood_dark')
    assert dark_identity.minimum_profession_level == 6
    assert not resolve_gather_access_decision(
        item_id='wood_dark', player_profession_level=5, zone_tier_band=1,
    ).is_allowed
    assert resolve_gather_access_decision(
        item_id='wood_dark', player_profession_level=6, zone_tier_band=1,
    ).is_allowed
    assert any(p.item_id == 'wood_dark' for p in build_location_gather_source_profiles('westwild_n6'))

    handbook = build_resource_handbook_index()['woodcutting']
    by_item = {entry['item_id']: entry['location_ids'] for entry in handbook}
    assert by_item['wood_common'] == ['westwild_n2', 'westwild_n3', 'westwild_n4', 'westwild_n5']
    assert all(location_id not in by_item['wood_dark'] for location_id in expected_chances)
    assert 'westwild_n6' in by_item['wood_dark']
