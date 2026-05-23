import os
import tempfile
import unittest

import database
from database import get_connection, init_db
from game.gear_instances import (
    create_gear_instance,
    enhance_gear_instance_once,
    grant_item_to_player,
    resolve_enhancement_material_routing,
    set_gear_instance_equipped_slot,
)
from game.mobs import MOBS
from game.open_world_pack_balance import validate_open_world_spawn_profile_placement
from game.open_world_progression_loop import (
    build_all_open_world_progression_source_reports,
    build_open_world_progression_source_report,
    validate_open_world_progression_loop_sanity,
)
from game.open_world_pve_tuning import validate_open_world_pve_numeric_tuning_baseline
from game.open_world_readiness_gap_report import validate_open_world_readiness_gap_report
from game.open_world_reward_alignment import validate_open_world_reward_alignment_metadata
from game.open_world_reward_sanity import validate_open_world_reward_loot_sanity
from game.open_world_route_balance_report import validate_open_world_route_balance_reports
from game.skills import SKILLS
from game.equipment_stats import get_player_effective_stats


class OpenWorldProgressionLoopPR3MTests(unittest.TestCase):
    NUMERIC_READY = {'route_westwild', 'route_frostspine', 'route_ashen_ruins', 'route_mireveil'}

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self._tmpdir.name, 'test_game.db')
        init_db()
        conn = get_connection()
        conn.execute(
            '''INSERT INTO players (
                telegram_id, username, name, level, gold, hp, max_hp, mana, max_mana,
                strength, agility, intuition, vitality, wisdom, luck
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (3001, 'p3m', 'Progression', 10, 10000, 150, 150, 80, 80, 10, 10, 10, 10, 10, 10),
        )

        from game.items_data import get_item
        for item_id in ('enhance_shard', 'wooden_sword', 'tracker_jacket', 'enhancement_crystal', 'power_essence', 'ashen_core'):
            item = get_item(item_id)
            conn.execute(
                '''INSERT INTO items (
                    item_id, name, item_type, rarity, req_level,
                    req_strength, req_agility, req_intuition, req_wisdom,
                    buy_price, stat_bonus_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    item['item_id'], item['name'], item['item_type'], item['rarity'], item['req_level'],
                    item['req_strength'], item['req_agility'], item['req_intuition'], item['req_wisdom'],
                    item.get('buy_price', 0), item.get('stat_bonus_json', '{}'),
                ),
            )
        conn.commit()
        conn.close()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def test_progression_report_builds_for_all_routes(self):
        reports = build_all_open_world_progression_source_reports()
        self.assertTrue(reports)
        required = {
            'route_id', 'numeric_tuning_ready', 'is_sparse_or_stub', 'reward_category', 'reward_profile_id',
            'mob_ids', 'loot_item_ids', 'enhancement_material_ids', 'gear_template_ids',
            'has_progression_materials', 'has_rewarded_items_with_metadata', 'progression_warnings',
        }
        for report in reports:
            self.assertTrue(required.issubset(set(report.keys())))

    def test_numeric_ready_routes_have_progression_signal(self):
        any_progression = False
        for route_id in self.NUMERIC_READY:
            report = build_open_world_progression_source_report(route_id)
            self.assertTrue(report['numeric_tuning_ready'])
            self.assertTrue(report['loot_item_ids'])
            self.assertTrue(report['has_rewarded_items_with_metadata'])
            self.assertFalse(any('unknown_loot_items' in w for w in report['progression_warnings']))
            any_progression = any_progression or report['has_progression_materials']
        self.assertTrue(any_progression)

    def test_enhancement_material_recognition(self):
        report = build_open_world_progression_source_report('route_westwild')
        self.assertIn('enhance_shard', report['loot_item_ids'])
        self.assertEqual(report['item_classification']['enhance_shard'], 'enhancement_material')

    def test_reward_to_inventory_sanity(self):
        conn = get_connection()
        before = conn.execute(
            'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (3001, 'enhance_shard'),
        ).fetchone()
        conn.close()

        grant_item_to_player(3001, 'enhance_shard', quantity=2)

        conn = get_connection()
        after = conn.execute(
            'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (3001, 'enhance_shard'),
        ).fetchone()
        conn.close()
        before_qty = 0 if before is None else int(before['quantity'])
        self.assertEqual(int(after['quantity']), before_qty + 2)

        with self.assertRaises(Exception):
            grant_item_to_player(3001, 'invalid_item_id', quantity=1)

    def test_gear_acquisition_and_effective_stats_sanity(self):
        conn = get_connection()
        player = dict(conn.execute('SELECT * FROM players WHERE telegram_id=?', (3001,)).fetchone())
        conn.close()

        before = get_player_effective_stats(3001, player)
        self.assertEqual(before['equipment_bonuses'], {})

        # tracker_jacket is already used by runtime integration tests and has stable runtime bonuses.
        instance_id = create_gear_instance(3001, 'tracker_jacket')
        set_gear_instance_equipped_slot(3001, instance_id, 'chest')

        after = get_player_effective_stats(3001, player)
        self.assertNotEqual(after['equipment_bonuses'], before['equipment_bonuses'])
        self.assertTrue(any(v > 0 for v in after['runtime_equipment_bonuses'].values()))
        self.assertNotEqual(after['runtime_equipment_bonuses'], before['runtime_equipment_bonuses'])

    def test_enhancement_sanity(self):
        decision = resolve_enhancement_material_routing('enhance_shard', 'open_world_normal')
        self.assertIsNotNone(decision)
        self.assertTrue(decision.is_allowed)

        grant_item_to_player(3001, 'enhance_shard', quantity=10)
        instance_id = create_gear_instance(3001, 'wooden_sword')
        result = enhance_gear_instance_once(3001, instance_id, rng_roll=0.01)
        self.assertIn('ok', result)

    def test_validators_stay_green(self):
        self.assertEqual(validate_open_world_reward_loot_sanity(), [])
        self.assertEqual(validate_open_world_pve_numeric_tuning_baseline(), [])
        self.assertEqual(validate_open_world_spawn_profile_placement(), [])
        self.assertEqual(validate_open_world_reward_alignment_metadata(), [])
        self.assertEqual(validate_open_world_route_balance_reports(), [])
        self.assertEqual(validate_open_world_readiness_gap_report(), [])
        self.assertEqual(validate_open_world_progression_loop_sanity(), [])

    def test_sunscar_remains_excluded_with_actionable_gap(self):
        report = build_open_world_progression_source_report('route_sunscar')
        self.assertFalse(report['numeric_tuning_ready'])
        self.assertIn('no_pack_mobs_on_non_stub_route', report['actionable_warnings'])

    def test_pr3k_and_pr3l_baselines_are_frozen(self):
        self.assertEqual((MOBS['white_wolf']['level'], MOBS['white_wolf']['hp'], MOBS['white_wolf']['damage_min'], MOBS['white_wolf']['damage_max']), (4, 58, 8, 13))
        self.assertEqual((MOBS['mountain_stone_golem']['level'], MOBS['mountain_stone_golem']['hp'], MOBS['mountain_stone_golem']['damage_min'], MOBS['mountain_stone_golem']['damage_max']), (10, 210, 15, 24))
        self.assertEqual((MOBS['zombie']['level'], MOBS['zombie']['hp'], MOBS['zombie']['damage_min'], MOBS['zombie']['damage_max']), (4, 62, 7, 12))
        self.assertEqual((MOBS['leech']['level'], MOBS['leech']['hp'], MOBS['leech']['damage_min'], MOBS['leech']['damage_max']), (3, 38, 5, 9))
        self.assertEqual((MOBS['drowned']['level'], MOBS['drowned']['hp'], MOBS['drowned']['damage_min'], MOBS['drowned']['damage_max']), (10, 138, 20, 30))

        self.assertEqual((MOBS['mountain_stone_golem']['exp_reward'], MOBS['mountain_stone_golem']['gold_min'], MOBS['mountain_stone_golem']['gold_max']), (110, 5, 14))
        self.assertEqual((MOBS['drowned']['exp_reward'], MOBS['drowned']['gold_min'], MOBS['drowned']['gold_max']), (105, 5, 14))

    def test_targeting_rollout_remains_frozen(self):
        expected = {
            'flame_wave', 'heavy_swing', 'cleave_through', 'arcane_lance',
            'hunters_mark', 'aimed_shot', 'piercing_arrow', 'deadeye',
        }
        actual = {skill_id for skill_id, skill in SKILLS.items() if skill.get('target_pattern_id') is not None}
        self.assertEqual(actual, expected)


    def test_progression_doc_guard_contains_required_scope_language(self):
        from pathlib import Path

        doc_path = Path(__file__).resolve().parents[1] / 'docs' / 'OPEN_WORLD_PROGRESSION_LOOP_PASS1.md'
        self.assertTrue(doc_path.exists())
        text = doc_path.read_text(encoding='utf-8').lower()

        required_phrases = (
            'open-world pve rewards',
            'inventory/material intake',
            'equipment/enhancement',
            'route_sunscar',
            'no combat formula changes',
            'no mob combat stat changes',
            'no reward formula',
            'no new mobs',
            'no route topology changes',
            'no mixed-mob pack',
            'no pvp behavior',
            'full direct route gear-drop tuning remains future work',
            'no spawn probability changes',
            'no skill targeting rollout changes',
        )
        for phrase in required_phrases:
            self.assertIn(phrase, text)

if __name__ == '__main__':
    unittest.main()
