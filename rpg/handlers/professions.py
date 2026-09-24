"""Paginated PEV1 profession journal, handbook, learning, and crafting UI."""

from __future__ import annotations

from html import escape
from math import ceil
import json
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from database import get_connection, get_player
from game.action_receipts import issue_actions
from game.crafting_runtime import craft_recipe
from game.economy_actions import get_receipt, list_receipts
from game.i18n import get_item_name, get_location_name, t
from game.locations import get_location
from game.profession_recipes import (
    ACTIVE_RECIPES, get_recipe, parse_recipe_intent, recipe_consumers,
    recipe_intent_payload,
)
from game.profession_resources import ENVIRONMENTAL_SOURCES, HARVEST_MANIFEST, RESOURCES
from game.profession_schema import CRAFTING_PROFESSION_KEYS, GATHERING_PROFESSION_KEYS, ensure_profession_rows
from game.recipe_knowledge import known_recipe_ids, learn_recipe
from game.hunting import harvest_victory

PAGE_SIZE = 6


def _kb(rows):
    return InlineKeyboardMarkup(rows)


def _state(player_id: int):
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        ensure_profession_rows(conn, player_id)
        gathering = {r['profession_key']: dict(r) for r in conn.execute(
            'SELECT * FROM player_gathering_professions WHERE telegram_id=?', (player_id,))}
        crafting = {r['profession_key']: dict(r) for r in conn.execute(
            'SELECT * FROM player_crafting_professions WHERE player_id=?', (player_id,))}
        inventory = {r['item_id']: int(r['qty']) for r in conn.execute(
            'SELECT item_id, SUM(quantity) qty FROM inventory WHERE telegram_id=? GROUP BY item_id', (player_id,))}
        conn.commit()
        return gathering, crafting, inventory
    finally:
        conn.close()


def _page(values, page, size=PAGE_SIZE):
    pages = max(1, ceil(len(values) / size))
    page = min(max(0, int(page)), pages - 1)
    return values[page * size:(page + 1) * size], page, pages


def _recipe_name(recipe, lang: str) -> str:
    band = 1 if recipe.required_level <= 2 else recipe.required_level
    return f"{get_item_name(recipe.output_spec.item_id, lang)} · {t(f'professions.band_{band}', lang)}"


def build_overview(player: dict, page: int = 0):
    lang, player_id = player.get('lang', 'ru'), int(player['telegram_id'])
    gathering, crafting, _ = _state(player_id)
    keys = list(GATHERING_PROFESSION_KEYS + CRAFTING_PROFESSION_KEYS)
    rows_on_page, page, pages = _page(keys, page)
    lines = [t('professions.title', lang)]
    rows = []
    for key in rows_on_page:
        state = gathering.get(key) or crafting.get(key)
        name = t(f'professions.names.{key}', lang)
        needed = int(state['level']) * 50 if int(state['level']) < 20 else '—'
        lines.append(f"• {escape(name)} — {t('professions.level', lang, level=state['level'], exp=state['exp'], needed=needed)}")
        rows.append([InlineKeyboardButton(name, callback_data=f'pe_p:{key}')])
    nav = []
    if page:
        nav.append(InlineKeyboardButton('◀️', callback_data=f'pe_o:{page-1}'))
    if page + 1 < pages:
        nav.append(InlineKeyboardButton('▶️', callback_data=f'pe_o:{page+1}'))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(t('professions.receipts', lang), callback_data='pe_h:0')])
    return '\n'.join(lines), _kb(rows)


def build_profession(player: dict, key: str):
    lang, player_id = player.get('lang', 'ru'), int(player['telegram_id'])
    gathering, crafting, _ = _state(player_id)
    state = gathering.get(key) or crafting.get(key)
    if not state:
        return build_overview(player)
    name = t(f'professions.names.{key}', lang)
    needed = int(state['level']) * 50 if int(state['level']) < 20 else '—'
    lines = [f'<b>{escape(name)}</b>', t('professions.level', lang, level=state['level'], exp=state['exp'], needed=needed)]
    rows = []
    if key in CRAFTING_PROFESSION_KEYS:
        for filter_key in ('known', 'learnable', 'locked'):
            rows.append([InlineKeyboardButton(t(f'professions.{filter_key}', lang), callback_data=f'pe_l:{key}:{filter_key}:0')])
    else:
        rows.append([InlineKeyboardButton(t('professions.sources', lang), callback_data=f'pe_g:{key}:0')])
    rows.append([InlineKeyboardButton(t('professions.back', lang), callback_data='pe_o:0')])
    return '\n'.join(lines), _kb(rows)


def build_resource_list(player: dict, key: str, page: int = 0):
    lang = player.get('lang', 'ru')
    materials = sorted(
        (resource for resource in RESOURCES.values() if resource.profession_key == key),
        key=lambda resource: (resource.required_level, resource.item_id),
    )
    shown, page, pages = _page(materials, page)
    rows = [[InlineKeyboardButton(get_item_name(resource.item_id, lang),
                                  callback_data=f'pe_m:{resource.item_id}:0')]
            for resource in shown]
    nav = []
    if page:
        nav.append(InlineKeyboardButton('◀️', callback_data=f'pe_g:{key}:{page-1}'))
    if page + 1 < pages:
        nav.append(InlineKeyboardButton('▶️', callback_data=f'pe_g:{key}:{page+1}'))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(t('professions.back', lang), callback_data=f'pe_p:{key}')])
    title = f"<b>{escape(t(f'professions.names.{key}', lang))} · {escape(t('professions.sources', lang))}</b>"
    return title + '\n' + t('professions.page', lang, page=page+1, pages=pages), _kb(rows)


def build_recipe_list(player: dict, key: str, filter_key: str, page: int = 0):
    lang, player_id = player.get('lang', 'ru'), int(player['telegram_id'])
    _, crafting, _ = _state(player_id)
    level = int(crafting.get(key, {}).get('level', 1))
    known = set(known_recipe_ids(player_id))
    recipes = [recipe for recipe in ACTIVE_RECIPES if recipe.profession_key == key]
    if filter_key == 'known': recipes = [r for r in recipes if r.recipe_id in known]
    elif filter_key == 'learnable': recipes = [r for r in recipes if r.recipe_id not in known and r.required_level <= level]
    else: recipes = [r for r in recipes if r.recipe_id not in known and r.required_level > level]
    recipes.sort(key=lambda r: (r.required_level, r.recipe_id))
    shown, page, pages = _page(recipes, page)
    rows = [[InlineKeyboardButton(_recipe_name(r, lang), callback_data=f'pe_r:{r.recipe_id}')] for r in shown]
    nav = []
    if page: nav.append(InlineKeyboardButton('◀️', callback_data=f'pe_l:{key}:{filter_key}:{page-1}'))
    if page + 1 < pages: nav.append(InlineKeyboardButton('▶️', callback_data=f'pe_l:{key}:{filter_key}:{page+1}'))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(t('professions.back', lang), callback_data=f'pe_p:{key}')])
    title = f"<b>{escape(t(f'professions.names.{key}', lang))} · {escape(t(f'professions.{filter_key}', lang))}</b>"
    return title + '\n' + t('professions.page', lang, page=page+1, pages=pages), _kb(rows)


def build_recipe(player: dict, recipe_id: str):
    lang, player_id = player.get('lang', 'ru'), int(player['telegram_id'])
    recipe = get_recipe(recipe_id)
    if not recipe:
        return build_overview(player)
    _, crafting, inventory = _state(player_id)
    known = recipe_id in set(known_recipe_ids(player_id))
    state = crafting[recipe.profession_key]
    lines = [f'<b>{escape(_recipe_name(recipe, lang))}</b>',
             t('professions.recipe_level', lang, level=recipe.required_level),
             t('professions.learning', lang, gold=recipe.learning_gold),
             t('professions.ingredients', lang)]
    enough = True
    for item_id, quantity in recipe.requirements:
        owned = inventory.get(item_id, 0); enough &= owned >= quantity
        lines.append(f"• {escape(get_item_name(item_id, lang))}: {t('professions.owned', lang, owned=owned, required=quantity)}")
    if recipe.output_spec.kind == 'gear':
        lines.append(f"T{recipe.output_spec.item_tier} · {recipe.output_spec.rarity} · {recipe.output_spec.secondary_policy}")
    else:
        from game.items_data import get_item
        lines.append(str((get_item(recipe.output_spec.item_id) or {}).get('stat_bonus_json', '{}')))
    can_craft = known and int(state['level']) >= recipe.required_level and enough and 'craftsmen_guild' in (get_location(player['location_id']) or {}).get('services', [])
    lines.append(t('professions.craftable' if can_craft else 'professions.not_craftable', lang))
    rows = []
    if known:
        payload = recipe_intent_payload(recipe_id)
        token = issue_actions(player_id, 'craft', [payload]).get(payload)
        if token: rows.append([InlineKeyboardButton(t('professions.craft', lang), callback_data=f'pe_a:{token}')])
    elif int(state['level']) >= recipe.required_level:
        payload = recipe_intent_payload(recipe_id)
        token = issue_actions(player_id, 'learn', [payload]).get(payload)
        if token: rows.append([InlineKeyboardButton(t('professions.learn', lang), callback_data=f'pe_a:{token}')])
    rows.append([InlineKeyboardButton(t('professions.back', lang), callback_data=f'pe_p:{recipe.profession_key}')])
    return '\n'.join(lines), _kb(rows)


def build_material(player: dict, item_id: str, page: int = 0):
    lang = player.get('lang', 'ru'); resource = RESOURCES.get(item_id)
    if not resource: return build_overview(player)
    sources = [(location_id, chance) for location_id, rows in ENVIRONMENTAL_SOURCES.items()
               for source_id, chance in rows if source_id == item_id]
    for mob_id, items in HARVEST_MANIFEST.items():
        if item_id in items: sources.append((mob_id, None))
    consumers = list(recipe_consumers(item_id))
    entries = [('source', value) for value in sources] + [('recipe', value) for value in consumers]
    shown, page, pages = _page(entries, page)
    lines = [f'<b>{escape(get_item_name(item_id, lang))}</b>',
             t('professions.recipe_level', lang, level=resource.required_level),
             t('professions.sale', lang, gold=resource.sell_price)]
    rows = []
    for kind, value in shown:
        if kind == 'source':
            source_id, chance = value
            label = source_id if chance is None else get_location_name(source_id, lang)
            lines.append(f"• {escape(label)}" + ('' if chance is None else f' — {chance*100:g}%'))
        else:
            recipe = get_recipe(value)
            rows.append([InlineKeyboardButton(_recipe_name(recipe, lang), callback_data=f'pe_r:{value}')])
    nav=[]
    if page: nav.append(InlineKeyboardButton('◀️', callback_data=f'pe_m:{item_id}:{page-1}'))
    if page+1<pages: nav.append(InlineKeyboardButton('▶️', callback_data=f'pe_m:{item_id}:{page+1}'))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(t('professions.back', lang), callback_data=f'pe_p:{resource.profession_key}')])
    return '\n'.join(lines), _kb(rows)


def build_receipts(player: dict, page: int = 0):
    lang, player_id = player.get('lang', 'ru'), int(player['telegram_id'])
    values = list_receipts(player_id, page=page, page_size=6)
    receipts, has_next = values[:5], len(values) > 5
    payloads = [str(receipt['request_id']) for receipt in receipts]
    tokens = issue_actions(player_id, 'receipt', payloads) if payloads else {}
    lines = [t('professions.receipts', lang)]
    rows = [[InlineKeyboardButton(
        f"{receipt.get('created_at','')} · {receipt.get('action_kind','')} · {receipt.get('status','')}",
        callback_data=f"pe_x:{tokens[receipt['request_id']]}",
    )] for receipt in receipts]
    nav = []
    if page:
        nav.append(InlineKeyboardButton('◀️', callback_data=f'pe_h:{page-1}'))
    if has_next:
        nav.append(InlineKeyboardButton('▶️', callback_data=f'pe_h:{page+1}'))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(t('professions.back', lang), callback_data='pe_o:0')])
    return '\n'.join(lines), _kb(rows)


def build_receipt(player: dict, token: str):
    lang, player_id = player.get('lang', 'ru'), int(player['telegram_id'])
    conn = get_connection()
    try:
        row = conn.execute('''SELECT payload FROM player_ui_actions
            WHERE token=? AND player_id=? AND kind='receipt' AND used=0 AND expires_at>=?''',
            (token, player_id, int(time.time()))).fetchone()
    finally:
        conn.close()
    receipt = get_receipt(player_id, str(row['payload'])) if row else None
    if not receipt:
        return build_receipts(player)
    lines = [t('professions.receipt_detail', lang),
             f"{escape(str(receipt.get('action_kind', '')))} · {escape(str(receipt.get('status', '')))}",
             t('professions.gold_result', lang, delta=receipt.get('gold_delta', 0), after=receipt.get('gold_after', 0))]
    for key in ('consumed', 'granted'):
        values = receipt.get(key) or []
        lines.append(t(f'professions.receipt_{key}', lang))
        lines.extend(f"• {escape(get_item_name(value.get('item_id'), lang))} ×{int(value.get('quantity', 0))}"
                     for value in values)
        if not values:
            lines.append(t('professions.none', lang))
    return '\n'.join(lines), _kb([[InlineKeyboardButton(t('professions.back', lang), callback_data='pe_h:0')]])


async def handle_profession_buttons(update, context):
    query = update.callback_query; player_row = get_player(query.from_user.id)
    if not player_row:
        await query.answer(t('common.no_character', 'ru'), show_alert=True); return
    player, data = dict(player_row), query.data; lang = player.get('lang', 'ru')
    notice = None
    try:
        if data.startswith('pe_o'):
            page = int(data.split(':')[1]) if ':' in data else 0; view = build_overview(player, page)
        elif data.startswith('pe_p:'):
            view = build_profession(player, data.split(':', 1)[1])
        elif data.startswith('pe_g:'):
            _, key, page = data.split(':'); view = build_resource_list(player, key, int(page))
        elif data.startswith('pe_l:'):
            _, key, filter_key, page = data.split(':'); view = build_recipe_list(player, key, filter_key, int(page))
        elif data.startswith('pe_r:'):
            view = build_recipe(player, data.split(':', 1)[1])
        elif data.startswith('pe_m:'):
            _, item_id, page = data.split(':'); view = build_material(player, item_id, int(page))
        elif data.startswith('pe_h:'):
            view = build_receipts(player, int(data.split(':')[1]))
        elif data.startswith('pe_x:'):
            view = build_receipt(player, data.split(':', 1)[1])
        elif data.startswith('pe_a:'):
            token = data.split(':', 1)[1]
            conn = get_connection()
            try: action = conn.execute('SELECT kind, payload FROM player_ui_actions WHERE token=? AND player_id=?', (token, player['telegram_id'])).fetchone()
            finally: conn.close()
            recovered_receipt = get_receipt(player['telegram_id'], f'ui:{token}') if not action else None
            if recovered_receipt:
                result = recovered_receipt; recipe_id = recovered_receipt.get('recipe_id') or ''
            elif not action: result = {'status':'stale_action'}; recipe_id = ''
            elif action['kind'] == 'learn':
                recipe_id=parse_recipe_intent(action['payload']) or ''; result=learn_recipe(player['telegram_id'], recipe_id, action_token=token)
            elif action['kind'] == 'harvest':
                import json
                payload=json.loads(action['payload']); recipe_id=''
                result=harvest_victory(player['telegram_id'], payload['encounter_id'], unit_id=payload['unit_id'], item_id=payload['item_id'], action_token=token)
            else:
                recipe_id=parse_recipe_intent(action['payload']) or ''; crafted=craft_recipe(player['telegram_id'], recipe_id, action_token=token); result={'status':crafted.status}
            notice = t(f"professions.{result['status']}", lang)
            view = build_recipe(dict(get_player(player['telegram_id'])), recipe_id) if recipe_id else build_overview(player)
        else: view = build_overview(player)
    except (ValueError, KeyError):
        notice = t('professions.stale_action', lang); view = build_overview(player)
    await query.answer(notice or '')
    await query.edit_message_text(view[0][:3600], reply_markup=view[1], parse_mode='HTML')
