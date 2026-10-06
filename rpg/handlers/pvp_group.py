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


def target_card(row, player_id, action_id, revision, lang):
    from game.pvp_group_runtime import authorize_order
    from game.action_receipts import ActionRejected
    battle = json.loads(row['reason_context'])['battle']
    if battle['turn_revision'] != revision:
        raise ActionRejected('stale_action')
    sides = locked_sides(row)
    side = 'side_a' if player_id in sides['side_a'] else 'side_b'
    targets = [player_id] if action_id=='guard' else living(battle,sides['side_b' if side=='side_a' else 'side_a'])
    definitions = []
    conn = get_connection()
    try:
        for target in targets:
            action = {'kind':'normal' if action_id=='normal' else 'guard' if action_id=='guard' else 'skill',
                      'target_id':target,'manual':True}
            if action['kind']=='skill':
                action['skill_id']=action_id
            authorize_order(conn,row,battle,player_id,action)
            definitions.append(action)
    finally:
        conn.close()
    tokens = issue_combat_intents(player_id,encounter_kind='pvp',encounter_id=str(row['id']),
        turn_revision=revision,deadline_at=battle['side_deadline_at'],actions=definitions)
    rows = []
    for action in definitions:
        target = battle['participants_v1'][str(action['target_id'])]
        label = f"{target['name']} · {target['hp']}/{target['max_hp']} HP"
        rows.append([InlineKeyboardButton(label,callback_data='pvp_v1_'+tokens[encoded(action)])])
    rows.append([InlineKeyboardButton(t('common.back',lang),callback_data='pvp_refresh')])
    return action_label(action_id,lang),InlineKeyboardMarkup(rows)


def live_card(row, context, player_id, lang):
    battle = context['battle']
    sides = locked_sides(row)
    own = 'side_a' if player_id in sides['side_a'] else 'side_b'
    active = battle['active_side']
    lines = ['⚔️ PvP · '+t('location.pvp_turn_you' if own==active else 'location.pvp_turn_enemy',lang)]
    for side,ids in sides.items():
        for actor_id in ids:
            actor = battle['participants_v1'][str(actor_id)]
            lines.append(f"{'🛡️' if side==own else '⚔️'} {escape(actor['name'])} · {actor['hp']}/{actor['max_hp']} HP")
    buttons = []
    actor = battle['participants_v1'].get(str(player_id))
    submitted = any(o['actor_id']==player_id for o in load_combat_orders(encounter_kind='pvp',encounter_id=str(row['id']),turn_revision=battle['turn_revision']))
    if actor and player_id in living(battle,sides[active]) and not submitted:
        for action_id in legal_actions(actor,pvp=True):
            selected = 'normal_attack' if action_id=='normal' else 'guard' if action_id=='guard' else 'skill:'+action_id
            if not _v1_action_ready(actor,selected):
                continue
            buttons.append(InlineKeyboardButton(action_label(action_id,lang),callback_data=f"pvp_pick_{row['id']}_{battle['turn_revision']}_{action_id}"))
    else:
        lines.append(t('location.pvp_wait_turn_timeout',lang))
    rows = [buttons[i:i+2] for i in range(0,len(buttons),2)]
    rows.append([InlineKeyboardButton(t('common.refresh',lang),callback_data='pvp_refresh')])
    return '\n'.join(lines),InlineKeyboardMarkup(rows)
