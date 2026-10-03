from game.enemy_profiles import MIXED_ENCOUNTERS
from game.locations import get_location
from game.pve_live import ensure_location_pve_spawn_instances, list_location_available_spawn_instances
from game.quest_board import HUNT_CONTRACTS_BY_KEY


def test_exact_service_additions_and_unchanged_inn_price():
    assert 'quest_board' in get_location('frostspine_n5')['services']
    assert 'quest_board' in get_location('ashen_n3a2')['services']
    assert 'quest_board' in get_location('mireveil_n5a1')['services']
    assert 'quest_board' in get_location('hub_sunscar')['services']
    assert 'inn' in get_location('hub_ashen_ruins')['services']
    assert 'inn' in get_location('hub_mireveil')['services']
    assert 'inn' in get_location('hub_sunscar')['services']
    from handlers.location import INN_REST_COST_GOLD
    assert INN_REST_COST_GOLD == 12


def test_five_existing_hunts_are_reachable_with_frozen_terms():
    expected = {
        'hunt_frostspine_white_wolves': (4,105,48,24,None),
        'hunt_ashen_zombie_clusters': (4,108,50,24,None),
        'hunt_mireveil_leech_swarms': (5,102,47,24,None),
        'hunt_sunscar_scorpions': (4,110,52,24,None),
        'hunt_sunscar_air_elementals': (2,120,58,30,'tracker'),
    }
    for key, values in expected.items():
        contract = HUNT_CONTRACTS_BY_KEY[key]
        assert (contract.required_kills,contract.reward_exp,contract.reward_gold,
                contract.hunter_points_reward,contract.required_hunter_rank) == values
        assert all('quest_board' in get_location(board)['services'] for board in contract.board_locations)


def test_named_spawns_have_exact_stable_identity_and_profiles():
    for location_id, expected_id, mob_id, key, profile in (
        ('westwild_n3','spawn-westwild_n3-forest_wolf-special-greyfang','forest_wolf','greyfang','normal'),
        ('sunscar_n8a2','spawn-sunscar_n8a2-air_elemental-special-salt_ridge_drifter','air_elemental','salt_ridge_drifter','elite'),
    ):
        ensure_location_pve_spawn_instances(location_id=location_id)
        rows = list_location_available_spawn_instances(location_id=location_id)
        row = next(row for row in rows if row.get('special_spawn_key') == key)
        assert row['spawn_instance_id'] == expected_id
        assert row['mob_id'] == mob_id and row['spawn_profile'] == profile


def test_two_new_mixed_recipes_exact_and_existing_retained():
    assert MIXED_ENCOUNTERS['westwild_n8_mixed']['units'] == (
        ('bear','front'),('goblin_hunter','melee'),('goblin_shaman','support'))
    assert MIXED_ENCOUNTERS['ashen_n3c1_mixed']['units'] == (
        ('zombie','melee'),('zombie','melee'),('skeleton_mage','ranged'))
    assert MIXED_ENCOUNTERS['rav1_frostspine_n6_pass']['units'] == (
        ('mountain_stone_golem','front'),('stone_beetle','melee'))
    assert MIXED_ENCOUNTERS['rav1_mireveil_n6_crosscurrent']['units'] == (
        ('giant_leech','melee'),('water_snake','melee'))
