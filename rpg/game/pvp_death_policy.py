"""Death-loss/respawn foundation helpers for open-world PvP."""

from __future__ import annotations

from game.locations import get_location_security_tier, resolve_region_safe_hub

PVP_DEATH_LOSS_PERCENT_BY_SECURITY_TIER = {
    'safe': 0.0,
    'guarded': 0.50,
    'frontier': 0.60,
    'core_war': 0.70,
}
PVE_DEATH_LOSS_PERCENT = 0.25


def resolve_pvp_death_loss_percent(*, location_id: str | None = None, security_tier: str | None = None) -> float:
    tier = security_tier or get_location_security_tier(location_id)
    return float(PVP_DEATH_LOSS_PERCENT_BY_SECURITY_TIER.get(tier, 0.0))


def resolve_pve_death_loss_percent() -> float:
    return PVE_DEATH_LOSS_PERCENT


def resolve_death_respawn_hub(*, location_id: str | None = None, region_id: str | None = None, world_id: str | None = None) -> str:
    return resolve_region_safe_hub(location_id=location_id, region_id=region_id, world_id=world_id)
