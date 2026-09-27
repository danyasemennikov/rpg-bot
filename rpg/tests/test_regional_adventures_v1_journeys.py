"""RAV1 J01-J20 production-path acceptance journeys.

The module creates one earned, post-Chapter-I checkpoint through the existing
PEV1 production harness, records its SHA-256 provenance, and clones that whole
SQLite checkpoint for independent branches.  Cloning a recorded history is the
only state accelerator; regional facts, projects, claims, goods, rewards, and
combat credit are never injected.
"""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil

import pytest

import database
from database import get_connection, get_player
from game.action_receipts import issue_actions
from game.crafting_runtime import craft_recipe
from game.enemy_profiles import MIXED_ENCOUNTERS
from game.gear_progression import set_equipment_goal
from game.gathering_runtime import gather_resource
from game.locations import get_location
from game.pve_live import ensure_location_pve_spawn_instances
from game.pve_reward_settlement import get_settlement
from game.profession_recipes import recipe_intent_payload
from game.quest_board import (
    HUNT_CONTRACTS_BY_KEY, accept_hunt_contract, get_contract_history,
    list_hunt_contracts_for_location,
)
from game.regional_adventures import (
    execute_regional_action, get_project_state, issue_project_choice_actions,
    issue_regional_action, list_claims, list_facts, list_pins,
)
from game.regional_catalog import PROJECTS_BY_ID
from game.regional_opportunities import nearby
from game.regional_schema import MIGRATION_VERSION, TABLES, ensure_regional_schema
from game.seed import seed_items
from game.pve_live import _ensure_pve_encounter_table, _ensure_world_spawn_table
from handlers.chapter import build_journal, journal_command
from handlers.location import handle_combat_buttons, handle_location_buttons
from handlers.regional import (
    _list_screen, build_detail, build_regional_home, handle_regional_buttons,
)
from tests.test_character_builds_v1_journeys import ProductionJourney
from tests.test_professions_economy_v1_journeys import (
    PLAYER_ID as EARNED_PLAYER_ID,
    FixedRoll, _environment_source, _fight_and_harvest, _move, _production_history, _quantity,
)


_RAV_GATHER_SEQUENCE = itertools.count(1)


def _callbacks(markup) -> list[str]:
    if not markup or not hasattr(markup, 'inline_keyboard'):
        return []
    return [
        str(button.callback_data)
        for row in markup.inline_keyboard for button in row if button.callback_data
    ]


@pytest.fixture(scope='session')
def rav1_earned_checkpoint(tmp_path_factory):
    """Record one legal advanced history once, then expose an immutable clone."""
    reusable = os.environ.get('RAV1_EARNED_CHECKPOINT')
    if reusable and Path(reusable).is_file():
        checkpoint = Path(reusable)
        return {
            'path': checkpoint,
            'sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            'player_id': EARNED_PLAYER_ID,
            'provenance': 'reused SHA-256 checkpoint from this suite’s prior legal PEV1 production history',
            'accelerators': ['whole-checkpoint clone only'],
        }
    checkpoint_dir = tmp_path_factory.mktemp('rav1-earned-history')
    checkpoint = checkpoint_dir / 'earned-rav1.sqlite3'
    original = database.DB_PATH
    database.DB_PATH = str(checkpoint)
    try:
        database.init_db()
        seed_items()
        _ensure_pve_encounter_table()
        _ensure_world_spawn_table()
        conn = get_connection(); ensure_regional_schema(conn); conn.close()
        evidence = asyncio.run(_production_history())
        conn = get_connection()
        conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        conn.close()
        digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    finally:
        database.DB_PATH = original
    assert all(evidence['production_checks'].values())
    return {
        'path': checkpoint,
        'sha256': digest,
        'player_id': EARNED_PLAYER_ID,
        'provenance': 'PEV1 real registration, Chapter I, travel, gathering, crafting, hunts and combat',
        'accelerators': ['mocked Telegram transport', 'zero sleep', 'controlled legal RNG/respawn clock'],
    }


def _restore_checkpoint(checkpoint) -> ProductionJourney:
    target = Path(database.DB_PATH)
    shutil.copy2(checkpoint['path'], target)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == checkpoint['sha256']
    return ProductionJourney(checkpoint['player_id'], lang='en')


@pytest.fixture
def earned(rav1_earned_checkpoint):
    return _restore_checkpoint(rav1_earned_checkpoint)


def _receipt(player_id: int, token: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT result_json FROM economy_action_receipts WHERE player_id=? AND request_id=?',
            (player_id, f'ui:{token}'),
        ).fetchone()
        return json.loads(row['result_json']) if row else None
    finally:
        conn.close()


async def _rav_action(journey: ProductionJourney, content_id: str, operation: str, **kwargs) -> dict:
    token = issue_regional_action(journey.player_id, content_id, operation, **kwargs)
    assert token and len(token) == 16
    await journey.callback(f'rv:a:{token}', handle_regional_buttons)
    result = _receipt(journey.player_id, token)
    assert result is not None, (content_id, operation)
    return result


async def _choose(journey: ProductionJourney, project_id: str, objective_id: str, value: str) -> dict:
    tokens = issue_project_choice_actions(journey.player_id, project_id, objective_id)
    assert set(tokens) == set(
        next(
            objective.target['values']
            for step in PROJECTS_BY_ID[project_id].steps
            for objective in step.objectives
            if objective.objective_id == objective_id
        )
    )
    stale_alternate = next(token for choice, token in tokens.items() if choice != value)
    await journey.callback(f'rv:a:{tokens[value]}', handle_regional_buttons)
    result = _receipt(journey.player_id, tokens[value])
    assert result and result['status'] in {'advanced', 'completed'}
    replay = execute_regional_action(journey.player_id, stale_alternate)
    assert replay['status'] in {'stale_action', 'incompatible_step', 'already_resolved'}
    return result


async def _inspect(journey: ProductionJourney, fact_id: str, location_id: str) -> dict:
    await _move(journey, location_id)
    return await _rav_action(journey, fact_id, 'inspect')


async def _fight_spawn(journey: ProductionJourney, callback: str) -> str:
    await journey.callback(callback, handle_combat_buttons)
    enter = next(value for value in _callbacks(journey.messages[-1][1]) if value.startswith('pve_enter_'))
    encounter_id = enter.removeprefix('pve_enter_')
    await journey.callback(enter, handle_location_buttons)
    opening = (('skill', 'defensive_stance'), ('skill', 'shield_bash'), ('skill', 'sword_rush'))
    for turn in range(90):
        if 'battle' not in journey.context.user_data:
            break
        kind, skill = opening[turn] if turn < len(opening) else ('basic_attack', None)
        try:
            action = journey._find_combat_action(kind=kind, skill_id=skill)
        except AssertionError:
            action = journey._find_combat_action(kind='basic_attack', skill_id=None)
        await journey.callback(action, __import__('handlers.battle', fromlist=['handle_battle_buttons']).handle_battle_buttons)
    else:
        raise AssertionError(('battle did not finish', encounter_id))
    settlement = get_settlement(encounter_id)
    assert settlement and settlement['status'] == 'applied'
    return encounter_id


async def _mixed_fight(journey: ProductionJourney, recipe_id: str) -> str:
    location_id = MIXED_ENCOUNTERS[recipe_id]['location_id']
    await _move(journey, location_id)
    ensure_location_pve_spawn_instances(location_id=location_id)
    conn = get_connection()
    conn.execute(
        "UPDATE pve_spawn_instances SET respawn_available_at='2000-01-01 00:00:00' "
        "WHERE location_id=? AND state='respawning'", (location_id,),
    )
    conn.commit(); conn.close()
    ensure_location_pve_spawn_instances(location_id=location_id)
    return await _fight_spawn(journey, f'fight_mixed_{recipe_id}')


async def _special_fight(journey: ProductionJourney, location_id: str, special_key: str) -> str:
    await _move(journey, location_id)
    ensure_location_pve_spawn_instances(location_id=location_id)
    conn = get_connection()
    conn.execute(
        "UPDATE pve_spawn_instances SET state='idle', linked_encounter_id=NULL, respawn_available_at=NULL "
        "WHERE location_id=? AND special_spawn_key=?", (location_id, special_key),
    )
    conn.commit(); conn.close()
    return await _fight_spawn(journey, f'fight_special_{special_key}')


async def _complete_names(journey, choice='shared_credit'):
    await _inspect(journey, 'ar_temple_names', 'ashen_n3a2')
    await _inspect(journey, 'ar_garden_ledger', 'ashen_n3c1')
    await _move(journey, 'hub_ashen_ruins')
    await _rav_action(journey, 'ar_two_names', 'start')
    await _choose(journey, 'ar_two_names', 'attribution', choice)


async def _complete_camp(journey, inspect_first=True):
    if inspect_first:
        await _inspect(journey, 'ss_pillar_shadow', 'sunscar_n8a2')
        await _inspect(journey, 'ss_camp_marks', 'sunscar_n8a1')
    await _move(journey, 'sunscar_n8a1')
    await _rav_action(journey, 'ss_camp_bearings', 'start')
    await _rav_action(journey, 'ss_camp_bearings', 'respond', objective_id='open_cache')


async def _complete_tool(journey):
    await _move(journey, 'hub_westwild')
    await _rest_if_needed(journey)
    await _rav_action(journey, 'ww_tool_roll', 'start')
    await _move(journey, 'westwild_n3')
    await journey.fight('forest_wolf')
    await _move(journey, 'hub_westwild')
    await _rav_action(journey, 'ww_tool_roll', 'respond', objective_id='report')


async def _complete_sled(journey):
    await _inspect(journey, 'fs_sled_damage', 'old_mine_entrance')
    await _rav_action(journey, 'fs_jammed_sled', 'start')
    await _move(journey, 'hub_frostspine')
    await _rest_if_needed(journey)
    await _move(journey, 'frostspine_n2')
    await journey.fight('rock_lizard')
    await _move(journey, 'hub_frostspine')
    await _rav_action(journey, 'fs_jammed_sled', 'respond', objective_id='receipt')


async def _complete_storehouse(journey, choice='archive_seal'):
    await _inspect(journey, 'ar_storehouse_seal', 'ashen_n3b1')
    await _rav_action(journey, 'ar_unquiet_storehouse', 'start')
    await _move(journey, 'hub_ashen_ruins')
    await _rest_if_needed(journey)
    await _move(journey, 'ashen_n3b1')
    await journey.fight('skeleton_guard')
    await _move(journey, 'hub_ashen_ruins')
    await _choose(journey, 'ar_unquiet_storehouse', 'seal_fate', choice)


async def _complete_ferry(journey, choice='save_supplies'):
    await _inspect(journey, 'mv_ford_marks', 'mireveil_n5')
    await _inspect(journey, 'mv_channel_rope', 'mireveil_n8')
    await _move(journey, 'hub_mireveil')
    await _rest_if_needed(journey)
    await _rav_action(journey, 'mv_ferry_crew', 'start')
    await _mixed_fight(journey, 'rav1_mireveil_n6_crosscurrent')
    await _move(journey, 'mireveil_n8')
    await _choose(journey, 'mv_ferry_crew', 'cargo', choice)
    await _move(journey, 'hub_mireveil')
    await _rav_action(journey, 'mv_ferry_crew', 'respond', objective_id='report')


async def _ensure_resource(journey, item_id: str, quantity: int, sequence: list[str]):
    missing = max(0, quantity - _quantity(journey.player_id, item_id))
    if not missing:
        return
    location_id, profession, roll = _environment_source(item_id)
    await _move(journey, location_id)
    before = _quantity(journey.player_id, item_id)
    for _ in range(missing):
        request_id = f'gather:rav1:{item_id}:{next(_RAV_GATHER_SEQUENCE)}'
        result = gather_resource(
            journey.player_id, profession, location_id=location_id,
            request_id=request_id, rng=FixedRoll(roll),
        )
        assert result['status'] == 'gathered', result
        sequence.append(request_id)
    assert _quantity(journey.player_id, item_id) == before + missing


async def _rest_if_needed(journey: ProductionJourney):
    player = dict(get_player(journey.player_id))
    if int(player['hp']) < int(player['max_hp']) or int(player['mana']) < int(player['max_mana']):
        await journey.rest_at_current_inn()


def _state_snapshot(player_id: int) -> dict:
    player = dict(get_player(player_id))
    return {
        'level': int(player['level']), 'exp': int(player['exp']), 'gold': int(player['gold']),
        'strength': int(player['strength']), 'agility': int(player['agility']),
        'intuition': int(player['intuition']), 'vitality': int(player['vitality']),
        'wisdom': int(player['wisdom']), 'luck': int(player['luck']),
        'claims': sorted(list_claims(player_id)),
    }


def test_j01_fresh_onboarding(rav1_earned_checkpoint, earned):
    async def run():
        assert rav1_earned_checkpoint['sha256'] and len(rav1_earned_checkpoint['sha256']) == 64
        assert 'chapter_homecoming' in get_contract_history(earned.player_id)
        assert not any(get_project_state(earned.player_id, key) for key in PROJECTS_BY_ID)
        await earned.text('/journal', journal_command)
        text, markup = earned.messages[-1]
        assert len([value for value in _callbacks(markup) if value.startswith('rv:v:')][:6]) == 6
        assert {'pe_o:0', 'inv_catalog', 'rv:v:r:0:all'} <= set(_callbacks(markup))
        assert 'main quest' in text.lower()
        await earned.callback('rv:v:r:0:all', handle_regional_buttons)
        region_text, region_markup = earned.messages[-1]
        assert len([value for value in _callbacks(region_markup) if value.startswith('rv:d:r:')]) == 5
        assert all(_title in region_text for _title in ('Westwild', 'Frostspine', 'Ashen Ruins', 'Sunscar', 'Mireveil'))
    asyncio.run(run())


def test_j02_five_way_choice_and_actual_entry_surfaces(earned):
    async def run():
        facts_before = set(list_facts(earned.player_id))
        await earned.text('/journal', journal_command)
        await earned.callback('rv:v:r:0:all', handle_regional_buttons)
        for region_id in ('region_westwild','region_frostspine','region_ashen_ruins','region_sunscar','region_mireveil'):
            await earned.callback(f'rv:d:r:{region_id}', handle_regional_buttons)
            assert earned.messages[-1][0]
        assert list_facts(earned.player_id) == facts_before
        west_text, west_markup = build_detail(dict(get_player(earned.player_id)), 'r', 'region_westwild')
        assert west_text and 'rv:d:e:greyfang' not in _callbacks(west_markup)
        sun_text, sun_markup = build_detail(dict(get_player(earned.player_id)), 'r', 'region_sunscar')
        assert sun_text and 'rv:d:p:ss_camp_bearings' not in _callbacks(sun_markup)

        for location in ('hub_westwild', 'frostspine_n5', 'ashen_n3a2', 'mireveil_n5a1', 'hub_sunscar'):
            await _move(earned, location)
            if 'quest_board' in get_location(location).get('services', []):
                assert list_hunt_contracts_for_location(location)
        keys = {c.contract_key for location in ('frostspine_n5','ashen_n3a2','mireveil_n5a1','hub_sunscar')
                for c in list_hunt_contracts_for_location(location)}
        assert {'hunt_frostspine_white_wolves','hunt_ashen_zombie_clusters','hunt_sunscar_scorpions',
                'hunt_sunscar_air_elementals'} <= keys
        await _move(earned, 'capital_city')
        wrong_token = issue_regional_action(earned.player_id, 'mv_medic_table', 'deliver')
        wrong_query = await earned.callback(f'rv:a:{wrong_token}', handle_regional_buttons)
        assert wrong_query.answer.await_args.kwargs.get('show_alert') is True
        assert _receipt(earned.player_id, wrong_token) is None
        assert 'mv_medic_table' not in list_claims(earned.player_id)
        assert len(_list_screen(dict(get_player(earned.player_id)), 'r', 0, 'all')[1].inline_keyboard) <= 10
    asyncio.run(run())


def test_j03_different_first_regions_and_solo_paths(rav1_earned_checkpoint):
    async def run():
        cases = (
            ('ww_tool_roll', _complete_tool), ('fs_jammed_sled', _complete_sled),
            ('ar_two_names', _complete_names), ('mv_ferry_crew', _complete_ferry),
            ('ss_camp_bearings', _complete_camp),
        )
        for project_id, complete in cases:
            journey = _restore_checkpoint(rav1_earned_checkpoint)
            await complete(journey)
            claims = list_claims(journey.player_id)
            assert project_id in claims
            assert not (set(PROJECTS_BY_ID) - {project_id}) & set(claims)
    asyncio.run(run())


def test_j04_stay_local(earned):
    async def run():
        await _move(earned, 'hub_westwild')
        await _rav_action(earned, 'ww_tool_roll', 'start')
        accepted, status = accept_hunt_contract(
            player_id=earned.player_id, location_id='hub_westwild', contract_key='hunt_greyfang')
        assert accepted and status == 'accepted'
        await _ensure_resource(earned, 'herb_common', 2, [])
        await _move(earned, 'hub_westwild')
        assert any(row['kind'] == 'work_link' for row in nearby(dict(get_player(earned.player_id))))
        assert get_project_state(earned.player_id, 'ww_tool_roll')['state'] == 'active'
    asyncio.run(run())


def test_j05_concurrent_pursuits_pins_and_restart(earned):
    async def run():
        await _move(earned, 'hub_ashen_ruins')
        await _rav_action(earned, 'ar_two_names', 'start')
        await _rav_action(earned, 'ar_unquiet_storehouse', 'start')
        for project_id in ('ar_two_names', 'ar_unquiet_storehouse'):
            assert (await _rav_action(earned, 'journal', 'pin', pin={
                'owner_kind':'project','owner_id':project_id,'remove':False}))['status'] == 'pinned'
        await _move(earned, 'ashen_n3a2')
        accepted, status = accept_hunt_contract(
            player_id=earned.player_id, location_id='ashen_n3a2',
            contract_key='hunt_ashen_zombie_clusters')
        assert accepted and status == 'accepted'
        await _rav_action(earned, 'journal', 'pin', pin={
            'owner_kind':'hunt','owner_id':'hunt_ashen_zombie_clusters','remove':False})
        assert set_equipment_goal(earned.player_id, 'field_sword_1h')
        fourth = await _rav_action(earned, 'journal', 'pin', pin={
            'owner_kind':'gear','owner_id':'current','remove':False})
        assert fourth['status'] == 'pins_full'
        assert len(list_pins(earned.player_id)) == 3
        assert get_project_state(earned.player_id, 'ar_two_names')['state'] == 'active'
    asyncio.run(run())


@pytest.mark.parametrize('order', [('names','storehouse'), ('storehouse','names')])
def test_j06_reverse_independent_order(earned, order):
    async def run():
        before = _state_snapshot(earned.player_id)
        for value in order:
            await (_complete_names(earned) if value == 'names' else _complete_storehouse(earned))
        after = _state_snapshot(earned.player_id)
        assert {'ar_two_names','ar_unquiet_storehouse'} <= set(after['claims'])
        claims = list_claims(earned.player_id)
        assert claims['ar_two_names']['gold'] + claims['ar_unquiet_storehouse']['gold'] == 50
        assert after['gold'] - before['gold'] >= 50  # ordinary fight proceeds are incidental
    asyncio.run(run())


def test_j07_explore_before_lead(earned):
    async def run():
        await _inspect(earned, 'ar_temple_names', 'ashen_n3a2')
        await _inspect(earned, 'ar_garden_ledger', 'ashen_n3c1')
        await _move(earned, 'hub_ashen_ruins')
        await _rav_action(earned, 'ar_two_names', 'start')
        assert get_project_state(earned.player_id, 'ar_two_names')['step_index'] == 1
        await _inspect(earned, 'ss_pillar_shadow', 'sunscar_n8a2')
        await _inspect(earned, 'ss_camp_marks', 'sunscar_n8a1')
        await _rav_action(earned, 'ss_camp_bearings', 'start')
        assert get_project_state(earned.player_id, 'ss_camp_bearings')['step_index'] == 1
        await _inspect(earned, 'fs_sled_damage', 'old_mine_entrance')
        await _rav_action(earned, 'fs_jammed_sled', 'start')
        assert get_project_state(earned.player_id, 'fs_jammed_sled')['step_index'] == 1
    asyncio.run(run())


def test_j08_low_profession_route(earned):
    asyncio.run(_complete_sled(earned))
    assert 'fs_jammed_sled' in list_claims(earned.player_id)


def test_j09_personal_practice(earned):
    async def run():
        await _move(earned, 'hub_mireveil')
        await _rav_action(earned, 'mv_medic_practice', 'start')
        for index in range(2):
            await _ensure_resource(earned, 'herb_common', 3, [])
            await _move(earned, 'capital_city')
            payload = recipe_intent_payload('field_tonic')
            token = issue_actions(earned.player_id, 'craft', [payload])[payload]
            crafted = craft_recipe(earned.player_id, 'field_tonic', action_token=token)
            assert crafted.status == 'crafted'
            assert craft_recipe(earned.player_id, 'field_tonic', action_token=token).recovered
        assert get_project_state(earned.player_id, 'mv_medic_practice')['step_index'] == 1
        await _move(earned, 'hub_mireveil')
        await _rav_action(earned, 'mv_medic_practice', 'deliver', objective_id='tonics')
        assert 'mv_medic_practice' in list_claims(earned.player_id)
    asyncio.run(run())


def test_j10_ordinary_delivery(earned):
    async def run():
        await _ensure_resource(earned, 'herb_common', 4, [])
        while _quantity(earned.player_id, 'boar_meat') < 4:
            await _fight_and_harvest(
                earned, location_id='westwild_n2', mob_id='forest_boar',
                item_id='boar_meat', encounter_ids=[],
            )
        while _quantity(earned.player_id, 'field_ration') < 4:
            await _move(earned, 'capital_city')
            payload = recipe_intent_payload('trail_ration')
            token = issue_actions(earned.player_id, 'craft', [payload])[payload]
            assert craft_recipe(earned.player_id, 'trail_ration', action_token=token).status == 'crafted'
        await _move(earned, 'hub_westwild')
        assert (await _rav_action(earned, 'ww_woodcutter_provisions', 'deliver'))['status'] == 'completed'
        await _ensure_resource(earned, 'herb_common', 4, [])
        await _move(earned, 'hub_mireveil')
        assert (await _rav_action(earned, 'mv_medic_table', 'deliver'))['status'] == 'completed'
        for content_id, location in (
            ('ww_ration_order','hub_westwild'), ('fs_forge_supplies','hub_frostspine'),
            ('mv_stew_order','hub_mireveil')):
            if content_id == 'fs_forge_supplies':
                await _ensure_resource(earned, 'iron_ore', 2, [])
                await _ensure_resource(earned, 'coal', 2, [])
            elif content_id == 'ww_ration_order':
                while _quantity(earned.player_id, 'field_ration') < 2:
                    await _move(earned, 'capital_city')
                    payload = recipe_intent_payload('trail_ration')
                    token = issue_actions(earned.player_id, 'craft', [payload])[payload]
                    assert craft_recipe(earned.player_id, 'trail_ration', action_token=token).status == 'crafted'
            elif content_id == 'mv_stew_order':
                await _ensure_resource(earned, 'marsh_fish', 4, [])
                await _ensure_resource(earned, 'marsh_herb', 2, [])
                await _ensure_resource(earned, 'salt_crystal', 2, [])
                while _quantity(earned.player_id, 'pe_marsh_stew') < 2:
                    await _move(earned, 'capital_city')
                    payload = recipe_intent_payload('pe_cooking_marsh_06')
                    token = issue_actions(earned.player_id, 'craft', [payload])[payload]
                    assert craft_recipe(earned.player_id, 'pe_cooking_marsh_06', action_token=token).status == 'crafted'
            await _move(earned, location)
            before_progress = dict(get_player(earned.player_id))
            result = await _rav_action(earned, content_id, 'deliver')
            after_progress = dict(get_player(earned.player_id))
            assert result['status'] == 'delivered'
            assert result['gold_delta'] == {'ww_ration_order':10,'fs_forge_supplies':20,'mv_stew_order':12}[content_id]
            assert (after_progress['level'], after_progress['exp']) == (before_progress['level'], before_progress['exp'])
    asyncio.run(run())


def test_j11_combat_overlap(earned):
    async def run():
        await _move(earned, 'hub_westwild')
        await _rav_action(earned, 'ww_tool_roll', 'start')
        accepted, status = accept_hunt_contract(
            player_id=earned.player_id, location_id='hub_westwild', contract_key='hunt_greyfang')
        assert accepted and status == 'accepted'
        await _special_fight(earned, 'westwild_n3', 'greyfang')
        assert get_project_state(earned.player_id, 'ww_tool_roll')['step_index'] == 1
        conn = get_connection()
        hunt = conn.execute('SELECT * FROM player_hunt_contracts WHERE player_id=?',(earned.player_id,)).fetchone()
        conn.close(); assert hunt and hunt['status'] == 'completed'
    asyncio.run(run())


def test_j12_optional_group_binding_contract(earned):
    async def run():
        await _inspect(earned, 'mv_ford_marks', 'mireveil_n5')
        await _inspect(earned, 'mv_channel_rope', 'mireveil_n8')
        await _move(earned, 'hub_mireveil')
        await _rav_action(earned, 'mv_ferry_crew', 'start')
        encounter_id = await _mixed_fight(earned, 'rav1_mireveil_n6_crosscurrent')
        conn = get_connection()
        row = conn.execute('SELECT applied_at,bindings_json FROM rav1_combat_bindings WHERE encounter_id=? AND player_id=?',
                           (encounter_id, earned.player_id)).fetchone()
        conn.close()
        assert row and row['applied_at'] and json.loads(row['bindings_json'])
    asyncio.run(run())


def test_j13_named_canonical_targets(earned):
    async def run():
        greyfang = await _special_fight(
            earned, 'westwild_n3', 'greyfang')
        drifter = await _special_fight(
            earned, 'sunscar_n8a2', 'salt_ridge_drifter')
        for encounter_id, key, profile in ((greyfang,'greyfang','normal'),(drifter,'salt_ridge_drifter','elite')):
            settlement = get_settlement(encounter_id)
            units = settlement['plan']['enemy_units']
            assert units[0]['special_spawn_key'] == key and units[0]['spawn_profile'] == profile
    asyncio.run(run())


def test_j14_busy_shared_sources(earned):
    async def run():
        await _move(earned, 'mireveil_n6')
        await earned.callback('fight_mixed_rav1_mireveil_n6_crosscurrent', handle_combat_buttons)
        rows = nearby(dict(get_player(earned.player_id)))
        mixed = next(row for row in rows if row['content_id']=='rav1_mireveil_n6_crosscurrent')
        assert mixed['status'] == 'busy'
        enter = next(value for value in _callbacks(earned.messages[-1][1]) if value.startswith('pve_enter_'))
        encounter_id = enter.removeprefix('pve_enter_')
        from game.pve_live import leave_open_world_pve_encounter
        assert leave_open_world_pve_encounter(encounter_id=encounter_id, player_id=earned.player_id)[0]
        assert next(row for row in nearby(dict(get_player(earned.player_id)))
                    if row['content_id']=='rav1_mireveil_n6_crosscurrent')['status'] == 'available'
    asyncio.run(run())


@pytest.mark.parametrize('choices', [
    ('shared_credit','archive_seal','save_supplies'),
    ('leave_unattributed','leave_seal','save_log'),
])
def test_j15_permanent_local_choices(earned, choices):
    async def run():
        await _complete_names(earned, choices[0])
        await _complete_storehouse(earned, choices[1])
        await _complete_ferry(earned, choices[2])
        states = [get_project_state(earned.player_id, value) for value in
                  ('ar_two_names','ar_unquiet_storehouse','mv_ferry_crew')]
        assert [next(iter(state['choices'].values())) for state in states] == list(choices)
    asyncio.run(run())


def test_j16_returning_player_migration(rav1_earned_checkpoint):
    _restore_checkpoint(rav1_earned_checkpoint)
    conn = get_connection()
    before = {
        'player': tuple(conn.execute('SELECT level,exp,gold,location_id FROM players WHERE telegram_id=?',
                                     (EARNED_PLAYER_ID,)).fetchone()),
        'inventory': conn.execute('SELECT COUNT(*),SUM(quantity) FROM inventory WHERE telegram_id=?',
                                  (EARNED_PLAYER_ID,)).fetchone()[0],
        'gear': conn.execute('SELECT COUNT(*) FROM gear_instances WHERE telegram_id=?',
                             (EARNED_PLAYER_ID,)).fetchone()[0],
    }
    conn.execute('DELETE FROM economy_schema_migrations WHERE version=?',(MIGRATION_VERSION,))
    for table in reversed(TABLES):
        conn.execute(f'DROP TABLE {table}')
    conn.commit()
    ensure_regional_schema(conn)
    ensure_regional_schema(conn)
    after_player = tuple(conn.execute('SELECT level,exp,gold,location_id FROM players WHERE telegram_id=?',
                                      (EARNED_PLAYER_ID,)).fetchone())
    assert before['player'] == after_player
    assert conn.execute('SELECT COUNT(*) FROM rav1_projects').fetchone()[0] == 0
    conn.close()


def test_j17_atomic_boundaries(earned):
    async def run():
        await _inspect(earned, 'ww_root_marks', 'westwild_n7')
        token = issue_regional_action(earned.player_id, 'ww_root_cache', 'claim')
        with pytest.raises(RuntimeError):
            execute_regional_action(earned.player_id, token,
                                    failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError('cut'))
                                    if point == 'before_receipt' else None)
        assert 'ww_root_cache' not in list_claims(earned.player_id)
        fresh = issue_regional_action(earned.player_id, 'ww_root_cache', 'claim')
        committed = execute_regional_action(earned.player_id, fresh)
        assert committed['status'] == 'completed'
        assert execute_regional_action(earned.player_id, fresh)['recovered'] is True
    asyncio.run(run())


@pytest.mark.parametrize('reverse', [False, True])
def test_j18_arbitrary_reward_order(rav1_earned_checkpoint, reverse):
    journey = _restore_checkpoint(rav1_earned_checkpoint)
    async def run():
        await _ensure_resource(journey, 'herb_common', 6, [])
        while _quantity(journey.player_id, 'boar_meat') < 2:
            await _fight_and_harvest(
                journey, location_id='westwild_n2', mob_id='forest_boar',
                item_id='boar_meat', encounter_ids=[],
            )
        while _quantity(journey.player_id, 'field_ration') < 2:
            await _move(journey, 'capital_city')
            payload = recipe_intent_payload('trail_ration')
            token = issue_actions(journey.player_id, 'craft', [payload])[payload]
            assert craft_recipe(journey.player_id, 'trail_ration', action_token=token).status == 'crafted'
        before = _state_snapshot(journey.player_id)
        actions = [
            lambda: _complete_names(journey), lambda: _complete_camp(journey),
            lambda: _request(journey, 'ww_woodcutter_provisions', 'hub_westwild'),
            lambda: _request(journey, 'mv_medic_table', 'hub_mireveil'),
        ]
        for action in reversed(actions) if reverse else actions:
            await action()
        after = _state_snapshot(journey.player_id)
        assert after['gold'] - before['gold'] == 68
        assert set(after['claims']) - set(before['claims']) == {
            'ar_two_names','ss_camp_bearings','ww_woodcutter_provisions','mv_medic_table'}
    asyncio.run(run())


async def _request(journey, content_id, location_id):
    if content_id == 'mv_medic_table':
        await _ensure_resource(journey, 'herb_common', 4, [])
    await _move(journey, location_id)
    return await _rav_action(journey, content_id, 'deliver')


@pytest.mark.parametrize('lang', ['ru','en','es'])
def test_j19_localized_real_handlers(earned, lang):
    async def run():
        conn = get_connection(); conn.execute('UPDATE players SET lang=? WHERE telegram_id=?',(lang,earned.player_id)); conn.commit(); conn.close()
        player = dict(get_player(earned.player_id))
        surfaces = [build_regional_home(player), _list_screen(player,'r',0,'all'),
                    build_detail(player,'p','ar_two_names'), build_detail(player,'w','mv_stew_order')]
        for text, markup in surfaces:
            assert text and len(text) <= 3000
            assert all(len(value.encode('utf-8')) <= 64 for value in _callbacks(markup))
        query = await earned.callback('rv:not-valid', handle_regional_buttons)
        assert query.answer.await_count == 1
    asyncio.run(run())


def test_j20_after_resolution(earned):
    async def run():
        await _complete_names(earned)
        before = dict(list_claims(earned.player_id))
        token = issue_regional_action(earned.player_id, 'ar_two_names', 'start')
        assert execute_regional_action(earned.player_id, token)['status'] == 'already_resolved'
        await _ensure_resource(earned, 'herb_common', 2, [])
        while _quantity(earned.player_id, 'boar_meat') < 2:
            await _fight_and_harvest(
                earned, location_id='westwild_n2', mob_id='forest_boar',
                item_id='boar_meat', encounter_ids=[],
            )
        while _quantity(earned.player_id, 'field_ration') < 2:
            await _move(earned, 'capital_city')
            payload = recipe_intent_payload('trail_ration')
            craft_token = issue_actions(earned.player_id, 'craft', [payload])[payload]
            assert craft_recipe(earned.player_id, 'trail_ration', action_token=craft_token).status == 'crafted'
        await _move(earned, 'hub_westwild')
        first = await _rav_action(earned, 'ww_ration_order', 'deliver')
        assert first['status'] == 'delivered'
        assert list_claims(earned.player_id) == before
        text, markup = _list_screen(dict(get_player(earned.player_id)), 'p', 0, 'all')
        assert text and _callbacks(markup)
        assert get_project_state(earned.player_id, 'ar_two_names')['state'] == 'completed'
    asyncio.run(run())
