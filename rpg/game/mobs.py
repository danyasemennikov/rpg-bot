# ============================================================
# mobs.py — все мобы игры
# ============================================================

# Структура моба:
# id, name, level, hp, damage_min, damage_max,
# weapon_type, exp_reward, gold_min, gold_max,
# aggressive (атакует сам), loot_table

MOBS = {

    # ── ТЁМНЫЙ ЛЕС (ур. 1-5) ────────────────────────────────

    'forest_wolf': {
        'id':          'forest_wolf',
        'name':        '🐺 Лесной волк',
        'level':       2,
        'hp':          45,
        'damage_min':  6,
        'damage_max':  10,
        'weapon_type': 'melee',
        'exp_reward':  20,
        'gold_min':    2,
        'gold_max':    5,
        'aggressive':  False,
        'encounter_role': 'normal',
        'creature_taxonomy': {
            'body_type': 'beast',
            'special_trait': 'predator',
            'encounter_class': 'normal',
        },
        'loot_table':  [
            ('wolf_pelt',   0.60),   # 60% шанс
            ('wolf_fang',   0.25),
            ('enhance_shard', 0.20),
            ('health_potion_small', 0.10),
        ]
    },

    'forest_boar': {
        'id':          'forest_boar',
        'name':        '🐗 Лесной кабан',
        'level':       1,
        'hp':          60,
        'damage_min':  4,
        'damage_max':  7,
        'weapon_type': 'melee',
        'exp_reward':  12,
        'gold_min':    1,
        'gold_max':    3,
        'aggressive':  False,
        'encounter_role': 'normal',
        'creature_taxonomy': {
            'body_type': 'beast',
            'special_trait': 'armored',
            'encounter_class': 'normal',
        },
        'loot_table':  [
            ('boar_meat',   0.75),
            ('boar_tusk',   0.20),
        ]
    },

    'forest_spider': {
        'id':          'forest_spider',
        'name':        '🕷️ Ядовитый паук',
        'level':       3,
        'hp':          35,
        'damage_min':  5,
        'damage_max':  8,
        'weapon_type': 'melee',
        'exp_reward':  25,
        'gold_min':    3,
        'gold_max':    6,
        'aggressive':  False,
        'encounter_role': 'normal',
        'creature_taxonomy': {
            'body_type': 'arachnid',
            'special_trait': 'venomous',
            'encounter_class': 'normal',
        },
        'effects':     [('poison', 0.40, 3)],  # 40% шанс яда на 3 хода
        'loot_table':  [
            ('spider_silk',  0.50),
            ('spider_venom', 0.30),
            ('enhance_shard', 0.15),
            ('novice_censer', 0.04),
        ]
    },

    'dark_treant': {
        'id':          'dark_treant',
        'name':        '🌳 Тёмный трент',
        'level':       5,
        'hp':          500000,
        'damage_min':  10,
        'damage_max':  15,
        'weapon_type': 'melee',
        'exp_reward':  55,
        'gold_min':    8,
        'gold_max':    15,
        'aggressive':  False,
        'encounter_role': 'regional_boss',
        'reward_source_category': 'open_world_regional_boss',
        'creature_taxonomy': {
            'body_type': 'plant',
            'special_trait': 'giant',
            'encounter_class': 'boss',
        },
        'loot_table':  [
            ('ancient_bark',  0.55),
            ('treant_heart',  0.15),
            ('iron_sword',    0.05),   # редкий дроп оружия
            ('apprentice_focus_orb', 0.05),
            ('militia_cuirass', 0.04),
        ]
    },

    # ── СТАРЫЕ ШАХТЫ (ур. 3-8) ──────────────────────────────

    'mine_rat': {
        'id':          'mine_rat',
        'name':        '🐀 Шахтная крыса',
        'level':       3,
        'hp':          30,
        'damage_min':  5,
        'damage_max':  9,
        'weapon_type': 'melee',
        'exp_reward':  18,
        'gold_min':    1,
        'gold_max':    4,
        'aggressive':  False,
        'encounter_role': 'normal',
        'creature_taxonomy': {
            'body_type': 'beast',
            'special_trait': 'toxic',
            'encounter_class': 'normal',
        },
        'loot_table':  [
            ('rat_tail',    0.50),
            ('rat_fur',     0.30),
        ]
    },

    'goblin_miner': {
        'id':          'goblin_miner',
        'name':        '👺 Гоблин-шахтёр',
        'level':       4,
        'hp':          55,
        'damage_min':  8,
        'damage_max':  13,
        'weapon_type': 'melee',
        'exp_reward':  35,
        'gold_min':    5,
        'gold_max':    12,
        'aggressive':  True,
        'encounter_role': 'elite',
        'reward_source_category': 'open_world_elite',
        'creature_taxonomy': {
            'body_type': 'humanoid',
            'special_trait': 'armored',
            'encounter_class': 'elite',
        },
        'loot_table':  [
            ('iron_ore',        0.60),
            ('goblin_ear',      0.40),
            ('enhancement_crystal', 0.12),
            ('worn_pickaxe',    0.15),
            ('tracker_jacket',  0.04),
            ('band_of_precision', 0.03),
            ('ring_of_quiet_mind', 0.02),
        ]
    },

    'cave_bat': {
        'id':          'cave_bat',
        'name':        '🦇 Пещерная летучая мышь',
        'level':       3,
        'hp':          25,
        'damage_min':  4,
        'damage_max':  7,
        'weapon_type': 'melee',
        'exp_reward':  15,
        'gold_min':    0,
        'gold_max':    2,
        'aggressive':  False,
        'encounter_role': 'normal',
        'creature_taxonomy': {
            'body_type': 'avian',
            'special_trait': 'frost_touched',
            'encounter_class': 'normal',
        },
        'loot_table':  [
            ('bat_wing',    0.45),
        ]
    },

    'stone_golem': {
        'id':          'stone_golem',
        'name':        '🗿 Каменный голем',
        'level':       8,
        'hp':          200,
        'damage_min':  20,
        'damage_max':  30,
        'weapon_type': 'melee',
        'exp_reward':  120,
        'gold_min':    15,
        'gold_max':    30,
        'aggressive':  False,
        'encounter_role': 'elite',
        'reward_source_category': 'open_world_elite',
        'creature_taxonomy': {
            'body_type': 'construct',
            'special_trait': 'armored',
            'encounter_class': 'elite',
        },
        'loot_table':  [
            ('stone_core',      0.40),
            ('golem_fragment',  0.25),
            ('power_essence',   0.10),
            ('iron_shield',     0.08),
            ('warden_kite_shield', 0.04),
            ('azure_focus_prism', 0.04),
            ('choir_censer', 0.04),
            ('amulet_of_kindled_prayer', 0.03),
            ('dual_path_loop', 0.03),
        ]
    },
}


# Phase 1 open-world rollout mobs.  These are intentionally simple baseline
# stat blocks that reuse the existing open-world combat/reward rails.
def _phase1_mob(
    mob_id: str,
    name: str,
    level: int,
    hp: int,
    damage_min: int,
    damage_max: int,
    body_type: str,
    special_trait: str,
    *,
    aggressive: bool = False,
    loot_table: list[tuple[str, float]] | None = None,
    exp_reward: int | None = None,
    gold_min: int | None = None,
    gold_max: int | None = None,
) -> dict:
    return {
        'id': mob_id,
        'name': name,
        'level': level,
        'hp': hp,
        'damage_min': damage_min,
        'damage_max': damage_max,
        'weapon_type': 'melee',
        'exp_reward': exp_reward if exp_reward is not None else max(8, level * 10),
        'gold_min': gold_min if gold_min is not None else max(0, level // 2),
        'gold_max': gold_max if gold_max is not None else max(2, level + 3),
        'aggressive': aggressive,
        'encounter_role': 'normal',
        'creature_taxonomy': {
            'body_type': body_type,
            'special_trait': special_trait,
            'encounter_class': 'normal',
        },
        'loot_table': loot_table or [('enhance_shard', 0.08)],
    }


MOBS.update({
    'westwild_rabbit': _phase1_mob('westwild_rabbit', '🐇 Заяц', 1, 22, 2, 4, 'beast', 'small_game', aggressive=False),
    'crow': _phase1_mob('crow', '🐦\u200d⬛ Ворон', 1, 18, 2, 5, 'avian', 'scavenger', aggressive=False),
    'goblin_scout': _phase1_mob('goblin_scout', '👺 Гоблин-разведчик', 3, 42, 5, 9, 'humanoid', 'scout', aggressive=False),
    'bear': _phase1_mob('bear', '🐻 Медведь', 5, 95, 10, 16, 'beast', 'predator', aggressive=False),
    'goblin_hunter': _phase1_mob('goblin_hunter', '👺 Гоблин-охотник', 6, 80, 13, 20, 'humanoid', 'hunter', aggressive=True),
    'goblin_shaman': _phase1_mob('goblin_shaman', '👺 Гоблин-шаман', 7, 74, 15, 23, 'humanoid', 'caster', aggressive=True),
    'goblin_chief': _phase1_mob('goblin_chief', '👺 Гоблин-вожак', 9, 156, 23, 34, 'humanoid', 'leader', aggressive=True),
    'mountain_rabbit': _phase1_mob('mountain_rabbit', '🐇 Горный заяц', 1, 24, 2, 4, 'beast', 'small_game', aggressive=False),
    'rock_lizard': _phase1_mob('rock_lizard', '🦎 Скальный ящер', 2, 34, 4, 7, 'reptile', 'armored', aggressive=False),
    'white_wolf': _phase1_mob('white_wolf', '🐺 Белый волк', 4, 58, 8, 13, 'beast', 'predator', aggressive=False, exp_reward=30, gold_min=1, gold_max=6),
    'stone_beetle': _phase1_mob('stone_beetle', '🪲 Каменный жук', 4, 76, 8, 13, 'insect', 'armored', aggressive=False),
    'mountain_stone_golem': _phase1_mob('mountain_stone_golem', '🗿 Каменный голем', 10, 245, 18, 28, 'construct', 'armored', aggressive=True, exp_reward=110, gold_min=5, gold_max=14),
    'troll': _phase1_mob('troll', '🧌 Тролль', 7, 152, 19, 28, 'giant', 'brute', aggressive=True),
    'ice_troll': _phase1_mob('ice_troll', '🧌 Ледяной тролль', 8, 178, 20, 30, 'giant', 'frost_touched', aggressive=True),
    'troll_chief': _phase1_mob('troll_chief', '🧌 Тролль-вожак', 10, 248, 26, 38, 'giant', 'leader', aggressive=True),
    'zombie': _phase1_mob('zombie', '🧟 Зомби', 4, 62, 7, 12, 'undead', 'rotting', aggressive=False, exp_reward=30, gold_min=1, gold_max=6),
    'skeleton_warrior': _phase1_mob('skeleton_warrior', '💀 Скелет-воин', 4, 58, 8, 13, 'undead', 'armed', aggressive=False),
    'skeleton_mage': _phase1_mob('skeleton_mage', '💀 Скелет-маг', 5, 48, 11, 17, 'undead', 'caster', aggressive=False),
    'ghost': _phase1_mob('ghost', '👻 Призрак', 6, 60, 12, 18, 'undead', 'ethereal', aggressive=False),
    'skeleton_guard': _phase1_mob('skeleton_guard', '💀 Скелет-страж', 7, 102, 15, 23, 'undead', 'armored', aggressive=True),
    'cursed_knight': _phase1_mob('cursed_knight', '🛡️ Проклятый рыцарь', 8, 146, 19, 28, 'undead', 'cursed', aggressive=True),
    'skeleton_priest': _phase1_mob('skeleton_priest', '💀 Скелет-жрец', 9, 118, 22, 31, 'undead', 'priest', aggressive=True),
    'temple_guardian': _phase1_mob('temple_guardian', '🗿 Храмовый страж', 10, 238, 27, 39, 'construct', 'guardian', aggressive=True),
    'desert_beetle': _phase1_mob('desert_beetle', '🪲 Пустынный жук', 2, 34, 4, 7, 'insect', 'armored', aggressive=False),
    'desert_lizard': _phase1_mob('desert_lizard', '🦎 Ящерица', 3, 44, 6, 10, 'reptile', 'desert', aggressive=False),
    'scavenger': _phase1_mob('scavenger', '🦅 Падальщик', 4, 48, 8, 13, 'avian', 'scavenger', aggressive=False),
    'scorpion': _phase1_mob('scorpion', '🦂 Скорпион', 5, 58, 10, 16, 'arachnid', 'venomous', aggressive=False),
    'snake': _phase1_mob('snake', '🐍 Змея', 5, 50, 10, 17, 'reptile', 'venomous', aggressive=False),
    'crocodile': _phase1_mob('crocodile', '🐊 Крокодил', 6, 105, 14, 22, 'reptile', 'predator', aggressive=False),
    'desert_elephant': _phase1_mob('desert_elephant', '🐘 Пустынный слон', 7, 160, 16, 24, 'beast', 'giant', aggressive=True),
    'fire_elemental': _phase1_mob('fire_elemental', '🔥 Огненный элементаль', 8, 110, 20, 30, 'elemental', 'fire', aggressive=True),
    'earth_elemental': _phase1_mob('earth_elemental', '🪨 Земляной элементаль', 9, 160, 21, 31, 'elemental', 'earth', aggressive=True),
    'air_elemental': _phase1_mob('air_elemental', '🌪️ Воздушный элементаль', 10, 120, 23, 34, 'elemental', 'air', aggressive=True),
    'swamp_toad': _phase1_mob('swamp_toad', '🐸 Болотная жаба', 2, 36, 4, 8, 'amphibian', 'swamp', aggressive=False),
    'leech': _phase1_mob('leech', '🪱 Пиявка', 3, 38, 5, 9, 'vermin', 'bloodsucker', aggressive=False, exp_reward=20, gold_min=1, gold_max=5),
    'water_snake': _phase1_mob('water_snake', '🐍 Водяная змея', 3, 45, 7, 11, 'reptile', 'venomous', aggressive=False),
    'swamp_spider': _phase1_mob('swamp_spider', '🕷️ Болотный паук', 4, 46, 8, 13, 'arachnid', 'venomous', aggressive=False),
    'giant_leech': _phase1_mob('giant_leech', '🪱 Гигантская пиявка', 6, 85, 13, 20, 'vermin', 'bloodsucker', aggressive=False),
    'slug': _phase1_mob('slug', '🐌 Слизень', 6, 75, 12, 19, 'ooze', 'acidic', aggressive=False),
    'drowned': _phase1_mob('drowned', '🧟 Утопленник', 10, 168, 24, 35, 'undead', 'drowned', aggressive=True, exp_reward=105, gold_min=5, gold_max=14),
    'swamp_witch': _phase1_mob('swamp_witch', '🧙 Болотная ведьма', 8, 95, 20, 29, 'humanoid', 'caster', aggressive=True),
    'toxic_slime': _phase1_mob('toxic_slime', '☣️ Ядовитая слизь', 9, 138, 20, 31, 'ooze', 'toxic', aggressive=True),
    'old_witch': _phase1_mob('old_witch', '🧙 Старая ведьма', 10, 154, 27, 39, 'humanoid', 'elder_caster', aggressive=True),
    'shore_crab': _phase1_mob('shore_crab', '🦀 Краб', 1, 24, 3, 5, 'crustacean', 'shoreline', aggressive=False),
    'seagull': _phase1_mob('seagull', '🐦 Чайка', 1, 20, 2, 5, 'avian', 'shoreline', aggressive=False),
    'shore_turtle': _phase1_mob('shore_turtle', '🐢 Береговая черепаха', 2, 55, 4, 7, 'reptile', 'armored', aggressive=False),
})

def get_mob(mob_id: str) -> dict:
    """Получить моба по ID. Возвращает копию чтобы не менять оригинал."""
    mob = MOBS.get(mob_id)
    if mob:
        return dict(mob)  # копия!
    return None

def get_mobs_for_location(mob_ids: list) -> list:
    """Получить список мобов для локации."""
    return [get_mob(mid) for mid in mob_ids if get_mob(mid)]



_PHASE1_COMBAT_PRESSURE_TAGS = {
    'westwild_rabbit': ('soft_entry','small_game','basic_beast'),'crow': ('soft_entry','small_game'),'forest_boar': ('basic_beast','bruiser'),
    'forest_wolf': ('pack_hunter','predator','moderate_pack'),'forest_spider': ('venom','ambush'),'goblin_scout': ('skirmisher','goblin_pressure'),
    'bear': ('bruiser','solo_pressure'),'goblin_hunter': ('ambush','ranged_hunter','goblin_pressure'),'goblin_shaman': ('caster','disruptor','goblin_shaman_pressure','goblin_pressure'),'goblin_chief': ('leader','goblin_pressure','route_exam'),
    'mountain_rabbit': ('soft_entry','small_game'),'rock_lizard': ('armored','mitigation_check'),'white_wolf': ('pack_hunter','sustained_trade'),'stone_beetle': ('armored','bruiser'),
    'mountain_stone_golem': ('armored','elite_bruiser','mitigation_check'),'troll': ('high_hp','sustained_trade','heavy_trade'),'ice_troll': ('high_hp','heavy_trade'),'troll_chief': ('high_hp','heavy_trade','route_exam'),
    'zombie': ('soft_entry','undead','attrition'),'skeleton_warrior': ('soft_entry','undead','relic'),'skeleton_mage': ('undead','caster','holy_target'),'ghost': ('undead','ethereal','evasive_target'),
    'skeleton_guard': ('undead','relic_guardian','poison_bleed_poor_target'),'cursed_knight': ('undead','bruiser','cursed','poison_bleed_poor_target'),'skeleton_priest': ('undead','caster','holy_target','poison_bleed_poor_target'),'temple_guardian': ('construct','relic_guardian','armored','holy_target','poison_bleed_poor_target','route_exam'),
    'swamp_toad': ('soft_entry','attrition'),'leech': ('attrition','sustain_pressure','mirror_checked_venom'),'water_snake': ('venom','attrition','mirror_checked_venom'),'swamp_spider': ('venom','attrition','mirror_checked_venom'),
    'giant_leech': ('attrition','sustain_pressure'),'slug': ('toxin','debuff_pressure'),'drowned': ('attrition_exam','sustain_pressure'),'swamp_witch': ('caster','control_pressure'),'toxic_slime': ('toxin','debuff_pressure','mirror_checked_venom'),'old_witch': ('caster','control_pressure','attrition_exam','route_exam'),
    'desert_beetle': ('soft_entry','armored_light'),'desert_lizard': ('skirmisher','precision_threat'),'scavenger': ('skirmisher','precision'),'scorpion': ('precision_threat','venom','evasive_target'),
    'snake': ('precision_threat','venom','evasive_target'),'desert_elephant': ('bruiser','solo_pressure'),'fire_elemental': ('elemental','precision','burst'),'earth_elemental': ('elemental','armored','solo_pressure'),'air_elemental': ('elemental','evasion_accuracy_check','evasive_target','elite_skirmisher','route_exam'),
}

for _mob_id, _tags in _PHASE1_COMBAT_PRESSURE_TAGS.items():
    if _mob_id in MOBS:
        MOBS[_mob_id]['combat_pressure_tags'] = tuple(_tags)

print('✅ game/mobs.py создан!')
print(f'   Мобов в базе: {len(MOBS)}')
