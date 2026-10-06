"""Journal, quartermaster, workshop and harvesting entry points for chapter one."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from html import escape

from database import get_connection, get_player, list_gathering_profession_states
from game.action_receipts import ActionRejected, issue_actions
from game.alpha_schema import ensure_crafting_professions
from game.crafting_runtime import LIVE_RECIPE_IDS, get_recipe, craft_recipe
from game.hunting import harvestable_victory_page, list_harvestable_victories, harvest_victory
from game.i18n import t, get_item_name, get_location_name, get_mob_name
from game.locations import get_location
from game.quest_board import (
    get_player_hunt_contract_state, get_chapter_contracts, get_contract_history,
    build_objective_lines, build_contract_title,
)
from game.starter_kit import STARTER_WEAPONS, has_starter_kit, claim_starter_kit
from game.gear_progression import get_equipment_goal


def _button(text, data):
    return [InlineKeyboardButton(text, callback_data=data)]


def _assignment(player):
    state = get_player_hunt_contract_state(player['telegram_id'])
    if state and state['status'] in {'active', 'completed'}:
        return state['contract'], state
    history = get_contract_history(player['telegram_id'])
    return next((c for c in get_chapter_contracts() if c.contract_key not in history), None), None


def _assignment_rows(player, contract, state):
    lang = player.get('lang', 'ru')
    rows = []
    destinations = contract.claim_locations or contract.board_locations
    if state and state['status'] == 'completed':
        from game.locations import resolve_location_id
        if resolve_location_id(player['location_id']) in {resolve_location_id(k) for k in destinations}:
            token = issue_actions(player['telegram_id'], 'contract_claim', [contract.contract_key])[contract.contract_key]
            rows.append(_button(t('location.quest_board_claim_btn', lang), f'quest_board_claim_{token}'))
        else:
            rows.append(_button(t('pxe1.route_to', lang, name=get_location_name(destinations[0], lang)), f'goto_{destinations[0]}'))
    elif not state:
        from game.locations import resolve_location_id
        if resolve_location_id(player['location_id']) in {resolve_location_id(k) for k in contract.board_locations}:
            rows.append(_button(t('pxe1.accept_assignment', lang), f'quest_board_accept_{contract.contract_key}'))
        else:
            rows.append(_button(t('pxe1.route_to', lang, name=get_location_name(contract.board_locations[0], lang)), f'goto_{contract.board_locations[0]}'))
    if state:
        from game.profession_recipes import ACTIVE_RECIPES
        recipe = next((r for o in contract.objectives if o.action == 'craft'
                       and state.get('objective_progress', {}).get(o.key, 0) < o.required
                       for r in ACTIVE_RECIPES if r.output_spec.item_id == o.target), None)
        if recipe:
            rows.append(_button(t('pxe1.required_recipe', lang), f'pe_r:{recipe.recipe_id}'))
        if any(o.action == 'equip' and state.get('objective_progress', {}).get(o.key, 0) < o.required for o in contract.objectives):
            rows.append(_button(t('keyboard.inventory', lang), 'inv_tab_armor'))
    return rows


def build_journal(player: dict, *, show_completed_history: bool = False):
    if show_completed_history:
        return build_history(player)
    lang = player.get('lang', 'ru')
    if 'chapter_homecoming' in get_contract_history(player['telegram_id']):
        from handlers.regional import build_regional_home
        return build_regional_home(player)
    contract, state = _assignment(player)
    lines = [t('chapter.title', lang), escape(build_contract_title(contract, lang))]
    if state:
        lines.extend(build_objective_lines(state, lang))
        if not contract.chapter_order:
            lines.append(t('pxe1.chapter_slot_busy', lang))
    else:
        lines.append(t('pxe1.assignment_available', lang))
    places = ' / '.join(get_location_name(k, lang) for k in (contract.claim_locations or contract.board_locations))
    lines.append(t('chapter.report_to', lang, places=escape(places)))
    rows = [_button(t('pxe1.open_assignment', lang), 'alpha_assignment')]
    rows.extend(_assignment_rows(player, contract, state)[:2])
    rows.append([InlineKeyboardButton(t('rav1.nav.opportunities', lang), callback_data='rv:v:h:0:all'),
                 InlineKeyboardButton(t('rav1.nav.history', lang), callback_data='alpha_history')])
    from game.player_ui import validate_surface
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines), keyboard)
    return '\n'.join(lines), keyboard


def build_assignment(player, *, story=False):
    lang = player.get('lang', 'ru')
    contract, state = _assignment(player)
    if not contract:
        return build_journal(player)
    lines = [f'<b>{escape(build_contract_title(contract, lang))}</b>']
    if story:
        lines.append(t(f'chapter.story_{contract.chapter_order}', lang) if contract.chapter_order else t('pxe1.hunt_purpose', lang))
        rows = [_button(t('gear.back_btn', lang), 'alpha_assignment')]
    else:
        preview = state or {'contract': contract, 'progress_kills': 0, 'objective_progress': {}}
        lines.extend(build_objective_lines(preview, lang))
        places = ' / '.join(get_location_name(k, lang) for k in (contract.claim_locations or contract.board_locations))
        lines.append(t('chapter.report_to', lang, places=escape(places)))
        rows = _assignment_rows(player, contract, state)
        rows.append([InlineKeyboardButton(t('pxe1.sources', lang), callback_data='alpha_sources'),
                     InlineKeyboardButton(t('pxe1.story', lang), callback_data='alpha_story')])
        if state and state['status'] == 'active':
            rows.append(_button(t('pxe1.more', lang), 'alpha_assignment_more'))
        rows.append(_button(t('gear.back_btn', lang), 'alpha_home'))
    keyboard = InlineKeyboardMarkup(rows)
    from game.player_ui import validate_surface
    validate_surface('\n'.join(lines), keyboard, long_detail=story)
    return '\n'.join(lines), keyboard


def build_assignment_more(player):
    contract, state = _assignment(player)
    if not state or state['status'] != 'active':
        return build_assignment(player)
    lang = player.get('lang', 'ru')
    token = issue_actions(player['telegram_id'], 'contract_abandon', [contract.contract_key])[contract.contract_key]
    return t('pxe1.abandon_warning', lang), InlineKeyboardMarkup([
        _button(t('location.quest_board_abandon_btn', lang), f'quest_board_abandon_{token}'),
        _button(t('gear.back_btn', lang), 'alpha_assignment')])


def build_assignment_sources(player):
    from game.profession_resources import ENVIRONMENTAL_SOURCES
    from game.travel_runtime import preview_travel
    contract, state = _assignment(player)
    if not contract:
        return build_journal(player)
    lang = player.get('lang', 'ru')
    candidates = []
    conn = get_connection()
    try:
        for objective in contract.objectives:
            if objective.action != 'gather' or (state and state.get('objective_progress', {}).get(objective.key, 0) >= objective.required):
                continue
            sources = [(chance, location_id) for location_id, entries in ENVIRONMENTAL_SOURCES.items()
                       if not objective.location_ids or location_id in objective.location_ids
                       for item_id, chance in entries if item_id == objective.target]
            for chance, location_id in sorted(sources, key=lambda source: (-source[0], source[1])):
                try:
                    if location_id != player['location_id']:
                        preview_travel(conn, player['telegram_id'], location_id)
                except (ValueError, ActionRejected):
                    continue
                candidates.append((get_item_name(objective.target, lang), location_id))
                break
    finally:
        conn.close()
    if contract.required_kills and (not state or state['progress_kills'] < contract.required_kills):
        candidates.extend((get_mob_name(contract.target_mob_id, lang), k) for k in contract.target_location_ids[:1])
    if any(o.action == 'harvest' for o in contract.objectives):
        candidates.append((t('chapter.harvest', lang), None))
    candidates = candidates[:6]
    lines = [t('pxe1.sources', lang)]
    rows = []
    for label, place in candidates:
        if place:
            lines.append(f'{escape(label)} · {escape(get_location_name(place, lang))}')
            rows.append(_button(get_location_name(place, lang), f'goto_{place}' if place != player['location_id'] else 'px:home'))
        else:
            rows.append(_button(label, 'alpha_harvest'))
    if not candidates:
        lines.append(t('pxe1.source_map_hint', lang))
    rows.append(_button(t('keyboard.map', lang), 'px:map'))
    rows.append(_button(t('gear.back_btn', lang), 'alpha_assignment'))
    keyboard = InlineKeyboardMarkup(rows)
    from game.player_ui import validate_surface
    validate_surface('\n'.join(lines), keyboard, list_view=True)
    return '\n'.join(lines), keyboard


def build_history(player, page=0, *, chapter_story=False):
    from game.quest_board import get_hunt_contract
    lang = player.get('lang', 'ru')
    history = get_contract_history(player['telegram_id'])
    if chapter_story:
        contracts = [c for c in get_chapter_contracts() if c.contract_key in history]
        lines = [t('chapter.title', lang)]
        for contract in contracts:
            lines += [escape(build_contract_title(contract, lang)), t(f'chapter.story_{contract.chapter_order}', lang)]
        if 'chapter_homecoming' in history:
            lines.append(t('chapter.epilogue', lang))
        return '\n\n'.join(lines), InlineKeyboardMarkup([_button(t('gear.back_btn', lang), 'alpha_history')])
    conn = get_connection()
    try:
        records = [dict(r) for r in conn.execute('SELECT contract_key,claimed_at FROM player_contract_history WHERE player_id=? ORDER BY claimed_at DESC,contract_key', (player['telegram_id'],))]
    finally:
        conn.close()
    chapter_keys = {c.contract_key for c in get_chapter_contracts()}
    archive = []
    if chapter_keys & history:
        chapter = [r for r in records if r['contract_key'] in chapter_keys]
        archive.append({'contract_key': 'chapter', 'claimed_at': max((r['claimed_at'] or '' for r in chapter), default='')})
    archive.extend(r for r in records if r['contract_key'] not in chapter_keys)
    archive.sort(key=lambda r: (r['claimed_at'] or '', r['contract_key']), reverse=True)
    pages = max(1, (len(archive)+5)//6)
    page = min(max(0, int(page)), pages-1)
    lines, rows = [t('rav1.nav.history', lang)], []
    for record in archive[page*6:(page+1)*6]:
        contract = get_hunt_contract(record['contract_key'])
        label = t('chapter.title', lang) if record['contract_key'] == 'chapter' else build_contract_title(contract, lang) if contract else t('pxe1.earlier_assignment', lang)
        lines.append(f'✓ {escape(label)}')
        if record['contract_key'] == 'chapter':
            rows.append(_button(label, 'alpha_history_chapter'))
    if not archive:
        lines.append(t('pxe1.history_empty', lang))
    nav = []
    if page:
        nav.append(InlineKeyboardButton('◀️', callback_data=f'alpha_history:{page-1}'))
    if page+1 < pages:
        nav.append(InlineKeyboardButton('▶️', callback_data=f'alpha_history:{page+1}'))
    if nav:
        rows.append(nav)
    rows.append(_button(t('rav1.nav.resolved', lang), 'rv:v:s:0:all'))
    rows.append(_button(t('gear.back_btn', lang), 'alpha_home'))
    return '\n'.join(lines), InlineKeyboardMarkup(rows)


def build_workshop(player: dict):
    """Legacy callback refreshes into the PEV1 overview; mutation stays token-bound."""
    from handlers.professions import build_overview
    return build_overview(player)


def build_harvest_menu(player: dict, page: int = 0):
    import json
    lang = player.get('lang', 'ru')
    victories, page, pages = harvestable_victory_page(player['telegram_id'], page=page)
    payloads = [json.dumps({'encounter_id':v['encounter_id'],'unit_id':v['unit_id'],'item_id':v['item_id']},
                           sort_keys=True,separators=(',',':')) for v in victories]
    tokens = issue_actions(player['telegram_id'], 'harvest', payloads) if payloads else {}
    rows = [_button(t('chapter.harvest_button', lang, name=get_item_name(v['item_id'], lang)),
                    f"pe_a:{tokens[payload]}") for v, payload in zip(victories, payloads)]
    nav = []
    if page:
        nav.append(InlineKeyboardButton('◀️', callback_data=f'alpha_harvest:{page-1}'))
    if page + 1 < pages:
        nav.append(InlineKeyboardButton('▶️', callback_data=f'alpha_harvest:{page+1}'))
    if nav:
        rows.append(nav)
    rows.append(_button(t('chapter.journal', lang), 'alpha_home'))
    return t('chapter.harvest_intro' if victories else 'chapter.harvest_empty', lang), InlineKeyboardMarkup(rows)


def build_sell_menu(player: dict, page: int = 0):
    from handlers.shop_views import sell_categories
    return sell_categories(player)


async def journal_command(update, context):
    player = get_player(update.effective_user.id)
    if not player:
        await update.message.reply_text(t('common.no_character', 'ru'))
        return
    from game.player_feedback import present_pending_feedback
    await present_pending_feedback(context.bot,update.effective_user.id,recover_presented=True)
    from game.pve_reward_settlement import recover_player_settlements
    recovery = recover_player_settlements(int(player['telegram_id']))
    player = get_player(update.effective_user.id)
    text, keyboard = build_journal(dict(player))
    notices = []
    if recovery['recovered']:
        notices.append(t('gear.settlement_recovered', player['lang'], count=len(recovery['recovered'])))
    if recovery['pending']:
        notices.append(t('gear.settlement_pending', player['lang']))
    notices.extend(t('gear.legacy_review', player['lang'], id=encounter_id) for encounter_id in recovery['legacy_review'])
    if notices:
        text = '\n'.join(notices) + '\n\n' + text
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')


async def handle_chapter_buttons(update, context):
    query = update.callback_query
    row = get_player(query.from_user.id)
    if not row:
        await query.answer(t('common.no_character', 'ru'), show_alert=True)
        return
    player, data = dict(row), query.data
    player_id, lang = player['telegram_id'], player.get('lang', 'ru')
    status = None
    answered = False
    view = build_journal
    if data == 'alpha_home':
        from game.pve_reward_settlement import recover_player_settlements
        recovery = recover_player_settlements(player_id)
        if recovery['legacy_review']:
            await query.answer(t('gear.legacy_review', lang, id=recovery['legacy_review'][0]), show_alert=True)
            answered = True
        elif recovery['recovered']:
            await query.answer(t('gear.settlement_recovered', lang, count=len(recovery['recovered'])), show_alert=True)
            answered = True
        elif recovery['pending']:
            await query.answer(t('gear.settlement_pending', lang), show_alert=True)
            answered = True
    if data == 'alpha_history':
        view = lambda current: build_journal(current, show_completed_history=True)
    elif data.startswith('alpha_history:'):
        view = lambda current: build_history(current, int(data.split(':', 1)[1]))
    elif data == 'alpha_history_chapter':
        view = lambda current: build_history(current, chapter_story=True)
    elif data == 'alpha_assignment':
        view = build_assignment
    elif data == 'alpha_story':
        view = lambda current: build_assignment(current, story=True)
    elif data == 'alpha_sources':
        view = build_assignment_sources
    elif data == 'alpha_assignment_more':
        view = build_assignment_more
    if data.startswith('alpha_kit_'):
        status = claim_starter_kit(player_id, data.removeprefix('alpha_kit_'))['status']
    elif data == 'alpha_workshop':
        view = build_workshop
    elif data.startswith('alpha_craft_'):
        result = craft_recipe(player_id, '', action_token=data.removeprefix('alpha_craft_'))
        status, view = result.status, build_workshop
    elif data == 'alpha_harvest' or data.startswith('alpha_harvest:'):
        page = int(data.split(':', 1)[1]) if ':' in data else 0
        text, keyboard = build_harvest_menu(dict(get_player(player_id)), page)
        await query.answer()
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return
    elif data.startswith('alpha_extract_'):
        # Legacy victory buttons only refresh the explicit, token-bound choice
        # preview. They never mutate from the encounter ID alone.
        view = build_harvest_menu
    elif data == 'alpha_sell' or data.startswith('alpha_sellone_') or data.startswith('alpha_sell_page_'):
        location = get_location(player['location_id']) or {}
        if 'shop' not in location.get('services', []) and not data.startswith('alpha_sellone_'):
            status = 'wrong_location'
        else:
            view = build_sell_menu
            if data.startswith('alpha_sell_page_'):
                page = int(data.removeprefix('alpha_sell_page_'))
                text, keyboard = build_sell_menu(dict(get_player(player_id)), page)
                await query.answer()
                await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
                return
            if data.startswith('alpha_sellone_'):
                from handlers.inventory import try_sell_inventory_item
                result = try_sell_inventory_item(player_id, data.removeprefix('alpha_sellone_'))
                from handlers.shop_views import sale_preview,result_card
                keys = []
                if result['status']=='confirmation_required':
                    quote = result['quote']
                    text,keyboard = sale_preview(dict(get_player(player_id)),f"i{quote['entry_id']}",confirmation_quote=quote)
                elif result['status']=='sold':
                    # Historical receipts may predate the compact result fields.
                    result = {**result,'item_id':result['consumed'][0]['item_id'],
                              'quantity':result['consumed'][0]['quantity']}
                    text,keyboard,keys = result_card(dict(get_player(player_id)),result)
                else:
                    await query.answer(t('pxe1.shop.stale',lang),show_alert=True)
                    return
                await query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
                if keys:
                    from game.player_feedback import acknowledge_presented_facts
                    acknowledge_presented_facts(player_id,keys)
                await query.answer()
                return
    if status:
        await query.answer(t(f'chapter.{status}', lang), show_alert=True)
    elif not answered:
        await query.answer()
    text, keyboard = view(dict(get_player(player_id)))
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
