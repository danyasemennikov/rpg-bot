import os
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from unittest.mock import AsyncMock

import database
from database import get_connection, init_db
from game.combat import calc_rewards
from game.mobs import MOBS, get_mob
from game.locations import get_mob_location_id
from game.reward_source_metadata import build_open_world_combat_source_metadata
from handlers.battle import apply_rewards
from handlers.location import (
    CURATED_EQUIPMENT_VENDOR_STOCK,
    get_curated_shop_stock,
    try_buy_curated_shop_item,
)


class EquipmentAcquisitionPassTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self._tmpdir.name, 'test_game.db')
        init_db()

        conn = get_connection()
        conn.execute(
            '''INSERT INTO players (
                telegram_id, username, name, level, gold, hp, max_hp, mana, max_mana,
                strength, agility, intuition, vitality, wisdom, luck, location_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (9001, 'acq', 'AcqTester', 4, 500, 100, 100, 50, 50, 6, 6, 6, 6, 6, 6, 'village'),
        )

        for item_id in (
            'oak_guard_shield',
            'apprentice_focus_orb',
            'novice_censer',
            'militia_cuirass',
            'acolyte_robe',
            'band_of_precision',
            'ring_of_quiet_mind',
        ):
            from game.items_data import get_item
            data = get_item(item_id)
            conn.execute(
                '''INSERT INTO items (
                    item_id, name, item_type, rarity, buy_price, req_level,
                    req_strength, req_agility, req_intuition, req_wisdom, stat_bonus_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    data['item_id'],
                    data['name'],
                    data['item_type'],
                    data['rarity'],
                    data['buy_price'],
                    data['req_level'],
                    data['req_strength'],
                    data['req_agility'],
                    data['req_intuition'],
                    data['req_wisdom'],
                    data['stat_bonus_json'],
                ),
            )

        conn.commit()
        conn.close()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def test_curated_shop_stock_is_gated_by_location_and_level(self):
        village_level_4 = {row['item_id'] for row in get_curated_shop_stock('village', 4)}
        village_level_5 = {row['item_id'] for row in get_curated_shop_stock('village', 5)}
        mines_level_8 = get_curated_shop_stock('old_mines', 8)

        self.assertIn('oak_guard_shield', village_level_4)
        self.assertIn('militia_cuirass', village_level_4)
        self.assertNotIn('band_of_precision', village_level_4)
        self.assertIn('band_of_precision', village_level_5)
        self.assertEqual(mines_level_8, [])

    def test_shop_purchase_obtains_curated_item_and_deducts_gold(self):
        result = try_buy_curated_shop_item(9001, 'village', 4, 'apprentice_focus_orb')
        self.assertTrue(result['ok'])

        conn = get_connection()
        gear_row = conn.execute(
            'SELECT base_item_id, equipped_slot, item_tier, rarity FROM gear_instances WHERE telegram_id=? AND base_item_id=?',
            (9001, 'apprentice_focus_orb'),
        ).fetchone()
        inv_row = conn.execute(
            'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (9001, 'apprentice_focus_orb'),
        ).fetchone()
        player_row = conn.execute('SELECT gold FROM players WHERE telegram_id=?', (9001,)).fetchone()
        conn.close()

        self.assertIsNotNone(gear_row)
        self.assertIsNone(inv_row)
        self.assertEqual(player_row['gold'], 320)
        self.assertEqual(gear_row['item_tier'], 1)
        self.assertIn(gear_row['rarity'], {'common', 'uncommon', 'rare', 'epic', 'legendary'})

    def test_shop_purchase_enforces_level_gating(self):
        result = try_buy_curated_shop_item(9001, 'village', 4, 'band_of_precision')
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'level_required')

    def test_existing_loot_behavior_remains_intact(self):
        wolf = get_mob('forest_wolf')
        with patch('game.combat.random.randint', return_value=3), \
             patch('game.combat.random.random', side_effect=[0.01, 0.99, 0.99, 0.99]):
            rewards = calc_rewards(wolf)

        self.assertEqual(rewards['gold'], 3)
        self.assertEqual(rewards['mob_level'], wolf['level'])
        self.assertIn('wolf_pelt', rewards['loot'])
        self.assertNotIn('wolf_fang', rewards['loot'])

    def test_curated_slice_is_actually_routed_to_shop_or_drops(self):
        curated_ids = {
            'oak_guard_shield',
            'apprentice_focus_orb',
            'novice_censer',
            'militia_cuirass',
            'tracker_jacket',
            'acolyte_robe',
            'band_of_precision',
            'ring_of_quiet_mind',
            'warden_kite_shield',
            'azure_focus_prism',
            'choir_censer',
            'amulet_of_kindled_prayer',
            'dual_path_loop',
        }

        shop_items = {
            row['item_id']
            for rows in CURATED_EQUIPMENT_VENDOR_STOCK.values()
            for row in rows
        }
        drop_items = set()
        for mob_id in ('forest_spider', 'dark_treant', 'goblin_miner', 'stone_golem'):
            drop_items.update(item_id for item_id, _chance in get_mob(mob_id)['loot_table'])

        surfaced = shop_items | drop_items
        self.assertTrue(curated_ids.issubset(surfaced))

    def test_enhancement_materials_are_available_via_live_routes(self):
        shop_items = {
            row['item_id']
            for rows in CURATED_EQUIPMENT_VENDOR_STOCK.values()
            for row in rows
        }
        drop_items = set()
        for mob in ('forest_wolf', 'forest_spider', 'goblin_miner', 'stone_golem'):
            drop_items.update(item_id for item_id, _chance in get_mob(mob)['loot_table'])

        self.assertIn('enhance_shard', drop_items)
        self.assertIn('enhancement_crystal', drop_items)
        self.assertIn('power_essence', drop_items)
        self.assertIn('ashen_core', shop_items)

    def test_schema_changes_are_additive_for_acquisition_pass(self):
        conn = get_connection()
        columns = {row['name'] for row in conn.execute('PRAGMA table_info(players)').fetchall()}
        gear_columns = {row['name'] for row in conn.execute('PRAGMA table_info(gear_instances)').fetchall()}
        conn.close()

        self.assertIn('gold', columns)
        self.assertIn('location_id', columns)
        self.assertNotIn('shop_rank', columns)
        self.assertIn('base_item_id', gear_columns)
        self.assertIn('equipped_slot', gear_columns)

    def test_all_current_mobs_have_phase2_creature_taxonomy_tags(self):
        for mob in MOBS.values():
            taxonomy = mob.get('creature_taxonomy')
            self.assertIsInstance(taxonomy, dict, msg=f'mob {mob["id"]} has no taxonomy')
            self.assertIn('body_type', taxonomy, msg=f'mob {mob["id"]} misses body_type')
            self.assertIn('special_trait', taxonomy, msg=f'mob {mob["id"]} misses special_trait')
            self.assertIn('encounter_class', taxonomy, msg=f'mob {mob["id"]} misses encounter_class')

    def test_live_rewards_flow_passes_taxonomy_and_tier_band_metadata(self):
        mob = get_mob('stone_golem')
        rewards = calc_rewards(mob)
        source_meta = build_open_world_combat_source_metadata(
            source_id=rewards['mob_id'],
            mob_level=rewards['mob_level'],
            source_category=rewards['source_category'],
            creature_taxonomy=rewards['creature_taxonomy'],
            location_id=get_mob_location_id(rewards['mob_id']),
        )
        self.assertEqual(source_meta.content_tier, 1)
        self.assertEqual(source_meta.creature_body_type, 'construct')
        self.assertEqual(source_meta.creature_encounter_class, 'elite')
        self.assertIn('core', source_meta.creature_loot_identity)
        self.assertEqual(source_meta.open_world_pool_profile, 'open_world_elite_surface')
        self.assertEqual(source_meta.open_world_world_identity, 'ashen_continent')
        self.assertIsNone(source_meta.open_world_macro_region_identity)
        self.assertEqual(source_meta.open_world_region_identity, 'ember_valley')
        self.assertEqual(source_meta.open_world_zone_identity, 'old_mines')
        self.assertEqual(source_meta.open_world_zone_role, 'elite')
        self.assertEqual(source_meta.open_world_encounter_role, 'elite')
        self.assertEqual(source_meta.future_dungeon_link_id, 'amber_catacombs')
        self.assertEqual(source_meta.future_world_boss_governance_id, 'ember_valley_world_boss')
        self.assertEqual(source_meta.open_world_future_pvp_ruleset_id, 'open_world_frontier')
        self.assertEqual(source_meta.quality_floor_rarity, 'uncommon')

    def test_live_flow_bridge_maps_elite_encounter_to_open_world_elite_when_source_missing(self):
        mob = {
            'id': 'synthetic_elite_beast',
            'level': 18,
            'exp_reward': 10,
            'gold_min': 1,
            'gold_max': 1,
            'loot_table': [],
            'creature_taxonomy': {
                'body_type': 'beast',
                'special_trait': 'predator',
                'encounter_class': 'elite',
            },
        }
        rewards = calc_rewards(mob)
        self.assertIsNone(rewards['source_category'])
        source_meta = build_open_world_combat_source_metadata(
            source_id=rewards['mob_id'],
            mob_level=rewards['mob_level'],
            source_category=rewards.get('source_category'),
            creature_taxonomy=rewards.get('creature_taxonomy'),
        )
        self.assertEqual(source_meta.source_category, 'open_world_elite')

    def test_live_flow_bridge_maps_boss_encounter_to_regional_boss_when_source_missing(self):
        mob = {
            'id': 'synthetic_boss_plant',
            'level': 26,
            'exp_reward': 10,
            'gold_min': 1,
            'gold_max': 1,
            'loot_table': [],
            'creature_taxonomy': {
                'body_type': 'plant',
                'special_trait': 'giant',
                'encounter_class': 'boss',
            },
        }
        rewards = calc_rewards(mob)
        self.assertIsNone(rewards['source_category'])
        source_meta = build_open_world_combat_source_metadata(
            source_id=rewards['mob_id'],
            mob_level=rewards['mob_level'],
            source_category=rewards.get('source_category'),
            creature_taxonomy=rewards.get('creature_taxonomy'),
        )
        self.assertEqual(source_meta.source_category, 'open_world_regional_boss')

    def test_grant_item_blocks_open_world_gear_outside_source_content_identity(self):
        from game.gear_instances import grant_item_to_player

        meta = build_open_world_combat_source_metadata(
            source_id='forest_wolf',
            mob_level=2,
            source_category='open_world_normal',
            creature_taxonomy=get_mob('forest_wolf').get('creature_taxonomy'),
            location_id='dark_forest',
        )
        blocked = grant_item_to_player(
            9001,
            'iron_shield',
            quantity=1,
            source='mob_drop',
            source_level=2,
            source_metadata=meta,
        )
        self.assertEqual(blocked, {'gear_instances_created': 0, 'stackable_added': 0})

    def test_live_reward_flow_prefers_mob_region_over_player_region(self):
        rewards = {
            'exp': 0,
            'gold': 0,
            'loot': ['stone_core'],
            'mob_level': 8,
            'mob_id': 'stone_golem',
            'source_category': 'open_world_elite',
            'creature_taxonomy': get_mob('stone_golem').get('creature_taxonomy'),
        }
        conn = get_connection()
        player = dict(conn.execute('SELECT * FROM players WHERE telegram_id=?', (9001,)).fetchone())
        conn.close()

        with patch('handlers.battle.grant_item_to_player') as grant_mock:
            apply_rewards(9001, player, rewards)

        source_meta = grant_mock.call_args.kwargs['source_metadata']
        self.assertEqual(source_meta.open_world_region_identity, 'ember_valley')
        self.assertEqual(source_meta.open_world_zone_identity, 'old_mines')

    def test_live_reward_flow_falls_back_to_player_region_when_mob_region_unknown(self):
        rewards = {
            'exp': 0,
            'gold': 0,
            'loot': ['wolf_pelt'],
            'mob_level': 2,
            'mob_id': 'synthetic_unknown_mob',
            'source_category': 'open_world_normal',
            'creature_taxonomy': get_mob('forest_wolf').get('creature_taxonomy'),
        }
        conn = get_connection()
        player = dict(conn.execute('SELECT * FROM players WHERE telegram_id=?', (9001,)).fetchone())
        conn.close()

        with patch('handlers.battle.grant_item_to_player') as grant_mock:
            apply_rewards(9001, player, rewards)

        source_meta = grant_mock.call_args.kwargs['source_metadata']
        self.assertEqual(source_meta.open_world_region_identity, 'ember_valley')
        self.assertEqual(source_meta.open_world_zone_identity, 'ember_village')


class ShopBackNavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_shop_back_returns_location_view_not_shop_view(self):
        query = SimpleNamespace(
            data='shop_back',
            from_user=SimpleNamespace(id=9001),
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace()

        player = {
            'telegram_id': 9001,
            'lang': 'ru',
            'in_battle': 0,
            'location_id': 'village',
            'level': 4,
            'hp': 100,
            'max_hp': 100,
            'mana': 50,
            'max_mana': 50,
            'gold': 500,
        }
        location = {'id': 'village', 'services': ['shop']}

        with patch('handlers.location.get_player', return_value=player), \
             patch('handlers.location.get_location', return_value=location), \
             patch(
                 'handlers.location.build_location_message',
                 return_value=('LOCATION_VIEW', 'LOCATION_KB', {'snapshot_tag': 's1', 'actions': {}}),
             ) as location_view_mock, \
             patch('handlers.location.build_shop_message', return_value=('SHOP_VIEW', 'SHOP_KB')) as shop_view_mock:
            from handlers.location import handle_location_buttons
            await handle_location_buttons(update, context)

        location_view_mock.assert_called_once_with(
            player,
            location,
            pvp_only_view=False,
            include_action_map=True,
            snapshot_tag='s1',
        )
        shop_view_mock.assert_not_called()
        query.edit_message_text.assert_awaited_once_with('LOCATION_VIEW', reply_markup='LOCATION_KB', parse_mode='HTML')

    async def test_in_battle_callback_uses_query_alert_instead_of_update_message(self):
        query = SimpleNamespace(
            data='shop',
            from_user=SimpleNamespace(id=9001),
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        update = SimpleNamespace(callback_query=query, message=None)
        context = SimpleNamespace()

        player = {
            'telegram_id': 9001,
            'lang': 'ru',
            'in_battle': 1,
            'location_id': 'village',
            'level': 4,
        }

        with patch('handlers.location.get_player', return_value=player):
            from handlers.location import handle_location_buttons
            await handle_location_buttons(update, context)

        query.answer.assert_awaited_once_with('⚔️ Сначала разберись с противником!', show_alert=True)
        query.edit_message_text.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
