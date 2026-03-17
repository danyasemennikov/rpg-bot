# ============================================================
# quests_data.py — все квесты игры
# ============================================================

QUESTS = {

    # ══════════════════════════════════════════════
    # ⚡ ИСПЫТАНИЯ
    # ══════════════════════════════════════════════

    'challenge_clean_kill': {
        'id':          'challenge_clean_kill',
        'title':       '⚡ Чистая победа',
        'type':        'challenge',
        'description': (
            'Охотник Рейн смотрит скептически:\n'
            '"Убей Лесного паука без единого зелья. '
            'И чтобы он тебя задел не больше чем на 30 урона. '
            'Иначе — не считается."'
        ),
        'giver_npc':      'Охотник Рейн',
        'giver_location': 'village',
        'req_level':      2,
        'steps': [
            {
                'id':          'talk',
                'type':        'talk_npc',
                'description': 'Поговори с Охотником Рейном',
                'location':    'village',
                'npc':         'Охотник Рейн',
                'dialogue': (
                    '🏹 <b>Охотник Рейн:</b> "Лесной паук — не самый опасный зверь. '
                    'Но убить его чисто — это уже мастерство. '
                    'Без зелий. Максимум 30 урона. Удачи."'
                ),
            },
            {
                'id':          'kill',
                'type':        'kill_challenge',
                'description': 'Убей Лесного паука (без зелий, макс 30 урона)',
                'location':    'dark_forest',
                'mob_id':      'forest_spider',
                'kill_count':  1,
                'conditions': {
                    'no_potions':       True,
                    'max_damage_taken': 30,
                },
                'fail_text': '❌ Ты нарушил условия. Охотник Рейн: "Ещё раз. Чище."',
            },
            {
                'id':          'report',
                'type':        'talk_npc',
                'description': 'Доложи Охотнику Рейну',
                'location':    'village',
                'npc':         'Охотник Рейн',
                'dialogue':    '🏹 <b>Охотник Рейн:</b> "Хм. Неплохо. Держи."',
            },
        ],
        'rewards': {
            'exp':   250,
            'gold':  150,
            'items': [('spider_silk', 3)],
        },
        'completion_text': '✅ <b>Испытание пройдено: Чистая победа!</b>',
    },

    'challenge_untouchable': {
        'id':          'challenge_untouchable',
        'title':       '⚡ Неуязвимый',
        'type':        'challenge',
        'description': (
            'Старый воин хмурится:\n'
            '"Волк — быстрый зверь. Если он тебя хоть раз задел — '
            'ты уже проиграл. Убей его без единой царапины."'
        ),
        'giver_npc':      'Ветеран Борг',
        'giver_location': 'village',
        'req_level':      3,
        'steps': [
            {
                'id':          'talk',
                'type':        'talk_npc',
                'description': 'Поговори с Ветераном Боргом',
                'location':    'village',
                'npc':         'Ветеран Борг',
                'dialogue': (
                    '⚔️ <b>Ветеран Борг:</b> "Я видел как новички гибнут от волков. '
                    'Не потому что слабы — потому что медленны. '
                    'Нулевой урон. Ни единого попадания. Докажи что ты быстрее."'
                ),
            },
            {
                'id':          'kill',
                'type':        'kill_challenge',
                'description': 'Убей Лесного волка (0 урона получено)',
                'location':    'dark_forest',
                'mob_id':      'forest_wolf',
                'kill_count':  1,
                'conditions': {
                    'max_damage_taken': 0,
                },
                'fail_text': '❌ Волк тебя задел. Борг: "Мёртвые не получают награду."',
            },
            {
                'id':          'report',
                'type':        'talk_npc',
                'description': 'Вернись к Ветерану Боргу',
                'location':    'village',
                'npc':         'Ветеран Борг',
                'dialogue': (
                    '⚔️ <b>Ветеран Борг:</b> "Я не верил что ты сможешь. '
                    'Теперь верю. Заслужил."'
                ),
            },
        ],
        'rewards': {
            'exp':   300,
            'gold':  200,
            'items': [('wolf_fang', 3)],
        },
        'completion_text': '✅ <b>Испытание пройдено: Неуязвимый!</b>',
    },

    'challenge_lightning': {
        'id':          'challenge_lightning',
        'title':       '⚡ Молниеносный',
        'type':        'challenge',
        'description': (
            'Торговец усмехается:\n'
            '"Говорят кабан — медленный зверь. Но убить его за 3 хода? '
            'Это уже другой разговор. Есть такая поговорка — '
            'быстрый меч кормит семью."'
        ),
        'giver_npc':      'Торговец Симон',
        'giver_location': 'village',
        'req_level':      2,
        'steps': [
            {
                'id':          'talk',
                'type':        'talk_npc',
                'description': 'Поговори с Торговцем Симоном',
                'location':    'village',
                'npc':         'Торговец Симон',
                'dialogue': (
                    '🧳 <b>Торговец Симон:</b> "Три хода — и кабан должен лежать. '
                    'Четыре — уже не считается. Я слежу за временем."'
                ),
            },
            {
                'id':          'kill',
                'type':        'kill_challenge',
                'description': 'Убей Лесного кабана за 3 хода',
                'location':    'dark_forest',
                'mob_id':      'forest_boar',
                'kill_count':  1,
                'conditions': {
                    'max_turns': 3,
                },
                'fail_text': '❌ Слишком долго. Симон: "Кабан умер от старости, не от тебя."',
            },
            {
                'id':          'report',
                'type':        'talk_npc',
                'description': 'Вернись к Торговцу Симону',
                'location':    'village',
                'npc':         'Торговец Симон',
                'dialogue': (
                    '🧳 <b>Торговец Симон:</b> "Быстро! Держи — заработал."'
                ),
            },
        ],
        'rewards': {
            'exp':   200,
            'gold':  180,
            'items': [('boar_meat', 5)],
        },
        'completion_text': '✅ <b>Испытание пройдено: Молниеносный!</b>',
    },

    'challenge_last_stand': {
        'id':          'challenge_last_stand',
        'title':       '⚡ На грани',
        'type':        'challenge',
        'description': (
            'Мистик смотрит сквозь тебя:\n'
            '"Настоящая сила просыпается когда смерть рядом. '
            'Убей Каменного голема когда твоё HP ниже половины. '
            'Страх должен стать топливом."'
        ),
        'giver_npc':      'Мистик Аэль',
        'giver_location': 'village',
        'req_level':      5,
        'steps': [
            {
                'id':          'talk',
                'type':        'talk_npc',
                'description': 'Поговори с Мистиком Аэлем',
                'location':    'village',
                'npc':         'Мистик Аэль',
                'dialogue': (
                    '🔮 <b>Мистик Аэль:</b> "Голем — это камень и воля. '
                    'Твоя воля должна быть сильнее. '
                    'Начни бой с полным HP — но победи только когда '
                    'останется меньше половины. Тогда я поверю тебе."'
                ),
            },
            {
                'id':          'kill',
                'type':        'kill_challenge',
                'description': 'Убей Каменного голема с HP ниже 50%',
                'location':    'old_mines',
                'mob_id':      'stone_golem',
                'kill_count':  1,
                'conditions': {
                    'max_hp_percent': 50,
                },
                'fail_text': '❌ Ты победил с HP выше 50%. Аэль: "Ты не почувствовал грань."',
            },
            {
                'id':          'report',
                'type':        'talk_npc',
                'description': 'Вернись к Мистику Аэлю',
                'location':    'village',
                'npc':         'Мистик Аэль',
                'dialogue': (
                    '🔮 <b>Мистик Аэль:</b> "Я видел твои глаза когда ты стоял '
                    'на краю. Вот это — настоящая сила. Прими этот дар."'
                ),
            },
        ],
        'rewards': {
            'exp':   500,
            'gold':  250,
            'items': [('stone_core', 1)],
        },
        'completion_text': '✅ <b>Испытание пройдено: На грани!</b>',
    },

    'challenge_bare_hands': {
        'id':          'challenge_bare_hands',
        'title':       '⚡ Голыми руками',
        'type':        'challenge',
        'description': (
            'Пьяный кузнец хохочет:\n'
            '"Крыса! Ты боишься крысы? '
            'Сними всё оружие и броню — и убей её кулаками! '
            'Поспорим на золото?"'
        ),
        'giver_npc':      'Кузнец Хогг',
        'giver_location': 'village',
        'req_level':      1,
        'steps': [
            {
                'id':          'talk',
                'type':        'talk_npc',
                'description': 'Поговори с Кузнецом Хоггом',
                'location':    'village',
                'npc':         'Кузнец Хогг',
                'dialogue': (
                    '🔨 <b>Кузнец Хогг:</b> "Снимаешь всё — оружие, броню — всё! '
                    'И убиваешь шахтную крысу голыми руками. '
                    'Справишься — плачу двойную цену за любой лут что принесёшь."'
                ),
            },
            {
                'id':          'kill',
                'type':        'kill_challenge',
                'description': 'Убей Шахтную крысу без оружия и брони',
                'location':    'old_mines',
                'mob_id':      'mine_rat',
                'kill_count':  1,
                'conditions': {
                    'no_weapon': True,
                    'no_armor':  True,
                },
                'fail_text': '❌ Ты использовал снаряжение. Хогг: "Жульничать нехорошо!"',
            },
            {
                'id':          'report',
                'type':        'talk_npc',
                'description': 'Вернись к Кузнецу Хоггу',
                'location':    'village',
                'npc':         'Кузнец Хогг',
                'dialogue': (
                    '🔨 <b>Кузнец Хогг:</b> "Ха! Не верю своим глазам! '
                    'Держи золото, заслужил. И уважение кузнеца — это дорогого стоит!"'
                ),
            },
        ],
        'rewards': {
            'exp':   150,
            'gold':  120,
            'items': [],
        },
        'completion_text': '✅ <b>Испытание пройдено: Голыми руками!</b>',
    },

    'challenge_skills_only': {
        'id':          'challenge_skills_only',
        'title':       '⚡ Чистая магия',
        'type':        'challenge',
        'description': (
            'Архимаг деревни поднимает бровь:\n'
            '"Ты называешь себя магом и бьёшь обычными ударами? '
            'Убей летучую мышь используя только способности. '
            'Ни одной обычной атаки."'
        ),
        'giver_npc':      'Архимаг Селис',
        'giver_location': 'village',
        'req_level':      3,
        'steps': [
            {
                'id':          'talk',
                'type':        'talk_npc',
                'description': 'Поговори с Архимагом Селис',
                'location':    'village',
                'npc':         'Архимаг Селис',
                'dialogue': (
                    '✨ <b>Архимаг Селис:</b> "Магия — это не просто инструмент. '
                    'Это образ мысли. Только способности. '
                    'Обычная атака — и испытание сброшено."'
                ),
            },
            {
                'id':          'kill',
                'type':        'kill_challenge',
                'description': 'Убей Пещерную летучую мышь только скиллами',
                'location':    'old_mines',
                'mob_id':      'cave_bat',
                'kill_count':  1,
                'conditions': {
                    'skills_only': True,
                },
                'fail_text': '❌ Ты использовал обычную атаку. Селис: "Разочарован."',
            },
            {
                'id':          'report',
                'type':        'talk_npc',
                'description': 'Вернись к Архимагу Селис',
                'location':    'village',
                'npc':         'Архимаг Селис',
                'dialogue': (
                    '✨ <b>Архимаг Селис:</b> "Вот теперь я вижу мага. '
                    'Прими этот свиток — он поможет тебе в будущем."'
                ),
            },
        ],
        'rewards': {
            'exp':   350,
            'gold':  200,
            'items': [('mana_potion', 3)],
        },
        'completion_text': '✅ <b>Испытание пройдено: Чистая магия!</b>',
    },

    'challenge_berserker': {
        'id':          'challenge_berserker',
        'title':       '⚡ Берсерк',
        'type':        'challenge',
        'description': (
            'Безумный варвар рычит:\n'
            '"Трент! Тёмный трент! Без щитов, без баффов — '
            'только ярость! И уложить его за 5 ходов! '
            'Слабаки не нужны нашему отряду!"'
        ),
        'giver_npc':      'Варвар Крог',
        'giver_location': 'village',
        'req_level':      4,
        'steps': [
            {
                'id':          'talk',
                'type':        'talk_npc',
                'description': 'Поговори с Варваром Крогом',
                'location':    'village',
                'npc':         'Варвар Крог',
                'dialogue': (
                    '🪓 <b>Варвар Крог:</b> "Никаких защитных стоек! '
                    'Никаких благословений! Только атака! '
                    'Тёмный трент должен упасть за 5 ходов. '
                    'Или ты не берсерк — ты трус."'
                ),
            },
            {
                'id':          'kill',
                'type':        'kill_challenge',
                'description': 'Убей Тёмного трента (без баффов, за 5 ходов)',
                'location':    'dark_forest',
                'mob_id':      'dark_treant',
                'kill_count':  1,
                'conditions': {
                    'no_buffs':  True,
                    'max_turns': 5,
                },
                'fail_text': '❌ Не уложился. Крог: "Слабак. Тренируйся."',
            },
            {
                'id':          'report',
                'type':        'talk_npc',
                'description': 'Вернись к Варвару Крогу',
                'location':    'village',
                'npc':         'Варвар Крог',
                'dialogue': (
                    '🪓 <b>Варвар Крог:</b> "ХОРОШО! Вот это берсерк! '
                    'Добро пожаловать в отряд!"'
                ),
            },
        ],
        'rewards': {
            'exp':   450,
            'gold':  300,
            'items': [('health_potion', 3)],
        },
        'completion_text': '✅ <b>Испытание пройдено: Берсерк!</b>',
    },

    # ══════════════════════════════════════════════
    # 🤝 МОРАЛЬНЫЙ ВЫБОР — Пленный гоблин
    # ══════════════════════════════════════════════
    'goblin_prisoner': {
        'id':          'goblin_prisoner',
        'title':       '🤝 Пленный гоблин',
        'type':        'moral',
        'description': (
            'В глубине шахт ты натыкаешься на раненого гоблина. '
            'Он не нападает — только смотрит с испугом и что-то бормочет.'
        ),
        'giver_npc':      None,
        'giver_location': 'old_mines',
        'trigger':        'explore',
        'req_level':      3,
        'steps': [
            {
                'id':          'find_goblin',
                'type':        'find_clue',
                'description': 'Найди раненого гоблина в шахтах',
                'location':    'old_mines',
                'clue_id':     'wounded_goblin',
                'clue_text': (
                    '👺 В углу шахты сидит раненый гоблин. Его нога перевязана '
                    'грязной тряпкой. Он смотрит на тебя и говорит на ломаном Common:\n\n'
                    '"Не убивай... Я знаю где клад. Скажу — если отпустишь."'
                ),
            },
            {
                'id':          'moral_choice',
                'type':        'choice',
                'description': 'Что ты сделаешь с гоблином?',
                'choices': [
                    {
                        'id':    'help_goblin',
                        'text':  '💚 Помочь и отпустить',
                        'result': (
                            '💚 Ты перевязываешь рану гоблина и отпускаешь его. '
                            'Тот удивлённо смотрит, потом указывает на камень в стене:\n\n'
                            '"Ты... добрый. Клад там. Бери."'
                        ),
                        'rewards': {
                            'exp':        200,
                            'gold':       0,
                            'items':      [('gem_common', 2), ('iron_ore', 5)],
                            'reputation': {'goblins': +10, 'village': -5},
                        },
                    },
                    {
                        'id':    'attack_goblin',
                        'text':  '⚔️ Атаковать',
                        'result': (
                            '⚔️ Ты не доверяешь гоблину. Короткий бой — '
                            'и враг повержен. При обыске находишь немного золота.'
                        ),
                        'rewards': {
                            'exp':        100,
                            'gold':       80,
                            'items':      [('goblin_ear', 1)],
                            'reputation': {'goblins': -10, 'village': +5},
                        },
                    },
                ],
            },
        ],
        'rewards':         None,
        'completion_text': '✅ <b>Выбор сделан.</b> Последствия могут проявиться позже...',
    },
}

def get_quest(quest_id: str) -> dict:
    return QUESTS.get(quest_id)

def get_available_quests(telegram_id: int, location_id: str) -> list:
    """Квесты доступные игроку в данной локации."""
    from database import get_connection, get_player
    player = dict(get_player(telegram_id))
    conn   = get_connection()
    taken  = {
        row['quest_id']
        for row in conn.execute(
            "SELECT quest_id FROM player_quests WHERE telegram_id=? AND status!='failed'",
            (telegram_id,)
        ).fetchall()
    }
    conn.close()

    result = []
    for q in QUESTS.values():
        if q['id'] in taken:
            continue
        if q.get('giver_location') != location_id:
            continue
        if q.get('giver_npc') is None:
            continue
        if player['level'] < q.get('req_level', 1):
            continue
        result.append(q)
    return result

def get_active_quests(telegram_id: int) -> list:
    """Активные квесты игрока."""
    from database import get_connection
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM player_quests WHERE telegram_id=? AND status='active'",
        (telegram_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

print(f'✅ game/quests_data.py обновлён! Квестов: {len(QUESTS)}')