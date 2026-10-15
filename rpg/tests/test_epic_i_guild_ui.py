import asyncio
import json
from types import SimpleNamespace
import pytest
import database
from game.profession_state import PROFESSIONS,register_profession
from game.profession_schema import ensure_profession_rows
from game.recipe_knowledge import learn_knowledge
from game.i18n import get_item_name,t
from handlers.profession_guild_views import profession_home,knowledge_view,work_picker,work_quote,job_view,commission_view,supply_view,handle_guild_buttons
from handlers.recipe_views import recipe_card


def assert_surface(view):
    text,keyboard=view
    assert '[' not in text,text
    for row in keyboard.inline_keyboard:
        for button in row:
            assert len(button.callback_data.encode())<=64,button.callback_data
            assert '[' not in button.text,button.text


class Query:
    def __init__(self,data):
        self.data=data;self.from_user=SimpleNamespace(id=1);self.edits=[];self.answers=[]
    async def answer(self,text=''):self.answers.append(text)
    async def edit_message_text(self,text,**kwargs):self.edits.append((text,kwargs['reply_markup']))


@pytest.mark.parametrize('profession',PROFESSIONS)
@pytest.mark.parametrize('lang',('ru','en','es'))
def test_registration_and_knowledge_callbacks_localized_and_replayable(profession,lang):
    conn=database.get_connection();conn.execute('UPDATE players SET lang=?,gold=0 WHERE telegram_id=1',(lang,));conn.commit();conn.close()
    player=dict(database.get_player(1))
    home=profession_home(player,profession);assert_surface(home)
    query=Query(home[1].inline_keyboard[0][0].callback_data)
    asyncio.run(handle_guild_buttons(SimpleNamespace(callback_query=query),None))
    assert_surface(query.edits[-1])
    asyncio.run(handle_guild_buttons(SimpleNamespace(callback_query=query),None))
    choices=knowledge_view(player,profession);assert_surface(choices)
    query=Query(choices[1].inline_keyboard[0][0].callback_data)
    asyncio.run(handle_guild_buttons(SimpleNamespace(callback_query=query),None))
    assert query.answers[-1]==t('epic_i.done',lang)
    assert_surface(query.edits[-1])
    assert_surface(work_picker(player,profession))


@pytest.mark.parametrize('lang',('ru','en','es'))
def test_paid_quote_accept_and_stage_screen(lang):
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    conn.execute('UPDATE players SET lang=?,gold=0 WHERE telegram_id=1',(lang,))
    ensure_profession_rows(conn,1);register_profession(conn,1,'mining');learn_knowledge(conn,1,'gp_mining_1_a');conn.commit();conn.close()
    player=dict(database.get_player(1))
    view=work_quote(player,source='iron_ore');assert_surface(view)
    query=Query(view[1].inline_keyboard[0][0].callback_data)
    asyncio.run(handle_guild_buttons(SimpleNamespace(callback_query=query),None))
    assert query.answers[-1]==t('epic_i.done',lang)
    assert_surface(query.edits[-1])
    conn=database.get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM guild_job WHERE status='active'").fetchone()[0]==1
        assert conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0]==0
    finally:conn.close()


def test_commission_ui_needs_no_maker_knowledge_and_supply_names_are_localized():
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    ensure_profession_rows(conn,1);register_profession(conn,1,'mining');conn.commit();conn.close()
    for lang in ('ru','en','es'):
        player={**dict(database.get_player(1)),'lang':lang}
        assert_surface(commission_view(player,'mining'))
        assert_surface(commission_view(player,'mining',tier=1))
        assert_surface(supply_view(player,'mining'))
        assert get_item_name('a25_whisper_bark',lang)!='a25_whisper_bark'


def test_batch_card_binds_full_cost_to_durable_batch_and_executes_once():
    from game.crafting_runtime import craft_recipe
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    ensure_profession_rows(conn,1);register_profession(conn,1,'alchemy');learn_knowledge(conn,1,'field_tonic')
    conn.execute("UPDATE player_crafting_professions SET level=10 WHERE player_id=1 AND profession_key='alchemy'")
    conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,'herb_common',6)")
    conn.commit();conn.close()
    view=recipe_card(dict(database.get_player(1)),'field_tonic',count=2)
    assert_surface(view)
    token=next(b.callback_data[5:] for row in view[1].inline_keyboard for b in row if b.callback_data.startswith('pe_a:'))
    result=craft_recipe(1,'field_tonic',action_token=token)
    assert result.status=='crafted' and result.crafted_quantity==2
    assert craft_recipe(1,'field_tonic',action_token=token).recovered


def test_personal_tool_confirmation_and_existing_receipt_renderer():
    from game.crafting_runtime import craft_recipe
    from game.profession_recipes import get_recipe
    from game.economy_actions import get_receipt
    from handlers.recipe_views import tool_craft_confirmation
    from handlers.professions import build_mutation_result
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    ensure_profession_rows(conn,1);register_profession(conn,1,'blacksmith');learn_knowledge(conn,1,'pxe_tool_mining_1')
    for item,quantity in get_recipe('pxe_tool_mining_1').requirements:
        conn.execute('INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,?,?)',(item,quantity))
    conn.commit();conn.close()
    player=dict(database.get_player(1))
    view=recipe_card(player,'pxe_tool_mining_1');assert_surface(view)
    token=next(b.callback_data[6:] for row in view[1].inline_keyboard for b in row if b.callback_data.startswith('pe_tc:'))
    confirmation=tool_craft_confirmation(player,token);assert_surface(confirmation)
    mutation=confirmation[1].inline_keyboard[0][0].callback_data[5:]
    assert craft_recipe(1,'pxe_tool_mining_1',action_token=mutation).status=='crafted'
    receipt=get_receipt(1,'ui:'+mutation)
    assert_surface(build_mutation_result(player,receipt,'pxe_tool_mining_1'))
