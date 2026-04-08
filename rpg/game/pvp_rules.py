"""Open-world PvP legality foundation helpers.

Phase-1 contract only: legality/state checks without full PvP combat flow.
"""

from __future__ import annotations

import time

from database import get_connection
from game.locations import get_location_security_tier
from game.pvp_state import build_player_pvp_state

PVP_STATUS_NEUTRAL = 'neutral'
PVP_STATUS_FLAGGED = 'flagged'
PVP_STATUS_FORCED_FLAGGED = 'forced_flagged'
PVP_STATUS_WAR_FLAGGED = 'war_flagged'

LEGAL_TARGET_STATUSES = {
    PVP_STATUS_FLAGGED,
    PVP_STATUS_FORCED_FLAGGED,
    PVP_STATUS_WAR_FLAGGED,
}

DEFAULT_NOVICE_PROTECTION_LEVEL_CAP = 15
RESPAWN_PROTECTION_WINDOW_SECONDS = 8 * 60
RECENT_AGGRESSOR_WINDOW_MINUTES = 20
BASE_INFAMY_ILLEGAL_GUARDED_AGGRESSION = 2
EXTRA_INFAMY_PROTECTED_TARGET_KILL = 2
MAX_EXTRA_INFAMY_REPEAT_HARASSMENT = 4


def get_player_pvp_status(player: dict | None) -> str:
    return build_player_pvp_state(player).pvp_status


def is_player_red_flagged(player: dict | None) -> bool:
    return bool(build_player_pvp_state(player).red_flag)


def is_novice_protection_active(
    player: dict | None,
    *,
    novice_level_cap: int = DEFAULT_NOVICE_PROTECTION_LEVEL_CAP,
) -> bool:
    if not player:
        return False
    state = build_player_pvp_state(player)
    novice_enabled = bool(state.novice_protection)
    return novice_enabled and int(player.get('level', 1) or 1) <= novice_level_cap


def does_novice_protection_block_interaction(
    *,
    attacker: dict,
    defender: dict,
    location_id: str | None,
    novice_level_cap: int = DEFAULT_NOVICE_PROTECTION_LEVEL_CAP,
) -> bool:
    security_tier = get_location_security_tier(location_id)
    if security_tier in {'frontier', 'core_war'}:
        return False
    if is_player_red_flagged(defender):
        return False
    return (
        is_novice_protection_active(attacker, novice_level_cap=novice_level_cap)
        or is_novice_protection_active(defender, novice_level_cap=novice_level_cap)
    )


def is_aggression_illegal(*, attacker: dict, defender: dict, location_id: str | None) -> bool:
    security_tier = get_location_security_tier(location_id)
    if security_tier != 'guarded':
        return False
    if is_player_red_flagged(defender):
        return False
    if get_player_pvp_status(defender) in LEGAL_TARGET_STATUSES:
        return False
    return get_player_pvp_status(defender) == PVP_STATUS_NEUTRAL


def should_apply_red_flag(*, attacker: dict, defender: dict, location_id: str | None) -> bool:
    if is_player_red_flagged(attacker):
        return False
    return is_aggression_illegal(attacker=attacker, defender=defender, location_id=location_id)


def has_respawn_protection(player: dict | None, *, now_ts: int | None = None) -> bool:
    if not player:
        return False
    check_ts = int(now_ts if now_ts is not None else time.time())
    protection_until = int(player.get('pvp_respawn_protection_until', 0) or 0)
    return protection_until > check_ts


def clear_respawn_protection(*, player_id: int) -> None:
    conn = get_connection()
    conn.execute(
        'UPDATE players SET pvp_respawn_protection_until=0 WHERE telegram_id=?',
        (player_id,),
    )
    conn.commit()
    conn.close()


def clear_respawn_protection_on_dangerous_reentry(*, player_id: int, location_id: str | None) -> None:
    if get_location_security_tier(location_id) in {'frontier', 'core_war'}:
        clear_respawn_protection(player_id=player_id)


def is_recent_retaliation_context(*, attacker_id: int, defender_id: int, window_minutes: int = RECENT_AGGRESSOR_WINDOW_MINUTES) -> bool:
    conn = get_connection()
    row = conn.execute(
        '''
        SELECT id
        FROM pvp_log
        WHERE attacker_id=? AND defender_id=?
          AND fought_at >= datetime('now', ?)
        ORDER BY id DESC
        LIMIT 1
        ''',
        (defender_id, attacker_id, f'-{int(window_minutes)} minutes'),
    ).fetchone()
    conn.close()
    return bool(row)


def count_recent_repeat_kills(*, winner_id: int, loser_id: int, window_minutes: int) -> int:
    conn = get_connection()
    row = conn.execute(
        '''
        SELECT COUNT(1) AS total
        FROM pvp_log
        WHERE winner_id=?
          AND (
            (attacker_id=? AND defender_id=?)
            OR
            (attacker_id=? AND defender_id=?)
          )
          AND fought_at >= datetime('now', ?)
        ''',
        (winner_id, winner_id, loser_id, loser_id, winner_id, f'-{int(window_minutes)} minutes'),
    ).fetchone()
    conn.close()
    return int(row['total'] or 0) if row else 0


def resolve_illegal_aggression_infamy(*, attacker: dict, defender: dict, location_id: str | None) -> int:
    if not is_aggression_illegal(attacker=attacker, defender=defender, location_id=location_id):
        return 0
    infamy = BASE_INFAMY_ILLEGAL_GUARDED_AGGRESSION
    attacker_id = int(attacker.get('telegram_id', 0) or 0)
    defender_id = int(defender.get('telegram_id', 0) or 0)
    if attacker_id and defender_id and is_recent_retaliation_context(attacker_id=attacker_id, defender_id=defender_id):
        infamy = 1
    return infamy


def resolve_kill_infamy_delta(
    *,
    winner: dict,
    loser: dict,
    initiator: dict | None = None,
    initial_target: dict | None = None,
    location_id: str | None,
    repeat_kill_count: int,
) -> int:
    initiator_row = initiator or winner
    target_row = initial_target or loser
    if int(winner.get('telegram_id', 0) or 0) != int(initiator_row.get('telegram_id', 0) or 0):
        return 0
    if is_aggression_illegal(attacker=initiator_row, defender=target_row, location_id=location_id):
        infamy = BASE_INFAMY_ILLEGAL_GUARDED_AGGRESSION
        if int(loser.get('telegram_id', 0) or 0) == int(target_row.get('telegram_id', 0) or 0) and has_respawn_protection(loser):
            infamy += EXTRA_INFAMY_PROTECTED_TARGET_KILL
        if repeat_kill_count > 0:
            infamy += min(MAX_EXTRA_INFAMY_REPEAT_HARASSMENT, repeat_kill_count)
        if is_recent_retaliation_context(
            attacker_id=int(initiator_row['telegram_id']),
            defender_id=int(target_row['telegram_id']),
        ):
            infamy = max(1, infamy - 1)
        return infamy
    return 0


def get_attack_block_reason(
    *,
    attacker: dict,
    defender: dict,
    location_id: str | None,
    novice_level_cap: int = DEFAULT_NOVICE_PROTECTION_LEVEL_CAP,
) -> str | None:
    if not attacker or not defender:
        return 'missing_player'
    if attacker.get('telegram_id') == defender.get('telegram_id'):
        return 'self_target'
    security_tier = get_location_security_tier(location_id)
    if security_tier == 'safe':
        return 'safe_zone'
    if does_novice_protection_block_interaction(
        attacker=attacker,
        defender=defender,
        location_id=location_id,
        novice_level_cap=novice_level_cap,
    ):
        return 'novice_protection'
    if security_tier in {'safe', 'guarded'} and has_respawn_protection(defender):
        return 'respawn_protection'
    return None


def is_target_attackable(
    *,
    attacker: dict,
    defender: dict,
    location_id: str | None,
    novice_level_cap: int = DEFAULT_NOVICE_PROTECTION_LEVEL_CAP,
) -> bool:
    return get_attack_block_reason(
        attacker=attacker,
        defender=defender,
        location_id=location_id,
        novice_level_cap=novice_level_cap,
    ) is None
