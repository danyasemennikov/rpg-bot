from __future__ import annotations

from game.locations import WORLD_LOCATIONS, WORLD_ROUTES, resolve_location_id
from game.mobs import MOBS
from game.open_world_pack_balance import collect_open_world_route_mob_ids, get_world_location_ids_by_route_id
from game.open_world_readiness_gap_report import build_open_world_readiness_gap_report
from game.open_world_route_balance_report import build_open_world_route_balance_report
from game.quest_board import HuntContract, list_hunt_contracts_for_location


ROUTE_REPRESENTATIVE_CONTRACT_LOCATIONS: dict[str, tuple[str, ...]] = {
    'route_westwild': ('hub_westwild', 'village'),
    'route_frostspine': ('frostspine_n5',),
    'route_ashen_ruins': ('ashen_n3a2',),
    'route_mireveil': ('mireveil_n5a1',),
    'route_sunscar': ('hub_sunscar',),
    'route_south_coast_stub': ('south_coast_shore',),
    'route_old_mine_stub': ('old_mine_entrance', 'old_mines'),
}


def _tuple(values: object) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip() for v in (values or ()) if str(v).strip()}))


def build_route_objective_profile(route_id: str) -> dict:
    report = build_open_world_route_balance_report(route_id)
    if not report:
        return {}

    normalized_route_id = str(report.get('route_id') or '').strip()
    route_meta = WORLD_ROUTES.get(normalized_route_id, {})
    readiness = build_open_world_readiness_gap_report()
    numeric_ready = normalized_route_id in set(readiness.get('numeric_tuning_ready_routes', ()))

    solo_mob_ids = _tuple(report.get('solo_mob_ids'))
    pack_mob_ids = _tuple(report.get('pack_mob_ids'))
    elite_anchor_mob_ids = _tuple(report.get('elite_anchor_mob_ids'))

    supported_contract_types = {'hunt'}
    if numeric_ready and pack_mob_ids:
        supported_contract_types.add('pack_pressure')
    if elite_anchor_mob_ids:
        supported_contract_types.add('elite_hunt')

    hunt_target_mob_ids = solo_mob_ids + pack_mob_ids
    elite_objective_mob_ids = elite_anchor_mob_ids

    return {
        'route_id': normalized_route_id,
        'numeric_tuning_ready': bool(numeric_ready),
        'is_sparse_or_stub': bool(report.get('is_sparse_or_stub')),
        'route_type': str(route_meta.get('route_type') or ''),
        'route_tags': _tuple(report.get('encounter_mix_tags') or ()),
        'solo_mob_ids': solo_mob_ids,
        'pack_mob_ids': pack_mob_ids,
        'elite_anchor_mob_ids': elite_anchor_mob_ids,
        'supported_contract_types': tuple(sorted(supported_contract_types)),
        'hunt_target_mob_ids': _tuple(hunt_target_mob_ids),
        'elite_objective_mob_ids': elite_objective_mob_ids,
        'progression_reward_signal': str(report.get('reward_profile_id') or ''),
        'objective_warnings': _tuple(report.get('readiness_warnings')),
    }


def build_all_route_objective_profiles() -> tuple[dict, ...]:
    profiles = []
    for route_id in WORLD_ROUTES:
        if route_id == 'core':
            continue
        profile = build_route_objective_profile(route_id)
        if profile:
            profiles.append(profile)
    return tuple(profiles)


def get_route_representative_contract_locations(route_id: str) -> tuple[str, ...]:
    return ROUTE_REPRESENTATIVE_CONTRACT_LOCATIONS.get(str(route_id or '').strip(), ())


def list_route_hunt_contracts(route_id: str) -> tuple[HuntContract, ...]:
    seen: dict[str, HuntContract] = {}
    route_local_mobs = collect_open_world_route_mob_ids(route_id)
    for location_id in get_route_representative_contract_locations(route_id):
        for contract in list_hunt_contracts_for_location(location_id):
            if contract.target_mob_id not in route_local_mobs:
                continue
            seen[contract.contract_key] = contract
    return tuple(seen[k] for k in sorted(seen))


def collect_route_contract_target_mob_ids(route_id: str) -> tuple[str, ...]:
    return tuple(sorted({contract.target_mob_id for contract in list_route_hunt_contracts(route_id)}))


def collect_route_spawnable_mob_locations(route_id: str, mob_id: str) -> tuple[str, ...]:
    normalized_route = str(route_id or '').strip()
    normalized_mob = str(mob_id or '').strip()
    if not normalized_route or not normalized_mob:
        return ()
    locations: list[str] = []
    for location_id in get_world_location_ids_by_route_id(normalized_route):
        location = WORLD_LOCATIONS.get(location_id, {})
        mobs = set(location.get('mobs') or ())
        spawn_profiles = set((location.get('world_spawn_profiles') or {}).keys())
        if normalized_mob in mobs or normalized_mob in spawn_profiles:
            locations.append(location_id)
    return tuple(sorted(set(locations)))


def validate_open_world_route_objectives() -> list[str]:
    errors: list[str] = []
    for profile in build_all_route_objective_profiles():
        route_id = str(profile.get('route_id') or '')
        route_local_mobs = collect_open_world_route_mob_ids(route_id)
        for key in ('hunt_target_mob_ids', 'elite_objective_mob_ids', 'pack_mob_ids'):
            for mob_id in profile.get(key, ()) or ():
                if mob_id not in MOBS:
                    errors.append(f'unknown objective mob for route {route_id}: {mob_id}')
                if mob_id not in route_local_mobs:
                    errors.append(f'non-route-local objective mob for route {route_id}: {mob_id}')

        if profile.get('numeric_tuning_ready') and not profile.get('is_sparse_or_stub'):
            if not profile.get('hunt_target_mob_ids'):
                errors.append(f'numeric-ready route has no hunt targets: {route_id}')
            if 'hunt' not in set(profile.get('supported_contract_types') or ()):
                errors.append(f'numeric-ready route missing hunt contract type: {route_id}')
            contracts = list_route_hunt_contracts(route_id)
            if not contracts:
                errors.append(f'numeric-ready route has no quest-board-visible hunt contracts: {route_id}')
            for contract in contracts:
                if contract.target_mob_id not in MOBS:
                    errors.append(f'route contract target mob missing in MOBS: {route_id}:{contract.contract_key}')
                if contract.target_mob_id not in route_local_mobs:
                    errors.append(f'route contract target mob is non-local: {route_id}:{contract.contract_key}')
                if int(contract.reward_exp) <= 0 or int(contract.reward_gold) <= 0:
                    errors.append(f'route contract has non-positive rewards: {route_id}:{contract.contract_key}')
                if not contract.target_location_ids:
                    errors.append(f'route contract has empty target locations: {route_id}:{contract.contract_key}')
                    continue
                spawnable_locations = set(collect_route_spawnable_mob_locations(route_id, contract.target_mob_id))
                valid_spawnable_count = 0
                for target_location_id in contract.target_location_ids:
                    normalized_target_location_id = resolve_location_id(target_location_id)
                    if normalized_target_location_id not in set(get_world_location_ids_by_route_id(route_id)):
                        errors.append(
                            f'route contract target location is not route-local: {route_id}:{contract.contract_key}:{target_location_id}'
                        )
                    if normalized_target_location_id not in spawnable_locations:
                        errors.append(
                            f'route contract target location does not spawn target mob: {route_id}:{contract.contract_key}:{target_location_id}:{contract.target_mob_id}'
                        )
                    else:
                        valid_spawnable_count += 1
                if valid_spawnable_count <= 0:
                    errors.append(f'route contract has no spawnable target locations: {route_id}:{contract.contract_key}')

        if route_id == 'route_sunscar':
            if not profile.get('numeric_tuning_ready'):
                errors.append('route_sunscar must be numeric-ready via route-specific pressure profile')
            if 'pack_pressure' in set(profile.get('supported_contract_types') or ()):
                errors.append('route_sunscar must not expose pack-ready objective signal')

    return errors
