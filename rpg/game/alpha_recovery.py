from __future__ import annotations

from game.locations import resolve_location_id, WORLD_LOCATIONS

SAFE_RECOVERY_LOCATION_ID = 'village'


def build_recovery_decision(player_state: dict) -> dict:
    player_state = player_state or {}
    if player_state.get('active_danger_context') or player_state.get('active_battle_context'):
        return {'allowed': False, 'reason': 'active_danger', 'target_location_id': None}
    if player_state.get('pvp_mobility_blocked'):
        return {'allowed': False, 'reason': 'pvp_blocked', 'target_location_id': None}

    raw_location_id = str(player_state.get('location_id') or '').strip()
    normalized_location_id = resolve_location_id(raw_location_id) if raw_location_id else ''
    if player_state.get('persisted_in_battle'):
        return {
            'allowed': True,
            'reason': 'stale_battle_flag',
            'target_location_id': SAFE_RECOVERY_LOCATION_ID,
        }
    if normalized_location_id and normalized_location_id in WORLD_LOCATIONS:
        return {'allowed': True, 'reason': 'ok', 'target_location_id': SAFE_RECOVERY_LOCATION_ID}
    return {'allowed': True, 'reason': 'unknown_location', 'target_location_id': SAFE_RECOVERY_LOCATION_ID}


def validate_alpha_recovery_policy() -> list[str]:
    errors: list[str] = []
    if build_recovery_decision({'active_battle_context': True}).get('allowed'):
        errors.append('recovery must be blocked in active battle context')
    if build_recovery_decision({'active_danger_context': True}).get('allowed'):
        errors.append('recovery must be blocked in active danger context')
    if build_recovery_decision({'pvp_mobility_blocked': True}).get('allowed'):
        errors.append('recovery must be blocked for pvp mobility lock')
    stale = build_recovery_decision({'persisted_in_battle': True, 'location_id': 'hub_westwild'})
    if stale.get('allowed') is not True or stale.get('reason') != 'stale_battle_flag':
        errors.append('stale persisted battle flag must allow safe recovery')
    known = build_recovery_decision({'location_id': 'hub_westwild'})
    if known.get('target_location_id') != SAFE_RECOVERY_LOCATION_ID:
        errors.append('known location recovery must target safe recovery location')
    fallback = build_recovery_decision({'location_id': 'not_a_real_location'})
    if fallback.get('target_location_id') != SAFE_RECOVERY_LOCATION_ID:
        errors.append('unknown location must fallback to safe recovery location')
    return errors
