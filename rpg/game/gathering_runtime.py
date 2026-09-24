"""The ordinary gathering roll, item, profession XP and objective in one commit."""

import random

from database import get_connection, add_gathering_profession_exp
from game.action_receipts import ActionRejected, peaceful_player, record_request, require_item_delivery
from game.gathering_foundation import build_location_gather_source_profiles, resolve_gather_access_decision
from game.gathering_progression import gathering_profession_xp_for_success
from game.gear_instances import grant_item_to_player
from game.locations import resolve_location_id


def gather_resource(player_id: int, profession: str, *, location_id: str, request_id: str, rng=None) -> dict:
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        from game.economy_actions import find_receipt, intent_hash, store_receipt
        receipt_hash = intent_hash('gather', player_id, {'profession': profession, 'location_id': resolve_location_id(location_id)})
        recovered = find_receipt(conn, player_id, request_id, 'gather', receipt_hash)
        if recovered is not None:
            conn.commit()
            return {**recovered, 'recovered': True}
        legacy = conn.execute('SELECT 1 FROM player_action_receipts WHERE player_id=? AND request_id=?',
                              (player_id, request_id)).fetchone()
        if legacy:
            conn.commit()
            return {'status': 'historical_receipt_unavailable'}
        player = peaceful_player(conn, player_id, location_id=location_id)
        profiles = [p for p in build_location_gather_source_profiles(resolve_location_id(player['location_id']))
                    if p.profession_key == profession]
        if not profiles:
            raise ActionRejected('stale_action')
        if not record_request(conn, player_id, request_id):
            raise ActionRejected('stale_action')
        roll, cumulative, picked = (rng or random).random(), 0.0, None
        for profile in profiles:
            cumulative += max(0.0, float(profile.chance))
            if roll < cumulative:
                picked = profile
                break
        if picked is None:
            result = {'schema_version': 1, 'action_kind': 'gather', 'status': 'empty',
                      'player_id': player_id, 'location_id': player['location_id'], 'recipe_id': None,
                      'consumed': [], 'granted': [], 'gold_delta': 0, 'gold_after': player['gold'],
                      'progression': [], 'source': {'profession_key': profession, 'roll': roll}, 'details': {}}
            store_receipt(conn, player_id, request_id, 'gather', receipt_hash, result)
            conn.commit()
            return result
        conn.execute('''INSERT OR IGNORE INTO player_gathering_professions
            (telegram_id, profession_key) VALUES (?, ?)''', (player_id, profession))
        state = conn.execute('''SELECT level FROM player_gathering_professions
            WHERE telegram_id=? AND profession_key=?''', (player_id, profession)).fetchone()
        access = resolve_gather_access_decision(item_id=picked.item_id,
                                               player_profession_level=state['level'],
                                               zone_tier_band=picked.zone_tier_band)
        if not access or not access.is_allowed:
            result = {'schema_version': 1, 'action_kind': 'gather', 'status': 'denied',
                      'player_id': player_id, 'location_id': player['location_id'], 'recipe_id': None,
                      'consumed': [], 'granted': [], 'gold_delta': 0, 'gold_after': player['gold'],
                      'progression': [], 'source': {'profession_key': profession, 'roll': roll,
                      'item_id': picked.item_id}, 'details': {'required_level': access.required_profession_level if access else None}}
            store_receipt(conn, player_id, request_id, 'gather', receipt_hash, result)
            conn.commit()
            return {**result, 'access': access}
        require_item_delivery(grant_item_to_player(player_id, picked.item_id, 1,
                                                   source='gathering', source_level=player['level'], conn=conn), 1)
        xp = gathering_profession_xp_for_success(current_profession_level=access.player_profession_level,
                                                required_profession_level=access.required_profession_level)
        progression = add_gathering_profession_exp(player_id, profession, xp, conn=conn)
        from game.quest_board import register_contract_objective
        register_contract_objective(conn, player_id, 'gather', picked.item_id, 1, player['location_id'])
        result = {'schema_version': 1, 'action_kind': 'gather', 'status': 'gathered',
                  'player_id': player_id, 'location_id': player['location_id'], 'recipe_id': None,
                  'consumed': [], 'granted': [{'item_id': picked.item_id, 'quantity': 1, 'instance_ids': [], 'gear_specs': []}],
                  'gold_delta': 0, 'gold_after': player['gold'],
                  'progression': [{'profession_key': profession, 'old_level': progression.old_level,
                    'old_exp': progression.old_exp, 'new_level': progression.new_level,
                    'new_exp': progression.new_exp, 'xp_awarded': progression.xp_awarded}],
                  'source': {'profession_key': profession, 'roll': roll, 'item_id': picked.item_id}, 'details': {}}
        store_receipt(conn, player_id, request_id, 'gather', receipt_hash, result)
        conn.commit()
        return {**result, 'item_id': picked.item_id, 'progression': progression}
    except ActionRejected as exc:
        conn.rollback()
        return {'status': str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
