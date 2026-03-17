# ============================================================
# i18n.py — движок переводов
# ============================================================

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SUPPORTED_LANGS = {
    'ru': '🇷🇺 Русский',
    'en': '🇬🇧 English',
    'es': '🇪🇸 Español',
}

DEFAULT_LANG = 'ru'

# Кэш загруженных языков
_cache = {}

def _load_lang(lang: str) -> dict:
    if lang in _cache:
        return _cache[lang]
    try:
        if lang == 'ru':
            from locales.ru import STRINGS
        elif lang == 'en':
            from locales.en import STRINGS
        elif lang == 'es':
            from locales.es import STRINGS
        else:
            from locales.ru import STRINGS
        _cache[lang] = STRINGS
        return STRINGS
    except ImportError:
        from locales.ru import STRINGS
        _cache['ru'] = STRINGS
        return STRINGS

def t(key: str, lang: str = 'ru', **kwargs) -> str:
    """
    Получить перевод по ключу.
    Ключи вложенные через точку: t('battle.attack_hit', lang, damage=24)
    """
    strings = _load_lang(lang)

    # Ищем по вложенному ключу
    parts = key.split('.')
    value = strings
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = None
        if value is None:
            break

    # Если не найдено — берём из русского
    if value is None and lang != 'ru':
        value = t(key, 'ru', **kwargs)
    elif value is None:
        return f'[{key}]'  # ключ не найден

    # Подставляем переменные
    if kwargs and isinstance(value, str):
        try:
            value = value.format(**kwargs)
        except (KeyError, ValueError):
            pass

    return value

def get_player_lang(telegram_id: int) -> str:
    """Получить язык игрока из БД."""
    try:
        from database import get_connection
        conn = get_connection()
        row  = conn.execute(
            'SELECT lang FROM players WHERE telegram_id=?', (telegram_id,)
        ).fetchone()
        conn.close()
        return row['lang'] if row and row['lang'] else DEFAULT_LANG
    except Exception:
        return DEFAULT_LANG

def set_player_lang(telegram_id: int, lang: str):
    """Установить язык игрока."""
    from database import get_connection
    conn = get_connection()
    conn.execute(
        'UPDATE players SET lang=? WHERE telegram_id=?', (lang, telegram_id)
    )
    conn.commit()
    conn.close()

def get_item_name(item_id: str, lang: str) -> str:
    """Получить локализованное название предмета."""
    try:
        if lang == 'ru':
            from locales.items_ru import ITEM_NAMES
        elif lang == 'en':
            from locales.items_en import ITEM_NAMES
        elif lang == 'es':
            from locales.items_es import ITEM_NAMES
        else:
            from locales.items_ru import ITEM_NAMES
        name = ITEM_NAMES.get(item_id)
        if name:
            return name
    except ImportError:
        pass
    # fallback — берём из items_data
    from game.items_data import get_item
    item = get_item(item_id)
    return item['name'] if item else item_id

def get_location_name(location_id: str, lang: str) -> str:
    try:
        if lang == 'ru': from locales.locations_ru import LOCATION_NAMES
        elif lang == 'en': from locales.locations_en import LOCATION_NAMES
        elif lang == 'es': from locales.locations_es import LOCATION_NAMES
        else: from locales.locations_ru import LOCATION_NAMES
        entry = LOCATION_NAMES.get(location_id, {})
        return entry.get('name') or _fallback_location(location_id, 'name')
    except ImportError:
        return _fallback_location(location_id, 'name')

def get_location_desc(location_id: str, lang: str) -> str:
    try:
        if lang == 'ru': from locales.locations_ru import LOCATION_NAMES
        elif lang == 'en': from locales.locations_en import LOCATION_NAMES
        elif lang == 'es': from locales.locations_es import LOCATION_NAMES
        else: from locales.locations_ru import LOCATION_NAMES
        entry = LOCATION_NAMES.get(location_id, {})
        return entry.get('description') or _fallback_location(location_id, 'description')
    except ImportError:
        return _fallback_location(location_id, 'description')

def _fallback_location(location_id: str, field: str) -> str:
    from game.locations import LOCATIONS
    loc = LOCATIONS.get(location_id, {})
    return loc.get(field, location_id)

def get_mob_name(mob_id: str, lang: str) -> str:
    try:
        if lang == 'ru': from locales.mobs_ru import MOB_NAMES
        elif lang == 'en': from locales.mobs_en import MOB_NAMES
        elif lang == 'es': from locales.mobs_es import MOB_NAMES
        else: from locales.mobs_ru import MOB_NAMES
        return MOB_NAMES.get(mob_id) or _fallback_mob(mob_id)
    except ImportError:
        return _fallback_mob(mob_id)

def _fallback_mob(mob_id: str) -> str:
    from game.mobs import get_mob
    mob = get_mob(mob_id)
    return mob['name'] if mob else mob_id

def get_skill_name(skill_id: str, lang: str) -> str:
    try:
        if lang == 'ru': from locales.skills_ru import SKILL_NAMES
        elif lang == 'en': from locales.skills_en import SKILL_NAMES
        elif lang == 'es': from locales.skills_es import SKILL_NAMES
        else: from locales.skills_ru import SKILL_NAMES
        entry = SKILL_NAMES.get(skill_id, {})
        return entry.get('name') or _fallback_skill(skill_id, 'name')
    except ImportError:
        return _fallback_skill(skill_id, 'name')

def get_skill_desc(skill_id: str, lang: str) -> str:
    try:
        if lang == 'ru': from locales.skills_ru import SKILL_NAMES
        elif lang == 'en': from locales.skills_en import SKILL_NAMES
        elif lang == 'es': from locales.skills_es import SKILL_NAMES
        else: from locales.skills_ru import SKILL_NAMES
        entry = SKILL_NAMES.get(skill_id, {})
        return entry.get('description') or _fallback_skill(skill_id, 'description')
    except ImportError:
        return _fallback_skill(skill_id, 'description')

def _fallback_skill(skill_id: str, field: str) -> str:
    from game.skills import get_skill
    skill = get_skill(skill_id)
    return skill.get(field, skill_id) if skill else skill_id

print('✅ game/i18n.py создан!')