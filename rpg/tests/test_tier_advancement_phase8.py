import os
import tempfile
import unittest

import database
from database import get_connection, init_db
from game.gear_instances import create_gear_instance
from game.tier_advancement import (
    AdvancementRequest,
    advance_gear_instance_tier,
    is_instance_eligible_for_tier_advancement,
    resolve_advancement_cost,
)


class TierAdvancementPhase8Tests(unittest.TestCase):
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
            (9201, 'advance', 'AdvanceTester', 25, 200000, 100, 100, 60, 60, 8, 8, 8, 8, 8, 8, 'village'),
        )

        from game.items_data import get_item
        for item_id in ('wooden_sword', 'magic_staff', 'enhancement_crystal', 'power_essence', 'ashen_core'):
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
                    item.get('req_strength', 0),
                    item.get('req_agility', 0),
                    item.get('req_intuition', 0),
                    item.get('req_wisdom', 0),
                    item.get('buy_price', 0),
                    item.get('stat_bonus_json', '{}'),
                ),
            )

        conn.execute(
            'INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)',
            (9201, 'enhancement_crystal', 500),
        )
        conn.execute(
            'INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)',
            (9201, 'power_essence', 500),
        )
        conn.execute(
            'INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)',
            (9201, 'ashen_core', 500),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def test_cost_escalation_by_rarity_is_explicit(self):
        common = resolve_advancement_cost(current_tier=10, target_tier=15, rarity='common')
        rare = resolve_advancement_cost(current_tier=10, target_tier=15, rarity='rare')
        epic = resolve_advancement_cost(current_tier=10, target_tier=15, rarity='epic')
        legendary = resolve_advancement_cost(current_tier=10, target_tier=15, rarity='legendary')

        self.assertGreater(rare.gold, common.gold)
        self.assertGreater(epic.gold, rare.gold)
        self.assertGreater(legendary.gold, epic.gold)

    def test_contract_rejects_non_next_target_tier(self):
        instance_id = create_gear_instance(9201, 'wooden_sword', item_tier=10, rarity='common', enhance_level=3)
        result = advance_gear_instance_tier(
            AdvancementRequest(telegram_id=9201, instance_id=instance_id, target_tier=25)
        )
        self.assertEqual(result.status, 'invalid_target_tier')

    def test_advancement_preserves_identity_rarity_and_enhancement(self):
        instance_id = create_gear_instance(9201, 'wooden_sword', item_tier=10, rarity='rare', enhance_level=4)
        result = advance_gear_instance_tier(AdvancementRequest(telegram_id=9201, instance_id=instance_id))

        self.assertEqual(result.status, 'advanced')
        self.assertEqual(result.previous_tier, 10)
        self.assertEqual(result.new_tier, 15)
        self.assertEqual(result.base_item_id_preserved, 'wooden_sword')
        self.assertEqual(result.rarity_preserved, 'rare')
        self.assertEqual(result.enhance_level_preserved, 4)

        conn = get_connection()
        row = conn.execute('SELECT id, base_item_id, item_tier, rarity, enhance_level FROM gear_instances WHERE id=?', (instance_id,)).fetchone()
        conn.close()
        self.assertEqual(row['id'], instance_id)
        self.assertEqual(row['base_item_id'], 'wooden_sword')
        self.assertEqual(row['item_tier'], 15)
        self.assertEqual(row['rarity'], 'rare')
        self.assertEqual(row['enhance_level'], 4)

    def test_unique_rarity_is_explicitly_not_eligible(self):
        instance_id = create_gear_instance(9201, 'wooden_sword', item_tier=10, rarity='unique', enhance_level=2)

        conn = get_connection()
        row = dict(conn.execute('SELECT * FROM gear_instances WHERE id=?', (instance_id,)).fetchone())
        conn.close()
        self.assertFalse(is_instance_eligible_for_tier_advancement(row))

        result = advance_gear_instance_tier(AdvancementRequest(telegram_id=9201, instance_id=instance_id))
        self.assertEqual(result.status, 'not_eligible')

    def test_minimal_runtime_slice_advances_higher_rarity_instance(self):
        instance_id = create_gear_instance(9201, 'magic_staff', item_tier=20, rarity='epic', enhance_level=6)
        before_cost = resolve_advancement_cost(current_tier=20, target_tier=25, rarity='epic')

        conn = get_connection()
        gold_before = conn.execute('SELECT gold FROM players WHERE telegram_id=?', (9201,)).fetchone()['gold']
        material_before = conn.execute(
            'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (9201, before_cost.material_id),
        ).fetchone()['quantity']
        conn.close()

        result = advance_gear_instance_tier(AdvancementRequest(telegram_id=9201, instance_id=instance_id, target_tier=25))
        self.assertTrue(result.is_success)
        self.assertIsNotNone(result.cost)

        conn = get_connection()
        gold_after = conn.execute('SELECT gold FROM players WHERE telegram_id=?', (9201,)).fetchone()['gold']
        material_after = conn.execute(
            'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (9201, before_cost.material_id),
        ).fetchone()['quantity']
        row = conn.execute('SELECT item_tier, rarity, enhance_level FROM gear_instances WHERE id=?', (instance_id,)).fetchone()
        conn.close()

        self.assertEqual(gold_after, gold_before - before_cost.gold)
        self.assertEqual(material_after, material_before - before_cost.material_qty)
        self.assertEqual(row['item_tier'], 25)
        self.assertEqual(row['rarity'], 'epic')
        self.assertEqual(row['enhance_level'], 6)


if __name__ == '__main__':
    unittest.main()
