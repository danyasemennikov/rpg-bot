"""Additive storage for the Aster–Elmor chapter; owns no player data migration."""

from game.action_receipts import ensure_action_schema


def ensure_alpha_schema(conn):
    ensure_action_schema(conn)
    conn.execute('''CREATE TABLE IF NOT EXISTS player_starter_kits (
        player_id INTEGER PRIMARY KEY REFERENCES players(telegram_id),
        weapon_id TEXT NOT NULL REFERENCES items(item_id),
        claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS player_crafting_professions (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        profession_key TEXT NOT NULL CHECK (profession_key IN
            ('alchemy', 'cooking', 'medium_armor')),
        level INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 20),
        exp INTEGER NOT NULL DEFAULT 0 CHECK (exp >= 0),
        PRIMARY KEY (player_id, profession_key)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS player_contract_history (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        contract_key TEXT NOT NULL,
        claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, contract_key)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS player_contract_objectives (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        contract_key TEXT NOT NULL,
        objective_key TEXT NOT NULL,
        progress INTEGER NOT NULL DEFAULT 0 CHECK (progress >= 0),
        PRIMARY KEY (player_id, contract_key, objective_key)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS pve_harvest_claims (
        encounter_id TEXT NOT NULL,
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        item_id TEXT NOT NULL REFERENCES items(item_id),
        claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (encounter_id, player_id)
    )''')


def ensure_crafting_professions(conn, player_id: int):
    conn.executemany('''INSERT OR IGNORE INTO player_crafting_professions
        (player_id, profession_key) VALUES (?, ?)''',
                     ((player_id, key) for key in ('alchemy', 'cooking', 'medium_armor')))
