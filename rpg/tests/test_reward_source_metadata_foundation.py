import os
import tempfile
import unittest
from unittest.mock import patch

import database
from database import get_connection, init_db
from game.gear_instances import grant_item_to_player
from game.enhancement_material_routing import (
    get_enhancement_material_tier,
    resolve_enhancement_material_routing,
)
from game.dungeon_reward_framework import build_dungeon_reward_surface_profile
from game.open_world_reward_pools import (
    build_open_world_reward_pool_profile,
    clamp_rarity_to_quality_floor,
    is_gear_item_allowed_for_open_world_content_identity,
    is_item_tier_band_allowed_for_bounds,
)
from game.reward_source_metadata import (
    RewardSourceMetadata,
    build_dungeon_combat_source_metadata,
    build_open_world_combat_source_metadata,
    classify_item_reward_family,
    normalize_reward_source_category,
    resolve_content_tier_band,
    resolve_allowed_reward_families,
)
from game.reward_policies import (
    REWARD_FAMILIES_BY_SOURCE,
    resolve_content_tier_band as resolve_content_tier_band_policy,
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
            ('tracker_jacket', 'tracker_jacket', 'armor', 'uncommon', 4, 0, 0, 0, 0, 0, '{}'),
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

    def test_spawn_profile_maps_open_world_source_identity_when_source_is_baseline(self):
        normal_meta = build_open_world_combat_source_metadata(
            source_id='forest_wolf',
            mob_level=2,
            source_category='open_world_normal',
            spawn_profile='normal',
            creature_taxonomy={
                'body_type': 'beast',
                'special_trait': 'predator',
                'encounter_class': 'normal',
            },
        )
        elite_meta = build_open_world_combat_source_metadata(
            source_id='forest_wolf',
            mob_level=2,
            source_category='open_world_normal',
            spawn_profile='elite',
            creature_taxonomy={
                'body_type': 'beast',
                'special_trait': 'predator',
                'encounter_class': 'normal',
            },
        )
        rare_meta = build_open_world_combat_source_metadata(
            source_id='forest_wolf',
            mob_level=2,
            source_category='open_world_normal',
            spawn_profile='rare',
            creature_taxonomy={
                'body_type': 'beast',
                'special_trait': 'predator',
                'encounter_class': 'normal',
            },
        )

        self.assertEqual(normal_meta.source_category, 'open_world_normal')
        self.assertEqual(elite_meta.source_category, 'open_world_elite')
        self.assertEqual(rare_meta.source_category, 'open_world_rare_spawn')
        self.assertEqual(normal_meta.quality_floor_rarity, 'common')
        self.assertEqual(elite_meta.quality_floor_rarity, 'uncommon')
        self.assertEqual(rare_meta.quality_floor_rarity, 'rare')

    def test_spawn_profile_unknown_falls_back_to_normal_source_identity(self):
        meta = build_open_world_combat_source_metadata(
            source_id='forest_wolf',
            mob_level=2,
            source_category='open_world_normal',
            spawn_profile='legacy_unknown',
            creature_taxonomy={
                'body_type': 'beast',
                'special_trait': 'predator',
                'encounter_class': 'normal',
            },
        )
        self.assertEqual(meta.source_category, 'open_world_normal')
        self.assertEqual(meta.quality_floor_rarity, 'common')

    def test_open_world_metadata_carries_optional_spawn_identity(self):
        meta = build_open_world_combat_source_metadata(
            source_id='forest_wolf',
            mob_level=2,
            source_category='open_world_normal',
            spawn_profile='rare',
            spawn_identity='dark_forest:forest_wolf:greyfang',
        )
        self.assertEqual(meta.open_world_spawn_identity, 'dark_forest:forest_wolf:greyfang')


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

    def test_content_tier_band_helper_has_single_source_of_truth(self):
        self.assertIs(resolve_content_tier_band, resolve_content_tier_band_policy)

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

    def test_open_world_pool_profile_contract_has_surface_identity_and_quality_floor(self):
        profile = build_open_world_reward_pool_profile(
            source_category='open_world_regional_boss',
            source_id='dark_treant',
            mob_level=5,
            location_id='dark_forest',
        )
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.reward_pool_profile, 'open_world_regional_boss_surface')
        self.assertEqual(profile.world_identity, 'ashen_continent')
        self.assertIsNone(profile.macro_region_identity)
        self.assertEqual(profile.region_identity, 'ember_valley')
        self.assertEqual(profile.zone_identity, 'dark_forest')
        self.assertEqual(profile.zone_role, 'regional_boss')
        self.assertEqual(profile.encounter_role, 'regional_boss')
        self.assertIn('poison_herbs', profile.region_flavor_tags)
        self.assertEqual(profile.linked_dungeon_id, 'rootbound_hollow')
        self.assertEqual(profile.world_boss_governance_id, 'ember_valley_world_boss')
        self.assertEqual(profile.future_pvp_ruleset_id, 'open_world_frontier')
        self.assertEqual(profile.content_identity, 'dark_treant')
        self.assertEqual(profile.quality_floor, 'epic')
        self.assertIn('gear', profile.allowed_reward_families)
        self.assertEqual(
            profile.allowed_reward_families,
            REWARD_FAMILIES_BY_SOURCE['open_world_regional_boss'],
        )

    def test_quality_floor_is_differentiated_between_open_world_surfaces(self):
        self.assertEqual(clamp_rarity_to_quality_floor('common', 'common'), 'common')
        self.assertEqual(clamp_rarity_to_quality_floor('common', 'uncommon'), 'uncommon')
        self.assertEqual(clamp_rarity_to_quality_floor('uncommon', 'rare'), 'rare')
        self.assertEqual(clamp_rarity_to_quality_floor('rare', 'epic'), 'epic')

    def test_bounded_tier_band_rules_block_out_of_band_items(self):
        self.assertTrue(is_item_tier_band_allowed_for_bounds(item_level=8, tier_band_min=1, tier_band_max=2))
        self.assertFalse(is_item_tier_band_allowed_for_bounds(item_level=95, tier_band_min=1, tier_band_max=2))

    def test_bounded_content_identity_blocks_gear_not_from_current_source(self):
        self.assertTrue(
            is_gear_item_allowed_for_open_world_content_identity(
                item_id='iron_sword',
                source_id='dark_treant',
            )
        )
        self.assertFalse(
            is_gear_item_allowed_for_open_world_content_identity(
                item_id='iron_shield',
                source_id='dark_treant',
            )
        )

    def test_live_grant_flow_uses_open_world_quality_floor_for_harder_sources(self):
        from game.gear_instances import _create_generated_gear_instance

        elite_meta = build_open_world_combat_source_metadata(
            source_id='goblin_miner',
            mob_level=4,
            source_category='open_world_elite',
            location_id='old_mines',
        )
        with patch('game.gear_instances.roll_generated_rarity', return_value='common'):
            instance_id = _create_generated_gear_instance(
                333,
                'tracker_jacket',
                source='mob_drop',
                source_level=4,
                source_metadata=elite_meta,
            )

        conn = get_connection()
        row = conn.execute('SELECT rarity FROM gear_instances WHERE id=?', (instance_id,)).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['rarity'], 'uncommon')

    def test_open_world_metadata_exposes_region_zone_and_future_linkage_hooks(self):
        source_meta = build_open_world_combat_source_metadata(
            source_id='goblin_miner',
            mob_level=4,
            source_category='open_world_elite',
            creature_taxonomy={
                'body_type': 'humanoid',
                'special_trait': 'armored',
                'encounter_class': 'elite',
            },
            location_id='old_mines',
        )
        self.assertEqual(source_meta.open_world_world_identity, 'ashen_continent')
        self.assertIsNone(source_meta.open_world_macro_region_identity)
        self.assertEqual(source_meta.open_world_region_identity, 'ember_valley')
        self.assertEqual(source_meta.open_world_zone_identity, 'old_mines')
        self.assertEqual(source_meta.open_world_zone_role, 'elite')
        self.assertEqual(source_meta.open_world_encounter_role, 'elite')
        self.assertEqual(source_meta.future_dungeon_link_id, 'amber_catacombs')
        self.assertEqual(source_meta.future_world_boss_governance_id, 'ember_valley_world_boss')
        self.assertEqual(source_meta.open_world_future_pvp_ruleset_id, 'open_world_frontier')
        self.assertIn('ore_veins', source_meta.open_world_region_flavor_tags)

    def test_explicit_encounter_role_maps_to_rare_spawn_even_with_normal_taxonomy(self):
        source_meta = build_open_world_combat_source_metadata(
            source_id='synthetic_rare_spawn',
            mob_level=24,
            source_category='open_world_rare_spawn',
            creature_taxonomy={
                'body_type': 'beast',
                'special_trait': 'predator',
                'encounter_class': 'normal',
            },
            encounter_role='rare_spawn',
            location_id='dark_forest',
        )
        self.assertEqual(source_meta.source_category, 'open_world_rare_spawn')
        self.assertEqual(source_meta.open_world_encounter_role, 'rare_spawn')
        self.assertEqual(source_meta.open_world_zone_role, 'rare_spawn')

    def test_dungeon_source_metadata_contains_identity_band_and_reward_profile(self):
        dungeon_meta = build_dungeon_combat_source_metadata(
            dungeon_id='amber_catacombs',
            encounter_identity='amber_guardian',
            mob_level=38,
            source_category='dungeon_elite',
            creature_taxonomy={
                'body_type': 'construct',
                'special_trait': 'armored',
                'encounter_class': 'elite',
            },
        )
        self.assertEqual(dungeon_meta.source_category, 'dungeon_elite')
        self.assertEqual(dungeon_meta.dungeon_id, 'amber_catacombs')
        self.assertEqual(dungeon_meta.dungeon_encounter_identity, 'amber_guardian')
        self.assertEqual(dungeon_meta.dungeon_reward_profile_identity, 'dungeon_elite_surface')
        self.assertEqual(dungeon_meta.content_tier, 4)
        self.assertEqual(dungeon_meta.content_tier_band_min, 3)
        self.assertEqual(dungeon_meta.content_tier_band_max, 5)

    def test_invalid_dungeon_surface_falls_back_to_dungeon_trash_not_open_world(self):
        profile = build_dungeon_reward_surface_profile(
            source_category='dungeon_typo_surface',
            dungeon_id='amber_catacombs',
            encounter_identity='amber_guardian',
            mob_level=38,
        )
        self.assertEqual(profile.source_category, 'dungeon_trash')
        self.assertEqual(profile.reward_profile_identity, 'dungeon_trash_surface')

        meta = build_dungeon_combat_source_metadata(
            dungeon_id='amber_catacombs',
            encounter_identity='amber_guardian',
            mob_level=38,
            source_category='dungeon_typo_surface',
        )
        self.assertEqual(meta.source_category, 'dungeon_trash')
        self.assertEqual(meta.dungeon_reward_profile_identity, 'dungeon_trash_surface')
        self.assertEqual(meta.dungeon_payoff_role, 'baseline_dungeon_feed')
        self.assertFalse(meta.dungeon_recipe_hook_enabled)

    def test_dungeon_surface_roles_are_differentiated_between_trash_elite_and_boss(self):
        trash = build_dungeon_combat_source_metadata(
            dungeon_id='amber_catacombs',
            encounter_identity='catacomb_rat',
            mob_level=34,
            source_category='dungeon_trash',
        )
        elite = build_dungeon_combat_source_metadata(
            dungeon_id='amber_catacombs',
            encounter_identity='amber_guardian',
            mob_level=36,
            source_category='dungeon_elite',
        )
        boss = build_dungeon_combat_source_metadata(
            dungeon_id='amber_catacombs',
            encounter_identity='amber_overseer',
            mob_level=40,
            source_category='dungeon_boss',
        )

        self.assertEqual(trash.dungeon_payoff_role, 'baseline_dungeon_feed')
        self.assertEqual(elite.dungeon_payoff_role, 'structured_progression_step')
        self.assertEqual(boss.dungeon_payoff_role, 'primary_dungeon_payoff')
        self.assertEqual(trash.quality_floor_rarity, 'common')
        self.assertEqual(elite.quality_floor_rarity, 'uncommon')
        self.assertEqual(boss.quality_floor_rarity, 'rare')

    def test_material_3_is_dungeon_primary_in_live_routing_flow(self):
        dungeon_elite_meta = build_dungeon_combat_source_metadata(
            dungeon_id='amber_catacombs',
            encounter_identity='amber_guardian',
            mob_level=40,
            source_category='dungeon_elite',
        )
        open_world_meta = build_open_world_combat_source_metadata(
            source_id='forest_wolf',
            mob_level=2,
            source_category='open_world_normal',
        )

        allowed = grant_item_to_player(
            333,
            'power_essence',
            quantity=1,
            source='mob_drop',
            source_level=40,
            source_metadata=dungeon_elite_meta,
        )
        blocked = grant_item_to_player(
            333,
            'power_essence',
            quantity=1,
            source='mob_drop',
            source_level=2,
            source_metadata=open_world_meta,
        )

        self.assertEqual(dungeon_elite_meta.power_essence_role, 'meaningful_layer')
        self.assertEqual(allowed, {'gear_instances_created': 0, 'stackable_added': 1})
        self.assertEqual(blocked, {'gear_instances_created': 0, 'stackable_added': 0})

    def test_dungeon_recipe_and_reagent_hooks_are_exposed_by_surface(self):
        trash = build_dungeon_combat_source_metadata(
            dungeon_id='amber_catacombs',
            encounter_identity='catacomb_rat',
            mob_level=34,
            source_category='dungeon_trash',
        )
        elite = build_dungeon_combat_source_metadata(
            dungeon_id='amber_catacombs',
            encounter_identity='amber_guardian',
            mob_level=36,
            source_category='dungeon_elite',
        )
        boss = build_dungeon_combat_source_metadata(
            dungeon_id='amber_catacombs',
            encounter_identity='amber_overseer',
            mob_level=40,
            source_category='dungeon_boss',
        )

        self.assertFalse(trash.dungeon_recipe_hook_enabled)
        self.assertFalse(trash.dungeon_reagent_hook_enabled)
        self.assertTrue(elite.dungeon_recipe_hook_enabled)
        self.assertTrue(elite.dungeon_reagent_hook_enabled)
        self.assertFalse(elite.boss_reagent_hook_enabled)
        self.assertTrue(boss.dungeon_recipe_hook_enabled)
        self.assertTrue(boss.dungeon_reagent_hook_enabled)
        self.assertTrue(boss.boss_reagent_hook_enabled)
        self.assertTrue(boss.future_set_crafting_input_hook_enabled)

    def test_live_grant_flow_uses_dungeon_quality_floor_and_family_allowlist(self):
        from game.gear_instances import _create_generated_gear_instance

        boss_meta = build_dungeon_combat_source_metadata(
            dungeon_id='amber_catacombs',
            encounter_identity='amber_overseer',
            mob_level=40,
            source_category='dungeon_boss',
        )

        with patch('game.gear_instances.roll_generated_rarity', return_value='common'):
            instance_id = _create_generated_gear_instance(
                333,
                'tracker_jacket',
                source='mob_drop',
                source_level=40,
                source_metadata=boss_meta,
            )

        denied = grant_item_to_player(
            333,
            'herb_common',
            quantity=1,
            source='mob_drop',
            source_level=40,
            source_metadata=boss_meta,
        )

        conn = get_connection()
        row = conn.execute('SELECT rarity FROM gear_instances WHERE id=?', (instance_id,)).fetchone()
        herb_row = conn.execute(
            'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (333, 'herb_common'),
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row['rarity'], 'rare')
        self.assertEqual(denied, {'gear_instances_created': 0, 'stackable_added': 0})
        self.assertIsNone(herb_row)


if __name__ == '__main__':
    unittest.main()
