"""Typed committed facts and a durable one-time Chapter finale."""

import json
import time

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


def acknowledge_feedback(conn,player_id,event_key,*,now_ms=None):
    return conn.execute("UPDATE player_feedback_events SET state='acknowledged',acknowledged_ms=? WHERE player_id=? AND event_key=? AND state<>'acknowledged'",
        (int(time.time()*1000) if now_ms is None else now_ms,player_id,event_key)).rowcount==1


def render_feedback(events,lang):
    from telegram import InlineKeyboardButton,InlineKeyboardMarkup
    finale = next((e for e in events if e['event_kind']=='chapter_finale'),None)
    if finale:
        text = t('pxe1.finale',lang)+'\n\n'+t('chapter.epilogue',lang)
        buttons = [[InlineKeyboardButton(t('rav1.nav.opportunities',lang),callback_data='px:finale:opportunities'),
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
            lines.append(t('pxe1.objective_feedback',lang,name=name,done=payload['progress'],required=payload['required']))
        elif kind=='ready':
            lines.append(t('pxe1.assignment_ready',lang))
        elif kind=='level_up':
            lines.append(t('pxe1.profession_level',lang,name=t('professions.names.'+payload['profession_key'],lang),level=payload['new_level'])
                         if payload.get('profession_key') else t('pxe1.character_level',lang,level=payload['new_level']))
        elif kind=='claim':
            lines.append(t('pxe1.assignment_claimed',lang,gold=payload['reward_gold'],xp=payload['reward_exp']))
        elif kind=='recovery':
            lines.append(t('pxe1.recovery',lang))
    return '\n'.join(lines),InlineKeyboardMarkup([[InlineKeyboardButton(t('chapter.journal',lang),callback_data='alpha_home')]])


def inline_feedback(player_id,lang,text):
    """Read committed facts for an action card. Acknowledge only after transport."""
    conn = get_connection()
    try:
        events = [dict(r) for r in conn.execute("SELECT * FROM player_feedback_events WHERE player_id=? AND state='pending' AND event_kind<>'chapter_finale' ORDER BY created_ms,event_key",(player_id,))]
    finally:
        conn.close()
    latest = {}
    for event in events:
        payload = json.loads(event['payload_json'])
        key = (event['source_kind'],payload.get('contract_key'),payload.get('objective_key'),payload.get('profession_key'))
        latest[key] = event
    ranked = sorted(latest.values(),key=lambda e: (e['event_kind'] in {'ready','level_up','recovery'},e['created_ms'],e['event_key']))
    room = max(0,10-len(text.splitlines()))
    selected = ranked[-min(2,room):] if room else []
    rendered, _ = render_feedback(selected,lang)
    if rendered and len((text+'\n'+rendered).encode('utf-16-le'))//2<=900:
        text += '\n'+rendered
    elif selected:
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
    selected = finales[:1] or events
    text,keyboard = render_feedback(selected,get_player_lang(player_id))
    if not text:
        return False
    prior_finale = next((event for event in selected if event['state']=='presented' and event.get('message_id')),None)
    if prior_finale:
        try:
            await bot.edit_message_text(text,chat_id=prior_finale['chat_id'],message_id=prior_finale['message_id'],reply_markup=keyboard,parse_mode='HTML')
        except Exception as exc:
            from telegram.error import BadRequest
            if not isinstance(exc,BadRequest) or 'not modified' not in str(exc).lower():
                raise
        return True
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
        for event in (events if finales else selected):
            conn.execute("UPDATE player_feedback_events SET state=?,chat_id=?,message_id=?,presented_ms=? WHERE player_id=? AND event_key=? AND state='pending'",
                ('presented' if event['event_kind']=='chapter_finale' else 'acknowledged',chat_id,message_id,int(time.time()*1000),player_id,event['event_key']))
        conn.commit()
    finally:
        conn.close()
    return True
