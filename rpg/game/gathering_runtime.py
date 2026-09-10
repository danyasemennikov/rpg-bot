"""The ordinary gathering roll, item, profession XP and objective in one commit."""

import random

from database import get_connection, add_gathering_profession_exp
from game.action_receipts import ActionRejected, peaceful_player, record_request, require_item_delivery
from game.gathering_foundation import build_location_gather_source_profiles, resolve_gather_access_decision
from game.gathering_progression import gathering_profession_xp_for_success
from game.gear_instances import grant_item_to_player
from game.locations import resolve_location_id


def gather_resource(player_id: int, profession: str, *, location_id: str, request_id: str) -> dict:
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        player = peaceful_player(conn, player_id, location_id=location_id)
        profiles = [p for p in build_location_gather_source_profiles(resolve_location_id(player['location_id']))
                    if p.profession_key == profession]
        if not profiles:
            raise ActionRejected('stale_action')
        if not record_request(conn, player_id, request_id):
            raise ActionRejected('stale_action')
        roll, cumulative, picked = random.random(), 0.0, None
        for profile in profiles:
            cumulative += max(0.0, float(profile.chance))
            if roll < cumulative:
                picked = profile
                break
        if picked is None:
            conn.commit()
            return {'status': 'empty'}
        conn.execute('''INSERT OR IGNORE INTO player_gathering_professions
            (telegram_id, profession_key) VALUES (?, ?)''', (player_id, profession))
        state = conn.execute('''SELECT level FROM player_gathering_professions
            WHERE telegram_id=? AND profession_key=?''', (player_id, profession)).fetchone()
        access = resolve_gather_access_decision(item_id=picked.item_id,
                                               player_profession_level=state['level'],
                                               zone_tier_band=picked.zone_tier_band)
        if not access or not access.is_allowed:
            conn.commit()
            return {'status': 'denied', 'access': access}
        require_item_delivery(grant_item_to_player(player_id, picked.item_id, 1,
                                                   source='gathering', source_level=player['level'], conn=conn), 1)
        xp = gathering_profession_xp_for_success(current_profession_level=access.player_profession_level,
                                                required_profession_level=access.required_profession_level)
        progression = add_gathering_profession_exp(player_id, profession, xp, conn=conn)
        from game.quest_board import register_contract_objective
        register_contract_objective(conn, player_id, 'gather', picked.item_id, 1, player['location_id'])
        conn.commit()
        return {'status': 'gathered', 'item_id': picked.item_id, 'progression': progression}
    except ActionRejected as exc:
        conn.rollback()
        return {'status': str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
