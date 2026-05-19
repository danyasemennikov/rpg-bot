# ============================================================
# contextual_keyboard.py — persistent lower menu helpers
# ============================================================

from __future__ import annotations

from telegram import ReplyKeyboardMarkup

from game.i18n import get_location_name, t
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


def build_contextual_main_keyboard(player: dict | None = None, lang: str = 'ru') -> ReplyKeyboardMarkup:
    """Build the persistent lower menu, with contextual travel rows first."""
    rows: list[list[str]] = []
    if player:
        for target_id in get_contextual_travel_targets(player.get('location_id')):
            rows.append([build_lower_travel_label(target_id, lang)])
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
