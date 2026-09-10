"""Persisted UI intents and shared validation for peaceful economic actions.

Call consume_action inside the same IMMEDIATE transaction as the mutation.
An exception rolls back both the receipt and its items/XP/gold.
"""

from __future__ import annotations

import secrets
import time

from database import get_connection
from game.locations import get_location, resolve_location_id


class ActionRejected(ValueError):
    pass


def ensure_action_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS player_ui_actions (
        token TEXT PRIMARY KEY,
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        kind TEXT NOT NULL,
        payload TEXT NOT NULL,
        location_id TEXT NOT NULL,
        travel_revision INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        used INTEGER NOT NULL DEFAULT 0
    )''')
    conn.execute('''CREATE INDEX IF NOT EXISTS idx_ui_actions_player
        ON player_ui_actions(player_id, kind)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS player_action_receipts (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        request_id TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, request_id)
    )''')


def peaceful_player(conn, player_id: int, *, service: str | None = None,
                    location_id: str | None = None) -> dict:
    """Read current authority under the caller's write lock; never trust UI state."""
    from game.pvp_live import is_player_busy_with_live_pvp

    row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (player_id,)).fetchone()
    if not row:
        raise ActionRejected('no_player')
    player = dict(row)
    if player['in_battle'] or is_player_busy_with_live_pvp(player_id, conn=conn):
        raise ActionRejected('in_battle')
    actual = resolve_location_id(player['location_id'])
    if location_id is not None and actual != resolve_location_id(location_id):
        raise ActionRejected('stale_action')
    if service and service not in (get_location(actual) or {}).get('services', []):
        raise ActionRejected('wrong_location')
    return player


def issue_actions(player_id: int, kind: str, payloads: list[str]) -> dict[str, str]:
    """Replace this menu's pending intents; consumed tokens are never reusable."""
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT location_id, travel_revision FROM players WHERE telegram_id=?',
                           (player_id,)).fetchone()
        if not row:
            return {}
        conn.execute('DELETE FROM player_ui_actions WHERE player_id=? AND kind=?', (player_id, kind))
        tokens = {}
        for payload in payloads:
            token = secrets.token_hex(8)
            conn.execute('''INSERT INTO player_ui_actions
                (token, player_id, kind, payload, location_id, travel_revision, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                         (token, player_id, kind, payload, resolve_location_id(row['location_id']),
                          row['travel_revision'], int(time.time()) + 900))
            tokens[payload] = token
        conn.commit()
        return tokens
    finally:
        conn.close()


def consume_action(conn, player_id: int, kind: str, token: str, *, payload: str | None = None) -> str:
    row = conn.execute('''SELECT a.* FROM player_ui_actions a JOIN players p
        ON p.telegram_id=a.player_id WHERE a.token=? AND a.player_id=? AND a.kind=?
        AND a.used=0 AND a.expires_at>=? AND a.travel_revision=p.travel_revision''',
                       (token, player_id, kind, int(time.time()))).fetchone()
    if not row or (payload is not None and row['payload'] != payload):
        raise ActionRejected('stale_action')
    player = conn.execute('SELECT location_id FROM players WHERE telegram_id=?', (player_id,)).fetchone()
    if resolve_location_id(player['location_id']) != row['location_id']:
        raise ActionRejected('stale_action')
    conn.execute('UPDATE player_ui_actions SET used=1 WHERE token=?', (token,))
    return str(row['payload'])


def record_request(conn, player_id: int, request_id: str) -> bool:
    return conn.execute('''INSERT OR IGNORE INTO player_action_receipts(player_id, request_id)
        VALUES (?, ?)''', (player_id, request_id)).rowcount == 1


def require_item_delivery(result: dict, quantity: int) -> None:
    if int(result.get('stackable_added', 0)) + int(result.get('gear_instances_created', 0)) != quantity:
        raise RuntimeError('item_delivery_mismatch')
