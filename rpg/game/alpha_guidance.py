from __future__ import annotations

from game.locations import WORLD_LOCATIONS
from game.i18n import t
from game.open_world_readiness_gap_report import build_open_world_readiness_gap_report
from game.open_world_route_objectives import build_route_objective_profile, list_route_hunt_contracts
from game.quest_board import list_hunt_contracts_for_location


def build_alpha_next_steps(player_state: dict, lang: str = 'en') -> tuple[str, ...]:
    if not isinstance(player_state, dict):
        player_state = {}
    steps: list[str] = []
    if player_state.get('in_battle'):
        steps.append(t('start.alpha_step_finish_battle', lang))
    else:
        steps.extend([
            t('start.alpha_step_check_location', lang),
            t('start.alpha_step_open_map', lang),
            t('start.alpha_step_take_contract', lang),
            t('start.alpha_step_fight_claim', lang),
        ])
    steps.extend([
        t('start.alpha_step_inventory_equipment', lang),
        t('start.alpha_step_enhance', lang),
        t('start.alpha_step_unstuck', lang),
    ])
    return tuple(steps)


def build_location_objective_hint(location_id: str) -> dict:
    normalized = str(location_id or '').strip()
    location = WORLD_LOCATIONS.get(normalized, {})
    route_id = str(location.get('route_id') or '').strip()
    contracts = list_hunt_contracts_for_location(normalized)
    return {
        'location_id': normalized,
        'route_id': route_id,
        'has_contracts': bool(contracts),
        'contract_count': len(contracts),
        'contract_keys': tuple(c.contract_key for c in contracts),
        'target_mob_ids': tuple(sorted({c.target_mob_id for c in contracts})),
    }


def build_alpha_route_status_hint(location_id: str) -> dict:
    normalized = str(location_id or '').strip()
    location = WORLD_LOCATIONS.get(normalized, {})
    route_id = str(location.get('route_id') or '').strip()
    profile = build_route_objective_profile(route_id) if route_id else {}
    readiness = build_open_world_readiness_gap_report()
    is_numeric_ready = route_id in set(readiness.get('numeric_tuning_ready_routes', ()))
    route_contracts = list_route_hunt_contracts(route_id) if route_id else ()
    return {
        'location_id': normalized,
        'route_id': route_id,
        'numeric_ready': bool(is_numeric_ready),
        'is_sparse_or_stub': bool(profile.get('is_sparse_or_stub')),
        'supported_contract_types': tuple(profile.get('supported_contract_types') or ()),
        'objective_warnings': tuple(profile.get('objective_warnings') or ()),
        'route_contract_count': len(route_contracts),
    }


def validate_alpha_guidance_surface() -> list[str]:
    errors: list[str] = []
    for lang in ('en', 'ru', 'es'):
        sample = build_alpha_next_steps({'in_battle': False}, lang=lang)
        if not isinstance(sample, tuple) or not sample:
            errors.append(f'alpha guidance next steps must be a non-empty tuple for {lang}')
    for location_id in ('hub_westwild', 'frostspine_n5', 'ashen_n3a2', 'mireveil_n5a1', 'hub_sunscar'):
        hint = build_location_objective_hint(location_id)
        if not isinstance(hint.get('has_contracts'), bool):
            errors.append(f'invalid objective hint bool flag: {location_id}')
        route_hint = build_alpha_route_status_hint(location_id)
        if 'numeric_ready' not in route_hint:
            errors.append(f'missing numeric_ready route hint key: {location_id}')
    return errors
