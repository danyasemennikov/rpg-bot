from __future__ import annotations

from game.mobs import MOBS
from game.open_world_pack_balance import get_open_world_route_encounter_compositions
from game.open_world_readiness_gap_report import build_open_world_readiness_gap_report
from game.open_world_route_balance_report import build_open_world_route_balance_report


def build_open_world_pve_numeric_profile(mob_id: str) -> dict[str, object]:
    normalized_mob_id = str(mob_id or '').strip()
    mob = MOBS.get(normalized_mob_id)
    if not mob:
        return {}

    profile: dict[str, object] = {
        'mob_id': normalized_mob_id,
        'level': mob.get('level'),
        'hp': mob.get('hp'),
        'damage_min': mob.get('damage_min'),
        'damage_max': mob.get('damage_max'),
        'defense': mob.get('defense'),
    }
    return profile


def _min_max(values: list[int]) -> tuple[int | None, int | None]:
    if not values:
        return (None, None)
    return (min(values), max(values))


def build_route_pve_numeric_tuning_report(route_id: str) -> dict[str, object]:
    base_report = build_open_world_route_balance_report(route_id)
    if not base_report:
        return {}

    readiness = build_open_world_readiness_gap_report()
    numeric_ready_routes = set(str(route) for route in readiness.get('numeric_tuning_ready_routes', ()))
    actionable_warnings = sorted(
        gap['warning_id']
        for gap in readiness.get('actionable_gaps', ())
        if str(gap.get('route_id') or '').strip() == str(route_id or '').strip()
    )

    mob_ids = sorted({
        *base_report.get('solo_mob_ids', ()),
        *base_report.get('pack_mob_ids', ()),
        *base_report.get('elite_anchor_mob_ids', ()),
        *base_report.get('rare_anchor_mob_ids', ()),
    })

    numeric_profiles = [build_open_world_pve_numeric_profile(mob_id) for mob_id in mob_ids]
    numeric_profiles = [profile for profile in numeric_profiles if profile]

    hp_values = [int(profile['hp']) for profile in numeric_profiles if isinstance(profile.get('hp'), int)]
    level_values = [int(profile['level']) for profile in numeric_profiles if isinstance(profile.get('level'), int)]
    damage_floor_values = [int(profile['damage_min']) for profile in numeric_profiles if isinstance(profile.get('damage_min'), int)]
    damage_ceiling_values = [int(profile['damage_max']) for profile in numeric_profiles if isinstance(profile.get('damage_max'), int)]
    damage_values = damage_floor_values + damage_ceiling_values

    hp_min, hp_max = _min_max(hp_values)
    level_min, level_max = _min_max(level_values)
    damage_min, damage_max = _min_max(damage_values)

    return {
        'route_id': base_report.get('route_id'),
        'threat_band': base_report.get('threat_band'),
        'content_tier_min': base_report.get('content_tier_min'),
        'content_tier_max': base_report.get('content_tier_max'),
        'is_sparse_or_stub': base_report.get('is_sparse_or_stub', False),
        'numeric_tuning_ready': str(base_report.get('route_id') or '').strip() in numeric_ready_routes,
        'mob_ids': tuple(mob_ids),
        'solo_mob_ids': tuple(base_report.get('solo_mob_ids', ())),
        'pack_mob_ids': tuple(base_report.get('pack_mob_ids', ())),
        'elite_anchor_mob_ids': tuple(base_report.get('elite_anchor_mob_ids', ())),
        'rare_anchor_mob_ids': tuple(base_report.get('rare_anchor_mob_ids', ())),
        'pack_mob_count': int(base_report.get('pack_count', 0)),
        'elite_anchor_count': int(base_report.get('elite_anchor_count', 0)),
        'solo_count': int(base_report.get('solo_count', 0)),
        'pack_eligibility_coverage_complete': bool(base_report.get('pack_eligibility_coverage_complete')),
        'pack_archetype_coverage_complete': bool(base_report.get('pack_archetype_coverage_complete')),
        'reward_category': base_report.get('reward_category'),
        'reward_profile_id': base_report.get('reward_profile_id'),
        'hp_min': hp_min,
        'hp_max': hp_max,
        'damage_min': damage_min,
        'damage_max': damage_max,
        'level_min': level_min,
        'level_max': level_max,
        'warnings': tuple(sorted(set(base_report.get('readiness_warnings', ())))),
        'actionable_warnings': tuple(actionable_warnings),
    }


def build_all_open_world_pve_numeric_tuning_reports() -> tuple[dict[str, object], ...]:
    reports: list[dict[str, object]] = []
    for composition in get_open_world_route_encounter_compositions():
        route_id = str(composition.get('route_id') or '').strip()
        if route_id:
            reports.append(build_route_pve_numeric_tuning_report(route_id))
    return tuple(reports)


def validate_open_world_pve_numeric_tuning_baseline() -> list[str]:
    errors: list[str] = []
    for report in build_all_open_world_pve_numeric_tuning_reports():
        route_id = str(report.get('route_id') or '').strip()
        if not route_id:
            errors.append('missing route_id in pve numeric tuning report')
            continue

        is_ready = bool(report.get('numeric_tuning_ready'))
        is_stub = bool(report.get('is_sparse_or_stub'))

        hp_min, hp_max = report.get('hp_min'), report.get('hp_max')
        level_min, level_max = report.get('level_min'), report.get('level_max')
        damage_min, damage_max = report.get('damage_min'), report.get('damage_max')

        if hp_min is not None and hp_max is not None and hp_min > hp_max:
            errors.append(f'invalid hp bounds on route {route_id}: {hp_min}>{hp_max}')
        if level_min is not None and level_max is not None and level_min > level_max:
            errors.append(f'invalid level bounds on route {route_id}: {level_min}>{level_max}')
        if damage_min is not None and damage_max is not None and damage_min > damage_max:
            errors.append(f'invalid damage bounds on route {route_id}: {damage_min}>{damage_max}')

        mob_ids = tuple(report.get('mob_ids', ()))
        elite_ids = set(report.get('elite_anchor_mob_ids', ()))
        solo_ids = set(report.get('solo_mob_ids', ()))
        for mob_id in mob_ids:
            profile = build_open_world_pve_numeric_profile(str(mob_id))
            if is_ready and not profile:
                errors.append(f'missing numeric profile for ready route mob {route_id}:{mob_id}')
                continue

            mob_damage_min = profile.get('damage_min')
            mob_damage_max = profile.get('damage_max')
            if isinstance(mob_damage_min, int) and isinstance(mob_damage_max, int):
                if mob_damage_min > mob_damage_max:
                    errors.append(
                        f'invalid damage range for mob {mob_id} on route {route_id}: {mob_damage_min}>{mob_damage_max}'
                    )

            for key in ('hp', 'level', 'damage_min', 'damage_max'):
                value = profile.get(key)
                if value is not None and isinstance(value, int) and value <= 0:
                    errors.append(f'non-positive {key} for mob {mob_id} on route {route_id}: {value}')

        if is_ready:
            if report.get('solo_count', 0) <= 0:
                errors.append(f'numeric-ready route has no solo mobs: {route_id}')
            if report.get('pack_mob_count', 0) <= 0:
                errors.append(f'numeric-ready route has no pack mobs: {route_id}')
            if report.get('elite_anchor_count', 0) <= 0:
                errors.append(f'numeric-ready route has no elite anchors: {route_id}')

            elite_levels = [
                int(build_open_world_pve_numeric_profile(mob_id).get('level'))
                for mob_id in elite_ids
                if isinstance(build_open_world_pve_numeric_profile(mob_id).get('level'), int)
            ]
            solo_levels = [
                int(build_open_world_pve_numeric_profile(mob_id).get('level'))
                for mob_id in solo_ids
                if isinstance(build_open_world_pve_numeric_profile(mob_id).get('level'), int)
            ]
            if elite_levels and solo_levels and max(elite_levels) < min(solo_levels):
                errors.append(f'elite anchor levels are unexpectedly below solo floor on route {route_id}')

        if is_stub and not report.get('mob_ids'):
            errors.append(f'stub route has empty mob list and should still report mobs: {route_id}')

    return errors
