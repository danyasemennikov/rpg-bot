import asyncio,json
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

import pytest
from database import get_connection
from game.pve_live import join_open_world_pve_encounter,process_due_pve_formations,process_due_pve_world_sides,load_active_pve_encounter,_sync_v1_to_legacy_projection,persist_solo_pve_encounter_state
from handlers.combat_delivery import deliver_pve_updates
from tests.test_pxe1_encounter_lifecycle import prepare
from tests.test_pxe1_pve_world_tick import started


def bot():
    return SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=80)),edit_message_text=AsyncMock(return_value=SimpleNamespace(message_id=80)))


def test_delivery_bound_excludes_unchanged_formations_before_selecting_new_member():
    from game.pve_live import list_location_available_spawn_instances,create_or_load_open_world_pve_encounter
    from game.mobs import get_mob
    from game.combat import init_battle
    from database import get_player
    from game.player_ui import record_surface
    from handlers.combat_delivery import formation_revision
    first,_=prepare()
    conn=get_connection()
    row=conn.execute('SELECT * FROM pve_encounters WHERE encounter_id=?',(first,)).fetchone()
    record_surface(1,kind='pve',ref=first,revision=formation_revision(row,1001000),chat_id=1,message_id=10)
    conn.close()
    source=next(s for s in list_location_available_spawn_instances(location_id='westwild_n1'))
    with patch('time.time',return_value=1001):
        mob=get_mob(source['mob_id'])
        second,_=create_or_load_open_world_pve_encounter(owner_player_id=777,location_id='westwild_n1',
            mob_id=source['mob_id'],mob=mob,battle_state=init_battle(dict(get_player(777)),mob),spawn_instance_id=source['spawn_instance_id'])
        transport=bot()
        asyncio.run(deliver_pve_updates(transport,now_ms=1001000,limit=1))
    assert transport.send_message.await_count==1
    assert transport.send_message.call_args.args[0]==777
    assert transport.edit_message_text.await_count==0


def test_pvp_delivery_bound_excludes_unchanged_engagement_before_selecting_new_members():
    from tests.test_pxe1_pvp_group_runtime import locked
    from game.pvp_world import create_preparation,lock_preparation
    from game.pvp_live import pending_pvp_live_delivery
    from game.player_ui import record_surface
    conn,e=locked()
    for player_id in (1,2,3,777):
        record_surface(player_id,kind='pvp',ref=str(e),revision=1,chat_id=player_id,message_id=10)
    conn.execute('BEGIN IMMEDIATE')
    second=create_preparation(conn,attacker_id=4,defender_id=5,location_id='westwild_n4',now_ms=1000000)
    lock_preparation(conn,engagement_id=second,now_ms=1300000);conn.commit();conn.close()
    assert [r['id'] for r in pending_pvp_live_delivery(limit=1)]==[second]


def test_formation_delivery_only_creation_eight_four_and_start_and_no_token_churn():
    from game.build_progression import migrate_character_builds_v1
    migrate_character_builds_v1()
    encounter,_=prepare()
    transport=bot()
    for second in (1000,1001,1002,1003,1004,1005,1006,1007,1008,1009,1010,1011):
        with patch('time.time',return_value=second):
            asyncio.run(deliver_pve_updates(transport,now_ms=second*1000))
    assert transport.send_message.await_count==1
    assert transport.edit_message_text.await_count==2
    assert '12' in transport.send_message.call_args.args[1]
    assert '8' in transport.edit_message_text.call_args_list[0].args[0]
    assert '4' in transport.edit_message_text.call_args_list[1].args[0]
    assert encounter not in transport.send_message.call_args.args[1]
    with patch('time.time',return_value=1012):
        updates=process_due_pve_formations(now_ms=1012000)
        asyncio.run(deliver_pve_updates(transport,updates,now_ms=1012000))
        conn=get_connection()
        tokens=[r[0] for r in conn.execute("SELECT token FROM player_ui_actions WHERE kind='pxe1_combat_view'")]
        conn.close()
        asyncio.run(deliver_pve_updates(transport,now_ms=1012500))
        conn=get_connection()
        assert [r[0] for r in conn.execute("SELECT token FROM player_ui_actions WHERE kind='pxe1_combat_view'")]==tokens
        conn.close()
    assert transport.send_message.await_count==1
    assert transport.edit_message_text.await_count==3


def test_blocked_member_delivery_retries_without_stopping_actual_combat():
    from game.build_progression import migrate_character_builds_v1
    migrate_character_builds_v1()
    encounter,_=prepare()
    with patch('time.time',return_value=1001): assert join_open_world_pve_encounter(encounter_id=encounter,player_id=777)[0]
    updates=process_due_pve_formations(now_ms=1012000)
    transport=bot();transport.send_message.side_effect=[RuntimeError('blocked'),SimpleNamespace(message_id=81),SimpleNamespace(message_id=82)]
    with patch('time.time',return_value=1013):
        asyncio.run(deliver_pve_updates(transport,updates,now_ms=1013000))
        asyncio.run(deliver_pve_updates(transport,now_ms=1014000))
    assert transport.send_message.await_count==3
    with patch('game.pve_live._utc_now',return_value=datetime.fromtimestamp(1027,timezone.utc)):
        assert process_due_pve_world_sides(now_ms=1027000)[0]['phase']=='active'
    assert load_active_pve_encounter(encounter_id=encounter)[0]['turn_revision']>1


def test_victory_updates_same_card_once_with_existing_reward_receipt():
    encounter,_=started();transport=bot()
    with patch('time.time',return_value=1013): asyncio.run(deliver_pve_updates(transport,now_ms=1013000))
    state,mob=load_active_pve_encounter(encounter_id=encounter)
    for enemy in state['enemy_states_v1']: enemy['hp']=0;enemy['dead']=True
    _sync_v1_to_legacy_projection(state)
    assert persist_solo_pve_encounter_state(encounter_id=encounter,battle_state=state,mob=mob)
    updates=process_due_pve_world_sides(now_ms=1014000)
    with patch('time.time',return_value=1014):
        asyncio.run(deliver_pve_updates(transport,updates,now_ms=1014000))
        asyncio.run(deliver_pve_updates(transport,updates,now_ms=1014000))
    assert transport.send_message.await_count==1
    assert transport.edit_message_text.await_count==1
    conn=get_connection()
    assert conn.execute('SELECT surface_kind FROM player_pxe1_ui WHERE player_id=1').fetchone()[0]=='pve_result'
    assert conn.execute('SELECT COUNT(*) FROM pve_reward_settlements').fetchone()[0]==1
    conn.close()


def test_manual_group_defeat_uses_shared_owner_and_personal_surface():
    from game.build_progression import migrate_character_builds_v1
    from handlers.battle import _resolve_post_attack_combat_resolution
    from database import get_player
    migrate_character_builds_v1();encounter,_=prepare()
    with patch('time.time',return_value=1001): assert join_open_world_pve_encounter(encounter_id=encounter,player_id=777)[0]
    process_due_pve_formations(now_ms=1012000)
    transport=bot()
    with patch('time.time',return_value=1013): asyncio.run(deliver_pve_updates(transport,now_ms=1013000))
    state,mob=load_active_pve_encounter(encounter_id=encounter)
    state['participant_states_v1']['1'].update(hp=0,dead=True)
    _sync_v1_to_legacy_projection(state)
    query=SimpleNamespace(message=SimpleNamespace(chat_id=1,message_id=80),answer=AsyncMock())
    context=SimpleNamespace(bot=transport,user_data={})
    with patch('time.time',return_value=1013),patch('game.pve_live._utc_now',return_value=datetime.fromtimestamp(1013,timezone.utc)):
        assert asyncio.run(_resolve_post_attack_combat_resolution(query,context,1,dict(get_player(1)),mob,state,'en'))
    conn=get_connection()
    assert conn.execute('SELECT COUNT(*) FROM economy_action_receipts WHERE request_id=?',(f'pve_death:{encounter}:1',)).fetchone()[0]==1
    assert conn.execute('SELECT surface_kind FROM player_pxe1_ui WHERE player_id=1').fetchone()[0]=='pve_result'
    assert conn.execute('SELECT in_battle FROM players WHERE telegram_id=777').fetchone()[0]==1
    conn.close()
    assert 'battle' not in context.user_data


def test_pvp_all_four_members_receive_one_card_and_dead_actor_stays_released():
    from game.pvp_live import _deliver_pxe1_pvp_event
    from tests.test_pxe1_pvp_group_runtime import locked,submit
    conn,e=locked();row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(e,)).fetchone()
    transport=bot()
    context=json.loads(row['reason_context'])
    with patch('time.time',return_value=1301):
        asyncio.run(_deliver_pxe1_pvp_event(transport,{'row':row,'payload':context}))
        asyncio.run(_deliver_pxe1_pvp_event(transport,{'row':row,'payload':context}))
    assert transport.send_message.await_count==4
    submit(conn,e,1,{'kind':'normal','target_id':777,'manual':True})
    status,context=submit(conn,e,2,{'kind':'guard','target_id':2,'manual':True})
    assert status=='resolved'
    with patch('time.time',return_value=1302):
        asyncio.run(_deliver_pxe1_pvp_event(transport,{'row':row,'payload':context}))
    assert transport.edit_message_text.await_count==4
    assert conn.execute('SELECT surface_kind FROM player_pxe1_ui WHERE player_id=777').fetchone()[0]=='pvp_result'
    status,context=submit(conn,e,3,{'kind':'guard','target_id':3,'manual':True})
    with patch('time.time',return_value=1303): asyncio.run(_deliver_pxe1_pvp_event(transport,{'row':row,'payload':context}))
    assert transport.edit_message_text.await_count==7
    assert 777 not in [c.kwargs['chat_id'] for c in transport.edit_message_text.call_args_list[-3:]]
    conn.close()
