import unittest
from unittest.mock import patch
from handlers.inventory import (
    _build_metadata_text_lines,
    _get_localized_stat_label,
    is_equipped,
    get_equipped_slot_for_inventory_id,
    resolve_equip_slot_for_item,
)
from handlers.profile import _format_equipped_identity
from game.items_data import get_item_metadata


class InventoryMetadataIntegrationTests(unittest.TestCase):
    def test_detect_equipped_slot_by_inventory_id(self):
        equipped = {'telegram_id': 999, 'weapon': 11, 'offhand': 12, 'ring1': 21, 'ring2': None, 'amulet': 31}
        self.assertEqual(get_equipped_slot_for_inventory_id(equipped, 12), 'offhand')
        self.assertEqual(get_equipped_slot_for_inventory_id(equipped, 31), 'amulet')
        self.assertIsNone(get_equipped_slot_for_inventory_id(equipped, 999))

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
        mocked_equipment = {'telegram_id': 777, 'weapon': 101, 'offhand': None}
        with patch('handlers.inventory.get_equipped', return_value=mocked_equipment):
            self.assertTrue(is_equipped(777, 101))
            self.assertFalse(is_equipped(777, 777))


if __name__ == '__main__':
    unittest.main()
