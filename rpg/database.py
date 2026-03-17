# ============================================================
# database.py — вся работа с базой данных
# ============================================================

import sqlite3
import os

import os
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'game.db')

def get_connection():
    """Подключение к БД."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # результаты как словари
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Создаёт все таблицы если их нет."""
    conn = get_connection()
    # Добавляем last_seen если колонки нет
    try:
        conn.execute(
            'ALTER TABLE players ADD COLUMN last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        )
        conn.commit()
    except:
        pass
    c = conn.cursor()

    # ────────────────────────────────────────
    # ИГРОКИ
    # ────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS players (
            telegram_id     INTEGER PRIMARY KEY,
            username        TEXT,
            name            TEXT NOT NULL,
            level           INTEGER DEFAULT 1,
            exp             INTEGER DEFAULT 0,
            stat_points     INTEGER DEFAULT 0,
            lang TEXT DEFAULT 'ru',

            -- Базовые статы
            strength        INTEGER DEFAULT 1,
            agility         INTEGER DEFAULT 1,
            intuition       INTEGER DEFAULT 1,
            vitality        INTEGER DEFAULT 1,
            wisdom          INTEGER DEFAULT 1,
            luck            INTEGER DEFAULT 1,

            -- Текущее состояние
            hp              INTEGER DEFAULT 118,
            max_hp          INTEGER DEFAULT 118,
            mana            INTEGER DEFAULT 62,
            max_mana        INTEGER DEFAULT 62,

            -- Экономика
            gold            INTEGER DEFAULT 50,
            carry_weight    INTEGER DEFAULT 0,

            -- Локация
            location_id     TEXT DEFAULT 'village',

            -- Состояние боя (NULL = не в бою)
            in_battle       INTEGER DEFAULT 0,

            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ────────────────────────────────────────
    # СПРАВОЧНИК ПРЕДМЕТОВ
    # ────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS items (
            item_id         TEXT PRIMARY KEY,   -- 'iron_sword', 'health_potion'
            name            TEXT NOT NULL,
            description     TEXT,
            item_type       TEXT NOT NULL,      -- 'weapon', 'armor', 'potion', 'material', 'quest'
            weapon_type     TEXT,               -- 'melee', 'ranged', 'magic', 'light' (только для оружия)
            rarity          TEXT DEFAULT 'common', -- common/uncommon/rare/epic/legendary

            -- Характеристики предмета
            damage_min      INTEGER DEFAULT 0,
            damage_max      INTEGER DEFAULT 0,
            defense         INTEGER DEFAULT 0,
            weight          INTEGER DEFAULT 1,

            -- Требования
            req_level       INTEGER DEFAULT 1,
            req_strength    INTEGER DEFAULT 0,
            req_agility     INTEGER DEFAULT 0,
            req_intuition   INTEGER DEFAULT 0,
            req_wisdom      INTEGER DEFAULT 0,

            -- Экономика
            buy_price       INTEGER DEFAULT 0,  -- цена в магазине (0 = нельзя купить)
            sell_price      INTEGER DEFAULT 0,

            -- Способности (JSON список skill_id)
            skills_json     TEXT DEFAULT '[]',

            -- Бонусы к статам (JSON)
            stat_bonus_json TEXT DEFAULT '{}'
        )
    ''')

    # ────────────────────────────────────────
    # ИНВЕНТАРЬ ИГРОКА
    # ────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id     INTEGER NOT NULL,
            item_id         TEXT NOT NULL,
            quantity        INTEGER DEFAULT 1,

            -- Заточка (только для оружия/брони)
            enhance_level   INTEGER DEFAULT 0,  -- +0 до +15

            -- Износ (опционально на будущее)
            durability      INTEGER DEFAULT 100,

            FOREIGN KEY (telegram_id) REFERENCES players(telegram_id),
            FOREIGN KEY (item_id) REFERENCES items(item_id)
        )
    ''')

    # ────────────────────────────────────────
    # ЭКИПИРОВКА ИГРОКА
    # ────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS equipment (
            telegram_id     INTEGER PRIMARY KEY,

            -- Слоты экипировки (хранится inventory.id)
            weapon          INTEGER,    -- главное оружие
            offhand         INTEGER,    -- щит или второе оружие
            helmet          INTEGER,
            chest           INTEGER,
            legs            INTEGER,
            boots           INTEGER,
            gloves          INTEGER,
            ring1           INTEGER,
            ring2           INTEGER,
            amulet          INTEGER,

            FOREIGN KEY (telegram_id) REFERENCES players(telegram_id)
        )
    ''')

    # ────────────────────────────────────────
    # КВЕСТЫ ИГРОКА
    # ────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS player_quests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id     INTEGER NOT NULL,
            quest_id        TEXT NOT NULL,
            status          TEXT DEFAULT 'active',  -- active/completed/failed
            progress_json   TEXT DEFAULT '{}',       -- {"kills": 3, "needed": 10}
            started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at    TIMESTAMP,

            FOREIGN KEY (telegram_id) REFERENCES players(telegram_id)
        )
    ''')

    # ────────────────────────────────────────
    # КУЛДАУНЫ СПОСОБНОСТЕЙ
    # ────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS skill_cooldowns (
            telegram_id   INTEGER NOT NULL,
            skill_id      TEXT NOT NULL,
            turns_left    INTEGER DEFAULT 0,
            PRIMARY KEY (telegram_id, skill_id),
            FOREIGN KEY (telegram_id) REFERENCES players(telegram_id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS weapon_mastery (
            telegram_id   INTEGER NOT NULL,
            weapon_id     TEXT NOT NULL,
            level         INTEGER DEFAULT 1,
            exp           INTEGER DEFAULT 0,
            skill_points  INTEGER DEFAULT 1,
            PRIMARY KEY (telegram_id, weapon_id),
            FOREIGN KEY (telegram_id) REFERENCES players(telegram_id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS player_skills (
            telegram_id   INTEGER NOT NULL,
            skill_id      TEXT NOT NULL,
            level         INTEGER DEFAULT 1,
            PRIMARY KEY (telegram_id, skill_id),
            FOREIGN KEY (telegram_id) REFERENCES players(telegram_id)
        )
    ''')

    # ────────────────────────────────────────
    # АКТИВНЫЕ ЭФФЕКТЫ (яды, баффы, дебаффы)
    # ────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS active_effects (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id     INTEGER NOT NULL,
            effect_id       TEXT NOT NULL,      -- 'poison', 'stun', 'blessed'
            effect_type     TEXT NOT NULL,      -- 'physical', 'magical', 'buff'
            value           INTEGER DEFAULT 0,  -- сила эффекта
            turns_left      INTEGER DEFAULT 1,  -- сколько ходов осталось

            FOREIGN KEY (telegram_id) REFERENCES players(telegram_id)
        )
    ''')

    # ────────────────────────────────────────
    # PVP ИСТОРИЯ
    # ────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS pvp_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            attacker_id     INTEGER NOT NULL,
            defender_id     INTEGER NOT NULL,
            winner_id       INTEGER,
            exp_gained      INTEGER DEFAULT 0,
            gold_gained     INTEGER DEFAULT 0,
            fought_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (attacker_id) REFERENCES players(telegram_id),
            FOREIGN KEY (defender_id) REFERENCES players(telegram_id)
        )
    ''')

    # ────────────────────────────────────────
    # РЕЙДЫ
    # ────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS raids (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            raid_id         TEXT NOT NULL,      -- тип рейда
            status          TEXT DEFAULT 'open', -- open/in_progress/completed
            leader_id       INTEGER NOT NULL,
            players_json    TEXT DEFAULT '[]',  -- список telegram_id участников
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (leader_id) REFERENCES players(telegram_id)
        )
    ''')

    conn.commit()
    conn.close()
    print('✅ База данных создана!')
    print('📋 Таблицы: players, items, inventory, equipment,')
    print('           player_quests, skill_cooldowns,')
    print('           active_effects, pvp_log, raids')
# ────────────────────────────────────────
# ФУНКЦИИ ИГРОКА
# ────────────────────────────────────────

def get_player(telegram_id: int):
    """Получить игрока по telegram_id. Возвращает None если не найден."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM players WHERE telegram_id = ?', (telegram_id,))
    player = c.fetchone()
    conn.close()
    return player

def create_player(telegram_id: int, username: str, name: str, stats: dict):
    """Создать нового игрока с выбранными статами."""
    import sys
    sys.path.append('/content/rpg_bot')
    from game.balance import calc_max_hp, calc_max_mana, calc_carry_weight

    max_hp   = calc_max_hp(stats['vitality'])
    max_mana = calc_max_mana(stats['wisdom'])
    weight   = calc_carry_weight(stats['strength'])

    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO players (
            telegram_id, username, name,
            strength, agility, intuition,
            vitality, wisdom, luck,
            hp, max_hp, mana, max_mana, carry_weight,
            last_seen
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    ''', (
        telegram_id, username, name,
        stats['strength'], stats['agility'], stats['intuition'],
        stats['vitality'], stats['wisdom'], stats['luck'],
        max_hp, max_hp, max_mana, max_mana, weight
    ))

    # Создаём пустую экипировку
    c.execute('INSERT INTO equipment (telegram_id) VALUES (?)', (telegram_id,))

    conn.commit()
    conn.close()

def update_player_stats(telegram_id: int, stats: dict):
    """Обновить статы игрока (при левелапе или распределении очков)."""
    from game.balance import calc_max_hp, calc_max_mana, calc_carry_weight

    max_hp   = calc_max_hp(stats['vitality'])
    max_mana = calc_max_mana(stats['wisdom'])
    weight   = calc_carry_weight(stats['strength'])

    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        UPDATE players SET
            strength=?, agility=?, intuition=?,
            vitality=?, wisdom=?, luck=?,
            max_hp=?, max_mana=?, carry_weight=?
        WHERE telegram_id=?
    ''', (
        stats['strength'], stats['agility'], stats['intuition'],
        stats['vitality'], stats['wisdom'], stats['luck'],
        max_hp, max_mana, weight,
        telegram_id
    ))
    conn.commit()
    conn.close()

def player_exists(telegram_id: int) -> bool:
    """Проверить существует ли игрок."""
    return get_player(telegram_id) is not None

init_db()

def is_in_battle(telegram_id: int) -> bool:
    p = get_player(telegram_id)
    return bool(p and p['in_battle'])