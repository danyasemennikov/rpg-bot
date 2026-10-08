"""RAV1 J01-J20 production-path acceptance journeys.

The module creates one earned, post-Chapter-I checkpoint through the existing
PXE1 production harness, records its SHA-256 provenance, and clones that whole
SQLite checkpoint for independent branches.  Cloning a recorded history is the
only state accelerator; regional facts, projects, claims, goods, rewards, and
combat credit are never injected.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
from unittest.mock import patch

import pytest

import database
from database import get_connection, get_player
from game.action_receipts import issue_actions
from game.crafting_runtime import craft_recipe
from game.economy_actions import gift_inventory_item
from game.enemy_profiles import MIXED_ENCOUNTERS
from game.gear_progression import apply_gear_intent, issue_gear_intent, set_equipment_goal
from game.locations import get_location
from game.hunting import harvest_victory, list_harvestable_victories
from game.i18n import t, validate_rav1_locales
from game.pve_live import (
    FORMING_ENCOUNTER_TTL_SECONDS, _prune_expired_forming_encounters,
    ensure_location_pve_spawn_instances,
    finish_solo_pve_encounter, leave_open_world_pve_encounter,
    reset_solo_pve_runtime_store,
)
from game.pve_reward_settlement import (
    apply_prepared_settlement, get_settlement, recover_prepared_settlements,
)
from game.profession_recipes import recipe_intent_payload
from game.quest_board import (
    HUNT_CONTRACTS_BY_KEY, accept_hunt_contract, build_contract_row,
    claim_completed_hunt_contract, get_contract_history,
    get_player_hunter_progress, list_hunt_contracts_for_location,
)
from game.regional_adventures import (
    execute_regional_action, get_project_state, issue_project_choice_actions,
    issue_regional_action, list_claims, list_facts, list_pins,
    preview_regional_choice,
)
from game.regional_catalog import FACTS_BY_ID, PROJECTS_BY_ID
from game.regional_opportunities import nearby
from game.regional_schema import MIGRATION_VERSION, TABLES, ensure_regional_schema
from handlers.chapter import handle_chapter_buttons, journal_command
from handlers.location import (
    handle_combat_buttons, handle_location_buttons,
    location_command,map_command,
)
from handlers.inventory import handle_inventory_buttons, try_sell_inventory_item,inventory_command
from handlers.profile import profile_command
from handlers.professions import handle_profession_buttons
from handlers.regional import (
    _list_screen, build_detail, build_regional_home, handle_regional_buttons,
)
from tests.test_character_builds_v1_journeys import ProductionJourney
from tests.test_character_builds_v1_group_journeys import (
    _commit_round, _encounter_state, _finish_group, _frozen_combat_clock,
    _set_encounter_combat_seed, _start_group, _start_mixed_group,
)
from tests.test_professions_economy_v1_journeys import (
    PLAYER_ID as EARNED_PLAYER_ID,
    _complete_aster_elmor_chapter, _gather,
    _fight_and_harvest, _move, _quantity, _recover,
)


PHYSICAL_PLAYER_ID = EARNED_PLAYER_ID + 1
MAGIC_PLAYER_ID = EARNED_PLAYER_ID + 2
BELOW_RANK_PLAYER_ID = EARNED_PLAYER_ID + 99


def _callbacks(markup) -> list[str]:
    if not markup or not hasattr(markup, 'inline_keyboard'):
        return []
    return [
        str(button.callback_data)
        for row in markup.inline_keyboard for button in row if button.callback_data
    ]


def _reply_labels(markup) -> list[str]:
    if not markup or not hasattr(markup, 'keyboard'):
        return []
    return [str(button.text) for row in markup.keyboard for button in row]


async def _open_location(journey: ProductionJourney) -> tuple[str, object]:
    """Return the inline location card emitted before lower-menu synchronization."""
    first_new_message = len(journey.messages)
    await journey.text('/location', location_command)
    emitted = journey.messages[first_new_message:]
    card = next((message for message in emitted if _callbacks(message[1])), None)
    assert card, emitted
    return card


async def _location_encounter_controls(journey):
    from handlers.activities import handle_activity_buttons
    await _open_location(journey)
    page=0
    controls=[]
    while True:
        await journey.callback(f'px:local:encounters:{page}',handle_activity_buttons)
        current=_callbacks(journey.messages[-1][1])
        controls.extend(c for c in current if c.startswith(('fight_','pve_enter_')))
        if f'px:local:encounters:{page+1}' not in current: break
        page+=1
    return controls


async def _open_command(journey,command,handler):
    before=len(journey.messages)
    await journey.text(command,handler)
    return next(message for message in journey.messages[before:] if _callbacks(message[1]))


async def _open_quest_board(journey: ProductionJourney) -> tuple[str, object]:
    from handlers.activities import handle_activity_buttons
    await _open_location(journey)
    await journey.callback('px:local:services:0', handle_activity_buttons)
    assert 'quest_board' in _callbacks(journey.messages[-1][1]), journey.messages[-1]
    await journey.callback('quest_board', handle_location_buttons)
    return journey.messages[-1]


async def _board_details(journey):
    _,root=await _open_quest_board(journey)
    categories=[c for c in _callbacks(root) if c.startswith('quest_board_list_')]
    keys=[]
    for callback in categories:
        category=callback.removeprefix('quest_board_list_').rsplit('_',1)[0]
        page=0
        while True:
            await journey.callback(f'quest_board_list_{category}_{page}',handle_location_buttons)
            callbacks=_callbacks(journey.messages[-1][1])
            keys.extend(c.removeprefix('quest_board_detail_') for c in callbacks if c.startswith('quest_board_detail_'))
            if f'quest_board_list_{category}_{page+1}' not in callbacks: break
            page+=1
    details={}
    for key in keys:
        await journey.callback('quest_board_detail_'+key,handle_location_buttons)
        details[key]=journey.messages[-1]
    return details


@pytest.fixture(scope='session')
def rav1_earned_checkpoint(pxe1_profession_checkpoint):
    """Reuse the current run's verified PXE1 history, never an old PEV1 hash."""
    return {
        'path': pxe1_profession_checkpoint['path'],
        'sha256': pxe1_profession_checkpoint['sha256'],
        'player_id': EARNED_PLAYER_ID,
        'provenance': 'current PXE1 timed gathering, all 83 recipes, 20 tools and XP-policy-2 production history',
        'accelerators': ['mocked Telegram transport', 'controlled legal rolls and due clocks', 'whole-checkpoint clone only'],
    }


async def _earn_chapter_player(player_id: int, *, primary: str, starter: str, family: str) -> ProductionJourney:
    """Create a post-Chapter-I character exclusively through production handlers."""
    journey = ProductionJourney(player_id, lang='en')
    await journey.register(primary=primary, name=f'RAV1 {primary.title()}')
    await journey.callback(f'alpha_kit_{starter}', handle_chapter_buttons)
    await journey.buy_and_equip_field_weapon(family)
    await _complete_aster_elmor_chapter(journey, [], [])
    assert 'chapter_homecoming' in get_contract_history(player_id)
    return journey


@pytest.fixture(scope='session')
def rav1_party_checkpoint(tmp_path_factory, rav1_earned_checkpoint):
    """Add two independently earned Chapter-I builds to the legal advanced history."""
    checkpoint_dir = tmp_path_factory.mktemp('rav1-earned-party')
    checkpoint = checkpoint_dir / 'earned-rav1-party.sqlite3'
    shutil.copy2(rav1_earned_checkpoint['path'], checkpoint)
    original = database.DB_PATH
    database.DB_PATH = str(checkpoint)
    try:
        from game.build_progression import migrate_character_builds_v1
        migrate_character_builds_v1()
        asyncio.run(_earn_chapter_player(
            PHYSICAL_PLAYER_ID, primary='strength', starter='practice_sword', family='sword_1h'))
        asyncio.run(_earn_chapter_player(
            MAGIC_PLAYER_ID, primary='intuition', starter='practice_staff', family='magic_staff'))
        conn = get_connection(); conn.execute('PRAGMA wal_checkpoint(TRUNCATE)'); conn.close()
    finally:
        database.DB_PATH = original
    output = os.environ.get('RAV1_PARTY_CHECKPOINT_OUT')
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(checkpoint, output)
        checkpoint = Path(output)
    return {
        'path': checkpoint,
        'sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        'player_id': EARNED_PLAYER_ID,
        'physical_id': PHYSICAL_PLAYER_ID,
        'magic_id': MAGIC_PLAYER_ID,
        'provenance': 'current PXE1 history plus two real registrations and complete Chapter-I handler histories',
    }


def _restore_checkpoint(checkpoint) -> ProductionJourney:
    target = Path(database.DB_PATH)
    shutil.copy2(checkpoint['path'], target)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == checkpoint['sha256']
    return ProductionJourney(checkpoint['player_id'], lang='en')


def _restore_checkpoint_as(checkpoint, player_id: int) -> ProductionJourney:
    target = Path(database.DB_PATH)
    shutil.copy2(checkpoint['path'], target)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == checkpoint['sha256']
    return ProductionJourney(player_id, lang='en')


@pytest.fixture
def earned(rav1_earned_checkpoint):
    return _restore_checkpoint(rav1_earned_checkpoint)


@pytest.fixture
def earned_party(rav1_party_checkpoint):
    target = Path(database.DB_PATH)
    shutil.copy2(rav1_party_checkpoint['path'], target)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == rav1_party_checkpoint['sha256']
    return {
        'advanced': ProductionJourney(rav1_party_checkpoint['player_id'], lang='en'),
        'physical': ProductionJourney(rav1_party_checkpoint['physical_id'], lang='en'),
        'magic': ProductionJourney(rav1_party_checkpoint['magic_id'], lang='en'),
        'checkpoint': rav1_party_checkpoint,
    }


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
    before = _state_snapshot(journey.player_id), _inventory_snapshot(journey.player_id)
    await journey.callback(f'rv:d:p:{project_id}', handle_regional_buttons)
    selection_callbacks = [callback for callback in _callbacks(journey.messages[-1][1]) if callback.startswith('rv:c:')]
    assert len(selection_callbacks) == 2
    by_value = {}
    conn = get_connection()
    for callback in selection_callbacks:
        token = callback.removeprefix('rv:c:')
        payload = json.loads(conn.execute('SELECT payload FROM player_ui_actions WHERE token=?', (token,)).fetchone()['payload'])
        by_value[payload['choice']] = callback
    conn.close()
    alternate = next(callback for choice, callback in by_value.items() if choice != value)
    await journey.callback(by_value[value], handle_regional_buttons)
    assert (_state_snapshot(journey.player_id), _inventory_snapshot(journey.player_id)) == before
    preview_callbacks = _callbacks(journey.messages[-1][1])
    confirm = next(callback for callback in preview_callbacks if callback.startswith('rv:a:'))
    assert f'rv:d:p:{project_id}' in preview_callbacks
    await journey.callback(confirm, handle_regional_buttons)
    token = confirm.removeprefix('rv:a:')
    result = _receipt(journey.player_id, token)
    assert result and result['status'] in {'advanced', 'completed'}
    await journey.callback(alternate, handle_regional_buttons)
    assert get_project_state(journey.player_id, project_id)['choices']
    return result


async def _pin_from_emitted_control(journey: ProductionJourney, owner_kind: str, owner_id: str) -> dict:
    if owner_kind == 'project':
        await journey.callback(f'rv:d:p:{owner_id}', handle_regional_buttons)
    elif owner_kind=='gear':
        await journey.callback('inv_catalog',handle_inventory_buttons)
        more=next(c for c in _callbacks(journey.messages[-1][1]) if c.startswith('inv_cmore_'))
        await journey.callback(more,handle_inventory_buttons)
    else:
        await journey.callback('rv:v:p:0:all', handle_regional_buttons)
    conn = get_connection()
    selected = None
    try:
        for callback in _callbacks(journey.messages[-1][1]):
            if not callback.startswith('rv:a:'):
                continue
            token = callback.removeprefix('rv:a:')
            row = conn.execute('SELECT payload FROM player_ui_actions WHERE token=?', (token,)).fetchone()
            payload = json.loads(row['payload']) if row else {}
            pin = payload.get('pin') or {}
            if pin.get('owner_kind') == owner_kind and pin.get('owner_id') == owner_id:
                selected = callback
                break
    finally:
        conn.close()
    assert selected, (owner_kind, owner_id, _callbacks(journey.messages[-1][1]))
    await journey.callback(selected, handle_regional_buttons)
    result = _receipt(journey.player_id, selected.removeprefix('rv:a:'))
    assert result
    return result


async def _inspect(journey: ProductionJourney, fact_id: str, location_id: str) -> dict:
    await _move(journey, location_id)
    return await _rav_action(journey, fact_id, 'inspect')


async def _fight_spawn(journey: ProductionJourney, callback: str) -> str:
    await journey.callback(callback, handle_combat_buttons)
    enter = next(value for value in _callbacks(journey.messages[-1][1]) if value.startswith('pve_view_'))
    encounter_id = enter.removeprefix('pve_view_')
    journey.start_due_formation(encounter_id)
    await journey.callback(f'pve_enter_{encounter_id}', handle_location_buttons)
    opening = (('skill', 'defensive_stance'), ('skill', 'shield_bash'), ('skill', 'sword_rush'))
    for turn in range(90):
        if 'battle' not in journey.context.user_data:
            break
        kind, skill = opening[turn] if turn < len(opening) else ('basic_attack', None)
        try:
            action = await journey._find_combat_action(kind=kind, skill_id=skill)
        except AssertionError:
            action = await journey._find_combat_action(kind='basic_attack', skill_id=None)
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
        "UPDATE pve_spawn_instances SET respawn_available_at='2000-01-01 00:00:00' "
        "WHERE location_id=? AND special_spawn_key=? AND state='respawning'",
        (location_id, special_key),
    )
    conn.commit(); conn.close()
    ensure_location_pve_spawn_instances(location_id=location_id)
    return await _fight_spawn(journey, f'fight_special_{special_key}')


async def _leave_real_prepared_settlement(
    journey: ProductionJourney, location_id: str, mob_id: str,
) -> str:
    """Play a canonical fight while injecting a crash only at T2 application."""
    await _move(journey, location_id)
    spawn_id = journey._accelerate_respawn(mob_id)
    await journey.callback(f'fight_spawn_{spawn_id}', handle_combat_buttons)
    enter = next(value for value in _callbacks(journey.messages[-1][1])
                 if value.startswith('pve_view_'))
    encounter_id = enter.removeprefix('pve_view_')
    journey.start_due_formation(encounter_id)
    await journey.callback(f'pve_enter_{encounter_id}', handle_location_buttons)
    battle_handler = __import__('handlers.battle', fromlist=['handle_battle_buttons'])
    with patch(
        'game.pve_reward_settlement.apply_prepared_settlement',
        side_effect=RuntimeError('simulated restart after durable T1'),
    ):
        for turn in range(90):
            settlement = get_settlement(encounter_id)
            if settlement and settlement['status'] == 'prepared':
                break
            opening = (('skill', 'defensive_stance'), ('skill', 'shield_bash'), ('skill', 'sword_rush'))
            kind, skill = opening[turn] if turn < len(opening) else ('basic_attack', None)
            try:
                action = await journey._find_combat_action(kind=kind, skill_id=skill)
            except AssertionError:
                action = await journey._find_combat_action(kind='basic_attack', skill_id=None)
            await journey.callback(action, battle_handler.handle_battle_buttons)
        else:
            raise AssertionError(('prepared settlement not reached', encounter_id))
    settlement = get_settlement(encounter_id)
    assert settlement and settlement['status'] == 'prepared'
    return encounter_id


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


async def _complete_medic_practice(journey):
    await _ensure_resource(journey, 'herb_common', 6, [])
    await _move(journey, 'hub_mireveil')
    await _rav_action(journey, 'mv_medic_practice', 'start')
    for _ in range(2):
        await _move(journey, 'capital_city')
        await _craft_known(journey, 'field_tonic')
    await _move(journey, 'hub_mireveil')
    await _rav_action(journey, 'mv_medic_practice', 'deliver', objective_id='tonics')


async def _ensure_rations(journey, quantity: int):
    while _quantity(journey.player_id, 'field_ration') < quantity:
        await _ensure_resource(journey, 'herb_common', 1, [])
        while _quantity(journey.player_id, 'boar_meat') < 1:
            await _fight_and_harvest(
                journey, location_id='westwild_n2', mob_id='forest_boar',
                item_id='boar_meat', encounter_ids=[],
            )
        await _move(journey, 'capital_city')
        await _craft_known(journey, 'trail_ration')


async def _complete_finite_region(journey, region: str):
    if region == 'westwild':
        await _complete_tool(journey)
        await _ensure_rations(journey, 2)
        await _request(journey, 'ww_woodcutter_provisions', 'hub_westwild')
        await _inspect(journey, 'ww_root_marks', 'westwild_n7')
        await _rav_action(journey, 'ww_root_cache', 'claim')
    elif region == 'frostspine':
        await _complete_sled(journey)
    elif region == 'ashen_ruins':
        await _complete_names(journey)
        await _complete_storehouse(journey)
    elif region == 'sunscar':
        await _complete_camp(journey)
    elif region == 'mireveil':
        await _complete_ferry(journey)
        await _complete_medic_practice(journey)
        await _ensure_resource(journey, 'herb_common', 4, [])
        await _request(journey, 'mv_medic_table', 'hub_mireveil')
    else:
        raise AssertionError(region)


async def _complete_all_finite(journey, regions):
    for region in regions:
        await _complete_finite_region(journey, region)


async def _ensure_resource(journey, item_id: str, quantity: int, sequence: list[str]):
    missing = max(0, quantity - _quantity(journey.player_id, item_id))
    if not missing:
        return
    await _gather(journey, item_id, missing, sequence)


async def _rest_if_needed(journey: ProductionJourney):
    player = dict(get_player(journey.player_id))
    if int(player['hp']) < int(player['max_hp']) or int(player['mana']) < int(player['max_mana']):
        await journey.rest_at_current_inn()


async def _claim_hunt(journey: ProductionJourney, contract_key: str, location_id: str) -> dict:
    await _move(journey, location_id)
    token = issue_actions(journey.player_id, 'contract_claim', [contract_key])[contract_key]
    claimed, status, result = claim_completed_hunt_contract(
        player_id=journey.player_id, location_id=location_id, action_token=token)
    assert claimed and status == 'claimed' and result
    replay = claim_completed_hunt_contract(
        player_id=journey.player_id, location_id=location_id, action_token=token)
    assert replay[0] is False and replay[1] in {'already_claimed', 'no_active_contract'}
    return result


async def _craft_known(journey: ProductionJourney, recipe_id: str) -> dict:
    payload = recipe_intent_payload(recipe_id)
    token = issue_actions(journey.player_id, 'craft', [payload])[payload]
    result = craft_recipe(journey.player_id, recipe_id, action_token=token)
    assert result.status == 'crafted'
    return {'token': token, 'result': result}


def _gift_one(sender: ProductionJourney, recipient: ProductionJourney, item_id: str) -> dict:
    conn = get_connection()
    row = conn.execute(
        '''SELECT * FROM inventory WHERE telegram_id=? AND item_id=? AND quantity>0
           ORDER BY id LIMIT 1''',
        (sender.player_id, item_id),
    ).fetchone()
    conn.close()
    assert row, (sender.player_id, item_id)
    payload = json.dumps({
        'recipient_id': recipient.player_id,
        'inventory_id': row['id'],
        'item_id': row['item_id'],
        'quantity': row['quantity'],
        'enhance_level': row['enhance_level'],
        'durability': row['durability'],
    }, sort_keys=True, separators=(',', ':'))
    token = issue_actions(sender.player_id, 'gift', [payload])[payload]
    sender_before = _quantity(sender.player_id, item_id)
    recipient_before = _quantity(recipient.player_id, item_id)
    result = gift_inventory_item(sender.player_id, token)
    assert result['status'] == 'gifted'
    assert _quantity(sender.player_id, item_id) == sender_before - 1
    assert _quantity(recipient.player_id, item_id) == recipient_before + 1
    replay = gift_inventory_item(sender.player_id, token)
    assert replay['status'] == 'gifted' and replay['recovered'] is True
    assert _quantity(sender.player_id, item_id) == sender_before - 1
    assert _quantity(recipient.player_id, item_id) == recipient_before + 1
    return {'token': token, 'result': result}


def _state_snapshot(player_id: int) -> dict:
    player = dict(get_player(player_id))
    return {
        'level': int(player['level']), 'exp': int(player['exp']), 'gold': int(player['gold']),
        'strength': int(player['strength']), 'agility': int(player['agility']),
        'intuition': int(player['intuition']), 'vitality': int(player['vitality']),
        'wisdom': int(player['wisdom']), 'luck': int(player['luck']),
        'claims': sorted(list_claims(player_id)),
    }


def _inventory_snapshot(player_id: int) -> dict[str, int]:
    conn = get_connection()
    rows = conn.execute(
        '''SELECT item_id,SUM(quantity) AS quantity FROM inventory
           WHERE telegram_id=? GROUP BY item_id ORDER BY item_id''',
        (player_id,),
    ).fetchall()
    conn.close()
    return {str(row['item_id']): int(row['quantity']) for row in rows}


def _pve_world_snapshot() -> list[tuple]:
    conn = get_connection()
    rows = [tuple(row) for row in conn.execute(
        '''SELECT spawn_instance_id,state,linked_encounter_id,respawn_available_at
           FROM pve_spawn_instances ORDER BY spawn_instance_id''')]
    conn.close()
    return rows


def test_j01_fresh_onboarding(rav1_earned_checkpoint, earned):
    async def run():
        assert rav1_earned_checkpoint['sha256'] and len(rav1_earned_checkpoint['sha256']) == 64
        assert 'chapter_homecoming' in get_contract_history(earned.player_id)
        assert not any(get_project_state(earned.player_id, key) for key in PROJECTS_BY_ID)
        await earned.text('/journal', journal_command)
        text, markup = earned.messages[-1]
        assert len(_callbacks(markup))==8
        assert {'rv:v:p:0:all','quest_board_back','rv:v:r:0:all','rv:v:l:0:all',
                'rv:v:s:0:all','rv:v:s:0:ww','rv:v:w:0:all','alpha_history'}==set(_callbacks(markup))
        assert t('pxe1.journal.choose_direction','en') in text
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

        presented_hunts = set()
        emitted_hunts = set()
        for location in ('capital_city', 'frostspine_n5', 'ashen_n3a2', 'mireveil_n5a1', 'hub_sunscar'):
            await _move(earned, location)
            if 'quest_board' in get_location(location).get('services', []):
                details=await _board_details(earned)
                for contract in list_hunt_contracts_for_location(location):
                    if contract.chapter_order:
                        continue
                    if contract.contract_key in details and build_contract_row(contract,'en') in details[contract.contract_key][0]:
                        presented_hunts.add(contract.contract_key)
                emitted_hunts.update(
                    value.removeprefix('quest_board_accept_')
                    for _,markup in details.values() for value in _callbacks(markup) if value.startswith('quest_board_accept_')
                )
        required = {
            'hunt_greyfang', 'hunt_frostspine_white_wolves', 'hunt_ashen_zombie_clusters',
            'hunt_mireveil_leech_swarms', 'hunt_sunscar_scorpions',
            'hunt_sunscar_air_elementals',
        }
        assert required <= presented_hunts
        assert required <= emitted_hunts

        # A separately and legitimately registered novice reaches the same
        # production board and receives the real rank denial for the elite
        # Air Elemental contract.
        novice = ProductionJourney(BELOW_RANK_PLAYER_ID, lang='en')
        await novice.register(primary='agility', name='RAV1 Novice')
        assert get_player_hunter_progress(novice.player_id)['current_rank'] == 'novice'
        await _move(novice, 'hub_sunscar')
        novice_text, novice_markup = (await _board_details(novice))['hunt_sunscar_air_elementals']
        air = HUNT_CONTRACTS_BY_KEY['hunt_sunscar_air_elementals']
        assert build_contract_row(air, 'en') in novice_text
        assert t('location.quest_board_locked_reason_rank', 'en',
                 rank=t('location.hunter_rank_tracker', 'en')) in novice_text
        assert 'quest_board_accept_hunt_sunscar_air_elementals' not in _callbacks(novice_markup)
        await _move(earned, 'capital_city')
        wrong_token = issue_regional_action(earned.player_id, 'mv_medic_table', 'deliver')
        wrong_query = await earned.callback(f'rv:a:{wrong_token}', handle_regional_buttons)
        assert wrong_query.answer.await_args.kwargs.get('show_alert') is True
        assert _receipt(earned.player_id, wrong_token) is None
        assert 'mv_medic_table' not in list_claims(earned.player_id)
        assert len(_list_screen(dict(get_player(earned.player_id)), 'r', 0, 'all')[1].inline_keyboard) <= 10
    asyncio.run(run())


def test_j03_different_first_regions_and_solo_paths(rav1_earned_checkpoint, rav1_party_checkpoint):
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

        physical = _restore_checkpoint_as(rav1_party_checkpoint, PHYSICAL_PLAYER_ID)
        await _complete_storehouse(physical)
        assert set(list_claims(physical.player_id)) == {'ar_unquiet_storehouse'}

        magic = _restore_checkpoint_as(rav1_party_checkpoint, MAGIC_PLAYER_ID)
        await _complete_ferry(magic)
        assert set(list_claims(magic.player_id)) == {'mv_ferry_crew'}

        for journey, expected_family in ((physical, 'sword_1h'), (magic, 'magic_staff')):
            conn = get_connection()
            equipped = conn.execute(
                "SELECT base_item_id FROM gear_instances WHERE telegram_id=? AND equipped_slot='weapon'",
                (journey.player_id,),
            ).fetchone()
            mastery = conn.execute(
                'SELECT COALESCE(SUM(exp),0) AS exp FROM weapon_mastery WHERE telegram_id=?',
                (journey.player_id,),
            ).fetchone()
            conn.close()
            assert equipped and str(equipped['base_item_id']).endswith(expected_family)
            assert mastery is not None and int(mastery['exp']) >= 0
    asyncio.run(run())


def test_j04_stay_local(rav1_earned_checkpoint):
    async def run():
        west = _restore_checkpoint(rav1_earned_checkpoint)
        # Earn inputs before the measured regional session; the session itself
        # never leaves Westwild merely to manufacture a hand-in basket.
        await _ensure_resource(west, 'herb_common', 6, [])
        while _quantity(west.player_id, 'field_ration') < 4:
            while _quantity(west.player_id, 'boar_meat') < 1:
                await _fight_and_harvest(west, location_id='westwild_n2', mob_id='forest_boar',
                                         item_id='boar_meat', encounter_ids=[])
            await _move(west, 'hub_westwild')
            await _craft_known(west, 'trail_ration')
        west_trace = []
        async def west_move(location_id):
            assert (get_location(location_id) or {}).get('route_id') == 'route_westwild'
            west_trace.append(location_id)
            await _move(west, location_id)
        await west_move('hub_westwild')
        await _rav_action(west, 'ww_tool_roll', 'start')
        accepted, status = accept_hunt_contract(
            player_id=west.player_id, location_id='hub_westwild', contract_key='hunt_greyfang')
        assert accepted and status == 'accepted'
        await _special_fight(west, 'westwild_n3', 'greyfang')
        await west_move('hub_westwild')
        await _rav_action(west, 'ww_tool_roll', 'respond', objective_id='report')
        await _claim_hunt(west, 'hunt_greyfang', 'hub_westwild')
        await west_move('hub_westwild')
        await _rav_action(west, 'ww_woodcutter_provisions', 'deliver')
        await _rav_action(west, 'ww_ration_order', 'deliver')
        await _inspect(west, 'ww_root_marks', 'westwild_n7')
        await _rav_action(west, 'ww_root_cache', 'claim')
        await west_move('hub_westwild')
        assert any(row['kind'] == 'work_link' for row in nearby(dict(get_player(west.player_id))))
        assert west_trace and all(location != 'capital_city' for location in west_trace)

        mire = _restore_checkpoint(rav1_earned_checkpoint)
        # Pre-earn ordinary ingredients and the standing-work basket.  The two
        # objective crafts are executed only after acceptance, inside Mireveil.
        await _ensure_resource(mire, 'herb_common', 10, [])
        while _quantity(mire.player_id, 'pe_marsh_stew') < 2:
            await _ensure_resource(mire, 'marsh_fish', 2, [])
            await _ensure_resource(mire, 'marsh_herb', 1, [])
            await _ensure_resource(mire, 'salt_crystal', 1, [])
            await _move(mire, 'hub_mireveil')
            await _craft_known(mire, 'pe_cooking_marsh_06')
        mire_trace = []
        async def mire_move(location_id):
            assert (get_location(location_id) or {}).get('route_id') == 'route_mireveil'
            mire_trace.append(location_id)
            await _move(mire, location_id)
        await mire_move('hub_mireveil')
        await _rav_action(mire, 'mv_medic_table', 'deliver')
        await _rav_action(mire, 'mv_medic_practice', 'start')
        for _ in range(2):
            await _craft_known(mire, 'field_tonic')
        await mire_move('hub_mireveil')
        await _rav_action(mire, 'mv_medic_practice', 'deliver', objective_id='tonics')
        await mire_move('mireveil_n5a1')
        accepted, status = accept_hunt_contract(
            player_id=mire.player_id, location_id='mireveil_n5a1',
            contract_key='hunt_mireveil_leech_swarms')
        assert accepted and status == 'accepted'
        for _ in range(5):
            await mire_move('mireveil_n5')
            await mire.fight('leech')
            await mire_move('hub_mireveil')
            await _rest_if_needed(mire)
        await _claim_hunt(mire, 'hunt_mireveil_leech_swarms', 'mireveil_n5a1')
        await mire_move('hub_mireveil')
        await _rav_action(mire, 'mv_stew_order', 'deliver')
        local = nearby(dict(get_player(mire.player_id)))
        assert any(row['kind'] == 'work_link' for row in local)
        assert any(row['kind'] == 'project' for row in local)
        assert mire_trace and all(location != 'capital_city' for location in mire_trace)
    asyncio.run(run())


def test_j05_concurrent_pursuits_pins_and_restart(earned):
    async def run():
        await _move(earned, 'hub_ashen_ruins')
        await _rav_action(earned, 'ar_two_names', 'start')
        await _rav_action(earned, 'ar_unquiet_storehouse', 'start')
        for project_id in ('ar_two_names', 'ar_unquiet_storehouse'):
            assert (await _pin_from_emitted_control(earned, 'project', project_id))['status'] == 'pinned'
        await _move(earned, 'ashen_n3a2')
        accepted, status = accept_hunt_contract(
            player_id=earned.player_id, location_id='ashen_n3a2',
            contract_key='hunt_ashen_zombie_clusters')
        assert accepted and status == 'accepted'
        assert (await _pin_from_emitted_control(
            earned, 'hunt', 'hunt_ashen_zombie_clusters'))['status'] == 'pinned'
        assert set_equipment_goal(earned.player_id, 'field_sword_1h')
        fourth = await _pin_from_emitted_control(earned, 'gear', 'current')
        assert fourth['status'] == 'pins_full'
        assert len(list_pins(earned.player_id)) == 3
        removed = await _pin_from_emitted_control(earned, 'project', 'ar_two_names')
        assert removed['status'] == 'unpinned'
        added = await _pin_from_emitted_control(earned, 'gear', 'current')
        assert added['status'] == 'pinned'
        await _inspect(earned, 'ar_temple_names', 'ashen_n3a2')
        await _inspect(earned, 'ar_storehouse_seal', 'ashen_n3b1')
        assert get_project_state(earned.player_id, 'ar_two_names')['progress']['evidence.temple'] == 1
        assert get_project_state(earned.player_id, 'ar_unquiet_storehouse')['step_index'] == 1
        pins_before = [(row['slot'], row['owner_kind'], row['owner_id']) for row in list_pins(earned.player_id)]
        database.init_db()
        conn = get_connection(); ensure_regional_schema(conn); conn.close()
        assert [(row['slot'], row['owner_kind'], row['owner_id']) for row in list_pins(earned.player_id)] == pins_before
        assert get_project_state(earned.player_id, 'ar_two_names')['state'] == 'active'
        text, markup = _list_screen(dict(get_player(earned.player_id)), 'p', 0, 'all')
        assert text and 'rv:d:p:ar_unquiet_storehouse' in _callbacks(markup)
        assert 'rv:d:p:ar_two_names' not in _callbacks(markup)
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
        before = _state_snapshot(earned.player_id)
        ration_before = _quantity(earned.player_id, 'field_ration')
        await _inspect(earned, 'ar_temple_names', 'ashen_n3a2')
        await _inspect(earned, 'ar_garden_ledger', 'ashen_n3c1')
        await _inspect(earned, 'ss_pillar_shadow', 'sunscar_n8a2')
        await _inspect(earned, 'ss_camp_marks', 'sunscar_n8a1')
        await _inspect(earned, 'fs_sled_damage', 'old_mine_entrance')
        after_inspection = _state_snapshot(earned.player_id)
        assert (after_inspection['level'], after_inspection['exp'], after_inspection['gold'], after_inspection['claims']) == (
            before['level'], before['exp'], before['gold'], before['claims'])
        assert _quantity(earned.player_id, 'field_ration') == ration_before

        await _move(earned, 'hub_ashen_ruins')
        await _rav_action(earned, 'ar_two_names', 'start')
        assert get_project_state(earned.player_id, 'ar_two_names')['step_index'] == 1
        await _move(earned, 'sunscar_n8a1')
        await _rav_action(earned, 'ss_camp_bearings', 'start')
        assert get_project_state(earned.player_id, 'ss_camp_bearings')['step_index'] == 1
        cache_token = issue_regional_action(
            earned.player_id, 'ss_camp_bearings', 'respond', objective_id='open_cache')
        await earned.callback(f'rv:a:{cache_token}', handle_regional_buttons)
        cache_result = _receipt(earned.player_id, cache_token)
        assert cache_result and cache_result['status'] == 'completed'
        assert _quantity(earned.player_id, 'field_ration') == ration_before + 1
        assert execute_regional_action(earned.player_id, cache_token)['recovered'] is True
        assert _quantity(earned.player_id, 'field_ration') == ration_before + 1
        assert list_claims(earned.player_id)['ss_camp_bearings']['gold'] == 12

        await _move(earned, 'old_mine_entrance')
        await _rav_action(earned, 'fs_jammed_sled', 'start')
        assert get_project_state(earned.player_id, 'fs_jammed_sled')['step_index'] == 1
    asyncio.run(run())


def test_j08_low_profession_route(rav1_party_checkpoint):
    journey = _restore_checkpoint_as(rav1_party_checkpoint, PHYSICAL_PLAYER_ID)
    async def run():
        conn = get_connection()
        before_professions = {row['profession_key']: int(row['level']) for row in conn.execute(
            'SELECT profession_key,level FROM player_gathering_professions WHERE telegram_id=?',
            (journey.player_id,))}
        conn.close()
        assert max(before_professions.values(), default=1) < 6
        wood_before = _quantity(journey.player_id, 'wood_common')
        iron_before = _quantity(journey.player_id, 'iron_ore')
        await _complete_sled(journey)
        assert _quantity(journey.player_id, 'wood_common') == wood_before
        assert _quantity(journey.player_id, 'iron_ore') == iron_before
        await _complete_names(journey)
        await _complete_camp(journey)
        await _ensure_resource(journey, 'herb_common', 4, [])
        await _move(journey, 'hub_mireveil')
        await _rav_action(journey, 'mv_medic_table', 'deliver')
        claims = list_claims(journey.player_id)
        assert {'fs_jammed_sled','ar_two_names','ss_camp_bearings','mv_medic_table'} <= set(claims)
        conn = get_connection()
        after_levels = [int(row['level']) for row in conn.execute(
            'SELECT level FROM player_gathering_professions WHERE telegram_id=?',
            (journey.player_id,))]
        conn.close()
        assert max(after_levels, default=1) < 6
    asyncio.run(run())


def test_j09_personal_practice(earned_party):
    recipient = earned_party['physical']
    donor = earned_party['advanced']
    async def run():
        # A legal pre-acceptance craft produces inventory but no process credit.
        await _ensure_resource(recipient, 'herb_common', 3, [])
        await _move(recipient, 'capital_city')
        pre_accept = await _craft_known(recipient, 'field_tonic')
        assert pre_accept['result'].profession_xp > 0
        assert get_project_state(recipient.player_id, 'mv_medic_practice') is None

        # XP policy 2 awards material-based XP rather than the old 250 XP.
        # Earn the near-ceiling state before acceptance through actual crafts;
        # the two post-acceptance crafts still prove positive then zero XP.
        for _ in range(400):
            conn = get_connection()
            alchemy = conn.execute(
                "SELECT level,exp FROM player_crafting_professions "
                "WHERE player_id=? AND profession_key='alchemy'", (recipient.player_id,)
            ).fetchone()
            conn.close()
            if int(alchemy['level']) == 5 and int(alchemy['exp']) >= 246:
                break
            assert int(alchemy['level']) < 6
            await _ensure_resource(recipient, 'herb_common', 3, [])
            await _move(recipient, 'capital_city')
            assert (await _craft_known(recipient, 'field_tonic'))['result'].profession_xp > 0
        else:
            raise AssertionError('earned tonic practice did not approach its level-6 ceiling')

        await _move(recipient, 'hub_mireveil')
        await _rav_action(recipient, 'mv_medic_practice', 'start')
        premature = await _rav_action(
            recipient, 'mv_medic_practice', 'deliver', objective_id='tonics')
        assert premature['status'] == 'incompatible_step'
        assert not premature['consumed']
        state = get_project_state(recipient.player_id, 'mv_medic_practice')
        assert state['progress']['practice.fresh_tonics'] == 0

        # A permitted transfer is valid inventory, but not the recipient's craft evidence.
        _gift_one(donor, recipient, 'health_potion_small')
        state = get_project_state(recipient.player_id, 'mv_medic_practice')
        assert state['progress']['practice.fresh_tonics'] == 0

        crafted_tokens = []
        xp_awarded = []
        for _ in range(2):
            await _ensure_resource(recipient, 'herb_common', 3, [])
            await _move(recipient, 'capital_city')
            payload = recipe_intent_payload('field_tonic')
            token = issue_actions(recipient.player_id, 'craft', [payload])[payload]
            crafted = craft_recipe(recipient.player_id, 'field_tonic', action_token=token)
            assert crafted.status == 'crafted'
            crafted_tokens.append(token)
            xp_awarded.append(crafted.profession_xp)
        # The first post-acceptance craft reaches the recipe's level-6 training
        # ceiling; the second still counts as a successful execution but awards
        # the policy-defined zero XP at that ceiling.
        assert xp_awarded[0] > 0 and xp_awarded[1] == 0
        conn = get_connection()
        alchemy = conn.execute(
            "SELECT level,exp FROM player_crafting_professions WHERE player_id=? AND profession_key='alchemy'",
            (recipient.player_id,),
        ).fetchone()
        conn.close()
        assert (int(alchemy['level']), int(alchemy['exp'])) == (6, 0)
        assert craft_recipe(
            recipient.player_id, 'field_tonic', action_token=crafted_tokens[0]).recovered
        state = get_project_state(recipient.player_id, 'mv_medic_practice')
        assert state['step_index'] == 1
        assert state['progress']['practice.fresh_tonics'] == 2

        before_delivery = _quantity(recipient.player_id, 'health_potion_small')
        await _move(recipient, 'hub_mireveil')
        result = await _rav_action(
            recipient, 'mv_medic_practice', 'deliver', objective_id='tonics')
        assert result['status'] == 'completed'
        assert result['consumed'] == [{'item_id': 'health_potion_small', 'quantity': 2}]
        assert _quantity(recipient.player_id, 'health_potion_small') == before_delivery - 2
        assert 'mv_medic_practice' in list_claims(recipient.player_id)
    asyncio.run(run())


def test_j10_ordinary_delivery(earned_party):
    donor = earned_party['advanced']
    recipient = earned_party['physical']
    async def run():
        # The advanced character legally gathers and crafts every transferred good.
        await _ensure_resource(donor, 'herb_common', _quantity(donor.player_id, 'herb_common') + 8, [])
        await _ensure_resource(donor, 'iron_ore', _quantity(donor.player_id, 'iron_ore') + 2, [])
        await _ensure_resource(donor, 'coal', _quantity(donor.player_id, 'coal') + 2, [])
        await _ensure_resource(donor, 'marsh_fish', _quantity(donor.player_id, 'marsh_fish') + 4, [])
        await _ensure_resource(donor, 'marsh_herb', _quantity(donor.player_id, 'marsh_herb') + 2, [])
        await _ensure_resource(donor, 'salt_crystal', _quantity(donor.player_id, 'salt_crystal') + 2, [])
        # Full-catalogue training legitimately spends its earlier meat stock.
        while _quantity(donor.player_id, 'boar_meat') < 4:
            await _fight_and_harvest(
                donor, location_id='westwild_n2', mob_id='forest_boar',
                item_id='boar_meat', encounter_ids=[],
            )
        await _move(donor, 'capital_city')
        for _ in range(4):
            assert (await _craft_known(donor, 'trail_ration'))['result'].status == 'crafted'
        for _ in range(2):
            assert (await _craft_known(donor, 'pe_cooking_marsh_06'))['result'].status == 'crafted'

        delivery_totals = {
            'field_ration': 4, 'herb_common': 4, 'iron_ore': 2,
            'coal': 2, 'pe_marsh_stew': 2,
        }
        for item_id, target in delivery_totals.items():
            before = _quantity(recipient.player_id, item_id)
            quantity = max(0, target - before)
            for _ in range(quantity):
                _gift_one(donor, recipient, item_id)
            assert _quantity(recipient.player_id, item_id) == target

        conn = get_connection()
        recipient_professions = {row['profession_key']: int(row['level']) for row in conn.execute(
            'SELECT profession_key,level FROM player_crafting_professions WHERE player_id=?',
            (recipient.player_id,))}
        conn.close()
        assert recipient_professions['cooking'] < 6

        finite = (
            ('ww_woodcutter_provisions', 'hub_westwild', [('field_ration', 2)], 18, 20),
            ('mv_medic_table', 'hub_mireveil', [('herb_common', 4)], 18, 20),
        )
        for content_id, location, items, gold, xp in finite:
            await _move(recipient, location)
            token = issue_regional_action(recipient.player_id, content_id, 'deliver')
            before_gold = int(get_player(recipient.player_id)['gold'])
            before_items = {item: _quantity(recipient.player_id, item) for item, _ in items}
            await recipient.callback(f'rv:a:{token}', handle_regional_buttons)
            result = _receipt(recipient.player_id, token)
            assert result['status'] == 'completed'
            assert result['consumed'] == [{'item_id': item, 'quantity': quantity} for item, quantity in items]
            assert result['gold_delta'] == gold
            assert list_claims(recipient.player_id)[content_id]['xp'] == xp
            assert int(get_player(recipient.player_id)['gold']) == before_gold + gold
            for item, quantity in items:
                assert _quantity(recipient.player_id, item) == before_items[item] - quantity
            assert execute_regional_action(recipient.player_id, token)['recovered'] is True
            replay_gold = int(get_player(recipient.player_id)['gold'])
            replay_items = {item: _quantity(recipient.player_id, item) for item, _ in items}
            fresh = issue_regional_action(recipient.player_id, content_id, 'deliver')
            # Depending on whether the later standing basket is still present,
            # validation reaches the one-time claim or rejects the missing goods.
            assert execute_regional_action(recipient.player_id, fresh)['status'] in {
                'already_resolved', 'insufficient_goods'}
            assert int(get_player(recipient.player_id)['gold']) == replay_gold
            assert {item: _quantity(recipient.player_id, item) for item, _ in items} == replay_items

        standing = (
            ('ww_ration_order', 'hub_westwild', [('field_ration', 2)], 10),
            ('fs_forge_supplies', 'hub_frostspine', [('iron_ore', 2), ('coal', 2)], 20),
            ('mv_stew_order', 'hub_mireveil', [('pe_marsh_stew', 2)], 12),
        )
        for content_id, location, items, gold in standing:
            await _move(recipient, location)
            token = issue_regional_action(recipient.player_id, content_id, 'deliver')
            before_player = dict(get_player(recipient.player_id))
            before_items = {item: _quantity(recipient.player_id, item) for item, _ in items}
            await recipient.callback(f'rv:a:{token}', handle_regional_buttons)
            result = _receipt(recipient.player_id, token)
            after_player = dict(get_player(recipient.player_id))
            assert result['status'] == 'delivered'
            assert result['consumed'] == [{'item_id': item, 'quantity': quantity} for item, quantity in items]
            assert result['gold_delta'] == gold
            assert int(after_player['gold']) == int(before_player['gold']) + gold
            assert (after_player['level'], after_player['exp']) == (before_player['level'], before_player['exp'])
            for item, quantity in items:
                assert _quantity(recipient.player_id, item) == before_items[item] - quantity
            assert execute_regional_action(recipient.player_id, token)['recovered'] is True
            replay_gold = int(get_player(recipient.player_id)['gold'])
            fresh = issue_regional_action(recipient.player_id, content_id, 'deliver')
            assert execute_regional_action(recipient.player_id, fresh)['status'] == 'insufficient_goods'
            assert int(get_player(recipient.player_id)['gold']) == replay_gold
    asyncio.run(run())


@pytest.mark.parametrize('contract_key', ['hunt_forest_wolves', 'hunt_greyfang'])
def test_j11_combat_overlap(rav1_earned_checkpoint, contract_key):
    journey = _restore_checkpoint(rav1_earned_checkpoint)
    async def run():
        await _move(journey, 'hub_westwild')
        await _rav_action(journey, 'ww_tool_roll', 'start')
        accepted, status = accept_hunt_contract(
            player_id=journey.player_id, location_id='hub_westwild', contract_key=contract_key)
        assert accepted and status == 'accepted'

        encounter_ids = []
        required = HUNT_CONTRACTS_BY_KEY[contract_key].required_kills
        for _ in range(required):
            if contract_key == 'hunt_greyfang':
                encounter_id = await _special_fight(journey, 'westwild_n3', 'greyfang')
            else:
                await _move(journey, 'westwild_n3')
                fight = await journey.fight('forest_wolf')
                encounter_id = fight['encounter_id']
            encounter_ids.append(encounter_id)
            await _recover(journey)

        assert get_project_state(journey.player_id, 'ww_tool_roll')['step_index'] == 1
        conn = get_connection()
        hunt = conn.execute(
            'SELECT * FROM player_hunt_contracts WHERE player_id=?',
            (journey.player_id,),
        ).fetchone()
        conn.close()
        assert hunt and hunt['contract_key'] == contract_key
        assert int(hunt['progress_kills']) == required and hunt['status'] == 'completed'

        # Reapplying or restarting settlement recovery cannot repeat either
        # combat loot or either independently bound objective.
        before_replay = (_state_snapshot(journey.player_id), _inventory_snapshot(journey.player_id))
        replay = apply_prepared_settlement(encounter_ids[-1])
        assert replay['status'] == 'applied' and replay['already_applied'] is True
        database.init_db()
        assert recover_prepared_settlements() == []
        assert (_state_snapshot(journey.player_id), _inventory_snapshot(journey.player_id)) == before_replay

        await _move(journey, 'hub_westwild')
        report = await _rav_action(journey, 'ww_tool_roll', 'respond', objective_id='report')
        assert report['status'] == 'completed'
        tool_claim = list_claims(journey.player_id)['ww_tool_roll']
        assert (tool_claim['xp'], tool_claim['gold']) == (40, 18)
        await _claim_hunt(journey, contract_key, 'hub_westwild')
        assert contract_key in get_contract_history(journey.player_id)
    asyncio.run(run())


def test_j11_acceptance_after_roster_lock_has_no_credit(rav1_earned_checkpoint):
    journey = _restore_checkpoint(rav1_earned_checkpoint)
    async def run():
        await _move(journey, 'westwild_n3')
        encounter_id = (await journey.fight('forest_wolf'))['encounter_id']
        settlement = get_settlement(encounter_id)
        assert settlement and settlement['status'] == 'applied'
        conn = get_connection()
        binding = conn.execute(
            '''SELECT bindings_json,applied_at FROM rav1_combat_bindings
               WHERE encounter_id=? AND player_id=?''',
            (encounter_id, journey.player_id),
        ).fetchone()
        conn.close()
        assert binding and json.loads(binding['bindings_json']) == [] and binding['applied_at']

        await _move(journey, 'hub_westwild')
        await _rav_action(journey, 'ww_tool_roll', 'start')
        assert get_project_state(journey.player_id, 'ww_tool_roll')['step_index'] == 0
        assert apply_prepared_settlement(encounter_id)['already_applied'] is True
        assert get_project_state(journey.player_id, 'ww_tool_roll')['step_index'] == 0
    asyncio.run(run())


@pytest.mark.parametrize('outcome', ['both_alive', 'one_defeated', 'one_fled'])
def test_j12_optional_group_binding_contract(earned_party, outcome):
    if outcome == 'one_defeated':
        owner, joiner = earned_party['physical'], earned_party['advanced']
    else:
        owner = earned_party['advanced']
        joiner = earned_party['magic' if outcome == 'both_alive' else 'physical']
    async def run():
        reset_solo_pve_runtime_store()
        if outcome == 'both_alive':
            owner_facts_before = set(list_facts(owner.player_id))
            joiner_facts_before = set(list_facts(joiner.player_id))
            await _inspect(owner, 'mv_ford_marks', 'mireveil_n5')
            assert set(list_facts(joiner.player_id)) == joiner_facts_before
            await _inspect(owner, 'mv_channel_rope', 'mireveil_n8')
            await _inspect(joiner, 'mv_ford_marks', 'mireveil_n5')
            await _inspect(joiner, 'mv_channel_rope', 'mireveil_n8')
            assert set(list_facts(owner.player_id)) - owner_facts_before == {
                'mv_ford_marks', 'mv_channel_rope'}
            assert set(list_facts(joiner.player_id)) - joiner_facts_before == {
                'mv_ford_marks', 'mv_channel_rope'}
            for member in (owner, joiner):
                await _move(member, 'hub_mireveil')
                await _rav_action(member, 'mv_ferry_crew', 'start')
                assert get_project_state(member.player_id, 'mv_ferry_crew')['step_index'] == 1
                await _rest_if_needed(member)
                await _move(member, 'mireveil_n6')
            recipe_id = 'rav1_mireveil_n6_crosscurrent'
        else:
            for member in (owner, joiner):
                await _inspect(member, 'mv_ford_marks', 'mireveil_n5')
                await _inspect(member, 'mv_channel_rope', 'mireveil_n8')
                await _move(member, 'hub_mireveil')
                await _rest_if_needed(member)
                await _rav_action(member, 'mv_ferry_crew', 'start')
                assert get_project_state(member.player_id, 'mv_ferry_crew')['step_index'] == 1
            if outcome == 'one_defeated':
                conn = get_connection()
                offhand = conn.execute(
                    '''SELECT id FROM gear_instances
                       WHERE telegram_id=? AND equipped_slot='offhand' ''',
                    (joiner.player_id,),
                ).fetchone()
                conn.close()
                assert offhand
                token = issue_gear_intent(joiner.player_id, 'unequip', int(offhand['id']))
                assert token and apply_gear_intent(
                    joiner.player_id, 'unequip', token)['status'] == 'unequipped'
            for member in (owner, joiner):
                await _move(member, 'mireveil_n6')
            recipe_id = 'rav1_mireveil_n6_crosscurrent'

        with _frozen_combat_clock():
            encounter_id, members, mastery_before = await _start_mixed_group(
                owner, [joiner], recipe_id=recipe_id)
            expected_units = len(MIXED_ENCOUNTERS[recipe_id]['units'])

            if outcome == 'one_fled':
                with patch('handlers.battle.random.randint', return_value=1):
                    await _commit_round(encounter_id, [joiner], {
                        joiner.player_id: ('flee', None, None),
                    })
                conn = get_connection()
                statuses = {int(row['player_id']): row['status'] for row in conn.execute(
                    'SELECT player_id,status FROM pve_encounter_participants WHERE encounter_id=?',
                    (encounter_id,))}
                conn.close()
                assert statuses[joiner.player_id] == 'fled'
                settlement = await _finish_group(
                    encounter_id, [owner], mastery_before,
                    max_rounds=30, expected_unit_count=expected_units)
            elif outcome == 'one_defeated':
                _set_encounter_combat_seed(encounter_id, 'rav1-j12-natural-defeat')
                for _ in range(30):
                    state = _encounter_state(encounter_id)
                    actors = state.get('participant_states_v1') or {}
                    living = [
                        member for member in members
                        if int((actors.get(str(member.player_id)) or {}).get('hp', 0)) > 0]
                    if len(living) == 1:
                        break
                    assert len(living) == 2
                    await _commit_round(
                        encounter_id, living,
                        {member.player_id: ('guard', None, None) for member in living})
                else:
                    raise AssertionError('one earned member was not naturally defeated')
                survivor = living[0]
                settlement = await _finish_group(
                    encounter_id, [survivor], mastery_before,
                    max_rounds=30, expected_unit_count=expected_units)
            else:
                settlement = await _finish_group(
                    encounter_id, members, mastery_before,
                    max_rounds=30, expected_unit_count=expected_units)

        eligible = set(settlement['plan']['eligible_recipient_ids'])
        recipients = {int(row['player_id']) for row in settlement['result']['recipients']}
        if outcome == 'both_alive':
            assert eligible == recipients == {owner.player_id, joiner.player_id}
            for member in (owner, joiner):
                state = get_project_state(member.player_id, 'mv_ferry_crew')
                assert state['step_index'] == 2 and state['choices'] == {}
            outsider = earned_party['physical']
            assert get_project_state(outsider.player_id, 'mv_ferry_crew') is None
            assert not {'mv_ford_marks', 'mv_channel_rope'} & set(list_facts(outsider.player_id))

        else:
            assert len(eligible) == len(recipients) == 1
            assert eligible == recipients

        conn = get_connection()
        bindings = {int(row['player_id']): row for row in conn.execute(
            '''SELECT player_id,applied_at,bindings_json FROM rav1_combat_bindings
               WHERE encounter_id=?''', (encounter_id,))}
        conn.close()
        assert set(bindings) == {owner.player_id, joiner.player_id}
        assert all(row['applied_at'] for row in bindings.values())
        if outcome in {'one_defeated', 'one_fled'}:
            assert all(json.loads(row['bindings_json']) for row in bindings.values())
            excluded = ({owner.player_id, joiner.player_id} - eligible).pop()
            assert get_project_state(excluded, 'mv_ferry_crew')['step_index'] == 1

        # Ferry's leech/snake units intentionally have no harvest outputs. Use
        # a separate legal production group encounter to prove that harvesting
        # remains owner-only even when both earned characters participated in
        # and received ordinary combat settlement from the same victory.
        for member in (owner, joiner):
            await _recover(member, force=True)
            await _move(member, 'westwild_n2')
        with _frozen_combat_clock():
            harvest_encounter_id, harvest_members, harvest_mastery_before = await _start_group(
                owner, [joiner], mob_id='forest_boar')
            _set_encounter_combat_seed(
                harvest_encounter_id, f'rav1-j12-owner-harvest-{outcome}')
            conn = get_connection()
            participant_ids = {
                int(row['player_id']) for row in conn.execute(
                    'SELECT player_id FROM pve_encounter_participants WHERE encounter_id=?',
                    (harvest_encounter_id,),
                )
            }
            conn.close()
            assert participant_ids == {owner.player_id, joiner.player_id}
            harvest_settlement = await _finish_group(
                harvest_encounter_id, harvest_members, harvest_mastery_before,
                expected_unit_count=1,
            )
        assert set(harvest_settlement['plan']['eligible_recipient_ids']) == {
            owner.player_id, joiner.player_id}

        owner_choices = [
            row for row in list_harvestable_victories(owner.player_id, page_size=20)
            if row['encounter_id'] == harvest_encounter_id and row['item_id'] == 'boar_meat'
        ]
        assert len(owner_choices) == 1
        choice = owner_choices[0]
        payload = json.dumps({
            'encounter_id': harvest_encounter_id,
            'unit_id': choice['unit_id'],
            'item_id': choice['item_id'],
        }, sort_keys=True, separators=(',', ':'))
        token = issue_actions(owner.player_id, 'harvest', [payload])[payload]
        owner_before = _quantity(owner.player_id, 'boar_meat')
        harvested = harvest_victory(owner.player_id, harvest_encounter_id, action_token=token)
        assert harvested['status'] == 'harvested'
        assert harvested['item_id'] == 'boar_meat'
        assert harvested['granted'] == [{
            'item_id': 'boar_meat', 'quantity': 1,
            'instance_ids': [], 'gear_specs': [],
        }]
        assert _quantity(owner.player_id, 'boar_meat') == owner_before + 1
        replay = harvest_victory(owner.player_id, harvest_encounter_id, action_token=token)
        assert replay['status'] == 'harvested' and replay['recovered'] is True
        assert _quantity(owner.player_id, 'boar_meat') == owner_before + 1

        conn = get_connection()
        non_owner_before = {
            'inventory': _inventory_snapshot(joiner.player_id),
            'claims': sorted(list_claims(joiner.player_id)),
            'harvest_claims': [tuple(row) for row in conn.execute(
                '''SELECT encounter_id,player_id,item_id,claimed_at
                   FROM pve_harvest_claims WHERE encounter_id=? ORDER BY player_id,item_id''',
                (harvest_encounter_id,),
            )],
            'settlement': get_settlement(harvest_encounter_id),
            'owner_player_id': int(conn.execute(
                'SELECT owner_player_id FROM pve_encounters WHERE encounter_id=?',
                (harvest_encounter_id,),
            ).fetchone()['owner_player_id']),
        }
        conn.close()
        rejected = harvest_victory(
            joiner.player_id, harvest_encounter_id,
            unit_id=choice['unit_id'], item_id=choice['item_id'])
        assert rejected['status'] == 'harvest_not_applied'
        conn = get_connection()
        non_owner_after = {
            'inventory': _inventory_snapshot(joiner.player_id),
            'claims': sorted(list_claims(joiner.player_id)),
            'harvest_claims': [tuple(row) for row in conn.execute(
                '''SELECT encounter_id,player_id,item_id,claimed_at
                   FROM pve_harvest_claims WHERE encounter_id=? ORDER BY player_id,item_id''',
                (harvest_encounter_id,),
            )],
            'settlement': get_settlement(harvest_encounter_id),
            'owner_player_id': int(conn.execute(
                'SELECT owner_player_id FROM pve_encounters WHERE encounter_id=?',
                (harvest_encounter_id,),
            ).fetchone()['owner_player_id']),
        }
        conn.close()
        assert non_owner_after == non_owner_before
    asyncio.run(run())


def test_j13_named_canonical_targets(earned):
    async def run():
        # A pre-notice kill is ordinary combat only and creates no retroactive bounty.
        first_greyfang = await _special_fight(earned, 'westwild_n3', 'greyfang')
        assert 'hunt_greyfang' not in get_contract_history(earned.player_id)
        conn = get_connection()
        assert conn.execute(
            '''SELECT 1 FROM player_hunt_contracts
               WHERE player_id=? AND contract_key='hunt_greyfang'
                 AND status IN ('active','completed')''',
            (earned.player_id,),
        ).fetchone() is None
        conn.close()

        await _move(earned, 'hub_westwild')
        accepted, status = accept_hunt_contract(
            player_id=earned.player_id, location_id='hub_westwild',
            contract_key='hunt_greyfang')
        assert accepted and status == 'accepted'

        # An ordinary wolf remains independent of the named special identity.
        await _move(earned, 'westwild_n3')
        ordinary = await earned.fight('forest_wolf')
        conn = get_connection()
        hunt = conn.execute(
            'SELECT progress_kills,status FROM player_hunt_contracts WHERE player_id=?',
            (earned.player_id,),
        ).fetchone()
        conn.close()
        assert int(hunt['progress_kills']) == 0 and hunt['status'] == 'active'
        ordinary_unit = get_settlement(ordinary['encounter_id'])['plan']['enemy_units'][0]
        assert ordinary_unit['special_spawn_key'] == ''

        second_greyfang = await _special_fight(earned, 'westwild_n3', 'greyfang')
        conn = get_connection()
        hunt = conn.execute(
            'SELECT progress_kills,status FROM player_hunt_contracts WHERE player_id=?',
            (earned.player_id,),
        ).fetchone()
        conn.close()
        assert int(hunt['progress_kills']) == 1 and hunt['status'] == 'completed'
        await _claim_hunt(earned, 'hunt_greyfang', 'hub_westwild')
        assert 'hunt_greyfang' in get_contract_history(earned.player_id)

        await _move(earned, 'hub_sunscar')
        accepted, status = accept_hunt_contract(
            player_id=earned.player_id, location_id='hub_sunscar',
            contract_key='hunt_sunscar_air_elementals')
        assert accepted and status == 'accepted'
        drifter = await _special_fight(earned, 'sunscar_n8a2', 'salt_ridge_drifter')
        conn = get_connection()
        active_sunscar = conn.execute(
            'SELECT contract_key,progress_kills,status FROM player_hunt_contracts WHERE player_id=?',
            (earned.player_id,),
        ).fetchone()
        conn.close()
        assert tuple(active_sunscar) == ('hunt_sunscar_air_elementals', 0, 'active')
        for encounter_id, key, profile in (
            (first_greyfang, 'greyfang', 'normal'),
            (second_greyfang, 'greyfang', 'normal'),
            (drifter, 'salt_ridge_drifter', 'elite'),
        ):
            settlement = get_settlement(encounter_id)
            units = settlement['plan']['enemy_units']
            assert units[0]['special_spawn_key'] == key and units[0]['spawn_profile'] == profile
        drifter_unit = get_settlement(drifter)['plan']['enemy_units'][0]
        assert drifter_unit['mob_id'] == 'air_elemental'
        assert not ({'hunt_sunscar_scorpions', 'hunt_sunscar_air_elementals'}
                    & get_contract_history(earned.player_id))
    asyncio.run(run())


def test_j14_busy_shared_sources(earned_party):
    holder = earned_party['physical']
    pursuer = earned_party['advanced']
    async def run():
        await _inspect(pursuer, 'mv_ford_marks', 'mireveil_n5')
        await _inspect(pursuer, 'mv_channel_rope', 'mireveil_n8')
        await _move(pursuer, 'hub_mireveil')
        await _rav_action(pursuer, 'mv_ferry_crew', 'start')
        await _move(pursuer, 'mireveil_n6')
        ensure_location_pve_spawn_instances(location_id='mireveil_n6')
        pursuer_controls=await _location_encounter_controls(pursuer)
        mixed_control = next(value for value in pursuer_controls
                             if value == 'fight_mixed_rav1_mireveil_n6_crosscurrent')
        await _move(holder, 'mireveil_n6')

        # Hold one ordinary source through its emitted production combat
        # control. The exact mixed recipe must reject without reserving the
        # independently idle companion source.
        ensure_location_pve_spawn_instances(location_id='mireveil_n6')
        holder_controls=await _location_encounter_controls(holder)
        emitted_spawns = [value for value in holder_controls
                          if value.startswith('fight_spawn_')]
        conn = get_connection()
        source_by_callback = {
            f"fight_spawn_{row['spawn_instance_id']}": dict(row)
            for row in conn.execute(
                "SELECT spawn_instance_id,mob_id FROM pve_spawn_instances "
                "WHERE location_id='mireveil_n6' AND state='idle' AND linked_encounter_id IS NULL"
            )
        }
        conn.close()
        source_callback = next(value for value in emitted_spawns
                               if source_by_callback.get(value, {}).get('mob_id') == 'giant_leech')
        await holder.callback(source_callback, handle_combat_buttons)
        held_enter = next(value for value in _callbacks(holder.messages[-1][1])
                          if value.startswith('pve_view_'))
        held_id = held_enter.removeprefix('pve_view_')
        held_projection = next(row for row in nearby(dict(get_player(pursuer.player_id)))
                               if row['content_id']=='rav1_mireveil_n6_crosscurrent')
        assert held_projection['status'] == 'busy'
        mixed_attempt = await pursuer.callback(mixed_control, handle_combat_buttons)
        assert any(call.kwargs.get('show_alert') for call in mixed_attempt.answer.await_args_list)
        assert not any(value.startswith('pve_enter_') for value in _callbacks(pursuer.messages[-1][1]))
        conn = get_connection()
        assert conn.execute(
            "SELECT COUNT(*) AS total FROM pve_spawn_instances "
            "WHERE location_id='mireveil_n6' AND mob_id='water_snake' "
            "AND linked_encounter_id IS NULL AND state='idle'"
        ).fetchone()['total'] > 0
        conn.close()
        assert leave_open_world_pve_encounter(
            encounter_id=held_id, player_id=holder.player_id) == (True, 'left_collapsed')

        await holder.callback(
            'fight_mixed_rav1_mireveil_n6_crosscurrent', handle_combat_buttons)
        enter = next(value for value in _callbacks(holder.messages[-1][1])
                     if value.startswith('pve_view_'))
        forming_id = enter.removeprefix('pve_view_')
        rows = nearby(dict(get_player(pursuer.player_id)))
        mixed = next(row for row in rows if row['content_id']=='rav1_mireveil_n6_crosscurrent')
        assert mixed['status'] == 'busy'
        busy_text, busy_markup = build_detail(
            dict(get_player(pursuer.player_id)), 'e', 'rav1_mireveil_n6_crosscurrent')
        assert busy_text
        assert {'rv:d:e:rav1_mireveil_n6_crosscurrent', 'rv:v:n:0:all', 'rv:v:h:0:all'} <= set(
            _callbacks(busy_markup))
        assert get_project_state(pursuer.player_id, 'mv_ferry_crew')['step_index'] == 1
        conn = get_connection()
        reserved = conn.execute(
            '''SELECT COUNT(*) AS total FROM pve_spawn_instances
               WHERE linked_encounter_id=? AND state='forming' ''',
            (forming_id,),
        ).fetchone()['total']
        assert int(reserved) == 2
        conn.execute(
            '''UPDATE pve_encounters
               SET created_at=datetime('now', ?), updated_at=datetime('now', ?)
               WHERE encounter_id=?''',
            (f'-{FORMING_ENCOUNTER_TTL_SECONDS + 1} seconds',
             f'-{FORMING_ENCOUNTER_TTL_SECONDS + 1} seconds', forming_id),
        )
        conn.commit(); conn.close()

        # Backdating a current formation must never expire it on read.
        still_busy=next(row for row in nearby(dict(get_player(pursuer.player_id)))
                        if row['content_id']=='rav1_mireveil_n6_crosscurrent')
        assert still_busy['status']=='busy'
        conn=get_connection()
        forming=conn.execute('SELECT * FROM pve_encounters WHERE encounter_id=?',(forming_id,)).fetchone()
        assert forming['status']=='active' and forming['runtime_started_ms'] is None
        conn.close()
        holder.start_due_formation(forming_id)
        # Explicit non-victory closure releases both sources with no project
        # credit or rewards, then the controlled respawn clock permits retry.
        finish_solo_pve_encounter(player_id=holder.player_id,encounter_id=forming_id,status='finished')
        assert get_project_state(pursuer.player_id,'mv_ferry_crew')['step_index']==1
        assert get_settlement(forming_id) is None
        conn=get_connection()
        assert conn.execute('SELECT COUNT(*) FROM pve_spawn_instances WHERE linked_encounter_id=?',(forming_id,)).fetchone()[0]==0
        conn.execute("UPDATE pve_spawn_instances SET respawn_available_at='2000-01-01 00:00:00' WHERE location_id='mireveil_n6' AND state='respawning'")
        conn.commit();conn.close()
        ensure_location_pve_spawn_instances(location_id='mireveil_n6')
        assert next(row for row in nearby(dict(get_player(pursuer.player_id)))
                    if row['content_id']=='rav1_mireveil_n6_crosscurrent')['status']=='available'

        completed_id = await _mixed_fight(pursuer, 'rav1_mireveil_n6_crosscurrent')
        assert get_settlement(completed_id)['status'] == 'applied'
        assert get_project_state(pursuer.player_id, 'mv_ferry_crew')['step_index'] == 2
        respawning = next(row for row in nearby(dict(get_player(pursuer.player_id)))
                          if row['content_id']=='rav1_mireveil_n6_crosscurrent')
        assert respawning['status'] == 'respawning'
        ensure_location_pve_spawn_instances(location_id='mireveil_n6')
        conn = get_connection()
        conn.execute(
            "UPDATE pve_spawn_instances SET respawn_available_at='2000-01-01 00:00:00' "
            "WHERE location_id='mireveil_n6' AND state='respawning'")
        conn.commit(); conn.close()
        ensure_location_pve_spawn_instances(location_id='mireveil_n6')
        assert next(row for row in nearby(dict(get_player(pursuer.player_id)))
                    if row['content_id']=='rav1_mireveil_n6_crosscurrent')['status'] == 'available'

        # The named source has the same single-owner contention lifecycle.
        for member in (holder, pursuer):
            await _move(member, 'westwild_n3')
        await holder.callback('fight_special_greyfang', handle_combat_buttons)
        grey_enter = next(value for value in _callbacks(holder.messages[-1][1])
                          if value.startswith('pve_view_'))
        grey_id = grey_enter.removeprefix('pve_view_')
        grey_busy = next(row for row in nearby(dict(get_player(pursuer.player_id)))
                         if row['content_id'] == 'greyfang')
        assert grey_busy['status'] == 'busy'
        assert leave_open_world_pve_encounter(
            encounter_id=grey_id, player_id=holder.player_id) == (True, 'left_collapsed')
        assert next(row for row in nearby(dict(get_player(pursuer.player_id)))
                    if row['content_id'] == 'greyfang')['status'] == 'available'
        grey_done = await _special_fight(pursuer, 'westwild_n3', 'greyfang')
        assert get_settlement(grey_done)['status'] == 'applied'
        assert next(row for row in nearby(dict(get_player(pursuer.player_id)))
                    if row['content_id'] == 'greyfang')['status'] == 'respawning'

        # Activation owns the same write serialization as pruning. Once the
        # roster transition wins, later TTL pruning cannot expire the encounter.
        conn = get_connection()
        conn.execute(
            "UPDATE pve_spawn_instances SET respawn_available_at='2000-01-01 00:00:00' "
            "WHERE location_id='westwild_n3' AND special_spawn_key='greyfang' AND state='respawning'"
        )
        conn.commit(); conn.close()
        ensure_location_pve_spawn_instances(location_id='westwild_n3')
        await holder.callback('fight_special_greyfang', handle_combat_buttons)
        active_enter = next(value for value in _callbacks(holder.messages[-1][1]) if value.startswith('pve_view_'))
        active_id = active_enter.removeprefix('pve_view_')
        holder.start_due_formation(active_id)
        conn=get_connection()
        assert json.loads(conn.execute('SELECT locked_roster_json FROM pve_encounters WHERE encounter_id=?',(active_id,)).fetchone()[0])=={'player_ids':[holder.player_id]}
        conn.close()
        conn = get_connection()
        conn.execute("UPDATE pve_encounters SET created_at=datetime('now','-10 minutes') WHERE encounter_id=?", (active_id,))
        conn.commit()
        assert _prune_expired_forming_encounters(conn, encounter_id=active_id) == []
        conn.close()
        finish_solo_pve_encounter(player_id=holder.player_id, encounter_id=active_id, status='finished')
    asyncio.run(run())


def test_j15_permanent_local_choices(earned_party):
    first = earned_party['advanced']
    second = earned_party['physical']
    outsider = earned_party['magic']
    async def run():
        outsider_before = {
            'state': _state_snapshot(outsider.player_id),
            'inventory': _inventory_snapshot(outsider.player_id),
            'facts': sorted(list_facts(outsider.player_id)),
            'projects': [get_project_state(outsider.player_id, key) for key in PROJECTS_BY_ID],
        }

        async def choose_without_world_change(member, project_id, objective_id, value):
            before = _pve_world_snapshot()
            await _choose(member, project_id, objective_id, value)
            assert _pve_world_snapshot() == before

        # Two Names outcomes.
        for member in (first, second):
            await _inspect(member, 'ar_temple_names', 'ashen_n3a2')
            await _inspect(member, 'ar_garden_ledger', 'ashen_n3c1')
            await _move(member, 'hub_ashen_ruins')
            await _rav_action(member, 'ar_two_names', 'start')
        await choose_without_world_change(first, 'ar_two_names', 'attribution', 'shared_credit')
        await choose_without_world_change(second, 'ar_two_names', 'attribution', 'leave_unattributed')

        # Two Storehouse outcomes after independent real solo fights.
        for member, value in ((first, 'archive_seal'), (second, 'leave_seal')):
            await _inspect(member, 'ar_storehouse_seal', 'ashen_n3b1')
            await _rav_action(member, 'ar_unquiet_storehouse', 'start')
            await _move(member, 'hub_ashen_ruins')
            await _rest_if_needed(member)
            await _move(member, 'ashen_n3b1')
            await member.fight('skeleton_guard')
            await _move(member, 'hub_ashen_ruins')
            await choose_without_world_change(
                member, 'ar_unquiet_storehouse', 'seal_fate', value)

        # Two Ferry outcomes after independently accepted exact encounters.
        for member, value in ((first, 'save_supplies'), (second, 'save_log')):
            await _inspect(member, 'mv_ford_marks', 'mireveil_n5')
            await _inspect(member, 'mv_channel_rope', 'mireveil_n8')
            await _move(member, 'hub_mireveil')
            await _rest_if_needed(member)
            await _rav_action(member, 'mv_ferry_crew', 'start')
            await _mixed_fight(member, 'rav1_mireveil_n6_crosscurrent')
            await _move(member, 'mireveil_n8')
            await choose_without_world_change(member, 'mv_ferry_crew', 'cargo', value)
            await _move(member, 'hub_mireveil')
            await _rav_action(member, 'mv_ferry_crew', 'respond', objective_id='report')

        # Sled alternatives preserve the method record, not a different reward.
        await _complete_sled(first)
        await _inspect(second, 'fs_sled_damage', 'old_mine_entrance')
        await _rav_action(second, 'fs_jammed_sled', 'start')
        await _ensure_resource(second, 'wood_common', 2, [])
        await _ensure_resource(second, 'iron_ore', 1, [])
        await _move(second, 'old_mine_entrance')
        delivered = await _rav_action(
            second, 'fs_jammed_sled', 'deliver', objective_id='materials')
        assert delivered['status'] == 'advanced'
        await _move(second, 'hub_frostspine')
        await _rav_action(second, 'fs_jammed_sled', 'respond', objective_id='receipt')

        database.init_db()
        conn = get_connection(); ensure_regional_schema(conn); conn.close()
        expected = {
            first.player_id: ('shared_credit', 'archive_seal', 'save_supplies'),
            second.player_id: ('leave_unattributed', 'leave_seal', 'save_log'),
        }
        projects = ('ar_two_names', 'ar_unquiet_storehouse', 'mv_ferry_crew')
        for member in (first, second):
            states = [get_project_state(member.player_id, project) for project in projects]
            assert tuple(next(iter(state['choices'].values())) for state in states) == expected[member.player_id]
            assert all(state['state'] == 'completed' for state in states)
            assert all(issue_project_choice_actions(
                member.player_id, project, objective) == {} for project, objective in (
                    ('ar_two_names', 'attribution'),
                    ('ar_unquiet_storehouse', 'seal_fate'),
                    ('mv_ferry_crew', 'cargo'),
                ))
            for project in projects:
                text, markup = build_detail(dict(get_player(member.player_id)), 'p', project)
                assert text and not any(value.startswith('rv:a:') for value in _callbacks(markup))

        first_claims, second_claims = list_claims(first.player_id), list_claims(second.player_id)
        for project in (*projects, 'fs_jammed_sled'):
            assert (first_claims[project]['xp'], first_claims[project]['gold'],
                    first_claims[project]['items']) == (
                        second_claims[project]['xp'], second_claims[project]['gold'],
                        second_claims[project]['items'])
        assert get_project_state(first.player_id, 'fs_jammed_sled')['step_results']['repair'] == ['clear_lizard']
        assert get_project_state(second.player_id, 'fs_jammed_sled')['step_results']['repair'] == ['materials']
        assert get_project_state(first.player_id, 'fs_jammed_sled')['choices'] == {}
        assert get_project_state(second.player_id, 'fs_jammed_sled')['choices'] == {}

        outsider_after = {
            'state': _state_snapshot(outsider.player_id),
            'inventory': _inventory_snapshot(outsider.player_id),
            'facts': sorted(list_facts(outsider.player_id)),
            'projects': [get_project_state(outsider.player_id, key) for key in PROJECTS_BY_ID],
        }
        assert outsider_after == outsider_before
        for member in (first, second):
            home_text, home_markup = build_regional_home(dict(get_player(member.player_id)))
            assert home_text and {'rv:v:r:0:all', 'rv:v:p:0:all'} <= set(_callbacks(home_markup))
    asyncio.run(run())


def test_j16_returning_player_migration(rav1_earned_checkpoint):
    journey = _restore_checkpoint(rav1_earned_checkpoint)
    async def run():
        await _move(journey, 'hub_westwild')
        accepted, status = accept_hunt_contract(
            player_id=journey.player_id, location_id='hub_westwild',
            contract_key='hunt_forest_spiders')
        assert accepted and status == 'accepted'
        # Recreate the genuine pre-RAV1 boundary before the encounter exists,
        # so its locked source correctly has no RAV1 credit marker/bindings.
        conn = get_connection()
        conn.execute('DELETE FROM economy_schema_migrations WHERE version=?', (MIGRATION_VERSION,))
        for table in reversed(TABLES):
            conn.execute(f'DROP TABLE {table}')
        conn.commit(); conn.close()
        encounter_id = await _leave_real_prepared_settlement(
            journey, 'westwild_n3', 'forest_wolf')

        def preserved_snapshot():
            conn = get_connection()
            try:
                return {
                    'player': tuple(conn.execute(
                        '''SELECT level,exp,gold,hp,mana,location_id,in_battle,build_revision,gear_revision
                           FROM players WHERE telegram_id=?''', (journey.player_id,)).fetchone()),
                    'inventory': [tuple(row) for row in conn.execute(
                        '''SELECT item_id,quantity,enhance_level,durability FROM inventory
                           WHERE telegram_id=? ORDER BY item_id,id''', (journey.player_id,))],
                    'gear': [tuple(row) for row in conn.execute(
                        '''SELECT id,base_item_id,equipped_slot,item_tier,rarity,revision
                           FROM gear_instances WHERE telegram_id=? ORDER BY id''', (journey.player_id,))],
                    'gathering': [tuple(row) for row in conn.execute(
                        '''SELECT profession_key,level,exp FROM player_gathering_professions
                           WHERE telegram_id=? ORDER BY profession_key''', (journey.player_id,))],
                    'crafting': [tuple(row) for row in conn.execute(
                        '''SELECT profession_key,level,exp FROM player_crafting_professions
                           WHERE player_id=? ORDER BY profession_key''', (journey.player_id,))],
                    'recipes': [row['recipe_id'] for row in conn.execute(
                        'SELECT recipe_id FROM player_recipe_knowledge WHERE player_id=? ORDER BY recipe_id',
                        (journey.player_id,))],
                    'hunt': tuple(conn.execute(
                        '''SELECT contract_key,progress_kills,status,completed_at,claimed_at
                           FROM player_hunt_contracts WHERE player_id=?''',
                        (journey.player_id,)).fetchone()),
                    'settlement': tuple(conn.execute(
                        '''SELECT status,plan_json,result_json FROM pve_reward_settlements
                           WHERE encounter_id=?''', (encounter_id,)).fetchone()),
                }
            finally:
                conn.close()

        before = preserved_snapshot()
        assert before['hunt'][0:3] == ('hunt_forest_spiders', 0, 'active')
        assert before['settlement'][0] == 'prepared'
        conn = get_connection()
        ensure_regional_schema(conn)
        ensure_regional_schema(conn)
        assert conn.execute('SELECT COUNT(*) FROM rav1_projects').fetchone()[0] == 0
        conn.close()
        assert preserved_snapshot() == before

        recovered = recover_prepared_settlements()
        assert len(recovered) == 1
        assert recovered[0]['status'] == 'applied'
        assert recovered[0]['result']['encounter_id'] == encounter_id
        assert recover_prepared_settlements() == []
        applied = get_settlement(encounter_id)
        assert applied['status'] == 'applied'
        assert apply_prepared_settlement(encounter_id)['already_applied'] is True
        conn = get_connection()
        hunt = conn.execute(
            '''SELECT contract_key,progress_kills,status FROM player_hunt_contracts
               WHERE player_id=?''', (journey.player_id,)).fetchone()
        conn.close()
        assert tuple(hunt) == ('hunt_forest_spiders', 0, 'active')
        text, markup = build_regional_home(dict(get_player(journey.player_id)))
        assert text and 'rv:v:r:0:all' in _callbacks(markup)
    asyncio.run(run())


async def _prepare_atomic_surface(journey: ProductionJourney, surface: str) -> tuple[str, str | None]:
    if surface in {'delivery', 'standing'}:
        while _quantity(journey.player_id, 'field_ration') < 2:
            await _ensure_resource(journey, 'herb_common', 1, [])
            while _quantity(journey.player_id, 'boar_meat') < 1:
                await _fight_and_harvest(
                    journey, location_id='westwild_n2', mob_id='forest_boar',
                    item_id='boar_meat', encounter_ids=[])
            await _move(journey, 'capital_city')
            await _craft_known(journey, 'trail_ration')
        await _move(journey, 'hub_westwild')
        content_id = 'ww_woodcutter_provisions' if surface == 'delivery' else 'ww_ration_order'
        stale = issue_regional_action(journey.player_id, content_id, 'deliver')
        token = issue_regional_action(journey.player_id, content_id, 'deliver')
        return token, stale
    if surface == 'cache':
        await _inspect(journey, 'ww_root_marks', 'westwild_n7')
        stale = issue_regional_action(journey.player_id, 'ww_root_cache', 'claim')
        token = issue_regional_action(journey.player_id, 'ww_root_cache', 'claim')
        return token, stale
    if surface == 'choice':
        await _inspect(journey, 'ar_temple_names', 'ashen_n3a2')
        await _inspect(journey, 'ar_garden_ledger', 'ashen_n3c1')
        await _move(journey, 'hub_ashen_ruins')
        await _rav_action(journey, 'ar_two_names', 'start')
        tokens = issue_project_choice_actions(
            journey.player_id, 'ar_two_names', 'attribution')
        preview = preview_regional_choice(journey.player_id, tokens['shared_credit'])
        assert preview and preview['confirm_token']
        return preview['confirm_token'], tokens['leave_unattributed']
    raise AssertionError(surface)


def _atomic_snapshot(player_id: int) -> dict:
    return {
        'player': _state_snapshot(player_id),
        'inventory': _inventory_snapshot(player_id),
        'projects': {
            key: get_project_state(player_id, key)
            for key in ('ar_two_names', 'mv_medic_practice')
        },
    }


@pytest.mark.parametrize('surface', ['delivery', 'choice', 'cache', 'standing'])
@pytest.mark.parametrize('failure_point', ['before_receipt', 'after_commit'])
def test_j17_atomic_boundaries(rav1_earned_checkpoint, surface, failure_point):
    journey = _restore_checkpoint(rav1_earned_checkpoint)
    async def run():
        token, stale = await _prepare_atomic_surface(journey, surface)
        before = _atomic_snapshot(journey.player_id)
        assert execute_regional_action(journey.player_id, stale)['status'] == 'stale_action'
        assert _atomic_snapshot(journey.player_id) == before
        with pytest.raises(RuntimeError):
            execute_regional_action(
                journey.player_id, token,
                failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError('cut'))
                if point == failure_point else None)

        if failure_point == 'before_receipt':
            assert _atomic_snapshot(journey.player_id) == before
            committed = execute_regional_action(journey.player_id, token)
        else:
            assert _atomic_snapshot(journey.player_id) != before
            committed = execute_regional_action(journey.player_id, token)
            assert committed['recovered'] is True
        expected = 'delivered' if surface == 'standing' else 'completed'
        assert committed['status'] == expected
        after = _atomic_snapshot(journey.player_id)
        replay = execute_regional_action(journey.player_id, token)
        assert replay['status'] == expected and replay['recovered'] is True
        assert _atomic_snapshot(journey.player_id) == after

        if surface == 'choice':
            rejected = execute_regional_action(journey.player_id, stale)
            assert rejected['status'] == 'stale_action'
        else:
            content_id = {
                'delivery': 'ww_woodcutter_provisions',
                'cache': 'ww_root_cache',
                'standing': 'ww_ration_order',
            }[surface]
            operation = 'claim' if surface == 'cache' else 'deliver'
            fresh = issue_regional_action(journey.player_id, content_id, operation)
            rejected = execute_regional_action(journey.player_id, fresh)
            assert rejected['status'] in {'already_resolved', 'insufficient_goods'}
        assert _atomic_snapshot(journey.player_id) == after
    asyncio.run(run())


def test_j17_combat_t2_restart_and_response_loss(earned):
    async def run():
        await _move(earned, 'hub_westwild')
        await _rav_action(earned, 'ww_tool_roll', 'start')
        encounter_id = await _leave_real_prepared_settlement(
            earned, 'westwild_n3', 'forest_wolf')
        conn = get_connection()
        binding = conn.execute(
            'SELECT bindings_json FROM rav1_combat_bindings WHERE encounter_id=? AND player_id=?',
            (encounter_id, earned.player_id),
        ).fetchone()
        conn.close()
        assert binding and json.loads(binding['bindings_json'])
        before = (_state_snapshot(earned.player_id), _inventory_snapshot(earned.player_id),
                  get_project_state(earned.player_id, 'ww_tool_roll'))
        with pytest.raises(RuntimeError, match='after_rav1_progress'):
            apply_prepared_settlement(
                encounter_id,
                failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError(point))
                if point == 'after_rav1_progress' else None)
        assert get_settlement(encounter_id)['status'] == 'prepared'
        assert (_state_snapshot(earned.player_id), _inventory_snapshot(earned.player_id),
                get_project_state(earned.player_id, 'ww_tool_roll')) == before

        with pytest.raises(RuntimeError, match='after_t2_commit'):
            apply_prepared_settlement(
                encounter_id,
                failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError(point))
                if point == 'after_t2_commit' else None)
        assert get_settlement(encounter_id)['status'] == 'applied'
        committed = (_state_snapshot(earned.player_id), _inventory_snapshot(earned.player_id),
                     get_project_state(earned.player_id, 'ww_tool_roll'))
        assert committed[2]['step_index'] == 1
        replay = apply_prepared_settlement(encounter_id)
        assert replay['already_applied'] is True
        assert (_state_snapshot(earned.player_id), _inventory_snapshot(earned.player_id),
                get_project_state(earned.player_id, 'ww_tool_roll')) == committed
    asyncio.run(run())


@pytest.mark.parametrize('content_id,expected_status', [
    ('ww_woodcutter_provisions', 'completed'),
    ('ww_ration_order', 'delivered'),
])
def test_j17_separate_connection_delivery_races(earned_party, content_id, expected_status):
    sender, recipient = earned_party['advanced'], earned_party['physical']
    async def prepare():
        while _quantity(sender.player_id, 'field_ration') < 2:
            await _ensure_resource(sender, 'herb_common', 1, [])
            await _move(sender, 'capital_city')
            await _craft_known(sender, 'trail_ration')
        assert _quantity(sender.player_id, 'field_ration') == 2
        await _move(sender, 'hub_westwild')
    asyncio.run(prepare())

    conn = get_connection()
    row = conn.execute(
        '''SELECT * FROM inventory WHERE telegram_id=? AND item_id='field_ration' ''',
        (sender.player_id,),
    ).fetchone()
    conn.close()
    assert row and int(row['quantity']) == 2
    sale_payload = f"{row['id']}:{row['quantity']}"
    sale_token = issue_actions(sender.player_id, 'sell', [sale_payload])[sale_payload]
    gift_payload = json.dumps({
        'recipient_id': recipient.player_id, 'inventory_id': row['id'],
        'item_id': row['item_id'], 'quantity': row['quantity'],
        'enhance_level': row['enhance_level'], 'durability': row['durability'],
    }, sort_keys=True, separators=(',', ':'))
    gift_token = issue_actions(sender.player_id, 'gift', [gift_payload])[gift_payload]
    handin_token = issue_regional_action(sender.player_id, content_id, 'deliver')
    before_total = (_quantity(sender.player_id, 'field_ration')
                    + _quantity(recipient.player_id, 'field_ration'))
    before_gold = int(get_player(sender.player_id)['gold'])
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(lambda: try_sell_inventory_item(sender.player_id, sale_token)),
            pool.submit(lambda: gift_inventory_item(sender.player_id, gift_token)),
            pool.submit(lambda: execute_regional_action(sender.player_id, handin_token)),
        ]
        results = [future.result() for future in futures]
    statuses = [result['status'] for result in results]
    winners = [status for status in statuses if status in {'sold', 'gifted', expected_status}]
    assert len(winners) == 1
    assert all(value >= 0 for value in (
        _quantity(sender.player_id, 'field_ration'),
        _quantity(recipient.player_id, 'field_ration')))
    after_total = (_quantity(sender.player_id, 'field_ration')
                   + _quantity(recipient.player_id, 'field_ration'))
    assert before_total - after_total == ({'sold': 1, 'gifted': 0}.get(winners[0], 2))
    if winners[0] == expected_status:
        assert int(get_player(sender.player_id)['gold']) == before_gold + (
            18 if content_id == 'ww_woodcutter_provisions' else 10)
    stable = (_state_snapshot(sender.player_id), _inventory_snapshot(sender.player_id),
              _inventory_snapshot(recipient.player_id))
    try_sell_inventory_item(sender.player_id, sale_token)
    gift_inventory_item(sender.player_id, gift_token)
    execute_regional_action(sender.player_id, handin_token)
    assert (_state_snapshot(sender.player_id), _inventory_snapshot(sender.player_id),
            _inventory_snapshot(recipient.player_id)) == stable


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


def test_j18_all_finite_claims_in_two_regional_orders(rav1_earned_checkpoint):
    orders = (
        ('westwild', 'frostspine', 'ashen_ruins', 'sunscar', 'mireveil'),
        ('mireveil', 'sunscar', 'ashen_ruins', 'frostspine', 'westwild'),
    )
    outcomes = []
    for order in orders:
        journey = _restore_checkpoint(rav1_earned_checkpoint)

        async def run():
            before = dict(get_player(journey.player_id))
            await _complete_all_finite(journey, order)
            claims = list_claims(journey.player_id)
            assert set(claims) == {
                'ww_tool_roll', 'fs_jammed_sled', 'ar_two_names',
                'ar_unquiet_storehouse', 'mv_ferry_crew', 'ss_camp_bearings',
                'mv_medic_practice', 'ww_woodcutter_provisions',
                'mv_medic_table', 'ww_root_cache',
            }
            assert sum(int(row['xp']) for row in claims.values()) == 440
            assert sum(int(row['gold']) for row in claims.values()) == 201
            item_totals: dict[str, int] = {}
            for row in claims.values():
                for item in row.get('items', []):
                    item_id, quantity = item['item_id'], item['quantity']
                    item_totals[item_id] = item_totals.get(item_id, 0) + int(quantity)
            assert item_totals == {
                'enhance_shard': 2,
                'field_ration': 1,
                'health_potion_small': 3,
            }
            after = dict(get_player(journey.player_id))
            assert int(after['gold']) - int(before['gold']) >= 201
            assert all(
                get_project_state(journey.player_id, project_id)['state'] == 'completed'
                for project_id in PROJECTS_BY_ID
            )
            assert all(project.catalog_version == 1 for project in PROJECTS_BY_ID.values())
            outcomes.append({
                'level': int(after['level']), 'exp': int(after['exp']),
                'attribute_budget': int(after['attribute_budget']),
                'attributes': tuple(int(after[key]) for key in (
                    'strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck')),
            })

        asyncio.run(run())
    assert outcomes[0] == outcomes[1]


async def _request(journey, content_id, location_id):
    if content_id == 'mv_medic_table':
        await _ensure_resource(journey, 'herb_common', 4, [])
    await _move(journey, location_id)
    return await _rav_action(journey, content_id, 'deliver')


@pytest.mark.parametrize('lang', ['ru','en','es'])
def test_j19_localized_real_handlers(earned_party, lang):
    earned = earned_party['advanced']
    holder = earned_party['physical']

    async def run():
        validate_rav1_locales()
        conn = get_connection()
        conn.execute('UPDATE players SET lang=? WHERE telegram_id IN (?,?)',
                     (lang, earned.player_id, holder.player_id))
        conn.commit(); conn.close()

        # Post-onboarding Journal and real Names evidence/choice handlers.
        await earned.text('/journal', journal_command)
        journal_callbacks = _callbacks(earned.messages[-1][1])
        assert {'rv:v:r:0:all','quest_board_back','alpha_history'}<=set(journal_callbacks)
        _,map_markup=await _open_command(earned,'/map',map_command)
        assert any(value.startswith('px:world:') for value in _callbacks(map_markup))
        assert (await _open_command(earned,'/inventory',inventory_command))[0]
        assert (await _open_command(earned,'/profile',profile_command))[0]

        # Follow source and recipe guidance only from controls emitted by the
        # regional Journal and their destination handlers.
        await _inspect(earned, 'fs_survey_stone', 'frostspine_n4')
        await earned.text('/journal', journal_command)
        nearby_callback = next(value for value in _callbacks(earned.messages[-1][1]) if value=='quest_board_back')
        await earned.callback(nearby_callback, handle_location_buttons)
        from handlers.activities import handle_activity_buttons
        more_callback=next(value for value in _callbacks(earned.messages[-1][1]) if value.startswith('px:local:more:'))
        await earned.callback(more_callback,handle_activity_buttons)
        survey_callback = next(value for value in _callbacks(earned.messages[-1][1])
                               if value.endswith(':fs_survey_stone'))
        await earned.callback(survey_callback, handle_regional_buttons)
        source_callback = next(value for value in _callbacks(earned.messages[-1][1])
                               if value.startswith('pe_m:'))
        await earned.callback(source_callback, handle_profession_buttons)
        assert earned.messages[-1][0]

        await earned.text('/journal', journal_command)
        work_callback = next(value for value in _callbacks(earned.messages[-1][1])
                             if value.startswith('rv:v:w:'))
        await earned.callback(work_callback, handle_regional_buttons)
        ration_callback = next(value for value in _callbacks(earned.messages[-1][1])
                               if value.endswith(':ww_ration_order'))
        await earned.callback(ration_callback, handle_regional_buttons)
        recipe_callback = next(value for value in _callbacks(earned.messages[-1][1])
                               if value.startswith('pe_r:'))
        await earned.callback(recipe_callback, handle_profession_buttons)
        assert earned.messages[-1][0]
        await _complete_names(earned)

        # A wrong-location action produces the locale-specific handler error.
        await _move(earned, 'capital_city')
        wrong_token = issue_regional_action(
            earned.player_id, 'mv_medic_table', 'deliver')
        wrong = await earned.callback(f'rv:a:{wrong_token}', handle_regional_buttons)
        assert wrong.answer.await_args.args[0] == t('rav1.errors.wrong_location', lang)

        # Medic delivery's result is retained so it can be replayed after a
        # language switch without changing the committed mechanics.
        await _ensure_resource(earned, 'herb_common', 4, [])
        await _move(earned, 'hub_mireveil')
        medic_token = issue_regional_action(
            earned.player_id, 'mv_medic_table', 'deliver')
        await earned.callback(f'rv:a:{medic_token}', handle_regional_buttons)
        medic_result = _receipt(earned.player_id, medic_token)
        assert medic_result and medic_result['status'] == 'completed'
        result_callbacks = _callbacks(earned.messages[-1][1])
        assert {'inv_tab_all', 'pe_h:0'} <= set(result_callbacks)
        await earned.callback('pe_h:0', handle_profession_buttons)
        receipt_callback = next(value for value in _callbacks(earned.messages[-1][1])
                                if value.startswith('pe_x:'))
        await earned.callback(receipt_callback, handle_profession_buttons)
        assert 'mv_medic_table' not in earned.messages[-1][0]

        # Camp exploration/cache and both canonical preview types use their
        # actual regional callback routes.
        await _complete_camp(earned)
        await _inspect(earned, 'ww_greyfang_tracks', 'westwild_n3')
        named = await earned.callback('rv:d:e:greyfang', handle_regional_buttons)
        assert named.answer.await_count == 1
        await _move(earned, 'mireveil_n6')
        mixed = await earned.callback(
            'rv:d:e:rav1_mireveil_n6_crosscurrent', handle_regional_buttons)
        assert mixed.answer.await_count == 1

        # Two fresh standing attempts consume four new rations, pay 10 gold
        # apiece, and never create a finite claim or character XP.
        await _ensure_rations(earned, 4)
        await _move(earned, 'hub_westwild')
        standing_before = dict(get_player(earned.player_id))
        claims_before = dict(list_claims(earned.player_id))
        ration_before = _quantity(earned.player_id, 'field_ration')
        first = await _rav_action(earned, 'ww_ration_order', 'deliver')
        second = await _rav_action(earned, 'ww_ration_order', 'deliver')
        standing_after = dict(get_player(earned.player_id))
        assert first['status'] == second['status'] == 'delivered'
        assert _quantity(earned.player_id, 'field_ration') == ration_before - 4
        assert int(standing_after['gold']) == int(standing_before['gold']) + 20
        assert (standing_after['level'], standing_after['exp']) == (
            standing_before['level'], standing_before['exp'])
        assert list_claims(earned.player_id) == claims_before

        # Inn screens/actions stay on the production callback path even when
        # the healthy character correctly needs no recovery.
        await _move(earned, 'hub_mireveil')
        await earned.rest_at_current_inn()

        # Stale and insufficient-goods errors are produced by real issued
        # intents. The second issue invalidates the first discovery token.
        await _move(earned, 'westwild_n7')
        stale_token = issue_regional_action(
            earned.player_id, 'ww_root_marks', 'inspect')
        assert issue_regional_action(earned.player_id, 'ww_root_marks', 'inspect')
        stale = await earned.callback(f'rv:a:{stale_token}', handle_regional_buttons)
        assert stale.answer.await_args.args[0] == t('rav1.errors.stale_action', lang)
        # XP policy 2 produces more ordinary food while training. Sell the
        # earned surplus through the real protected Shop flow before testing
        # the actual insufficient-goods denial.
        from tests.test_professions_economy_v1_journeys import _sell_owned
        await _move(earned,'capital_city')
        while _quantity(earned.player_id,'pe_marsh_stew')>=2:
            conn=get_connection()
            stack=conn.execute("SELECT id,quantity FROM inventory WHERE telegram_id=? AND item_id='pe_marsh_stew'",(earned.player_id,)).fetchone()
            conn.close()
            await _sell_owned(earned,'i'+str(stack['id']),min(99,stack['quantity']))
        assert _quantity(earned.player_id, 'pe_marsh_stew') < 2
        await _move(earned, 'hub_mireveil')
        short_token = issue_regional_action(
            earned.player_id, 'mv_stew_order', 'deliver')
        short = await earned.callback(f'rv:a:{short_token}', handle_regional_buttons)
        assert short.answer.await_args.args[0] == t('rav1.errors.insufficient_goods', lang)

        # A second earned player owns the exact mixed source, so both its busy
        # preview and the attempted combat callback are localized real paths.
        for member in (holder, earned):
            await _move(member, 'mireveil_n6')
        await holder.callback(
            'fight_mixed_rav1_mireveil_n6_crosscurrent', handle_combat_buttons)
        enter = next(value for value in _callbacks(holder.messages[-1][1])
                     if value.startswith('pve_view_'))
        encounter_id = enter.removeprefix('pve_view_')
        await earned.callback(
            'rv:d:e:rav1_mireveil_n6_crosscurrent', handle_regional_buttons)
        assert t('rav1.errors.busy_target', lang) in earned.messages[-1][0]
        busy = await earned.callback(
            'fight_mixed_rav1_mireveil_n6_crosscurrent', handle_combat_buttons)
        assert busy.answer.await_count >= 1
        assert any(call.kwargs.get('show_alert') for call in busy.answer.await_args_list)
        assert leave_open_world_pve_encounter(
            encounter_id=encounter_id, player_id=holder.player_id)[0] is True

        # Replaying a saved completion renders in the player's new locale but
        # recovers the exact original receipt and grants nothing again.
        next_lang = {'ru':'en', 'en':'es', 'es':'ru'}[lang]
        conn = get_connection()
        conn.execute('UPDATE players SET lang=? WHERE telegram_id=?',
                     (next_lang, earned.player_id))
        conn.commit(); conn.close()
        claims_before_replay = dict(list_claims(earned.player_id))
        replay = await earned.callback(
            f'rv:a:{medic_token}', handle_regional_buttons)
        assert replay.answer.await_args.args[0] == t('rav1.status.resolved', next_lang)
        assert _receipt(earned.player_id, medic_token) == medic_result
        assert list_claims(earned.player_id) == claims_before_replay

        claims = list_claims(earned.player_id)
        assert (claims['ar_two_names']['xp'], claims['ar_two_names']['gold']) == (50, 20)
        assert (claims['ss_camp_bearings']['xp'], claims['ss_camp_bearings']['gold']) == (30, 12)
        assert (claims['mv_medic_table']['xp'], claims['mv_medic_table']['gold']) == (20, 18)
        for text, markup in earned.messages:
            assert text and len(text) <= 4096
            assert '[rav1.' not in text
            assert not any(content_id in text for content_id in (
                'ar_two_names', 'ss_camp_bearings', 'mv_medic_table',
                'ww_ration_order', 'rav1_mireveil_n6_crosscurrent'))
            assert all(len(value.encode('utf-8')) <= 64 for value in _callbacks(markup))

    asyncio.run(run())


def test_j20_after_resolution(earned):
    async def run():
        # Leave Tool unfinished while completing a different project, restart,
        # and then resume the original project's real combat/report path.
        await _move(earned, 'hub_westwild')
        await _rav_action(earned, 'ww_tool_roll', 'start')
        await _complete_names(earned)
        assert get_project_state(earned.player_id, 'ww_tool_roll')['state'] == 'active'
        database.init_db()
        conn = get_connection(); ensure_regional_schema(conn); conn.close()
        assert get_project_state(earned.player_id, 'ww_tool_roll')['state'] == 'active'
        assert get_project_state(earned.player_id, 'ar_two_names')['state'] == 'completed'
        await _move(earned, 'westwild_n3')
        await earned.fight('forest_wolf')
        await _move(earned, 'hub_westwild')
        await _rav_action(earned, 'ww_tool_roll', 'respond', objective_id='report')

        # Finish every other finite record through the same earned production
        # helpers used by the order journey.
        await _ensure_rations(earned, 2)
        await _request(earned, 'ww_woodcutter_provisions', 'hub_westwild')
        await _inspect(earned, 'ww_root_marks', 'westwild_n7')
        await _rav_action(earned, 'ww_root_cache', 'claim')
        await _complete_sled(earned)
        await _complete_storehouse(earned)
        await _complete_camp(earned)
        await _complete_ferry(earned)
        await _complete_medic_practice(earned)
        await _ensure_resource(earned, 'herb_common', 4, [])
        await _request(earned, 'mv_medic_table', 'hub_mireveil')
        finite_ids = {
            'ww_tool_roll', 'fs_jammed_sled', 'ar_two_names',
            'ar_unquiet_storehouse', 'mv_ferry_crew', 'ss_camp_bearings',
            'mv_medic_practice', 'ww_woodcutter_provisions',
            'mv_medic_table', 'ww_root_cache',
        }
        claims_before = dict(list_claims(earned.player_id))
        assert set(claims_before) == finite_ids
        inventory_before = _inventory_snapshot(earned.player_id)
        progression_before = _state_snapshot(earned.player_id)
        facts_before = set(list_facts(earned.player_id))

        # Reinspect every recorded discovery with a newly issued handler token.
        for fact_id in facts_before:
            definition = FACTS_BY_ID[fact_id]
            await _move(earned, definition.location_id)
            result = await _rav_action(earned, fact_id, 'inspect')
            assert result['status'] == 'inspected'
            assert result['details']['new'] is False

        # Reopen all seven project records and exercise a fresh reward-bearing
        # start token at an eligible location. Completed records remain closed.
        for project_id, project in PROJECTS_BY_ID.items():
            await _move(earned, project.start_locations[0])
            detail = await earned.callback(
                f'rv:d:p:{project_id}', handle_regional_buttons)
            assert detail.answer.await_count == 1
            token = issue_regional_action(earned.player_id, project_id, 'start')
            await earned.callback(f'rv:a:{token}', handle_regional_buttons)
            assert _receipt(earned.player_id, token)['status'] == 'already_resolved'

        # Reopen both finite requests and the cache. Supply the delivery baskets
        # to prove the failed fresh claims roll their tentative debits back.
        await _ensure_rations(earned, 2)
        await _ensure_resource(earned, 'herb_common', 4, [])
        interaction_inventory = _inventory_snapshot(earned.player_id)
        for content_id, location_id, kind, operation in (
            ('ww_woodcutter_provisions', 'hub_westwild', 'i', 'deliver'),
            ('mv_medic_table', 'hub_mireveil', 'i', 'deliver'),
            ('ww_root_cache', 'westwild_n7', 'i', 'claim'),
        ):
            await _move(earned, location_id)
            detail = await earned.callback(
                f'rv:d:{kind}:{content_id}', handle_regional_buttons)
            assert detail.answer.await_count == 1
            token = issue_regional_action(earned.player_id, content_id, operation)
            await earned.callback(f'rv:a:{token}', handle_regional_buttons)
            assert _receipt(earned.player_id, token)['status'] == 'already_resolved'
        assert _inventory_snapshot(earned.player_id) == interaction_inventory
        assert list_claims(earned.player_id) == claims_before

        # Local Work plus the linked profession and equipment browsers remain
        # usable after every finite claim has resolved.
        await _move(earned, 'hub_westwild')
        for callback, handler in (
            ('rv:v:w:0:all', handle_regional_buttons),
            ('pe_o:0', handle_profession_buttons),
            ('inv_catalog', handle_inventory_buttons),
        ):
            query = await earned.callback(callback, handler)
            assert query.answer.await_count >= 1
            assert earned.messages[-1][0]

        # Standing work remains renewable: a fresh basket pays once, replaying
        # its exact token recovers the receipt without another debit or reward.
        await _ensure_rations(earned, 2)
        await _move(earned, 'hub_westwild')
        ration_before = _quantity(earned.player_id, 'field_ration')
        gold_before = int(get_player(earned.player_id)['gold'])
        standing_token = issue_regional_action(
            earned.player_id, 'ww_ration_order', 'deliver')
        await earned.callback(f'rv:a:{standing_token}', handle_regional_buttons)
        standing = _receipt(earned.player_id, standing_token)
        assert standing['status'] == 'delivered' and standing['gold_delta'] == 10
        assert _quantity(earned.player_id, 'field_ration') == ration_before - 2
        assert int(get_player(earned.player_id)['gold']) == gold_before + 10
        await earned.callback(f'rv:a:{standing_token}', handle_regional_buttons)
        assert _quantity(earned.player_id, 'field_ration') == ration_before - 2
        assert int(get_player(earned.player_id)['gold']) == gold_before + 10
        assert list_claims(earned.player_id) == claims_before

        home_text, home_markup = build_regional_home(dict(get_player(earned.player_id)))
        assert t('pxe1.journal.choose_direction','en') in home_text
        assert {'rv:v:w:0:all','rv:v:r:0:all','alpha_history'}<=set(_callbacks(home_markup))
        assert set(list_claims(earned.player_id)) == finite_ids
        assert set(PROJECTS_BY_ID) == {
            'ww_tool_roll', 'fs_jammed_sled', 'ar_two_names',
            'ar_unquiet_storehouse', 'mv_ferry_crew', 'ss_camp_bearings',
            'mv_medic_practice',
        }
        assert all(
            get_project_state(earned.player_id, project_id)['state'] == 'completed'
            for project_id in PROJECTS_BY_ID
        )
        assert progression_before['claims'] == sorted(finite_ids)
        assert inventory_before  # captured before reopen/reward-token proofs
    asyncio.run(run())
