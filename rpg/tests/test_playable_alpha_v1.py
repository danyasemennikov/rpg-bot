"""Chapter acceptance through production Telegram actions with ordinary stats.

Only randomness, travel delays and spawn availability are controlled. No rewards,
completed objectives, combat outcomes or character power are injected.
"""
import asyncio
import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from database import get_connection, get_player, get_gathering_profession_state
from game.contextual_keyboard import build_contextual_main_keyboard
from game.locations import get_location
from game.pve_live import ensure_location_pve_spawn_instances, reset_solo_pve_runtime_store
from game.quest_board import get_contract_history, get_player_hunt_contract_state
from handlers.start import start_command, handle_name_input, handle_stat_buttons
from handlers.location import handle_location_buttons, handle_combat_buttons, handle_lower_menu_gather_text, build_quest_board_message
from handlers.battle import handle_battle_buttons
from handlers.chapter import handle_chapter_buttons, build_journal, build_workshop, build_sell_menu
from handlers.inventory import handle_inventory_buttons, build_item_detail


PLAYER = 90101


def rows(sql, args=()):
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute(sql, args)]
    finally:
        conn.close()


def quantity(item):
    return rows('SELECT COALESCE(SUM(quantity),0) AS n FROM inventory WHERE telegram_id=? AND item_id=?', (PLAYER, item))[0]['n']


def buttons(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]


class Journey:
    def __init__(self, lang):
        self.user = SimpleNamespace(id=PLAYER, username='traveler', language_code=lang)
        self.lang, self.message_id = lang, 0
        self.context = SimpleNamespace(user_data={}, bot=SimpleNamespace(send_message=AsyncMock(side_effect=self.output)))
        self.context.application = SimpleNamespace(user_data={PLAYER: self.context.user_data},
                                                  create_task=lambda coro: coro.close(), bot=self.context.bot)
        self.messages = []

    async def output(self, text=None, **kwargs):
        text = text or ''
        assert len(text) <= 4096, text
        assert '[chapter.' not in text, text
        markup = kwargs.get('reply_markup')
        if markup and hasattr(markup, 'inline_keyboard'):
            assert all(len(value.encode()) <= 64 for value in buttons(markup))
        self.messages.append((text, markup))
        return SimpleNamespace(message_id=self.message_id)

    async def callback(self, data, handler):
        self.message_id += 1
        message = SimpleNamespace(message_id=self.message_id, chat_id=PLAYER, reply_text=AsyncMock(side_effect=self.output))
        query = SimpleNamespace(data=data, from_user=self.user, answer=AsyncMock(), message=message,
                                edit_message_text=AsyncMock(side_effect=self.output))
        await handler(SimpleNamespace(callback_query=query, effective_user=self.user, effective_message=message), self.context)
        return query

    async def text(self, text, handler):
        self.message_id += 1
        message = SimpleNamespace(text=text, message_id=self.message_id, chat_id=PLAYER, reply_text=AsyncMock(side_effect=self.output))
        await handler(SimpleNamespace(message=message, effective_user=self.user, effective_message=message), self.context)

    async def travel(self, *locations):
        for location in locations:
            with patch('handlers.location.asyncio.sleep', new=AsyncMock()):
                await self.callback(f'goto_{location}', handle_location_buttons)
            assert get_player(PLAYER)['location_id'] == location

    async def gather(self, profession, count):
        from game.contextual_keyboard import resolve_lower_gather_profession_button
        for _ in range(count):
            player = dict(get_player(PLAYER))
            keyboard = build_contextual_main_keyboard(player, self.lang)
            label = next(b.text for row in keyboard.keyboard for b in row
                         if resolve_lower_gather_profession_button(b.text, player, self.lang) == profession)
            with patch('game.gathering_runtime.random.random', return_value=0.0):
                await self.text(label, handle_lower_menu_gather_text)

    async def accept(self, key):
        _, markup = build_quest_board_message(dict(get_player(PLAYER)), get_location(get_player(PLAYER)['location_id']))
        data = f'quest_board_accept_{key}'
        assert data in buttons(markup)
        await self.callback(data, handle_location_buttons)
        assert get_player_hunt_contract_state(PLAYER)['contract_key'] == key

    async def claim(self):
        state = get_player_hunt_contract_state(PLAYER)
        assert state['status'] == 'completed', state
        _, markup = build_quest_board_message(dict(get_player(PLAYER)), get_location(get_player(PLAYER)['location_id']))
        data = next(b for b in buttons(markup) if b.startswith('quest_board_claim_'))
        if state['contract_key'] == 'chapter_first_watch':
            from game.quest_board import claim_completed_hunt_contract
            from tests.test_alpha_transactions_v1 import snapshot, grant_then_fail
            before = snapshot()
            with patch('game.quest_board.grant_item_to_player', side_effect=grant_then_fail):
                assert claim_completed_hunt_contract(player_id=PLAYER, location_id='capital_city',
                    action_token=data.removeprefix('quest_board_claim_'))[1] == 'reward_delivery_failed'
            assert snapshot() == before
        await self.callback(data, handle_location_buttons)
        after = dict(get_player(PLAYER))
        await self.callback(data, handle_location_buttons)
        assert (get_player(PLAYER)['exp'], get_player(PLAYER)['gold']) == (after['exp'], after['gold'])
        assert state['contract_key'] in get_contract_history(PLAYER)

    async def fight(self, mob, restart=False):
        location = get_player(PLAYER)['location_id']
        ensure_location_pve_spawn_instances(location_id=location)
        # Controlled spawn availability: one ordinary creature, unchanged template.
        conn = get_connection()
        conn.execute("UPDATE pve_spawn_instances SET state='respawning', respawn_available_at='2099-01-01' WHERE location_id=?", (location,))
        spawn = conn.execute("SELECT spawn_instance_id FROM pve_spawn_instances WHERE location_id=? AND mob_id=? AND spawn_profile='normal' LIMIT 1", (location, mob)).fetchone()
        assert spawn, mob
        conn.execute("UPDATE pve_spawn_instances SET state='idle', linked_encounter_id=NULL, respawn_available_at=NULL WHERE spawn_instance_id=?", (spawn[0],))
        conn.commit()
        conn.close()
        await self.callback(f'fight_spawn_{spawn[0]}', handle_combat_buttons)
        encounter = rows("SELECT encounter_id FROM pve_encounters WHERE owner_player_id=? AND status='active'", (PLAYER,))[0]['encounter_id']
        await self.callback(f'pve_enter_{encounter}', handle_location_buttons)
        for turn in range(100):
            state = self.context.user_data.get('battle')
            if not state:
                break
            assert not state.get('player_dead'), (mob, state)
            if state['player_hp'] < 65 and quantity('health_potion_small'):
                await self.callback(f'battle_potions_{mob}', handle_battle_buttons)
                token = next(b for b in buttons(self.messages[-1][1]) if b.startswith('battle_use_potion_'))
                await self.callback(token, handle_battle_buttons)
            if restart and turn == 1:
                self.context.user_data.clear()
                reset_solo_pve_runtime_store()
            await self.callback(f'battle_attack_{mob}', handle_battle_buttons)
        assert rows('SELECT status FROM pve_encounters WHERE encounter_id=?', (encounter,))[0]['status'] == 'victory', (mob, dict(get_player(PLAYER)), self.messages[-1])
        before = (get_player(PLAYER)['exp'], get_player(PLAYER)['gold'])
        await self.callback(f'battle_attack_{mob}', handle_battle_buttons)
        assert before == (get_player(PLAYER)['exp'], get_player(PLAYER)['gold'])
        return encounter

    async def craft(self, recipe):
        from game.crafting_runtime import LIVE_RECIPE_IDS
        _, markup = build_workshop(dict(get_player(PLAYER)))
        data = [b for b in buttons(markup) if b.startswith('alpha_craft_')][LIVE_RECIPE_IDS.index(recipe)]
        response = await self.callback(data, handle_chapter_buttons)
        assert 'craft_failed' not in str(response.answer.call_args)
        return data


@pytest.mark.parametrize('lang', ['en', 'ru', 'es'])
def test_complete_chapter_with_ordinary_new_character(lang):
    asyncio.run(run_chapter(lang))


async def run_chapter(lang):
    random.seed(901)
    reset_solo_pve_runtime_store()
    j = Journey(lang)
    await j.text('/start', start_command)
    await j.text('Traveler', handle_name_input)
    for stat in ['strength'] * 3 + ['vitality'] * 3:
        await j.callback(f'stat_plus_{stat}', handle_stat_buttons)
    await j.callback('stat_confirm', handle_stat_buttons)
    assert sum(get_player(PLAYER)[s] for s in ('strength', 'vitality', 'agility', 'intuition', 'wisdom', 'luck')) == 12
    await j.callback('alpha_kit_practice_sword', handle_chapter_buttons)
    assert quantity('health_potion_small') == 3
    await j.accept('chapter_first_watch')
    await j.travel('westwild_n1')
    await j.gather('herbalism', 12)
    await j.fight('westwild_rabbit', restart=True)
    await j.fight('westwild_rabbit')
    await j.travel('capital_city')
    await j.claim()
    await j.accept('chapter_caravan')
    await j.travel('westwild_n1', 'westwild_n2')
    await j.gather('woodcutting', 3)
    for _ in range(2):
        encounter = await j.fight('forest_boar')
        from game.hunting import harvest_victory
        from tests.test_alpha_transactions_v1 import snapshot
        before = snapshot()
        assert harvest_victory(1, encounter)['status'] == 'stale_action'
        with patch('game.hunting.add_gathering_profession_exp', side_effect=RuntimeError('harvest progression')):
            with pytest.raises(RuntimeError):
                await j.callback(f'alpha_extract_{encounter}', handle_chapter_buttons)
        assert snapshot() == before
        await j.callback(f'alpha_extract_{encounter}', handle_chapter_buttons)
        before = quantity('boar_meat')
        await j.callback(f'alpha_extract_{encounter}', handle_chapter_buttons)
        assert quantity('boar_meat') == before
    await j.travel('westwild_n3', 'westwild_n4', 'westwild_n5', 'hub_westwild')
    await j.claim()
    await j.accept('chapter_outfitter')
    await j.travel('westwild_n5', 'westwild_n4', 'westwild_n3')
    for _ in range(2):
        encounter = await j.fight('forest_wolf')
        await j.callback(f'alpha_extract_{encounter}', handle_chapter_buttons)
    await j.travel('westwild_n4', 'westwild_n5', 'hub_westwild')
    await j.craft('trail_vest')
    await j.craft('trail_ration')
    gear = rows("SELECT id FROM gear_instances WHERE telegram_id=? AND base_item_id='trail_vest'", (PLAYER,))[0]['id']
    _, markup = build_item_detail(PLAYER, f'g{gear}', 'armor', lang)
    await j.callback(next(b for b in buttons(markup) if b.startswith('inv_equip_')), handle_inventory_buttons)
    await j.claim()
    await j.accept('chapter_homecoming')
    await j.travel('westwild_n5', 'westwild_n4', 'westwild_n3', 'westwild_n2', 'westwild_n1', 'capital_city')
    token = await j.craft('field_tonic')
    before = quantity('health_potion_small')
    await j.callback(token, handle_chapter_buttons)
    assert quantity('health_potion_small') == before
    _, markup = build_sell_menu(dict(get_player(PLAYER)))
    sale = next(b for b in buttons(markup) if b.startswith('alpha_sellone_'))
    await j.callback(sale, handle_chapter_buttons)
    before = get_player(PLAYER)['gold']
    await j.callback(sale, handle_chapter_buttons)
    assert get_player(PLAYER)['gold'] == before
    await j.claim()
    assert len(get_contract_history(PLAYER)) == 4
    assert get_player(PLAYER)['level'] > 1
    assert get_gathering_profession_state(PLAYER, 'herbalism')['level'] >= 2
    assert rows('SELECT SUM(exp) AS xp FROM player_crafting_professions WHERE player_id=?', (PLAYER,))[0]['xp'] > 0
    potion = rows("SELECT id FROM inventory WHERE telegram_id=? AND item_id='field_ration'", (PLAYER,))[0]['id']
    _, markup = build_item_detail(PLAYER, str(potion), 'potion', lang)
    token = next(b for b in buttons(markup) if b.startswith('inv_use_'))
    await j.callback(token, handle_inventory_buttons)
    assert quantity('field_ration') == 0
    await j.callback(token, handle_inventory_buttons)
    await j.output(*build_journal(dict(get_player(PLAYER)))[:1], reply_markup=build_journal(dict(get_player(PLAYER)))[1])
