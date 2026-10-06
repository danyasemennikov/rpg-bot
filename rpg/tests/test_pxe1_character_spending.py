import pytest

from database import get_connection,get_player
from game.build_progression import apply_attribute_spending,attribute_spending_preview,migrate_character_builds_v1
from game.player_ui import validate_surface
from handlers.character import character_card,spending_card,spending_preview_card,weapon_family_card


def setup_player():
    migrate_character_builds_v1()
    conn = get_connection()
    conn.execute('UPDATE players SET stat_points=6,attribute_budget=60,hp=37,mana=19 WHERE telegram_id=1')
    conn.commit()
    conn.close()


def test_spending_anywhere_caps_without_refill_and_receipt_replay_after_arrival():
    setup_player()
    conn = get_connection()
    conn.execute("UPDATE players SET location_id='westwild_n1' WHERE telegram_id=1")
    conn.commit()
    before = dict(get_player(1))
    preview = attribute_spending_preview(1,{'vitality':2,'wisdom':1})
    assert preview['success']
    result = apply_attribute_spending(1,preview['token'])
    assert result['success'] and result['unspent']==3
    after = dict(get_player(1))
    assert (after['hp'],after['mana'])==(37,19)
    assert after['max_hp']==before['max_hp']+36 and after['max_mana']==before['max_mana']+12
    assert after['build_revision']==before['build_revision']+1 and after['gear_revision']==before['gear_revision']
    conn.execute("UPDATE players SET location_id='westwild_n2',travel_revision=travel_revision+1 WHERE telegram_id=1")
    conn.commit()
    assert apply_attribute_spending(1,preview['token'])['already_applied']
    assert get_player(1)['stat_points']==3
    conn.close()


@pytest.mark.parametrize('deltas',[{}, {'strength':-1}, {'strength':True}, {'strength':1.5}, {'strength':7}, {'vitality':101}, {'unknown':1}])
def test_spending_rejects_bounds_negative_noninteger_and_overspend(deltas):
    setup_player()
    before = dict(get_player(1))
    assert not attribute_spending_preview(1,deltas)['success']
    assert dict(get_player(1))==before


def test_spending_allowed_during_travel_but_arrival_stales_preview_and_combat_blocks():
    from game.travel_runtime import preview_travel,start_travel_session,advance_travel_edge
    setup_player()
    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    trip = start_travel_session(conn,1,preview_travel(conn,1,'westwild_n1'),request_id='spend-trip',now_ms=1000)
    conn.commit()
    preview = attribute_spending_preview(1,{'strength':1})
    assert preview['success']
    assert apply_attribute_spending(1,preview['token'])['success']
    preview = attribute_spending_preview(1,{'strength':1})
    conn.execute('BEGIN IMMEDIATE')
    advance_travel_edge(conn,trip['session_id'],now_ms=16000)
    conn.commit()
    assert not apply_attribute_spending(1,preview['token'])['success']
    assert get_player(1)['stat_points']==5
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=1')
    conn.commit()
    assert attribute_spending_preview(1,{'strength':1})['reason']=='in_battle'
    conn.execute('UPDATE players SET in_battle=0,hp=0 WHERE telegram_id=1')
    conn.commit()
    assert attribute_spending_preview(1,{'strength':1})['reason']=='dead'
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_character_attribute_and_all_twenty_branch_cards_use_compact_localized_views(lang):
    from game.build_contract import FAMILIES
    setup_player()
    for view in (character_card,spending_card):
        text,keyboard = view(1,lang)
        validate_surface(text,keyboard)
        assert 'capital_city' not in text and 'pxe1.' not in text
    _,view = spending_preview_card(1,lang,{'strength':1,'vitality':1})
    validate_surface(*view)
    for family in FAMILIES:
        text,keyboard = weapon_family_card(1,family,lang)
        validate_surface(text,keyboard)
        for branch in ('A','B'):
            text,keyboard = weapon_family_card(1,family,lang,branch=branch)
            validate_surface(text,keyboard,list_view=True)
            assert len([b for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith('bv_skill_')])==5
            import re
            assert not re.search(r'\bM\d+\b',text) and 'pxe1.' not in text
