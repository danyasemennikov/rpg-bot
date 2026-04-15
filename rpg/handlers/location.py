# ============================================================
# location.py — отображение локации и агрессия мобов
# ============================================================

import sys, random, asyncio, re
from types import SimpleNamespace
sys.path.append('/content/rpg_bot')

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from database import get_player, get_connection, is_in_battle
from game.locations import get_location, get_connected_locations
from game.gathering_foundation import build_location_gather_source_profiles
from game.mobs import get_mob
from game.gear_instances import grant_item_to_player
from game.items_data import get_item
from game.i18n import t, get_player_lang, get_mob_name, get_location_name, get_location_desc, get_item_name
from game.pve_live import (
    can_join_open_world_pve_encounter,
    get_open_world_pve_encounter_detail,
    join_open_world_pve_encounter,
    leave_open_world_pve_encounter,
    list_location_active_pve_encounters,
    list_location_available_spawn_instances,
)
from game.pvp_live import (
    advance_engagement_to_live_battle_if_ready,
    apply_illegal_aggression_penalties,
    can_join_pending_encounter_side,
    can_create_live_engagement,
    create_live_engagement,
    get_engagement_reinforcement_state,
    get_pending_encounter_detail,
    get_pending_location_encounters,
    get_pending_reinforcement_invite_for_player,
    get_pending_player_engagement,
    get_pending_reinforcement_engagement_for_player,
    has_active_live_pvp_engagement,
    is_player_joined_pending_encounter,
    invite_reinforcement_ally,
    is_pvp_mobility_blocked,
    get_manual_pvp_action_labels,
    is_player_busy_with_live_pvp,
    join_pending_encounter_side,
    list_reinforcement_candidates,
    respond_to_reinforcement_invite,
    resolve_engagement_escape,
    resolve_live_battle_turn,
)
from game.pvp_rules import (
    clear_respawn_protection,
    clear_respawn_protection_on_dangerous_reentry,
    get_attack_block_reason,
    is_aggression_illegal,
    is_target_attackable,
    should_apply_red_flag,
)

CURATED_EQUIPMENT_VENDOR_STOCK = {
    'village': [
        {'item_id': 'oak_guard_shield', 'level_min': 4},
        {'item_id': 'apprentice_focus_orb', 'level_min': 3},
        {'item_id': 'novice_censer', 'level_min': 3},
        {'item_id': 'militia_cuirass', 'level_min': 4},
        {'item_id': 'acolyte_robe', 'level_min': 4},
        {'item_id': 'band_of_precision', 'level_min': 5},
        {'item_id': 'ring_of_quiet_mind', 'level_min': 5},
        # Temporary bridge before full apex/world-boss rollout (Phase 3 routing).
        {'item_id': 'ashen_core', 'level_min': 12},
    ],
}


def _should_use_pvp_only_location_view(player: dict) -> bool:
    return bool(player.get('in_battle')) and is_player_busy_with_live_pvp(int(player['telegram_id']))


def _build_live_pvp_runtime_stats(player: dict, battle: dict, engagement_row) -> dict:
    runtime = {
        'hp': player['hp'],
        'max_hp': player['max_hp'],
        'mana': player['mana'],
        'max_mana': player['max_mana'],
    }
    if not battle or not engagement_row:
        return runtime
    player_id = int(player['telegram_id'])
    attacker_id = int(engagement_row['attacker_id'])
    if player_id == attacker_id:
        runtime['hp'] = int(battle.get('attacker_hp', runtime['hp']))
        runtime['max_hp'] = int(battle.get('attacker_max_hp', runtime['max_hp']))
        runtime['mana'] = int(battle.get('attacker_mana', runtime['mana']))
        runtime['max_mana'] = int(battle.get('attacker_max_mana', runtime['max_mana']))
    else:
        runtime['hp'] = int(battle.get('defender_hp', runtime['hp']))
        runtime['max_hp'] = int(battle.get('defender_max_hp', runtime['max_hp']))
        runtime['mana'] = int(battle.get('defender_mana', runtime['mana']))
        runtime['max_mana'] = int(battle.get('defender_max_mana', runtime['max_mana']))
    return runtime


def _format_seconds_short(total_seconds: int) -> str:
    minutes = max(0, int(total_seconds)) // 60
    seconds = max(0, int(total_seconds)) % 60
    return f"{minutes:02d}:{seconds:02d}"


LOCATION_ACTION_SNAPSHOT_KEY = 'location_action_snapshot'
_TOKEN_COMMAND_RE = re.compile(
    r'^(?P<snapshot>s\d+)\s+(?P<token>(?:p|m|pv|pe|sv)\d+)\s+(?P<action>[a-z_]+)$'
)
_SUPPORTED_LOCATION_SERVICE_ACTIONS = {
    'shop': ('shop', 'shop'),
}


def _format_spawn_profile_marker(profile: str | None, lang: str) -> str:
    normalized = str(profile or 'normal').strip().lower()
    if normalized == 'elite':
        return t('location.spawn_profile_elite', lang)
    if normalized == 'rare':
        return t('location.spawn_profile_rare', lang)
    return ''


def _ensure_location_context_user_data(context: ContextTypes.DEFAULT_TYPE) -> dict:
    user_data = getattr(context, 'user_data', None)
    if user_data is None:
        user_data = {}
        setattr(context, 'user_data', user_data)
    return user_data


def _next_snapshot_tag(context: ContextTypes.DEFAULT_TYPE) -> str:
    user_data = _ensure_location_context_user_data(context)
    next_seq = int(user_data.get('location_action_snapshot_seq', 0) or 0) + 1
    user_data['location_action_snapshot_seq'] = next_seq
    return f"s{next_seq}"


def build_pvp_encounter_detail_message(player: dict, encounter_id: int) -> tuple[str, InlineKeyboardMarkup]:
    lang = player.get('lang', 'ru')
    detail = get_pending_encounter_detail(engagement_id=encounter_id)
    if not detail or detail['engagement_state'] != 'pending':
        return t('location.pvp_no_engagement', lang), InlineKeyboardMarkup([])
    text = t(
        'location.pvp_detail_header',
        lang,
        id=detail['id'],
        location=get_location_name(detail['location_id'], lang),
        time_left=_format_seconds_short(detail['seconds_until_start']),
    ) + '\n'
    text += t('location.pvp_detail_core', lang, attacker=detail['attacker_name'], defender=detail['defender_name']) + '\n'
    text += t('location.pvp_detail_side', lang, side=t('location.pvp_side_initiator', lang), players=', '.join(detail['initiator_names'])) + '\n'
    text += t('location.pvp_detail_side', lang, side=t('location.pvp_side_defender', lang), players=', '.join(detail['defender_names'])) + '\n'

    keyboard_rows: list[list[InlineKeyboardButton]] = []
    viewer_id = int(player['telegram_id'])
    can_join_initiator, _ = can_join_pending_encounter_side(
        engagement_row=detail,
        player_id=viewer_id,
        side='initiator',
    )
    can_join_defender, _ = can_join_pending_encounter_side(
        engagement_row=detail,
        player_id=viewer_id,
        side='defender',
    )
    if can_join_initiator or can_join_defender:
        join_row: list[InlineKeyboardButton] = []
        if can_join_initiator:
            join_row.append(InlineKeyboardButton(
                t('location.pvp_join_initiator_btn', lang),
                callback_data=f"pvp_join_{detail['id']}_initiator",
            ))
        if can_join_defender:
            join_row.append(InlineKeyboardButton(
                t('location.pvp_join_defender_btn', lang),
                callback_data=f"pvp_join_{detail['id']}_defender",
            ))
        if join_row:
            keyboard_rows.append(join_row)
    else:
        text += t('location.pvp_join_commitment_notice', lang) + '\n'
    return text, InlineKeyboardMarkup(keyboard_rows)


def build_pve_encounter_detail_message(player: dict, encounter_id: str) -> tuple[str, InlineKeyboardMarkup]:
    lang = player.get('lang', 'ru')
    detail = get_open_world_pve_encounter_detail(encounter_id=encounter_id)
    if not detail or detail.get('status') != 'active':
        return t('location.pve_no_encounter', lang), InlineKeyboardMarkup([])

    profile_marker = _format_spawn_profile_marker(str(detail.get('spawn_profile') or 'normal'), lang)
    mob_name = f"{profile_marker} {get_mob_name(str(detail.get('mob_id') or ''), lang)}".strip()
    status_key = 'location.pve_status_locked'
    can_join, _ = can_join_open_world_pve_encounter(
        encounter_id=encounter_id,
        player_id=int(player['telegram_id']),
    )
    participant_ids = {
        int(pid) for pid in detail.get('participant_player_ids', [])
    } if isinstance(detail.get('participant_player_ids'), list) else set()
    is_participant = int(player['telegram_id']) in participant_ids
    if bool(detail.get('joinable')):
        if is_participant:
            status_key = 'location.pve_status_already_joined'
        elif can_join:
            status_key = 'location.pve_status_joinable'
        else:
            status_key = 'location.pve_status_unavailable'
    else:
        status_key = 'location.pve_status_locked'

    text = t(
        'location.pve_detail_header',
        lang,
        id=detail['encounter_id'],
        mob=mob_name,
        players=int(detail.get('participant_count', 0)),
        join_state=t(status_key, lang),
    )
    text += '\n' + t(
        'location.pve_start_policy_open' if bool(detail.get('joinable')) else 'location.pve_start_policy_locked',
        lang,
    )
    keyboard_rows: list[list[InlineKeyboardButton]] = []

    if can_join:
        keyboard_rows.append([InlineKeyboardButton(
            t('location.pve_join_btn', lang),
            callback_data=f"pve_join_{detail['encounter_id']}",
        )])
    if is_participant and bool(detail.get('joinable')):
        keyboard_rows.append([InlineKeyboardButton(
            t('location.pve_leave_btn', lang),
            callback_data=f"pve_leave_{detail['encounter_id']}",
        )])
    if is_participant:
        keyboard_rows.append([InlineKeyboardButton(
            t('location.pve_enter_btn', lang),
            callback_data=f"pve_enter_{detail['encounter_id']}",
        )])
    return text, InlineKeyboardMarkup(keyboard_rows)


def get_curated_shop_stock(location_id: str, player_level: int) -> list[dict]:
    """Возвращает доступный список витрины магазина для локации и уровня."""
    stock_rows = CURATED_EQUIPMENT_VENDOR_STOCK.get(location_id, [])
    available = []
    for row in stock_rows:
        item = get_item(row['item_id'])
        if not item:
            continue
        level_min = row.get('level_min', item.get('req_level', 1))
        if player_level < level_min:
            continue
        if item.get('buy_price', 0) <= 0:
            continue
        available.append({
            'item_id': row['item_id'],
            'level_min': level_min,
            'price': item['buy_price'],
        })
    return available


def try_buy_curated_shop_item(telegram_id: int, location_id: str, player_level: int, item_id: str) -> dict:
    """Покупка предмета из витрины магазина. Возвращает статус операции."""
    stock_by_id = {
        row['item_id']: row
        for row in CURATED_EQUIPMENT_VENDOR_STOCK.get(location_id, [])
    }
    stock_row = stock_by_id.get(item_id)
    if not stock_row:
        return {'ok': False, 'reason': 'not_available'}

    item = get_item(item_id)
    if not item:
        return {'ok': False, 'reason': 'not_available'}

    level_min = stock_row.get('level_min', item.get('req_level', 1))
    if player_level < level_min:
        return {'ok': False, 'reason': 'level_required', 'required_level': level_min}

    price = item.get('buy_price', 0)
    conn = get_connection()
    player_row = conn.execute('SELECT gold FROM players WHERE telegram_id=?', (telegram_id,)).fetchone()
    if not player_row:
        conn.close()
        return {'ok': False, 'reason': 'not_available'}

    if player_row['gold'] < price:
        conn.close()
        return {'ok': False, 'reason': 'not_enough_gold', 'price': price}

    conn.execute(
        'UPDATE players SET gold=gold-? WHERE telegram_id=?',
        (price, telegram_id),
    )
    conn.commit()
    conn.close()

    grant_item_to_player(
        telegram_id,
        item_id,
        quantity=1,
        source='shop',
        source_level=max(player_level, level_min),
    )
    return {'ok': True, 'price': price}


def build_shop_message(player: dict, location: dict) -> tuple[str, InlineKeyboardMarkup]:
    lang = player.get('lang', 'ru')
    stock_rows = CURATED_EQUIPMENT_VENDOR_STOCK.get(location['id'], [])
    text = t('location.shop_title', lang) + '\n\n'
    keyboard = []

    if not stock_rows:
        text += t('location.shop_empty', lang)
    else:
        for stock_row in stock_rows:
            item = get_item(stock_row['item_id'])
            if not item:
                continue
            item_name = get_item_name(stock_row['item_id'], lang)
            req_level = stock_row.get('level_min', item.get('req_level', 1))
            price = item.get('buy_price', 0)
            text += t(
                'location.shop_entry',
                lang,
                name=item_name,
                level=req_level,
                price=price,
            ) + '\n'
            if player['level'] >= req_level:
                keyboard.append([InlineKeyboardButton(
                    t('location.shop_buy_btn', lang, name=item_name, price=price),
                    callback_data=f"shop_buy_{stock_row['item_id']}",
                )])

    keyboard.append([InlineKeyboardButton(t('location.shop_back_btn', lang), callback_data='shop_back')])
    return text, InlineKeyboardMarkup(keyboard)

# ────────────────────────────────────────
# ОТОБРАЖЕНИЕ ЛОКАЦИИ
# ────────────────────────────────────────

def build_location_message(
    player: dict,
    location: dict,
    *,
    pvp_only_view: bool = False,
    include_action_map: bool = False,
    snapshot_tag: str | None = None,
) -> tuple:
    """Возвращает (текст, клавиатура) для текущей локации."""
    lang = player.get('lang', 'ru')

    if location['safe']:
        lvl_range = t('location.safe_zone', lang)
    else:
        lvl_range = t('location.level_range', lang,
                      min=location['level_min'],
                      max=location['level_max'])

    text  = f"📍 <b>{get_location_name(location['id'], lang)}</b>  |  {lvl_range}\n"
    text += f"<i>{get_location_desc(location['id'], lang)}</i>\n\n"

    keyboard = []
    token_actions: dict[str, str] = {}
    players_nearby_lines: list[str] = []
    players_nearby_cmds: list[str] = []
    pvp_encounter_lines: list[str] = []
    pvp_encounter_cmds: list[str] = []
    pve_encounter_lines: list[str] = []
    pve_encounter_cmds: list[str] = []
    mob_lines: list[str] = []
    mob_cmds: list[str] = []
    service_cmds: list[str] = []
    snapshot_tag = (snapshot_tag or 's1').lower()

    def _register_action(command_suffix: str, callback_data: str, command_lines: list[str]) -> None:
        full_command = f'{snapshot_tag} {command_suffix}'
        token_actions[full_command] = callback_data
        command_lines.append(full_command)

    if not pvp_only_view:
        service_token_index = 1
        for service_id in location.get('services', []) or []:
            service_action = _SUPPORTED_LOCATION_SERVICE_ACTIONS.get(str(service_id))
            if not service_action:
                continue
            action_word, callback_data = service_action
            token = f"sv{service_token_index}"
            _register_action(f'{token} {action_word}', callback_data, service_cmds)
            service_token_index += 1

    # ── PvP nearby players ──
    conn = get_connection()
    nearby_players = conn.execute(
        '''
        SELECT telegram_id, name, level
        FROM players
        WHERE location_id=? AND telegram_id!=?
        ORDER BY level DESC, telegram_id ASC
        LIMIT 5
        ''',
        (location['id'], player['telegram_id']),
    ).fetchall()
    conn.close()
    if nearby_players and not location['safe'] and not pvp_only_view:
        player_token_index = 1
        for row in nearby_players:
            is_busy = is_player_busy_with_live_pvp(int(row['telegram_id']))
            busy_tag = f" {t('location.pvp_busy_tag', lang)}" if is_busy else ""
            token = f"p{player_token_index}"
            players_nearby_lines.append(f"{token} — {row['name']}  {t('common.level_short', lang)}{row['level']}{busy_tag}")
            if not is_busy:
                _register_action(f'{token} attack', f"pvp_attack_{row['telegram_id']}", players_nearby_cmds)
            player_token_index += 1

    if not pvp_only_view:
        prep_encounters = get_pending_location_encounters(location_id=location['id'], limit=3)
        if prep_encounters:
            pvp_token_index = 1
            for encounter in prep_encounters:
                token = f"pv{pvp_token_index}"
                pvp_encounter_lines.append(
                    f"{token} — " + t(
                    'location.pvp_encounter_row',
                    lang,
                    id=encounter['id'],
                    attacker=encounter['attacker_name'],
                    defender=encounter['defender_name'],
                    time_left=_format_seconds_short(encounter['seconds_until_start']),
                    initiator_count=encounter['initiator_side_count'],
                    defender_count=encounter['defender_side_count'],
                ))
                _register_action(f'{token} view', f"pvp_view_{encounter['id']}", pvp_encounter_cmds)
                pvp_token_index += 1

    player_id = int(player['telegram_id'])
    engagement_row = get_pending_player_engagement(player_id)
    if not engagement_row:
        engagement_row = get_pending_reinforcement_engagement_for_player(player_id)
    runtime_stats = None
    if engagement_row:
        state, payload = advance_engagement_to_live_battle_if_ready(engagement_row)
        is_live_participant = player_id in {
            int(engagement_row['attacker_id']),
            int(engagement_row['defender_id']),
        }
        if state == 'pending':
            text += t('location.pvp_pending', lang) + '\n'
            reinforcement_state = get_engagement_reinforcement_state(engagement_id=int(engagement_row['id']))
            initiator_state = reinforcement_state.get('initiator') or {}
            defender_state = reinforcement_state.get('defender') or {}
            text += t(
                'location.pvp_reinforcement_state',
                lang,
                initiator=initiator_state.get('ally_name', t('location.pvp_reinforcement_none', lang)),
                initiator_status=t(f"location.pvp_reinforcement_status_{initiator_state.get('status', 'none')}", lang),
                defender=defender_state.get('ally_name', t('location.pvp_reinforcement_none', lang)),
                defender_status=t(f"location.pvp_reinforcement_status_{defender_state.get('status', 'none')}", lang),
            ) + '\n'
            if is_live_participant:
                keyboard.append([InlineKeyboardButton(
                    t('location.pvp_escape_btn', lang),
                    callback_data=f"pvp_escape_{engagement_row['id']}",
                )])
                candidates = list_reinforcement_candidates(
                    engagement_row=engagement_row,
                    inviter_id=player_id,
                    limit=2,
                )
                for candidate in candidates:
                    keyboard.append([InlineKeyboardButton(
                        t('location.pvp_reinforcement_invite_btn', lang, name=candidate['name']),
                        callback_data=f"pvp_invite_{engagement_row['id']}_{candidate['telegram_id']}",
                    )])
            pending_invite = get_pending_reinforcement_invite_for_player(
                engagement_id=int(engagement_row['id']),
                ally_id=player_id,
            )
            if pending_invite:
                text += t('location.pvp_reinforcement_invited_notice', lang) + '\n'
                keyboard.append([
                    InlineKeyboardButton(
                        t('location.pvp_reinforcement_accept_btn', lang),
                        callback_data=f"pvp_reinf_accept_{engagement_row['id']}",
                    ),
                    InlineKeyboardButton(
                        t('location.pvp_reinforcement_decline_btn', lang),
                        callback_data=f"pvp_reinf_decline_{engagement_row['id']}",
                    ),
                ])
            else:
                if is_player_joined_pending_encounter(
                    engagement_id=int(engagement_row['id']),
                    player_id=player_id,
                ):
                    text += t('location.pvp_reinforcement_accepted_notice', lang) + '\n'
        elif state == 'converted_to_battle':
            if is_live_participant:
                battle = payload.get('battle') or {}
                runtime_stats = _build_live_pvp_runtime_stats(player, battle, engagement_row)
                turn_owner_id = int(battle.get('turn_owner', 0) or 0)
                text += t(
                    'location.pvp_live_status',
                    lang,
                    attacker_hp=battle.get('attacker_hp', 0),
                    defender_hp=battle.get('defender_hp', 0),
                    turn=t(
                        'location.pvp_turn_you' if turn_owner_id == int(player['telegram_id']) else 'location.pvp_turn_enemy',
                        lang,
                    ),
                ) + '\n'
                if turn_owner_id == int(player['telegram_id']):
                    for action_id, action_label in get_manual_pvp_action_labels(
                        player_id=int(player['telegram_id']),
                        lang=lang,
                        battle=battle,
                        attacker_id=int(engagement_row['attacker_id']),
                        defender_id=int(engagement_row['defender_id']),
                    ):
                        keyboard.append([InlineKeyboardButton(
                            action_label,
                            callback_data=f"pvp_act_{engagement_row['id']}_{action_id}",
                        )])
            else:
                text += t('location.pvp_reinforcement_commitment_released', lang) + '\n'

    # ── Open-world PvE: active encounters + available spawns ──
    if not pvp_only_view:
        active_pve_encounters = list_location_active_pve_encounters(location_id=location['id'])
        if active_pve_encounters:
            pve_token_index = 1
            for encounter in active_pve_encounters:
                mob_id = str(encounter.get('mob_id') or '')
                profile_marker = _format_spawn_profile_marker(str(encounter.get('spawn_profile') or 'normal'), lang)
                participant_ids = {
                    int(pid) for pid in encounter.get('participant_player_ids', [])
                } if isinstance(encounter.get('participant_player_ids'), list) else set()
                is_participant = int(player['telegram_id']) in participant_ids
                token = f"pe{pve_token_index}"
                pve_encounter_lines.append(
                    f"{token} — " + t(
                    'location.pve_encounter_row',
                    lang,
                    id=encounter['encounter_id'],
                    mob=f"{profile_marker} {get_mob_name(mob_id, lang)}".strip(),
                    players=int(encounter.get('participant_count', 0)),
                    join_state=t(
                        (
                            'location.pve_status_already_joined'
                            if is_participant
                            else 'location.pve_status_joinable'
                        ) if bool(encounter.get('joinable')) else 'location.pve_status_locked',
                        lang,
                    ),
                ))
                _register_action(f'{token} view', f"pve_view_{encounter['encounter_id']}", pve_encounter_cmds)
                can_join, _ = can_join_open_world_pve_encounter(
                    encounter_id=str(encounter['encounter_id']),
                    player_id=int(player['telegram_id']),
                )
                if can_join:
                    _register_action(f'{token} join', f"pve_join_{encounter['encounter_id']}", pve_encounter_cmds)
                if is_participant:
                    _register_action(f'{token} enter', f"pve_enter_{encounter['encounter_id']}", pve_encounter_cmds)
                    if bool(encounter.get('joinable')):
                        _register_action(f'{token} leave', f"pve_leave_{encounter['encounter_id']}", pve_encounter_cmds)
                pve_token_index += 1

        available_spawns = list_location_available_spawn_instances(location_id=location['id'])
        if available_spawns:
            mob_token_index = 1
            mob_counter: dict[tuple[str, str], int] = {}
        for spawn in available_spawns:
            mob_id = str(spawn.get('mob_id') or '')
            spawn_profile = str(spawn.get('spawn_profile') or 'normal')
            mob = get_mob(mob_id)
            if not mob:
                continue
            agr_tag  = t('location.aggressive_tag', lang) if mob['aggressive'] else ""
            lvl_diff = mob['level'] - player['level']

            if lvl_diff >= 3:
                diff = t('location.diff_deadly', lang)
            elif lvl_diff >= 1:
                diff = t('location.diff_hard', lang)
            elif lvl_diff == 0:
                diff = t('location.diff_normal', lang)
            elif lvl_diff >= -2:
                diff = t('location.diff_easy', lang)
            else:
                diff = t('location.diff_unknown', lang)

            token = f"m{mob_token_index}"
            mob_key = (mob_id, spawn_profile)
            mob_counter[mob_key] = mob_counter.get(mob_key, 0) + 1
            dup_suffix = f" #{mob_counter[mob_key]}" if mob_counter[mob_key] > 1 else ""
            profile_marker = _format_spawn_profile_marker(spawn_profile, lang)
            mob_label = f"{profile_marker} {get_mob_name(mob_id, lang)}".strip()
            mob_lines.append(
                f"{token} — {diff} {mob_label}{dup_suffix}  "
                f"{t('common.level_short', lang)}{mob['level']}{agr_tag}"
            )
            _register_action(f'{token} fight', f"fight_spawn_{spawn['spawn_instance_id']}", mob_cmds)
            mob_token_index += 1

    # ── Ресурсы ──
    gather_profiles = build_location_gather_source_profiles(location['id'])
    if gather_profiles and not pvp_only_view:
        text += t('location.gather_title', lang) + " "
        text += ", ".join(get_item_name(profile.item_id, lang) for profile in gather_profiles) + "\n"
        keyboard.append([InlineKeyboardButton(
            t('location.gather_btn', lang), callback_data="gather"
        )])
        text += "\n"

    # ── Переходы в другие локации ──
    connected = get_connected_locations(location['id'])
    if connected and not pvp_only_view:
        text += t('location.travel_title', lang) + '\n'
        nav_buttons = []
        for conn_loc in connected:
            req_level = conn_loc['level_min']
            can_go    = player['level'] >= req_level or conn_loc['safe']
            if can_go:
                label = t('location.go_to_btn', lang, name=get_location_name(conn_loc['id'], lang))
                cb    = f"goto_{conn_loc['id']}"
            else:
                label = t('location.locked_btn', lang, name=get_location_name(conn_loc['id'], lang), req=req_level)
                cb    = f"locked_{conn_loc['id']}"
            nav_buttons.append(InlineKeyboardButton(label, callback_data=cb))
        keyboard.append(nav_buttons)

    if players_nearby_lines:
        text += t('location.players_nearby', lang) + '\n'
        text += '\n'.join(players_nearby_lines) + '\n\n'
    if pvp_encounter_lines:
        text += t('location.pvp_encounters_title', lang) + '\n'
        text += '\n'.join(pvp_encounter_lines) + '\n\n'
    if pve_encounter_lines:
        text += t('location.pve_encounters_title', lang) + '\n'
        text += '\n'.join(pve_encounter_lines) + '\n\n'
    if mob_lines:
        text += t('location.mobs_nearby', lang) + '\n'
        text += '\n'.join(mob_lines) + '\n\n'
    action_lines = service_cmds + players_nearby_cmds + pvp_encounter_cmds + pve_encounter_cmds + mob_cmds
    if action_lines:
        text += t('location.actions_title', lang) + '\n'
        text += '\n'.join(f"• {line}" for line in action_lines[:20]) + '\n'
        text += t('location.actions_hint', lang, snapshot=snapshot_tag) + '\n\n'

    # ── Статус игрока ──
    if runtime_stats is None:
        runtime_stats = {
            'hp': player['hp'],
            'max_hp': player['max_hp'],
            'mana': player['mana'],
            'max_mana': player['max_mana'],
        }
    text += f"\n❤️ {runtime_stats['hp']}/{runtime_stats['max_hp']}  " \
            f"🔵 {runtime_stats['mana']}/{runtime_stats['max_mana']}  " \
            f"💰 {player['gold']}"

    keyboard_markup = InlineKeyboardMarkup(keyboard)
    if not include_action_map:
        return text, keyboard_markup

    snapshot = {
        'snapshot_tag': snapshot_tag,
        'player_id': int(player['telegram_id']),
        'location_id': str(location['id']),
        'actions': token_actions,
    }
    return text, keyboard_markup, snapshot


# ────────────────────────────────────────
# КОМАНДА /location
# ────────────────────────────────────────

async def location_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p    = get_player(user.id)
    lang = p['lang'] if p else 'ru'

    if not p:
        await update.message.reply_text(t('common.no_character', lang))
        return

    in_live_pvp = bool(p['in_battle']) and is_player_busy_with_live_pvp(user.id)
    if p['in_battle'] and not in_live_pvp:
        await update.message.reply_text(t('location.in_battle_block', lang))
        return

    if is_in_battle(user.id) and not in_live_pvp:
        await update.message.reply_text(t('location.in_battle', lang))
        return

    location = get_location(p['location_id'])
    if not location:
        await update.message.reply_text(t('location.not_found', lang))
        return

    text, keyboard = _build_location_message_with_snapshot(
        context,
        dict(p),
        location,
        pvp_only_view=in_live_pvp,
    )
    msg = await update.message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')


def _build_location_message_with_snapshot(
    context: ContextTypes.DEFAULT_TYPE,
    player: dict,
    location: dict,
    *,
    pvp_only_view: bool = False,
) -> tuple[str, InlineKeyboardMarkup]:
    snapshot_tag = _next_snapshot_tag(context)
    text, keyboard, snapshot = build_location_message(
        player,
        location,
        pvp_only_view=pvp_only_view,
        include_action_map=True,
        snapshot_tag=snapshot_tag,
    )
    user_data = _ensure_location_context_user_data(context)
    user_data[LOCATION_ACTION_SNAPSHOT_KEY] = snapshot
    return text, keyboard


async def pvp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user.id)
    lang = player['lang'] if player else 'ru'
    if not player:
        await update.message.reply_text(t('common.no_character', lang))
        return
    location = get_location(player['location_id'])
    if not location:
        await update.message.reply_text(t('location.not_found', lang))
        return
    encounters = get_pending_location_encounters(location_id=location['id'], limit=10)
    if not encounters:
        await update.message.reply_text(t('location.pvp_list_empty', lang))
        return
    text = t('location.pvp_list_title', lang, location=get_location_name(location['id'], lang)) + '\n\n'
    keyboard = []
    for encounter in encounters:
        text += t(
            'location.pvp_encounter_row',
            lang,
            id=encounter['id'],
            attacker=encounter['attacker_name'],
            defender=encounter['defender_name'],
            time_left=_format_seconds_short(encounter['seconds_until_start']),
            initiator_count=encounter['initiator_side_count'],
            defender_count=encounter['defender_side_count'],
        ) + '\n'
        keyboard.append([InlineKeyboardButton(
            t('location.pvp_view_fight_btn', lang, id=encounter['id']),
            callback_data=f"pvp_view_{encounter['id']}",
        )])
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


class _MessageActionQueryAdapter:
    def __init__(self, *, update: Update, callback_data: str):
        self.data = callback_data
        self.from_user = update.effective_user
        self.message = update.message
        self._update = update

    async def answer(self, text: str | None = None, show_alert: bool = False):
        if text:
            await self._update.message.reply_text(text)

    async def edit_message_text(self, text: str, reply_markup=None, parse_mode=None):
        await self._update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)


async def handle_location_action_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.message.text:
        return False
    raw_text = update.message.text.strip().lower()
    token_match = _TOKEN_COMMAND_RE.match(raw_text)
    if not token_match:
        return False

    player = get_player(update.effective_user.id)
    lang = player['lang'] if player else 'ru'
    if not player:
        await update.message.reply_text(t('common.no_character', lang))
        return True

    user_data = _ensure_location_context_user_data(context)
    snapshot = user_data.get(LOCATION_ACTION_SNAPSHOT_KEY) or {}
    if int(snapshot.get('player_id', 0) or 0) != int(update.effective_user.id):
        await update.message.reply_text(t('location.action_stale', lang))
        return True
    if str(snapshot.get('location_id', '')) != str(player.get('location_id', '')):
        await update.message.reply_text(t('location.action_stale', lang))
        return True
    if str(snapshot.get('snapshot_tag', '')) != str(token_match.group('snapshot') or ''):
        await update.message.reply_text(t('location.action_stale', lang))
        return True

    callback_data = snapshot.get('actions', {}).get(raw_text)
    if not callback_data:
        await update.message.reply_text(t('location.action_stale', lang))
        return True

    adapted_update = SimpleNamespace(callback_query=_MessageActionQueryAdapter(update=update, callback_data=callback_data))
    if callback_data.startswith(('fight_', 'flee_')):
        await handle_combat_buttons(adapted_update, context)
    else:
        await handle_location_buttons(adapted_update, context)
    return True


# ────────────────────────────────────────
# ПЕРЕХОД МЕЖДУ ЛОКАЦИЯМИ
# ────────────────────────────────────────

async def handle_location_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data

    if data == 'noop':
        await query.answer()
        return

    user = query.from_user
    p    = get_player(user.id)
    lang = p['lang'] if p else 'ru'

    if p and has_active_live_pvp_engagement(int(user.id)) and not data.startswith('pvp_'):
        await query.answer(t('location.pvp_context_block', lang), show_alert=True)
        return
    
    if p and p['in_battle'] and not data.startswith('pvp_'):
        await query.answer(t('location.in_battle_block', lang), show_alert=True)
        return

    if data.startswith('pvp_attack_'):
        target_id = int(data.replace('pvp_attack_', '', 1))
        defender = get_player(target_id)
        attacker = p
        if not defender:
            await query.answer(t('location.pvp_target_missing', lang), show_alert=True)
            return
        if defender['location_id'] != attacker['location_id']:
            await query.answer(t('location.pvp_target_missing', lang), show_alert=True)
            return
        block_reason = get_attack_block_reason(attacker=dict(attacker), defender=dict(defender), location_id=attacker['location_id'])
        if block_reason is not None:
            msg_key = 'location.pvp_not_allowed'
            if block_reason == 'respawn_protection':
                msg_key = 'location.pvp_respawn_protection_block'
            await query.answer(t(msg_key, lang), show_alert=True)
            return
        clear_respawn_protection(player_id=int(attacker['telegram_id']))
        can_create, reason = can_create_live_engagement(
            attacker_id=int(attacker['telegram_id']),
            defender_id=int(defender['telegram_id']),
        )
        if not can_create:
            if reason in {'defender_busy', 'already_in_battle'}:
                await query.answer(t('location.pvp_target_busy', lang), show_alert=True)
            else:
                await query.answer(t('location.pvp_you_busy', lang), show_alert=True)
            return

        illegal = is_aggression_illegal(attacker=dict(attacker), defender=dict(defender), location_id=attacker['location_id'])
        create_live_engagement(
            attacker=dict(attacker),
            defender=dict(defender),
            location_id=attacker['location_id'],
            illegal_aggression=illegal,
        )
        if should_apply_red_flag(attacker=dict(attacker), defender=dict(defender), location_id=attacker['location_id']):
            apply_illegal_aggression_penalties(attacker_id=int(attacker['telegram_id']))

        defender_lang = get_player_lang(int(defender['telegram_id']))
        try:
            await context.bot.send_message(
                chat_id=int(defender['telegram_id']),
                text=t('location.pvp_defender_alert', defender_lang, name=attacker.get('name', 'Unknown')),
            )
        except Exception:
            pass
        await query.answer(t('location.pvp_engagement_started', lang), show_alert=True)
        location = get_location(attacker['location_id'])
        refreshed_player = dict(get_player(user.id))
        text, keyboard = _build_location_message_with_snapshot(
            context,
            refreshed_player,
            location,
            pvp_only_view=_should_use_pvp_only_location_view(refreshed_player),
        )
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    if data.startswith('pvp_escape_'):
        engagement_id = int(data.replace('pvp_escape_', '', 1))
        conn = get_connection()
        engagement_row = conn.execute(
            'SELECT * FROM pvp_engagements WHERE id=?',
            (engagement_id,),
        ).fetchone()
        conn.close()
        if not engagement_row:
            await query.answer(t('location.pvp_no_engagement', lang), show_alert=True)
            return
        success = random.randint(1, 100) <= 50
        state, _ = resolve_engagement_escape(engagement_row, escape_succeeded=success)
        if state == 'escaped':
            await query.answer(t('location.pvp_escape_success', lang), show_alert=True)
        else:
            await query.answer(t('location.pvp_escape_fail', lang), show_alert=True)
        location = get_location(get_player(user.id)['location_id'])
        refreshed_player = dict(get_player(user.id))
        text, keyboard = _build_location_message_with_snapshot(
            context,
            refreshed_player,
            location,
            pvp_only_view=_should_use_pvp_only_location_view(refreshed_player),
        )
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    if data.startswith('pvp_view_'):
        engagement_id = int(data.replace('pvp_view_', '', 1))
        detail_text, detail_keyboard = build_pvp_encounter_detail_message(dict(p), engagement_id)
        await query.edit_message_text(detail_text, reply_markup=detail_keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('pve_view_'):
        encounter_id = data.replace('pve_view_', '', 1)
        detail_text, detail_keyboard = build_pve_encounter_detail_message(dict(p), encounter_id)
        await query.edit_message_text(detail_text, reply_markup=detail_keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('pve_join_'):
        encounter_id = data.replace('pve_join_', '', 1)
        ok, reason = join_open_world_pve_encounter(encounter_id=encounter_id, player_id=int(user.id))
        if ok:
            await query.answer(t('location.pve_join_success', lang), show_alert=True)
        else:
            key_by_reason = {
                'already_joined': 'location.pve_join_already',
                'locked': 'location.pve_join_locked',
                'wrong_location': 'location.pve_join_wrong_location',
                'busy': 'location.pve_join_busy',
            }
            await query.answer(t(key_by_reason.get(reason, 'location.pve_join_blocked'), lang), show_alert=True)
        detail_text, detail_keyboard = build_pve_encounter_detail_message(dict(get_player(user.id)), encounter_id)
        await query.edit_message_text(detail_text, reply_markup=detail_keyboard, parse_mode='HTML')
        return

    if data.startswith('pve_enter_'):
        encounter_id = data.replace('pve_enter_', '', 1)
        from handlers.battle import enter_open_world_pve_battle
        await enter_open_world_pve_battle(update, context, encounter_id)
        return

    if data.startswith('pve_leave_'):
        encounter_id = data.replace('pve_leave_', '', 1)
        ok, reason = leave_open_world_pve_encounter(encounter_id=encounter_id, player_id=int(user.id))
        if ok:
            message_key = 'location.pve_leave_success'
            if reason == 'left_collapsed':
                message_key = 'location.pve_leave_collapsed'
            await query.answer(t(message_key, lang), show_alert=True)
        else:
            key_by_reason = {
                'not_joined': 'location.pve_leave_not_joined',
                'locked': 'location.pve_leave_locked',
            }
            await query.answer(t(key_by_reason.get(reason, 'location.pve_leave_blocked'), lang), show_alert=True)
        detail_text, detail_keyboard = build_pve_encounter_detail_message(dict(get_player(user.id)), encounter_id)
        await query.edit_message_text(detail_text, reply_markup=detail_keyboard, parse_mode='HTML')
        return

    if data.startswith('pvp_join_'):
        raw = data.replace('pvp_join_', '', 1)
        engagement_id = int(raw.split('_', 1)[0])
        side = raw.split('_', 1)[1]
        conn = get_connection()
        engagement_row = conn.execute(
            'SELECT * FROM pvp_engagements WHERE id=?',
            (engagement_id,),
        ).fetchone()
        conn.close()
        if not engagement_row:
            await query.answer(t('location.pvp_no_engagement', lang), show_alert=True)
            return
        ok, _reason = join_pending_encounter_side(
            engagement_row=engagement_row,
            player_id=int(user.id),
            side=side,
        )
        if ok:
            await query.answer(t('location.pvp_join_success', lang), show_alert=True)
        else:
            await query.answer(t('location.pvp_join_blocked', lang), show_alert=True)
        detail_text, detail_keyboard = build_pvp_encounter_detail_message(dict(get_player(user.id)), engagement_id)
        await query.edit_message_text(detail_text, reply_markup=detail_keyboard, parse_mode='HTML')
        return

    if data.startswith('pvp_invite_'):
        raw = data.replace('pvp_invite_', '', 1)
        engagement_id = int(raw.split('_', 1)[0])
        ally_id = int(raw.split('_', 1)[1])
        conn = get_connection()
        engagement_row = conn.execute(
            'SELECT * FROM pvp_engagements WHERE id=?',
            (engagement_id,),
        ).fetchone()
        conn.close()
        if not engagement_row:
            await query.answer(t('location.pvp_no_engagement', lang), show_alert=True)
            return
        ok, reason = invite_reinforcement_ally(
            engagement_row=engagement_row,
            inviter_id=int(user.id),
            ally_id=ally_id,
        )
        if ok:
            await query.answer(t('location.pvp_reinforcement_invite_sent', lang), show_alert=True)
        else:
            await query.answer(t('location.pvp_reinforcement_invite_blocked', lang), show_alert=True)
        location = get_location(get_player(user.id)['location_id'])
        refreshed_player = dict(get_player(user.id))
        text, keyboard = _build_location_message_with_snapshot(
            context,
            refreshed_player,
            location,
            pvp_only_view=_should_use_pvp_only_location_view(refreshed_player),
        )
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        if ok:
            ally_lang = get_player_lang(ally_id)
            try:
                await context.bot.send_message(
                    chat_id=ally_id,
                    text=t('location.pvp_reinforcement_invite_alert', ally_lang),
                )
            except Exception:
                pass
        return

    if data.startswith('pvp_reinf_'):
        raw = data.replace('pvp_reinf_', '', 1)
        action = raw.split('_', 1)[0]
        engagement_id = int(raw.split('_', 1)[1])
        accepted = action == 'accept'
        ok, reason = respond_to_reinforcement_invite(
            engagement_id=engagement_id,
            ally_id=int(user.id),
            accepted=accepted,
        )
        if ok and accepted:
            await query.answer(t('location.pvp_reinforcement_accept_done', lang), show_alert=True)
        elif ok:
            await query.answer(t('location.pvp_reinforcement_decline_done', lang), show_alert=True)
        else:
            await query.answer(t('location.pvp_reinforcement_response_blocked', lang), show_alert=True)
        location = get_location(get_player(user.id)['location_id'])
        refreshed_player = dict(get_player(user.id))
        text, keyboard = _build_location_message_with_snapshot(
            context,
            refreshed_player,
            location,
            pvp_only_view=_should_use_pvp_only_location_view(refreshed_player),
        )
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    if data.startswith('pvp_act_'):
        raw = data.replace('pvp_act_', '', 1)
        engagement_id = int(raw.split('_', 1)[0])
        action_id = raw.split('_', 1)[1]
        conn = get_connection()
        engagement_row = conn.execute(
            'SELECT * FROM pvp_engagements WHERE id=?',
            (engagement_id,),
        ).fetchone()
        conn.close()
        if not engagement_row:
            await query.answer(t('location.pvp_no_engagement', lang), show_alert=True)
            return
        status, _payload = resolve_live_battle_turn(
            engagement_row,
            actor_id=int(user.id),
            selected_action_id=action_id,
        )
        if status == 'waiting':
            await query.answer(t('location.pvp_wait_turn_timeout', lang), show_alert=True)
        elif status == 'invalid_action':
            await query.answer(t('location.pvp_action_not_ready', lang), show_alert=True)
        elif status == 'not_your_turn':
            await query.answer(t('location.pvp_not_your_turn', lang), show_alert=True)
        elif status == 'finished':
            await query.answer(t('location.pvp_battle_finished', lang), show_alert=True)
        else:
            await query.answer(t('location.pvp_action_done', lang), show_alert=True)
        location = get_location(get_player(user.id)['location_id'])
        refreshed_player = dict(get_player(user.id))
        text, keyboard = _build_location_message_with_snapshot(
            context,
            refreshed_player,
            location,
            pvp_only_view=_should_use_pvp_only_location_view(refreshed_player),
        )
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    if data == 'shop':
        location = get_location(p['location_id'])
        if not location:
            await query.answer(t('location.not_found', lang), show_alert=True)
            return
        if 'shop' not in location.get('services', []):
            await query.answer(t('location.shop_not_available', lang), show_alert=True)
            return

        text, keyboard = build_shop_message(dict(p), location)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data == 'shop_back':
        location = get_location(p['location_id'])
        if not location:
            await query.answer(t('location.not_found', lang), show_alert=True)
            return
        if 'shop' not in location.get('services', []):
            await query.answer(t('location.shop_not_available', lang), show_alert=True)
            return

        text, keyboard = _build_location_message_with_snapshot(context, dict(p), location)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('shop_buy_'):
        item_id = data.replace('shop_buy_', '', 1)
        location = get_location(p['location_id'])
        if not location:
            await query.answer(t('location.not_found', lang), show_alert=True)
            return
        if 'shop' not in location.get('services', []):
            await query.answer(t('location.shop_not_available', lang), show_alert=True)
            return

        result = try_buy_curated_shop_item(
            telegram_id=user.id,
            location_id=location['id'],
            player_level=p['level'],
            item_id=item_id,
        )
        if not result['ok']:
            if result['reason'] == 'level_required':
                await query.answer(t('location.shop_level_required', lang, level=result['required_level']), show_alert=True)
            elif result['reason'] == 'not_enough_gold':
                await query.answer(t('location.shop_no_gold', lang, price=result['price']), show_alert=True)
            else:
                await query.answer(t('location.shop_not_available', lang), show_alert=True)
            return

        player_after = dict(get_player(user.id))
        text, keyboard = build_shop_message(player_after, location)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer(t('location.shop_buy_ok', lang, name=get_item_name(item_id, lang), price=result['price']))
        return

    if data.startswith('goto_') and (is_in_battle(user.id) or is_pvp_mobility_blocked(int(user.id))):
        await query.answer(t('location.in_battle_move', lang), show_alert=True)
        return

    if data.startswith('goto_'):
        new_loc_id = data.replace('goto_', '')
        new_loc    = get_location(new_loc_id)

        if not new_loc:
            await query.answer(t('location.not_found', lang), show_alert=True)
            return

        if not new_loc['safe'] and p['level'] < new_loc['level_min']:
            await query.answer(
                t('location.level_required', lang, level=new_loc['level_min']),
                show_alert=True
            )
            return

        await query.answer()

        # Сообщение о переходе
        await query.edit_message_text(
            t('location.traveling', lang,
                name=get_location_name(new_loc_id, lang),
                seconds=15,
                description=get_location_desc(new_loc_id, lang).lower()),
            parse_mode='HTML'
        )

        await asyncio.sleep(15)

        if is_pvp_mobility_blocked(int(user.id)):
            await query.edit_message_text(t('location.pvp_mobility_block', lang), parse_mode='HTML')
            return

        conn = get_connection()
        conn.execute(
            'UPDATE players SET location_id=? WHERE telegram_id=?',
            (new_loc_id, user.id)
        )
        conn.commit()
        conn.close()
        clear_respawn_protection_on_dangerous_reentry(
            player_id=int(user.id),
            location_id=new_loc_id,
        )

        p = dict(get_player(user.id))
        text, keyboard = _build_location_message_with_snapshot(context, p, new_loc)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')

        if not new_loc['safe']:
            context.application.create_task(
                schedule_mob_aggro(context, user.id, new_loc, query.message.message_id)
            )


# ────────────────────────────────────────
# АГРЕССИЯ МОБОВ (таймер)
# ────────────────────────────────────────

async def schedule_mob_aggro(context, telegram_id: int, location: dict, message_id: int):
    aggressive_mobs = [
        get_mob(mid) for mid in location['mobs']
        if get_mob(mid) and get_mob(mid)['aggressive']
    ]
    tasks = [
        aggro_attack(context, telegram_id, mob, location['id'], random.randint(5, 60))
        for mob in aggressive_mobs
    ]
    await asyncio.gather(*tasks)


async def aggro_attack(context, telegram_id: int, mob: dict, location_id: str, delay: int):
    await asyncio.sleep(delay)

    p = get_player(telegram_id)
    if not p:
        return
    if p['location_id'] != location_id:
        return
    if p['in_battle']:
        return
    if p['level'] > mob['level'] + 1:
        return

    lang = get_player_lang(telegram_id)

    conn = get_connection()
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=?', (telegram_id,))
    conn.commit()
    conn.close()

    try:
        msg = await context.bot.send_message(
            chat_id=telegram_id,
            text=t('location.aggro_alert', lang,
                   mob_name=mob['name'],
                   level=mob['level'],
                   hp=mob['hp']),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    t('location.aggro_fight_btn', lang),
                    callback_data=f"fight_{mob['id']}"
                ),
                InlineKeyboardButton(
                    t('location.aggro_flee_btn', lang),
                    callback_data=f"flee_{mob['id']}"
                ),
            ]])
        )
        context.application.user_data.setdefault(telegram_id, {})['aggro_message_id'] = msg.message_id
    except Exception:
        pass


# ────────────────────────────────────────
# КНОПКИ БОЕВОГО ВЫЗОВА (fight_ / flee_)
# ────────────────────────────────────────

async def handle_combat_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    user  = query.from_user
    p     = get_player(user.id)
    lang  = p['lang'] if p else 'ru'

    if has_active_live_pvp_engagement(int(user.id)):
        await query.answer(t('location.pvp_context_block', lang), show_alert=True)
        return

    if data.startswith('fight_first_'):
        mob_id = data.replace('fight_first_', '')
        from handlers.battle import start_battle
        await start_battle(update, context, mob_id, mob_first=True)

    elif data.startswith('fight_spawn_'):
        spawn_instance_id = data.replace('fight_spawn_', '')
        from handlers.battle import start_battle
        await start_battle(
            update,
            context,
            mob_id='',
            mob_first=False,
            spawn_instance_id=spawn_instance_id,
            open_runtime_now=False,
        )

    elif data.startswith('fight_'):
        mob_id = data.replace('fight_', '')
        from handlers.battle import start_battle
        await start_battle(update, context, mob_id, mob_first=False)

    elif data.startswith('flee_'):
        mob_id = data.replace('flee_', '')
        mob    = get_mob(mob_id)

        if random.randint(1, 100) <= 20:
            conn = get_connection()
            conn.execute('UPDATE players SET in_battle=0 WHERE telegram_id=?', (user.id,))
            conn.commit()
            conn.close()
            try:
                await query.edit_message_text(
                    t('battle.flee_success', lang, mob_name=mob['name']),
                    parse_mode='HTML'
                )
            except BadRequest:
                pass
        else:
            try:
                await query.edit_message_text(
                    t('location.aggro_flee_fail', lang, mob_name=mob['name'],
                      level=mob['level'], hp=mob['hp']),
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            t('location.aggro_fight_first_btn', lang),
                            callback_data=f"fight_first_{mob['id']}"
                        ),
                    ]])
                )
            except BadRequest:
                pass

    await query.answer()

print('✅ handlers/location.py создан!')
