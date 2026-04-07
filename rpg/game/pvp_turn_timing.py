"""Timed PvP turn foundation with auto-action fallback contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

PVP_TURN_TIMEOUT_SECONDS = 15

ACTION_FAMILY_FINISHING = 'finishing'
ACTION_FAMILY_DEFENSIVE = 'defensive'
ACTION_FAMILY_SETUP = 'setup'
ACTION_FAMILY_CORE = 'core'
ACTION_FAMILY_ATTACK = 'attack'

AUTO_ACTION_PRIORITY = (
    ACTION_FAMILY_FINISHING,
    ACTION_FAMILY_DEFENSIVE,
    ACTION_FAMILY_SETUP,
    ACTION_FAMILY_CORE,
    ACTION_FAMILY_ATTACK,
)

DEFAULT_AUTO_ACTION_ID = 'normal_attack'


@dataclass(frozen=True)
class PvpActionOption:
    action_id: str
    action_family: str
    is_ready: bool = True


@dataclass(frozen=True)
class PvpTurnResolution:
    action_id: str
    action_source: str  # 'player' or 'auto'
    timed_out: bool


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_turn_deadline(*, turn_started_at: datetime) -> datetime:
    return turn_started_at + timedelta(seconds=PVP_TURN_TIMEOUT_SECONDS)


def is_turn_timed_out(*, turn_started_at: datetime, now: datetime | None = None) -> bool:
    check_time = now or _utc_now()
    return check_time >= build_turn_deadline(turn_started_at=turn_started_at)


def resolve_auto_pvp_action(options: list[PvpActionOption]) -> str:
    ready_options = [row for row in options if row.is_ready]
    for family in AUTO_ACTION_PRIORITY:
        for option in ready_options:
            if option.action_family == family:
                return option.action_id
    return DEFAULT_AUTO_ACTION_ID


def resolve_timed_turn_action(
    *,
    turn_started_at: datetime,
    available_options: list[PvpActionOption],
    selected_action_id: str | None,
    now: datetime | None = None,
) -> PvpTurnResolution | None:
    timed_out = is_turn_timed_out(turn_started_at=turn_started_at, now=now)
    if not timed_out:
        if selected_action_id:
            for option in available_options:
                if option.action_id == selected_action_id and option.is_ready:
                    return PvpTurnResolution(
                        action_id=selected_action_id,
                        action_source='player',
                        timed_out=False,
                    )
        return None

    return PvpTurnResolution(
        action_id=resolve_auto_pvp_action(available_options),
        action_source='auto',
        timed_out=timed_out,
    )
