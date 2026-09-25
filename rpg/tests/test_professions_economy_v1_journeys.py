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
from game.hunting import harvest_victory, list_harvestable_victories
from game.locations import WORLD_LOCATIONS
from game.profession_recipes import ACTIVE_RECIPES, recipe_intent_payload
from game.profession_resources import ENVIRONMENTAL_SOURCES, MANDATORY_RESOURCE_IDS, RESOURCES
from game.recipe_knowledge import known_recipe_ids, learn_recipe
from handlers.chapter import handle_chapter_buttons
from handlers.inventory import build_item_detail, handle_inventory_buttons, try_sell_inventory_item
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


async def _gather_to_level(
    journey: ProductionJourney, profession: str, item_id: str, target: int,
    sequence: list[str],
) -> None:
    while _profession_level(
        journey.player_id, 'player_gathering_professions', 'telegram_id', profession,
    ) < target:
        await _gather(journey, item_id, 1, sequence)


async def _recover(journey: ProductionJourney) -> None:
    player = dict(get_player(journey.player_id))
    if int(player['hp']) * 10 > int(player['max_hp']) * 7:
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
        if enhance:
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


async def _production_history() -> dict:
    from game.build_progression import migrate_character_builds_v1
    migrate_character_builds_v1()
    journey = ProductionJourney(PLAYER_ID, lang='en')
    await journey.register(primary='strength', name='PEV1 Traveler')
    await journey.callback('alpha_kit_practice_sword', handle_chapter_buttons)
    await journey.buy_and_equip_field_weapon('sword_1h')
    assert len(known_recipe_ids(PLAYER_ID)) == 17
    await _prove_battle_consumable(journey)

    gather_ids: list[str] = []
    for profession, ladder in {
        'herbalism': (('herb_common', 6), ('marsh_herb', 12), ('desert_plant', 18), ('toxic_herb', 20)),
        'woodcutting': (('wood_common', 6), ('wood_dark', 12), ('frostpine_wood', 18), ('ancient_bark', 20)),
        'mining': (('iron_ore', 6), ('salt_crystal', 12), ('gem_common', 18), ('sunscar_ore', 20)),
        'fishing': (('shore_fish', 6), ('marsh_fish', 12), ('oasis_fish', 18), ('deep_marsh_fish', 20)),
    }.items():
        for item_id, target in ladder:
            await _gather_to_level(journey, profession, item_id, target, gather_ids)

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

    encounter_ids: list[str] = []
    await _hunt_history(journey, encounter_ids)
    craft_actions: list[str] = []
    crafted = await _craft_all(journey, craft_actions, gather_ids)

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
        receipt_count = conn.execute(
            'SELECT COUNT(*) AS count FROM economy_action_receipts WHERE player_id=?', (PLAYER_ID,)
        ).fetchone()['count']
    finally:
        conn.close()
    return {
        'journey_ids': list(range(1, 12)), 'gather_requests': gather_ids,
        'encounter_ids': encounter_ids, 'craft_actions': craft_actions,
        'crafted': crafted, 'gathering': gathering, 'crafting': crafting,
        'acquired': acquired, 'receipt_count': int(receipt_count),
    }


def test_shared_production_history_covers_pev1_acceptance_matrix():
    evidence = asyncio.run(_production_history())
    assert evidence['journey_ids'] == list(range(1, 12))
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
    assert evidence['receipt_count'] >= len(evidence['craft_actions'])
    assert evidence['encounter_ids']


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
