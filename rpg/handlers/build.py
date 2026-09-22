"""Character Builds & Combat Identity V1 Telegram views and mutations."""

from __future__ import annotations

from html import escape
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import get_connection, get_player
from game.actor_snapshot import build_actor_snapshot, healing_power, raw_power_range
from game.build_contract import (
    BRANCH_IDENTITIES,
    BRANCH_TRADEOFFS,
    FAMILIES,
    MAX_MASTERY,
    MAX_SKILL_RANK,
    PVP_SKILL_ALLOWLIST,
    RANK_REQUIREMENTS,
    SAFE_BUILD_HUBS,
    SKILL_SPECS,
    SKILL_TREES,
    mastery_exp_needed,
    normalize_family,
    rank_mana_cost,
    rank_multiplier,
)
from game.build_progression import (
    ATTRIBUTE_KEYS,
    apply_attribute_redistribution,
    apply_family_reset,
    apply_skill_purchase,
    attribute_redistribution_preview,
    ensure_player_build_v1,
    family_skill_ranks,
    get_pending_build_notice,
    issue_family_reset_intent,
    issue_skill_purchase_intent,
)
from game.combat_identity import crit_chance
from game.i18n import get_player_lang, get_skill_desc, get_skill_name, t


_COPY = {
    "en": {
        "title": "🧭 <b>Character Build</b>", "attributes": "Attributes", "masteries": "Masteries",
        "skills": "Skill trees", "pvp": "PvP identity", "back": "Back", "confirm": "Confirm",
        "apply": "Apply", "cancel": "Cancel", "reset": "Reset family skills", "unspent": "Unspent",
        "base_effective": "base → effective", "safe_only": "Free redistribution/reset is available in a safe hub.",
        "learn": "Learn / rank up", "locked": "Locked", "ready": "Available", "max": "MAX",
        "rank": "Rank", "mastery": "Mastery", "points": "points", "cost": "MP",
        "cooldown": "cooldown", "target": "target", "school": "school", "exact": "V1 combat profile",
        "passive": "passive", "hits": "components", "utility": "utility",
        "coefficient": "power", "description": "Description", "rank_effect": "Rank effect",
        "unequip": "These requirement-invalid items will be unequipped", "none": "none",
        "changed": "Build updated.", "stale": "That build action is stale; the current view was reloaded.",
        "old": "This old button cannot mutate V1. The current build view was reloaded.",
        "pvp_copy": "PvP uses normal attack, Guard and Power Strike for every family. Only the listed family skills are enabled in V1 PvP; all other learned skills are PvE-only.",
        "normal": "Normal attack (0 MP, restores 6 MP)", "guard": "Guard (20% Ward)",
        "power": "Power Strike (12 MP, C3, 1.25P)", "available_pvp": "PvP enabled",
        "pve_only": "PvE only", "current": "equipped", "requires": "requires mastery",
        "branch_points": "capstone requires 8 other branch points", "preview": "Redistribution preview",
        "hp": "HP", "mana": "MP", "carry": "Carry", "accuracy": "Accuracy rating",
        "evasion": "Evasion rating", "crit": "Critical chance", "pdef": "Physical defense",
        "mdef": "Magic defense", "block": "Block", "magic_power": "Magic power amplification",
        "healing_power": "Healing power amplification", "attack": "Attack power",
        "healing": "Healing reference", "migration": "Your prior skill points were refunded under V1.",
        "equipment": "Equipment & comparison", "effects": "Build effects", "tradeoff": "Tradeoff",
        "no_points": "No family points", "capstone_locked": "needs 8 other points in this branch",
        "error_no_points": "No family skill points are available.",
        "error_mastery": "More family mastery is required.",
        "error_capstone": "The capstone needs 8 other points in this branch.",
        "error_max_rank": "This skill is already at maximum rank.",
        "error_safe_hub": "This build change is only available in a safe hub.",
    },
    "ru": {
        "title": "🧭 <b>Билд персонажа</b>", "attributes": "Характеристики", "masteries": "Владение",
        "skills": "Деревья навыков", "pvp": "PvP-роль", "back": "Назад", "confirm": "Подтвердить",
        "apply": "Применить", "cancel": "Отмена", "reset": "Сбросить навыки семейства", "unspent": "Свободно",
        "base_effective": "база → итог", "safe_only": "Бесплатное перераспределение и сброс доступны в безопасном городе.",
        "learn": "Изучить / повысить", "locked": "Закрыто", "ready": "Доступно", "max": "МАКС",
        "rank": "Ранг", "mastery": "Владение", "points": "очков", "cost": "МП",
        "cooldown": "перезарядка", "target": "цель", "school": "школа", "exact": "Боевой профиль V1",
        "passive": "пассивно", "hits": "компоненты", "utility": "поддержка",
        "coefficient": "сила", "description": "Описание", "rank_effect": "Эффект ранга",
        "unequip": "Предметы с нарушенными требованиями будут сняты", "none": "нет",
        "changed": "Билд обновлён.", "stale": "Действие устарело; открыт актуальный билд.",
        "old": "Старая кнопка не меняет V1. Открыт актуальный билд.",
        "pvp_copy": "В PvP всем доступны обычная атака, Защита и Силовой удар. Только перечисленные семейные навыки разрешены в PvP V1; остальные изученные навыки — только PvE.",
        "normal": "Обычная атака (0 МП, восстанавливает 6 МП)", "guard": "Защита (20% Ward)",
        "power": "Силовой удар (12 МП, C3, 1.25P)", "available_pvp": "Доступно в PvP",
        "pve_only": "Только PvE", "current": "экипировано", "requires": "нужно владение",
        "branch_points": "капстоун требует 8 очков в других навыках ветки", "preview": "Предпросмотр перераспределения",
        "hp": "ОЗ", "mana": "МП", "carry": "Груз", "accuracy": "Рейтинг точности",
        "evasion": "Рейтинг уклонения", "crit": "Шанс крита", "pdef": "Физическая защита",
        "mdef": "Магическая защита", "block": "Блок", "magic_power": "Усиление магии",
        "healing_power": "Усиление лечения", "attack": "Сила атаки",
        "healing": "База лечения", "migration": "Прежние очки навыков возвращены по правилам V1.",
        "equipment": "Экипировка и сравнение", "effects": "Эффекты билда", "tradeoff": "Компромисс",
        "no_points": "Нет очков семейства", "capstone_locked": "нужно 8 других очков в этой ветке",
        "error_no_points": "Нет свободных очков навыков этого семейства.",
        "error_mastery": "Нужно повысить владение этим семейством.",
        "error_capstone": "Для капстоуна нужно 8 других очков в этой ветке.",
        "error_max_rank": "Навык уже достиг максимального ранга.",
        "error_safe_hub": "Этот билд можно изменить только в безопасном городе.",
    },
    "es": {
        "title": "🧭 <b>Configuración del personaje</b>", "attributes": "Atributos", "masteries": "Maestrías",
        "skills": "Árboles de habilidades", "pvp": "Identidad JcJ", "back": "Atrás", "confirm": "Confirmar",
        "apply": "Aplicar", "cancel": "Cancelar", "reset": "Reiniciar habilidades de familia", "unspent": "Sin gastar",
        "base_effective": "base → efectivo", "safe_only": "La redistribución y el reinicio gratuitos están disponibles en una ciudad segura.",
        "learn": "Aprender / mejorar", "locked": "Bloqueado", "ready": "Disponible", "max": "MÁX",
        "rank": "Rango", "mastery": "Maestría", "points": "puntos", "cost": "PM",
        "cooldown": "recarga", "target": "objetivo", "school": "escuela", "exact": "Perfil de combate V1",
        "passive": "pasiva", "hits": "componentes", "utility": "utilidad",
        "coefficient": "potencia", "description": "Descripción", "rank_effect": "Efecto del rango",
        "unequip": "Se desequiparán estos objetos cuyos requisitos ya no se cumplen", "none": "ninguno",
        "changed": "Configuración actualizada.", "stale": "La acción caducó; se recargó la configuración actual.",
        "old": "El botón antiguo no puede cambiar V1. Se recargó la vista actual.",
        "pvp_copy": "En JcJ todas las familias usan ataque normal, Guardia y Golpe Poderoso. Solo las habilidades familiares indicadas están habilitadas en JcJ V1; las demás son solo JcE.",
        "normal": "Ataque normal (0 PM, recupera 6 PM)", "guard": "Guardia (20% de Ward)",
        "power": "Golpe Poderoso (12 PM, C3, 1.25P)", "available_pvp": "Habilitada en JcJ",
        "pve_only": "Solo JcE", "current": "equipado", "requires": "requiere maestría",
        "branch_points": "la culminación requiere 8 puntos en las otras habilidades de la rama", "preview": "Vista previa de redistribución",
        "hp": "PV", "mana": "PM", "carry": "Carga", "accuracy": "Índice de precisión",
        "evasion": "Índice de evasión", "crit": "Probabilidad crítica", "pdef": "Defensa física",
        "mdef": "Defensa mágica", "block": "Bloqueo", "magic_power": "Amplificación mágica",
        "healing_power": "Amplificación de curación", "attack": "Poder de ataque",
        "healing": "Referencia de curación", "migration": "Tus puntos de habilidad anteriores se devolvieron con V1.",
        "equipment": "Equipo y comparación", "effects": "Efectos de la configuración", "tradeoff": "Desventaja",
        "no_points": "No hay puntos de familia", "capstone_locked": "necesita 8 puntos distintos en esta rama",
        "error_no_points": "No quedan puntos de habilidad de esta familia.",
        "error_mastery": "Se necesita más maestría con esta familia.",
        "error_capstone": "La culminación necesita 8 puntos distintos en esta rama.",
        "error_max_rank": "Esta habilidad ya tiene el rango máximo.",
        "error_safe_hub": "Este cambio de configuración solo está disponible en una ciudad segura.",
    },
}

_BRANCH_COPY = {
    "en": {
        identity: (identity.replace("_", " ").title(), tradeoff)
        for identity, tradeoff in BRANCH_TRADEOFFS.items()
    },
    "ru": {
        "guardian": ("Страж", "Принимает давление, выживает и отвечает; урон ниже, чем у Авангарда."),
        "vanguard": ("Авангард", "Поддерживает натиск и общие окна атаки; не может бросить Вызов ради группы."),
        "executioner": ("Палач", "Рассекает переднюю линию и добивает раненых; слабее против одной здоровой цели."),
        "blademaster": ("Мастер клинка", "Набирает и тратит Поток; защитные окна конечны."),
        "berserker": ("Берсерк", "Рискует частью ОЗ без смертельного исхода ради урона и личного восстановления."),
        "ravager": ("Разоритель", "Кровотечение и разрушение брони требуют времени на цели."),
        "venom": ("Яд", "Накапливает яд на стойких целях и поглощает его; короткий бой может закончиться раньше."),
        "shadow": ("Тень", "Зарабатывает Открытие и тратит его на быстрый урон по одной цели."),
        "sniper": ("Снайпер", "Готовит выстрел по важной задней цели; хуже с ограниченным уроном по площади."),
        "ranger": ("Следопыт", "Дешёвые манёвры, Замедление и ограниченный урон по площади; слабее точечный взрыв."),
        "destruction": ("Разрушение", "Дорогая артиллерия; меняет безопасность Контроля и экономность жезла на урон."),
        "control": ("Контроль", "Прерывает угрозы и разбивает Охлаждённых; подготовка снижает немедленный урон."),
        "arcanist": ("Арканист", "Экономные короткие циклы заклинаний с конечным ресурсом Эха."),
        "duelist": ("Дуэлянт", "Принимает один попавший обмен и отвечает; уклонение не создаёт Ответный удар."),
        "healer": ("Целитель", "Лечит союзников и предотвращает смерть; в одиночку полагается на обычные атаки."),
        "dawn": ("Рассвет", "Общий светлый натиск с попутным лечением; меньше предотвращения, чем у Целителя."),
        "protector": ("Защитник", "Закрывает выбранного союзника от конкретного удара; мало группового лечения."),
        "judgment": ("Правосудие", "Личный урон отмеченной цели и заслуженное восстановление; без вампиризма группы."),
        "enchanter": ("Чародей", "Конечная защита, передача ресурса и рассеивание; без крупного прямого лечения."),
        "synthesis": ("Синтез", "Замкнутый цикл магии и света через Горение и Благодать; без заимствования чар."),
    },
    "es": {
        "guardian": ("Guardián", "Atrae presión, sobrevive y responde; inflige menos daño que Vanguardia."),
        "vanguard": ("Vanguardia", "Mantiene la presión y aperturas compartidas; no puede Desafiar por el grupo."),
        "executioner": ("Verdugo", "Barre el frente y remata heridos; rinde peor contra un objetivo sano."),
        "blademaster": ("Maestro de espada", "Mantiene y gasta Flujo; sus ventanas defensivas son limitadas."),
        "berserker": ("Berserker", "Arriesga PV sin morir a cambio de daño y recuperación personal."),
        "ravager": ("Devastador", "Sangrado y ruptura de armadura necesitan tiempo sobre el objetivo."),
        "venom": ("Veneno", "Acumula veneno en objetivos resistentes y lo consume; los combates cortos pueden acabar antes."),
        "shadow": ("Sombra", "Obtiene una Apertura y la gasta en daño inmediato a un solo objetivo."),
        "sniper": ("Francotirador", "Prepara impactos contra la retaguardia prioritaria; tiene menos presión de área."),
        "ranger": ("Explorador", "Escaramuzas baratas, Lentitud y área limitada; menor explosión prioritaria."),
        "destruction": ("Destrucción", "Artillería cara; cambia la seguridad de Control y eficiencia de varita por daño."),
        "control": ("Control", "Interrumpe peligros y rompe objetivos Enfriados; preparar reduce el daño inmediato."),
        "arcanist": ("Arcanista", "Ciclos breves y eficientes con un recurso de Eco limitado."),
        "duelist": ("Duelista", "Invita un intercambio acertado y responde; esquivar no genera Réplica."),
        "healer": ("Sanador", "Cura aliados y evita muertes; en solitario depende del ataque normal."),
        "dawn": ("Alba", "Luz ofensiva compartida con sustento incidental; menos prevención que Sanador."),
        "protector": ("Protector", "Protege a un aliado concreto de un golpe; poca curación grupal directa."),
        "judgment": ("Juicio", "Daño personal al objetivo marcado y sustento ganado; sin robo de vida grupal."),
        "enchanter": ("Encantador", "Defensa finita, reparto de recursos y disipación; sin gran cura directa."),
        "synthesis": ("Síntesis", "Ciclo cerrado de magia/luz con Quemadura y Gracia; sin tomar otros conjuros."),
    },
}

_ATTRIBUTE_LABELS = {
    "en": {"strength": "Strength", "agility": "Agility", "intuition": "Intuition", "vitality": "Vitality", "wisdom": "Wisdom", "luck": "Luck"},
    "ru": {"strength": "Сила", "agility": "Ловкость", "intuition": "Интуиция", "vitality": "Живучесть", "wisdom": "Мудрость", "luck": "Удача"},
    "es": {"strength": "Fuerza", "agility": "Agilidad", "intuition": "Intuición", "vitality": "Vitalidad", "wisdom": "Sabiduría", "luck": "Suerte"},
}

_TARGET_LABELS = {
    "en": {"S": "one enemy", "F": "front line", "B": "priority back line", "A": "all enemies", "2x2": "up to two per line", "Ally": "one ally", "AllyOrEnemy": "one ally or enemy", "Attacker": "the attacker", "Self": "self", "Party": "party"},
    "ru": {"S": "один враг", "F": "передняя линия", "B": "приоритетная задняя линия", "A": "все враги", "2x2": "до двух в каждой линии", "Ally": "один союзник", "AllyOrEnemy": "один союзник или враг", "Attacker": "атакующий", "Self": "на себя", "Party": "группа"},
    "es": {"S": "un enemigo", "F": "línea delantera", "B": "retaguardia prioritaria", "A": "todos los enemigos", "2x2": "hasta dos por línea", "Ally": "un aliado", "AllyOrEnemy": "un aliado o enemigo", "Attacker": "el atacante", "Self": "propio", "Party": "grupo"},
}

_SCHOOL_LABELS = {
    "en": {"physical": "physical", "magic": "magic", "holy": "holy", "mixed": "mixed", "poison": "poison", "support": "support"},
    "ru": {"physical": "физическая", "magic": "магическая", "holy": "священная", "mixed": "смешанная", "poison": "яд", "support": "поддержка"},
    "es": {"physical": "física", "magic": "mágica", "holy": "sagrada", "mixed": "mixta", "poison": "veneno", "support": "apoyo"},
}

_KIND_LABELS = {
    "en": {"barrier": "Barrier", "buff": "enhancement", "cleanse": "cleanse", "covenant": "Covenant", "damage": "damage", "dispel": "dispel", "heal": "healing", "hostile_effect": "hostile effect", "hot": "healing over time", "mana": "mana recovery", "parry": "Parry", "passive": "passive", "rage": "Rage", "setup": "setup", "ward": "Ward"},
    "ru": {"barrier": "Барьер", "buff": "усиление", "cleanse": "очищение", "covenant": "Завет", "damage": "урон", "dispel": "рассеивание", "heal": "лечение", "hostile_effect": "враждебный эффект", "hot": "периодическое лечение", "mana": "восстановление маны", "parry": "Парирование", "passive": "пассивный эффект", "rage": "Ярость", "setup": "подготовка", "ward": "Защита"},
    "es": {"barrier": "Barrera", "buff": "mejora", "cleanse": "limpieza", "covenant": "Pacto", "damage": "daño", "dispel": "disipación", "heal": "curación", "hostile_effect": "efecto hostil", "hot": "curación periódica", "mana": "recuperación de maná", "parry": "Parada", "passive": "efecto pasivo", "rage": "Furia", "setup": "preparación", "ward": "Guardia"},
}

_REJECTION_COPY = {
    "no_points": "error_no_points",
    "mastery_required": "error_mastery",
    "capstone_branch_points_required": "error_capstone",
    "max_rank": "error_max_rank",
    "safe_hub_required": "error_safe_hub",
}


def _c(lang: str, key: str) -> str:
    return _COPY.get(lang, _COPY["en"])[key]


def _label(table: dict[str, dict[str, str]], lang: str, key: str) -> str:
    localized = table.get(lang, table["en"])
    return localized.get(key, table["en"].get(key, key.replace("_", " ").title()))


def _skill_profile(spec: Any, lang: str, rank: int) -> str:
    parts = [_label(_KIND_LABELS, lang, spec.kind)]
    if spec.power:
        ranked_power = float(spec.power) * rank_multiplier(max(1, int(rank)))
        power = f"{ranked_power:.4f}".rstrip("0").rstrip(".").removeprefix("0")
        parts.append(f"{_c(lang, 'coefficient')}: {power}P")
    if spec.hits > 1:
        parts.append(f"{_c(lang, 'hits')}: {spec.hits}")
    if spec.utility:
        parts.append(_c(lang, "utility"))
    return " · ".join(parts)


def _localized_rejection(lang: str, reason: Any) -> str:
    key = _REJECTION_COPY.get(str(reason or ""))
    return _c(lang, key) if key else _c(lang, "stale")


def _consume_notice(player_id: int, lang: str) -> str:
    notice = get_pending_build_notice(player_id, consume=True)
    if not notice:
        return ""
    lines = [f"ℹ️ {_c(lang, 'migration')}"]
    if notice.get("staff_normalized"):
        staff_copy = {
            "en": "Magic Staff base damage is now 9–14; your instance, tier and rolls were preserved.",
            "ru": "Базовый урон Магического посоха теперь 9–14; экземпляр, ранг и модификаторы сохранены.",
            "es": "El daño base del Bastón Mágico ahora es 9–14; se conservaron tu objeto, rango y atributos.",
        }
        lines.append(staff_copy.get(lang, staff_copy["en"]))
    if notice.get("old_fight_ended"):
        ended_copy = {
            "en": "An old-rules fight ended without rewards or penalties; its latest HP/MP was preserved.",
            "ru": "Бой по старым правилам завершён без наград и штрафов; последние ОЗ/МП сохранены.",
            "es": "Un combate con reglas antiguas terminó sin premios ni penalizaciones; se conservaron los PV/PM.",
        }
        lines.append(ended_copy.get(lang, ended_copy["en"]))
    return "\n".join(lines)


def _family_name(family: str, lang: str) -> str:
    value = t(f"profile.identity.weapon_profile.{family}", lang)
    return family.replace("_", " ").title() if value.startswith("[") else value


def _load_model(player_id: int) -> dict[str, Any]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM players WHERE telegram_id=?", (player_id,)).fetchone()
        if not row:
            raise ValueError("no_character")
        ensure_player_build_v1(player_id, conn=conn)
        snapshot = build_actor_snapshot(player_id, conn=conn)
        player = dict(conn.execute("SELECT * FROM players WHERE telegram_id=?", (player_id,)).fetchone())
        masteries = {
            str(row["weapon_id"]): dict(row)
            for row in conn.execute(
                "SELECT * FROM weapon_mastery WHERE telegram_id=? AND model_version=1 ORDER BY weapon_id",
                (player_id,),
            )
        }
        conn.commit()
        return {"player": player, "snapshot": snapshot, "masteries": masteries}
    finally:
        conn.close()


def build_main_view(player_id: int, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    model = _load_model(player_id)
    player, snapshot = model["player"], model["snapshot"]
    family = snapshot["family"]
    attack_low, attack_high = raw_power_range(snapshot)
    ranks = snapshot.get("skill_ranks") or {}
    split = {branch: sum(int(ranks.get(skill_id, 0)) for skill_id in SKILL_TREES.get(family, {}).get(branch, ())) for branch in ("A", "B")}
    active_branch = "A" if split["A"] >= split["B"] else "B"
    identity = BRANCH_IDENTITIES.get(family, {}).get(active_branch)
    branch_name, branch_tradeoff = _BRANCH_COPY.get(lang, _BRANCH_COPY["en"]).get(identity, ("Unarmed", _c(lang, "power")))
    learned = sorted(
        ((int(rank), skill_id) for skill_id, rank in ranks.items() if int(rank) > 0),
        reverse=True,
    )[:3]
    lines = [
        _c(lang, "title"),
        f"⚔️ {_family_name(family, lang)}" + (f" · M{snapshot['mastery_level']}" if family in FAMILIES else ""),
        f"❤️ {snapshot['hp']}/{snapshot['max_hp']}  🔷 {snapshot['mana']}/{snapshot['max_mana']}",
        f"🎯 {_c(lang, 'attack')}: {attack_low}–{attack_high}  ✨ {_c(lang, 'healing')}: {healing_power(snapshot)}",
        f"📦 {_c(lang, 'unspent')}: {player['stat_points']}/{player['attribute_budget']}",
        f"🌿 A {split['A']}◆ · B {split['B']}◆ · {escape(branch_name)}",
        f"✨ {_c(lang, 'effects')}: " + (
            ", ".join(f"{escape(get_skill_name(skill_id, lang))} R{rank}" for rank, skill_id in learned)
            if learned else _c(lang, "power")
        ),
        f"⚖️ {_c(lang, 'tradeoff')}: {escape(branch_tradeoff)}",
    ]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📊 {_c(lang, 'attributes')}", callback_data="bv_attr")],
        [InlineKeyboardButton(f"🏹 {_c(lang, 'skills')}", callback_data="bv_families")],
        [InlineKeyboardButton(f"📈 {_c(lang, 'masteries')}", callback_data="bv_masteries")],
        [InlineKeyboardButton(f"🎒 {_c(lang, 'equipment')}", callback_data="inv_tab_weapon")],
        [InlineKeyboardButton(f"⚔️ {_c(lang, 'pvp')}", callback_data="bv_pvp")],
    ])
    return "\n\n".join(lines), keyboard


def _new_attribute_draft(model: dict[str, Any]) -> dict[str, int]:
    return {key: int(model["player"][key]) for key in ATTRIBUTE_KEYS}


def build_attributes_view(
    player_id: int, lang: str, *, draft: dict[str, int] | None = None,
) -> tuple[str, InlineKeyboardMarkup, dict[str, int]]:
    model = _load_model(player_id)
    snapshot, player = model["snapshot"], model["player"]
    draft = dict(draft or _new_attribute_draft(model))
    budget = int(player["attribute_budget"])
    spent = sum(max(0, int(draft[key]) - 1) for key in ATTRIBUTE_KEYS)
    remaining = budget - spent
    labels = _ATTRIBUTE_LABELS.get(lang, _ATTRIBUTE_LABELS["en"])
    lines = [
        f"📊 <b>{_c(lang, 'attributes')}</b>",
        f"{_c(lang, 'unspent')}: <b>{remaining}</b>",
        _c(lang, "safe_only"),
    ]
    keyboard = []
    for key in ATTRIBUTE_KEYS:
        effective = int(snapshot[key])
        base = int(draft[key])
        lines.append(f"{escape(labels[key])}: <b>{base}</b> → {effective - int(player[key]) + base}")
        keyboard.append([
            InlineKeyboardButton("−", callback_data=f"bv_ad_{key}"),
            InlineKeyboardButton(f"{labels[key]} {base}", callback_data="bv_noop"),
            InlineKeyboardButton("+", callback_data=f"bv_ai_{key}"),
        ])
    lines.extend([
        "",
        f"❤️ {_c(lang, 'hp')}: {100 + 18 * draft['vitality']} + gear",
        f"🔷 {_c(lang, 'mana')}: {50 + 12 * draft['wisdom']} + gear",
        f"🎒 {_c(lang, 'carry')}: {20 + 5 * draft['strength']}",
        f"🎯 {_c(lang, 'accuracy')}: 100 + 2×AGI + INT + gear",
        f"💨 {_c(lang, 'evasion')}: 100 + 2×AGI + LUCK + gear",
        f"💥 {_c(lang, 'crit')}: min(35%, .35×LUCK + .05×AGI)",
    ])
    keyboard.extend([
        [InlineKeyboardButton(f"✅ {_c(lang, 'confirm')}", callback_data="bv_attr_preview")],
        [InlineKeyboardButton(f"↩️ {_c(lang, 'back')}", callback_data="bv_main")],
    ])
    return "\n".join(lines), InlineKeyboardMarkup(keyboard), draft


def build_masteries_view(player_id: int, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    model = _load_model(player_id)
    equipped = model["snapshot"]["family"]
    lines = [f"📈 <b>{_c(lang, 'masteries')}</b>"]
    keyboard = []
    for family in FAMILIES:
        mastery = model["masteries"].get(family)
        if not mastery and family != equipped:
            continue
        mastery = mastery or {"level": 1, "exp": 0, "skill_points": 2}
        needed = mastery_exp_needed(int(mastery["level"]))
        suffix = f" · {_c(lang, 'current')}" if family == equipped else ""
        lines.append(
            f"{_family_name(family, lang)}: M{mastery['level']} "
            f"{mastery['exp']}/{needed if int(mastery['level']) < MAX_MASTERY else 'MAX'} · "
            f"{mastery['skill_points']} {_c(lang, 'points')}{suffix}"
        )
        keyboard.append([InlineKeyboardButton(
            f"{_family_name(family, lang)} · M{mastery['level']}", callback_data=f"bv_family_{family}",
        )])
    keyboard.append([InlineKeyboardButton(f"↩️ {_c(lang, 'back')}", callback_data="bv_main")])
    return "\n\n".join(lines), InlineKeyboardMarkup(keyboard)


def build_families_view(player_id: int, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    model = _load_model(player_id)
    equipped = model["snapshot"]["family"]
    lines = [f"🏹 <b>{_c(lang, 'skills')}</b>"]
    keyboard = []
    for family in FAMILIES:
        mastery = model["masteries"].get(family)
        if not mastery and family != equipped:
            continue
        level = int((mastery or {}).get("level", 1))
        points = int((mastery or {}).get("skill_points", 2))
        suffix = " ✅" if family == equipped else ""
        keyboard.append([InlineKeyboardButton(
            f"{_family_name(family, lang)} · M{level} · {points}◆{suffix}",
            callback_data=f"bv_family_{family}",
        )])
    if equipped == "unarmed" and not keyboard:
        lines.append(_c(lang, "power"))
    keyboard.append([InlineKeyboardButton(f"↩️ {_c(lang, 'back')}", callback_data="bv_main")])
    return "\n\n".join(lines), InlineKeyboardMarkup(keyboard)


def build_family_view(player_id: int, family: str, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    family = normalize_family(family)
    if family not in FAMILIES:
        return build_families_view(player_id, lang)
    model = _load_model(player_id)
    mastery = model["masteries"].get(family) or {"level": 1, "exp": 0, "skill_points": 2}
    conn = get_connection()
    try:
        ranks = family_skill_ranks(player_id, family, conn=conn)
    finally:
        conn.close()
    lines = [
        f"⚔️ <b>{escape(_family_name(family, lang))}</b>",
        f"{_c(lang, 'mastery')} M{mastery['level']} · {mastery['skill_points']} {_c(lang, 'points')}",
    ]
    keyboard = []
    for branch in ("A", "B"):
        identity = BRANCH_IDENTITIES[family][branch]
        identity_name, tradeoff = _BRANCH_COPY.get(lang, _BRANCH_COPY["en"])[identity]
        branch_spend = sum(int(ranks.get(item, 0)) for item in SKILL_TREES[family][branch][:-1])
        lines.extend(["", f"<b>{branch} · {escape(identity_name)}</b>", escape(tradeoff)])
        for skill_id in SKILL_TREES[family][branch]:
            spec = SKILL_SPECS[skill_id]
            rank = int(ranks.get(skill_id, 0))
            required = spec.unlock_mastery if rank == 0 else RANK_REQUIREMENTS.get(rank + 1, MAX_MASTERY + 1)
            if rank >= MAX_SKILL_RANK:
                state = _c(lang, "max")
            elif int(mastery["level"]) < required:
                state = f"{_c(lang, 'locked')} M{required}"
            elif int(mastery["skill_points"]) < 1:
                state = _c(lang, "no_points")
            elif rank == 0 and spec.unlock_mastery == 8 and branch_spend < 8:
                state = f"{_c(lang, 'locked')} {branch_spend}/8"
            else:
                state = _c(lang, "ready")
            lines.append(f"{'✅' if rank else '○'} {escape(get_skill_name(skill_id, lang))} · {rank}/3 · {state}")
            keyboard.append([InlineKeyboardButton(
                f"{get_skill_name(skill_id, lang)} · {rank}/3", callback_data=f"bv_skill_{skill_id}",
            )])
    keyboard.extend([
        [InlineKeyboardButton(f"♻️ {_c(lang, 'reset')}", callback_data=f"bv_reset_{family}")],
        [InlineKeyboardButton(f"↩️ {_c(lang, 'back')}", callback_data="bv_families")],
    ])
    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def build_skill_view(player_id: int, skill_id: str, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    spec = SKILL_SPECS.get(skill_id)
    if not spec:
        return build_families_view(player_id, lang)
    model = _load_model(player_id)
    mastery = model["masteries"].get(spec.family) or {"level": 1, "skill_points": 2}
    conn = get_connection()
    try:
        ranks = family_skill_ranks(player_id, spec.family, conn=conn)
        rank = ranks.get(skill_id, 0)
    finally:
        conn.close()
    next_rank = min(3, rank + 1)
    required = spec.unlock_mastery if rank == 0 else RANK_REQUIREMENTS.get(next_rank, MAX_MASTERY + 1)
    lines = [
        f"{escape(get_skill_name(skill_id, lang))}",
        f"{_c(lang, 'rank')}: <b>{rank}/3</b>",
        f"{_c(lang, 'cost')}: <b>{rank_mana_cost(spec, max(1, next_rank))}</b> · {_c(lang, 'cooldown')}: <b>{spec.cooldown if spec.cooldown is not None else _c(lang, 'passive')}</b>",
        f"{_c(lang, 'target')}: <b>{escape(_label(_TARGET_LABELS, lang, spec.target))}</b> · {_c(lang, 'school')}: <b>{escape(_label(_SCHOOL_LABELS, lang, spec.school or 'support'))}</b>",
        f"{_c(lang, 'description')}: {escape(get_skill_desc(skill_id, lang))}",
        f"{_c(lang, 'rank_effect')} {max(1, next_rank)} · {_c(lang, 'exact')}: {escape(_skill_profile(spec, lang, max(1, next_rank)))}",
        f"PvP: {_c(lang, 'available_pvp') if skill_id in PVP_SKILL_ALLOWLIST else _c(lang, 'pve_only')}",
    ]
    keyboard = []
    if rank < 3:
        branch_spend = sum(int(ranks.get(item, 0)) for item in SKILL_TREES[spec.family][spec.branch][:-1])
        legal_level = (
            int(mastery["level"]) >= required
            and int(mastery["skill_points"]) > 0
            and not (rank == 0 and spec.unlock_mastery == 8 and branch_spend < 8)
        )
        button = f"➕ {_c(lang, 'learn')} · M{required} · 1◆"
        keyboard.append([InlineKeyboardButton(button, callback_data=f"bv_buy_{skill_id}" if legal_level else "bv_noop")])
    keyboard.append([InlineKeyboardButton(f"↩️ {_c(lang, 'back')}", callback_data=f"bv_family_{spec.family}")])
    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def build_pvp_view(player_id: int, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    model = _load_model(player_id)
    family = model["snapshot"]["family"]
    ranks = model["snapshot"]["skill_ranks"]
    lines = [f"⚔️ <b>{_c(lang, 'pvp')}</b>", _c(lang, "pvp_copy"), "", _c(lang, "normal"), _c(lang, "guard"), _c(lang, "power")]
    for skill_id in sorted(PVP_SKILL_ALLOWLIST - {"power_strike"}):
        learned = skill_id in ranks and SKILL_SPECS[skill_id].family == family
        lines.append(f"{'✅' if learned else '○'} {escape(get_skill_name(skill_id, lang))} · {escape(_family_name(SKILL_SPECS[skill_id].family, lang))}")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(f"↩️ {_c(lang, 'back')}", callback_data="bv_main")]])
    return "\n".join(lines), keyboard


async def _send_view(update: Update, text: str, keyboard: InlineKeyboardMarkup) -> None:
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
        await update.callback_query.answer()
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")


async def build_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = get_player_lang(user.id)
    if not get_player(user.id):
        await update.message.reply_text(t("common.no_character", lang))
        return
    text, keyboard = build_main_view(user.id, lang)
    notice = _consume_notice(user.id, lang)
    if notice:
        text = notice + "\n\n" + text
    await _send_view(update, text, keyboard)


async def build_attributes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = get_player_lang(user.id)
    if not get_player(user.id):
        await update.message.reply_text(t("common.no_character", lang))
        return
    text, keyboard, draft = build_attributes_view(user.id, lang)
    notice = _consume_notice(user.id, lang)
    if notice:
        text = notice + "\n\n" + text
    context.user_data["build_v1_attributes"] = draft
    await _send_view(update, text, keyboard)


async def build_skills_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = get_player_lang(user.id)
    if not get_player(user.id):
        await update.message.reply_text(t("common.no_character", lang))
        return
    text, keyboard = build_families_view(user.id, lang)
    notice = _consume_notice(user.id, lang)
    if notice:
        text = notice + "\n\n" + text
    await _send_view(update, text, keyboard)


async def handle_build_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    lang = get_player_lang(user.id)
    data = str(query.data or "")
    if data == "bv_noop":
        await query.answer()
        return
    if data == "bv_main":
        text, keyboard = build_main_view(user.id, lang)
    elif data == "bv_attr":
        text, keyboard, draft = build_attributes_view(user.id, lang)
        context.user_data["build_v1_attributes"] = draft
    elif data.startswith(("bv_ai_", "bv_ad_")):
        draft = context.user_data.get("build_v1_attributes")
        if not isinstance(draft, dict):
            _, _, draft = build_attributes_view(user.id, lang)
        key = data[6:]
        if key not in ATTRIBUTE_KEYS:
            await query.answer()
            return
        model = _load_model(user.id)
        budget = int(model["player"]["attribute_budget"])
        spent = sum(int(draft[item]) - 1 for item in ATTRIBUTE_KEYS)
        if data.startswith("bv_ai_") and spent < budget and int(draft[key]) < 100:
            draft[key] = int(draft[key]) + 1
        elif data.startswith("bv_ad_") and int(draft[key]) > 1:
            draft[key] = int(draft[key]) - 1
        context.user_data["build_v1_attributes"] = draft
        text, keyboard, _ = build_attributes_view(user.id, lang, draft=draft)
    elif data == "bv_attr_preview":
        draft = context.user_data.get("build_v1_attributes") or _new_attribute_draft(_load_model(user.id))
        preview = attribute_redistribution_preview(user.id, draft)
        if not preview.get("success"):
            await query.answer(_c(lang, "stale"), show_alert=True)
            text, keyboard, draft = build_attributes_view(user.id, lang)
            context.user_data["build_v1_attributes"] = draft
        else:
            unequips = preview["unequips"]
            item_lines = [f"• {escape(item['name'])} ({escape(item['slot'])})" for item in unequips] or [f"• {_c(lang, 'none')}"]
            text = "\n".join([
                f"📊 <b>{_c(lang, 'preview')}</b>",
                f"{_c(lang, 'unspent')}: {preview['unspent']}",
                f"{_c(lang, 'hp')}: {preview['max_hp']} + gear",
                f"{_c(lang, 'mana')}: {preview['max_mana']} + gear",
                f"{_c(lang, 'carry')}: {preview['carry_weight']}", "",
                f"<b>{_c(lang, 'unequip')}:</b>", *item_lines,
            ])
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ {_c(lang, 'apply')}", callback_data=f"bv_attr_apply_{preview['token']}")],
                [InlineKeyboardButton(f"↩️ {_c(lang, 'cancel')}", callback_data="bv_attr")],
            ])
    elif data.startswith("bv_attr_apply_"):
        result = apply_attribute_redistribution(user.id, data.removeprefix("bv_attr_apply_"))
        await query.answer(_c(lang, "changed") if result.get("success") else _c(lang, "stale"), show_alert=True)
        text, keyboard, draft = build_attributes_view(user.id, lang)
        context.user_data["build_v1_attributes"] = draft
    elif data == "bv_masteries":
        text, keyboard = build_masteries_view(user.id, lang)
    elif data == "bv_families":
        text, keyboard = build_families_view(user.id, lang)
    elif data.startswith("bv_family_"):
        text, keyboard = build_family_view(user.id, data.removeprefix("bv_family_"), lang)
    elif data.startswith("bv_skill_"):
        text, keyboard = build_skill_view(user.id, data.removeprefix("bv_skill_"), lang)
    elif data.startswith("bv_buy_"):
        skill_id = data.removeprefix("bv_buy_")
        spec = SKILL_SPECS.get(skill_id)
        issued = issue_skill_purchase_intent(user.id, spec.family if spec else "", skill_id)
        if not issued.get("success") or not issued.get("legal"):
            reason = issued.get("reason")
            if issued.get("success") and not issued.get("legal"):
                if int(issued.get("points", 0)) < 1:
                    reason = "no_points"
                elif int(issued.get("mastery_level", 0)) < int(issued.get("mastery_required", 0)):
                    reason = "mastery_required"
                else:
                    reason = "capstone_branch_points_required"
            await query.answer(_localized_rejection(lang, reason), show_alert=True)
            text, keyboard = build_skill_view(user.id, skill_id, lang)
        else:
            text, _ = build_skill_view(user.id, skill_id, lang)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ {_c(lang, 'confirm')}", callback_data=f"bv_apply_{issued['token']}")],
                [InlineKeyboardButton(f"↩️ {_c(lang, 'cancel')}", callback_data=f"bv_skill_{skill_id}")],
            ])
    elif data.startswith("bv_apply_"):
        result = apply_skill_purchase(user.id, data.removeprefix("bv_apply_"))
        await query.answer(_c(lang, "changed") if result.get("success") else _c(lang, "stale"), show_alert=True)
        if result.get("success"):
            text, keyboard = build_family_view(user.id, result["family"], lang)
        else:
            text, keyboard = build_families_view(user.id, lang)
    elif data.startswith("bv_reset_apply_"):
        result = apply_family_reset(user.id, data.removeprefix("bv_reset_apply_"))
        await query.answer(_c(lang, "changed") if result.get("success") else _c(lang, "stale"), show_alert=True)
        text, keyboard = build_family_view(user.id, result.get("family", ""), lang) if result.get("success") else build_families_view(user.id, lang)
    elif data.startswith("bv_reset_"):
        family = data.removeprefix("bv_reset_")
        issued = issue_family_reset_intent(user.id, family)
        if not issued.get("success"):
            await query.answer(_localized_rejection(lang, issued.get("reason")), show_alert=True)
            text, keyboard = build_family_view(user.id, family, lang)
        else:
            text = f"♻️ <b>{_c(lang, 'reset')}</b>\n{_family_name(family, lang)} · {issued['refund']} {_c(lang, 'points')}"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ {_c(lang, 'confirm')}", callback_data=f"bv_reset_apply_{issued['token']}")],
                [InlineKeyboardButton(f"↩️ {_c(lang, 'cancel')}", callback_data=f"bv_family_{family}")],
            ])
    elif data == "bv_pvp":
        text, keyboard = build_pvp_view(user.id, lang)
    else:
        await query.answer()
        return
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    if not data.startswith(("bv_attr_apply_", "bv_apply_", "bv_reset_apply_")):
        await query.answer()


async def handle_legacy_build_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Retired stat/skill callbacks are refresh-only under the V1 authority."""
    query = update.callback_query
    lang = get_player_lang(query.from_user.id)
    if str(query.data).startswith("sk_"):
        text, keyboard = build_families_view(query.from_user.id, lang)
    else:
        text, keyboard, draft = build_attributes_view(query.from_user.id, lang)
        context.user_data["build_v1_attributes"] = draft
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    await query.answer(_c(lang, "old"), show_alert=True)
