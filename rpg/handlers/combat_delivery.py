"""Deliver committed shared combat through one persisted card per member."""

import json
import logging
import time
from html import escape

from telegram import InlineKeyboardButton,InlineKeyboardMarkup
from database import get_connection,get_player
from game.i18n import t,get_item_name,get_location_name
from game.player_ui import present_surface,record_surface

logger = logging.getLogger(__name__)


def formation_revision(row,now_ms):
    left = max(0,(int(row['formation_deadline_ms'])-now_ms+999)//1000)
    stage = 0 if left>8 else 1 if left>4 else 2 if left>0 else 3
    return 1_000_000_000+int(row['formation_revision'])*4+stage


def remember_pve_card(query,player_id,encounter_id):
    message = getattr(query,'message',None)
    if not message or not getattr(message,'message_id',None): return
    conn = get_connection()
    try:
        row = conn.execute('SELECT * FROM pve_encounters WHERE encounter_id=?',(encounter_id,)).fetchone()
        member = conn.execute("SELECT 1 FROM pve_encounter_participants WHERE encounter_id=? AND player_id=? AND status='active'",(encounter_id,player_id)).fetchone()
    finally: conn.close()
    if row and row['lifecycle_version']==1 and member:
        revision = formation_revision(row,int(time.time()*1000)) if row['runtime_started_ms'] is None else row['turn_revision']
        record_surface(player_id,kind='pve',ref=encounter_id,revision=revision,
                       chat_id=message.chat_id,message_id=message.message_id)


def pve_result(player,row,participant,death,settlement):
    from game.hunting import HARVEST_ITEMS
    lang = player.get('lang','ru')
    rows = [[InlineKeyboardButton(t('keyboard.location',lang),callback_data='px:local:home:0'),
             InlineKeyboardButton(t('chapter.journal',lang),callback_data='alpha_home')]]
    if death:
        penalty = death['penalty']
        lines = [t('battle.death',lang,exp_loss=penalty['exp_loss'],gold_loss=penalty['gold_loss']),
                 escape(get_location_name(player['location_id'],lang))+f" · ❤️ {player['hp']}/{player['max_hp']} · 🔵 {player['mana']}/{player['max_mana']}"]
    elif settlement:
        reward = next((r for r in settlement.get('recipients',[]) if r['player_id']==player['telegram_id']),None)
        eligible = reward is not None
        reward = reward or {'exp':0,'gold':0}
        lines = [t('pxe1.combat.victory',lang,xp=reward['exp'],gold=reward['gold'])]
        items = reward.get('stackable_items',[])+[g['base_item_id'] for g in reward.get('gear',[])]
        if items:
            from collections import Counter
            lines.append(t('battle.loot',lang,items=', '.join(escape(get_item_name(i,lang))+f' ×{n}' for i,n in list(Counter(items).items())[:3])))
            rows.append([InlineKeyboardButton(t('keyboard.inventory',lang),callback_data='inv_tab_all')])
        if reward.get('leveled_up'): lines.append(t('pxe1.character_level',lang,level=reward['new_level']))
        if eligible and player['telegram_id']==row['owner_player_id'] and row['mob_id'] in HARVEST_ITEMS:
            rows.append([InlineKeyboardButton(t('chapter.harvest',lang),callback_data='alpha_extract_'+row['encounter_id'])])
    else: return None
    return '\n'.join(lines),InlineKeyboardMarkup(rows)


async def deliver_pve_updates(bot,results=(),*,now_ms=None,limit=100):
    from handlers.location import build_pve_encounter_detail_message
    from handlers.combat_views import home
    from game.pve_live import load_active_pve_encounter
    now_ms = int(time.time()*1000) if now_ms is None else now_ms
    changed = {r['encounter_id'] for r in results if r.get('encounter_id')}
    conn = get_connection()
    try:
        # Include failed terminal delivery on the prior surface after a restart.
        encounters = [dict(r) for r in conn.execute("""SELECT e.* FROM pve_encounters e WHERE lifecycle_version=1
            AND (status='active' OR EXISTS(SELECT 1 FROM player_pxe1_ui u WHERE u.surface_kind='pve' AND u.surface_ref=e.encounter_id))
            ORDER BY e.created_at,e.encounter_id LIMIT ?""",(limit,))]
        known = {e['encounter_id'] for e in encounters}
        for eid in sorted(changed-known):
            row = conn.execute('SELECT * FROM pve_encounters WHERE encounter_id=? AND lifecycle_version=1',(eid,)).fetchone()
            if row: encounters.append(dict(row))
        work = []
        for row in encounters:
            participants = [dict(r) for r in conn.execute("SELECT * FROM pve_encounter_participants WHERE encounter_id=? AND status IN ('active','victory','defeated')",(row['encounter_id'],))]
            settlement = conn.execute("SELECT result_json FROM pve_reward_settlements WHERE encounter_id=? AND status='applied'",(row['encounter_id'],)).fetchone()
            for participant in participants:
                player_id = participant['player_id']
                prior = conn.execute('SELECT * FROM player_pxe1_ui WHERE player_id=?',(player_id,)).fetchone()
                death = conn.execute("SELECT result_json FROM economy_action_receipts WHERE player_id=? AND request_id=?",(player_id,f"pve_death:{row['encounter_id']}:{player_id}")).fetchone()
                result = death is not None or participant['status']=='victory'
                kind = 'pve_result' if result else 'pve'
                revision = 1 if result else formation_revision(row,now_ms) if row['runtime_started_ms'] is None else row['turn_revision']
                if prior and prior['surface_kind']==kind and prior['surface_ref']==row['encounter_id'] and prior['surface_revision']==revision and prior['message_id']:
                    continue  # Do not replace action-selection tokens on unchanged ticks.
                if participant['status']=='defeated' and not death: continue
                work.append((row,participant,kind,revision,json.loads(death['result_json']) if death else None,
                             json.loads(settlement['result_json']) if settlement else None))
    finally: conn.close()
    for row,participant,kind,revision,death,settlement in work:
        player_id = participant['player_id']
        try:
            player = dict(get_player(player_id))
            if kind=='pve_result':
                card = pve_result(player,row,participant,death,settlement)
                if not card: continue
                text,keyboard = card
            elif row['runtime_started_ms'] is None:
                text,keyboard = build_pve_encounter_detail_message(player,row['encounter_id'])
            else:
                loaded = load_active_pve_encounter(encounter_id=row['encounter_id'])
                if not loaded: continue
                text,keyboard = home(player,loaded[1],loaded[0])
            from game.player_feedback import inline_feedback,acknowledge_presented_facts
            text,keys = inline_feedback(player_id,player.get('lang','ru'),text)
            delivered = await present_surface(bot,player_id,text,keyboard,kind=kind,ref=row['encounter_id'],revision=revision)
            if delivered: acknowledge_presented_facts(player_id,keys)
        except Exception:
            logger.exception('PXE1 PvE delivery retry for player %s',player_id)
