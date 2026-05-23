from pathlib import Path

from game.alpha_guidance import build_alpha_next_steps, build_alpha_route_status_hint, build_location_objective_hint, validate_alpha_guidance_surface
from game.alpha_recovery import build_recovery_decision, validate_alpha_recovery_policy
from game.mobs import MOBS
from game.open_world_pack_balance import validate_open_world_spawn_profile_placement
from game.open_world_progression_loop import validate_open_world_progression_loop_sanity
from game.open_world_pve_tuning import validate_open_world_pve_numeric_tuning_baseline
from game.open_world_readiness_gap_report import build_open_world_readiness_gap_report, validate_open_world_readiness_gap_report
from game.open_world_reward_alignment import validate_open_world_reward_alignment_metadata
from game.open_world_reward_sanity import validate_open_world_reward_loot_sanity
from game.open_world_route_balance_report import validate_open_world_route_balance_reports
from game.open_world_route_objectives import validate_open_world_route_objectives
from game.quest_board import get_hunt_contract, list_hunt_contracts_for_location
from game.skills import SKILLS


def test_alpha_guidance_helpers_shape_and_stability():
    steps = build_alpha_next_steps({'in_battle': False}, lang='en')
    assert isinstance(steps, tuple) and steps
    ru_steps = build_alpha_next_steps({'in_battle': False}, lang='ru')
    es_steps = build_alpha_next_steps({'in_battle': False}, lang='es')
    assert isinstance(ru_steps, tuple) and ru_steps
    assert isinstance(es_steps, tuple) and es_steps
    ru_text = ' '.join(ru_steps)
    es_text = ' '.join(es_steps)
    assert 'Check your location' not in ru_text
    assert 'Take a hunt contract' not in ru_text
    assert 'Check your location' not in es_text
    assert 'Take a hunt contract' not in es_text
    assert build_location_objective_hint('unknown_location')['contract_count'] == 0
    assert 'route_' not in ' '.join(steps).lower()
    assert validate_alpha_guidance_surface() == []


def test_onboarding_and_help_locale_keys_exist():
    for locale in ('locales/en.py', 'locales/ru.py', 'locales/es.py'):
        text = Path(locale).read_text(encoding='utf-8').lower()
        for needle in ('alpha_intro', 'alpha_next_steps_title', 'location', 'map', 'contract', 'inventory'):
            assert needle in text
        for needle in (
            'alpha_step_finish_battle', 'alpha_step_check_location', 'alpha_step_open_map',
            'alpha_step_take_contract', 'alpha_step_fight_claim', 'alpha_step_inventory_equipment',
            'alpha_step_enhance', 'alpha_step_unstuck',
        ):
            assert needle in text


def test_location_objective_hints_numeric_routes_and_sunscar_truthful():
    for location_id in ('hub_westwild', 'frostspine_n5', 'ashen_n3a2', 'mireveil_n5a1'):
        hint = build_location_objective_hint(location_id)
        assert hint['has_contracts'] is True
        assert hint['contract_count'] > 0
    sunscar = build_alpha_route_status_hint('hub_sunscar')
    assert sunscar['route_id'] == 'route_sunscar'
    assert sunscar['numeric_ready'] is False


def test_quest_board_discoverability_route_locality():
    contracts = list_hunt_contracts_for_location('frostspine_n5')
    assert contracts
    keys = {c.contract_key for c in contracts}
    assert 'hunt_frostspine_white_wolves' in keys
    assert 'hunt_ashen_zombie_clusters' not in keys


def test_recovery_policy_blocks_and_unknown_fallback():
    assert build_recovery_decision({'active_danger_context': True})['allowed'] is False
    assert build_recovery_decision({'active_battle_context': True})['allowed'] is False
    assert build_recovery_decision({'active_danger_context': True, 'battle_mob': True})['allowed'] is False
    assert build_recovery_decision({'active_danger_context': True, 'aggro_message_id': 123})['allowed'] is False
    assert build_recovery_decision({'pvp_mobility_blocked': True})['allowed'] is False
    stale = build_recovery_decision({'persisted_in_battle': True, 'active_danger_context': False, 'location_id': 'hub_westwild'})
    assert stale['allowed'] is True
    assert stale['reason'] == 'stale_battle_flag'
    assert stale['target_location_id'] == 'village'
    known = build_recovery_decision({'location_id': 'hub_westwild'})
    assert known['allowed'] is True
    assert known['target_location_id'] == 'village'
    unknown = build_recovery_decision({'location_id': 'bad_location'})
    assert unknown['allowed'] is True
    assert unknown['target_location_id'] == 'village'
    assert validate_alpha_recovery_policy() == []


def test_recovery_policy_stale_battle_flag_vs_aggro_marker():
    allowed = build_recovery_decision({'persisted_in_battle': True, 'active_danger_context': False, 'location_id': 'hub_westwild'})
    blocked = build_recovery_decision({'persisted_in_battle': True, 'active_danger_context': True, 'location_id': 'hub_westwild'})
    assert allowed['allowed'] is True
    assert blocked['allowed'] is False


def test_validators_baselines_and_rollout_locks():
    assert validate_open_world_route_objectives() == []
    assert validate_open_world_progression_loop_sanity() == []
    assert validate_open_world_reward_loot_sanity() == []
    assert validate_open_world_pve_numeric_tuning_baseline() == []
    assert validate_open_world_spawn_profile_placement() == []
    assert validate_open_world_reward_alignment_metadata() == []
    assert validate_open_world_route_balance_reports() == []
    assert validate_open_world_readiness_gap_report() == []

    assert MOBS['white_wolf']['level'] == 4 and MOBS['white_wolf']['hp'] == 58 and MOBS['white_wolf']['damage_min'] == 8 and MOBS['white_wolf']['damage_max'] == 13
    assert MOBS['mountain_stone_golem']['level'] == 10 and MOBS['mountain_stone_golem']['hp'] == 210 and MOBS['mountain_stone_golem']['damage_min'] == 15 and MOBS['mountain_stone_golem']['damage_max'] == 24
    assert MOBS['zombie']['level'] == 4 and MOBS['zombie']['hp'] == 62 and MOBS['zombie']['damage_min'] == 7 and MOBS['zombie']['damage_max'] == 12
    assert MOBS['leech']['level'] == 3 and MOBS['leech']['hp'] == 38 and MOBS['leech']['damage_min'] == 5 and MOBS['leech']['damage_max'] == 9
    assert MOBS['drowned']['level'] == 10 and MOBS['drowned']['hp'] == 138 and MOBS['drowned']['damage_min'] == 20 and MOBS['drowned']['damage_max'] == 30
    assert MOBS['mountain_stone_golem']['exp_reward'] == 110 and (MOBS['mountain_stone_golem']['gold_min'], MOBS['mountain_stone_golem']['gold_max']) == (5, 14)
    assert MOBS['drowned']['exp_reward'] == 105 and (MOBS['drowned']['gold_min'], MOBS['drowned']['gold_max']) == (5, 14)

    assert get_hunt_contract('hunt_frostspine_white_wolves')
    assert get_hunt_contract('hunt_ashen_zombie_clusters')
    assert get_hunt_contract('hunt_mireveil_leech_swarms')

    rolled_out = {skill_id for skill_id, skill in SKILLS.items() if str(skill.get('target_pattern_id') or '').strip()}
    assert rolled_out == {'flame_wave', 'heavy_swing', 'cleave_through', 'arcane_lance', 'hunters_mark', 'aimed_shot', 'piercing_arrow', 'deadeye'}


def test_docs_guard():
    text = Path('docs/ALPHA_UX_ONBOARDING_RECOVERY_PASS1.md').read_text(encoding='utf-8').lower()
    for phrase in (
        'onboarding', 'route objectives', 'quest board contracts', 'inventory', 'equipment',
        'enhancement', 'recovery', 'route_sunscar', 'no_pack_mobs_on_non_stub_route',
        'no combat formula changes', 'no reward formula changes', 'no new mobs', 'no new items',
        'no route topology changes', 'no spawn probability changes', 'no mixed-mob packs', 'no pvp behavior changes',
    ):
        assert phrase in text


def test_sunscar_warning_remains_in_internal_report():
    report = build_open_world_readiness_gap_report()
    warnings_by_route = report['remaining_warnings_by_route']
    assert 'no_pack_mobs_on_non_stub_route' in set(warnings_by_route.get('route_sunscar', ()))
