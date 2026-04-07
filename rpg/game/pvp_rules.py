"""Open-world PvP legality foundation helpers.

Phase-1 contract only: legality/state checks without full PvP combat flow.
"""

from __future__ import annotations

from game.locations import get_location_security_tier

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


def get_player_pvp_status(player: dict | None) -> str:
    if not player:
        return PVP_STATUS_NEUTRAL
    status = str(player.get('pvp_status') or PVP_STATUS_NEUTRAL)
    if status in {
        PVP_STATUS_NEUTRAL,
        PVP_STATUS_FLAGGED,
        PVP_STATUS_FORCED_FLAGGED,
        PVP_STATUS_WAR_FLAGGED,
    }:
        return status
    return PVP_STATUS_NEUTRAL


def is_player_red_flagged(player: dict | None) -> bool:
    if not player:
        return False
    return bool(int(player.get('red_flag', 0) or 0))


def is_novice_protection_active(
    player: dict | None,
    *,
    novice_level_cap: int = DEFAULT_NOVICE_PROTECTION_LEVEL_CAP,
) -> bool:
    if not player:
        return False
    novice_enabled = bool(int(player.get('novice_protection', 0) or 0))
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


def is_target_attackable(
    *,
    attacker: dict,
    defender: dict,
    location_id: str | None,
    novice_level_cap: int = DEFAULT_NOVICE_PROTECTION_LEVEL_CAP,
) -> bool:
    if not attacker or not defender:
        return False
    if attacker.get('telegram_id') == defender.get('telegram_id'):
        return False
    if get_location_security_tier(location_id) == 'safe':
        return False
    if does_novice_protection_block_interaction(
        attacker=attacker,
        defender=defender,
        location_id=location_id,
        novice_level_cap=novice_level_cap,
    ):
        return False
    return True
