from game.gathering_foundation import build_location_gather_source_profiles, resolve_gather_access_decision
from game.profession_recipes import recipe_consumers
from game.profession_resources import ENVIRONMENTAL_SOURCES, MANDATORY_RESOURCE_IDS, RESOURCES, validate_environmental_sources


def test_single_source_authority_and_probabilities():
    assert validate_environmental_sources() == []
    for location_id, rows in ENVIRONMENTAL_SOURCES.items():
        assert [(p.item_id, p.chance) for p in build_location_gather_source_profiles(location_id)] == list(rows)


def test_all_resources_have_source_and_consumer():
    environmental = {item for rows in ENVIRONMENTAL_SOURCES.values() for item, _ in rows}
    hunting = set(MANDATORY_RESOURCE_IDS) - environmental
    assert hunting == {'boar_meat','wolf_pelt','wolf_fang','spider_silk','bear_hide','troll_sinew'}
    assert all(recipe_consumers(item_id) for item_id in MANDATORY_RESOURCE_IDS)


def test_access_uses_explicit_level_without_zone_multiplier():
    for item_id, resource in RESOURCES.items():
        denied = resolve_gather_access_decision(item_id=item_id, player_profession_level=max(1, resource.required_level-1), zone_tier_band=10)
        allowed = resolve_gather_access_decision(item_id=item_id, player_profession_level=resource.required_level, zone_tier_band=10)
        if resource.required_level > 1:
            assert not denied.level_allowed
        assert allowed.level_allowed and allowed.required_profession_level == resource.required_level
