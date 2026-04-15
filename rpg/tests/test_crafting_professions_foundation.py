import unittest

from game.crafting_foundation import (
    CRAFTING_PROFESSION_CONTRACTS,
    get_crafting_profession_contract,
    resolve_crafting_material_identity,
)
from game.gathering_foundation import GatherResourceIdentity, GATHER_RESOURCE_IDENTITY_BY_ITEM_ID


class CraftingProfessionsFoundationTests(unittest.TestCase):
    def test_crafting_profession_contracts_are_explicit_and_readable(self):
        self.assertEqual(
            set(CRAFTING_PROFESSION_CONTRACTS.keys()),
            {'heavy_armor', 'medium_armor', 'light_armor', 'blacksmith', 'arcane_engineer', 'alchemy', 'cooking'},
        )
        self.assertIn('metal_weapons', get_crafting_profession_contract('blacksmith').output_families)
        self.assertIn('bows', get_crafting_profession_contract('arcane_engineer').output_families)
        self.assertTrue(get_crafting_profession_contract('alchemy').recipes_are_permanent)

    def test_gather_to_craft_bridge_uses_gather_resource_identity(self):
        ore_identity = resolve_crafting_material_identity('iron_ore')
        self.assertIsNotNone(ore_identity)
        assert ore_identity is not None
        self.assertEqual(ore_identity.origin_channel, 'gathering')
        self.assertEqual(ore_identity.gather_profession_key, 'mining')
        self.assertEqual(ore_identity.bulk_resource_group, 'ore')
        self.assertIn('blacksmith', ore_identity.default_professions)

        hide_identity = resolve_crafting_material_identity('wolf_pelt')
        self.assertIsNotNone(hide_identity)
        assert hide_identity is not None
        self.assertEqual(hide_identity.origin_channel, 'gathering')
        self.assertEqual(hide_identity.gather_profession_key, 'hunting')

    def test_bulk_and_special_ingredients_are_separated(self):
        bulk = resolve_crafting_material_identity('coal')
        special = resolve_crafting_material_identity('stone_core')

        self.assertIsNotNone(bulk)
        self.assertIsNotNone(special)
        assert bulk is not None and special is not None

        self.assertTrue(bulk.is_bulk_resource)
        self.assertFalse(bulk.is_special_ingredient)
        self.assertEqual(bulk.bulk_resource_group, 'fuel')

        self.assertTrue(special.is_special_ingredient)
        self.assertFalse(special.is_bulk_resource)
        self.assertEqual(special.special_ingredient_group, 'core')

    def test_spider_silk_stays_bulk_fiber_via_explicit_mapping(self):
        identity = resolve_crafting_material_identity('spider_silk')
        self.assertIsNotNone(identity)
        assert identity is not None
        self.assertEqual(identity.bulk_resource_group, 'fiber')
        self.assertFalse(identity.is_special_ingredient)

    def test_generic_special_part_fallback_is_not_bulk_fiber(self):
        test_item_id = '__test_special_part_fallback__'
        GATHER_RESOURCE_IDENTITY_BY_ITEM_ID[test_item_id] = GatherResourceIdentity(
            item_id=test_item_id,
            profession_key='hunting',
            resource_family='special_part',
            reward_family='creature_loot',
            base_gather_surface='creature_harvest',
            minimum_profession_level=1,
            min_zone_tier_band=1,
            max_zone_tier_band=10,
            is_basic_resource=False,
        )
        try:
            identity = resolve_crafting_material_identity(test_item_id)
            self.assertIsNotNone(identity)
            assert identity is not None
            self.assertIsNone(identity.bulk_resource_group)
            self.assertTrue(identity.is_special_ingredient)
            self.assertEqual(identity.special_ingredient_group, 'monster_part')
        finally:
            GATHER_RESOURCE_IDENTITY_BY_ITEM_ID.pop(test_item_id, None)

    def test_current_craft_relevant_materials_have_system_identity(self):
        for item_id in (
            'iron_ore',
            'coal',
            'wood_dark',
            'herb_common',
            'spider_silk',
            'wolf_pelt',
            'boar_meat',
            'spider_venom',
            'treant_heart',
            'stone_core',
            'golem_fragment',
        ):
            identity = resolve_crafting_material_identity(item_id)
            self.assertIsNotNone(identity, msg=f'{item_id} should have craft identity')

    def test_foundation_identity_can_be_used_for_recipe_requirements_contract(self):
        recipe_like_requirements = ('iron_ore', 'coal', 'stone_core')
        identities = [resolve_crafting_material_identity(item_id) for item_id in recipe_like_requirements]
        self.assertTrue(all(identity is not None for identity in identities))

        resolved = [identity for identity in identities if identity is not None]
        self.assertTrue(any(identity.is_bulk_resource for identity in resolved))
        self.assertTrue(any(identity.is_special_ingredient for identity in resolved))
        self.assertIn('heavy_armor', resolved[0].default_professions)


if __name__ == '__main__':
    unittest.main()
