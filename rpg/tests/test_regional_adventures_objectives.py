import json

from database import get_connection
from game.action_receipts import issue_actions
from game.crafting_runtime import craft_recipe
from game.profession_recipes import recipe_intent_payload
from game.profession_schema import ensure_profession_rows, grant_new_player_starters
from game.regional_adventures import execute_regional_action, get_project_state, issue_regional_action


def _move(location):
    conn=get_connection(); conn.execute('UPDATE players SET location_id=?,travel_revision=travel_revision+1 WHERE telegram_id=1',(location,)); conn.commit(); conn.close()


def _act(content, operation, **kwargs):
    token=issue_regional_action(1,content,operation,**kwargs); assert token
    return execute_regional_action(1,token)


def _prepare_crafter(herbs):
    conn=get_connection(); ensure_profession_rows(conn,1); grant_new_player_starters(conn,1)
    conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,'herb_common',?)",(herbs,)); conn.commit(); conn.close()


def _craft():
    payload=recipe_intent_payload('field_tonic'); token=issue_actions(1,'craft',[payload])[payload]
    return token, craft_recipe(1,'',action_token=token)


def test_personal_craft_observer_counts_executions_after_activation_and_not_replay():
    _move('hub_mireveil'); _prepare_crafter(9)
    _token, before = _craft(); assert before.status == 'crafted'
    _act('mv_medic_practice','start')
    assert get_project_state(1,'mv_medic_practice')['progress']['practice.fresh_tonics'] == 0
    first_token, first = _craft(); assert first.status == 'crafted'
    assert get_project_state(1,'mv_medic_practice')['progress']['practice.fresh_tonics'] == 1
    replay = craft_recipe(1,'field_tonic',action_token=first_token)
    assert replay.status == 'crafted' and replay.recovered
    assert get_project_state(1,'mv_medic_practice')['progress']['practice.fresh_tonics'] == 1
    _second_token, second = _craft(); assert second.status == 'crafted'
    state=get_project_state(1,'mv_medic_practice')
    assert state['step_index'] == 1 and state['progress']['practice.fresh_tonics'] == 2


def test_fact_event_cannot_reuse_location_discovery_or_inventory_possession():
    conn=get_connection()
    conn.execute("INSERT OR IGNORE INTO player_location_discovery(telegram_id,location_id) VALUES (1,'sunscar_n8a1')")
    conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,'health_potion_small',2)")
    conn.commit(); conn.close()
    _move('sunscar_n8a1'); _act('ss_camp_bearings','start')
    state=get_project_state(1,'ss_camp_bearings')
    assert state['progress']['bearings.camp'] == state['progress']['bearings.pillars'] == 0
    _move('hub_mireveil'); _act('mv_medic_practice','start')
    assert get_project_state(1,'mv_medic_practice')['progress']['practice.fresh_tonics'] == 0
