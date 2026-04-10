# ============================================================
# battle.py — обработчик боёв в Telegram
# ============================================================

import sys, json
sys.path.append('/content/rpg_bot')
import random

from game.skill_engine import get_battle_skills
from game.weapon_mastery import get_mastery, add_mastery_exp, tick_cooldowns
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from database import get_player, get_connection
from game.mobs import get_mob
from game.combat import (
    init_battle, process_turn, calc_rewards,
    calc_death_penalty, hp_bar, resolve_enemy_response, process_skill_turn,
    process_enemy_side_turn, apply_timeout_fallback_guard, preview_skill_turn_precheck,
)
from game.pve_live import (
    create_or_load_open_world_pve_encounter,
    choose_enemy_target_participant_id,
    ensure_location_pve_spawn_instances,
    finish_solo_pve_encounter,
    ensure_runtime_for_battle,
    list_location_available_spawn_instances,
    get_pve_encounter_player_ids,
    load_active_solo_pve_encounter,
    mark_group_participant_defeated,
    persist_solo_pve_encounter_state,
    process_due_timeout_for_battle,
    resolve_current_side_if_ready,
    run_with_participant_projection,
    run_enemy_instant_side,
    submit_player_commit,
    sync_projection_for_participant,
    update_participant_combat_state_from_projection,
)
from game.balance import (
    exp_to_next_level, calc_max_hp, normalize_weapon_profile,
    normalize_offhand_profile, normalize_armor_class, normalize_damage_school,
    normalize_encumbrance,
)
from game.items_data import get_item, get_item_encumbrance
from game.itemization import get_item_archetype_metadata
from game.i18n import t, get_item_name, get_skill_name, get_mob_name
from game.equipment_stats import get_equipped_item_ids, get_player_effective_stats
from game.gear_instances import (
    get_equipped_gear_instances,
    grant_item_to_player,
    resolve_gear_instance_item_data,
)
from game.reward_source_metadata import build_open_world_combat_source_metadata
from game.locations import get_mob_location_id
from game.pvp_death_policy import resolve_death_respawn_hub


# ────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ────────────────────────────────────────

def save_battle(telegram_id: int):
    """Сохраняем состояние боя в БД."""
    conn = get_connection()
    conn.execute(
        'UPDATE players SET in_battle=1 WHERE telegram_id=?',
        (telegram_id,)
    )
    conn.commit()
    conn.close()

def end_battle(telegram_id: int):
    """Заканчиваем бой."""
    conn = get_connection()
    conn.execute(
        'UPDATE players SET in_battle=0 WHERE telegram_id=?',
        (telegram_id,)
    )
    conn.commit()
    conn.close()


def _rollback_prebattle_lock_if_needed(*, context, telegram_id: int, should_rollback: bool) -> None:
    if not should_rollback:
        return
    conn = get_connection()
    conn.execute('UPDATE players SET in_battle=0 WHERE telegram_id=?', (telegram_id,))
    conn.commit()
    conn.close()
    if context is not None:
        app_state = context.application.user_data.setdefault(telegram_id, {})
        app_state.pop('aggro_message_id', None)

def add_to_inventory(telegram_id: int, item_id: str, quantity: int = 1):
    """Добавляет предмет в инвентарь."""
    grant_item_to_player(telegram_id, item_id, quantity=quantity)


def get_equipped_combat_items(telegram_id: int) -> dict[str, dict]:
    """
    Runtime read-model for equipped items:
    - start from instance-first+legacy fallback ids
    - overwrite instance slots with resolved instance data (tier-scaled where relevant)
    """
    equipped_item_ids = get_equipped_item_ids(telegram_id)
    equipped_items: dict[str, dict] = {}
    for slot, item_id in equipped_item_ids.items():
        item = get_item(item_id)
        if item:
            equipped_items[slot] = item

    for slot, instance_row in get_equipped_gear_instances(telegram_id).items():
        equipped_items[slot] = resolve_gear_instance_item_data(instance_row)

    return equipped_items

def apply_rewards(telegram_id: int, player: dict, rewards: dict) -> dict:
    new_exp  = player['exp'] + rewards['exp']
    new_gold = player['gold'] + rewards['gold']
    leveled_up = False
    new_level  = player['level']

    while new_exp >= exp_to_next_level(new_level):
        new_exp  -= exp_to_next_level(new_level)
        new_level += 1
        leveled_up = True

    levels_gained = new_level - player['level']
    stat_points = player['stat_points'] + (3 * levels_gained)

    conn = get_connection()
    try:
        conn.execute(
            '''UPDATE players SET
                exp=?, gold=?, level=?, stat_points=?
               WHERE telegram_id=?''',
            (new_exp, new_gold, new_level, stat_points, telegram_id)
        )
        conn.commit()
    finally:
        conn.close()

    # Сброс кулдаунов после боя
    conn2 = get_connection()
    conn2.execute('DELETE FROM skill_cooldowns WHERE telegram_id=?', (telegram_id,))
    conn2.commit()
    conn2.close()

    mob_level = rewards.get('mob_level', 1)
    source_metadata = build_open_world_combat_source_metadata(
        source_id=str(rewards.get('mob_id', 'unknown_mob')),
        mob_level=mob_level,
        source_category=rewards.get('source_category'),
        creature_taxonomy=rewards.get('creature_taxonomy'),
        encounter_role=rewards.get('encounter_role'),
        location_id=get_mob_location_id(str(rewards.get('mob_id', ''))) or player.get('location_id'),
    )
    for item_id in rewards['loot']:
        grant_item_to_player(
            telegram_id,
            item_id,
            quantity=1,
            source='mob_drop',
            source_level=mob_level,
            source_metadata=source_metadata,
        )

    return {
        'leveled_up': leveled_up,
        'new_level':  new_level,
        'new_exp':    new_exp,
        'new_gold':   new_gold,
    }

def apply_death(telegram_id: int, player: dict):
    """Применяет штраф смерти и возрождает в региональном safe-хабе."""
    penalty  = calc_death_penalty(player)
    new_exp  = max(0, player['exp'] - penalty['exp_loss'])
    new_gold = max(0, player['gold'] - penalty['gold_loss'])

    conn = get_connection()
    revive_hp = int(calc_max_hp(player['vitality']) * 0.30)
    respawn_hub_id = resolve_death_respawn_hub(location_id=player.get('location_id'))

    conn.execute(
        '''UPDATE players SET
            exp=?, gold=?, hp=?,
            location_id=?, in_battle=0
           WHERE telegram_id=?''',
        (new_exp, new_gold, revive_hp, respawn_hub_id, telegram_id)
    )
    conn.commit()
    conn.close()

    conn2 = get_connection()
    conn2.execute('DELETE FROM skill_cooldowns WHERE telegram_id=?', (telegram_id,))
    conn2.commit()
    conn2.close()

    return penalty

# ────────────────────────────────────────
# ОТОБРАЖЕНИЕ БОЯ
# ────────────────────────────────────────

def build_battle_message(player, mob, battle_state, log):
    lang = player.get('lang', 'ru')

    hp_bar_player = hp_bar(battle_state['player_hp'], battle_state['player_max_hp'])
    hp_bar_mob    = hp_bar(battle_state['mob_hp'],    mob['hp'])

    mana_pct = int(battle_state['player_mana'] / max(battle_state['player_max_mana'], 1) * 10)
    mana_bar = '🔵' * mana_pct + '⚫' * (10 - mana_pct)

    weapon_id   = battle_state.get('weapon_id', 'unarmed')
    weapon_name = get_item_name(weapon_id, lang) if weapon_id != 'unarmed' else t('battle.unarmed', lang)

    text  = f"⚔️ <b>{get_mob_name(mob['id'], lang)}</b>\n"
    text += f"{hp_bar_mob} {battle_state['mob_hp']}/{mob['hp']}\n\n"
    text += f"👤 <b>{t('battle.player_label', lang)}</b>\n"
    text += f"{hp_bar_player} {battle_state['player_hp']}/{battle_state['player_max_hp']}\n"
    text += f"🔵 {battle_state['player_mana']}/{battle_state['player_max_mana']}\n"
    text += f"🗡️ {weapon_name}\n"

    # Активные баффы
    buff_lines = []
    if battle_state.get('defense_buff_turns', 0) > 0:
        buff_lines.append(t('battle.buff_defense', lang,
            value=battle_state['defense_buff_value'],
            turns=battle_state['defense_buff_turns']))
    if battle_state.get('berserk_turns', 0) > 0:
        buff_lines.append(t('battle.buff_berserk', lang,
            value=battle_state['berserk_damage'],
            turns=battle_state['berserk_turns']))
    if battle_state.get('blessing_turns', 0) > 0:
        buff_lines.append(t('battle.buff_blessing', lang,
            value=battle_state['blessing_value'],
            turns=battle_state['blessing_turns']))
    if battle_state.get('regen_turns', 0) > 0:
        buff_lines.append(t('battle.buff_regen', lang,
            amount=battle_state['regen_amount'],
            turns=battle_state['regen_turns']))
    if battle_state.get('resurrection_active'):
        buff_lines.append(t('battle.buff_resurrection', lang))
    if battle_state.get('invincible_turns', 0) > 0:
        buff_lines.append(t('battle.buff_invincible', lang,
            turns=battle_state['invincible_turns']))

    if battle_state.get('dodge_buff_turns', 0) > 0:
        buff_lines.append(t('battle.buff_dodge', lang,
            value=battle_state['dodge_buff_value'],
            turns=battle_state['dodge_buff_turns']))

    if battle_state.get('guaranteed_crit_turns', 0) > 0:
        buff_lines.append(t('battle.buff_guaranteed_crit', lang,
            turns=battle_state['guaranteed_crit_turns']))

    if battle_state.get('hunters_mark_turns', 0) > 0:
        buff_lines.append(t('battle.buff_hunters_mark', lang,
            turns=battle_state['hunters_mark_turns']))

    if battle_state.get('vulnerability_turns', 0) > 0:
        buff_lines.append(t('battle.buff_vulnerability', lang,
            turns=battle_state['vulnerability_turns']))

    if battle_state.get('disarm_turns', 0) > 0:
        buff_lines.append(t('battle.buff_disarm', lang,
            turns=battle_state['disarm_turns']))

    if battle_state.get('fire_shield_turns', 0) > 0:
        buff_lines.append(t('battle.buff_fire_shield', lang,
            value=battle_state['fire_shield_value'],
            turns=battle_state['fire_shield_turns']))

    if buff_lines:
        text += '\n'.join(buff_lines) + '\n'

    # Лог последних ходов
    if log:
        text += '\n' + '\n'.join(
            f'▫️ {l}' for l in log[-4:] if isinstance(l, str)
        ) + '\n'

    # Кнопки
    keyboard = [[
        InlineKeyboardButton(t('battle.attack_btn', lang), callback_data=f"battle_attack_{mob['id']}"),
        InlineKeyboardButton(t('battle.flee_btn', lang),   callback_data=f"battle_flee_{mob['id']}"),
    ]]

    # Скиллы в бою
    weapon_id     = battle_state.get('weapon_id', 'unarmed')
    weapon_profile = battle_state.get('weapon_profile', 'unarmed')
    mastery_level = battle_state.get('mastery_level', 1)
    skills        = get_battle_skills(
        player['telegram_id'],
        weapon_id,
        mastery_level,
        weapon_profile,
    )

    if skills:
        for skill in skills:
            cd    = skill['cooldown_left']
            mana  = skill['mana_cost_actual']
            label = f"{get_skill_name(skill['id'], lang)} {t('common.level_short', lang)}{skill['skill_level']}"
            if cd > 0:
                label += f" ⏳{cd}"
            else:
                label += f" 🔵{mana}"
            keyboard.append([InlineKeyboardButton(
                label, callback_data=f"battle_skill_{skill['id']}|{mob['id']}"
            )])

    keyboard.append([InlineKeyboardButton(
        t('battle.potions_btn', lang), callback_data=f"battle_potions_{mob['id']}"
    )])

    return text, InlineKeyboardMarkup(keyboard)

# ────────────────────────────────────────
# НАЧАЛО БОЯ
# ────────────────────────────────────────

async def start_battle(update, context, mob_id: str, mob_first: bool = False, spawn_instance_id: str | None = None):
    """Запускает бой — вызывается из location.py."""
    query = update.callback_query
    user  = query.from_user
    p     = dict(get_player(user.id))
    lang  = p.get('lang', 'ru')
    aggro_prelock = bool(mob_first and int(p.get('in_battle', 0) or 0) == 1)

    if spawn_instance_id:
        location_id = str(p.get('location_id') or '')
        ensure_location_pve_spawn_instances(location_id=location_id)
        spawn_rows = list_location_available_spawn_instances(location_id=location_id)
        spawn_by_id = {str(row.get('spawn_instance_id')): row for row in spawn_rows}
        selected_spawn = spawn_by_id.get(str(spawn_instance_id))
        if not selected_spawn:
            _rollback_prebattle_lock_if_needed(context=context, telegram_id=user.id, should_rollback=aggro_prelock)
            await query.answer(t('location.pve_spawn_unavailable', lang), show_alert=True)
            return
        mob_id = str(selected_spawn.get('mob_id') or '')

    mob = get_mob(mob_id)
    if not mob:
        _rollback_prebattle_lock_if_needed(context=context, telegram_id=user.id, should_rollback=aggro_prelock)
        await query.answer(t('battle.mob_not_found', lang), show_alert=True)
        return

    equipped_items = get_equipped_combat_items(user.id)
    weapon_item = equipped_items.get('weapon')
    offhand_item = equipped_items.get('offhand')
    chest_item = equipped_items.get('chest')

    effective_stats = get_player_effective_stats(user.id, p)
    p['strength'] = effective_stats['strength']
    p['agility'] = effective_stats['agility']
    p['intuition'] = effective_stats['intuition']
    p['vitality'] = effective_stats['vitality']
    p['wisdom'] = effective_stats['wisdom']
    p['luck'] = effective_stats['luck']
    p['max_hp'] = effective_stats['max_hp']
    p['max_mana'] = effective_stats['max_mana']
    p['hp'] = min(p['hp'], p['max_hp'])
    p['mana'] = min(p['mana'], p['max_mana'])
    p['equipment_physical_defense_bonus'] = effective_stats['physical_defense_bonus']
    p['equipment_magic_defense_bonus'] = effective_stats['magic_defense_bonus']
    p['equipment_accuracy_bonus'] = effective_stats['accuracy_bonus']
    p['equipment_evasion_bonus'] = effective_stats['evasion_bonus']
    p['equipment_block_chance_bonus'] = effective_stats['block_chance_bonus']
    p['equipment_magic_power_bonus'] = effective_stats['magic_power_bonus']
    p['equipment_healing_power_bonus'] = effective_stats['healing_power_bonus']

    # Явный special-case для unarmed, чтобы profile не падал в sword_1h.
    if weapon_item:
        p['weapon_type'] = weapon_item.get('weapon_type', 'melee')
        p['weapon_profile'] = normalize_weapon_profile(
            weapon_item.get('weapon_profile'),
            p['weapon_type'],
        )
        p['weapon_damage'] = random.randint(
            weapon_item.get('damage_min', 10),
            weapon_item.get('damage_max', 10),
        )
        p['weapon_name'] = get_item_name(weapon_item.get('item_id', 'unarmed'), lang)
        p['damage_school'] = normalize_damage_school(
            weapon_item.get('damage_school'),
            weapon_profile=p['weapon_profile'],
            weapon_type=p['weapon_type'],
        )
    else:
        p['weapon_type'] = 'melee'
        p['weapon_profile'] = 'unarmed'
        p['weapon_damage'] = 10
        p['weapon_name'] = t('battle.unarmed', lang)
        p['damage_school'] = 'physical'

    chest_meta = get_item_archetype_metadata(chest_item)
    offhand_meta = get_item_archetype_metadata(offhand_item)
    p['armor_class'] = normalize_armor_class(chest_meta.get('armor_class'))
    p['offhand_profile'] = normalize_offhand_profile(offhand_meta.get('offhand_profile'))
    p['encumbrance'] = normalize_encumbrance(
        get_item_encumbrance(chest_item) or get_item_encumbrance(offhand_item)
    )

    # Инициализируем бой
    battle_state = init_battle(p, mob, mob_first=mob_first)
    battle_state['weapon_type']   = p.get('weapon_type', 'melee')
    battle_state['weapon_profile'] = p.get('weapon_profile', 'unarmed')
    battle_state['armor_class'] = p.get('armor_class')
    battle_state['offhand_profile'] = p.get('offhand_profile', 'none')
    battle_state['damage_school'] = p.get('damage_school', 'physical')
    battle_state['encumbrance'] = p.get('encumbrance')
    battle_state['weapon_damage'] = p.get('weapon_damage', 10)
    battle_state['weapon_name']   = p.get('weapon_name', t('battle.unarmed', lang))
    battle_state['equipment_physical_defense_bonus'] = p.get('equipment_physical_defense_bonus', 0)
    battle_state['equipment_magic_defense_bonus'] = p.get('equipment_magic_defense_bonus', 0)
    battle_state['equipment_accuracy_bonus'] = p.get('equipment_accuracy_bonus', 0)
    battle_state['equipment_evasion_bonus'] = p.get('equipment_evasion_bonus', 0)
    battle_state['equipment_block_chance_bonus'] = p.get('equipment_block_chance_bonus', 0)
    battle_state['equipment_magic_power_bonus'] = p.get('equipment_magic_power_bonus', 0)
    battle_state['equipment_healing_power_bonus'] = p.get('equipment_healing_power_bonus', 0)
    battle_state['effective_strength'] = p.get('strength', 1)
    battle_state['effective_agility'] = p.get('agility', 1)
    battle_state['effective_intuition'] = p.get('intuition', 1)
    battle_state['effective_vitality'] = p.get('vitality', 1)
    battle_state['effective_wisdom'] = p.get('wisdom', 1)
    battle_state['effective_luck'] = p.get('luck', 1)
    battle_state['location_id'] = p.get('location_id')

    # Владение оружием
    actual_weapon_id = 'unarmed'
    if weapon_item:
        actual_weapon_id = weapon_item['item_id']

    mastery = get_mastery(user.id, actual_weapon_id)
    battle_state['weapon_id']     = actual_weapon_id
    battle_state['mastery_level'] = mastery['level']
    battle_state['mastery_exp']   = mastery['exp']
    encounter_id, encounter_status = create_or_load_open_world_pve_encounter(
        owner_player_id=user.id,
        location_id=str(p.get('location_id') or ''),
        mob_id=mob_id,
        battle_state=battle_state,
        mob=mob,
        side_a_player_ids=[user.id],
        spawn_instance_id=spawn_instance_id,
    )
    if not encounter_id:
        _rollback_prebattle_lock_if_needed(context=context, telegram_id=user.id, should_rollback=aggro_prelock)
        await query.answer(t('location.pve_spawn_unavailable', lang), show_alert=True)
        return
    if encounter_status == 'spawn_busy':
        _rollback_prebattle_lock_if_needed(context=context, telegram_id=user.id, should_rollback=aggro_prelock)
        await query.answer(t('location.pve_spawn_engaged', lang), show_alert=True)
        return
    battle_state['pve_encounter_id'] = encounter_id

    # Если моб ходит первым — сразу обрабатываем его ход
    if mob_first:
        from game.combat import mob_attack
        mob_result = mob_attack(mob, p)
        p['hp']    = mob_result['player_hp']
        battle_state['player_hp'] = p['hp']
        battle_state['log']       = [t('battle.mob_attack', lang,
                                        mob_name=get_mob_name(mob['id'], lang),
                                        damage=mob_result['damage'])]

        if p['hp'] <= 0:
            penalty = apply_death(user.id, p)
            await query.edit_message_text(
                t('battle.death_first_strike', lang,
                  mob_name=get_mob_name(mob['id'], lang),
                  exp_loss=penalty['exp_loss'],
                  gold_loss=penalty['gold_loss']),
                parse_mode='HTML'
            )
            return

    # Сохраняем состояние в context
    context.user_data['battle']     = battle_state
    context.user_data['battle_mob'] = mob
    ensure_runtime_for_battle(player_id=user.id, battle_state=battle_state, mob=mob)
    persist_solo_pve_encounter_state(
        encounter_id=str(battle_state.get('pve_encounter_id', '')),
        battle_state=battle_state,
        mob=mob,
    )

    save_battle(user.id)

    text, keyboard = build_battle_message(p, mob, battle_state, battle_state.get('log', []))
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')

# ────────────────────────────────────────
# КНОПКИ В БОЮ
# ────────────────────────────────────────

async def safe_edit(query, text, reply_markup=None, parse_mode='HTML'):
    """edit_message_text без краша если сообщение не изменилось."""
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as e:
        if 'Message is not modified' not in str(e):
            raise

async def _handle_victory_cleanup(
    query,
    context,
    user_id: int,
    player: dict,
    mob: dict,
    battle_state: dict,
    lang: str,
    levelup_before_loot: bool = False,
):
    """Общий post-victory cleanup для обычной атаки и скиллов."""
    rewards = calc_rewards(mob)
    if _is_group_encounter(battle_state):
        participant_ids = get_pve_encounter_player_ids(encounter_id=str(battle_state.get('pve_encounter_id', '')))
        if not participant_ids:
            participant_ids = _group_participant_ids(battle_state)
    else:
        participant_ids = [user_id]
    rewarded_participants: list[int] = []
    result_reward = None
    for participant_id in participant_ids:
        snapshot = _participant_snapshot(battle_state, participant_id)
        if snapshot and bool(snapshot.get('player_dead', snapshot.get('defeated', False))):
            end_battle(participant_id)
            continue

        participant_player_row = get_player(participant_id)
        if participant_player_row:
            participant_player = dict(participant_player_row)
            reward_result = apply_rewards(participant_id, participant_player, rewards)
            rewarded_participants.append(participant_id)
            if participant_id == user_id:
                result_reward = reward_result
        end_battle(participant_id)

    if result_reward is None:
        result_reward = {
            'leveled_up': False,
            'new_level': player.get('level', 1),
            'new_exp': player.get('exp', 0),
            'new_gold': player.get('gold', 0),
        }

    finish_solo_pve_encounter(
        player_id=user_id,
        encounter_id=battle_state.get('pve_encounter_id'),
        status='victory',
    )
    context.user_data.pop('battle', None)
    context.user_data.pop('battle_mob', None)

    weapon_id = battle_state.get('weapon_id', 'unarmed')
    mastery_result = add_mastery_exp(user_id, weapon_id, 10)
    mastery_text = _build_mastery_text(mastery_result, lang)

    owner_penalty = (battle_state.get('group_death_penalties') or {}).get(str(user_id))
    owner_snapshot = _participant_snapshot(battle_state, user_id)
    owner_dead = bool(owner_snapshot.get('player_dead', owner_snapshot.get('defeated', False)))

    victory_text = t('battle.victory', lang,
                     mob_name=get_mob_name(mob['id'], lang),
                     exp=rewards['exp'],
                     gold=rewards['gold'])
    if owner_dead and owner_penalty:
        victory_text = t(
            'battle.death',
            lang,
            exp_loss=owner_penalty.get('exp_loss', 0),
            gold_loss=owner_penalty.get('gold_loss', 0),
        )

    levelup_text = ""
    if result_reward['leveled_up']:
        levelup_text = '\n\n' + t('battle.levelup', lang, level=result_reward['new_level'])

    loot_text = ""
    if rewards['loot']:
        loot_names = [get_item_name(i, lang) for i in rewards['loot']]
        loot_text = '\n' + t('battle.loot', lang, items=', '.join(loot_names))

    if levelup_before_loot:
        await safe_edit(query, victory_text + levelup_text + loot_text + mastery_text, parse_mode='HTML')
    else:
        await safe_edit(query, victory_text + loot_text + levelup_text + mastery_text, parse_mode='HTML')

async def _handle_death_or_resurrection(
    query,
    context,
    user_id: int,
    player: dict,
    mob: dict,
    battle_state: dict,
    lang: str,
    log: list,
    death_key: str = 'battle.death',
    clear_player_dead_flag: bool = False,
    answer_on_resurrection: bool = False,
) -> bool:
    """
    Общий путь завершения боя при смерти игрока.
    Возвращает True, если ветка (resurrection/death) была полностью обработана.
    """
    if battle_state.get('resurrection_active'):
        revive_hp = int(battle_state['player_max_hp'] * battle_state['resurrection_hp'] / 100)
        battle_state['player_hp'] = revive_hp
        if clear_player_dead_flag:
            battle_state['player_dead'] = False
        battle_state['resurrection_active'] = False
        log.append(t('battle.buff_resurrection_proc', lang, hp=revive_hp))
        update_participant_combat_state_from_projection(battle_state=battle_state, player_id=user_id)
        context.user_data['battle'] = battle_state
        persist_solo_pve_encounter_state(
            encounter_id=str(battle_state.get('pve_encounter_id', '')),
            battle_state=battle_state,
            mob=mob,
        )

        text, keyboard = build_battle_message(player, mob, battle_state, log)
        await safe_edit(query, text, reply_markup=keyboard, parse_mode='HTML')
        if answer_on_resurrection:
            await query.answer()
        return True

    grouped_penalties = battle_state.get('group_death_penalties') or {}
    cached_penalty = grouped_penalties.get(str(user_id)) if _is_group_encounter(battle_state) else None
    penalty = cached_penalty or apply_death(user_id, player)
    battle_state['player_dead'] = True
    battle_state['player_hp'] = 0
    update_participant_combat_state_from_projection(battle_state=battle_state, player_id=user_id)

    if _is_group_encounter(battle_state) and not _all_group_participants_defeated(battle_state):
        mark_group_participant_defeated(
            encounter_id=str(battle_state.get('pve_encounter_id', '')),
            participant_id=user_id,
            status='defeated',
        )
        end_battle(user_id)
        persist_solo_pve_encounter_state(
            encounter_id=str(battle_state.get('pve_encounter_id', '')),
            battle_state=battle_state,
            mob=mob,
        )
        context.user_data.pop('battle', None)
        context.user_data.pop('battle_mob', None)
        await safe_edit(query,
            t(death_key, lang, exp_loss=penalty['exp_loss'], gold_loss=penalty['gold_loss']),
            parse_mode='HTML'
        )
        return True

    end_battle(user_id)
    finish_solo_pve_encounter(
        player_id=user_id,
        encounter_id=battle_state.get('pve_encounter_id'),
        status='death',
    )
    context.user_data.pop('battle', None)
    context.user_data.pop('battle_mob', None)
    await safe_edit(query,
        t(death_key, lang, exp_loss=penalty['exp_loss'], gold_loss=penalty['gold_loss']),
        parse_mode='HTML'
    )
    return True

async def _resolve_post_attack_combat_resolution(
    query,
    context,
    user_id: int,
    player: dict,
    mob: dict,
    battle_state: dict,
    lang: str,
) -> bool:
    """Единый post-attack combat resolution: victory/death/persist/render."""
    _process_group_participant_death_consequences(
        battle_state=battle_state,
        owner_player_id=user_id,
        log=battle_state.get('log'),
        lang=lang,
    )

    # Моб убит
    if battle_state['mob_dead']:
        await _handle_victory_cleanup(
            query=query,
            context=context,
            user_id=user_id,
            player=player,
            mob=mob,
            battle_state=battle_state,
            lang=lang,
            levelup_before_loot=False,
        )
        return True

    # Игрок убит
    if battle_state['player_dead']:
        await _handle_death_or_resurrection(
            query=query,
            context=context,
            user_id=user_id,
            player=player,
            mob=mob,
            battle_state=battle_state,
            lang=lang,
            log=battle_state['log'],
            death_key='battle.death',
            clear_player_dead_flag=True,
            answer_on_resurrection=False,
        )
        return True

    await _handle_battle_continues_update(
        query=query,
        user_id=user_id,
        player=player,
        mob=mob,
        battle_state=battle_state,
    )
    return False

async def _handle_battle_continues_update(
    query,
    user_id: int,
    player: dict,
    mob: dict,
    battle_state: dict,
) -> None:
    """Общий путь для продолжающегося боя: persist hp/mana + рендер."""
    update_participant_combat_state_from_projection(battle_state=battle_state, player_id=user_id)
    if _is_group_encounter(battle_state):
        _persist_group_participant_hp_mana(battle_state)
    else:
        conn = get_connection()
        conn.execute(
            'UPDATE players SET hp=?, mana=? WHERE telegram_id=?',
            (battle_state['player_hp'], battle_state['player_mana'], user_id)
        )
        conn.commit()
        conn.close()
    persist_solo_pve_encounter_state(
        encounter_id=str(battle_state.get('pve_encounter_id', '')),
        battle_state=battle_state,
        mob=mob,
    )

    # Бой продолжается
    text, keyboard = build_battle_message(player, mob, battle_state, battle_state['log'])
    await safe_edit(query, text, reply_markup=keyboard, parse_mode='HTML')


def _build_enemy_response_player_state(player: dict, battle_state: dict) -> dict:
    return {
        'hp': battle_state.get('player_hp', player.get('hp', 0)),
        'agility': battle_state.get('effective_agility', player.get('agility', 1)),
        'vitality': battle_state.get('effective_vitality', player.get('vitality', 1)),
        'wisdom': battle_state.get('effective_wisdom', player.get('wisdom', 1)),
        'luck': battle_state.get('effective_luck', player.get('luck', 1)),
        'armor_class': battle_state.get('armor_class'),
        'offhand_profile': battle_state.get('offhand_profile', 'none'),
        'encumbrance': battle_state.get('encumbrance'),
        'equipment_physical_defense_bonus': battle_state.get('equipment_physical_defense_bonus', 0),
        'equipment_magic_defense_bonus': battle_state.get('equipment_magic_defense_bonus', 0),
        'equipment_block_chance_bonus': battle_state.get('equipment_block_chance_bonus', 0),
    }


def _group_participant_ids(battle_state: dict) -> list[int]:
    ids: list[int] = []
    for raw in battle_state.get('side_a_player_ids', []):
        try:
            pid = int(raw)
        except (TypeError, ValueError):
            continue
        if pid > 0:
            ids.append(pid)
    return ids


def _is_group_encounter(battle_state: dict) -> bool:
    return len(_group_participant_ids(battle_state)) > 1


def _participant_snapshot(battle_state: dict, participant_id: int) -> dict:
    snapshots = battle_state.get('participant_states', {})
    if not isinstance(snapshots, dict):
        return {}
    snapshot = snapshots.get(str(int(participant_id)))
    return snapshot if isinstance(snapshot, dict) else {}


def _all_group_participants_defeated(battle_state: dict) -> bool:
    participant_ids = _group_participant_ids(battle_state)
    if not participant_ids:
        return bool(battle_state.get('player_dead', False))
    for participant_id in participant_ids:
        snapshot = _participant_snapshot(battle_state, participant_id)
        if not bool(snapshot.get('player_dead', snapshot.get('defeated', False))):
            return False
    return True


def _persist_group_participant_hp_mana(battle_state: dict) -> None:
    participant_ids = _group_participant_ids(battle_state)
    if not participant_ids:
        return
    conn = get_connection()
    try:
        for participant_id in participant_ids:
            snapshot = _participant_snapshot(battle_state, participant_id)
            if not snapshot:
                continue
            hp_value = int(snapshot.get('player_hp', snapshot.get('hp', 0)) or 0)
            mana_value = int(snapshot.get('player_mana', snapshot.get('mana', 0)) or 0)
            conn.execute(
                'UPDATE players SET hp=?, mana=? WHERE telegram_id=?',
                (hp_value, mana_value, participant_id),
            )
        conn.commit()
    finally:
        conn.close()


def _resolve_action_player(participant_id: int, fallback_player: dict) -> dict:
    participant_row = get_player(participant_id)
    if participant_row:
        player = dict(participant_row)
        player['lang'] = fallback_player.get('lang', player.get('lang', 'ru'))
        return player
    return dict(fallback_player)


def _resolve_enemy_target_player_for_group(*, owner_player: dict, battle_state: dict) -> tuple[int, dict]:
    target_id = choose_enemy_target_participant_id(battle_state=battle_state) or int(owner_player.get('telegram_id', 0))
    sync_projection_for_participant(battle_state=battle_state, player_id=target_id)
    target_player = _resolve_action_player(target_id, owner_player)
    return target_id, target_player


def _apply_timeout_fallback_action(action, battle_state: dict, lang: str) -> None:
    if getattr(action, 'action_type', '') == 'fallback_guard':
        participant_id = int(getattr(action, 'participant_id', 0) or 0)
        if participant_id <= 0:
            apply_timeout_fallback_guard(battle_state, lang=lang)
            return
        run_with_participant_projection(
            battle_state=battle_state,
            participant_id=participant_id,
            resolver=lambda: apply_timeout_fallback_guard(battle_state, lang=lang),
        )


def _run_group_enemy_side_action(
    *,
    owner_player: dict,
    mob: dict,
    battle_state: dict,
    lang: str,
    include_pre_enemy_ticks: bool = False,
) -> None:
    target_id, target_player = _resolve_enemy_target_player_for_group(
        owner_player=owner_player,
        battle_state=battle_state,
    )
    player_state = _build_enemy_response_player_state(target_player, battle_state)
    process_enemy_side_turn(
        mob,
        player_state,
        battle_state,
        lang=lang,
        user_id=target_id,
        include_pre_enemy_ticks=include_pre_enemy_ticks,
        tick_player_post_action_buffs=True,
        tick_timed_trigger_buffs=True,
        increment_turn=True,
    )
    update_participant_combat_state_from_projection(battle_state=battle_state, player_id=target_id)
    _reconcile_group_participant_outcomes(battle_state)


def _reconcile_group_participant_outcomes(battle_state: dict) -> None:
    if not _is_group_encounter(battle_state):
        return
    encounter_id = str(battle_state.get('pve_encounter_id', ''))
    if not encounter_id:
        return

    active_participants = get_pve_encounter_player_ids(encounter_id=encounter_id)
    for participant_id in active_participants:
        snapshot = _participant_snapshot(battle_state, participant_id)
        if not snapshot:
            continue
        is_dead = bool(snapshot.get('player_dead', snapshot.get('defeated', False)))
        if int(snapshot.get('player_hp', snapshot.get('hp', 1)) or 0) <= 0:
            is_dead = True
        if not is_dead:
            continue
        if bool(snapshot.get('resurrection_active')):
            continue
        mark_group_participant_defeated(
            encounter_id=encounter_id,
            participant_id=participant_id,
            status='defeated',
        )


def _process_group_participant_death_consequences(
    *,
    battle_state: dict,
    owner_player_id: int,
    log: list | None = None,
    lang: str = 'ru',
) -> None:
    if not _is_group_encounter(battle_state):
        return
    encounter_id = str(battle_state.get('pve_encounter_id', ''))
    if not encounter_id:
        return

    participant_ids = _group_participant_ids(battle_state)
    death_penalties = battle_state.setdefault('group_death_penalties', {})
    for participant_id in participant_ids:
        snapshot = _participant_snapshot(battle_state, participant_id)
        if not snapshot:
            continue
        is_dead = bool(snapshot.get('player_dead', snapshot.get('defeated', False)))
        if int(snapshot.get('player_hp', snapshot.get('hp', 1)) or 0) <= 0:
            is_dead = True
        if not is_dead:
            continue

        sync_projection_for_participant(battle_state=battle_state, player_id=participant_id)
        participant_snapshot = _participant_snapshot(battle_state, participant_id)
        if bool(participant_snapshot.get('resurrection_active')):
            revive_hp = int(
                int(participant_snapshot.get('player_max_hp', participant_snapshot.get('max_hp', 1)) or 1)
                * float(participant_snapshot.get('resurrection_hp', 0.3))
                / 100
            )
            if revive_hp <= 0:
                revive_hp = 1
            battle_state['player_hp'] = revive_hp
            battle_state['hp'] = revive_hp
            battle_state['player_dead'] = False
            battle_state['defeated'] = False
            battle_state['resurrection_active'] = False
            update_participant_combat_state_from_projection(battle_state=battle_state, player_id=participant_id)
            if isinstance(log, list):
                participant_player_row = get_player(participant_id)
                participant_name = str((participant_player_row or {}).get('nickname') or participant_id)
                log.append(t('battle.buff_resurrection_proc', lang, hp=revive_hp) + f' ({participant_name})')
            continue

        if str(participant_id) not in death_penalties:
            participant_player_row = get_player(participant_id)
            if participant_player_row:
                penalty = apply_death(participant_id, dict(participant_player_row))
                death_penalties[str(participant_id)] = penalty

        battle_state['player_dead'] = True
        battle_state['player_hp'] = 0
        battle_state['hp'] = 0
        update_participant_combat_state_from_projection(battle_state=battle_state, player_id=participant_id)
        mark_group_participant_defeated(
            encounter_id=encounter_id,
            participant_id=participant_id,
            status='defeated',
        )
        end_battle(participant_id)

    sync_projection_for_participant(battle_state=battle_state, player_id=owner_player_id)


def _dispatch_group_player_action(
    action,
    *,
    owner_player: dict,
    mob: dict,
    battle_state: dict,
    lang: str,
) -> None:
    actor_id = int(getattr(action, 'participant_id', owner_player.get('telegram_id', 0)) or 0)
    if actor_id <= 0:
        return
    actor_player = _resolve_action_player(actor_id, owner_player)
    action_type = str(getattr(action, 'action_type', '') or '')
    action_skill_id = getattr(action, 'skill_id', None)

    def _mark_terminal_flags() -> None:
        battle_state['mob_dead'] = battle_state.get('mob_dead', battle_state.get('mob_hp', 1) <= 0)
        battle_state['player_dead'] = battle_state.get('player_dead', battle_state.get('player_hp', 1) <= 0)

    def _resolver():
        if action_type == 'basic_attack':
            updated_state = process_turn(
                actor_player,
                mob,
                battle_state,
                lang,
                actor_id,
                include_enemy_response=False,
            )
            if updated_state is not battle_state:
                battle_state.clear()
                battle_state.update(updated_state)
            tick_cooldowns(actor_id)
            _mark_terminal_flags()
            return

        if action_type == 'skill':
            if not action_skill_id:
                apply_timeout_fallback_guard(battle_state, lang=lang)
                _mark_terminal_flags()
                return
            updated = process_skill_turn(
                skill_id=str(action_skill_id),
                player=actor_player,
                mob=mob,
                battle_state=battle_state,
                user_id=actor_id,
                lang=lang,
                include_enemy_response=False,
                tick_timed_trigger_buffs_now=False,
            )['battle_state']
            battle_state.update(updated)
            weapon_id = battle_state.get('weapon_id', 'unarmed')
            add_mastery_exp(actor_id, weapon_id, 5)
            tick_cooldowns(actor_id)
            _mark_terminal_flags()
            return

        if action_type == 'fallback_guard':
            apply_timeout_fallback_guard(battle_state, lang=lang)
            _mark_terminal_flags()
            return

        # Phase-1 explicit safe fallback for unsupported action envelopes.
        apply_timeout_fallback_guard(battle_state, lang=lang)
        _mark_terminal_flags()

    run_with_participant_projection(
        battle_state=battle_state,
        participant_id=actor_id,
        resolver=_resolver,
    )

async def handle_battle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    user  = query.from_user
    p     = dict(get_player(user.id))
    lang  = p.get('lang', 'ru')

    battle_state = context.user_data.get('battle')
    mob          = context.user_data.get('battle_mob')

    # Если состояние боя потеряно (перезапуск бота)
    if not battle_state or not mob:
        restored = load_active_solo_pve_encounter(player_id=user.id)
        if restored:
            battle_state, mob = restored
            context.user_data['battle'] = battle_state
            context.user_data['battle_mob'] = mob
        else:
            end_battle(user.id)
            finish_solo_pve_encounter(player_id=user.id, status='state_lost')
            conn = get_connection()
            conn.execute('DELETE FROM skill_cooldowns WHERE telegram_id=?', (user.id,))
            conn.commit()
            conn.close()

            await safe_edit(query, t('battle.state_lost', lang))
            return

    ensure_runtime_for_battle(player_id=user.id, battle_state=battle_state, mob=mob)
    sync_projection_for_participant(battle_state=battle_state, player_id=user.id)
    timed_out = process_due_timeout_for_battle(
        player_id=user.id,
        battle_state=battle_state,
        on_player_timeout_action=lambda action: _dispatch_group_player_action(
            action,
            owner_player=p,
            mob=mob,
            battle_state=battle_state,
            lang=lang,
        ),
        on_enemy_action=lambda _action: _run_group_enemy_side_action(
            owner_player=p,
            mob=mob,
            battle_state=battle_state,
            lang=lang,
        ),
    )
    if timed_out:
        _reconcile_group_participant_outcomes(battle_state)
        _process_group_participant_death_consequences(
            battle_state=battle_state,
            owner_player_id=user.id,
            log=battle_state.get('log'),
            lang=lang,
        )
        sync_projection_for_participant(battle_state=battle_state, player_id=user.id)
        update_participant_combat_state_from_projection(battle_state=battle_state, player_id=user.id)
        context.user_data['battle'] = battle_state
        handled = await _resolve_post_attack_combat_resolution(
            query=query,
            context=context,
            user_id=user.id,
            player=p,
            mob=mob,
            battle_state=battle_state,
            lang=lang,
        )
        if handled:
            return
        await query.answer()
        return

    # ── Открыть зелья в бою ──
    if data.startswith('battle_potions_'):
        mob_id  = data.replace('battle_potions_', '')
        potions = get_connection().execute('''
            SELECT inv.id, inv.item_id, inv.quantity
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            WHERE inv.telegram_id=? AND i.item_type='potion'
        ''', (user.id,)).fetchall()

        if not potions:
            await query.answer(t('battle.no_potions', lang), show_alert=True)
            return

        keyboard = []
        for pot in potions:
            item = get_item(pot['item_id'])
            keyboard.append([InlineKeyboardButton(
                f"💊 {item['name']} x{pot['quantity']}",
                callback_data=f"battle_use_potion_{pot['id']}_{mob_id}"
            )])
        keyboard.append([InlineKeyboardButton(
            t('common.back', lang), callback_data=f"battle_back_{mob_id}"
        )])

        await safe_edit(query, 
            t('battle.choose_potion', lang),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        await query.answer()
        return

    # ── Использовать зелье в бою ──
    if data.startswith('battle_use_potion_'):
        rest   = data.replace('battle_use_potion_', '', 1)
        inv_id = int(rest.split('_')[0])
        mob_id = '_'.join(rest.split('_')[1:])

        conn    = get_connection()
        inv_row = conn.execute('SELECT * FROM inventory WHERE id=?', (inv_id,)).fetchone()
        conn.close()

        item  = get_item(inv_row['item_id'])
        bonus = json.loads(item['stat_bonus_json'])

        conn = get_connection()
        msg  = ""

        if 'heal' in bonus:
            heal = min(bonus['heal'], battle_state['player_max_hp'] - battle_state['player_hp'])
            battle_state['player_hp'] += heal
            conn.execute('UPDATE players SET hp=hp+? WHERE telegram_id=?', (heal, user.id))
            msg += t('battle.potion_heal', lang, amount=heal)

        if 'mana' in bonus:
            mana_gain = min(bonus['mana'], battle_state['player_max_mana'] - battle_state['player_mana'])
            battle_state['player_mana'] += mana_gain
            conn.execute('UPDATE players SET mana=mana+? WHERE telegram_id=?', (mana_gain, user.id))
            msg += t('battle.potion_mana', lang, amount=mana_gain)

        if inv_row['quantity'] > 1:
            conn.execute('UPDATE inventory SET quantity=quantity-1 WHERE id=?', (inv_id,))
        else:
            conn.execute('DELETE FROM inventory WHERE id=?', (inv_id,))

        conn.commit()
        conn.close()

        context.user_data['battle'] = battle_state
        persist_solo_pve_encounter_state(
            encounter_id=str(battle_state.get('pve_encounter_id', '')),
            battle_state=battle_state,
            mob=mob,
        )
        await query.answer(msg or t('battle.potion_used', lang), show_alert=True)

        mob = context.user_data.get('battle_mob')
        text, keyboard = build_battle_message(p, mob, battle_state, [])
        await safe_edit(query, text, reply_markup=keyboard, parse_mode='HTML')
        return

    # ── Назад к бою ──
    if data.startswith('battle_back_'):
        mob = context.user_data.get('battle_mob')
        text, keyboard = build_battle_message(p, mob, battle_state, battle_state.get('log', []))
        await safe_edit(query, text, reply_markup=keyboard, parse_mode='HTML')
        await query.answer()
        return

    # ── Использовать скилл ──
    if data.startswith('battle_skill_'):
        rest     = data.replace('battle_skill_', '', 1)
        skill_id, mob_id = rest.split('|', 1)

        mob = context.user_data.get('battle_mob')
        precheck_result = preview_skill_turn_precheck(
            skill_id,
            battle_state,
            user_id=user.id,
            lang=lang,
        )
        if not precheck_result.get('success'):
            await query.answer(precheck_result.get('log', t('battle.turn_not_ready', lang)), show_alert=True)
            return

        accepted, _ = submit_player_commit(
            player_id=user.id,
            action_type='skill',
            skill_id=skill_id,
            battle_state=battle_state,
        )
        if not accepted:
            await query.answer(t('battle.turn_not_ready', lang), show_alert=True)
            return

        resolved_player_side = resolve_current_side_if_ready(
            player_id=user.id,
            on_player_action=lambda action: _dispatch_group_player_action(
                action,
                owner_player=p,
                mob=mob,
                battle_state=battle_state,
                lang=lang,
            ),
            on_enemy_action=lambda _action: None,
        )
        if not resolved_player_side:
            context.user_data['battle'] = battle_state
            await _handle_battle_continues_update(
                query=query,
                user_id=user.id,
                player=p,
                mob=mob,
                battle_state=battle_state,
            )
            await query.answer()
            return

        # Важно для group PvE: batch может закончиться на другом участнике.
        # Перед post-resolve ветвлением возвращаем projection владельца callback.
        _reconcile_group_participant_outcomes(battle_state)
        _process_group_participant_death_consequences(
            battle_state=battle_state,
            owner_player_id=user.id,
            log=battle_state.get('log'),
            lang=lang,
        )
        sync_projection_for_participant(battle_state=battle_state, player_id=user.id)
        context.user_data['battle'] = battle_state
        update_participant_combat_state_from_projection(battle_state=battle_state, player_id=user.id)

        if battle_state.get('mob_dead'):
            await _handle_victory_cleanup(
                query=query, context=context, user_id=user.id, player=p, mob=mob,
                battle_state=battle_state, lang=lang, levelup_before_loot=True,
            )
            return

        if (
            not battle_state.get('mob_dead')
            and not battle_state.get('player_dead')
        ):
            run_enemy_instant_side(
                player_id=user.id,
                battle_state=battle_state,
                on_enemy_action=lambda _action: _run_group_enemy_side_action(
                    owner_player=p,
                    mob=mob,
                    battle_state=battle_state,
                    lang=lang,
                    include_pre_enemy_ticks=True,
                ),
            )
            sync_projection_for_participant(battle_state=battle_state, player_id=user.id)

        if battle_state.get('mob_dead'):
            await _handle_victory_cleanup(
                query=query, context=context, user_id=user.id, player=p, mob=mob,
                battle_state=battle_state, lang=lang, levelup_before_loot=True,
            )
            return

        if battle_state.get('player_dead'):
            await _handle_death_or_resurrection(
                query=query, context=context, user_id=user.id, player=p, mob=mob,
                battle_state=battle_state, lang=lang, log=battle_state['log'],
                death_key='battle.death', clear_player_dead_flag=False, answer_on_resurrection=True,
            )
            return

        await _handle_battle_continues_update(
            query=query,
            user_id=user.id,
            player=p,
            mob=mob,
            battle_state=battle_state,
        )
        await query.answer()
        return

    # ── АТАКА ──
    if data.startswith('battle_attack_'):
        accepted, _ = submit_player_commit(
            player_id=user.id,
            action_type='basic_attack',
            battle_state=battle_state,
        )
        if not accepted:
            await query.answer(t('battle.turn_not_ready', lang), show_alert=True)
            return

        resolved_player_side = resolve_current_side_if_ready(
            player_id=user.id,
            on_player_action=lambda action: _dispatch_group_player_action(
                action,
                owner_player=p,
                mob=mob,
                battle_state=battle_state,
                lang=lang,
            ),
            on_enemy_action=lambda _action: None,
        )
        if not resolved_player_side:
            context.user_data['battle'] = battle_state
            await _handle_battle_continues_update(
                query=query,
                user_id=user.id,
                player=p,
                mob=mob,
                battle_state=battle_state,
            )
            await query.answer()
            return

        # Важно для group PvE: batch может закончиться на другом участнике.
        # Перед post-resolve ветвлением возвращаем projection владельца callback.
        _reconcile_group_participant_outcomes(battle_state)
        _process_group_participant_death_consequences(
            battle_state=battle_state,
            owner_player_id=user.id,
            log=battle_state.get('log'),
            lang=lang,
        )
        sync_projection_for_participant(battle_state=battle_state, player_id=user.id)
        if (
            not battle_state.get('mob_dead')
            and not battle_state.get('player_dead')
        ):
            run_enemy_instant_side(
                player_id=user.id,
                battle_state=battle_state,
                on_enemy_action=lambda _action: _run_group_enemy_side_action(
                    owner_player=p,
                    mob=mob,
                    battle_state=battle_state,
                    lang=lang,
                ),
            )
            sync_projection_for_participant(battle_state=battle_state, player_id=user.id)
        context.user_data['battle'] = battle_state
        update_participant_combat_state_from_projection(battle_state=battle_state, player_id=user.id)

        handled = await _resolve_post_attack_combat_resolution(
            query=query,
            context=context,
            user_id=user.id,
            player=p,
            mob=mob,
            battle_state=battle_state,
            lang=lang,
        )
        if handled:
            return

    # ── ПОБЕГ ──
    elif data.startswith('battle_flee_'):
        if random.randint(1, 100) <= 20:
            end_battle(user.id)
            finish_solo_pve_encounter(
                player_id=user.id,
                encounter_id=battle_state.get('pve_encounter_id'),
                status='fled',
            )
            conn = get_connection()
            conn.execute('DELETE FROM skill_cooldowns WHERE telegram_id=?', (user.id,))
            conn.commit()
            conn.close()
            context.user_data.pop('battle', None)
            context.user_data.pop('battle_mob', None)
            await safe_edit(query, 
                t('battle.flee_success', lang, mob_name=get_mob_name(mob['id'], lang)),
                parse_mode='HTML'
            )
            await query.answer()
            return
        else:
            p['hp'] = battle_state['player_hp']
            prev_hp = battle_state['player_hp']
            flee_log = resolve_enemy_response(mob, p, battle_state, lang=lang, user_id=user.id)
            new_hp = battle_state['player_hp']
            context.user_data['battle'] = battle_state

            if new_hp <= 0:
                penalty = apply_death(user.id, p)
                end_battle(user.id)
                finish_solo_pve_encounter(
                    player_id=user.id,
                    encounter_id=battle_state.get('pve_encounter_id'),
                    status='death',
                )
                context.user_data.pop('battle', None)
                context.user_data.pop('battle_mob', None)
                await safe_edit(query, 
                    t('battle.flee_death', lang,
                      mob_name=get_mob_name(mob['id'], lang),
                      exp_loss=penalty['exp_loss'],
                      gold_loss=penalty['gold_loss']),
                    parse_mode='HTML'
                )
                return

            damage_taken = max(0, prev_hp - new_hp)
            flee_fail_header = t('battle.flee_fail', lang,
                                  mob_name=get_mob_name(mob['id'], lang),
                                  damage=damage_taken)
            persist_solo_pve_encounter_state(
                encounter_id=str(battle_state.get('pve_encounter_id', '')),
                battle_state=battle_state,
                mob=mob,
            )
            text, keyboard = build_battle_message(p, mob, battle_state, flee_log)
            await safe_edit(query, 
                flee_fail_header + '\n\n' + text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )


    try:
        await query.answer()
    except BadRequest:
        pass

# ────────────────────────────────────────
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ
# ────────────────────────────────────────

def _build_mastery_text(mastery_result: dict, lang: str) -> str:
    """Формирует текст о повышении мастерства оружия."""
    if not mastery_result.get('leveled_up'):
        return ""

    text = '\n' + t('battle.mastery_up', lang, level=mastery_result['new_level'])
    for skill in mastery_result.get('new_skills', []):
        text += '\n' + t('battle.skill_unlocked', lang, skill_name=get_skill_name(skill['id'], lang))
    return text

print('✅ handlers/battle.py создан!')
