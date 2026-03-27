# ============================================================
# balance.py — все игровые формулы в одном месте
# Если хочешь изменить баланс — меняй только этот файл
# ============================================================
import random

# ────────────────────────────────────────
# ПРОГРЕССИЯ УРОВНЕЙ
# ────────────────────────────────────────

MAX_LEVEL = 100

def exp_to_next_level(level: int) -> int:
    """Сколько опыта нужно чтобы получить следующий уровень."""
    return int(100 * (level ** 1.8))

def stat_points_per_level() -> int:
    """Сколько очков статов даётся за каждый левелап."""
    return 3

# ────────────────────────────────────────
# БАЗОВЫЕ СТАТЫ ПЕРСОНАЖА
# ────────────────────────────────────────

BASE_STATS = {
    'hp':        100,   # базовое HP на старте
    'mana':      50,    # базовая мана на старте
    'strength':  1,     # 💪 Сила
    'agility':   1,     # 🤸 Ловкость
    'intuition': 1,     # 🔮 Интуиция
    'vitality':  1,     # ❤️ Живучесть
    'wisdom':    1,     # 🧠 Мудрость
    'luck':      1,     # 🍀 Удача
}

HIT_CHANCE_MIN = 25
HIT_CHANCE_MAX = 95

CRIT_CHANCE_CAP_PERCENT = 35.0
CRIT_REDUCTION_CAP_PERCENT = 20.0
CRIT_DAMAGE_MULTIPLIER = 2.0

DODGE_HARD_CAP_PERCENT = 35.0
PHYSICAL_AGILITY_MITIGATION_CAP_PERCENT = 12.0

DEFENSE_MITIGATION_HARD_CAP_PERCENT = 55.0
COMBINED_MITIGATION_HARD_CAP_PERCENT = 75.0
PHYSICAL_DEFENSE_SCALING = 120.0
MAGIC_DEFENSE_SCALING = 120.0

MAGIC_SCHOOL_BONUS_CAP_PERCENT = 30.0
HOLY_SCHOOL_BONUS_CAP_PERCENT = 32.0
HEALING_SCHOOL_BONUS_CAP_PERCENT = 35.0


def clamp_hit_chance(chance: int) -> int:
    """Ограничивает шанс попадания в безопасном диапазоне."""
    return max(HIT_CHANCE_MIN, min(HIT_CHANCE_MAX, int(chance)))


def _read_rating_source_value(source, key: str, default: int = 0) -> int:
    if source is None:
        return default
    try:
        value = source.get(key, default)
    except AttributeError:
        try:
            value = source[key]
        except (KeyError, TypeError):
            value = default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_player_accuracy_rating(player, battle_state) -> int:
    agility = _read_rating_source_value(player, 'agility', 0)
    intuition = _read_rating_source_value(player, 'intuition', 0)
    mastery_level = _read_rating_source_value(battle_state, 'mastery_level', 0)
    accuracy_bonus = _read_rating_source_value(battle_state, 'accuracy_bonus', 0)
    return 100 + agility * 2 + intuition + mastery_level * 2 + accuracy_bonus


def get_player_evasion_rating(player, battle_state) -> int:
    agility = _read_rating_source_value(player, 'agility', 0)
    luck = _read_rating_source_value(player, 'luck', 0)
    evasion_bonus = _read_rating_source_value(battle_state, 'evasion_bonus', 0)
    return 100 + agility * 2 + luck + evasion_bonus


def get_enemy_accuracy_rating(mob, battle_state) -> int:
    level = _read_rating_source_value(mob, 'level', 1)
    mob_accuracy = _read_rating_source_value(mob, 'accuracy', 0)
    bonus = _read_rating_source_value(battle_state, 'enemy_accuracy_bonus', 0)
    return 100 + level * 2 + mob_accuracy + bonus


def get_enemy_evasion_rating(mob, battle_state) -> int:
    level = _read_rating_source_value(mob, 'level', 1)
    mob_evasion = _read_rating_source_value(mob, 'evasion', 0)
    bonus = _read_rating_source_value(battle_state, 'enemy_evasion_bonus', 0)
    return 100 + level + mob_evasion + bonus


def resolve_hit_check(accuracy_rating: int, evasion_rating: int, rng_roll: int | None = None) -> dict:
    raw_hit_chance = calc_hit_chance_from_ratings(accuracy_rating, evasion_rating)
    hit_chance = clamp_hit_chance(raw_hit_chance)
    roll = int(rng_roll) if rng_roll is not None else random.randint(1, 100)
    is_hit = roll <= hit_chance
    return {
        'outcome': 'hit' if is_hit else 'miss',
        'is_hit': is_hit,
        'hit_chance': hit_chance,
        'roll': roll,
        'accuracy_rating': int(accuracy_rating),
        'evasion_rating': int(evasion_rating),
    }


def calc_hit_chance_from_ratings(accuracy_rating: int, evasion_rating: int) -> int:
    """Базовый контракт Accuracy vs Evasion до clamp."""
    return 85 + (int(accuracy_rating) - int(evasion_rating)) // 4

# ────────────────────────────────────────
# COMBAT SEMANTICS (Stage 1 hooks)
# ────────────────────────────────────────

VALID_WEAPON_PROFILES = {
    'sword_1h', 'sword_2h', 'axe_2h', 'daggers', 'bow',
    'magic_staff', 'holy_staff', 'wand', 'holy_rod', 'tome', 'unarmed',
}
VALID_ARMOR_CLASSES = {'light', 'medium', 'heavy'}
VALID_OFFHAND_PROFILES = {'none', 'shield', 'focus', 'censer', 'orb', 'tome'}
VALID_DAMAGE_SCHOOLS = {'physical', 'magic', 'holy'}

LEGACY_WEAPON_PROFILE_BY_TYPE = {
    'melee': 'sword_1h',
    'ranged': 'bow',
    'magic': 'magic_staff',
    'light': 'holy_staff',
}

DEFAULT_DAMAGE_SCHOOL_BY_WEAPON_PROFILE = {
    'bow': 'physical',
    'magic_staff': 'magic',
    'wand': 'magic',
    'holy_staff': 'holy',
    'holy_rod': 'holy',
    'tome': 'magic',
}


def normalize_weapon_profile(weapon_profile: str | None, weapon_type: str = 'melee') -> str:
    if weapon_profile in VALID_WEAPON_PROFILES:
        return weapon_profile
    return LEGACY_WEAPON_PROFILE_BY_TYPE.get(weapon_type, 'sword_1h')


def normalize_armor_class(armor_class: str | None) -> str | None:
    if armor_class in VALID_ARMOR_CLASSES:
        return armor_class
    return None


def normalize_offhand_profile(offhand_profile: str | None) -> str:
    if offhand_profile in VALID_OFFHAND_PROFILES:
        return offhand_profile
    return 'none'


def normalize_damage_school(
    damage_school: str | None,
    *,
    weapon_profile: str | None = None,
    weapon_type: str = 'melee',
) -> str:
    if damage_school in VALID_DAMAGE_SCHOOLS:
        return damage_school
    profile = normalize_weapon_profile(weapon_profile, weapon_type)
    return DEFAULT_DAMAGE_SCHOOL_BY_WEAPON_PROFILE.get(profile, 'physical')


def normalize_encumbrance(encumbrance: int | float | None) -> int | None:
    if encumbrance is None:
        return None
    try:
        value = int(encumbrance)
    except (TypeError, ValueError):
        return None
    return max(0, value)


def calc_armor_class_defense_multiplier(armor_class: str | None) -> float:
    """Множитель defense-side value от класса брони."""
    normalized = normalize_armor_class(armor_class)
    if normalized == 'heavy':
        return 1.14
    if normalized == 'medium':
        return 1.06
    if normalized == 'light':
        return 0.96
    return 1.0


def calc_armor_class_dodge_bonus_percent(armor_class: str | None) -> float:
    """Бонус/штраф к уклонению в процентных пунктах."""
    normalized = normalize_armor_class(armor_class)
    if normalized == 'light':
        return 2.5
    if normalized == 'medium':
        return 0.5
    if normalized == 'heavy':
        return -2.0
    return 0.0


def calc_armor_class_tempo_bonus(armor_class: str | None) -> int:
    """Небольшой бонус/штраф к темпу/приоритету хода."""
    normalized = normalize_armor_class(armor_class)
    if normalized == 'light':
        return 3
    if normalized == 'medium':
        return 1
    if normalized == 'heavy':
        return -2
    return 0


def calc_armor_class_caster_bonus_percent(armor_class: str | None) -> float:
    """Небольшой caster/support бонус от класса брони."""
    normalized = normalize_armor_class(armor_class)
    if normalized == 'light':
        return 4.0
    if normalized == 'medium':
        return 1.0
    if normalized == 'heavy':
        return -2.0
    return 0.0


def calc_armor_class_support_bonus_percent(armor_class: str | None) -> float:
    """Небольшой support/heal бонус от класса брони."""
    normalized = normalize_armor_class(armor_class)
    if normalized == 'light':
        return 5.0
    if normalized == 'medium':
        return 1.5
    if normalized == 'heavy':
        return -1.0
    return 0.0


def calc_offhand_defense_multiplier(offhand_profile: str | None) -> float:
    """Множитель defense-side value от оффхенда."""
    normalized = normalize_offhand_profile(offhand_profile)
    if normalized == 'shield':
        return 1.12
    if normalized in ('focus', 'orb', 'tome'):
        return 1.02
    if normalized == 'censer':
        return 1.04
    return 1.0


def calc_offhand_tempo_bonus(offhand_profile: str | None) -> int:
    """Небольшой бонус/штраф к темпу от оффхенда."""
    normalized = normalize_offhand_profile(offhand_profile)
    if normalized == 'shield':
        return -1
    if normalized in ('focus', 'orb'):
        return 1
    return 0


def calc_offhand_caster_bonus_percent(offhand_profile: str | None) -> float:
    """Кастерский бонус от оффхенда."""
    normalized = normalize_offhand_profile(offhand_profile)
    if normalized == 'focus':
        return 8.0
    if normalized == 'orb':
        return 7.0
    if normalized == 'tome':
        return 6.0
    if normalized == 'censer':
        return 3.0
    if normalized == 'shield':
        return -2.0
    return 0.0


def calc_offhand_support_bonus_percent(offhand_profile: str | None) -> float:
    """Support/heal бонус от оффхенда."""
    normalized = normalize_offhand_profile(offhand_profile)
    if normalized == 'censer':
        return 14.0
    if normalized == 'focus':
        return 3.0
    if normalized == 'orb':
        return 2.0
    if normalized == 'tome':
        return 4.0
    return 0.0


def calc_encumbrance_tempo_penalty(encumbrance: int | float | None) -> int:
    """Лёгкий штраф к темпу от encumbrance."""
    value = normalize_encumbrance(encumbrance)
    if value is None:
        return 0
    return min(5, int(value * 0.5))


def calc_encumbrance_dodge_penalty_percent(encumbrance: int | float | None) -> float:
    """Лёгкий штраф к уклонению (процентные пункты)."""
    value = normalize_encumbrance(encumbrance)
    if value is None:
        return 0.0
    return min(3.5, round(value * 0.35, 2))


def calc_encumbrance_damage_penalty_percent(encumbrance: int | float | None) -> float:
    """Лёгкая модуляция offensive value от веса экипировки."""
    value = normalize_encumbrance(encumbrance)
    if value is None:
        return 0.0
    return min(6.0, round(value * 0.30, 2))

def calc_max_hp(vitality: int) -> int:
    """Максимальное HP от Живучести."""
    return BASE_STATS['hp'] + (vitality * 18)

def calc_max_mana(wisdom: int) -> int:
    """Максимальная мана от Мудрости."""
    return BASE_STATS['mana'] + (wisdom * 12)

# ────────────────────────────────────────
# 💪 СИЛА — физический урон ближнего боя
# ────────────────────────────────────────

def calc_strength_bonus(strength: int) -> int:
    """Плоский бонус к физ. урону ближнего боя."""
    return strength * 3

def calc_carry_weight(strength: int) -> int:
    """Максимальный переносимый вес инвентаря (в у.е.)."""
    return 20 + (strength * 5)

# ────────────────────────────────────────
# 🤸 ЛОВКОСТЬ — уклонение, % урон, приоритет
# ────────────────────────────────────────

def calc_dodge_chance(agility: int) -> float:
    """Шанс уклонения (0.0 — 1.0). С мягким спадом и cap 35%."""
    base = min(agility, 20) * 0.45
    if agility > 20:
        base += (agility - 20) * 0.20
    return round(min(base, DODGE_HARD_CAP_PERCENT) / 100, 4)

def calc_agility_damage_bonus(agility: int) -> float:
    """Небольшой общий % бонус к урону от Ловкости. Cap 9%."""
    return round(min(agility * 0.18, 9.0), 2)

def calc_physical_damage_reduction(agility: int) -> float:
    """Небольшое снижение входящего физ. урона (%)."""
    return round(min(agility * 0.24, PHYSICAL_AGILITY_MITIGATION_CAP_PERCENT), 2)

def calc_action_priority(
    agility: int,
    luck: int,
    *,
    armor_class: str | None = None,
    offhand_profile: str | None = None,
    encumbrance: int | float | None = None,
) -> int:
    """Приоритет хода в бою. Выше = ходишь первым."""
    base_priority = agility * 2 + luck
    base_priority += calc_armor_class_tempo_bonus(armor_class)
    base_priority += calc_offhand_tempo_bonus(offhand_profile)
    base_priority -= calc_encumbrance_tempo_penalty(encumbrance)
    return max(0, base_priority)

# ────────────────────────────────────────
# 🔮 ИНТУИЦИЯ — дальний бой, магия
# ────────────────────────────────────────

def calc_ranged_damage_bonus(intuition: int) -> int:
    """Плоский бонус к урону дальнего боя (как Сила для ближнего)."""
    return intuition * 3

def calc_magic_damage_percent(intuition: int) -> float:
    """% бонус к магическому урону от Интуиции. Cap 30%."""
    return round(min(intuition * 0.9, 30.0), 2)

def calc_intuition_melee_bonus(intuition: int) -> int:
    """Небольшой плоский бонус к ближнему урону от Интуиции."""
    return intuition * 1  # вдвое слабее Силы

# ────────────────────────────────────────
# ❤️ ЖИВУЧЕСТЬ — защита, сопротивление эффектам
# ────────────────────────────────────────

def calc_physical_defense(vitality: int) -> int:
    """Физическая defense rating — основной слой против physical."""
    return int(vitality * 2.2)

def calc_physical_effect_duration(base_duration: int, vitality: int) -> int:
    """Снижает длительность физ. эффектов (оглушение, слепота, кровотечение).
    Минимум 1 ход."""
    reduction = vitality * 0.05  # каждые 20 Живучести = -1 ход
    reduced = base_duration * (1 - reduction)
    return max(1, int(reduced))

# ────────────────────────────────────────
# 🧠 МУДРОСТЬ — мана, маг. защита, свет, хил
# ────────────────────────────────────────

def calc_magic_defense(wisdom: int) -> int:
    """Магическая defense rating — основной слой против magic/holy."""
    return int(wisdom * 2.2)

def calc_healing_bonus(wisdom: int) -> float:
    """% бонус к силе лечения."""
    return round(min((wisdom * 0.70) + (wisdom * 0.08), HEALING_SCHOOL_BONUS_CAP_PERCENT), 2)

def calc_light_damage_bonus(wisdom: int) -> float:
    """% бонус к урону светом."""
    return round(min((wisdom * 0.70) + (wisdom * 0.10), HOLY_SCHOOL_BONUS_CAP_PERCENT), 2)

def calc_magic_effect_duration(base_duration: int, wisdom: int) -> int:
    """Снижает длительность маг. эффектов (заморозка, страх, проклятие).
    Минимум 1 ход."""
    reduction = wisdom * 0.05
    reduced = base_duration * (1 - reduction)
    return max(1, int(reduced))

# ────────────────────────────────────────
# 🍀 УДАЧА — криты + бонус всем статам
# ────────────────────────────────────────

def calc_crit_chance(luck: int, agility: int = 0) -> float:
    """Шанс критического удара (0.0 — 1.0). Cap 35%."""
    raw = (luck * 0.35) + (agility * 0.05)
    return round(min(raw, CRIT_CHANCE_CAP_PERCENT) / 100, 4)

def calc_crit_reduction(luck: int) -> float:
    """Снижение шанса получить крит от врага (%). Cap 20%."""
    return round(min(luck * 0.2, CRIT_REDUCTION_CAP_PERCENT), 2)

def calc_luck_bonus(luck: int, stat_value: int) -> float:
    """Удача даёт небольшой % бонус к любому стату."""
    return round(stat_value * (luck * 0.002), 2)  # 0.2% за очко Удачи


def calc_defense_mitigation_percent(defense_rating: int, *, school: str = 'physical') -> float:
    """
    Нормализованный mitigation от defense rating с мягким убыванием.
    Используется для снижения входящего урона до hard-cap.
    """
    defense_rating = max(0, int(defense_rating))
    scaling = PHYSICAL_DEFENSE_SCALING if school == 'physical' else MAGIC_DEFENSE_SCALING
    if defense_rating <= 0:
        return 0.0
    raw_percent = (defense_rating / (defense_rating + scaling)) * 100
    return round(min(raw_percent, DEFENSE_MITIGATION_HARD_CAP_PERCENT), 2)


def combine_mitigation_percents(*layers: float, hard_cap: float = COMBINED_MITIGATION_HARD_CAP_PERCENT) -> float:
    """Комбинирует mitigation-слои мультипликативно и даёт единый capped результат."""
    remaining_multiplier = 1.0
    for layer in layers:
        normalized_layer = max(0.0, min(float(layer), 100.0))
        remaining_multiplier *= (1 - normalized_layer / 100)
    combined = (1 - remaining_multiplier) * 100
    return round(min(combined, hard_cap), 2)


def apply_mitigation_percent(incoming_damage: int, mitigation_percent: float) -> int:
    """Применяет единый mitigation-процент к входящему урону."""
    damage = max(1, int(incoming_damage))
    mitig = max(0.0, min(float(mitigation_percent), 100.0))
    return max(1, int(damage * (1 - mitig / 100)))

# ────────────────────────────────────────
# 🎯 ФИНАЛЬНЫЙ УРОН — сводная формула
# ────────────────────────────────────────

PROFILE_PRIMARY_SCALING = {
    'sword_1h': ('strength', 2.3),
    'sword_2h': ('strength', 2.6),
    'axe_2h': ('strength', 2.7),
    'daggers': ('agility', 2.2),
    'bow': ('agility', 2.3),
    'magic_staff': ('intuition', 2.75),
    'wand': ('intuition', 2.35),
    'holy_staff': ('wisdom', 2.55),
    'holy_rod': ('wisdom', 2.2),
    'tome': ('wisdom', 2.05),
    'unarmed': ('strength', 1.5),
}

PROFILE_SECONDARY_SCALING = {
    'sword_1h': ('vitality', 0.9),
    'sword_2h': ('agility', 0.8),
    'axe_2h': ('vitality', 1.0),
    'daggers': ('luck', 0.85),
    'bow': ('intuition', 1.1),
    'magic_staff': ('wisdom', 1.0),
    'wand': ('agility', 0.85),
    'holy_staff': ('intuition', 1.0),
    'holy_rod': ('vitality', 0.95),
    'tome': ('intuition', 1.0),
    'unarmed': ('vitality', 0.5),
}


def calc_profile_primary_offense_bonus(attacker_stats: dict, weapon_profile: str) -> int:
    """Основной offensive scaling от weapon_profile."""
    stat_name, multiplier = PROFILE_PRIMARY_SCALING.get(weapon_profile, ('strength', 2.0))
    return int(attacker_stats.get(stat_name, 0) * multiplier)


def calc_profile_secondary_offense_bonus(attacker_stats: dict, weapon_profile: str) -> int:
    """Вторичный offensive scaling от weapon_profile."""
    stat_name, multiplier = PROFILE_SECONDARY_SCALING.get(weapon_profile, ('vitality', 0.6))
    return int(attacker_stats.get(stat_name, 0) * multiplier)


def calc_school_damage_bonus_percent(attacker_stats: dict, damage_school: str) -> float:
    """School-aware бонус к урону в процентах."""
    if damage_school == 'magic':
        bonus = (attacker_stats.get('intuition', 0) * 0.55) + (attacker_stats.get('wisdom', 0) * 0.20)
        return round(min(bonus, MAGIC_SCHOOL_BONUS_CAP_PERCENT), 2)
    if damage_school == 'holy':
        bonus = (attacker_stats.get('wisdom', 0) * 0.60) + (attacker_stats.get('intuition', 0) * 0.15)
        return round(min(bonus, HOLY_SCHOOL_BONUS_CAP_PERCENT), 2)
    return 0.0


def calc_crit_multiplier(luck: int = 0) -> float:
    """Крит множитель. Для нормализации оставляем фиксированным (x2)."""
    return CRIT_DAMAGE_MULTIPLIER

def calc_final_damage(
    base_weapon_damage: int,
    attacker_stats: dict,
    weapon_type: str,  # 'melee', 'ranged', 'magic', 'light'
    is_crit: bool = False,
    weapon_profile: str | None = None,
    damage_school: str | None = None,
    armor_class: str | None = None,
    offhand_profile: str | None = None,
    encumbrance: int | float | None = None,
) -> int:
    """
    Считает итоговый урон с учётом всех статов.
    attacker_stats — словарь со статами атакующего.
    """
    s = attacker_stats
    normalized_profile = normalize_weapon_profile(weapon_profile, weapon_type)
    normalized_school = normalize_damage_school(
        damage_school,
        weapon_profile=normalized_profile,
        weapon_type=weapon_type,
    )
    damage = max(1, base_weapon_damage)

    primary_bonus = calc_profile_primary_offense_bonus(s, normalized_profile)
    secondary_bonus = calc_profile_secondary_offense_bonus(s, normalized_profile)
    damage += primary_bonus + secondary_bonus

    school_bonus = calc_school_damage_bonus_percent(s, normalized_school)
    damage *= (1 + school_bonus / 100)

    semantic_bonus = 0.0
    if normalized_school in ('magic', 'holy'):
        semantic_bonus += calc_armor_class_caster_bonus_percent(armor_class)
        semantic_bonus += calc_offhand_caster_bonus_percent(offhand_profile)
    damage *= (1 + semantic_bonus / 100)

    # Бонус от Ловкости (% ко всему)
    agi_bonus = calc_agility_damage_bonus(s['agility'])
    damage *= (1 + agi_bonus / 100)

    encumbrance_penalty = calc_encumbrance_damage_penalty_percent(encumbrance)
    damage *= (1 - encumbrance_penalty / 100)

    # Крит — мягко масштабируемый множитель
    if is_crit:
        damage *= calc_crit_multiplier(s.get('luck', 0))

    return max(1, int(damage))  # минимум 1 урона всегда
