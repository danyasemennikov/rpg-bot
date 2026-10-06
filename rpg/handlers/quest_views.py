"""Compact quest-board projections; quest_board owns every mutation."""

from html import escape
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from game.action_receipts import issue_actions
from game.i18n import get_location_name, t
from game.locations import resolve_location_id
from game.player_ui import validate_surface
from game.quest_board import build_contract_title, get_player_hunt_contract_state, list_hunt_contracts_for_player


def board_card(player, location, *, category=None, page=0):
    lang = player.get('lang', 'ru')
    split = list_hunt_contracts_for_player(location_id=location['id'], player_id=player['telegram_id'], lang=lang)
    state = get_player_hunt_contract_state(player['telegram_id'])
    active = state and state['status'] in {'active', 'completed'}
    lines = [t('location.quest_board_title', lang, board_name=escape(get_location_name(location['id'], lang)))]
    rows = []
    if category:
        entries = split['locked'] if category == 'locked' else split['available']
        pages = max(1, (len(entries)+5)//6)
        page = min(max(0, int(page)), pages-1)
        lines.append(t('location.quest_board_locked_title' if category == 'locked' else 'location.quest_board_available_title', lang))
        for entry in entries[page*6:(page+1)*6]:
            contract = entry['contract'] if category == 'locked' else entry
            label = build_contract_title(contract, lang)
            lines.append(('🔒 ' if category == 'locked' else '• ') + escape(label))
            rows.append([InlineKeyboardButton(label, callback_data=f'quest_board_detail_{contract.contract_key}')])
        if not entries:
            lines.append(t('location.quest_board_empty', lang))
        nav = []
        if page:
            nav.append(InlineKeyboardButton('◀️', callback_data=f'quest_board_list_{category}_{page-1}'))
        if page+1 < pages:
            nav.append(InlineKeyboardButton('▶️', callback_data=f'quest_board_list_{category}_{page+1}'))
        if nav:
            rows.append(nav)
        rows.append([InlineKeyboardButton(t('gear.back_btn', lang), callback_data='quest_board')])
    else:
        if active:
            contract = state['contract']
            status = t('location.quest_board_status_ready' if state['status'] == 'completed' else 'location.quest_board_status_active', lang)
            lines.append(f'{status} · {escape(build_contract_title(contract, lang))}')
            if contract.objectives:
                done = sum(state.get('objective_progress', {}).get(o.key, 0) >= o.required for o in contract.objectives)
                done += int(bool(contract.required_kills and state['progress_kills'] >= contract.required_kills))
                total = len(contract.objectives) + int(bool(contract.required_kills))
                lines.append(t('pxe1.objectives_count', lang, done=done, total=total))
            else:
                lines.append(f"{state['progress_kills']}/{contract.required_kills}")
            if state['status'] == 'completed':
                places = contract.claim_locations or contract.board_locations
                if resolve_location_id(location['id']) in {resolve_location_id(k) for k in places}:
                    token = issue_actions(player['telegram_id'], 'contract_claim', [contract.contract_key])[contract.contract_key]
                    rows.append([InlineKeyboardButton(t('location.quest_board_claim_btn', lang), callback_data=f'quest_board_claim_{token}')])
                else:
                    rows.append([InlineKeyboardButton(t('pxe1.route_to', lang, name=get_location_name(places[0], lang)), callback_data=f'goto_{places[0]}')])
            rows.append([InlineKeyboardButton(t('pxe1.open_assignment', lang), callback_data='alpha_assignment')])
        else:
            chapter = next((c for c in split['available'] if c.chapter_order), None)
            if chapter:
                lines.append(escape(build_contract_title(chapter, lang)))
                rows.append([InlineKeyboardButton(t('pxe1.open_assignment', lang), callback_data=f'quest_board_detail_{chapter.contract_key}')])
            else:
                lines.append(t('location.quest_board_no_active', lang))
        if split['available']:
            rows.append([InlineKeyboardButton(t('pxe1.available_contracts', lang, count=len(split['available'])), callback_data='quest_board_list_available_0')])
        if split['locked']:
            rows.append([InlineKeyboardButton(t('location.quest_board_locked_title', lang), callback_data='quest_board_list_locked_0')])
        rows.append([InlineKeyboardButton(t('gear.back_btn', lang), callback_data='quest_board_back')])
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines), keyboard, list_view=bool(category))
    return '\n'.join(lines), keyboard


def board_detail(player, location, contract_key):
    from game.quest_board import build_contract_row, get_hunt_contract
    contract = get_hunt_contract(contract_key)
    if not contract:
        return board_card(player, location)
    lang = player.get('lang', 'ru')
    split = list_hunt_contracts_for_player(location_id=location['id'], player_id=player['telegram_id'], lang=lang)
    state = get_player_hunt_contract_state(player['telegram_id'])
    if state and state['status'] in {'active', 'completed'} and state['contract_key'] == contract_key:
        from handlers.chapter import build_assignment
        return build_assignment(player)
    rows = []
    text = build_contract_row(contract, lang)
    locked = next((r for r in split['locked'] if r['contract'].contract_key == contract_key), None)
    if locked:
        text += '\n' + escape(locked['reason'])
    elif contract in split['available']:
        if not state or state['status'] not in {'active', 'completed'}:
            rows.append([InlineKeyboardButton(t('pxe1.accept_assignment', lang), callback_data=f'quest_board_accept_{contract_key}')])
        else:
            text += '\n' + t('pxe1.chapter_slot_busy', lang)
    rows.append([InlineKeyboardButton(t('gear.back_btn', lang), callback_data='quest_board')])
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface(text, keyboard, long_detail=True)
    return text, keyboard
