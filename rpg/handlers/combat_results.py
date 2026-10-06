"""Retry personal result delivery from existing committed combat receipts."""

import json,logging,time
from collections import Counter
from html import escape

from telegram import InlineKeyboardButton,InlineKeyboardMarkup
from database import get_connection,get_player
from game.i18n import t,get_item_name,get_location_name
from game.player_ui import present_surface,validate_surface
from game.action_receipts import issue_actions,ActionRejected

logger=logging.getLogger(__name__)


def result_card(event,player,*,details=False,page=0):
    payload=json.loads(event['payload_json']);domain=payload['domain'];phase=payload['phase']
    ref=event['source_id'];player_id=player['telegram_id'];lang=player.get('lang','ru')
    conn=get_connection()
    try:
        if domain=='pve':
            from handlers.combat_delivery import pve_result
            row=conn.execute('SELECT * FROM pve_encounters WHERE encounter_id=?',(ref,)).fetchone()
            member=conn.execute('SELECT * FROM pve_encounter_participants WHERE encounter_id=? AND player_id=?',(ref,player_id)).fetchone()
            death=conn.execute('SELECT result_json FROM economy_action_receipts WHERE player_id=? AND request_id=?',(player_id,f'pve_death:{ref}:{player_id}')).fetchone()
            settled=conn.execute("SELECT result_json FROM pve_reward_settlements WHERE encounter_id=? AND status='applied'",(ref,)).fetchone()
            if not row or not member: raise ActionRejected('result_missing')
            card=pve_result(player,row,member,json.loads(death[0]) if death else None,json.loads(settled[0]) if settled else None)
            if not card: raise ActionRejected('result_missing')
            return card
        if domain!='pvp': raise ActionRejected('result_missing')
        row=conn.execute('SELECT * FROM pvp_engagements WHERE id=? AND world_model_version=1',(ref,)).fetchone()
        if not row: raise ActionRejected('result_missing')
        from game.pvp_group_runtime import locked_sides
        sides=locked_sides(row)
        if player_id not in sides['side_a']+sides['side_b']: raise ActionRejected('not_participant')
        context=json.loads(row['reason_context']);battle=context['battle']
        deaths=[json.loads(r[0]) for r in conn.execute('SELECT result_json FROM pvp_participant_settlements_pxe1 WHERE engagement_id=?',(ref,))]
        death=next((d for d in deaths if d['player_id']==player_id),None)
        group=conn.execute('SELECT result_json FROM pvp_group_settlements_pxe1 WHERE engagement_id=?',(ref,)).fetchone()
        group=json.loads(group[0]) if group else None
        if phase=='death' and not death or phase=='terminal' and not group: raise ActionRejected('result_missing')
    finally: conn.close()
    actor=battle['participants_v1'][str(player_id)]
    own_side='side_a' if player_id in sides['side_a'] else 'side_b'
    items=Counter(death['loss_pool']) if death else Counter()
    if death:
        lines=[t('location.pvp_personal_death',lang,hub=get_location_name(death['respawn_hub'],lang),
            quantity=sum(items.values()),hp=death['hp_after'],mana=death['mana_after'])]
    else:
        for grant in group['grants']:
            if grant['recipient_id']==player_id: items[grant['item_id']]+=grant['quantity']
        lines=[t('pxe1.result.draw' if group['winner_side'] is None else 'pxe1.result.victory' if group['winner_side']==own_side else 'location.pvp_battle_finished',lang),
            t('location.pvp_personal_result',lang,hp=actor['hp'],mana=actor['mana'],quantity=sum(items.values()))]
    given=sum(int(sources.get(str(player_id),0)) for sources in battle.get('damage_by_source',{}).values())
    taken=sum(int(n) for n in battle.get('damage_by_source',{}).get(str(player_id),{}).values())
    infamy=int(context.get('crime_context',{}).get(str(player_id),{}).get('initiation_infamy',0))
    infamy+=sum(int(d['infamy_delta']) for d in deaths if d['credited_actor_id']==player_id)
    if death:
        given=death.get('damage_dealt',given);taken=death.get('damage_taken',taken)
        infamy=death.get('personal_infamy_delta',infamy)
    lines += [t('pxe1.result.damage',lang,given=given,taken=taken),t('pxe1.result.infamy',lang,delta=infamy)]
    item_lines=[escape(get_item_name(item,lang))+f' ×{quantity}' for item,quantity in sorted(items.items())]
    if item_lines: lines.append(t('pxe1.result.lost' if death else 'pxe1.result.received',lang))
    definitions=[]
    if details:
        pages=max(1,(len(item_lines)+5)//6);page=max(0,min(int(page),pages-1))
        lines+=item_lines[page*6:page*6+6]
        lines.append(t('gear.page',lang,page=page+1,pages=pages))
        if page: definitions.append(('◀️',{'details':True,'page':page-1}))
        if page+1<pages: definitions.append(('▶️',{'details':True,'page':page+1}))
        definitions.append((t('common.back',lang),{'details':False}))
    else:
        lines+=item_lines[:3]
        definitions.append((t('pxe1.details',lang),{'details':True,'page':0}))
    intents=[json.dumps({'schema_version':1,'event_key':event['event_key'],**data},sort_keys=True) for _,data in definitions]
    tokens=issue_actions(player_id,'pxe1_combat_result',intents)
    rows=[[InlineKeyboardButton(label,callback_data='pvp_result_'+tokens[intent])] for (label,_),intent in zip(definitions,intents)]
    rows.append([InlineKeyboardButton(t('keyboard.location',lang),callback_data='px:local:home:0'),
                 InlineKeyboardButton(t('keyboard.inventory',lang),callback_data='inv_tab_all')])
    text='\n'.join(lines);keyboard=InlineKeyboardMarkup(rows)
    validate_surface(text,keyboard,long_detail=details)
    return text,keyboard


async def deliver_pending_results(bot,*,player_id=None,domain=None,limit=100):
    from game.player_feedback import inline_feedback,acknowledge_presented_facts
    conn=get_connection()
    try:
        events=[dict(r) for r in conn.execute("""SELECT * FROM player_feedback_events WHERE source_kind='combat_result'
            AND state='pending' AND (? IS NULL OR player_id=?) AND (? IS NULL OR event_key LIKE ?)
            ORDER BY created_ms,event_key LIMIT ?""",(player_id,player_id,domain,f'combat_result:{domain}:%',limit))]
    finally: conn.close()
    delivered=False
    for event in events:
        try:
            payload=json.loads(event['payload_json'])
            from game.player_ui import _row
            prior=_row(event['player_id']) or {}
            kind=payload['domain']+'_result';revision=1 if payload['phase']=='death' else 2
            if prior.get('surface_kind')==kind and prior.get('surface_ref')==event['source_id'] and prior.get('surface_revision')==revision and prior.get('message_id'):
                acknowledge_presented_facts(event['player_id'],[event['event_key']])
                delivered=True;continue
            player=dict(get_player(event['player_id']))
            text,keyboard=result_card(event,player)
            text,keys=inline_feedback(player['telegram_id'],player.get('lang','ru'),text)
            await present_surface(bot,player['telegram_id'],text,keyboard,kind=kind,ref=event['source_id'],revision=revision)
            acknowledge_presented_facts(player['telegram_id'],[event['event_key'],*keys])
            delivered=True
        except Exception:
            logger.exception('Personal combat result delivery retry: player %s',event['player_id'])
    return delivered


async def handle_result_details(update,context):
    query=update.callback_query;player=dict(get_player(query.from_user.id))
    conn=get_connection()
    try:
        row=conn.execute("SELECT payload FROM player_ui_actions WHERE token=? AND player_id=? AND kind='pxe1_combat_result' AND expires_at>=?",
            (query.data.removeprefix('pvp_result_'),player['telegram_id'],int(time.time()))).fetchone()
        intent=json.loads(row[0]) if row else {}
        event=conn.execute("SELECT * FROM player_feedback_events WHERE event_key=? AND player_id=? AND source_kind='combat_result'",(intent.get('event_key'),player['telegram_id'])).fetchone()
    finally: conn.close()
    if not event or intent.get('schema_version')!=1:
        await query.answer(t('chapter.stale_action',player.get('lang','ru')),show_alert=True);return
    text,keyboard=result_card(event,player,details=intent.get('details',False),page=intent.get('page',0))
    await query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
    await query.answer()
