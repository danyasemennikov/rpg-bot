"""Compact catalogue-two item/tool recipe views."""

from html import escape
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
        token = issue_actions(player_id,'craft',[payload])[payload]
        rows.append([InlineKeyboardButton(t('pxe1.commission' if commission else 'professions.craft',lang),callback_data='pe_a:'+token)])
    elif not known and state['level']>=recipe.required_level and _peaceful_guild_access(player_id):
        payload = recipe_intent_payload(recipe_id)
        token = issue_actions(player_id,'learn',[payload])[payload]
        rows.append([InlineKeyboardButton(t('professions.learn',lang)+f' · {recipe.learning_gold} 💰',callback_data='pe_a:'+token)])
    else:
        lines.append(t('professions.not_craftable',lang))
    if recipe.output_spec.kind=='tool' and recipe.output_spec.profession_key in {'woodcutting','mining'} and recipe.output_spec.tool_tier>1 and not commission:
        rows.append([InlineKeyboardButton(t('pxe1.commission',lang),callback_data='pe_commission:'+recipe_id)])
    rows.append([InlineKeyboardButton(t('pxe1.sources',lang),callback_data=f'pe_inputs:{recipe_id}:0'),InlineKeyboardButton(t('pxe1.details',lang),callback_data='pe_details:'+recipe_id)])
    rows.append([InlineKeyboardButton(t('common.back',lang),callback_data='pe_p:'+recipe.profession_key)])
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines),keyboard)
    return '\n'.join(lines),keyboard
