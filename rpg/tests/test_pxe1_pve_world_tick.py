import json
from datetime import datetime,timezone
from unittest.mock import patch

from database import get_connection
from game.build_progression import migrate_character_builds_v1
from game.pve_live import (
    _sync_v1_to_legacy_projection,apply_pxe1_pve_death,load_active_pve_encounter,
    persist_solo_pve_encounter_state,process_due_pve_formations,process_due_pve_world_sides,
)
from tests.test_pxe1_encounter_lifecycle import prepare


def started():
    migrate_character_builds_v1()
    encounter,spawn = prepare()
    process_due_pve_formations(now_ms=1012000)
    return encounter,spawn


def test_nine_actor_formation_authorization_resolution_and_settlement():
    from database import create_player
    from game.combat_orders import issue_combat_intents
    from game.pve_live import join_open_world_pve_encounter
    from game.pve_reward_settlement import get_settlement
    from tests.test_pxe1_combat_order_replay import consume
    roster=[1,777,*range(101,108)]
    for actor in roster[2:]:
        create_player(actor,'large_party',f'Actor {actor}',
            dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'),10))
    conn=get_connection()
    conn.execute("UPDATE players SET location_id='westwild_n1'")
    conn.commit()
    migrate_character_builds_v1()
    encounter,_=prepare()
    with patch('time.time',return_value=1001):
        for actor in roster[1:]:
            assert join_open_world_pve_encounter(encounter_id=encounter,player_id=actor)==(True,'joined')
    roster=sorted(roster)
    assert process_due_pve_formations(now_ms=1012000)[0]['player_ids']==roster
    state,_=load_active_pve_encounter(encounter_id=encounter)
    assert set(state['participant_states_v1'])=={str(actor) for actor in roster}
    enemy=state['enemy_states_v1'][0]['unit_id']
    # Arrival order differs from the immutable formation order.
    for actor in reversed(roster):
        with patch('time.time',return_value=1013):
            token=next(iter(issue_combat_intents(actor,encounter_id=encounter,
                turn_revision=state['turn_revision'],deadline_at=state['side_deadline_at'],
                actions=[{'kind':'basic_attack','target_info':{'id':enemy}}]).values()))
        assert consume(actor,token,1013)['accepted']
    with patch('game.pve_live._utc_now',return_value=datetime.fromtimestamp(1013,timezone.utc)):
        result=process_due_pve_world_sides(now_ms=1013000,encounter_id=encounter)
    assert result[0]['phase']=='victory'
    settlement=get_settlement(encounter)
    assert settlement['status']=='applied'
    assert settlement['plan']['eligible_recipient_ids']==roster
    assert conn.execute('SELECT COUNT(*) FROM pve_encounter_participants WHERE encounter_id=? AND status=?',
                        (encounter,'victory')).fetchone()[0]==9
    assert all(not conn.execute('SELECT in_battle FROM players WHERE telegram_id=?',(actor,)).fetchone()[0]
               for actor in roster)
    before=[tuple(conn.execute('SELECT exp,gold,hp FROM players WHERE telegram_id=?',(actor,)).fetchone()) for actor in roster]
    assert process_due_pve_world_sides(now_ms=9999999,encounter_id=encounter)==[]
    assert before==[tuple(conn.execute('SELECT exp,gold,hp FROM players WHERE telegram_id=?',(actor,)).fetchone()) for actor in roster]
    conn.close()


def test_generic_target_and_detail_pages_cover_twenty_three_enemies_and_seventeen_allies():
    from copy import deepcopy
    from database import get_player
    from game.player_ui import validate_surface
    from handlers.combat_views import action_card,details_card
    encounter,_=started()
    state,_=load_active_pve_encounter(encounter_id=encounter)
    actor=state['participant_states_v1']['1']
    state['participant_states_v1']={str(i):{**deepcopy(actor),'actor_id':str(i),'name':f'Actor {i}'} for i in range(1,18)}
    enemy=state['enemy_states_v1'][0]
    state['enemy_states_v1']=[{**deepcopy(enemy),'unit_id':f'enemy-{i}'} for i in range(23)]
    snapshot=deepcopy(state)
    conn=get_connection()
    durable=conn.execute('SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0]
    player=dict(get_player(1))
    for lang in ('ru','en','es'):
        player['lang']=lang
        selected=[]
        with patch('time.time',return_value=1013):
            for page in range(4):
                text,kb=action_card(player,state,'normal',page)
                validate_surface(text,kb,list_view=True)
                targets=[b for row in kb.inline_keyboard for b in row if b.callback_data.startswith('battle_v1_')]
                assert len(targets)==(6 if page<3 else 5)
                for button in targets:
                    action=json.loads(conn.execute('SELECT payload FROM player_ui_actions WHERE token=?',
                        (button.callback_data.removeprefix('battle_v1_'),)).fetchone()[0])
                    selected.append(action['action']['target_info']['id'])
            assert selected==[f'enemy-{i}' for i in range(23)]
            for section,count in (('enemies',23),('allies',17)):
                pages=[details_card(player,state,section,page) for page in range((count+5)//6)]
                for text,kb in pages: validate_surface(text,kb,long_detail=True)
                if section=='allies':
                    combined='\n'.join(text for text,_ in pages)
                    assert all(f'Actor {i} ·' in combined for i in range(1,18))
    assert state==snapshot
    assert conn.execute('SELECT battle_state_json FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0]==durable
    assert not conn.execute('SELECT 1 FROM combat_orders_v1 WHERE encounter_id=?',(encounter,)).fetchone()
    conn.close()


def test_background_timeout_uses_actual_engine_and_durable_orders_without_context():
    encounter,_ = started()
    with patch('game.pve_live._utc_now',return_value=datetime.fromtimestamp(1027,timezone.utc)):
        assert process_due_pve_world_sides(now_ms=1026999)==[]
        results = process_due_pve_world_sides(now_ms=1027000)
    assert len(results)==1 and results[0]['phase']=='active'
    state,mob = load_active_pve_encounter(encounter_id=encounter)
    assert any(event['kind']=='guard' and event['timeout'] for event in state['combat_events_v1'])
    assert any(event['kind'].startswith('enemy') for event in state['combat_events_v1'])
    conn = get_connection()
    assert conn.execute("SELECT COUNT(*) FROM combat_turn_results_v1 WHERE encounter_kind='pve'").fetchone()[0]==2
    assert not conn.execute('SELECT 1 FROM pve_reward_settlements WHERE encounter_id=?',(encounter,)).fetchone()
    conn.close()


def test_background_terminal_victory_runs_existing_t1_t2_and_thirty_second_respawn():
    encounter,spawn = started()
    state,mob = load_active_pve_encounter(encounter_id=encounter)
    for enemy in state['enemy_states_v1']:
        enemy['hp']=0
        enemy['dead']=True
    _sync_v1_to_legacy_projection(state)
    assert persist_solo_pve_encounter_state(encounter_id=encounter,battle_state=state,mob=mob)
    results = process_due_pve_world_sides(now_ms=1013000)
    assert results[0]['phase']=='victory'
    conn = get_connection()
    assert conn.execute('SELECT status FROM pve_reward_settlements WHERE encounter_id=?',(encounter,)).fetchone()[0]=='applied'
    assert conn.execute('SELECT status FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0]=='victory'
    assert conn.execute('SELECT state FROM pve_spawn_instances WHERE spawn_instance_id=?',(spawn['spawn_instance_id'],)).fetchone()[0]=='respawning'
    assert not conn.execute('SELECT in_battle FROM players WHERE telegram_id=1').fetchone()[0]
    assert process_due_pve_world_sides(now_ms=999999999)==[]
    conn.close()


def test_background_defeat_receipt_replays_without_repeated_penalty():
    encounter,spawn = started()
    state,mob = load_active_pve_encounter(encounter_id=encounter)
    actor = state['participant_states_v1']['1']
    actor['hp']=0
    actor['dead']=True
    _sync_v1_to_legacy_projection(state)
    assert persist_solo_pve_encounter_state(encounter_id=encounter,battle_state=state,mob=mob)
    results = process_due_pve_world_sides(now_ms=1013000)
    assert results[0]['phase']=='death'
    conn = get_connection()
    before = tuple(conn.execute('SELECT exp,gold,hp,location_id,travel_revision,location_visit_revision FROM players WHERE telegram_id=1').fetchone())
    apply_pxe1_pve_death(1,encounter,now_ms=1014000)
    assert tuple(conn.execute('SELECT exp,gold,hp,location_id,travel_revision,location_visit_revision FROM players WHERE telegram_id=1').fetchone())==before
    assert conn.execute('SELECT status FROM pve_encounters WHERE encounter_id=?',(encounter,)).fetchone()[0]=='death'
    assert conn.execute('SELECT state FROM pve_spawn_instances WHERE spawn_instance_id=?',(spawn['spawn_instance_id'],)).fetchone()[0]=='respawning'
    conn.close()


def test_partial_defeat_settles_before_next_deadline_and_preserves_survivor():
    from game.pve_live import join_open_world_pve_encounter
    from game.player_activity import player_activity
    migrate_character_builds_v1()
    encounter,_=prepare()
    with patch('time.time',return_value=1001):
        assert join_open_world_pve_encounter(encounter_id=encounter,player_id=777)[0]
    process_due_pve_formations(now_ms=1012000)
    state,mob=load_active_pve_encounter(encounter_id=encounter)
    state['participant_states_v1']['1'].update(hp=0,dead=True)
    survivor=dict(state['participant_states_v1']['777'])
    deadline=state['side_deadline_at']
    _sync_v1_to_legacy_projection(state)
    assert persist_solo_pve_encounter_state(encounter_id=encounter,battle_state=state,mob=mob)
    result=process_due_pve_world_sides(now_ms=1013000,encounter_id=encounter)
    assert result[0]['phase']=='active'
    current,_=load_active_pve_encounter(encounter_id=encounter)
    assert current['participant_states_v1']['777']==survivor
    assert current['side_deadline_at']==deadline
    assert current['side_a_player_ids']==[777]
    conn=get_connection()
    assert player_activity(conn,1) is None
    assert player_activity(conn,777)['kind']=='pve'
    assert not conn.execute('SELECT 1 FROM combat_turn_results_v1').fetchone()
    assert conn.execute('SELECT COUNT(*) FROM economy_action_receipts WHERE request_id=?',(f'pve_death:{encounter}:1',)).fetchone()[0]==1
    conn.close()
    assert process_due_pve_world_sides(now_ms=1014000,encounter_id=encounter)==[]
