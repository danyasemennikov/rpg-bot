# 🎮 Осколки Вечности — RPG Telegram Bot

## Стек
- Python 3.12 + python-telegram-bot
- SQLite (файл: game.db)
- GitHub Codespaces (/workspaces/rpg-bot/)

---

## 📁 Структура проекта

```
rpg-bot/
├── CLAUDE.md          ← этот файл
├── bot.py             ← точка входа, регистрация хендлеров
├── database.py        ← БД, get_connection(), get_player()
├── game.db
├── game/
│   ├── balance.py     ← формулы: exp, hp, mana, урон
│   ├── combat.py      ← расчёт боя, process_turn() с парированием
│   ├── i18n.py        ← движок переводов: t(), get_item_name(), get_mob_name(),
│   │                     get_location_name/desc(), get_skill_name/desc()
│   ├── items_data.py  ← ITEMS dict, get_item(item_id)
│   ├── locations.py   ← LOCATIONS dict
│   ├── mobs.py        ← MOBS dict
│   ├── quests_data.py ← QUESTS dict (8 квестов, см. ниже)
│   ├── regen.py       ← реген HP/маны по last_seen
│   ├── seed.py        ← заполняет таблицу items из ITEMS
│   ├── skill_engine.py← use_skill(), calc_skill_value(), parry логика
│   ├── skills.py      ← SKILLS dict, SKILL_TREES dict
│   └── weapon_mastery.py ← get_mastery(), add_mastery_exp()
├── handlers/
│   ├── battle.py      ← бой ✅ i18n готов
│   ├── inventory.py   ← инвентарь ✅ i18n готов
│   ├── location.py    ← локации ✅ i18n готов
│   ├── profile.py     ← профиль, статы ✅ i18n готов
│   ├── quests.py      ← квесты ⏳ не написан
│   ├── settings.py    ← настройки и смена языка ✅
│   ├── skills_ui.py   ← интерфейс навыков ✅ i18n готов
│   └── start.py       ← регистрация персонажа ✅ i18n готов
└── locales/
    ├── ru.py           ← русский (основной) ✅
    ├── en.py           ← английский ✅
    ├── es.py           ← испанский ✅
    ├── items_ru/en/es.py     ← названия предметов ✅
    ├── locations_ru/en/es.py ← названия/описания локаций ✅
    ├── mobs_ru/en/es.py      ← названия мобов ✅
    └── skills_ru/en/es.py    ← названия/описания скиллов ✅
```

---

## 🗄️ База данных — ключевые таблицы

```sql
players         — telegram_id, username, name, level, exp, hp, max_hp,
                  mana, max_mana, gold, strength, agility, intuition,
                  vitality, wisdom, luck, stat_points, location_id,
                  in_battle, carry_weight, lang, last_seen

items           — item_id, name, type, rarity, ...
inventory       — telegram_id, item_id, quantity
equipment       — telegram_id, slot, item_id

weapon_mastery  — PRIMARY KEY (telegram_id, weapon_id), level, exp
player_skills   — PRIMARY KEY (telegram_id, skill_id), level
skill_cooldowns — telegram_id, skill_id, turns_left

player_quests   — telegram_id, quest_id, status, step_index, progress (JSON)
active_effects  — telegram_id, effect_type, value, turns_left
```

### Важные функции БД
```python
get_connection()          # row_factory = sqlite3.Row
get_player(telegram_id)   # → Row | None
create_player(...)        # устанавливает last_seen=datetime('now')
player_exists(telegram_id)
```

---

## 🌍 Система переводов (i18n)

```python
from game.i18n import t, get_player_lang, set_player_lang, SUPPORTED_LANGS
from game.i18n import get_item_name, get_mob_name, get_location_name, get_location_desc
from game.i18n import get_skill_name, get_skill_desc

lang = get_player_lang(user.id)
text = t('battle.attack_hit', lang, damage=24)
name = get_item_name('iron_sword', lang)
name = get_mob_name('forest_wolf', lang)
name = get_location_name('village', lang)
desc = get_location_desc('village', lang)
name = get_skill_name('fireball', lang)
desc = get_skill_desc('fireball', lang)
```

### Добавление нового контента — чеклист
- Предмет → `items_data.py` + `locales/items_ru/en/es.py`
- Моб → `mobs.py` + `locales/mobs_ru/en/es.py`
- Локация → `locations.py` + `locales/locations_ru/en/es.py`
- Скилл → `skills.py` + `locales/skills_ru/en/es.py`

### Структура ключей в locales/ru.py
```
common.*        — yes/no/back/error/no_character/level/exp/gold/hp/mana/confirm
start.*         — welcome/name_taken/name_short/name_long/distribute/created
profile.*       — title/level/exp/gold/hp/mana/location/stats_title/strength/
                  agility/intuition/vitality/wisdom/luck/stat_points/
                  reset_btn/reset_ask/reset_confirm_btn/reset_cancel_btn/
                  reset_ok/reset_no_gold/reset_success/saved_ok
keyboard.*      — location/profile/inventory/skills/quests/stats/help
location.*      — safe_zone/level_range/mobs_nearby/aggressive_tag/
                  diff_easy/diff_normal/diff_hard/diff_deadly/diff_unknown/
                  attack_mob_btn/gather_title/gather_btn/go_to_btn/locked_btn/
                  shop_btn/inn_btn/quests_btn/travel_title/traveling/
                  in_battle/in_battle_block/in_battle_move/level_required/not_found
battle.*        — start/attack_btn/flee_btn/potions_btn/skills_btn/
                  attack_hit/attack_crit/mob_attack/player_dodge/mob_dodge/
                  flee_success/flee_fail/victory/levelup/death/no_potions/
                  mastery_up/skill_unlocked/stunned/effect_poison/effect_burn/
                  regen/already_over/unarmed/player_label/mob_not_found/
                  buff_defense/buff_berserk/buff_blessing/buff_regen/buff_resurrection/
                  parry_reflect/death_first_strike
inventory.*     — title/empty/tab_weapon/tab_armor/tab_potion/tab_material/
                  equip_btn/unequip_btn/use_btn/drop_btn/back_btn/
                  equipped_ok/unequipped_ok/dropped/healed/mana_restored/
                  item_not_found/weight/quantity/reqs/bonuses/damage/defense/
                  rarity_common/rarity_uncommon/rarity_rare/rarity_epic/rarity_legendary
skills.*        — title/weapon_label/mastery_level/mastery_info/skill_points/
                  branch_a/branch_b/branch_base/locked/not_learned/max_level/
                  can_upgrade/learn_btn/upgrade_btn/no_points/upgraded/
                  base_skills/back_btn/unarmed/skill_not_found/tree_btn
quests.*        — title/active/available/completed/empty_active/empty_available/
                  accept_btn/accepted/step_done/quest_done/reward_exp/reward_gold/
                  reward_item/low_level/progress/challenge_fail
settings.*      — title/language/language_set/current_lang
help.*          — title/commands
```

---

## ⚔️ Боевая система

### battle_state в context.user_data['battle']
```python
{
    'mob_id':               str,
    'mob_hp':               int,
    'mob_effects':          list,
    'player_hp':            int,
    'player_max_hp':        int,
    'player_mana':          int,
    'player_max_mana':      int,
    'player_goes_first':    bool,
    'turn':                 int,
    'log':                  list,
    'damage_taken':         int,
    'potions_used':         int,
    'skills_used':          list,
    'normal_attacks':       int,
    'buffs_used':           bool,
    'weapon_id':            str,
    'weapon_type':          str,
    'weapon_damage':        int,
    'weapon_name':          str,
    'mastery_level':        int,
    'mastery_exp':          int,
    # Баффы:
    'parry_active':         bool,
    'parry_value':          float,
    'defense_buff_turns':   int,
    'defense_buff_value':   int,
    'berserk_turns':        int,
    'berserk_damage':       int,
    'blessing_turns':       int,
    'blessing_value':       int,
    'regen_turns':          int,
    'regen_amount':         int,
    'resurrection_active':  bool,
    'resurrection_hp':      int,
}
```

### Callback паттерны
```
fight_{mob_id}                     — начать бой
fight_first_{mob_id}               — начать бой (моб первым)
battle_attack_{mob_id}             — обычная атака
battle_flee_{mob_id}               — побег
battle_potions_{mob_id}            — зелья в бою
battle_skill_{skill_id}|{mob_id}   — скилл (разделитель PIPE!)
```

### Ключевые функции
```python
process_turn(player, mob, battle_state, lang)  # lang обязателен!
mob_attack(mob, player)
apply_rewards(telegram_id, exp, gold, context) # сбрасывает КД скиллов
tick_cooldowns(telegram_id)
add_mastery_exp(telegram_id, weapon_id, amount)
```

### Важные механики
- КД скиллов сбрасываются после каждого боя в `apply_rewards`
- `weapon_name` пересчитывается при отображении через `get_item_name(weapon_id, lang)`
- Лог атак формируется в `process_turn` через `t()` — полностью локализован
- `parry` — отражает урон моба обратно, игрок урона не получает

---

## 🏃 Система агрессивных мобов

- `schedule_mob_aggro` — только из `handle_location_buttons` (переход), НЕ из `location_command`
- `aggro_attack` устанавливает `in_battle=1` перед отправкой сообщения
- `message_id` → `context.application.user_data[telegram_id]['aggro_message_id']`
- `/unstuck` снимает `in_battle=0` и удаляет агро-сообщение

---

## 📊 Система статов

```python
STAT_RESET_COST = 100  # profile.py
```

- Меню открывается всегда, даже без свободных очков
- Кнопки ➕/➖ только при наличии очков
- Confirm сохраняет распределение + оставшиеся очки (не обнуляет!)
- Сброс → все статы=1, возвращает все потраченные + свободные очки

---

## 🔮 Система навыков

### Оружие и ветки
```
iron_sword / wooden_sword → A: Натиск, B: Мастерство
dagger                    → A: Яды, B: Уклонение
short_bow                 → A: Точность, B: Мобильность
magic_staff               → A: Огонь, B: Лёд
holy_staff                → A: Свет, B: Исцеление
```

### Скиллы с особой логикой
- `parry` → `parry_active` + `parry_value` в battle_state
- `defensive_stance` → `defense_buff_turns` + `defense_buff_value`
- `berserker` → `berserk_turns` + `berserk_damage`
- `blessing` → `blessing_turns` + `blessing_value`
- `regeneration` → `regen_turns` + `regen_amount`
- `resurrection` → `resurrection_active` + `resurrection_hp`

### Мастерство XP
- +2 атака, +5 скилл, +10 убийство
- Формула: `level × 50 exp`

---

## 🌿 Ресурсы для сбора

Формат в `locations.py`: `(item_id, chance, display_name)`

```
herb_common  — 🌿 Обычная трава   (common,   sell: 3g)
herb_magic   — ✨ Магическая трава (uncommon, sell: 12g)
wood_dark    — 🌑 Тёмное дерево   (uncommon, sell: 10g)
```

---

## 🔁 Система регена

```python
REGEN_RATES = {
    'village': {'hp': 5.0, 'mana': 8.0},   # % от макс в минуту
    'default': {'hp': 1.0, 'mana': 2.0},
}
MAX_OFFLINE_MINUTES = 120
```

- Реген по `last_seen` из БД, тик каждую минуту
- `create_player` устанавливает `last_seen=datetime('now')`
- При `in_battle=1` реген не применяется

---

## 📋 Квесты (quests_data.py — написано, engine — нет)

```
⚡ challenge_clean_kill / untouchable / lightning / last_stand /
   bare_hands / skills_only / berserker
🤝 goblin_prisoner
```

Не написано: `game/quest_engine.py`, `handlers/quests.py`

---



## 💡 Как использовать

> "Вот контекст моего проекта: [CLAUDE.md]. Сегодня нужно: [задача]"

Вставляй только нужный файл, не весь проект сразу.
