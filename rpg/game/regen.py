from datetime import datetime, timezone
from database import get_connection

REGEN_RATES = {
    'capital_city': {'hp': 5.0, 'mana': 8.0},
    'village': {'hp': 5.0, 'mana': 8.0},
    'hub_westwild': {'hp': 5.0, 'mana': 8.0},
    'hub_frostspine': {'hp': 5.0, 'mana': 8.0},
    'hub_ashen_ruins': {'hp': 5.0, 'mana': 8.0},
    'hub_sunscar': {'hp': 5.0, 'mana': 8.0},
    'hub_mireveil': {'hp': 5.0, 'mana': 8.0},
    'default': {'hp': 1.0, 'mana': 2.0},
}

MAX_OFFLINE_MINUTES = 120

def apply_regen(player: dict) -> dict:
    """Считает реген с момента last_seen и применяет."""
    if player.get('in_battle'):
        return {'hp_gained': 0, 'mana_gained': 0}

    now = datetime.now(timezone.utc)
    last_seen_raw = player.get('last_seen')

    try:
        if isinstance(last_seen_raw, str):
            last_seen = datetime.fromisoformat(
                last_seen_raw.split('.')[0]
            ).replace(tzinfo=timezone.utc)
        else:
            last_seen = now
    except:
        last_seen = now

    minutes = min((now - last_seen).total_seconds() / 60, MAX_OFFLINE_MINUTES)
    if minutes < 1:
        return {'hp_gained': 0, 'mana_gained': 0}

    location = player.get('location_id', 'default')
    rates    = REGEN_RATES.get(location, REGEN_RATES['default'])

    hp_gained   = min(
        int(player['max_hp']   * (rates['hp']   / 100) * minutes),
        player['max_hp']   - player['hp']
    )
    mana_gained = min(
        int(player['max_mana'] * (rates['mana'] / 100) * minutes),
        player['max_mana'] - player['mana']
    )
    hp_gained   = max(0, hp_gained)
    mana_gained = max(0, mana_gained)

    conn = get_connection()
    conn.execute(
        '''UPDATE players SET hp=?, mana=?, last_seen=?
           WHERE telegram_id=?''',
        (
            player['hp'] + hp_gained,
            player['mana'] + mana_gained,
            now.strftime('%Y-%m-%d %H:%M:%S'),
            player['telegram_id']
        )
    )
    conn.commit()
    conn.close()

    return {
        'hp_gained':   hp_gained,
        'mana_gained': mana_gained,
        'minutes':     int(minutes),
    }
