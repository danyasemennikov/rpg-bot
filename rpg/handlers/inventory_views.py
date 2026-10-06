"""Compact inventory projections over existing gear, inventory and tool owners."""

from html import escape
import json
from telegram import InlineKeyboardButton,InlineKeyboardMarkup
from database import get_connection,get_player
from game.i18n import get_item_name,t
from game.items_data import get_item
from game.player_ui import validate_surface

CATEGORIES = ('all','gear','supplies','material','tools')
LEGACY_CATEGORIES = {'weapon':'gear','armor':'gear','accessory':'gear','potion':'supplies'}


def category_card(lang):
    rows = [[InlineKeyboardButton(t('pxe1.inventory_categories.'+key,lang),callback_data='inv_tab_'+key)] for key in CATEGORIES]
    rows.append([InlineKeyboardButton(t('common.back',lang),callback_data='inv_tab_all')])
    return t('pxe1.categories',lang),InlineKeyboardMarkup(rows)


def inventory_card(player_id,category,lang,page=0):
    from handlers.inventory import get_equipped,get_inventory,get_gear_inventory_entries,make_entry_token,_get_entry_enhance_level,_get_entry_rarity_and_tier
    from game.profession_tools import TOOL_NAMES
    category = LEGACY_CATEGORIES.get(category,category)
    if category not in CATEGORIES:
        category = 'all'
    eq = get_equipped(player_id)
    entries = []
    if category!='tools':
        candidates = get_gear_inventory_entries(player_id)
        candidates += [{**r,'entry_type':'legacy_inventory'} for r in get_inventory(player_id)]
        for row in candidates:
            item = get_item(row['item_id'])
            if not item or row['quantity']<=0:
                continue
            kind = 'gear' if item['item_type'] in {'weapon','armor','accessory'} else 'supplies' if item['item_type']=='potion' else 'material'
            if category not in {'all',kind}:
                continue
            token = make_entry_token(row['entry_type'],row['id'])
            equipped = token in eq.values()
            rarity,tier = _get_entry_rarity_and_tier(row,item)
            enhance = _get_entry_enhance_level(row)
            label = get_item_name(row['item_id'],lang)
            if kind=='gear':
                from handlers.inventory import RARITY_NAME
                label += ' · '+RARITY_NAME.get(lang,RARITY_NAME['en']).get(rarity,rarity)
                if enhance:
                    label += f' +{enhance}'
                if row['entry_type']=='gear_instance':
                    from game.gear_instances import resolve_gear_instance_item_data
                    from handlers.inventory import _get_localized_stat_label
                    resolved = resolve_gear_instance_item_data(row['instance'])
                    secondaries = resolved['secondary_rolls']
                    if secondaries:
                        label += ' · '+', '.join(_get_localized_stat_label(str(roll['stat']),lang)+f" {int(roll['value']):+}" for roll in secondaries)
            elif row['quantity']>1:
                label += f" ×{row['quantity']}"
            if equipped:
                label += ' ✓'
            entries.append((not equipped,row['item_id'],row['id'],label,token))
    if category in {'all','tools'}:
        conn = get_connection()
        try:
            tools = conn.execute('SELECT * FROM player_profession_tools WHERE player_id=? ORDER BY profession_key',(player_id,)).fetchall()
        finally:
            conn.close()
        for tool in tools:
            label = t('pxe1.tool.'+TOOL_NAMES[tool['profession_key']],lang)+f" · {tool['durability']}/{60*tool['tier']}"
            entries.append((True,'tool:'+tool['profession_key'],0,label,'px:tool:'+tool['profession_key']))
    entries.sort(key=lambda row:row[:3])
    pages = max(1,(len(entries)+5)//6)
    page = min(max(0,int(page)),pages-1)
    lines = [t('inventory.title',lang)+' · '+t('pxe1.inventory_categories.'+category,lang)]
    rows = []
    for _,_,_,label,callback in entries[page*6:(page+1)*6]:
        if not callback.startswith('px:'):
            route = category if page==0 else f'{category}~{page}'
            callback = f'inv_item_{callback}_{route}'
        lines.append(escape(label))
        rows.append([InlineKeyboardButton(label,callback_data=callback)])
    if not entries:
        lines.append(t('inventory.empty',lang))
    nav = []
    if page:
        nav.append(InlineKeyboardButton('◀️',callback_data=f'inv_tab_{category}~{page-1}'))
    if page+1<pages:
        nav.append(InlineKeyboardButton('▶️',callback_data=f'inv_tab_{category}~{page+1}'))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(t('pxe1.categories',lang),callback_data='inv_categories'),InlineKeyboardButton(t('pxe1.more',lang),callback_data='inv_more_home')])
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines),keyboard,list_view=True)
    return '\n'.join(lines),keyboard


def item_card(player_id,entry_token,category,lang,*,more=False):
    from handlers.inventory import _legacy_item_detail,_load_inventory_entry,get_equipped,get_equipped_slot_for_entry_token,STAT_NAMES
    from game.gear_instances import MAX_ENHANCE_LEVEL,resolve_gear_instance_item_data
    entry = _load_inventory_entry(player_id,entry_token)
    if not entry:
        return t('inventory.item_not_found',lang),InlineKeyboardMarkup([[InlineKeyboardButton(t('common.back',lang),callback_data='inv_tab_'+category)]])
    full_text,full_keyboard = _legacy_item_detail(player_id,entry_token,category,lang)
    item = get_item(entry['item_id'])
    if more:
        # The detailed layer retains all existing actions and readable metadata.
        buttons = [button for row in full_keyboard.inline_keyboard for button in row]
        buttons[-1:-1] = [InlineKeyboardButton(t('gear.catalog_btn',lang),callback_data='inv_catalog'),
                          InlineKeyboardButton(t('gear.receipts_btn',lang),callback_data='inv_receipts'),
                          InlineKeyboardButton(t('location.shop_btn',lang),callback_data='shop')]
        keyboard = InlineKeyboardMarkup([buttons[i:i+2] for i in range(0,len(buttons),2)])
        validate_surface(full_text,keyboard,list_view=True,long_detail=True)
        return full_text,keyboard
    resolved = resolve_gear_instance_item_data(entry['instance']) if entry['entry_type']=='gear_instance' else item
    gear = item['item_type'] in {'weapon','armor','accessory'}
    kind = 'gear' if gear else 'supplies' if item['item_type']=='potion' else 'material'
    lines = [f"<b>{escape(get_item_name(entry['item_id'],lang))}</b> ×{entry['quantity']} · "+t('pxe1.inventory_categories.'+kind,lang)]
    if gear:
        rarity = resolved.get('instance_rarity',item['rarity'])
        from handlers.inventory import RARITY_NAME
        lines.append(RARITY_NAME.get(lang,RARITY_NAME['en']).get(rarity,rarity)+' · '+t('inventory.instance_tier',lang,tier=resolved.get('item_tier',1))+' · '+t('inventory.enhance_level',lang,level=resolved.get('enhance_level',entry.get('enhance_level',0)),max=MAX_ENHANCE_LEVEL))
        if item['item_type']=='weapon':
            lines.append(t('inventory.damage',lang,min=resolved['damage_min'],max=resolved['damage_max']))
        else:
            lines.append(t('inventory.defense',lang,val=resolved['defense']))
        requirements = [t('common.level',lang)+' '+str(item['req_level'])]
        requirements += [STAT_NAMES.get(lang,STAT_NAMES['en'])[key]+' '+str(item['req_'+key]) for key in ('strength','agility','intuition','wisdom') if item['req_'+key]>0]
        lines.append(t('inventory.reqs',lang,val=', '.join(requirements)))
        bonuses = resolved.get('resolved_stat_bonus') if entry['entry_type']=='gear_instance' else json.loads(item['stat_bonus_json'] or '{}')
        if bonuses:
            from handlers.inventory import _get_localized_stat_label
            lines.append(t('inventory.bonuses',lang,val=', '.join(_get_localized_stat_label(key,lang)+f' {value:+}' for key,value in bonuses.items())))
        slot = get_equipped_slot_for_entry_token(get_equipped(player_id),entry_token)
        if slot:
            lines.append(t('inventory.equipped',lang))
    elif item['item_type']=='potion':
        effects = json.loads(item['stat_bonus_json'] or '{}')
        lines.append(f"❤️ +{effects.get('heal',0)} · 🔵 +{effects.get('mana',0)}")
        lines.append(t('pxe1.supplies_restrictions',lang))
    usable = True
    if item['item_type']=='potion':
        from game.action_receipts import ActionRejected,peaceful_player
        conn = get_connection()
        try:
            peaceful_player(conn,player_id)
        except ActionRejected:
            usable = False
            lines.append(t('pxe1.supplies_busy',lang))
        finally:
            conn.close()
    rows = []
    prefixes = ('inv_gequip_','inv_lequip_','inv_use_','inv_genh_','inv_cmp_')
    for row in full_keyboard.inline_keyboard:
        buttons = [b for b in row if b.callback_data.startswith(prefixes) and (usable or not b.callback_data.startswith('inv_use_'))]
        if buttons:
            rows.append(buttons)
    if item['item_type']=='material':
        rows.append([InlineKeyboardButton(t('pxe1.sources',lang),callback_data=f"pe_m:{entry['item_id']}:0")])
    rows.append([InlineKeyboardButton(t('pxe1.more',lang),callback_data=f'inv_more_{entry_token}_{category}'),InlineKeyboardButton(t('common.back',lang),callback_data='inv_tab_'+category)])
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines),keyboard)
    return '\n'.join(lines),keyboard
