"""Explicit guild stages. Deadlines never execute work or issue rewards."""
import json
import secrets
import time
from pathlib import Path
from dataclasses import asdict
from game.action_receipts import ActionRejected, peaceful_player, require_item_delivery
from game.economy_actions import intent_hash
from game.profession_state import get_state, award_operation
from game.profession_schema import GATHERING_PROFESSION_KEYS
from game.profession_resources import RESOURCES
from game.profession_recipes import get_recipe
from game.profession_progression import work_xp, processing_duration_ms
from game.recipe_knowledge import require_knowledge

MILESTONE_JOBS = {r['job_key']:r for r in json.loads(
    Path(__file__).with_name('profession_guild_jobs.json').read_text(encoding='utf-8'))}


def _writer(conn):
    if not conn.in_transaction:
        raise RuntimeError('guild action requires caller-owned writer transaction')


def _now(now_ms):
    return int(time.time()*1000) if now_ms is None else int(now_ms)


def _escrow(conn,player_id,job_id,escrow_id,contents):
    conn.execute("INSERT INTO guild_escrow VALUES (?,?, 'job',?,'npc','input',?,'reserved')",
                 (escrow_id,player_id,job_id,json.dumps(contents,sort_keys=True)))


def accept_job(conn,player_id,profession,*,mode='paid_job',source_id=None,job_key=None,
               request_id,now_ms=None):
    _writer(conn)
    now_ms=_now(now_ms)
    # Stable acceptance identity survives reconnect and a replacement UI token.
    job_id='guild:'+str(player_id)+':'+request_id
    selection={'profession':profession,'mode':mode,'source_id':source_id,'job_key':job_key}
    prior=conn.execute('SELECT * FROM guild_job WHERE job_id=? AND player_id=?',(job_id,player_id)).fetchone()
    if prior:
        if json.loads(prior['plan_json'])['selection']!=selection:
            raise ActionRejected('request_receipt_mismatch')
        return dict(prior)
    player=peaceful_player(conn,player_id,service='craftsmen_guild')
    state=get_state(conn,player_id,profession,registered=True)
    if mode not in ('paid_job','personal_processing'):
        raise ActionRejected('invalid_profession_mode')
    gathering=profession in GATHERING_PROFESSION_KEYS
    if mode=='personal_processing' and not gathering:
        raise ActionRejected('invalid_profession_mode')
    definition=MILESTONE_JOBS.get(job_key) if job_key else None
    if job_key and (not definition or definition['profession_key']!=profession or mode!='paid_job'
                    or state['level']<definition['unlock_P']):
        raise ActionRejected('guild_job_locked')
    sources=definition['sources'] if definition else [source_id]
    if not all(sources):
        raise ActionRejected('invalid_guild_source')
    stages=[]
    tier=None
    for source in sources:
        if gathering:
            resource=RESOURCES.get(source)
            if not resource or resource.profession_key!=profession:
                raise ActionRejected('invalid_guild_source')
            source_tier=resource.resource_tier
            category=resource.work_category
            snapshot={'item_id':source,'tier':source_tier,'category':category,'value':resource.sell_price}
            require_knowledge(conn,player_id,profession,source_tier)
            from game.profession_recipes import GATHERING_MANUALS
            knowledge_id=next(k for k in sorted(GATHERING_MANUALS)
                if GATHERING_MANUALS[k]['profession_key']==profession and GATHERING_MANUALS[k]['tier']==source_tier
                and conn.execute('SELECT 1 FROM player_recipe_knowledge WHERE player_id=? AND recipe_id=?',(player_id,k)).fetchone())
        else:
            recipe=get_recipe(source)
            if not recipe or recipe.profession_key!=profession:
                raise ActionRejected('invalid_guild_source')
            source_tier=recipe.tier
            category=recipe.work_category
            snapshot=asdict(recipe)
            require_knowledge(conn,player_id,profession,source_tier,source)
            knowledge_id=source
        if state['tier']<source_tier or tier is not None and tier!=source_tier:
            raise ActionRejected('profession_level_too_low')
        tier=source_tier
        stage={'source_id':source,'snapshot':snapshot,'knowledge_id':knowledge_id,
               'attempted_xp':work_xp(gathering=gathering,work_tier=tier,category=category,current_level=state['level'])}
        stages.append(stage)
    if gathering:
        stages=([stages[0]]*8+[stages[1]]*7) if definition else [stages[0]]*15
    else:
        stages=([stages[0]]*2+[stages[1]]*2) if definition else [stages[0]]*4
    duration=processing_duration_ms(state['level']) if mode=='personal_processing' else 120000
    qty=({'S':3,'R':2,'C':1}[stages[0]['snapshot']['category']]) if mode=='personal_processing' else 0
    cost=2*stages[0]['snapshot']['value']*qty if qty else 0
    if player['gold']<cost:
        raise ActionRejected('insufficient_gold')
    plan={'selection':selection,'player_id':player_id,'profession_key':profession,'mode':mode,
          'tier':tier,'location_id':player['location_id'],'travel_revision':player['travel_revision'],
          'required_knowledge':sorted({stage['knowledge_id'] for stage in stages}),
          'active_activity_revision':0,'catalog_version':3,'policy_version':3,'mastery_snapshot':state['level'],
          'stages':stages,'stage_duration_ms':duration//len(stages),'total_duration_ms':duration,
          'cost':cost,'wage':(5 if tier==1 else 10) if mode=='paid_job' else 0,
          'result_item_id':source_id if qty else None,'result_qty':qty,'loan_tool_tier':1 if tier==1 else 4}
    fingerprint=intent_hash('guild_plan',player_id,plan)
    conn.execute('''INSERT INTO guild_job(job_id,player_id,profession_key,mode,status,plan_json,
        fingerprint,accepted_ms,next_stage_earliest_ms) VALUES (?,?,?,?,'active',?,?,?,?)''',
        (job_id,player_id,profession,mode,json.dumps(plan,sort_keys=True),fingerprint,
         now_ms,now_ms+plan['stage_duration_ms']))
    for index,stage in enumerate(stages):
        contents=stage['snapshot']['requirements'] if not gathering else {'source_id':stage['source_id'],'loan_tool_tier':plan['loan_tool_tier']}
        if not gathering:
            contents=dict(contents)
        _escrow(conn,player_id,job_id,f'{job_id}:input:{index}',contents)
    if cost:
        conn.execute('UPDATE players SET gold=gold-? WHERE telegram_id=?',(cost,player_id))
    return get_job(conn,player_id,job_id)


def get_job(conn,player_id,job_id):
    row=conn.execute('SELECT * FROM guild_job WHERE job_id=? AND player_id=?',(job_id,player_id)).fetchone()
    if not row:
        raise ActionRejected('guild_job_not_found')
    plan=json.loads(row['plan_json'])
    if intent_hash('guild_plan',player_id,plan)!=row['fingerprint']:
        raise ActionRejected('guild_plan_mismatch')
    return dict(row)


def complete_stage(conn,player_id,job_id,*,stage_index,expected_revision,now_ms=None):
    _writer(conn)
    job=get_job(conn,player_id,job_id)
    prior=conn.execute('''SELECT o.result_json FROM guild_stage_receipt s
        JOIN profession_operation_receipts o ON o.operation_id=s.operation_id
        WHERE s.job_id=? AND s.stage_index=?''',(job_id,stage_index)).fetchone()
    if prior:
        return json.loads(prior['result_json'])
    if type(stage_index) is not int or stage_index!=job['stage_cursor'] or job['revision']!=expected_revision:
        raise ActionRejected('stale_action')
    if job['status']!='active':
        raise ActionRejected('guild_job_not_active')
    from game.player_activity import require_available
    require_available(conn,player_id,exclude_guild=job_id)
    now_ms=_now(now_ms)
    if now_ms<job['next_stage_earliest_ms']:
        raise ActionRejected('guild_stage_not_due')
    plan=json.loads(job['plan_json'])
    player=dict(conn.execute('SELECT * FROM players WHERE telegram_id=?',(player_id,)).fetchone())
    if player['location_id']!=plan['location_id'] or player['travel_revision']!=plan['travel_revision']:
        raise ActionRejected('stale_action')
    stage=plan['stages'][stage_index]
    operation_id=f'{job_id}:stage:{stage_index}'
    input_ref=f'{job_id}:input:{stage_index}'
    if job['profession_key'] in GATHERING_PROFESSION_KEYS:
        escrow=conn.execute("SELECT * FROM guild_escrow WHERE escrow_id=? AND status='reserved'",(input_ref,)).fetchone()
        if not escrow or escrow['player_id']!=player_id or escrow['context_id']!=job_id:
            raise ActionRejected('invalid_input_authority')
        conn.execute("UPDATE guild_escrow SET status='consumed' WHERE escrow_id=?",(input_ref,))
        result=award_operation(conn,player_id,job['profession_key'],operation_id=operation_id,
            mode=job['mode'],source_id=stage['source_id'],context_id=job_id,attempted=stage['attempted_xp'],
            result={'job_id':job_id,'stage_index':stage_index},now_ms=now_ms)
    else:
        from game.crafting_runtime import execute_craft_operation
        execute_craft_operation(conn,player_id,stage['source_id'],operation_id=operation_id,
            mode='paid_job',context_id=job_id,input_escrow_id=input_ref,now_ms=now_ms,
            recipe_snapshot=stage['snapshot'],attempted_xp=stage['attempted_xp'])
        result=json.loads(conn.execute('SELECT result_json FROM profession_operation_receipts WHERE operation_id=?',
                                       (operation_id,)).fetchone()[0])
    conn.execute('INSERT INTO guild_stage_receipt VALUES (?,?,?,?)',(job_id,stage_index,operation_id,now_ms))
    final=stage_index+1==len(plan['stages'])
    next_due=max(now_ms,job['next_stage_earliest_ms'])+plan['stage_duration_ms']
    conn.execute('''UPDATE guild_job SET stage_cursor=stage_cursor+1,next_stage_earliest_ms=?,
        revision=revision+1,status=? WHERE job_id=? AND revision=?''',
        (next_due,'ready_to_claim' if final else 'active',job_id,expected_revision))
    return result


def finish_job(conn,player_id,job_id,*,claim,expected_revision):
    _writer(conn)
    job=get_job(conn,player_id,job_id)
    if job['terminal_result_json']:
        result=json.loads(job['terminal_result_json'])
        if result['action']!=('claim' if claim else 'cancel'):
            raise ActionRejected('guild_job_terminal')
        return result
    if job['revision']!=expected_revision:
        raise ActionRejected('stale_action')
    from game.player_activity import require_available
    require_available(conn,player_id,exclude_guild=job_id)
    if claim and job['status']!='ready_to_claim':
        raise ActionRejected('guild_job_not_ready')
    if not claim and job['status']!='active':
        raise ActionRejected('guild_claim_only')
    plan=json.loads(job['plan_json'])
    refund=plan['cost'] if not claim and job['stage_cursor']==0 else 0
    gold=plan['wage'] if claim else refund
    granted=[]
    if claim and plan['result_qty']:
        from game.gear_instances import grant_item_to_player
        require_item_delivery(grant_item_to_player(player_id,plan['result_item_id'],plan['result_qty'],
                              source='personal_processing',conn=conn),plan['result_qty'])
        granted=[{'item_id':plan['result_item_id'],'quantity':plan['result_qty']}]
    conn.execute('UPDATE players SET gold=gold+? WHERE telegram_id=?',(gold,player_id))
    conn.execute("UPDATE guild_escrow SET status='closed' WHERE context_kind='job' AND context_id=?",(job_id,))
    result={'status':'claimed' if claim else 'cancelled','action':'claim' if claim else 'cancel',
            'job_id':job_id,'gold_delta':gold,'refund':refund,'granted':granted,'completed_stages':job['stage_cursor']}
    conn.execute('UPDATE guild_job SET status=?,revision=revision+1,terminal_result_json=? WHERE job_id=?',
                 (result['status'],json.dumps(result,sort_keys=True),job_id))
    return result
