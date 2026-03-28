import os
import tempfile
import unittest
from unittest.mock import patch

import database
from database import get_connection, init_db
from game.balance import get_player_accuracy_rating, get_player_evasion_rating
from game.combat import mob_attack
from game.equipment_stats import (
    aggregate_equipped_stat_bonuses,
    build_effective_player_stats,
    clamp_player_resources_to_effective_caps,
)


class EquipmentRuntimeIntegrationTests(unittest.TestCase):
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
            (1001, 'tester', 'Tester', 10, 120, 120, 60, 60, 8, 9, 10, 11, 12, 7),
        )

        items = [
            'tracker_jacket',
            'oak_guard_shield',
            'band_of_precision',
            'ring_of_quiet_mind',
            'iron_sword',
        ]
        for item_id in items:
            conn.execute(
                'INSERT INTO items (item_id, name, item_type, rarity, stat_bonus_json) VALUES (?, ?, ?, ?, ?)',
                (item_id, item_id, 'armor', 'common', '{}'),
            )

        inv_rows = [
            (1, 'tracker_jacket'),
            (2, 'oak_guard_shield'),
            (3, 'band_of_precision'),
            (4, 'ring_of_quiet_mind'),
            (5, 'iron_sword'),
        ]
        for inv_id, item_id in inv_rows:
            conn.execute(
                'INSERT INTO inventory (id, telegram_id, item_id, quantity) VALUES (?, ?, ?, ?)',
                (inv_id, 1001, item_id, 1),
            )

        conn.execute(
            '''INSERT INTO equipment (telegram_id, chest, offhand, ring1)
               VALUES (?, ?, ?, ?)''',
            (1001, 1, 2, 3),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def test_equipped_item_bonuses_aggregate_correctly(self):
        bonuses = aggregate_equipped_stat_bonuses(1001)
        self.assertEqual(bonuses['max_hp'], 20)
        self.assertEqual(bonuses['accuracy'], 6)
        self.assertEqual(bonuses['evasion'], 2)
        self.assertEqual(bonuses['agility'], 1)

    def test_effective_base_stat_bonuses_feed_runtime_formulas(self):
        conn = get_connection()
        player = dict(conn.execute('SELECT * FROM players WHERE telegram_id=?', (1001,)).fetchone())
        conn.close()

        effective = build_effective_player_stats(player, {'vitality': 3, 'wisdom': 2, 'agility': 1, 'luck': 2})
        self.assertEqual(effective['vitality'], player['vitality'] + 3)
        self.assertEqual(effective['wisdom'], player['wisdom'] + 2)
        self.assertEqual(effective['agility'], player['agility'] + 1)
        self.assertEqual(effective['luck'], player['luck'] + 2)
        self.assertGreater(effective['max_hp'], player['max_hp'])
        self.assertGreater(effective['max_mana'], player['max_mana'])

    def test_non_equipped_inventory_items_do_not_affect_effective_stats(self):
        bonuses = aggregate_equipped_stat_bonuses(1001)
        self.assertNotIn('max_mana', bonuses)
        self.assertNotIn('strength', bonuses)

    def test_accessory_offhand_and_chest_all_contribute(self):
        bonuses = aggregate_equipped_stat_bonuses(1001)
        self.assertEqual(bonuses['max_hp'], 20)
        self.assertEqual(bonuses['accuracy'], 6)
        self.assertEqual(bonuses['evasion'], 2)

    def test_effective_runtime_paths_consume_defense_accuracy_and_evasion(self):
        conn = get_connection()
        player = dict(conn.execute('SELECT * FROM players WHERE telegram_id=?', (1001,)).fetchone())
        conn.close()

        bonuses = aggregate_equipped_stat_bonuses(1001)
        effective = build_effective_player_stats(player, bonuses)

        battle_state = {
            'mastery_level': 2,
            'accuracy_bonus': 0,
            'evasion_bonus': 0,
            'equipment_accuracy_bonus': effective['accuracy_bonus'],
            'equipment_evasion_bonus': effective['evasion_bonus'],
        }
        player_with_runtime = dict(player)
        player_with_runtime['equipment_physical_defense_bonus'] = effective['physical_defense_bonus']
        player_with_runtime['equipment_magic_defense_bonus'] = effective['magic_defense_bonus']

        self.assertEqual(
            get_player_accuracy_rating(player_with_runtime, battle_state),
            100 + player['agility'] * 2 + player['intuition'] + 4 + 6,
        )
        self.assertEqual(
            get_player_evasion_rating(player_with_runtime, battle_state),
            100 + player['agility'] * 2 + player['luck'] + 2,
        )

        defense_effective = build_effective_player_stats(player, {'physical_defense': 12})
        player_with_defense_bonus = dict(player)
        player_with_defense_bonus['equipment_physical_defense_bonus'] = defense_effective['physical_defense_bonus']
        player_with_defense_bonus['equipment_magic_defense_bonus'] = defense_effective['magic_defense_bonus']

        mob = {'damage_min': 60, 'damage_max': 60, 'damage_school': 'physical', 'weapon_type': 'melee'}
        with patch('game.combat.random.randint', return_value=60):
            with_bonus = mob_attack(mob, player_with_defense_bonus, allow_dodge=False)
            without_bonus = mob_attack(mob, dict(player), allow_dodge=False)

        self.assertLess(with_bonus['damage'], without_bonus['damage'])

    def test_legacy_items_remain_backward_compatible(self):
        bonuses = aggregate_equipped_stat_bonuses(1001)
        self.assertNotIn('strength', bonuses)

        conn = get_connection()
        player = dict(conn.execute('SELECT * FROM players WHERE telegram_id=?', (1001,)).fetchone())
        conn.close()

        effective = build_effective_player_stats(player, bonuses)
        self.assertEqual(effective['max_mana'], 60)

    def test_no_schema_changes_required(self):
        conn = get_connection()
        equipment_columns = {
            row['name']
            for row in conn.execute('PRAGMA table_info(equipment)').fetchall()
        }
        conn.close()

        self.assertIn('weapon', equipment_columns)
        self.assertIn('offhand', equipment_columns)
        self.assertIn('chest', equipment_columns)
        self.assertNotIn('effective_max_hp', equipment_columns)

    def test_unequip_max_hp_gear_clamps_current_hp_to_new_effective_cap(self):
        conn = get_connection()
        conn.execute('UPDATE players SET hp=140 WHERE telegram_id=?', (1001,))
        conn.execute('UPDATE equipment SET offhand=NULL WHERE telegram_id=?', (1001,))
        conn.commit()
        conn.close()

        result = clamp_player_resources_to_effective_caps(1001)
        self.assertTrue(result['changed'])
        self.assertEqual(result['max_hp'], 120)
        self.assertEqual(result['hp'], 120)

    def test_unequip_max_mana_gear_clamps_current_mana_to_new_effective_cap(self):
        conn = get_connection()
        conn.execute('UPDATE players SET mana=95 WHERE telegram_id=?', (1001,))
        conn.execute('UPDATE equipment SET ring1=NULL WHERE telegram_id=?', (1001,))
        conn.commit()
        conn.close()

        result = clamp_player_resources_to_effective_caps(1001)
        self.assertTrue(result['changed'])
        self.assertEqual(result['max_mana'], 60)
        self.assertEqual(result['mana'], 60)

    def test_clamp_keeps_profile_read_values_consistent_with_effective_caps(self):
        conn = get_connection()
        conn.execute('UPDATE players SET hp=145, mana=99 WHERE telegram_id=?', (1001,))
        conn.execute('UPDATE equipment SET offhand=NULL, ring1=NULL WHERE telegram_id=?', (1001,))
        conn.commit()
        player = dict(conn.execute('SELECT * FROM players WHERE telegram_id=?', (1001,)).fetchone())
        conn.close()

        clamp_player_resources_to_effective_caps(1001, player)

        conn = get_connection()
        clamped_player = dict(conn.execute('SELECT * FROM players WHERE telegram_id=?', (1001,)).fetchone())
        conn.close()
        effective = build_effective_player_stats(clamped_player, aggregate_equipped_stat_bonuses(1001))
        self.assertLessEqual(clamped_player['hp'], effective['max_hp'])
        self.assertLessEqual(clamped_player['mana'], effective['max_mana'])


if __name__ == '__main__':
    unittest.main()
