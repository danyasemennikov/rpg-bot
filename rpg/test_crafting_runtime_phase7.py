import os
import tempfile
import unittest
from unittest.mock import patch

import database
from database import get_connection, init_db
from game.crafting_runtime import (
    RECIPE_BY_ID,
    RecipeDefinition,
    RecipeRequirement,
    _aggregate_recipe_requirements,
    craft_recipe,
    get_recipe,
    validate_recipe_contract,
)


class CraftingRuntimePhase7Tests(unittest.TestCase):
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
            (9101, 'craft', 'CraftTester', 10, 500, 100, 100, 60, 60, 8, 8, 8, 8, 8, 8, 'village'),
        )

        from game.items_data import get_item
        for item_id in (
            'herb_common',
            'herb_magic',
            'spider_venom',
            'health_potion_small',
            'iron_ore',
            'coal',
            'wood_dark',
            'wolf_fang',
            'iron_sword',
        ):
            item = get_item(item_id)
            conn.execute(
                '''INSERT INTO items (
                    item_id, name, item_type, rarity, buy_price, req_level,
                    req_strength, req_agility, req_intuition, req_wisdom, stat_bonus_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    item['item_id'],
                    item['name'],
                    item['item_type'],
                    item['rarity'],
                    item.get('buy_price', 0),
                    item.get('req_level', 1),
                    item.get('req_strength', 0),
                    item.get('req_agility', 0),
                    item.get('req_intuition', 0),
                    item.get('req_wisdom', 0),
                    item.get('stat_bonus_json', '{}'),
                ),
            )

        conn.commit()
        conn.close()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def _set_inventory(self, item_id: str, quantity: int):
        conn = get_connection()
        row = conn.execute(
            'SELECT id FROM inventory WHERE telegram_id=? AND item_id=?',
            (9101, item_id),
        ).fetchone()
        if row:
            conn.execute('UPDATE inventory SET quantity=? WHERE id=?', (quantity, row['id']))
        else:
            conn.execute(
                'INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)',
                (9101, item_id, quantity),
            )

        conn.commit()
        conn.close()

    def _get_inventory_qty(self, item_id: str) -> int:
        conn = get_connection()
        row = conn.execute(
            'SELECT quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (9101, item_id),
        ).fetchone()
        conn.close()
        return int(row['quantity']) if row else 0

    def test_recipe_schema_defaults_to_permanent(self):
        recipe = get_recipe('alchemy_minor_health_potion')
        self.assertIsNotNone(recipe)
        assert recipe is not None
        self.assertTrue(recipe.recipes_are_permanent)

    def test_recipe_contract_uses_profession_material_contract(self):
        invalid_recipe = RecipeDefinition(
            recipe_id='invalid_alchemy_ore_recipe',
            output_item_id='health_potion_small',
            output_quantity=1,
            profession_key='alchemy',
            minimum_profession_level=1,
            material_requirements=(RecipeRequirement(item_id='iron_ore', quantity=1),),
        )
        errors = validate_recipe_contract(invalid_recipe)
        self.assertTrue(errors)
        self.assertTrue(any('not allowed for alchemy' in error for error in errors))

    def test_starter_recipe_contract_is_valid_for_output_and_material_domains(self):
        errors = validate_recipe_contract(RECIPE_BY_ID['alchemy_minor_health_potion'])
        self.assertEqual(errors, [])

    def test_recipe_contract_rejects_output_domain_conflict(self):
        invalid_output_recipe = RecipeDefinition(
            recipe_id='invalid_alchemy_sword_output',
            output_item_id='iron_sword',
            output_quantity=1,
            profession_key='alchemy',
            minimum_profession_level=1,
            material_requirements=(
                RecipeRequirement(item_id='herb_common', quantity=2),
                RecipeRequirement(item_id='herb_magic', quantity=1),
            ),
            special_ingredient_requirements=(
                RecipeRequirement(item_id='spider_venom', quantity=1),
            ),
        )
        errors = validate_recipe_contract(invalid_output_recipe)
        self.assertTrue(any('output families' in error for error in errors))

    def test_validation_path_uses_craft_identity_resolver(self):
        with patch('game.crafting_runtime.resolve_crafting_material_identity', return_value=None):
            errors = validate_recipe_contract(RECIPE_BY_ID['alchemy_minor_health_potion'])
        self.assertTrue(errors)
        self.assertTrue(any('missing crafting identity' in error for error in errors))

    def test_profession_requirement_is_checked(self):
        result = craft_recipe(
            telegram_id=9101,
            recipe_id='blacksmith_iron_sword',
            profession_levels={'blacksmith': 1},
        )
        self.assertEqual(result.status, 'profession_level_too_low')
        self.assertEqual(result.required_profession_level, 2)

    def test_material_consumption_and_output_grant_for_stackable_recipe(self):
        self._set_inventory('herb_common', 5)
        self._set_inventory('herb_magic', 2)
        self._set_inventory('spider_venom', 1)

        result = craft_recipe(
            telegram_id=9101,
            recipe_id='alchemy_minor_health_potion',
            profession_levels={'alchemy': 2},
        )

        self.assertEqual(result.status, 'crafted')
        self.assertEqual(result.crafted_item_id, 'health_potion_small')
        self.assertEqual(result.crafted_quantity, 1)
        self.assertEqual(self._get_inventory_qty('herb_common'), 3)
        self.assertEqual(self._get_inventory_qty('herb_magic'), 1)
        self.assertEqual(self._get_inventory_qty('spider_venom'), 0)
        self.assertEqual(self._get_inventory_qty('health_potion_small'), 1)

    def test_starter_recipe_runtime_end_to_end_for_gear_output(self):
        self._set_inventory('iron_ore', 3)
        self._set_inventory('coal', 1)
        self._set_inventory('wood_dark', 1)
        self._set_inventory('wolf_fang', 1)

        result = craft_recipe(
            telegram_id=9101,
            recipe_id='blacksmith_iron_sword',
            profession_levels={'blacksmith': 3},
        )

        self.assertEqual(result.status, 'crafted')
        self.assertEqual(result.crafted_item_id, 'iron_sword')

        conn = get_connection()
        gear_row = conn.execute(
            'SELECT id, base_item_id FROM gear_instances WHERE telegram_id=? AND base_item_id=?',
            (9101, 'iron_sword'),
        ).fetchone()
        conn.close()

        self.assertIsNotNone(gear_row)
        self.assertEqual(self._get_inventory_qty('iron_ore'), 0)
        self.assertEqual(self._get_inventory_qty('coal'), 0)

    def test_crafting_is_atomic_when_grant_fails(self):
        self._set_inventory('herb_common', 5)
        self._set_inventory('herb_magic', 2)
        self._set_inventory('spider_venom', 1)

        with patch('game.crafting_runtime.grant_item_to_player', side_effect=RuntimeError('grant_failed')):
            result = craft_recipe(
                telegram_id=9101,
                recipe_id='alchemy_minor_health_potion',
                profession_levels={'alchemy': 2},
            )

        self.assertEqual(result.status, 'craft_failed_atomic')
        self.assertEqual(self._get_inventory_qty('herb_common'), 5)
        self.assertEqual(self._get_inventory_qty('herb_magic'), 2)
        self.assertEqual(self._get_inventory_qty('spider_venom'), 1)

    def test_duplicate_requirements_are_aggregated_for_validation_and_consume(self):
        duplicate_recipe = RecipeDefinition(
            recipe_id='dup_req_recipe',
            output_item_id='health_potion_small',
            output_quantity=1,
            profession_key='alchemy',
            minimum_profession_level=1,
            material_requirements=(
                RecipeRequirement(item_id='herb_common', quantity=2, expected_group='herb_base'),
                RecipeRequirement(item_id='herb_common', quantity=2, expected_group='herb_base'),
            ),
            special_ingredient_requirements=(
                RecipeRequirement(item_id='spider_venom', quantity=1, expected_group='venom'),
            ),
        )
        self.assertEqual(validate_recipe_contract(duplicate_recipe), [])

        aggregated = _aggregate_recipe_requirements(duplicate_recipe)
        self.assertEqual(aggregated['bulk']['herb_common'], 4)

        self._set_inventory('herb_common', 4)
        self._set_inventory('spider_venom', 1)

        result = craft_recipe(
            telegram_id=9101,
            recipe_id='alchemy_minor_health_potion',
            profession_levels={'alchemy': 2},
        )
        self.assertEqual(result.status, 'missing_materials')

        original = RECIPE_BY_ID['alchemy_minor_health_potion']
        RECIPE_BY_ID['alchemy_minor_health_potion'] = duplicate_recipe
        try:
            result = craft_recipe(
                telegram_id=9101,
                recipe_id='alchemy_minor_health_potion',
                profession_levels={'alchemy': 2},
            )
        finally:
            RECIPE_BY_ID['alchemy_minor_health_potion'] = original

        self.assertEqual(result.status, 'crafted')
        self.assertEqual(self._get_inventory_qty('herb_common'), 0)
        self.assertEqual(self._get_inventory_qty('spider_venom'), 0)

    def test_contract_rejects_duplicate_item_across_bulk_and_special(self):
        cross_kind_duplicate_recipe = RecipeDefinition(
            recipe_id='cross_kind_dup_recipe',
            output_item_id='health_potion_small',
            output_quantity=1,
            profession_key='alchemy',
            minimum_profession_level=1,
            material_requirements=(
                RecipeRequirement(item_id='herb_common', quantity=2, expected_group='herb_base'),
            ),
            special_ingredient_requirements=(
                RecipeRequirement(item_id='herb_common', quantity=1, expected_group='venom'),
            ),
        )

        errors = validate_recipe_contract(cross_kind_duplicate_recipe)
        self.assertTrue(any('duplicate requirement across bulk and special' in error for error in errors))


if __name__ == '__main__':
    unittest.main()
