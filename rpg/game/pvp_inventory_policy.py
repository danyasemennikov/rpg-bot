"""PvP/PvE death vulnerability policy helpers for inventory items."""

from __future__ import annotations

from dataclasses import dataclass

from game.items_data import get_item, get_item_reward_tags

VULNERABLE_ON_PVP_DEATH = 'vulnerable_on_pvp_death'
VULNERABLE_ON_PVE_DEATH = 'vulnerable_on_pve_death'
PROTECTED = 'protected'


@dataclass(frozen=True)
class ItemDeathVulnerabilityProfile:
    classification: str
    vulnerable_on_pvp_death: bool
    vulnerable_on_pve_death: bool


def resolve_item_death_vulnerability(item_id: str) -> ItemDeathVulnerabilityProfile:
    item = get_item(item_id) or {}
    reward_tags = get_item_reward_tags(item_id)

    explicit_policy = reward_tags.get('death_vulnerability')
    if explicit_policy == VULNERABLE_ON_PVP_DEATH:
        return ItemDeathVulnerabilityProfile(
            classification=VULNERABLE_ON_PVP_DEATH,
            vulnerable_on_pvp_death=True,
            vulnerable_on_pve_death=True,
        )
    if explicit_policy == VULNERABLE_ON_PVE_DEATH:
        return ItemDeathVulnerabilityProfile(
            classification=VULNERABLE_ON_PVE_DEATH,
            vulnerable_on_pvp_death=False,
            vulnerable_on_pve_death=True,
        )

    reward_family = reward_tags.get('reward_family')
    if reward_family in {
        'creature_loot',
        'gathering_material',
        'crafting_material',
        'reagent',
        'enhancement_material',
    }:
        return ItemDeathVulnerabilityProfile(
            classification=VULNERABLE_ON_PVP_DEATH,
            vulnerable_on_pvp_death=True,
            vulnerable_on_pve_death=True,
        )

    if item.get('item_type') in {'potion'}:
        return ItemDeathVulnerabilityProfile(
            classification=VULNERABLE_ON_PVE_DEATH,
            vulnerable_on_pvp_death=False,
            vulnerable_on_pve_death=True,
        )

    return ItemDeathVulnerabilityProfile(
        classification=PROTECTED,
        vulnerable_on_pvp_death=False,
        vulnerable_on_pve_death=False,
    )
