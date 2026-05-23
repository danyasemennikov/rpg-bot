import os
import tempfile

import database
from database import get_connection, init_db
from game.locations import WORLD_LOCATIONS, resolve_location_id
from game.mobs import MOBS
from game.open_world_pack_balance import collect_open_world_route_mob_ids
from game.open_world_progression_loop import validate_open_world_progression_loop_sanity
from game.open_world_pve_tuning import validate_open_world_pve_numeric_tuning_baseline
from game.open_world_readiness_gap_report import validate_open_world_readiness_gap_report
from game.open_world_reward_alignment import validate_open_world_reward_alignment_metadata
from game.open_world_reward_sanity import validate_open_world_reward_loot_sanity
from game.open_world_route_balance_report import validate_open_world_route_balance_reports
from game.open_world_route_objectives import (
    build_all_route_objective_profiles,
    build_route_objective_profile,
    collect_route_contract_target_mob_ids,
    collect_route_spawnable_mob_locations,
    get_route_representative_contract_locations,
    list_route_hunt_contracts,
    validate_open_world_route_objectives,
)
from game.open_world_pack_balance import validate_open_world_spawn_profile_placement
from game.quest_board import (
    accept_hunt_contract,
    claim_completed_hunt_contract,
    get_player_hunt_contract_state,
    get_hunt_contract,
    list_hunt_contracts_for_location,
    register_hunt_kill_progress,
)
from game.skills import SKILLS

ROUTES = (
    'route_westwild', 'route_frostspine', 'route_ashen_ruins', 'route_sunscar',
    'route_mireveil', 'route_south_coast_stub', 'route_old_mine_stub',
)
NUMERIC_READY_ROUTES = ('route_westwild', 'route_frostspine', 'route_ashen_ruins', 'route_mireveil')


def test_route_objective_profiles_build():
    required = {
        'route_id', 'numeric_tuning_ready', 'is_sparse_or_stub', 'solo_mob_ids', 'pack_mob_ids',
        'elite_anchor_mob_ids', 'supported_contract_types', 'hunt_target_mob_ids',
        'elite_objective_mob_ids', 'progression_reward_signal', 'objective_warnings',
    }
    for route_id in ROUTES:
        profile = build_route_objective_profile(route_id)
        assert profile
        assert required.issubset(profile.keys())


def test_numeric_ready_routes_have_objective_coverage():
    for route_id in NUMERIC_READY_ROUTES:
        profile = build_route_objective_profile(route_id)
        route_local = collect_open_world_route_mob_ids(route_id)
        assert profile['numeric_tuning_ready'] is True
        assert profile['hunt_target_mob_ids']
        assert 'hunt' in set(profile['supported_contract_types'])
        if profile['pack_mob_ids']:
            assert 'pack_pressure' in set(profile['supported_contract_types'])
        if profile['elite_anchor_mob_ids']:
            assert profile['elite_objective_mob_ids']
            assert 'elite_hunt' in set(profile['supported_contract_types'])
        for mob_id in profile['hunt_target_mob_ids'] + profile['elite_objective_mob_ids']:
            assert mob_id in route_local


def test_sunscar_remains_truthful():
    profile = build_route_objective_profile('route_sunscar')
    assert profile
    assert profile['numeric_tuning_ready'] is False
    assert 'no_pack_mobs_on_non_stub_route' in set(profile['objective_warnings'])
    assert 'pack_pressure' not in set(profile['supported_contract_types'])


def test_stub_route_handling():
    for route_id in ('route_south_coast_stub', 'route_old_mine_stub'):
        profile = build_route_objective_profile(route_id)
        assert profile['is_sparse_or_stub'] is True


def test_objective_references_valid_mobs_and_route_locality():
    for profile in build_all_route_objective_profiles():
        route_local = collect_open_world_route_mob_ids(profile['route_id'])
        for key in ('hunt_target_mob_ids', 'elite_objective_mob_ids', 'pack_mob_ids'):
            for mob_id in profile[key]:
                assert mob_id in MOBS
                assert mob_id in route_local


def test_quest_board_listing_respects_route_local_and_canonical_aliases():
    legacy = {c.contract_key: c for c in list_hunt_contracts_for_location('village')}
    canonical = {c.contract_key: c for c in list_hunt_contracts_for_location('hub_westwild')}
    assert set(legacy.keys()) == set(canonical.keys())
    westwild_local = collect_open_world_route_mob_ids('route_westwild')
    for contract in canonical.values():
        assert contract.target_mob_id in westwild_local


def test_quest_board_visible_contract_coverage_for_all_numeric_ready_routes():
    for route_id in NUMERIC_READY_ROUTES:
        contracts = list_route_hunt_contracts(route_id)
        route_local = collect_open_world_route_mob_ids(route_id)
        assert contracts, route_id
        for contract in contracts:
            assert contract.target_mob_id in MOBS
            assert contract.target_mob_id in route_local
            assert contract.reward_exp > 0 and contract.reward_gold > 0
        expected_targets = {c.target_mob_id for c in contracts}
        assert expected_targets.issubset(route_local)


def test_route_contract_target_locations_are_spawnable():
    for route_id in NUMERIC_READY_ROUTES:
        route_local_mobs = collect_open_world_route_mob_ids(route_id)
        route_targets = set(collect_route_contract_target_mob_ids(route_id))
        assert route_targets.issubset(route_local_mobs)
        for contract in list_route_hunt_contracts(route_id):
            assert contract.target_location_ids
            spawnable_locations = set(collect_route_spawnable_mob_locations(route_id, contract.target_mob_id))
            for location_id in contract.target_location_ids:
                normalized_location_id = resolve_location_id(location_id)
                location = WORLD_LOCATIONS.get(normalized_location_id, {})
                assert location.get('route_id') == route_id
                loc_mobs = set(location.get('mobs') or ())
                loc_profiles = set((location.get('world_spawn_profiles') or {}).keys())
                assert contract.target_mob_id in loc_mobs or contract.target_mob_id in loc_profiles
                assert normalized_location_id in spawnable_locations


def test_contract_accept_progress_claim_smoke_all_numeric_ready_routes():
    tmpdir = tempfile.TemporaryDirectory()
    orig = database.DB_PATH
    database.DB_PATH = os.path.join(tmpdir.name, 'test.db')
    try:
        init_db()
        for idx, route_id in enumerate(NUMERIC_READY_ROUTES):
            board_location = get_route_representative_contract_locations(route_id)[0]
            player_id = 9200 + idx
            conn = get_connection()
            conn.execute(
                """INSERT INTO players (telegram_id, username, name, level, exp, hp, max_hp, mana, max_mana, gold,
                strength, agility, intuition, vitality, wisdom, luck, stat_points, location_id, in_battle, lang)
                VALUES (?, ?, ?, 10, 0, 100, 100, 50, 50, 0, 5,5,5,5,5,5,0, ?, 0, 'en')""",
                (player_id, f'p{idx}', f'P{idx}', board_location),
            )
            conn.commit()
            conn.close()
            contract = next(c for c in list_route_hunt_contracts(route_id) if not c.required_hunter_rank)
            ok, reason = accept_hunt_contract(player_id=player_id, location_id=board_location, contract_key=contract.contract_key)
            assert (ok, reason) == (True, 'accepted')
            for _ in range(contract.required_kills):
                kill_location = contract.target_location_ids[0] if contract.target_location_ids else board_location
                location = WORLD_LOCATIONS.get(kill_location, {})
                location_mobs = set(location.get('mobs') or ())
                location_profiles = set((location.get('world_spawn_profiles') or {}).keys())
                assert contract.target_mob_id in location_mobs or contract.target_mob_id in location_profiles
                register_hunt_kill_progress(player_id=player_id, mob_id=contract.target_mob_id, location_id=kill_location)
            state = get_player_hunt_contract_state(player_id)
            assert state and state['status'] == 'completed'
            ok_claim, reason_claim, reward = claim_completed_hunt_contract(player_id=player_id, location_id=board_location)
            assert (ok_claim, reason_claim) == (True, 'claimed')
            assert reward and reward['reward_exp'] > 0 and reward['reward_gold'] > 0
            ok_dup, reason_dup, _ = claim_completed_hunt_contract(player_id=player_id, location_id=board_location)
            assert (ok_dup, reason_dup) == (False, 'already_claimed')
    finally:
        database.DB_PATH = orig
        tmpdir.cleanup()


def test_wrong_target_and_wrong_route_do_not_progress_contract():
    tmpdir = tempfile.TemporaryDirectory()
    orig = database.DB_PATH
    database.DB_PATH = os.path.join(tmpdir.name, 'test.db')
    try:
        init_db()
        conn = get_connection()
        conn.execute("""INSERT INTO players (telegram_id, username, name, level, exp, hp, max_hp, mana, max_mana, gold,
            strength, agility, intuition, vitality, wisdom, luck, stat_points, location_id, in_battle, lang)
            VALUES (9102, 'p2', 'P2', 10, 0, 100, 100, 50, 50, 0, 5,5,5,5,5,5,0, 'village', 0, 'en')""")
        conn.commit(); conn.close()
        accept_hunt_contract(player_id=9102, location_id='village', contract_key='hunt_forest_wolves')
        assert register_hunt_kill_progress(player_id=9102, mob_id='mine_rat', location_id='westwild_n3')['updated'] is False
        assert register_hunt_kill_progress(player_id=9102, mob_id='forest_wolf', location_id='old_mines')['updated'] is False
    finally:
        database.DB_PATH = orig
        tmpdir.cleanup()


def test_profile_hunt_targets_cover_route_contract_targets():
    for route_id in NUMERIC_READY_ROUTES:
        profile = build_route_objective_profile(route_id)
        contract_targets = {c.target_mob_id for c in list_route_hunt_contracts(route_id)}
        allowed_targets = set(profile['hunt_target_mob_ids']) | set(profile['elite_objective_mob_ids'])
        assert contract_targets.issubset(allowed_targets)
        assert 'hunt' in set(profile['supported_contract_types'])


def test_new_route_contract_titles_are_route_specific_and_localized():
    assert get_hunt_contract('hunt_frostspine_white_wolves').title_i18n_key == 'location.quest_contract_frostspine_white_wolves_title'
    assert get_hunt_contract('hunt_ashen_zombie_clusters').title_i18n_key == 'location.quest_contract_ashen_zombie_clusters_title'
    assert get_hunt_contract('hunt_mireveil_leech_swarms').title_i18n_key == 'location.quest_contract_mireveil_leech_swarms_title'

    for locale_path in ('locales/en.py', 'locales/ru.py', 'locales/es.py'):
        text = open(locale_path, encoding='utf-8').read()
        assert 'quest_contract_frostspine_white_wolves_title' in text
        assert 'quest_contract_ashen_zombie_clusters_title' in text
        assert 'quest_contract_mireveil_leech_swarms_title' in text


def test_documentation_guard_required_phrases_present():
    text = open('docs/OPEN_WORLD_ROUTE_OBJECTIVES_PASS1.md', encoding='utf-8').read().lower()
    required = (
        'quest board contracts', 'curated/static', 'route_westwild', 'route_frostspine',
        'route_ashen_ruins', 'route_mireveil', 'route_sunscar', 'no_pack_mobs_on_non_stub_route',
        'no combat formula changes', 'no mob stat changes', 'no reward formula', 'no new mobs',
        'no new items', 'no route topology changes', 'no spawn probability changes',
        'no mixed-mob packs', 'no pvp behavior', 'single-active-contract architecture unchanged',
    )
    for phrase in required:
        assert phrase in text


def test_validators_and_baselines_stay_green():
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

    rolled_out = {skill_id for skill_id, skill in SKILLS.items() if str(skill.get('target_pattern_id') or '').strip()}
    assert rolled_out == {
        'flame_wave', 'heavy_swing', 'cleave_through', 'arcane_lance',
        'hunters_mark', 'aimed_shot', 'piercing_arrow', 'deadeye',
    }
