import unittest

from game.i18n import get_location_desc, get_location_name
from game.locations import (
    _WORLD_GRAPH,
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

        self.assertEqual(get_location_neighbors('village'), ['dark_forest', 'old_mines', 'frontier_outpost'])
        self.assertEqual(get_location_neighbors('hub_westwild'), ['westwild_n5'])

    def test_full_canonical_graph_is_live_topology(self):
        for location_id, canonical_neighbors in _WORLD_GRAPH.items():
            with self.subTest(location_id=location_id):
                location = get_location(location_id)
                self.assertIsNotNone(location)
                self.assertEqual(location.get('canonical_neighbors'), canonical_neighbors)
                self.assertEqual(get_location_neighbors(location_id), canonical_neighbors)

    def test_all_canonical_locations_are_reachable_from_capital(self):
        visited = set()
        pending = ['capital_city']
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            pending.extend(
                neighbor_id
                for neighbor_id in get_location_neighbors(current)
                if neighbor_id not in visited
            )

        self.assertEqual(visited, set(_WORLD_GRAPH))

    def test_full_graph_required_cross_links_are_live(self):
        required_edges = [
            ('westwild_n6', 'mireveil_n6'),
            ('mireveil_n6', 'frostspine_n6'),
            ('frostspine_n6', 'ashen_n3b1'),
            ('ashen_n3b1', 'sunscar_n6'),
            ('sunscar_n6', 'westwild_n6'),
            ('westwild_n8', 'mireveil_n8'),
            ('mireveil_n8', 'frostspine_n8'),
            ('frostspine_n8', 'ashen_n3b2'),
            ('ashen_n3b2', 'sunscar_n8'),
            ('sunscar_n8', 'westwild_n8'),
            ('westwild_n9', 'mireveil_n9'),
            ('mireveil_n9', 'frostspine_n9'),
            ('frostspine_n9', 'ashen_n3b2a1'),
            ('ashen_n3b2a1', 'sunscar_n9'),
            ('sunscar_n9', 'westwild_n9'),
            ('westwild_n10', 'frostspine_n10'),
            ('mireveil_n10', 'ashen_n3b2b1'),
        ]
        for left, right in required_edges:
            with self.subTest(edge=f'{left}<->{right}'):
                self.assertIn(right, get_location_neighbors(left))
                self.assertIn(left, get_location_neighbors(right))

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

    def test_capital_city_shop_has_usable_starter_stock(self):
        stock = get_curated_shop_stock('capital_city', 1)
        item_ids = {row['item_id'] for row in stock}

        self.assertGreaterEqual(len(stock), 4)
        self.assertIn('wooden_sword', item_ids)
        self.assertIn('health_potion_small', item_ids)
        for row in stock:
            self.assertEqual(row['level_min'], 1)
            self.assertGreater(row['price'], 0)

    def test_curated_shop_stock_legacy_and_canonical_ids_match(self):
        westwild_legacy = get_curated_shop_stock('village', 20)
        westwild_canonical = get_curated_shop_stock('hub_westwild', 20)
        self.assertEqual(westwild_legacy, westwild_canonical)

        frost_legacy = get_curated_shop_stock('frontier_outpost', 20)
        frost_canonical = get_curated_shop_stock('hub_frostspine', 20)
        self.assertEqual(frost_legacy, frost_canonical)

    def test_teleport_metadata_remains_disabled_while_teleport_phase_is_skipped(self):
        self.assertFalse(get_location('capital_city').get('teleport_enabled'))
        self.assertIsNone(get_location('capital_city').get('teleport_group'))
        self.assertFalse(get_location('hub_westwild').get('teleport_enabled'))

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
