from __future__ import annotations

from game.alpha_guidance import validate_alpha_guidance_surface
from game.alpha_recovery import validate_alpha_recovery_policy
from game.open_world_pack_balance import validate_open_world_spawn_profile_placement
from game.open_world_progression_loop import validate_open_world_progression_loop_sanity
from game.open_world_pve_tuning import validate_open_world_pve_numeric_tuning_baseline
from game.open_world_readiness_gap_report import build_open_world_readiness_gap_report, validate_open_world_readiness_gap_report
from game.open_world_reward_alignment import validate_open_world_reward_alignment_metadata
from game.open_world_reward_sanity import validate_open_world_reward_loot_sanity
from game.open_world_route_balance_report import validate_open_world_route_balance_reports
from game.open_world_route_objectives import validate_open_world_route_objectives
from game.skills import SKILLS

ALPHA_READY_ROUTES: tuple[str, ...] = (
    'route_westwild',
    'route_frostspine',
    'route_ashen_ruins',
    'route_mireveil',
)
BLOCKED_ROUTES: tuple[str, ...] = ('route_sunscar',)
SPARSE_STUB_ROUTES: tuple[str, ...] = ('route_south_coast_stub', 'route_old_mine_stub')

TARGETING_ROLLOUT_FROZEN_NOTE = 'targeting rollout remains frozen by pr2c11 policy'
SUNSCAR_BLOCKER_NOTE = 'route_sunscar remains blocked by no_pack_mobs_on_non_stub_route'
APPROVED_TARGET_PATTERN_SKILL_IDS: frozenset[str] = frozenset({
    'flame_wave', 'heavy_swing', 'cleave_through', 'arcane_lance',
    'hunters_mark', 'aimed_shot', 'piercing_arrow', 'deadeye',
})


def _collect_validator_status() -> dict[str, list[str]]:
    return {
        'alpha_guidance_surface': validate_alpha_guidance_surface(),
        'alpha_recovery_policy': validate_alpha_recovery_policy(),
        'open_world_route_objectives': validate_open_world_route_objectives(),
        'open_world_progression_loop_sanity': validate_open_world_progression_loop_sanity(),
        'open_world_reward_loot_sanity': validate_open_world_reward_loot_sanity(),
        'open_world_pve_numeric_tuning_baseline': validate_open_world_pve_numeric_tuning_baseline(),
        'open_world_spawn_profile_placement': validate_open_world_spawn_profile_placement(),
        'open_world_reward_alignment_metadata': validate_open_world_reward_alignment_metadata(),
        'open_world_route_balance_reports': validate_open_world_route_balance_reports(),
        'open_world_readiness_gap_report': validate_open_world_readiness_gap_report(),
    }


def build_alpha_release_gate_report() -> dict[str, object]:
    readiness_report = build_open_world_readiness_gap_report()
    validator_status = _collect_validator_status()

    required_systems = (
        'player creation / start flow',
        'canonical capital/default location',
        'location view',
        'travel/canonical route access',
        'quest board contracts',
        'contract accept/progress/claim',
        'reward/loot sanity',
        'inventory/material intake',
        'equipment/effective stats path',
        'enhancement material sanity',
        'recovery/unstuck policy',
        'i18n surface for EN/RU/ES',
        'targeting rollout freeze',
        'Sunscar known blocker remains explicit',
    )

    known_alpha_limits = (
        SUNSCAR_BLOCKER_NOTE,
        'contracts are curated/static',
        'single-active-contract architecture unchanged',
        'no full dynamic quest generation',
        'no mixed-mob packs',
        'no dungeon/world boss/rare boss readiness',
    )

    smoke_path_status = {
        'fresh_player_bootstrap': 'covered_by_alpha_release_gate_pr3p',
        'route_contract_loop': 'covered_by_alpha_release_gate_pr3p',
        'reward_progression_recovery': 'covered_by_alpha_release_gate_pr3p',
    }

    release_warnings: list[str] = []
    for validator_name, validator_errors in validator_status.items():
        if validator_errors:
            release_warnings.append(f'validator_failed:{validator_name}')
    sunscar_warnings = set(readiness_report.get('remaining_warnings_by_route', {}).get('route_sunscar', ()))
    if 'no_pack_mobs_on_non_stub_route' in sunscar_warnings:
        release_warnings.append(SUNSCAR_BLOCKER_NOTE)
    release_warnings.append(TARGETING_ROLLOUT_FROZEN_NOTE)

    return {
        'alpha_ready_routes': ALPHA_READY_ROUTES,
        'blocked_routes': BLOCKED_ROUTES,
        'sparse_stub_routes': SPARSE_STUB_ROUTES,
        'known_alpha_limits': known_alpha_limits,
        'required_systems': required_systems,
        'validator_status': validator_status,
        'smoke_path_status': smoke_path_status,
        'release_warnings': tuple(release_warnings),
    }


def validate_alpha_release_gate() -> list[str]:
    errors: list[str] = []
    report = build_alpha_release_gate_report()

    expected_keys = {
        'alpha_ready_routes',
        'blocked_routes',
        'sparse_stub_routes',
        'known_alpha_limits',
        'required_systems',
        'validator_status',
        'smoke_path_status',
        'release_warnings',
    }
    missing = expected_keys - set(report.keys())
    if missing:
        errors.append(f'missing alpha release gate keys: {sorted(missing)}')

    if tuple(report.get('alpha_ready_routes') or ()) != ALPHA_READY_ROUTES:
        errors.append('alpha ready routes drifted from pr3p baseline')
    if tuple(report.get('blocked_routes') or ()) != BLOCKED_ROUTES:
        errors.append('blocked routes drifted from pr3p baseline')
    if tuple(report.get('sparse_stub_routes') or ()) != SPARSE_STUB_ROUTES:
        errors.append('sparse stub routes drifted from pr3p baseline')

    validator_status = report.get('validator_status', {})
    if not isinstance(validator_status, dict):
        errors.append('validator_status must be a dict')
    else:
        for validator_name, validator_errors in validator_status.items():
            if validator_errors:
                errors.append(f'validator {validator_name} failed: {validator_errors}')

    warnings = set(report.get('release_warnings', ()))
    if SUNSCAR_BLOCKER_NOTE not in warnings:
        errors.append('sunscar alpha blocker warning missing from release warnings')
    if TARGETING_ROLLOUT_FROZEN_NOTE not in warnings:
        errors.append('targeting rollout freeze warning missing from release warnings')

    rolled_out = {
        skill_id
        for skill_id, skill in SKILLS.items()
        if str(skill.get('target_pattern_id') or '').strip()
    }
    if rolled_out != APPROVED_TARGET_PATTERN_SKILL_IDS:
        errors.append(
            'targeting rollout drifted from pr2c11/pr3p freeze: '
            f'expected={sorted(APPROVED_TARGET_PATTERN_SKILL_IDS)}, actual={sorted(rolled_out)}'
        )

    return errors
