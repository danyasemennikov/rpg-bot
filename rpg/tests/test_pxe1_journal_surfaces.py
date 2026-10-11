import pytest

from database import get_connection, get_player
from game.player_ui import validate_surface
from game.quest_board import accept_hunt_contract, get_chapter_contracts
from handlers.chapter import build_assignment, build_history, build_journal
from handlers.regional import build_regional_home


@pytest.mark.parametrize('lang', ['ru', 'en', 'es'])
@pytest.mark.parametrize('order', [1, 2, 3, 4])
def test_chapter_journal_and_detail_use_actual_objectives_within_budget(lang, order):
    contracts = get_chapter_contracts()
    contract = contracts[order-1]
    conn = get_connection()
    for prior in contracts[:order-1]:
        conn.execute('INSERT INTO player_contract_history(player_id,contract_key) VALUES (1,?)', (prior.contract_key,))
    conn.execute('UPDATE players SET location_id=?,lang=? WHERE telegram_id=1', (contract.board_locations[0], lang))
    conn.commit()
    conn.close()
    assert accept_hunt_contract(player_id=1, location_id=contract.board_locations[0], contract_key=contract.contract_key)[0]
    player = dict(get_player(1))
    for view in (build_journal, build_assignment):
        text, keyboard = view(player)
        validate_surface(text, keyboard)
        assert '0/0' not in text
        assert 'pxe1.' not in text and 'chapter_' not in text
        callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
        assert not any(c.startswith('quest_board_abandon_') for c in callbacks)
    story, keyboard = build_assignment(player, story=True)
    validate_surface(story, keyboard, long_detail=True)


@pytest.mark.parametrize('lang', ['ru', 'en', 'es'])
def test_regional_home_eight_controls_and_archive_contains_only_completions(lang):
    conn = get_connection()
    for contract in get_chapter_contracts():
        conn.execute('INSERT INTO player_contract_history(player_id,contract_key) VALUES (1,?)', (contract.contract_key,))
    conn.execute("INSERT INTO player_contract_history(player_id,contract_key) VALUES (1,'unknown_old_assignment')")
    conn.execute('UPDATE players SET lang=? WHERE telegram_id=1', (lang,))
    conn.commit()
    conn.close()
    player = dict(get_player(1))
    text, keyboard = build_regional_home(player)
    validate_surface(text, keyboard)
    assert sum(len(row) for row in keyboard.inline_keyboard) == 8
    assert build_journal(player)[0] == text
    text, keyboard = build_history(player)
    validate_surface(text, keyboard, list_view=True)
    assert 'unknown_old_assignment' not in text
    assert 'pe_o:' not in str(keyboard) and 'inv_catalog' not in str(keyboard)
    text, keyboard = build_history(player, chapter_story=True)
    validate_surface(text, keyboard, long_detail=True)
