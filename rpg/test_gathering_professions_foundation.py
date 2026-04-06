import unittest

from game.gathering_foundation import (
    GATHERING_PROFESSION_CONTRACTS,
    build_location_gather_source_profiles,
    resolve_gather_access_decision,
    resolve_gather_resource_identity,
)
from game.reward_policies import REWARD_FAMILIES_BY_SOURCE


class GatheringProfessionsFoundationTests(unittest.TestCase):
    def test_current_gather_resources_map_to_explicit_professions(self):
        self.assertEqual(resolve_gather_resource_identity('herb_common').profession_key, 'herbalism')
        self.assertEqual(resolve_gather_resource_identity('herb_magic').profession_key, 'herbalism')
        self.assertEqual(resolve_gather_resource_identity('wood_dark').profession_key, 'woodcutting')
        self.assertEqual(resolve_gather_resource_identity('iron_ore').profession_key, 'mining')
        self.assertEqual(resolve_gather_resource_identity('coal').profession_key, 'mining')
        self.assertEqual(resolve_gather_resource_identity('gem_common').profession_key, 'mining')
        self.assertEqual(resolve_gather_resource_identity('wolf_pelt').profession_key, 'hunting')
        self.assertEqual(resolve_gather_resource_identity('boar_meat').profession_key, 'hunting')
        self.assertEqual(resolve_gather_resource_identity('spider_silk').profession_key, 'hunting')

    def test_foundation_access_gate_uses_profession_level_and_zone_tier(self):
        denied = resolve_gather_access_decision(
            item_id='gem_common',
            player_profession_level=8,
            zone_tier_band=3,
        )
        self.assertIsNotNone(denied)
        assert denied is not None
        self.assertEqual(denied.profession_key, 'mining')
        self.assertFalse(denied.level_allowed)
        self.assertFalse(denied.is_allowed)

        allowed = resolve_gather_access_decision(
            item_id='gem_common',
            player_profession_level=20,
            zone_tier_band=3,
        )
        self.assertIsNotNone(allowed)
        assert allowed is not None
        self.assertTrue(allowed.zone_allowed)
        self.assertTrue(allowed.level_allowed)
        self.assertTrue(allowed.is_allowed)

    def test_location_gather_entries_are_normalized_into_foundation_profiles(self):
        forest_profiles = build_location_gather_source_profiles('dark_forest')
        forest_by_item = {profile.item_id: profile for profile in forest_profiles}
        self.assertEqual(set(forest_by_item), {'herb_common', 'herb_magic', 'wood_dark'})
        self.assertEqual(forest_by_item['wood_dark'].profession_key, 'woodcutting')

        mines_profiles = build_location_gather_source_profiles('old_mines')
        mines_by_item = {profile.item_id: profile for profile in mines_profiles}
        self.assertEqual(set(mines_by_item), {'iron_ore', 'coal', 'gem_common'})
        self.assertEqual(mines_by_item['gem_common'].profession_key, 'mining')

    def test_location_profiles_use_existing_region_and_tier_hooks(self):
        forest_profiles = build_location_gather_source_profiles('dark_forest')
        self.assertTrue(forest_profiles)
        for profile in forest_profiles:
            self.assertEqual(profile.world_identity, 'ashen_continent')
            self.assertIsNone(profile.macro_region_identity)
            self.assertEqual(profile.region_identity, 'ember_valley')
            self.assertEqual(profile.zone_identity, 'dark_forest')
            self.assertEqual(profile.zone_role, 'normal')
            self.assertEqual(profile.encounter_role, 'normal')
            self.assertIn('dark_wood', profile.region_flavor_tags)
            self.assertEqual(profile.linked_dungeon_id, 'rootbound_hollow')
            self.assertEqual(profile.world_boss_governance_id, 'ember_valley_world_boss')
            self.assertEqual(profile.future_pvp_ruleset_id, 'open_world_frontier')
            self.assertEqual(profile.zone_tier_band, 1)

    def test_hunting_is_contractual_supplemental_layer_not_creature_loot_replacement(self):
        hunting = GATHERING_PROFESSION_CONTRACTS['hunting']
        self.assertTrue(hunting.supplemental_over_creature_loot)
        self.assertEqual(hunting.base_gather_surface, 'creature_harvest')
        self.assertIn('creature_loot', REWARD_FAMILIES_BY_SOURCE['open_world_normal'])


if __name__ == '__main__':
    unittest.main()
