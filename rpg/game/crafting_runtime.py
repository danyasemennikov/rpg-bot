"""Phase 7 crafting runtime: recipe contract + validation + craft execution."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Literal

from game.profession_state import write_progression
from database import get_connection
from game.crafting_foundation import (
    CRAFTING_PROFESSION_CONTRACTS,
    CraftingProfessionKey,
    resolve_crafting_material_identity,
)
from game.gear_instances import grant_item_to_player
from game.gear_instances import generate_secondary_rolls_for_item
from game.items_data import get_item, get_item_metadata
from game.profession_recipes import (
    ACTIVE_RECIPES as PEV1_ACTIVE_RECIPES,
    ACTIVE_RECIPE_IDS as PEV1_ACTIVE_RECIPE_IDS,
    INACTIVE_RECIPE_IDS,
    parse_recipe_intent,
)
from game.profession_resources import RESOURCES

RequirementKind = Literal['bulk', 'special']
CraftStatus = Literal[
    'crafted',
    'recipe_not_found',
    'invalid_recipe_contract',
    'profession_level_too_low',
    'missing_materials',
    'craft_failed_atomic',
    'stale_action', 'in_battle', 'wrong_location', 'no_player',
]


@dataclass(frozen=True)
class RecipeRequirement:
    item_id: str
    quantity: int
    expected_group: str | None = None


@dataclass(frozen=True)
class RecipeDefinition:
    recipe_id: str
    output_item_id: str | None
    output_quantity: int
    profession_key: CraftingProfessionKey
    minimum_profession_level: int
    material_requirements: tuple[RecipeRequirement, ...]
    special_ingredient_requirements: tuple[RecipeRequirement, ...] = ()
    category: str | None = None
    notes: str | None = None
    recipes_are_permanent: bool = True
    active: bool = True
    starter: bool = False
    learning_gold: int = 0
    training_ceiling: int = 6
    catalog_version: int = 1
    output_kind: str = 'consumable'
    item_tier: int | None = None
    output_rarity: str = 'common'
    secondary_policy: str = 'not_applicable'
    material_value: int = 0
    tool_profession: str | None = None
    tool_tier: int | None = None


@dataclass(frozen=True)
class MissingMaterial:
    item_id: str
    required: int
    available: int
    requirement_kind: RequirementKind


@dataclass(frozen=True)
class CraftResult:
    status: CraftStatus
    recipe_id: str
    profession_key: CraftingProfessionKey | None = None
    required_profession_level: int | None = None
    player_profession_level: int | None = None
    missing_materials: tuple[MissingMaterial, ...] = field(default_factory=tuple)
    crafted_item_id: str | None = None
    crafted_quantity: int = 0
    profession_xp: int = 0
    instance_ids: tuple[int, ...] = field(default_factory=tuple)
    recovered: bool = False

    @property
    def is_success(self) -> bool:
        return self.status == 'crafted'


STARTER_RECIPES: tuple[RecipeDefinition, ...] = (
    RecipeDefinition(
        recipe_id='alchemy_minor_health_potion',
        output_item_id='health_potion_small',
        output_quantity=1,
        profession_key='alchemy',
        minimum_profession_level=1,
        material_requirements=(
            RecipeRequirement(item_id='herb_common', quantity=2, expected_group='herb_base'),
            RecipeRequirement(item_id='herb_magic', quantity=1, expected_group='herb_base'),
        ),
        special_ingredient_requirements=(
            RecipeRequirement(item_id='spider_venom', quantity=1, expected_group='venom'),
        ),
        category='starter_alchemy',
    ),
    RecipeDefinition(
        recipe_id='cooking_field_ration',
        output_item_id='health_potion_small',
        output_quantity=1,
        profession_key='cooking',
        minimum_profession_level=1,
        material_requirements=(
            RecipeRequirement(item_id='boar_meat', quantity=2, expected_group='meat'),
            RecipeRequirement(item_id='herb_common', quantity=1, expected_group='herb_base'),
            RecipeRequirement(item_id='coal', quantity=1, expected_group='fuel'),
        ),
        category='starter_cooking',
        notes='Temporary food-output bridge until dedicated food consumables are added.',
    ),
    RecipeDefinition(
        recipe_id='blacksmith_iron_sword',
        output_item_id='iron_sword',
        output_quantity=1,
        profession_key='blacksmith',
        minimum_profession_level=2,
        material_requirements=(
            RecipeRequirement(item_id='iron_ore', quantity=3, expected_group='ore'),
            RecipeRequirement(item_id='coal', quantity=1, expected_group='fuel'),
            RecipeRequirement(item_id='wood_dark', quantity=1, expected_group='wood'),
        ),
        special_ingredient_requirements=(
            RecipeRequirement(item_id='wolf_fang', quantity=1, expected_group='trophy'),
        ),
        category='starter_blacksmith',
    ),
    RecipeDefinition(
        recipe_id='arcane_focus_orb',
        output_item_id='apprentice_focus_orb',
        output_quantity=1,
        profession_key='arcane_engineer',
        minimum_profession_level=2,
        material_requirements=(
            RecipeRequirement(item_id='wood_dark', quantity=2, expected_group='wood'),
            RecipeRequirement(item_id='gem_common', quantity=1, expected_group='gem'),
        ),
        special_ingredient_requirements=(
            RecipeRequirement(item_id='stone_core', quantity=1, expected_group='core'),
        ),
        category='starter_arcane_engineer',
    ),
)

EARLY_RECIPES = (
    RecipeDefinition('field_tonic', 'health_potion_small', 1, 'alchemy', 1,
                     (RecipeRequirement('herb_common', 3, 'herb_base'),)),
    RecipeDefinition('trail_ration', 'field_ration', 1, 'cooking', 1,
                     (RecipeRequirement('boar_meat', 1, 'meat'), RecipeRequirement('herb_common', 1, 'herb_base'))),
    RecipeDefinition('trail_vest', 'trail_vest', 1, 'medium_armor', 1,
                     (RecipeRequirement('wolf_pelt', 2, 'hide'), RecipeRequirement('wood_common', 2, 'wood'))),
    RecipeDefinition('field_mana', 'mana_potion', 1, 'alchemy', 2,
                     (RecipeRequirement('herb_common', 5, 'herb_base'),)),
)
def _pev1_runtime_recipe(recipe) -> RecipeDefinition:
    bulk, special = [], []
    for item_id, quantity in recipe.requirements:
        group = RESOURCES[item_id].resource_group
        target = special if group in {'trophy', 'monster_part'} else bulk
        target.append(RecipeRequirement(item_id, quantity, group))
    return RecipeDefinition(
        recipe.recipe_id, recipe.output_spec.item_id, recipe.output_spec.quantity,
        recipe.profession_key, recipe.required_level, tuple(bulk), tuple(special),
        recipes_are_permanent=True, active=True, starter=recipe.starter,
        learning_gold=recipe.learning_gold, training_ceiling=recipe.training_ceiling,
        catalog_version=recipe.catalog_version, output_kind=recipe.output_spec.kind,
        item_tier=recipe.output_spec.item_tier, output_rarity=recipe.output_spec.rarity,
        secondary_policy=recipe.output_spec.secondary_policy,
        material_value=recipe.material_value,tool_profession=recipe.output_spec.profession_key,
        tool_tier=recipe.output_spec.tool_tier,
    )


ACTIVE_RECIPES = tuple(_pev1_runtime_recipe(recipe) for recipe in PEV1_ACTIVE_RECIPES)
LIVE_RECIPE_IDS = tuple(PEV1_ACTIVE_RECIPE_IDS)
INACTIVE_RECIPE_BY_ID = {recipe.recipe_id: recipe for recipe in STARTER_RECIPES if recipe.recipe_id in INACTIVE_RECIPE_IDS}
RECIPE_BY_ID: dict[str, RecipeDefinition] = {
    **{recipe.recipe_id: recipe for recipe in ACTIVE_RECIPES},
    **INACTIVE_RECIPE_BY_ID,
}


def get_recipe(recipe_id: str) -> RecipeDefinition | None:
    return RECIPE_BY_ID.get(recipe_id) or INACTIVE_RECIPE_BY_ID.get(recipe_id)


def _craft_rejection(conn, *, player_id, player, request_id, receipt_hash, recipe, status, details=None):
    from game.economy_actions import store_receipt
    result = {'schema_version':1,'catalog_version':2,'action_kind':'craft','status':status,'player_id':player_id,
              'location_id':player.get('location_id'),'recipe_id':recipe.recipe_id,
              'consumed':[],'granted':[],'gold_delta':0,'gold_after':player.get('gold',0),
              'progression':[],'source':{'catalog_version':2},'details':details or {}}
    if request_id:
        store_receipt(conn, player_id, request_id, 'craft', receipt_hash, result,catalog_version=2)
        conn.commit()
    return CraftResult(status=status, recipe_id=recipe.recipe_id,
                       profession_key=recipe.profession_key,
                       required_profession_level=recipe.minimum_profession_level)


def craft_recipe(telegram_id, recipe_id, profession_levels=None, *, action_token=None, request_id=None, rng=None):
    """Telegram singleton adapter; the same executor serves durable batches."""
    from game.action_receipts import consume_action, ActionRejected
    conn=get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if not action_token:
            raise ActionRejected('stale_action')
        request_id=request_id or 'ui:'+action_token
        prior=conn.execute('SELECT result_json FROM economy_action_receipts WHERE player_id=? AND request_id=?',
                           (telegram_id,request_id)).fetchone()
        if prior:
            result=json.loads(prior['result_json'])
            if result.get('recipe_id')!=recipe_id:
                raise ActionRejected('stale_action')
            return _craft_result(result,recovered=True)
        payload=json.loads(consume_action(conn,telegram_id,'craft',action_token))
        if payload.get('recipe_id')!=recipe_id or payload.get('catalog_version')!=3:
            raise ActionRejected('stale_action')
        from game.profession_recipes import get_recipe as catalog_recipe
        recipe=catalog_recipe(recipe_id)
        if not recipe:
            raise ActionRejected('recipe_not_found')
        if payload.get('commission'):
            from game.profession_supply import execute_commission
            result=execute_commission(conn,telegram_id,recipe_id,expected_revision=payload.get('tool_revision'),
                confirmed=payload.get('replacement_confirmed'),request_id=request_id,
                expected_quote=payload.get('commission_quote'))
        elif recipe.output_spec.kind=='tool':
            if payload.get('count',1)!=1 or payload.get('replacement_confirmed') is not True:
                raise ActionRejected('tool_confirmation_required')
            result=execute_craft_operation(conn,telegram_id,recipe_id,operation_id=request_id,
                mode='personal',expected_tool_revision=payload.get('tool_revision'))
        else:
            batch_id=payload.get('batch_id')
            if not batch_id:
                batch=create_craft_batch(conn,telegram_id,recipe_id,payload.get('count',1),batch_id=request_id)
                batch_id=batch['batch_id']
            result=execute_craft_batch(conn,telegram_id,batch_id)
        from game.economy_actions import store_receipt,intent_hash
        store_receipt(conn,telegram_id,request_id,'craft',intent_hash('craft',telegram_id,payload),result,catalog_version=3)
        conn.commit()
        return _craft_result(result)
    except ActionRejected as exc:
        conn.rollback()
        return CraftResult(status=str(exc),recipe_id=recipe_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _craft_result(result, *, recovered=False):
    progression=result.get('progression',[])
    grants=result.get('granted',[])
    return CraftResult(status=result.get('status','crafted'),recipe_id=result['recipe_id'],
        crafted_quantity=sum(g.get('quantity',0) for g in grants),
        profession_xp=sum(p.get('applied',0) for p in progression),
        instance_ids=tuple(i for g in grants for i in g.get('instance_ids',[])),recovered=recovered)


def create_craft_batch(conn,player_id,recipe_id,count,*,batch_id=None):
    import secrets,time
    from game.profession_recipes import get_recipe as catalog_recipe
    from game.profession_state import get_state
    from game.profession_progression import personal_batch_limit
    from game.action_receipts import peaceful_player,ActionRejected
    from game.economy_actions import intent_hash
    if not conn.in_transaction:
        raise RuntimeError('batch preview requires writer transaction')
    peaceful_player(conn,player_id,service='craftsmen_guild')
    recipe=catalog_recipe(recipe_id)
    if not recipe or recipe.output_spec.kind not in ('gear','consumable'):
        raise ActionRejected('invalid_batch_recipe')
    state=get_state(conn,player_id,recipe.profession_key,registered=True)
    from game.recipe_knowledge import require_knowledge
    require_knowledge(conn,player_id,recipe.profession_key,recipe.tier,recipe_id)
    if state['tier']<recipe.tier:
        raise ActionRejected('profession_level_too_low')
    if type(count) is not int or not 1<=count<=personal_batch_limit(state['level']):
        raise ActionRejected('batch_limit')
    batch_id=batch_id or secrets.token_hex(16)
    payload={'player_id':player_id,'profession_key':recipe.profession_key,'recipe_id':recipe_id,
             'count':count,'catalog_version':3,'policy_version':3,'destination':'inventory',
             'knowledge_version':3,'profession_revision':state['revision'],
             'requirements':dict(recipe.requirements)}
    fingerprint=intent_hash('profession_batch',player_id,payload)
    conn.execute('INSERT INTO profession_batch(batch_id,player_id,fingerprint,payload_json,created_ms) VALUES (?,?,?,?,?)',
                 (batch_id,player_id,fingerprint,json.dumps(payload,sort_keys=True),int(time.time()*1000)))
    return {'batch_id':batch_id,'payload':payload,'fingerprint':fingerprint}


def execute_craft_batch(conn,player_id,batch_id,*,expected_fingerprint=None):
    from game.action_receipts import ActionRejected,peaceful_player
    from game.profession_state import get_state
    from game.profession_progression import personal_batch_limit
    from game.profession_recipes import get_recipe as catalog_recipe
    from game.economy_actions import intent_hash
    if not conn.in_transaction:
        raise RuntimeError('batch requires writer transaction')
    batch=conn.execute('SELECT * FROM profession_batch WHERE batch_id=? AND player_id=?',(batch_id,player_id)).fetchone()
    if not batch:
        raise ActionRejected('stale_action')
    payload=json.loads(batch['payload_json'])
    if (intent_hash('profession_batch',player_id,payload)!=batch['fingerprint']
            or expected_fingerprint is not None and batch['fingerprint']!=expected_fingerprint):
        raise ActionRejected('batch_fingerprint_mismatch')
    if batch['result_json']:
        return json.loads(batch['result_json'])
    player=peaceful_player(conn,player_id,service='craftsmen_guild')
    recipe=catalog_recipe(payload['recipe_id'])
    state=get_state(conn,player_id,payload['profession_key'],registered=True)
    if (state['revision']!=payload['profession_revision'] or not recipe
            or recipe.output_spec.kind not in ('gear','consumable') or payload['destination']!='inventory'
            or payload['catalog_version']!=3 or payload['policy_version']!=3
            or payload['count']>personal_batch_limit(state['level'])
            or payload['requirements']!=dict(recipe.requirements)):
        raise ActionRejected('stale_action')
    count=payload['count']
    required={'bulk':{i:q*count for i,q in recipe.requirements},'special':{}}
    if _find_missing_materials(player_id,required,conn=conn):
        raise ActionRejected('missing_materials')
    # SAVEPOINT also makes the executor safe when a caller catches an error.
    conn.execute('SAVEPOINT personal_batch')
    try:
        children=[]
        for index in range(count):
            operation_id=f'batch:{batch_id}:{index}'
            children.append(execute_craft_operation(conn,player_id,recipe.recipe_id,
                operation_id=operation_id,mode='personal'))
            conn.execute('INSERT INTO profession_batch_child VALUES (?,?,?)',(batch_id,index,operation_id))
        result={'schema_version':1,'catalog_version':3,'status':'crafted','action_kind':'craft',
                'player_id':player_id,'recipe_id':recipe.recipe_id,'batch_id':batch_id,
                'consumed':[{'item_id':i,'quantity':q*count} for i,q in recipe.requirements],
                'granted':[g for child in children for g in child['granted']],
                'progression':[p for child in children for p in child['progression']],
                'gold_delta':0,'gold_after':player['gold'],'children':children}
        conn.execute('UPDATE profession_batch SET result_json=? WHERE batch_id=?',
                     (json.dumps(result,sort_keys=True),batch_id))
        conn.execute('RELEASE personal_batch')
        return result
    except Exception:
        conn.execute('ROLLBACK TO personal_batch')
        conn.execute('RELEASE personal_batch')
        raise


def execute_craft_operation(conn,player_id,recipe_id,*,operation_id,mode,context_id=None,input_escrow_id=None,
                            expected_tool_revision=None,now_ms=None,recipe_snapshot=None,attempted_xp=None):
    """No commit/close. Inputs, outputs, observers and XP join the caller's writer."""
    import time,random,hashlib
    from game.action_receipts import ActionRejected,peaceful_player,require_item_delivery
    from game.profession_recipes import get_recipe as catalog_recipe
    from game.profession_state import get_state,award_operation
    from game.profession_progression import work_xp
    from game.recipe_knowledge import require_knowledge
    if not conn.in_transaction:
        raise RuntimeError('craft operation requires writer transaction')
    prior=conn.execute('SELECT * FROM profession_operation_receipts WHERE operation_id=?',(operation_id,)).fetchone()
    if prior:
        if (prior['player_id'],prior['source_id'],prior['origin_mode'],prior['context_id'])!=(player_id,recipe_id,mode,context_id):
            raise ActionRejected('operation_identity_mismatch')
        return json.loads(prior['result_json'])['craft_result']
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    if mode=='paid_job':
        from game.profession_guild import get_job
        job=get_job(conn,player_id,context_id)
        plan=json.loads(job['plan_json'])
        if job['status']!='active' or not 0<=job['stage_cursor']<len(plan['stages']):
            raise ActionRejected('invalid_input_authority')
        if now_ms<job['next_stage_earliest_ms']:
            raise ActionRejected('guild_stage_not_due')
        stage=plan['stages'][job['stage_cursor']]
        if (stage['source_id']!=recipe_id or stage['snapshot']!=recipe_snapshot
                or stage['attempted_xp']!=attempted_xp
                or operation_id!=f"{context_id}:stage:{job['stage_cursor']}"
                or input_escrow_id!=f"{context_id}:input:{job['stage_cursor']}"):
            raise ActionRejected('invalid_input_authority')
    elif mode=='profession_exam':
        if recipe_snapshot is not None or attempted_xp is not None:
            raise ActionRejected('invalid_input_authority')
        from game.profession_exams import validate_exam_craft_context
        recipe_snapshot=validate_exam_craft_context(conn,player_id,context_id,recipe_id,operation_id,input_escrow_id)
    elif recipe_snapshot is not None or attempted_xp is not None:
        raise ActionRejected('invalid_input_authority')
    if recipe_snapshot is not None:
        from game.profession_recipes import ProfessionRecipe,RecipeOutputSpec
        raw=dict(recipe_snapshot)
        raw['output_spec']=RecipeOutputSpec(**raw['output_spec'])
        raw['requirements']=tuple((i,q) for i,q in raw['requirements'])
        recipe=ProfessionRecipe(**raw)
    else:
        recipe=catalog_recipe(recipe_id)
    if not recipe:
        raise ActionRejected('recipe_not_found')
    state=get_state(conn,player_id,recipe.profession_key,registered=True)
    if state['tier']<recipe.tier:
        raise ActionRejected('profession_level_too_low')
    require_knowledge(conn,player_id,recipe.profession_key,recipe.tier,recipe_id)
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    if mode=='personal':
        player=peaceful_player(conn,player_id,service='craftsmen_guild')
        required={'bulk':dict(recipe.requirements),'special':{}}
        if _find_missing_materials(player_id,required,conn=conn):
            raise ActionRejected('missing_materials')
        _consume_recipe_materials(conn,player_id,required)
    elif mode in ('paid_job','profession_exam'):
        escrow=conn.execute("SELECT * FROM guild_escrow WHERE escrow_id=? AND player_id=? AND context_id=? AND direction='input' AND status='reserved'",
                             (input_escrow_id,player_id,context_id)).fetchone()
        expected_owner='npc' if mode=='paid_job' else 'exam'
        if not escrow or escrow['owner']!=expected_owner or json.loads(escrow['contents_json'])!=dict(recipe.requirements):
            raise ActionRejected('invalid_input_authority')
        conn.execute("UPDATE guild_escrow SET status='consumed' WHERE escrow_id=?",(input_escrow_id,))
        player=dict(conn.execute('SELECT * FROM players WHERE telegram_id=?',(player_id,)).fetchone())
    else:
        raise ActionRejected('invalid_profession_mode')
    output=recipe.output_spec
    if mode!='personal':
        from dataclasses import asdict
        output_ref='output:'+operation_id
        conn.execute("INSERT INTO guild_escrow VALUES (?,?,?,?,?,'output',?,'reserved')",
            (output_ref,player_id,'job' if mode=='paid_job' else 'exam',context_id,
             'npc' if mode=='paid_job' else 'exam',json.dumps(asdict(output),sort_keys=True)))
        granted=[]
    elif output.kind=='tool':
        from game.profession_tools import install_tool
        installed=install_tool(conn,player_id,output.profession_key,output.tool_tier,
            expected_revision=expected_tool_revision,now_ms=now_ms)
        output_ref=None
        granted=[{'kind':'tool','quantity':1,'tool':installed}]
    else:
        deterministic_rng=random.Random(int.from_bytes(hashlib.sha256(operation_id.encode()).digest(),'big'))
        secondary=[]
        spec=None
        if output.kind=='gear':
            if output.secondary_policy=='ordinary_one':
                secondary=generate_secondary_rolls_for_item(get_item(output.item_id),rarity=output.rarity,
                    item_tier=output.item_tier,rng=deterministic_rng)[:1]
            spec={'base_item_id':output.item_id,'item_tier':output.item_tier,'rarity':output.rarity,
                  'secondary_rolls':secondary,'enhance_level':0,'durability':100,'max_durability':100}
        grant=grant_item_to_player(player_id,output.item_id,output.quantity,source='crafting',gear_spec=spec,
            provenance={'source':'personal_adventure_craft','recipe_id':recipe_id,'operation_id':operation_id,'catalog_version':3},
            rng=deterministic_rng,conn=conn)
        require_item_delivery(grant,output.quantity)
        output_ref=None
        granted=[{'item_id':output.item_id,'quantity':output.quantity,'instance_ids':grant.get('instance_ids',[]),'gear_specs':[spec] if spec else []}]
        from game.quest_board import register_contract_objective
        from game.regional_objectives import observe_successful_craft
        register_contract_objective(conn,player_id,'craft',output.item_id,output.quantity,player['location_id'])
        observe_successful_craft(conn,player_id=player_id,recipe_id=recipe_id,output_item_id=output.item_id)
    xp=attempted_xp if attempted_xp is not None else work_xp(
        gathering=False,work_tier=recipe.tier,category=recipe.work_category,current_level=state['level'])
    result={'status':'crafted','recipe_id':recipe_id,'player_id':player_id,'mode':mode,'operation_id':operation_id,
            'consumed':[{'item_id':i,'quantity':q} for i,q in recipe.requirements] if mode=='personal' else [],
            'granted':granted,'output_escrow_ref':output_ref,'gold_delta':0,'gold_after':player['gold']}
    progression=award_operation(conn,player_id,recipe.profession_key,operation_id=operation_id,mode=mode,
        source_id=recipe_id,context_id=context_id,attempted=xp,result={'craft_result':result},now_ms=now_ms)
    result['progression']=[{k:v for k,v in progression.items() if k!='craft_result'}]
    # Persist the complete response, including progression, for lost-response replay.
    conn.execute('UPDATE profession_operation_receipts SET result_json=? WHERE operation_id=?',
                 (json.dumps({**progression,'craft_result':result},sort_keys=True),operation_id))
    return result


def validate_recipe_contract(recipe: RecipeDefinition) -> list[str]:
    errors: list[str] = []
    if recipe.profession_key not in CRAFTING_PROFESSION_CONTRACTS:
        errors.append(f'unknown profession {recipe.profession_key}')
        return errors

    if recipe.output_kind=='tool':
        if recipe.output_item_id is not None or recipe.output_quantity!=1 or recipe.tool_tier not in (1,2,3,4,5,6):
            errors.append('invalid tool output')
        return errors

    output_item = get_item(recipe.output_item_id)
    if output_item is None:
        errors.append(f'unknown output item {recipe.output_item_id}')

    if recipe.output_quantity <= 0:
        errors.append('output quantity must be positive')

    if recipe.minimum_profession_level < 1:
        errors.append('minimum profession level must be >= 1')

    if not recipe.material_requirements and not recipe.special_ingredient_requirements:
        errors.append('recipe must include at least one material requirement')

    bulk_ids = {requirement.item_id for requirement in recipe.material_requirements}
    special_ids = {requirement.item_id for requirement in recipe.special_ingredient_requirements}
    cross_kind_duplicates = sorted(bulk_ids.intersection(special_ids))
    for item_id in cross_kind_duplicates:
        errors.append(f'{item_id}: duplicate requirement across bulk and special is not allowed')

    contract = CRAFTING_PROFESSION_CONTRACTS[recipe.profession_key]
    output_families = resolve_crafting_output_families(recipe.output_item_id)
    if not output_families:
        errors.append(f'{recipe.output_item_id}: output family is unknown for crafting contract')
    elif not any(output_family in contract.output_families for output_family in output_families):
        errors.append(
            f'{recipe.output_item_id}: output families {output_families} are not allowed for {recipe.profession_key}'
        )

    errors.extend(_validate_requirements(recipe.profession_key, contract.bulk_resource_groups, recipe.material_requirements, 'bulk'))
    errors.extend(_validate_requirements(recipe.profession_key, contract.special_ingredient_groups, recipe.special_ingredient_requirements, 'special'))
    return errors


def resolve_crafting_output_families(item_id: str) -> tuple[str, ...]:
    item = get_item(item_id)
    if item is None:
        return ()

    item_type = item.get('item_type')
    if item.get('consumable_family') == 'food':
        return ('food', 'edible_recovery')
    if item_type == 'potion':
        # Temporary bridge: current cooking starter output reuses a consumable potion item.
        return ('potions', 'edible_recovery')

    metadata = get_item_metadata(item_id)
    weapon_profile = metadata.get('weapon_profile')
    slot_identity = metadata.get('slot_identity')
    offhand_profile = metadata.get('offhand_profile')
    armor_class = metadata.get('armor_class')

    if item_type == 'weapon':
        if weapon_profile == 'bow':
            return ('bows',)
        if weapon_profile in {'magic_staff', 'holy_staff'}:
            return ('staffs',)
        if weapon_profile == 'wand':
            return ('wands',)
        if weapon_profile == 'holy_rod':
            return ('rods',)
        if weapon_profile == 'tome':
            return ('tomes',)
        if weapon_profile in {'sword_1h', 'sword_2h', 'axe_2h', 'daggers'}:
            return ('metal_weapons',)

    if slot_identity == 'offhand':
        if offhand_profile == 'shield':
            return ('shields',)
        if offhand_profile == 'focus':
            return ('foci',)
        if offhand_profile == 'censer':
            return ('censers',)

    if item_type == 'armor' and slot_identity in {'helmet', 'chest', 'legs', 'boots', 'gloves'}:
        if armor_class == 'heavy':
            return ('heavy_armor',)
        if armor_class == 'medium':
            return ('medium_armor',)
        if armor_class == 'light':
            return ('light_armor',)

    return ()


def _validate_requirements(
    profession_key: CraftingProfessionKey,
    allowed_groups: tuple[str, ...],
    requirements: tuple[RecipeRequirement, ...],
    requirement_kind: RequirementKind,
) -> list[str]:
    errors: list[str] = []
    for requirement in requirements:
        if requirement.quantity <= 0:
            errors.append(f'{requirement.item_id}: quantity must be positive')
            continue

        identity = resolve_crafting_material_identity(requirement.item_id)
        if identity is None:
            errors.append(f'{requirement.item_id}: missing crafting identity')
            continue

        if requirement_kind == 'bulk':
            group = identity.bulk_resource_group
            if group is None:
                errors.append(f'{requirement.item_id}: expected bulk material')
                continue
        else:
            group = identity.special_ingredient_group
            if group is None:
                errors.append(f'{requirement.item_id}: expected special ingredient')
                continue

        if group not in allowed_groups:
            errors.append(f'{requirement.item_id}: group {group} is not allowed for {profession_key}')

        if requirement.expected_group is not None and group != requirement.expected_group:
            errors.append(f'{requirement.item_id}: group {group} does not match expected {requirement.expected_group}')

        if identity.default_professions and profession_key not in identity.default_professions:
            errors.append(f'{requirement.item_id}: profession {profession_key} is outside material contract')
    return errors


def _aggregate_recipe_requirements(recipe: RecipeDefinition) -> dict[str, dict[str, int]]:
    aggregated = {'bulk': {}, 'special': {}}
    for requirement in recipe.material_requirements:
        aggregated['bulk'][requirement.item_id] = aggregated['bulk'].get(requirement.item_id, 0) + int(requirement.quantity)
    for requirement in recipe.special_ingredient_requirements:
        aggregated['special'][requirement.item_id] = (
            aggregated['special'].get(requirement.item_id, 0) + int(requirement.quantity)
        )
    return aggregated


def _find_missing_materials(telegram_id: int, aggregated_requirements: dict[str, dict[str, int]], *, conn=None) -> list[MissingMaterial]:
    inventory = _get_inventory_quantities(telegram_id, conn=conn)
    missing: list[MissingMaterial] = []
    for item_id, required_qty in aggregated_requirements['bulk'].items():
        available = inventory.get(item_id, 0)
        if available < required_qty:
            missing.append(MissingMaterial(item_id, required_qty, available, 'bulk'))
    for item_id, required_qty in aggregated_requirements['special'].items():
        available = inventory.get(item_id, 0)
        if available < required_qty:
            missing.append(MissingMaterial(item_id, required_qty, available, 'special'))
    return missing


def _get_inventory_quantities(telegram_id: int, *, conn=None) -> dict[str, int]:
    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()
    try:
        rows = conn.execute('SELECT item_id, SUM(quantity) AS quantity FROM inventory WHERE telegram_id=? GROUP BY item_id', (telegram_id,)).fetchall()
        return {str(row['item_id']): int(row['quantity']) for row in rows}
    finally:
        if owns_connection:
            conn.close()


def _consume_recipe_materials(conn, telegram_id: int, aggregated_requirements: dict[str, dict[str, int]]):
    for requirement_kind in ('bulk', 'special'):
        for item_id, required_qty in aggregated_requirements[requirement_kind].items():
            rows = conn.execute(
                'SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id=? ORDER BY id',
                (telegram_id, item_id),
            ).fetchall()
            remaining = required_qty
            for row in rows:
                take = min(remaining, int(row['quantity']))
                if take <= 0:
                    continue
                if take == row['quantity']:
                    conn.execute('DELETE FROM inventory WHERE id=?', (row['id'],))
                else:
                    conn.execute('UPDATE inventory SET quantity=quantity-? WHERE id=?', (take, row['id']))
                remaining -= take
            if remaining:
                raise ValueError('materials_changed')
