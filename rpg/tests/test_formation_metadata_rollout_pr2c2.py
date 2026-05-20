import unittest
from unittest.mock import patch

from game.pve_live import (
    _build_participant_bootstrap_snapshot_for_player,
    _normalize_projection_snapshot,
    create_or_load_open_world_pve_encounter,
)
from game.pvp_live import _init_live_battle_payload, _resolve_combat_profile


class FormationMetadataRolloutPR2C2Tests(unittest.TestCase):
    def test_pve_participant_snapshot_includes_formation_line(self):
        battle_state = {
            'player_hp': 100,
            'player_mana': 50,
            'player_max_hp': 100,
            'player_max_mana': 50,
            'weapon_id': 'unarmed',
            'weapon_type': 'melee',
            'weapon_profile': 'melee',
            'offhand_profile': 'none',
        }
        with patch('game.pve_live.get_connection') as conn_mock:
            conn = conn_mock.return_value
            cur = conn.execute.return_value
            cur.fetchone.return_value = {
                'telegram_id': 1, 'hp': 100, 'mana': 50,
                'strength': 1, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1,
            }
            with patch('game.pve_live.get_player_effective_stats', return_value={'max_hp': 100, 'max_mana': 50}), \
                 patch('game.pve_live.get_equipped_item_ids', return_value={'weapon': 'unarmed', 'offhand': 'wooden_shield'}), \
                 patch('game.pve_live.get_item', side_effect=lambda item_id: {'offhand_profile': 'shield'} if item_id == 'wooden_shield' else {'weapon_type': 'melee'}), \
                 patch('game.pve_live.get_item_archetype_metadata', return_value={'offhand_profile': 'shield'}), \
                 patch('game.pve_live.get_item_encumbrance', return_value=0):
                snapshot = _build_participant_bootstrap_snapshot_for_player(battle_state=battle_state, participant_id=1)
        self.assertEqual(snapshot['formation_line'], 'front')

    def test_pve_bootstrap_does_not_inherit_foreign_battle_state_formation_line(self):
        battle_state = {
            'player_hp': 100,
            'player_mana': 50,
            'player_max_hp': 100,
            'player_max_mana': 50,
            'weapon_id': 'unarmed',
            'weapon_type': 'melee',
            'weapon_profile': 'melee',
            'offhand_profile': 'none',
            'formation_line': 'front',  # foreign projected participant value
        }
        with patch('game.pve_live.get_connection') as conn_mock:
            conn = conn_mock.return_value
            cur = conn.execute.return_value
            cur.fetchone.return_value = {
                'telegram_id': 2, 'hp': 100, 'mana': 50,
                'strength': 1, 'agility': 1, 'intuition': 1, 'vitality': 1, 'wisdom': 1, 'luck': 1,
            }
            with patch('game.pve_live.get_player_effective_stats', return_value={'max_hp': 100, 'max_mana': 50}), \
                 patch('game.pve_live.get_equipped_item_ids', return_value={'weapon': 'magic_staff', 'offhand': None}), \
                 patch('game.pve_live.get_item', side_effect=lambda item_id: {'weapon_type': 'magic', 'weapon_profile': 'magic_staff'} if item_id == 'magic_staff' else {}), \
                 patch('game.pve_live.get_item_archetype_metadata', return_value={}), \
                 patch('game.pve_live.get_item_encumbrance', return_value=0):
                snapshot = _build_participant_bootstrap_snapshot_for_player(battle_state=battle_state, participant_id=2)
        self.assertEqual(snapshot['formation_line'], 'ranged')

    def test_projection_normalization_preserves_participant_local_formation_line(self):
        fallback_snapshot = {
            'formation_line': 'ranged',
            'offhand_profile': 'none',
            'weapon_profile': 'magic_staff',
            'player_hp': 100,
            'player_mana': 50,
            'player_dead': False,
            'player_max_hp': 100,
            'player_max_mana': 50,
        }
        normalized = _normalize_projection_snapshot(
            {'formation_line': 'front'},
            fallback_snapshot=fallback_snapshot,
        )
        self.assertEqual(normalized['formation_line'], 'front')

    def test_pack_enemy_units_include_default_formation_line(self):
        mock_conn = patch('game.pve_live.get_connection').start()
        self.addCleanup(patch.stopall)
        conn = mock_conn.return_value
        conn.execute.return_value.fetchone.return_value = {'spawn_profile': 'normal', 'special_spawn_key': '', 'special_spawn_name': ''}
        with patch('game.pve_live._ensure_pve_encounter_table'), \
             patch('game.pve_live._ensure_world_spawn_table'), \
             patch('game.pve_live._claim_spawn_instance_for_encounter', return_value='s1'), \
             patch('game.pve_live._claim_spawn_pack_for_encounter', return_value=['s1', 's2', 's3']), \
             patch('game.pve_live.create_pve_encounter') as create_mock:
            create_or_load_open_world_pve_encounter(
                owner_player_id=1,
                location_id='x',
                mob_id='forest_wolf',
                mob={'hp': 10},
                battle_state={},
                spawn_instance_id='s1',
                pack_claim_from_visible_group=True,
            )
            created_state = create_mock.call_args.kwargs['battle_state']
        self.assertTrue(all(unit.get('formation_line') == 'melee' for unit in created_state['enemy_units']))

    def test_pvp_profile_and_payload_include_formation_metadata(self):
        with patch('game.pvp_live.get_player_effective_stats', return_value={'max_hp': 100, 'max_mana': 50}), \
             patch('game.pvp_live.get_equipped_item_ids', side_effect=lambda pid: {'weapon': 'magic_staff', 'offhand': None} if pid == 10 else {'weapon': 'iron_sword', 'offhand': 'wooden_shield'}), \
             patch('game.pvp_live.get_item', side_effect=lambda item_id: {'weapon_type': 'magic', 'weapon_profile': 'magic_staff'} if item_id == 'magic_staff' else ({'offhand_profile': 'shield'} if item_id == 'wooden_shield' else {'weapon_type': 'melee', 'weapon_profile': 'sword'})), \
             patch('game.pvp_live.get_mastery', return_value={'level': 1}), \
             patch('game.pvp_live.get_connection') as conn_mock:
            conn = conn_mock.return_value
            conn.execute.side_effect = [
                type('R', (), {'fetchone': lambda self: {'telegram_id': 10, 'hp': 100, 'max_hp': 100, 'mana': 50, 'max_mana': 50}})(),
                type('R', (), {'fetchone': lambda self: {'telegram_id': 11, 'hp': 100, 'max_hp': 100, 'mana': 50, 'max_mana': 50}})(),
            ]
            profile = _resolve_combat_profile(10, {'telegram_id': 10})
            payload = _init_live_battle_payload(attacker_id=10, defender_id=11, now=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))
        self.assertIn('formation_line', profile)
        self.assertIn('attacker_formation_line', payload)
        self.assertIn('defender_formation_line', payload)

    def test_pvp_profile_normalizes_shield_offhand_and_front_line(self):
        with patch('game.pvp_live.get_player_effective_stats', return_value={'max_hp': 100, 'max_mana': 50}), \
             patch('game.pvp_live.get_equipped_item_ids', return_value={'weapon': 'iron_sword', 'offhand': 'wooden_shield'}), \
             patch('game.pvp_live.get_item', side_effect=lambda item_id: {'offhand_profile': 'shield'} if item_id == 'wooden_shield' else {'weapon_type': 'melee', 'weapon_profile': 'sword'}), \
             patch('game.pvp_live.get_mastery', return_value={'level': 1}):
            profile = _resolve_combat_profile(10, {'telegram_id': 10})
        self.assertEqual(profile['offhand_profile'], 'shield')
        self.assertEqual(profile['formation_line'], 'front')

    def test_pvp_profile_normalizes_missing_or_invalid_offhand_to_none(self):
        with patch('game.pvp_live.get_player_effective_stats', return_value={'max_hp': 100, 'max_mana': 50}), \
             patch('game.pvp_live.get_mastery', return_value={'level': 1}):
            with patch('game.pvp_live.get_equipped_item_ids', return_value={'weapon': 'iron_sword', 'offhand': None}), \
                 patch('game.pvp_live.get_item', side_effect=lambda _item_id: {'weapon_type': 'melee', 'weapon_profile': 'sword'}):
                profile_none = _resolve_combat_profile(10, {'telegram_id': 10})
            with patch('game.pvp_live.get_equipped_item_ids', return_value={'weapon': 'iron_sword', 'offhand': 'odd_talisman'}), \
                 patch('game.pvp_live.get_item', side_effect=lambda item_id: {'offhand_profile': 'weird_value'} if item_id == 'odd_talisman' else {'weapon_type': 'melee', 'weapon_profile': 'sword'}):
                profile_invalid = _resolve_combat_profile(10, {'telegram_id': 10})
        self.assertEqual(profile_none['offhand_profile'], 'none')
        self.assertEqual(profile_invalid['offhand_profile'], 'none')


if __name__ == '__main__':
    unittest.main()
