"""Shared PEV1 production history covering the eleven acceptance journeys.

The history uses production handlers/domain actions.  Its only accelerators are
deterministic rolls, mocked Telegram transport, and the existing controlled
respawn clock in ``ProductionJourney``.  No material, gold, recipe knowledge,
character level, or profession level is inserted or granted by the test.
"""

from __future__ import annotations

import asyncio
from collections import Counter, deque
import json
from unittest.mock import patch

from database import get_connection, get_player
from game.action_receipts import issue_actions
from game.crafting_runtime import craft_recipe
from game.gathering_runtime import gather_resource
from game.gear_progression import (
    apply_gear_intent,
    exchange_enhancement_crystal,
    issue_crystal_exchange_intent,
    issue_gear_intent,
)
from game.equipment_stats import get_player_effective_stats
from game.hunting import harvest_victory, list_harvestable_victories
from game.items_data import get_item
from game.locations import WORLD_LOCATIONS
from game.profession_recipes import ACTIVE_RECIPES, recipe_intent_payload
from game.profession_resources import ENVIRONMENTAL_SOURCES, MANDATORY_RESOURCE_IDS, RESOURCES
from game.quest_board import accept_hunt_contract, claim_completed_hunt_contract, get_contract_history
from game.recipe_knowledge import known_recipe_ids, learn_recipe
from handlers.chapter import handle_chapter_buttons
from handlers.inventory import (
    build_item_detail,
    handle_inventory_buttons,
    try_sell_inventory_item,
    use_inventory_consumable,
)
from handlers.professions import (
    build_material,
    build_mutation_result,
    build_overview,
    build_profession,
    build_receipts,
    build_recipe,
    build_resource_list,
)
from tests.test_character_builds_v1_journeys import ProductionJourney


PLAYER_ID = 989301


class FixedRoll:
    def __init__(self, value: float):
        self.value = value

    def random(self) -> float:
        return self.value


def _route(origin: str, destination: str) -> list[str]:
    if origin == destination:
        return []
    pending = deque([(origin, [])])
    visited = {origin}
    while pending:
        current, path = pending.popleft()
        for neighbor in WORLD_LOCATIONS[current]['connections']:
            if neighbor in visited:
                continue
            next_path = [*path, neighbor]
            if neighbor == destination:
                return next_path
            visited.add(neighbor)
            pending.append((neighbor, next_path))
    raise AssertionError((origin, destination))


async def _move(journey: ProductionJourney, destination: str) -> None:
    origin = str(get_player(journey.player_id)['location_id'])
    await journey.travel(*_route(origin, destination))


def _profession_level(player_id: int, table: str, player_column: str, key: str) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            f'SELECT level FROM {table} WHERE {player_column}=? AND profession_key=?',
            (player_id, key),
        ).fetchone()
        return int(row['level'])
    finally:
        conn.close()


def _quantity(player_id: int, item_id: str) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT COALESCE(SUM(quantity),0) AS qty FROM inventory WHERE telegram_id=? AND item_id=?',
            (player_id, item_id),
        ).fetchone()
        return int(row['qty'])
    finally:
        conn.close()


def _environment_source(item_id: str) -> tuple[str, str, float]:
    resource = RESOURCES[item_id]
    for location_id, rows in ENVIRONMENTAL_SOURCES.items():
        cumulative = 0.0
        for source_id, chance in rows:
            if RESOURCES.get(source_id, resource).profession_key != resource.profession_key:
                continue
            if source_id == item_id:
                return location_id, resource.profession_key, cumulative + chance / 2
            cumulative += chance
    raise AssertionError(item_id)


async def _gather(journey: ProductionJourney, item_id: str, count: int, sequence: list[str]) -> None:
    location_id, profession, roll = _environment_source(item_id)
    await _move(journey, location_id)
    before = _quantity(journey.player_id, item_id)
    for index in range(count):
        request_id = f'gather:pev1:{len(sequence)}:{index}:{item_id}'
        result = gather_resource(
            journey.player_id, profession, location_id=location_id,
            request_id=request_id, rng=FixedRoll(roll),
        )
        assert result['status'] == 'gathered', (item_id, result)
        sequence.append(request_id)
    assert _quantity(journey.player_id, item_id) == before + count


async def _gather_at(
    journey: ProductionJourney, item_id: str, location_id: str, count: int,
    sequence: list[str],
) -> None:
    resource = RESOURCES[item_id]
    cumulative = 0.0
    roll = None
    for source_id, chance in ENVIRONMENTAL_SOURCES[location_id]:
        if RESOURCES[source_id].profession_key != resource.profession_key:
            continue
        if source_id == item_id:
            roll = cumulative + chance / 2
            break
        cumulative += chance
    assert roll is not None, (location_id, item_id)
    await _move(journey, location_id)
    before = _quantity(journey.player_id, item_id)
    for index in range(count):
        request_id = f'gather:pev1:{len(sequence)}:{index}:{location_id}:{item_id}'
        result = gather_resource(
            journey.player_id, resource.profession_key, location_id=location_id,
            request_id=request_id, rng=FixedRoll(roll),
        )
        assert result['status'] == 'gathered', (location_id, item_id, result)
        sequence.append(request_id)
    assert _quantity(journey.player_id, item_id) == before + count


async def _gather_to_level(
    journey: ProductionJourney, profession: str, item_id: str, target: int,
    sequence: list[str],
) -> None:
    while _profession_level(
        journey.player_id, 'player_gathering_professions', 'telegram_id', profession,
    ) < target:
        await _gather(journey, item_id, 1, sequence)


async def _recover(journey: ProductionJourney, *, force: bool = False) -> None:
    player = dict(get_player(journey.player_id))
    effective = get_player_effective_stats(journey.player_id, player)
    if not force and int(player['hp']) * 10 > int(effective['max_hp']) * 7:
        return
    origin = str(player['location_id'])
    await _move(journey, 'capital_city')
    while int(get_player(journey.player_id)['gold']) < 12:
        conn = get_connection()
        try:
            row = conn.execute('''SELECT inv.id, inv.quantity FROM inventory inv
                JOIN items i ON i.item_id=inv.item_id
                WHERE inv.telegram_id=? AND i.item_type='material' AND i.sell_price>0
                ORDER BY i.sell_price DESC, inv.item_id LIMIT 1''', (journey.player_id,)).fetchone()
        finally:
            conn.close()
        assert row
        payload = f"{row['id']}:{row['quantity']}"
        token = issue_actions(journey.player_id, 'sell', [payload])[payload]
        assert try_sell_inventory_item(journey.player_id, token)['status'] == 'sold'
    await journey.rest_at_current_inn()
    await _move(journey, origin)


async def _fight_and_harvest(
    journey: ProductionJourney, *, location_id: str, mob_id: str, item_id: str,
    encounter_ids: list[str],
) -> None:
    await _move(journey, location_id)
    await _recover(journey)
    opening = (
        (('skill', 'defensive_stance'), ('skill', 'shield_bash'), ('skill', 'sword_rush'))
        if mob_id == 'troll' else ()
    )
    fight = await journey.fight(mob_id, opening=opening, use_potions=mob_id == 'troll')
    encounter_id = fight['encounter_id']
    choice = next(
        row for row in list_harvestable_victories(journey.player_id, page_size=20)
        if row['encounter_id'] == encounter_id and row['item_id'] == item_id
    )
    payload = json.dumps(
        {'encounter_id': encounter_id, 'unit_id': choice['unit_id'], 'item_id': item_id},
        sort_keys=True, separators=(',', ':'),
    )
    token = issue_actions(journey.player_id, 'harvest', [payload])[payload]
    result = harvest_victory(
        journey.player_id, encounter_id, unit_id=choice['unit_id'], item_id=item_id,
        action_token=token,
    )
    assert result['status'] == 'harvested', result
    replay = harvest_victory(
        journey.player_id, encounter_id, unit_id=choice['unit_id'], item_id=item_id,
        action_token=token,
    )
    assert replay['status'] == 'harvested' and replay['recovered']
    encounter_ids.append(encounter_id)


async def _prove_battle_consumable(journey: ProductionJourney) -> None:
    """Create a deficit in real combat, then consume through the battle path."""
    await _move(journey, 'westwild_n2')
    for _ in range(4):
        await journey.fight('forest_boar')
        player = get_player(journey.player_id)
        if int(player['hp']) < int(player['max_hp']):
            break
    player = get_player(journey.player_id)
    assert int(player['hp']) < int(player['max_hp'])
    proof = await journey.fight('forest_boar', use_potions=True)
    assert proof['battle_potions_used'] > 0


async def _learn_and_craft(journey: ProductionJourney, recipe_id: str) -> None:
    if recipe_id not in set(known_recipe_ids(journey.player_id)):
        payload = recipe_intent_payload(recipe_id)
        token = issue_actions(journey.player_id, 'learn', [payload])[payload]
        assert learn_recipe(journey.player_id, recipe_id, action_token=token)['status'] == 'learned'
    payload = recipe_intent_payload(recipe_id)
    token = issue_actions(journey.player_id, 'craft', [payload])[payload]
    assert craft_recipe(journey.player_id, recipe_id, action_token=token).status == 'crafted'


async def _claim_chapter_contract(
    journey: ProductionJourney, contract_key: str, location_id: str,
) -> None:
    await _move(journey, location_id)
    token = issue_actions(journey.player_id, 'contract_claim', [contract_key])[contract_key]
    claimed, status, result = claim_completed_hunt_contract(
        player_id=journey.player_id,
        location_id=location_id,
        action_token=token,
    )
    assert claimed and status == 'claimed' and result, (contract_key, status, result)


async def _complete_aster_elmor_chapter(
    journey: ProductionJourney, gather_ids: list[str], encounter_ids: list[str],
) -> set[str]:
    """Complete all four chapter contracts through their production authorities."""
    accepted, status = accept_hunt_contract(
        player_id=journey.player_id,
        location_id='capital_city',
        contract_key='chapter_first_watch',
    )
    assert accepted and status == 'accepted'
    await _gather_at(journey, 'herb_common', 'westwild_n1', 3, gather_ids)
    for _ in range(2):
        fight = await journey.fight('westwild_rabbit')
        encounter_ids.append(fight['encounter_id'])
    await _claim_chapter_contract(journey, 'chapter_first_watch', 'capital_city')

    accepted, status = accept_hunt_contract(
        player_id=journey.player_id,
        location_id='capital_city',
        contract_key='chapter_caravan',
    )
    assert accepted and status == 'accepted'
    await _gather_at(journey, 'wood_common', 'westwild_n2', 3, gather_ids)
    for _ in range(2):
        await _fight_and_harvest(
            journey,
            location_id='westwild_n2',
            mob_id='forest_boar',
            item_id='boar_meat',
            encounter_ids=encounter_ids,
        )
    await _claim_chapter_contract(journey, 'chapter_caravan', 'hub_westwild')

    accepted, status = accept_hunt_contract(
        player_id=journey.player_id,
        location_id='hub_westwild',
        contract_key='chapter_outfitter',
    )
    assert accepted and status == 'accepted'
    for _ in range(2):
        await _fight_and_harvest(
            journey,
            location_id='westwild_n3',
            mob_id='forest_wolf',
            item_id='wolf_pelt',
            encounter_ids=encounter_ids,
        )
    await _move(journey, 'capital_city')
    await _learn_and_craft(journey, 'trail_vest')
    await _learn_and_craft(journey, 'trail_ration')
    conn = get_connection()
    try:
        vest = conn.execute(
            "SELECT id FROM gear_instances WHERE telegram_id=? AND base_item_id='trail_vest' "
            'ORDER BY id DESC LIMIT 1',
            (journey.player_id,),
        ).fetchone()
    finally:
        conn.close()
    assert vest
    _, markup = build_item_detail(journey.player_id, f"g{vest['id']}", 'armor', 'en')
    equip = next(
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data and button.callback_data.startswith('inv_gequip_')
    )
    await journey.callback(equip, handle_inventory_buttons)
    await _claim_chapter_contract(journey, 'chapter_outfitter', 'hub_westwild')

    accepted, status = accept_hunt_contract(
        player_id=journey.player_id,
        location_id='hub_westwild',
        contract_key='chapter_homecoming',
    )
    assert accepted and status == 'accepted'
    await _gather_at(journey, 'herb_common', 'westwild_n1', 2, gather_ids)
    await _move(journey, 'capital_city')
    await _learn_and_craft(journey, 'field_tonic')
    conn = get_connection()
    try:
        sale_row = conn.execute(
            "SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id='health_potion_small' "
            'ORDER BY id LIMIT 1',
            (journey.player_id,),
        ).fetchone()
    finally:
        conn.close()
    assert sale_row
    payload = f"{sale_row['id']}:{sale_row['quantity']}"
    token = issue_actions(journey.player_id, 'sell', [payload])[payload]
    assert try_sell_inventory_item(journey.player_id, token)['status'] == 'sold'
    await _claim_chapter_contract(journey, 'chapter_homecoming', 'capital_city')
    history = get_contract_history(journey.player_id)
    expected = {
        'chapter_first_watch', 'chapter_caravan', 'chapter_outfitter', 'chapter_homecoming',
    }
    assert expected <= history
    return history


async def _equip_regional_combat_gear(journey: ProductionJourney) -> None:
    await _move(journey, 'capital_city')
    for profession, first, second, regional in (
        ('blacksmith', 'pe_sword_1h_01', 'pe_shield_06', 'pe_sword_1h_12'),
        ('heavy_armor', 'pe_heavy_chest_01', 'pe_heavy_helmet_06', 'pe_heavy_legs_12'),
    ):
        while _crafting_level(journey.player_id, profession) < 6:
            await _learn_and_craft(journey, first)
        while _crafting_level(journey.player_id, profession) < 12:
            await _learn_and_craft(journey, second)
        await _learn_and_craft(journey, regional)
    while _crafting_level(journey.player_id, 'alchemy') < 6:
        await _learn_and_craft(journey, 'field_tonic')
    while _crafting_level(journey.player_id, 'alchemy') < 12:
        await _learn_and_craft(journey, 'pe_alchemy_health_06')
    for _ in range(20):
        await _learn_and_craft(journey, 'pe_alchemy_health_06')
    for _ in range(5):
        await _learn_and_craft(journey, 'field_mana')
    conn = get_connection()
    try:
        instances = [dict(row) for row in conn.execute('''SELECT id, base_item_id FROM gear_instances
            WHERE telegram_id=? AND base_item_id IN
            ('field_sword_1h','field_shield','field_heavy_chest','field_heavy_helmet','field_heavy_legs')
            ORDER BY item_tier DESC, id DESC''', (journey.player_id,))]
    finally:
        conn.close()
    selected = {}
    for row in instances:
        selected.setdefault(row['base_item_id'], row['id'])
    for item_id in ('field_sword_1h', 'field_shield', 'field_heavy_chest', 'field_heavy_helmet', 'field_heavy_legs'):
        instance_id = selected[item_id]
        _, markup = build_item_detail(journey.player_id, f'g{instance_id}', 'weapon', 'en')
        callback = next(
            button.callback_data for row in markup.inline_keyboard for button in row
            if button.callback_data and button.callback_data.startswith('inv_gequip_')
        )
        await journey.callback(callback, handle_inventory_buttons)
        _, enhanced_markup = build_item_detail(journey.player_id, f'g{instance_id}', 'weapon', 'en')
        enhance = next((
            button.callback_data for row in enhanced_markup.inline_keyboard for button in row
            if button.callback_data and button.callback_data.startswith('inv_genh_')
        ), None)
        if enhance and item_id != 'field_sword_1h':
            with patch('game.gear_instances.random.random', return_value=0.0):
                await journey.callback(enhance, handle_inventory_buttons)
    for skill_id in ('sword_rush', 'defensive_stance', 'shield_bash'):
        await journey.learn('sword_1h', skill_id)


async def _hunt_history(journey: ProductionJourney, encounter_ids: list[str]) -> None:
    requirements = Counter()
    for recipe in ACTIVE_RECIPES:
        requirements.update(dict(recipe.requirements))
    low_plan = [('boar_meat', 'forest_boar')] * requirements['boar_meat']
    low_plan += [('wolf_pelt', 'forest_wolf')] * requirements['wolf_pelt']
    low_plan += [('wolf_fang', 'forest_wolf')] * requirements['wolf_fang']
    for item_id, mob_id in low_plan:
        await _fight_and_harvest(
            journey, location_id='westwild_n2' if mob_id == 'forest_boar' else 'westwild_n3',
            mob_id=mob_id, item_id=item_id, encounter_ids=encounter_ids,
        )
    low_training = (
        ('boar_meat', 'forest_boar', 'westwild_n2'),
        ('wolf_pelt', 'forest_wolf', 'westwild_n3'),
        ('wolf_fang', 'forest_wolf', 'westwild_n3'),
    )
    low_training_index = 0
    while _profession_level(journey.player_id, 'player_gathering_professions', 'telegram_id', 'hunting') < 6:
        item_id, mob_id, location_id = low_training[low_training_index % len(low_training)]
        low_training_index += 1
        await _fight_and_harvest(
            journey, location_id=location_id, mob_id=mob_id, item_id=item_id,
            encounter_ids=encounter_ids,
        )
    while _profession_level(journey.player_id, 'player_gathering_professions', 'telegram_id', 'hunting') < 12:
        await _fight_and_harvest(
            journey, location_id='westwild_n5', mob_id='forest_spider', item_id='spider_silk',
            encounter_ids=encounter_ids,
        )
    while _profession_level(journey.player_id, 'player_gathering_professions', 'telegram_id', 'hunting') < 18:
        await _fight_and_harvest(
            journey, location_id='westwild_n7', mob_id='bear', item_id='bear_hide',
            encounter_ids=encounter_ids,
        )
    await _equip_regional_combat_gear(journey)
    while _profession_level(journey.player_id, 'player_gathering_professions', 'telegram_id', 'hunting') < 20:
        await _fight_and_harvest(
            journey, location_id='frostspine_n7', mob_id='troll', item_id='troll_sinew',
            encounter_ids=encounter_ids,
        )


async def _sell_bark_for_learning(journey: ProductionJourney, quantity: int) -> None:
    await _move(journey, 'capital_city')
    for _ in range(quantity):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id='ancient_bark'",
                (journey.player_id,),
            ).fetchone()
        finally:
            conn.close()
        payload = f"{row['id']}:{row['quantity']}"
        token = issue_actions(journey.player_id, 'sell', [payload])[payload]
        result = try_sell_inventory_item(journey.player_id, token)
        assert result['status'] == 'sold'


def _crafting_level(player_id: int, key: str) -> int:
    return _profession_level(player_id, 'player_crafting_professions', 'player_id', key)


async def _craft_all(
    journey: ProductionJourney, action_ids: list[str], gather_ids: list[str],
) -> set[str]:
    await _move(journey, 'capital_city')
    crafted: set[str] = set()
    professions = sorted({recipe.profession_key for recipe in ACTIVE_RECIPES})
    for profession in professions:
        recipes = sorted(
            (recipe for recipe in ACTIVE_RECIPES if recipe.profession_key == profession),
            key=lambda recipe: (recipe.required_level, recipe.recipe_id),
        )
        safety = 0
        while _crafting_level(journey.player_id, profession) < 20 or any(
            recipe.recipe_id not in crafted for recipe in recipes
        ):
            safety += 1
            assert safety < 80, profession
            level = _crafting_level(journey.player_id, profession)
            known = set(known_recipe_ids(journey.player_id))
            for recipe in recipes:
                if recipe.required_level <= level and recipe.recipe_id not in known:
                    payload = recipe_intent_payload(recipe.recipe_id)
                    token = issue_actions(journey.player_id, 'learn', [payload])[payload]
                    result = learn_recipe(journey.player_id, recipe.recipe_id, action_token=token)
                    assert result['status'] in {'learned', 'already_known'}, result
                    action_ids.append(f'ui:{token}')
            known = set(known_recipe_ids(journey.player_id))
            available = [recipe for recipe in recipes if recipe.required_level <= level and recipe.recipe_id in known]
            candidate = next((recipe for recipe in available if recipe.recipe_id not in crafted), available[-1])
            environmental_ids = {
                item_id for sources in ENVIRONMENTAL_SOURCES.values() for item_id, _ in sources
            }
            for item_id, quantity in candidate.requirements:
                missing = max(0, quantity - _quantity(journey.player_id, item_id))
                if missing and item_id in environmental_ids:
                    await _gather(journey, item_id, missing, gather_ids)
            await _move(journey, 'capital_city')
            payload = recipe_intent_payload(candidate.recipe_id)
            token = issue_actions(journey.player_id, 'craft', [payload])[payload]
            result = craft_recipe(journey.player_id, candidate.recipe_id, action_token=token)
            assert result.status == 'crafted', (profession, candidate.recipe_id, result)
            replay = craft_recipe(journey.player_id, candidate.recipe_id, action_token=token)
            assert replay.status == 'crafted' and replay.recovered
            action_ids.append(f'ui:{token}')
            crafted.add(candidate.recipe_id)
    return crafted


def _inventory_row(player_id: int, item_id: str):
    conn = get_connection()
    try:
        return conn.execute(
            'SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id=? ORDER BY id LIMIT 1',
            (player_id, item_id),
        ).fetchone()
    finally:
        conn.close()


async def _prove_crafted_gear_lifecycle(journey: ProductionJourney) -> dict:
    """Use earned combat materials to enhance and advance one crafted T5 instance."""
    await _move(journey, 'westwild_n3')
    shard_fights = 0
    while _quantity(journey.player_id, 'enhance_shard') < 11:
        shard_fights += 1
        assert shard_fights <= 120
        await _recover(journey)
        await journey.fight('forest_wolf')

    conn = get_connection()
    try:
        candidates = [dict(row) for row in conn.execute(
            "SELECT * FROM gear_instances WHERE telegram_id=? AND base_item_id='field_sword_1h' "
            "AND item_tier=5 AND rarity='uncommon' ORDER BY id",
            (journey.player_id,),
        )]
        combat_loot = conn.execute(
            'SELECT id FROM gear_instances WHERE telegram_id=? AND source_settlement_id IS NOT NULL LIMIT 1',
            (journey.player_id,),
        ).fetchone()
    finally:
        conn.close()
    crafted = next(
        row for row in candidates
        if json.loads(row['source_metadata_json']).get('recipe_id') == 'pe_sword_1h_12'
    )
    assert combat_loot
    assert len(json.loads(crafted['secondary_rolls_json'])) == 1
    comparison_text, _ = build_item_detail(
        journey.player_id, f"g{crafted['id']}", 'weapon', 'en',
    )
    assert comparison_text and 'Tier 5' in comparison_text

    await _move(journey, 'capital_city')
    if crafted['equipped_slot'] != 'weapon':
        token = issue_gear_intent(
            journey.player_id, 'equip', int(crafted['id']), target_slot='weapon',
        )
        assert token
        assert apply_gear_intent(journey.player_id, 'equip', token)['status'] == 'equipped'

    exchange_token = issue_crystal_exchange_intent(journey.player_id)
    assert exchange_token
    exchange = exchange_enhancement_crystal(journey.player_id, exchange_token)
    assert exchange['status'] == 'exchanged'

    enhance_token = issue_gear_intent(journey.player_id, 'enhance', int(crafted['id']))
    assert enhance_token
    enhanced = apply_gear_intent(
        journey.player_id, 'enhance', enhance_token, rng_roll=0.0,
    )
    assert enhanced['status'] == 'enhanced' and enhanced['outcome'] == 'success'

    advance_token = issue_gear_intent(journey.player_id, 'advance', int(crafted['id']))
    assert advance_token
    advanced = apply_gear_intent(journey.player_id, 'advance', advance_token)
    assert advanced['status'] == 'advanced' and advanced['before'] == 5 and advanced['after'] == 10

    conn = get_connection()
    try:
        after = dict(conn.execute(
            'SELECT * FROM gear_instances WHERE id=? AND telegram_id=?',
            (crafted['id'], journey.player_id),
        ).fetchone())
    finally:
        conn.close()
    for key in ('id', 'base_item_id', 'rarity', 'secondary_rolls_json',
                'source_settlement_id', 'source_metadata_json'):
        assert after[key] == crafted[key], (key, crafted[key], after[key])
    assert int(after['enhance_level']) == int(crafted['enhance_level']) + 1
    assert int(after['item_tier']) == 10
    return {
        'instance_id': int(after['id']),
        'rolls': json.loads(after['secondary_rolls_json']),
        'provenance': json.loads(after['source_metadata_json']),
        'shard_fights': shard_fights,
        'combat_loot_instance_id': int(combat_loot['id']),
    }


async def _create_recovery_deficit(
    journey: ProductionJourney, *, need_hp: bool, need_mana: bool,
) -> None:
    await _move(journey, 'westwild_n3')
    opening = (('skill', 'defensive_stance'), ('skill', 'sword_rush'))
    for _ in range(5):
        await _recover(journey, force=True)
        await journey.fight('forest_wolf', opening=opening)
        player = dict(get_player(journey.player_id))
        effective = get_player_effective_stats(journey.player_id, player)
        hp_deficit = int(player['hp']) < int(effective['max_hp'])
        mana_deficit = int(player['mana']) < int(effective['max_mana'])
        if (not need_hp or hp_deficit) and (not need_mana or mana_deficit):
            return
    raise AssertionError(('real combat did not create required recovery deficit', need_hp, need_mana))


async def _consume_new_recovery_outputs(journey: ProductionJourney) -> dict[str, dict]:
    output_ids = (
        'pe_mana_potion_medium', 'pe_health_potion_large', 'pe_mana_potion_large',
        'pe_shore_broth', 'pe_marsh_stew', 'pe_boar_feast', 'pe_oasis_meal',
        'pe_deep_marsh_meal',
    )
    assert all(_quantity(journey.player_id, item_id) > 0 for item_id in output_ids)
    results: dict[str, dict] = {}
    battle_items = {
        item_id for item_id in output_ids
        if int(json.loads(get_item(item_id)['stat_bonus_json']).get('mana', 0)) > 0
    }
    for item_id in sorted(battle_items):
        await _move(journey, 'westwild_n3')
        await _recover(journey, force=True)
        battle = await journey.fight(
            'forest_wolf',
            opening=(('skill', 'defensive_stance'), ('skill', 'sword_rush')),
            use_potions=True,
            potion_item_id=item_id,
        )
        use_result = next(
            (row for row in battle['potion_results'] if row['item_id'] == item_id),
            None,
        )
        assert use_result and use_result['mana'] > 0, (item_id, battle['potion_results'])
        bonuses = json.loads(get_item(item_id)['stat_bonus_json'])
        if int(bonuses.get('heal', 0)):
            assert use_result['heal'] > 0, (item_id, use_result)
        results[item_id] = {'path': 'battle', **use_result}

    for item_id in output_ids:
        if item_id in battle_items:
            continue
        bonuses = json.loads(get_item(item_id)['stat_bonus_json'])
        await _create_recovery_deficit(
            journey,
            need_hp=int(bonuses.get('heal', 0)) > 0,
            need_mana=False,
        )
        row = _inventory_row(journey.player_id, item_id)
        assert row, item_id
        payload = f"{row['id']}:{row['quantity']}"
        token = issue_actions(journey.player_id, 'use', [payload])[payload]
        result = use_inventory_consumable(journey.player_id, token)
        assert result['status'] == 'used' and result['item_id'] == item_id
        if int(bonuses.get('heal', 0)):
            assert int(result['heal']) > 0, (item_id, result)
        if int(bonuses.get('mana', 0)):
            assert int(result['mana']) > 0, (item_id, result)
        results[item_id] = {
            'path': 'inventory', 'heal': int(result['heal']), 'mana': int(result['mana']),
        }
    assert set(results) == set(output_ids)
    return results


def _prove_localized_production_navigation(player_id: int) -> dict[str, tuple[str, ...]]:
    conn = get_connection()
    try:
        receipt_rows = [dict(row) for row in conn.execute(
            "SELECT action_kind, result_json FROM economy_action_receipts "
            "WHERE player_id=? AND action_kind IN ('learn','craft','consume') "
            "ORDER BY created_at DESC, request_id DESC",
            (player_id,),
        )]
    finally:
        conn.close()
    receipts = {}
    for row in receipt_rows:
        receipts.setdefault(row['action_kind'], json.loads(row['result_json']))
    assert set(receipts) == {'learn', 'craft', 'consume'}

    rendered: dict[str, tuple[str, ...]] = {}
    for lang in ('ru', 'en', 'es'):
        player = dict(get_player(player_id))
        player['lang'] = lang
        stages = (
            build_overview(player, 0)[0],
            build_profession(player, 'herbalism')[0],
            build_resource_list(player, 'herbalism', 0)[0],
            build_material(player, 'herb_magic', 0)[0],
            build_profession(player, 'alchemy')[0],
            build_recipe(player, 'pe_alchemy_mana_12')[0],
            build_mutation_result(player, receipts['learn'])[0],
            build_mutation_result(player, receipts['craft'], 'pe_alchemy_mana_12')[0],
            build_receipts(player, 0)[0],
            build_mutation_result(player, receipts['consume'])[0],
        )
        combined = '\n'.join(stages)
        assert all(stage.strip() for stage in stages)
        assert '[professions.' not in combined
        assert not any(raw in combined for raw in (
            'ordinary_one', 'not_applicable', 'action_kind', 'profession_key',
            'recipe_id', 'source_metadata_json',
        ))
        if lang != 'ru':
            assert not any('А' <= char <= 'я' or char in 'Ёё' for char in combined)
        rendered[lang] = stages
    return rendered


async def _production_history() -> dict:
    from game.build_progression import migrate_character_builds_v1
    migrate_character_builds_v1()
    journey = ProductionJourney(PLAYER_ID, lang='en')
    await journey.register(primary='strength', name='PEV1 Traveler')
    await journey.callback('alpha_kit_practice_sword', handle_chapter_buttons)
    vendor_instance = await journey.buy_and_equip_field_weapon('sword_1h')
    starter_recipe_count = len(known_recipe_ids(PLAYER_ID))
    assert starter_recipe_count == 17
    gather_ids: list[str] = []
    encounter_ids: list[str] = []
    chapter_history = await _complete_aster_elmor_chapter(journey, gather_ids, encounter_ids)
    await _prove_battle_consumable(journey)

    for profession, ladder in {
        'herbalism': (('herb_common', 6), ('marsh_herb', 12), ('desert_plant', 18), ('toxic_herb', 20)),
        'woodcutting': (('wood_common', 6), ('wood_dark', 12), ('frostpine_wood', 18), ('ancient_bark', 20)),
        'mining': (('iron_ore', 6), ('salt_crystal', 12), ('gem_common', 18), ('sunscar_ore', 20)),
        'fishing': (('shore_fish', 6), ('marsh_fish', 12), ('oasis_fish', 18), ('deep_marsh_fish', 20)),
    }.items():
        for item_id, target in ladder:
            await _gather_to_level(journey, profession, item_id, target, gather_ids)
    await _gather_at(journey, 'herb_magic', 'ashen_n3c1', 1, gather_ids)

    requirements = Counter()
    for recipe in ACTIVE_RECIPES:
        requirements.update(dict(recipe.requirements))
    environmental = set(MANDATORY_RESOURCE_IDS) - {
        'boar_meat', 'wolf_pelt', 'wolf_fang', 'spider_silk', 'bear_hide', 'troll_sinew',
    }
    for item_id in sorted(environmental):
        target = max(requirements[item_id] * 2, 180 if item_id == 'herb_common' else 0)
        missing = max(0, target - _quantity(PLAYER_ID, item_id))
        if missing:
            await _gather(journey, item_id, missing, gather_ids)
    # Learning is paid from legitimate sales. Keep the recipe reserve intact.
    bark_reserve = requirements['ancient_bark'] * 2
    sale_quantity = 250
    missing_bark = max(0, bark_reserve + sale_quantity - _quantity(PLAYER_ID, 'ancient_bark'))
    if missing_bark:
        await _gather(journey, 'ancient_bark', missing_bark, gather_ids)
    await _sell_bark_for_learning(journey, sale_quantity)

    await _hunt_history(journey, encounter_ids)
    craft_actions: list[str] = []
    crafted = await _craft_all(journey, craft_actions, gather_ids)
    gear_proof = await _prove_crafted_gear_lifecycle(journey)
    consumable_proof = await _consume_new_recovery_outputs(journey)
    locale_proof = _prove_localized_production_navigation(PLAYER_ID)

    conn = get_connection()
    try:
        gathering = {row['profession_key']: int(row['level']) for row in conn.execute(
            'SELECT profession_key, level FROM player_gathering_professions WHERE telegram_id=?', (PLAYER_ID,))}
        crafting = {row['profession_key']: int(row['level']) for row in conn.execute(
            'SELECT profession_key, level FROM player_crafting_professions WHERE player_id=?', (PLAYER_ID,))}
        acquired: set[str] = set()
        for row in conn.execute(
            'SELECT result_json FROM economy_action_receipts WHERE player_id=?', (PLAYER_ID,)
        ):
            result = json.loads(row['result_json'])
            acquired.update(
                grant['item_id'] for grant in result.get('granted', [])
                if grant.get('item_id') in MANDATORY_RESOURCE_IDS
            )
        gather_locations = {
            json.loads(row['result_json']).get('location_id')
            for row in conn.execute(
                "SELECT result_json FROM economy_action_receipts "
                "WHERE player_id=? AND action_kind='gather'",
                (PLAYER_ID,),
            )
            if json.loads(row['result_json']).get('status') == 'gathered'
        }
        receipt_count = conn.execute(
            'SELECT COUNT(*) AS count FROM economy_action_receipts WHERE player_id=?', (PLAYER_ID,)
        ).fetchone()['count']
    finally:
        conn.close()
    recipe_ids_by_profession = {
        profession: {recipe.recipe_id for recipe in ACTIVE_RECIPES if recipe.profession_key == profession}
        for profession in {recipe.profession_key for recipe in ACTIVE_RECIPES}
    }
    acquired_regions = {
        region
        for prefix, region in (
            ('westwild_', 'Westwild'), ('frostspine_', 'Frostspine'),
            ('ashen_', 'Ashen Ruins'), ('mireveil_', 'Mireveil'), ('sunscar_', 'Sunscar'),
        )
        if any(str(location).startswith(prefix) for location in gather_locations)
    }
    gathering_expected = {
        'fishing': 20, 'herbalism': 20, 'hunting': 20, 'mining': 20, 'woodcutting': 20,
    }
    crafting_expected = {
        'alchemy': 20, 'arcane_engineer': 20, 'blacksmith': 20, 'cooking': 20,
        'heavy_armor': 20, 'light_armor': 20, 'medium_armor': 20,
    }
    production_checks = {
        'new_character_and_chapter': (
            starter_recipe_count == 17
            and int(vendor_instance['id']) > 0
            and {'chapter_first_watch', 'chapter_caravan', 'chapter_outfitter', 'chapter_homecoming'}
                <= chapter_history
        ),
        'mining_smith_heavy': (
            {'iron_ore', 'coal', 'stone_chunk', 'salt_crystal', 'gem_common', 'sunscar_ore'} <= acquired
            and recipe_ids_by_profession['blacksmith'] <= crafted
            and recipe_ids_by_profession['heavy_armor'] <= crafted
        ),
        'wood_fiber_arcane': (
            {'wood_common', 'wood_dark', 'frostpine_wood', 'ancient_bark', 'reed_bundle', 'spider_silk'} <= acquired
            and recipe_ids_by_profession['arcane_engineer'] <= crafted
            and recipe_ids_by_profession['light_armor'] <= crafted
        ),
        'herbalism_alchemy': (
            {'herb_common', 'herb_magic', 'marsh_herb', 'desert_plant', 'toxic_herb'} <= acquired
            and recipe_ids_by_profession['alchemy'] <= crafted
            and {'pe_mana_potion_medium', 'pe_health_potion_large', 'pe_mana_potion_large'}
                <= set(consumable_proof)
        ),
        'fishing_cooking': (
            {'shore_fish', 'marsh_fish', 'oasis_fish', 'deep_marsh_fish'} <= acquired
            and recipe_ids_by_profession['cooking'] <= crafted
            and {'pe_shore_broth', 'pe_marsh_stew', 'pe_boar_feast', 'pe_oasis_meal',
                 'pe_deep_marsh_meal'} <= set(consumable_proof)
            and consumable_proof['pe_oasis_meal']['heal'] > 0
            and consumable_proof['pe_oasis_meal']['mana'] > 0
        ),
        'hunting_claims_and_consumers': (
            {'boar_meat', 'wolf_pelt', 'wolf_fang', 'spider_silk', 'bear_hide', 'troll_sinew'} <= acquired
            and bool(encounter_ids)
        ),
        'gear_integration': (
            gear_proof['provenance'].get('recipe_id') == 'pe_sword_1h_12'
            and len(gear_proof['rolls']) == 1
            and gear_proof['combat_loot_instance_id'] > 0
        ),
        'learning_authority': set(known_recipe_ids(PLAYER_ID)) == {recipe.recipe_id for recipe in ACTIVE_RECIPES},
        'conservation_and_receipts': int(receipt_count) >= len(craft_actions) + len(gather_ids),
        'localized_complete_navigation': set(locale_proof) == {'ru', 'en', 'es'},
        'regional_source_coverage': acquired_regions == {
            'Westwild', 'Frostspine', 'Ashen Ruins', 'Mireveil', 'Sunscar',
        },
    }
    return {
        'production_checks': production_checks,
        'gather_request_count': len(gather_ids),
        'encounter_count': len(encounter_ids),
        'craft_action_count': len(craft_actions),
        'crafted': crafted, 'gathering': gathering, 'crafting': crafting,
        'acquired': acquired, 'receipt_count': int(receipt_count),
        'acquired_regions': acquired_regions,
        'gear_proof': gear_proof,
        'consumable_proof': consumable_proof,
        'locale_proof': locale_proof,
    }


def test_shared_production_history_covers_pev1_acceptance_matrix():
    evidence = asyncio.run(_production_history())
    assert all(evidence['production_checks'].values()), evidence['production_checks']
    assert set(evidence['crafted']) == {recipe.recipe_id for recipe in ACTIVE_RECIPES}
    assert len(evidence['crafted']) == 63
    assert set(MANDATORY_RESOURCE_IDS) <= evidence['acquired']
    assert len(MANDATORY_RESOURCE_IDS) == 28
    assert evidence['gathering'] == {
        'fishing': 20, 'herbalism': 20, 'hunting': 20, 'mining': 20, 'woodcutting': 20,
    }
    assert evidence['crafting'] == {
        'alchemy': 20, 'arcane_engineer': 20, 'blacksmith': 20, 'cooking': 20,
        'heavy_armor': 20, 'light_armor': 20, 'medium_armor': 20,
    }
    assert evidence['receipt_count'] >= evidence['craft_action_count'] + evidence['gather_request_count']
    assert evidence['encounter_count'] > 0
    assert evidence['acquired_regions'] == {
        'Westwild', 'Frostspine', 'Ashen Ruins', 'Mireveil', 'Sunscar',
    }
    assert set(evidence['consumable_proof']) == {
        'pe_mana_potion_medium', 'pe_health_potion_large', 'pe_mana_potion_large',
        'pe_shore_broth', 'pe_marsh_stew', 'pe_boar_feast', 'pe_oasis_meal',
        'pe_deep_marsh_meal',
    }


def test_real_battle_consumable_path_commits_a_receipt():
    async def run() -> None:
        from game.build_progression import migrate_character_builds_v1
        migrate_character_builds_v1()
        journey = ProductionJourney(PLAYER_ID + 1, lang='en')
        await journey.register(primary='strength', name='PEV1 Potion Proof')
        await journey.callback('alpha_kit_practice_sword', handle_chapter_buttons)
        await journey.buy_and_equip_field_weapon('sword_1h')
        await _prove_battle_consumable(journey)

    asyncio.run(run())
