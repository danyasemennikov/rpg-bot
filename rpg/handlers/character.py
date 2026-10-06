"""Compact character and earned-attribute spending views."""

from html import escape
from telegram import InlineKeyboardButton,InlineKeyboardMarkup
from database import get_connection
from game.balance import exp_to_next_level
from game.build_progression import ATTRIBUTE_KEYS,attribute_spending_preview
from game.i18n import get_location_name,t
from game.player_ui import validate_surface


def character_card(player_id,lang):
    from handlers.build import _load_model,_family_name
    model = _load_model(player_id)
    player,snapshot = model['player'],model['snapshot']
    lines = [f"👤 <b>{escape(player['name'])}</b> · {t('common.level',lang)} {player['level']}",
             f"📍 {escape(get_location_name(player['location_id'],lang))} · 💰 {player['gold']}",
             f"❤️ {player['hp']}/{snapshot['max_hp']} · 🔵 {player['mana']}/{snapshot['max_mana']}",
             f"{t('common.exp',lang)}: {player['exp']}/{exp_to_next_level(player['level'])} · {t('pxe1.free_points',lang,count=player['stat_points'])}",
             f"{escape(_family_name(snapshot['family'],lang))} · {t('pxe1.mastery_level',lang,level=snapshot['mastery_level'])}"]
    conn = get_connection()
    try:
        travel = conn.execute("SELECT * FROM player_travel_sessions WHERE player_id=? AND status='running'",(player_id,)).fetchone()
    finally:
        conn.close()
    if travel:
        import json,time
        from handlers.activities import duration
        remaining = max(0,(travel['next_due_ms']-int(time.time()*1000)+999)//1000)+18*max(0,len(json.loads(travel['path_json']))-travel['edge_index']-2)
        lines.append(t('pxe1.travel_destination',lang,name=escape(get_location_name(travel['destination_location_id'],lang)))+' · '+duration(remaining))
    rows = [[InlineKeyboardButton(t('pxe1.attributes',lang),callback_data='bv_attr'),InlineKeyboardButton(t('pxe1.weapon_skills',lang),callback_data='bv_equipped_skills')],
            [InlineKeyboardButton(t('pxe1.build_equipment',lang),callback_data='bv_main')],
            [InlineKeyboardButton(t('pxe1.details',lang),callback_data='bv_character_details'),InlineKeyboardButton(t('pxe1.more',lang),callback_data='bv_character_more')]]
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines),keyboard)
    return '\n'.join(lines),keyboard


def spending_card(player_id,lang,*,selected=None,deltas=None):
    from handlers.build import _load_model,_ATTRIBUTE_LABELS
    player = _load_model(player_id)['player']
    deltas = dict(deltas or {})
    labels = _ATTRIBUTE_LABELS.get(lang,_ATTRIBUTE_LABELS['en'])
    remaining = player['stat_points']-sum(deltas.values())
    lines = [t('pxe1.attributes',lang),t('pxe1.free_points',lang,count=remaining)]
    if selected in ATTRIBUTE_KEYS:
        lines.append(f"{labels[selected]}: {player[selected]} → {player[selected]+deltas.get(selected,0)}")
        rows = [[InlineKeyboardButton('+1',callback_data='bv_spend_add_1'),InlineKeyboardButton(t('pxe1.spend_all',lang),callback_data='bv_spend_add_all')],
                [InlineKeyboardButton(t('pxe1.preview',lang),callback_data='bv_spend_preview'),InlineKeyboardButton(t('pxe1.choose_attribute',lang),callback_data='bv_spend_choose')]]
    else:
        for key in ATTRIBUTE_KEYS:
            lines.append(f"{labels[key]}: {player[key]}"+(f" (+{deltas[key]})" if deltas.get(key) else ''))
        buttons = [InlineKeyboardButton(labels[key],callback_data='bv_spend_select_'+key) for key in ATTRIBUTE_KEYS]
        rows = [buttons[i:i+2] for i in range(0,len(buttons),2)]
    rows.append([InlineKeyboardButton(t('pxe1.reset_options',lang),callback_data='bv_reset_options'),InlineKeyboardButton(t('common.back',lang),callback_data='bv_character')])
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines),keyboard)
    return '\n'.join(lines),keyboard


def spending_preview_card(player_id,lang,deltas):
    from handlers.build import _ATTRIBUTE_LABELS
    preview = attribute_spending_preview(player_id,deltas)
    if not preview.get('success'):
        return preview,None
    labels = _ATTRIBUTE_LABELS.get(lang,_ATTRIBUTE_LABELS['en'])
    lines = [t('pxe1.preview',lang)]
    for key in ATTRIBUTE_KEYS:
        if deltas.get(key):
            lines.append(f"{labels[key]}: {preview['before'][key]} → {preview['attributes'][key]}")
    lines.append(t('pxe1.free_points',lang,count=preview['unspent']))
    lines.append(f"❤️ {preview['max_hp']} · 🔵 {preview['max_mana']} · 🎒 {preview['carry_weight']}")
    lines.append(t('pxe1.no_refill',lang))
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(t('common.confirm',lang),callback_data='bv_spend_apply_'+preview['token'])],
        [InlineKeyboardButton(t('common.back',lang),callback_data='bv_spend_choose')]])
    validate_surface('\n'.join(lines),keyboard)
    return {'success':True},('\n'.join(lines),keyboard)


def weapon_families_card(player_id,lang,page=0):
    from game.build_contract import FAMILIES
    from handlers.build import _family_name
    families = list(FAMILIES)
    pages = max(1,(len(families)+5)//6)
    page = min(max(0,int(page)),pages-1)
    rows = [[InlineKeyboardButton(_family_name(family,lang),callback_data='bv_family_'+family)] for family in families[page*6:(page+1)*6]]
    nav = []
    if page:
        nav.append(InlineKeyboardButton('◀️',callback_data=f'bv_families_page_{page-1}'))
    if page+1<pages:
        nav.append(InlineKeyboardButton('▶️',callback_data=f'bv_families_page_{page+1}'))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(t('common.back',lang),callback_data='bv_equipped_skills')])
    return t('pxe1.other_families',lang),InlineKeyboardMarkup(rows)


def weapon_family_card(player_id,family,lang,*,branch=None):
    from game.build_contract import BRANCH_IDENTITIES,FAMILIES,MAX_SKILL_RANK,RANK_REQUIREMENTS,SKILL_SPECS,SKILL_TREES
    from game.build_progression import family_skill_ranks
    from game.i18n import get_skill_name
    from handlers.build import _load_model,_family_name,_BRANCH_COPY,_c
    model = _load_model(player_id)
    if family not in FAMILIES:
        return t('pxe1.weapon_skills',lang)+'\n'+t('pxe1.unarmed_skills',lang),InlineKeyboardMarkup([
            [InlineKeyboardButton(t('pxe1.other_families',lang),callback_data='bv_families')],
            [InlineKeyboardButton(t('common.back',lang),callback_data='bv_character')]])
    mastery = model['masteries'].get(family) or {'level':1,'skill_points':2}
    lines = [t('pxe1.weapon_skills',lang)+' · '+escape(_family_name(family,lang)),
             t('pxe1.mastery_level',lang,level=mastery['level'])+' · '+str(mastery['skill_points'])+' '+_c(lang,'points')]
    rows = []
    if branch in {'A','B'}:
        conn = get_connection()
        try:
            ranks = family_skill_ranks(player_id,family,conn=conn)
        finally:
            conn.close()
        name,purpose = _BRANCH_COPY.get(lang,_BRANCH_COPY['en'])[BRANCH_IDENTITIES[family][branch]]
        lines.append(escape(name)+' · '+escape(purpose))
        spent = sum(ranks.get(k,0) for k in SKILL_TREES[family][branch][:-1])
        for skill_id in SKILL_TREES[family][branch]:
            rank = ranks.get(skill_id,0)
            spec = SKILL_SPECS[skill_id]
            required = spec.unlock_mastery if rank==0 else RANK_REQUIREMENTS.get(rank+1,21)
            if rank>=MAX_SKILL_RANK:
                reason = _c(lang,'max')
            elif mastery['level']<required:
                reason = t('pxe1.requires_mastery',lang,family=_family_name(family,lang),level=required)
            elif rank==0 and spec.position==4 and spent<8:
                reason = t('pxe1.requires_branch',lang,spent=spent)
            elif mastery['skill_points']<1:
                reason = t('pxe1.requires_point',lang)
            else:
                reason = _c(lang,'ready')
            label = get_skill_name(skill_id,lang)
            lines.append(f'{escape(label)} · {rank}/3 · {escape(reason)}')
            rows.append([InlineKeyboardButton(label,callback_data='bv_skill_'+skill_id)])
        other = 'B' if branch=='A' else 'A'
        other_name = _BRANCH_COPY.get(lang,_BRANCH_COPY['en'])[BRANCH_IDENTITIES[family][other]][0]
        rows.append([InlineKeyboardButton(other_name,callback_data=f'bv_branch_{family}:{other}')])
    else:
        for selected in ('A','B'):
            name = _BRANCH_COPY.get(lang,_BRANCH_COPY['en'])[BRANCH_IDENTITIES[family][selected]][0]
            rows.append([InlineKeyboardButton(name,callback_data=f'bv_branch_{family}:{selected}')])
        rows.append([InlineKeyboardButton(t('pxe1.other_families',lang),callback_data='bv_families')])
    rows.append([InlineKeyboardButton(_c(lang,'reset'),callback_data='bv_reset_'+family),
                 InlineKeyboardButton(t('common.back',lang),callback_data='bv_family_'+family if branch else 'bv_character')])
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines),keyboard,list_view=bool(branch))
    return '\n'.join(lines),keyboard


def skill_card(player_id,skill_id,lang,*,details=False):
    from game.build_contract import MAX_SKILL_RANK,PVP_SKILL_ALLOWLIST,RANK_REQUIREMENTS,SKILL_SPECS,SKILL_TREES,rank_mana_cost
    from game.build_progression import family_skill_ranks
    from game.i18n import get_skill_name
    from handlers.build import _load_model,_family_name,_c,_label,_KIND_LABELS,_TARGET_LABELS,_skill_profile
    spec = SKILL_SPECS.get(skill_id)
    if not spec:
        return weapon_families_card(player_id,lang)
    model = _load_model(player_id)
    mastery = model['masteries'].get(spec.family) or {'level':1,'skill_points':2}
    conn = get_connection()
    try:
        ranks = family_skill_ranks(player_id,spec.family,conn=conn)
    finally:
        conn.close()
    rank = ranks.get(skill_id,0)
    required = spec.unlock_mastery if rank==0 else RANK_REQUIREMENTS.get(rank+1,21)
    spent = sum(ranks.get(k,0) for k in SKILL_TREES[spec.family][spec.branch][:-1])
    reasons = []
    if rank<MAX_SKILL_RANK:
        if mastery['level']<required:
            reasons.append(t('pxe1.requires_mastery',lang,family=_family_name(spec.family,lang),level=required))
        if rank==0 and spec.position==4 and spent<8:
            reasons.append(t('pxe1.requires_branch',lang,spent=spent))
        if mastery['skill_points']<1:
            reasons.append(t('pxe1.requires_point',lang))
    current_rank = max(1,rank)
    lines = [f"<b>{escape(get_skill_name(skill_id,lang))}</b> · {rank}/3",
             escape(_label(_KIND_LABELS,lang,spec.kind)),
             _c(lang,'target')+': '+escape(_label(_TARGET_LABELS,lang,spec.target)),
             t('pxe1.passive_skill',lang) if spec.passive else t('pxe1.skill_cost',lang,mana=rank_mana_cost(spec,current_rank),cooldown=spec.cooldown if spec.cooldown is not None else 0),
             _c(lang,'available_pvp') if skill_id in PVP_SKILL_ALLOWLIST else _c(lang,'pve_only')]
    if reasons:
        lines.extend(reasons)
    rows = []
    if rank<MAX_SKILL_RANK and not reasons:
        rows.append([InlineKeyboardButton(_c(lang,'learn'),callback_data='bv_buy_'+skill_id)])
    if details:
        lines.append(escape(_skill_profile(spec,lang,current_rank)))
        rows.append([InlineKeyboardButton(t('common.back',lang),callback_data='bv_skill_'+skill_id)])
    else:
        rows.append([InlineKeyboardButton(t('pxe1.details',lang),callback_data='bv_skilldetails_'+skill_id)])
        rows.append([InlineKeyboardButton(t('common.back',lang),callback_data=f'bv_branch_{spec.family}:{spec.branch}')])
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines),keyboard,long_detail=details)
    return '\n'.join(lines),keyboard


def redistribution_card(player_id,lang,*,draft=None,selected=None):
    from game.build_progression import ATTRIBUTE_KEYS
    from handlers.build import _load_model,_ATTRIBUTE_LABELS
    player = _load_model(player_id)['player']
    draft = dict(draft or {key:player[key] for key in ATTRIBUTE_KEYS})
    labels = _ATTRIBUTE_LABELS.get(lang,_ATTRIBUTE_LABELS['en'])
    remaining = player['attribute_budget']-sum(draft[key]-1 for key in ATTRIBUTE_KEYS)
    lines = [t('pxe1.redistribute',lang),t('pxe1.free_points',lang,count=remaining)]
    rows = []
    if selected in ATTRIBUTE_KEYS:
        lines.append(f'{labels[selected]}: {player[selected]} → {draft[selected]}')
        lines.append(t('pxe1.reset_only_hubs',lang))
        rows.append([InlineKeyboardButton('−1',callback_data='bv_ad_'+selected),InlineKeyboardButton('+1',callback_data='bv_ai_'+selected)])
        rows.append([InlineKeyboardButton(t('pxe1.choose_attribute',lang),callback_data='bv_reset_attr_choose')])
    else:
        for key in ATTRIBUTE_KEYS:
            lines.append(f'{labels[key]}: {draft[key]}')
        buttons = [InlineKeyboardButton(labels[key],callback_data='bv_reset_attr_'+key) for key in ATTRIBUTE_KEYS]
        rows = [buttons[i:i+2] for i in range(0,len(buttons),2)]
    rows.append([InlineKeyboardButton(t('pxe1.preview',lang),callback_data='bv_attr_preview'),InlineKeyboardButton(t('common.back',lang),callback_data='bv_attr')])
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines),keyboard)
    return '\n'.join(lines),keyboard,draft


async def handle_character_buttons(update,context):
    from handlers.build import _load_model,build_character_details
    from game.build_progression import apply_attribute_spending
    from game.i18n import get_player_lang
    query = update.callback_query
    player_id,lang,data = query.from_user.id,get_player_lang(query.from_user.id),query.data
    draft = context.user_data.setdefault('pxe1_attribute_deltas',{})
    selected = context.user_data.get('pxe1_attribute_selected')
    notice = None
    if data.startswith('bv_spend_select_'):
        selected = data.removeprefix('bv_spend_select_')
        context.user_data['pxe1_attribute_selected'] = selected
        text,keyboard = spending_card(player_id,lang,selected=selected,deltas=draft)
    elif data.startswith('bv_spend_add_'):
        player = _load_model(player_id)['player']
        if selected in ATTRIBUTE_KEYS:
            available = max(0,min(player['stat_points']-sum(draft.values()),100-player[selected]-draft.get(selected,0)))
            amount = available if data.endswith('_all') else min(1,available)
            if amount:
                draft[selected] = draft.get(selected,0)+amount
        text,keyboard = spending_card(player_id,lang,selected=selected,deltas=draft)
    elif data=='bv_spend_preview':
        result,view = spending_preview_card(player_id,lang,draft)
        if view:
            text,keyboard = view
        else:
            notice = t('pxe1.spend_rejected',lang)
            text,keyboard = spending_card(player_id,lang,selected=selected,deltas=draft)
    elif data.startswith('bv_spend_apply_'):
        result = apply_attribute_spending(player_id,data.removeprefix('bv_spend_apply_'))
        notice = t('pxe1.spend_applied' if result.get('success') else 'pxe1.spend_rejected',lang)
        context.user_data['pxe1_attribute_deltas'] = {}
        text,keyboard = spending_card(player_id,lang)
    elif data in {'bv_spend_choose','bv_attr'}:
        text,keyboard = spending_card(player_id,lang,deltas=draft)
    elif data=='bv_reset_options':
        text = t('pxe1.reset_only_hubs',lang)
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(t('pxe1.redistribute',lang),callback_data='bv_attr_reset')],
            [InlineKeyboardButton(t('pxe1.weapon_skills',lang),callback_data='bv_equipped_skills')],
            [InlineKeyboardButton(t('common.back',lang),callback_data='bv_attr')]])
    elif data=='bv_character_more':
        text = t('pxe1.more',lang)
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(t('keyboard.settings',lang),callback_data='bv_settings'),InlineKeyboardButton(t('keyboard.help',lang),callback_data='bv_help')],
            [InlineKeyboardButton(t('common.back',lang),callback_data='bv_character')]])
    elif data=='bv_character_details':
        text,keyboard = build_character_details(player_id,lang)
    elif data=='bv_settings':
        from handlers.settings import build_settings
        text,keyboard = build_settings(player_id,lang)
    elif data=='bv_help':
        text,keyboard = t('help.title',lang)+'\n\n'+t('help.commands',lang),InlineKeyboardMarkup([[InlineKeyboardButton(t('common.back',lang),callback_data='bv_character')]])
    else:
        text,keyboard = character_card(player_id,lang)
    await query.answer(notice or '')
    await query.edit_message_text(text,reply_markup=keyboard,parse_mode='HTML')
