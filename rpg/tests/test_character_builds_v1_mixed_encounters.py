import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from database import get_connection
from game.build_progression import migrate_character_builds_v1
from game.enemy_profiles import MIXED_ENCOUNTERS
from game.mobs import get_mob
from game.pve_live import (
    create_mixed_open_world_pve_encounter,
    ensure_location_pve_spawn_instances,
    list_location_available_mixed_encounters,
    list_location_available_spawn_instances,
    load_active_pve_encounter,
)
from handlers.location import build_location_message, handle_combat_buttons


def _battle_state(mob_id: str) -> dict:
    mob = get_mob(mob_id)
    return {
        'mob_id': mob_id,
        'mob_hp': int(mob['hp']),
        'mob_max_hp': int(mob['hp']),
        'player_hp': 100,
        'player_max_hp': 100,
        'player_mana': 100,
        'player_max_mana': 100,
        'log': [],
    }


def _move_player(location_id: str) -> None:
    conn = get_connection()
    conn.execute('UPDATE players SET location_id=? WHERE telegram_id=1', (location_id,))
    conn.commit()
    conn.close()


def test_westwild_mixed_recipe_reserves_exact_real_roster_atomically():
    migrate_character_builds_v1()
    _move_player('westwild_n8')
    ensure_location_pve_spawn_instances(location_id='westwild_n8')

    available_recipe_ids = {
        row['recipe_id'] for row in list_location_available_mixed_encounters(location_id='westwild_n8')
    }
    assert available_recipe_ids == {'westwild_n8_mixed'}
    ordinary_before = list_location_available_spawn_instances(location_id='westwild_n8')
    assert {'bear', 'goblin_hunter', 'goblin_shaman'} <= {row['mob_id'] for row in ordinary_before}

    encounter_id, status = create_mixed_open_world_pve_encounter(
        owner_player_id=1,
        recipe_id='westwild_n8_mixed',
        battle_state=_battle_state('bear'),
    )
    assert status == 'created'
    assert encounter_id

    loaded = load_active_pve_encounter(encounter_id=encounter_id)
    assert loaded is not None
    battle_state, _mob = loaded
    units = battle_state['enemy_units']
    assert [(unit['mob_id'], unit['formation_line']) for unit in units] == list(
        MIXED_ENCOUNTERS['westwild_n8_mixed']['units']
    )
    assert len({unit['spawn_instance_id'] for unit in units}) == 3
    assert battle_state['mixed_encounter_id'] == 'westwild_n8_mixed'
    assert battle_state['pack_size'] == 3

    conn = get_connection()
    encounter = conn.execute(
        'SELECT anchor_spawn_instance_id, source_units_json FROM pve_encounters WHERE encounter_id=?',
        (encounter_id,),
    ).fetchone()
    reserved = conn.execute(
        '''SELECT spawn_instance_id, mob_id, spawn_profile, state
           FROM pve_spawn_instances WHERE linked_encounter_id=? ORDER BY spawn_instance_id''',
        (encounter_id,),
    ).fetchall()
    conn.close()
    assert len(reserved) == 3
    assert all(row['spawn_profile'] == 'normal' and row['state'] == 'forming' for row in reserved)
    assert encounter['anchor_spawn_instance_id'] == units[0]['spawn_instance_id']
    source_units = json.loads(encounter['source_units_json'])['units']
    assert {(row['spawn_instance_id'], row['mob_id']) for row in source_units} == {
        (unit['spawn_instance_id'], unit['mob_id']) for unit in units
    }
    assert list_location_available_mixed_encounters(location_id='westwild_n8') == []


def test_partial_availability_never_claims_a_subset():
    migrate_character_builds_v1()
    _move_player('ashen_n3c1')
    ensure_location_pve_spawn_instances(location_id='ashen_n3c1')
    conn = get_connection()
    mage = conn.execute(
        '''SELECT spawn_instance_id FROM pve_spawn_instances
           WHERE location_id='ashen_n3c1' AND mob_id='skeleton_mage'
             AND spawn_profile='normal' AND state='idle' LIMIT 1'''
    ).fetchone()
    conn.execute(
        "UPDATE pve_spawn_instances SET state='active', linked_encounter_id='existing' WHERE spawn_instance_id=?",
        (mage['spawn_instance_id'],),
    )
    conn.commit()
    conn.close()

    assert list_location_available_mixed_encounters(location_id='ashen_n3c1') == []
    encounter_id, status = create_mixed_open_world_pve_encounter(
        owner_player_id=1,
        recipe_id='ashen_n3c1_mixed',
        battle_state=_battle_state('zombie'),
    )
    assert encounter_id is None
    assert status == 'spawn_unavailable'
    conn = get_connection()
    accidental = conn.execute(
        '''SELECT COUNT(*) AS total FROM pve_spawn_instances
           WHERE location_id='ashen_n3c1' AND linked_encounter_id IS NOT NULL
             AND linked_encounter_id != 'existing' '''
    ).fetchone()
    created = conn.execute(
        "SELECT COUNT(*) AS total FROM pve_encounters WHERE owner_player_id=1 AND location_id='ashen_n3c1'"
    ).fetchone()
    conn.close()
    assert accidental['total'] == 0
    assert created['total'] == 0


def test_second_mixed_claim_loses_contention_without_extra_spawns():
    migrate_character_builds_v1()
    _move_player('westwild_n8')
    first_id, first_status = create_mixed_open_world_pve_encounter(
        owner_player_id=1,
        recipe_id='westwild_n8_mixed',
        battle_state=_battle_state('bear'),
    )
    second_id, second_status = create_mixed_open_world_pve_encounter(
        owner_player_id=777,
        recipe_id='westwild_n8_mixed',
        battle_state=_battle_state('bear'),
    )
    assert first_status == 'created'
    assert first_id
    assert second_id is None
    assert second_status == 'spawn_unavailable'
    conn = get_connection()
    first_claims = conn.execute(
        'SELECT COUNT(*) AS total FROM pve_spawn_instances WHERE linked_encounter_id=?', (first_id,),
    ).fetchone()
    second_encounters = conn.execute(
        "SELECT COUNT(*) AS total FROM pve_encounters WHERE owner_player_id=777 AND location_id='westwild_n8'",
    ).fetchone()
    conn.close()
    assert first_claims['total'] == 3
    assert second_encounters['total'] == 0


def test_mixed_recipe_is_visibly_localized_beside_individual_spawns():
    migrate_character_builds_v1()
    _move_player('westwild_n8')
    conn = get_connection()
    player = dict(conn.execute('SELECT * FROM players WHERE telegram_id=1').fetchone())
    conn.close()
    from game.locations import get_location
    location = get_location('westwild_n8')
    expected_labels = {
        'en': 'Bear Hunting Party',
        'ru': 'Охотничий отряд медведя',
        'es': 'Partida de caza del oso',
    }
    for lang, expected in expected_labels.items():
        player['lang'] = lang
        text, keyboard = build_location_message(player, location)
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        assert expected in text
        assert '×3' in text
        assert 'fight_mixed_westwild_n8_mixed' in callbacks
        assert any(value.startswith('fight_spawn_') for value in callbacks)
        assert all(len(value.encode('utf-8')) <= 64 for value in callbacks)


def test_mixed_callback_opens_forming_view_before_runtime_lock():
    query = SimpleNamespace(
        data='fight_mixed_westwild_n8_mixed',
        from_user=SimpleNamespace(id=1),
        answer=AsyncMock(),
    )
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace()
    with patch('handlers.location.get_player', return_value={'lang': 'en'}), \
         patch('handlers.location.has_active_live_pvp_engagement', return_value=False), \
         patch('handlers.battle.start_battle', new=AsyncMock()) as start_mock:
        asyncio.run(handle_combat_buttons(update, context))
    start_mock.assert_awaited_once_with(
        update,
        context,
        mob_id='',
        mob_first=False,
        mixed_encounter_id='westwild_n8_mixed',
        open_runtime_now=False,
    )
