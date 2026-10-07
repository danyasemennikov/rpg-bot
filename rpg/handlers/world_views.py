"""Read projections for Location/Nearby and local-first maps."""

from html import escape
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import get_connection
from game.i18n import get_location_name, get_mob_name, t
from game.locations import WORLD_LOCATIONS, WORLD_ROUTES, get_location, get_location_neighbors, resolve_location_id
from game.player_ui import validate_surface


def _button(label, callback):
    return [InlineKeyboardButton(label, callback_data=callback)]


def _page(entries, page):
    pages = max(1, (len(entries)+5)//6)
    page = min(max(0, int(page)), pages-1)
    return entries[page*6:(page+1)*6], page, pages


def local_entries(player):
    from game.hunting import harvestable_victory_page
    from game.player_activity import player_activity
    from game.profession_resources import RESOURCES, location_sources
    from game.pve_live import list_location_active_pve_encounters, list_location_available_mixed_encounters, list_location_available_spawn_instances
    from game.pvp_live import get_pending_location_encounters
    from game.quest_board import get_player_hunt_contract_state
    from game.regional_opportunities import nearby
    from game.regional_adventures import list_pins
    lang, player_id = player.get('lang', 'ru'), player['telegram_id']
    location = get_location(player['location_id'])
    categories = {key: [] for key in ('encounters', 'gathering', 'services', 'exits', 'more')}
    priority = []
    conn = get_connection()
    try:
        finale = conn.execute("SELECT 1 FROM player_feedback_events WHERE player_id=? AND event_kind='chapter_finale' AND state IN ('pending','presented')", (player_id,)).fetchone()
        activity = player_activity(conn, player_id)
        if finale:
            priority.append((t('pxe1.finale_resume', lang), 'px:finale:show'))
        if activity:
            if activity['kind'] == 'pve':
                callback = f"pve_enter_{activity['ref']}"
            elif activity['kind'] == 'pvp':
                callback = 'pvp_refresh'
            else:
                callback = 'px:home'
            priority.append((t('pxe1.encounter.resume', lang), callback))
        near_players = [dict(r) for r in conn.execute('SELECT telegram_id,name,level FROM players WHERE location_id=? AND telegram_id<>? ORDER BY level DESC,telegram_id', (player['location_id'], player_id))]
    finally:
        conn.close()
    state = get_player_hunt_contract_state(player_id)
    if state and state['status'] in {'active', 'completed'}:
        contract = state['contract']
        claim_places = {resolve_location_id(k) for k in (contract.claim_locations or contract.board_locations)}
        if state['status'] == 'completed' and resolve_location_id(player['location_id']) in claim_places:
            priority.append((t('pxe1.quest.turn_in', lang), 'alpha_assignment'))
        categories['more'].append((t('pxe1.open_assignment', lang), 'alpha_assignment'))
    if harvestable_victory_page(player_id)[0]:
        priority.append((t('chapter.harvest', lang), 'alpha_harvest'))
    encounters = list_location_active_pve_encounters(location_id=player['location_id'])
    conn = get_connection()
    try:
        deadlines = {r['encounter_id']: r['formation_deadline_ms'] or 0 for r in conn.execute('SELECT encounter_id,formation_deadline_ms FROM pve_encounters WHERE location_id=?', (player['location_id'],))}
    finally:
        conn.close()
    for encounter in sorted(encounters, key=lambda r: (deadlines.get(r['encounter_id'], 0), r['encounter_id'])):
        label = get_mob_name(encounter['mob_id'], lang)
        entry = (t('pxe1.encounter.open_label', lang, name=label, count=encounter['participant_count']), f"pve_enter_{encounter['encounter_id']}")
        categories['encounters'].append(entry)
        if encounter.get('joinable'):
            priority.append(entry)
    seen = set()
    for spawn in list_location_available_spawn_instances(location_id=player['location_id']):
        key = (spawn['mob_id'], spawn['spawn_profile'], spawn['special_spawn_key'])
        if key in seen:
            continue
        seen.add(key)
        label = get_mob_name(spawn['mob_id'], lang)
        if spawn['special_spawn_key']:
            from game.i18n import get_special_spawn_name
            label = get_special_spawn_name(spawn['special_spawn_key'], lang)
        elif spawn['spawn_profile'] == 'elite':
            label += ' · ' + t('location.spawn_profile_elite', lang)
        categories['encounters'].append((label, f"fight_spawn_{spawn['spawn_instance_id']}"))
    for mixed in list_location_available_mixed_encounters(location_id=player['location_id']):
        label = str(mixed['label'].get(lang) or mixed['label'].get('en'))
        label += ' ×'+str(len(mixed['units']))
        categories['encounters'].append((label, f"fight_mixed_{mixed['recipe_id']}"))
    for encounter in get_pending_location_encounters(location_id=player['location_id'], limit=100):
        label = t('pxe1.pvp_pair', lang, attacker=encounter['attacker_name'], defender=encounter['defender_name'])
        categories['encounters'].append((label, f"pvp_view_{encounter['id']}"))
    if not location['safe']:
        for target in near_players:
            categories['encounters'].append((t('pxe1.player_nearby', lang, name=target['name'], level=target['level']), f"pvp_preview_{target['telegram_id']}"))
    professions = dict.fromkeys(RESOURCES[item].profession_key for item, chance in location_sources(player['location_id']) if chance > 0 and item in RESOURCES)
    for profession in professions:
        categories['gathering'].append((t('professions.names.'+profession, lang), f'px:gatherpreview:{profession}'))
    service_keys = [('shop', 'location.shop_btn', 'shop'), ('quest_board', 'location.quests_btn', 'quest_board'),
                    ('craftsmen_guild', 'location.service_craftsmen_guild', 'craftsmen_guild'), ('inn', 'location.inn_btn', 'inn')]
    for service, key, callback in service_keys:
        if service in location.get('services', []):
            categories['services'].append((t(key, lang), callback))
    categories['exits'] = [(get_location_name(k, lang), f'goto_{k}') for k in get_location_neighbors(player['location_id'])]
    pinned_projects = {pin['owner_id'] for pin in list_pins(player_id) if pin['owner_kind']=='project'}
    for row in nearby(player):
        from handlers.regional import _title, _detail_kind
        if row['kind'] == 'work_link':
            entry = (t('pxe1.journal.local_work',lang),'rv:v:w:0:all')
        else:
            entry = (_title(row['kind'], row['content_id'], lang), f"rv:d:{_detail_kind(row)}:{row['content_id']}")
        categories['more'].append(entry)
        if row['kind'] == 'project' and row.get('status') == 'active' and row['content_id'] in pinned_projects:
            priority.append(entry)
    return priority, categories


def location_card(player, *, category=None, page=0):
    from game.locations import get_location_security_tier
    lang = player.get('lang', 'ru')
    priority, categories = local_entries(player)
    lines = [f"📍 <b>{escape(get_location_name(player['location_id'], lang))}</b>",
             f"❤️ {player['hp']}/{player['max_hp']} · 🔵 {player['mana']}/{player['max_mana']} · 💰 {player['gold']}",
             t('pxe1.location.security.'+get_location_security_tier(player['location_id']),lang)]
    rows = []
    if category:
        visible, page, pages = _page(categories.get(category, []), page)
        lines.append(t('pxe1.local_categories.'+category, lang))
        for label, callback in visible:
            lines.append('• '+escape(label))
            rows.append(_button(label, callback))
        if not visible:
            lines.append(t('pxe1.location.nothing_actionable', lang))
        nav = []
        if page:
            nav.append(InlineKeyboardButton('◀️', callback_data=f'px:local:{category}:{page-1}'))
        if page+1 < pages:
            nav.append(InlineKeyboardButton('▶️', callback_data=f'px:local:{category}:{page+1}'))
        if nav:
            rows.append(nav)
        rows.append(_button(t('gear.back_btn', lang), 'px:local:home:0'))
    else:
        seen = set()
        for label, callback in priority:
            if callback in seen:
                continue
            seen.add(callback)
            rows.append(_button(label, callback))
            lines.append('• '+escape(label))
            if len(rows) == 3:
                break
        groups = [InlineKeyboardButton(t('pxe1.local_categories.'+key, lang), callback_data=f'px:local:{key}:0') for key, entries in categories.items() if entries]
        # Priority actions use full-width labels; short category labels share rows.
        rows.extend([groups[i:i+2] for i in range(0, len(groups), 2)])
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines), keyboard, list_view=bool(category))
    return '\n'.join(lines), keyboard


def current_region(player):
    route = str((get_location(player['location_id']) or {}).get('route_id') or 'core')
    return 'route_frostspine' if route == 'route_old_mine_stub' else route


def map_card(player, *, region=None, page=0, world=False):
    lang = player.get('lang', 'ru')
    current = resolve_location_id(player['location_id'])
    lines = [t('keyboard.map', lang), t('pxe1.map.you_are_here',lang,name=escape(get_location_name(current,lang)))]
    if world:
        entries = [(get_location_name(row['hub_location_id'] or row['entry_location_id'], lang), f'px:mapregion:{key}:0')
                   for key, row in WORLD_ROUTES.items() if key != 'route_old_mine_stub']
        prefix = 'px:world:'
    else:
        region = region or current_region(player)
        if region not in WORLD_ROUTES:
            region = current_region(player)
        if region == 'core':
            nodes = get_location_neighbors('capital_city')
        else:
            nodes = [k for k, location in WORLD_LOCATIONS.items() if location.get('route_id') == region and k != current]
            if region == 'route_frostspine':
                nodes += [k for k, location in WORLD_LOCATIONS.items() if location.get('route_id') == 'route_old_mine_stub']
            # The mine opens its spur rather than a distant first page.
            if (get_location(current) or {}).get('route_id') == 'route_old_mine_stub' and page == 0:
                nodes.sort(key=lambda k: (k != 'old_mine_entrance', k not in get_location_neighbors(current)))
        entries = [(get_location_name(k, lang), f'goto_{k}') for k in nodes]
        prefix = f'px:mapregion:{region}:'
    visible, page, pages = _page(entries, page)
    rows = []
    for label, callback in visible:
        lines.append('• '+escape(label))
        rows.append(_button(label, callback))
    nav = []
    if page:
        nav.append(InlineKeyboardButton('◀️', callback_data=prefix+str(page-1)))
    if page+1 < pages:
        nav.append(InlineKeyboardButton('▶️', callback_data=prefix+str(page+1)))
    if nav:
        rows.append(nav)
    if not world:
        rows.append(_button(t('pxe1.map.world', lang), 'px:world:0'))
    rows.append(_button(t('gear.back_btn', lang), 'px:local:home:0'))
    keyboard = InlineKeyboardMarkup(rows)
    validate_surface('\n'.join(lines), keyboard, list_view=True)
    return '\n'.join(lines), keyboard
