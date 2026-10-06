import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from database import get_connection, get_player
from game.locations import get_location, get_location_neighbors
from game.player_ui import validate_surface
from game.quest_board import accept_hunt_contract
from handlers.location import build_location_message, handle_location_buttons, location_command, map_command
from handlers.quest_views import board_card
from handlers.world_views import current_region, local_entries, location_card, map_card


def callbacks(keyboard):
    return [b.callback_data for row in keyboard.inline_keyboard for b in row]


@pytest.mark.parametrize('lang', ['ru','en','es'])
@pytest.mark.parametrize('place', ['capital_city','hub_westwild','old_mine_entrance','south_coast_shore','westwild_n2'])
def test_location_categories_and_local_world_maps_bounded_and_localized(lang, place):
    conn = get_connection()
    conn.execute('UPDATE players SET location_id=?,lang=? WHERE telegram_id=1', (place,lang))
    conn.commit()
    conn.close()
    player = dict(get_player(1))
    for view in (location_card, map_card):
        text, keyboard = view(player)
        validate_surface(text,keyboard,list_view=view == map_card)
        assert 'pxe1.' not in text and 'location.' not in text and '/go ' not in text
        assert place not in text
        assert not any('location.' in b.text for row in keyboard.inline_keyboard for b in row)
    _, categories = local_entries(player)
    for category, entries in categories.items():
        text, keyboard = location_card(player,category=category)
        validate_surface(text,keyboard,list_view=True)
    text, keyboard = map_card(player,world=True)
    validate_surface(text,keyboard,list_view=True)
    if place == 'capital_city':
        assert len([c for c in callbacks(map_card(player)[1]) if c.startswith('goto_')]) == len(get_location_neighbors(place)) == 6
    if place == 'old_mine_entrance':
        assert current_region(player) == 'route_frostspine'
    if place == 'south_coast_shore':
        assert current_region(player) == 'route_south_coast_stub'


def test_nearby_includes_city_services_without_regional_records_and_board_objective_count():
    player = dict(get_player(1))
    with patch('game.regional_opportunities.nearby', return_value=[]):
        priority, categories = local_entries(player)
    assert {c for _,c in categories['services']} >= {'shop','quest_board','craftsmen_guild','inn'}
    conn = get_connection()
    conn.execute("INSERT INTO player_contract_history(player_id,contract_key) VALUES (1,'chapter_outfitter')")
    conn.commit()
    conn.close()
    assert accept_hunt_contract(player_id=1,location_id='capital_city',contract_key='chapter_homecoming')[0]
    text, keyboard = board_card(player,get_location('capital_city'))
    assert '0/0' not in text and '0/2' in text
    assert not any(c.startswith('quest_board_abandon_') for c in callbacks(keyboard))


def test_location_and_map_commands_and_route_preview_are_readable_during_combat():
    conn = get_connection()
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=1')
    conn.commit()
    conn.close()
    user = SimpleNamespace(id=1)
    message = SimpleNamespace(text='/map',reply_text=AsyncMock())
    update = SimpleNamespace(effective_user=user,message=message)
    context = SimpleNamespace(user_data={},bot=SimpleNamespace(send_message=AsyncMock()))
    asyncio.run(map_command(update,context))
    asyncio.run(location_command(update,context))
    query = SimpleNamespace(from_user=user,data='goto_westwild_n1',answer=AsyncMock(),edit_message_text=AsyncMock())
    asyncio.run(handle_location_buttons(SimpleNamespace(callback_query=query),context))
    assert query.edit_message_text.await_count == 1
    assert not any(c.startswith('px:travel:') for c in callbacks(query.edit_message_text.call_args.kwargs['reply_markup']))


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_preparation_cards_principal_pending_ally_and_accepted_ally(lang):
    import time
    from tests.test_pxe1_pvp_membership import prepare
    from game.pvp_world import invite,respond,iso
    from handlers.pvp_group import preparation_or_live_card
    conn,e = prepare()
    now = int(time.time()*1000)
    conn.execute('UPDATE pvp_engagements SET engagement_started_at=?,engagement_ready_at=? WHERE id=?',(iso(now),iso(now+300000),e))
    conn.execute('UPDATE players SET lang=?',(lang,))
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    invite(conn,engagement_id=e,principal_id=1,ally_id=2,now_ms=now)
    conn.commit()
    row = dict(conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(e,)).fetchone())
    text,keyboard = preparation_or_live_card(row,dict(get_player(1)))
    validate_surface(text,keyboard)
    assert any(c.startswith('pvp_revoke_') for c in callbacks(keyboard))
    text,keyboard = preparation_or_live_card(row,dict(get_player(2)))
    validate_surface(text,keyboard)
    assert f'pvp_reinf_accept_{e}' in callbacks(keyboard)
    assert not any(c.startswith('pvp_escape_') for c in callbacks(keyboard))
    conn.execute('BEGIN IMMEDIATE')
    respond(conn,engagement_id=e,ally_id=2,accepted=True,now_ms=now+1)
    conn.commit()
    row = dict(conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(e,)).fetchone())
    text,keyboard = preparation_or_live_card(row,dict(get_player(2)))
    validate_surface(text,keyboard)
    assert f'pvp_leaveprep_{e}' in callbacks(keyboard)
    assert not any(c.startswith('pvp_join_') for c in callbacks(keyboard))
    conn.close()
