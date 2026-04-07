"""Open-world PvP engagement/preparation window foundation.

This module intentionally does not launch live combat by itself.
It only manages a narrow engagement contract that future PvP flow can build on.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

ENGAGEMENT_PREPARATION_WINDOW_SECONDS = 300  # 5 minutes

ENGAGEMENT_STATE_PENDING = 'pending'
ENGAGEMENT_STATE_ACTIVE = 'active'
ENGAGEMENT_STATE_ESCAPED = 'escaped'
ENGAGEMENT_STATE_CANCELLED = 'cancelled'
ENGAGEMENT_STATE_CONVERTED_TO_BATTLE = 'converted_to_battle'


@dataclass(frozen=True)
class OpenWorldPvpEngagement:
    attacker_id: int
    defender_id: int
    location_id: str
    engagement_started_at: datetime
    engagement_ready_at: datetime
    engagement_state: str
    reason_context: str | None = None
    reinforcement_hook: str | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_open_world_pvp_engagement(
    *,
    attacker_id: int,
    defender_id: int,
    location_id: str,
    reason_context: str | None = None,
    reinforcement_hook: str | None = None,
    now: datetime | None = None,
) -> OpenWorldPvpEngagement:
    started_at = now or _utc_now()
    ready_at = started_at + timedelta(seconds=ENGAGEMENT_PREPARATION_WINDOW_SECONDS)
    return OpenWorldPvpEngagement(
        attacker_id=attacker_id,
        defender_id=defender_id,
        location_id=location_id,
        engagement_started_at=started_at,
        engagement_ready_at=ready_at,
        engagement_state=ENGAGEMENT_STATE_PENDING,
        reason_context=reason_context,
        reinforcement_hook=reinforcement_hook,
    )


def activate_engagement_if_ready(
    engagement: OpenWorldPvpEngagement,
    *,
    now: datetime | None = None,
) -> OpenWorldPvpEngagement:
    if engagement.engagement_state != ENGAGEMENT_STATE_PENDING:
        return engagement
    check_time = now or _utc_now()
    if check_time < engagement.engagement_ready_at:
        return engagement
    return replace(engagement, engagement_state=ENGAGEMENT_STATE_ACTIVE)


def resolve_escape_attempt(
    engagement: OpenWorldPvpEngagement,
    *,
    escape_succeeded: bool,
    reason_context: str | None = None,
) -> tuple[OpenWorldPvpEngagement, bool]:
    """Resolve escape attempt and indicate whether live combat should start now.

    Returns: (updated_engagement, should_start_live_battle)
    """
    if engagement.engagement_state in {
        ENGAGEMENT_STATE_ESCAPED,
        ENGAGEMENT_STATE_CANCELLED,
        ENGAGEMENT_STATE_CONVERTED_TO_BATTLE,
    }:
        return engagement, False

    if escape_succeeded:
        return (
            replace(
                engagement,
                engagement_state=ENGAGEMENT_STATE_ESCAPED,
                reason_context=reason_context or engagement.reason_context,
            ),
            False,
        )

    return (
        replace(
            engagement,
            engagement_state=ENGAGEMENT_STATE_CONVERTED_TO_BATTLE,
            reason_context=reason_context or 'failed_escape',
        ),
        True,
    )
