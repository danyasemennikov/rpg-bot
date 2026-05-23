from __future__ import annotations

from game.items_data import get_item
from game.mobs import MOBS
from game.open_world_pack_balance import get_open_world_route_encounter_compositions
from game.open_world_pve_tuning import build_route_pve_numeric_tuning_report


def _iter_invalid_loot_entries(loot_table: object) -> list[dict[str, object]]:
    invalid: list[dict[str, object]] = []
    if not isinstance(loot_table, (list, tuple)):
        return [{'entry': loot_table, 'reason': 'loot_table_not_sequence'}]

    for index, entry in enumerate(loot_table):
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            invalid.append({'index': index, 'entry': entry, 'reason': 'entry_not_pair'})
            continue
        item_id, chance = entry
        if not isinstance(item_id, str) or not item_id.strip():
            invalid.append({'index': index, 'entry': entry, 'reason': 'invalid_item_id'})
            continue
        if not isinstance(chance, (int, float)) or chance <= 0 or chance > 1:
            invalid.append({'index': index, 'entry': entry, 'reason': 'invalid_chance'})
            continue
        if get_item(item_id) is None:
            invalid.append({'index': index, 'entry': entry, 'reason': 'unknown_item_id'})
    return invalid


def build_open_world_mob_reward_profile(mob_id) -> dict:
    normalized_mob_id = str(mob_id or '').strip()
    mob = MOBS.get(normalized_mob_id)
    if not mob:
        return {}
    loot_table = mob.get('loot_table')
    invalid_loot_entries = _iter_invalid_loot_entries(loot_table)
    return {
        'mob_id': normalized_mob_id,
        'level': mob.get('level'),
        'exp_reward': mob.get('exp_reward'),
        'gold_min': mob.get('gold_min'),
        'gold_max': mob.get('gold_max'),
        'loot_table': loot_table,
        'loot_table_size': len(loot_table) if isinstance(loot_table, (list, tuple)) else 0,
        'invalid_loot_entries': tuple(invalid_loot_entries),
    }


def build_route_open_world_reward_sanity_report(route_id) -> dict:
    numeric_report = build_route_pve_numeric_tuning_report(str(route_id or '').strip())
    if not numeric_report:
        return {}

    mob_ids = numeric_report.get('mob_ids', ())
    profiles: list[dict] = []
    missing_mob_ids: list[str] = []
    for mob_id in mob_ids:
        profile = build_open_world_mob_reward_profile(mob_id)
        if profile:
            profiles.append(profile)
        else:
            missing_mob_ids.append(str(mob_id))

    exp_values = [int(p['exp_reward']) for p in profiles if isinstance(p.get('exp_reward'), int)]
    gold_min_values = [int(p['gold_min']) for p in profiles if isinstance(p.get('gold_min'), int)]
    gold_max_values = [int(p['gold_max']) for p in profiles if isinstance(p.get('gold_max'), int)]

    warnings: list[str] = []
    for missing_mob_id in sorted(set(missing_mob_ids)):
        warnings.append(f'missing_mob_reward_profile:{missing_mob_id}')
    for profile in profiles:
        mob_id = str(profile.get('mob_id'))
        if not isinstance(profile.get('exp_reward'), int) or profile.get('exp_reward', 0) <= 0:
            warnings.append(f'non_positive_exp_reward:{mob_id}')
        if not isinstance(profile.get('gold_min'), int) or profile.get('gold_min', -1) < 0:
            warnings.append(f'invalid_gold_min:{mob_id}')
        if not isinstance(profile.get('gold_max'), int) or profile.get('gold_max', -1) < int(profile.get('gold_min', 0)):
            warnings.append(f'invalid_gold_bounds:{mob_id}')
        if profile.get('invalid_loot_entries'):
            warnings.append(f'invalid_loot_entries:{mob_id}')

    return {
        'route_id': numeric_report.get('route_id'),
        'numeric_tuning_ready': numeric_report.get('numeric_tuning_ready', False),
        'is_sparse_or_stub': numeric_report.get('is_sparse_or_stub', False),
        'reward_category': numeric_report.get('reward_category'),
        'reward_profile_id': numeric_report.get('reward_profile_id'),
        'solo_mob_ids': numeric_report.get('solo_mob_ids', ()),
        'pack_mob_ids': numeric_report.get('pack_mob_ids', ()),
        'elite_anchor_mob_ids': numeric_report.get('elite_anchor_mob_ids', ()),
        'rare_anchor_mob_ids': numeric_report.get('rare_anchor_mob_ids', ()),
        'mob_profiles': tuple(profiles),
        'missing_mob_ids': tuple(sorted(set(missing_mob_ids))),
        'exp_min': min(exp_values) if exp_values else None,
        'exp_max': max(exp_values) if exp_values else None,
        'gold_min': min(gold_min_values) if gold_min_values else None,
        'gold_max': max(gold_max_values) if gold_max_values else None,
        'has_loot_tables': all(isinstance(p.get('loot_table'), (list, tuple)) and len(p.get('loot_table') or ()) > 0 for p in profiles),
        'route_reward_warnings': tuple(sorted(set(warnings))),
        'actionable_warnings': numeric_report.get('actionable_warnings', ()),
    }


def build_all_open_world_reward_sanity_reports() -> tuple[dict, ...]:
    reports: list[dict] = []
    for composition in get_open_world_route_encounter_compositions():
        route_id = str(composition.get('route_id') or '').strip()
        if route_id:
            reports.append(build_route_open_world_reward_sanity_report(route_id))
    return tuple(reports)


def validate_open_world_reward_loot_sanity() -> list[str]:
    errors: list[str] = []
    for report in build_all_open_world_reward_sanity_reports():
        route_id = str(report.get('route_id') or '').strip()
        if not route_id:
            errors.append('missing route_id in reward sanity report')
            continue
        if report.get('exp_min') is not None and report.get('exp_max') is not None and report['exp_min'] > report['exp_max']:
            errors.append(f'invalid exp bounds on route {route_id}')
        if report.get('gold_min') is not None and report.get('gold_max') is not None and report['gold_min'] > report['gold_max']:
            errors.append(f'invalid gold bounds on route {route_id}')

        missing_mob_ids = tuple(str(mob_id) for mob_id in report.get('missing_mob_ids', ()) if str(mob_id).strip())
        for mob_id in missing_mob_ids:
            errors.append(f'missing reward profile on route {route_id}: {mob_id}')

        if bool(report.get('numeric_tuning_ready')):
            for profile in report.get('mob_profiles', ()):
                mob_id = str(profile.get('mob_id') or '').strip()
                if not mob_id:
                    errors.append(f'missing mob_id profile on route {route_id}')
                    continue
                if profile.get('exp_reward', 0) <= 0:
                    errors.append(f'non-positive exp reward on ready route {route_id}:{mob_id}')
                if profile.get('gold_min', -1) < 0:
                    errors.append(f'negative gold_min on ready route {route_id}:{mob_id}')
                if profile.get('gold_max', -1) < profile.get('gold_min', 0):
                    errors.append(f'invalid gold bounds on ready route {route_id}:{mob_id}')
                if profile.get('invalid_loot_entries'):
                    errors.append(f'invalid loot entries on ready route {route_id}:{mob_id}')
    return errors
