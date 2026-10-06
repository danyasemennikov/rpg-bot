import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from database import get_connection,get_player
from game.build_progression import migrate_character_builds_v1
from game.gear_instances import grant_item_to_player
from game.player_ui import validate_surface
from handlers.inventory import build_gear_comparison,build_inventory_list,build_item_detail,handle_inventory_buttons
from handlers.inventory_views import CATEGORIES,category_card


def seed_inventory():
    migrate_character_builds_v1()
    from game.player_experience_schema import ensure_player_experience_schema,grant_player_pxe1_starters
    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    ensure_player_experience_schema(conn)
    grant_player_pxe1_starters(conn,1,now_ms=1000,acquired_via='starter')
    for item in ('field_sword_1h','trail_vest','health_potion_small','wood_common'):
        grant_item_to_player(1,item,quantity=1 if item in {'field_sword_1h','trail_vest'} else 3,source='test',source_level=1,conn=conn)
    conn.commit()
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_five_category_projection_tools_not_sellable_and_compact_details(lang):
    seed_inventory()
    text,keyboard = category_card(lang)
    validate_surface(text,keyboard)
    assert len([b for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith('inv_tab_')])==6
    for category in CATEGORIES:
        text,keyboard = build_inventory_list(1,category,lang)
        validate_surface(text,keyboard,list_view=True)
        assert 'pxe1.' not in text and '#' not in text
        for button in [b for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith('inv_item_')]:
            _,_,entry_token,route = button.callback_data.split('_')
            text,detail = build_item_detail(1,entry_token,route,lang)
            validate_surface(text,detail)
            assert '#' not in text and 'instance #' not in text
    text,keyboard = build_inventory_list(1,'tools',lang)
    assert len([b for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith('px:tool:')])==5
    assert not any(b.callback_data.startswith('inv_item_') for row in keyboard.inline_keyboard for b in row)


def test_comparison_equips_exact_owned_instance_with_existing_mutation():
    seed_inventory()
    conn = get_connection()
    instance = conn.execute("SELECT id FROM gear_instances WHERE telegram_id=1 AND base_item_id='field_sword_1h'").fetchone()[0]
    conn.close()
    text,keyboard = build_gear_comparison(1,f'g{instance}','weapon','gear','en')
    validate_surface(text,keyboard)
    equip = next(b.callback_data for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith('inv_cequip_'))
    query = SimpleNamespace(from_user=SimpleNamespace(id=1),data=equip,answer=AsyncMock(),edit_message_text=AsyncMock())
    asyncio.run(handle_inventory_buttons(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={})))
    conn = get_connection()
    assert conn.execute('SELECT equipped_slot FROM gear_instances WHERE id=?',(instance,)).fetchone()[0]=='weapon'
    assert query.edit_message_text.await_count==1
    text,keyboard = build_gear_comparison(777,f'g{instance}','weapon','gear','en')
    assert not any(b.callback_data.startswith('inv_cequip_') for row in keyboard.inline_keyboard for b in row)
    conn.close()
