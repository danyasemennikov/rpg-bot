"""Supplementary harvesting of an owned persisted victory, once per encounter."""

from database import get_connection, add_gathering_profession_exp
from game.action_receipts import ActionRejected, peaceful_player, require_item_delivery
from game.gathering_foundation import resolve_gather_access_decision
from game.gathering_progression import gathering_profession_xp_for_success
from game.gear_instances import grant_item_to_player
from game.locations import get_location, resolve_location_id
from game.reward_policies import resolve_content_tier_band


HARVEST_ITEMS = {'forest_boar': 'boar_meat', 'forest_wolf': 'wolf_pelt'}


def list_harvestable_victories(player_id: int) -> list[dict]:
    conn = get_connection()
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='pve_encounters'").fetchone():
            return []
        player = conn.execute('SELECT location_id FROM players WHERE telegram_id=?', (player_id,)).fetchone()
        if not player:
            return []
        rows = conn.execute('''SELECT e.encounter_id, e.mob_id, e.location_id
            FROM pve_encounters e LEFT JOIN pve_harvest_claims h
            ON h.encounter_id=e.encounter_id AND h.player_id=?
            WHERE e.owner_player_id=? AND e.status='victory' AND h.encounter_id IS NULL
            AND e.finished_at >= datetime('now', '-30 minutes')
            ORDER BY e.finished_at DESC LIMIT 20''', (player_id, player_id)).fetchall()
        return [dict(row) for row in rows if row['mob_id'] in HARVEST_ITEMS
                and resolve_location_id(row['location_id']) == resolve_location_id(player['location_id'])]
    finally:
        conn.close()


def harvest_victory(player_id: int, encounter_id: str) -> dict:
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        player = peaceful_player(conn, player_id)
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='pve_encounters'").fetchone():
            raise ActionRejected('stale_action')
        row = conn.execute('''SELECT * FROM pve_encounters WHERE encounter_id=?
            AND owner_player_id=? AND status='victory'
            AND finished_at >= datetime('now', '-30 minutes')''', (encounter_id, player_id)).fetchone()
        if not row or row['mob_id'] not in HARVEST_ITEMS:
            raise ActionRejected('stale_action')
        if resolve_location_id(row['location_id']) != resolve_location_id(player['location_id']):
            raise ActionRejected('wrong_location')
        item_id = HARVEST_ITEMS[row['mob_id']]
        conn.execute('''INSERT OR IGNORE INTO player_gathering_professions
            (telegram_id, profession_key) VALUES (?, 'hunting')''', (player_id,))
        state = conn.execute('''SELECT level FROM player_gathering_professions
            WHERE telegram_id=? AND profession_key='hunting' ''', (player_id,)).fetchone()
        location = get_location(player['location_id'])
        access = resolve_gather_access_decision(item_id=item_id, player_profession_level=state['level'],
                                               zone_tier_band=resolve_content_tier_band(location['level_max']))
        if not access or not access.is_allowed:
            raise ActionRejected('profession_locked')
        inserted = conn.execute('''INSERT OR IGNORE INTO pve_harvest_claims
            (encounter_id, player_id, item_id) VALUES (?, ?, ?)''', (encounter_id, player_id, item_id))
        if not inserted.rowcount:
            raise ActionRejected('stale_action')
        require_item_delivery(grant_item_to_player(player_id, item_id, 1, source='hunting', conn=conn), 1)
        xp = gathering_profession_xp_for_success(current_profession_level=state['level'],
                                                required_profession_level=access.required_profession_level)
        progression = add_gathering_profession_exp(player_id, 'hunting', xp, conn=conn)
        from game.quest_board import register_contract_objective
        register_contract_objective(conn, player_id, 'harvest', item_id, 1, player['location_id'])
        conn.commit()
        return {'status': 'harvested', 'item_id': item_id, 'progression': progression}
    except ActionRejected as exc:
        conn.rollback()
        return {'status': str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
