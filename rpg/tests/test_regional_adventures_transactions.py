import json

from database import get_connection, get_player
from game.regional_adventures import (
    execute_regional_action, get_project_state, issue_project_choice_actions,
    issue_regional_action, list_claims, list_facts,
)


def _move(player_id, location_id):
    conn = get_connection()
    conn.execute('UPDATE players SET location_id=?, travel_revision=travel_revision+1, in_battle=0 WHERE telegram_id=?',
                 (location_id, player_id))
    conn.commit(); conn.close()


def _inventory(player_id, item_id, quantity):
    conn = get_connection()
    conn.execute('INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (?,?,?)', (player_id,item_id,quantity))
    conn.commit(); conn.close()


def _quantity(player_id, item_id):
    conn = get_connection()
    row = conn.execute('SELECT COALESCE(SUM(quantity),0) q FROM inventory WHERE telegram_id=? AND item_id=?',
                       (player_id,item_id)).fetchone()
    conn.close(); return int(row['q'])


def _act(player_id, content_id, operation, **kwargs):
    token = issue_regional_action(player_id, content_id, operation, **kwargs)
    assert token and len(token) == 16
    return token, execute_regional_action(player_id, token)


def test_preinspection_reconciles_names_then_choice_is_immutable_and_atomic():
    _move(1, 'ashen_n3a2'); _act(1, 'ar_temple_names', 'inspect')
    _move(1, 'ashen_n3c1'); _act(1, 'ar_garden_ledger', 'inspect')
    assert list_facts(1) >= {'ar_temple_names', 'ar_garden_ledger'}
    _move(1, 'hub_ashen_ruins'); _act(1, 'ar_two_names', 'start')
    state = get_project_state(1, 'ar_two_names')
    assert state['step_index'] == 1 and state['revision'] == 1
    tokens = issue_project_choice_actions(1, 'ar_two_names', 'attribution')
    result = execute_regional_action(1, tokens['shared_credit'])
    assert result['status'] == 'completed'
    state = get_project_state(1, 'ar_two_names')
    assert state['state'] == 'completed' and state['choices'] == {'attribution':'shared_credit'}
    assert state['step_results']['evidence'] == ['garden', 'temple']
    before = dict(get_player(1))
    stale = execute_regional_action(1, tokens['leave_unattributed'])
    after = dict(get_player(1))
    assert stale['status'] in {'already_resolved', 'incompatible_step'}
    assert get_project_state(1, 'ar_two_names')['choices'] == {'attribution':'shared_credit'}
    assert (after['exp'], after['gold']) == (before['exp'], before['gold'])


def test_receipt_first_recovery_precedes_location_and_travel_validation():
    _move(1, 'hub_westwild'); _inventory(1, 'field_ration', 2)
    token, result = _act(1, 'ww_woodcutter_provisions', 'deliver')
    assert result['status'] == 'completed' and result['gold_delta'] == 18
    _move(1, 'sunscar_n1')
    replay = execute_regional_action(1, token)
    assert replay['status'] == 'completed' and replay['recovered'] is True
    assert _quantity(1, 'field_ration') == 0
    assert len(list_claims(1)) == 1


def test_standing_delivery_consumes_fresh_batches_and_never_creates_claim():
    _move(1, 'hub_frostspine'); _inventory(1, 'iron_ore', 4); _inventory(1, 'coal', 4)
    before = dict(get_player(1))
    first_token, first = _act(1, 'fs_forge_supplies', 'deliver')
    assert first['status'] == 'delivered' and first['gold_delta'] == 20
    assert execute_regional_action(1, first_token)['recovered'] is True
    second_token, second = _act(1, 'fs_forge_supplies', 'deliver')
    assert second['status'] == 'delivered'
    assert _quantity(1, 'iron_ore') == _quantity(1, 'coal') == 0
    after = dict(get_player(1))
    assert after['gold'] - before['gold'] == 40 and after['exp'] == before['exp']
    assert 'fs_forge_supplies' not in list_claims(1)


def test_sled_any_delivery_winner_is_exact_and_combat_route_cannot_reopen():
    _move(1, 'old_mine_entrance'); _act(1, 'fs_sled_damage', 'inspect')
    _move(1, 'hub_frostspine'); _act(1, 'fs_jammed_sled', 'start')
    _move(1, 'old_mine_entrance'); _inventory(1, 'wood_common', 2); _inventory(1, 'iron_ore', 1)
    _act(1, 'fs_jammed_sled', 'deliver', objective_id='materials')
    state = get_project_state(1, 'fs_jammed_sled')
    assert state['step_index'] == 2
    assert state['step_results']['repair'] == ['materials']
    assert state['progress']['repair.clear_lizard'] == 0


def test_root_cache_requires_exact_fact_and_claims_once():
    _move(1, 'westwild_n7')
    token = issue_regional_action(1, 'ww_root_cache', 'claim')
    assert execute_regional_action(1, token)['status'] == 'not_discovered'
    _act(1, 'ww_root_marks', 'inspect')
    token, result = _act(1, 'ww_root_cache', 'claim')
    assert result['status'] == 'completed'
    assert _quantity(1, 'health_potion_small') == 1
    assert _quantity(1, 'enhance_shard') == 1
    fresh = issue_regional_action(1, 'ww_root_cache', 'claim')
    assert execute_regional_action(1, fresh)['status'] == 'already_resolved'


def test_three_pin_limit_is_display_only_and_unpin_preserves_project():
    starts = [('ww_tool_roll','hub_westwild'),('ar_two_names','hub_ashen_ruins'),('mv_medic_practice','hub_mireveil')]
    for project_id, location in starts:
        _move(1, location); _act(1, project_id, 'start')
        token = issue_regional_action(1, project_id, 'pin', pin={'owner_kind':'project','owner_id':project_id,'remove':False})
        assert execute_regional_action(1, token)['status'] == 'pinned'
    _move(1, 'hub_ashen_ruins'); _act(1, 'ar_unquiet_storehouse', 'start')
    token = issue_regional_action(1, 'ar_unquiet_storehouse', 'pin', pin={'owner_kind':'project','owner_id':'ar_unquiet_storehouse','remove':False})
    assert execute_regional_action(1, token)['status'] == 'pins_full'
    token = issue_regional_action(1, 'ar_two_names', 'pin', pin={'owner_kind':'project','owner_id':'ar_two_names','remove':True})
    assert execute_regional_action(1, token)['status'] == 'unpinned'
    assert get_project_state(1, 'ar_two_names')['state'] == 'active'
