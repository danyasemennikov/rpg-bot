import pytest
from database import get_connection,get_player
from game.player_experience_schema import grant_player_pxe1_starters
from game.player_ui import validate_surface
from game.profession_recipes import ACTIVE_RECIPES
from handlers.professions import build_recipe
from handlers.recipe_views import recipe_card


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_all_eighty_three_recipe_cards_compact_tool_output_has_no_sale_value(lang):
    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    grant_player_pxe1_starters(conn,1,now_ms=1000,acquired_via='starter')
    conn.commit()
    conn.close()
    player = dict(get_player(1))
    player['lang'] = lang
    for recipe in ACTIVE_RECIPES:
        text,keyboard = build_recipe(player,recipe.recipe_id)
        validate_surface(text,keyboard)
        assert 'pxe1.' not in text and 'professions.' not in text
        assert len([b for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith('pe_m:')])==0
        if recipe.output_spec.kind=='tool':
            text,keyboard = recipe_card(player,recipe.recipe_id,details=True)
            validate_surface(text,keyboard,long_detail=True)
            from game.i18n import t
            assert t('professions.output_sale',lang,gold=0) not in text
            if recipe.output_spec.profession_key in {'woodcutting','mining'} and recipe.output_spec.tool_tier>1:
                text,keyboard = recipe_card(player,recipe.recipe_id,commission=True)
                validate_surface(text,keyboard)
                assert 'pxe1.' not in text


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_craft_result_can_equip_its_exact_vest_and_replay_keeps_original_xp(lang):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from game.build_progression import migrate_character_builds_v1
    from game.gear_instances import grant_item_to_player
    from game.action_receipts import issue_actions
    from game.profession_recipes import recipe_intent_payload
    from game.economy_actions import get_receipt
    from handlers.professions import handle_profession_buttons
    from handlers.inventory import handle_inventory_buttons
    migrate_character_builds_v1()
    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    grant_player_pxe1_starters(conn,1,now_ms=1000,acquired_via='starter')
    from game.profession_schema import grant_new_player_starters
    grant_new_player_starters(conn,1)
    conn.execute("UPDATE players SET location_id='hub_westwild',lang=? WHERE telegram_id=1",(lang,))
    for item,quantity in (('wood_common',2),('wolf_pelt',2)):
        grant_item_to_player(1,item,quantity=quantity,source='test',conn=conn)
    conn.commit();conn.close()
    payload = recipe_intent_payload('trail_vest')
    token = issue_actions(1,'craft',[payload])[payload]
    query = SimpleNamespace(from_user=SimpleNamespace(id=1),data='pe_a:'+token,answer=AsyncMock(),edit_message_text=AsyncMock())
    asyncio.run(handle_profession_buttons(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={})))
    text = query.edit_message_text.call_args.args[0]
    keyboard = query.edit_message_text.call_args.kwargs['reply_markup']
    validate_surface(text,keyboard)
    assert '[pxe1.' not in text and 'instance #' not in text
    receipt = get_receipt(1,'ui:'+token)
    assert receipt['status']=='crafted',receipt
    assert receipt['progression'][0]['xp_awarded']==15
    equip = next(b.callback_data for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith('inv_gequip_'))
    query.data = equip
    asyncio.run(handle_inventory_buttons(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={})))
    conn = get_connection()
    assert conn.execute("SELECT id FROM gear_instances WHERE telegram_id=1 AND equipped_slot='chest'").fetchone()[0]==receipt['granted'][0]['instance_ids'][0]
    conn.execute('DELETE FROM player_ui_actions WHERE player_id=1')
    conn.execute("UPDATE players SET location_id='capital_city',travel_revision=travel_revision+1 WHERE telegram_id=1")
    conn.commit();conn.close()
    query.data = 'pe_a:'+token
    asyncio.run(handle_profession_buttons(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={})))
    assert get_receipt(1,'ui:'+token)['progression']==receipt['progression']


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_tool_replacement_confirmation_is_read_only_and_quote_rechecked(lang):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from game.gear_instances import grant_item_to_player
    from handlers.professions import handle_profession_buttons
    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    grant_player_pxe1_starters(conn,1,now_ms=1000,acquired_via='starter')
    conn.execute("UPDATE players SET location_id='hub_westwild',lang=? WHERE telegram_id=1",(lang,))
    for item,quantity in (('wood_common',4),('iron_ore',2),('coal',1)):
        grant_item_to_player(1,item,quantity=quantity,source='test',conn=conn)
    conn.commit();conn.close()
    text,keyboard = recipe_card(dict(get_player(1)),'pxe_tool_mining_1')
    preview = next(b.callback_data for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith('pe_tc:'))
    q = SimpleNamespace(from_user=SimpleNamespace(id=1),data=preview,answer=AsyncMock(),edit_message_text=AsyncMock())
    asyncio.run(handle_profession_buttons(SimpleNamespace(callback_query=q),SimpleNamespace(user_data={})))
    validate_surface(q.edit_message_text.call_args.args[0],q.edit_message_text.call_args.kwargs['reply_markup'])
    confirmation = next(b.callback_data for row in q.edit_message_text.call_args.kwargs['reply_markup'].inline_keyboard for b in row if b.callback_data.startswith('pe_a:'))
    conn = get_connection()
    assert conn.execute("SELECT revision FROM player_profession_tools WHERE player_id=1 AND profession_key='mining'").fetchone()[0]==1
    conn.execute("UPDATE inventory SET quantity=5 WHERE telegram_id=1 AND item_id='wood_common'")
    conn.commit();conn.close()
    q.data = confirmation
    asyncio.run(handle_profession_buttons(SimpleNamespace(callback_query=q),SimpleNamespace(user_data={})))
    conn = get_connection()
    assert conn.execute("SELECT revision FROM player_profession_tools WHERE player_id=1 AND profession_key='mining'").fetchone()[0]==1
    assert conn.execute("SELECT quantity FROM inventory WHERE telegram_id=1 AND item_id='wood_common'").fetchone()[0]==5
    conn.execute("UPDATE inventory SET quantity=4 WHERE telegram_id=1 AND item_id='wood_common'")
    conn.commit()
    conn.close()
    text,keyboard = recipe_card(dict(get_player(1)),'pxe_tool_mining_1')
    q.data = next(b.callback_data for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith('pe_tc:'))
    asyncio.run(handle_profession_buttons(SimpleNamespace(callback_query=q),SimpleNamespace(user_data={})))
    q.data = next(b.callback_data for row in q.edit_message_text.call_args.kwargs['reply_markup'].inline_keyboard for b in row if b.callback_data.startswith('pe_a:'))
    asyncio.run(handle_profession_buttons(SimpleNamespace(callback_query=q),SimpleNamespace(user_data={})))
    validate_surface(q.edit_message_text.call_args.args[0],q.edit_message_text.call_args.kwargs['reply_markup'])
    conn = get_connection()
    assert conn.execute("SELECT revision FROM player_profession_tools WHERE player_id=1 AND profession_key='mining'").fetchone()[0]==2
    assert not conn.execute("SELECT 1 FROM inventory WHERE telegram_id=1 AND item_id='wood_common'").fetchone()
    conn.close()
