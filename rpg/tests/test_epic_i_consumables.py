"""SQLite/evaluator evidence; no Telegram client or real-time balance claim."""
import asyncio
import copy
import json
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

import pytest
import database
from game.action_receipts import issue_actions,ActionRejected
from game.actor_snapshot import build_actor_snapshot
from game.profession_consumables import CONSUMABLES,use_payload,pending_slot,bind_next_battle,accuracy_rating,clamp_after_battle
from game.combat_identity import evaluate_action,_add_effect,mitigation_fraction
from handlers.inventory import use_inventory_consumable


def stock(item_id,quantity=3):
    conn=database.get_connection()
    conn.execute('UPDATE players SET hp=20,mana=10 WHERE telegram_id=1')
    inv=conn.execute('INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,?,?)',(item_id,quantity)).lastrowid
    conn.commit();conn.close()
    return inv


def intent(inv,*,confirmed=False):
    conn=database.get_connection()
    row=conn.execute('SELECT quantity FROM inventory WHERE id=?',(inv,)).fetchone()
    payload=use_payload(conn,1,inv,row['quantity'],confirmed=confirmed)
    conn.close()
    return issue_actions(1,'use',[payload])[payload]


@pytest.mark.parametrize('item_id',CONSUMABLES)
def test_all_twelve_have_actual_use_policy_and_localized_cards(item_id):
    from game.equipment_stats import get_player_effective_stats
    from handlers.inventory_views import item_card
    from game.i18n import get_item_description
    inv=stock(item_id)
    token=intent(inv)
    caps=get_player_effective_stats(1,dict(database.get_player(1)))
    first=use_inventory_consumable(1,token)
    spec=CONSUMABLES[item_id]
    if spec.get('cleanse'):
        assert first['status']=='consumable_wrong_context'
    else:
        assert first['status']=='used'
        assert first['heal']==min(caps['max_hp']-20,caps['max_hp']*spec.get('restore_hp',0)//100)
        assert first['mana']==min(caps['max_mana']-10,caps['max_mana']*spec.get('restore_mana',0)//100)
    assert use_inventory_consumable(1,token)['status']==first['status']
    conn=database.get_connection()
    try:
        assert conn.execute('SELECT quantity FROM inventory WHERE id=?',(inv,)).fetchone()[0]==(3 if spec.get('cleanse') else 2)
        if 'slot' in spec:
            assert pending_slot(conn,1,spec['slot'])['item_id']==item_id
    finally:conn.close()
    for lang in ('ru','en','es'):
        text,keyboard=item_card(1,f'i{inv}','supplies',lang)
        assert get_item_description(item_id,lang) in text
        assert '[' not in text
        assert all(len(b.callback_data.encode())<=64 for row in keyboard.inline_keyboard for b in row)


def test_slot_replacement_requires_confirmation_and_rejects_racing_preview():
    a=stock('a25_clear_sight');b=stock('a25_balanced_elixir')
    old=intent(b,confirmed=True)
    assert use_inventory_consumable(1,intent(a))['status']=='used'
    assert use_inventory_consumable(1,old)['status']=='stale_action'
    assert use_inventory_consumable(1,intent(b))['status']=='consumable_replace_required'
    assert use_inventory_consumable(1,intent(b,confirmed=True))['status']=='used'
    conn=database.get_connection()
    assert pending_slot(conn,1,'preparation')['item_id']=='a25_balanced_elixir'
    assert pending_slot(conn,1,'preparation')['revision']==2
    conn.close()


def test_slots_persist_preview_does_not_consume_and_binding_is_atomic_and_idempotent():
    for item in ('a25_balanced_elixir','a25_hunters_stew'):
        inv=stock(item);assert use_inventory_consumable(1,intent(inv))['status']=='used'
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    preview=build_actor_snapshot(1,conn=conn)
    assert pending_slot(conn,1,'food')['item_id']=='a25_hunters_stew'
    bound=bind_next_battle(conn,1,'pve','bound',preview)
    assert bound['hp']==preview['hp'] and bound['mana']==preview['mana']
    assert bound['max_hp']==preview['max_hp']+preview['max_hp']*12//100
    assert bound['max_mana']==preview['max_mana']+preview['max_mana']*8//100
    assert len(bound['profession_consumables'])==2
    assert pending_slot(conn,1,'food')['item_id'] is None
    conn.rollback();conn.close()
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    assert pending_slot(conn,1,'food')['item_id']=='a25_hunters_stew'
    again=bind_next_battle(conn,1,'pve','bound',build_actor_snapshot(1,conn=conn))
    conn.commit();conn.close()
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    assert bind_next_battle(conn,1,'pve','bound',preview)==again
    next_battle=bind_next_battle(conn,1,'pve','next',preview)
    assert next_battle['profession_consumables']==[]
    assert next_battle['max_hp']==preview['max_hp']
    conn.rollback();conn.close()


def test_first_three_opportunities_accuracy_and_first_two_poison_applications():
    inv=stock('a25_clear_sight');use_inventory_consumable(1,intent(inv))
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    base=build_actor_snapshot(1,conn=conn);actor=bind_next_battle(conn,1,'pve','sight',base)
    conn.rollback();conn.close()
    for opportunity in range(4):
        assert actor['opportunity_index']==opportunity
        assert accuracy_rating(actor)==base['accuracy']+(base['accuracy']*8//100 if opportunity<3 else 0)
        actor=evaluate_action(actor,[actor],[],{'kind':'guard'},rng_seed=1)['actor']
    actor['profession_consumables']=[{'poison_charges':2}]
    for index,duration in enumerate((2,1,3)):
        effect={'kind':'poison','duration':(3,1,3)[index],'source_id':'enemy','created_side_index':index}
        _add_effect(actor,effect)
        assert effect['duration']==duration
    assert actor['profession_consumables'][0]['poison_charges']==0


def test_defense_is_rating_and_exit_caps_never_heal():
    inv=stock('a25_deepwater_supper');use_inventory_consumable(1,intent(inv))
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    actor=build_actor_snapshot(1,conn=conn);actor['physical_defense']=100;actor['magic_defense']=200
    bound=bind_next_battle(conn,1,'pve','defense',actor)
    assert bound['physical_defense']==106 and bound['magic_defense']==212
    assert mitigation_fraction(bound,source_level=1,school='physical')==pytest.approx(106/226)
    conn.execute('UPDATE players SET hp=9999,mana=9999 WHERE telegram_id=1')
    clamp_after_battle(conn,1)
    row=conn.execute('SELECT * FROM players WHERE telegram_id=1').fetchone()
    assert row['hp']==actor['max_hp'] and row['mana']==actor['max_mana']
    conn.execute('UPDATE players SET hp=7,mana=3 WHERE telegram_id=1');clamp_after_battle(conn,1)
    assert conn.execute('SELECT hp,mana FROM players WHERE telegram_id=1').fetchone()[:]==(7,3)
    conn.rollback();conn.close()


def cleanse_fixture():
    from tests.test_pxe1_pve_world_tick import started
    from game.pve_live import load_active_pve_encounter
    inv=stock('a25_cleanse_draught')
    encounter,_=started()
    state,_=load_active_pve_encounter(encounter_id=encounter)
    actor=state['participant_states_v1']['1']
    actor['effects']=[{'kind':'poison','source_id':'enemy','duration':3,'value':0,'raw_tick':1,'created_side_index':0},
                      {'kind':'poison','source_id':'enemy2','duration':3,'value':0,'raw_tick':1,'created_side_index':0}]
    conn=database.get_connection();conn.execute('UPDATE pve_encounters SET battle_state_json=? WHERE encounter_id=?',(json.dumps(state),encounter));conn.commit();conn.close()
    from game.combat_orders import issue_combat_intents
    action={'kind':'cleanse','skill_id':None,'item_id':'a25_cleanse_draught','target_info':{'id':1}}
    with patch('time.time',return_value=1013):
        token=next(iter(issue_combat_intents(1,encounter_id=encounter,turn_revision=state['turn_revision'],deadline_at=state['side_deadline_at'],actions=[action]).values()))
    return inv,encounter,state,token


@pytest.mark.parametrize('restart',(False,True))
def test_cleanse_commits_one_item_and_one_normal_opportunity_across_restart(restart):
    from tests.test_pxe1_combat_order_replay import consume
    from game import pve_live
    inv,encounter,state,token=cleanse_fixture()
    assert consume(1,token,1013)['accepted']
    assert consume(1,token,1013)['already_applied']
    conn=database.get_connection()
    assert conn.execute('SELECT quantity FROM inventory WHERE id=?',(inv,)).fetchone()[0]==2
    assert len(json.loads(conn.execute('SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0])['participant_states_v1']['1']['effects'])==2
    conn.close()
    if restart:pve_live.reset_solo_pve_runtime_store()
    state,mob=pve_live.load_active_pve_encounter(encounter_id=encounter)
    now=datetime.fromtimestamp(1013,timezone.utc)
    pve_live.ensure_runtime_for_battle(player_id=1,battle_state=state,mob=mob,now=now)
    initial=state['participant_states_v1']['1']['opportunity_index']
    with patch('game.pve_live._utc_now',return_value=now):
        assert pve_live.resolve_current_side_if_ready(player_id=1,battle_state=state,
            on_player_action=lambda action:pve_live._dispatch_v1_player_action(action,battle_state=state),on_enemy_action=lambda action:None)
    actor=state['participant_states_v1']['1']
    assert actor['opportunity_index']==initial+1
    assert len([e for e in actor['effects'] if e['kind']=='poison'])==1
    assert len([e for e in state['combat_events_v1'] if e['kind']=='consumable_cleanse'])==1


def test_cleanse_ack_failure_rolls_back_inventory_and_order():
    from tests.test_pxe1_combat_order_replay import consume
    inv,encounter,state,token=cleanse_fixture()
    with patch('game.economy_actions.store_receipt',side_effect=RuntimeError('injected')):
        with pytest.raises(RuntimeError,match='injected'):consume(1,token,1013)
    conn=database.get_connection()
    assert conn.execute('SELECT quantity FROM inventory WHERE id=?',(inv,)).fetchone()[0]==3
    assert not conn.execute('SELECT 1 FROM combat_orders_v1 WHERE encounter_id=?',(encounter,)).fetchone()
    conn.close()
    assert consume(1,token,1013)['accepted']


@pytest.mark.parametrize('lang',('ru','en','es'))
def test_real_inventory_callback_previews_and_confirms_slot_replacement(lang):
    from handlers.inventory import handle_inventory_buttons
    from game.i18n import t
    conn=database.get_connection();conn.execute('UPDATE players SET lang=? WHERE telegram_id=1',(lang,));conn.commit();conn.close()
    a=stock('a25_dry_ration');b=stock('a25_hunters_stew')
    assert use_inventory_consumable(1,intent(a))['status']=='used'
    token=intent(b)
    query=SimpleNamespace(from_user=SimpleNamespace(id=1),data=f'inv_use_{token}_supplies',answer=AsyncMock(),edit_message_text=AsyncMock())
    asyncio.run(handle_inventory_buttons(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={})))
    assert t('epic_i.consumable_replace',lang,name='').split(':')[0] in query.edit_message_text.call_args.args[0]
    keyboard=query.edit_message_text.call_args.kwargs['reply_markup']
    query.data=keyboard.inline_keyboard[0][0].callback_data
    conn=database.get_connection()
    assert pending_slot(conn,1,'food')['item_id']=='a25_dry_ration'
    assert conn.execute('SELECT quantity FROM inventory WHERE id=?',(b,)).fetchone()[0]==3
    conn.close()
    asyncio.run(handle_inventory_buttons(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={})))
    conn=database.get_connection()
    assert pending_slot(conn,1,'food')['item_id']=='a25_hunters_stew'
    assert conn.execute('SELECT quantity FROM inventory WHERE id=?',(b,)).fetchone()[0]==2
    conn.close()


@pytest.mark.parametrize('lang',('ru','en','es'))
def test_current_pve_supplies_card_issues_cleanse_order_and_callback_spends_turn(lang):
    from handlers.combat_views import supplies_card
    from handlers.battle import handle_battle_buttons
    from game.pve_live import load_active_pve_encounter
    from game.i18n import t
    inv,encounter,state,_=cleanse_fixture()
    conn=database.get_connection();conn.execute('UPDATE players SET lang=? WHERE telegram_id=1',(lang,));conn.commit();conn.close()
    player=dict(database.get_player(1))
    with patch('time.time',return_value=1013):
        text,keyboard=supplies_card(player,state,inventory_id=inv)
    assert t('epic_i.effect_a25_cleanse_draught',lang) in text
    callback=keyboard.inline_keyboard[0][0].callback_data
    assert callback.startswith('battle_v1_') and len(callback.encode())<=64
    query=SimpleNamespace(from_user=SimpleNamespace(id=1),data=callback,answer=AsyncMock(),edit_message_text=AsyncMock(),
        message=SimpleNamespace(chat_id=1,message_id=90))
    context=SimpleNamespace(user_data={},bot=SimpleNamespace(send_message=AsyncMock(),edit_message_text=AsyncMock()),application=SimpleNamespace(user_data={1:{}}))
    with patch('time.time',return_value=1013),patch('game.pve_live._utc_now',return_value=datetime.fromtimestamp(1013,timezone.utc)),patch('game.combat_orders.datetime') as clock:
        clock.fromisoformat.side_effect=datetime.fromisoformat
        clock.now.return_value=datetime.fromtimestamp(1013,timezone.utc)
        asyncio.run(handle_battle_buttons(SimpleNamespace(callback_query=query),context))
    state,_=load_active_pve_encounter(encounter_id=encounter)
    assert len([e for e in state['combat_events_v1'] if e['kind']=='consumable_cleanse'])==1
    conn=database.get_connection()
    assert conn.execute('SELECT quantity FROM inventory WHERE id=?',(inv,)).fetchone()[0]==2
    conn.close()


def test_pve_forming_keeps_slots_roster_lock_binds_once_and_flee_clamps():
    from game.build_progression import migrate_character_builds_v1
    from tests.test_pxe1_encounter_lifecycle import prepare
    from game.pve_live import process_due_pve_formations,load_active_pve_encounter,resolve_pve_flee_intent
    from game.combat_orders import issue_combat_intents
    inv=stock('a25_balanced_elixir');use_inventory_consumable(1,intent(inv))
    migrate_character_builds_v1()
    encounter,_=prepare()
    conn=database.get_connection()
    assert pending_slot(conn,1,'preparation')['item_id']=='a25_balanced_elixir'
    assert not conn.execute('SELECT 1 FROM consumable_battle_bindings WHERE encounter_id=?',(encounter,)).fetchone()
    conn.close()
    process_due_pve_formations(now_ms=1012000)
    state,_=load_active_pve_encounter(encounter_id=encounter)
    actor=state['participant_states_v1']['1']
    base_hp=actor['consumable_base_caps']['max_hp'];base_mp=actor['consumable_base_caps']['max_mana']
    assert actor['max_hp']==base_hp+base_hp*8//100 and actor['hp']==100
    assert actor['profession_consumables'][0]['item_id']=='a25_balanced_elixir'
    assert process_due_pve_formations(now_ms=1013000)==[]
    actor['hp']=actor['max_hp'];actor['mana']=actor['max_mana']
    conn=database.get_connection();conn.execute('UPDATE pve_encounters SET battle_state_json=? WHERE encounter_id=?',(json.dumps(state),encounter));conn.commit();conn.close()
    with patch('time.time',return_value=1013):
        token=next(iter(issue_combat_intents(1,encounter_id=encounter,turn_revision=state['turn_revision'],deadline_at=state['side_deadline_at'],actions=[{'kind':'flee'}]).values()))
        assert resolve_pve_flee_intent(player_id=1,encounter_id=encounter,action_token=token,success=True)['fled']
    player=database.get_player(1)
    assert player['hp']==base_hp and player['mana']==base_mp


def test_pvp_roster_lock_binds_preparation_but_pvp_orders_still_reject_cleanse():
    from tests.test_pxe1_pvp_membership import prepare
    from game.pvp_world import lock_preparation
    from game.pvp_group_runtime import authorize_order
    inv=stock('a25_mana_infusion');use_inventory_consumable(1,intent(inv))
    conn,encounter=prepare();conn.execute('BEGIN IMMEDIATE')
    assert pending_slot(conn,1,'preparation')['item_id']=='a25_mana_infusion'
    lock_preparation(conn,engagement_id=encounter,now_ms=1300000)
    row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(encounter,)).fetchone()
    battle=json.loads(row['reason_context'])['battle']
    actor=battle['participants_v1']['1']
    assert actor['max_mana']==112 and actor['mana']==10
    with pytest.raises(ActionRejected,match='invalid_action'):
        authorize_order(conn,row,battle,1,{'kind':'cleanse','item_id':'a25_cleanse_draught'})
    assert pending_slot(conn,1,'preparation')['item_id'] is None
    conn.rollback();conn.close()


def test_replacement_confirmation_recovers_success_after_lost_ack_and_token_cleanup():
    from handlers.inventory import handle_inventory_buttons
    a=stock('a25_dry_ration');b=stock('a25_hunters_stew')
    use_inventory_consumable(1,intent(a))
    query=SimpleNamespace(from_user=SimpleNamespace(id=1),data=f'inv_use_{intent(b)}_supplies',answer=AsyncMock(),edit_message_text=AsyncMock())
    asyncio.run(handle_inventory_buttons(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={})))
    query.data=query.edit_message_text.call_args.kwargs['reply_markup'].inline_keyboard[0][0].callback_data
    query.answer=AsyncMock(side_effect=TimeoutError('lost ack'))
    with pytest.raises(TimeoutError,match='lost ack'):
        asyncio.run(handle_inventory_buttons(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={})))
    conn=database.get_connection()
    callback_token=query.data.split('_')[2]
    assert conn.execute('SELECT 1 FROM economy_action_receipts WHERE player_id=1 AND request_id=?',('ui:'+callback_token,)).fetchone()
    conn.execute('DELETE FROM player_ui_actions WHERE player_id=1');conn.commit();conn.close()
    query.answer=AsyncMock();query.edit_message_text=AsyncMock()
    asyncio.run(handle_inventory_buttons(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={})))
    assert query.edit_message_text.await_count==1
    conn=database.get_connection()
    assert pending_slot(conn,1,'food')['revision']==2
    assert conn.execute('SELECT quantity FROM inventory WHERE id=?',(b,)).fetchone()[0]==2
    conn.close()


def test_accepted_draught_still_spends_opportunity_when_earlier_ally_cleanses_first():
    from tests.test_pxe1_pve_world_tick import started_group
    from tests.test_pxe1_combat_order_replay import consume
    from game import pve_live
    from game.combat_orders import issue_combat_intents
    conn=database.get_connection()
    inv=conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (777,'a25_cleanse_draught',3)").lastrowid
    conn.commit();conn.close()
    encounter,_=started_group()
    state,mob=pve_live.load_active_pve_encounter(encounter_id=encounter)
    healer=state['participant_states_v1']['1'];healer['family']='holy_staff';healer['skill_ranks']['cleanse']=1;healer['mana']=100
    consumer=state['participant_states_v1']['777']
    consumer['effects']=[{'kind':'poison','source_id':'enemy','duration':3,'value':0,'raw_tick':1,'created_side_index':0}]
    conn=database.get_connection();conn.execute('UPDATE pve_encounters SET battle_state_json=? WHERE encounter_id=?',(json.dumps(state),encounter));conn.commit();conn.close()
    for player_id,action in [(1,{'kind':'skill','skill_id':'cleanse','item_id':None,'target_info':{'id':777}}),
                             (777,{'kind':'cleanse','skill_id':None,'item_id':'a25_cleanse_draught','target_info':{'id':777}})]:
        with patch('time.time',return_value=1013):
            token=next(iter(issue_combat_intents(player_id,encounter_id=encounter,turn_revision=state['turn_revision'],deadline_at=state['side_deadline_at'],actions=[action]).values()))
        assert consume(player_id,token,1013)['accepted']
    pve_live.reset_solo_pve_runtime_store();state,mob=pve_live.load_active_pve_encounter(encounter_id=encounter)
    now=datetime.fromtimestamp(1013,timezone.utc)
    pve_live.ensure_runtime_for_battle(player_id=1,battle_state=state,mob=mob,now=now)
    with patch('game.pve_live._utc_now',return_value=now):
        assert pve_live.resolve_current_side_if_ready(player_id=1,battle_state=state,
            on_player_action=lambda action:pve_live._dispatch_v1_player_action(action,battle_state=state),on_enemy_action=lambda action:None)
    assert state['participant_states_v1']['777']['opportunity_index']==1
    assert not any(e['kind']=='poison' for e in state['participant_states_v1']['777']['effects'])
    event=next(e for e in state['combat_events_v1'] if e['kind']=='consumable_cleanse')
    assert event['removed'] is False
    conn=database.get_connection();assert conn.execute('SELECT quantity FROM inventory WHERE id=?',(inv,)).fetchone()[0]==2;conn.close()
