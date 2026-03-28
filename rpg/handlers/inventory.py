# ============================================================
# inventory.py — инвентарь игрока
# ============================================================

import sys, json, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_player, get_connection, is_in_battle
from game.items_data import get_item, get_item_metadata
from game.i18n import t, get_player_lang, get_item_name
from game.equipment_stats import get_player_effective_stats, clamp_player_resources_to_effective_caps
from game.gear_instances import (
    list_player_gear_instances,
    get_equipped_gear_instances,
    equip_gear_instance_in_slot,
    equip_legacy_inventory_in_slot,
    resolve_gear_instance_item_data,
    unequip_slot_across_models,
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

def build_tab_keyboard(active_tab: str, lang: str) -> list:
    row = []
    for tab_key in TABS:
        label = t(f'inventory.tab_{tab_key}', lang)
        if tab_key == active_tab:
            row.append(InlineKeyboardButton(f"[{label}]", callback_data='inv_noop'))
        else:
            row.append(InlineKeyboardButton(label, callback_data=f'inv_tab_{tab_key}'))
    return row


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


def build_inventory_list(telegram_id: int, active_tab: str, lang: str = 'ru') -> tuple:
    items = []
    if active_tab in ('weapon', 'armor', 'accessory'):
        items.extend(get_gear_inventory_entries(telegram_id, active_tab))
    legacy_items = get_inventory(telegram_id, active_tab)
    for row in legacy_items:
        row['entry_type'] = 'legacy_inventory'
        items.append(row)

    eq = get_equipped(telegram_id)
    keyboard = [build_tab_keyboard(active_tab, lang)]

    text = t('inventory.title', lang) + '\n\n'

    if not items:
        text += t('inventory.empty', lang) + '\n'
    else:
        for inv_row in items:
            item = get_item(inv_row['item_id'])
            if not item:
                continue

            entry_rarity, entry_tier = _get_entry_rarity_and_tier(inv_row, item)
            rarity  = t(f"inventory.{RARITY_KEYS.get(entry_rarity, 'rarity_common')}", lang)
            enhance = f" +{inv_row['enhance_level']}" if inv_row['enhance_level'] > 0 else ""
            qty     = f" x{inv_row['quantity']}" if inv_row['quantity'] > 1 else ""
            token = make_entry_token(inv_row.get('entry_type', 'legacy_inventory'), inv_row['id'])
            eq_mark = t('inventory.equipped', lang) if token in eq.values() else ""
            tier_tag = f" {t('inventory.instance_tier_short', lang, tier=entry_tier)}" if inv_row.get('entry_type') == 'gear_instance' else ''

            label = f"{rarity} {get_item_name(inv_row['item_id'], lang)}{tier_tag}{enhance}{qty}{eq_mark}"
            keyboard.append([InlineKeyboardButton(
                label,
                callback_data=f"inv_item_{token}_{active_tab}"
            )])

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
    item_name    = get_item_name(inv_row['item_id'], lang)

    text = f"{rarity_emoji} <b>{item_name}{enhance}</b>\n{rarity_name}"
    if inv_row.get('entry_type') == 'gear_instance':
        text += f" · {t('inventory.instance_tier', lang, tier=tier_value)}"

    if item['item_type'] == 'weapon':
        wtype = WEAPON_TYPE_NAME.get(lang, WEAPON_TYPE_NAME['ru']).get(item['weapon_type'], '')
        text += f" | {wtype} | Ур.{item['req_level']}\n\n"
        weapon_min = resolved_instance['damage_min'] if resolved_instance else item['damage_min']
        weapon_max = resolved_instance['damage_max'] if resolved_instance else item['damage_max']
        text += t('inventory.damage', lang, min=weapon_min, max=weapon_max) + '\n'
    elif item['item_type'] in ('armor', 'accessory'):
        text += f" | Ур.{item['req_level']}\n\n"
        text += t('inventory.defense', lang, val=item['defense']) + '\n'
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

    if item['description']:
        text += f"\n<i>{item['description']}</i>\n"

    if equipped:
        text += f"\n<b>{t('inventory.equipped', lang)}</b>"

    # Кнопки
    keyboard = []
    if item['item_type'] in ('weapon', 'armor', 'accessory'):
        if equipped:
            keyboard.append([InlineKeyboardButton(t('inventory.unequip_btn', lang), callback_data=f"inv_unequip_{entry_token}_{equipped_slot}_{back_tab}")])
        else:
            equip_slot = resolve_equip_slot_for_item(inv_row['item_id'], eq)
            if equip_slot:
                keyboard.append([InlineKeyboardButton(t('inventory.equip_btn', lang), callback_data=f"inv_equip_{entry_token}_{equip_slot}_{back_tab}")])
    elif item['item_type'] == 'potion':
        keyboard.append([InlineKeyboardButton(t('inventory.use_btn', lang), callback_data=f"inv_use_{entry_token}_{back_tab}")])

    keyboard.append([
        InlineKeyboardButton(t('inventory.drop_btn', lang),     callback_data=f"inv_drop_{entry_token}_{back_tab}"),
        InlineKeyboardButton(t('inventory.transfer_btn', lang), callback_data=f"inv_transfer_{entry_token}"),
    ])
    keyboard.append([InlineKeyboardButton(t('inventory.back_btn', lang), callback_data=f"inv_tab_{back_tab}")])

    return text, InlineKeyboardMarkup(keyboard)

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
    p     = dict(get_player(user.id))
    lang  = get_player_lang(user.id)
    effective_stats = get_player_effective_stats(user.id, p)

    if data == 'inv_noop':
        await query.answer()
        return

    # ── Смена вкладки ──
    if data.startswith('inv_tab_'):
        tab = data.replace('inv_tab_', '')
        text, keyboard = build_inventory_list(user.id, tab, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    # ── Детальный вид ──
    if data.startswith('inv_item_'):
        parts    = data.split('_')
        entry_token = parts[2]
        back_tab = parts[3]
        text, keyboard = build_item_detail(user.id, entry_token, back_tab, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    # ── Экипировать ──
    if data.startswith('inv_equip_'):
        parts    = data.split('_')
        entry_token = parts[2]
        slot     = parts[3]
        back_tab = parts[4]

        inv_row = _load_inventory_entry(user.id, entry_token)
        if not inv_row:
            await query.answer(t('inventory.item_not_found', lang), show_alert=True)
            return
        item = get_item(inv_row['item_id'])

        if p['level']     < item['req_level']:     await query.answer(t('inventory.req_level',     lang, level=item['req_level']),     show_alert=True); return
        if p['strength']  < item['req_strength']:  await query.answer(t('inventory.req_strength',  lang, val=item['req_strength']),    show_alert=True); return
        if p['agility']   < item['req_agility']:   await query.answer(t('inventory.req_agility',   lang, val=item['req_agility']),     show_alert=True); return
        if p['intuition'] < item['req_intuition']: await query.answer(t('inventory.req_intuition', lang, val=item['req_intuition']),   show_alert=True); return
        if p['wisdom']    < item['req_wisdom']:    await query.answer(t('inventory.req_wisdom',    lang, val=item['req_wisdom']),      show_alert=True); return

        if inv_row.get('entry_type') == 'gear_instance':
            equip_gear_instance_in_slot(user.id, inv_row['id'], slot)
        else:
            equip_legacy_inventory_in_slot(user.id, inv_row['id'], slot)
        clamp_player_resources_to_effective_caps(user.id)

        await query.answer(t('inventory.equipped_ok', lang, name=get_item_name(inv_row['item_id'], lang)))
        text, keyboard = build_item_detail(user.id, entry_token, back_tab, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    # ── Снять ──
    if data.startswith('inv_unequip_'):
        parts    = data.split('_')
        entry_token = parts[2]
        slot     = parts[3]
        back_tab = parts[4]

        unequip_slot_across_models(user.id, slot)
        clamp_player_resources_to_effective_caps(user.id)

        await query.answer(t('inventory.unequipped_ok', lang))
        text, keyboard = build_item_detail(user.id, entry_token, back_tab, lang)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        return

    # ── Использовать зелье ──
    if data.startswith('inv_use_'):
        parts    = data.split('_')
        entry_token = parts[2]
        back_tab = parts[3]

        inv_row = _load_inventory_entry(user.id, entry_token)
        if not inv_row:
            await query.answer(t('inventory.item_not_found', lang), show_alert=True)
            return
        if inv_row.get('entry_type') == 'gear_instance':
            await query.answer(t('inventory.item_not_found', lang), show_alert=True)
            return
        item  = get_item(inv_row['item_id'])
        bonus = json.loads(item['stat_bonus_json'])

        conn = get_connection()
        msg  = ""

        if 'heal' in bonus:
            heal = _calc_safe_restore_amount(p['hp'], effective_stats['max_hp'], bonus['heal'])
            conn.execute('UPDATE players SET hp=hp+? WHERE telegram_id=?', (heal, user.id))
            msg += t('inventory.healed', lang, val=heal) + '\n'

        if 'mana' in bonus:
            mana_gain = _calc_safe_restore_amount(p['mana'], effective_stats['max_mana'], bonus['mana'])
            conn.execute('UPDATE players SET mana=mana+? WHERE telegram_id=?', (mana_gain, user.id))
            msg += t('inventory.mana_restored', lang, val=mana_gain) + '\n'

        if inv_row['quantity'] > 1:
            conn.execute('UPDATE inventory SET quantity=quantity-1 WHERE id=?', (inv_row['id'],))
        else:
            conn.execute('DELETE FROM inventory WHERE id=?', (inv_row['id'],))

        conn.commit()
        conn.close()

        await query.answer(msg or t('inventory.used_ok', lang), show_alert=True)
        text, keyboard = build_inventory_list(user.id, back_tab, lang)
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
