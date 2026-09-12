# ============================================================
# inventory.py — инвентарь игрока
# ============================================================

import sys, json, os
from collections import Counter
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_player, get_connection, is_in_battle, is_location_discovered
from game.items_data import get_item, get_item_metadata
from game.i18n import t, get_player_lang, get_item_name, get_item_description, get_location_name
from game.equipment_stats import get_player_effective_stats
from game.gear_instances import (
    MAX_ENHANCE_LEVEL,
    get_enhance_requirements_for_target_level,
    get_enhance_outcome_chances_for_target_level,
    list_player_gear_instances,
    get_equipped_gear_instances,
    resolve_gear_instance_item_data,
)
from game.field_catalog import FIELD_ITEM_IDS, FIELD_VENDOR_LOCATIONS, get_field_category, is_field_item
from game.gear_progression import (
    apply_gear_intent,
    apply_legacy_gear_intent,
    build_gear_mutation_preview,
    get_equipment_goal,
    issue_gear_intent,
    issue_gear_equip_intents,
    issue_legacy_gear_intent,
    issue_legacy_gear_equip_intents,
    set_equipment_goal,
)
from game.gear_ui import (
    COMPARISON_CHANNELS,
    ROUTE_SOURCE_HUBS,
    catalog_page,
    compare_instance_to_slot,
    contribution_from_resolved_item,
    get_field_source_manifest,
    resolve_template_preview,
)

RARITY_KEYS = {
    'common':    'rarity_common',
    'uncommon':  'rarity_uncommon',
    'rare':      'rarity_rare',
    'epic':      'rarity_epic',
    'legendary': 'rarity_legendary',
}

RARITY_NAME = {
    'ru': {'common': 'Обычный', 'uncommon': 'Необычный', 'rare': 'Редкий', 'epic': 'Эпический', 'legendary': 'Легендарный'},
    'en': {'common': 'Common',  'uncommon': 'Uncommon',  'rare': 'Rare',   'epic': 'Epic',      'legendary': 'Legendary'},
    'es': {'common': 'Común',   'uncommon': 'Poco común','rare': 'Raro',   'epic': 'Épico',     'legendary': 'Legendario'},
}

WEAPON_TYPE_NAME = {
    'ru': {'melee': 'Ближний бой', 'ranged': 'Дальний бой', 'magic': 'Магия', 'light': 'Свет'},
    'en': {'melee': 'Melee',       'ranged': 'Ranged',       'magic': 'Magic', 'light': 'Holy'},
    'es': {'melee': 'Cuerpo a cuerpo', 'ranged': 'A distancia', 'magic': 'Magia', 'light': 'Luz'},
}

STAT_NAMES = {
    'ru': {'strength': '💪 Сила', 'agility': '🤸 Ловкость', 'intuition': '🔮 Интуиция', 'vitality': '❤️ Живучесть', 'wisdom': '🧠 Мудрость', 'luck': '🍀 Удача'},
    'en': {'strength': '💪 Strength', 'agility': '🤸 Agility', 'intuition': '🔮 Intuition', 'vitality': '❤️ Vitality', 'wisdom': '🧠 Wisdom', 'luck': '🍀 Luck'},
    'es': {'strength': '💪 Fuerza', 'agility': '🤸 Agilidad', 'intuition': '🔮 Intuición', 'vitality': '❤️ Vitalidad', 'wisdom': '🧠 Sabiduría', 'luck': '🍀 Suerte'},
}

TABS = ['weapon', 'armor', 'accessory', 'potion', 'material']
EQUIPMENT_SLOT_KEYS = (
    'weapon',
    'offhand',
    'helmet',
    'chest',
    'legs',
    'boots',
    'gloves',
    'ring1',
    'ring2',
    'amulet',
)

SLOT_IDENTITY_NAME = {
    'ru': {
        'weapon': '⚔️ Основное оружие',
        'offhand': '🛡️ Оффхенд',
        'helmet': '⛑️ Шлем',
        'chest': '🧥 Нагрудник',
        'legs': '🥾 Поножи',
        'boots': '👢 Обувь',
        'gloves': '🧤 Перчатки',
        'ring': '💍 Кольцо',
        'amulet': '📿 Амулет',
    },
    'en': {
        'weapon': '⚔️ Main-hand',
        'offhand': '🛡️ Offhand',
        'helmet': '⛑️ Helmet',
        'chest': '🧥 Chest',
        'legs': '🥾 Legs',
        'boots': '👢 Boots',
        'gloves': '🧤 Gloves',
        'ring': '💍 Ring',
        'amulet': '📿 Amulet',
    },
    'es': {
        'weapon': '⚔️ Mano principal',
        'offhand': '🛡️ Mano secundaria',
        'helmet': '⛑️ Casco',
        'chest': '🧥 Pecho',
        'legs': '🥾 Piernas',
        'boots': '👢 Botas',
        'gloves': '🧤 Guantes',
        'ring': '💍 Anillo',
        'amulet': '📿 Amuleto',
    },
}

ARMOR_CLASS_NAME = {
    'ru': {'heavy': 'Тяжёлая', 'medium': 'Средняя', 'light': 'Лёгкая'},
    'en': {'heavy': 'Heavy', 'medium': 'Medium', 'light': 'Light'},
    'es': {'heavy': 'Pesada', 'medium': 'Media', 'light': 'Ligera'},
}

OFFHAND_PROFILE_NAME = {
    'ru': {'shield': 'Щит', 'focus': 'Фокус', 'censer': 'Кадило'},
    'en': {'shield': 'Shield', 'focus': 'Focus', 'censer': 'Censer'},
    'es': {'shield': 'Escudo', 'focus': 'Foco', 'censer': 'Incensario'},
}

WEAPON_PROFILE_NAME = {
    'ru': {'sword_1h': 'Одноручный меч', 'sword_2h': 'Двуручный меч', 'axe_2h': 'Двуручный топор', 'daggers': 'Парные кинжалы', 'bow': 'Лук', 'magic_staff': 'Маг. посох', 'holy_staff': 'Святой посох', 'wand': 'Волшебная палочка', 'holy_rod': 'Святой жезл', 'tome': 'Фолиант', 'unarmed': 'Без оружия'},
    'en': {'sword_1h': '1H Sword', 'sword_2h': '2H Sword', 'axe_2h': '2H Axe', 'daggers': 'Daggers', 'bow': 'Bow', 'magic_staff': 'Magic Staff', 'holy_staff': 'Holy Staff', 'wand': 'Wand', 'holy_rod': 'Holy Rod', 'tome': 'Tome', 'unarmed': 'Unarmed'},
    'es': {'sword_1h': 'Espada 1M', 'sword_2h': 'Espada 2M', 'axe_2h': 'Hacha 2M', 'daggers': 'Dagas', 'bow': 'Arco', 'magic_staff': 'Bastón mágico', 'holy_staff': 'Bastón sagrado', 'wand': 'Varita', 'holy_rod': 'Vara sagrada', 'tome': 'Tomo', 'unarmed': 'Sin arma'},
}

INVENTORY_PAGE_SIZE = 8

def get_inventory(telegram_id: int, item_type: str = None) -> list:
    conn = get_connection()
    if item_type:
        rows = conn.execute('''
            SELECT inv.id, inv.item_id, inv.quantity, inv.enhance_level
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            WHERE inv.telegram_id=? AND i.item_type=?
        ''', (telegram_id, item_type)).fetchall()
    else:
        rows = conn.execute('''
            SELECT inv.id, inv.item_id, inv.quantity, inv.enhance_level
            FROM inventory inv
            WHERE inv.telegram_id=?
        ''', (telegram_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_gear_inventory_entries(telegram_id: int, item_type: str | None = None) -> list[dict]:
    out: list[dict] = []
    for row in list_player_gear_instances(telegram_id):
        item = get_item(row['base_item_id'])
        if not item:
            continue
        if item_type and item.get('item_type') != item_type:
            continue
        out.append({
            'entry_type': 'gear_instance',
            'id': row['id'],
            'item_id': row['base_item_id'],
            'quantity': 1,
            'enhance_level': row.get('enhance_level', 0),
            'equipped_slot': row.get('equipped_slot'),
            'instance': row,
        })
    return out


def _get_entry_rarity_and_tier(inv_row: dict, item: dict) -> tuple[str, int]:
    if inv_row.get('entry_type') == 'gear_instance':
        resolved = resolve_gear_instance_item_data(inv_row.get('instance', {}))
        rarity = resolved.get('instance_rarity', item.get('rarity', 'common'))
        tier = int(resolved.get('item_tier', 1))
        return rarity, tier
    return item.get('rarity', 'common'), 1


def _get_entry_enhance_level(inv_row: dict) -> int:
    if inv_row.get('entry_type') == 'gear_instance':
        resolved = resolve_gear_instance_item_data(inv_row.get('instance', {}))
        return int(resolved.get('enhance_level', 0))
    return int(inv_row.get('enhance_level', 0))


def make_entry_token(entry_type: str, entry_id: int) -> str:
    return f"g{entry_id}" if entry_type == 'gear_instance' else f"i{entry_id}"


def get_equipped(telegram_id: int) -> dict:
    equipped_instances = get_equipped_gear_instances(telegram_id)
    out = {slot: make_entry_token('gear_instance', row['id']) for slot, row in equipped_instances.items()}
    conn = get_connection()
    try:
        legacy = conn.execute('SELECT * FROM equipment WHERE telegram_id=?', (telegram_id,)).fetchone()
        if not legacy:
            return out
        for slot in EQUIPMENT_SLOT_KEYS:
            if slot in out:
                continue
            if legacy[slot] is not None:
                out[slot] = make_entry_token('legacy_inventory', legacy[slot])
        return out
    finally:
        conn.close()


def get_equipped_slot_for_inventory_id(equipped: dict, inv_id: int) -> str | None:
    return get_equipped_slot_for_entry_token(equipped, make_entry_token('legacy_inventory', inv_id))


def get_equipped_slot_for_entry_token(equipped: dict, entry_token: str) -> str | None:
    for slot in EQUIPMENT_SLOT_KEYS:
        equipped_entry = equipped.get(slot)
        if equipped_entry == entry_token:
            return slot
    return None


def resolve_equip_slot_for_item(item_id: str, equipped: dict) -> str | None:
    metadata = get_item_metadata(item_id)
    slot_identity = metadata.get('slot_identity')

    if slot_identity in {'weapon', 'offhand', 'helmet', 'chest', 'legs', 'boots', 'gloves'}:
        return slot_identity

    if slot_identity == 'amulet':
        return 'amulet'

    if slot_identity == 'ring':
        if equipped.get('ring1') is None:
            return 'ring1'
        if equipped.get('ring2') is None:
            return 'ring2'
        return 'ring1'

    return None


def _build_metadata_text_lines(metadata: dict, lang: str) -> list[str]:
    lines = []
    lang_map = SLOT_IDENTITY_NAME.get(lang, SLOT_IDENTITY_NAME['ru'])
    slot_identity = metadata.get('slot_identity')
    if slot_identity in lang_map:
        lines.append(lang_map[slot_identity])

    armor_class = metadata.get('armor_class')
    if armor_class:
        armor_label = ARMOR_CLASS_NAME.get(lang, ARMOR_CLASS_NAME['ru']).get(armor_class, armor_class)
        lines.append(f"🧱 {armor_label}")

    offhand_profile = metadata.get('offhand_profile')
    if offhand_profile and offhand_profile != 'none':
        offhand_label = OFFHAND_PROFILE_NAME.get(lang, OFFHAND_PROFILE_NAME['ru']).get(offhand_profile, offhand_profile)
        lines.append(f"🔰 {offhand_label}")

    if metadata.get('slot_identity') == 'weapon':
        weapon_profile = metadata.get('weapon_profile')
        profile_label = WEAPON_PROFILE_NAME.get(lang, WEAPON_PROFILE_NAME['ru']).get(weapon_profile, weapon_profile)
        lines.append(f"⚙️ {profile_label}")

    return lines


def _get_localized_stat_label(stat_key: str, lang: str) -> str:
    localized = t(f'inventory.stat_labels.{stat_key}', lang)
    if localized and localized != f'[inventory.stat_labels.{stat_key}]':
        return localized
    return STAT_NAMES.get(lang, STAT_NAMES['ru']).get(stat_key, stat_key.replace('_', ' ').title())

def is_equipped(telegram_id: int, inv_id: int) -> bool:
    eq = get_equipped(telegram_id)
    token = make_entry_token('legacy_inventory', inv_id)
    return token in eq.values()


def _calc_safe_restore_amount(current_value: int, effective_cap: int, restore_value: int) -> int:
    missing = max(0, int(effective_cap) - int(current_value))
    return max(0, min(int(restore_value), missing))

def try_sell_inventory_item(telegram_id: int, action_token: str) -> dict:
    """Sell one owned material at a shop with its receipt and objective atomically."""
    from game.action_receipts import ActionRejected, peaceful_player, consume_action
    from game.quest_board import register_contract_objective
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        player = peaceful_player(conn, telegram_id, service='shop')
        payload = consume_action(conn, telegram_id, 'sell', action_token)
        inv_id, expected_quantity = (int(value) for value in payload.split(':'))
        row = conn.execute('SELECT * FROM inventory WHERE id=? AND telegram_id=?', (inv_id, telegram_id)).fetchone()
        if not row or row['quantity'] != expected_quantity or expected_quantity <= 0:
            raise ActionRejected('stale_action')
        item = get_item(row['item_id'])
        if not item or item['item_type'] != 'material' or item['sell_price'] <= 0:
            raise ActionRejected('stale_action')
        if expected_quantity == 1:
            conn.execute('DELETE FROM inventory WHERE id=?', (inv_id,))
        else:
            conn.execute('UPDATE inventory SET quantity=quantity-1 WHERE id=?', (inv_id,))
        conn.execute('UPDATE players SET gold=gold+? WHERE telegram_id=?', (item['sell_price'], telegram_id))
        register_contract_objective(conn, telegram_id, 'sell', row['item_id'], 1, player['location_id'])
        conn.commit()
        return {'status': 'sold', 'gold': item['sell_price']}
    except ActionRejected as exc:
        conn.rollback()
        return {'status': str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def consume_owned_potion(conn, telegram_id: int, inventory_id: int, *, hp: int, mana: int,
                        max_hp: int, max_mana: int, expected_quantity: int | None = None) -> dict:
    """Shared inventory/battle consumption, using caller-owned transaction and caps."""
    from game.action_receipts import ActionRejected
    row = conn.execute('SELECT * FROM inventory WHERE id=? AND telegram_id=?', (inventory_id, telegram_id)).fetchone()
    if not row or row['quantity'] <= 0 or (expected_quantity is not None and row['quantity'] != expected_quantity):
        raise ActionRejected('stale_action')
    item = get_item(row['item_id'])
    if not item or item['item_type'] != 'potion':
        raise ActionRejected('stale_action')
    bonus = json.loads(item['stat_bonus_json'])
    heal = _calc_safe_restore_amount(hp, max_hp, bonus.get('heal', 0))
    mana_gain = _calc_safe_restore_amount(mana, max_mana, bonus.get('mana', 0))
    conn.execute('UPDATE players SET hp=?, mana=? WHERE telegram_id=?', (hp + heal, mana + mana_gain, telegram_id))
    if row['quantity'] == 1:
        conn.execute('DELETE FROM inventory WHERE id=?', (inventory_id,))
    else:
        conn.execute('UPDATE inventory SET quantity=quantity-1 WHERE id=?', (inventory_id,))
    return {'status': 'used', 'heal': heal, 'mana': mana_gain, 'item_id': row['item_id']}


def use_inventory_consumable(telegram_id: int, action_token: str) -> dict:
    from game.action_receipts import ActionRejected, peaceful_player, consume_action
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        player = peaceful_player(conn, telegram_id)
        payload = consume_action(conn, telegram_id, 'use', action_token)
        inv_id, expected_quantity = (int(value) for value in payload.split(':'))
        effective = get_player_effective_stats(telegram_id, player)
        result = consume_owned_potion(conn, telegram_id, inv_id, hp=player['hp'], mana=player['mana'],
                    max_hp=effective['max_hp'], max_mana=effective['max_mana'], expected_quantity=expected_quantity)
        conn.commit()
        return result
    except ActionRejected as exc:
        conn.rollback()
        return {'status': str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def use_battle_consumable(telegram_id: int, action_token: str, encounter_id: str) -> dict:
    """Consume and persist the active solo encounter in the same transaction."""
    from game.action_receipts import ActionRejected, consume_action
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        payload = consume_action(conn, telegram_id, 'battle_use', action_token)
        saved_encounter, inv_id, quantity = payload.split(':')
        row = conn.execute("""SELECT e.* FROM pve_encounters e JOIN pve_encounter_participants p
            ON p.encounter_id=e.encounter_id WHERE e.encounter_id=? AND e.status='active'
            AND p.player_id=? AND p.status='active'""", (encounter_id, telegram_id)).fetchone()
        if saved_encounter != encounter_id or not row:
            raise ActionRejected('stale_action')
        state = json.loads(row['battle_state_json'])
        from game.pve_live import sync_projection_for_participant
        sync_projection_for_participant(battle_state=state, player_id=telegram_id)
        if state.get('player_dead') or state.get('mob_dead'):
            raise ActionRejected('stale_action')
        result = consume_owned_potion(conn, telegram_id, int(inv_id),
                    hp=state['player_hp'], mana=state['player_mana'],
                    max_hp=state['player_max_hp'], max_mana=state['player_max_mana'],
                    expected_quantity=int(quantity))
        state['player_hp'] += result['heal']
        state['player_mana'] += result['mana']
        from game.pve_live import update_participant_combat_state_from_projection
        update_participant_combat_state_from_projection(battle_state=state, player_id=telegram_id)
        conn.execute('UPDATE pve_encounters SET battle_state_json=?, updated_at=CURRENT_TIMESTAMP WHERE encounter_id=?',
                     (json.dumps(state, ensure_ascii=False), encounter_id))
        conn.commit()
        return {**result, 'battle': state}
    except ActionRejected as exc:
        conn.rollback()
        return {'status': str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def build_tab_keyboard(active_tab: str, lang: str) -> list:
    row = []
    for tab_key in TABS:
        label = t(f'inventory.tab_{tab_key}', lang)
        if tab_key == active_tab:
            row.append(InlineKeyboardButton(f"[{label}]", callback_data='inv_noop'))
        else:
            row.append(InlineKeyboardButton(label, callback_data=f'inv_tab_{tab_key}'))
    return row


def _inventory_route(tab: str, page: int) -> str:
    normalized_page = max(0, int(page))
    return tab if normalized_page == 0 else f'{tab}~{normalized_page}'


def _parse_inventory_route(raw_route: str) -> tuple[str, int] | None:
    tab, separator, raw_page = str(raw_route or '').partition('~')
    if tab not in TABS:
        return None
    if not separator:
        return tab, 0
    if not raw_page.isdigit():
        return None
    return tab, int(raw_page)


def _parse_entry_token(token: str) -> tuple[str, int]:
    if token.startswith('g'):
        return 'gear_instance', int(token[1:])
    if token.startswith('i'):
        return 'legacy_inventory', int(token[1:])
    return 'legacy_inventory', int(token)


def _load_inventory_entry(telegram_id: int, token: str) -> dict | None:
    entry_type, entry_id = _parse_entry_token(token)
    if entry_type == 'gear_instance':
        for row in get_gear_inventory_entries(telegram_id):
            if row['id'] == entry_id:
                return row
        return None

    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT * FROM inventory WHERE id=? AND telegram_id=?',
            (entry_id, telegram_id)
        ).fetchone()
        if not row:
            return None
        out = dict(row)
        out['entry_type'] = 'legacy_inventory'
        return out
    finally:
        conn.close()


def build_inventory_list(
        telegram_id: int, active_tab: str, lang: str = 'ru', page: int | None = None) -> tuple:
    parsed_route = _parse_inventory_route(active_tab)
    if parsed_route is None:
        active_tab, route_page = 'weapon', 0
    else:
        active_tab, route_page = parsed_route
    requested_page = route_page if page is None else max(0, int(page))
    items = []
    if active_tab in ('weapon', 'armor', 'accessory'):
        items.extend(get_gear_inventory_entries(telegram_id, active_tab))
    legacy_items = get_inventory(telegram_id, active_tab)
    for row in legacy_items:
        row['entry_type'] = 'legacy_inventory'
        items.append(row)
    items.sort(key=lambda row: (
        str(row.get('item_id') or ''),
        0 if row.get('entry_type') == 'gear_instance' else 1,
        int(row.get('id', 0)),
    ))
    page_count = max(1, (len(items) + INVENTORY_PAGE_SIZE - 1) // INVENTORY_PAGE_SIZE)
    current_page = min(requested_page, page_count - 1)
    visible_items = items[
        current_page * INVENTORY_PAGE_SIZE:(current_page + 1) * INVENTORY_PAGE_SIZE
    ]
    current_route = _inventory_route(active_tab, current_page)

    eq = get_equipped(telegram_id)
    keyboard = [build_tab_keyboard(active_tab, lang)]
    keyboard.append([InlineKeyboardButton(t('gear.catalog_btn', lang), callback_data='inv_catalog')])

    text = t('inventory.title', lang) + '\n'
    text += t('gear.page', lang, page=current_page + 1, pages=page_count) + '\n\n'

    if not items:
        text += t('inventory.empty', lang) + '\n'
    else:
        for inv_row in visible_items:
            item = get_item(inv_row['item_id'])
            if not item:
                continue

            entry_rarity, entry_tier = _get_entry_rarity_and_tier(inv_row, item)
            entry_enhance = _get_entry_enhance_level(inv_row)
            rarity  = t(f"inventory.{RARITY_KEYS.get(entry_rarity, 'rarity_common')}", lang)
            enhance = f" +{entry_enhance}" if entry_enhance > 0 else ""
            qty     = f" x{inv_row['quantity']}" if inv_row['quantity'] > 1 else ""
            token = make_entry_token(inv_row.get('entry_type', 'legacy_inventory'), inv_row['id'])
            eq_mark = t('inventory.equipped', lang) if token in eq.values() else ""
            tier_tag = f" {t('inventory.instance_tier_short', lang, tier=entry_tier)}" if inv_row.get('entry_type') == 'gear_instance' else ''

            label = f"{rarity} {get_item_name(inv_row['item_id'], lang)}{tier_tag}{enhance}{qty}{eq_mark}"
            keyboard.append([InlineKeyboardButton(
                label,
                callback_data=f"inv_item_{token}_{current_route}"
            )])

    nav = []
    if current_page > 0:
        nav.append(InlineKeyboardButton('◀️', callback_data=f'inv_tab_{_inventory_route(active_tab, current_page - 1)}'))
    if current_page + 1 < page_count:
        nav.append(InlineKeyboardButton('▶️', callback_data=f'inv_tab_{_inventory_route(active_tab, current_page + 1)}'))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton(
        t('gear.refresh_btn', lang), callback_data=f'inv_tab_{current_route}')])

    return text, InlineKeyboardMarkup(keyboard)

def build_item_detail(telegram_id: int, entry_token: str, back_tab: str, lang: str = 'ru') -> tuple:
    inv_row = _load_inventory_entry(telegram_id, entry_token)
    if not inv_row:
        return t('inventory.item_not_found', lang), InlineKeyboardMarkup([[
            InlineKeyboardButton(t('inventory.back_btn', lang), callback_data=f"inv_tab_{back_tab}")
        ]])

    item         = get_item(inv_row['item_id'])
    eq           = get_equipped(telegram_id)
    equipped_slot = get_equipped_slot_for_entry_token(eq, entry_token)
    equipped     = bool(equipped_slot)
    metadata     = get_item_metadata(inv_row['item_id'])

    resolved_instance = None
    rarity_key = item['rarity']
    tier_value = 1
    if inv_row.get('entry_type') == 'gear_instance':
        resolved_instance = resolve_gear_instance_item_data(inv_row.get('instance', {}))
        rarity_key = resolved_instance.get('instance_rarity', rarity_key)
        tier_value = int(resolved_instance.get('item_tier', 1))

    rarity_emoji = t(f"inventory.{RARITY_KEYS.get(rarity_key, 'rarity_common')}", lang)
    rarity_name  = RARITY_NAME.get(lang, RARITY_NAME['ru']).get(rarity_key, '')
    enhance      = f" <b>+{inv_row['enhance_level']}</b>" if inv_row['enhance_level'] > 0 else ""
    if resolved_instance:
        instance_enhance = int(resolved_instance.get('enhance_level', inv_row.get('enhance_level', 0)))
    else:
        instance_enhance = int(inv_row.get('enhance_level', 0))
    enhance      = f" <b>+{instance_enhance}</b>" if instance_enhance > 0 else ""
    item_name    = get_item_name(inv_row['item_id'], lang)

    text = f"{rarity_emoji} <b>{item_name}{enhance}</b>\n{rarity_name}"
    if inv_row.get('entry_type') == 'gear_instance':
        text += f" · {t('inventory.instance_tier', lang, tier=tier_value)}"
        text += f" · {t('inventory.enhance_level', lang, level=instance_enhance, max=MAX_ENHANCE_LEVEL)}"

    if item['item_type'] == 'weapon':
        wtype = WEAPON_TYPE_NAME.get(lang, WEAPON_TYPE_NAME['ru']).get(item['weapon_type'], '')
        text += f" | {wtype} | {t('common.level_short', lang)}{item['req_level']}\n\n"
        weapon_min = resolved_instance['damage_min'] if resolved_instance else item['damage_min']
        weapon_max = resolved_instance['damage_max'] if resolved_instance else item['damage_max']
        text += t('inventory.damage', lang, min=weapon_min, max=weapon_max) + '\n'
    elif item['item_type'] in ('armor', 'accessory'):
        text += f" | {t('common.level_short', lang)}{item['req_level']}\n\n"
        defense_value = resolved_instance['defense'] if resolved_instance else item['defense']
        text += t('inventory.defense', lang, val=defense_value) + '\n'
    else:
        text += '\n\n'

    metadata_lines = _build_metadata_text_lines(metadata, lang)
    if metadata_lines:
        text += " · ".join(metadata_lines) + '\n'

    text += t('inventory.weight', lang, val=item['weight']) + '\n'

    if inv_row['quantity'] > 1:
        text += t('inventory.quantity', lang, val=inv_row['quantity']) + '\n'

    # Требования
    stat_names = STAT_NAMES.get(lang, STAT_NAMES['ru'])
    reqs = []
    if item['req_strength']  > 0: reqs.append(f"{stat_names['strength']} {item['req_strength']}")
    if item['req_agility']   > 0: reqs.append(f"{stat_names['agility']} {item['req_agility']}")
    if item['req_intuition'] > 0: reqs.append(f"{stat_names['intuition']} {item['req_intuition']}")
    if item['req_wisdom']    > 0: reqs.append(f"{stat_names['wisdom']} {item['req_wisdom']}")
    if reqs:
        text += t('inventory.reqs', lang, val=', '.join(reqs)) + '\n'

    # Бонусы
    stat_bonus = resolved_instance.get('resolved_stat_bonus', {}) if resolved_instance else json.loads(item['stat_bonus_json'])
    bonuses = [f"{_get_localized_stat_label(k, lang)} +{v}" for k, v in stat_bonus.items() if k not in ('heal', 'mana')]
    if bonuses:
        text += t('inventory.bonuses', lang, val=', '.join(bonuses)) + '\n'

    if resolved_instance:
        secondary_rolls = resolved_instance.get('secondary_rolls', [])
        if secondary_rolls:
            secondary_lines = [
                f"{_get_localized_stat_label(str(roll.get('stat')), lang)} +{int(roll.get('value', 0))}"
                for roll in secondary_rolls
            ]
            text += t('inventory.instance_secondaries', lang, val=', '.join(secondary_lines)) + '\n'
        equipped_suffix = t('gear.equipped_suffix', lang, slot=equipped_slot) if equipped_slot else ''
        text += t('gear.ownership', lang, id=inv_row['id'], equipped=equipped_suffix) + '\n'

    if item['description']:
        from game.starter_kit import STARTER_WEAPONS
        description = get_item_description(inv_row['item_id'], lang) or item['description']
        if inv_row['item_id'] in STARTER_WEAPONS:
            description = t('chapter.starter_description', lang)
        elif inv_row['item_id'] in {'trail_vest', 'field_ration'}:
            description = t(f"chapter.{inv_row['item_id']}_description", lang)
        text += f"\n<i>{description}</i>\n"

    if inv_row.get('entry_type') == 'gear_instance' and instance_enhance < MAX_ENHANCE_LEVEL:
        req = get_enhance_requirements_for_target_level(instance_enhance + 1)
        chances = get_enhance_outcome_chances_for_target_level(instance_enhance + 1)
        material_name = get_item_name(req['material_id'], lang)
        text += '\n' + t(
            'inventory.enhance_cost',
            lang,
            next=instance_enhance + 1,
            gold=req['gold'],
            material=material_name,
            qty=req['material_qty'],
        )
        text += '\n' + t(
            'inventory.enhance_risk',
            lang,
            success=int(round(chances['success'] * 100)),
            fail=int(round(chances['fail'] * 100)),
            rollback=int(round(chances['rollback'] * 100)),
            break_chance=int(round(chances['break'] * 100)),
        )

    if equipped:
        text += f"\n<b>{t('inventory.equipped', lang)}</b>"

    # Кнопки
    keyboard = []
    if item['item_type'] in ('weapon', 'armor', 'accessory'):
        if equipped:
            if inv_row.get('entry_type') == 'gear_instance':
                intent = issue_gear_intent(telegram_id, 'unequip', inv_row['id'], target_slot=equipped_slot)
                callback = f"inv_gunequip_{intent}_{entry_token}_{back_tab}" if intent else None
            else:
                intent = issue_legacy_gear_intent(telegram_id, 'unequip', inv_row['id'], target_slot=equipped_slot)
                callback = f"inv_lunequip_{intent}_{entry_token}_{back_tab}" if intent else None
            if callback:
                keyboard.append([InlineKeyboardButton(t('inventory.unequip_btn', lang), callback_data=callback)])
        else:
            identity = str(metadata.get('slot_identity') or '')
            if identity == 'ring':
                if inv_row.get('entry_type') == 'gear_instance':
                    intents = issue_gear_equip_intents(telegram_id, inv_row['id'], ['ring1', 'ring2'])
                    prefix = 'inv_gequip'
                else:
                    intents = issue_legacy_gear_equip_intents(telegram_id, inv_row['id'], ['ring1', 'ring2'])
                    prefix = 'inv_lequip'
                ring_buttons = []
                for slot in ('ring1', 'ring2'):
                    if slot in intents:
                        ring_buttons.append(InlineKeyboardButton(
                            t(f'gear.equip_{slot}_btn', lang),
                            callback_data=f"{prefix}_{intents[slot]}_{entry_token}_{back_tab}",
                        ))
                if ring_buttons:
                    keyboard.append(ring_buttons)
            else:
                equip_slot = resolve_equip_slot_for_item(inv_row['item_id'], eq)
                if equip_slot:
                    if inv_row.get('entry_type') == 'gear_instance':
                        intent = issue_gear_intent(telegram_id, 'equip', inv_row['id'], target_slot=equip_slot)
                        callback = f"inv_gequip_{intent}_{entry_token}_{back_tab}" if intent else None
                    else:
                        intent = issue_legacy_gear_intent(telegram_id, 'equip', inv_row['id'], target_slot=equip_slot)
                        callback = f"inv_lequip_{intent}_{entry_token}_{back_tab}" if intent else None
                    if callback:
                        keyboard.append([InlineKeyboardButton(t('inventory.equip_btn', lang), callback_data=callback)])
        if inv_row.get('entry_type') == 'gear_instance' and instance_enhance < MAX_ENHANCE_LEVEL:
            intent = issue_gear_intent(telegram_id, 'enhance', inv_row['id'])
            if intent:
                keyboard.append([InlineKeyboardButton(t('inventory.enhance_btn', lang), callback_data=f"inv_genh_{intent}_{entry_token}_{back_tab}")])
        if inv_row.get('entry_type') == 'gear_instance':
            identity = str(metadata.get('slot_identity') or '')
            if identity == 'ring':
                keyboard.append([
                    InlineKeyboardButton(t('gear.compare_ring1_btn', lang), callback_data=f'inv_cmp_{entry_token}_ring1_{back_tab}'),
                    InlineKeyboardButton(t('gear.compare_ring2_btn', lang), callback_data=f'inv_cmp_{entry_token}_ring2_{back_tab}'),
                ])
            else:
                compare_slot = equipped_slot or resolve_equip_slot_for_item(inv_row['item_id'], eq)
                if compare_slot:
                    keyboard.append([InlineKeyboardButton(t('gear.compare_btn', lang), callback_data=f'inv_cmp_{entry_token}_{compare_slot}_{back_tab}')])
            if is_field_item(inv_row['item_id']):
                index = FIELD_ITEM_IDS.index(inv_row['item_id'])
                keyboard.append([InlineKeyboardButton(t('gear.goal_btn', lang), callback_data=f'inv_igoal_{index}_{entry_token}_{back_tab}')])
            if not equipped:
                preview = build_gear_mutation_preview(telegram_id, 'sale', inv_row['id'])
                token = issue_gear_intent(telegram_id, 'sale', inv_row['id']) if preview else None
                if token:
                    keyboard.append([InlineKeyboardButton(
                        t('gear.sell_btn', lang, gold=preview['cost']['gold']),
                        callback_data=f'inv_sellask_{token}_{entry_token}_{back_tab}',
                    )])
    elif item['item_type'] == 'potion':
        from game.action_receipts import issue_actions
        payload = f"{inv_row['id']}:{inv_row['quantity']}"
        token = issue_actions(telegram_id, 'use', [payload])[payload]
        keyboard.append([InlineKeyboardButton(t('inventory.use_btn', lang), callback_data=f"inv_use_{token}_{back_tab}")])

    if inv_row.get('entry_type') != 'gear_instance':
        keyboard.append([
            InlineKeyboardButton(t('inventory.drop_btn', lang),     callback_data=f"inv_drop_{entry_token}_{back_tab}"),
            InlineKeyboardButton(t('inventory.transfer_btn', lang), callback_data=f"inv_transfer_{entry_token}"),
        ])
    keyboard.append([InlineKeyboardButton(t('inventory.back_btn', lang), callback_data=f"inv_tab_{back_tab}")])

    return text, InlineKeyboardMarkup(keyboard)


def build_field_catalog(player: dict, category: str = 'weapon', page: int = 0) -> tuple:
    lang = player.get('lang', 'ru')
    view = catalog_page(category, page)
    goal = get_equipment_goal(int(player['telegram_id']))
    lines = [t('gear.catalog_title', lang), t('gear.catalog_intro', lang), '',
             t('gear.goal_current', lang, name=get_item_name(goal, lang)) if goal else t('gear.goal_none', lang),
             t('gear.page', lang, page=view['page'] + 1, pages=view['page_count'])]
    rows = [[
        InlineKeyboardButton(t(f'gear.category_{key}', lang), callback_data=f'inv_cat_{key}_0')
        for key in ('weapon', 'armor', 'offhand', 'accessories')
    ]]
    for item_id in view['item_ids']:
        index = FIELD_ITEM_IDS.index(item_id)
        marker = '🎯 ' if goal == item_id else ''
        rows.append([InlineKeyboardButton(
            marker + get_item_name(item_id, lang),
            callback_data=f"inv_citem_{index}_{view['category']}_{view['page']}",
        )])
    nav = []
    if view['page'] > 0:
        nav.append(InlineKeyboardButton('◀️', callback_data=f"inv_cat_{view['category']}_{view['page'] - 1}"))
    if view['page'] + 1 < view['page_count']:
        nav.append(InlineKeyboardButton('▶️', callback_data=f"inv_cat_{view['category']}_{view['page'] + 1}"))
    if nav:
        rows.append(nav)
    if goal:
        rows.append([InlineKeyboardButton(t('gear.goal_clear_btn', lang), callback_data=f"inv_gclear_{view['category']}_{view['page']}")])
    rows.append([InlineKeyboardButton(t('gear.refresh_btn', lang), callback_data=f"inv_cat_{view['category']}_{view['page']}")])
    rows.append([InlineKeyboardButton(t('gear.receipts_btn', lang), callback_data='inv_receipts')])
    rows.append([InlineKeyboardButton(t('gear.back_btn', lang), callback_data='inv_tab_weapon')])
    return '\n'.join(lines), InlineKeyboardMarkup(rows)


def build_field_catalog_detail(player: dict, item_id: str, category: str, page: int) -> tuple:
    lang = player.get('lang', 'ru')
    item = get_item(item_id) or {}
    resolved = resolve_template_preview(item_id)
    metadata = get_item_metadata(item_id)
    sources = get_field_source_manifest(item_id)
    family_key = metadata.get('weapon_profile') or metadata.get('armor_class') or metadata.get('offhand_profile')
    family = (
        WEAPON_PROFILE_NAME.get(lang, WEAPON_PROFILE_NAME['ru']).get(family_key)
        or ARMOR_CLASS_NAME.get(lang, ARMOR_CLASS_NAME['ru']).get(family_key)
        or OFFHAND_PROFILE_NAME.get(lang, OFFHAND_PROFILE_NAME['ru']).get(family_key)
        or '—'
    )
    slot_key = metadata.get('slot_identity') or ''
    slot = SLOT_IDENTITY_NAME.get(lang, SLOT_IDENTITY_NAME['ru']).get(slot_key, '—')
    lines = [f"<b>{get_item_name(item_id, lang)}</b>", get_item_description(item_id, lang), '',
             t('gear.family', lang, value=family), t('gear.slot', lang, value=slot),
             t('gear.tier_rarity', lang, tier=1, rarity=RARITY_NAME.get(lang, RARITY_NAME['ru'])['common'], enhance=0),
             t('gear.price', lang, price=item.get('buy_price', 0), sale=5)]
    contribution = {key: value for key, value in contribution_from_resolved_item(resolved).items() if value}
    for key, value in contribution.items():
        lines.append(f"• {t(f'gear.stat_{key}', lang)}: +{value}")
    vendors = ', '.join(get_location_name(location_id, lang) for location_id in sources['vendors'])
    curated = ', '.join(get_location_name(ROUTE_SOURCE_HUBS[route_id], lang) for route_id in sources['curated_routes'])
    lines += ['', t('gear.vendors', lang, places=vendors)]
    if curated:
        lines.append(t('gear.curated_routes', lang, places=curated))
    lines.append(t('gear.universal_routes', lang))
    rows = [[InlineKeyboardButton(t('gear.goal_btn', lang), callback_data=f'inv_goal_{FIELD_ITEM_IDS.index(item_id)}_{category}_{page}')]]
    for route_id in sources['curated_routes']:
        hub_id = ROUTE_SOURCE_HUBS[route_id]
        if is_location_discovered(int(player['telegram_id']), hub_id):
            rows.append([InlineKeyboardButton(
                f"🗺️ {get_location_name(hub_id, lang)}",
                callback_data=f"map_route_{route_id.removeprefix('route_')}",
            )])
    if str(player.get('location_id')) in FIELD_VENDOR_LOCATIONS:
        from game.action_receipts import issue_actions
        token = issue_actions(int(player['telegram_id']), 'shop_buy', [item_id]).get(item_id)
        if token:
            rows.append([InlineKeyboardButton(
                t('gear.buy_here_btn', lang, gold=item.get('buy_price', 0)),
                callback_data=f'shop_buy_{item_id}|{token}',
            )])
    rows.append([InlineKeyboardButton(t('gear.back_btn', lang), callback_data=f'inv_cat_{category}_{page}')])
    return '\n'.join(lines)[:4096], InlineKeyboardMarkup(rows)


def build_recent_gear_receipts(player: dict, page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    from game.pve_reward_settlement import list_recent_reward_receipts

    lang = player.get('lang', 'ru')
    receipts = list_recent_reward_receipts(int(player['telegram_id']), limit=20)
    page_size = 6
    page_count = max(1, (len(receipts) + page_size - 1) // page_size)
    page = max(0, min(page_count - 1, int(page)))
    visible = receipts[page * page_size:(page + 1) * page_size]
    lines = [t('gear.receipts_title', lang), t('gear.page', lang, page=page + 1, pages=page_count)]
    rows = []
    if not receipts:
        lines.append(t('gear.receipts_empty', lang))
    for receipt in visible:
        recipient = receipt['recipient']
        timestamp = str(receipt.get('applied_at') or '')[:16].replace('T', ' ')
        lines.append(t(
            'gear.receipt_line', lang,
            time=timestamp,
            place=get_location_name(str(receipt.get('location_id') or ''), lang),
            exp=int(recipient.get('exp', 0)),
            gold=int(recipient.get('gold', 0)),
            gear=len(recipient.get('gear') or []),
        ))
        callback = f"inv_receipt_{receipt['encounter_id']}_{page}"
        if len(callback.encode('utf-8')) <= 64:
            rows.append([InlineKeyboardButton(
                t('gear.receipt_open_btn', lang, time=timestamp),
                callback_data=callback,
            )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton('◀️', callback_data=f'inv_rpage_{page - 1}'))
    if page + 1 < page_count:
        nav.append(InlineKeyboardButton('▶️', callback_data=f'inv_rpage_{page + 1}'))
    if nav:
        rows.append(nav)
    rows.extend([
        [InlineKeyboardButton(t('gear.refresh_btn', lang), callback_data=f'inv_rpage_{page}')],
        [InlineKeyboardButton(t('gear.back_btn', lang), callback_data='inv_catalog')],
    ])
    return '\n'.join(lines)[:4096], InlineKeyboardMarkup(rows)


def build_reward_receipt_detail(player: dict, encounter_id: str, page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    from game.pve_reward_settlement import get_reward_receipt_for_player

    lang = player.get('lang', 'ru')
    receipt = get_reward_receipt_for_player(int(player['telegram_id']), encounter_id)
    if not receipt:
        return t('gear.state_changed', lang), InlineKeyboardMarkup([[
            InlineKeyboardButton(t('gear.back_btn', lang), callback_data=f'inv_rpage_{page}')]])
    recipient = receipt['recipient']
    timestamp = str(receipt.get('applied_at') or '')[:16].replace('T', ' ')
    lines = [
        t('gear.receipt_detail_title', lang),
        t('gear.receipt_id', lang, id=encounter_id),
        t('gear.receipt_time_place', lang, time=timestamp,
          place=get_location_name(str(receipt.get('location_id') or ''), lang)),
        t('gear.receipt_rewards', lang, exp=int(recipient.get('exp', 0)), gold=int(recipient.get('gold', 0))),
        t('gear.receipt_guaranteed_yes' if recipient.get('guaranteed') else 'gear.receipt_guaranteed_no', lang),
    ]
    stackables = Counter(str(item_id) for item_id in recipient.get('stackable_items') or [])
    gear_rows = list(recipient.get('gear') or [])
    if not stackables and not gear_rows:
        lines.append(t('gear.receipt_no_items', lang))
    for item_id, quantity in sorted(stackables.items()):
        lines.append(t('gear.receipt_stackable_line', lang,
                       name=get_item_name(item_id, lang), quantity=quantity))
    for gear in gear_rows:
        rarity = RARITY_NAME.get(lang, RARITY_NAME['ru']).get(str(gear.get('rarity')), str(gear.get('rarity')))
        lines.append(t(
            'gear.receipt_gear_line', lang,
            name=get_item_name(str(gear.get('base_item_id') or ''), lang),
            id=int(gear.get('instance_id', 0)),
            tier=int(gear.get('item_tier', 1)),
            rarity=rarity,
            enhance=int(gear.get('enhance_level', 0)),
            guarantee=t('gear.receipt_gear_guaranteed', lang) if gear.get('guaranteed') else '',
        ))
    return '\n'.join(lines)[:4096], InlineKeyboardMarkup([[
        InlineKeyboardButton(t('gear.back_btn', lang), callback_data=f'inv_rpage_{page}')]])


def build_gear_comparison(player_id: int, entry_token: str, slot: str, back_tab: str, lang: str) -> tuple:
    entry_type, instance_id = _parse_entry_token(entry_token)
    comparison = compare_instance_to_slot(player_id, instance_id, slot) if entry_type == 'gear_instance' else None
    if not comparison:
        return t('gear.state_changed', lang), InlineKeyboardMarkup([[
            InlineKeyboardButton(t('gear.back_btn', lang), callback_data=f'inv_tab_{back_tab}')]])
    current_name = get_item_name(comparison['current_item_id'], lang) if comparison['current_item_id'] else t('gear.comparison_empty', lang)
    lines = [t('gear.comparison_title', lang, candidate=get_item_name(comparison['candidate_item_id'], lang), current=current_name)]
    for key in COMPARISON_CHANNELS:
        delta = comparison['deltas'][key]
        if not delta:
            continue
        sign = f'+{delta}' if delta > 0 else str(delta)
        lines.append(t('gear.comparison_line', lang, label=t(f'gear.stat_{key}', lang),
                       current=comparison['current'][key], candidate=comparison['candidate'][key], delta=sign))
    if len(lines) == 1:
        lines.append(t('gear.comparison_no_change', lang))
    return '\n'.join(lines), InlineKeyboardMarkup([[
        InlineKeyboardButton(t('gear.back_btn', lang), callback_data=f'inv_item_{entry_token}_{back_tab}')]])

# ────────────────────────────────────────
# КОМАНДА /inventory
# ────────────────────────────────────────

async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p    = get_player(user.id)
    lang = get_player_lang(user.id)

    if not p:
        await update.message.reply_text(t('common.no_character', lang))
        return

    text, keyboard = build_inventory_list(user.id, 'weapon', lang)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')

# ────────────────────────────────────────
# КНОПКИ ИНВЕНТАРЯ
# ────────────────────────────────────────

async def handle_inventory_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    user  = query.from_user
    player_row = get_player(user.id)
    if not player_row:
        await query.answer(t('common.no_character', 'ru'), show_alert=True)
        return
    p     = dict(player_row)
    lang  = get_player_lang(user.id)
    effective_stats = get_player_effective_stats(user.id, p)

    if data.startswith(('inv_equip_', 'inv_unequip_', 'inv_enhance_', 'inv_drop_', 'inv_transfer_',
                        'inv_gequip_', 'inv_gunequip_', 'inv_genh_', 'inv_lequip_', 'inv_lunequip_',
                        'inv_sellask_', 'inv_gsell_')):
        from game.pvp_live import has_active_live_pvp_engagement
        if p['in_battle'] or has_active_live_pvp_engagement(user.id):
            await query.answer(t('chapter.in_battle', lang), show_alert=True)
            return

    if data == 'inv_noop':
        await query.answer()
        return

    if data == 'inv_catalog':
        text, keyboard = build_field_catalog(p, 'weapon', 0)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data == 'inv_receipts':
        text, keyboard = build_recent_gear_receipts(p, 0)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('inv_rpage_'):
        raw_page = data.removeprefix('inv_rpage_')
        if not raw_page.isdigit():
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        text, keyboard = build_recent_gear_receipts(p, int(raw_page))
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('inv_receipt_'):
        raw = data.removeprefix('inv_receipt_')
        encounter_id, separator, raw_page = raw.rpartition('_')
        if not separator or not encounter_id or not raw_page.isdigit():
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        text, keyboard = build_reward_receipt_detail(p, encounter_id, int(raw_page))
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('inv_cat_'):
        parts = data.split('_')
        if len(parts) != 4:
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        text, keyboard = build_field_catalog(p, parts[2], int(parts[3]))
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('inv_citem_'):
        parts = data.split('_')
        if len(parts) != 5 or not parts[2].isdigit() or int(parts[2]) >= len(FIELD_ITEM_IDS):
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        text, keyboard = build_field_catalog_detail(p, FIELD_ITEM_IDS[int(parts[2])], parts[3], int(parts[4]))
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('inv_goal_'):
        parts = data.split('_')
        if len(parts) != 5 or not parts[2].isdigit() or int(parts[2]) >= len(FIELD_ITEM_IDS):
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        item_id = FIELD_ITEM_IDS[int(parts[2])]
        if not set_equipment_goal(user.id, item_id):
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        await query.answer(t('gear.goal_set', lang, name=get_item_name(item_id, lang)), show_alert=True)
        text, keyboard = build_field_catalog_detail(dict(get_player(user.id)), item_id, parts[3], int(parts[4]))
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    if data.startswith('inv_igoal_'):
        parts = data.split('_')
        if len(parts) != 5 or not parts[2].isdigit() or int(parts[2]) >= len(FIELD_ITEM_IDS):
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        item_id = FIELD_ITEM_IDS[int(parts[2])]
        if not set_equipment_goal(user.id, item_id):
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        await query.answer(t('gear.goal_set', lang, name=get_item_name(item_id, lang)), show_alert=True)
        text, keyboard = build_item_detail(user.id, parts[3], parts[4], lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    if data.startswith('inv_gclear_'):
        parts = data.split('_')
        if len(parts) != 4 or not set_equipment_goal(user.id, None):
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        text, keyboard = build_field_catalog(dict(get_player(user.id)), parts[2], int(parts[3]))
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('inv_cmp_'):
        parts = data.split('_')
        if len(parts) != 5:
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        text, keyboard = build_gear_comparison(user.id, parts[2], parts[3], parts[4], lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('inv_sellask_'):
        parts = data.split('_')
        if len(parts) != 5:
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        entry = _load_inventory_entry(user.id, parts[3])
        preview = build_gear_mutation_preview(user.id, 'sale', entry['id']) if entry else None
        if not preview:
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        text = t('gear.sell_confirm', lang, gold=preview['cost']['gold'])
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t('common.confirm', lang), callback_data=f'inv_gsell_{parts[2]}_{parts[3]}_{parts[4]}')],
            [InlineKeyboardButton(t('gear.back_btn', lang), callback_data=f'inv_item_{parts[3]}_{parts[4]}')],
        ])
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('inv_gsell_'):
        parts = data.split('_')
        if len(parts) != 5:
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        result = apply_gear_intent(user.id, 'sale', parts[2])
        if result.get('status') != 'sold':
            key = 'equipped_item' if result.get('status') == 'equipped_item' else 'state_changed'
            await query.answer(t(f'gear.{key}', lang), show_alert=True)
            return
        await query.answer(t('gear.sold', lang, gold=result['gold']), show_alert=True)
        text, keyboard = build_inventory_list(user.id, parts[4], lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    if data.startswith(('inv_gequip_', 'inv_gunequip_', 'inv_genh_')):
        parts = data.split('_')
        if len(parts) != 5:
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        action = 'equip' if parts[1] == 'gequip' else 'unequip' if parts[1] == 'gunequip' else 'enhance'
        result = apply_gear_intent(user.id, action, parts[2])
        expected = {'equip': 'equipped', 'unequip': 'unequipped', 'enhance': 'enhanced'}[action]
        if result.get('status') != expected:
            key = result.get('status') if result.get('status') in {'no_gold', 'no_material', 'equipped_item', 'max_tier', 'not_eligible'} else 'state_changed'
            await query.answer(t(f'gear.{key}', lang), show_alert=True)
            return
        if action == 'equip':
            message = t('inventory.equipped_ok', lang, name=get_item_name((_load_inventory_entry(user.id, parts[3]) or {}).get('item_id', ''), lang))
        elif action == 'unequip':
            message = t('inventory.unequipped_ok', lang)
        else:
            outcome = result.get('outcome', 'fail')
            after = result.get('after')
            message = t('inventory.enhance_ok', lang, level=after, gold=result['cost']['gold'],
                        material=get_item_name(result['cost']['material_id'], lang), qty=result['cost']['material_qty']) if outcome == 'success' else t(
                f'inventory.enhance_{outcome}', lang, before=result.get('before'), after=after,
                level=result.get('before'), gold=result['cost']['gold'],
                material=get_item_name(result['cost']['material_id'], lang), qty=result['cost']['material_qty'])
        await query.answer(message, show_alert=True)
        if action == 'enhance' and result.get('outcome') == 'break':
            text, keyboard = build_inventory_list(user.id, parts[4], lang)
        else:
            text, keyboard = build_item_detail(user.id, parts[3], parts[4], lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    if data.startswith(('inv_lequip_', 'inv_lunequip_')):
        parts = data.split('_')
        if len(parts) != 5:
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        action = 'equip' if parts[1] == 'lequip' else 'unequip'
        result = apply_legacy_gear_intent(user.id, action, parts[2])
        expected = 'equipped' if action == 'equip' else 'unequipped'
        if result.get('status') != expected:
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        entry = _load_inventory_entry(user.id, parts[3])
        message = (
            t('inventory.equipped_ok', lang, name=get_item_name((entry or {}).get('item_id', ''), lang))
            if action == 'equip'
            else t('inventory.unequipped_ok', lang)
        )
        await query.answer(message, show_alert=True)
        text, keyboard = build_item_detail(user.id, parts[3], parts[4], lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    # ── Смена вкладки ──
    if data.startswith('inv_tab_'):
        route = data.removeprefix('inv_tab_')
        if _parse_inventory_route(route) is None:
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        text, keyboard = build_inventory_list(user.id, route, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    # ── Детальный вид ──
    if data.startswith('inv_item_'):
        parts = data.split('_')
        if len(parts) != 4 or _parse_inventory_route(parts[3]) is None:
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        entry_token = parts[2]
        back_tab = parts[3]
        text, keyboard = build_item_detail(user.id, entry_token, back_tab, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    if data.startswith('inv_enhance_'):
        parts = data.split('_')
        entry_token = parts[2]
        back_tab = parts[3]
        inv_row = _load_inventory_entry(user.id, entry_token)
        if not inv_row:
            await query.answer(t('inventory.item_not_found', lang), show_alert=True)
            return
        if inv_row.get('entry_type') != 'gear_instance':
            await query.answer(t('inventory.enhance_only_instance', lang), show_alert=True)
            return

        await query.answer(t('gear.state_changed', lang), show_alert=True)
        return

    # ── Экипировать ──
    if data.startswith('inv_equip_'):
        # Reviewed-head callbacks carried mutable slot authority.  They remain
        # parseable for backward compatibility but never mutate after V1.
        await query.answer(t('gear.state_changed', lang), show_alert=True)
        return

    # ── Снять ──
    if data.startswith('inv_unequip_'):
        await query.answer(t('gear.state_changed', lang), show_alert=True)
        return

    # ── Использовать зелье ──
    if data.startswith('inv_use_'):
        parts = data.split('_')
        if len(parts) != 4:
            await query.answer(t('chapter.stale_action', lang), show_alert=True)
            return
        result = use_inventory_consumable(user.id, parts[2])
        if result['status'] != 'used':
            await query.answer(t(f"chapter.{result['status']}", lang), show_alert=True)
            return
        msg = t('inventory.healed', lang, val=result['heal']) + '\n' + t('inventory.mana_restored', lang, val=result['mana'])
        await query.answer(msg, show_alert=True)
        text, keyboard = build_inventory_list(user.id, parts[3], lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    # ── Выбросить ──
    if data.startswith('inv_drop_'):
        parts    = data.split('_')
        entry_token = parts[2]
        back_tab = parts[3]

        inv_row = _load_inventory_entry(user.id, entry_token)
        if not inv_row:
            await query.answer(t('inventory.item_not_found', lang), show_alert=True)
            return

        if inv_row.get('entry_type') == 'legacy_inventory' and is_equipped(user.id, inv_row['id']):
            await query.answer(t('inventory.drop_equipped', lang), show_alert=True)
            return
        if inv_row.get('entry_type') == 'gear_instance' and inv_row.get('equipped_slot'):
            await query.answer(t('inventory.drop_equipped', lang), show_alert=True)
            return
        if inv_row.get('entry_type') == 'gear_instance':
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return

        conn    = get_connection()
        if inv_row.get('entry_type') == 'gear_instance':
            conn.execute('DELETE FROM gear_instances WHERE telegram_id=? AND id=?', (user.id, inv_row['id']))
        else:
            if inv_row['quantity'] > 1:
                conn.execute('UPDATE inventory SET quantity=quantity-1 WHERE id=?', (inv_row['id'],))
            else:
                conn.execute('DELETE FROM inventory WHERE id=?', (inv_row['id'],))
        conn.commit()
        conn.close()

        await query.answer(t('inventory.dropped', lang, name=get_item_name(inv_row['item_id'], lang)))
        text, keyboard = build_inventory_list(user.id, back_tab, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    # ── Передать ──
    if data.startswith('inv_transfer_'):
        entry_token = data.replace('inv_transfer_', '')
        if entry_token.startswith('g'):
            await query.answer(t('gear.state_changed', lang), show_alert=True)
            return
        context.user_data['transfer_item'] = entry_token
        await query.edit_message_text(
            t('inventory.transfer_prompt', lang),
            parse_mode='HTML'
        )
        await query.answer()
        return

    await query.answer()

# ── Обработка ввода username для передачи ──
async def handle_transfer_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if 'transfer_item' not in context.user_data:
        return False

    entry_token = context.user_data.pop('transfer_item')
    username = update.message.text.strip().lstrip('@')
    user     = update.effective_user
    lang     = get_player_lang(user.id)

    conn   = get_connection()
    target = conn.execute('SELECT * FROM players WHERE username=?', (username,)).fetchone()

    if not target:
        await update.message.reply_text(t('inventory.transfer_not_found', lang, username=username))
        conn.close()
        return True

    if target['telegram_id'] == user.id:
        await update.message.reply_text(t('inventory.transfer_self', lang))
        conn.close()
        return True

    inv_row = _load_inventory_entry(user.id, entry_token)

    if not inv_row:
        await update.message.reply_text(t('inventory.item_not_found', lang))
        conn.close()
        return True

    if inv_row.get('entry_type') == 'gear_instance':
        if inv_row.get('equipped_slot'):
            await update.message.reply_text(t('inventory.drop_equipped', lang))
            conn.close()
            return True
        conn.execute(
            'UPDATE gear_instances SET telegram_id=? WHERE id=? AND telegram_id=?',
            (target['telegram_id'], inv_row['id'], user.id),
        )
    else:
        existing = conn.execute(
            'SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (target['telegram_id'], inv_row['item_id'])
        ).fetchone()

        if existing:
            conn.execute('UPDATE inventory SET quantity=quantity+1 WHERE id=?', (existing['id'],))
        else:
            conn.execute(
                'INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?,?,1)',
                (target['telegram_id'], inv_row['item_id'])
            )

        if inv_row['quantity'] > 1:
            conn.execute('UPDATE inventory SET quantity=quantity-1 WHERE id=?', (inv_row['id'],))
        else:
            conn.execute('DELETE FROM inventory WHERE id=?', (inv_row['id'],))

    conn.commit()
    conn.close()

    await update.message.reply_text(
        t('inventory.transfer_ok', lang, name=get_item_name(inv_row['item_id'], lang), username=username),
        parse_mode='HTML'
    )
    return True

print('✅ handlers/inventory.py обновлён!')
