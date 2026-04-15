import unittest
from unittest.mock import patch
from handlers.inventory import (
    _build_metadata_text_lines,
    _calc_safe_restore_amount,
    _get_localized_stat_label,
    is_equipped,
    get_equipped_slot_for_inventory_id,
    get_equipped_slot_for_entry_token,
    make_entry_token,
    resolve_equip_slot_for_item,
)
from handlers.profile import _format_equipped_identity
from game.items_data import get_item_metadata


class InventoryMetadataIntegrationTests(unittest.TestCase):
    def test_detect_equipped_slot_by_inventory_id(self):
        equipped = {
            'telegram_id': 999,
            'weapon': make_entry_token('legacy_inventory', 11),
            'offhand': make_entry_token('legacy_inventory', 12),
            'ring1': make_entry_token('gear_instance', 21),
            'ring2': None,
            'amulet': make_entry_token('legacy_inventory', 31),
        }
        self.assertEqual(get_equipped_slot_for_inventory_id(equipped, 12), 'offhand')
        self.assertEqual(get_equipped_slot_for_inventory_id(equipped, 31), 'amulet')
        self.assertIsNone(get_equipped_slot_for_inventory_id(equipped, 999))
        self.assertEqual(get_equipped_slot_for_entry_token(equipped, 'g21'), 'ring1')

    def test_resolve_equip_slot_uses_normalized_slot_identity(self):
        eq = {'weapon': None, 'offhand': None, 'ring1': None, 'ring2': None, 'amulet': None}

        self.assertEqual(resolve_equip_slot_for_item('oak_guard_shield', eq), 'offhand')
        self.assertEqual(resolve_equip_slot_for_item('militia_cuirass', eq), 'chest')
        self.assertEqual(resolve_equip_slot_for_item('ring_of_quiet_mind', eq), 'ring1')

        eq['ring1'] = 101
        self.assertEqual(resolve_equip_slot_for_item('band_of_precision', eq), 'ring2')

    def test_metadata_lines_render_offhand_and_armor_identity(self):
        shield_lines = _build_metadata_text_lines(get_item_metadata('warden_kite_shield'), 'en')
        robe_lines = _build_metadata_text_lines(get_item_metadata('acolyte_robe'), 'en')

        self.assertTrue(any('Offhand' in line for line in shield_lines))
        self.assertTrue(any('Shield' in line for line in shield_lines))
        self.assertTrue(any('Light' in line for line in robe_lines))

    def test_profile_identity_formatter_uses_normalized_metadata(self):
        offhand_tag = _format_equipped_identity('azure_focus_prism', 'en')
        chest_tag = _format_equipped_identity('militia_cuirass', 'en')

        self.assertIn('Focus', offhand_tag)
        self.assertNotIn('focus', offhand_tag)
        self.assertIn('Heavy armor', chest_tag)
        self.assertNotIn('heavy', chest_tag)

    def test_inventory_stat_labels_are_localized_for_secondary_stats(self):
        self.assertEqual(_get_localized_stat_label('magic_power', 'en'), '🔮 Magic Power')
        self.assertEqual(_get_localized_stat_label('physical_defense', 'ru'), '🛡️ Физ. защита')
        self.assertEqual(_get_localized_stat_label('cast_tempo', 'es'), '⚡ Ritmo de lanzamiento')

    def test_is_equipped_ignores_non_slot_columns(self):
        mocked_equipment = {'telegram_id': 777, 'weapon': 'i101', 'offhand': None}
        with patch('handlers.inventory.get_equipped', return_value=mocked_equipment):
            self.assertTrue(is_equipped(777, 101))
            self.assertFalse(is_equipped(777, 777))

    def test_safe_restore_amount_never_goes_negative_above_cap(self):
        self.assertEqual(_calc_safe_restore_amount(current_value=150, effective_cap=120, restore_value=30), 0)
        self.assertEqual(_calc_safe_restore_amount(current_value=100, effective_cap=120, restore_value=30), 20)
        self.assertEqual(_calc_safe_restore_amount(current_value=100, effective_cap=120, restore_value=-5), 0)


if __name__ == '__main__':
    unittest.main()
