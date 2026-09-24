import json

import database
from game.hunting import harvest_victory, list_harvestable_victories
from game.pve_live import _ensure_pve_encounter_table
from game.seed import seed_items


def _player(player_id):
    database.create_player(player_id, f'u{player_id}', f'P{player_id}',
        dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'),2), lang='en')
    conn=database.get_connection(); conn.execute("UPDATE players SET location_id='westwild_n2' WHERE telegram_id=?",(player_id,)); conn.commit(); conn.close()


def _settlement(player_id, encounter_id, *, eligible):
    plan={'schema_version':1,'policy_version':'field_loot_v1','encounter_id':encounter_id,
          'owner_player_id':player_id,'location_id':'westwild_n2',
          'eligible_recipient_ids':[player_id] if eligible else [],
          'defeated_participant_ids':[] if eligible else [player_id],
          'enemy_units':[{'unit_id':'unit-1','mob_id':'forest_boar'}]}
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
