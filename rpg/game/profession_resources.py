"""PEV1-1 resource identities and the single environmental source authority."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfessionResource:
    item_id: str
    profession_key: str
    required_level: int
    resource_group: str
    sell_price: int
    is_new: bool = False


RESOURCE_ROWS = (
    ('herb_common', 'herbalism', 1, 'herb_base', 3, False),
    ('herb_magic', 'herbalism', 8, 'herb_base', 12, False),
    ('shore_herbs', 'herbalism', 1, 'herb_base', 4, False),
    ('marsh_herb', 'herbalism', 6, 'herb_base', 4, False),
    ('desert_plant', 'herbalism', 12, 'herb_base', 4, False),
    ('toxic_herb', 'herbalism', 18, 'herb_base', 4, False),
    ('forest_mushroom', 'herbalism', 1, 'herb_base', 4, False),
    ('reed_bundle', 'herbalism', 1, 'fiber', 4, False),
    ('wood_common', 'woodcutting', 1, 'wood', 3, False),
    ('wood_dark', 'woodcutting', 6, 'wood', 10, False),
    ('frostpine_wood', 'woodcutting', 12, 'wood', 6, True),
    ('ancient_bark', 'woodcutting', 18, 'wood', 30, False),
    ('iron_ore', 'mining', 1, 'ore', 6, False),
    ('coal', 'mining', 1, 'fuel', 4, False),
    ('stone_chunk', 'mining', 1, 'stone', 4, False),
    ('salt_crystal', 'mining', 6, 'seasoning', 4, False),
    ('gem_common', 'mining', 12, 'gem', 35, False),
    ('sunscar_ore', 'mining', 18, 'ore', 8, True),
    ('shore_fish', 'fishing', 1, 'fish', 4, False),
    ('marsh_fish', 'fishing', 6, 'fish', 4, False),
    ('oasis_fish', 'fishing', 12, 'fish', 4, False),
    ('deep_marsh_fish', 'fishing', 18, 'fish', 8, True),
    ('boar_meat', 'hunting', 1, 'meat', 5, False),
    ('wolf_pelt', 'hunting', 1, 'hide', 8, False),
    ('wolf_fang', 'hunting', 2, 'trophy', 12, False),
    ('spider_silk', 'hunting', 6, 'fiber', 18, False),
    ('bear_hide', 'hunting', 12, 'hide', 12, True),
    ('troll_sinew', 'hunting', 18, 'monster_part', 18, True),
)

RESOURCES = {row[0]: ProfessionResource(*row) for row in RESOURCE_ROWS}
MANDATORY_RESOURCE_IDS = tuple(row[0] for row in RESOURCE_ROWS)
NEW_MATERIAL_IDS = tuple(row[0] for row in RESOURCE_ROWS if row[5])

# Location order is authoritative. Each tuple is (item_id, unconditional chance).
ENVIRONMENTAL_SOURCES: dict[str, tuple[tuple[str, float], ...]] = {
    'south_coast_shore': (('shore_fish', .70), ('shore_herbs', .20)),
    'old_mine_entrance': (('iron_ore', .65), ('coal', .30), ('gem_common', .05)),
    'westwild_n1': (('herb_common', .55),),
    'westwild_n2': (('herb_common', .45), ('wood_common', .15)),
    'westwild_n3': (('herb_common', .35), ('wood_common', .25)),
    'westwild_n4': (('herb_common', .35), ('forest_mushroom', .25), ('wood_common', .35)),
    'westwild_n5': (('herb_common', .35), ('wood_common', .40)),
    'westwild_n6': (('forest_mushroom', .30), ('wood_dark', .45)),
    'westwild_n7': (('forest_mushroom', .35), ('wood_dark', .50)),
    'westwild_n8': (('herb_common', .25), ('stone_chunk', .30), ('wood_dark', .25)),
    'westwild_n9': (('forest_mushroom', .40), ('herb_magic', .10)),
    'westwild_n10': (('forest_mushroom', .45), ('herb_magic', .15)),
    'westwild_n11': (('forest_mushroom', .50), ('wood_dark', .35), ('ancient_bark', .20)),
    'frostspine_n4': (('frostpine_wood', .45),),
    'frostspine_n6': (('frostpine_wood', .55), ('stone_chunk', .40), ('gem_common', .35)),
    'ashen_n3c1': (('herb_magic', .35), ('herb_common', .30), ('ancient_bark', .30)),
    'sunscar_n1': (('dry_reagent', .45),),
    'sunscar_n2': (('dry_reagent', .35), ('stone_chunk', .30)),
    'sunscar_n3': (('dry_reagent', .30), ('stone_chunk', .35)),
    'sunscar_n4': (('stone_chunk', .45),),
    'sunscar_n5': (('stone_chunk', .40), ('dry_reagent', .20)),
    'sunscar_n5a1': (('oasis_fish', .65), ('desert_plant', .35)),
    'sunscar_n6': (('desert_plant', .30),),
    'sunscar_n7': (('salt_crystal', .55),),
    'sunscar_n8': (('stone_chunk', .45),),
    'sunscar_n8a1': (('dry_reagent', .35),),
    'sunscar_n8a2': (('stone_chunk', .50),),
    'sunscar_n9': (('salt_crystal', .30), ('stone_chunk', .30)),
    'sunscar_n10': (('salt_crystal', .45), ('stone_chunk', .35), ('sunscar_ore', .20)),
    'sunscar_n11': (('dry_reagent', .30), ('stone_chunk', .30), ('sunscar_ore', .30)),
    'mireveil_n1': (('marsh_herb', .50),),
    'mireveil_n2': (('marsh_herb', .45),),
    'mireveil_n3': (('reed_bundle', .55),),
    'mireveil_n4': (('marsh_fish', .45), ('marsh_herb', .25)),
    'mireveil_n5': (('marsh_fish', .40), ('reed_bundle', .30)),
    'mireveil_n5a1': (('marsh_fish', .60),),
    'mireveil_n6': (('marsh_herb', .35),),
    'mireveil_n7': (('reed_bundle', .40), ('marsh_herb', .30)),
    'mireveil_n8': (('marsh_fish', .45), ('marsh_herb', .25), ('deep_marsh_fish', .20)),
    'mireveil_n8a1': (('marsh_mushroom', .55),),
    'mireveil_n8a2': (('toxic_herb', .45),),
    'mireveil_n9': (('marsh_mushroom', .35), ('toxic_herb', .25)),
    'mireveil_n10': (('toxic_herb', .50), ('deep_marsh_fish', .45)),
}

HARVEST_MANIFEST: dict[str, tuple[str, ...]] = {
    'forest_boar': ('boar_meat',),
    'forest_wolf': ('wolf_pelt', 'wolf_fang'),
    'white_wolf': ('wolf_pelt', 'wolf_fang'),
    'forest_spider': ('spider_silk',),
    'swamp_spider': ('spider_silk',),
    'bear': ('bear_hide',),
    'troll': ('troll_sinew',),
    'ice_troll': ('troll_sinew',),
    'troll_chief': ('troll_sinew',),
}


def location_sources(location_id: str) -> tuple[tuple[str, float], ...]:
    return ENVIRONMENTAL_SOURCES.get(location_id, ())


def validate_environmental_sources() -> list[str]:
    errors = []
    for location_id, rows in ENVIRONMENTAL_SOURCES.items():
        totals: dict[str, float] = {}
        for item_id, chance in rows:
            if item_id not in RESOURCES and item_id not in {'dry_reagent', 'marsh_mushroom'}:
                errors.append(f'{location_id}: invalid source {item_id} {chance}')
                continue
            if not 0 < chance <= 1:
                errors.append(f'{location_id}: invalid source {item_id} {chance}')
                continue
            profession = RESOURCES[item_id].profession_key if item_id in RESOURCES else 'herbalism'
            totals[profession] = totals.get(profession, 0.0) + chance
        for profession, total in totals.items():
            if total > 1.0000001:
                errors.append(f'{location_id}/{profession}: chance sum exceeds 1')
    return errors
