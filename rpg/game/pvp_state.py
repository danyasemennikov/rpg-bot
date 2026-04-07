"""Persistent/runtime PvP state contract for player rows."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PVP_STATUS = 'neutral'
ALLOWED_PVP_STATUSES = {
    'neutral',
    'flagged',
    'forced_flagged',
    'war_flagged',
}
DEFAULT_COMBAT_TAG_UNTIL = 0
DEFAULT_RED_FLAG = 0
DEFAULT_INFAMY = 0
DEFAULT_NOVICE_PROTECTION = 1


@dataclass(frozen=True)
class PlayerPvpState:
    pvp_status: str
    combat_tag_until: int
    red_flag: int
    infamy: int
    novice_protection: int


def build_player_pvp_state(player: dict | None) -> PlayerPvpState:
    if not player:
        return PlayerPvpState(
            pvp_status=DEFAULT_PVP_STATUS,
            combat_tag_until=DEFAULT_COMBAT_TAG_UNTIL,
            red_flag=DEFAULT_RED_FLAG,
            infamy=DEFAULT_INFAMY,
            novice_protection=DEFAULT_NOVICE_PROTECTION,
        )

    raw_status = str(player.get('pvp_status') or DEFAULT_PVP_STATUS)
    normalized_status = raw_status if raw_status in ALLOWED_PVP_STATUSES else DEFAULT_PVP_STATUS

    return PlayerPvpState(
        pvp_status=normalized_status,
        combat_tag_until=int(player.get('combat_tag_until', DEFAULT_COMBAT_TAG_UNTIL) or DEFAULT_COMBAT_TAG_UNTIL),
        red_flag=int(player.get('red_flag', DEFAULT_RED_FLAG) or DEFAULT_RED_FLAG),
        infamy=max(0, int(player.get('infamy', DEFAULT_INFAMY) or DEFAULT_INFAMY)),
        novice_protection=int(player.get('novice_protection', DEFAULT_NOVICE_PROTECTION) or DEFAULT_NOVICE_PROTECTION),
    )
