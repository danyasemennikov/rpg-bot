import os
import random
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import database
from database import get_connection, init_db
from game.equipment_stats import get_equipped_item_ids
from game.gear_instances import (
    MAX_ENHANCE_LEVEL,
    create_gear_instance,
    determine_mob_drop_item_tier,
    determine_shop_item_tier,
    enhance_gear_instance_once,
    get_enhance_requirements_for_target_level,
    generate_secondary_rolls_for_item,
    grant_item_to_player,
    resolve_gear_instance_item_data,
    resolve_item_tier_band,
    resolve_equipped_item_ids_with_fallback,
    set_gear_instance_equipped_slot,
)
from game.i18n import t
from handlers.inventory import build_inventory_list, build_item_detail, get_equipped
from handlers.inventory import handle_inventory_buttons
from handlers.profile import _build_equipment_summary


class GearInstanceTransitionTests(unittest.TestCase):
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
            (2001, 'gear', 'GearTester', 10, 120, 120, 60, 60, 8, 8, 8, 8, 8, 8),
        )

        from game.items_data import get_item
        for item_id in (
            'wooden_sword', 'health_potion', 'iron_sword',
            'enhance_shard', 'enhancement_crystal', 'power_essence', 'ashen_core',
            'iron_ore', 'coal', 'gem_common', 'stone_core', 'treant_heart',
        ):
            item = get_item(item_id)
            conn.execute(
                '''INSERT INTO items (
                    item_id, name, item_type, rarity, req_level,
                    req_strength, req_agility, req_intuition, req_wisdom,
                    buy_price, stat_bonus_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    item['item_id'],
                    item['name'],
                    item['item_type'],
                    item['rarity'],
                    item['req_level'],
                    item['req_strength'],
                    item['req_agility'],
                    item['req_intuition'],
                    item['req_wisdom'],
                    item.get('buy_price', 0),
                    item.get('stat_bonus_json', '{}'),
                ),
            )
        for item_id in ('oak_guard_shield',):
            item = get_item(item_id)
            conn.execute(
                '''INSERT INTO items (
                    item_id, name, item_type, rarity, req_level,
                    req_strength, req_agility, req_intuition, req_wisdom,
                    buy_price, stat_bonus_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    item['item_id'],
                    item['name'],
                    item['item_type'],
                    item['rarity'],
                    item['req_level'],
                    item['req_strength'],
                    item['req_agility'],
                    item['req_intuition'],
                    item['req_wisdom'],
                    item.get('buy_price', 0),
                    item.get('stat_bonus_json', '{}'),
                ),
            )

        conn.execute('INSERT INTO equipment (telegram_id) VALUES (?)', (2001,))
        conn.commit()
        conn.close()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def test_non_gear_items_remain_stackable(self):
        grant_item_to_player(2001, 'health_potion', quantity=2)
        grant_item_to_player(2001, 'health_potion', quantity=1)

        conn = get_connection()
        inv_row = conn.execute(
            'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (2001, 'health_potion'),
        ).fetchone()
        gear_row = conn.execute(
            'SELECT * FROM gear_instances WHERE telegram_id=? AND base_item_id=?',
            (2001, 'health_potion'),
        ).fetchone()
        conn.close()

        self.assertIsNotNone(inv_row)
        self.assertEqual(inv_row['quantity'], 3)
        self.assertIsNone(gear_row)

    def test_gear_items_are_granted_as_non_stackable_instances(self):
        grant_item_to_player(2001, 'wooden_sword', quantity=2)

        conn = get_connection()
        instance_count = conn.execute(
            'SELECT COUNT(*) AS c FROM gear_instances WHERE telegram_id=? AND base_item_id=?',
            (2001, 'wooden_sword'),
        ).fetchone()['c']
        inv_row = conn.execute(
            'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (2001, 'wooden_sword'),
        ).fetchone()
        conn.close()

        self.assertEqual(instance_count, 2)
        self.assertIsNone(inv_row)

    def test_instance_equipped_slot_is_used_by_runtime_read_path(self):
        instance_id = create_gear_instance(2001, 'wooden_sword')
        set_gear_instance_equipped_slot(2001, instance_id, 'weapon')

        equipped = get_equipped_item_ids(2001)
        self.assertEqual(equipped.get('weapon'), 'wooden_sword')

    def test_legacy_fallback_still_works_when_no_instance_equipment(self):
        conn = get_connection()
        conn.execute(
            'INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)',
            (2001, 'iron_sword', 1),
        )
        inv_id = conn.execute(
            'SELECT id FROM inventory WHERE telegram_id=? AND item_id=?',
            (2001, 'iron_sword'),
        ).fetchone()['id']
        conn.execute('UPDATE equipment SET weapon=? WHERE telegram_id=?', (inv_id, 2001))
        conn.commit()
        conn.close()

        equipped = resolve_equipped_item_ids_with_fallback(2001)
        self.assertEqual(equipped.get('weapon'), 'iron_sword')

    def test_id_collision_does_not_create_false_equipped_marker(self):
        conn = get_connection()
        conn.execute(
            'INSERT INTO inventory (id, telegram_id, item_id, quantity) VALUES (?, ?, ?, ?)',
            (1, 2001, 'iron_sword', 1),
        )
        conn.execute('UPDATE equipment SET weapon=? WHERE telegram_id=?', (1, 2001))
        conn.commit()
        conn.close()

        # same raw integer ID in a different table namespace
        create_gear_instance(2001, 'wooden_sword')  # gear_instances.id == 1

        eq = get_equipped(2001)
        self.assertEqual(eq.get('weapon'), 'i1')
        self.assertNotIn('g1', eq.values())

        _text, keyboard = build_inventory_list(2001, 'weapon', 'ru')
        equipped_tag = t('inventory.equipped', 'ru')

        by_callback = {
            row[0].callback_data: row[0].text
            for row in keyboard.inline_keyboard[1:]
        }
        self.assertIn('inv_item_i1_weapon', by_callback)
        self.assertIn('inv_item_g1_weapon', by_callback)
        self.assertIn(equipped_tag, by_callback['inv_item_i1_weapon'])
        self.assertNotIn(equipped_tag, by_callback['inv_item_g1_weapon'])

    def test_instance_equipped_item_is_marked_as_equipped(self):
        instance_id = create_gear_instance(2001, 'oak_guard_shield')
        set_gear_instance_equipped_slot(2001, instance_id, 'offhand')

        _text, keyboard = build_inventory_list(2001, 'armor', 'ru')
        equipped_tag = t('inventory.equipped', 'ru')
        labels = {
            row[0].callback_data: row[0].text
            for row in keyboard.inline_keyboard[1:]
        }
        self.assertIn('inv_item_g1_armor', labels)
        self.assertIn(equipped_tag, labels['inv_item_g1_armor'])

    def test_generated_gear_instance_has_tier_rarity_and_runtime_secondary_rolls(self):
        rng = random.Random(7)
        grant_item_to_player(2001, 'wooden_sword', source='mob_drop', source_level=12, rng=rng)

        conn = get_connection()
        row = dict(conn.execute(
            'SELECT * FROM gear_instances WHERE telegram_id=? AND base_item_id=? ORDER BY id DESC LIMIT 1',
            (2001, 'wooden_sword'),
        ).fetchone())
        conn.close()

        self.assertEqual(row['item_tier'], 10)
        self.assertIn(row['rarity'], {'common', 'uncommon', 'rare', 'epic', 'legendary'})
        resolved = resolve_gear_instance_item_data(row)
        for roll in resolved['secondary_rolls']:
            self.assertIn(
                roll['stat'],
                {
                    'strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck',
                    'max_hp', 'max_mana', 'physical_defense', 'magic_defense',
                    'accuracy', 'evasion', 'block_chance', 'magic_power', 'healing_power',
                },
            )

    def test_secondary_count_matches_rarity_budget(self):
        item = {'item_type': 'accessory', 'slot_identity': 'ring'}
        self.assertEqual(len(generate_secondary_rolls_for_item(item, rarity='common', item_tier=1, rng=random.Random(1))), 0)
        self.assertEqual(len(generate_secondary_rolls_for_item(item, rarity='uncommon', item_tier=1, rng=random.Random(1))), 1)
        self.assertEqual(len(generate_secondary_rolls_for_item(item, rarity='rare', item_tier=1, rng=random.Random(1))), 2)
        self.assertEqual(len(generate_secondary_rolls_for_item(item, rarity='epic', item_tier=1, rng=random.Random(1))), 3)
        self.assertEqual(len(generate_secondary_rolls_for_item(item, rarity='legendary', item_tier=1, rng=random.Random(1))), 4)

    def test_tier_assignment_helpers_are_deterministic(self):
        self.assertEqual(resolve_item_tier_band(1), 1)
        self.assertEqual(resolve_item_tier_band(4), 1)
        self.assertEqual(resolve_item_tier_band(5), 5)
        self.assertEqual(determine_mob_drop_item_tier(mob_level=14), 10)
        self.assertEqual(determine_shop_item_tier({'req_level': 3}, player_level=8, level_min=4), 5)

    def test_tier_scales_base_stats_and_secondary_strength(self):
        low = create_gear_instance(
            2001,
            'wooden_sword',
            item_tier=1,
            rarity='rare',
            secondary_rolls_json='[{\"stat\":\"strength\",\"value\":1}]',
        )
        high = create_gear_instance(
            2001,
            'wooden_sword',
            item_tier=10,
            rarity='rare',
            secondary_rolls_json='[{\"stat\":\"strength\",\"value\":3}]',
        )
        conn = get_connection()
        low_row = dict(conn.execute('SELECT * FROM gear_instances WHERE id=?', (low,)).fetchone())
        high_row = dict(conn.execute('SELECT * FROM gear_instances WHERE id=?', (high,)).fetchone())
        conn.close()
        low_resolved = resolve_gear_instance_item_data(low_row)
        high_resolved = resolve_gear_instance_item_data(high_row)
        self.assertGreaterEqual(high_resolved['damage_max'], low_resolved['damage_max'])
        self.assertGreaterEqual(high_resolved['resolved_stat_bonus']['strength'], low_resolved['resolved_stat_bonus']['strength'])

    def test_inventory_detail_surfaces_instance_generation_identity(self):
        instance_id = create_gear_instance(
            2001,
            'wooden_sword',
            item_tier=5,
            rarity='rare',
            secondary_rolls_json='[{\"stat\":\"accuracy\",\"value\":2}]',
        )
        text, _kb = build_item_detail(2001, f'g{instance_id}', 'weapon', 'en')
        self.assertIn('Tier 5', text)
        self.assertIn('Secondaries', text)
        self.assertIn('Accuracy +2', text)

    def test_inventory_detail_surfaces_enhancement_ui(self):
        instance_id = create_gear_instance(2001, 'wooden_sword', enhance_level=2)
        text, keyboard = build_item_detail(2001, f'g{instance_id}', 'weapon', 'en')
        self.assertIn('+2', text)
        flat_buttons = [btn.text for row in keyboard.inline_keyboard for btn in row]
        self.assertIn('🔨 Enhance', flat_buttons)
        self.assertIn('Upgrade to +3', text)
        self.assertIn('Chance: success', text)

    def test_enhancement_level_cannot_exceed_cap(self):
        conn = get_connection()
        conn.execute('UPDATE players SET gold=? WHERE telegram_id=?', (999999, 2001))
        conn.execute('INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)', (2001, 'iron_ore', 999))
        conn.commit()
        conn.close()

        instance_id = create_gear_instance(2001, 'wooden_sword', enhance_level=MAX_ENHANCE_LEVEL)
        result = enhance_gear_instance_once(2001, instance_id, rng_roll=0.10)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'max_level')

    def test_enhancement_consumes_gold_and_material_atomically(self):
        req = get_enhance_requirements_for_target_level(1)
        conn = get_connection()
        conn.execute('UPDATE players SET gold=? WHERE telegram_id=?', (req['gold'] + 50, 2001))
        conn.execute(
            'INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)',
            (2001, req['material_id'], req['material_qty'] + 2),
        )
        conn.commit()
        conn.close()
        instance_id = create_gear_instance(2001, 'wooden_sword', enhance_level=0)

        result = enhance_gear_instance_once(2001, instance_id, rng_roll=0.10)
        self.assertTrue(result['ok'])

        conn = get_connection()
        player = conn.execute('SELECT gold FROM players WHERE telegram_id=?', (2001,)).fetchone()
        mat = conn.execute(
            'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (2001, req['material_id']),
        ).fetchone()
        row = dict(conn.execute('SELECT * FROM gear_instances WHERE id=?', (instance_id,)).fetchone())
        conn.close()

        self.assertEqual(player['gold'], 50)
        self.assertEqual(mat['quantity'], 2)
        resolved = resolve_gear_instance_item_data(row)
        self.assertEqual(resolved['enhance_level'], 1)

    def test_enhancement_forced_success_path(self):
        req = get_enhance_requirements_for_target_level(10)
        conn = get_connection()
        conn.execute('UPDATE players SET gold=? WHERE telegram_id=?', (req['gold'] + 100, 2001))
        conn.execute('INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)', (2001, req['material_id'], req['material_qty']))
        conn.commit()
        conn.close()
        instance_id = create_gear_instance(2001, 'wooden_sword', enhance_level=9)
        result = enhance_gear_instance_once(2001, instance_id, rng_roll=0.10)
        self.assertTrue(result['ok'])
        self.assertEqual(result['outcome'], 'success')
        self.assertEqual(result['enhance_level_after'], 10)
        conn = get_connection()
        player = conn.execute('SELECT gold FROM players WHERE telegram_id=?', (2001,)).fetchone()
        mat = conn.execute('SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?', (2001, req['material_id'])).fetchone()
        conn.close()
        self.assertEqual(player['gold'], 100)
        self.assertIsNone(mat)

    def test_enhancement_forced_fail_path(self):
        req = get_enhance_requirements_for_target_level(10)
        conn = get_connection()
        conn.execute('UPDATE players SET gold=? WHERE telegram_id=?', (req['gold'] + 100, 2001))
        conn.execute('INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)', (2001, req['material_id'], req['material_qty']))
        conn.commit()
        conn.close()
        instance_id = create_gear_instance(2001, 'wooden_sword', enhance_level=9)
        result = enhance_gear_instance_once(2001, instance_id, rng_roll=0.30)
        self.assertTrue(result['ok'])
        self.assertEqual(result['outcome'], 'fail')
        self.assertEqual(result['enhance_level_after'], 9)
        conn = get_connection()
        player = conn.execute('SELECT gold FROM players WHERE telegram_id=?', (2001,)).fetchone()
        mat = conn.execute('SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?', (2001, req['material_id'])).fetchone()
        conn.close()
        self.assertEqual(player['gold'], 100)
        self.assertIsNone(mat)

    def test_enhancement_forced_rollback_path(self):
        req = get_enhance_requirements_for_target_level(10)
        conn = get_connection()
        conn.execute('UPDATE players SET gold=? WHERE telegram_id=?', (req['gold'] + 100, 2001))
        conn.execute('INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)', (2001, req['material_id'], req['material_qty']))
        conn.commit()
        conn.close()
        instance_id = create_gear_instance(2001, 'wooden_sword', enhance_level=9)
        result = enhance_gear_instance_once(2001, instance_id, rng_roll=0.70)
        self.assertTrue(result['ok'])
        self.assertEqual(result['outcome'], 'rollback')
        self.assertEqual(result['enhance_level_after'], 8)
        conn = get_connection()
        player = conn.execute('SELECT gold FROM players WHERE telegram_id=?', (2001,)).fetchone()
        mat = conn.execute('SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?', (2001, req['material_id'])).fetchone()
        conn.close()
        self.assertEqual(player['gold'], 100)
        self.assertIsNone(mat)

    def test_enhancement_forced_break_path(self):
        req = get_enhance_requirements_for_target_level(10)
        conn = get_connection()
        conn.execute('UPDATE players SET gold=? WHERE telegram_id=?', (req['gold'] + 100, 2001))
        conn.execute('INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)', (2001, req['material_id'], req['material_qty']))
        conn.commit()
        conn.close()
        instance_id = create_gear_instance(2001, 'wooden_sword', enhance_level=9)
        result = enhance_gear_instance_once(2001, instance_id, rng_roll=0.95)
        self.assertTrue(result['ok'])
        self.assertEqual(result['outcome'], 'break')
        self.assertIsNone(result['enhance_level_after'])

        conn = get_connection()
        row = conn.execute('SELECT id FROM gear_instances WHERE id=?', (instance_id,)).fetchone()
        player = conn.execute('SELECT gold FROM players WHERE telegram_id=?', (2001,)).fetchone()
        mat = conn.execute('SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?', (2001, req['material_id'])).fetchone()
        conn.close()
        self.assertIsNone(row)
        self.assertEqual(player['gold'], 100)
        self.assertIsNone(mat)

    def test_generated_and_enhancement_layers_compose(self):
        instance_id = create_gear_instance(
            2001,
            'wooden_sword',
            item_tier=10,
            rarity='rare',
            secondary_rolls_json='[{\"stat\":\"strength\",\"value\":3}]',
            enhance_level=5,
        )
        conn = get_connection()
        row = dict(conn.execute('SELECT * FROM gear_instances WHERE id=?', (instance_id,)).fetchone())
        conn.close()
        resolved = resolve_gear_instance_item_data(row)
        self.assertEqual(resolved['item_tier'], 10)
        self.assertEqual(resolved['enhance_level'], 5)
        self.assertGreaterEqual(resolved['resolved_stat_bonus'].get('strength', 0), 3)


if __name__ == '__main__':
    unittest.main()


class CrossModelExclusivityFlowTests(unittest.IsolatedAsyncioTestCase):
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
            (3001, 'flow', 'FlowTester', 10, 120, 120, 60, 60, 8, 8, 8, 8, 8, 8),
        )

        from game.items_data import get_item
        for item_id in ('wooden_sword', 'iron_sword'):
            item = get_item(item_id)
            conn.execute(
                '''INSERT INTO items (
                    item_id, name, item_type, rarity, req_level,
                    req_strength, req_agility, req_intuition, req_wisdom,
                    buy_price, stat_bonus_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    item['item_id'],
                    item['name'],
                    item['item_type'],
                    item['rarity'],
                    item['req_level'],
                    item['req_strength'],
                    item['req_agility'],
                    item['req_intuition'],
                    item['req_wisdom'],
                    item.get('buy_price', 0),
                    item.get('stat_bonus_json', '{}'),
                ),
            )

        conn.execute('INSERT INTO equipment (telegram_id) VALUES (?)', (3001,))
        conn.execute(
            'INSERT INTO inventory (id, telegram_id, item_id, quantity) VALUES (?, ?, ?, ?)',
            (1, 3001, 'iron_sword', 1),
        )
        conn.execute('UPDATE equipment SET weapon=1 WHERE telegram_id=?', (3001,))
        conn.commit()
        conn.close()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    async def _run_callback(self, data: str):
        query = SimpleNamespace(
            data=data,
            from_user=SimpleNamespace(id=3001),
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(user_data={})
        await handle_inventory_buttons(update, context)
        return query

    async def test_cross_model_slot_exclusivity_and_no_resurrection(self):
        instance_id = create_gear_instance(3001, 'wooden_sword')  # g1

        await self._run_callback(f'inv_equip_g{instance_id}_weapon_weapon')

        conn = get_connection()
        legacy_weapon = conn.execute('SELECT weapon FROM equipment WHERE telegram_id=?', (3001,)).fetchone()['weapon']
        instance_slot = conn.execute('SELECT equipped_slot FROM gear_instances WHERE id=?', (instance_id,)).fetchone()['equipped_slot']
        conn.close()
        self.assertIsNone(legacy_weapon)
        self.assertEqual(instance_slot, 'weapon')
        self.assertEqual(get_equipped_item_ids(3001).get('weapon'), 'wooden_sword')

        await self._run_callback('inv_equip_i1_weapon_weapon')

        conn = get_connection()
        legacy_weapon = conn.execute('SELECT weapon FROM equipment WHERE telegram_id=?', (3001,)).fetchone()['weapon']
        instance_slot = conn.execute('SELECT equipped_slot FROM gear_instances WHERE id=?', (instance_id,)).fetchone()['equipped_slot']
        conn.close()
        self.assertEqual(legacy_weapon, 1)
        self.assertIsNone(instance_slot)
        self.assertEqual(get_equipped_item_ids(3001).get('weapon'), 'iron_sword')

        _text, keyboard = build_inventory_list(3001, 'weapon', 'ru')
        equipped_tag = t('inventory.equipped', 'ru')
        labels = {row[0].callback_data: row[0].text for row in keyboard.inline_keyboard[1:]}
        self.assertIn(equipped_tag, labels['inv_item_i1_weapon'])
        self.assertNotIn(equipped_tag, labels[f'inv_item_g{instance_id}_weapon'])

        profile_summary = _build_equipment_summary(3001, 'ru')
        self.assertIn('Железный меч', profile_summary)
        self.assertNotIn('Деревянный меч', profile_summary)

        await self._run_callback('inv_unequip_i1_weapon_weapon')

        conn = get_connection()
        legacy_weapon = conn.execute('SELECT weapon FROM equipment WHERE telegram_id=?', (3001,)).fetchone()['weapon']
        instance_slot = conn.execute('SELECT equipped_slot FROM gear_instances WHERE id=?', (instance_id,)).fetchone()['equipped_slot']
        conn.close()
        self.assertIsNone(legacy_weapon)
        self.assertIsNone(instance_slot)
        self.assertNotIn('weapon', get_equipped_item_ids(3001))
