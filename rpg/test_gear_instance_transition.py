import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import database
from database import get_connection, init_db
from game.equipment_stats import get_equipped_item_ids
from game.gear_instances import (
    create_gear_instance,
    grant_item_to_player,
    resolve_equipped_item_ids_with_fallback,
    set_gear_instance_equipped_slot,
)
from game.i18n import t
from handlers.inventory import build_inventory_list, get_equipped
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
        for item_id in ('wooden_sword', 'health_potion', 'iron_sword'):
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
