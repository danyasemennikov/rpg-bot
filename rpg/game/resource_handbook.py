"""Resource handbook derived from PEV1 source and recipe authorities."""

from __future__ import annotations

from game.profession_recipes import recipe_consumers
from game.profession_resources import ENVIRONMENTAL_SOURCES, HARVEST_MANIFEST, RESOURCES

HANDBOOK_PROFESSIONS = ('herbalism', 'woodcutting', 'mining', 'fishing', 'hunting')


def build_resource_handbook_index() -> dict[str, list[dict[str, object]]]:
    result = {key: [] for key in HANDBOOK_PROFESSIONS}
    for resource in sorted(RESOURCES.values(), key=lambda row: (row.profession_key, row.required_level, row.item_id)):
        environmental = [
            {'location_id': location_id, 'chance': chance}
            for location_id, rows in ENVIRONMENTAL_SOURCES.items()
            for item_id, chance in rows if item_id == resource.item_id
        ]
        mobs = [mob_id for mob_id, items in HARVEST_MANIFEST.items() if resource.item_id in items]
        result[resource.profession_key].append({
            'item_id': resource.item_id,
            'required_level': resource.required_level,
            'sell_price': resource.sell_price,
            'location_ids': [row['location_id'] for row in environmental],
            'environmental_sources': environmental,
            'mob_ids': mobs,
            'recipe_ids': list(recipe_consumers(resource.item_id)),
        })
    return result
