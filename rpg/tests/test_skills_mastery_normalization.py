import os
import tempfile
import unittest
from unittest.mock import patch

import database
from game.seed import seed_items
from game.skills import normalize_weapon_family_key
from game.weapon_mastery import get_mastery
from handlers.skills_ui import build_skills_main, get_equipped_weapon


class SkillsMasteryNormalizationTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmpdir.name, 'test_game.db')
        self._db_patch = patch.object(database, 'DB_PATH', self.db_path)
        self._db_patch.start()
        database.init_db()
        seed_items()

        conn = database.get_connection()
        conn.execute(
            '''INSERT INTO players (telegram_id, username, name, level, exp, stat_points, lang)
               VALUES (?, ?, ?, 1, 0, 0, 'ru')''',
            (101, 'tester', 'Tester'),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self._db_patch.stop()
        self._tmpdir.cleanup()

    def _insert_mastery(self, weapon_id: str, level: int, exp: int, skill_points: int):
        conn = database.get_connection()
        conn.execute(
            '''INSERT INTO weapon_mastery (telegram_id, weapon_id, level, exp, skill_points)
               VALUES (?, ?, ?, ?, ?)''',
            (101, weapon_id, level, exp, skill_points),
        )
        conn.commit()
        conn.close()

    def _equip_instance_weapon(self, base_item_id: str):
        conn = database.get_connection()
        conn.execute(
            '''INSERT INTO gear_instances (
                telegram_id, base_item_id, slot_identity, item_tier, rarity,
                secondary_rolls_json, enhance_level, durability, max_durability, equipped_slot
            ) VALUES (?, ?, 'weapon', 1, 'common', '[]', 0, 100, 100, 'weapon')''',
            (101, base_item_id),
        )
        conn.commit()
        conn.close()

    def _equip_legacy_weapon(self, item_id: str):
        conn = database.get_connection()
        cursor = conn.execute(
            'INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, 1)',
            (101, item_id),
        )
        conn.execute(
            'INSERT OR REPLACE INTO equipment (telegram_id, weapon) VALUES (?, ?)',
            (101, cursor.lastrowid),
        )
        conn.commit()
        conn.close()

    def test_legacy_key_normalization_map(self):
        self.assertEqual(normalize_weapon_family_key('wooden_sword'), 'sword_1h')
        self.assertEqual(normalize_weapon_family_key('iron_sword'), 'sword_1h')
        self.assertEqual(normalize_weapon_family_key('short_bow'), 'bow')
        self.assertEqual(normalize_weapon_family_key('dagger'), 'daggers')
        self.assertEqual(normalize_weapon_family_key('fists'), 'unarmed')

    def test_old_sword_rows_collapse_into_single_sword_1h_menu_entry(self):
        self._insert_mastery('wooden_sword', level=2, exp=10, skill_points=1)
        self._insert_mastery('iron_sword', level=2, exp=15, skill_points=2)

        text, _ = build_skills_main(101, 'ru')

        self.assertIn('Одноручный меч', text)
        self.assertEqual(text.count('Одноручный меч'), 1)
        self.assertNotIn('Деревянный меч', text)
        self.assertNotIn('Железный меч', text)

    def test_short_bow_and_dagger_are_grouped_by_family_labels(self):
        self._insert_mastery('short_bow', level=2, exp=10, skill_points=1)
        self._insert_mastery('dagger', level=2, exp=10, skill_points=1)

        text, _ = build_skills_main(101, 'ru')

        self.assertIn('Лук', text)
        self.assertIn('Парные кинжалы', text)
        self.assertNotIn('Короткий лук', text)
        self.assertNotIn('Кинжал', text)

    def test_get_mastery_preserves_progress_from_legacy_rows(self):
        self._insert_mastery('wooden_sword', level=2, exp=45, skill_points=2)
        self._insert_mastery('iron_sword', level=1, exp=20, skill_points=1)

        mastery = get_mastery(101, 'sword_1h')

        self.assertEqual(mastery['weapon_id'], 'sword_1h')
        self.assertEqual(mastery['level'], 2)
        self.assertEqual(mastery['exp'], 65)
        self.assertEqual(mastery['skill_points'], 3)

    def test_menu_has_no_duplicate_legacy_buckets_when_new_and_old_rows_exist(self):
        self._insert_mastery('short_bow', level=1, exp=10, skill_points=1)
        self._insert_mastery('bow', level=2, exp=10, skill_points=1)

        text, _ = build_skills_main(101, 'ru')
        self.assertEqual(text.count('Лук'), 1)

    def test_instance_equipped_sword_resolves_sword_1h(self):
        self._equip_instance_weapon('iron_sword')
        weapon_id, _ = get_equipped_weapon(101, 'ru')
        self.assertEqual(weapon_id, 'sword_1h')

    def test_instance_equipped_bow_resolves_bow(self):
        self._equip_instance_weapon('short_bow')
        weapon_id, _ = get_equipped_weapon(101, 'ru')
        self.assertEqual(weapon_id, 'bow')

    def test_menu_marks_instance_equipped_family_with_checkmark(self):
        self._insert_mastery('short_bow', level=2, exp=10, skill_points=1)
        self._equip_instance_weapon('short_bow')

        text, _ = build_skills_main(101, 'ru')
        self.assertIn('Лук ✅', text)

    def test_legacy_fallback_for_equipped_weapon_still_works(self):
        self._equip_legacy_weapon('iron_sword')
        weapon_id, _ = get_equipped_weapon(101, 'ru')
        self.assertEqual(weapon_id, 'sword_1h')


if __name__ == '__main__':
    unittest.main()
