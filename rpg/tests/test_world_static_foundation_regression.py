import unittest

from game.i18n import get_location_desc, get_location_name
from game.locations import (
    get_location,
    get_location_neighbors,
    resolve_location_id,
    resolve_region_safe_hub,
)
from game.regen import REGEN_RATES
from handlers.location import get_curated_shop_stock


class WorldStaticFoundationRegressionTests(unittest.TestCase):
    def test_legacy_and_canonical_location_names_ru(self):
        self.assertEqual(get_location_name('village', 'ru'), '🏘️ Пепельная Деревня')
        self.assertEqual(get_location_name('hub_westwild', 'ru'), '🏘️ Элмор')

    def test_legacy_and_canonical_location_names_en_smoke(self):
        self.assertEqual(get_location_name('village', 'en'), '🏘️ Ashen Village')
        self.assertEqual(get_location_name('hub_westwild', 'en'), '🏘️ Elmor')

    def test_legacy_and_canonical_location_descriptions_ru(self):
        self.assertEqual(
            get_location_desc('village', 'ru'),
            'Мирные поля, тихая деревушка на краю тёмного леса. Здесь можно отдохнуть, закупиться и взять квесты.',
        )
        self.assertEqual(
            get_location_desc('hub_westwild', 'ru'),
            'Региональный хаб западных земель. Здесь можно отдохнуть, пополнить припасы и взять контракты.',
        )

    def test_legacy_and_canonical_location_descriptions_en_smoke(self):
        self.assertEqual(
            get_location_desc('village', 'en'),
            'Peaceful fields and a quiet hamlet on the edge of a dark forest. Rest, shop, and take quests here.',
        )
        self.assertEqual(
            get_location_desc('hub_westwild', 'en'),
            'Regional hub of the western wilds for rest, supplies, and contracts.',
        )

    def test_resolve_location_id_aliases(self):
        self.assertEqual(resolve_location_id('village'), 'hub_westwild')
        self.assertEqual(resolve_location_id('dark_forest'), 'westwild_n4')

    def test_get_location_and_neighbors_legacy_vs_canonical(self):
        legacy_location = get_location('village')
        canonical_location = get_location('hub_westwild')

        self.assertIsNotNone(legacy_location)
        self.assertIsNotNone(canonical_location)
        assert legacy_location is not None and canonical_location is not None

        self.assertEqual(legacy_location['id'], 'village')
        self.assertEqual(legacy_location.get('canonical_id'), 'hub_westwild')
        self.assertEqual(canonical_location['id'], 'hub_westwild')
        self.assertNotIn('canonical_id', canonical_location)

        self.assertEqual(get_location_neighbors('village'), ['westwild_n5'])
        self.assertEqual(get_location_neighbors('hub_westwild'), ['westwild_n5'])

    def test_mapped_canonical_locations_keep_region_flavor_tags(self):
        self.assertEqual(
            get_location('hub_westwild').get('region_flavor_tags'),
            ['civilized_frontier', 'ashen_farmland'],
        )
        self.assertEqual(
            get_location('hub_frostspine').get('region_flavor_tags'),
            ['mine_waystation', 'hunter_lodge'],
        )
        self.assertEqual(
            get_location('westwild_n4').get('region_flavor_tags'),
            ['beast_hunting', 'poison_herbs', 'dark_wood'],
        )
        self.assertEqual(
            get_location('old_mine_entrance').get('region_flavor_tags'),
            ['ore_veins', 'construct_ruins', 'goblin_camps'],
        )

    def test_legacy_overlay_locations_keep_region_flavor_tags(self):
        self.assertEqual(
            get_location('village').get('region_flavor_tags'),
            ['civilized_frontier', 'ashen_farmland'],
        )
        self.assertEqual(
            get_location('frontier_outpost').get('region_flavor_tags'),
            ['mine_waystation', 'hunter_lodge'],
        )
        self.assertEqual(
            get_location('dark_forest').get('region_flavor_tags'),
            ['beast_hunting', 'poison_herbs', 'dark_wood'],
        )
        self.assertEqual(
            get_location('old_mines').get('region_flavor_tags'),
            ['ore_veins', 'construct_ruins', 'goblin_camps'],
        )

    def test_resolve_region_safe_hub_by_location(self):
        self.assertEqual(resolve_region_safe_hub(location_id='old_mines'), 'village')
        self.assertEqual(resolve_region_safe_hub(location_id='hub_sunscar'), 'hub_sunscar')

    def test_resolve_region_safe_hub_by_region_and_world(self):
        self.assertEqual(
            resolve_region_safe_hub(region_id='ember_valley', world_id='ashen_continent'),
            'hub_westwild',
        )
        self.assertEqual(
            resolve_region_safe_hub(region_id='iron_pass', world_id='ashen_continent'),
            'hub_frostspine',
        )

    def test_curated_shop_stock_legacy_and_canonical_ids_match(self):
        westwild_legacy = get_curated_shop_stock('village', 20)
        westwild_canonical = get_curated_shop_stock('hub_westwild', 20)
        self.assertEqual(westwild_legacy, westwild_canonical)

        frost_legacy = get_curated_shop_stock('frontier_outpost', 20)
        frost_canonical = get_curated_shop_stock('hub_frostspine', 20)
        self.assertEqual(frost_legacy, frost_canonical)

    def test_safe_hub_regen_profile_parity(self):
        self.assertIn('capital_city', REGEN_RATES)
        self.assertIn('village', REGEN_RATES)

        safe_profile = REGEN_RATES['village']
        safe_hub_ids = (
            'capital_city',
            'hub_westwild',
            'hub_frostspine',
            'hub_ashen_ruins',
            'hub_sunscar',
            'hub_mireveil',
        )
        for location_id in safe_hub_ids:
            self.assertIn(location_id, REGEN_RATES)
            self.assertEqual(REGEN_RATES[location_id], safe_profile)


if __name__ == '__main__':
    unittest.main()
