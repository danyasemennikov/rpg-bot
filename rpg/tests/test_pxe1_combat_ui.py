import asyncio,json
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

import pytest
from database import get_connection,get_player
from game.combat_orders import load_combat_orders
from game.i18n import t
from game.player_ui import validate_surface
from game.pve_live import load_active_pve_encounter
from handlers import combat_views,pvp_group
from tests.test_pxe1_pve_world_tick import started
from tests.test_pxe1_pvp_group_runtime import locked


def payload(callback):
    conn=get_connection()
    try:
        return json.loads(conn.execute('SELECT payload FROM player_ui_actions WHERE token=?',(callback.split('_')[-1],)).fetchone()[0])
    finally: conn.close()


def buttons(keyboard): return [b for row in keyboard.inline_keyboard for b in row]


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_pve_home_single_target_skills_and_scope_are_read_only(lang):
    encounter,_=started()
    state,mob=load_active_pve_encounter(encounter_id=encounter)
    player=dict(get_player(1));player['lang']=lang
    before=json.dumps(state,sort_keys=True)
    with patch('time.time',return_value=1013):
        text,kb=combat_views.home(player,mob,state)
        assert len(buttons(kb))==6
        assert {b.text for b in buttons(kb)}=={t('battle.attack_btn',lang),t('pxe1.combat.skills',lang),t('location.pvp_action_guard_btn',lang),t('battle.potions_btn',lang),t('battle.flee_btn',lang),t('pxe1.details',lang)}
        text,kb=combat_views.action_card(player,state,'normal')
        committing=[b for b in buttons(kb) if b.callback_data.startswith('battle_v1_')]
        assert len(committing)==1
        action=payload(committing[0].callback_data)['action']
        assert action['target_info']['id']==state['enemy_states_v1'][0]['unit_id']
        text,kb=combat_views.action_card(player,state,'guard')
        assert buttons(kb)[0].text==t('pxe1.combat.use',lang)
        text,kb=combat_views.skills_card(player,state)
        assert sum(t('skill_names.power_strike',lang) in b.text for b in buttons(kb))<=1
        state['participant_states_v1']['1']['mana']=0
        text,kb=combat_views.action_card(player,state,'power_strike')
        assert t('pxe1.combat.no_mana',lang,cost=8)[:3] in text
        assert not any(b.callback_data.startswith('battle_v1_') for b in buttons(kb))
    state['participant_states_v1']['1']['mana']=json.loads(before)['participant_states_v1']['1']['mana']
    assert json.dumps(state,sort_keys=True)==before
    assert load_combat_orders(encounter_kind='pve',encounter_id=encounter,turn_revision=state['turn_revision'])==[]


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_pvp_group_home_and_explicit_single_target_no_cost(lang):
    conn,e=locked(defenders=1)
    row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(e,)).fetchone()
    context=json.loads(row['reason_context']);before=row['reason_context']
    with patch('time.time',return_value=1301):
        text,kb=pvp_group.live_card(row,context,2,lang)
        assert len(buttons(kb))==5
        assert all(b.callback_data.startswith('pvp_cv_') for b in buttons(kb))
        text,kb=pvp_group.target_card(row,2,'normal',context['battle']['turn_revision'],lang)
        assert t('pxe1.combat.choose_target',lang) in text
        assert len([b for b in buttons(kb) if b.callback_data.startswith('pvp_v1_')])==1
        text,kb=pvp_group.menu_card(row,2,'skills',lang)
        validate_surface(text,kb,list_view=True)
        text,kb=pvp_group.menu_card(row,2,'details',lang)
        validate_surface(text,kb,long_detail=True)
        text,kb=pvp_group.live_card(row,context,5,lang)
        assert '❤️' not in text and '🔵' not in text
    assert conn.execute('SELECT reason_context FROM pvp_engagements WHERE id=?',(e,)).fetchone()[0]==before
    assert load_combat_orders(encounter_kind='pvp',encounter_id=str(e),turn_revision=1)==[]
    conn.close()


def test_pve_read_handler_loads_authority_and_does_not_resolve_timeout():
    encounter,_=started()
    state,mob=load_active_pve_encounter(encounter_id=encounter)
    player=dict(get_player(1))
    with patch('time.time',return_value=1013):
        _,kb=combat_views.home(player,mob,state)
        query=SimpleNamespace(data=buttons(kb)[0].callback_data,from_user=SimpleNamespace(id=1),
            message=SimpleNamespace(chat_id=1,message_id=100),edit_message_text=AsyncMock(),answer=AsyncMock())
        asyncio.run(combat_views.handle_read_selection(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={})))
    assert t('pxe1.combat.choose_target',player['lang']) in query.edit_message_text.call_args.args[0]
    current,_=load_active_pve_encounter(encounter_id=encounter)
    assert current['side_deadline_at']==state['side_deadline_at']
    assert current['participant_states_v1']==state['participant_states_v1']
    conn=get_connection()
    assert not conn.execute('SELECT 1 FROM combat_turn_results_v1').fetchone()
    assert conn.execute('SELECT message_id FROM player_pxe1_ui WHERE player_id=1').fetchone()[0]==100
    conn.close()


def test_pve_supplies_are_paginated_and_use_requires_confirmation():
    encounter,_=started();state,_=load_active_pve_encounter(encounter_id=encounter)
    conn=get_connection();conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,'health_potion_small',3)")
    inv=conn.execute('SELECT id FROM inventory WHERE telegram_id=1').fetchone()[0];conn.commit();conn.close()
    player=dict(get_player(1))
    with patch('time.time',return_value=1013):
        _,kb=combat_views.supplies_card(player,state)
        assert not any(b.callback_data.startswith('battle_use_potion_') for b in buttons(kb))
        text,kb=combat_views.supplies_card(player,state,inventory_id=inv)
        assert buttons(kb)[0].text==t('pxe1.combat.use',player['lang'])
    conn=get_connection()
    assert conn.execute('SELECT quantity FROM inventory WHERE id=?',(inv,)).fetchone()[0]==3
    conn.close()
