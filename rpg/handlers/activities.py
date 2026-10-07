"""Activities home and durable travel/gather cards."""

from html import escape
import json
import time

from telegram import InlineKeyboardButton,InlineKeyboardMarkup
from database import get_connection,get_player
from game.action_receipts import ActionRejected,consume_action,issue_actions
from game.i18n import get_item_name,get_location_name,t
from game.player_ui import present_surface,validate_surface
from game.pvp_world import encoded


def _kb(rows):
    return InlineKeyboardMarkup(rows)


def duration(seconds):
    seconds = max(0,int(seconds))
    return f'{seconds//60}:{seconds%60:02d}'


def activity_card(player,session,kind,*,now_ms=None):
    now_ms = int(time.time()*1000) if now_ms is None else now_ms
    lang = player.get('lang','ru')
    status = session['status']
    lines = [t('pxe1.'+kind+'_title',lang),t('pxe1.status.'+status,lang)]
    if kind=='travel':
        path = json.loads(session['path_json'])
        lines += [t('pxe1.travel_position',lang,name=escape(get_location_name(player['location_id'],lang))),
                  t('pxe1.travel_destination',lang,name=escape(get_location_name(session['destination_location_id'],lang))),
                  t('pxe1.travel_progress',lang,done=session['edge_index'],total=len(path)-1)]
        if status=='running':
            remaining = max(0,(session['next_due_ms']-now_ms+999)//1000)+18*max(0,len(path)-session['edge_index']-2)
            lines.append(t('pxe1.remaining',lang,time=duration(remaining)))
    else:
        accounting = json.loads(session['result_json'])
        lines += [t('professions.names.'+session['profession_key'],lang),
                  t('pxe1.gather_progress',lang,done=session['last_tick'],total=accounting['max_attempts'],quantity=session['yield_total']),
                  t('pxe1.gather_xp',lang,xp=accounting['xp'])]
        for item,quantity in list(accounting['items'].items())[:4]:
            lines.append(f'{escape(get_item_name(item,lang))} ×{quantity}')
    rows = []
    if status=='running':
        rows.append([InlineKeyboardButton(t('pxe1.stop',lang),callback_data=f"px:stop:{kind}:{session['session_id']}")])
    rows.append([InlineKeyboardButton(t('keyboard.activities',lang),callback_data='px:home'),InlineKeyboardButton(t('keyboard.location',lang),callback_data='pvp_refresh')])
    keyboard = _kb(rows)
    validate_surface('\n'.join(lines),keyboard)
    return '\n'.join(lines),keyboard


def build_activities(player):
    from game.gathering_foundation import build_location_gather_source_profiles
    lang = player.get('lang','ru')
    conn = get_connection()
    try:
        for table,kind in (('player_travel_sessions','travel'),('player_gathering_sessions','gather')):
            active = conn.execute(f"SELECT * FROM {table} WHERE player_id=? AND status='running'",(player['telegram_id'],)).fetchone()
            if active:
                return activity_card(player,dict(active),kind)
    finally:
        conn.close()
    lines = [t('keyboard.activities',lang),'📍 '+escape(get_location_name(player['location_id'],lang))]
    buttons = [InlineKeyboardButton(t('pxe1.gather',lang,profession=t('professions.names.'+source.profession_key,lang)),callback_data='px:gatherpreview:'+source.profession_key)
        for source in build_location_gather_source_profiles(player['location_id']) if source.profession_key!='hunting'][:4]
    buttons += [InlineKeyboardButton(t('professions.title',lang),callback_data='pe_o:0'),
        InlineKeyboardButton(t('pxe1.tools',lang),callback_data='px:tools'),
        InlineKeyboardButton(t('chapter.journal',lang),callback_data='alpha_home')]
    keyboard = _kb([buttons[i:i+2] for i in range(0,len(buttons),2)])
    validate_surface('\n'.join(lines),keyboard)
    return '\n'.join(lines),keyboard


def gathering_preview_card(player,profession):
    from game.gathering_runtime import _source_snapshot
    from game.profession_tools import get_tool
    from game.player_activity import require_available
    lang = player.get('lang','ru')
    snapshot = _source_snapshot(player['location_id'],profession)
    conn = get_connection()
    reason = None
    try:
        tool = get_tool(conn,player['telegram_id'],profession)
        state = conn.execute('SELECT level FROM player_gathering_professions WHERE telegram_id=? AND profession_key=?',
                             (player['telegram_id'],profession)).fetchone()
        level = int(state[0]) if state else 1
        try: require_available(conn,player['telegram_id'])
        except ActionRejected: reason = 'gather_busy'
    finally: conn.close()
    if not reason:
        if not tool or not tool['durability']: reason = 'gather_broken'
        elif not any(e['required_level']<=level and e['required_tool_tier']<=tool['tier'] for e in snapshot['entries']):
            reason = 'gather_locked'
    lines = [t('pxe1.gather',lang,profession=t('professions.names.'+profession,lang)),
             t('pxe1.gather_preview',lang),t('pxe1.gather_tool_hint',lang)]
    for entry in snapshot['entries'][:4]:
        lines.append(t('pxe1.gather_source_line',lang,name=escape(get_item_name(entry['item_id'],lang)),
                       chance=entry['chance_bp']/100,level=entry['required_level'],tier=entry['required_tool_tier']))
    if tool: lines.append(t('pxe1.tool.durability',lang,current=tool['durability'],maximum=60*tool['tier']))
    rows = []
    if reason: lines.append(t('pxe1.'+reason,lang))
    else:
        payload = encoded({'schema_version':1,'catalog_version':2,'profession_key':profession,
                           'location_id':player['location_id'],'tool_revision':tool['revision'],'source_snapshot':snapshot})
        token = issue_actions(player['telegram_id'],'pxe1_gather_start',[payload])[payload]
        rows.append([InlineKeyboardButton(t('pxe1.gather_start',lang),callback_data='px:gatherstart:'+token)])
    rows.append([InlineKeyboardButton(t('pxe1.tools',lang),callback_data='px:tools'),
                 InlineKeyboardButton(t('gear.back_btn',lang),callback_data='px:local:home:0')])
    keyboard = _kb(rows)
    validate_surface('\n'.join(lines),keyboard)
    return '\n'.join(lines),keyboard


def travel_preview_card(player,destination):
    from game.travel_runtime import preview_travel
    conn = get_connection()
    try:
        preview = preview_travel(conn,player['telegram_id'],destination)
        from game.player_activity import player_activity
        activity = player_activity(conn,player['telegram_id'])
    finally:
        conn.close()
    payload = encoded({'schema_version':1,'catalog_version':2,'preview':preview})
    token = issue_actions(player['telegram_id'],'pxe1_travel',[payload])[payload]
    lang = player.get('lang','ru')
    text = '\n'.join([t('pxe1.travel_title',lang),
        t('pxe1.travel_destination',lang,name=escape(get_location_name(preview['destination_location_id'],lang))),
        t('pxe1.route_preview',lang,hops=len(preview['path'])-1,time=duration(preview['duration_seconds']))])
    rows = []
    if activity and activity['kind'] in {'travel','gather'}:
        rows.append([InlineKeyboardButton(t('pxe1.stop',lang),callback_data=f"px:stop:{activity['kind']}:{activity['ref']}")])
        text += '\n'+t('pxe1.stop_before_trip',lang)
    elif activity:
        text += '\n'+t('location.in_battle_move',lang)
    else:
        rows.append([InlineKeyboardButton(t('pxe1.start_travel',lang),callback_data='px:travel:'+token)])
    rows.append([InlineKeyboardButton(t('common.back',lang),callback_data='px:map')])
    keyboard = _kb(rows)
    validate_surface(text,keyboard)
    return text,keyboard


def tool_list(player):
    from game.profession_tools import TOOL_NAMES
    lang = player.get('lang','ru')
    conn = get_connection()
    try:
        tools = conn.execute('SELECT * FROM player_profession_tools WHERE player_id=? ORDER BY profession_key',(player['telegram_id'],)).fetchall()
    finally:
        conn.close()
    rows = [[InlineKeyboardButton(f"{t('pxe1.tool.'+TOOL_NAMES[tool['profession_key']],lang)} · {tool['durability']}/{60*tool['tier']}",callback_data='px:tool:'+tool['profession_key'])] for tool in tools]
    rows.append([InlineKeyboardButton(t('common.back',lang),callback_data='px:home')])
    return t('pxe1.tools',lang),_kb(rows)


def tool_card(player,profession):
    from game.profession_tools import TOOL_NAMES,get_tool,repair_quote
    from game.locations import get_location
    conn = get_connection()
    try:
        tool = get_tool(conn,player['telegram_id'],profession)
        if not tool:
            raise ActionRejected('tool_missing')
        quote = repair_quote(conn,player['telegram_id'],profession) if tool['tier']>1 else None
    finally:
        conn.close()
    lang = player.get('lang','ru')
    lines = [t('pxe1.tool.'+TOOL_NAMES[profession],lang)+' · '+t('pxe1.tool.tier.'+str(tool['tier']),lang),
             t('pxe1.tool.durability',lang,current=tool['durability'],maximum=60*tool['tier'])]
    rows = []
    location = get_location(player['location_id']) or {}
    if quote and quote['restored']:
        lines.append(t('pxe1.repair_materials',lang))
        for item in quote['consumed']:
            lines.append(t('pxe1.repair_input',lang,name=escape(get_item_name(item,lang)),owned=quote['consumed'][item],supplied=quote['supplied'][item]))
        lines.append(t('pxe1.tool.repair_cost',lang,gold=quote['gold']))
        if 'craftsmen_guild' in location.get('services',[]):
            payload = encoded(quote)
            token = issue_actions(player['telegram_id'],'tool_repair_pxe1',[payload])[payload]
            rows.append([InlineKeyboardButton(t('pxe1.tool.assisted_repair' if quote['repair_mode']=='assisted' else 'pxe1.tool.repair',lang),callback_data='px:repair:'+token)])
    elif tool['tier']==1 and location.get('is_regional_safe_hub'):
        quote = {'schema_version':1,'profession_key':profession,'tool_revision':tool['revision'],'gold':12}
        payload = encoded(quote)
        token = issue_actions(player['telegram_id'],'tool_replace_pxe1',[payload])[payload]
        rows.append([InlineKeyboardButton(t('pxe1.replace',lang,gold=12),callback_data='px:replace:'+token)])
    next_tier = min(4,tool['tier']+1)
    rows.append([InlineKeyboardButton(t('pxe1.tool_recipe',lang),callback_data=f'pe_r:pxe_tool_{profession}_{next_tier}')])
    rows.append([InlineKeyboardButton(t('common.back',lang),callback_data='px:tools')])
    keyboard = _kb(rows)
    validate_surface('\n'.join(lines),keyboard)
    return '\n'.join(lines),keyboard


async def activities_command(update,context):
    row = get_player(update.effective_user.id)
    if not row:
        await update.message.reply_text(t('common.no_character','ru'))
        return
    player = dict(row)
    from game.player_ui import install_menu_on_message
    await install_menu_on_message(update.message,player)
    conn = get_connection()
    try:
        current = None
        for table,kind in (('player_travel_sessions','travel'),('player_gathering_sessions','gather')):
            row = conn.execute(f"SELECT * FROM {table} WHERE player_id=? AND status='running'",(player['telegram_id'],)).fetchone()
            if row:
                current = (dict(row),kind);break
    finally: conn.close()
    if current:
        session,kind = current
        text,keyboard = activity_card(player,session,kind)
        await present_surface(context.bot,player['telegram_id'],text,keyboard,kind=kind,
                              ref=session['session_id'],revision=session['revision'],force_refresh=True)
    else:
        text,keyboard = build_activities(player)
        await update.message.reply_text(text,reply_markup=keyboard,parse_mode='HTML')


async def handle_activity_buttons(update,context):
    from game.gathering_runtime import start_gathering_session,stop_gathering_session
    from game.travel_runtime import start_travel_session,stop_travel_session
    query = update.callback_query
    player = dict(get_player(query.from_user.id))
    lang = player.get('lang','ru')
    data = query.data
    now_ms = int(time.time()*1000)
    if data.startswith('px:shop:'):
        from handlers.shop_views import handle_shop_buttons
        await handle_shop_buttons(update,context)
        return
    if data.startswith(('px:local:', 'px:mapregion:', 'px:world:')):
        from handlers.world_views import location_card, map_card
        if data.startswith('px:local:'):
            category, page = data.removeprefix('px:local:').rsplit(':', 1)
            text, keyboard = location_card(player, category=None if category=='home' else category, page=int(page))
        elif data.startswith('px:world:'):
            text, keyboard = map_card(player, world=True, page=int(data.removeprefix('px:world:')))
        else:
            region, page = data.removeprefix('px:mapregion:').rsplit(':', 1)
            text, keyboard = map_card(player, region=region, page=int(page))
        await query.answer()
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return
    if data.startswith(('px:gatherpreview:','px:gather:')):
        profession = data.split(':',2)[2]
        text,keyboard = gathering_preview_card(player,profession)
        await query.answer()
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return
    if data in {'px:home','px:map'}:
        if data=='px:map':
            from handlers.location import map_command
            from types import SimpleNamespace
            await map_command(SimpleNamespace(message=query.message,effective_user=query.from_user),context)
            await query.answer()
            return
        text,keyboard = build_activities(player)
        await query.answer()
        await query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
        return
    if data.startswith('px:finale:'):
        if data=='px:finale:show':
            from game.player_feedback import present_pending_feedback
            await present_pending_feedback(context.bot,player['telegram_id'],recover_presented=True,originating_query=query)
            await query.answer()
            return
        from game.player_feedback import acknowledge_feedback
        conn = get_connection()
        try:
            conn.execute('BEGIN IMMEDIATE')
            acknowledge_feedback(conn,player['telegram_id'],'chapter_finale:chapter_homecoming')
            conn.commit()
        finally:
            conn.close()
        destination = data.removeprefix('px:finale:')
        if destination=='map':
            from handlers.location import map_command
            from types import SimpleNamespace
            await map_command(SimpleNamespace(message=query.message,effective_user=query.from_user),context)
            await query.answer()
            return
        if destination=='opportunities':
            from handlers.regional import build_regional_home
            text,keyboard = build_regional_home(player)
        elif destination=='local':
            from handlers.location import build_quest_board_message
            from game.locations import get_location
            text,keyboard = build_quest_board_message(player,get_location(player['location_id']))
        else:
            from handlers.chapter import build_journal
            text,keyboard = build_journal(player)
        await query.answer()
        await query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
        return
    if data in {'px:tools'} or data.startswith(('px:tool:','px:repair:','px:replace:')):
        try:
            if data=='px:tools':
                text,keyboard = tool_list(player)
            elif data.startswith('px:tool:'):
                text,keyboard = tool_card(player,data.removeprefix('px:tool:'))
            else:
                from game.profession_tools import commit_tool_maintenance
                result = commit_tool_maintenance(player['telegram_id'],action_token=data.split(':',2)[2],replace=data.startswith('px:replace:'))
                player = dict(get_player(player['telegram_id']))
                text,keyboard = tool_card(player,result['quote']['profession_key']) if result.get('quote') else tool_list(player)
        except ActionRejected:
            await query.answer(t('professions.stale_action',lang),show_alert=True)
            return
        await query.answer()
        await query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
        return
    kind,session = None,None
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if data.startswith('px:travel:'):
            token = data.removeprefix('px:travel:')
            prior = conn.execute('SELECT * FROM player_travel_sessions WHERE player_id=? AND start_request_id=?',(player['telegram_id'],'ui:'+token)).fetchone()
            if prior:
                session = dict(prior)
            else:
                intent = json.loads(consume_action(conn,player['telegram_id'],'pxe1_travel',token))
                if intent.get('schema_version')!=1 or intent.get('catalog_version')!=2:
                    raise ActionRejected('stale_action')
                session = start_travel_session(conn,player['telegram_id'],intent['preview'],request_id='ui:'+token,now_ms=now_ms)
            kind = 'travel'
        elif data.startswith('px:gatherstart:'):
            token = data.removeprefix('px:gatherstart:')
            prior = conn.execute('SELECT * FROM player_gathering_sessions WHERE player_id=? AND start_request_id=?',
                                 (player['telegram_id'],'ui:'+token)).fetchone()
            if prior: session = dict(prior)
            else:
                from game.gathering_runtime import _source_snapshot
                from game.profession_tools import get_tool
                intent = json.loads(consume_action(conn,player['telegram_id'],'pxe1_gather_start',token))
                if intent.get('schema_version')!=1 or intent.get('catalog_version')!=2:
                    raise ActionRejected('stale_action')
                profession = intent['profession_key']
                tool = get_tool(conn,player['telegram_id'],profession)
                if not tool or tool['revision']!=intent['tool_revision'] or _source_snapshot(player['location_id'],profession)!=intent['source_snapshot']:
                    raise ActionRejected('stale_action')
                result = start_gathering_session(conn,player['telegram_id'],profession,location_id=intent['location_id'],
                                                request_id='ui:'+token,now_ms=now_ms)
                session = result['session']
            kind = 'gather'
        elif data.startswith('px:stop:'):
            _,_,kind,session_id = data.split(':',3)
            if kind not in {'travel','gather'}:
                raise ActionRejected('stale_action')
            operation = stop_travel_session if kind=='travel' else stop_gathering_session
            session = operation(conn,player['telegram_id'],session_id,now_ms=now_ms)
        conn.commit()
    except (ActionRejected,ValueError,KeyError) as exc:
        conn.rollback()
        await query.answer(t('professions.stale_action',lang),show_alert=True)
        return
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    player = dict(get_player(player['telegram_id']))
    if session:
        text,keyboard = activity_card(player,session,kind,now_ms=now_ms)
        await query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
        conn = get_connection()
        try:
            conn.execute('''INSERT INTO player_pxe1_ui(player_id,schema_version,surface_kind,surface_ref,chat_id,message_id,surface_revision,updated_ms)
                VALUES (?,1,?,?,?,?,?,?) ON CONFLICT(player_id) DO UPDATE SET surface_kind=excluded.surface_kind,
                surface_ref=excluded.surface_ref,chat_id=excluded.chat_id,message_id=excluded.message_id,
                surface_revision=excluded.surface_revision,updated_ms=excluded.updated_ms''',
                (player['telegram_id'],kind,session['session_id'],query.message.chat_id,query.message.message_id,session['revision'],now_ms))
            conn.commit()
        finally:
            conn.close()
    else:
        text,keyboard = build_activities(player)
        await query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
    await query.answer()


async def deliver_activity_updates(bot,results):
    # Tick rows are authoritative; one edited card per changed session per run.
    changed = {}
    for result in results:
        session = result.get('session') or result
        if session.get('session_id'):
            changed[session['session_id']] = session
    conn = get_connection()
    try:
        rows = []
        for session_id in changed:
            for table,kind in (('player_travel_sessions','travel'),('player_gathering_sessions','gather')):
                row = conn.execute(f'SELECT * FROM {table} WHERE session_id=?',(session_id,)).fetchone()
                if row:
                    rows.append((dict(row),kind))
                    break
    finally:
        conn.close()
    for session,kind in rows:
        player = dict(get_player(session['player_id']))
        text,keyboard = activity_card(player,session,kind)
        from game.player_feedback import inline_feedback,acknowledge_presented_facts
        text,keys = inline_feedback(player['telegram_id'],player.get('lang','ru'),text)
        delivered = await present_surface(bot,player['telegram_id'],text,keyboard,kind=kind,ref=session['session_id'],revision=session['revision'])
        if delivered:
            acknowledge_presented_facts(player['telegram_id'],keys)
