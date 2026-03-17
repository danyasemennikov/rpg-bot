import sys
sys.path.append('/workspaces/rpg-bot')

import sqlite3
from game.skills import SKILLS, SKILL_TREES

TELEGRAM_ID = 347433727
DB_PATH = '/workspaces/rpg-bot/game.db'

conn = sqlite3.connect(DB_PATH)

# Максимальные статы и ресурсы
conn.execute('''UPDATE players SET
    hp=9999, max_hp=9999, mana=9999, max_mana=9999,
    gold=99999, level=50, stat_points=99,
    strength=50, agility=50, intuition=50,
    vitality=50, wisdom=50, luck=50
    WHERE telegram_id=?''', (TELEGRAM_ID,))

# Все виды оружия в инвентарь
weapons = ['wooden_sword', 'iron_sword', 'dagger', 'short_bow', 'magic_staff', 'holy_staff']
for w in weapons:
    existing = conn.execute(
        'SELECT id FROM inventory WHERE telegram_id=? AND item_id=?',
        (TELEGRAM_ID, w)
    ).fetchone()
    if not existing:
        conn.execute(
            'INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?,?,1)',
            (TELEGRAM_ID, w)
        )

# Все скиллы — уровень 5
for skill_id, skill in SKILLS.items():
    if skill['type'] == 'passive':
        level = 5
    else:
        level = 5
    existing = conn.execute(
        'SELECT * FROM player_skills WHERE telegram_id=? AND skill_id=?',
        (TELEGRAM_ID, skill_id)
    ).fetchone()
    if existing:
        conn.execute(
            'UPDATE player_skills SET level=? WHERE telegram_id=? AND skill_id=?',
            (level, TELEGRAM_ID, skill_id)
        )
    else:
        conn.execute(
            'INSERT INTO player_skills (telegram_id, skill_id, level) VALUES (?,?,?)',
            (TELEGRAM_ID, skill_id, level)
        )

# Мастерство всех оружий — уровень 10
for w in weapons + ['unarmed']:
    existing = conn.execute(
        'SELECT * FROM weapon_mastery WHERE telegram_id=? AND weapon_id=?',
        (TELEGRAM_ID, w)
    ).fetchone()
    if existing:
        conn.execute(
            'UPDATE weapon_mastery SET level=10, exp=0 WHERE telegram_id=? AND weapon_id=?',
            (TELEGRAM_ID, w)
        )
    else:
        conn.execute(
            'INSERT INTO weapon_mastery (telegram_id, weapon_id, level, exp) VALUES (?,?,10,0)',
            (TELEGRAM_ID, w)
        )

# Сбросить кулдауны
conn.execute('DELETE FROM skill_cooldowns WHERE telegram_id=?', (TELEGRAM_ID,))

conn.commit()
conn.close()
print('✅ Тестовый персонаж готов!')
print('Теперь зайди в бот, экипируй нужное оружие и тестируй скиллы.')