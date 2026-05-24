from __future__ import annotations

from game.open_world_route_balance_report import build_all_open_world_route_balance_reports

ACTIONABLE_WARNING_IDS: frozenset[str] = frozenset({
    'no_pack_mobs_on_non_stub_route',
    'no_elite_anchors_on_non_stub_route',
    'pack_mobs_missing_archetype_metadata',
    'mid_high_or_high_without_elite_anchor',
    'no_world_spawn_profiles',
    'missing_alpha_pressure_profile',
})

DEFERRED_WARNING_IDS: frozenset[str] = frozenset({
    'no_rare_anchors',
    'very_low_location_count',
})

def classify_readiness_warning_id(warning_id: str) -> str:
    normalized_warning_id = str(warning_id or '').strip()
    if normalized_warning_id in DEFERRED_WARNING_IDS:
        return 'deferred'
    if normalized_warning_id in ACTIONABLE_WARNING_IDS:
        return 'actionable'
    return 'actionable'


def collect_open_world_route_readiness_gaps() -> tuple[dict[str, object], ...]:
    gaps: list[dict[str, object]] = []
    for report in build_all_open_world_route_balance_reports():
        route_id = str(report.get('route_id') or '').strip()
        for warning in report.get('readiness_warnings', ()):
            warning_id = str(warning or '').strip()
            if not warning_id:
                continue
            classification = classify_readiness_warning_id(warning_id)
            gaps.append({'route_id': route_id, 'warning_id': warning_id, 'classification': classification})
    return tuple(gaps)


def build_open_world_readiness_gap_report() -> dict[str, object]:
    reports = build_all_open_world_route_balance_reports()
    major_routes = sorted(str(r['route_id']) for r in reports if not bool(r.get('is_sparse_or_stub')))
    sparse_stub_routes = sorted(str(r['route_id']) for r in reports if bool(r.get('is_sparse_or_stub')))

    remaining_warnings_by_route: dict[str, tuple[str, ...]] = {
        str(r['route_id']): tuple(sorted(str(w) for w in r.get('readiness_warnings', ()) if str(w).strip()))
        for r in reports
    }
    routes_with_warnings = sorted(route_id for route_id, warnings in remaining_warnings_by_route.items() if warnings)

    actionable_gaps: list[dict[str, str]] = []
    deferred_gaps: list[dict[str, str]] = []
    for gap in collect_open_world_route_readiness_gaps():
        target = actionable_gaps if gap['classification'] == 'actionable' else deferred_gaps
        target.append({'route_id': str(gap['route_id']), 'warning_id': str(gap['warning_id'])})

    actionable_route_ids = {g['route_id'] for g in actionable_gaps}
    numeric_tuning_ready_routes = sorted(route_id for route_id in major_routes if route_id not in actionable_route_ids)

    return {
        'routes_total': len(reports),
        'major_routes': tuple(major_routes),
        'sparse_stub_routes': tuple(sparse_stub_routes),
        'routes_with_warnings': tuple(routes_with_warnings),
        'remaining_warnings_by_route': remaining_warnings_by_route,
        'actionable_gaps': tuple(actionable_gaps),
        'deferred_gaps': tuple(deferred_gaps),
        'numeric_tuning_ready_routes': tuple(numeric_tuning_ready_routes),
    }


def validate_open_world_readiness_gap_report() -> list[str]:
    errors: list[str] = []
    report = build_open_world_readiness_gap_report()
    required_keys = {
        'routes_total', 'major_routes', 'sparse_stub_routes', 'routes_with_warnings',
        'remaining_warnings_by_route', 'actionable_gaps', 'deferred_gaps', 'numeric_tuning_ready_routes',
    }
    missing = required_keys - set(report.keys())
    if missing:
        errors.append(f'missing readiness gap report keys: {sorted(missing)}')

    for key in ('actionable_gaps', 'deferred_gaps'):
        for gap in report.get(key, ()):  # type: ignore[arg-type]
            if not str(gap.get('route_id') or '').strip() or not str(gap.get('warning_id') or '').strip():
                errors.append(f'invalid {key} entry: {gap}')

    remaining_warnings_by_route = report.get('remaining_warnings_by_route')
    if not isinstance(remaining_warnings_by_route, dict):
        errors.append('remaining_warnings_by_route must be a dict')
    else:
        known_warning_ids = set(ACTIONABLE_WARNING_IDS) | set(DEFERRED_WARNING_IDS)
        for route_id, warning_ids in remaining_warnings_by_route.items():
            normalized_route_id = str(route_id or '').strip()
            for warning_id in warning_ids or ():
                normalized_warning_id = str(warning_id or '').strip()
                if normalized_warning_id and normalized_warning_id not in known_warning_ids:
                    errors.append(
                        f'unknown readiness warning id for route {normalized_route_id}: {normalized_warning_id}'
                    )

    return errors
