"""Shared PXE1 profession history retaining the eleven PEV1 acceptance journeys.

The history uses production handlers/domain actions.  Its only accelerators are
deterministic rolls, mocked Telegram transport, and the existing controlled
respawn clock in ``ProductionJourney``.  No material, gold, recipe knowledge,
character level, or profession level is inserted or granted by the test.
"""

from __future__ import annotations

import asyncio
from collections import Counter, deque
import json
import random
import hashlib
from unittest.mock import patch

import pytest
import database

from database import get_connection, get_player
from game.action_receipts import issue_actions
from game.crafting_runtime import craft_recipe
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
    location_id, _, _ = _environment_source(item_id)
    await _gather_at(journey,item_id,location_id,count,sequence)


async def _gather_at(
    journey: ProductionJourney, item_id: str, location_id: str, count: int,
    sequence: list[str],
) -> None:
    from handlers.activities import handle_activity_buttons
    from game.gathering_runtime import _source_snapshot,gather_tick_roll,start_gathering_session
    from game.world_activity_tick import run_world_activity_tick
    from game.profession_tools import get_tool
    profession=RESOURCES[item_id].profession_key
    journey.profession_gather_ids=sequence
    await _move(journey, location_id)
    before = _quantity(journey.player_id, item_id)
    while _quantity(journey.player_id,item_id)<before+count:
        await _maintain_tool(journey,profession)
        conn=get_connection()
        tool=get_tool(conn,journey.player_id,profession);conn.close()
        attempts=min(4,before+count-_quantity(journey.player_id,item_id),tool['durability'])
        snapshot=_source_snapshot(location_id,profession)
        probability=next(entry['chance_bp']/10000 for entry in snapshot['entries'] if entry['item_id']==item_id)
        while attempts>1 and 1000000*probability**attempts<10:
            attempts-=1
        cache=getattr(journey,'gather_seed_cache',{})
        key=(location_id,item_id,attempts)
        if key not in cache:
            cache[key]=next(f'{n:032x}' for n in range(1000000)
                if all((entry:=gather_tick_roll(f'{n:032x}',tick,snapshot)) and entry['item_id']==item_id
                    for tick in range(1,attempts+1)))
        journey.gather_seed_cache=cache
        await journey.callback('px:gatherpreview:'+profession,handle_activity_buttons)
        start=next(b.callback_data for row in journey.messages[-1][1].inline_keyboard for b in row
                   if b.callback_data.startswith('px:gatherstart:'))
        def seeded_start(*args,**kwargs): return start_gathering_session(*args,**kwargs,seed=cache[key])
        with patch('game.gathering_runtime.start_gathering_session',side_effect=seeded_start):
            await journey.callback(start,handle_activity_buttons)
        conn=get_connection()
        session=dict(conn.execute("SELECT * FROM player_gathering_sessions WHERE player_id=? AND status='running'",
                                  (journey.player_id,)).fetchone());conn.close()
        for tick in range(1,attempts+1):
            run_world_activity_tick(now_ms=session['started_ms']+tick*8000)
            request_id=f"gather:{session['session_id']}:{tick}"
            conn=get_connection()
            row=conn.execute('SELECT result_json FROM economy_action_receipts WHERE player_id=? AND request_id=?',
                             (journey.player_id,request_id)).fetchone();conn.close()
            if not row:
                # A due hostile visit interrupts before the next gather tick.
                # Keep the real committed yields, then choose the legal prelock
                # Leave action; stopping never manufactures the missing yield.
                conn=get_connection()
                stopped=dict(conn.execute('SELECT * FROM player_gathering_sessions WHERE session_id=?',
                                          (session['session_id'],)).fetchone())
                conn.close()
                assert stopped['status']=='interrupted' and stopped['terminal_reason']=='hostile_encounter',stopped
                assert stopped['last_tick']==tick-1 and stopped['yield_total']==tick-1
                from game.pve_live import get_active_pve_encounter_id_for_player
                from handlers.location import handle_location_buttons
                active=get_active_pve_encounter_id_for_player(player_id=journey.player_id,ensure_schema=False)
                assert active
                before_leave=dict(get_player(journey.player_id))
                await journey.callback('pve_enter_'+active,handle_location_buttons)
                leave='pve_leave_'+active
                assert any(b.callback_data==leave for row in journey.messages[-1][1].inline_keyboard for b in row)
                await journey.callback(leave,handle_location_buttons)
                after_leave=dict(get_player(journey.player_id))
                assert (after_leave['gold'],after_leave['exp'])==(before_leave['gold'],before_leave['exp'])
                assert get_active_pve_encounter_id_for_player(player_id=journey.player_id,ensure_schema=False) is None
                break
            result=json.loads(row['result_json'])
            assert result['granted']==[{'item_id':item_id,'quantity':1,'instance_ids':[],'gear_specs':[]}],result
            assert result['tool']['durability']==tool['durability']-tick
            sequence.append(request_id)
        with patch('handlers.activities.time.time',return_value=(session['started_ms']+attempts*8000)/1000):
            await journey.callback('px:stop:gather:'+session['session_id'],handle_activity_buttons)
    assert _quantity(journey.player_id, item_id) == before + count


async def _sell_owned(journey,entry,quantity=1):
    from handlers.shop_views import handle_shop_buttons
    await journey.callback(f'px:shop:saleview:{entry}:{quantity}',handle_shop_buttons)
    for _ in range(2):
        callback=next(b.callback_data for row in journey.messages[-1][1].inline_keyboard for b in row
                      if b.callback_data.startswith('px:shop:commit:'))
        await journey.callback(callback,handle_shop_buttons)
        if not any(b.callback_data.startswith('px:shop:commit:') for row in journey.messages[-1][1].inline_keyboard for b in row):
            return
    raise AssertionError('Sale did not commit after explicit confirmation')


async def _ensure_gold(journey,required,*,protected_materials=()):
    origin=get_player(journey.player_id)['location_id']
    await _move(journey,'capital_city')
    for _ in range(200):
        if get_player(journey.player_id)['gold']>=required: break
        conn=get_connection()
        gear=conn.execute('SELECT id FROM gear_instances WHERE telegram_id=? AND equipped_slot IS NULL ORDER BY id',
                          (journey.player_id,)).fetchone()
        exclusions=','.join('?' for _ in protected_materials)
        protected_clause=f' AND inv.item_id NOT IN ({exclusions})' if exclusions else ''
        material=conn.execute("SELECT inv.id,inv.quantity FROM inventory inv JOIN items i ON inv.item_id=i.item_id WHERE inv.telegram_id=? AND i.item_type='material' AND i.sell_price>0"+protected_clause+" ORDER BY i.sell_price DESC,inv.id",
                              (journey.player_id,*protected_materials)).fetchone();conn.close()
        if gear: await _sell_owned(journey,'g'+str(gear['id']))
        elif material: await _sell_owned(journey,'i'+str(material['id']),min(99,material['quantity']))
        else:
            await _move(journey,'westwild_n1')
            await journey.fight('westwild_rabbit')
            await _move(journey,'capital_city')
    assert get_player(journey.player_id)['gold']>=required
    await _move(journey,origin)


async def _maintain_tool(journey,profession):
    from game.profession_tools import get_tool,repair_quote,commit_tool_maintenance
    conn=get_connection();tool=get_tool(conn,journey.player_id,profession);conn.close()
    assert tool,profession
    if tool['durability']: return
    origin=get_player(journey.player_id)['location_id']
    await _move(journey,'capital_city')
    if tool['tier']==1:
        quote={'schema_version':1,'profession_key':profession,'tool_revision':tool['revision'],'gold':12}
        kind='tool_replace_pxe1'
    else:
        conn=get_connection();quote=repair_quote(conn,journey.player_id,profession);conn.close()
        kind='tool_repair_pxe1'
    await _ensure_gold(journey,quote['gold'])
    # Funding sales can change owned materials, so render a new exact repair quote.
    if tool['tier']>1:
        conn=get_connection();quote=repair_quote(conn,journey.player_id,profession);conn.close()
        await _ensure_gold(journey,quote['gold'])
        conn=get_connection();quote=repair_quote(conn,journey.player_id,profession);conn.close()
    payload=json.dumps(quote,sort_keys=True,separators=(',',':'))
    token=issue_actions(journey.player_id,kind,[payload])[payload]
    result=commit_tool_maintenance(journey.player_id,action_token=token,replace=tool['tier']==1)
    assert result['status'] in {'repaired','replaced'}
    assert not result['granted'] and not result['progression']
    assert commit_tool_maintenance(journey.player_id,action_token=token,replace=tool['tier']==1)['recovered']
    await _move(journey,origin)


async def _gather_to_level(
    journey: ProductionJourney, profession: str, item_id: str, target: int,
    sequence: list[str],
) -> None:
    while _profession_level(
        journey.player_id, 'player_gathering_professions', 'telegram_id', profession,
    ) < target:
        before=_profession_level(journey.player_id,'player_gathering_professions','telegram_id',profession)
        assert before<=RESOURCES[item_id].required_level+5,(profession,item_id,target,'zero-XP source')
        from game.gathering_progression import gathering_profession_xp_for_success
        from game.profession_progression import xp_to_level
        conn=get_connection()
        state=conn.execute('SELECT level,exp FROM player_gathering_professions WHERE telegram_id=? AND profession_key=?',
                           (journey.player_id,profession)).fetchone()
        conn.close()
        xp=gathering_profession_xp_for_success(current_profession_level=state['level'],
                                              required_profession_level=RESOURCES[item_id].required_level)
        needed=xp_to_level(state['level'],state['exp'],target)
        await _gather(journey,item_id,min(4,(needed+xp-1)//xp),sequence)


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
        # Inn funding uses the same explicit quantity/valuable-sale confirmation
        # as other earned sales, rather than the obsolete immediate All intent.
        await _sell_owned(journey, f"i{row['id']}", min(99, int(row['quantity'])))
    await journey.rest_at_current_inn()
    await _move(journey, origin)


async def _fight_and_harvest(
    journey: ProductionJourney, *, location_id: str, mob_id: str, item_id: str,
    encounter_ids: list[str],
) -> None:
    await _move(journey, location_id)
    await _maintain_tool(journey,'hunting')
    await _recover(journey)
    opening = (
        (('skill', 'defensive_stance'), ('skill', 'shield_bash'), ('skill', 'sword_rush'))
        if mob_id == 'troll' else ()
    )
    fight = await journey.fight(mob_id, opening=opening, use_potions=True)
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
    # A level-up may refill HP after victory. Create the deficit inside the
    # battle being tested, then let the existing consumable owner use the potion.
    for _ in range(8):
        proof = await journey.fight('forest_boar', opening=(('guard', None),) * 3, use_potions=True)
        if proof['battle_potions_used']:
            assert any(result['heal'] > 0 for result in proof['potion_results'])
            return
    raise AssertionError('Eight real encounters did not produce a consumable deficit')


async def _learn_and_craft(journey: ProductionJourney, recipe_id: str, *, commission=False) -> str:
    from game.profession_recipes import get_recipe
    from game.profession_tools import get_tool
    recipe=get_recipe(recipe_id)
    assert recipe
    sequence=getattr(journey,'profession_gather_ids',[])
    await _move(journey,'capital_city')
    if recipe_id not in set(known_recipe_ids(journey.player_id)):
        await _ensure_gold(journey,recipe.learning_gold)
    inputs=dict(recipe.requirements)
    if commission:
        # Own-tier materials are supplied only after a real visit. The lower
        # inputs and 3x wood requirement remain earned and consumed normally.
        for item in list(inputs):
            if RESOURCES[item].resource_tier==recipe.output_spec.tool_tier:
                await _move(journey,_environment_source(item)[0]);inputs.pop(item)
        inputs['wood_common']*=3
        await _ensure_gold(journey,20*recipe.output_spec.tool_tier**2+recipe.learning_gold)
    environmental={item for rows in ENVIRONMENTAL_SOURCES.values() for item,_ in rows}
    harvest_sources={'boar_meat':('forest_boar','westwild_n2'),'wolf_pelt':('forest_wolf','westwild_n3'),
                     'wolf_fang':('forest_wolf','westwild_n3'),'spider_silk':('forest_spider','westwild_n5'),
                     'bear_hide':('bear','westwild_n7'),'troll_sinew':('troll','frostspine_n7')}
    for _ in range(20):
        if all(_quantity(journey.player_id,item)>=quantity for item,quantity in inputs.items()): break
        for item,quantity in inputs.items():
            missing=max(0,quantity-_quantity(journey.player_id,item))
            if missing and item in environmental: await _gather(journey,item,missing,sequence)
            elif missing:
                mob,place=harvest_sources[item]
                for _ in range(missing):
                    await _fight_and_harvest(journey,location_id=place,mob_id=mob,item_id=item,encounter_ids=[])
    assert all(_quantity(journey.player_id,item)>=quantity for item,quantity in inputs.items()),(recipe_id,inputs)
    await _move(journey,'capital_city')
    learning_fee=recipe.learning_gold if recipe_id not in set(known_recipe_ids(journey.player_id)) else 0
    final_fee=learning_fee+(20*recipe.output_spec.tool_tier**2 if commission else 0)
    if final_fee:
        # Gathering maintenance can spend the earlier fee reserve. Fund again
        # after the ingredients are complete, without selling those ingredients.
        await _ensure_gold(journey,final_fee,protected_materials=tuple(inputs))
    if recipe_id not in set(known_recipe_ids(journey.player_id)):
        payload = recipe_intent_payload(recipe_id)
        token = issue_actions(journey.player_id, 'learn', [payload])[payload]
        assert learn_recipe(journey.player_id, recipe_id, action_token=token)['status'] == 'learned'
    if recipe.output_spec.kind=='tool':
        conn=get_connection();tool=get_tool(conn,journey.player_id,recipe.output_spec.profession_key);conn.close()
        payload=recipe_intent_payload(recipe_id,tool_revision=tool['revision'],commission=commission,replacement_confirmed=True)
    else: payload = recipe_intent_payload(recipe_id)
    token = issue_actions(journey.player_id, 'craft', [payload])[payload]
    result=craft_recipe(journey.player_id, recipe_id, action_token=token)
    assert result.status == 'crafted',(recipe_id,result)
    replay=craft_recipe(journey.player_id,recipe_id,action_token=token)
    assert replay.status=='crafted' and replay.recovered
    return token


async def _train_crafting(journey,profession,target,tier):
    recipe={
        'blacksmith':{1:'pe_sword_1h_01',2:'pe_shield_06',3:'pe_sword_2h_12'},
        'arcane_engineer':{1:'pe_magic_staff_01',2:'pe_focus_06',3:'pe_holy_rod_12'},
    }[profession][tier]
    for _ in range(2000):
        if _crafting_level(journey.player_id,profession)>=target: return
        await _learn_and_craft(journey,recipe)
    raise AssertionError((profession,target,'craft training failed to progress'))


async def _earned_tool_ladders(journey,gather_ids,encounter_ids):
    ladders={
        'herbalism':(('herb_common',6),('marsh_herb',12),('desert_plant',18),('toxic_herb',20)),
        'woodcutting':(('wood_common',6),('wood_dark',12),('frostpine_wood',18),('ancient_bark',20)),
        'mining':(('iron_ore',6),('salt_crystal',12),('gem_common',18),('sunscar_ore',20)),
        'fishing':(('shore_fish',6),('marsh_fish',12),('oasis_fish',18),('deep_marsh_fish',20)),
    }
    for profession in (*ladders,'hunting'):
        await _learn_and_craft(journey,f'pxe_tool_{profession}_1')
    for tier,target in ((1,6),(2,12),(3,18),(4,20)):
        print(f'PXE1 earned tools: tier {tier}, target {target}',flush=True)
        # Hunt before distant sources: these victories earn character power and
        # the ordinary gear/materials used by subsequent crafts and repairs.
        item,mob,place={1:('boar_meat','forest_boar','westwild_n2'),
                       2:('spider_silk','forest_spider','westwild_n5'),
                       3:('bear_hide','bear','westwild_n7'),
                       4:('troll_sinew','troll','frostspine_n7')}[tier]
        if tier==4: await _equip_regional_combat_gear(journey)
        for _ in range(2000):
            if _profession_level(journey.player_id,'player_gathering_professions','telegram_id','hunting')>=target: break
            await _fight_and_harvest(journey,location_id=place,mob_id=mob,item_id=item,encounter_ids=encounter_ids)
        assert _profession_level(journey.player_id,'player_gathering_professions','telegram_id','hunting')>=target
        for profession,ladder in ladders.items():
            item,target=ladder[tier-1]
            await _gather_to_level(journey,profession,item,target,gather_ids)
        if tier<4:
            for crafting in ('blacksmith','arcane_engineer'):
                await _train_crafting(journey,crafting,{1:6,2:12,3:18}[tier],tier)
            for profession in ('woodcutting','mining'):
                await _learn_and_craft(journey,f'pxe_tool_{profession}_{tier+1}',commission=True)
            for profession in ('herbalism','fishing','hunting'):
                await _learn_and_craft(journey,f'pxe_tool_{profession}_{tier+1}')


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
    await _sell_owned(journey, f"i{sale_row['id']}", min(99, int(sale_row['quantity'])))
    await _claim_chapter_contract(journey, 'chapter_homecoming', 'capital_city')
    history = get_contract_history(journey.player_id)
    expected = {
        'chapter_first_watch', 'chapter_caravan', 'chapter_outfitter', 'chapter_homecoming',
    }
    assert expected <= history
    return history


async def _equip_best_earned_piece(journey: ProductionJourney, item_id: str):
    conn = get_connection()
    try:
        row = conn.execute('''SELECT id, equipped_slot FROM gear_instances
            WHERE telegram_id=? AND base_item_id=?
            ORDER BY item_tier DESC, (equipped_slot IS NOT NULL) DESC, id DESC LIMIT 1''',
            (journey.player_id, item_id)).fetchone()
        piece = dict(row) if row else None
    finally:
        conn.close()
    if not piece:
        return None
    if piece['equipped_slot'] is None:
        _, markup = build_item_detail(journey.player_id, f"g{piece['id']}", 'armor', 'en')
        callback = next(button.callback_data for row in markup.inline_keyboard for button in row
                        if button.callback_data and button.callback_data.startswith('inv_gequip_'))
        await journey.callback(callback, handle_inventory_buttons)
    conn = get_connection()
    try:
        assert conn.execute('SELECT equipped_slot FROM gear_instances WHERE id=? AND telegram_id=?',
                            (piece['id'], journey.player_id)).fetchone()['equipped_slot'] is not None
    finally:
        conn.close()
    return piece['id']


async def _equip_regional_combat_gear(journey: ProductionJourney) -> None:
    from game.profession_recipes import get_recipe
    await _move(journey, 'capital_city')
    for profession, first, second, regional in (
        ('blacksmith', 'pe_sword_1h_01', 'pe_shield_06', 'pe_sword_1h_12'),
        ('heavy_armor', 'pe_heavy_chest_01', 'pe_heavy_helmet_06', 'pe_heavy_legs_12'),
    ):
        for recipe_id, target in ((first, 6), (second, 12)):
            item_id = get_recipe(recipe_id).output_spec.item_id
            while _crafting_level(journey.player_id, profession) < target:
                await _learn_and_craft(journey, recipe_id)
                # Equip as soon as earned: later funding sales protect equipped
                # pieces, but may consume an unequipped future combat loadout.
                assert await _equip_best_earned_piece(journey, item_id)
            if not await _equip_best_earned_piece(journey, item_id):
                await _learn_and_craft(journey, recipe_id)
                assert await _equip_best_earned_piece(journey, item_id)
        await _learn_and_craft(journey, regional)
        assert await _equip_best_earned_piece(journey, get_recipe(regional).output_spec.item_id)
    while _crafting_level(journey.player_id, 'alchemy') < 6:
        await _learn_and_craft(journey, 'field_tonic')
    while _crafting_level(journey.player_id, 'alchemy') < 12:
        await _learn_and_craft(journey, 'pe_alchemy_health_06')
    # Hunting 18 -> 20 legitimately requires many troll victories. Keep enough
    # earned healing stock for the deterministic worst segment of that journey.
    for _ in range(60):
        await _learn_and_craft(journey, 'pe_alchemy_health_06')
    for _ in range(5):
        await _learn_and_craft(journey, 'field_mana')
    for item_id in ('field_sword_1h', 'field_shield', 'field_heavy_chest', 'field_heavy_helmet', 'field_heavy_legs'):
        instance_id = await _equip_best_earned_piece(journey, item_id)
        assert instance_id
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
    remaining = quantity
    while remaining:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id='ancient_bark'",
                (journey.player_id,),
            ).fetchone()
        finally:
            conn.close()
        assert row and row['quantity'] >= remaining
        amount = min(99, remaining)
        await _sell_owned(journey, f"i{row['id']}", amount)
        remaining -= amount


def _crafting_level(player_id: int, key: str) -> int:
    return _profession_level(player_id, 'player_crafting_professions', 'player_id', key)


async def _craft_all(
    journey: ProductionJourney, action_ids: list[str], gather_ids: list[str],
) -> set[str]:
    await _move(journey, 'capital_city')
    conn=get_connection()
    crafted={json.loads(row['result_json'])['recipe_id'] for row in conn.execute(
        "SELECT result_json FROM economy_action_receipts WHERE player_id=? AND action_kind IN ('craft','tool_craft_pxe1','tool_commission_pxe1')",
        (journey.player_id,)) if json.loads(row['result_json']).get('status')=='crafted'}
    conn.close()
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
            assert safety < 2000, profession
            level = _crafting_level(journey.player_id, profession)
            available=[recipe for recipe in recipes if recipe.required_level<=level]
            candidate=next((recipe for recipe in available if recipe.recipe_id not in crafted),
                           next(r for r in reversed(available) if r.output_spec.kind!='tool'))
            token=await _learn_and_craft(journey,candidate.recipe_id)
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
    random.seed(901)
    from game.build_progression import migrate_character_builds_v1
    migrate_character_builds_v1()
    journey = ProductionJourney(PLAYER_ID, lang='en')
    await journey.register(primary='strength', name='PEV1 Traveler')
    await journey.callback('alpha_kit_practice_sword', handle_chapter_buttons)
    vendor_instance = await journey.buy_and_equip_field_weapon('sword_1h')
    starter_recipe_count = len(known_recipe_ids(PLAYER_ID))
    assert starter_recipe_count == 22
    gather_ids: list[str] = []
    encounter_ids: list[str] = []
    chapter_history = await _complete_aster_elmor_chapter(journey, gather_ids, encounter_ids)
    await _prove_battle_consumable(journey)

    await _earned_tool_ladders(journey,gather_ids,encounter_ids)
    await _gather_at(journey, 'herb_magic', 'ashen_n3c1', 1, gather_ids)

    requirements = Counter()
    for recipe in ACTIVE_RECIPES:
        requirements.update(dict(recipe.requirements))
    environmental = set(MANDATORY_RESOURCE_IDS) - {
        'boar_meat', 'wolf_pelt', 'wolf_fang', 'spider_silk', 'bear_hide', 'troll_sinew',
    }
    for item_id in sorted(environmental):
        combat_reserve = {'herb_common': 240, 'marsh_herb': 140}.get(item_id, 0)
        target = max(requirements[item_id] * 2, combat_reserve)
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
                "WHERE player_id=? AND action_kind='gather_tick_pxe1'",
                (PLAYER_ID,),
            )
            if json.loads(row['result_json']).get('granted')
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
            starter_recipe_count == 22
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


def _earned_source_hash():
    from pathlib import Path
    digest=hashlib.sha256()
    paths=[Path('database.py'),Path('bot.py'),Path(__file__),
           Path('tests/test_character_builds_v1_journeys.py'),
           Path('tests/test_character_builds_v1_group_journeys.py')]
    for folder in ('game','handlers','locales'):
        paths.extend(Path(folder).rglob('*.py'))
    for path in sorted(paths):
        digest.update(str(path).encode());digest.update(path.read_bytes())
    return digest.hexdigest()


def load_recorded_pxe1_checkpoint(directory):
    # Optional focused-repair accelerator: only this exact current earned
    # source history, copied whole and verified by both source and DB hashes.
    from pathlib import Path
    directory=Path(directory)
    data=json.loads((directory/'provenance.json').read_text(encoding='utf-8'))
    assert data['source_sha256']==_earned_source_hash(),'earned source changed'
    checkpoint=directory/'earned.sqlite3'
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==data['sha256']
    evidence=data['evidence']
    assert all(evidence['production_checks'].values())
    assert len(evidence['crafted'])==83
    assert evidence['gathering']==dict.fromkeys(('herbalism','woodcutting','mining','fishing','hunting'),20)
    assert evidence['crafting']==dict.fromkeys(('blacksmith','arcane_engineer','alchemy','cooking','heavy_armor','medium_armor','light_armor'),20)
    for key in ('crafted','acquired','acquired_regions'):evidence[key]=set(evidence[key])
    return {'path':checkpoint,'sha256':data['sha256'],'evidence':evidence,'player_id':data['player_id']}


def build_pxe1_profession_checkpoint(tmp_path_factory):
    """One current earned history, cloned whole by the independent RAV branches."""
    from game.seed import seed_items
    from game.pve_live import _ensure_pve_encounter_table,_ensure_world_spawn_table
    source_sha256=_earned_source_hash()
    checkpoint=tmp_path_factory.mktemp('pxe1-earned-professions')/'earned.sqlite3'
    original=database.DB_PATH
    database.DB_PATH=str(checkpoint)
    try:
        database.init_db()
        seed_items()
        _ensure_pve_encounter_table()
        _ensure_world_spawn_table()
        from game.regional_schema import ensure_regional_schema
        conn = get_connection()
        ensure_regional_schema(conn)
        conn.close()
        try:
            evidence=asyncio.run(_production_history())
        except Exception:
            import traceback
            (checkpoint.parent/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
            raise
        assert all(evidence['production_checks'].values()),evidence['production_checks']
        conn=get_connection();conn.execute('PRAGMA wal_checkpoint(TRUNCATE)');conn.close()
    finally:
        database.DB_PATH=original
    result={'path':checkpoint,'sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            'evidence':evidence,'player_id':PLAYER_ID}
    import tempfile,shutil
    from pathlib import Path
    saved=Path(tempfile.mkdtemp(prefix='pxe1-earned-history-'))
    shutil.copy2(checkpoint,saved/'earned.sqlite3')
    assert _earned_source_hash()==source_sha256,'earned sources changed during history build'
    metadata={'sha256':result['sha256'],'source_sha256':source_sha256,
              'evidence':evidence,'player_id':PLAYER_ID}
    (saved/'provenance.json').write_text(json.dumps(metadata,default=lambda value:sorted(value) if isinstance(value,set) else value,indent=2),encoding='utf-8')
    print(f'PXE1 earned checkpoint: {saved}',flush=True)
    return result


def test_shared_production_history_covers_pev1_acceptance_matrix(pxe1_profession_checkpoint):
    evidence=pxe1_profession_checkpoint['evidence']
    assert all(evidence['production_checks'].values()), evidence['production_checks']
    assert set(evidence['crafted']) == {recipe.recipe_id for recipe in ACTIVE_RECIPES}
    assert len(evidence['crafted']) == 83
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
