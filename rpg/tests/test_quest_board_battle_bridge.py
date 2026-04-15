import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.battle import _handle_victory_cleanup


class QuestBoardBattleBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_victory_cleanup_reports_kill_to_hunt_contract_tracker(self):
        query = SimpleNamespace(edit_message_text=AsyncMock())
        context = SimpleNamespace(user_data={'battle': {}, 'battle_mob': {}})
        player = {'level': 10, 'exp': 0, 'gold': 0}
        mob = {'id': 'forest_wolf'}
        battle_state = {
            'spawn_profile': 'elite',
            'special_spawn_key': 'greyfang',
            'pve_encounter_id': 'pve-test-1',
            'weapon_id': 'unarmed',
        }

        with (
            patch('handlers.battle.calc_rewards', return_value={'exp': 10, 'gold': 3, 'loot': [], 'mob_id': 'forest_wolf'}),
            patch('handlers.battle._is_group_encounter', return_value=False),
            patch('handlers.battle.apply_rewards', return_value={'leveled_up': False, 'new_level': 10, 'new_exp': 0, 'new_gold': 0}),
            patch('handlers.battle.get_player', return_value={'telegram_id': 8101, 'level': 10, 'exp': 0, 'gold': 0}),
            patch('handlers.battle.end_battle'),
            patch('handlers.battle.finish_solo_pve_encounter'),
            patch('handlers.battle.add_mastery_exp', return_value={'mastery_up': False}),
            patch('handlers.battle.register_hunt_kill_progress') as progress_mock,
            patch('handlers.battle.t', side_effect=lambda key, _lang, **kwargs: key),
            patch('handlers.battle.get_mob_name', return_value='Forest Wolf'),
            patch('handlers.battle.safe_edit', new=AsyncMock()),
        ):
            await _handle_victory_cleanup(
                query=query,
                context=context,
                user_id=8101,
                player=player,
                mob=mob,
                battle_state=battle_state,
                lang='en',
            )

        progress_mock.assert_called_once_with(
            player_id=8101,
            mob_id='forest_wolf',
            spawn_profile='elite',
            special_spawn_key='greyfang',
        )
