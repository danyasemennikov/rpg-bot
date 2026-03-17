# ============================================================
# weapon_mastery.py — прокачка владения оружием
# ============================================================

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection

MAX_MASTERY = 20

def mastery_exp_needed(level: int) -> int:
    """Опыт для следующего уровня владения."""
    return level * 50

def get_mastery(telegram_id: int, weapon_id: str) -> dict:
    """Получить данные владения оружием."""
    conn = get_connection()
    row  = conn.execute(
        '''SELECT * FROM weapon_mastery
           WHERE telegram_id=? AND weapon_id=?''',
        (telegram_id, weapon_id)
    ).fetchone()
    conn.close()

    if row:
        return dict(row)

    # Создаём запись если нет
    return create_mastery(telegram_id, weapon_id)

def create_mastery(telegram_id: int, weapon_id: str) -> dict:
    """Создаёт запись владения если её нет."""
    conn = get_connection()
    conn.execute(
        '''INSERT OR IGNORE INTO weapon_mastery
           (telegram_id, weapon_id, level, exp, skill_points)
           VALUES (?, ?, 1, 0, 1)''',
        (telegram_id, weapon_id)
    )
    conn.commit()
    row = conn.execute(
        'SELECT * FROM weapon_mastery WHERE telegram_id=? AND weapon_id=?',
        (telegram_id, weapon_id)
    ).fetchone()
    conn.close()
    return dict(row)

def add_mastery_exp(telegram_id: int, weapon_id: str, exp: int) -> dict:
    """
    Добавляет опыт владения оружием.
    Возвращает словарь с результатом (левелап, новые скиллы).
    """
    mastery    = get_mastery(telegram_id, weapon_id)
    new_exp    = mastery['exp'] + exp
    new_level  = mastery['level']
    new_points = mastery['skill_points']
    leveled_up = False
    new_skills = []

    # Проверяем левелап
    while new_level < MAX_MASTERY and new_exp >= mastery_exp_needed(new_level):
        new_exp   -= mastery_exp_needed(new_level)
        new_level += 1
        new_points += 1
        leveled_up = True

        # Проверяем какие скиллы открылись
        from game.skills import get_weapon_tree, get_skill, SKILL_TREES
        tree = get_weapon_tree(weapon_id)
        for branch, skill_ids in tree.items():
            for skill_id in skill_ids:
                skill = get_skill(skill_id)
                if skill and skill['unlock_mastery'] == new_level:
                    new_skills.append(skill)

    conn = get_connection()
    conn.execute(
        '''UPDATE weapon_mastery SET
            level=?, exp=?, skill_points=?
           WHERE telegram_id=? AND weapon_id=?''',
        (new_level, new_exp, new_points, telegram_id, weapon_id)
    )
    conn.commit()
    conn.close()

    return {
        'leveled_up':  leveled_up,
        'new_level':   new_level,
        'new_exp':     new_exp,
        'new_points':  new_points,
        'new_skills':  new_skills,
        'exp_needed':  mastery_exp_needed(new_level),
    }

def get_skill_level(telegram_id: int, skill_id: str) -> int:
    """Получить уровень прокачки скилла."""
    conn = get_connection()
    row  = conn.execute(
        'SELECT level FROM player_skills WHERE telegram_id=? AND skill_id=?',
        (telegram_id, skill_id)
    ).fetchone()
    conn.close()
    return row['level'] if row else 0

def upgrade_skill(telegram_id: int, weapon_id: str, skill_id: str) -> dict:
    """Прокачать скилл на 1 уровень."""
    from game.skills import get_skill
    skill   = get_skill(skill_id)
    mastery = get_mastery(telegram_id, weapon_id)

    if not skill:
        return {'success': False, 'reason': 'Скилл не найден'}

    if mastery['level'] < skill['unlock_mastery']:
        return {'success': False, 'reason': f"Нужен уровень владения {skill['unlock_mastery']}"}

    if mastery['skill_points'] <= 0:
        return {'success': False, 'reason': 'Нет очков скиллов'}

    current_level = get_skill_level(telegram_id, skill_id)
    if current_level >= skill['max_level']:
        return {'success': False, 'reason': f"Скилл уже максимального уровня ({skill['max_level']})"}

    conn = get_connection()

    if current_level == 0:
        conn.execute(
            'INSERT INTO player_skills (telegram_id, skill_id, level) VALUES (?,?,1)',
            (telegram_id, skill_id)
        )
    else:
        conn.execute(
            'UPDATE player_skills SET level=level+1 WHERE telegram_id=? AND skill_id=?',
            (telegram_id, skill_id)
        )

    conn.execute(
        'UPDATE weapon_mastery SET skill_points=skill_points-1 WHERE telegram_id=? AND weapon_id=?',
        (telegram_id, weapon_id)
    )
    conn.commit()
    conn.close()

    return {
        'success':    True,
        'new_level':  current_level + 1,
        'skill_name': skill['name'],
    }

def get_skill_cooldown(telegram_id: int, skill_id: str) -> int:
    """Возвращает оставшиеся ходы кулдауна. 0 = готово."""
    conn = get_connection()
    row  = conn.execute(
        'SELECT turns_left FROM skill_cooldowns WHERE telegram_id=? AND skill_id=?',
        (telegram_id, skill_id)
    ).fetchone()
    conn.close()
    return row['turns_left'] if row else 0

def set_skill_cooldown(telegram_id: int, skill_id: str, turns: int):
    """Устанавливает кулдаун скилла."""
    conn = get_connection()
    conn.execute(
        '''INSERT OR REPLACE INTO skill_cooldowns
           (telegram_id, skill_id, turns_left)
           VALUES (?, ?, ?)''',
        (telegram_id, skill_id, turns)
    )
    conn.commit()
    conn.close()

def tick_cooldowns(telegram_id: int):
    """Уменьшает все кулдауны на 1 ход."""
    conn = get_connection()
    conn.execute(
        '''UPDATE skill_cooldowns SET turns_left=turns_left-1
           WHERE telegram_id=? AND turns_left > 0''',
        (telegram_id,)
    )
    conn.execute(
        'DELETE FROM skill_cooldowns WHERE telegram_id=? AND turns_left <= 0',
        (telegram_id,)
    )
    conn.commit()
    conn.close()

print('✅ game/weapon_mastery.py создан!')