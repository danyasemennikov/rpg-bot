"""Frozen Character Builds & Combat Identity V1 product constants.

This module is deliberately data-only.  Combat, Telegram previews, persistence,
PvP and the balance harness all consume the same catalogue instead of carrying
their own copies of unlocks, costs or coefficients.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


RULES_VERSION: Final = "character_builds_combat_identity_v1"
MIGRATION_KEY: Final = "character_builds_combat_identity_v1"
MASTERY_MODEL_VERSION: Final = 1
MAX_MASTERY: Final = 20
MAX_SKILL_RANK: Final = 3
RANK_MULTIPLIERS: Final = (0.0, 1.0, 1.15, 1.30)
RANK_PERCENT_BONUS: Final = (0.0, 0.0, 0.03, 0.06)
SKILL_UNLOCK_LEVELS: Final = (1, 2, 3, 5, 8)
RANK_REQUIREMENTS: Final = {1: 1, 2: 4, 3: 10}
SAFE_BUILD_HUBS: Final = frozenset({
    "capital_city",
    "hub_westwild",
    "hub_frostspine",
    "hub_ashen_ruins",
    "hub_mireveil",
    "hub_sunscar",
})

FAMILIES: Final = (
    "sword_1h",
    "sword_2h",
    "axe_2h",
    "daggers",
    "bow",
    "magic_staff",
    "wand",
    "holy_staff",
    "holy_rod",
    "tome",
)

FAMILY_ALIASES: Final = {
    "practice_sword": "sword_1h",
    "wooden_sword": "sword_1h",
    "iron_sword": "sword_1h",
    "dagger": "daggers",
    "short_bow": "bow",
    "practice_bow": "bow",
    "practice_staff": "magic_staff",
    "fists": "unarmed",
    "bare_hands": "unarmed",
    "hands": "unarmed",
    "base": "unarmed",
}

BRANCH_IDENTITIES: Final = {
    "sword_1h": {"A": "guardian", "B": "vanguard"},
    "sword_2h": {"A": "executioner", "B": "blademaster"},
    "axe_2h": {"A": "berserker", "B": "ravager"},
    "daggers": {"A": "venom", "B": "shadow"},
    "bow": {"A": "sniper", "B": "ranger"},
    "magic_staff": {"A": "destruction", "B": "control"},
    "wand": {"A": "arcanist", "B": "duelist"},
    "holy_staff": {"A": "healer", "B": "dawn"},
    "holy_rod": {"A": "protector", "B": "judgment"},
    "tome": {"A": "enchanter", "B": "synthesis"},
}

BRANCH_TRADEOFFS: Final = {
    "guardian": "Attract pressure, survive it and retaliate; damage is lower than Vanguard.",
    "vanguard": "Sustained pressure and shared openings; cannot challenge for the party.",
    "executioner": "Front-line cleave and wounded finishers; inefficient against one healthy target.",
    "blademaster": "Maintain and spend Flow; defensive windows are finite.",
    "berserker": "Voluntary nonlethal HP risk for damage and personal recovery.",
    "ravager": "Bleed and armor breaking need time on target.",
    "venom": "Build poison on durable targets, then consume it; short fights may end first.",
    "shadow": "Earn an Opening and spend it on immediate single-target burst.",
    "sniper": "Prepare and hit priority back-line targets; less bounded area pressure.",
    "ranger": "Cheap skirmishing, Slow and bounded area damage; lower priority burst.",
    "destruction": "Expensive spell artillery; trades Control safety and wand efficiency for damage.",
    "control": "Interrupt danger and shatter Chilled targets; setup lowers immediate damage.",
    "arcanist": "Efficient short spell cycles with a finite Echo resource.",
    "duelist": "Invite one landed exchange and answer it; evasion does not create Reprisal.",
    "healer": "Actual ally recovery and death prevention; solo progress leans on normal attacks.",
    "dawn": "Shared offensive light with incidental sustain; less prevention than Healer.",
    "protector": "Protect a named ally from a specific hit; little raw group healing.",
    "judgment": "Personal marked-target damage and earned sustain; no party lifesteal.",
    "enchanter": "Finite defense, resource sharing and dispel; no large direct heal.",
    "synthesis": "A closed magic/holy cycle using Burn and Grace; no arbitrary spell borrowing.",
}


@dataclass(frozen=True)
class SkillSpec:
    skill_id: str
    family: str
    branch: str
    position: int
    mana: int
    cooldown: int | None
    target: str
    school: str | None
    kind: str
    power: float = 0.0
    hits: int = 1
    utility: bool = False
    description: str = ""

    @property
    def unlock_mastery(self) -> int:
        return SKILL_UNLOCK_LEVELS[self.position]

    @property
    def passive(self) -> bool:
        return self.cooldown is None


def _s(
    skill_id: str,
    family: str,
    branch: str,
    position: int,
    mana: int,
    cooldown: int | None,
    target: str,
    school: str | None,
    kind: str,
    power: float = 0.0,
    hits: int = 1,
    description: str = "",
    *,
    utility: bool = False,
) -> SkillSpec:
    return SkillSpec(
        skill_id, family, branch, position, mana, cooldown, target, school,
        kind, power, hits, utility, description,
    )


# Target codes: S single enemy, F front line, B back-line priority, A all
# enemies, 2x2 bounded two-per-line, Ally/Self/Party friendly recipients.
_SPECS = [
    # Sword 1H — Guardian / Vanguard
    _s("sword_rush", "sword_1h", "A", 0, 8, 2, "S", "physical", "damage", .95, description=".95P; Challenge the hit target for 2 opportunities."),
    _s("defensive_stance", "sword_1h", "A", 1, 10, 4, "Self", None, "ward", description="Ward 30% for 2 opportunities."),
    _s("shield_bash", "sword_1h", "A", 2, 12, 3, "S", "physical", "damage", .85, description=".85P; Weakness 20% for 2 opportunities on hit; shield optional."),
    _s("parry", "sword_1h", "A", 3, 12, 4, "Self", None, "parry", description="First landed direct action is reduced 60% after mitigation/block; retaliate .45P."),
    _s("counter", "sword_1h", "A", 4, 0, None, "Attacker", "physical", "passive", .40, description="While own Ward or Parry is active, first landed direct action each enemy side retaliates .40P."),
    _s("driving_slash", "sword_1h", "B", 0, 8, 2, "S", "physical", "damage", 1.10, description="1.10P; grant Driving, making the next landed normal attack +20%."),
    _s("expose_guard", "sword_1h", "B", 1, 12, 3, "S", "physical", "damage", .80, description=".80P; shared Exposure 15% for 2 opportunities after the hit."),
    _s("press_the_line", "sword_1h", "B", 2, 10, 4, "S", "physical", "damage", .95, description=".95P; self Attack Up 15% for 2 opportunities on hit."),
    _s("punishing_cut", "sword_1h", "B", 3, 16, 3, "S", "physical", "damage", 1.25, description="1.25P, plus .55P if the target was already Exposed."),
    _s("vanguard_surge", "sword_1h", "B", 4, 22, 5, "S", "physical", "damage", 1.75, description="1.75P; if already Exposed add .40P and gain Ward 20% for 2 opportunities."),
    # Sword 2H — Executioner / Blademaster
    _s("heavy_swing", "sword_2h", "A", 0, 12, 2, "F", "physical", "damage", .85, description=".85P to each selected front-line target."),
    _s("armor_split", "sword_2h", "A", 1, 12, 3, "S", "physical", "damage", 1.0, description="Open Guard: 1.00P and Exposure 15% for 2 opportunities."),
    _s("executioners_focus", "sword_2h", "A", 2, 8, 3, "Self", None, "setup", description="Next successful direct damage action gains +25% damage."),
    _s("cleave_through", "sword_2h", "A", 3, 20, 4, "F", "physical", "damage", 1.15, description="1.15P each; +.30P for targets starting at or below 50% HP."),
    _s("executioners_stroke", "sword_2h", "A", 4, 24, 5, "S", "physical", "damage", 1.80, description="1.80P; +1.00P if target starts at or below 35% HP."),
    _s("battle_stance", "sword_2h", "B", 0, 10, 4, "Self", None, "buff", description="Attack Up 15%, Ward 15% for 2 opportunities, and Flow."),
    _s("twin_cut", "sword_2h", "B", 1, 10, 2, "S", "physical", "damage", 1.35, 2, "Total 1.35P in 2 components; grant or refresh Flow."),
    _s("riposte_step", "sword_2h", "B", 2, 10, 4, "Self", None, "buff", description="+40 evasion for 2 opportunities and Flow."),
    _s("flowing_combo", "sword_2h", "B", 3, 16, 3, "S", "physical", "damage", 1.20, 2, "Total 1.20P; with Flow add .65P and consume Flow on hit."),
    _s("masters_sequence", "sword_2h", "B", 4, 24, 5, "S", "physical", "damage", 2.05, 3, "Total 2.05P; with Flow add .55P, Ward 25% for 1 opportunity, consume Flow."),
    # Axe — Berserker / Ravager
    _s("rage_call", "axe_2h", "A", 0, 4, 4, "Self", None, "rage", description="Pay 8% current HP nonlethally; Attack Up 25% and +15% received direct damage for 2 opportunities."),
    _s("savage_chop", "axe_2h", "A", 1, 8, 2, "S", "physical", "damage", 1.02, description="1.02P; while own Rage is active add .35P."),
    _s("blooded_resolve", "axe_2h", "A", 2, 12, 5, "Self", None, "heal", description="Heal 25+2.5×VIT, capped at 25% max HP."),
    _s("frenzy_chain", "axe_2h", "A", 3, 18, 4, "S", "physical", "damage", 1.84, 3, "Total 1.84P; during Rage add .70P and consume Rage on hit."),
    _s("last_roar", "axe_2h", "A", 4, 24, 6, "S", "physical", "damage", 1.62, description="1.62P; at ≤40% HP add .85P; heal 15% actual damage, capped at 12% max HP."),
    _s("bleeding_cut", "axe_2h", "B", 0, 8, 2, "S", "physical", "damage", .73, description=".73P and Bleed .20P for 3 ticks."),
    _s("sunder_armor", "axe_2h", "B", 1, 12, 3, "S", "physical", "damage", .77, description=".77P and fixed 30% physical-defense break for 3 opportunities."),
    _s("brutal_overhead", "axe_2h", "B", 2, 14, 3, "S", "physical", "damage", 1.45, description="1.45P with fixed 25% physical-rating penetration."),
    _s("reopen_wounds", "axe_2h", "B", 3, 16, 3, "S", "physical", "damage", 1.38, description="1.38P; own Bleed adds .45P and refreshes its original 3-tick snapshot."),
    _s("ravage", "axe_2h", "B", 4, 24, 5, "S", "physical", "damage", 2.07, 2, "Total 2.07P; +.40P for own Bleed and +.40P for physical-defense break."),
    # Daggers — Venom / Shadow
    _s("envenom_blades", "daggers", "A", 0, 6, 3, "Self", None, "setup", description="Next landed dagger action adds one Poison stack of .25P for 3 ticks."),
    _s("toxic_cut", "daggers", "A", 1, 8, 2, "S", "physical", "damage", .90, description=".90P and one Poison stack of .20P for 3 ticks."),
    _s("crippling_venom", "daggers", "A", 2, 10, 3, "S", "physical", "damage", .70, description=".70P; Slow and Weakness 15% for 2 opportunities."),
    _s("widows_kiss", "daggers", "A", 3, 16, 3, "S", "physical", "damage", 1.15, description="1.15P plus .20P per own Poison stack, up to three."),
    _s("rupture_toxins", "daggers", "A", 4, 22, 5, "S", "poison", "damage", 1.38, description="1.38P direct; consume own Poison and deal 80% of its remaining raw ticks."),
    _s("smoke_bomb", "daggers", "B", 0, 8, 4, "Self", None, "buff", description="+40 evasion for 2 opportunities and Opening."),
    _s("quick_slice", "daggers", "B", 1, 6, 2, "S", "physical", "damage", 1.10, description="1.10P; with Opening add .35P and consume it."),
    _s("feint_step", "daggers", "B", 2, 8, 3, "S", "physical", "damage", .65, description=".65P; on hit gain +20 accuracy for 2 opportunities and Opening."),
    _s("backstab", "daggers", "B", 3, 16, 3, "S", "physical", "damage", 1.49, description="1.49P; with Opening add .80P and consume it."),
    _s("shadow_chain", "daggers", "B", 4, 24, 5, "S", "physical", "damage", 1.90, 3, "Total 1.90P; Opening adds .80P and +40 evasion for 1 opportunity, then is consumed."),
    # Bow — Sniper / Ranger
    _s("hunters_mark", "bow", "A", 0, 6, 3, "B", None, "hostile_effect", description="Mark for 3 opportunities; own direct damage +15% (+3pp/rank)."),
    _s("aimed_shot", "bow", "A", 1, 12, 2, "B", "physical", "damage", 1.45, description="1.45P with +20 accuracy for this action."),
    _s("steady_aim", "bow", "A", 2, 6, 3, "Self", None, "setup", description="Next landed bow action gets +25% damage (+3pp/rank) and +20 accuracy."),
    _s("piercing_arrow", "bow", "A", 3, 18, 3, "B", "physical", "damage", 1.65, description="1.65P with fixed 35% physical-rating penetration."),
    _s("deadeye", "bow", "A", 4, 26, 5, "B", "physical", "damage", 2.05, description="Guaranteed hit, 2.05P; +.55P against own Hunter's Mark."),
    _s("quick_shot", "bow", "B", 0, 6, 1, "S", "physical", "damage", 1.05, description="1.05P; no normal-attack mana restoration."),
    _s("hamstring_arrow", "bow", "B", 1, 10, 3, "S", "physical", "damage", .85, description=".85P and Slow for 2 opportunities."),
    _s("reposition", "bow", "B", 2, 8, 4, "Self", None, "buff", description="+45 evasion for 2 opportunities."),
    _s("volley_step", "bow", "B", 3, 14, 3, "S", "physical", "damage", 1.35, 2, "Total 1.35P; add .50P if target is already Slowed."),
    _s("rain_of_barbs", "bow", "B", 4, 24, 5, "2x2", "physical", "damage", .95, description=".95P each; +.20P if already Slowed, then Slow for 2 opportunities."),
    # Magic staff — Destruction / Control
    _s("fireball", "magic_staff", "A", 0, 12, 2, "S", "magic", "damage", 1.15, description="1.15P and Burn .15P for 2 ticks."),
    _s("arcane_surge", "magic_staff", "A", 1, 8, 3, "Self", None, "setup", description="Next landed magic-staff action gets +25% damage."),
    _s("flame_wave", "magic_staff", "A", 2, 22, 4, "A", "magic", "damage", .85, description=".85P each and same-source Burn .10P for 2 ticks."),
    _s("arcane_lance", "magic_staff", "A", 3, 18, 3, "B", "magic", "damage", 1.55, description="1.55P with fixed 25% magic-rating penetration."),
    _s("cataclysm", "magic_staff", "A", 4, 30, 6, "A", "magic", "damage", 1.30, description="1.30P each; +.40P against own magic Burn."),
    _s("frost_bolt", "magic_staff", "B", 0, 8, 2, "S", "magic", "damage", .95, description=".95P, Slow 2 and Chilled 3 opportunities."),
    _s("ice_shackles", "magic_staff", "B", 1, 14, 4, "S", "magic", "damage", .45, description=".45P, Freeze one eligible opportunity and Chilled 3; Resolve may reject Freeze."),
    _s("mana_shield", "magic_staff", "B", 2, 14, 4, "Self", None, "barrier", description="Barrier .80H for 2 opportunities, capped at 35% max HP."),
    _s("shatter", "magic_staff", "B", 3, 16, 3, "S", "magic", "damage", 1.05, description="1.05P; own Chilled adds .70P and is consumed."),
    _s("absolute_zero", "magic_staff", "B", 4, 28, 6, "A", "magic", "damage", .90, description=".90P each, Slow 2 and Chilled 3; Freeze only the selected active target."),
    # Wand — Arcanist / Duelist
    _s("arcane_bolt", "wand", "A", 0, 4, 1, "S", "magic", "damage", 1.0, description="1.00P."),
    _s("spell_echo", "wand", "A", 1, 6, 3, "Self", None, "setup", description="Next landed wand action gains +25% direct damage."),
    _s("quick_channel", "wand", "A", 2, 0, 4, "Self", None, "mana", description="Restore 20 MP, scaled by rank and capped by missing MP."),
    _s("overload", "wand", "A", 3, 14, 3, "S", "magic", "damage", 1.50, description="1.50P; Echo adds its +25% and another .25P, then is consumed."),
    _s("arcane_barrage", "wand", "A", 4, 20, 5, "S", "magic", "damage", 1.90, 3, "Total 1.90P; if Echo existed restore 8 MP and consume it."),
    _s("dueling_ward", "wand", "B", 0, 8, 3, "Self", None, "ward", description="Ward 25% through next enemy side; first landed action grants one Reprisal."),
    _s("hex_bolt", "wand", "B", 1, 8, 2, "S", "magic", "damage", 1.0, description="1.00P and Weakness 15% for 2 opportunities."),
    _s("mana_feint", "wand", "B", 2, 10, 3, "S", "magic", "damage", .80, description=".80P, Slow 2 and restore 4 MP on hit."),
    _s("counterpulse", "wand", "B", 3, 16, 3, "S", "magic", "damage", 1.15, description="1.15P; Reprisal adds .75P and is consumed."),
    _s("duel_arc", "wand", "B", 4, 24, 5, "S", "magic", "damage", 1.70, description="1.70P; Reprisal adds .70P and grants .45H Barrier, then is consumed."),
    # Holy staff — Healer / Dawn
    _s("heal", "holy_staff", "A", 0, 12, 2, "Ally", None, "heal", description="Heal 1.00H immediately."),
    _s("regeneration", "holy_staff", "A", 1, 14, 4, "Ally", None, "hot", description="Heal .35H for 3 recipient-side ticks; same source refreshes."),
    _s("cleanse", "holy_staff", "A", 2, 10, 3, "Ally", None, "cleanse", description="Remove Poison, Bleed, Burn and Weakness from the selected ally.", utility=True),
    _s("blessing", "holy_staff", "A", 3, 16, 4, "Party", None, "buff", description="Party Attack Up 12% for 2 recipient opportunities."),
    _s("resurrection", "holy_staff", "A", 4, 28, 8, "Ally", None, "covenant", description="Life Covenant: first lethal loss within 3 opportunities leaves 1 HP and heals .80H once/encounter."),
    _s("smite", "holy_staff", "B", 0, 8, 2, "S", "holy", "damage", 1.0, description="1.00P; heal self 15% actual damage, capped at 8% max HP."),
    _s("judgment_mark", "holy_staff", "B", 1, 10, 3, "S", "holy", "damage", .70, description=".70P; Dawn Mark grants party +12% direct damage for 3 opportunities."),
    _s("radiant_ward", "holy_staff", "B", 2, 12, 4, "Ally", None, "ward", description="Ward 20% for 2 opportunities."),
    _s("sanctified_burst", "holy_staff", "B", 3, 18, 3, "S", "holy", "damage", 1.30, description="1.30P; +.45P on Dawn Mark; heal lowest-HP living ally .25H."),
    _s("halo_of_dawn", "holy_staff", "B", 4, 28, 6, "A", "holy", "damage", .95, description=".95P each; +.25P on Dawn Mark; if any hit, heal each living ally .25H once."),
    # Holy rod — Protector / Judgment
    _s("sacred_shield", "holy_rod", "A", 0, 10, 3, "Ally", None, "barrier", description="Barrier .75H for 2 opportunities, capped at 35% recipient max HP."),
    _s("mend_self", "holy_rod", "A", 1, 12, 4, "Self", None, "heal", description="Heal self .65H."),
    _s("aura_of_resolve", "holy_rod", "A", 2, 14, 4, "Ally", None, "ward", description="Ward 20% for 2 opportunities; another ally also gets one Interception."),
    _s("aegis_strike", "holy_rod", "A", 3, 14, 3, "S", "holy", "damage", 1.10, description="1.10P; if caster has Barrier, add .45P."),
    _s("guardian_light", "holy_rod", "A", 4, 26, 6, "Party", None, "barrier", description="Party Barrier .55H for 2 opportunities; caster Ward 25% for 2."),
    _s("judgment", "holy_rod", "B", 0, 6, 3, "S", "holy", "damage", .75, description=".75P and own Judgment 3; normal attacks add .15P and heal 10% damage."),
    _s("radiant_strike", "holy_rod", "B", 1, 8, 2, "S", "holy", "damage", 1.10, description="1.10P; against own Judgment heal 20% damage, capped at 10% max HP."),
    _s("rod_consecration", "holy_rod", "B", 2, 12, 3, "S", "holy", "damage", .70, description=".70P and holy Burn .20P for 3 ticks."),
    _s("punish_the_wicked", "holy_rod", "B", 3, 16, 3, "S", "holy", "damage", 1.35, description="1.35P; own Judgment adds .55P."),
    _s("final_verdict", "holy_rod", "B", 4, 24, 5, "S", "holy", "damage", 1.80, description="1.80P; Judgment adds .60P and 25% damage heal, then is consumed."),
    # Tome — Enchanter / Synthesis
    _s("arcane_shield", "tome", "A", 0, 8, 3, "Ally", None, "barrier", description="Barrier .60H for 2 opportunities, capped at 35% recipient max HP."),
    _s("weaken", "tome", "A", 1, 8, 3, "S", "magic", "hostile_effect", description="Hit-check then Weakness 20% for 2 opportunities; no damage."),
    _s("insight", "tome", "A", 2, 8, 4, "Ally", None, "mana", description="Restore 22 MP after paying the caster cost."),
    _s("dispel_script", "tome", "A", 3, 10, 3, "AllyOrEnemy", "magic", "dispel", description="Ally: remove Weakness/Slow/Exposure. Enemy: hit-check and remove Ward/Barrier/Attack Up.", utility=True),
    _s("grand_enchantment", "tome", "A", 4, 24, 6, "Party", None, "buff", description="Party Ward 20% for 2 opportunities and restore 14 MP each."),
    _s("hybrid_missile", "tome", "B", 0, 6, 1, "S", "magic", "damage", 1.0, description="1.00P magic."),
    _s("borrowed_flame", "tome", "B", 1, 10, 3, "S", "magic", "damage", .85, description=".85P and own magic Burn .15P for 3 ticks."),
    _s("borrowed_grace", "tome", "B", 2, 12, 3, "S", "holy", "damage", .75, description=".75P; heal self .35H and grant Grace; Grace gives next normal tome attack +20%."),
    _s("synthesis", "tome", "B", 3, 18, 3, "S", "mixed", "damage", 1.20, description="1.20P half magic/holy; own Burn and Grace each add .35P; consume Grace."),
    _s("forbidden_thesis", "tome", "B", 4, 26, 5, "S", "mixed", "damage", 1.70, description="1.70P split; Grace adds .55P and .35H; consume Grace and own Burn for 60% remaining ticks."),
]

SKILL_SPECS: Final = {spec.skill_id: spec for spec in _SPECS}
SKILL_TREES: Final = {
    family: {
        branch: tuple(
            spec.skill_id
            for spec in sorted(_SPECS, key=lambda item: item.position)
            if spec.family == family and spec.branch == branch
        )
        for branch in ("A", "B")
    }
    for family in FAMILIES
}

POWER_STRIKE: Final = SkillSpec(
    "power_strike", "universal", "base", 0, 12, 3, "S", "weapon",
    "damage", 1.25, description="1.25P with the equipped weapon school.",
)

# Exactly the historical rows archived and retired by the global migration.
RETIRED_SKILL_IDS: Final = frozenset({
    "disarm", "sword_ultimate_b", "poison_blade", "envenom",
    "venom_storm", "dagger_ult_a", "death_dance", "dagger_ult_b",
    "eagle_eye", "bow_ult_a", "retreat", "arrow_rain", "kite",
    "bow_ult_b", "berserker", "burning_ground", "fire_shield", "meteor",
    "ice_lance", "ice_chains", "blizzard", "holy_bolt", "consecration",
    "divine_wrath",
})

PVP_SKILL_ALLOWLIST: Final = frozenset({
    "power_strike", "quick_shot", "fireball", "smite",
})


def normalize_family(value: str | None) -> str:
    key = str(value or "unarmed")
    return FAMILY_ALIASES.get(key, key)


def mastery_exp_needed(level: int) -> int:
    level = max(1, min(MAX_MASTERY, int(level)))
    return 0 if level >= MAX_MASTERY else 20 * level


def legal_family_budget(mastery_level: int) -> int:
    return min(MAX_MASTERY, max(1, int(mastery_level))) + 1


def rank_multiplier(rank: int) -> float:
    return RANK_MULTIPLIERS[max(0, min(MAX_SKILL_RANK, int(rank)))]


def rank_percent(base: float, rank: int) -> float:
    return float(base) + RANK_PERCENT_BONUS[max(0, min(MAX_SKILL_RANK, int(rank)))]


def rank_mana_cost(spec: SkillSpec, rank: int) -> int:
    if not spec.utility:
        return spec.mana
    return max(0, spec.mana - (2 * (max(1, min(3, int(rank))) - 1)))


def validate_frozen_catalogue() -> tuple[str, ...]:
    errors: list[str] = []
    if len(SKILL_SPECS) != 100:
        errors.append(f"expected 100 family skills, got {len(SKILL_SPECS)}")
    seen: set[str] = set()
    for family in FAMILIES:
        for branch in ("A", "B"):
            ids = SKILL_TREES[family][branch]
            if len(ids) != 5:
                errors.append(f"{family}/{branch} must contain five skills")
            if ids and tuple(SKILL_SPECS[item].unlock_mastery for item in ids) != SKILL_UNLOCK_LEVELS:
                errors.append(f"{family}/{branch} unlock schedule drift")
            for skill_id in ids:
                if skill_id in seen:
                    errors.append(f"duplicate skill {skill_id}")
                seen.add(skill_id)
    return tuple(errors)


assert not validate_frozen_catalogue(), validate_frozen_catalogue()
