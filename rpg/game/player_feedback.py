"""Typed committed facts and a durable one-time Chapter finale."""

import json
import time
from html import escape

from database import get_connection
from game.i18n import get_item_name,get_mob_name,get_player_lang,t

KINDS = {'progress','objective_complete','ready','claim','level_up','chapter_finale','recovery'}


def record_feedback(conn,player_id,*,event_key,source_kind,source_id,event_kind,payload,now_ms=None):
    if event_kind not in KINDS or not isinstance(payload,dict):
        raise ValueError('invalid_feedback_fact')
    if not conn.in_transaction:
        raise RuntimeError('feedback requires the action transaction')
    conn.execute('''INSERT OR IGNORE INTO player_feedback_events
        (player_id,event_key,schema_version,source_kind,source_id,event_kind,payload_json,state,created_ms)
        VALUES (?,?,1,?,?,?,?,'pending',?)''',(player_id,event_key,source_kind,str(source_id),event_kind,
            json.dumps(payload,ensure_ascii=False,sort_keys=True),int(time.time()*1000) if now_ms is None else now_ms))


def record_progression(conn,player_id,profession,progression,source_id):
    if progression.new_level>progression.old_level:
        record_feedback(conn,player_id,event_key=f'profession_level:{profession}:{progression.new_level}',
            source_kind='profession',source_id=source_id,event_kind='level_up',
            payload={'profession_key':profession,'old_level':progression.old_level,'new_level':progression.new_level})


def record_combat_result(conn,player_id,*,domain,ref,phase,now_ms=None):
    """Delivery fact only: the existing immutable combat receipt owns effects."""
    record_feedback(conn,player_id,event_key=f'combat_result:{domain}:{ref}:{phase}',source_kind='combat_result',
        source_id=ref,event_kind='recovery',payload={'domain':domain,'phase':phase},now_ms=now_ms)


def acknowledge_feedback(conn,player_id,event_key,*,now_ms=None):
    return conn.execute("UPDATE player_feedback_events SET state='acknowledged',acknowledged_ms=? WHERE player_id=? AND event_key=? AND state<>'acknowledged'",
        (int(time.time()*1000) if now_ms is None else now_ms,player_id,event_key)).rowcount==1


def render_claim_feedback(payload,lang):
    """Only the committed snapshot supplies rewards; old payloads stay readable."""
    lines = [t('pxe1.quest.claimed',lang,gold=payload['reward_gold'],xp=payload['reward_exp'])]
    bonus = payload.get('bonus_item') or {}
    if bonus.get('granted'):
        lines.append(t('location.quest_board_claim_bonus_item',lang,qty=bonus['quantity'],
                       item=escape(get_item_name(bonus['item_id'],lang))))
    hunter = payload.get('hunter_progress')
    if hunter is not None:
        lines.append(t('location.quest_board_claim_hunter_points',lang,points=hunter['points_gained']))
        if hunter.get('rank_up'):
            lines.append(t('location.quest_board_claim_rank_up',lang,rank=t('location.hunter_rank_'+hunter['rank_after'],lang)))
    if payload.get('leveled_up'):
        lines.append(t('pxe1.character_level',lang,level=payload['new_level']))
    return '\n'.join(lines)


def claim_feedback_event(player_id,action_token):
    conn = get_connection()
    try:
        row = conn.execute("""SELECT * FROM player_feedback_events WHERE player_id=?
            AND source_kind='chapter_claim' AND event_kind='claim'
            AND json_extract(payload_json,'$.action_token')=?""",(player_id,action_token)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def claim_feedback_keys(conn,player_id,event):
    contract = event['source_id']
    return [row['event_key'] for row in conn.execute("""SELECT event_key FROM player_feedback_events
        WHERE player_id=? AND state='pending' AND source_id=? AND created_ms<=? AND (
            (source_kind IN ('chapter','chapter_claim','chapter_objective')
             AND event_kind IN ('progress','objective_complete','ready'))
            OR (event_kind='claim' AND event_key=?) OR (source_kind='character' AND event_kind='level_up'))""",
            (player_id,contract,event['created_ms'],event['event_key']))]


def _remember_feedback_message(player_id,event_key,chat_id,message_id):
    if not message_id:
        return
    conn = get_connection()
    try:
        conn.execute("""UPDATE player_feedback_events SET chat_id=?,message_id=?
            WHERE player_id=? AND event_key=? AND state IN ('pending','presented')""",(chat_id,message_id,player_id,event_key))
        conn.commit()
    finally:
        conn.close()


async def _present_feedback_card(bot,player_id,event,text,keyboard,originating_query=None):
    """Retry known cards; only a confirmed missing/uneditable card is replaced."""
    from telegram.error import BadRequest
    chat_id,message_id = event.get('chat_id') or player_id,event.get('message_id')
    if originating_query:
        original = getattr(originating_query,'message',None)
        if original:
            chat_id,message_id = original.chat_id,original.message_id
            # Bind the known card before transport, without acknowledging facts.
            _remember_feedback_message(player_id,event['event_key'],chat_id,message_id)
    try:
        if originating_query:
            await originating_query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
        elif message_id:
            await bot.edit_message_text(text,chat_id=chat_id,message_id=message_id,reply_markup=keyboard,parse_mode='HTML')
        else:
            message = await bot.send_message(player_id,text,reply_markup=keyboard,parse_mode='HTML')
            chat_id,message_id = player_id,message.message_id
    except BadRequest as exc:
        reason = str(exc).lower()
        if 'not modified' in reason:
            pass  # The complete requested card is already visible.
        elif any(part in reason for part in ('message to edit not found',"message can't be edited")):
            message = await bot.send_message(player_id,text,reply_markup=keyboard,parse_mode='HTML')
            chat_id,message_id = player_id,message.message_id
        else:
            raise
    # Retain replacement coordinates even if the subsequent acknowledgement fails.
    _remember_feedback_message(player_id,event['event_key'],chat_id,message_id)
    return chat_id,message_id


async def present_claim_feedback(bot,player_id,event,*,originating_query=None):
    if event['state']!='pending':
        return False
    from telegram import InlineKeyboardButton,InlineKeyboardMarkup
    from game.player_ui import validate_surface
    lang = get_player_lang(player_id)
    text = render_claim_feedback(json.loads(event['payload_json']),lang)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t('pxe1.open_assignment',lang),callback_data='alpha_assignment')],
        [InlineKeyboardButton(t('location.quests_btn',lang),callback_data='quest_board'),
         InlineKeyboardButton(t('chapter.journal',lang),callback_data='alpha_home')],
    ])
    validate_surface(text,keyboard)
    conn = get_connection()
    try:
        keys = claim_feedback_keys(conn,player_id,event)
    finally:
        conn.close()
    await _present_feedback_card(bot,player_id,event,text,keyboard,originating_query)
    acknowledge_presented_facts(player_id,keys)
    return True


def render_feedback(events,lang):
    from telegram import InlineKeyboardButton,InlineKeyboardMarkup
    finale = next((e for e in events if e['event_kind']=='chapter_finale'),None)
    if finale:
        text = t('pxe1.chapter.complete',lang)+'\n\n'+t('pxe1.chapter.epilogue_intro',lang)
        buttons = [[InlineKeyboardButton(t('pxe1.journal.opportunities',lang),callback_data='px:finale:opportunities'),
                    InlineKeyboardButton(t('keyboard.map',lang),callback_data='px:finale:map')],
                   [InlineKeyboardButton(t('chapter.journal',lang),callback_data='px:finale:journal'),
                    InlineKeyboardButton(t('location.quests_btn',lang),callback_data='px:finale:local')]]
        return text,InlineKeyboardMarkup(buttons)
    lines = []
    for event in events[-3:]:
        payload = json.loads(event['payload_json'])
        kind = event['event_kind']
        if kind in {'progress','objective_complete'}:
            name = (get_mob_name(payload['target'],lang) if payload.get('action')=='kill'
                    else get_item_name(payload['target'],lang) if payload.get('target')!='*' else t('chapter.journal',lang))
            lines.append(t('pxe1.quest.progress',lang,name=name,done=payload['progress'],required=payload['required']))
        elif kind=='ready':
            lines.append(t('pxe1.quest.ready',lang))
        elif kind=='level_up':
            lines.append(t('pxe1.profession_level',lang,name=t('professions.names.'+payload['profession_key'],lang),level=payload['new_level'])
                         if payload.get('profession_key') else t('pxe1.character_level',lang,level=payload['new_level']))
        elif kind=='claim':
            lines.append(render_claim_feedback(payload,lang))
        elif kind=='recovery':
            key={'reinvite_required':'pxe1.encounter.pvp_reinvite_required','cancelled':'pxe1.encounter.pvp_cancelled',
                 'start_failed':'pxe1.encounter.start_failed','escaped':'pxe1.encounter.pvp_escape_success',
                 'restart':'pxe1.gather.restart_stopped' if event['source_kind']=='gather_session' else 'pxe1.recovery'}.get(payload.get('reason'),'pxe1.recovery')
            lines.append(t(key,lang))
    return '\n'.join(lines),InlineKeyboardMarkup([[InlineKeyboardButton(t('chapter.journal',lang),callback_data='alpha_home')]])


def inline_feedback(player_id,lang,text):
    """Read committed facts for an action card. Acknowledge only after transport."""
    conn = get_connection()
    try:
        events = [dict(r) for r in conn.execute("SELECT * FROM player_feedback_events WHERE player_id=? AND state='pending' AND event_kind NOT IN ('chapter_finale','claim') AND source_kind<>'combat_result' ORDER BY created_ms,event_key",(player_id,))]
        pending_claims = {r['source_id'] for r in conn.execute("SELECT source_id FROM player_feedback_events WHERE player_id=? AND event_kind='claim' AND state='pending'",(player_id,))}
    finally:
        conn.close()
    events = [event for event in events if not (event['source_id'] in pending_claims
        and event['source_kind'] in {'chapter','chapter_objective','character'})]
    latest = {}
    for event in events:
        payload = json.loads(event['payload_json'])
        key = (event['source_kind'],payload.get('contract_key'),payload.get('objective_key'),payload.get('profession_key'))
        latest[key] = event
    ranked = sorted(latest.values(),key=lambda e: (e['event_kind'] in {'ready','level_up','recovery'},e['created_ms'],e['event_key']))
    room = max(0,10-len(text.splitlines()))
    selected = ranked[-min(2,room):] if room else []
    rendered, _ = render_feedback(selected,lang)
    # The action result may already contain the same committed fact (level-up,
    # claim). It still needs acknowledgement after successful delivery.
    existing_lines = set(text.splitlines())
    rendered = '\n'.join(line for line in rendered.splitlines() if line not in existing_lines)
    if rendered:
        if len((text+'\n'+rendered).encode('utf-16-le'))//2<=900:
            text += '\n'+rendered
        else:
            selected = []
    # Facts coalesce into one result, but an overflowing fact stays recoverable.
    selected_keys = {e['event_key'] for e in selected}
    represented = {key for key,event in latest.items() if event['event_key'] in selected_keys}
    keys = [e['event_key'] for e in events if (e['source_kind'],json.loads(e['payload_json']).get('contract_key'),
        json.loads(e['payload_json']).get('objective_key'),json.loads(e['payload_json']).get('profession_key')) in represented]
    return text, keys


def acknowledge_presented_facts(player_id,keys):
    if not keys:
        return
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        for key in keys:
            acknowledge_feedback(conn,player_id,key)
        conn.commit()
    finally:
        conn.close()


async def present_pending_feedback(bot,player_id,*,recover_presented=False,originating_query=None):
    conn = get_connection()
    try:
        events = [dict(r) for r in conn.execute("SELECT * FROM player_feedback_events WHERE player_id=? AND (state='pending' OR (? AND state='presented' AND event_kind='chapter_finale')) ORDER BY created_ms,event_key",(player_id,recover_presented))]
    finally:
        conn.close()
    if not events:
        return False
    finales = [event for event in events if event['event_kind']=='chapter_finale']
    claims = [event for event in events if event['event_kind']=='claim']
    if not finales and claims:
        return await present_claim_feedback(bot,player_id,claims[0],originating_query=originating_query)
    if not finales and any(event['source_kind']=='combat_result' for event in events):
        from handlers.combat_results import deliver_pending_results
        return await deliver_pending_results(bot,player_id=player_id)
    events=[event for event in events if event['source_kind']!='combat_result']
    selected = finales[:1] or events
    text,keyboard = render_feedback(selected,get_player_lang(player_id))
    if finales:
        finale = finales[0]
        conn = get_connection()
        try:
            claim = conn.execute("SELECT * FROM player_feedback_events WHERE player_id=? AND source_id=? AND event_kind='claim' ORDER BY created_ms DESC,event_key DESC LIMIT 1",
                                 (player_id,finale['source_id'])).fetchone()
            keys = claim_feedback_keys(conn,player_id,dict(claim) if claim else finale)
        finally:
            conn.close()
        if claim:
            text += '\n\n'+render_claim_feedback(json.loads(claim['payload_json']),get_player_lang(player_id))
        chat_id,message_id = await _present_feedback_card(bot,player_id,finale,text,keyboard,originating_query)
        acknowledge_presented_facts(player_id,keys)
        conn = get_connection()
        try:
            conn.execute("""UPDATE player_feedback_events SET state='presented',chat_id=?,message_id=?,presented_ms=?
                WHERE player_id=? AND event_key=? AND state='pending'""",(chat_id,message_id,int(time.time()*1000),player_id,finale['event_key']))
            conn.commit()
        finally:
            conn.close()
        return True
    if not text:
        return False
    if originating_query:
        message = await originating_query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
        chat_id = originating_query.message.chat_id
        message_id = originating_query.message.message_id
    else:
        message = await bot.send_message(player_id,text,reply_markup=keyboard,parse_mode='HTML')
        chat_id, message_id = player_id, message.message_id
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        for event in selected:
            conn.execute("UPDATE player_feedback_events SET state=?,chat_id=?,message_id=?,presented_ms=? WHERE player_id=? AND event_key=? AND state='pending'",
                ('presented' if event['event_kind']=='chapter_finale' else 'acknowledged',chat_id,message_id,int(time.time()*1000),player_id,event['event_key']))
        conn.commit()
    finally:
        conn.close()
    return True
