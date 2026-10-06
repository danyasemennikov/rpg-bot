"""Read-only PvE action selection; complete orders use combat_orders.py."""

import json
import time
from datetime import datetime,timezone
from html import escape

from telegram import InlineKeyboardButton,InlineKeyboardMarkup

from database import get_connection,get_player
from game.action_receipts import ActionRejected,issue_actions
from game.build_contract import POWER_STRIKE,SKILL_SPECS,rank_mana_cost
from game.combat_identity import cooldown_remaining,legal_actions,hit_chance,preview_damage_range
from game.combat_orders import issue_combat_intents,load_combat_orders
from game.i18n import t,get_mob_name,get_skill_name,get_item_name
from game.player_ui import validate_surface,record_surface


def deadline_ms(value):
    parsed = datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp()*1000)


def packed(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def skill_label(actor,skill_id,lang):
    spec = POWER_STRIKE if skill_id=='power_strike' else SKILL_SPECS[skill_id]
    rank = 1 if skill_id=='power_strike' else int(actor.get('skill_ranks',{}).get(skill_id,0))
    return f"{get_skill_name(skill_id,lang)} · {rank}{'' if skill_id=='power_strike' else '/3'} · 🔵{rank_mana_cost(spec,rank)} · ⏳{cooldown_remaining(actor,skill_id)}"


def view_rows(player,state,definitions):
    payloads = [packed({'schema_version':1,'encounter_id':state['pve_encounter_id'],
                       'turn_revision':state.get('turn_revision',0),'deadline_at':state.get('side_deadline_at'),**data})
                for _,data in definitions]
    tokens = issue_actions(player['telegram_id'],'pxe1_combat_view',payloads)
    return [[InlineKeyboardButton(label,callback_data='battle_px_'+tokens[payload])]
            for (label,_),payload in zip(definitions,payloads)]


def home(player,mob,state):
    lang = player.get('lang','ru')
    actor = (state.get('participant_states_v1') or {}).get(str(player['telegram_id']),{})
    alive = [e for e in state.get('enemy_states_v1',[]) if int(e.get('hp',0))>0]
    left = max(0,(deadline_ms(state['side_deadline_at'])-int(time.time()*1000)+999)//1000) if state.get('side_deadline_at') else 0
    lines = ['⚔️ <b>'+escape(get_mob_name(mob['id'],lang))+'</b>',
             t('pxe1.combat.side_time',lang,seconds=left),
             f"❤️ {actor.get('hp',state.get('player_hp',0))}/{actor.get('max_hp',state.get('player_max_hp',0))} · 🔵 {actor.get('mana',state.get('player_mana',0))}/{actor.get('max_mana',state.get('player_max_mana',0))}",
             t('battle.pack_remaining',lang,count=len(alive))]
    if alive:
        enemy = alive[0]
        lines.append(escape(get_mob_name(enemy.get('mob_id',mob['id']),lang))+f" · ❤️ {enemy['hp']}/{enemy['max_hp']}")
    submitted = any(o['actor_id']==player['telegram_id'] for o in load_combat_orders(encounter_kind='pve',encounter_id=state['pve_encounter_id'],turn_revision=int(state.get('turn_revision',0))))
    available = bool(actor and int(actor.get('hp',0))>0 and state.get('active_side')=='side_a' and not submitted and left>0)
    definitions = []
    if available:
        definitions += [(t('battle.attack_btn',lang),{'view':'action','action_id':'normal'}),
                        (t('pxe1.combat.skills',lang),{'view':'skills','page':0}),
                        (t('location.pvp_action_guard_btn',lang),{'view':'action','action_id':'guard'}),
                        (t('battle.potions_btn',lang),{'view':'supplies','page':0}),
                        (t('battle.flee_btn',lang),{'view':'action','action_id':'flee'})]
    else: lines.append(t('pxe1.combat.waiting',lang))
    definitions.append((t('pxe1.details',lang),{'view':'details'}))
    from handlers.battle import _render_v1_event
    for event in state.get('combat_events_v1',[])[-2:]:
        rendered = _render_v1_event(event,state,lang)
        if rendered and len(('\n'.join(lines)+'\n'+rendered).encode('utf-16-le'))//2<=900:
            lines.append(rendered)
    rows = view_rows(player,state,definitions)
    # Main actions use two columns and stay within the six-control home.
    buttons = [b for row in rows for b in row]
    rows = [buttons[i:i+2] for i in range(0,len(buttons),2)]
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines),keyboard)
    return '\n'.join(lines),keyboard


def action_card(player,state,action_id,page=0):
    lang = player.get('lang','ru')
    actor = (state.get('participant_states_v1') or {}).get(str(player['telegram_id']))
    if not actor or int(actor.get('hp',0))<=0:
        raise ActionRejected('not_participant')
    if state.get('active_side')!='side_a' or int(time.time()*1000)>=deadline_ms(state['side_deadline_at']):
        raise ActionRejected('not_your_turn')
    if action_id not in {*legal_actions(actor),'flee'}:
        raise ActionRejected('invalid_action')
    enemies = [e for e in state.get('enemy_states_v1',[]) if int(e.get('hp',0))>0]
    allies = [a for a in state.get('participant_states_v1',{}).values() if int(a.get('hp',0))>0]
    spec = None
    if action_id not in {'normal','guard','flee'}:
        spec = POWER_STRIKE if action_id=='power_strike' else SKILL_SPECS[action_id]
        rank = 1 if action_id=='power_strike' else int(actor.get('skill_ranks',{}).get(action_id,0))
        remaining = cooldown_remaining(actor,action_id)
        cost = rank_mana_cost(spec,rank)
        if remaining or int(actor.get('mana',0))<cost:
            reason = t('pxe1.combat.cooldown',lang,count=remaining) if remaining else t('pxe1.combat.no_mana',lang,cost=cost)
            keyboard = InlineKeyboardMarkup(view_rows(player,state,[(t('common.back',lang),{'view':'skills','page':0})]))
            return get_skill_name(action_id,lang)+'\n'+reason,keyboard
    scope = action_id in {'guard','flee'} or (spec and spec.target in {'Self','Party','F','A','2x2'})
    if scope: recipients = [None]
    elif spec and spec.target=='Ally': recipients = allies
    elif spec and spec.target=='AllyOrEnemy': recipients = allies+enemies
    else: recipients = enemies
    pages = max(1,(len(recipients)+5)//6); page = max(0,min(int(page),pages-1))
    actions = []
    for recipient in recipients[page*6:page*6+6]:
        target_id = str(recipient.get('unit_id',recipient.get('actor_id'))) if recipient else None
        actions.append({'kind':'basic_attack' if action_id=='normal' else action_id if action_id in {'guard','flee'} else 'skill',
                        'skill_id':action_id if spec else None,'item_id':None,
                        'target_info':{'id':target_id} if target_id else None})
    tokens = issue_combat_intents(player['telegram_id'],encounter_id=state['pve_encounter_id'],
                                  turn_revision=state['turn_revision'],deadline_at=state['side_deadline_at'],actions=actions)
    label = t('battle.attack_btn',lang) if action_id=='normal' else t('location.pvp_action_guard_btn',lang) if action_id=='guard' else t('battle.flee_btn',lang) if action_id=='flee' else get_skill_name(action_id,lang)
    lines = [escape(label),t('pxe1.combat.confirm_scope' if scope else 'pxe1.combat.choose_target',lang)]
    if spec: lines.append(skill_label(actor,action_id,lang))
    if scope and spec:
        from handlers.build import _TARGET_LABELS,_label
        lines.append(t('pxe1.combat.scope',lang,scope=_label(_TARGET_LABELS,lang,spec.target)))
    rows = []
    for recipient,action in zip(recipients[page*6:page*6+6],actions):
        if recipient:
            name = get_mob_name(recipient['mob_id'],lang) if recipient.get('mob_id') else recipient.get('name',t('battle.player_label',lang))
            chance = hit_chance(actor,recipient) if recipient in enemies and action_id=='normal' else None
            damage = preview_damage_range(actor,recipient) if chance is not None else None
            lines.append(escape(name)+f" · ❤️ {recipient['hp']}/{recipient['max_hp']}"+(f' · {chance}% · {damage[0]}–{damage[1]}' if chance is not None else ''))
            target_label = name+f" · ❤️ {recipient['hp']}/{recipient['max_hp']}"
        else: target_label = t('pxe1.combat.use',lang)
        rows.append([InlineKeyboardButton(target_label,callback_data='battle_v1_'+tokens[packed(action)])])
    navigation = []
    if page: navigation.append(('◀️',{'view':'action','action_id':action_id,'page':page-1}))
    if page+1<pages: navigation.append(('▶️',{'view':'action','action_id':action_id,'page':page+1}))
    navigation.append((t('common.back',lang),{'view':'home'}))
    rows.extend(view_rows(player,state,navigation))
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines),keyboard,list_view=True)
    return '\n'.join(lines),keyboard


def skills_card(player,state,page=0):
    lang = player.get('lang','ru')
    actor = state['participant_states_v1'][str(player['telegram_id'])]
    skills = [s for s in legal_actions(actor) if s not in {'normal','guard'}]
    pages = max(1,(len(skills)+5)//6); page = max(0,min(int(page),pages-1))
    lines = [t('pxe1.weapon_skills',lang),t('gear.page',lang,page=page+1,pages=pages)]
    definitions = []
    for skill in skills[page*6:page*6+6]:
        label = skill_label(actor,skill,lang)
        lines.append(escape(label))
        definitions.append((label,{'view':'action','action_id':skill}))
    if page: definitions.append(('◀️',{'view':'skills','page':page-1}))
    if page+1<pages: definitions.append(('▶️',{'view':'skills','page':page+1}))
    definitions.append((t('common.back',lang),{'view':'home'}))
    keyboard = InlineKeyboardMarkup(view_rows(player,state,definitions))
    validate_surface('\n'.join(lines),keyboard,list_view=True)
    return '\n'.join(lines),keyboard


def supplies_card(player,state,page=0,inventory_id=None):
    from game.items_data import get_item
    lang = player.get('lang','ru')
    conn = get_connection()
    try:
        supplies = [dict(r) for r in conn.execute("""SELECT inv.id,inv.item_id,inv.quantity FROM inventory inv
            JOIN items i ON inv.item_id=i.item_id WHERE inv.telegram_id=? AND i.item_type='potion'
            AND inv.quantity>0 ORDER BY inv.item_id,inv.id""",(player['telegram_id'],))]
        encounter = conn.execute('SELECT turn_revision,state_revision FROM pve_encounters WHERE encounter_id=?',
                                 (state['pve_encounter_id'],)).fetchone()
    finally: conn.close()
    if inventory_id is not None:
        supply = next((r for r in supplies if r['id']==inventory_id),None)
        if not supply or not encounter: raise ActionRejected('stale_action')
        item = get_item(supply['item_id'])
        lines = [escape(get_item_name(supply['item_id'],lang))+f" ×{supply['quantity']}"]
        bonuses = json.loads(item['stat_bonus_json'])
        for key,locale in (('heal','battle.potion_heal'),('mana','battle.potion_mana')):
            if bonuses.get(key): lines.append(t(locale,lang,amount=bonuses[key]))
        payload = f"{state['pve_encounter_id']}:{supply['id']}:{supply['quantity']}:{encounter['turn_revision']}:{encounter['state_revision']}"
        token = issue_actions(player['telegram_id'],'battle_use',[payload])[payload]
        rows = [[InlineKeyboardButton(t('pxe1.combat.use',lang),callback_data='battle_use_potion_'+token)]]
        rows.extend(view_rows(player,state,[(t('common.back',lang),{'view':'supplies','page':page})]))
    else:
        pages = max(1,(len(supplies)+5)//6); page = max(0,min(int(page),pages-1))
        lines = [t('battle.choose_potion',lang),t('gear.page',lang,page=page+1,pages=pages)]
        definitions = [(get_item_name(r['item_id'],lang)+f" ×{r['quantity']}",
                        {'view':'supply','inventory_id':r['id'],'page':page}) for r in supplies[page*6:page*6+6]]
        if not supplies: lines.append(t('battle.no_potions',lang))
        if page: definitions.append(('◀️',{'view':'supplies','page':page-1}))
        if page+1<pages: definitions.append(('▶️',{'view':'supplies','page':page+1}))
        definitions.append((t('common.back',lang),{'view':'home'}))
        rows = view_rows(player,state,definitions)
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines),keyboard,list_view=True)
    return '\n'.join(lines),keyboard


def details_card(player,state,section=None,page=0):
    from handlers.battle import _render_v1_event,_V1_EFFECT_COPY
    from handlers.build import _COPY
    lang=player.get('lang','ru')
    definitions=[]
    if section not in {'enemies','allies','log'}:
        text=t('pxe1.details',lang)
        definitions=[(t('pxe1.combat.'+group,lang),{'view':'details','section':group,'page':0}) for group in ('enemies','allies','log')]
        definitions.append((t('common.back',lang),{'view':'home'}))
    else:
        entries=[]
        if section=='log':
            entries=[line for e in state.get('combat_events_v1',[]) if (line:=_render_v1_event(e,state,lang))]
        else:
            entities = state.get('enemy_states_v1',[]) if section=='enemies' else list(state.get('participant_states_v1',{}).values())
            for entity in entities:
                name=get_mob_name(entity['mob_id'],lang) if entity.get('mob_id') else entity.get('name',t('battle.player_label',lang))
                lines=[escape(name)+f" · ❤️ {entity['hp']}/{entity['max_hp']}"]
                if 'mana' in entity: lines.append(f"🔵 {entity['mana']}/{entity['max_mana']}")
                copy=_COPY.get(lang,_COPY['en'])
                stats=[copy[label]+': '+str(entity[key]) for key,label in (
                    ('physical_defense','pdef'),('magic_defense','mdef'),('accuracy','accuracy'),('evasion','evasion')) if key in entity]
                if stats: lines.append(' · '.join(stats))
                for effect in entity.get('effects',[]):
                    label=_V1_EFFECT_COPY.get(lang,_V1_EFFECT_COPY['en']).get(effect.get('kind'),t('pxe1.details',lang))
                    lines.append(escape(label)+f" · {effect.get('value',effect.get('raw_tick',''))} · ⏳{effect.get('duration',0)}")
                entries.append('\n'.join(lines))
        pages=[[]]
        for entry in entries:
            if pages[-1] and (len(pages[-1])==6 or len(('\n\n'.join(pages[-1])+'\n\n'+entry).encode('utf-16-le'))//2>2800): pages.append([])
            pages[-1].append(entry)
        page=max(0,min(int(page),len(pages)-1))
        text='\n'.join([t('pxe1.combat.'+section,lang),t('gear.page',lang,page=page+1,pages=len(pages))])+'\n\n'+'\n\n'.join(pages[page])
        if page: definitions.append(('◀️',{'view':'details','section':section,'page':page-1}))
        if page+1<len(pages): definitions.append(('▶️',{'view':'details','section':section,'page':page+1}))
        definitions.append((t('common.back',lang),{'view':'details'}))
    keyboard=InlineKeyboardMarkup(view_rows(player,state,definitions))
    validate_surface(text,keyboard,long_detail=True)
    return text,keyboard


async def handle_read_selection(update,context):
    from game.pve_live import load_active_pve_encounter,pve_world_phase
    query = update.callback_query
    player = dict(get_player(query.from_user.id))
    lang = player.get('lang','ru')
    conn = get_connection()
    try:
        row = conn.execute("SELECT payload FROM player_ui_actions WHERE token=? AND player_id=? AND kind='pxe1_combat_view' AND used=0 AND expires_at>=?",
                           (query.data.removeprefix('battle_px_'),player['telegram_id'],int(time.time()))).fetchone()
        intent = json.loads(row['payload']) if row else {}
        if intent.get('schema_version')!=1 or pve_world_phase(conn,intent.get('encounter_id',''))!='active':
            raise ActionRejected('stale_action')
        participant = conn.execute("SELECT 1 FROM pve_encounter_participants WHERE encounter_id=? AND player_id=? AND status='active'",(intent['encounter_id'],player['telegram_id'])).fetchone()
        if not participant: raise ActionRejected('not_participant')
    except (ActionRejected,ValueError,KeyError):
        intent = None
    finally: conn.close()
    loaded = load_active_pve_encounter(encounter_id=intent['encounter_id']) if intent else None
    if not loaded:
        await query.answer(t('battle.turn_not_ready',lang),show_alert=True)
        return
    state,mob = loaded
    if state.get('turn_revision')!=intent['turn_revision'] or state.get('side_deadline_at')!=intent['deadline_at']:
        text,keyboard = home(player,mob,state)
    else:
        try:
            view = intent['view']
            if view=='action': text,keyboard = action_card(player,state,intent['action_id'],intent.get('page',0))
            elif view=='skills': text,keyboard = skills_card(player,state,intent.get('page',0))
            elif view in {'supplies','supply'}: text,keyboard = supplies_card(player,state,intent.get('page',0),intent.get('inventory_id'))
            elif view=='details': text,keyboard = details_card(player,state,intent.get('section'),intent.get('page',0))
            else: text,keyboard = home(player,mob,state)
        except (ActionRejected,ValueError,KeyError):
            text,keyboard = home(player,mob,state)
    await query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
    record_surface(player['telegram_id'],kind='pve',ref=state['pve_encounter_id'],revision=state['turn_revision'],
                   chat_id=query.message.chat_id,message_id=query.message.message_id)
    await query.answer()
