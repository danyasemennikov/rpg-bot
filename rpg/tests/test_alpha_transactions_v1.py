"""Fault injection and upgrade coverage for chapter transactions."""
import json
from unittest.mock import patch

import pytest

from database import create_player, get_connection, get_player, get_gathering_profession_state
from game.action_receipts import issue_actions
from game.crafting_runtime import craft_recipe
from game.gathering_runtime import gather_resource
from game.gear_instances import grant_item_to_player, get_equipped_gear_instances
from game.starter_kit import claim_starter_kit, has_starter_kit
from handlers.inventory import try_sell_inventory_item, use_inventory_consumable, use_battle_consumable
from tests.test_playable_alpha_v1 import rows


PID = 90201


def player():
    create_player(PID, 'ordinary', 'Ordinary', dict(strength=4, vitality=4, agility=1, intuition=1, wisdom=1, luck=1), lang='en')


def move(location):
    conn = get_connection()
    conn.execute('UPDATE players SET location_id=?, travel_revision=travel_revision+1 WHERE telegram_id=?', (location, PID))
    conn.commit()
    conn.close()


def snapshot():
    return {table: rows(f'SELECT * FROM {table} ORDER BY 1,2') for table in (
        'players', 'inventory', 'gear_instances', 'player_crafting_professions',
        'player_gathering_professions', 'player_contract_objectives', 'player_contract_history',
        'player_starter_kits', 'player_action_receipts', 'player_ui_actions', 'pve_harvest_claims')}


def grant_then_fail(*args, **kwargs):
    grant_item_to_player(*args, **kwargs)
    raise RuntimeError('after item write')


def test_startup_reconciles_missing_static_items_and_preserves_legacy_player(tmp_path):
    import database
    from bot import initialize_runtime
    # A persisted pre-upgrade database: player data + old gear, missing new items
    # and columns. Dropping columns is test fixture construction, never migration.
    player()
    grant_item_to_player(PID, 'wooden_sword', 1, source='test_fixture')
    before = rows('SELECT * FROM gear_instances')
    conn = get_connection()
    conn.execute("DELETE FROM items WHERE item_id IN ('wood_common','practice_sword','trail_vest','field_ration')")
    conn.execute('ALTER TABLE players DROP COLUMN travel_revision')
    conn.execute('ALTER TABLE players DROP COLUMN last_seen')
    conn.commit()
    conn.close()
    initialize_runtime()
    initialize_runtime()
    assert rows('SELECT * FROM gear_instances') == before
    assert get_player(PID)['name'] == 'Ordinary'
    assert get_player(PID)['travel_revision'] == 0
    assert get_player(PID)['last_seen']
    assert len(rows("SELECT item_id FROM items WHERE item_id IN ('wood_common','practice_sword','trail_vest','field_ration')")) == 4
    assert not rows('PRAGMA foreign_key_check')
    with patch.object(database, 'DB_PATH', str(tmp_path / 'fresh.db')):
        initialize_runtime()
        player()
        assert claim_starter_kit(PID, 'practice_sword')['status'] == 'equipped'
        assert not rows('PRAGMA foreign_key_check')


@pytest.mark.parametrize('weapon', ['practice_sword', 'practice_bow', 'practice_staff'])
def test_kit_once_atomic_and_legacy_equipment_preserved(weapon):
    player()
    before = snapshot()
    with patch('game.starter_kit.grant_item_to_player', side_effect=grant_then_fail):
        with pytest.raises(RuntimeError, match='after item write'):
            claim_starter_kit(PID, weapon)
    assert snapshot() == before
    grant_item_to_player(PID, 'wooden_sword', 1, source='test_fixture')
    from game.gear_instances import equip_gear_instance_in_slot
    gear = rows('SELECT id FROM gear_instances WHERE telegram_id=?', (PID,))[0]['id']
    equip_gear_instance_in_slot(PID, gear, 'weapon')
    assert claim_starter_kit(PID, weapon)['status'] == 'equipped'
    assert get_equipped_gear_instances(PID)['weapon']['id'] == gear
    assert has_starter_kit(PID)
    before = snapshot()
    assert claim_starter_kit(PID, weapon)['status'] == 'stale_action'
    assert snapshot() == before


def test_gather_transaction_rolls_back_item_xp_objective_and_receipt_then_retries_once():
    player()
    from game.quest_board import accept_hunt_contract
    assert accept_hunt_contract(player_id=PID, location_id='capital_city', contract_key='chapter_first_watch')[0]
    move('westwild_n1')
    before = snapshot()
    with patch('game.gathering_runtime.random.random', return_value=0.0):
        with patch('game.gathering_runtime.add_gathering_profession_exp', side_effect=RuntimeError('progress failure')):
            with pytest.raises(RuntimeError):
                gather_resource(PID, 'herbalism', location_id='westwild_n1', request_id='gather:99')
        assert snapshot() == before
        assert gather_resource(PID, 'herbalism', location_id='westwild_n1', request_id='gather:99')['status'] == 'gathered'
        before = snapshot()
        assert gather_resource(PID, 'herbalism', location_id='westwild_n1', request_id='gather:99')['status'] == 'stale_action'
        assert snapshot() == before
    assert get_gathering_profession_state(PID, 'herbalism')['exp'] == 10


def test_craft_locked_missing_materials_rollback_restart_duplicate_and_travel_stale():
    player()
    grant_item_to_player(PID, 'herb_common', 20, source='test_fixture')
    assert craft_recipe(PID, 'field_mana', {'alchemy': 99}).status == 'profession_level_too_low'
    assert craft_recipe(PID, 'trail_vest').status == 'missing_materials'
    token = issue_actions(PID, 'craft', ['field_tonic'])['field_tonic']
    before = snapshot()
    with patch('game.crafting_runtime.grant_item_to_player', side_effect=grant_then_fail):
        assert craft_recipe(PID, '', action_token=token).status == 'craft_failed_atomic'
    assert snapshot() == before
    # All APIs reopen the database; no process-local craft state can grant items.
    assert craft_recipe(PID, '', action_token=token).status == 'crafted'
    before = snapshot()
    assert craft_recipe(PID, '', action_token=token).status == 'stale_action'
    assert snapshot() == before
    token = issue_actions(PID, 'craft', ['field_tonic'])['field_tonic']
    move('westwild_n1')
    move('capital_city')
    assert craft_recipe(PID, '', action_token=token).status == 'stale_action'
    for _ in range(2):
        assert craft_recipe(PID, 'field_tonic').status == 'crafted'
    assert craft_recipe(PID, 'field_mana').status == 'crafted'
    assert rows("SELECT level FROM player_crafting_professions WHERE player_id=? AND profession_key='alchemy'", (PID,))[0]['level'] == 2


def test_sale_and_consumable_are_owned_single_use_and_atomic():
    player()
    grant_item_to_player(PID, 'herb_common', 3, source='test_fixture')
    inv = rows('SELECT id FROM inventory WHERE telegram_id=?', (PID,))[0]['id']
    token = issue_actions(PID, 'sell', [f'{inv}:3'])[f'{inv}:3']
    before = snapshot()
    assert try_sell_inventory_item(1, token)['status'] == 'stale_action'
    with patch('game.quest_board.register_contract_objective', side_effect=RuntimeError('progress failure')):
        with pytest.raises(RuntimeError):
            try_sell_inventory_item(PID, token)
    assert snapshot() == before
    assert try_sell_inventory_item(PID, token)['status'] == 'sold'
    before = snapshot()
    assert try_sell_inventory_item(PID, token)['status'] == 'stale_action'
    assert snapshot() == before
    grant_item_to_player(PID, 'health_potion_small', 1, source='test_fixture')
    inv = rows("SELECT id FROM inventory WHERE telegram_id=? AND item_id='health_potion_small'", (PID,))[0]['id']
    token = issue_actions(PID, 'use', [f'{inv}:1'])[f'{inv}:1']
    assert use_inventory_consumable(1, token)['status'] == 'stale_action'
    assert use_inventory_consumable(PID, token)['status'] == 'used'
    before = snapshot()
    assert use_inventory_consumable(PID, token)['status'] == 'stale_action'
    assert snapshot() == before


def test_peaceful_mutations_reject_active_battle():
    player()
    grant_item_to_player(PID, 'herb_common', 10, source='test_fixture')
    conn = get_connection()
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=?', (PID,))
    conn.commit()
    conn.close()
    before = snapshot()
    assert craft_recipe(PID, 'field_tonic').status == 'in_battle'
    assert claim_starter_kit(PID, 'practice_sword')['status'] == 'in_battle'
    assert gather_resource(PID, 'herbalism', location_id='capital_city', request_id='gather:1')['status'] == 'in_battle'
    assert snapshot() == before


def test_registration_rolls_back_all_starting_rows_on_failure():
    before = snapshot()
    with patch('game.alpha_schema.ensure_crafting_professions', side_effect=RuntimeError('creation failure')):
        with pytest.raises(RuntimeError):
            player()
    assert snapshot() == before
    player()
    assert get_player(PID)


def test_pending_live_pvp_blocks_crafting_even_without_pve_flag():
    from game.pvp_live import create_live_engagement
    player()
    grant_item_to_player(PID, 'herb_common', 3, source='test_fixture')
    create_live_engagement(attacker=dict(get_player(PID)), defender=dict(get_player(1)),
                           location_id='capital_city', illegal_aggression=False)
    before = snapshot()
    assert get_player(PID)['in_battle'] == 0
    assert craft_recipe(PID, 'field_tonic').status == 'in_battle'
    assert snapshot() == before


def test_shop_purchase_receipt_and_delivery_rollback():
    from handlers.location import try_buy_curated_shop_item
    player()
    token = issue_actions(PID, 'shop_buy', ['health_potion_small'])['health_potion_small']
    before = snapshot()
    with patch('handlers.location.grant_item_to_player', side_effect=grant_then_fail):
        assert try_buy_curated_shop_item(PID, 'capital_city', 99, 'health_potion_small', action_token=token)['reason'] == 'delivery_failed'
    assert snapshot() == before
    assert try_buy_curated_shop_item(PID, 'capital_city', 99, 'health_potion_small', action_token=token)['ok']
    before = snapshot()
    assert not try_buy_curated_shop_item(PID, 'capital_city', 99, 'health_potion_small', action_token=token)['ok']
    assert snapshot() == before


def test_travel_discovery_failure_keeps_previous_location_and_revision():
    import asyncio
    from unittest.mock import AsyncMock
    from tests.test_playable_alpha_v1 import Journey, PLAYER
    from handlers.location import handle_location_buttons
    create_player(PLAYER, 'traveler', 'Traveler', dict(strength=4, vitality=4, agility=1, intuition=1, wisdom=1, luck=1))
    before = snapshot()
    with patch('handlers.location.asyncio.sleep', new=AsyncMock()), patch(
        'handlers.location.ensure_player_location_discovered', side_effect=RuntimeError('discovery failure')
    ):
        with pytest.raises(RuntimeError):
            asyncio.run(Journey('en').callback('goto_westwild_n1', handle_location_buttons))
    assert snapshot() == before


def test_old_abandon_token_cannot_remove_a_new_contract():
    from game.quest_board import accept_hunt_contract, abandon_hunt_contract, get_player_hunt_contract_state
    player()
    assert accept_hunt_contract(player_id=PID, location_id='capital_city', contract_key='chapter_first_watch')[0]
    token = issue_actions(PID, 'contract_abandon', ['chapter_first_watch'])['chapter_first_watch']
    assert abandon_hunt_contract(player_id=PID, action_token=token)[0]
    assert accept_hunt_contract(player_id=PID, location_id='capital_city', contract_key='hunt_forest_wolves')[0]
    assert abandon_hunt_contract(player_id=PID, action_token=token) == (False, 'stale_action')
    assert get_player_hunt_contract_state(PID)['contract_key'] == 'hunt_forest_wolves'


def test_chapter_translations_have_equal_keys_and_format_fields():
    from string import Formatter
    from locales.chapter import CHAPTER_STRINGS
    baseline = CHAPTER_STRINGS['ru']
    fields = lambda text: {key for _, key, _, _ in Formatter().parse(text) if key}
    for lang in ('en', 'es'):
        assert CHAPTER_STRINGS[lang].keys() == baseline.keys()
        for key, value in baseline.items():
            assert fields(CHAPTER_STRINGS[lang][key]) == fields(value), (lang, key)


def test_battle_consumption_updates_projection_and_rolls_back_on_persist_failure():
    player()
    move('westwild_n1')
    from game.combat import init_battle
    from game.mobs import get_mob
    from game.pve_live import create_or_load_open_world_pve_encounter, load_active_pve_encounter
    mob = get_mob('westwild_rabbit')
    state = init_battle(dict(get_player(PID)), mob)
    state['player_hp'] -= 45  # Unit fixture for restoration, not acceptance combat.
    encounter, _ = create_or_load_open_world_pve_encounter(owner_player_id=PID,
        location_id='westwild_n1', mob_id=mob['id'], battle_state=state, mob=mob)
    assert encounter
    grant_item_to_player(PID, 'health_potion_small', 2, source='test_fixture')
    inv = rows('SELECT id FROM inventory WHERE telegram_id=?', (PID,))[0]['id']
    payload = f'{encounter}:{inv}:2'
    token = issue_actions(PID, 'battle_use', [payload])[payload]
    before = snapshot()
    with patch('handlers.inventory.json.dumps', side_effect=RuntimeError('persist failure')):
        with pytest.raises(RuntimeError):
            use_battle_consumable(PID, token, encounter)
    assert snapshot() == before
    result = use_battle_consumable(PID, token, encounter)
    assert result['status'] == 'used'
    restored, _ = load_active_pve_encounter(encounter_id=encounter)
    assert restored['player_hp'] == state['player_hp'] + result['heal']
    assert restored['participant_states'][str(PID)]['player_hp'] == restored['player_hp']
    assert use_battle_consumable(PID, token, encounter)['status'] == 'stale_action'
