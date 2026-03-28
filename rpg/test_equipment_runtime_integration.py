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
from game.gear_instances import create_gear_instance, resolve_gear_instance_item_data, set_gear_instance_equipped_slot
from game.skill_engine import use_skill
from handlers.battle import get_equipped_combat_items
from handlers.inventory import build_item_detail


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
            'apprentice_focus_orb',
            'novice_censer',
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
            (6, 'apprentice_focus_orb'),
            (7, 'novice_censer'),
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

    def test_block_chance_can_reduce_incoming_damage(self):
        conn = get_connection()
        player = dict(conn.execute('SELECT * FROM players WHERE telegram_id=?', (1001,)).fetchone())
        conn.close()

        with_block = dict(player)
        with_block['equipment_block_chance_bonus'] = 100  # проверяем clamp+roll path
        without_block = dict(player)
        without_block['equipment_block_chance_bonus'] = 0
        mob = {'damage_min': 60, 'damage_max': 60, 'damage_school': 'physical', 'weapon_type': 'melee'}

        with patch('game.combat.random.randint', return_value=60), patch('game.combat.random.random', return_value=0.0):
            blocked = mob_attack(mob, with_block, allow_dodge=False)
            plain = mob_attack(mob, without_block, allow_dodge=False)

        self.assertTrue(blocked['blocked'])
        self.assertLess(blocked['damage'], plain['damage'])

    def test_magic_power_scales_existing_magic_direct_damage_path(self):
        battle_state = {
            'weapon_type': 'magic',
            'weapon_profile': 'magic_staff',
            'mob_hp': 500,
            'equipment_magic_power_bonus': 20,
            'vulnerability_turns': 0,
            'press_the_line_turns': 0,
            'berserk_turns': 0,
        }

        from game.combat import finalize_player_direct_damage_action
        plain = finalize_player_direct_damage_action(dict(battle_state, equipment_magic_power_bonus=0), base_damage=100, can_consume_guaranteed_crit=False, damage_school='magic')
        boosted = finalize_player_direct_damage_action(dict(battle_state), base_damage=100, can_consume_guaranteed_crit=False, damage_school='magic')

        self.assertEqual(plain['final_damage'], 100)
        self.assertEqual(boosted['final_damage'], 120)

    def test_healing_power_scales_existing_heal_path(self):
        player = {'mana': 100, 'wisdom': 18}
        state_plain = {
            'weapon_damage': 14,
            'weapon_type': 'light',
            'weapon_profile': 'holy_staff',
            'player_hp': 10,
            'player_max_hp': 300,
            'equipment_healing_power_bonus': 0,
        }
        state_boosted = dict(state_plain, equipment_healing_power_bonus=25)
        mob_state = {'hp': 100, 'defense': 0, 'effects': []}

        with patch('game.skill_engine.get_skill_level', return_value=1), patch('game.skill_engine.get_skill_cooldown', return_value=0), patch('game.skill_engine.set_skill_cooldown'):
            plain = use_skill('heal', dict(player), dict(mob_state), dict(state_plain), telegram_id=1001, lang='ru')
            boosted = use_skill('heal', dict(player), dict(mob_state), dict(state_boosted), telegram_id=1001, lang='ru')

        self.assertGreater(boosted['heal'], plain['heal'])

    def test_new_secondary_hooks_use_equipped_bonuses_only(self):
        bonuses = aggregate_equipped_stat_bonuses(1001)
        self.assertNotIn('block_chance', bonuses)
        self.assertNotIn('magic_power', bonuses)
        self.assertNotIn('healing_power', bonuses)

    def test_curated_secondary_stats_are_runtime_active_not_inert(self):
        bonuses = build_effective_player_stats(
            {'strength': 1, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1, 'max_hp': 100, 'max_mana': 50},
            {'block_chance': 6, 'magic_power': 8, 'healing_power': 10},
        )
        self.assertEqual(bonuses['block_chance_bonus'], 6)
        self.assertEqual(bonuses['magic_power_bonus'], 8)
        self.assertEqual(bonuses['healing_power_bonus'], 10)

    def test_legacy_items_remain_backward_compatible(self):
        bonuses = aggregate_equipped_stat_bonuses(1001)
        self.assertNotIn('strength', bonuses)

        conn = get_connection()
        player = dict(conn.execute('SELECT * FROM players WHERE telegram_id=?', (1001,)).fetchone())
        conn.close()

        effective = build_effective_player_stats(player, bonuses)
        self.assertEqual(effective['max_mana'], 60)

    def test_schema_changes_are_additive(self):
        conn = get_connection()
        equipment_columns = {
            row['name']
            for row in conn.execute('PRAGMA table_info(equipment)').fetchall()
        }
        gear_columns = {
            row['name']
            for row in conn.execute('PRAGMA table_info(gear_instances)').fetchall()
        }
        conn.close()

        self.assertIn('weapon', equipment_columns)
        self.assertIn('offhand', equipment_columns)
        self.assertIn('chest', equipment_columns)
        self.assertNotIn('effective_max_hp', equipment_columns)
        self.assertIn('base_item_id', gear_columns)
        self.assertIn('item_tier', gear_columns)

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

    def test_tiered_weapon_instance_affects_runtime_weapon_damage_path(self):
        conn = get_connection()
        conn.execute('UPDATE equipment SET weapon=NULL WHERE telegram_id=?', (1001,))
        conn.commit()
        conn.close()

        instance_id = create_gear_instance(
            1001,
            'iron_sword',
            item_tier=10,
            rarity='rare',
            secondary_rolls_json='[]',
        )
        set_gear_instance_equipped_slot(1001, instance_id, 'weapon')

        combat_items = get_equipped_combat_items(1001)
        weapon = combat_items['weapon']
        base_weapon_max = 18  # iron_sword template max damage
        self.assertGreater(weapon['damage_max'], base_weapon_max)

        conn = get_connection()
        row = dict(conn.execute('SELECT * FROM gear_instances WHERE id=?', (instance_id,)).fetchone())
        conn.close()
        resolved = resolve_gear_instance_item_data(row)
        self.assertEqual(weapon['damage_min'], resolved['damage_min'])
        self.assertEqual(weapon['damage_max'], resolved['damage_max'])

    def test_legacy_weapon_fallback_keeps_base_damage_values(self):
        combat_items = get_equipped_combat_items(1001)
        self.assertNotIn('weapon', combat_items)

        conn = get_connection()
        conn.execute('UPDATE equipment SET weapon=? WHERE telegram_id=?', (5, 1001))
        conn.commit()
        conn.close()

        combat_items = get_equipped_combat_items(1001)
        weapon = combat_items['weapon']
        self.assertEqual(weapon['damage_min'], 12)
        self.assertEqual(weapon['damage_max'], 18)

    def test_inventory_detail_does_not_overstate_unwired_scaled_defense(self):
        instance_id = create_gear_instance(
            1001,
            'tracker_jacket',
            item_tier=10,
            rarity='rare',
            secondary_rolls_json='[]',
        )
        text, _kb = build_item_detail(1001, f'g{instance_id}', 'armor', 'en')
        self.assertIn('Defense: <b>7</b>', text)
        self.assertNotIn('Defense: <b>13</b>', text)


if __name__ == '__main__':
    unittest.main()
