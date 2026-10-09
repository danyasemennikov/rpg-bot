"""Regressions for the seven confirmed PR237 independent review findings."""
import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest

from tests.conftest import isolated_sqlite_db
from tests.test_pxe1_pvp_group_runtime import locked, submit
from database import get_player
from game.pvp_world import create_preparation, invite, respond
from handlers.pvp_group import live_card
from handlers.location import handle_location_buttons


def test_emitted_pvp_action_routes_to_target_selection():
    conn, encounter = locked(defenders=1)
    row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (encounter,)).fetchone()
    with patch('time.time', return_value=1301):
        _, keyboard = live_card(row, json.loads(row['reason_context']), 2, 'en')
        callback = keyboard.inline_keyboard[0][0].callback_data
        query = SimpleNamespace(data=callback, from_user=SimpleNamespace(id=2),
            message=SimpleNamespace(chat_id=2, message_id=100),
            edit_message_text=AsyncMock(), answer=AsyncMock())
        update = SimpleNamespace(callback_query=query, effective_user=query.from_user)
        context = SimpleNamespace(user_data={}, bot=SimpleNamespace(send_message=AsyncMock()))
        asyncio.run(handle_location_buttons(update, context))
    assert query.edit_message_text.called
    conn.close()


@pytest.mark.parametrize('lang', ['ru', 'en', 'es'])
@pytest.mark.parametrize('shape,actor', [(1,1),(1,777),(2,1),(2,2),(2,777),(3,1),(3,2),(3,777),(3,3)])
@pytest.mark.parametrize('selection', ['normal', 'skills', 'guard'])
def test_current_pvp_emitted_selection_and_commit(lang, shape, actor, selection):
    from tests.test_pxe1_pvp_membership import prepare
    from game.pvp_world import lock_preparation
    if shape == 1:
        conn, encounter = prepare()
        conn.execute('BEGIN IMMEDIATE')
        lock_preparation(conn, engagement_id=encounter, now_ms=1300000)
        conn.commit()
    else:
        conn, encounter = locked(defenders=shape-1)
    row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (encounter,)).fetchone()
    context_value = json.loads(row['reason_context'])
    # Defender controls become available on their actual side, without editing
    # the runtime snapshot or bypassing callback authorization.
    if actor in (777,3):
        submit(conn,encounter,1,{'kind':'guard','target_id':1,'manual':True})
        if shape>1: submit(conn,encounter,2,{'kind':'guard','target_id':2,'manual':True})
        row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(encounter,)).fetchone()
        context_value = json.loads(row['reason_context'])
    conn.execute('UPDATE players SET lang=? WHERE telegram_id=?',(lang,actor)); conn.commit()
    query = SimpleNamespace(from_user=SimpleNamespace(id=actor),
        message=SimpleNamespace(chat_id=actor,message_id=100),
        edit_message_text=AsyncMock(),answer=AsyncMock())
    update = SimpleNamespace(callback_query=query,effective_user=query.from_user)
    context = SimpleNamespace(user_data={},bot=SimpleNamespace(send_message=AsyncMock(),edit_message_text=AsyncMock()))
    with patch('time.time',return_value=1301), patch('game.pvp_live._utc_now',return_value=datetime.fromtimestamp(1301,timezone.utc)), patch('game.combat_orders.datetime',wraps=datetime) as clock:
        clock.now.return_value=datetime.fromtimestamp(1301,timezone.utc)
        _,keyboard=live_card(row,context_value,actor,lang)
        buttons=[b for r in keyboard.inline_keyboard for b in r if b.callback_data.startswith('pvp_cv_')]
        view='skills' if selection=='skills' else 'action'
        def chosen(button):
            payload=json.loads(conn.execute('SELECT payload FROM player_ui_actions WHERE token=?',(button.callback_data[7:],)).fetchone()[0])
            return payload['view']==view and (view=='skills' or payload.get('action_id')==selection)
        query.data=next(b.callback_data for b in buttons if chosen(b))
        before=dict(get_player(actor))
        asyncio.run(handle_location_buttons(update,context))
        keyboard=query.edit_message_text.call_args.kwargs['reply_markup']
        if selection=='skills':
            query.data=keyboard.inline_keyboard[0][0].callback_data
            asyncio.run(handle_location_buttons(update,context))
            keyboard=query.edit_message_text.call_args.kwargs['reply_markup']
        assert dict(get_player(actor))==before  # Selection is read-only.
        query.data=keyboard.inline_keyboard[0][0].callback_data
        assert query.data.startswith('pvp_v1_')
        asyncio.run(handle_location_buttons(update,context))
    assert conn.execute('SELECT COUNT(*) FROM combat_orders_v1 WHERE encounter_id=? AND actor_id=? AND turn_revision=?',
                        (str(encounter),actor,context_value['battle']['turn_revision'])).fetchone()[0]==1
    conn.close()


@pytest.mark.parametrize('token_state',['expired','stale_side','legacy_discriminator'])
def test_old_pvp_read_selection_never_spends_resources(token_state):
    conn,encounter=locked()
    row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(encounter,)).fetchone()
    with patch('time.time',return_value=1301):
        _,kb=live_card(row,json.loads(row['reason_context']),2,'en')
        callback=kb.inline_keyboard[0][0].callback_data
    if token_state=='expired':
        conn.execute('UPDATE player_ui_actions SET expires_at=1300 WHERE token=?',(callback.removeprefix('pvp_cv_'),));conn.commit()
    elif token_state=='legacy_discriminator':
        conn.execute('UPDATE pvp_engagements SET world_model_version=0 WHERE id=?',(encounter,));conn.commit()
    else:
        submit(conn,encounter,1,{'kind':'guard','target_id':1,'manual':True})
        submit(conn,encounter,2,{'kind':'guard','target_id':2,'manual':True})
    before=[tuple(r) for r in conn.execute('SELECT hp,mana,exp,gold FROM players ORDER BY telegram_id')]
    orders=conn.execute('SELECT COUNT(*) FROM combat_orders_v1').fetchone()[0]
    query=SimpleNamespace(data=callback,from_user=SimpleNamespace(id=2),
        message=SimpleNamespace(chat_id=2,message_id=100),edit_message_text=AsyncMock(),answer=AsyncMock())
    with patch('time.time',return_value=1301):
        asyncio.run(handle_location_buttons(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={})))
    assert before==[tuple(r) for r in conn.execute('SELECT hp,mana,exp,gold FROM players ORDER BY telegram_id')]
    assert conn.execute('SELECT COUNT(*) FROM combat_orders_v1').fetchone()[0]==orders
    assert query.answer.called
    conn.close()


def test_surviving_ally_can_accept_a_later_engagement():
    conn, encounter = locked(defenders=1)
    submit(conn, encounter, 1, {'kind':'normal','target_id':777,'manual':True})
    assert submit(conn, encounter, 2, {'kind':'guard','target_id':2,'manual':True})[0] == 'finished'
    assert get_player(2)['in_battle'] == 0
    conn.execute('BEGIN IMMEDIATE')
    later = create_preparation(conn, attacker_id=4, defender_id=5,
        location_id='westwild_n4', now_ms=1400000, seed='02'*16)
    invite(conn, engagement_id=later, principal_id=4, ally_id=2, now_ms=1401000)
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    try:
        respond(conn, engagement_id=later, ally_id=2, accepted=True, now_ms=1402000)
        conn.commit()
    finally:
        conn.close()


def test_defeated_ally_rejoins_before_old_terminal_and_new_commitment_survives():
    from game.pvp_world import encoded, reconcile_settled_memberships
    from game.pvp_group_runtime import validate_live_group
    from game.travel_runtime import preview_travel,start_travel_session,advance_travel_edge
    conn,encounter=locked()
    row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(encounter,)).fetchone()
    roster=row['locked_roster_json']
    context=json.loads(row['reason_context'])
    context['battle']['participants_v1']['2']['hp']=1
    context['battle']['participants_v1']['3']['hp']=1
    from game.locations import WORLD_LOCATIONS
    conn.executemany('INSERT OR IGNORE INTO player_location_discovery(telegram_id,location_id) VALUES (2,?)',[(node,) for node in WORLD_LOCATIONS])
    conn.execute('UPDATE pvp_engagements SET reason_context=? WHERE id=?',(encoded(context),encounter));conn.commit()
    submit(conn,encounter,1,{'kind':'guard','target_id':1,'manual':True})
    submit(conn,encounter,2,{'kind':'guard','target_id':2,'manual':True})
    submit(conn,encounter,777,{'kind':'normal','target_id':2,'manual':True},now=1302000)
    assert submit(conn,encounter,3,{'kind':'guard','target_id':3,'manual':True},now=1302000)[0]=='resolved'
    assert conn.execute('SELECT status FROM pvp_engagement_reinforcements WHERE engagement_id=? AND ally_id=2',(encounter,)).fetchone()[0]=='settled'
    validate_live_group(conn,conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(encounter,)).fetchone())
    conn.execute('BEGIN IMMEDIATE')
    route=start_travel_session(conn,2,preview_travel(conn,2,'westwild_n4'),request_id='return-after-defeat',now_ms=1303000)
    while route['status']=='running':
        session=conn.execute('SELECT * FROM player_travel_sessions WHERE session_id=?',(route['session_id'],)).fetchone()
        route=advance_travel_edge(conn,route['session_id'],now_ms=session['next_due_ms'])
    later=create_preparation(conn,attacker_id=4,defender_id=5,location_id='westwild_n4',now_ms=1400000,seed='02'*16)
    invite(conn,engagement_id=later,principal_id=4,ally_id=2,now_ms=1401000)
    respond(conn,engagement_id=later,ally_id=2,accepted=True,now_ms=1402000)
    conn.commit()
    assert submit(conn,encounter,1,{'kind':'normal','target_id':777,'manual':True},now=1303000)[0]=='resolved'
    submit(conn,encounter,3,{'kind':'guard','target_id':3,'manual':True},now=1304000)
    for attempt in range(20):
        result=submit(conn,encounter,1,{'kind':'normal','target_id':3,'manual':True},now=1305000+attempt*1000)
        if result[0]=='finished':
            break
        submit(conn,encounter,3,{'kind':'guard','target_id':3,'manual':True},now=1305000+attempt*1000)
    assert result[0]=='finished'
    conn.execute('BEGIN IMMEDIATE')
    assert reconcile_settled_memberships(conn)==0
    conn.commit()
    assert conn.execute('SELECT status FROM pvp_engagement_reinforcements WHERE engagement_id=? AND ally_id=2',(later,)).fetchone()[0]=='accepted'
    assert conn.execute('SELECT locked_roster_json FROM pvp_engagements WHERE id=?',(encounter,)).fetchone()[0]==roster
    conn.close()


def test_existing_settled_leak_is_repaired_idempotently_without_losing_history():
    from game.pvp_world import reconcile_settled_memberships
    conn,encounter=locked(defenders=1)
    submit(conn,encounter,1,{'kind':'normal','target_id':777,'manual':True})
    submit(conn,encounter,2,{'kind':'guard','target_id':2,'manual':True})
    conn.execute("UPDATE pvp_engagement_reinforcements SET status='locked' WHERE engagement_id=?",(encounter,));conn.commit()
    before=conn.execute('SELECT result_json FROM pvp_group_settlements_pxe1 WHERE engagement_id=?',(encounter,)).fetchone()[0]
    conn.execute('BEGIN IMMEDIATE')
    assert reconcile_settled_memberships(conn)==1
    assert reconcile_settled_memberships(conn)==0
    conn.commit()
    assert conn.execute('SELECT result_json FROM pvp_group_settlements_pxe1 WHERE engagement_id=?',(encounter,)).fetchone()[0]==before
    assert conn.execute('SELECT COUNT(*) FROM pvp_engagement_reinforcements WHERE engagement_id=?',(encounter,)).fetchone()[0]==1
    conn.close()


def test_dangerous_arrival_consumes_respawn_protection():
    from database import get_connection
    from game.locations import get_location_security_tier
    from game.travel_runtime import preview_travel, start_travel_session, advance_travel_edge
    conn = get_connection()
    assert get_location_security_tier('westwild_n4') == 'frontier'
    conn.execute("UPDATE players SET location_id='westwild_n3', pvp_respawn_protection_until=2000 WHERE telegram_id=1")
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    session = start_travel_session(conn, 1, preview_travel(conn, 1, 'westwild_n4'), request_id='danger-reentry', now_ms=1000000)
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    assert advance_travel_edge(conn, session['session_id'], now_ms=1015000)['status'] == 'arrived'
    conn.commit()
    assert get_player(1)['pvp_respawn_protection_until'] == 0
    conn.close()


@pytest.mark.parametrize('operation',['advance','stop','recovery'])
@pytest.mark.parametrize('origin,destination,expected',[
    ('westwild_n3','westwild_n4',0),('hub_westwild','westwild_n5',2000),
    ('westwild_n1','capital_city',2000)])
def test_arrival_protection_is_atomic_at_normal_stop_and_recovery_boundaries(operation,origin,destination,expected):
    from database import get_connection
    from game.travel_runtime import preview_travel,start_travel_session,advance_travel_edge,stop_travel_session
    conn=get_connection()
    conn.execute('UPDATE players SET location_id=?,pvp_respawn_protection_until=2000 WHERE telegram_id=1',(origin,));conn.commit()
    before=conn.execute('SELECT location_visit_revision FROM players WHERE telegram_id=1').fetchone()[0]
    conn.execute('BEGIN IMMEDIATE')
    session=start_travel_session(conn,1,preview_travel(conn,1,destination),request_id='protection:'+operation,now_ms=1000000)
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    if operation=='stop':
        result=stop_travel_session(conn,1,session['session_id'],now_ms=1015000)
    else:
        result=advance_travel_edge(conn,session['session_id'],now_ms=1015000,recovering=operation=='recovery')
    assert result['status']=='arrived'
    conn.rollback()
    assert get_player(1)['location_id']==origin
    assert get_player(1)['pvp_respawn_protection_until']==2000
    conn.execute('BEGIN IMMEDIATE')
    advance_travel_edge(conn,session['session_id'],now_ms=1015000,recovering=operation=='recovery')
    conn.commit()
    player=get_player(1)
    assert player['location_id']==destination
    assert player['pvp_respawn_protection_until']==expected
    assert player['location_visit_revision']==before+1
    conn.close()


def test_discovered_aster_is_selectable_from_map():
    from database import get_connection
    from handlers.world_views import map_card
    conn=get_connection()
    conn.execute("UPDATE players SET location_id='hub_westwild' WHERE telegram_id=1")
    conn.execute("INSERT OR IGNORE INTO player_location_discovery(telegram_id,location_id) VALUES (1,'capital_city')")
    conn.commit()
    player=dict(get_player(1))
    pending=[('world',0)]; visited=set(); destinations=set()
    while pending:
        region,page=pending.pop()
        if (region,page) in visited: continue
        visited.add((region,page))
        _,kb=map_card(player,world=region=='world',region=None if region=='world' else region,page=page)
        for row in kb.inline_keyboard:
            for button in row:
                data=button.callback_data
                if data.startswith('goto_'): destinations.add(data[5:])
                elif data.startswith('px:mapregion:'):
                    region_value,page_value=data.removeprefix('px:mapregion:').rsplit(':',1)
                    pending.append((region_value,int(page_value)))
                elif data.startswith('px:world:'): pending.append(('world',int(data.removeprefix('px:world:'))))
    conn.close()
    assert 'capital_city' in destinations, sorted(destinations)


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_emitted_elmor_world_aster_preview_and_start(lang):
    from handlers.activities import handle_activity_buttons
    from tests.test_pxe1_travel import prepare
    from handlers.world_views import map_card
    from game.i18n import t
    conn=prepare()
    conn.execute('UPDATE players SET lang=? WHERE telegram_id=1',(lang,));conn.commit()
    player=dict(get_player(1))
    query=SimpleNamespace(from_user=SimpleNamespace(id=1),message=SimpleNamespace(chat_id=1,message_id=100),
        edit_message_text=AsyncMock(),answer=AsyncMock())
    context=SimpleNamespace(user_data={},bot=SimpleNamespace(send_message=AsyncMock(),edit_message_text=AsyncMock()))
    update=SimpleNamespace(callback_query=query,effective_user=query.from_user)
    _,kb=map_card(player)
    query.data=next(b.callback_data for row in kb.inline_keyboard for b in row if b.callback_data=='px:world:0')
    with patch('time.time',return_value=1000):
        asyncio.run(handle_activity_buttons(update,context))
        kb=query.edit_message_text.call_args.kwargs['reply_markup']
        query.data=next(b.callback_data for row in kb.inline_keyboard for b in row if b.callback_data=='px:mapregion:core:0')
        asyncio.run(handle_activity_buttons(update,context))
        kb=query.edit_message_text.call_args.kwargs['reply_markup']
        query.data=next(b.callback_data for row in kb.inline_keyboard for b in row if b.callback_data=='goto_capital_city')
        asyncio.run(handle_location_buttons(update,context))
        text=query.edit_message_text.call_args.args[0]
        kb=query.edit_message_text.call_args.kwargs['reply_markup']
        assert t('pxe1.map.route_preview',lang,hops=6,time='1:45') in text
        assert get_player(1)['location_id']=='hub_westwild'
        assert not conn.execute('SELECT 1 FROM player_travel_sessions').fetchone()
        query.data=next(b.callback_data for row in kb.inline_keyboard for b in row if b.callback_data.startswith('px:travel:'))
        asyncio.run(handle_activity_buttons(update,context))
    assert conn.execute('SELECT destination_location_id,status FROM player_travel_sessions').fetchone()[:]==('capital_city','running')
    assert get_player(1)['location_id']=='hub_westwild'
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_aster_browsing_does_not_discover_unknown_route_or_select_current_place(lang):
    from database import get_connection
    from handlers.world_views import map_card
    from game.action_receipts import ActionRejected
    from game.travel_runtime import preview_travel
    conn=get_connection()
    conn.execute("UPDATE players SET location_id='hub_westwild',lang=? WHERE telegram_id=1",(lang,));conn.commit()
    before=[tuple(r) for r in conn.execute('SELECT * FROM player_location_discovery')]
    _,kb=map_card(dict(get_player(1)),region='core')
    assert 'goto_capital_city' in [b.callback_data for row in kb.inline_keyboard for b in row]
    with pytest.raises(ActionRejected,match='no_known_route'):
        preview_travel(conn,1,'capital_city')
    assert before==[tuple(r) for r in conn.execute('SELECT * FROM player_location_discovery')]
    _,kb=map_card({**dict(get_player(1)),'location_id':'capital_city'},region='core')
    assert 'goto_capital_city' not in [b.callback_data for row in kb.inline_keyboard for b in row]
    conn.close()


@pytest.mark.parametrize('crash_side', [1, 2])
def test_committed_nonterminal_pve_side_survives_process_restart(crash_side):
    from datetime import datetime, timezone
    from database import get_connection
    from tests.test_pxe1_pve_world_tick import started
    from game import pve_live
    encounter, _ = started()
    original = pve_live.persist_turn_result
    class SimulatedProcessExit(BaseException):
        pass
    def stop_after_commit(**kwargs):
        result = original(**kwargs)
        assert result['applied']
        if kwargs['turn_revision'] == crash_side:
            raise SimulatedProcessExit()
        return result
    with patch('game.pve_live._utc_now', return_value=datetime.fromtimestamp(1027, timezone.utc)):
        with patch('game.pve_live.persist_turn_result', side_effect=stop_after_commit):
            try:
                pve_live.process_due_pve_world_sides(now_ms=1027000, encounter_id=encounter)
            except SimulatedProcessExit:
                pass
            else:
                raise AssertionError('Crash point not reached')
    conn = get_connection()
    assert conn.execute('SELECT COUNT(*) FROM combat_turn_results_v1 WHERE encounter_id=?', (encounter,)).fetchone()[0] == crash_side
    completed=json.loads(conn.execute('SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0])
    pve_live.reset_solo_pve_runtime_store()
    with patch('game.pve_live._utc_now', return_value=datetime.fromtimestamp(1028, timezone.utc)):
        outcome = pve_live.process_due_pve_world_sides(now_ms=1028000, encounter_id=encounter)
    assert not outcome or outcome[0]['phase'] == 'active', outcome
    assert conn.execute('SELECT status FROM pve_encounters WHERE encounter_id=?', (encounter,)).fetchone()[0] == 'active'
    saved=json.loads(conn.execute('SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0])
    assert saved['side_turn_state']=='collecting_orders'
    assert saved['round_index']==completed['round_index']+(1 if crash_side==1 else 0)
    deadline=saved['side_deadline_at']
    pve_live.reset_solo_pve_runtime_store()
    with patch('game.pve_live._utc_now',return_value=datetime.fromtimestamp(1030,timezone.utc)):
        assert pve_live.process_due_pve_world_sides(now_ms=1030000,encounter_id=encounter)==[]
    restored,_=pve_live.load_active_pve_encounter(encounter_id=encounter)
    assert restored['side_deadline_at']==deadline
    conn.close()


@pytest.mark.parametrize('restart', [False, True])
@pytest.mark.parametrize('fault', ['before_result', 'after_vitals', 'after_commit'])
@pytest.mark.parametrize('order_kind', ['timeout', 'basic_attack', 'skill'])
def test_pve_write_fault_preserves_durable_orders_and_retries(fault,restart,order_kind):
    import sqlite3
    from copy import deepcopy
    from database import get_connection
    from tests.test_pxe1_pve_world_tick import started
    from game import pve_live
    encounter,_=started()
    state,mob=pve_live.load_active_pve_encounter(encounter_id=encounter)
    for enemy in state['enemy_states_v1']:
        enemy.update(hp=10000,max_hp=10000)
    pve_live._sync_v1_to_legacy_projection(state)
    assert pve_live.persist_solo_pve_encounter_state(encounter_id=encounter,battle_state=state,mob=mob)
    original=pve_live.persist_turn_result
    vitals=pve_live.persist_pxe1_participant_vitals
    expected={}
    def write(**kwargs):
        expected.update(deepcopy(kwargs['complete_state']))
        if fault=='before_result':
            raise sqlite3.OperationalError('before result')
        result=original(**kwargs)
        if fault=='after_commit':
            raise sqlite3.OperationalError('ambiguous commit')
        return result
    def fail_vitals(conn,ref,snapshot):
        vitals(conn,ref,snapshot)
        raise sqlite3.OperationalError('before commit after vitals')
    with patch('game.pve_live._utc_now',return_value=datetime.fromtimestamp(1013,timezone.utc)):
        if order_kind!='timeout':
            pve_live.ensure_runtime_for_battle(player_id=1,battle_state=state,mob=mob)
            accepted,_=pve_live.submit_player_commit(player_id=1,battle_state=state,
                action_type=order_kind,skill_id='power_strike' if order_kind=='skill' else None,
                target_info={'id':state['enemy_states_v1'][0]['unit_id']})
            assert accepted
    with patch('game.pve_live._utc_now',return_value=datetime.fromtimestamp(1027,timezone.utc)):
        with patch('game.pve_live.persist_turn_result',side_effect=write), patch('game.pve_live.persist_pxe1_participant_vitals',side_effect=fail_vitals if fault=='after_vitals' else vitals):
            assert pve_live.process_due_pve_world_sides(now_ms=1027000,encounter_id=encounter)==[]
        if restart:
            pve_live.reset_solo_pve_runtime_store()
        pve_live.process_due_pve_world_sides(now_ms=1028000,encounter_id=encounter)
    conn=get_connection()
    rows=conn.execute('SELECT turn_revision,state_json FROM combat_turn_results_v1 WHERE encounter_id=? ORDER BY turn_revision',(encounter,)).fetchall()
    assert [r[0] for r in rows]==[1,2]
    committed=json.loads(rows[0]['state_json'])
    for key in ('participant_states_v1','enemy_states_v1','combat_events_v1','side_turn_state','active_side'):
        assert committed.get(key)==expected.get(key)
    before=[tuple(r) for r in conn.execute('SELECT hp,mana,exp,gold FROM players ORDER BY telegram_id')]
    with patch('game.pve_live._utc_now',return_value=datetime.fromtimestamp(1028,timezone.utc)):
        assert pve_live.process_due_pve_world_sides(now_ms=1028000,encounter_id=encounter)==[]
    assert before==[tuple(r) for r in conn.execute('SELECT hp,mana,exp,gold FROM players ORDER BY telegram_id')]
    assert conn.execute('SELECT COUNT(*) FROM combat_turn_results_v1 WHERE encounter_id=?',(encounter,)).fetchone()[0]==2
    conn.close()


@pytest.mark.parametrize('terminal', ['victory', 'death'])
def test_terminal_committed_pve_side_restarts_and_settles_once(terminal):
    from database import get_connection
    from game import pve_live
    from tests.test_pxe1_pve_world_tick import started
    encounter,_=started()
    state,mob=pve_live.load_active_pve_encounter(encounter_id=encounter)
    actor=state['participant_states_v1']['1']
    if terminal=='victory':
        for enemy in state['enemy_states_v1']:
            enemy.update(hp=1,effects=[{'kind':'burn','source_id':1,'duration':3,
                'raw_tick':100,'created_side_index':0,'school':'magic','metadata':{}}])
    else:
        actor.update(hp=1,effects=[{'kind':'burn','source_id':state['enemy_states_v1'][0]['unit_id'],
            'duration':3,'raw_tick':100,'created_side_index':0,'school':'magic','metadata':{}}])
    pve_live._sync_v1_to_legacy_projection(state)
    assert pve_live.persist_solo_pve_encounter_state(encounter_id=encounter,battle_state=state,mob=mob)
    writer=pve_live.persist_turn_result
    def ambiguous(**kwargs):
        result=writer(**kwargs)
        assert result['applied']
        if kwargs['turn_revision']==(2 if terminal=='victory' else 1):
            raise RuntimeError('committed exit')
        return result
    with patch('game.pve_live._utc_now',return_value=datetime.fromtimestamp(1013,timezone.utc)):
        pve_live.ensure_runtime_for_battle(player_id=1,battle_state=state,mob=mob)
        assert pve_live.submit_player_commit(player_id=1,battle_state=state,
            action_type='guard',
            target_info={'id':state['enemy_states_v1'][0]['unit_id']})[0]
        with patch('game.pve_live.persist_turn_result',side_effect=ambiguous):
            assert pve_live.process_due_pve_world_sides(now_ms=1013000,encounter_id=encounter)==[]
        pve_live.reset_solo_pve_runtime_store()
        result=pve_live.process_due_pve_world_sides(now_ms=1014000,encounter_id=encounter)
    assert result[0]['phase']==terminal
    conn=get_connection()
    before=[tuple(r) for r in conn.execute('SELECT hp,mana,exp,gold,location_id FROM players ORDER BY telegram_id')]
    assert conn.execute('SELECT COUNT(*) FROM combat_turn_results_v1 WHERE encounter_id=?',(encounter,)).fetchone()[0]==(2 if terminal=='victory' else 1)
    assert pve_live.process_due_pve_world_sides(now_ms=999999999,encounter_id=encounter)==[]
    assert before==[tuple(r) for r in conn.execute('SELECT hp,mana,exp,gold,location_id FROM players ORDER BY telegram_id')]
    conn.close()


@pytest.mark.parametrize('corruption',['missing_receipt','wrong_phase','missing_open_deadline'])
def test_completed_pve_phase_requires_durable_proof(corruption):
    from database import get_connection
    from game import pve_live
    from tests.test_pxe1_pve_world_tick import started
    encounter,_=started()
    conn=get_connection()
    state=json.loads(conn.execute('SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0])
    state['side_turn_state']='completed' if corruption=='missing_receipt' else 'invalid' if corruption=='wrong_phase' else 'collecting_orders'
    state['side_deadline_at']=None
    conn.execute('UPDATE pve_encounters SET battle_state_json=? WHERE encounter_id=?',(json.dumps(state),encounter));conn.commit()
    assert pve_live.process_due_pve_world_sides(now_ms=1027000,encounter_id=encounter)[0]['phase']=='state_lost'
    assert not conn.execute('SELECT 1 FROM pve_reward_settlements WHERE encounter_id=?',(encounter,)).fetchone()
    conn.close()


@pytest.mark.parametrize('lang', ['ru','en','es'])
def test_gather_activity_reports_remaining_tool_durability(lang):
    from tests.test_pxe1_gathering_sessions import start
    from handlers.activities import activity_card
    from game.gathering_runtime import commit_gathering_tick
    from game.i18n import t
    conn,session_id=start(durability=13)
    conn.execute('BEGIN IMMEDIATE')
    result=commit_gathering_tick(conn,session_id,now_ms=9000)
    conn.commit()
    assert result['tool']['durability']==12 and result['tool']['worn_warning']
    session=dict(conn.execute('SELECT * FROM player_gathering_sessions WHERE session_id=?',(session_id,)).fetchone())
    text,_=activity_card({**dict(get_player(1)),'lang':lang},session,'gather',now_ms=9000)
    conn.close()
    assert t('pxe1.tool.durability',lang,current=12,maximum=60) in text, text


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_gather_threshold_coalesces_until_delivery_then_does_not_repeat(lang):
    from tests.test_pxe1_gathering_sessions import start
    from game.gathering_runtime import commit_gathering_tick,interrupt_gathering_at_startup
    from handlers.activities import activity_card,deliver_activity_updates
    from game.i18n import t
    conn,session_id=start(durability=13)
    conn.execute('UPDATE players SET lang=? WHERE telegram_id=1',(lang,));conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    first=commit_gathering_tick(conn,session_id,now_ms=9000);conn.commit()
    assert first['tool']['worn_warning']
    def session(): return dict(conn.execute('SELECT * FROM player_gathering_sessions WHERE session_id=?',(session_id,)).fetchone())
    warning=t('pxe1.tool.worn_warning',lang)
    for _ in range(2):
        assert activity_card(dict(get_player(1)),session(),'gather',now_ms=9000)[0].count(warning)==1
    bot=SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError('transport down')),
                        edit_message_text=AsyncMock(return_value=SimpleNamespace(message_id=42)))
    with pytest.raises(RuntimeError,match='transport down'):
        asyncio.run(deliver_activity_updates(bot,[first]))
    conn.execute('BEGIN IMMEDIATE')
    second=commit_gathering_tick(conn,session_id,now_ms=17000);conn.commit()
    assert second['tool']['durability']==11 and not second['tool']['worn_warning']
    assert activity_card(dict(get_player(1)),session(),'gather',now_ms=17000)[0].count(warning)==1
    bot.send_message=AsyncMock(return_value=SimpleNamespace(message_id=42))
    asyncio.run(deliver_activity_updates(bot,[second]))
    assert warning in bot.send_message.call_args.args[1]
    assert warning not in activity_card(dict(get_player(1)),session(),'gather',now_ms=17000)[0]
    asyncio.run(deliver_activity_updates(bot,[second]))
    assert bot.send_message.call_count==1 and bot.edit_message_text.call_count==0
    conn.execute('BEGIN IMMEDIATE')
    interrupt_gathering_at_startup(conn,now_ms=18000);conn.commit()
    assert warning not in activity_card(dict(get_player(1)),session(),'gather',now_ms=18000)[0]
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_last_gather_yield_survives_break_and_emitted_recovery_opens_tool(lang):
    from tests.test_pxe1_gathering_sessions import start
    from game.gathering_runtime import commit_gathering_tick
    from handlers.activities import activity_card,handle_activity_buttons
    from game.i18n import t
    conn,session_id=start(durability=1)
    conn.execute('UPDATE players SET lang=? WHERE telegram_id=1',(lang,));conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    result=commit_gathering_tick(conn,session_id,now_ms=9000);conn.commit()
    assert result['status']=='broken' and result['tool']['durability']==0 and result['granted']
    session=dict(conn.execute('SELECT * FROM player_gathering_sessions WHERE session_id=?',(session_id,)).fetchone())
    text,kb=activity_card(dict(get_player(1)),session,'gather',now_ms=9000)
    assert session['yield_total']==1 and t('pxe1.tool.durability',lang,current=0,maximum=60) in text
    query=SimpleNamespace(data=next(b.callback_data for r in kb.inline_keyboard for b in r if b.callback_data=='px:tool:mining'),
        from_user=SimpleNamespace(id=1),message=SimpleNamespace(chat_id=1,message_id=100),edit_message_text=AsyncMock(),answer=AsyncMock())
    asyncio.run(handle_activity_buttons(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={})))
    assert t('pxe1.tool.replacement_cost',lang,gold=12) in query.edit_message_text.call_args.args[0]
    assert conn.execute('SELECT COUNT(*) FROM economy_action_receipts WHERE request_id=?',(f'gather:{session_id}:1',)).fetchone()[0]==1
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
@pytest.mark.parametrize('tier,materials',[(1,{}),(2,{}),(2,{'wood_common':4,'iron_ore':2,'coal':1})])
def test_wilderness_tool_guidance_routes_to_existing_maintenance_and_sources(lang,tier,materials):
    from tests.test_pxe1_tools_economy import prepare
    from handlers.activities import tool_card,handle_activity_buttons
    from handlers.professions import build_material
    from game.i18n import t
    from game.locations import WORLD_LOCATIONS
    from game.travel_runtime import advance_travel_edge
    from game.profession_tools import repair_quote
    conn=prepare(tier=tier,materials=materials)
    conn.execute("UPDATE players SET location_id='old_mine_entrance',lang=? WHERE telegram_id=1",(lang,))
    conn.executemany('INSERT OR IGNORE INTO player_location_discovery(telegram_id,location_id) VALUES (1,?)',[(node,) for node in WORLD_LOCATIONS]);conn.commit()
    quote=repair_quote(conn,1,'mining') if tier>1 else None
    text,kb=tool_card(dict(get_player(1)),'mining')
    assert t('pxe1.tool.broken',lang) in text
    if quote:
        assert t('pxe1.tool.repair_cost',lang,gold=quote['gold']) in text
        if not materials: assert t('pxe1.tool.assisted_repair_explanation',lang) in text
        for b in [b for r in kb.inline_keyboard for b in r if b.callback_data.startswith('pe_m:')]:
            item=b.callback_data.split(':')[1]
            source_text,_=build_material(dict(get_player(1)),item)
            assert source_text
    else: assert t('pxe1.tool.replacement_cost',lang,gold=12) in text
    destination=next(b.callback_data for r in kb.inline_keyboard for b in r if b.callback_data.startswith('goto_'))
    query=SimpleNamespace(data=destination,from_user=SimpleNamespace(id=1),
        message=SimpleNamespace(chat_id=1,message_id=100),edit_message_text=AsyncMock(),answer=AsyncMock())
    update=SimpleNamespace(callback_query=query)
    context=SimpleNamespace(user_data={},bot=SimpleNamespace(send_message=AsyncMock(),edit_message_text=AsyncMock()))
    with patch('time.time',return_value=1000):
        asyncio.run(handle_location_buttons(update,context))
        kb=query.edit_message_text.call_args.kwargs['reply_markup']
        query.data=next(b.callback_data for r in kb.inline_keyboard for b in r if b.callback_data.startswith('px:travel:'))
        asyncio.run(handle_activity_buttons(update,context))
    conn.execute('BEGIN IMMEDIATE')
    session=conn.execute('SELECT * FROM player_travel_sessions WHERE player_id=1').fetchone()
    while session['status']=='running':
        session=advance_travel_edge(conn,session['session_id'],now_ms=session['next_due_ms'])
    conn.commit()
    _,kb=tool_card(dict(get_player(1)),'mining')
    query.data=next(b.callback_data for r in kb.inline_keyboard for b in r if b.callback_data.startswith('px:replace:' if tier==1 else 'px:repair:'))
    before=get_player(1)['gold']
    with patch('time.time',return_value=1100): asyncio.run(handle_activity_buttons(update,context))
    assert conn.execute("SELECT durability FROM player_profession_tools WHERE player_id=1 AND profession_key='mining'").fetchone()[0]==60*tier
    assert get_player(1)['gold']==before-(12 if tier==1 else quote['gold'])
    # Replaying a maintenance control cannot charge or repair again.
    asyncio.run(handle_activity_buttons(update,context))
    assert get_player(1)['gold']==before-(12 if tier==1 else quote['gold'])
    conn.close()


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_repaired_tool_can_cross_threshold_again_in_a_new_session(lang):
    from tests.test_pxe1_tools_economy import prepare
    from game.profession_tools import get_tool,wear_tool,repair_quote,commit_tool_maintenance
    from game.action_receipts import issue_actions
    from game.gathering_runtime import start_gathering_session,commit_gathering_tick,stop_gathering_session,interrupt_gathering_at_startup
    from game.location_threats import arrive_at_location
    from handlers.activities import activity_card,deliver_activity_updates
    from game.i18n import t
    conn=prepare(tier=2,durability=25)
    conn.execute('UPDATE players SET lang=? WHERE telegram_id=1',(lang,));conn.commit()
    def crossing(request,now):
        conn.execute('BEGIN IMMEDIATE')
        arrive_at_location(conn,1,'old_mine_entrance',now_ms=now)
        session=start_gathering_session(conn,1,'mining',location_id='old_mine_entrance',request_id=request,now_ms=now,seed='00'*16)['session']
        tick=commit_gathering_tick(conn,session['session_id'],now_ms=now+8000)
        conn.commit()
        assert tick['tool']['worn_warning'] and tick['tool']['durability']==24
        return tick
    first=crossing('before-repair',1000)
    conn.execute('BEGIN IMMEDIATE')
    stop_gathering_session(conn,1,first['session_id'],now_ms=9001)
    arrive_at_location(conn,1,'hub_westwild',now_ms=9002);conn.commit()
    payload=json.dumps(repair_quote(conn,1,'mining'),sort_keys=True,separators=(',',':'))
    token=issue_actions(1,'tool_repair_pxe1',[payload])[payload]
    assert commit_tool_maintenance(1,action_token=token)['status']=='repaired'
    conn.execute('BEGIN IMMEDIATE')
    for _ in range(95):
        assert not wear_tool(conn,get_tool(conn,1,'mining'),now_ms=10000)['worn_warning']
    conn.commit()
    second=crossing('after-repair',20000)
    conn.execute('BEGIN IMMEDIATE')
    interrupt_gathering_at_startup(conn,now_ms=28001);conn.commit()
    session=dict(conn.execute('SELECT * FROM player_gathering_sessions WHERE session_id=?',(second['session_id'],)).fetchone())
    warning=t('pxe1.tool.worn_warning',lang)
    assert warning in activity_card(dict(get_player(1)),session,'gather',now_ms=28001)[0]
    bot=SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=42)))
    asyncio.run(deliver_activity_updates(bot,[second]))
    session=dict(conn.execute('SELECT * FROM player_gathering_sessions WHERE session_id=?',(second['session_id'],)).fetchone())
    assert warning not in activity_card(dict(get_player(1)),session,'gather',now_ms=28001)[0]
    conn.close()


def test_detail_guard_enforces_frozen_three_thousand_utf16_units():
    from game.player_ui import validate_surface
    from telegram import InlineKeyboardMarkup
    validate_surface('a'*3000,InlineKeyboardMarkup([]),long_detail=True)
    with pytest.raises(ValueError,match='surface_text_budget'):
        validate_surface('a'*3001,InlineKeyboardMarkup([]),long_detail=True)


@pytest.mark.parametrize('inject_failure',[False,True])
def test_transient_pve_result_write_failure_retries_same_side(inject_failure):
    import sqlite3
    from datetime import datetime,timezone
    from database import get_connection
    from tests.test_pxe1_pve_world_tick import started
    from game import pve_live
    encounter,_=started()
    initial=pve_live.load_active_pve_encounter(encounter_id=encounter)[0]['turn_revision']
    with patch('game.pve_live._utc_now',return_value=datetime.fromtimestamp(1027,timezone.utc)):
        if inject_failure:
            with patch('game.pve_live.persist_turn_result',side_effect=sqlite3.OperationalError('simulated transient write failure')):
                assert pve_live.process_due_pve_world_sides(now_ms=1027000,encounter_id=encounter)==[]
        else:
            pve_live.process_due_pve_world_sides(now_ms=1027000,encounter_id=encounter)
        pve_live.process_due_pve_world_sides(now_ms=1028000,encounter_id=encounter)
    conn=get_connection()
    revisions=[r[0] for r in conn.execute('SELECT turn_revision FROM combat_turn_results_v1 WHERE encounter_id=? ORDER BY turn_revision',(encounter,))]
    conn.close()
    assert revisions==[initial,initial+1], {'initial':initial,'committed':revisions}
