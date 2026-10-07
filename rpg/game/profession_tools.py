"""Dedicated profession slots, deterministic wear and material/guild repairs."""

from __future__ import annotations

import json
import time

from game.action_receipts import ActionRejected, consume_action, peaceful_player
from game.economy_actions import find_receipt, intent_hash, store_receipt
from game.locations import get_location

PROFESSIONS = ('woodcutting','mining','herbalism','fishing','hunting')
TOOL_NAMES = dict(zip(PROFESSIONS,('axe','pick','sickle','rod','knife')))
ACCESS_LEVELS = {1:1,2:6,3:12,4:18}
MATERIAL_PRICES = {'wood_common':3,'iron_ore':6,'coal':4}


def get_tool(conn, player_id: int, profession: str) -> dict | None:
    row = conn.execute('SELECT * FROM player_profession_tools WHERE player_id=? AND profession_key=?', (player_id,profession)).fetchone()
    return dict(row) if row else None


def require_tool(conn, player_id: int, profession: str, *, required_tier: int=1) -> dict:
    tool = get_tool(conn,player_id,profession)
    if not tool:
        raise ActionRejected('tool_missing')
    if tool['tier'] < required_tier:
        raise ActionRejected('tool_tier_locked')
    if tool['durability'] <= 0:
        raise ActionRejected('tool_broken')
    return tool


def wear_tool(conn, tool: dict, *, now_ms: int) -> dict:
    changed = conn.execute('''UPDATE player_profession_tools SET durability=durability-1,
        revision=revision+1,updated_ms=? WHERE player_id=? AND profession_key=? AND revision=? AND durability>0''',
        (now_ms,tool['player_id'],tool['profession_key'],tool['revision']))
    if changed.rowcount != 1:
        raise ActionRejected('tool_changed')
    updated = get_tool(conn,tool['player_id'],tool['profession_key'])
    capacity = 60*tool['tier']
    updated['worn_warning'] = tool['durability']*5>capacity and updated['durability']*5<=capacity
    return updated


def install_tool(conn, player_id: int, profession: str, tier: int, *, expected_revision: int,
                 now_ms: int, commission: bool=False) -> dict:
    old = get_tool(conn,player_id,profession)
    if tier not in ACCESS_LEVELS or profession not in PROFESSIONS:
        raise ActionRejected('invalid_tool')
    if not old or old['revision'] != expected_revision:
        raise ActionRejected('tool_changed')
    if tier < old['tier']:
        raise ActionRejected('tool_no_downgrade')
    mask = int(old['bootstrap_used_mask'])
    if commission:
        if profession not in {'woodcutting','mining'} or tier<2 or old['tier'] != tier-1:
            raise ActionRejected('commission_previous_tier')
        bit = 1 << (tier-2)
        if mask & bit:
            raise ActionRejected('commission_used')
        mask |= bit
    conn.execute('''UPDATE player_profession_tools SET tier=?,durability=?,revision=revision+1,
        bootstrap_used_mask=?,updated_ms=? WHERE player_id=? AND profession_key=? AND revision=?''',
        (tier,60*tier,mask,now_ms,player_id,profession,expected_revision))
    return get_tool(conn,player_id,profession)


def repair_costs(tier: int, durability: int) -> dict:
    if tier not in ACCESS_LEVELS or not 0<=durability<=60*tier:
        raise ValueError('invalid_tool')
    if tier == 1:
        raise ActionRejected('tool_t1_no_repair')
    missing = 60*tier-durability
    return {'materials':{item:(missing*tier+denominator-1)//denominator
            for item,denominator in [('wood_common',60),('iron_ore',120),('coal',240)]},
            'gold':(missing*tier+19)//20,'restored':missing}


def repair_quote(conn, player_id: int, profession: str) -> dict:
    tool = get_tool(conn,player_id,profession)
    if not tool:
        raise ActionRejected('tool_missing')
    costs = repair_costs(tool['tier'],tool['durability'])
    consumed,supplied,owned = {},{},{}
    for item,required in costs['materials'].items():
        available = conn.execute('SELECT COALESCE(SUM(quantity),0) FROM inventory WHERE telegram_id=? AND item_id=?', (player_id,item)).fetchone()[0]
        owned[item] = int(available)
        consumed[item] = min(int(available),required)
        supplied[item] = required-consumed[item]
    mode = 'assisted' if any(supplied.values()) else 'materials'
    gold = costs['gold']+3*sum(supplied[i]*MATERIAL_PRICES[i] for i in supplied)
    return {'schema_version':1,'profession_key':profession,'tool_revision':tool['revision'],
            'tool_tier':tool['tier'],'durability':tool['durability'],'repair_mode':mode,
            'consumed':consumed,'supplied':supplied,'owned':owned,'gold':gold,
            'restored':costs['restored'],'durability_after':60*tool['tier']}


def commission_inputs(conn, player_id: int, recipe) -> tuple[dict,int,dict]:
    from game.profession_resources import RESOURCES, ENVIRONMENTAL_SOURCES
    output = recipe.output_spec
    tier,profession = output.tool_tier,output.profession_key
    tool = get_tool(conn,player_id,profession)
    if profession not in {'woodcutting','mining'} or tier not in (2,3,4):
        raise ActionRejected('commission_unavailable')
    if not tool or tool['tier'] != tier-1:
        raise ActionRejected('commission_previous_tier')
    if tool['bootstrap_used_mask'] & (1 << (tier-2)):
        raise ActionRejected('commission_used')
    state = conn.execute('SELECT level FROM player_gathering_professions WHERE telegram_id=? AND profession_key=?', (player_id,profession)).fetchone()
    if not state or state['level'] < ACCESS_LEVELS[tier]:
        raise ActionRejected('profession_level_too_low')
    inputs = dict(recipe.requirements)
    contributed = {i:q for i,q in recipe.requirements if RESOURCES[i].resource_tier==tier}
    visited = {r['location_id'] for r in conn.execute('SELECT location_id FROM player_location_discovery WHERE telegram_id=?', (player_id,))}
    for item in contributed:
        sources = {loc for loc,rows in ENVIRONMENTAL_SOURCES.items() if any(i==item for i,_ in rows)}
        if not sources & visited:
            raise ActionRejected('commission_visit_required')
        inputs.pop(item)
    inputs['wood_common'] *= 3
    return inputs,20*tier*tier,contributed


def craft_tool(player_id: int, recipe_id: str, *, action_token: str | None,
               request_id: str | None=None) -> dict:
    from database import get_connection
    from game.crafting_runtime import _consume_recipe_materials
    from game.profession_recipes import get_recipe
    from game.profession_progression import apply_profession_xp, crafting_xp_for_success
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if not action_token:
            raise ActionRejected('stale_action')
        request_id = request_id or f'ui:{action_token}'
        prior = conn.execute('SELECT action_kind,result_json FROM economy_action_receipts WHERE player_id=? AND request_id=?', (player_id,request_id)).fetchone()
        if prior:
            result = json.loads(prior['result_json'])
            if prior['action_kind'] not in {'tool_craft_pxe1','tool_commission_pxe1'} or result['recipe_id']!=recipe_id:
                raise ActionRejected('stale_action')
            conn.commit()
            return {**result,'recovered':True}
        payload = json.loads(consume_action(conn,player_id,'craft',action_token))
        if payload.get('schema_version')!=1 or payload.get('catalog_version')!=2 or payload.get('recipe_id')!=recipe_id:
            raise ActionRejected('stale_action')
        recipe = get_recipe(recipe_id)
        if not recipe or recipe.output_spec.kind!='tool':
            raise ActionRejected('recipe_not_found')
        player = peaceful_player(conn,player_id,service='craftsmen_guild')
        from game.profession_schema import ensure_profession_rows
        ensure_profession_rows(conn,player_id)
        known = conn.execute('SELECT 1 FROM player_recipe_knowledge WHERE player_id=? AND recipe_id=?', (player_id,recipe_id)).fetchone()
        if not known:
            raise ActionRejected('recipe_not_known')
        state = conn.execute('SELECT level,exp FROM player_crafting_professions WHERE player_id=? AND profession_key=?', (player_id,recipe.profession_key)).fetchone()
        if not state or state['level']<recipe.required_level:
            raise ActionRejected('profession_level_too_low')
        tool = get_tool(conn,player_id,recipe.output_spec.profession_key)
        if not tool or tool['revision']!=payload.get('tool_revision'):
            raise ActionRejected('tool_changed')
        if tool['tier']>recipe.output_spec.tool_tier:
            raise ActionRejected('tool_no_downgrade')
        if payload.get('replacement_confirmed') is not True:
            raise ActionRejected('tool_confirmation_required')
        commission = payload.get('commission') is True
        inputs,gold,supplied = commission_inputs(conn,player_id,recipe) if commission else (dict(recipe.requirements),0,{})
        # Aggregate duplicate stacks; never credit guild contributions to inventory.
        for item,quantity in inputs.items():
            owned = conn.execute('SELECT COALESCE(SUM(quantity),0) FROM inventory WHERE telegram_id=? AND item_id=?', (player_id,item)).fetchone()[0]
            if 'input_snapshot' in payload and payload['input_snapshot'].get(item)!=owned:
                raise ActionRejected('tool_quote_changed')
            if owned<quantity:
                raise ActionRejected('missing_materials')
        if player['gold']<gold:
            raise ActionRejected('insufficient_gold')
        _consume_recipe_materials(conn,player_id,{'bulk':inputs,'special':{}})
        conn.execute('UPDATE players SET gold=gold-? WHERE telegram_id=?', (gold,player_id))
        installed = install_tool(conn,player_id,recipe.output_spec.profession_key,recipe.output_spec.tool_tier,
            expected_revision=tool['revision'],now_ms=int(time.time()*1000),commission=commission)
        xp = crafting_xp_for_success(current_level=state['level'],current_exp=state['exp'],
            recipe_level=recipe.required_level,material_value=recipe.material_value)
        progression = apply_profession_xp(state['level'],state['exp'],xp)
        from game.player_feedback import record_progression
        record_progression(conn,player_id,recipe.profession_key,progression,request_id)
        if xp:
            conn.execute('UPDATE player_crafting_professions SET level=?,exp=? WHERE player_id=? AND profession_key=?',
                (progression.new_level,progression.new_exp,player_id,recipe.profession_key))
        kind = 'tool_commission_pxe1' if commission else 'tool_craft_pxe1'
        result = {'schema_version':1,'catalog_version':2,'xp_policy_version':2,'action_kind':kind,'status':'crafted',
            'player_id':player_id,'location_id':player['location_id'],'recipe_id':recipe_id,
            'consumed':[{'item_id':i,'quantity':q} for i,q in inputs.items()],
            'granted':[{'kind':'tool','profession_key':recipe.output_spec.profession_key,'tool_tier':recipe.output_spec.tool_tier,'quantity':1}],
            'gold_delta':-gold,'gold_after':player['gold']-gold,
            'progression':[{'profession_key':recipe.profession_key,**progression.__dict__}],
            'source':{'catalog_version':2},'details':{'tool':installed,'guild_supplied':supplied}}
        store_receipt(conn,player_id,request_id,kind,intent_hash(kind,player_id,payload),result,catalog_version=2)
        conn.commit()
        return result
    except ActionRejected as exc:
        conn.rollback()
        return {'status':str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def commit_tool_maintenance(player_id: int, *, action_token: str, replace: bool=False) -> dict:
    """Exact preview hash, token, debit, tool and receipt share one transaction."""
    from database import get_connection
    from game.crafting_runtime import _consume_recipe_materials
    kind = 'tool_replace_pxe1' if replace else 'tool_repair_pxe1'
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        request_id = f'ui:{action_token}'
        prior = conn.execute('SELECT action_kind,result_json FROM economy_action_receipts WHERE player_id=? AND request_id=?', (player_id,request_id)).fetchone()
        if prior:
            if prior['action_kind'] != kind:
                raise ActionRejected('stale_action')
            conn.commit()
            return {**json.loads(prior['result_json']),'recovered':True}
        quote = json.loads(consume_action(conn,player_id,kind,action_token))
        player = peaceful_player(conn,player_id)
        profession = quote['profession_key']
        tool = get_tool(conn,player_id,profession)
        if replace:
            from game.build_contract import SAFE_BUILD_HUBS
            from game.locations import resolve_location_id
            if resolve_location_id(player['location_id']) not in SAFE_BUILD_HUBS:
                raise ActionRejected('safe_hub_required')
            if not tool or tool['tier']>1:
                raise ActionRejected('tool_no_downgrade')
            current = {'schema_version':1,'profession_key':profession,'tool_revision':tool['revision'],'gold':12}
        else:
            if 'craftsmen_guild' not in (get_location(player['location_id']) or {}).get('services',[]):
                raise ActionRejected('wrong_location')
            current = repair_quote(conn,player_id,profession)
        if quote != current:
            raise ActionRejected('repair_quote_changed')
        if not replace and current['restored']==0:
            conn.rollback()
            return {'status':'full','gold_delta':0}
        cost = current['gold']
        if player['gold']<cost:
            raise ActionRejected('insufficient_gold')
        if not replace:
            _consume_recipe_materials(conn,player_id,{'bulk':current['consumed'],'special':{}})
        conn.execute('UPDATE players SET gold=gold-? WHERE telegram_id=?', (cost,player_id))
        if replace:
            updated = install_tool(conn,player_id,profession,1,expected_revision=tool['revision'],now_ms=int(time.time()*1000))
        else:
            conn.execute('''UPDATE player_profession_tools SET durability=60*tier,revision=revision+1,
                updated_ms=? WHERE player_id=? AND profession_key=? AND revision=?''',
                (int(time.time()*1000),player_id,profession,tool['revision']))
            updated = get_tool(conn,player_id,profession)
        result = {'schema_version':1,'catalog_version':2,'action_kind':kind,'status':'replaced' if replace else 'repaired',
            'player_id':player_id,'location_id':player['location_id'],'recipe_id':None,'quote':current,
            'consumed':[{'item_id':i,'quantity':q} for i,q in current.get('consumed',{}).items() if q],
            'granted':[],'gold_delta':-cost,'gold_after':player['gold']-cost,
            'progression':[],'source':{'catalog_version':2},'details':{'tool':updated}}
        store_receipt(conn,player_id,request_id,kind,intent_hash(kind,player_id,current),result,catalog_version=2)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
