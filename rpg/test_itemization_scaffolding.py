import unittest
import json

from game.items_data import get_item, get_item_metadata
from game.itemization import (
    ARMOR_ARCHETYPE_BASE_STATS,
    OFFHAND_ARCHETYPE_BASE_STATS,
    RARITY_SECONDARY_COUNT_RULES,
    SECONDARY_STAT_POOLS,
    WEAPON_ARCHETYPE_BASE_STATS,
    get_base_archetype_stats_for_item,
    get_item_archetype_metadata,
    get_secondary_count_budget_for_rarity,
    get_secondary_pool_for_item,
    pool_contains_forbidden_combo,
    roll_secondary_stats_for_item,
)


class ItemizationScaffoldingTests(unittest.TestCase):
    RUNTIME_SUPPORTED_CURATED_BONUS_KEYS = {
        'strength',
        'agility',
        'intuition',
        'vitality',
        'wisdom',
        'luck',
        'max_hp',
        'max_mana',
        'physical_defense',
        'magic_defense',
        'accuracy',
        'evasion',
        'block_chance',
        'magic_power',
        'healing_power',
    }

    def test_non_weapon_items_keep_neutral_weapon_profile(self):
        shield_meta = get_item_archetype_metadata({
            'item_type': 'armor',
            'slot_identity': 'offhand',
            'offhand_profile': 'shield',
            'weapon_type': 'melee',
        })
        chest_meta = get_item_archetype_metadata({'item_type': 'armor', 'slot_identity': 'chest', 'armor_class': 'medium'})
        accessory_meta = get_item_archetype_metadata({'item_type': 'accessory', 'slot_identity': 'ring'})
        material_meta = get_item_archetype_metadata({'item_type': 'material'})

        self.assertEqual(shield_meta['weapon_profile'], 'unarmed')
        self.assertEqual(chest_meta['weapon_profile'], 'unarmed')
        self.assertEqual(accessory_meta['weapon_profile'], 'unarmed')
        self.assertEqual(material_meta['weapon_profile'], 'unarmed')

    def test_weapon_items_still_normalize_weapon_profile(self):
        explicit_profile_meta = get_item_archetype_metadata({'item_type': 'weapon', 'weapon_type': 'magic', 'weapon_profile': 'magic_staff'})
        fallback_profile_meta = get_item_archetype_metadata({'item_type': 'weapon', 'weapon_type': 'ranged'})

        self.assertEqual(explicit_profile_meta['weapon_profile'], 'magic_staff')
        self.assertEqual(fallback_profile_meta['weapon_profile'], 'bow')

    def test_armor_secondary_pools_follow_identity_rules(self):
        heavy_pool = get_secondary_pool_for_item({'item_type': 'armor', 'armor_class': 'heavy', 'slot_identity': 'chest'})
        medium_pool = get_secondary_pool_for_item({'item_type': 'armor', 'armor_class': 'medium', 'slot_identity': 'chest'})
        light_pool = get_secondary_pool_for_item({'item_type': 'armor', 'armor_class': 'light', 'slot_identity': 'chest'})

        self.assertEqual(heavy_pool, SECONDARY_STAT_POOLS['armor_heavy'])
        self.assertIn('block_chance', heavy_pool)
        self.assertNotIn('magic_power', heavy_pool)

        self.assertEqual(medium_pool, SECONDARY_STAT_POOLS['armor_medium'])
        self.assertIn('evasion', medium_pool)
        self.assertNotIn('healing_power', medium_pool)

        self.assertEqual(light_pool, SECONDARY_STAT_POOLS['armor_light'])
        self.assertIn('magic_power', light_pool)
        self.assertNotIn('aggro_power', light_pool)

    def test_offhand_pools_keep_role_identity(self):
        shield_pool = get_secondary_pool_for_item({'item_type': 'armor', 'slot_identity': 'offhand', 'offhand_profile': 'shield'})
        focus_pool = get_secondary_pool_for_item({'item_type': 'armor', 'slot_identity': 'offhand', 'offhand_profile': 'focus'})
        censer_pool = get_secondary_pool_for_item({'item_type': 'armor', 'slot_identity': 'offhand', 'offhand_profile': 'censer'})

        self.assertIn('block_chance', shield_pool)
        self.assertNotIn('magic_power', shield_pool)

        self.assertIn('magic_power', focus_pool)
        self.assertIn('max_mana', focus_pool)
        self.assertNotIn('aggro_power', focus_pool)

        self.assertIn('healing_power', censer_pool)
        self.assertIn('buff_power', censer_pool)
        self.assertNotIn('physical_penetration', censer_pool)

    def test_accessories_are_flexible_but_bounded(self):
        accessory_pool = get_secondary_pool_for_item({'item_type': 'accessory', 'slot_identity': 'ring'})
        self.assertEqual(accessory_pool, SECONDARY_STAT_POOLS['accessory'])
        self.assertIn('physical_power', accessory_pool)
        self.assertIn('magic_power', accessory_pool)
        self.assertIn('healing_power', accessory_pool)
        self.assertNotIn('armor_break', accessory_pool)
        self.assertNotIn('aggro_power', accessory_pool)

    def test_rarity_secondary_budgets_include_unique(self):
        self.assertEqual(get_secondary_count_budget_for_rarity('common'), 0)
        self.assertEqual(get_secondary_count_budget_for_rarity('uncommon'), 1)
        self.assertEqual(get_secondary_count_budget_for_rarity('rare'), 2)
        self.assertEqual(get_secondary_count_budget_for_rarity('epic'), 3)
        self.assertEqual(get_secondary_count_budget_for_rarity('legendary'), 4)
        self.assertEqual(get_secondary_count_budget_for_rarity('unique'), 4)
        self.assertEqual(set(RARITY_SECONDARY_COUNT_RULES.keys()), {'common', 'uncommon', 'rare', 'epic', 'legendary', 'unique'})

    def test_hybrid_categories_do_not_roll_forbidden_all_in_one_combos(self):
        heavy_forbidden = {'magic_power', 'healing_power', 'crit_chance'}
        light_forbidden = {'block_chance', 'aggro_power', 'physical_power'}

        self.assertFalse(pool_contains_forbidden_combo(SECONDARY_STAT_POOLS['armor_heavy'], heavy_forbidden))
        self.assertFalse(pool_contains_forbidden_combo(SECONDARY_STAT_POOLS['armor_light'], light_forbidden))

    def test_base_archetype_templates_exist_for_key_categories(self):
        sword_stats = get_base_archetype_stats_for_item({'item_type': 'weapon', 'weapon_profile': 'sword_1h'})
        shield_stats = get_base_archetype_stats_for_item({'item_type': 'armor', 'slot_identity': 'offhand', 'offhand_profile': 'shield'})
        heavy_stats = get_base_archetype_stats_for_item({'item_type': 'armor', 'slot_identity': 'chest', 'armor_class': 'heavy'})

        self.assertEqual(sword_stats, WEAPON_ARCHETYPE_BASE_STATS['sword_1h'])
        self.assertEqual(shield_stats, OFFHAND_ARCHETYPE_BASE_STATS['shield'])
        self.assertEqual(heavy_stats, ARMOR_ARCHETYPE_BASE_STATS['heavy'])

    def test_existing_item_read_paths_remain_backward_compatible(self):
        shield_item = get_item('iron_shield')
        self.assertEqual(shield_item['item_id'], 'iron_shield')
        self.assertIn('stat_bonus_json', shield_item)

        metadata = get_item_metadata('iron_shield')
        self.assertEqual(metadata['slot_identity'], 'offhand')
        self.assertEqual(metadata['offhand_profile'], 'shield')
        self.assertEqual(metadata['rarity'], 'common')

    def test_curated_offhands_have_expected_normalized_identity(self):
        shield_meta = get_item_metadata('warden_kite_shield')
        focus_meta = get_item_metadata('azure_focus_prism')
        censer_meta = get_item_metadata('choir_censer')

        self.assertEqual(shield_meta['slot_identity'], 'offhand')
        self.assertEqual(shield_meta['offhand_profile'], 'shield')
        self.assertEqual(shield_meta['weapon_profile'], 'unarmed')

        self.assertEqual(focus_meta['slot_identity'], 'offhand')
        self.assertEqual(focus_meta['offhand_profile'], 'focus')
        self.assertEqual(focus_meta['weapon_profile'], 'unarmed')

        self.assertEqual(censer_meta['slot_identity'], 'offhand')
        self.assertEqual(censer_meta['offhand_profile'], 'censer')
        self.assertEqual(censer_meta['weapon_profile'], 'unarmed')

    def test_curated_armor_items_match_class_identity(self):
        heavy_meta = get_item_metadata('militia_cuirass')
        medium_meta = get_item_metadata('tracker_jacket')
        light_meta = get_item_metadata('acolyte_robe')

        self.assertEqual(heavy_meta['armor_class'], 'heavy')
        self.assertEqual(medium_meta['armor_class'], 'medium')
        self.assertEqual(light_meta['armor_class'], 'light')

        heavy_pool = set(get_secondary_pool_for_item(get_item('militia_cuirass')))
        light_pool = set(get_secondary_pool_for_item(get_item('acolyte_robe')))

        heavy_stats = set(json.loads(get_item('militia_cuirass')['stat_bonus_json']).keys())
        light_stats = set(json.loads(get_item('acolyte_robe')['stat_bonus_json']).keys())
        self.assertTrue(heavy_stats.issubset(heavy_pool))
        self.assertTrue(light_stats.issubset(light_pool))

    def test_accessory_slice_stays_flexible_but_bounded(self):
        accessory_pool = set(SECONDARY_STAT_POOLS['accessory'])
        for item_id in ('band_of_precision', 'ring_of_quiet_mind', 'amulet_of_kindled_prayer', 'dual_path_loop'):
            metadata = get_item_metadata(item_id)
            self.assertIn(metadata['slot_identity'], ('ring', 'amulet'))
            bonuses = set(json.loads(get_item(item_id)['stat_bonus_json']).keys())
            self.assertTrue(bonuses.issubset(accessory_pool))
            self.assertNotIn('aggro_power', bonuses)
            self.assertNotIn('armor_break', bonuses)

    def test_curated_items_respect_rarity_secondary_budget(self):
        curated_ids = (
            'oak_guard_shield',
            'warden_kite_shield',
            'apprentice_focus_orb',
            'azure_focus_prism',
            'novice_censer',
            'choir_censer',
            'militia_cuirass',
            'tracker_jacket',
            'acolyte_robe',
            'band_of_precision',
            'ring_of_quiet_mind',
            'amulet_of_kindled_prayer',
            'dual_path_loop',
        )
        for item_id in curated_ids:
            item = get_item(item_id)
            budget = get_secondary_count_budget_for_rarity(item['rarity'])
            actual = len(json.loads(item['stat_bonus_json']).keys())
            self.assertLessEqual(actual, budget, msg=f'{item_id} exceeds rarity budget')

    def test_curated_items_do_not_expose_inert_bonus_keys(self):
        curated_ids = (
            'oak_guard_shield',
            'warden_kite_shield',
            'apprentice_focus_orb',
            'azure_focus_prism',
            'novice_censer',
            'choir_censer',
            'militia_cuirass',
            'tracker_jacket',
            'acolyte_robe',
            'band_of_precision',
            'ring_of_quiet_mind',
            'amulet_of_kindled_prayer',
            'dual_path_loop',
        )
        for item_id in curated_ids:
            bonuses = json.loads(get_item(item_id)['stat_bonus_json'])
            self.assertTrue(
                set(bonuses.keys()).issubset(self.RUNTIME_SUPPORTED_CURATED_BONUS_KEYS),
                msg=f'{item_id} contains inert runtime bonus keys: {set(bonuses.keys()) - self.RUNTIME_SUPPORTED_CURATED_BONUS_KEYS}',
            )

    def test_each_curated_item_has_runtime_mechanical_value(self):
        curated_ids = (
            'oak_guard_shield',
            'warden_kite_shield',
            'apprentice_focus_orb',
            'azure_focus_prism',
            'novice_censer',
            'choir_censer',
            'militia_cuirass',
            'tracker_jacket',
            'acolyte_robe',
            'band_of_precision',
            'ring_of_quiet_mind',
            'amulet_of_kindled_prayer',
            'dual_path_loop',
        )
        for item_id in curated_ids:
            bonuses = json.loads(get_item(item_id)['stat_bonus_json'])
            metadata = get_item_metadata(item_id)
            has_runtime_bonus = len(bonuses) > 0
            has_identity_runtime = metadata.get('slot_identity') in {'weapon', 'offhand', 'chest'}
            self.assertTrue(
                has_runtime_bonus or has_identity_runtime,
                msg=f'{item_id} has neither runtime bonus nor runtime identity effect',
            )

    def test_secondary_roll_helper_is_deterministic_with_injected_rng(self):
        import random

        item = {'item_type': 'armor', 'slot_identity': 'chest', 'armor_class': 'medium', 'rarity': 'rare'}
        rng_a = random.Random(42)
        rng_b = random.Random(42)

        roll_a = roll_secondary_stats_for_item(item, rng=rng_a)
        roll_b = roll_secondary_stats_for_item(item, rng=rng_b)

        self.assertEqual(len(roll_a), 2)
        self.assertEqual(roll_a, roll_b)
        self.assertTrue(set(roll_a).issubset(set(SECONDARY_STAT_POOLS['armor_medium'])))


if __name__ == '__main__':
    unittest.main()
