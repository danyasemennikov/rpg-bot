"""Compact catalogue-two item/tool recipe views."""

from html import escape
import json
import time
from telegram import InlineKeyboardButton,InlineKeyboardMarkup
from database import get_connection
from game.action_receipts import ActionRejected,issue_actions
from game.i18n import get_item_name,t
from game.player_ui import validate_surface
from game.profession_recipes import get_recipe,recipe_intent_payload
from game.profession_progression import crafting_xp_for_success
from game.recipe_knowledge import known_recipe_ids


def recipe_card(player,recipe_id,*,commission=False,details=False,inputs_page=None):
    from handlers.professions import _recipe_name,_state,_peaceful_guild_access,_legacy_recipe
    from game.profession_tools import commission_inputs,get_tool
    recipe = get_recipe(recipe_id)
    if not recipe:
        from handlers.professions import build_overview
        return build_overview(player)
    player_id,lang = player['telegram_id'],player.get('lang','ru')
    _,crafting,inventory = _state(player_id)
    state = crafting[recipe.profession_key]
    known = recipe_id in known_recipe_ids(player_id)
    required = dict(recipe.requirements)
    gold,supplied,tool = 0,{},None
    reason = None
    conn = get_connection()
    try:
        if recipe.output_spec.kind=='tool':
            tool = get_tool(conn,player_id,recipe.output_spec.profession_key)
        if commission:
            try:
                required,gold,supplied = commission_inputs(conn,player_id,recipe)
            except ActionRejected as exc:
                reason = str(exc)
    finally:
        conn.close()
    if inputs_page is not None:
        values = list(required.items())
        pages = max(1,(len(values)+5)//6)
        page = min(max(0,int(inputs_page)),pages-1)
        lines = [t('professions.ingredients',lang)]
        rows = []
        for item,quantity in values[page*6:(page+1)*6]:
            label = get_item_name(item,lang)
            lines.append(f'{escape(label)}: {inventory.get(item,0)}/{quantity}')
            rows.append([InlineKeyboardButton(label,callback_data=f'pe_m:{item}:0')])
        nav = []
        if page:
            nav.append(InlineKeyboardButton('◀️',callback_data=f'pe_inputs:{recipe_id}:{page-1}'))
        if page+1<pages:
            nav.append(InlineKeyboardButton('▶️',callback_data=f'pe_inputs:{recipe_id}:{page+1}'))
        if nav:
            rows.append(nav)
        rows.append([InlineKeyboardButton(t('common.back',lang),callback_data='pe_r:'+recipe_id)])
        keyboard = InlineKeyboardMarkup(rows)
        validate_surface('\n'.join(lines),keyboard,list_view=True)
        return '\n'.join(lines),keyboard
    if details:
        text,_ = _legacy_recipe(player,recipe_id)
        rows = [[InlineKeyboardButton(t('pxe1.sources',lang),callback_data=f'pe_inputs:{recipe_id}:0')],
                [InlineKeyboardButton(t('common.back',lang),callback_data='pe_r:'+recipe_id)]]
        keyboard = InlineKeyboardMarkup(rows)
        validate_surface(text,keyboard,long_detail=True)
        return text,keyboard
    lines = [f'<b>{escape(_recipe_name(recipe,lang))}</b>',
             t('professions.known' if known else 'professions.learnable' if state['level']>=recipe.required_level else 'professions.locked',lang)+' · '+t('professions.recipe_level',lang,level=recipe.required_level)]
    ingredients = [f'{escape(get_item_name(item,lang))}: {inventory.get(item,0)}/{quantity}' for item,quantity in required.items()]
    lines.extend(' · '.join(ingredients[i:i+3]) for i in range(0,len(ingredients),3))
    if recipe.output_spec.kind=='tool':
        lines.append(t('pxe1.tool_output',lang,capacity=60*recipe.output_spec.tool_tier))
    else:
        from game.items_data import get_item
        output = get_item(recipe.output_spec.item_id)
        lines.append(t('professions.output_sale',lang,gold=output['sell_price']))
    xp = crafting_xp_for_success(current_level=state['level'],current_exp=state['exp'],recipe_level=recipe.required_level,material_value=recipe.material_value)
    lines.append(t('professions.recipe_xp_award',lang,xp=xp)+' · '+t('professions.recipe_xp_ceiling',lang,ceiling=recipe.training_ceiling))
    if commission:
        if reason:
            lines.append(t('pxe1.commission_reasons.'+reason,lang))
        else:
            lines.append(t('pxe1.commission_cost',lang,gold=gold))
            if supplied:
                lines.append(t('pxe1.commission_supplied',lang,items=', '.join(get_item_name(item,lang)+f' ×{quantity}' for item,quantity in supplied.items())))
    enough = all(inventory.get(item,0)>=quantity for item,quantity in required.items()) and player['gold']>=gold
    legal = known and state['level']>=recipe.required_level and enough and _peaceful_guild_access(player_id) and not reason
    if tool and tool['tier']>recipe.output_spec.tool_tier:
        legal = False
    rows = []
    if legal:
        payload = recipe_intent_payload(recipe_id,tool_revision=tool['revision'] if tool else None,commission=commission)
        if tool:
            parameters = json.loads(payload)
            parameters['input_snapshot'] = {item:inventory.get(item,0) for item in required}
            parameters['gold'] = gold
            parameters['required'] = required
            parameters['guild_supplied'] = supplied
            payload = json.dumps(parameters,sort_keys=True,separators=(',',':'))
            token = issue_actions(player_id,'tool_craft_preview',[payload])[payload]
            callback = 'pe_tc:'+token
        else:
            token = issue_actions(player_id,'craft',[payload])[payload]
            callback = 'pe_a:'+token
        rows.append([InlineKeyboardButton(t('pxe1.commission' if commission else 'professions.craft',lang),callback_data=callback)])
    elif not known and state['level']>=recipe.required_level and _peaceful_guild_access(player_id):
        payload = recipe_intent_payload(recipe_id)
        token = issue_actions(player_id,'learn',[payload])[payload]
        rows.append([InlineKeyboardButton(t('professions.learn',lang)+f' · {recipe.learning_gold} 💰',callback_data='pe_a:'+token)])
    else:
        blocker = 'recipe_need_knowledge' if not known else 'recipe_need_level' if state['level']<recipe.required_level else 'recipe_need_guild' if not _peaceful_guild_access(player_id) else 'recipe_need_inputs'
        lines.append(t('pxe1.'+blocker,lang))
        if blocker=='recipe_need_guild':
            rows.append([InlineKeyboardButton(t('pxe1.route_guild',lang),callback_data='px:map')])
    if recipe.output_spec.kind=='tool' and recipe.output_spec.profession_key in {'woodcutting','mining'} and recipe.output_spec.tool_tier>1 and not commission:
        rows.append([InlineKeyboardButton(t('pxe1.commission',lang),callback_data='pe_commission:'+recipe_id)])
    rows.append([InlineKeyboardButton(t('pxe1.sources',lang),callback_data=f'pe_inputs:{recipe_id}:0'),InlineKeyboardButton(t('pxe1.details',lang),callback_data='pe_details:'+recipe_id)])
    rows.append([InlineKeyboardButton(t('common.back',lang),callback_data='pe_p:'+recipe.profession_key)])
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines),keyboard)
    return '\n'.join(lines),keyboard


def tool_craft_confirmation(player,token):
    from game.locations import resolve_location_id
    from game.profession_tools import get_tool
    from handlers.professions import _recipe_name
    player_id,lang = player['telegram_id'],player.get('lang','ru')
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM player_ui_actions WHERE token=? AND player_id=? AND kind='tool_craft_preview' AND used=0 AND expires_at>=?",
                           (token,player_id,int(time.time()))).fetchone()
        if not row or row['travel_revision']!=player['travel_revision'] or row['location_id']!=resolve_location_id(player['location_id']):
            raise ActionRejected('stale_action')
        intent = json.loads(row['payload'])
        recipe = get_recipe(intent['recipe_id'])
        tool = get_tool(conn,player_id,recipe.output_spec.profession_key)
        if not tool or tool['revision']!=intent['tool_revision']:
            raise ActionRejected('tool_changed')
        for item,owned in intent['input_snapshot'].items():
            current = conn.execute('SELECT COALESCE(SUM(quantity),0) FROM inventory WHERE telegram_id=? AND item_id=?',(player_id,item)).fetchone()[0]
            if current!=owned:
                raise ActionRejected('tool_quote_changed')
    finally: conn.close()
    intent['replacement_confirmed'] = True
    payload = json.dumps(intent,sort_keys=True,separators=(',',':'))
    mutation = issue_actions(player_id,'craft',[payload])[payload]
    lines = [f'<b>{escape(_recipe_name(recipe,lang))}</b>',
             t('pxe1.tool_replace_warning',lang,tier=tool['tier'],current=tool['durability'],maximum=60*tool['tier']),
             t('pxe1.tool_output',lang,capacity=60*recipe.output_spec.tool_tier)]
    consumed = [escape(get_item_name(item,lang))+f' ×{quantity}' for item,quantity in intent['required'].items()]
    lines += [' · '.join(consumed[i:i+3]) for i in range(0,len(consumed),3)]
    if intent['gold']: lines.append(t('pxe1.commission_cost',lang,gold=intent['gold']))
    if intent['guild_supplied']:
        lines.append(t('pxe1.commission_supplied',lang,items=', '.join(get_item_name(item,lang)+f' ×{quantity}' for item,quantity in intent['guild_supplied'].items())))
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(t('common.confirm',lang),callback_data='pe_a:'+mutation)],
                                    [InlineKeyboardButton(t('common.back',lang),callback_data='pe_r:'+recipe.recipe_id)]])
    validate_surface('\n'.join(lines),keyboard)
    return '\n'.join(lines),keyboard
