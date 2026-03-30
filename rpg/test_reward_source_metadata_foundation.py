import os
import tempfile
import unittest

import database
from database import get_connection, init_db
from game.gear_instances import grant_item_to_player
from game.reward_source_metadata import (
    RewardSourceMetadata,
    build_open_world_combat_source_metadata,
    classify_item_reward_family,
    normalize_reward_source_category,
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
        conn.execute(
            '''INSERT INTO items (
                item_id, name, item_type, rarity, req_level,
                req_strength, req_agility, req_intuition, req_wisdom,
                buy_price, stat_bonus_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            ('wolf_pelt', 'wolf_pelt', 'material', 'common', 1, 0, 0, 0, 0, 0, '{}'),
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


if __name__ == '__main__':
    unittest.main()
