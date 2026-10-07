"""Compact live group card and action-to-target selection."""

from html import escape
import json

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import get_connection
from game.combat_identity import legal_actions
from game.combat_orders import issue_combat_intents, load_combat_orders
from game.i18n import get_skill_name, t
from game.pvp_group_runtime import living, locked_sides
from game.pvp_live import _v1_action_ready
from game.pvp_world import encoded
from game.player_ui import validate_surface


def preparation_or_live_card(row, player):
    import time
    from game.action_receipts import issue_actions
    from game.pvp_live import advance_engagement_to_live_battle_if_ready
    state, context = advance_engagement_to_live_battle_if_ready(row)
    player_id, lang = player['telegram_id'], player.get('lang', 'ru')
    if state == 'converted_to_battle':
        conn = get_connection()
        try:
            current = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (row['id'],)).fetchone()
        finally:
            conn.close()
        return live_card(current, context, player_id, lang)
    if state != 'pending':
        return t('pxe1.encounter.finished', lang), InlineKeyboardMarkup([[InlineKeyboardButton(t('keyboard.location', lang), callback_data='px:local:home:0')]])
    conn = get_connection()
    try:
        principals = [conn.execute('SELECT name FROM players WHERE telegram_id=?', (pid,)).fetchone()['name'] for pid in (row['attacker_id'], row['defender_id'])]
        members = [dict(r) for r in conn.execute('SELECT r.*,p.name FROM pvp_engagement_reinforcements r JOIN players p ON p.telegram_id=r.ally_id WHERE engagement_id=? AND membership_version=1 ORDER BY r.id', (row['id'],))]
    finally:
        conn.close()
    from game.pvp_world import milliseconds
    left = max(0,(milliseconds(row['engagement_ready_at'])-int(time.time()*1000)+999)//1000)
    lines = [t('pxe1.encounter.pvp_preparing', lang), escape(principals[0])+' ↔ '+escape(principals[1]),
             t('pxe1.travel.remaining', lang, time=f'{left//60}:{left%60:02d}')]
    for side,name in zip(('initiator','defender'),principals):
        count=1+sum(m['side']==side and m['status']=='accepted' for m in members)
        invited=sum(m['side']==side and m['status']=='pending' for m in members)
        lines.append(t('pxe1.encounter.pvp_side_count',lang,name=escape(name),count=count,invited=invited))
    rows = []
    membership_choices = []
    for member in members:
        if member['status'] in {'pending', 'accepted'}:
            lines.append(f"{escape(member['name'])} · {t('location.pvp_reinforcement_status_'+member['status'], lang)}")
    if player_id in {row['attacker_id'], row['defender_id']}:
        payload = encoded({'schema_version':1,'catalog_version':2,'engagement_id':row['id'],'state_revision':row['state_revision']})
        token = issue_actions(player_id, 'pvp_prep_escape', [payload])[payload]
        rows.append([InlineKeyboardButton(t('pxe1.encounter.pvp_escape_attempt', lang), callback_data=f"pvp_escape_{row['id']}_{token}")])
        own_side='initiator' if player_id==row['attacker_id'] else 'defender'
        if not any(m['side']==own_side and m['status'] in {'pending','accepted'} for m in members):
            rows.append([InlineKeyboardButton(t('pxe1.encounter.pvp_invite',lang),callback_data=f"pvp_allies_{row['id']}_0")])
        for member in members:
            if member['inviter_id'] == player_id and member['status'] == 'pending':
                membership_choices.append((t('pxe1.encounter.pvp_revoke',lang),
                    {'operation':'revoke','ally_id':member['ally_id'],'reinforcement_id':member['id']}))
    else:
        member = next((m for m in members if m['ally_id'] == player_id and m['status'] in {'pending','accepted'}), None)
        if member and member['status'] == 'pending':
            warning='pxe1.encounter.pvp_illegal_assist_warning' if member['side']=='initiator' and context.get('illegal_aggression') else 'pxe1.membership.attacking' if member['side']=='initiator' else 'pxe1.pvp_ally_defence'
            lines.append(t(warning,lang))
            side_name=principals[0] if member['side']=='initiator' else principals[1]
            membership_choices += [(t('pxe1.encounter.pvp_join_named_side',lang,name=side_name),{'operation':'accept','reinforcement_id':member['id']}),
                                   (t('pxe1.encounter.pvp_decline',lang),{'operation':'decline','reinforcement_id':member['id']})]
        elif member:
            membership_choices.append((t('location.pvp_leave_prep',lang),{'operation':'leave','reinforcement_id':member['id']}))
    payloads=[encoded({'schema_version':1,'catalog_version':2,'engagement_id':row['id'],
                       'state_revision':row['state_revision'],**choice}) for _,choice in membership_choices]
    tokens=issue_actions(player_id,'pvp_membership_pxe1',payloads)
    for (label,_),payload in zip(membership_choices,payloads):
        rows.append([InlineKeyboardButton(label,callback_data='pvp_member_'+tokens[payload])])
    rows.append([InlineKeyboardButton(t('common.refresh',lang),callback_data=f"pvp_view_{row['id']}")])
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines), keyboard)
    return '\n'.join(lines), keyboard


def action_label(action_id, lang):
    if action_id == 'normal':
        return t('location.pvp_action_attack_btn',lang)
    if action_id == 'guard':
        return t('location.pvp_action_guard_btn',lang)
    return get_skill_name(action_id,lang)


def view_buttons(row,battle,player_id,definitions):
    from game.action_receipts import issue_actions
    payloads = [encoded({'schema_version':1,'engagement_id':row['id'],
        'turn_revision':battle['turn_revision'],'deadline_at':battle['side_deadline_at'],**data}) for _,data in definitions]
    tokens = issue_actions(player_id,'pxe1_pvp_view',payloads)
    return [InlineKeyboardButton(label,callback_data='pvp_cv_'+tokens[payload])
            for (label,_),payload in zip(definitions,payloads)]


def target_card(row, player_id, action_id, revision, lang):
    from game.pvp_group_runtime import authorize_order
    from game.action_receipts import ActionRejected
    from handlers.combat_views import skill_label
    battle = json.loads(row['reason_context'])['battle']
    if battle['turn_revision'] != revision:
        raise ActionRejected('stale_action')
    sides = locked_sides(row)
    if player_id not in sides['side_a']+sides['side_b']: raise ActionRejected('not_participant')
    actor = battle['participants_v1'][str(player_id)]
    if action_id not in legal_actions(actor,pvp=True): raise ActionRejected('invalid_action')
    selected = 'normal_attack' if action_id=='normal' else 'guard' if action_id=='guard' else 'skill:'+action_id
    if not _v1_action_ready(actor,selected):
        from game.build_contract import POWER_STRIKE,SKILL_SPECS,rank_mana_cost
        from game.combat_identity import cooldown_remaining
        spec = POWER_STRIKE if action_id=='power_strike' else SKILL_SPECS[action_id]
        rank = 1 if action_id=='power_strike' else actor['skill_ranks'][action_id]
        cd = cooldown_remaining(actor,action_id)
        reason = t('pxe1.combat.cooldown',lang,count=cd) if cd else t('pxe1.combat.no_mana',lang,cost=rank_mana_cost(spec,rank))
        buttons = view_buttons(row,battle,player_id,[(t('common.back',lang),{'view':'skills','page':0})])
        return escape(action_label(action_id,lang))+'\n'+reason,InlineKeyboardMarkup([buttons])
    side = 'side_a' if player_id in sides['side_a'] else 'side_b'
    targets = [player_id] if action_id=='guard' else living(battle,sides['side_b' if side=='side_a' else 'side_a'])
    definitions = []
    conn = get_connection()
    try:
        for target in targets:
            action = {'kind':'normal' if action_id=='normal' else 'guard' if action_id=='guard' else 'skill',
                      'target_id':target,'manual':True}
            if action['kind']=='skill': action['skill_id']=action_id
            authorize_order(conn,row,battle,player_id,action)
            definitions.append(action)
    finally: conn.close()
    tokens = issue_combat_intents(player_id,encounter_kind='pvp',encounter_id=str(row['id']),
        turn_revision=revision,deadline_at=battle['side_deadline_at'],actions=definitions)
    lines = [escape(action_label(action_id,lang)),t('pxe1.combat.confirm_scope' if action_id=='guard' else 'pxe1.combat.choose_target',lang)]
    if action_id not in {'normal','guard'}: lines.append(escape(skill_label(actor,action_id,lang)))
    rows = []
    for action in definitions:
        target = battle['participants_v1'][str(action['target_id'])]
        label = t('pxe1.combat.use',lang) if action_id=='guard' else f"{target['name']} · ❤️ {target['hp']}/{target['max_hp']}"
        rows.append([InlineKeyboardButton(label,callback_data='pvp_v1_'+tokens[encoded(action)])])
    rows.append(view_buttons(row,battle,player_id,[(t('common.back',lang),{'view':'home'})]))
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines),keyboard)
    return '\n'.join(lines),keyboard


def menu_card(row,player_id,view,lang,page=0):
    from game.action_receipts import ActionRejected
    from handlers.combat_views import skill_label
    battle = json.loads(row['reason_context'])['battle']
    sides = locked_sides(row)
    if player_id not in sides['side_a']+sides['side_b']: raise ActionRejected('not_participant')
    actor = battle['participants_v1'][str(player_id)]
    definitions = []
    if view=='skills':
        skills = [s for s in legal_actions(actor,pvp=True) if s not in {'normal','guard'}]
        pages = max(1,(len(skills)+5)//6); page = max(0,min(int(page),pages-1))
        lines = [t('pxe1.weapon_skills',lang),t('gear.page',lang,page=page+1,pages=pages)]
        for skill in skills[page*6:page*6+6]:
            label = skill_label(actor,skill,lang); lines.append(escape(label))
            definitions.append((label,{'view':'action','action_id':skill}))
        if page: definitions.append(('◀️',{'view':'skills','page':page-1}))
        if page+1<pages: definitions.append(('▶️',{'view':'skills','page':page+1}))
    else:
        lines = [t('pxe1.combat.participants',lang) if view=='participants' else t('pxe1.details',lang)]
        for ids in sides.values():
            for pid in ids:
                member = battle['participants_v1'][str(pid)]
                lines.append(escape(member['name'])+f" · ❤️ {member['hp']}/{member['max_hp']} · 🔵 {member['mana']}/{member['max_mana']}")
                if view=='details':
                    # Details keep all structured status without introducing combat rules.
                    for effect in member.get('effects',[]):
                        from game.i18n import get_skill_name
                        from handlers.battle import _V1_EFFECT_COPY
                        label = get_skill_name(effect.get('skill_id',''),lang) if effect.get('skill_id') else _V1_EFFECT_COPY.get(lang,_V1_EFFECT_COPY['en']).get(effect['kind'],t('pxe1.details',lang))
                        lines.append(escape(str(label))+f" · ⏳{effect.get('duration',0)}")
        if view=='details':
            from handlers.battle import _render_v1_event
            for event in battle.get('events_v1',[])[-12:]:
                rendered = _render_v1_event(event,battle,lang)
                if rendered: lines.append(rendered)
    definitions.append((t('common.back',lang),{'view':'home'}))
    buttons = view_buttons(row,battle,player_id,definitions)
    keyboard = InlineKeyboardMarkup([[b] for b in buttons])
    text = '\n'.join(lines)
    validate_surface(text,keyboard,list_view=view=='skills',long_detail=view=='details')
    return text,keyboard


def live_card(row, context, player_id, lang):
    import time
    from handlers.combat_views import deadline_ms
    battle = context['battle']
    sides = locked_sides(row)
    member = player_id in sides['side_a']+sides['side_b']
    own = 'side_a' if player_id in sides['side_a'] else 'side_b'
    active = battle['active_side']
    left = max(0,(deadline_ms(battle['side_deadline_at'])-int(time.time()*1000)+999)//1000)
    lines = ['⚔️ PvP',t('pxe1.combat.side_time',lang,seconds=left)]
    for side,ids in sides.items():
        for actor_id in ids:
            actor = battle['participants_v1'][str(actor_id)]
            lines.append(f"{'🛡️' if side==own else '⚔️'} {escape(actor['name'])}"+(f" · ❤️ {actor['hp']}/{actor['max_hp']}" if member else ''))
    actor = battle['participants_v1'].get(str(player_id))
    submitted = any(o['actor_id']==player_id for o in load_combat_orders(encounter_kind='pvp',encounter_id=str(row['id']),turn_revision=battle['turn_revision']))
    definitions = []
    if actor and player_id in living(battle,sides[active]) and not submitted and left>0:
        lines.append(f"🔵 {actor['mana']}/{actor['max_mana']}")
        definitions += [(action_label('normal',lang),{'view':'action','action_id':'normal'}),
                        (t('pxe1.combat.skills',lang),{'view':'skills','page':0}),
                        (action_label('guard',lang),{'view':'action','action_id':'guard'})]
    elif member: lines.append(t('location.pvp_wait_turn_timeout',lang))
    if member:
        definitions += [(t('pxe1.combat.participants',lang),{'view':'participants'}),(t('pxe1.details',lang),{'view':'details'})]
    buttons = view_buttons(row,battle,player_id,definitions)
    rows = [buttons[i:i+2] for i in range(0,len(buttons),2)]
    if not member: rows.append([InlineKeyboardButton(t('common.refresh',lang),callback_data='pvp_refresh')])
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines),keyboard)
    return '\n'.join(lines),keyboard


async def handle_read_selection(update,context):
    import time
    from database import get_player
    from game.action_receipts import ActionRejected
    from game.player_ui import record_surface
    query = update.callback_query
    player = dict(get_player(query.from_user.id)); lang = player.get('lang','ru')
    conn = get_connection()
    try:
        token = conn.execute("SELECT payload FROM player_ui_actions WHERE token=? AND player_id=? AND kind='pxe1_pvp_view' AND used=0 AND expires_at>=?",
                             (query.data.removeprefix('pvp_cv_'),player['telegram_id'],int(time.time()))).fetchone()
        intent = json.loads(token['payload']) if token else {}
        row = conn.execute('SELECT * FROM pvp_engagements WHERE id=? AND group_rules_version=1',(intent.get('engagement_id'),)).fetchone()
    finally: conn.close()
    if not row or intent.get('schema_version')!=1 or row['engagement_state']!='converted_to_battle':
        await query.answer(t('location.pvp_action_not_ready',lang),show_alert=True); return
    battle_context = json.loads(row['reason_context']); battle = battle_context['battle']
    try:
        if battle['turn_revision']!=intent['turn_revision'] or battle['side_deadline_at']!=intent['deadline_at'] or intent['view']=='home':
            text,keyboard = live_card(row,battle_context,player['telegram_id'],lang)
        elif intent['view']=='action':
            text,keyboard = target_card(row,player['telegram_id'],intent['action_id'],intent['turn_revision'],lang)
        else: text,keyboard = menu_card(row,player['telegram_id'],intent['view'],lang,intent.get('page',0))
    except (ActionRejected,ValueError,KeyError):
        text,keyboard = live_card(row,battle_context,player['telegram_id'],lang)
    await query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
    record_surface(player['telegram_id'],kind='pvp',ref=str(row['id']),revision=battle['turn_revision'],
                   chat_id=query.message.chat_id,message_id=query.message.message_id)
    await query.answer()


async def handle_membership_choice(update,context):
    import time
    from database import get_player
    from game.pvp_world import apply_membership_intent
    from game.action_receipts import ActionRejected
    from game.player_ui import record_surface
    query=update.callback_query;actor_id=query.from_user.id
    player=dict(get_player(actor_id));lang=player.get('lang','ru')
    conn=get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        result=apply_membership_intent(conn,actor_id=actor_id,token=query.data.removeprefix('pvp_member_'),now_ms=int(time.time()*1000))
        conn.commit()
    except (ActionRejected,ValueError,KeyError,TypeError):
        conn.rollback();result=None
    finally: conn.close()
    if not result:
        await query.answer(t('location.pvp_reinforcement_response_blocked',lang),show_alert=True)
        conn=get_connection()
        try:
            token=conn.execute("SELECT payload FROM player_ui_actions WHERE token=? AND player_id=? AND kind='pvp_membership_pxe1'",(query.data.removeprefix('pvp_member_'),actor_id)).fetchone()
            intent=json.loads(token['payload']) if token else {}
            row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(intent.get('engagement_id'),)).fetchone()
        finally: conn.close()
        if row:
            text,keyboard=preparation_or_live_card(row,player)
            await query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
        return
    if result.get('recovered'):
        text=t('pxe1.membership.recovered',lang,outcome=t('pxe1.membership.'+result['outcome'],lang))
        keyboard=InlineKeyboardMarkup([[InlineKeyboardButton(t('keyboard.location',lang),callback_data='px:local:home:0')]])
    else:
        conn=get_connection()
        try: row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(result['engagement_id'],)).fetchone()
        finally: conn.close()
        text,keyboard=preparation_or_live_card(row,player)
    await query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
    await query.answer()
    # Transport may fail after the commit. The tick retries from persisted members.
    if not result.get('recovered'):
        conn=get_connection()
        try: current=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(result['engagement_id'],)).fetchone()
        finally: conn.close()
        revision=current['turn_revision'] if current['engagement_state']=='converted_to_battle' else 1_000_000_000+current['state_revision']
        record_surface(actor_id,kind='pvp',ref=str(result['engagement_id']),revision=revision,
                       chat_id=query.message.chat_id,message_id=query.message.message_id)
        await deliver_preparation_updates(context.bot,result['engagement_id'],skip_player=actor_id,
                                          invited_player=result['ally_id'] if result['operation']=='invite' else None)


async def deliver_preparation_updates(bot,engagement_id,*,skip_player=None,invited_player=None):
    import logging
    from database import get_player
    from game.player_ui import present_surface,_row
    conn=get_connection()
    try:
        row=conn.execute('SELECT * FROM pvp_engagements WHERE id=?',(engagement_id,)).fetchone()
        if not row or row['world_model_version']!=1: return
        members=[dict(r) for r in conn.execute('SELECT * FROM pvp_engagement_reinforcements WHERE engagement_id=? AND membership_version=1',(engagement_id,))]
        recipients={row['attacker_id'],row['defender_id']}
        recipients.update(m['ally_id'] for m in members)
        closure_facts={r['player_id']:r['event_key'] for r in conn.execute(
            "SELECT player_id,event_key FROM player_feedback_events WHERE source_kind='pvp' AND source_id=? AND event_key=? AND state='pending'",
            (str(engagement_id),f'recovery:pvp:{engagement_id}:escaped'))}
        recipients.update(closure_facts)
        if invited_player: recipients.add(invited_player)
    finally: conn.close()
    for player_id in sorted(recipients):
        if player_id==skip_player: continue
        prior=_row(player_id) or {}
        # Live cards and their personal consequences belong to combat delivery.
        if row['engagement_state']=='converted_to_battle' and player_id in {row['attacker_id'],row['defender_id'],*(m['ally_id'] for m in members if m['status']=='locked')}: continue
        member=next((m for m in members if m['ally_id']==player_id),None)
        closed=member and member['status'] not in {'pending','accepted'}
        if closed and player_id not in closure_facts and (prior.get('surface_ref')!=str(engagement_id) or prior.get('surface_kind') not in {'pvp','pvp_result'}): continue
        kind='pvp_result' if closed or row['engagement_state']!='pending' else 'pvp'
        revision=1_000_000_000+row['state_revision']
        if player_id not in closure_facts and prior.get('surface_kind')==kind and prior.get('surface_ref')==str(engagement_id) and prior.get('surface_revision')==revision: continue
        try:
            if player_id in closure_facts:
                lang=get_player(player_id)['lang']
                text=t('pxe1.encounter.pvp_escape_success',lang)
                keyboard=InlineKeyboardMarkup([[InlineKeyboardButton(t('pxe1.menu.location',lang),callback_data='px:local:home:0')]])
            elif closed:
                lang=get_player(player_id)['lang']
                text=t('pxe1.membership.'+member['status'],lang)
                keyboard=InlineKeyboardMarkup([[InlineKeyboardButton(t('keyboard.location',lang),callback_data='px:local:home:0')]])
            else:
                text,keyboard=preparation_or_live_card(row,dict(get_player(player_id)))
            await present_surface(bot,player_id,text,keyboard,kind=kind,ref=str(engagement_id),revision=revision)
            if player_id in closure_facts:
                from game.player_feedback import acknowledge_presented_facts
                acknowledge_presented_facts(player_id,[closure_facts[player_id]])
        except Exception:
            logging.getLogger(__name__).exception('PvP preparation delivery retry for player %s',player_id)


async def retry_preparation_delivery(bot):
    """Retry failed invitations/status cards without changing gameplay authority."""
    conn=get_connection()
    try:
        ids=[r[0] for r in conn.execute("""SELECT e.id FROM pvp_engagements e
            WHERE e.world_model_version=1 AND (e.engagement_state='pending' OR EXISTS(
                SELECT 1 FROM player_feedback_events f WHERE f.source_kind='pvp'
                    AND f.source_id=CAST(e.id AS TEXT) AND f.state='pending'
                    AND f.event_key='recovery:pvp:'||e.id||':escaped') OR EXISTS(
                SELECT 1 FROM player_pxe1_ui u WHERE u.surface_kind='pvp'
                    AND u.surface_ref=CAST(e.id AS TEXT) AND u.surface_revision>=1000000000))
            ORDER BY e.id LIMIT 100""")]
    finally: conn.close()
    for engagement_id in ids:
        await deliver_preparation_updates(bot,engagement_id)


def allies_card(row,player,page=0):
    from game.pvp_live import list_reinforcement_candidates
    from game.action_receipts import issue_actions,ActionRejected
    from game.pvp_world import milliseconds
    import time
    player_id=player['telegram_id'];lang=player.get('lang','ru')
    if not row or row['world_model_version']!=1 or player_id not in {row['attacker_id'],row['defender_id']} or row['engagement_state']!='pending' or int(time.time()*1000)>=milliseconds(row['engagement_ready_at']):
        raise ActionRejected('not_principal')
    candidates=list_reinforcement_candidates(engagement_row=row,inviter_id=player_id,limit=None)
    pages=max(1,(len(candidates)+5)//6);page=max(0,min(int(page),pages-1))
    visible=candidates[page*6:page*6+6]
    payloads=[encoded({'schema_version':1,'catalog_version':2,'engagement_id':row['id'],
        'state_revision':row['state_revision'],'operation':'invite','ally_id':ally['telegram_id']}) for ally in visible]
    tokens=issue_actions(player_id,'pvp_membership_pxe1',payloads)
    lines=[t('pxe1.encounter.pvp_invite',lang),t('gear.page',lang,page=page+1,pages=pages)]
    rows=[]
    for ally,payload in zip(visible,payloads):
        label=ally['name']+' · '+t('common.level',lang)+' '+str(ally['level'])
        lines.append(escape(label))
        rows.append([InlineKeyboardButton(label,callback_data='pvp_member_'+tokens[payload])])
    if not visible: lines.append(t('location.pvp_reinforcement_invite_blocked',lang))
    nav=[]
    if page: nav.append(InlineKeyboardButton('◀️',callback_data=f"pvp_allies_{row['id']}_{page-1}"))
    if page+1<pages: nav.append(InlineKeyboardButton('▶️',callback_data=f"pvp_allies_{row['id']}_{page+1}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(t('common.back',lang),callback_data=f"pvp_view_{row['id']}")])
    keyboard=InlineKeyboardMarkup(rows);text='\n'.join(lines)
    validate_surface(text,keyboard,list_view=True)
    return text,keyboard
