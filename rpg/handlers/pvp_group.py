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
    from datetime import datetime, timezone
    from game.action_receipts import issue_actions
    from game.pvp_live import advance_engagement_to_live_battle_if_ready, list_reinforcement_candidates
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
        return t('location.pvp_battle_finished', lang), InlineKeyboardMarkup([[InlineKeyboardButton(t('keyboard.location', lang), callback_data='px:local:home:0')]])
    conn = get_connection()
    try:
        principals = [conn.execute('SELECT name FROM players WHERE telegram_id=?', (pid,)).fetchone()['name'] for pid in (row['attacker_id'], row['defender_id'])]
        members = [dict(r) for r in conn.execute('SELECT r.*,p.name FROM pvp_engagement_reinforcements r JOIN players p ON p.telegram_id=r.ally_id WHERE engagement_id=? AND membership_version=1 ORDER BY r.id', (row['id'],))]
    finally:
        conn.close()
    left = max(0, int((datetime.fromisoformat(row['engagement_ready_at']).replace(tzinfo=timezone.utc)-datetime.now(timezone.utc)).total_seconds()))
    lines = [t('location.pvp_pending', lang), escape(principals[0])+' ↔ '+escape(principals[1]),
             t('pxe1.remaining', lang, time=f'{left//60}:{left%60:02d}')]
    rows = []
    for member in members:
        if member['status'] in {'pending', 'accepted'}:
            lines.append(f"{escape(member['name'])} · {t('location.pvp_reinforcement_status_'+member['status'], lang)}")
    if player_id in {row['attacker_id'], row['defender_id']}:
        payload = encoded({'schema_version':1,'catalog_version':2,'engagement_id':row['id'],'state_revision':row['state_revision']})
        token = issue_actions(player_id, 'pvp_prep_escape', [payload])[payload]
        rows.append([InlineKeyboardButton(t('location.pvp_escape_btn', lang), callback_data=f"pvp_escape_{row['id']}_{token}")])
        for candidate in list_reinforcement_candidates(engagement_row=row, inviter_id=player_id, limit=2):
            rows.append([InlineKeyboardButton(t('location.pvp_reinforcement_invite_btn', lang, name=candidate['name']), callback_data=f"pvp_invite_{row['id']}_{candidate['telegram_id']}")])
        for member in members:
            if member['inviter_id'] == player_id and member['status'] == 'pending':
                rows.append([InlineKeyboardButton(t('pxe1.revoke_invitation', lang), callback_data=f"pvp_revoke_{row['id']}_{member['ally_id']}")])
    else:
        member = next((m for m in members if m['ally_id'] == player_id and m['status'] in {'pending','accepted'}), None)
        if member and member['status'] == 'pending':
            lines.append(t('pxe1.pvp_ally_crime_warning' if member['side'] == 'initiator' else 'pxe1.pvp_ally_defence', lang))
            rows.append([InlineKeyboardButton(t('location.pvp_reinforcement_accept_btn', lang), callback_data=f"pvp_reinf_accept_{row['id']}"),
                         InlineKeyboardButton(t('location.pvp_reinforcement_decline_btn', lang), callback_data=f"pvp_reinf_decline_{row['id']}")])
        elif member:
            rows.append([InlineKeyboardButton(t('location.pvp_leave_prep', lang), callback_data=f"pvp_leaveprep_{row['id']}")])
    rows.append([InlineKeyboardButton(t('common.refresh', lang), callback_data='pvp_refresh')])
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
