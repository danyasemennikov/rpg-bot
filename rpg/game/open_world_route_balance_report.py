from __future__ import annotations

from game.locations import (
    WORLD_LOCATIONS,
    WORLD_ROUTES,
    get_route_alpha_pressure_profile,
    get_route_alpha_depth_stage,
    get_route_gameplay_identity_profile,
    get_route_matchup_target_profile,
)
from game.open_world_pack_balance import (
    ALLOWED_OPEN_WORLD_THREAT_BANDS,
    get_open_world_pack_archetype_metadata,
    get_open_world_route_composition_by_route_id,
    get_open_world_route_encounter_compositions,
    get_world_location_ids_by_route_id,
    is_open_world_pack_enabled_mob,
)
from game.open_world_reward_alignment import get_open_world_reward_profile_for_threat_band

def _resolve_pressure_stage_for_location(location_id: str) -> str:
    normalized = str(location_id or '').strip().lower()
    if normalized.startswith('ashen_'):
        if normalized in {'ashen_n1', 'ashen_n2'}:
            return 'soft_entry'
        if normalized in {'ashen_n3', 'ashen_n3a1', 'ashen_n3a2', 'ashen_n3c1'}:
            return 'identity_visible'
        if normalized in {'ashen_n3b1', 'ashen_n3b2', 'ashen_n3b2b1'}:
            return 'build_testing'
        if normalized in {'ashen_n3b2a1', 'ashen_n3c2'}:
            return 'route_exam'
    stage = get_route_alpha_depth_stage(location_id)
    if stage:
        return stage
    location = WORLD_LOCATIONS.get(location_id, {})
    level_cap = int(location.get('level_max', 0) or 0)
    if level_cap <= 3:
        return 'soft_entry'
    if level_cap <= 6:
        return 'identity_visible'
    if level_cap <= 8:
        return 'build_testing'
    return 'route_exam'


def _collect_route_spawn_profiles(route_id: str) -> tuple[str, ...]:
    profiles: set[str] = set()
    for location_id in get_world_location_ids_by_route_id(route_id):
        location = WORLD_LOCATIONS.get(location_id, {})
        for profile_map in (location.get('world_spawn_profiles') or {}).values():
            for profile in (profile_map or {}).keys():
                normalized = str(profile or '').strip().lower()
                if normalized:
                    profiles.add(normalized)
    return tuple(sorted(profiles))


def _collect_route_mob_pressure_tags(route_id: str) -> tuple[str, ...]:
    tags: set[str] = set()
    for location_id in get_world_location_ids_by_route_id(route_id):
        location = WORLD_LOCATIONS.get(location_id, {})
        for mob_id in location.get('mobs', ()):
            from game.mobs import MOBS
            for tag in (MOBS.get(str(mob_id), {}).get('combat_pressure_tags') or ()):
                normalized = str(tag or '').strip().lower()
                if normalized:
                    tags.add(normalized)
    return tuple(sorted(tags))


def _build_depth_pressure_summary(route_id: str) -> dict[str, tuple[str, ...]]:
    summary: dict[str, set[str]] = {}
    from game.mobs import MOBS
    for location_id in get_world_location_ids_by_route_id(route_id):
        stage = _resolve_pressure_stage_for_location(location_id)
        if not stage:
            continue
        stage_tags = summary.setdefault(stage, set())
        for mob_id in (WORLD_LOCATIONS.get(location_id, {}).get('mobs') or ()):
            for tag in (MOBS.get(str(mob_id), {}).get('combat_pressure_tags') or ()):
                normalized = str(tag or '').strip().lower()
                if normalized:
                    stage_tags.add(normalized)
    return {k: tuple(sorted(v)) for k, v in summary.items()}


def _build_depth_pressure_density(route_id: str) -> dict[str, int]:
    density = {'soft_entry': 0, 'identity_visible': 0, 'build_testing': 0, 'route_exam': 0}
    from game.mobs import MOBS
    weighted_tags = {'ambush', 'moderate_pack', 'heavy_trade', 'route_exam', 'attrition_exam', 'elite_skirmisher', 'mitigation_check', 'goblin_pressure', 'caster', 'construct', 'toxin', 'control_pressure', 'precision', 'elemental'}
    for location_id in get_world_location_ids_by_route_id(route_id):
        stage = _resolve_pressure_stage_for_location(location_id)
        if stage not in density:
            continue
        location = WORLD_LOCATIONS.get(location_id, {})
        mobs = tuple(location.get('mobs') or ())
        profiles = dict(location.get('world_spawn_profiles') or {})
        for mob_id in mobs:
            profile_counts = dict(profiles.get(mob_id) or {})
            normal_count = int(profile_counts.get('normal', 0) or 0)
            elite_count = int(profile_counts.get('elite', 0) or 0)
            spawn_weight = normal_count + elite_count
            if spawn_weight <= 0:
                spawn_weight = 1
            tags = {str(t or '').strip().lower() for t in (MOBS.get(str(mob_id), {}).get('combat_pressure_tags') or ())}
            if tags:
                density[stage] += max(1, len(tags & weighted_tags)) * max(1, spawn_weight)
    return density


def _is_sparse_or_stub_route(route_id: str, composition: dict[str, object], *, location_count: int) -> bool:
    normalized_route_id = str(route_id or '').strip().lower()
    encounter_tags = {str(tag or '').strip().lower() for tag in (composition.get('encounter_mix_tags') or ())}
    total_mob_count = sum(
        len(tuple(composition.get(key, ()) or ()))
        for key in ('solo_mob_ids', 'pack_mob_ids', 'elite_anchor_mob_ids', 'rare_anchor_mob_ids')
    )

    return (
        normalized_route_id.endswith('_stub')
        or '_stub' in normalized_route_id
        or 'sparse_content' in encounter_tags
        or location_count <= 1
        or total_mob_count <= 3
    )


def _build_readiness_warnings(report: dict[str, object]) -> tuple[str, ...]:
    warnings: list[str] = []
    is_sparse = bool(report.get('is_sparse_or_stub'))
    threat_band = str(report.get('threat_band') or '').strip().lower()

    if report.get('location_count', 0) <= 1:
        warnings.append('very_low_location_count')
    if not report.get('spawn_profiles_present'):
        warnings.append('no_world_spawn_profiles')
    requires_pack_pressure = bool(report.get('requires_pack_pressure'))

    if report.get('pack_count', 0) == 0 and not is_sparse and requires_pack_pressure:
        warnings.append('no_pack_mobs_on_non_stub_route')
    if not report.get('pressure_profile_id') and not is_sparse:
        warnings.append('missing_alpha_pressure_profile')
    if not report.get('gameplay_identity_id') and not is_sparse:
        warnings.append('missing_route_gameplay_identity_profile')
    if not report.get('matchup_target_profile_id') and not is_sparse:
        warnings.append('missing_route_matchup_target_profile')
    if not report.get('identity_tag_representation_ok', False) and not is_sparse:
        warnings.append('route_identity_tags_not_represented_by_mobs')
    if report.get('elite_anchor_count', 0) == 0 and not is_sparse:
        warnings.append('no_elite_anchors_on_non_stub_route')
    if report.get('rare_anchor_count', 0) == 0 and not is_sparse:
        warnings.append('no_rare_anchors')
    if threat_band in {'mid_high', 'high'} and report.get('elite_anchor_count', 0) == 0 and not is_sparse:
        warnings.append('mid_high_or_high_without_elite_anchor')
    if report.get('pack_count', 0) > 0 and not report.get('pack_archetype_coverage_complete', False):
        warnings.append('pack_mobs_missing_archetype_metadata')

    return tuple(sorted(set(warnings)))


def build_open_world_route_balance_report(route_id: str) -> dict[str, object]:
    composition = get_open_world_route_composition_by_route_id(route_id)
    if not composition:
        return {}

    normalized_route_id = str(composition.get('route_id') or '').strip()
    location_ids = get_world_location_ids_by_route_id(normalized_route_id)

    solo_mob_ids = tuple(str(m) for m in (composition.get('solo_mob_ids') or ()) if str(m).strip())
    pack_mob_ids = tuple(str(m) for m in (composition.get('pack_mob_ids') or ()) if str(m).strip())
    elite_anchor_mob_ids = tuple(str(m) for m in (composition.get('elite_anchor_mob_ids') or ()) if str(m).strip())
    rare_anchor_mob_ids = tuple(str(m) for m in (composition.get('rare_anchor_mob_ids') or ()) if str(m).strip())

    location_count = len(location_ids)
    is_sparse_or_stub = _is_sparse_or_stub_route(normalized_route_id, composition, location_count=location_count)
    threat_profile = get_open_world_reward_profile_for_threat_band(composition.get('threat_band'))

    report: dict[str, object] = {
        'route_id': normalized_route_id,
        'threat_band': str(composition.get('threat_band') or '').strip(),
        'content_tier_min': int(composition.get('content_tier_min', 0)),
        'content_tier_max': int(composition.get('content_tier_max', 0)),
        'location_ids': location_ids,
        'location_count': location_count,
        'solo_mob_ids': solo_mob_ids,
        'pack_mob_ids': pack_mob_ids,
        'elite_anchor_mob_ids': elite_anchor_mob_ids,
        'rare_anchor_mob_ids': rare_anchor_mob_ids,
        'solo_count': len(solo_mob_ids),
        'pack_count': len(pack_mob_ids),
        'elite_anchor_count': len(elite_anchor_mob_ids),
        'rare_anchor_count': len(rare_anchor_mob_ids),
        'spawn_profiles_present': _collect_route_spawn_profiles(normalized_route_id),
        'reward_category': str(threat_profile.get('reward_category') or '').strip(),
        'reward_profile_id': str(threat_profile.get('reward_profile_id') or '').strip(),
        'encounter_mix_tags': tuple(sorted(str(tag) for tag in (composition.get('encounter_mix_tags') or ()) if str(tag).strip())),
        'pack_eligibility_coverage_complete': all(is_open_world_pack_enabled_mob(mob_id) for mob_id in pack_mob_ids),
        'pack_archetype_coverage_complete': all(bool(get_open_world_pack_archetype_metadata(mob_id)) for mob_id in pack_mob_ids),
        'is_sparse_or_stub': is_sparse_or_stub,
        'pressure_profile_id': '',
        'pressure_entry_band': '',
        'pressure_identity_band': '',
        'pressure_build_test_band': '',
        'pressure_exam_band': '',
        'requires_pack_pressure': False,
        'gameplay_identity_id': '',
        'route_pressure_tags': (),
        'represented_mob_pressure_tags': (),
        'depth_pressure_summary': {},
        'depth_pressure_density': {},
        'soft_entry_safety_ok': True,
        'identity_pressure_present': False,
        'build_test_pressure_present': False,
        'route_exam_pressure_present': False,
        'overpressure_warnings': (),
        'identity_tag_representation_ok': True,
        'matchup_target_profile_id': '',
        'matchup_target_labels': (),
        'readiness_warnings': (),
    }
    route_meta = WORLD_ROUTES.get(normalized_route_id, {})
    if str(route_meta.get('route_type') or '') == 'full':
        pressure_profile = get_route_alpha_pressure_profile(normalized_route_id)
        report['pressure_profile_id'] = str(pressure_profile.get('pressure_profile_id') or '')
        report['pressure_entry_band'] = str(pressure_profile.get('entry_band') or '')
        report['pressure_identity_band'] = str(pressure_profile.get('identity_band') or '')
        report['pressure_build_test_band'] = str(pressure_profile.get('build_test_band') or '')
        report['pressure_exam_band'] = str(pressure_profile.get('exam_band') or '')
        report['requires_pack_pressure'] = bool(pressure_profile.get('requires_pack_pressure'))

        identity_profile = get_route_gameplay_identity_profile(normalized_route_id)
        report['gameplay_identity_id'] = str(identity_profile.get('gameplay_identity_id') or '')
        matchup_profile = get_route_matchup_target_profile(normalized_route_id)
        report['matchup_target_profile_id'] = str(matchup_profile.get('matchup_profile_id') or '')
        report['matchup_target_labels'] = tuple(sorted(str(v) for v in (matchup_profile.get('target_matchups') or {}).values()))
        report['route_pressure_tags'] = tuple(sorted(str(t) for t in (identity_profile.get('primary_pressure_tags') or ()) if str(t).strip()))
        represented_tags = _collect_route_mob_pressure_tags(normalized_route_id)
        report['represented_mob_pressure_tags'] = represented_tags
        report['depth_pressure_summary'] = _build_depth_pressure_summary(normalized_route_id)
        report['depth_pressure_density'] = _build_depth_pressure_density(normalized_route_id)
        represented_set = {str(t).strip().lower() for t in represented_tags}
        expected_set = {str(t).strip().lower() for t in report['route_pressure_tags']}
        has_primary_overlap = bool(represented_set & expected_set)
        expected_depth = identity_profile.get('depth_pressure_tags') or {}
        depth_summary = report['depth_pressure_summary']
        has_depth_overlap = True
        for stage in ('identity_visible', 'build_testing', 'route_exam'):
            stage_expected = {str(t).strip().lower() for t in (expected_depth.get(stage) or ()) if str(t).strip()}
            if not stage_expected or stage not in depth_summary:
                continue
            stage_actual = {str(t).strip().lower() for t in (depth_summary.get(stage) or ()) if str(t).strip()}
            if not (stage_expected & stage_actual):
                has_depth_overlap = False
                break

        soft_entry_tags = {str(t).strip().lower() for t in (depth_summary.get('soft_entry') or ()) if str(t).strip()}
        banned_soft_entry_tags = {'elite_bruiser', 'elite_skirmisher', 'attrition_exam', 'heavy_trade', 'route_exam'}
        soft_entry_ok = (
            bool(soft_entry_tags)
            and 'soft_entry' in soft_entry_tags
            and 'route_exam' not in soft_entry_tags
            and not (soft_entry_tags & banned_soft_entry_tags)
        )

        report['identity_tag_representation_ok'] = has_primary_overlap and has_depth_overlap and soft_entry_ok
        density = report['depth_pressure_density']
        report['soft_entry_safety_ok'] = bool(soft_entry_ok and density.get('soft_entry', 0) <= 10)
        report['identity_pressure_present'] = density.get('identity_visible', 0) > 0
        report['build_test_pressure_present'] = density.get('build_testing', 0) > 0
        report['route_exam_pressure_present'] = density.get('route_exam', 0) > 0
        overpressure: list[str] = []
        if density.get('soft_entry', 0) > 12:
            overpressure.append('soft_entry_density_too_high')
        if (
            'route_exam' in depth_summary
            and 'identity_visible' in depth_summary
            and density.get('route_exam', 0) <= density.get('identity_visible', 0)
        ):
            overpressure.append('route_exam_density_not_above_identity')
        report['overpressure_warnings'] = tuple(sorted(overpressure))
    report['readiness_warnings'] = _build_readiness_warnings(report)
    return report


def build_all_open_world_route_balance_reports() -> tuple[dict[str, object], ...]:
    reports: list[dict[str, object]] = []
    for composition in get_open_world_route_encounter_compositions():
        route_id = str(composition.get('route_id') or '').strip()
        if route_id:
            reports.append(build_open_world_route_balance_report(route_id))
    return tuple(reports)


def validate_open_world_route_balance_reports() -> list[str]:
    errors: list[str] = []
    for composition in get_open_world_route_encounter_compositions():
        route_id = str(composition.get('route_id') or '').strip()
        if not route_id:
            errors.append('route composition entry is missing route_id')
            continue

        report = build_open_world_route_balance_report(route_id)
        if not report:
            errors.append(f'missing route composition report for route {route_id}')
            continue

        threat_band = str(report.get('threat_band') or '').strip()
        if threat_band not in ALLOWED_OPEN_WORLD_THREAT_BANDS:
            errors.append(f'invalid threat band for route {route_id}: {threat_band}')
        if not report.get('reward_category') or not report.get('reward_profile_id'):
            errors.append(f'missing reward profile alignment for route {route_id}')
        if int(report.get('location_count', 0)) <= 0 and not bool(report.get('is_sparse_or_stub')):
            errors.append(f'route has no mapped locations and is not sparse/stub: {route_id}')
        if not bool(report.get('is_sparse_or_stub')) and not report.get('matchup_target_profile_id'):
            errors.append(f'missing route matchup target profile for full route {route_id}')
        if not bool(report.get('is_sparse_or_stub')):
            if not report.get('soft_entry_safety_ok', False):
                errors.append(f'soft entry pressure safety failed on route {route_id}')
            if not report.get('identity_pressure_present', False):
                errors.append(f'identity pressure missing on route {route_id}')
            if not report.get('build_test_pressure_present', False):
                errors.append(f'build-test pressure missing on route {route_id}')
            if not report.get('route_exam_pressure_present', False):
                errors.append(f'route-exam pressure missing on route {route_id}')
            overpressure_warnings = tuple(str(v) for v in (report.get('overpressure_warnings') or ()) if str(v).strip())
            if overpressure_warnings:
                errors.append(f'route has pressure overage warnings: {route_id}:{",".join(overpressure_warnings)}')

        for mob_id in report.get('pack_mob_ids', ()):
            if not is_open_world_pack_enabled_mob(str(mob_id)):
                errors.append(f'route pack mob is not pack-enabled: {route_id}:{mob_id}')
            if not get_open_world_pack_archetype_metadata(str(mob_id)):
                errors.append(f'route pack mob has no archetype metadata: {route_id}:{mob_id}')

    return errors
