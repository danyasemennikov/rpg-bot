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
    """Шанс уклонения (0.0 — 1.0). Мягкий cap на 40%."""
    raw = agility * 0.8
    return round(min(raw, 40.0) / 100, 4)

def calc_agility_damage_bonus(agility: int) -> float:
    """% бонус к итоговому урону от Ловкости."""
    return round(agility * 0.5, 2)  # +0.5% за каждое очко

def calc_physical_damage_reduction(agility: int) -> float:
    """Небольшое снижение входящего физ. урона (%)."""
    return round(min(agility * 0.2, 10.0), 2)  # cap 10%

def calc_action_priority(agility: int, luck: int) -> int:
    """Приоритет хода в бою. Выше = ходишь первым."""
    return agility * 2 + luck

# ────────────────────────────────────────
# 🔮 ИНТУИЦИЯ — дальний бой, магия
# ────────────────────────────────────────

def calc_ranged_damage_bonus(intuition: int) -> int:
    """Плоский бонус к урону дальнего боя (как Сила для ближнего)."""
    return intuition * 3

def calc_magic_damage_percent(intuition: int) -> float:
    """% бонус к магическому урону от Интуиции."""
    return round(intuition * 5, 2)

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
    """Шанс критического удара (0.0 — 1.0). Cap 60%."""
    raw = (luck * 0.6) + (agility * 0.1)
    return round(min(raw, 60.0) / 100, 4)

def calc_crit_reduction(luck: int) -> float:
    """Снижение шанса получить крит от врага (%). Cap 30%."""
    return round(min(luck * 0.3, 30.0), 2)

def calc_luck_bonus(luck: int, stat_value: int) -> float:
    """Удача даёт небольшой % бонус к любому стату."""
    return round(stat_value * (luck * 0.002), 2)  # 0.2% за очко Удачи

# ────────────────────────────────────────
# 🎯 ФИНАЛЬНЫЙ УРОН — сводная формула
# ────────────────────────────────────────

def calc_final_damage(
    base_weapon_damage: int,
    attacker_stats: dict,
    weapon_type: str,  # 'melee', 'ranged', 'magic', 'light'
    is_crit: bool = False
) -> int:
    """
    Считает итоговый урон с учётом всех статов.
    attacker_stats — словарь со статами атакующего.
    """
    s = attacker_stats
    damage = base_weapon_damage

    if weapon_type == 'melee':
        damage += calc_strength_bonus(s['strength'])
        damage += calc_intuition_melee_bonus(s['intuition'])

    elif weapon_type == 'ranged':
        damage += calc_ranged_damage_bonus(s['intuition'])

    elif weapon_type == 'magic':
        bonus_pct = calc_magic_damage_percent(s['intuition'])
        damage *= (1 + bonus_pct / 100)

    elif weapon_type == 'light':
        bonus_pct = calc_light_damage_bonus(s['wisdom'])
        damage *= (1 + bonus_pct / 100)

    # Бонус от Ловкости (% ко всему)
    agi_bonus = calc_agility_damage_bonus(s['agility'])
    damage *= (1 + agi_bonus / 100)

    # Крит — множитель 1.8x (не промахивается)
    if is_crit:
        damage *= 2.5

    return max(1, int(damage))  # минимум 1 урона всегда

print('✅ balance.py создан!')
