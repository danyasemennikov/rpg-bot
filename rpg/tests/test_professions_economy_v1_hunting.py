import json

import database
from game.hunting import _choices, harvest_victory, harvestable_victory_page, list_harvestable_victories
from game.pve_live import _ensure_pve_encounter_table
from game.seed import seed_items
from handlers.chapter import build_harvest_menu


def _player(player_id):
    database.create_player(player_id, f'u{player_id}', f'P{player_id}',
        dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'),2), lang='en')
    conn=database.get_connection(); conn.execute("UPDATE players SET location_id='westwild_n2' WHERE telegram_id=?",(player_id,)); conn.commit(); conn.close()


def _settlement(player_id, encounter_id, *, eligible, enemy_units=None):
    enemy_units = enemy_units or [{'unit_id':'unit-1','mob_id':'forest_boar'}]
    plan={'schema_version':1,'policy_version':'field_loot_v1','encounter_id':encounter_id,
          'owner_player_id':player_id,'location_id':'westwild_n2',
          'eligible_recipient_ids':[player_id] if eligible else [],
          'defeated_participant_ids':[] if eligible else [player_id],
          'enemy_units':enemy_units}
    result={'encounter_id':encounter_id,'location_id':'westwild_n2',
            'recipients':[{'player_id':player_id}] if eligible else []}
    conn=database.get_connection()
    conn.execute('''INSERT INTO pve_encounters(encounter_id,owner_player_id,status,mob_id,battle_state_json,mob_json,finished_at,location_id)
        VALUES (?,?,'victory','forest_boar','{}','{}',CURRENT_TIMESTAMP,'westwild_n2')''',(encounter_id,player_id))
    conn.execute('''INSERT INTO pve_reward_settlements(encounter_id,schema_version,policy_version,status,plan_json,result_json)
        VALUES (?,1,'field_loot_v1','applied',?,?)''',(encounter_id,json.dumps(plan),json.dumps(result)))
    conn.commit(); conn.close()


def test_applied_eligible_owner_harvests_once_and_defeated_owner_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(database,'DB_PATH',str(tmp_path/'game.db')); database.init_db(); seed_items(); _ensure_pve_encounter_table()
    _player(10); _settlement(10,'win',eligible=True)
    choices=list_harvestable_victories(10); assert choices[0]['item_id']=='boar_meat'
    assert harvest_victory(10,'win',unit_id='unit-1',item_id='boar_meat')['status']=='harvested'
    assert harvest_victory(10,'win',unit_id='unit-1',item_id='boar_meat')['status']=='stale_action'
    _player(11); _settlement(11,'defeat',eligible=False)
    assert harvest_victory(11,'defeat',unit_id='unit-1',item_id='boar_meat')['status']=='harvest_owner_defeated'


def test_harvest_filters_before_five_row_pagination(tmp_path, monkeypatch):
    monkeypatch.setattr(database,'DB_PATH',str(tmp_path/'game.db')); database.init_db(); seed_items(); _ensure_pve_encounter_table()
    _player(20)
    for index in range(7):
        _settlement(20, f'eligible-{index}', eligible=True)
    for index in range(9):
        _settlement(20, f'ineligible-{index}', eligible=False)
    first, page, pages = harvestable_victory_page(20, page=0)
    second, second_page, _ = harvestable_victory_page(20, page=1)
    clamped, clamped_page, _ = harvestable_victory_page(20, page=999)
    assert (len(first), page, pages) == (5, 0, 2)
    assert (len(second), second_page) == (2, 1)
    assert [row['encounter_id'] for row in clamped] == [row['encounter_id'] for row in second]
    assert clamped_page == 1
    assert not ({row['encounter_id'] for row in first} & {row['encounter_id'] for row in second})


def test_duplicate_units_offer_each_item_once_from_first_stable_unit():
    plan = {'enemy_units': [
        {'unit_id': 'wolf-c', 'mob_id': 'forest_wolf'},
        {'unit_id': 'wolf-a', 'mob_id': 'white_wolf'},
        {'unit_id': 'wolf-b', 'mob_id': 'forest_wolf'},
    ]}
    choices = _choices(plan)
    assert [(choice['unit_id'], choice['item_id']) for choice in choices] == [
        ('wolf-a', 'wolf_pelt'), ('wolf-a', 'wolf_fang')
    ]


def test_harvest_pages_five_eligible_encounters_before_expanding_multi_choices(tmp_path, monkeypatch):
    monkeypatch.setattr(database,'DB_PATH',str(tmp_path/'game.db')); database.init_db(); seed_items(); _ensure_pve_encounter_table()
    _player(21)
    for index in range(6):
        units = ([
            {'unit_id':'wolf-z','mob_id':'forest_wolf'},
            {'unit_id':'wolf-a','mob_id':'white_wolf'},
        ] if index == 5 else [{'unit_id':f'boar-{index}','mob_id':'forest_boar'}])
        _settlement(21, f'eligible-{index}', eligible=True, enemy_units=units)

    first, page, pages = harvestable_victory_page(21, page=0)
    second, second_page, _ = harvestable_victory_page(21, page=1)
    assert (page, second_page, pages) == (0, 1, 2)
    assert {row['encounter_id'] for row in first} == {
        'eligible-5', 'eligible-4', 'eligible-3', 'eligible-2', 'eligible-1'
    }
    assert [(row['unit_id'], row['item_id']) for row in first if row['encounter_id'] == 'eligible-5'] == [
        ('wolf-a', 'wolf_pelt'), ('wolf-a', 'wolf_fang')
    ]
    assert {row['encounter_id'] for row in second} == {'eligible-0'}
    _, keyboard = build_harvest_menu(dict(database.get_player(21)), page=0)
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert sum(value.startswith('pe_a:') for value in callbacks) == 6
    assert 'alpha_harvest:1' in callbacks
