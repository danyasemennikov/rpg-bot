# ============================================================
# balance.py — все игровые формулы в одном месте
# Если хочешь изменить баланс — меняй только этот файл
# ============================================================

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

# ────────────────────────────────────────
# COMBAT SEMANTICS (Stage 1 hooks)
# ────────────────────────────────────────

VALID_WEAPON_PROFILES = {
    'sword_1h', 'sword_2h', 'axe_2h', 'daggers', 'bow',
    'magic_staff', 'holy_staff', 'wand', 'holy_rod', 'unarmed',
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
    return round(min(base, 35.0) / 100, 4)

def calc_agility_damage_bonus(agility: int) -> float:
    """Небольшой общий % бонус к урону от Ловкости. Cap 9%."""
    return round(min(agility * 0.18, 9.0), 2)

def calc_physical_damage_reduction(agility: int) -> float:
    """Небольшое снижение входящего физ. урона (%)."""
    return round(min(agility * 0.2, 10.0), 2)  # cap 10%

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
    """Физическая защита — снижает входящий физ. урон."""
    return vitality * 2

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
    """Магическая защита — снижает входящий маг. урон."""
    return wisdom * 2

def calc_healing_bonus(wisdom: int) -> float:
    """% бонус к силе лечения."""
    return round(wisdom * 0.8, 2)

def calc_light_damage_bonus(wisdom: int) -> float:
    """% бонус к урону светом."""
    return round(wisdom * 1.0, 2)

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
    return round(min(raw, 35.0) / 100, 4)

def calc_crit_reduction(luck: int) -> float:
    """Снижение шанса получить крит от врага (%). Cap 20%."""
    return round(min(luck * 0.2, 20.0), 2)

def calc_luck_bonus(luck: int, stat_value: int) -> float:
    """Удача даёт небольшой % бонус к любому стату."""
    return round(stat_value * (luck * 0.002), 2)  # 0.2% за очко Удачи

# ────────────────────────────────────────
# 🎯 ФИНАЛЬНЫЙ УРОН — сводная формула
# ────────────────────────────────────────

PROFILE_PRIMARY_SCALING = {
    'sword_1h': ('strength', 2.2),
    'sword_2h': ('strength', 2.6),
    'axe_2h': ('strength', 2.8),
    'daggers': ('agility', 2.3),
    'bow': ('agility', 2.4),
    'magic_staff': ('intuition', 2.7),
    'wand': ('intuition', 2.3),
    'holy_staff': ('wisdom', 2.6),
    'holy_rod': ('wisdom', 2.4),
    'unarmed': ('strength', 1.5),
}

PROFILE_SECONDARY_SCALING = {
    'sword_1h': ('vitality', 0.9),
    'sword_2h': ('agility', 0.9),
    'axe_2h': ('vitality', 1.1),
    'daggers': ('luck', 0.8),
    'bow': ('intuition', 1.0),
    'magic_staff': ('wisdom', 1.0),
    'wand': ('agility', 0.9),
    'holy_staff': ('intuition', 1.0),
    'holy_rod': ('vitality', 0.9),
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
        return round(min(bonus, 28.0), 2)
    if damage_school == 'holy':
        bonus = (attacker_stats.get('wisdom', 0) * 0.60) + (attacker_stats.get('intuition', 0) * 0.15)
        return round(min(bonus, 30.0), 2)
    return 0.0


def calc_crit_multiplier(luck: int = 0) -> float:
    """Крит множитель. На этом проходе фиксирован и не ниже x2."""
    return 2.0

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

print('✅ balance.py создан!')
