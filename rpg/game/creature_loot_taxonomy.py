"""Creature loot taxonomy foundation helpers (Phase 2).

Small, readable contract:
- body_type
- special_trait
- encounter_class
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CreatureBodyType = Literal[
    'beast',
    'avian',
    'reptile',
    'insectoid',
    'arachnid',
    'humanoid',
    'undead',
    'construct',
    'slime',
    'elemental',
    'plant',
    'fungal',
    'corrupted',
    'demonic',
    'arcane_beast',
]

CreatureSpecialTrait = Literal[
    'predator',
    'venomous',
    'armored',
    'spectral',
    'cursed',
    'fire_touched',
    'frost_touched',
    'holy',
    'arcane',
    'toxic',
    'giant',
]

CreatureEncounterClass = Literal[
    'normal',
    'elite',
    'boss',
    'world_boss',
    'quest_target',
]

CreatureLootIdentity = Literal[
    'meat',
    'hide',
    'bones',
    'fang_claw_horn',
    'feathers',
    'talons',
    'beak',
    'venom_gland',
    'humanoid_trophy',
    'grave_dust',
    'ectoplasm',
    'cursed_cloth',
    'metal_scrap',
    'plates',
    'mechanism',
    'core',
    'gel',
    'spores',
    'sap',
    'resin',
    'goo',
    'elemental_essence',
    'special_part',
]

BASE_LOOT_IDENTITY_BY_BODY_TYPE: dict[CreatureBodyType, tuple[CreatureLootIdentity, ...]] = {
    'beast': ('meat', 'hide', 'bones', 'fang_claw_horn'),
    'avian': ('meat', 'feathers', 'talons', 'beak'),
    'reptile': ('meat', 'hide', 'bones', 'fang_claw_horn'),
    'insectoid': ('goo', 'venom_gland', 'special_part'),
    'arachnid': ('goo', 'venom_gland', 'special_part'),
    'humanoid': ('humanoid_trophy', 'bones'),
    'undead': ('bones', 'grave_dust', 'ectoplasm', 'cursed_cloth'),
    'construct': ('metal_scrap', 'plates', 'mechanism', 'core'),
    'slime': ('gel', 'goo', 'special_part'),
    'elemental': ('elemental_essence', 'core', 'special_part'),
    'plant': ('sap', 'resin', 'spores'),
    'fungal': ('spores', 'goo', 'special_part'),
    'corrupted': ('meat', 'bones', 'special_part'),
    'demonic': ('meat', 'bones', 'special_part'),
    'arcane_beast': ('meat', 'hide', 'bones', 'elemental_essence'),
}

TRAIT_OVERLAY_IDENTITY: dict[CreatureSpecialTrait, tuple[CreatureLootIdentity, ...]] = {
    'predator': ('fang_claw_horn',),
    'venomous': ('venom_gland',),
    'armored': ('plates',),
    'spectral': ('ectoplasm',),
    'cursed': ('grave_dust', 'cursed_cloth'),
    'fire_touched': ('elemental_essence',),
    'frost_touched': ('elemental_essence',),
    'holy': ('elemental_essence',),
    'arcane': ('elemental_essence',),
    'toxic': ('venom_gland',),
    'giant': ('special_part',),
}


@dataclass(frozen=True)
class CreatureLootTaxonomy:
    body_type: CreatureBodyType
    special_trait: CreatureSpecialTrait
    encounter_class: CreatureEncounterClass


def normalize_creature_taxonomy(raw: dict | None) -> CreatureLootTaxonomy:
    raw = raw or {}
    body_type = raw.get('body_type') if raw.get('body_type') in BASE_LOOT_IDENTITY_BY_BODY_TYPE else 'beast'
    special_trait = raw.get('special_trait') if raw.get('special_trait') in TRAIT_OVERLAY_IDENTITY else 'predator'
    encounter = raw.get('encounter_class') if raw.get('encounter_class') in {'normal', 'elite', 'boss', 'world_boss', 'quest_target'} else 'normal'
    return CreatureLootTaxonomy(
        body_type=body_type,
        special_trait=special_trait,
        encounter_class=encounter,
    )


def resolve_creature_loot_identity(taxonomy: CreatureLootTaxonomy) -> tuple[CreatureLootIdentity, ...]:
    base = list(BASE_LOOT_IDENTITY_BY_BODY_TYPE[taxonomy.body_type])
    base.extend(TRAIT_OVERLAY_IDENTITY.get(taxonomy.special_trait, ()))
    if taxonomy.encounter_class in {'elite', 'boss', 'world_boss', 'quest_target'}:
        base.append('special_part')
    ordered_unique = tuple(dict.fromkeys(base))
    return ordered_unique


def encounter_class_to_source_category(encounter_class: CreatureEncounterClass) -> str:
    """Bridge helper: encounter class is not source category, but maps cleanly."""
    if encounter_class == 'world_boss':
        return 'world_boss'
    if encounter_class == 'boss':
        return 'open_world_regional_boss'
    if encounter_class == 'elite':
        return 'open_world_elite'
    return 'open_world_normal'
