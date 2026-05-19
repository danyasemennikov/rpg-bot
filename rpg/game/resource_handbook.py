from __future__ import annotations

from collections import OrderedDict

from game.gathering_foundation import build_location_gather_source_profiles
from game.locations import LOCATIONS, resolve_location_id

HANDBOOK_PROFESSIONS: tuple[str, ...] = ('herbalism', 'woodcutting', 'mining', 'fishing')


def build_resource_handbook_index() -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {profession: [] for profession in HANDBOOK_PROFESSIONS}
    buckets: dict[str, OrderedDict[str, list[str]]] = {
        profession: OrderedDict() for profession in HANDBOOK_PROFESSIONS
    }

    for location_id in LOCATIONS:
        canonical_location_id = resolve_location_id(location_id)
        for profile in build_location_gather_source_profiles(canonical_location_id):
            profession = str(profile.profession_key)
            if profession not in buckets:
                continue
            item_id = str(profile.item_id)
            item_locations = buckets[profession].setdefault(item_id, [])
            if canonical_location_id not in item_locations:
                item_locations.append(canonical_location_id)

    for profession in HANDBOOK_PROFESSIONS:
        for item_id, location_ids in buckets[profession].items():
            result[profession].append({
                'item_id': item_id,
                'location_ids': list(location_ids),
            })
    return result
