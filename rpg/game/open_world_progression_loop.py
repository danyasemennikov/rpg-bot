from __future__ import annotations

from game.items_data import get_item, get_item_metadata
from game.open_world_pve_tuning import build_all_open_world_pve_numeric_tuning_reports
from game.open_world_reward_sanity import build_route_open_world_reward_sanity_report
from game.reward_source_metadata import classify_item_reward_family


PROGRESSION_ITEM_TYPES = {'gear', 'enhancement_material', 'crafting_material'}


def _classify_item(item_id: str) -> str:
    item = get_item(item_id)
    if not item:
        return 'unknown'

    metadata = get_item_metadata(item_id)
    reward_family = classify_item_reward_family(item_id)
    item_type = str(item.get('item_type') or '').strip()

    if reward_family == 'enhancement_material':
        return 'enhancement_material'
    if item_type in {'weapon', 'armor', 'accessory'}:
        return 'gear'
    if item_type == 'material':
        return 'crafting_material'
    if item_type in {'consumable', 'potion'}:
        return 'consumable'
    return 'unknown'




def _iter_valid_loot_item_ids(profile: dict) -> tuple[list[str], list[str]]:
    valid_item_ids: list[str] = []
    warnings: list[str] = []
    mob_id = str(profile.get('mob_id') or '').strip() or 'unknown_mob'
    loot_table = profile.get('loot_table')

    if not isinstance(loot_table, (list, tuple)):
        warnings.append(f'malformed_loot_table:{mob_id}')
        return valid_item_ids, warnings

    for index, entry in enumerate(loot_table):
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            warnings.append(f'malformed_loot_entry:{mob_id}:{index}')
            continue

        item_id, chance = entry
        normalized_item_id = str(item_id or '').strip() if isinstance(item_id, str) else ''
        if not normalized_item_id:
            warnings.append(f'malformed_loot_item_id:{mob_id}:{index}')
            continue

        if not isinstance(chance, (int, float)) or chance <= 0 or chance > 1:
            warnings.append(f'malformed_loot_chance:{mob_id}:{index}')
            continue

        valid_item_ids.append(normalized_item_id)

    return valid_item_ids, warnings
def build_open_world_progression_source_report(route_id: str) -> dict:
    reward_report = build_route_open_world_reward_sanity_report(str(route_id or '').strip())
    if not reward_report:
        return {}

    loot_item_ids: set[str] = set()
    unknown_item_ids: set[str] = set()
    enhancement_material_ids: set[str] = set()
    gear_template_ids: set[str] = set()
    progression_warnings: list[str] = []

    for profile in reward_report.get('mob_profiles', ()):
        valid_item_ids, malformed_warnings = _iter_valid_loot_item_ids(profile if isinstance(profile, dict) else {})
        progression_warnings.extend(malformed_warnings)
        for normalized_item_id in valid_item_ids:
            loot_item_ids.add(normalized_item_id)
            item_class = _classify_item(normalized_item_id)
            if item_class == 'unknown':
                unknown_item_ids.add(normalized_item_id)
            if item_class == 'enhancement_material':
                enhancement_material_ids.add(normalized_item_id)
            if item_class == 'gear':
                gear_template_ids.add(normalized_item_id)

    if unknown_item_ids:
        progression_warnings.append(f'unknown_loot_items:{sorted(unknown_item_ids)}')

    if reward_report.get('numeric_tuning_ready') and not loot_item_ids:
        progression_warnings.append('numeric_ready_route_has_no_loot_item_ids')

    has_progression_materials = any(
        _classify_item(item_id) in PROGRESSION_ITEM_TYPES for item_id in loot_item_ids
    )
    has_rewarded_items_with_metadata = all(get_item(item_id) is not None for item_id in loot_item_ids)

    return {
        'route_id': reward_report.get('route_id'),
        'numeric_tuning_ready': bool(reward_report.get('numeric_tuning_ready')),
        'is_sparse_or_stub': bool(reward_report.get('is_sparse_or_stub')),
        'reward_category': reward_report.get('reward_category'),
        'reward_profile_id': reward_report.get('reward_profile_id'),
        'mob_ids': tuple(sorted({str(p.get('mob_id')) for p in reward_report.get('mob_profiles', ()) if p.get('mob_id')})),
        'loot_item_ids': tuple(sorted(loot_item_ids)),
        'enhancement_material_ids': tuple(sorted(enhancement_material_ids)),
        'gear_template_ids': tuple(sorted(gear_template_ids)),
        'item_classification': {item_id: _classify_item(item_id) for item_id in sorted(loot_item_ids)},
        'has_progression_materials': has_progression_materials,
        'has_rewarded_items_with_metadata': has_rewarded_items_with_metadata,
        'progression_warnings': tuple(sorted(set(progression_warnings))),
        'actionable_warnings': tuple(sorted(set(str(w) for w in reward_report.get('actionable_warnings', ()) if str(w).strip()))),
    }


def build_all_open_world_progression_source_reports() -> tuple[dict, ...]:
    return tuple(
        build_open_world_progression_source_report(str(r.get('route_id') or '').strip())
        for r in build_all_open_world_pve_numeric_tuning_reports()
        if str(r.get('route_id') or '').strip()
    )


def validate_open_world_progression_loop_sanity() -> list[str]:
    errors: list[str] = []
    for report in build_all_open_world_progression_source_reports():
        route_id = str(report.get('route_id') or '').strip()
        if not route_id:
            errors.append('missing route_id in progression loop report')
            continue
        if report.get('numeric_tuning_ready'):
            if not report.get('loot_item_ids'):
                errors.append(f'progression report missing loot item ids on ready route {route_id}')
            if not report.get('has_rewarded_items_with_metadata'):
                errors.append(f'progression report has unknown rewarded item ids on ready route {route_id}')
            if any('unknown_loot_items' in warning for warning in report.get('progression_warnings', ())):
                errors.append(f'progression report has unknown loot item ids on ready route {route_id}')
            if any('malformed_loot_' in warning for warning in report.get('progression_warnings', ())):
                errors.append(f'progression report has malformed loot entries on ready route {route_id}')
    return errors
