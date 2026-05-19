# ============================================================
# contextual_keyboard.py — persistent lower menu helpers
# ============================================================

from __future__ import annotations

from telegram import ReplyKeyboardMarkup

from game.i18n import SUPPORTED_LANGS, get_location_name, t
from game.gathering_foundation import build_location_gather_source_profiles
from game.locations import get_location, get_location_neighbors, resolve_location_id

LOWER_TRAVEL_PREFIX = '🧭 '


def _baseline_keyboard_rows(lang: str) -> list[list[str]]:
    return [
        [t('keyboard.location', lang), t('keyboard.map', lang)],
        [t('keyboard.inventory', lang), t('keyboard.profile', lang)],
        [t('keyboard.skills', lang), t('keyboard.stats', lang)],
        [t('keyboard.settings', lang), t('keyboard.help', lang)],
    ]


def build_lower_travel_label(location_id: str, lang: str) -> str:
    """Return the stable text sent by a lower-menu travel button."""
    return LOWER_TRAVEL_PREFIX + get_location_name(location_id, lang)


def get_contextual_travel_targets(current_location_id: str | None) -> list[str]:
    """Return valid ordinary neighbor ids for the current canonical location."""
    canonical_current_id = resolve_location_id(str(current_location_id or ''))
    targets: list[str] = []
    seen: set[str] = set()
    for neighbor_id in get_location_neighbors(canonical_current_id):
        canonical_neighbor_id = resolve_location_id(str(neighbor_id or ''))
        if canonical_neighbor_id in seen:
            continue
        if not get_location(canonical_neighbor_id):
            continue
        seen.add(canonical_neighbor_id)
        targets.append(canonical_neighbor_id)
    return targets




_GATHER_PROFESSION_ORDER = (
    ('herbalism', 'keyboard.gather_herbalism'),
    ('woodcutting', 'keyboard.gather_woodcutting'),
    ('mining', 'keyboard.gather_mining'),
    ('fishing', 'keyboard.gather_fishing'),
)
_SERVICE_ORDER = (
    ('shop', 'keyboard.service_shop'),
    ('inn', 'keyboard.service_inn'),
    ('quest_board', 'keyboard.service_quest_board'),
    ('craftsmen_guild', 'keyboard.service_craftsmen_guild'),
)


def _build_contextual_gather_rows(current_location_id: str | None, lang: str) -> list[list[str]]:
    canonical_location_id = resolve_location_id(str(current_location_id or ''))
    profiles = build_location_gather_source_profiles(canonical_location_id)
    available = {profile.profession_key for profile in profiles}
    labels = [t(locale_key, lang) for profession, locale_key in _GATHER_PROFESSION_ORDER if profession in available]
    rows: list[list[str]] = []
    for index in range(0, len(labels), 2):
        rows.append(labels[index:index + 2])
    return rows


def _resolve_gather_profession_from_label(text: str, preferred_lang: str) -> str | None:
    languages = [preferred_lang] + [lang for lang in SUPPORTED_LANGS if lang != preferred_lang]
    for lang in languages:
        for profession, locale_key in _GATHER_PROFESSION_ORDER:
            if text == t(locale_key, lang):
                return profession
    return None


def _can_open_inn_in_location(location: dict | None) -> bool:
    if not location:
        return False
    services = location.get('services', []) or []
    return bool(location.get('safe')) and ('inn' in services)


def _build_contextual_service_rows(current_location_id: str | None, lang: str) -> list[list[str]]:
    location = get_location(resolve_location_id(str(current_location_id or '')))
    if not location:
        return []
    services = {str(service_id) for service_id in (location.get('services', []) or [])}
    labels: list[str] = []
    for service_id, locale_key in _SERVICE_ORDER:
        if service_id == 'inn':
            if not _can_open_inn_in_location(location):
                continue
        elif service_id not in services:
            continue
        labels.append(t(locale_key, lang))
    rows: list[list[str]] = []
    for label in labels:
        rows.append([label])
    return rows


def _resolve_service_from_label(text: str, preferred_lang: str) -> str | None:
    languages = [preferred_lang] + [lang for lang in SUPPORTED_LANGS if lang != preferred_lang]
    for lang in languages:
        for service_id, locale_key in _SERVICE_ORDER:
            if text == t(locale_key, lang):
                return service_id
    return None


def looks_like_lower_gather_button(text: str) -> bool:
    normalized_text = str(text or '').strip()
    if not normalized_text:
        return False
    return _resolve_gather_profession_from_label(normalized_text, 'ru') is not None


def resolve_lower_gather_profession_button(text: str, player: dict, lang: str) -> str | None:
    normalized_text = str(text or '').strip()
    if not normalized_text:
        return None
    matched_profession = _resolve_gather_profession_from_label(normalized_text, lang)
    if matched_profession is None:
        return None
    current_profiles = build_location_gather_source_profiles(resolve_location_id(str(player.get('location_id') or '')))
    if any(profile.profession_key == matched_profession for profile in current_profiles):
        return matched_profession
    return ''

def build_contextual_main_keyboard(player: dict | None = None, lang: str = 'ru') -> ReplyKeyboardMarkup:
    """Build the persistent lower menu, with contextual travel rows first."""
    rows: list[list[str]] = []
    if player:
        for target_id in get_contextual_travel_targets(player.get('location_id')):
            rows.append([build_lower_travel_label(target_id, lang)])
        rows.extend(_build_contextual_gather_rows(player.get('location_id'), lang))
        rows.extend(_build_contextual_service_rows(player.get('location_id'), lang))
    rows.extend(_baseline_keyboard_rows(lang))
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def resolve_lower_travel_button(text: str, player: dict, lang: str) -> str | None:
    """Map lower-menu travel text to a current neighbor id, or None if stale."""
    normalized_text = str(text or '').strip()
    if not normalized_text.startswith(LOWER_TRAVEL_PREFIX):
        return None
    for target_id in get_contextual_travel_targets(player.get('location_id')):
        if normalized_text == build_lower_travel_label(target_id, lang):
            return target_id
    return None


def looks_like_lower_travel_button(text: str) -> bool:
    return str(text or '').strip().startswith(LOWER_TRAVEL_PREFIX)


def looks_like_lower_service_button(text: str) -> bool:
    normalized_text = str(text or '').strip()
    if not normalized_text:
        return False
    return _resolve_service_from_label(normalized_text, 'ru') is not None


def resolve_lower_service_button(text: str, player: dict, lang: str) -> str | None:
    normalized_text = str(text or '').strip()
    if not normalized_text:
        return None
    matched_service = _resolve_service_from_label(normalized_text, lang)
    if matched_service is None:
        return None
    location = get_location(resolve_location_id(str(player.get('location_id') or '')))
    services = {str(service_id) for service_id in ((location or {}).get('services', []) or [])}
    if matched_service == 'inn':
        return 'inn' if _can_open_inn_in_location(location) else ''
    if matched_service in services:
        return matched_service
    return ''
