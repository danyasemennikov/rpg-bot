"""Quantity and protection previews over the existing economy mutation owners."""

import json
from html import escape

from telegram import InlineKeyboardButton,InlineKeyboardMarkup

from database import get_connection,get_player
from game.action_receipts import ActionRejected,issue_actions
from game.i18n import t,get_item_name,get_location_name
from game.items_data import get_item
from game.locations import get_location,resolve_location_id
from game.player_ui import validate_surface
from game.sale_policy import owned_count,sale_quote,sale_payload


def button(text,data):
    return InlineKeyboardButton(text,callback_data=data)


def surface(lines,rows,*,list_view=False):
    text,keyboard = '\n'.join(lines),InlineKeyboardMarkup(rows)
    validate_surface(text,keyboard,list_view=list_view)
    return text,keyboard


def modes(lang,mode):
    return [button(t('pxe1.shop.buy',lang)+(' ✓' if mode=='buy' else ''),'px:shop:buy:0'),
            button(t('pxe1.shop.sell',lang)+(' ✓' if mode=='sell' else ''),'px:shop:categories')]


def title(player):
    lang = player.get('lang','ru')
    return t('pxe1.shop.title',lang,place=escape(get_location_name(player['location_id'],lang)),gold=player['gold'])


def buy_list(player,page=0):
    from handlers.location import CURATED_EQUIPMENT_VENDOR_STOCK
    lang = player.get('lang','ru')
    entries = CURATED_EQUIPMENT_VENDOR_STOCK.get(resolve_location_id(player['location_id']),[])
    pages = max(1,(len(entries)+5)//6); page = max(0,min(int(page),pages-1))
    lines,rows = [title(player),t('gear.page',lang,page=page+1,pages=pages)],[modes(lang,'buy')]
    for row in entries[page*6:page*6+6]:
        item = get_item(row['item_id'])
        if not item:
            continue
        name,price = get_item_name(row['item_id'],lang),int(item['buy_price'])
        lines.append(f'{escape(name)} · {price} 🪙')
        rows.append([button(f'{name} · {price} 🪙',f"px:shop:preview:{row['item_id']}:1")])
    nav = []
    if page: nav.append(button('◀️',f'px:shop:buy:{page-1}'))
    if page+1<pages: nav.append(button('▶️',f'px:shop:buy:{page+1}'))
    if nav: rows.append(nav)
    rows.extend([[button(t('pxe1.shop.starter_tools',lang),'px:tools')],
                 [button(t('gear.back_btn',lang),'px:local:home:0')]])
    return surface(lines,rows,list_view=True)


def buy_preview(player,item_id,quantity=1):
    from handlers.location import CURATED_EQUIPMENT_VENDOR_STOCK
    lang = player.get('lang','ru')
    stock = next((r for r in CURATED_EQUIPMENT_VENDOR_STOCK.get(resolve_location_id(player['location_id']),[])
                  if r['item_id']==item_id),None)
    item = get_item(item_id)
    if not stock or not item or int(item.get('buy_price',0))<=0:
        raise ActionRejected('not_sellable')
    gear = item['item_type'] in {'weapon','armor','accessory'}
    price = int(item['buy_price'])
    maximum = min(1 if gear else 99,int(player['gold'])//price)
    quantity = max(1,min(int(quantity),max(1,maximum)))
    conn = get_connection()
    try: owned = owned_count(conn,player['telegram_id'],item_id)
    finally: conn.close()
    lines = [f'<b>{escape(get_item_name(item_id,lang))}</b>',
             t('pxe1.shop.quantity',lang,quantity=quantity,owned=owned),
             t('pxe1.shop.unit_price',lang,gold=price),t('pxe1.shop.total',lang,gold=price*quantity),
             t('pxe1.shop.balance',lang,gold=player['gold'])]
    requirement = int(stock.get('level_min',item.get('req_level',1)))
    lines.append(t('common.level',lang)+' '+str(requirement))
    bonus = json.loads(item.get('stat_bonus_json') or '{}')
    if item['item_type']=='potion':
        effects = []
        if bonus.get('heal'): effects.append(f"❤️ +{bonus['heal']}")
        if bonus.get('mana'): effects.append(f"🔵 +{bonus['mana']}")
        if effects: lines.append(' · '.join(effects))
    elif gear:
        requirements = [t(f'inventory.stat_labels.{s}',lang)+f' {int(item.get("req_"+s,0))}'
                        for s in ('strength','agility','intuition','wisdom') if int(item.get('req_'+s,0))]
        if requirements: lines.append(' · '.join(requirements))
        stats = []
        if item.get('damage_max'): stats.append(t('inventory.damage',lang,min=item['damage_min'],max=item['damage_max']))
        if item.get('defense'): stats.append(t('inventory.defense',lang,val=item['defense']))
        if stats: lines.append(' · '.join(stats))
    rows = []
    if not gear and maximum>1:
        controls = [button('1',f'px:shop:preview:{item_id}:1')]
        if quantity<maximum: controls.append(button('+1',f'px:shop:preview:{item_id}:{quantity+1}'))
        rows.append(controls)
        if quantity<maximum: rows.append([button('+5',f'px:shop:preview:{item_id}:{min(maximum,quantity+5)}')])
    if maximum>=quantity and int(player['level'])>=requirement:
        payload = json.dumps({'schema_version':1,'catalog_version':2,'item_id':item_id,'quantity':quantity,
                              'unit_price':price,'location_id':resolve_location_id(player['location_id'])},
                             sort_keys=True,separators=(',',':'))
        token = issue_actions(player['telegram_id'],'shop_buy',[payload])[payload]
        rows.append([button(t('pxe1.shop.buy_quantity',lang,quantity=quantity,gold=price*quantity),f'px:shop:purchase:{token}')])
    elif maximum<quantity:
        lines.append(t('location.shop_no_gold',lang,price=price*quantity))
    rows.append([button(t('gear.back_btn',lang),'px:shop:buy:0')])
    return surface(lines,rows)


def sell_categories(player):
    lang = player.get('lang','ru')
    rows = [modes(lang,'sell')]
    for category in ('all','gear','supplies','material','tools'):
        rows.append([button(t(f'pxe1.inventory_categories.{category}',lang),f'px:shop:sell:{category}:0')])
    rows[-1].append(button(t('gear.back_btn',lang),'px:local:home:0'))
    return surface([title(player),t('pxe1.categories',lang)],rows)


def sell_list(player,category='all',page=0):
    from handlers.inventory import get_inventory,get_gear_inventory_entries
    lang = player.get('lang','ru')
    entries = [('g',r) for r in get_gear_inventory_entries(player['telegram_id'])]
    entries += [('i',r) for r in get_inventory(player['telegram_id']) if r['quantity']>0]
    filtered = []
    for kind,row in entries:
        item = get_item(row['item_id']) or {}
        item_type = item.get('item_type')
        group = 'gear' if item_type in {'weapon','armor','accessory'} else 'supplies' if item_type=='potion' else 'material'
        if category=='tools' or (category!='all' and category!=group): continue
        if int(item.get('sell_price',0))<=0: continue
        filtered.append((kind,row))
    filtered.sort(key=lambda e:(e[1]['item_id'],e[0],e[1]['id']))
    pages = max(1,(len(filtered)+5)//6); page = max(0,min(int(page),pages-1))
    lines,rows = [title(player),t(f'pxe1.inventory_categories.{category}',lang)],[modes(lang,'sell')]
    for kind,row in filtered[page*6:page*6+6]:
        name = get_item_name(row['item_id'],lang)
        qty = row.get('quantity',1)
        lines.append(f'{escape(name)} ×{qty}')
        rows.append([button(f'{name} ×{qty}',f"px:shop:saleview:{kind}{row['id']}:1")])
    if not filtered:
        lines.append(t('pxe1.shop.tools_unsellable' if category=='tools' else 'inventory.empty',lang))
    nav = []
    if page: nav.append(button('◀️',f'px:shop:sell:{category}:{page-1}'))
    if page+1<pages: nav.append(button('▶️',f'px:shop:sell:{category}:{page+1}'))
    if nav: rows.append(nav)
    rows.append([button(t('pxe1.categories',lang),'px:shop:categories'),button(t('gear.back_btn',lang),'px:shop:buy:0')])
    return surface(lines,rows,list_view=True)


def issue_sale(player_id,quote,confirmed=False):
    if quote['entry_type']=='i':
        payload = sale_payload(quote,confirmed=confirmed)
        return issue_actions(player_id,'sell',[payload])[payload]
    from game.gear_progression import build_gear_mutation_preview
    preview = build_gear_mutation_preview(player_id,'sale',quote['entry_id'])
    if not preview:
        raise ActionRejected('stale_action')
    parameters = json.loads(preview['payload'])
    parameters.update(sale_quote=quote,sale_confirmed=confirmed)
    payload = json.dumps(parameters,sort_keys=True,separators=(',',':'))
    return issue_actions(player_id,'gear_sale',[payload])[payload]


def sale_preview(player,entry_token,quantity=1,*,confirmation_quote=None):
    lang = player.get('lang','ru')
    conn = get_connection()
    try:
        quote = confirmation_quote or sale_quote(conn,player['telegram_id'],entry_token[0],int(entry_token[1:]),int(quantity))
    finally: conn.close()
    lines = [f"<b>{escape(get_item_name(quote['item_id'],lang))}</b>",
             t('pxe1.shop.quantity',lang,quantity=quote['quantity'],owned=quote['stack_count']),
             t('pxe1.shop.unit_price',lang,gold=quote['unit_price']),
             t('pxe1.shop.total',lang,gold=quote['total']),
             t('pxe1.shop.sale_remaining',lang,count=quote['remaining'])]
    rows = []
    if confirmation_quote is not None:
        lines.append(t('pxe1.shop.confirm_sale',lang))
        for risk in quote['risks']:
            if risk=='quest_needed':
                from game.quest_board import get_hunt_contract
                contract = get_hunt_contract(quote['assignment'])
                name = t(contract.title_i18n_key,lang) if contract else t('pxe1.open_assignment',lang)
                lines.append(t('pxe1.shop.quest_needed',lang,name=name))
            else: lines.append(t(f'pxe1.shop.{risk}',lang))
    elif quote['entry_type']=='i' and (get_item(quote['item_id']) or {}).get('item_type') not in {'weapon','armor','accessory'}:
        maximum = min(99,quote['stack_count'])
        rows.append([button('1',f'px:shop:saleview:{entry_token}:1'),
                     button('+5',f"px:shop:saleview:{entry_token}:{min(maximum,quote['quantity']+5)}")])
        rows.append([button(t('pxe1.shop.all',lang),f'px:shop:saleview:{entry_token}:{maximum}')])
    token = issue_sale(player['telegram_id'],quote,confirmed=confirmation_quote is not None)
    label = t('pxe1.shop.confirm_sale' if confirmation_quote else 'pxe1.shop.sell_quantity',lang,
              quantity=quote['quantity'],gold=quote['total'])
    rows.append([button(label,f"px:shop:commit:{quote['entry_type']}:{token}")])
    rows.append([button(t('gear.back_btn',lang),'px:shop:sell:all:0')])
    return surface(lines,rows)


def result_card(player,result,*,buy=False):
    lang = player.get('lang','ru')
    lines = [t('pxe1.shop.purchase_result' if buy else 'pxe1.shop.sale_result',lang,
               name=escape(get_item_name(result['item_id'],lang)),quantity=result.get('quantity',1)),
             f"{'−' if buy else '+'}{abs(result.get('gold_delta',result.get('price',result.get('gold',0))))} 🪙"]
    if 'gold_after' in result: lines.append(t('pxe1.shop.balance',lang,gold=result['gold_after']))
    if 'remaining' in result: lines.append(t('pxe1.shop.sale_remaining',lang,count=result['remaining']))
    text = '\n'.join(lines)
    keys = []
    if not result.get('recovered'):
        from game.player_feedback import inline_feedback
        text,keys = inline_feedback(player['telegram_id'],lang,text)
    rows = [[button(t('pxe1.shop.continue_buying' if buy else 'pxe1.shop.continue_selling',lang),
                    'px:shop:buy:0' if buy else 'px:shop:sell:all:0')]]
    from game.quest_board import get_player_hunt_contract_state
    state = get_player_hunt_contract_state(player['telegram_id'])
    if state and state['status']=='completed':
        rows.append([button(t('pxe1.assignment_ready',lang),'alpha_assignment')])
    rows.append([button(t('gear.back_btn',lang),'px:local:home:0')])
    validate_surface(text,InlineKeyboardMarkup(rows))
    return text,InlineKeyboardMarkup(rows),keys


async def handle_shop_buttons(update,context):
    query = update.callback_query
    player = dict(get_player(query.from_user.id))
    lang = player.get('lang','ru')
    parts = query.data.split(':')
    action = parts[2]
    keys = []
    try:
        if action=='purchase':
            token = parts[3]
            conn = get_connection()
            try:
                row = conn.execute("SELECT payload FROM player_ui_actions WHERE token=? AND player_id=? AND kind='shop_buy'",
                                   (token,player['telegram_id'])).fetchone()
                if row:
                    raw = row['payload']; item_id = json.loads(raw)['item_id'] if raw.startswith('{') else raw
                else:
                    receipt = conn.execute("SELECT result_json FROM gear_mutation_receipts WHERE action_token=? AND player_id=? AND action_kind='purchase'",
                                           (token,player['telegram_id'])).fetchone()
                    if not receipt: raise ActionRejected('stale_action')
                    item_id = json.loads(receipt['result_json'])['item_id']
            finally: conn.close()
            from handlers.location import try_buy_curated_shop_item
            result = try_buy_curated_shop_item(player['telegram_id'],player['location_id'],player['level'],item_id,action_token=token)
            if not result['ok']: raise ActionRejected(result['reason'])
            text,keyboard,keys = result_card(dict(get_player(player['telegram_id'])),result,buy=True)
        elif action=='commit':
            kind,token = parts[3:5]
            if kind=='g':
                from game.gear_progression import apply_gear_intent
                result = apply_gear_intent(player['telegram_id'],'sale',token)
            elif kind=='i':
                from handlers.inventory import try_sell_inventory_item
                result = try_sell_inventory_item(player['telegram_id'],token)
            else: raise ActionRejected('stale_action')
            if result['status']=='confirmation_required':
                quote = result['quote']
                text,keyboard = sale_preview(player,f"{quote['entry_type']}{quote['entry_id']}",confirmation_quote=quote)
            elif result['status']=='sold':
                text,keyboard,keys = result_card(dict(get_player(player['telegram_id'])),result)
            else: raise ActionRejected(result['status'])
        elif action=='buy': text,keyboard = buy_list(player,int(parts[3]))
        elif action=='preview': text,keyboard = buy_preview(player,parts[3],int(parts[4]))
        elif action=='categories': text,keyboard = sell_categories(player)
        elif action=='sell': text,keyboard = sell_list(player,parts[3],int(parts[4]))
        elif action=='saleview': text,keyboard = sale_preview(player,parts[3],int(parts[4]))
        else: raise ActionRejected('stale_action')
    except (ActionRejected,ValueError,KeyError,IndexError) as exc:
        reason = str(exc)
        key = 'cannot_sell_equipped' if reason=='equipped_item' else 'cannot_sell' if reason=='not_sellable' else 'stale'
        await query.answer(t(f'pxe1.shop.{key}',lang),show_alert=True)
        return
    await query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
    if keys:
        from game.player_feedback import acknowledge_presented_facts
        acknowledge_presented_facts(player['telegram_id'],keys)
    await query.answer()
