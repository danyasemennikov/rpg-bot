import json

from database import get_connection
from game.action_receipts import issue_actions
from game.hunting import harvest_victory
from game.player_experience_schema import grant_player_pxe1_starters
from tests.test_professions_economy_v1_hunting import _settlement


def test_harvest_last_wear_and_replay_with_broken_or_changed_tool():
    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    grant_player_pxe1_starters(conn,1,now_ms=0,acquired_via='starter')
    conn.execute("UPDATE players SET location_id='westwild_n2' WHERE telegram_id=1")
    conn.execute("UPDATE player_profession_tools SET durability=1 WHERE player_id=1 AND profession_key='hunting'")
    conn.commit()
    _settlement(1,'hunt-win',eligible=True)
    payload = json.dumps({'encounter_id':'hunt-win','unit_id':'unit-1','item_id':'boar_meat'},sort_keys=True,separators=(',',':'))
    token = issue_actions(1,'harvest',[payload])[payload]
    result = harvest_victory(1,'hunt-win',unit_id='unit-1',item_id='boar_meat',action_token=token)
    assert result['status']=='harvested'
    assert conn.execute("SELECT durability FROM player_profession_tools WHERE player_id=1 AND profession_key='hunting'").fetchone()[0]==0
    assert conn.execute("SELECT SUM(quantity) FROM inventory WHERE telegram_id=1 AND item_id='boar_meat'").fetchone()[0]==1
    assert harvest_victory(1,'hunt-win',unit_id='unit-1',item_id='boar_meat',action_token=token)['recovered']
    assert conn.execute("SELECT durability FROM player_profession_tools WHERE player_id=1 AND profession_key='hunting'").fetchone()[0]==0
    _settlement(1,'hunt-next',eligible=True)
    assert harvest_victory(1,'hunt-next',unit_id='unit-1',item_id='boar_meat')['status']=='tool_broken'
    assert not conn.execute("SELECT 1 FROM pve_harvest_claims WHERE encounter_id='hunt-next'").fetchone()
    conn.close()
