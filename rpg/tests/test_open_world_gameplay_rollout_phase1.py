import unittest

from game.gathering_foundation import build_location_gather_source_profiles
from game.i18n import get_location_desc, get_location_name
from game.items_data import get_item_reward_tags
from game.locations import LOCATIONS, get_location, get_route_alpha_depth_stage, resolve_location_id
from game.mobs import MOBS
from game.quest_board import HUNT_CONTRACTS_BY_KEY
from game.open_world_reward_pools import build_open_world_reward_pool_profile
from game.reward_source_metadata import build_open_world_combat_source_metadata


APPROVED_ELITE_ANCHORS = {
    'westwild_n7', 'westwild_n8', 'westwild_n10', 'westwild_n11',
    'frostspine_n6', 'frostspine_n8', 'frostspine_n10',
    'ashen_n3b1', 'ashen_n3b2', 'ashen_n3b2a1', 'ashen_n3c2',
    'sunscar_n6', 'sunscar_n8', 'sunscar_n8a2', 'sunscar_n10', 'sunscar_n11',
    'mireveil_n6', 'mireveil_n8', 'mireveil_n8a2', 'mireveil_n10',
}


APPROVED_RU_NAMES = {
    'westwild_n1': '🌾 Пшеничные поля',
    'westwild_n7': '🌲 Тёмный лес',
    'frostspine_n6': '⛏️ Рудники',
    'ashen_n3b1': '🏚️ Глухие руины',
    'sunscar_n7': '🧂 Солончак',
    'mireveil_n8a1': '🍄 Грибная топь',
    'south_coast_shore': '🏖️ Южный берег',
    'old_mine_entrance': '⛏️ Старая шахта',
}


class OpenWorldGameplayRolloutPhase1Tests(unittest.TestCase):
    def test_approved_display_names_and_legacy_aliases_resolve(self):
        for location_id, expected_name in APPROVED_RU_NAMES.items():
            with self.subTest(location_id=location_id):
                self.assertEqual(get_location_name(location_id, 'ru'), expected_name)
                self.assertEqual(get_location(location_id)['display_name'], expected_name)

        self.assertEqual(resolve_location_id('dark_forest'), 'westwild_n7')
        self.assertEqual(resolve_location_id('village'), 'hub_westwild')
        self.assertEqual(resolve_location_id('frontier_outpost'), 'hub_frostspine')
        self.assertEqual(resolve_location_id('old_mines'), 'old_mine_entrance')

    def test_every_non_safe_canonical_overworld_location_has_pve_and_hubs_do_not(self):
        for location_id, location in LOCATIONS.items():
            with self.subTest(location_id=location_id):
                if location.get('safe'):
                    self.assertEqual(location.get('mobs', []), [])
                    continue
                self.assertTrue(location.get('mobs'), f'{location_id} missing PvE mobs')
                self.assertTrue(location.get('world_spawn_profiles'), f'{location_id} missing spawn profile bindings')

    def test_elite_anchors_exist_exactly_where_approved(self):
        actual = set()
        for location_id, location in LOCATIONS.items():
            profiles = location.get('world_spawn_profiles') or {}
            has_elite = any('elite' in profile_counts and profile_counts['elite'] > 0 for profile_counts in profiles.values())
            if has_elite:
                actual.add(location_id)
        self.assertEqual(actual, APPROVED_ELITE_ANCHORS)
        self.assertNotIn('south_coast_shore', actual)
        self.assertNotIn('old_mine_entrance', actual)

    def test_gathering_phase1_route_constraints(self):
        ashen_with_gather = {
            location_id
            for location_id in LOCATIONS
            if location_id.startswith('ashen_') and build_location_gather_source_profiles(location_id)
        }
        self.assertEqual(ashen_with_gather, {'ashen_n3c1'})

        coast_professions = {profile.profession_key for profile in build_location_gather_source_profiles('south_coast_shore')}
        self.assertIn('fishing', coast_professions)

        old_mine_professions = {profile.profession_key for profile in build_location_gather_source_profiles('old_mine_entrance')}
        self.assertEqual(old_mine_professions, {'mining'})

        sunscar_salt = {profile.item_id: profile for profile in build_location_gather_source_profiles('sunscar_n7')}
        self.assertEqual(sunscar_salt['salt_crystal'].profession_key, 'herbalism')

        mireveil_fungal_items = {profile.item_id for profile in build_location_gather_source_profiles('mireveil_n8a1')}
        self.assertEqual(mireveil_fungal_items, {'marsh_mushroom'})
        self.assertNotIn('fungal', ' '.join(get_location('mireveil_n8a1').get('mobs', [])))

    def test_reward_source_integrity_for_normal_and_elite_content(self):
        normal_profile = build_open_world_reward_pool_profile(
            source_category='open_world_normal',
            source_id='westwild_rabbit',
            mob_level=1,
            location_id='westwild_n1',
        )
        self.assertEqual(normal_profile.source_category, 'open_world_normal')
        self.assertEqual(normal_profile.region_identity, 'ember_valley')
        self.assertIn('forest_wilds', normal_profile.region_flavor_tags)

        elite_meta = build_open_world_combat_source_metadata(
            source_id='goblin_chief',
            mob_level=9,
            source_category='open_world_elite',
            spawn_profile='elite',
            location_id='westwild_n11',
        )
        self.assertEqual(elite_meta.source_category, 'open_world_elite')
        self.assertEqual(elite_meta.open_world_region_identity, 'ember_valley')
        self.assertEqual(elite_meta.open_world_zone_identity, 'westwild_n11')
        self.assertEqual(elite_meta.open_world_encounter_role, 'elite')

        mine_profile = build_open_world_reward_pool_profile(
            source_category='open_world_normal',
            source_id='mine_rat',
            mob_level=3,
            location_id='old_mine_entrance',
        )
        self.assertEqual(mine_profile.region_identity, 'ember_valley')
        self.assertIn('ore_veins', mine_profile.region_flavor_tags)
        self.assertIn('goblin_camps', mine_profile.region_flavor_tags)

    def test_dark_forest_semantics_are_not_split_from_alias_target(self):
        dark_forest = get_location('dark_forest')
        canonical_dark = get_location('westwild_n7')
        leafy_grove = get_location('westwild_n4')

        self.assertEqual(dark_forest.get('canonical_id'), 'westwild_n7')
        self.assertEqual(canonical_dark.get('zone_id'), 'dark_forest')
        self.assertEqual(dark_forest.get('zone_id'), canonical_dark.get('zone_id'))
        self.assertEqual(canonical_dark.get('linked_dungeon_id'), 'rootbound_hollow')
        self.assertEqual(canonical_dark.get('world_boss_governance_id'), 'ember_valley_world_boss')
        self.assertIn('poison_herbs', canonical_dark.get('region_flavor_tags', []))

        self.assertEqual(leafy_grove.get('zone_id'), 'westwild_n4')
        self.assertIsNone(leafy_grove.get('linked_dungeon_id'))
        self.assertIsNone(leafy_grove.get('world_boss_governance_id'))
        self.assertNotIn('poison_herbs', leafy_grove.get('region_flavor_tags', []))

    def test_old_mine_sparse_gameplay_preserves_compatibility_identity(self):
        old_mine = get_location('old_mine_entrance')
        self.assertEqual(old_mine.get('mobs'), ['mine_rat', 'cave_bat'])
        self.assertEqual(old_mine.get('zone_role'), 'normal')
        self.assertIsNone(old_mine.get('linked_dungeon_id'))
        self.assertIsNone(old_mine.get('world_boss_governance_id'))
        self.assertEqual(old_mine.get('world_special_spawns'), [])
        self.assertEqual(old_mine.get('region_id'), 'ember_valley')
        self.assertEqual(old_mine.get('region_flavor_tags'), ['ore_veins', 'construct_ruins', 'goblin_camps'])

    def test_starter_westwild_contract_targets_remain_sensible(self):
        self.assertIn('westwild_rabbit', get_location('westwild_n1').get('mobs', []))
        self.assertIn('forest_boar', get_location('westwild_n2').get('mobs', []))
        self.assertIn('forest_wolf', get_location('westwild_n3').get('mobs', []))
        self.assertIn('forest_spider', get_location('westwild_n4').get('mobs', []))
        self.assertIn('goblin_scout', get_location('westwild_n5').get('mobs', []))
        self.assertIn('forest_boar', get_location('westwild_n7').get('mobs', []))
        self.assertEqual(HUNT_CONTRACTS_BY_KEY['hunt_forest_wolves'].target_location_ids, ('westwild_n3',))
        self.assertEqual(HUNT_CONTRACTS_BY_KEY['hunt_greyfang'].target_location_ids, ('westwild_n3',))
        self.assertEqual(HUNT_CONTRACTS_BY_KEY['hunt_forest_spiders'].target_location_ids, ('westwild_n4',))

    def test_elite_boar_contract_is_backed_by_real_elite_spawn_data(self):
        contract = HUNT_CONTRACTS_BY_KEY['hunt_elite_boars']
        self.assertEqual(contract.target_mob_id, 'forest_boar')
        self.assertEqual(contract.spawn_profile, 'elite')

        resolved_target_ids = {resolve_location_id(location_id) for location_id in contract.target_location_ids}
        self.assertEqual(resolved_target_ids, {'westwild_n7'})

        for location_id in resolved_target_ids:
            with self.subTest(location_id=location_id):
                location = get_location(location_id)
                self.assertIn(contract.target_mob_id, location.get('mobs', []))
                profiles = location.get('world_spawn_profiles') or {}
                self.assertGreater(profiles.get(contract.target_mob_id, {}).get('elite', 0), 0)

    def test_phase1_does_not_assign_normal_profiles_to_intrinsic_elites(self):
        for location_id, location in LOCATIONS.items():
            profiles = location.get('world_spawn_profiles') or {}
            for mob_id, profile_counts in profiles.items():
                if profile_counts.get('normal', 0) <= 0:
                    continue
                mob = MOBS.get(mob_id, {})
                taxonomy = mob.get('creature_taxonomy') or {}
                has_intrinsic_elite_identity = (
                    mob.get('encounter_role') == 'elite'
                    or mob.get('reward_source_category') == 'open_world_elite'
                    or taxonomy.get('encounter_class') == 'elite'
                )
                self.assertFalse(
                    has_intrinsic_elite_identity,
                    f'{location_id} assigns a normal spawn profile to intrinsically elite mob {mob_id}',
                )

    def test_frostspine_n6_uses_normal_rollout_golem_with_elite_anchor_profile(self):
        frostspine_mines = get_location('frostspine_n6')
        self.assertIn('stone_beetle', frostspine_mines.get('mobs', []))
        self.assertIn('mountain_stone_golem', frostspine_mines.get('mobs', []))
        self.assertNotIn('stone_golem', frostspine_mines.get('mobs', []))

        profiles = frostspine_mines.get('world_spawn_profiles') or {}
        self.assertEqual(profiles.get('stone_beetle'), {'normal': 2})
        self.assertEqual(profiles.get('mountain_stone_golem'), {'normal': 1, 'elite': 1})

        golem = MOBS['mountain_stone_golem']
        normal_meta = build_open_world_combat_source_metadata(
            source_id='mountain_stone_golem',
            mob_level=golem['level'],
            source_category=None,
            creature_taxonomy=golem.get('creature_taxonomy'),
            encounter_role=golem.get('encounter_role'),
            spawn_profile='normal',
            location_id='frostspine_n6',
        )
        self.assertEqual(normal_meta.source_category, 'open_world_normal')
        self.assertEqual(normal_meta.creature_encounter_class, 'normal')
        self.assertEqual(normal_meta.open_world_encounter_role, 'normal')

        elite_meta = build_open_world_combat_source_metadata(
            source_id='mountain_stone_golem',
            mob_level=golem['level'],
            source_category=None,
            creature_taxonomy=golem.get('creature_taxonomy'),
            spawn_profile='elite',
            location_id='frostspine_n6',
        )
        self.assertEqual(elite_meta.source_category, 'open_world_elite')
        self.assertEqual(elite_meta.creature_encounter_class, 'normal')
        self.assertEqual(elite_meta.open_world_encounter_role, 'elite')

    def test_stub_descriptions_and_phase1_subtypes_are_specific(self):
        self.assertNotIn('World location:', get_location_desc('south_coast_shore', 'en'))
        self.assertNotIn('World location:', get_location_desc('old_mine_entrance', 'en'))
        self.assertIn('shoreline', get_location_desc('south_coast_shore', 'en'))
        self.assertIn('mining stub', get_location_desc('old_mine_entrance', 'en'))
        self.assertEqual(get_item_reward_tags('desert_plant').get('material_subtype'), 'plant')
        self.assertEqual(get_item_reward_tags('reed_bundle').get('material_subtype'), 'reed')
        self.assertEqual(get_item_reward_tags('salt_crystal').get('material_subtype'), 'salt')
        self.assertEqual(get_item_reward_tags('stone_chunk').get('material_subtype'), 'stone')

    def test_phase1_level_max_uses_route_depth_not_blanket_value(self):
        self.assertLess(get_location('westwild_n1').get('level_max'), get_location('westwild_n7').get('level_max'))
        self.assertLess(get_location('sunscar_n1').get('level_max'), get_location('sunscar_n11').get('level_max'))
        self.assertEqual(get_location('old_mine_entrance').get('level_max'), 4)

    def test_alpha_depth_stage_policy_for_full_routes(self):
        for location_id in ('westwild_n1', 'frostspine_n2', 'ashen_n1', 'sunscar_n2', 'mireveil_n1'):
            self.assertEqual(get_route_alpha_depth_stage(location_id), 'soft_entry')

        self.assertEqual(get_route_alpha_depth_stage('ashen_n3b2a1'), 'identity_visible')
        self.assertEqual(get_route_alpha_depth_stage('sunscar_n6'), 'build_testing')
        self.assertEqual(get_route_alpha_depth_stage('westwild_n10'), 'route_exam')

        self.assertEqual(get_route_alpha_depth_stage('hub_westwild'), '')
        self.assertEqual(get_route_alpha_depth_stage('south_coast_shore'), '')
        self.assertEqual(get_route_alpha_depth_stage('old_mine_entrance'), '')

    def test_alpha_depth_stage_metadata_does_not_affect_travel_or_discovery_surface(self):
        westwild = get_location('westwild_n1')
        self.assertIn('westwild_n2', westwild.get('neighbors', []))
        self.assertIn('westwild_n2', westwild.get('canonical_neighbors', []))
        self.assertEqual(westwild.get('alpha_depth_stage'), 'soft_entry')


if __name__ == '__main__':
    unittest.main()
