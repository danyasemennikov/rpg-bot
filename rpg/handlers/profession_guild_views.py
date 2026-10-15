"""Guild UI carries server-persisted intents; callbacks never choose output modes."""
import json
import time
from html import escape
from telegram import InlineKeyboardButton as Button,InlineKeyboardMarkup
from database import get_connection,get_player
from game.action_receipts import ActionRejected,issue_actions,consume_action
from game.economy_actions import intent_hash,store_receipt
from game.i18n import t,get_item_name
from game.profession_schema import GATHERING_PROFESSION_KEYS
from game.profession_state import get_state,register_profession
from game.profession_recipes import ACTIVE_RECIPES,GATHERING_MANUALS,get_recipe
from game.profession_resources import RESOURCES
from game.profession_progression import profession_exp_needed,personal_batch_limit,processing_duration_ms
from game.recipe_knowledge import known_recipe_ids,knowledge_spec,learn_knowledge
from game.profession_guild import accept_job,complete_stage,finish_job,get_job,MILESTONE_JOBS
from game.profession_exams import register_exam,perform_exam_action,confirm_exam,get_exam,CRITERIA


def knowledge_name(knowledge_id,lang):
    if knowledge_id in GATHERING_MANUALS:
        manual=GATHERING_MANUALS[knowledge_id]
        return t('epic_i.manual_'+manual['technique'],lang)+' · '+t('epic_i.tier',lang,tier=manual['tier'])
    recipe=get_recipe(knowledge_id)
    if recipe:
        from handlers.professions import _recipe_name
        return _recipe_name(recipe,lang)
    return get_item_name(knowledge_id,lang)


def _intent_buttons(player_id,entries):
    payloads=[json.dumps(payload,sort_keys=True,separators=(',',':')) for label,payload in entries]
    tokens=issue_actions(player_id,'epic_i',payloads)
    return [[Button(label,callback_data='ei:a:'+tokens[payload])] for (label,_),payload in zip(entries,payloads)]


def _view(lines,rows):
    return '\n'.join(lines),InlineKeyboardMarkup(rows)


def _back(key,lang):
    return [Button(t('common.back',lang),callback_data='pe_p:'+key)]


def _paginate(values,page,prefix,lang):
    page=min(max(int(page),0),max(0,(len(values)-1)//6))
    rows=[]
    if page:
        rows.append(Button('◀️',callback_data=f'{prefix}:{page-1}'))
    if (page+1)*6<len(values):
        rows.append(Button('▶️',callback_data=f'{prefix}:{page+1}'))
    return values[page*6:(page+1)*6],([rows] if rows else [])


def profession_home(player,key):
    player_id,lang=player['telegram_id'],player.get('lang','ru')
    conn=get_connection()
    try:
        from game.profession_schema import ensure_profession_rows
        conn.execute('BEGIN IMMEDIATE');ensure_profession_rows(conn,player_id);conn.commit()
        state=get_state(conn,player_id,key)
        active=conn.execute("SELECT job_id FROM guild_job WHERE player_id=? AND status IN ('active','ready_to_claim')",(player_id,)).fetchone()
        certified=conn.execute("SELECT 1 FROM profession_exam WHERE player_id=? AND profession_key=? AND status='confirmed'",(player_id,key)).fetchone()
    finally:conn.close()
    name=t('professions.names.'+key,lang)
    lines=[f'<b>{escape(name)}</b>']
    if state['registered_at'] is None:
        lines.append(t('epic_i.unregistered',lang))
        rows=_intent_buttons(player_id,[(t('epic_i.register',lang),{'op':'register','profession':key})])
    else:
        needed='—' if state['level'] in (15,30) else profession_exp_needed(state['level'])
        lines.append(t('epic_i.status',lang,tier=state['tier'],level=state['level'],xp=state['exp'],needed=needed))
        if state['level'] in (15,30):lines.append(t('epic_i.halt',lang))
        lines.append(t('epic_i.perks',lang,batch=personal_batch_limit(state['level']),seconds=processing_duration_ms(state['level'])//1000))
        if certified:lines.append(t('epic_i.certificate',lang,profession=name))
        rows=[[Button(t('epic_i.learn',lang),callback_data=f'ei:k:{key}:0')],
              [Button(t('epic_i.work',lang),callback_data=f'ei:w:{key}:0')]]
        if key in GATHERING_PROFESSION_KEYS:
            rows+=[[Button(t('epic_i.processing',lang),callback_data=f'ei:p:{key}:0')],
                   [Button(t('epic_i.tools',lang),callback_data=f'ei:tools:{key}')]]
        else:
            rows.append([Button(t('professions.known',lang),callback_data=f'pe_l:{key}:known:0')])
        if state['level']==15:
            rows.append([Button(t('epic_i.exam',lang),callback_data='ei:e:'+key+':0')])
        rows.append([Button(t('epic_i.supply',lang),callback_data=f'ei:s:{key}:0')])
    if active:rows.insert(0,[Button(t('epic_i.active',lang),callback_data='ei:job:'+active['job_id'])])
    rows.append([Button(t('common.back',lang),callback_data='pe_o:0')])
    return _view(lines,rows)


def knowledge_view(player,key,page=0):
    pid,lang=player['telegram_id'],player.get('lang','ru')
    conn=get_connection()
    try:
        state=get_state(conn,pid,key,registered=True)
        known=set(known_recipe_ids(pid,conn=conn))
        voucher=conn.execute('SELECT COUNT(*) FROM profession_vouchers WHERE player_id=? AND profession_key=? AND knowledge_id IS NULL',(pid,key)).fetchone()[0]
    finally:conn.close()
    choices=[r.recipe_id for r in ACTIVE_RECIPES if r.profession_key==key and r.tier<=state['tier']]
    choices+=[k for k,v in GATHERING_MANUALS.items() if v['profession_key']==key and v['tier']<=state['tier']]
    choices=[k for k in choices if k not in known]
    selected,nav=_paginate(choices,page,'ei:k:'+key,lang)
    entries=[]
    for choice in selected:
        spec=knowledge_spec(choice)
        price=0 if voucher and spec['tier']==1 else spec['learning_gold']
        entries.append((t('epic_i.learn_price',lang,name=knowledge_name(choice,lang),price=price),
                        {'op':'learn','profession':key,'knowledge_id':choice}))
    return _view([t('epic_i.learn',lang)] if choices else [t('epic_i.empty',lang)],
                 _intent_buttons(pid,entries)+nav+[_back(key,lang)])


def work_picker(player,key,page=0,*,processing=False):
    pid,lang=player['telegram_id'],player.get('lang','ru')
    conn=get_connection()
    try:
        state=get_state(conn,pid,key,registered=True)
        known=set(known_recipe_ids(pid,conn=conn))
    finally:conn.close()
    gathering=key in GATHERING_PROFESSION_KEYS
    if gathering:
        tiers={v['tier'] for k,v in GATHERING_MANUALS.items() if v['profession_key']==key and k in known}
        sources=[r.item_id for r in RESOURCES.values() if r.profession_key==key and r.resource_tier<=state['tier'] and r.resource_tier in tiers]
    else:
        sources=[r.recipe_id for r in ACTIVE_RECIPES if r.profession_key==key and r.tier<=state['tier'] and r.recipe_id in known]
    entries=[(knowledge_name(source,lang),'ei:q:'+('personal_processing' if processing else 'paid_job')+':'+source) for source in sources]
    if not processing:
        for job in MILESTONE_JOBS.values():
            if job['profession_key']==key and state['level']>=job['unlock_P'] and (gathering or set(job['sources'])<=known):
                entries.append((' → '.join(knowledge_name(source,lang) for source in job['sources']),'ei:theme:'+job['job_key']))
    selected,nav=_paginate(entries,page,f"ei:{'p' if processing else 'w'}:{key}",lang)
    return _view([t('epic_i.processing' if processing else 'epic_i.work',lang)] if entries else [t('epic_i.empty',lang)],
                 [[Button(label,callback_data=callback)] for label,callback in selected]+nav+[_back(key,lang)])


def work_quote(player,*,mode='paid_job',source=None,job_key=None):
    pid,lang=player['telegram_id'],player.get('lang','ru')
    key=MILESTONE_JOBS[job_key]['profession_key'] if job_key else RESOURCES[source].profession_key if source in RESOURCES else get_recipe(source).profession_key
    conn=get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        job=accept_job(conn,pid,key,mode=mode,source_id=source,job_key=job_key,request_id='preview',now_ms=0)
        plan=json.loads(job['plan_json'])
        name=' → '.join(knowledge_name(stage_source,lang) for stage_source in (MILESTONE_JOBS[job_key]['sources'] if job_key else [source]))
    finally:conn.rollback();conn.close()
    if mode=='paid_job':
        text=t('epic_i.job_quote',lang,name=escape(name),stages=len(plan['stages']),seconds=plan['total_duration_ms']//1000,wage=plan['wage'])
    else:
        text=t('epic_i.processing_quote',lang,name=escape(name),qty=plan['result_qty'],cost=plan['cost'],seconds=plan['total_duration_ms']//1000)
    rows=_intent_buttons(pid,[(t('epic_i.accept',lang),{'op':'accept','profession':key,'mode':mode,'source_id':source,
                        'job_key':job_key,'fingerprint':job['fingerprint']})])
    return _view([text],rows+[_back(key,lang)])


def job_view(player,job_id,*,cancel=False):
    pid,lang=player['telegram_id'],player.get('lang','ru')
    conn=get_connection()
    try:job=get_job(conn,pid,job_id)
    finally:conn.close()
    plan=json.loads(job['plan_json']);key=job['profession_key'];cursor=job['stage_cursor']
    payload={'profession':key,'job_id':job_id,'revision':job['revision']}
    if cancel:
        refund=plan['cost'] if cursor==0 else 0
        return _view([t('epic_i.cancel_warning',lang,refund=refund)],_intent_buttons(pid,[(t('common.confirm',lang),
            {**payload,'op':'finish','claim':False})])+[[Button(t('common.back',lang),callback_data='ei:job:'+job_id)]])
    if job['status'] not in ('active','ready_to_claim'):
        return profession_home(player,key)
    rows=[]
    lines=[t('epic_i.active',lang)]
    if job['status']=='ready_to_claim':
        rows=_intent_buttons(pid,[(t('epic_i.claim',lang),{**payload,'op':'finish','claim':True})])
    else:
        seconds=max(0,(job['next_stage_earliest_ms']-int(time.time()*1000)+999)//1000)
        lines.append(t('epic_i.stage',lang,current=cursor+1,total=len(plan['stages']),name=knowledge_name(plan['stages'][cursor]['source_id'],lang),seconds=seconds))
        if seconds==0:
            rows=_intent_buttons(pid,[(t('epic_i.perform',lang),{**payload,'op':'stage','stage_index':cursor})])
        rows+=[[Button(t('epic_i.refresh',lang),callback_data='ei:job:'+job_id)],
               [Button(t('epic_i.cancel',lang),callback_data='ei:cancel:'+job_id)]]
    return _view(lines,rows+[_back(key,lang)])


def exam_view(player,key,page=0):
    pid,lang=player['telegram_id'],player.get('lang','ru')
    conn=get_connection()
    try:
        state=get_state(conn,pid,key,registered=True)
        row=conn.execute('SELECT * FROM profession_exam WHERE player_id=? AND profession_key=?',(pid,key)).fetchone()
        exam=dict(row) if row else None
        proofs={r['criterion'] for r in conn.execute('SELECT criterion FROM profession_exam_proof WHERE exam_id=?',(exam['exam_id'],))} if exam else set()
        known=set(known_recipe_ids(pid,conn=conn))
    finally:conn.close()
    lines=[t('epic_i.exam',lang),t('epic_i.exam_help',lang)]
    if state['level']!=15:return profession_home(player,key)
    if not exam:
        return _view(lines,_intent_buttons(pid,[(t('epic_i.register_exam',lang),{'op':'exam_register','profession':key})])+[_back(key,lang)])
    payload={'profession':key,'exam_id':exam['exam_id'],'revision':exam['revision']}
    if exam['status']=='sample_submitted':
        choices=[r.recipe_id for r in ACTIVE_RECIPES if r.profession_key==key and r.tier==2 and r.recipe_id not in known]
        choices+=[k for k,v in GATHERING_MANUALS.items() if v['profession_key']==key and v['tier']==2 and k not in known]
        selected,nav=_paginate(choices,page,'ei:e:'+key,lang)
        lines.append(t('epic_i.choose_reward',lang))
        entries=[(knowledge_name(choice,lang),{**payload,'op':'exam_confirm','reward':choice}) for choice in selected]
    else:
        nav=[];entries=[]
        plan=json.loads(exam['plan_json'])
        for criterion in CRITERIA:
            label=t('epic_i.'+('sample' if criterion=='sample' else 'practice_'+criterion),lang)
            lines.append(('✓ ' if criterion in proofs else '• ')+label+': '+escape(knowledge_name(plan[criterion]['source_id'],lang)))
            if criterion not in proofs and (criterion!='sample' or {'a','b'}<=proofs):
                entries.append((label,{**payload,'op':'exam_action','criterion':criterion}))
    return _view(lines,_intent_buttons(pid,entries)+nav+[_back(key,lang)])


def supply_view(player,key,page=0,*,item_id=None,quantity=1):
    pid,lang=player['telegram_id'],player.get('lang','ru')
    if item_id:
        cost=3*RESOURCES[item_id].sell_price*quantity
        payload={'op':'buy','profession':key,'item_id':item_id,'quantity':quantity,'gold':cost}
        return _view([t('epic_i.buy_quote',lang,name=get_item_name(item_id,lang),qty=quantity,gold=cost)],
            _intent_buttons(pid,[(t('common.confirm',lang),payload)])+[_back(key,lang)])
    selected,nav=_paginate(list(RESOURCES),page,'ei:s:'+key,lang)
    rows=[]
    for item in selected:
        name=get_item_name(item,lang)
        rows.append([Button(name+' ×1',callback_data=f'ei:buy:{key}:{item}:1'),
                     Button('×5',callback_data=f'ei:buy:{key}:{item}:5')])
    return _view([t('epic_i.supply',lang)],rows+nav+[_back(key,lang)])


def commission_view(player,key,*,tier=None):
    from game.profession_supply import commission_quote
    pid,lang=player['telegram_id'],player.get('lang','ru')
    conn=get_connection()
    try:
        state=get_state(conn,pid,key,registered=True)
        if key not in GATHERING_PROFESSION_KEYS:raise ActionRejected('invalid_tool')
        if tier is not None:
            recipe_id=f'pxe_tool_{key}_{tier}' if tier<=4 else f'a25_tool_{key}_{tier}'
            quote=commission_quote(conn,pid,recipe_id)
        else:
            tool=conn.execute('SELECT tier FROM player_profession_tools WHERE player_id=? AND profession_key=?',(pid,key)).fetchone()
    finally:conn.close()
    if tier is not None:
        return _view([t('epic_i.commission_quote',lang,name=knowledge_name(recipe_id,lang),gold=quote['gold'])],
            _intent_buttons(pid,[(t('common.confirm',lang),{'op':'commission','profession':key,'quote':quote})])+[_back(key,lang)])
    rows=[]
    for grade in range(1,4 if state['tier']==1 else 7):
        if tool and tool['tier']>grade:continue
        rows.append([Button('U'+str(grade),callback_data=f'ei:tool:{key}:{grade}')])
    return _view([t('epic_i.tools',lang)],rows+[_back(key,lang)])


async def handle_guild_buttons(update,context):
    query=update.callback_query
    player=dict(get_player(query.from_user.id));pid=player['telegram_id'];lang=player.get('lang','ru')
    parts=query.data.split(':');notice='';key=None
    try:
        if parts[1]=='a':
            token=parts[2];conn=get_connection()
            try:
                conn.execute('BEGIN IMMEDIATE')
                prior=conn.execute("SELECT result_json FROM economy_action_receipts WHERE player_id=? AND request_id=? AND action_kind='epic_i'",(pid,'ui:'+token)).fetchone()
                if prior:
                    result=json.loads(prior[0]);key=result['profession'];destination=result['destination']
                else:
                    payload=json.loads(consume_action(conn,pid,'epic_i',token));key=payload['profession'];op=payload['op']
                    destination='home'
                    if op=='register':outcome=register_profession(conn,pid,key)
                    elif op=='learn':outcome=learn_knowledge(conn,pid,payload['knowledge_id']);destination='knowledge'
                    elif op=='accept':
                        outcome=accept_job(conn,pid,key,mode=payload['mode'],source_id=payload['source_id'],job_key=payload['job_key'],request_id=token)
                        if outcome['fingerprint']!=payload['fingerprint']:raise ActionRejected('stale_action')
                        destination='job:'+outcome['job_id']
                    elif op=='stage':
                        outcome=complete_stage(conn,pid,payload['job_id'],stage_index=payload['stage_index'],expected_revision=payload['revision']);destination='job:'+payload['job_id']
                    elif op=='finish':outcome=finish_job(conn,pid,payload['job_id'],claim=payload['claim'],expected_revision=payload['revision'])
                    elif op=='exam_register':outcome=register_exam(conn,pid,key);destination='exam'
                    elif op=='exam_action':outcome=perform_exam_action(conn,pid,payload['exam_id'],payload['criterion'],expected_revision=payload['revision']);destination='exam'
                    elif op=='exam_confirm':outcome=confirm_exam(conn,pid,payload['exam_id'],payload['reward'],expected_revision=payload['revision'])
                    elif op=='buy':
                        from game.profession_supply import buy_material
                        outcome=buy_material(conn,pid,payload['item_id'],payload['quantity'],request_id='supply:'+token)
                        if outcome['gold_delta']!=-payload['gold']:raise ActionRejected('stale_action')
                    elif op=='commission':
                        from game.profession_supply import execute_commission
                        quote=payload['quote']
                        outcome=execute_commission(conn,pid,quote['recipe_id'],expected_revision=quote['tool_revision'],
                            confirmed=True,request_id=token,expected_quote=quote)
                    else:raise ActionRejected('stale_action')
                    after=conn.execute('SELECT location_id,gold FROM players WHERE telegram_id=?',(pid,)).fetchone()
                    delta=outcome.get('gold_delta',0)
                    if op=='accept':delta=-json.loads(outcome['plan_json'])['cost']
                    # Supply/commission already own their economic receipt; this is a UI acknowledgement.
                    effects=op not in ('buy','commission')
                    result={'schema_version':1,'catalog_version':3,'action_kind':'epic_i','status':'done',
                        'player_id':pid,'location_id':after['location_id'],'recipe_id':None,
                        'profession':key,'destination':destination,'outcome':outcome,
                        'gold_delta':delta if effects else 0,'gold_after':after['gold'],
                        'consumed':outcome.get('consumed',[]) if effects else [],
                        'granted':outcome.get('granted',[]) if effects else [],'progression':[],
                        'source':{'catalog_version':3},'details':{'operation':op}}
                    store_receipt(conn,pid,'ui:'+token,'epic_i',intent_hash('epic_i',pid,payload),result,catalog_version=3)
                conn.commit()
            except Exception:conn.rollback();raise
            finally:conn.close()
            player=dict(get_player(pid));notice=t('epic_i.done',lang)
            view=job_view(player,destination[4:]) if destination.startswith('job:') else exam_view(player,key) if destination=='exam' else knowledge_view(player,key) if destination=='knowledge' else profession_home(player,key)
        elif parts[1] in ('k','w','p','e'):
            key=parts[2];page=int(parts[3])
            view=knowledge_view(player,key,page) if parts[1]=='k' else exam_view(player,key,page) if parts[1]=='e' else work_picker(player,key,page,processing=parts[1]=='p')
        elif parts[1]=='q':view=work_quote(player,mode=parts[2],source=parts[3])
        elif parts[1]=='theme':view=work_quote(player,job_key=parts[2])
        elif parts[1]=='s':key=parts[2];view=supply_view(player,key,int(parts[3]))
        elif parts[1]=='buy':key=parts[2];view=supply_view(player,key,item_id=parts[3],quantity=int(parts[4]))
        elif parts[1]=='tools':key=parts[2];view=commission_view(player,key)
        elif parts[1]=='tool':key=parts[2];view=commission_view(player,key,tier=int(parts[3]))
        elif parts[1] in ('job','cancel'):view=job_view(player,':'.join(parts[2:]),cancel=parts[1]=='cancel')
        else:raise ActionRejected('stale_action')
    except (ActionRejected,ValueError,KeyError):
        notice=t('epic_i.changed',lang)
        from handlers.professions import build_overview
        view=profession_home(player,key) if key else build_overview(player)
    await query.answer(notice)
    await query.edit_message_text(view[0],reply_markup=view[1],parse_mode='HTML')
