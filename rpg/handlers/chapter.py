"""Journal, quartermaster, workshop and harvesting entry points for chapter one."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from database import get_connection, get_player, list_gathering_profession_states
from game.action_receipts import issue_actions
from game.alpha_schema import ensure_crafting_professions
from game.crafting_runtime import LIVE_RECIPE_IDS, get_recipe, craft_recipe
from game.hunting import list_harvestable_victories, harvest_victory
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


def build_journal(player: dict):
    player_id, lang = player['telegram_id'], player.get('lang', 'ru')
    history = get_contract_history(player_id)
    contracts = get_chapter_contracts()
    lines = [t('chapter.title', lang), t('chapter.premise', lang), '']
    lines.append(t('chapter.progress', lang, done=sum(c.contract_key in history for c in contracts), total=len(contracts)))
    for contract in contracts:
        mark = '✓' if contract.contract_key in history else '○'
        lines.append(f'{mark} {build_contract_title(contract, lang)}')
    state = get_player_hunt_contract_state(player_id)
    if state and state['status'] in {'active', 'completed'}:
        contract = state['contract']
        lines += ['', build_contract_title(contract, lang)]
        if contract.chapter_order:
            lines.append(t(f'chapter.story_{contract.chapter_order}', lang))
        lines.extend(build_objective_lines(state, lang))
        places = ' / '.join(get_location_name(key, lang) for key in (contract.claim_locations or contract.board_locations))
        lines.append(t('chapter.report_to', lang, places=places))
    else:
        next_contract = next((c for c in contracts if c.contract_key not in history), None)
        lines.append(t(f'chapter.story_{next_contract.chapter_order}', lang) if next_contract else t('chapter.epilogue', lang))
        if next_contract:
            places = ' / '.join(get_location_name(key, lang) for key in next_contract.board_locations)
            lines.append(t('chapter.accept_at', lang, places=places))
    rows = []
    if not has_starter_kit(player_id):
        lines += ['', t('chapter.kit_intro', lang)]
        if player['location_id'] == 'capital_city':
            rows.extend(_button(get_item_name(key, lang), f'alpha_kit_{key}') for key in STARTER_WEAPONS)
    lines += ['', t('chapter.professions', lang)]
    rows.append(_button(t('professions.title', lang).replace('<b>', '').replace('</b>', ''), 'pe_o:0'))
    for row in list_gathering_profession_states(player_id):
        key = row['profession_key']
        lines.append(t('chapter.profession_row', lang, name=t(f'professions.names.{key}', lang),
                       level=row['level'], exp=row['exp'], needed=row['level'] * 50 if row['level'] < 20 else '—'))
    conn = get_connection()
    try:
        ensure_crafting_professions(conn, player_id)
        conn.commit()
        for row in conn.execute('SELECT * FROM player_crafting_professions WHERE player_id=? ORDER BY profession_key', (player_id,)):
            lines.append(t('chapter.profession_row', lang, name=t(f"professions.names.{row['profession_key']}", lang),
                           level=row['level'], exp=row['exp'], needed=row['level'] * 50 if row['level'] < 20 else '—'))
    finally:
        conn.close()
    location = get_location(player['location_id']) or {}
    if 'chapter_homecoming' in history:
        goal = get_equipment_goal(player_id)
        next_step = t('gear.journal_goal_step', lang, name=get_item_name(goal, lang)) if goal else t('gear.journal_choose_goal', lang)
        lines += ['', t('gear.journal_next_step', lang, step=next_step)]
        rows.append(_button(t('gear.catalog_btn', lang), 'inv_catalog'))
        rows.append(_button(t('gear.receipts_btn', lang), 'inv_receipts'))
    if 'quest_board' in location.get('services', []):
        rows.append(_button(t('location.quests_btn', lang), 'quest_board'))
    if 'craftsmen_guild' in location.get('services', []):
        rows.append(_button(t('chapter.workshop', lang), 'pe_o:0'))
    rows.append(_button(t('chapter.harvest', lang), 'alpha_harvest'))
    return '\n'.join(lines), InlineKeyboardMarkup(rows)


def build_workshop(player: dict):
    """Legacy callback refreshes into the PEV1 overview; mutation stays token-bound."""
    from handlers.professions import build_overview
    return build_overview(player)


def build_harvest_menu(player: dict):
    import json
    lang = player.get('lang', 'ru')
    victories = list_harvestable_victories(player['telegram_id'])
    payloads = [json.dumps({'encounter_id':v['encounter_id'],'unit_id':v['unit_id'],'item_id':v['item_id']},
                           sort_keys=True,separators=(',',':')) for v in victories]
    tokens = issue_actions(player['telegram_id'], 'harvest', payloads) if payloads else {}
    rows = [_button(t('chapter.harvest_button', lang, name=get_item_name(v['item_id'], lang)),
                    f"pe_a:{tokens[payload]}") for v, payload in zip(victories, payloads)]
    rows.append(_button(t('chapter.journal', lang), 'alpha_home'))
    return t('chapter.harvest_intro' if victories else 'chapter.harvest_empty', lang), InlineKeyboardMarkup(rows)


def build_sell_menu(player: dict, page: int = 0):
    lang, player_id = player.get('lang', 'ru'), player['telegram_id']
    conn = get_connection()
    try:
        candidates = conn.execute('''SELECT inv.id, inv.item_id, inv.quantity FROM inventory inv
            JOIN items i ON i.item_id=inv.item_id WHERE inv.telegram_id=?
            AND i.sell_price>0 AND inv.quantity>0 ORDER BY inv.item_id''',
                             (player_id,)).fetchall()
    finally:
        conn.close()
    from game.items_data import get_item
    from game.seed import PEV1_CONSUMABLE_IDS
    items = [row for row in candidates if get_item(row['item_id'])['item_type'] == 'material' or row['item_id'] in PEV1_CONSUMABLE_IDS]
    pages = max(1, (len(items) + 7) // 8); page = min(max(0, int(page)), pages - 1)
    items = items[page * 8:(page + 1) * 8]
    payloads = [f"{row['id']}:{row['quantity']}" for row in items]
    tokens = issue_actions(player_id, 'sell', payloads)
    rows = [_button(t('chapter.sell_button', lang, name=get_item_name(row['item_id'], lang),
                      price=get_item(row['item_id'])['sell_price'], qty=row['quantity']),
                    f'alpha_sellone_{tokens[payload]}') for row, payload in zip(items, payloads)]
    nav = []
    if page: nav.append(InlineKeyboardButton('◀️', callback_data=f'alpha_sell_page_{page-1}'))
    if page + 1 < pages: nav.append(InlineKeyboardButton('▶️', callback_data=f'alpha_sell_page_{page+1}'))
    if nav: rows.append(nav)
    rows.append(_button(t('location.shop_btn', lang), 'shop'))
    return t('chapter.sell_intro', lang), InlineKeyboardMarkup(rows)


async def journal_command(update, context):
    player = get_player(update.effective_user.id)
    if not player:
        await update.message.reply_text(t('common.no_character', 'ru'))
        return
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
    if data.startswith('alpha_kit_'):
        status = claim_starter_kit(player_id, data.removeprefix('alpha_kit_'))['status']
    elif data == 'alpha_workshop':
        view = build_workshop
    elif data.startswith('alpha_craft_'):
        result = craft_recipe(player_id, '', action_token=data.removeprefix('alpha_craft_'))
        status, view = result.status, build_workshop
    elif data == 'alpha_harvest':
        view = build_harvest_menu
    elif data.startswith('alpha_extract_'):
        # Legacy victory buttons only refresh the explicit, token-bound choice
        # preview. They never mutate from the encounter ID alone.
        view = build_harvest_menu
    elif data == 'alpha_sell' or data.startswith('alpha_sellone_') or data.startswith('alpha_sell_page_'):
        location = get_location(player['location_id']) or {}
        if 'shop' not in location.get('services', []):
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
                status = result['status']
    if status:
        await query.answer(t(f'chapter.{status}', lang), show_alert=True)
    elif not answered:
        await query.answer()
    text, keyboard = view(dict(get_player(player_id)))
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
