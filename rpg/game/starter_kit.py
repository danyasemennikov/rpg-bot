"""A one-time, classless loadout from Aster's quartermaster."""

from database import get_connection
from game.action_receipts import ActionRejected, peaceful_player, require_item_delivery
from game.gear_instances import grant_item_to_player, equip_gear_instance_in_slot
from game.locations import resolve_location_id


STARTER_WEAPONS = ('practice_sword', 'practice_bow', 'practice_staff')


def has_starter_kit(player_id: int) -> bool:
    conn = get_connection()
    try:
        return conn.execute('SELECT 1 FROM player_starter_kits WHERE player_id=?', (player_id,)).fetchone() is not None
    finally:
        conn.close()


def claim_starter_kit(player_id: int, weapon_id: str) -> dict:
    if weapon_id not in STARTER_WEAPONS:
        return {'status': 'stale_action'}
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        player = peaceful_player(conn, player_id)
        if resolve_location_id(player['location_id']) != 'capital_city':
            raise ActionRejected('wrong_location')
        if conn.execute('SELECT 1 FROM player_starter_kits WHERE player_id=?', (player_id,)).fetchone():
            raise ActionRejected('stale_action')
        require_item_delivery(grant_item_to_player(player_id, weapon_id, 1, source='starter', conn=conn), 1)
        for item_id, qty in (('health_potion_small', 3), ('mana_potion', 2)):
            require_item_delivery(grant_item_to_player(player_id, item_id, qty, source='starter', conn=conn), qty)
        instance_id = conn.execute('''SELECT id FROM gear_instances WHERE telegram_id=?
            AND base_item_id=? ORDER BY id DESC LIMIT 1''', (player_id, weapon_id)).fetchone()['id']
        legacy = conn.execute('SELECT weapon FROM equipment WHERE telegram_id=?', (player_id,)).fetchone()
        equipped = conn.execute("SELECT 1 FROM gear_instances WHERE telegram_id=? AND equipped_slot='weapon'",
                                (player_id,)).fetchone()
        if not equipped and not (legacy and legacy['weapon']):
            equip_gear_instance_in_slot(player_id, instance_id, 'weapon', conn=conn)
        conn.execute('INSERT INTO player_starter_kits(player_id, weapon_id) VALUES (?, ?)', (player_id, weapon_id))
        conn.commit()
        return {'status': 'equipped', 'weapon_id': weapon_id}
    except ActionRejected as exc:
        conn.rollback()
        return {'status': str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
