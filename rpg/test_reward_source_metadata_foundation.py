import os
import tempfile
import unittest

import database
from database import get_connection, init_db
from game.gear_instances import grant_item_to_player
from game.enhancement_material_routing import (
    get_enhancement_material_tier,
    resolve_enhancement_material_routing,
)
from game.reward_source_metadata import (
    RewardSourceMetadata,
    build_open_world_combat_source_metadata,
    classify_item_reward_family,
    normalize_reward_source_category,
    resolve_content_tier_band,
    resolve_allowed_reward_families,
)


class RewardSourceMetadataFoundationTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self._tmpdir.name, 'test_game.db')
        init_db()

        conn = get_connection()
        conn.execute(
            '''INSERT INTO players (
                telegram_id, username, name, level, hp, max_hp, mana, max_mana,
                strength, agility, intuition, vitality, wisdom, luck
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (333, 'meta', 'MetaTester', 10, 100, 100, 50, 50, 5, 5, 5, 5, 5, 5),
        )
        for item_row in (
            ('wolf_pelt', 'wolf_pelt', 'material', 'common', 1, 0, 0, 0, 0, 0, '{}'),
            ('power_essence', 'power_essence', 'material', 'rare', 1, 0, 0, 0, 0, 0, '{}'),
        ):
            conn.execute(
                '''INSERT INTO items (
                    item_id, name, item_type, rarity, req_level,
                    req_strength, req_agility, req_intuition, req_wisdom,
                    buy_price, stat_bonus_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                item_row,
            )
        conn.commit()
        conn.close()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def test_source_categories_expose_expected_reward_families(self):
        open_world = RewardSourceMetadata(
            source_category='open_world_normal',
            content_tier=5,
            content_identity='forest_wolf',
        )
        world_boss = RewardSourceMetadata(
            source_category='world_boss',
            content_tier=60,
            content_identity='ash_titan',
        )
        quest = RewardSourceMetadata(
            source_category='quest_reward',
            content_tier=5,
            content_identity='quest_clean_kill',
        )

        open_world_families = set(resolve_allowed_reward_families(open_world))
        world_boss_families = set(resolve_allowed_reward_families(world_boss))
        quest_families = set(resolve_allowed_reward_families(quest))

        self.assertIn('creature_loot', open_world_families)
        self.assertNotIn('prestige_or_apex', open_world_families)
        self.assertIn('prestige_or_apex', world_boss_families)
        self.assertIn('quest_tagged', quest_families)

    def test_item_family_classifier_covers_foundation_channels(self):
        self.assertEqual(classify_item_reward_family('wooden_sword'), 'gear')
        self.assertEqual(classify_item_reward_family('enhance_shard'), 'enhancement_material')
        self.assertEqual(classify_item_reward_family('wolf_pelt'), 'creature_loot')
        self.assertEqual(classify_item_reward_family('herb_common'), 'gathering_material')
        self.assertEqual(classify_item_reward_family('spider_venom'), 'reagent')
        self.assertEqual(classify_item_reward_family('coal'), 'crafting_material')

    def test_grant_item_respects_source_family_allowlist_when_metadata_is_provided(self):
        quest_meta = RewardSourceMetadata(
            source_category='quest_reward',
            content_tier=3,
            content_identity='starter_quest',
        )
        no_drop = grant_item_to_player(
            333,
            'wolf_pelt',
            quantity=1,
            source='quest',
            source_level=3,
            source_metadata=quest_meta,
        )
        self.assertEqual(no_drop, {'gear_instances_created': 0, 'stackable_added': 0})

        combat_meta = build_open_world_combat_source_metadata(
            source_id='forest_wolf',
            mob_level=2,
            source_category='open_world_normal',
        )
        dropped = grant_item_to_player(
            333,
            'wolf_pelt',
            quantity=1,
            source='mob_drop',
            source_level=2,
            source_metadata=combat_meta,
        )
        self.assertEqual(dropped, {'gear_instances_created': 0, 'stackable_added': 1})

    def test_unknown_source_category_normalizes_to_open_world_normal(self):
        normalized = normalize_reward_source_category('open_world_typo')
        self.assertEqual(normalized, 'open_world_normal')

        fallback_meta = build_open_world_combat_source_metadata(
            source_id='forest_wolf',
            mob_level=2,
            source_category='open_world_typo',
        )
        self.assertEqual(fallback_meta.source_category, 'open_world_normal')

    def test_unknown_source_category_does_not_produce_empty_allowlist(self):
        typo_meta = RewardSourceMetadata(
            source_category='open_world_typo',  # type: ignore[arg-type]
            content_tier=5,
            content_identity='forest_wolf',
        )
        families = resolve_allowed_reward_families(typo_meta)
        self.assertIn('creature_loot', families)
        self.assertTrue(len(families) > 0)


    def test_enhancement_material_tiers_are_explicitly_mapped(self):
        self.assertEqual(get_enhancement_material_tier('enhance_shard'), 1)
        self.assertEqual(get_enhancement_material_tier('enhancement_crystal'), 2)
        self.assertEqual(get_enhancement_material_tier('power_essence'), 3)
        self.assertEqual(get_enhancement_material_tier('ashen_core'), 4)
        self.assertIsNone(get_enhancement_material_tier('wolf_pelt'))

    def test_enhancement_routing_resolver_distinguishes_normal_fallback_and_disallowed(self):
        normal = resolve_enhancement_material_routing('enhance_shard', 'open_world_normal')
        fallback = resolve_enhancement_material_routing('power_essence', 'open_world_elite')
        disallowed = resolve_enhancement_material_routing('power_essence', 'open_world_normal')

        self.assertIsNotNone(normal)
        self.assertEqual(normal.status, 'normal')
        self.assertTrue(normal.is_allowed)

        self.assertIsNotNone(fallback)
        self.assertEqual(fallback.status, 'temporary_fallback')
        self.assertTrue(fallback.is_allowed)

        self.assertIsNotNone(disallowed)
        self.assertEqual(disallowed.status, 'disallowed')
        self.assertFalse(disallowed.is_allowed)

    def test_live_grant_flow_blocks_disallowed_enhancement_routing(self):
        combat_meta = RewardSourceMetadata(
            source_category='open_world_normal',
            content_tier=1,
            content_identity='forest_wolf',
        )

        blocked = grant_item_to_player(
            333,
            'power_essence',
            quantity=1,
            source='mob_drop',
            source_level=2,
            source_metadata=combat_meta,
        )
        self.assertEqual(blocked, {'gear_instances_created': 0, 'stackable_added': 0})

        conn = get_connection()
        row = conn.execute(
            'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (333, 'power_essence'),
        ).fetchone()
        conn.close()
        self.assertIsNone(row)

    def test_live_grant_flow_allows_temporary_fallback_enhancement_routing(self):
        elite_meta = RewardSourceMetadata(
            source_category='open_world_elite',
            content_tier=1,
            content_identity='stone_golem',
        )

        dropped = grant_item_to_player(
            333,
            'power_essence',
            quantity=1,
            source='mob_drop',
            source_level=8,
            source_metadata=elite_meta,
        )
        self.assertEqual(dropped, {'gear_instances_created': 0, 'stackable_added': 1})

    def test_content_tier_is_normalized_to_tier_bands(self):
        self.assertEqual(resolve_content_tier_band(1), 1)
        self.assertEqual(resolve_content_tier_band(10), 1)
        self.assertEqual(resolve_content_tier_band(11), 2)
        self.assertEqual(resolve_content_tier_band(55), 6)
        self.assertEqual(resolve_content_tier_band(100), 10)
        self.assertEqual(resolve_content_tier_band(145), 10)

    def test_combat_metadata_contains_taxonomy_identity(self):
        source_meta = build_open_world_combat_source_metadata(
            source_id='forest_spider',
            mob_level=3,
            source_category=None,
            creature_taxonomy={
                'body_type': 'arachnid',
                'special_trait': 'venomous',
                'encounter_class': 'elite',
            },
        )
        self.assertEqual(source_meta.source_category, 'open_world_elite')
        self.assertEqual(source_meta.content_tier, 1)
        self.assertEqual(source_meta.creature_body_type, 'arachnid')
        self.assertEqual(source_meta.creature_special_trait, 'venomous')
        self.assertEqual(source_meta.creature_encounter_class, 'elite')
        self.assertIn('venom_gland', source_meta.creature_loot_identity)
        self.assertIn('special_part', source_meta.creature_loot_identity)


if __name__ == '__main__':
    unittest.main()
