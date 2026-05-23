import os
import tempfile
from pathlib import Path

import database
from database import create_player, get_connection, init_db, is_location_discovered
from game.alpha_guidance import build_alpha_next_steps, validate_alpha_guidance_surface
from game.alpha_recovery import SAFE_RECOVERY_LOCATION_ID, build_recovery_decision, validate_alpha_recovery_policy
from game.alpha_release_gate import build_alpha_release_gate_report, validate_alpha_release_gate
from game.locations import WORLD_LOCATIONS, resolve_location_id
from game.mobs import MOBS
from game.open_world_pack_balance import validate_open_world_spawn_profile_placement
from game.open_world_progression_loop import validate_open_world_progression_loop_sanity
from game.open_world_pve_tuning import validate_open_world_pve_numeric_tuning_baseline
from game.open_world_readiness_gap_report import validate_open_world_readiness_gap_report
from game.open_world_reward_alignment import validate_open_world_reward_alignment_metadata
from game.open_world_reward_sanity import validate_open_world_reward_loot_sanity
from game.open_world_route_balance_report import validate_open_world_route_balance_reports
from game.open_world_route_objectives import (
    collect_route_spawnable_mob_locations,
    get_route_representative_contract_locations,
    list_route_hunt_contracts,
    validate_open_world_route_objectives,
)
from game.quest_board import (
    accept_hunt_contract,
    claim_completed_hunt_contract,
    get_hunt_contract,
    get_player_hunt_contract_state,
    list_hunt_contracts_for_location,
    register_hunt_kill_progress,
)
from game.skills import SKILLS

RPG_ROOT = Path(__file__).resolve().parents[1]
ALPHA_READY_ROUTES = ('route_westwild', 'route_frostspine', 'route_ashen_ruins', 'route_mireveil')


def test_release_gate_report_builds_and_routes_are_explicit():
    report = build_alpha_release_gate_report()
    assert isinstance(report, dict)
    for key in ('alpha_ready_routes', 'blocked_routes', 'sparse_stub_routes', 'known_alpha_limits', 'required_systems', 'validator_status', 'smoke_path_status', 'release_warnings'):
        assert key in report
    assert tuple(report['alpha_ready_routes']) == ALPHA_READY_ROUTES
    assert 'route_sunscar' in set(report['blocked_routes'])
    assert set(report['sparse_stub_routes']) == {'route_south_coast_stub', 'route_old_mine_stub'}


def test_all_validators_green_including_release_gate():
    assert validate_alpha_release_gate() == []
    assert validate_alpha_guidance_surface() == []
    assert validate_alpha_recovery_policy() == []
    assert validate_open_world_route_objectives() == []
    assert validate_open_world_progression_loop_sanity() == []
    assert validate_open_world_reward_loot_sanity() == []
    assert validate_open_world_pve_numeric_tuning_baseline() == []
    assert validate_open_world_spawn_profile_placement() == []
    assert validate_open_world_reward_alignment_metadata() == []
    assert validate_open_world_route_balance_reports() == []
    assert validate_open_world_readiness_gap_report() == []


def test_fresh_player_bootstrap_sanity_and_alpha_guidance_surface():
    tmpdir = tempfile.TemporaryDirectory()
    original_db = database.DB_PATH
    database.DB_PATH = os.path.join(tmpdir.name, 'test.db')
    try:
        init_db()
        create_player(
            telegram_id=9301,
            username='fresh',
            name='Fresh',
            stats={
                'strength': 5,
                'agility': 5,
                'intuition': 5,
                'vitality': 5,
                'wisdom': 5,
                'luck': 5,
            },
        )
        conn = get_connection()
        row = conn.execute('SELECT * FROM players WHERE telegram_id=9301').fetchone()
        conn.close()

        assert row is not None
        location_id = resolve_location_id(row['location_id'])
        assert location_id in WORLD_LOCATIONS
        assert WORLD_LOCATIONS.get(location_id)
        assert row['hp'] > 0 and row['max_hp'] >= row['hp']
        assert row['mana'] >= 0 and row['max_mana'] >= row['mana']
        assert is_location_discovered(9301, 'capital_city') is True
        assert resolve_location_id('village') in WORLD_LOCATIONS
        steps = build_alpha_next_steps(dict(row), lang='en')
        assert isinstance(steps, tuple) and steps
    finally:
        database.DB_PATH = original_db
        tmpdir.cleanup()


def test_route_contract_smoke_for_all_alpha_ready_routes():
    for route_id in ALPHA_READY_ROUTES:
        contracts = list_route_hunt_contracts(route_id)
        assert contracts, route_id
        board_location = get_route_representative_contract_locations(route_id)[0]
        board_keys = {c.contract_key for c in list_hunt_contracts_for_location(board_location)}
        for contract in contracts:
            assert contract.target_mob_id in MOBS
            assert contract.reward_exp > 0 and contract.reward_gold > 0
            assert contract.reward_exp <= 150 and contract.reward_gold <= 120
            assert contract.contract_key in board_keys
            spawnable = set(collect_route_spawnable_mob_locations(route_id, contract.target_mob_id))
            for loc in contract.target_location_ids:
                assert resolve_location_id(loc) in spawnable


def test_contract_progress_claim_e2e_all_alpha_ready_routes():
    tmpdir = tempfile.TemporaryDirectory()
    original_db = database.DB_PATH
    database.DB_PATH = os.path.join(tmpdir.name, 'test.db')
    try:
        init_db()
        for idx, route_id in enumerate(ALPHA_READY_ROUTES):
            board_location = get_route_representative_contract_locations(route_id)[0]
            player_id = 9400 + idx
            conn = get_connection()
            conn.execute("""INSERT INTO players (telegram_id, username, name, level, exp, hp, max_hp, mana, max_mana, gold,
                strength, agility, intuition, vitality, wisdom, luck, stat_points, location_id, in_battle, lang)
                VALUES (?, ?, ?, 10, 0, 100, 100, 50, 50, 0, 5,5,5,5,5,5,0, ?, 0, 'en')""", (player_id, f'p{idx}', f'P{idx}', board_location))
            conn.commit(); conn.close()
            contract = next(c for c in list_route_hunt_contracts(route_id) if not c.required_hunter_rank)
            ok, reason = accept_hunt_contract(player_id=player_id, location_id=board_location, contract_key=contract.contract_key)
            assert (ok, reason) == (True, 'accepted')
            for _ in range(contract.required_kills):
                kill_location = contract.target_location_ids[0]
                update = register_hunt_kill_progress(player_id=player_id, mob_id=contract.target_mob_id, location_id=kill_location)
                assert update['updated'] is True
            state = get_player_hunt_contract_state(player_id=player_id)
            assert state and state['status'] == 'completed'
            ok_claim, reason_claim, reward = claim_completed_hunt_contract(player_id=player_id, location_id=board_location)
            assert (ok_claim, reason_claim) == (True, 'claimed')
            assert reward and (reward['reward_exp'] > 0 or reward['reward_gold'] > 0)
            dup_ok, dup_reason, _ = claim_completed_hunt_contract(player_id=player_id, location_id=board_location)
            assert (dup_ok, dup_reason) == (False, 'already_claimed')
    finally:
        database.DB_PATH = original_db
        tmpdir.cleanup()


def test_recovery_policy_release_gate_smoke():
    assert build_recovery_decision({'active_danger_context': True})['allowed'] is False
    assert build_recovery_decision({'pvp_mobility_blocked': True})['allowed'] is False
    stale = build_recovery_decision({'persisted_in_battle': True, 'location_id': 'hub_westwild'})
    assert stale['allowed'] is True and stale['target_location_id'] == SAFE_RECOVERY_LOCATION_ID
    unknown = build_recovery_decision({'location_id': 'not_a_real_location'})
    assert unknown['allowed'] is True and unknown['target_location_id'] == SAFE_RECOVERY_LOCATION_ID
    report = build_alpha_release_gate_report()
    assert 'alpha_recovery_policy' in report['validator_status']


def test_i18n_and_known_limitations_and_frozen_baselines():
    for locale_rel in ('locales/en.py', 'locales/ru.py', 'locales/es.py'):
        text = (RPG_ROOT / locale_rel).read_text(encoding='utf-8')
        for needle in (
            'alpha_intro', 'alpha_next_steps_title', 'alpha_step_',
            'alpha_contracts_available', 'alpha_route_partial',
            'unstuck_blocked_battle', 'unstuck_done',
        ):
            assert needle in text

    report = build_alpha_release_gate_report()
    limits_text = ' '.join(report['known_alpha_limits']) + ' ' + ' '.join(report['release_warnings'])
    assert 'route_sunscar' in limits_text
    assert 'no_pack_mobs_on_non_stub_route' in limits_text
    for phrase in ('curated/static', 'single-active-contract architecture unchanged', 'no full dynamic quest generation', 'no mixed-mob packs', 'world boss'):
        assert phrase in limits_text

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


def test_alpha_release_gate_doc_guard():
    text = (RPG_ROOT / 'docs/ALPHA_RELEASE_GATE_PR3P.md').read_text(encoding='utf-8').lower()
    for phrase in (
        'follows pr 3o', 'first alpha release gate',
        'route_westwild', 'route_frostspine', 'route_ashen_ruins', 'route_mireveil',
        'route_sunscar', 'no_pack_mobs_on_non_stub_route', 'route_south_coast_stub', 'route_old_mine_stub',
        'curated/static', 'single-active-contract architecture unchanged', 'no dynamic quest generation', 'no mixed-mob packs',
        'no combat formula changes', 'no mob stat changes', 'no reward formula', 'no spawn probability changes',
        'no new mobs/items', 'no route topology changes', 'no skill targeting rollout', 'no pvp behavior changes',
    ):
        assert phrase in text
